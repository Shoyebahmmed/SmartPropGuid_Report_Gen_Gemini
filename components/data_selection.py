import os
import re
import pandas as pd
import streamlit as st
from components.config import SessionState, AppConfig
from components.services import HtagService
from components.ui_utils import UiHelper
from components.variable_mapper import build_standardized_property_payload

class DataSelectionComponent:
    def __init__(self, session: SessionState, config: AppConfig, htag_service: HtagService = None):
        self.session = session
        self.config = config
        self.htag_service = htag_service or HtagService(config)

    def render(self) -> str:
        st.markdown("### Data Source & Template Configuration")
        st.markdown("Choose whether to use live HTAG Suburb Analysis API data or upload manual operator records for Step 3.")

        col_data, col_template = st.columns(2)
        text_muted = "#71717a"
        border_color = UiHelper.get_border_color(self.session.theme)

        with col_data:
            st.markdown('<div class="zinc-card">', unsafe_allow_html=True)
            st.markdown("<h4>1. Source Data Selection</h4>", unsafe_allow_html=True)
            st.markdown(f"<p style='font-size:0.8rem; color:{text_muted};'>Select your property intelligence source mode below:</p>", unsafe_allow_html=True)

            source_options = [
                "📁 Upload Data File (CSV / Excel)",
                "🌐 Live HTAG Suburb Analysis API"
            ]

            # Current selection default
            current_mode = self.session.data_source_mode if self.session.data_source_mode in source_options else source_options[0]
            selected_mode = st.selectbox(
                "Data Source Mode",
                options=source_options,
                index=source_options.index(current_mode),
                key="data_mode_select"
            )
            self.session.data_source_mode = selected_mode

            if selected_mode == "📁 Upload Data File (CSV / Excel)":
                st.markdown(f"<p style='font-size:0.8rem; color:{text_muted}; margin-top:0.5rem;'>Upload property listings or sales statistics file compiled manually.</p>", unsafe_allow_html=True)
                uploaded_data = st.file_uploader(
                    "Select compiled data file",
                    type=["csv", "xlsx", "xls"],
                    key="data_uploader"
                )

                # Read and display data preview
                if uploaded_data is not None:
                    try:
                        uploaded_data.seek(0)
                        if uploaded_data.name.endswith(".csv"):
                            self.session.df_data = pd.read_csv(uploaded_data)
                        else:
                            self.session.df_data = pd.read_excel(uploaded_data)

                        st.success(f"Successfully loaded: `{uploaded_data.name}` ({len(self.session.df_data)} rows)")
                        st.markdown("##### File Preview (First 5 Rows):")
                        st.dataframe(self.session.df_data.head(5), use_container_width=True)
                    except Exception as e:
                        st.error(f"Error reading file: {e}")
                else:
                    # Keep existing df_data if already present, or None
                    if self.session.df_data is not None:
                        st.info(f"ℹ️ Active dataset loaded ({len(self.session.df_data)} rows).")

            else:
                # Live HTAG API Integration
                st.markdown(f"<p style='font-size:0.8rem; color:{text_muted}; margin-top:0.5rem;'>Fetch real-time institutional suburb intelligence from HTAG Analytics.</p>", unsafe_allow_html=True)

                # Parse defaults from form state if available
                suburb_state_val = st.session_state.get("suburb", "").strip()
                prop_type_val = st.session_state.get("property_type", "House")

                postcode_default = ""
                state_default = ""
                suburb_name_default = suburb_state_val

                if suburb_state_val:
                    pc_match = re.search(r"\b\d{3,4}\b", suburb_state_val)
                    if pc_match:
                        postcode_default = pc_match.group(0)
                        suburb_name_default = suburb_name_default.replace(postcode_default, "")

                    st_match = re.search(r"\b(VIC|NSW|QLD|WA|SA|TAS|ACT|NT)\b", suburb_name_default, re.IGNORECASE)
                    if st_match:
                        state_default = st_match.group(0).upper()
                        suburb_name_default = re.sub(rf"\b{state_default}\b", "", suburb_name_default, flags=re.IGNORECASE)

                    suburb_name_default = re.sub(r"[,\-\s]+", " ", suburb_name_default).strip()

                h_col1, h_col2 = st.columns(2)
                with h_col1:
                    api_suburb = st.text_input("Suburb Name", value=suburb_name_default or "Richmond", key="htag_input_suburb")
                    api_state = st.text_input("State (optional)", value=state_default or "VIC", key="htag_input_state")
                with h_col2:
                    api_postcode = st.text_input("Postcode (optional)", value=postcode_default or "3121", key="htag_input_postcode")
                    api_prop_type = st.selectbox(
                        "Property Type",
                        options=["House", "Unit", "Townhouse", "Land"],
                        index=["House", "Unit", "Townhouse", "Land"].index(prop_type_val) if prop_type_val in ["House", "Unit", "Townhouse", "Land"] else 0,
                        key="htag_input_proptype"
                    )

                if st.button("⚡ Fetch Suburb Data from HTAG API", use_container_width=True, type="secondary"):
                    if not api_suburb:
                        st.error("Please enter a Suburb Name to fetch analysis from HTAG.")
                    else:
                        loader = UiHelper.start_loader("Connecting to HTAG Suburb Intelligence Agent...", self.session.theme)
                        try:
                            htag_result = self.htag_service.fetch_suburb_analysis(
                                suburb=api_suburb,
                                state=api_state,
                                postcode=api_postcode,
                                property_type=api_prop_type
                            )
                            self.session.htag_data = htag_result
                            # Process and pretty-print 41 matched & extra variables to terminal
                            build_standardized_property_payload(
                                suburb=api_suburb,
                                state=api_state,
                                postcode=api_postcode,
                                property_type=api_prop_type,
                                raw_api_data=htag_result
                            )
                            st.success(f"✅ Successfully retrieved HTAG analysis for {api_suburb}!")
                        except Exception as e:
                            st.error(f"❌ Failed to fetch from HTAG API: {e}")
                        finally:
                            UiHelper.stop_loader(loader)

                # Show preview of HTAG data if loaded
                if self.session.htag_data:
                    hdata = self.session.htag_data
                    metrics = hdata.get("metrics", {})
                    rcs = hdata.get("rcs", {})
                    med_price = metrics.get("median_price")
                    price_display = f"${med_price:,.0f}" if isinstance(med_price, (int, float)) else "N/A"
                    yield_val = metrics.get("gross_yield")
                    yield_display = f"{yield_val * 100:.2f}%" if isinstance(yield_val, (int, float)) else "N/A"
                    vac_val = metrics.get("vacancy_rate")
                    vac_display = f"{vac_val * 100:.2f}%" if isinstance(vac_val, (int, float)) else "N/A"
                    rcs_overall = rcs.get("overall", "N/A")
                    cycle_stage = hdata.get("cycle_stage", metrics.get("cycle_stage", "N/A"))

                    st.markdown(f"""
                    <div style="background: rgba(37,99,235,0.06); border: 1px solid rgba(37,99,235,0.25); border-radius: 8px; padding: 0.85rem; margin-top: 0.8rem; font-size: 0.84rem;">
                        <strong>📊 HTAG Live Data Ready:</strong><br>
                        <strong>Median Price:</strong> {price_display} | 
                        <strong>Gross Yield:</strong> {yield_display} | 
                        <strong>Vacancy:</strong> {vac_display}<br>
                        <strong>RCS Score:</strong> {rcs_overall}/100 | 
                        <strong>Cycle Stage:</strong> {cycle_stage}
                    </div>
                    """, unsafe_allow_html=True)

                    with st.expander("🔍 View HTAG Research Summary"):
                        research_text = hdata.get("research_output", "")
                        if research_text:
                            st.markdown(research_text[:1500] + ("..." if len(research_text) > 1500 else ""))
                        else:
                            st.json(hdata)

            st.markdown('</div>', unsafe_allow_html=True)

        with col_template:
            st.markdown('<div class="zinc-card">', unsafe_allow_html=True)
            st.markdown("<h4>2. Predefined Report Template (HTML)</h4>", unsafe_allow_html=True)
            st.markdown(f"<p style='font-size:0.8rem; color:{text_muted};'>Upload your customized corporate report HTML template. Leave empty to use the system default template.</p>", unsafe_allow_html=True)

            uploaded_template = st.file_uploader(
                "Select custom HTML template",
                type=["html", "htm"],
                key="template_uploader"
            )

            # Load custom or default template
            default_template_path = self.config.get_asset_path("sample_template.html")

            if uploaded_template is not None:
                try:
                    uploaded_template.seek(0)
                    self.session.template_content = uploaded_template.read().decode("utf-8")
                    st.success(f"Custom template loaded: `{uploaded_template.name}`")
                except Exception as e:
                    st.error(f"Error reading template: {e}")
            else:
                if os.path.exists(default_template_path):
                    with open(default_template_path, "r", encoding="utf-8") as f:
                        self.session.template_content = f.read()
                    st.info("ℹ️ Using default SmartPropGuid template.")
                else:
                    self.session.template_content = ""
                    st.warning("⚠️ System default template not found. Please upload a template.")

            template_content = self.session.template_content

            # Template preview in a collapsible expander
            if template_content:
                with st.expander("👁️ View Template HTML Structure"):
                    st.markdown(f'<div class="preview-box">{template_content}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # Custom AI System Prompt
        st.markdown('<div class="zinc-card">', unsafe_allow_html=True)
        st.markdown("<h4>3. Pre-Sales Operator Instructions (Prompt)</h4>", unsafe_allow_html=True)
        custom_prompt = st.text_area(
            "Define what aspects you want the AI to emphasize in the report analysis",
            value="Focus heavily on capital growth trends, school catchment boundaries, and transport proximity recommendations based on the customer requirements and listing data.",
            height=100
        )
        st.markdown('</div>', unsafe_allow_html=True)

        return custom_prompt
