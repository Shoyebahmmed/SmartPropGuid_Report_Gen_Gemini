import streamlit as st
from components.config import SessionState, BUDGET_OPTIONS
from components.au_locations import all_options, label_for


def _on_location_pick():
    """
    on_change for the single Suburb/Postcode search box: fills Suburb,
    Postcode and State from the confirmed locality record (all three always
    change together, so they can never disagree). Clearing the box clears
    all three.
    """
    match = all_options()[1].get(st.session_state.get("location_picker"))
    st.session_state["suburb"] = match["suburb"] if match else ""
    st.session_state["postcode"] = match["postcode"] if match else ""
    st.session_state["state"] = match["state"] if match else ""


class FormComponent:
    def __init__(self, session: SessionState):
        self.session = session
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

    def render(self):
        st.markdown("### Customer Preferences Form")
        st.markdown("Capture customer search requirements to guide the AI report writer.")

        # --- Customer Info Card ---
        with st.container(border=True):
            st.markdown("<h4>Customer Information</h4>", unsafe_allow_html=True)
            ci_col1, ci_col2, ci_col3 = st.columns(3)
            with ci_col1:
                st.text_input("Full Name", placeholder="e.g. John Smith", key="full_name")
            with ci_col2:
                st.text_input("Phone Number", placeholder="e.g. 0412 345 678", key="phone")
            with ci_col3:
                st.text_input("Email Address", placeholder="e.g. john@email.com", key="email")

        col1, col2 = st.columns(2)

        with col1:
            with st.container(border=True):
                st.markdown("<h4>Property Details</h4>", unsafe_allow_html=True)

                st.selectbox(
                    "What type of property are you looking for?",
                    options=["House", "Unit", "Townhouse", "Land", "Not sure"],
                    key="property_type"
                )

                location_options, _ = all_options()
                current_label = label_for(
                    st.session_state.get("suburb", ""),
                    st.session_state.get("postcode", ""),
                    st.session_state.get("state", ""),
                )

                # One live type-to-filter search over ~18k confirmed AU
                # localities. Labels are "Suburb, STATE postcode", and
                # st.selectbox filters on the whole label client-side, so
                # typing either a suburb name or a postcode finds it.
                # Postcode and State below are read-only: they're always
                # filled from the picked record (see _on_location_pick), so
                # they can't drift out of sync with the suburb.
                st.selectbox(
                    "Which suburb or area are you interested in?",
                    options=location_options,
                    index=location_options.index(current_label) if current_label else None,
                    placeholder="Search by suburb name or postcode...",
                    key="location_picker",
                    on_change=_on_location_pick,
                )

                loc_col1, loc_col2 = st.columns(2)
                with loc_col1:
                    st.text_input("Postcode", placeholder="Auto-filled", key="postcode", disabled=True)
                with loc_col2:
                    st.text_input("State", placeholder="Auto-filled", key="state", disabled=True)

                st.selectbox(
                    "What is your budget?",
                    options=BUDGET_OPTIONS,
                    key="budget"
                )

                st.selectbox(
                    "Are you buying to live in or invest?",
                    options=["Live in", "Invest", "Both"],
                    key="intention"
                )

        with col2:
            with st.container(border=True):
                st.markdown("<h4>What Matters Most</h4>", unsafe_allow_html=True)

                text_muted = "#9c9484"
                st.markdown(f"<p style='font-size:0.85rem; color:{text_muted}; margin-bottom:10px;'>Select everything the customer wants in their area -- the report will focus on these:</p>", unsafe_allow_html=True)

                # Toggle-chip multi-select (replaces the old 2-column checkbox grid)
                st.pills(
                    "Priorities",
                    options=self.priorities_list,
                    selection_mode="multi",
                    default=[],
                    label_visibility="collapsed",
                    key="priorities_pills",
                )

        # --- Reset Button ---
        # There's no separate Submit step: the enquiry is recorded when the
        # report is generated on "3. AI Report Generation".
        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
        btn_col1, btn_col2, btn_spacer = st.columns([1, 1.4, 3.6])

        with btn_col1:
            if st.button("🔄 Reset", use_container_width=True, key="reset_btn"):
                self.session.reset_form()
                st.rerun()

        with btn_col2:
            st.button(
                "Next: Data Source →", type="primary", use_container_width=True,
                key="next_to_data_btn", on_click=SessionState.go_to_tab, args=(1,),
            )
