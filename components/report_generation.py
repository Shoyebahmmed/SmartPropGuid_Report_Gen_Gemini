import datetime
import json
import re
import streamlit as st
from components.config import SessionState, AppConfig
from components.services import DataService, GeminiService, AnthropicService, HtagService, PdfService, TemplateService
from components.ui_utils import UiHelper
from components.variable_mapper import build_standardized_property_payload

class ReportGenerationComponent:
    def __init__(self, session: SessionState, config: AppConfig, 
                 data_service: DataService, gemini_service: GeminiService, 
                 anthropic_service: AnthropicService, htag_service: HtagService,
                 pdf_service: PdfService, template_service: TemplateService):
        self.session = session
        self.config = config
        self.data_service = data_service
        self.gemini_service = gemini_service
        self.anthropic_service = anthropic_service
        self.htag_service = htag_service
        self.pdf_service = pdf_service
        self.template_service = template_service
        
        self.priorities_list = [
            "Good schools nearby",
            "Public transport access",
            "Shopping centres nearby",
            "Parks and green spaces",
            "Hospital or medical centre nearby",
            "Low flood risk",
            "Low bushfire risk",
            "Quiet neighbourhood",
            "Investment potential",
            "Family friendly area",
            "Close to CBD"
        ]

    def render(self, custom_prompt: str):
        st.markdown("### Generate and Review Report")
        
        # Fetch form values from session state
        suburb = st.session_state.get("suburb", "")
        property_type = st.session_state.get("property_type", "House")
        budget = st.session_state.get("budget", "")
        intention = st.session_state.get("intention", "")
        
        selected_priorities = []
        for i, priority in enumerate(self.priorities_list):
            if st.session_state.get(f"priority_{i}"):
                selected_priorities.append(priority)

        # AI Provider Selection Card
        st.markdown('<div class="zinc-card">', unsafe_allow_html=True)
        prov_col1, prov_col2 = st.columns([2, 1])
        
        with prov_col1:
            st.markdown("<h4>AI Engine & Generation Settings</h4>", unsafe_allow_html=True)
            provider_choice = st.radio(
                "Select Generative AI Model Provider:",
                options=["Google Gemini (gemini-2.5-flash)", f"Anthropic Claude ({self.config.claude_model})"],
                index=0 if "Gemini" in self.session.ai_provider else 1,
                horizontal=True,
                key="ai_provider_radio"
            )
            self.session.ai_provider = "Google Gemini" if "Gemini" in provider_choice else "Anthropic Claude"
            
        with prov_col2:
            st.markdown("<h4>Active Data Source</h4>", unsafe_allow_html=True)
            st.info(f"Using: **{self.session.data_source_mode}**")
        st.markdown('</div>', unsafe_allow_html=True)

        # UI Layout: Settings Summary Card & Generation Button
        bg_subtle = "#0c0c0f" if self.session.theme == "dark" else "#f9fafb"
        border_color = UiHelper.get_border_color(self.session.theme)
        
        sum_col1, sum_col2 = st.columns([3, 1])
        with sum_col1:
            st.markdown(f"""
            <div style="background-color: {bg_subtle}; padding: 1rem; border-radius: 8px; border: 1px solid {border_color}; font-size: 0.88rem;">
                <strong>Target Area:</strong> {suburb if suburb else "Not specified"} | 
                <strong>Property Type:</strong> {property_type} | 
                <strong>Budget:</strong> {budget} | 
                <strong>Purpose:</strong> {intention} | 
                <strong>AI Model:</strong> {self.session.ai_provider}<br>
                <strong>Key Preferences Selected:</strong> {', '.join(selected_priorities) if selected_priorities else "None"}
            </div>
            """, unsafe_allow_html=True)
            
        with sum_col2:
            generate_btn = st.button("✨ Generate AI Report", type="primary", use_container_width=True)

        if generate_btn:
            # Check API keys before execution
            is_anthropic = "Anthropic" in self.session.ai_provider
            if is_anthropic and not self.config.anthropic_api_key:
                st.error("❌ Cannot generate report: ANTHROPIC_API_KEY is missing. Please add it to your Cred.env file.")
                return
            elif not is_anthropic and not self.config.api_key:
                st.error("❌ Cannot generate report: GEMINI_API_KEY is missing. Please add it to your Cred.env file.")
                return

            # Extract postcode & state from suburb string
            postcode_str = ""
            state_str = ""
            suburb_clean = suburb
            if suburb:
                pm = re.search(r"\b\d{3,4}\b", suburb.strip())
                postcode_str = pm.group(0) if pm else ""
                
                sm = re.search(r"\b(VIC|NSW|QLD|WA|SA|TAS|ACT|NT)\b", suburb.strip(), re.IGNORECASE)
                state_str = sm.group(0).upper() if sm else ""
                
                if postcode_str:
                    suburb_clean = suburb_clean.replace(postcode_str, "")
                if state_str:
                    suburb_clean = re.sub(rf"\b{state_str}\b", "", suburb_clean, flags=re.IGNORECASE)
                suburb_clean = re.sub(r"[,\-\s]+", " ", suburb_clean).strip()

            loader_placeholder = UiHelper.start_loader(f"{self.session.ai_provider} is analyzing suburb data and composing report...", self.session.theme)
            
            try:
                listings_records = []
                extra_context = {}

                # Branch by Data Source Mode
                is_htag_mode = "HTAG" in self.session.data_source_mode
                raw_api_payload = None
                
                if is_htag_mode:
                    # Retrieve or fetch HTAG data
                    htag_data = self.session.htag_data
                    if not htag_data and suburb_clean:
                        try:
                            htag_data = self.htag_service.fetch_suburb_analysis(
                                suburb=suburb_clean,
                                state=state_str,
                                postcode=postcode_str,
                                property_type=property_type
                            )
                            self.session.htag_data = htag_data
                        except Exception as htag_err:
                            st.warning(f"⚠️ Could not auto-fetch HTAG API data: {htag_err}")

                    raw_api_payload = htag_data
                else:
                    # Upload File Mode (CSV / Excel)
                    df_active = self.session.df_data
                    if df_active is None and postcode_str:
                        try:
                            df_loaded, filename = self.data_service.auto_load_postcode_dataset(postcode_str)
                            if df_loaded is not None:
                                df_active = df_loaded
                                self.session.df_data = df_loaded
                                st.info(f"ℹ️ Automatically loaded postcode dataset: `{filename}`")
                        except Exception as e:
                            st.warning(f"⚠️ Could not auto-load postcode dataset: {e}")

                    df_filtered = None
                    if df_active is not None:
                        df_filtered = self.data_service.filter_property_data(
                            df_active, 
                            postcode_str, 
                            budget, 
                            property_type
                        )

                    if df_filtered is not None and len(df_filtered) > 0:
                        for _, r in df_filtered.iterrows():
                            listings_records.append({
                                "address": r.get('Address') or r.get('Property address') or '',
                                "price": r.get('Purchase price') or r.get('Price') or '',
                            })
                        extra_context["manual_dataset_sample"] = df_filtered.head(10).to_dict(orient="records")

                # Structure incoming data into 41 standard matched_variables and extra_variables
                standardized_payload = build_standardized_property_payload(
                    suburb=suburb_clean,
                    state=state_str,
                    postcode=postcode_str,
                    property_type=property_type,
                    raw_api_data=raw_api_payload,
                    extra_context=extra_context
                )

                # Assemble prompt asking AI for STRUCTURED JSON ONLY
                full_prompt = f"""<system_prompt>
<role>
You are the primary AI Engine for SmartPropGuide. Your task is to process a pre-formatted JSON data payload containing standardized property variables (`matched_variables`) alongside optional extra variables (`extra_variables`), and generate the structured text and metrics required for the report template.
</role>

<input_data_structure>
{json.dumps(standardized_payload, indent=2, ensure_ascii=False)}
</input_data_structure>

<client_context>
1. Property Type: {property_type}
2. Target Suburb/Area: {suburb}
3. Budget Range: {budget}
4. Purchase Intention: {intention}
5. Key Client Priorities: {', '.join(selected_priorities) if selected_priorities else "General property investment and lifestyle evaluation"}
6. Pre-Sales Operator Instructions: {custom_prompt}
7. Report Date: {datetime.date.today().strftime("%B %d, %Y")}
</client_context>

<processing_rules>
1. STRICT DATA GROUNDING & ZERO HALLUCINATION:
   - Rely strictly and exclusively on the data provided within the input JSON payload (matched_variables and extra_variables).
   - Do NOT search online, use external knowledge, or invent/hallucinate any property or market numbers.

2. MISSING DATA HANDLING & SMART INFERENCE:
   - Check `matched_variables` first.
   - If a standard key in `matched_variables` is `null` or missing, inspect `extra_variables` to see if the missing value can be logically derived, estimated, or calculated (e.g., deriving averages, medians, or ranges from min/max metrics, counts, or related fields available in `extra_variables`).
   - If a missing value CANNOT be derived from `extra_variables`, leave or output it as `null` / unavailable. Do not make up replacement values.

3. DYNAMIC EXTRA DATA UTILIZATION:
   - Incorporate any remaining relevant data points from `extra_variables` into the appropriate report narrative or text blocks (e.g., adding unique infrastructure, zoning, or amenity insights).

4. OUTPUT INSTRUCTIONS:
   - Generate ONLY a single valid JSON object containing the required report data structure below.
   - Do NOT wrap in conversational intro/outro text, meta-commentary, or HTML markup.
   - Maintain an objective, professional, and analytical tone tailored to first-home buyers and property investors.
</processing_rules>

<required_json_schema>
Return a single JSON object with EXACTLY these top-level keys matching the report template requirements:
"median_price" (string formatted e.g. "$1,658,000" or derived from matched_variables), "clearance_rate" (string e.g. "68%"), "days_on_market" (string e.g. "34 days"),
"snapshot" (object: match_score int, stats list of {{value, label, highlight (boolean true or false)}}, summary string),
"affordability" (object: summary string, stats list of {{value,label}}, trends list of {{label,value,direction: up|down|neutral}}),
"rental" (object: summary string, metrics list of {{label,value,bar_percent 0-100}}),
"budget" (object: summary string, units_percent int 0-100, pills list of {{value,label,style: gold|navy|outline}}),
"growth" (object: summary string, category string, metrics list of {{value,label,bar_percent 0-100}}),
"infrastructure" (object: summary string, entries list of {{year,title,tag_type: transport|amenity|community,tag_label,status_type: active|planned,status_label,value}}),
"price_history" (object: y_axis_labels list of 4 strings low-to-high, points list of ~7 {{year,value (numeric, in millions)}}, legend list of {{color,label}}),
"lifestyle" (object: summary string, scores list of {{value 0-100,label,sublabel,color}}),
"amenities" (list of {{icon (single emoji),count,label}}),
"day_in_life" (list of {{time,text}}),
"community" (object: summary string, stats list of {{value,label}}, age_distribution list of {{label,value 0-100,dark bool}}, owner_vs_renter list of exactly 2 {{value 0-100,label,color}}, household_composition list of {{label,value 0-100,dark bool}}, type_summary string),
"schools" (object: pending_notice string or empty, summary string, list of {{type,name,distance,score 0-100}}, family_fit list of {{label,value 0-100,dark bool}}, verdict string),
"risk" (object: summary string, entries list of {{level: low|medium|high,title,detail,badge}}, disclaimer string),
"verdict" (object: match_score int 0-100, subscores list of {{label,value 0-100,good bool}}, strengths list of strings, considerations list of strings, next_step string, comparable_suburbs list of {{name,postcode,price}}),
"listings" ({json.dumps(listings_records)} -- reformat/annotate these into a list of {{address,price,badge_score,availability}} if available, else provide representative market listing examples).
</required_json_schema>
</system_prompt>"""

                # Execute with selected AI Service
                if is_anthropic:
                    report_data = self.anthropic_service.generate_report_data(full_prompt)
                else:
                    report_data = self.gemini_service.generate_report_data(full_prompt)

                # Ensure snapshot highlight flag defaults safely
                snapshot = report_data.get("snapshot", {})
                if isinstance(snapshot, dict):
                    for stat in snapshot.get("stats", []):
                        if isinstance(stat, dict):
                            stat.setdefault("highlight", False)

                # Set verified deterministic fields
                report_data["suburb"] = suburb_clean or report_data.get("suburb", suburb)
                report_data["postcode"] = postcode_str or report_data.get("postcode", "")
                report_data["state_display"] = state_str if state_str else "AUSTRALIA"

                # Render HTML with Jinja2 template
                report_html = self.template_service.render(self.session.template_content, report_data)
                self.session.generated_report_html = report_html
                st.success(f"✅ Report generated successfully using {self.session.ai_provider}!")

            except Exception as e:
                st.error(f"❌ Failed to generate report: {e}")
            finally:
                UiHelper.stop_loader(loader_placeholder)

        # Render generated HTML report & PDF compilation controls
        if self.session.generated_report_html:
            st.markdown("### Generated Report Preview")
            html_code = self.session.generated_report_html

            try:
                pdf_bytes = self.pdf_service.convert_html_to_pdf(html_code)
                if pdf_bytes:
                    clean_suburb_name = suburb.replace(' ', '_') if suburb else 'Property'
                    st.download_button(
                        label="📥 Download PDF Report",
                        data=pdf_bytes,
                        file_name=f"SmartPropGuid_Report_{clean_suburb_name}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                else:
                    st.error("Could not compile HTML to PDF. Check if the HTML template format has errors.")
            except Exception as e:
                st.error(f"Error compiling HTML to PDF: {e}")

            # Embed iframe HTML preview on screen
            st.components.v1.html(html_code, height=700, scrolling=True)