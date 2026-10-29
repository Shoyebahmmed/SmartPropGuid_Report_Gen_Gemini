import pandas as pd
import streamlit as st
from components.config import SessionState, AppConfig
from components.services import HtagService, HtagNoMarketData
from components.ui_utils import UiHelper
from components.variable_mapper import build_standardized_property_payload

# Ready-made focus areas for the AI, offered as click-to-add chips on Tab 2.
# The first is the original default instruction, pre-selected.
PROMPT_SUGGESTIONS = [
    "Focus on capital growth trends, school catchments and transport access",
    "Investor lens: rental yield, vacancy rates and cash flow",
    "First-home buyer: affordability, entry-level prices and government grants",
    "Family needs: school zones, parks, childcare and safe streets",
    "Be clear and upfront about flood, bushfire and planning risks",
    "Compare value against nearby suburbs at a similar price",
    "Commute times to the CBD and major job hubs",
    "Upcoming infrastructure and developments that could lift values",
    "Downsizer needs: low maintenance, healthcare and quiet streets",
    "Keep the tone simple and reassuring for a first-time buyer",
]

class DataSelectionComponent:
    def __init__(self, session: SessionState, config: AppConfig, htag_service: HtagService = None):
        self.session = session
        self.config = config
        self.htag_service = htag_service or HtagService(config)

    def render(self) -> str:
        st.markdown("### Data Source Configuration")
        st.markdown("Live HTAG Suburb Analysis data is always pulled in automatically when an API key is configured. Optionally also upload manual operator records below to layer real listings on top for Step 3. Reports are always rendered with SmartPropGuid's standard template.")

        text_muted = "#9c9484"

        with st.container(border=True):
            st.markdown("<h4>Real-Data Grounding</h4>", unsafe_allow_html=True)
            st.checkbox(
                "Always pull real data from HTAG, ABS Census and ArcGIS/OSM for every report (recommended)",
                value=self.session.real_data_enrichment,
                key="real_data_enrichment_toggle",
                on_change=lambda: setattr(self.session, "real_data_enrichment", st.session_state.real_data_enrichment_toggle),
                help=(
                    "On by default. Every report pulls real HTAG suburb metrics, real ABS Census 2021 "
                    "medians/population for the suburb's actual council area, and real named nearby "
                    "places from ArcGIS/OpenStreetMap -- so median price, income, rent and nearby "
                    "amenities are sourced, not guessed. Turn this off only to generate a faster draft "
                    "report using the AI's own estimates, with no live data calls."
                ),
            )
            if not self.session.real_data_enrichment:
                st.warning("⚠️ Real-data grounding is OFF -- this report's figures will be the AI's own estimates, not sourced from HTAG/ABS/ArcGIS.")

        with st.container(border=True):
            st.markdown("<h4>1. Source Data Selection</h4>", unsafe_allow_html=True)
            st.markdown(f"<p style='font-size:0.8rem; color:{text_muted};'>Optionally add manual listings on top of the automatic HTAG suburb intelligence:</p>", unsafe_allow_html=True)

            source_options = [
                "🌐 Live HTAG Suburb Analysis API",
                "📁 Upload Data File (CSV / Excel)"
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

                # Location and property type come straight from Step 1 and are
                # shown as plain text, not widgets: a keyless widget here can
                # keep displaying its first value after Step 1 changes, which
                # made Tab 2 look like it was using a stale suburb/state.
                api_suburb = st.session_state.get("suburb", "").strip()
                api_state = st.session_state.get("state", "").strip()
                api_postcode = st.session_state.get("postcode", "").strip()
                api_prop_type = st.session_state.get("property_type", "House")
                current_query = (api_suburb.lower(), api_state.upper(), api_postcode, api_prop_type)

                if not api_suburb:
                    st.warning("⚠️ No suburb set yet. Go back to **1. Customer Preferences** and search for the suburb first.")
                else:
                    st.markdown(
                        f'<span class="loc-chip">Suburb <b>{api_suburb}</b></span>'
                        f'<span class="loc-chip">Postcode <b>{api_postcode or "—"}</b></span>'
                        f'<span class="loc-chip">State <b>{api_state or "—"}</b></span>'
                        f'<span class="loc-chip">Property <b>{api_prop_type}</b></span>',
                        unsafe_allow_html=True,
                    )

                if st.button("Fetch Suburb Data from HTAG", icon=":material/query_stats:", use_container_width=True,
                             type="secondary", key="htag_fetch_btn"):
                    if not api_suburb:
                        st.error("Please pick a suburb on the Customer Preferences tab before fetching from HTAG.")
                    else:
                        loader = UiHelper.start_loader(
                            f"Fetching market data for {api_suburb}",
                            ["Connecting to HTAG", "Analysing suburb market data", "Preparing preview"],
                        )
                        try:
                            loader.stage(1, "HTAG's research agent is analysing prices, growth, rents and demand -- this usually takes about a minute.",
                                         start=5, end=92, expected_seconds=70)
                            htag_result, stand_in = self.htag_service.fetch_suburb_analysis_or_nearby(
                                suburb=api_suburb,
                                state=api_state,
                                postcode=api_postcode,
                                property_type=api_prop_type
                            )
                            if stand_in:
                                st.info(
                                    f"ℹ️ HTAG has no market data for **{api_suburb}** (common for small or rural "
                                    f"localities). Showing nearby **{stand_in['suburb']} ({stand_in['postcode']})** "
                                    "instead -- the report will say these figures are for that suburb."
                                )
                            loader.stage(2, "Preparing the data preview...", start=92, end=100, expected_seconds=2)
                            self.session.htag_data = htag_result
                            st.session_state["htag_query"] = current_query
                            # Process and pretty-print 41 matched & extra variables to terminal
                            build_standardized_property_payload(
                                suburb=api_suburb,
                                state=api_state,
                                postcode=api_postcode,
                                property_type=api_prop_type,
                                raw_api_data=htag_result
                            )
                            st.success(f"✅ Retrieved HTAG analysis for {stand_in['suburb'] if stand_in else api_suburb}.")
                        except HtagNoMarketData:
                            st.info(
                                f"ℹ️ HTAG has no {api_prop_type.lower()} market data for **{api_suburb}** or the nearby "
                                "suburbs checked (common for small or rural localities). You can still generate the "
                                "report: it will use real ABS Census and OpenStreetMap data, with market figures "
                                "estimated and labelled as estimates."
                            )
                        except Exception as e:
                            st.error(f"❌ Failed to fetch from HTAG API: {e}")
                        finally:
                            UiHelper.stop_loader(loader)

                # Preview only if the loaded HTAG data is for the location and
                # property type currently selected in Step 1.
                if self.session.htag_data and st.session_state.get("htag_query") == current_query:
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

        # Operator instructions for the AI: pick any ready-made focus areas
        # (click to add, click again to remove) and/or write your own.
        with st.container(border=True):
            st.markdown("<h4>2. Pre-Sales Operator Instructions (Prompt)</h4>", unsafe_allow_html=True)
            st.markdown(f"<p style='font-size:0.85rem; color:{text_muted}; margin-bottom:6px;'>Click to add an instruction, click again to remove it:</p>", unsafe_allow_html=True)
            selected_suggestions = st.pills(
                "Suggested instructions",
                options=PROMPT_SUGGESTIONS,
                selection_mode="multi",
                default=[PROMPT_SUGGESTIONS[0]],
                label_visibility="collapsed",
                key="prompt_suggestions",
            ) or []
            extra_prompt = st.text_area(
                "Anything else the AI should emphasise? (optional)",
                placeholder="e.g. The customer works in Parramatta and wants a short commute; they have two primary-school-age kids.",
                height=90,
                key="prompt_custom",
            )

        nav_back, nav_next, nav_spacer = st.columns([1, 1.6, 3.4])
        with nav_back:
            st.button("← Back", use_container_width=True, key="back_to_prefs_btn",
                      on_click=SessionState.go_to_tab, args=(0,))
        with nav_next:
            st.button("Next: Generate Report →", type="primary", use_container_width=True,
                      key="next_to_generate_btn", on_click=SessionState.go_to_tab, args=(2,))

        lines = [f"- {s}" for s in selected_suggestions]
        if extra_prompt.strip():
            lines.append(f"- {extra_prompt.strip()}")
        return "\n".join(lines) if lines else "No specific operator instructions -- give a balanced overview."
