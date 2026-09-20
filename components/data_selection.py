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
        st.markdown("### Data Source Configuration")
        st.markdown("Choose whether to use live HTAG Suburb Analysis API data or upload manual operator records for Step 3. Reports are always rendered with SmartPropGuid's standard template.")

        text_muted = "#9c9484"

        with st.container(border=True):
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

                # Suburb, state, and postcode are entered once on the Customer
                # Preferences form (Step 1) and reused here -- shown read-only
                # so operators don't have to retype the same location twice.
                api_suburb = st.session_state.get("suburb", "").strip()
                api_state = st.session_state.get("state", "").strip()
                api_postcode = st.session_state.get("postcode", "").strip()
                prop_type_val = st.session_state.get("property_type", "House")

                if not api_suburb:
                    st.warning("⚠️ No suburb set yet. Go back to **1. Customer Preferences** and fill in the Suburb, State, and Postcode fields first.")

                h_col1, h_col2 = st.columns(2)
                with h_col1:
                    st.text_input("Suburb Name", value=api_suburb or "Not set", disabled=True)
                    st.text_input("State", value=api_state or "Not set", disabled=True)
                with h_col2:
                    st.text_input("Postcode", value=api_postcode or "Not set", disabled=True)
                    api_prop_type = st.selectbox(
                        "Property Type",
                        options=["House", "Unit", "Townhouse", "Land"],
                        index=["House", "Unit", "Townhouse", "Land"].index(prop_type_val) if prop_type_val in ["House", "Unit", "Townhouse", "Land"] else 0,
                        key="htag_input_proptype"
                    )

                if st.button("⚡ Fetch Suburb Data from HTAG API", use_container_width=True, type="secondary"):
                    if not api_suburb:
                        st.error("Please fill in the Suburb field on the Customer Preferences tab before fetching from HTAG.")
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
                    <div style="background: rgba(215,179,94,0.08); border: 1px solid rgba(215,179,94,0.3); border-radius: 8px; padding: 0.85rem; margin-top: 0.8rem; font-size: 0.84rem;">
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

        # Custom AI System Prompt
        with st.container(border=True):
            st.markdown("<h4>2. Pre-Sales Operator Instructions (Prompt)</h4>", unsafe_allow_html=True)
            custom_prompt = st.text_area(
                "Define what aspects you want the AI to emphasize in the report analysis",
                value="Focus heavily on capital growth trends, school catchment boundaries, and transport proximity recommendations based on the customer requirements and listing data.",
                height=100
            )

        return custom_prompt
