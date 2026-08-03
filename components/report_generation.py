import datetime
import json
import re
import streamlit as st
from components.config import SessionState, AppConfig
from components.services import DataService, GeminiService, PdfService, TemplateService
from components.ui_utils import UiHelper

class ReportGenerationComponent:
    def __init__(self, session: SessionState, config: AppConfig, 
                 data_service: DataService, gemini_service: GeminiService, 
                 pdf_service: PdfService, template_service: TemplateService):
        self.session = session
        self.config = config
        self.data_service = data_service
        self.gemini_service = gemini_service
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
        
        # Verify API key
        if not self.config.api_key:
            st.error("❌ Cannot generate report: Gemini API key is missing. Please add it to your Cred.env file.")
            return

        # Fetch form values from session state
        suburb = st.session_state.get("suburb", "")
        property_type = st.session_state.get("property_type", "House")
        budget = st.session_state.get("budget", "")
        intention = st.session_state.get("intention", "")
        
        selected_priorities = []
        for i, priority in enumerate(self.priorities_list):
            if st.session_state.get(f"priority_{i}"):
                selected_priorities.append(priority)

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
                <strong>Key Preferences Selected:</strong> {', '.join(selected_priorities) if selected_priorities else "None"}
            </div>
            """, unsafe_allow_html=True)
            
        with sum_col2:
            generate_btn = st.button("✨ Generate AI Report", type="primary", use_container_width=True)

        if generate_btn:
            # Extract postcode from suburb
            postcode_str = ""
            if suburb:
                pm = re.search(r"\b\d{3,4}\b", suburb.strip())
                postcode_str = pm.group(0) if pm else ""

            # Check for active dataset in session
            df_active = self.session.df_data
            
            # Auto-load if active is None and postcode is available
            if df_active is None and postcode_str:
                try:
                    df_loaded, filename = self.data_service.auto_load_postcode_dataset(postcode_str)
                    if df_loaded is not None:
                        df_active = df_loaded
                        self.session.df_data = df_loaded
                        st.info(f"ℹ️ Automatically loaded postcode dataset: `{filename}`")
                except Exception as e:
                    st.warning(f"⚠️ Could not auto-load postcode dataset: {e}")

            # Filter property listings data
            df_filtered = None
            if df_active is not None:
                df_filtered = self.data_service.filter_property_data(
                    df_active, 
                    postcode_str, 
                    budget, 
                    property_type
                )

            # Prepare listings data context (as structured data, not HTML)
            data_context = ""
            listings_records = []
            if df_filtered is not None and len(df_filtered) > 0:
                data_context = f"Manual Listings Data Compiled (Filtered for Postcode {postcode_str}):\n{df_filtered.to_string(index=False)}"
                for _, r in df_filtered.iterrows():
                    listings_records.append({
                        "address": r.get('Address') or r.get('Property address') or '',
                        "price": r.get('Purchase price') or r.get('Price') or '',
                    })
            else:
                st.warning("No matching listings data found. Report will be generated without property rows.")
                data_context = "No listing data uploaded or matching the criteria."

            # Assemble prompt asking Gemini for STRUCTURED JSON ONLY.
            # Gemini never sees or touches the HTML template -- it only
            # returns content, which TemplateService merges into
            # sample_template.html via Jinja2. This is the key change from
            # the old approach (which had Gemini re-emit the entire HTML
            # document from scratch and was the source of the layout/CSS
            # corruption bugs).
            full_prompt = f"""
            You are a professional property investment analyst assistant.
            Generate the CONTENT for a suburb property report as a single JSON object.
            Do not include any HTML markup -- plain text/numbers/lists only.

            --- INPUTS ---
            1. Property Type Preference: {property_type}
            2. Target Suburb/Area: {suburb}
            3. Budget: {budget}
            4. Purchase Intention: {intention}
            5. Key Client Priorities: {', '.join(selected_priorities) if selected_priorities else "General property advice"}
            6. Pre-Sales Operator Instructions: {custom_prompt}
            7. Report Date: {datetime.date.today().strftime("%B %d, %Y")}

            8. Source Data:
            {data_context}

            --- REQUIRED JSON SCHEMA ---
            Return a single JSON object with EXACTLY these top-level keys:
            "median_price" (string), "clearance_rate" (string), "days_on_market" (string),
            "snapshot" (object: match_score int, stats list of {{value, label, highlight (boolean true or false)}}, summary string)
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
            "listings" ({json.dumps(listings_records)} -- reformat/annotate these into a list of {{address,price,badge_score,availability}} if useful, else pass through).

            Ground every figure and claim in the Source Data where available; where data is
            genuinely unavailable, provide a clearly-labelled reasonable estimate rather than
            inventing overly specific false precision.
            """

            # Display loader while generating
            loader_placeholder = UiHelper.start_loader("AI is analyzing data and compiling report content…", self.session.theme)
            try:
                # 1) Gemini returns structured JSON content only
                report_data = self.gemini_service.generate_report_data(full_prompt)

                # 2) Ensure any missing 'highlight' flag in snapshot stats defaults to False
                snapshot = report_data.get("snapshot", {})
                if isinstance(snapshot, dict):
                    for stat in snapshot.get("stats", []):
                        if isinstance(stat, dict):
                            stat.setdefault("highlight", False)

                # 3) Deterministic fields we already know for certain -- set
                #    these ourselves rather than trusting the model to echo
                #    them back correctly.
                report_data["suburb"] = suburb or report_data.get("suburb", "")
                report_data["postcode"] = postcode_str or report_data.get("postcode", "")
                report_data.setdefault("state_display", "AUSTRALIA")

                # 3) Jinja2 renders the data into the HTML template. Template
                #    markup/CSS is never touched by the AI at any point.
                report_html = self.template_service.render(self.session.template_content, report_data)

                self.session.generated_report_html = report_html
                st.success("✅ Report generated successfully!")
            except Exception as e:
                st.error(f"Failed to generate report from Gemini API: {e}")
            finally:
                UiHelper.stop_loader(loader_placeholder)

        # Render generated HTML report & PDF compilation controls
        if self.session.generated_report_html:
            st.markdown("### Generated Report Preview")
            html_code = self.session.generated_report_html

            try:
                # Convert HTML to PDF
                pdf_bytes = self.pdf_service.convert_html_to_pdf(html_code)
                
                if pdf_bytes:
                    st.download_button(
                        label="📥 Download PDF Report",
                        data=pdf_bytes,
                        file_name=f"SmartPropGuid_Report_{suburb.replace(' ', '_') if suburb else 'General'}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                else:
                    st.error("Could not compile HTML to PDF. Check if the HTML template format has errors.")
            except Exception as e:
                st.error(f"Error compiling HTML to PDF: {e}")

            # Embed iframe HTML preview on screen
            st.components.v1.html(html_code, height=700, scrolling=True)