import os
import io
import datetime
import pandas as pd
import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
from xhtml2pdf import pisa

# ==============================================================================
# 1. SETUP & CONFIGURATION
# ==============================================================================
st.set_page_config(
    page_title="SmartPropGuid Report Generator",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Load environment variables from Cred.env or .env relative to script directory
script_dir = os.path.dirname(os.path.abspath(__file__))
cred_path = os.path.join(script_dir, "Cred.env")
env_path = os.path.join(script_dir, ".env")

if os.path.exists(cred_path):
    load_dotenv(cred_path)
else:
    load_dotenv(env_path)

# Initialize Gemini API
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    st.warning("⚠️ GEMINI_API_KEY not found in Cred.env or system environment. Please configure it to enable AI generation.")

# Initialize Session State
if "theme" not in st.session_state:
    st.session_state.theme = "dark"

if "generated_report_html" not in st.session_state:
    st.session_state.generated_report_html = None

# Form field defaults
FORM_DEFAULTS = {
    "full_name": "",
    "phone": "",
    "email": "",
    "property_type": "House",
    "suburb": "",
    "budget": "Under $500k",
    "intention": "Live in",
}
for k, v in FORM_DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v
# Checkbox defaults
for i in range(11):
    if f"priority_{i}" not in st.session_state:
        st.session_state[f"priority_{i}"] = False

# Toggle Theme Helper
def toggle_theme():
    st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"

IS_DARK = st.session_state.theme == "dark"

# ==============================================================================
# 2. DESIGN SYSTEM & CSS INJECTION
# ==============================================================================
# Color palette definitions depending on the selected theme
BG_COLOR = "#09090b" if IS_DARK else "#ffffff"
BG_SUBTLE = "#0c0c0f" if IS_DARK else "#f9fafb"
CARD_COLOR = "#0c0c0f" if IS_DARK else "#ffffff"
CARD_HOVER = "#131316" if IS_DARK else "#f4f4f5"
BORDER_COLOR = "#1e1e24" if IS_DARK else "#e4e4e7"
BORDER_SUBTLE = "#16161a" if IS_DARK else "#f0f0f2"
TEXT_COLOR = "#fafafa" if IS_DARK else "#09090b"
TEXT_MUTED = "#71717a"
TEXT_DIM = "#52525b" if IS_DARK else "#a1a1aa"
ACCENT_COLOR = "#2563eb"
ACCENT_MUTED = "#1d4ed8"

css = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    /* Hide Streamlit default components for custom branding */
    header[data-testid="stHeader"], #MainMenu, footer, [data-testid="stToolbar"],
    [data-testid="stDecoration"], [data-testid="stStatusWidget"], .stDeployButton,
    div[data-testid="stSidebarCollapsedControl"] {{
        display: none !important;
    }}

    /* Global App Container */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"], .main, .block-container, section[data-testid="stMain"] {{
        background-color: {BG_COLOR} !important;
        color: {TEXT_COLOR} !important;
        font-family: 'DM Sans', -apple-system, sans-serif !important;
    }}
    .block-container {{
        padding: 2rem 2.5rem 3rem !important;
        max-width: 1300px !important;
    }}

    /* Tabs (pill-style navigation) */
    button[data-baseweb="tab"] {{
        background: transparent !important;
        color: {TEXT_MUTED} !important;
        font-size: 0.88rem !important;
        font-weight: 500 !important;
        padding: 0.6rem 1.2rem !important;
        border: 1px solid transparent !important;
        border-radius: 8px !important;
        transition: all 0.2s ease !important;
    }}
    button[data-baseweb="tab"]:hover {{
        color: {TEXT_COLOR} !important;
        background: {CARD_HOVER} !important;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: {TEXT_COLOR} !important;
        background: {CARD_COLOR} !important;
        border-color: {BORDER_COLOR} !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important;
    }}
    [data-baseweb="tab-highlight"], [data-baseweb="tab-border"] {{
        display: none !important;
    }}
    [data-baseweb="tab-list"] {{
        gap: 6px !important;
        background: {BG_SUBTLE} !important;
        border: 1px solid {BORDER_COLOR} !important;
        border-radius: 12px !important;
        padding: 4px;
        margin-bottom: 2rem !important;
    }}

    /* Column spacing */
    [data-testid="stHorizontalBlock"] {{
        gap: 1.5rem !important;
    }}

    /* Custom Card container */
    .zinc-card {{
        background-color: {CARD_COLOR};
        border: 1px solid {BORDER_COLOR};
        border-radius: 12px;
        padding: 1.75rem;
        margin-bottom: 1.5rem;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    .zinc-card:hover {{
        border-color: {ACCENT_COLOR};
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
    }}

    /* Brand banner styling */
    .brand {{
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 1.5rem;
    }}
    .brand-logo {{
        font-size: 1.6rem;
        background: linear-gradient(135deg, #3b82f6, #2563eb);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        letter-spacing: -0.05em;
    }}
    .brand-title {{
        font-size: 1.6rem;
        font-weight: 700;
        color: {TEXT_COLOR};
        letter-spacing: -0.03em;
    }}
    .brand-subtitle {{
        font-size: 0.88rem;
        color: {TEXT_MUTED};
        margin-top: -5px;
    }}

    /* Professional details badge */
    .badge {{
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        text-transform: uppercase;
    }}
    .badge-accent {{
        color: {ACCENT_COLOR};
        background: rgba(37, 99, 235, 0.1);
        border: 1px solid rgba(37, 99, 235, 0.2);
    }}

    /* Streamlit widget overrides — selectbox, text input, multiselect */
    .stTextInput>div>div>input,
    .stTextInput input,
    .stSelectbox>div>div>div,
    .stSelectbox [data-baseweb="select"] > div,
    .stMultiSelect>div>div,
    [data-baseweb="select"] > div {{
        background-color: {BG_SUBTLE} !important;
        border: 1px solid {BORDER_COLOR} !important;
        color: {TEXT_COLOR} !important;
        border-radius: 8px !important;
    }}
    /* Selectbox dropdown option text */
    [data-baseweb="select"] span,
    [data-baseweb="select"] div {{
        color: {TEXT_COLOR} !important;
    }}
    /* Placeholder text color */
    .stTextInput input::placeholder {{
        color: {TEXT_DIM} !important;
        opacity: 1 !important;
    }}
    
    /* Styled HTML Tables */
    .data-table {{
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        font-size: 0.85rem;
        margin-top: 1rem;
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid {BORDER_COLOR};
    }}
    .data-table th {{
        background: {BG_SUBTLE};
        color: {TEXT_MUTED};
        text-align: left;
        padding: 0.75rem 1rem;
        font-size: 0.78rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        border-bottom: 1px solid {BORDER_COLOR};
    }}
    .data-table td {{
        padding: 0.8rem 1rem;
        color: {TEXT_COLOR};
        background: {CARD_COLOR};
        border-bottom: 1px solid {BORDER_SUBTLE};
    }}
    .data-table tr:last-child td {{
        border-bottom: none;
    }}
    
    /* Previews */
    .preview-box {{
        background-color: {BG_SUBTLE};
        border: 1px solid {BORDER_COLOR};
        border-radius: 8px;
        padding: 1rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
        overflow-x: auto;
        white-space: pre-wrap;
        color: {TEXT_COLOR};
    }}

    /* Theme toggle button — white bg + black text in light, dark bg + white text in dark */
    [data-testid="stBaseButton-secondary"] button,
    button[kind="secondary"],
    .stButton > button {{
        background-color: {"#1e1e24" if IS_DARK else "#ffffff"} !important;
        color: {TEXT_COLOR} !important;
        border: 1px solid {BORDER_COLOR} !important;
    }}
    [data-testid="stBaseButton-secondary"] button *,
    [data-testid="stBaseButton-secondary"] button p,
    [data-testid="stBaseButton-secondary"] button span,
    .stButton > button p,
    .stButton > button span {{
        color: {TEXT_COLOR} !important;
    }}

    /* Widget labels (selectbox, text_input, checkbox) — readable in both modes */
    .stSelectbox label,
    .stTextInput label,
    .stCheckbox label,
    .stCheckbox label p,
    .stCheckbox span,
    .stCheckbox p,
    [data-testid="stCheckbox"] label,
    [data-testid="stCheckbox"] label p,
    [data-testid="stCheckbox"] span {{
        color: {TEXT_COLOR} !important;
    }}

    /* Checkbox box (the square) — border and background match theme */
    [data-baseweb="checkbox"] > div:first-child,
    [data-testid="stCheckbox"] [data-baseweb="checkbox"] > div {{
        background-color: {BG_SUBTLE} !important;
        border-color: {BORDER_COLOR} !important;
    }}
    /* Checked state — keep accent blue */
    [data-baseweb="checkbox"][aria-checked="true"] > div:first-child {{
        background-color: {ACCENT_COLOR} !important;
        border-color: {ACCENT_COLOR} !important;
    }}
</style>
"""
st.markdown(css, unsafe_allow_html=True)

# ==============================================================================
# 3. HEADER & BRAND AREA
# ==============================================================================
head_left, head_right = st.columns([9, 2])
with head_left:
    st.markdown(f"""
    <div class="brand">
        <div>
            <span class="brand-logo">◆ SmartPropGuid</span>
            <span class="brand-title">Report Engine</span>
            <div class="brand-subtitle">Pre-Sales Manual Compilation & AI Generation Tool</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
with head_right:
    theme_label = "☀️ Light Mode" if IS_DARK else "🌙 Dark Mode"
    st.button(theme_label, on_click=toggle_theme, use_container_width=True)

st.markdown("<hr style='margin-top:0.5rem; margin-bottom:1.5rem; border-color:" + BORDER_COLOR + "'>", unsafe_allow_html=True)

# ==============================================================================
# 4. APPLICATION TABS (FLOW STEPS)
# ==============================================================================
tab_preferences, tab_upload, tab_generate = st.tabs([
    "📋 1. Customer Preferences", 
    "📂 2. Data & Template Upload", 
    "✨ 3. AI Report Generation"
])



# ------------------------------------------------------------------------------
# TAB 1: CUSTOMER PREFERENCES
# ------------------------------------------------------------------------------
with tab_preferences:
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
        
        property_type = st.selectbox(
            "What type of property are you looking for?",
            options=["House", "Unit", "Townhouse", "Land", "Not sure"],
            key="property_type"
        )
        
        suburb = st.text_input(
            "Which suburb or area are you interested in?",
            placeholder="e.g. Richmond, VIC 3121 or 2000",
            key="suburb"
        )
        
        budget = st.selectbox(
            "What is your budget?",
            options=["Under $500k", "$500k–$800k", "$800k–$1.2M", "Above $1.2M"],
            key="budget"
        )
        
        intention = st.selectbox(
            "Are you buying to live in or invest?",
            options=["Live in", "Invest", "Both"],
            key="intention"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col2:
        st.markdown('<div class="zinc-card">', unsafe_allow_html=True)
        st.markdown("<h4>Sub-regional Priorities & Preferences</h4>", unsafe_allow_html=True)
        
        priorities_list = [
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
        
        selected_priorities = []
        st.markdown("<p style='font-size:0.85rem; color:"+TEXT_MUTED+"; margin-bottom:10px;'>Select all that apply:</p>", unsafe_allow_html=True)
        
        # Grid of checkboxes for priorities
        cb_cols = st.columns(2)
        for i, priority in enumerate(priorities_list):
            with cb_cols[i % 2]:
                if st.checkbox(priority, key=f"priority_{i}"):
                    selected_priorities.append(priority)
                    
        st.markdown('</div>', unsafe_allow_html=True)
        
    # --- Reset & Submit Buttons ---
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    btn_col1, btn_col2, btn_spacer = st.columns([1, 1, 4])
    with btn_col1:
        if st.button("🔄 Reset", use_container_width=True, key="reset_btn"):
            for k in FORM_DEFAULTS.keys():
                if k in st.session_state:
                    del st.session_state[k]
            for i in range(len(priorities_list)):
                key = f"priority_{i}"
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    with btn_col2:
        if st.button("✅ Submit", use_container_width=True, key="submit_btn"):
            EXCEL_PATH = r"C:\Users\ahmma\.gemini\antigravity-ide\scratch\SmartPropGuid_Report_Gen_Gemini\SPG_Customer_Intake_Form.xlsx"
            new_row = {
                "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Full Name": st.session_state.full_name,
                "Phone": st.session_state.phone,
                "Email": st.session_state.email,
                "Property Type": st.session_state.property_type,
                "Suburb": st.session_state.suburb,
                "Budget": st.session_state.budget,
                "Intention": st.session_state.intention,
                "Priorities": ", ".join(selected_priorities),
            }
            try:
                if os.path.exists(EXCEL_PATH):
                    df_existing = pd.read_excel(EXCEL_PATH)
                    df_updated = pd.concat([df_existing, pd.DataFrame([new_row])], ignore_index=True)
                else:
                    df_updated = pd.DataFrame([new_row])
                df_updated.to_excel(EXCEL_PATH, index=False)
                st.success("✅ Submission saved to Excel successfully!")
            except Exception as e:
                st.error(f"❌ Failed to save: {e}")

# ------------------------------------------------------------------------------
# TAB 2: DATA & TEMPLATE UPLOAD
# ------------------------------------------------------------------------------
with tab_upload:
    st.markdown("### Manual Data Compilation & Predefined Layouts")
    st.markdown("Upload the source documents gathered by your operator for Step 3.")
    
    col_data, col_template = st.columns(2)
    
    with col_data:
        st.markdown('<div class="zinc-card">', unsafe_allow_html=True)
        st.markdown("<h4>1. Source Data File (CSV / Excel)</h4>", unsafe_allow_html=True)
        st.markdown(f"<p style='font-size:0.8rem; color:{TEXT_MUTED};'>Upload the property listings, demographics or market statistics file compiled manually.</p>", unsafe_allow_html=True)
        
        uploaded_data = st.file_uploader(
            "Select compiled data file",
            type=["csv", "xlsx", "xls"],
            key="data_uploader"
        )
        
        # Read and display data preview
        data_preview_html = ""
        df_data = None
        if uploaded_data is not None:
            try:
                if uploaded_data.name.endswith(".csv"):
                    df_data = pd.read_csv(uploaded_data)
                else:
                    df_data = pd.read_excel(uploaded_data)
                
                st.success(f"Successfully loaded: `{uploaded_data.name}` ({len(df_data)} rows)")
                st.markdown("##### File Preview (First 5 Rows):")
                st.dataframe(df_data.head(5), use_container_width=True)
                
                # Format to a table string for the LLM
                data_preview_html = df_data.head(20).to_html(index=False, classes="data-table")
            except Exception as e:
                st.error(f"Error reading file: {e}")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col_template:
        st.markdown('<div class="zinc-card">', unsafe_allow_html=True)
        st.markdown("<h4>2. Predefined Report Template (HTML)</h4>", unsafe_allow_html=True)
        st.markdown(f"<p style='font-size:0.8rem; color:{TEXT_MUTED};'>Upload your customized corporate report HTML template. Leave empty to use the system default template.</p>", unsafe_allow_html=True)
        
        uploaded_template = st.file_uploader(
            "Select custom HTML template",
            type=["html", "htm"],
            key="template_uploader"
        )
        
        # Load custom or default template
        template_content = ""
        default_template_path = os.path.join(script_dir, "sample_template.html")
        
        if uploaded_template is not None:
            try:
                template_content = uploaded_template.read().decode("utf-8")
                st.success(f"Custom template loaded: `{uploaded_template.name}`")
            except Exception as e:
                st.error(f"Error reading template: {e}")
        else:
            if os.path.exists(default_template_path):
                with open(default_template_path, "r", encoding="utf-8") as f:
                    template_content = f.read()
                st.info("ℹ️ Using default SmartPropGuid template.")
            else:
                st.warning("⚠️ System default template not found. Please upload a template.")
                
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

# ------------------------------------------------------------------------------
# TAB 3: AI GENERATION & PDF EXPORT
# ------------------------------------------------------------------------------
with tab_generate:
    st.markdown("### Generate and Review Report")
    
    # Check if API key is present
    if not api_key:
        st.error("❌ Cannot generate report: Gemini API key is missing. Please add it to your Cred.env file.")
    else:
        # Layout: Settings Summary Card & Generation Button
        sum_col1, sum_col2 = st.columns([3, 1])
        with sum_col1:
            st.markdown(f"""
            <div style="background-color: {BG_SUBTLE}; padding: 1rem; border-radius: 8px; border: 1px solid {BORDER_COLOR}; font-size: 0.88rem;">
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
            # Prepare instructions and data details to inject into Gemini prompt
            data_context = ""
            if df_data is not None:
                # Include a text presentation of listings
                data_context = f"Manual Listings Data Compiled:\n{df_data.to_string(index=False)}"
            else:
                data_context = "No Listing data uploaded. Generate standard market advice for the suburb based on public statistics."

            # Build Prompt
            full_prompt = f"""
            You are a professional property investment analyst assistant.
            You must populate the HTML report template provided below based on the following Inputs.

            --- INPUTS ---
            1. Property Type Preference: {property_type}
            2. Target Suburb/Area: {suburb}
            3. Budget: {budget}
            4. Purchase Intention: {intention}
            5. Key Client Priorities: {', '.join(selected_priorities) if selected_priorities else "General property advice"}
            6. Pre-Sales Operator Instructions: {custom_prompt}
            
            7. Source Data:
            {data_context}
            
            --- HTML REPORT TEMPLATE ---
            {template_content}

            --- COMPILING INSTRUCTIONS ---
            1. Populate all variable placeholders in the HTML template (like `{{ executive_summary }}`, `{{ market_analysis }}`, `{{ key_priorities }}`, `{{ date_generated }}`).
            2. For `{{ date_generated }}`, use today's date: {datetime.date.today().strftime("%B %d, %Y")}.
            3. For `{{ key_priorities }}`, output a bulleted list based on the inputs.
            4. Populate `{{ source_data_rows }}` by matching properties from the listing data that suit the client's preferences. Render each matching listing as a table row:
               `<tr><td>Address</td><td>Price</td><td><span class="badge badge-blue">Score</span></td><td><span class="badge badge-green">Available</span></td></tr>`
               If no listings data is provided, synthesize 3 plausible mockup properties for the target suburb that match the budget and type, and add them as table rows.
            5. Return ONLY the complete, final HTML code starting with `<!DOCTYPE html>` and ending with `</html>`.
            6. Do NOT wrap the code in markdown blocks like ````html```` or add any conversational intro/outro text. Output only raw HTML.
            """

            with st.spinner("AI is analyzing data and populating report layout..."):
                try:
                    # Request model completion
                    response = genai.GenerativeModel('gemini-2.5-flash').generate_content(full_prompt)
                    
                    # Store output in session state
                    clean_html = response.text.strip()
                    # Clean markdown code fences if model accidentally output them
                    if clean_html.startswith("```html"):
                        clean_html = clean_html[7:]
                    if clean_html.endswith("```"):
                        clean_html = clean_html[:-3]
                    clean_html = clean_html.strip()
                    
                    st.session_state.generated_report_html = clean_html
                    st.success("✅ Report generated successfully!")
                except Exception as e:
                    st.error(f"Failed to generate report from Gemini API: {e}")

        # Render generated report and PDF download option if exists
        if st.session_state.generated_report_html:
            st.markdown("### Generated Report Preview")
            
            # PDF Generation Block
            html_code = st.session_state.generated_report_html
            
            # Compiling helper to convert HTML to PDF bytes
            def get_pdf_bytes(html_text):
                pdf_io = io.BytesIO()
                pisa_status = pisa.CreatePDF(html_text, dest=pdf_io)
                if pisa_status.err:
                    return None
                return pdf_io.getvalue()
                
            pdf_bytes = get_pdf_bytes(html_code)
            
            # Download Button
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

            # On-screen preview using HTML component iframe
            st.components.v1.html(html_code, height=700, scrolling=True)
