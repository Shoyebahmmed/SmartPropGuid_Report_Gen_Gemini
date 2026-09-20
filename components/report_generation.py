import datetime
import json
import streamlit as st
from components.config import SessionState, AppConfig
from components.services import DataService, AnthropicService, HtagService, PdfService, TemplateService
from components.ui_utils import UiHelper
from components.variable_mapper import build_standardized_property_payload
from components.report_sanitizer import sanitize_report_data

AU_STATE_NAMES = {
    "NSW": "NEW SOUTH WALES",
    "VIC": "VICTORIA",
    "QLD": "QUEENSLAND",
    "WA": "WESTERN AUSTRALIA",
    "SA": "SOUTH AUSTRALIA",
    "TAS": "TASMANIA",
    "ACT": "AUSTRALIAN CAPITAL TERRITORY",
    "NT": "NORTHERN TERRITORY",
}


def _state_from_postcode(postcode_str):
    """Deterministic Australian postcode -> state abbreviation, per the
    official postcode ranges. Used as a fallback when the operator filled
    in Postcode but left the State field blank."""
    try:
        pc = int(postcode_str)
    except (TypeError, ValueError):
        return ""
    if 1000 <= pc <= 2599 or 2619 <= pc <= 2899 or 2921 <= pc <= 2999:
        return "NSW"
    if 200 <= pc <= 299 or 2600 <= pc <= 2618 or 2900 <= pc <= 2920:
        return "ACT"
    if 3000 <= pc <= 3999 or 8000 <= pc <= 8999:
        return "VIC"
    if 4000 <= pc <= 4999 or 9000 <= pc <= 9999:
        return "QLD"
    if 5000 <= pc <= 5999:
        return "SA"
    if 6000 <= pc <= 6999:
        return "WA"
    if 7000 <= pc <= 7999:
        return "TAS"
    if 800 <= pc <= 999:
        return "NT"
    return ""


