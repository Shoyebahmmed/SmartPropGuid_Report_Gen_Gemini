import streamlit as st
from components.config import SessionState
from components.services import ExcelService

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

    def render(self):
        st.markdown("### Customer Preferences Form")
        st.markdown("Capture customer search requirements to guide the AI report writer.")
        
        # --- Customer Info Card ---
        st.markdown('<div class="zinc-card">', unsafe_allow_html=True)
        st.markdown("<h4>Customer Information</h4>", unsafe_allow_html=True)
        ci_col1, ci_col2, ci_col3 = st.columns(3)
        with ci_col1:
            st.text_input("Full Name", placeholder="e.g. John Smith", key="full_name")
        with ci_col2:
            st.text_input("Phone Number", placeholder="e.g. 0412 345 678", key="phone")
        with ci_col3:
            st.text_input("Email Address", placeholder="e.g. john@email.com", key="email")
        st.markdown('</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="zinc-card">', unsafe_allow_html=True)
            st.markdown("<h4>Property Details</h4>", unsafe_allow_html=True)
            
            st.selectbox(
                "What type of property are you looking for?",
                options=["House", "Unit", "Townhouse", "Land", "Not sure"],
                key="property_type"
            )
            
            st.text_input(
                "Which suburb or area are you interested in?",
                placeholder="e.g. Richmond, VIC 3121 or 2000",
                key="suburb"
            )
            
            st.selectbox(
                "What is your budget?",
                options=["Under $500k", "$500k–$800k", "$800k–$1.2M", "Above $1.2M"],
                key="budget"
            )
            
            st.selectbox(
                "Are you buying to live in or invest?",
                options=["Live in", "Invest", "Both"],
                key="intention"
            )
            st.markdown('</div>', unsafe_allow_html=True)
            
        with col2:
            st.markdown('<div class="zinc-card">', unsafe_allow_html=True)
            st.markdown("<h4>Sub-regional Priorities & Preferences</h4>", unsafe_allow_html=True)
            
            text_muted = "#71717a"
            st.markdown(f"<p style='font-size:0.85rem; color:{text_muted}; margin-bottom:10px;'>Select all that apply:</p>", unsafe_allow_html=True)
            
            # Grid of checkboxes for priorities
            cb_cols = st.columns(2)
            for i, priority in enumerate(self.priorities_list):
                with cb_cols[i % 2]:
                    st.checkbox(priority, key=f"priority_{i}")
                        
            st.markdown('</div>', unsafe_allow_html=True)
            
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
                suburb_input = st.session_state.get("suburb", "").strip()
                
                if not full_name or not phone or not email or not suburb_input:
                    st.error("❌ Full Name, Phone Number, Email Address, and Suburb/Area are required fields.")
                else:
                    try:
                        # Extract priorities mapped to Yes/No
                        priorities_yes_no = []
                        for i in range(len(self.priorities_list)):
                            val = "Yes" if st.session_state.get(f"priority_{i}") else "No"
                            priorities_yes_no.append(val)
                            
                        # Save via Excel Service
                        next_id = self.excel_service.save_submission(
                            full_name=full_name,
                            phone=phone,
                            email=email,
                            property_type=st.session_state.get("property_type", "House"),
                            suburb_input=suburb_input,
                            budget=st.session_state.get("budget", ""),
                            intention=st.session_state.get("intention", ""),
                            priorities_yes_no=priorities_yes_no
                        )
                        st.success(f"✅ Submission saved to Excel successfully as {next_id}!")
                    except Exception as e:
                        st.error(f"❌ Failed to save: {e}")
