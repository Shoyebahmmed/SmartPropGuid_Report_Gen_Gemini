import streamlit as st
from components.config import SessionState, BUDGET_OPTIONS
from components.services import ExcelService
from components.au_locations import search_by_suburb, search_by_postcode


def _format_match(m):
    return f"{m['suburb']}, {m['state']} {m['postcode']}"


def _apply_suburb_match():
    choice = st.session_state.get("suburb_match_choice")
    match = st.session_state.get("_suburb_match_map", {}).get(choice)
    if match:
        st.session_state["suburb"] = match["suburb"]
        st.session_state["postcode"] = match["postcode"]
        st.session_state["state"] = match["state"]
    st.session_state["suburb_match_choice"] = None


def _apply_postcode_match():
    choice = st.session_state.get("postcode_match_choice")
    match = st.session_state.get("_postcode_match_map", {}).get(choice)
    if match:
        st.session_state["suburb"] = match["suburb"]
        st.session_state["postcode"] = match["postcode"]
        st.session_state["state"] = match["state"]
    st.session_state["postcode_match_choice"] = None


class FormComponent:
    def __init__(self, session: SessionState, excel_service: ExcelService):
        self.session = session
        self.excel_service = excel_service
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

    def _render_match_picker(self, query, search_fn, match_map_key, picker_key, on_change):
        """
        Shows a small "confirm suburb/postcode" dropdown of real matches as
        the operator types, sourced from components/au_locations.py (a
        bundled, official Australia Post locality list -- not a live API
        call, so it's instant). Picking one fills Suburb, Postcode and
        State from that confirmed record via the on_change callback.

        Skipped once the current Suburb/Postcode/State already exactly
        matches one of the real candidates -- so the picker doesn't linger
        after a selection has already been applied.
        """
        query = (query or "").strip()
        if len(query) < 2:
            return

        matches = search_fn(query, limit=8)
        if not matches:
            return

        current = (
            st.session_state.get("suburb", "").strip().lower(),
            st.session_state.get("postcode", "").strip(),
            st.session_state.get("state", "").strip().upper(),
        )
        if any((m["suburb"].lower(), m["postcode"], m["state"]) == current for m in matches):
            # The current Suburb/Postcode/State already exactly matches one
            # of the real candidates -- already confirmed, even if other
            # (different, equally real) suburbs also match what was typed.
            return

        options = [_format_match(m) for m in matches]
        st.session_state[match_map_key] = dict(zip(options, matches))
        st.selectbox(
            "Confirm match",
            options=options,
            index=None,
            placeholder="Select to confirm & auto-fill the other fields",
            label_visibility="collapsed",
            key=picker_key,
            on_change=on_change,
        )

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

                st.text_input(
                    "Which suburb or area are you interested in?",
                    placeholder="e.g. Richmond",
                    key="suburb"
                )
                self._render_match_picker(
                    query=st.session_state.get("suburb", ""),
                    search_fn=search_by_suburb,
                    match_map_key="_suburb_match_map",
                    picker_key="suburb_match_choice",
                    on_change=_apply_suburb_match,
                )

                loc_col1, loc_col2 = st.columns(2)
                with loc_col1:
                    st.text_input("Postcode", placeholder="e.g. 3121", key="postcode")
                    self._render_match_picker(
                        query=st.session_state.get("postcode", ""),
                        search_fn=search_by_postcode,
                        match_map_key="_postcode_match_map",
                        picker_key="postcode_match_choice",
                        on_change=_apply_postcode_match,
                    )
                with loc_col2:
                    st.text_input("State", placeholder="e.g. VIC", key="state")

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
                st.markdown("<h4>Sub-regional Priorities & Preferences</h4>", unsafe_allow_html=True)

                text_muted = "#9c9484"
                st.markdown(f"<p style='font-size:0.85rem; color:{text_muted}; margin-bottom:10px;'>Tap to select the features that matter most:</p>", unsafe_allow_html=True)

                # Toggle-chip multi-select (replaces the old 2-column checkbox grid)
                st.pills(
                    "Priorities",
                    options=self.priorities_list,
                    selection_mode="multi",
                    default=[],
                    label_visibility="collapsed",
                    key="priorities_pills",
                )

        # --- Reset & Submit Buttons ---
        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
        btn_col1, btn_col2, btn_spacer = st.columns([1, 1, 4])

        with btn_col1:
            if st.button("🔄 Reset", use_container_width=True, key="reset_btn"):
                self.session.reset_form()
                st.rerun()

        with btn_col2:
            if st.button("✅ Submit", use_container_width=True, key="submit_btn"):
                full_name = st.session_state.get("full_name", "").strip()
                phone = st.session_state.get("phone", "").strip()
                email = st.session_state.get("email", "").strip()
                suburb_val = st.session_state.get("suburb", "").strip()
                postcode_val = st.session_state.get("postcode", "").strip()
                state_val = st.session_state.get("state", "").strip().upper()

                if not full_name or not phone or not email or not suburb_val:
                    st.error("❌ Full Name, Phone Number, Email Address, and Suburb/Area are required fields.")
                else:
                    try:
                        # Extract priorities mapped to Yes/No
                        selected_now = st.session_state.get("priorities_pills", []) or []
                        priorities_yes_no = ["Yes" if p in selected_now else "No" for p in self.priorities_list]

                        # Save via Excel Service
                        next_id = self.excel_service.save_submission(
                            full_name=full_name,
                            phone=phone,
                            email=email,
                            property_type=st.session_state.get("property_type", "House"),
                            suburb=suburb_val,
                            postcode=postcode_val,
                            state=state_val,
                            budget=st.session_state.get("budget", ""),
                            intention=st.session_state.get("intention", ""),
                            priorities_yes_no=priorities_yes_no
                        )
                        st.success(f"✅ Submission saved to Excel successfully as {next_id}!")
                    except Exception as e:
                        st.error(f"❌ Failed to save: {e}")