class ReportGenerationComponent:
    def __init__(self, session: SessionState, config: AppConfig,
                 data_service: DataService,
                 anthropic_service: AnthropicService, htag_service: HtagService,
                 pdf_service: PdfService, template_service: TemplateService):
        self.session = session
        self.config = config
        self.data_service = data_service
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

        selected_priorities = st.session_state.get("priorities_pills", []) or []

        # AI Engine info + Active Data Source Card
        ai_model_label = f"Anthropic Claude ({self.config.claude_model})"
        with st.container(border=True):
            prov_col1, prov_col2 = st.columns([2, 1])

            with prov_col1:
                st.markdown("<h4>AI Engine & Generation Settings</h4>", unsafe_allow_html=True)
                st.info(f"Reports are generated using **{ai_model_label}**.")

            with prov_col2:
                st.markdown("<h4>Active Data Source</h4>", unsafe_allow_html=True)
                st.info(f"Using: **{self.session.data_source_mode}**")

        # UI Layout: Settings Summary Card & Generation Button
        bg_subtle = UiHelper.get_bg_subtle_color(self.session.theme)
        border_color = UiHelper.get_border_color(self.session.theme)

        sum_col1, sum_col2 = st.columns([3, 1])
        with sum_col1:
            st.markdown(f"""
            <div style="background-color: {bg_subtle}; padding: 1rem; border-radius: 8px; border: 1px solid {border_color}; font-size: 0.88rem;">
                <strong>Target Area:</strong> {suburb if suburb else "Not specified"} |
                <strong>Property Type:</strong> {property_type} |
                <strong>Budget:</strong> {budget} |
                <strong>Purpose:</strong> {intention} |
                <strong>AI Model:</strong> {ai_model_label}<br>
                <strong>Key Preferences Selected:</strong> {', '.join(selected_priorities) if selected_priorities else "None"}
            </div>
            """, unsafe_allow_html=True)

        with sum_col2:
            generate_btn = st.button("✨ Generate AI Report", type="primary", use_container_width=True)

        if generate_btn:
            # Check API key before execution
            if not self.config.anthropic_api_key:
                st.error("❌ Cannot generate report: ANTHROPIC_API_KEY is missing. Please add it to your Cred.env file.")
                return
            elif not suburb.strip():
                st.error("❌ Cannot generate report: please fill in the Suburb field on the '1. Customer Preferences' tab first.")
                return

            # Suburb, postcode, and state are captured as their own fields on
            # the Customer Preferences form (Step 1). Always Title Case the
            # suburb for a clean cover-page look regardless of how the
            # operator typed it, and -- if they left State blank but did
            # fill in Postcode -- derive the state deterministically from
            # the postcode range rather than leaving the cover page blank.
            suburb_clean = suburb.strip().title()
            postcode_str = st.session_state.get("postcode", "").strip()
            state_str = st.session_state.get("state", "").strip().upper()
            if not state_str and postcode_str:
                state_str = _state_from_postcode(postcode_str)

            loader_placeholder = UiHelper.start_loader("Preparing suburb data...", self.session.theme, percent=8)

            try:
                listings_records = []
                extra_context = {}
                # Deterministic, Python-counted match total (not AI-guessed) --
                # only meaningful in file-upload mode, where "matching listings"
                # is a real concept. Left None in HTAG mode, which the title
                # page's `{% if property_match_count is defined %}` uses to
                # skip the banner entirely for suburb-level HTAG reports.
                property_match_count = None

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

                    if df_filtered is not None:
                        property_match_count = len(df_filtered)

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

                UiHelper.update_loader(
                    loader_placeholder,
                    f"{ai_model_label} is analyzing suburb data and composing your report...",
                    20, self.session.theme
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
1. GROUNDED, BUT NEVER EMPTY:
   - When a value is present in the input JSON payload (matched_variables or extra_variables),
     use it exactly -- never override real data with a guess.
   - When a value is missing, you MUST still provide a realistic, well-reasoned estimate drawn
     from your own general knowledge of this suburb, its state, and comparable Australian
     property markets -- the way an experienced local buyer's agent would ballpark a figure for
     a client on the spot. Round to a sensible precision ("around $1.25M", not "$1,247,382") so
     an estimate never masquerades as a verified exact figure.
   - The client should almost never see a blank "Data unavailable" card for a standard metric
     (median price, clearance rate, days on market, rental yield, walk/transit score,
     demographics, etc.) -- that reads as the tool being broken, not as honesty. Reserve
     "data_available": false (rule 2b) for the rare case where even a competent local-agent
     estimate genuinely isn't possible -- not as a default whenever no live data is connected.

2. MISSING DATA HANDLING & SMART INFERENCE:
   - Check `matched_variables` first.
   - If a standard key in `matched_variables` is `null` or missing, inspect `extra_variables` to see if the missing value can be logically derived, estimated, or calculated (e.g., deriving averages, medians, or ranges from min/max metrics, counts, or related fields available in `extra_variables`). The `research_output` / `htag_research_narrative` field, when present, is a detailed markdown research report about this exact suburb -- READ IT CAREFULLY and pull real figures out of its prose (median rent, days on market, population, dwelling mix, sales volume, IRSAD, etc.) rather than skimming past it; almost every "missing" standard variable is usually stated in there in plain text.
   - If a missing value still can't be derived from `extra_variables`, estimate it yourself per rule 1 above. Do not leave it null just because it wasn't handed to you directly.

2b. FLAGGING A WHOLE SECTION AS UNAVAILABLE:
   - Every section object listed in <required_json_schema> below (snapshot, affordability, rental, budget, growth, infrastructure, price_history, lifestyle, community, schools, risk, verdict) MAY additionally include "data_available": false and a short "unavailable_reason" string when the section is about something this suburb genuinely doesn't have, or that not even a knowledgeable local agent could estimate -- not merely "no live data was connected for this request".
   - Prefer a reasonable estimate (rule 1) over this banner whenever a competent estimate is possible at all. A downstream sanitizer guarantees safe placeholder values for anything you do leave out, so use this flag deliberately, not as a shortcut.

3. DYNAMIC EXTRA DATA UTILIZATION:
   - Incorporate any remaining relevant data points from `extra_variables` into the appropriate report narrative or text blocks (e.g., adding unique infrastructure, zoning, or amenity insights).

4. OUTPUT INSTRUCTIONS:
   - Generate ONLY a single valid JSON object containing the required report data structure below.
   - Do NOT wrap in conversational intro/outro text, meta-commentary, or HTML markup.
   - Maintain an objective, professional, and analytical tone tailored to first-home buyers and property investors.

5. WRITING STYLE -- this report is read directly by the client (a home buyer), not another analyst:
   - Plain, warm, everyday English in every summary/text field. No investor jargon (e.g. avoid
     "yield compression", "capital velocity"), no unexplained acronyms.
   - Never leave a number, score, or recommendation to speak for itself -- every stat in a
     summary/verdict/next_step field should be followed by a short, plain-English reason it
     matters to THIS buyer (e.g. "72% auction clearance -- meaning sellers currently have the
     upper hand, so be ready to move quickly").
</processing_rules>

<required_json_schema>
Return a single JSON object with EXACTLY these top-level keys matching the report template requirements. Every object-typed section below (not the bare lists "amenities"/"day_in_life") may also carry the optional "data_available"/"unavailable_reason" pair described in rule 2b:
"median_price" (string formatted e.g. "$1,658,000" or derived from matched_variables), "clearance_rate" (string e.g. "68%"), "days_on_market" (string e.g. "34 days"),
"snapshot" (object: match_score int, stats list of {{value, label, highlight (boolean true or false)}}, summary string),
"affordability" (object: summary string, stats list of {{value,label}}, trends list of {{label,value,direction: up|down|neutral}}),
"rental" (object: summary string, metrics list of {{label,value,bar_percent 0-100}}),
"budget" (object: summary string, units_percent int 0-100, pills list of {{value,label,style: gold|navy|outline}}),
"growth" (object: summary string, category string, metrics list of {{value,label,bar_percent 0-100}}),
"infrastructure" (object: summary string, entries list of {{year,title,tag_type: transport|amenity|community,tag_label,status_type: active|planned,status_label,value}}),
"price_history" (object: y_axis_labels list of 4 strings low-to-high, points list of ~7 {{year,value (numeric, in millions)}}, legend list of {{color,label}}),
"lifestyle" (object: summary string, scores list of {{value 0-100,label,sublabel,color}}),
"amenities" (list of EXACTLY 6 objects, one per category in this exact order: "Transport", "Shopping & Retail", "Healthcare", "Education", "Parks & Recreation", "Dining & Cafes" -- each object: {{category (one of those 6 exact strings), description (a SHORT skimmable phrase, under 8 words / 50 characters, naming just the single most relevant specific nearby fact -- e.g. "Richmond Station, 5 min walk" or "Bridge Road shopping strip" -- NOT a full sentence or paragraph, grounded in matched_variables/extra_variables)}}),
"day_in_life" (list of {{time,text}}),
"community" (object: summary string, stats list of {{value,label}}, age_distribution list of {{label,value 0-100,dark bool}}, owner_vs_renter list of exactly 2 {{value 0-100,label,color}}, household_composition list of {{label,value 0-100,dark bool}}, type_summary string),
"schools" (object: pending_notice string or empty, summary string, list of {{type,name,distance,score 0-100}}, family_fit list of {{label,value 0-100,dark bool}}, verdict string),
"risk" (object: summary string, entries list of {{level: low|medium|high,title,detail,badge}}, disclaimer string),
"verdict" (object: match_score int 0-100, subscores list of {{label,value 0-100,good bool}}, strengths list of strings, considerations list of strings, next_step string, comparable_suburbs list of {{name,postcode,price}}),
"listings" ({json.dumps(listings_records)} -- reformat/annotate these into a list of {{address,price,badge_score,availability}} if available, else provide representative market listing examples).
</required_json_schema>
</system_prompt>"""

                report_data = self.anthropic_service.generate_report_data(full_prompt)

                UiHelper.update_loader(loader_placeholder, "Structuring your report...", 75, self.session.theme)

                # Repair the AI's JSON before it ever reaches the template: guarantees
                # every field the template loops/does chart math over exists with a
                # safe type, and flags any section that came back materially empty
                # with data_available=False so data_notice() shows an honest banner
                # instead of the render crashing or a chart drawing off bad data.
                report_data = sanitize_report_data(report_data)

                # Set verified deterministic fields
                report_data["suburb"] = suburb_clean or report_data.get("suburb", suburb)
                report_data["postcode"] = postcode_str or str(report_data.get("postcode") or "").strip()
                state_full = AU_STATE_NAMES.get(state_str, "")
                report_data["state_display"] = f"{state_full}, AUSTRALIA" if state_full else "AUSTRALIA"
                if property_match_count is not None:
                    report_data["property_match_count"] = property_match_count

                # Render HTML with Jinja2 template -- always the fixed default
                # template; operators can no longer swap it out, so there's no
                # session-stored template content to read here anymore.
                template_path = self.config.get_asset_path("sample_template.html")
                with open(template_path, "r", encoding="utf-8") as f:
                    template_source = f.read()
                report_html = self.template_service.render(template_source, report_data)
                self.session.generated_report_html = report_html

                # Compile the PDF now, still inside the loader's span, and cache
                # it in session state. Previously this ran *after* the loader had
                # already stopped (in the block below, on every single rerun),
                # which is exactly the few-second "stall" after the spinner
                # disappears that Playwright's headless-Chromium PDF pass causes --
                # now the loader covers the whole pipeline, and the PDF is only
                # ever regenerated when a new report is actually produced.
                UiHelper.update_loader(loader_placeholder, "Compiling your PDF report...", 88, self.session.theme)
                self.session.generated_pdf_bytes = None
                try:
                    self.session.generated_pdf_bytes = self.pdf_service.convert_html_to_pdf(report_html)
                except Exception as pdf_err:
                    st.warning(f"⚠️ Report generated, but PDF compilation failed: {pdf_err}")

                UiHelper.update_loader(loader_placeholder, "Done!", 100, self.session.theme)
                st.success(f"✅ Report generated successfully using {ai_model_label}!")

            except Exception as e:
                st.error(f"❌ Failed to generate report: {e}")
            finally:
                UiHelper.stop_loader(loader_placeholder)

        # Render generated HTML report & PDF compilation controls
        if self.session.generated_report_html:
            st.markdown("### Generated Report Preview")
            html_code = self.session.generated_report_html
            pdf_bytes = self.session.generated_pdf_bytes

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

            # Embed iframe HTML preview on screen -- same asset-embedding pass
            # PdfService applies before printing, so the logo/house image
            # resolve here too instead of showing as broken image icons
            # (a relative "src=LOGO.png" has no route to resolve inside an
            # iframe's srcdoc, so it always needs to become a data URI).
            st.components.v1.html(self.pdf_service.prepare_html_assets(html_code), height=700, scrolling=True)
