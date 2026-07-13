# from app import get_pdf_bytes_playwright
import os
import io
import datetime
import pandas as pd
import streamlit as st
import google.generativeai as genai
import asyncio
import base64
from playwright.async_api import async_playwright
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


# abs_path = os.path.dirname(os.path.abspath(__file__))
# logo_path = os.path.join(abs_path, "LOGO.svg")
# html_code = html_code.replace('src="LOGO.svg"', f'src="{logo_path}"')


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

if "df_data" not in st.session_state:
    st.session_state.df_data = None

if "template_content" not in st.session_state:
    st.session_state.template_content = ""

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

# Helper to start a compact loading box
def start_loader(message: str):
    placeholder = st.empty()
    placeholder.markdown(
        f'''<div class="loader-container">
                <div class="loader"></div>
                <p class="loader-text">{message}</p>
            </div>''',
        unsafe_allow_html=True,
    )
    return placeholder

# Helper to stop the loading box
def stop_loader(placeholder):
    if placeholder:
        placeholder.empty()

IS_DARK = st.session_state.theme == "dark"

# Helper to filter property listing datasets by postcode and budget
def filter_property_data(df, postcode_str, budget_str, property_type_str):
    if df is None or len(df) == 0:
        return df
    df_filtered = df.copy()
    if postcode_str:
        try:
            pc_val = float(postcode_str)
            if 'Property post code' in df_filtered.columns:
                df_filtered = df_filtered[df_filtered['Property post code'] == pc_val]
        except ValueError:
            pass
    if budget_str and 'Purchase price' in df_filtered.columns:
        if "Under $500k" in budget_str:
            df_filtered = df_filtered[df_filtered['Purchase price'] < 500000]
        elif "$500k" in budget_str and "$800k" in budget_str:
            df_filtered = df_filtered[(df_filtered['Purchase price'] >= 500000) & (df_filtered['Purchase price'] <= 800000)]
        elif "$800k" in budget_str and "$1.2M" in budget_str:
            df_filtered = df_filtered[(df_filtered['Purchase price'] >= 800000) & (df_filtered['Purchase price'] <= 1200000)]
        elif "Above $1.2M" in budget_str:
            df_filtered = df_filtered[df_filtered['Purchase price'] > 1200000]
    if property_type_str and 'Primary purpose' in df_filtered.columns:
        if property_type_str == "Land":
            df_filtered = df_filtered[df_filtered['Primary purpose'] == 'Vacant land']
        elif property_type_str in ["House", "Unit", "Townhouse"]:
            df_filtered = df_filtered[df_filtered['Primary purpose'] == 'Residence']
    if len(df_filtered) > 50:
        if 'Contract date' in df_filtered.columns:
            try:
                df_filtered = df_filtered.sort_values(by='Contract date', ascending=False)
            except Exception:
                pass
        df_filtered = df_filtered.head(50)
    return df_filtered

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

    /* Loader container – small centered box */
    .loader-container {{
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 1.5rem;
        background: rgba(0,0,0,0.5);
        border-radius: 12px;
        width: 260px;
        margin: auto;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }}
    .loader {{
        border: 4px solid {BG_SUBTLE};
        border-top: 4px solid {ACCENT_COLOR};
        border-radius: 50%;
        width: 60px;
        height: 60px;
        animation: spin 1s linear infinite;
    }}
    @keyframes spin {{
        0% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(360deg); }}
    }}
    .loader-text {{
        margin-top: 1rem;
        color: {TEXT_COLOR};
        font-size: 1.1rem;
        text-align: center;
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
            full_name = st.session_state.get("full_name", "").strip()
            phone = st.session_state.get("phone", "").strip()
            email = st.session_state.get("email", "").strip()
            suburb_input = st.session_state.get("suburb", "").strip()
            
            if not full_name or not phone or not email or not suburb_input:
                st.error("❌ Full Name, Phone Number, Email Address, and Suburb/Area are required fields.")
            else:
                EXCEL_PATH = r"C:\Users\ahmma\.gemini\antigravity-ide\scratch\SmartPropGuid_Report_Gen_Gemini\SPG_Customer_Intake_Form.xlsx"
                try:
                    import openpyxl
                    import re
                    from copy import copy
                    
                    if not os.path.exists(EXCEL_PATH):
                        st.error(f"❌ Excel file not found: {EXCEL_PATH}. Please make sure the template file exists.")
                    else:
                        wb = openpyxl.load_workbook(EXCEL_PATH)
                        sheet = wb.active
                        
                        # Find the last row with data in Column A (Submission ID)
                        last_row = 3
                        for r in range(4, sheet.max_row + 2):
                            if sheet.cell(row=r, column=1).value is not None:
                                last_row = r
                        
                        # Generate Submission ID
                        last_id = sheet.cell(row=last_row, column=1).value
                        if last_id and isinstance(last_id, str) and last_id.startswith("SPG-"):
                            try:
                                num = int(last_id.split("-")[1])
                                next_id = f"SPG-{num + 1:03d}"
                            except (IndexError, ValueError):
                                next_id = "SPG-002"
                        else:
                            next_id = "SPG-001"
                        
                        # Suburb, Postcode, and State parsing
                        suburb_clean, postcode_clean, state_clean = "", "", ""
                        if suburb_input:
                            postcode_match = re.search(r"\b\d{3,4}\b", suburb_input)
                            postcode_clean = postcode_match.group(0) if postcode_match else ""
                            
                            state_match = re.search(r"\b(VIC|NSW|QLD|WA|SA|TAS|ACT|NT)\b", suburb_input, re.IGNORECASE)
                            state_clean = state_match.group(0).upper() if state_match else ""
                            
                            suburb_clean = suburb_input
                            if postcode_clean:
                                suburb_clean = suburb_clean.replace(postcode_clean, "")
                            if state_clean:
                                suburb_clean = re.sub(rf"\b{state_clean}\b", "", suburb_clean, flags=re.IGNORECASE)
                                
                            suburb_clean = re.sub(r"[,\-\s]+", " ", suburb_clean).strip()
                        
                        # Map priority checkboxes to Yes/No
                        priorities_yes_no = []
                        for i in range(11):
                            val = "Yes" if st.session_state.get(f"priority_{i}") else "No"
                            priorities_yes_no.append(val)
                        
                        next_row = last_row + 1
                        
                        # Date format
                        date_submitted = datetime.date.today().strftime("%d/%m/%Y")
                        
                        # Assemble row data (now 25 columns)
                        row_values = [
                            next_id,                           # 1: Submission ID
                            date_submitted,                    # 2: Date Submitted
                            full_name,                         # 3: Full Name
                            email,                             # 4: Email Address
                            phone,                             # 5: Phone Number
                            st.session_state.get("property_type", "House"),  # 6: Property Type
                            suburb_clean,                      # 7: Suburb / Area
                            postcode_clean,                    # 8: Postcode
                            state_clean,                       # 9: State
                            st.session_state.get("budget", ""), # 10: Budget Range
                            st.session_state.get("intention", ""), # 11: Buying Purpose
                        ]
                        # Append 11 priorities
                        row_values.extend(priorities_yes_no)
                        # Append remaining columns: Additional Notes (23), Report Status (24), Assigned To (25)
                        row_values.extend(["", "Pending", "Shoyeb"])
                        
                        # Write to the cells and copy style if last_row has styles
                        for col_idx, val in enumerate(row_values, start=1):
                            new_cell = sheet.cell(row=next_row, column=col_idx, value=val)
                            if last_row >= 4:
                                src_cell = sheet.cell(row=last_row, column=col_idx)
                                if src_cell.has_style:
                                    new_cell.font = copy(src_cell.font)
                                    new_cell.border = copy(src_cell.border)
                                    new_cell.fill = copy(src_cell.fill)
                                    new_cell.number_format = copy(src_cell.number_format)
                                    new_cell.protection = copy(src_cell.protection)
                                    new_cell.alignment = copy(src_cell.alignment)
                        
                        wb.save(EXCEL_PATH)
                        st.success(f"✅ Submission saved to Excel successfully as {next_id}!")
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
        if uploaded_data is not None:
            try:
                uploaded_data.seek(0)
                if uploaded_data.name.endswith(".csv"):
                    st.session_state.df_data = pd.read_csv(uploaded_data)
                else:
                    st.session_state.df_data = pd.read_excel(uploaded_data)
                
                st.success(f"Successfully loaded: `{uploaded_data.name}` ({len(st.session_state.df_data)} rows)")
                st.markdown("##### File Preview (First 5 Rows):")
                st.dataframe(st.session_state.df_data.head(5), use_container_width=True)
                
                # Format to a table string for the LLM
                data_preview_html = st.session_state.df_data.head(20).to_html(index=False, classes="data-table")
            except Exception as e:
                st.error(f"Error reading file: {e}")
        else:
            st.session_state.df_data = None
            
        df_data = st.session_state.df_data
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
        default_template_path = os.path.join(script_dir, "sample_template.html")
        
        if uploaded_template is not None:
            try:
                uploaded_template.seek(0)
                st.session_state.template_content = uploaded_template.read().decode("utf-8")
                st.success(f"Custom template loaded: `{uploaded_template.name}`")
            except Exception as e:
                st.error(f"Error reading template: {e}")
        else:
            if os.path.exists(default_template_path):
                with open(default_template_path, "r", encoding="utf-8") as f:
                    st.session_state.template_content = f.read()
                st.info("ℹ️ Using default SmartPropGuid template.")
            else:
                st.session_state.template_content = ""
                st.warning("⚠️ System default template not found. Please upload a template.")
                
        template_content = st.session_state.template_content
        
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
            # Get postcode from suburb input
            suburb_input = st.session_state.get("suburb", "").strip()
            postcode_str = ""
            if suburb_input:
                import re
                pm = re.search(r"\b\d{3,4}\b", suburb_input)
                postcode_str = pm.group(0) if pm else ""

            # Try to auto-load from Property_Data_Split if no manual file is uploaded
            df_active = st.session_state.get("df_data")
            if df_active is None and postcode_str:
                try:
                    pc_val = float(postcode_str)
                    split_dir = r"C:\Users\ahmma\Desktop\Property_Data_Split"
                    if os.path.exists(split_dir):
                        for fname in os.listdir(split_dir):
                            if fname.startswith("postcode_") and fname.endswith(".csv"):
                                parts = fname.replace("postcode_", "").replace(".csv", "").split("_to_")
                                if len(parts) == 2:
                                    start_pc = float(parts[0])
                                    end_pc = float(parts[1])
                                    if start_pc <= pc_val <= end_pc:
                                        csv_path = os.path.join(split_dir, fname)
                                        df_active = pd.read_csv(csv_path)
                                        st.info(f"ℹ️ Automatically loaded postcode dataset: `{fname}`")
                                        break
                except Exception as e:
                    st.warning(f"⚠️ Could not auto-load postcode dataset: {e}")

            # Filter data to make prompt compact and relevant
            df_filtered = None
            if df_active is not None:
                df_filtered = filter_property_data(
                    df_active, 
                    postcode_str, 
                    st.session_state.get("budget", ""), 
                    st.session_state.get("property_type", "")
                )

            # Prepare instructions and data details to inject into Gemini prompt
            data_context = ""
            if df_filtered is not None and len(df_filtered) > 0:
                data_context = f"Manual Listings Data Compiled (Filtered for Postcode {postcode_str}):\n{df_filtered.to_string(index=False)}"
            else:
                data_context = "No Listing data matching the criteria was found or uploaded. Generate standard market advice for the suburb based on public statistics."

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

            loader_placeholder = start_loader("AI is analyzing data and populating report layout…")
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
            finally:
                stop_loader(loader_placeholder)

        # Render generated report and PDF download option if exists
        if st.session_state.generated_report_html:
            st.markdown("### Generated Report Preview")
            
            # PDF Generation Block
            html_code = st.session_state.generated_report_html
            
            # Compiling helper to convert HTML to PDF bytes
            # def get_pdf_bytes(html_text):
            #     pdf_io = io.BytesIO()
            #     pisa_status = pisa.CreatePDF(html_text, dest=pdf_io)
            #     if pisa_status.err:
            #         return None
            #     return pdf_io.getvalue()

            def to_data_uri(path, mime):
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                return f"data:{mime};base64,{b64}"

            logo_uri = to_data_uri(os.path.join(script_dir, "LOGO.svg"), "image/svg+xml")
            house_uri = to_data_uri(os.path.join(script_dir, "House.png"), "image/png")

            html_code = html_code.replace('src="LOGO.svg"', f'src="{logo_uri}"')
            html_code = html_code.replace('src="House.png"', f'src="{house_uri}"')

            async def get_pdf_bytes_playwright(html_text):
                async with async_playwright() as p:
                    browser = await p.chromium.launch()
                    try:
                        page = await browser.new_page()
                        await page.set_content(html_text, wait_until="networkidle")
                        
                        pdf_bytes = await page.pdf(
                            format="A4",
                            print_background=True,
                            margin={"top": "0px", "right": "0px", "bottom": "14mm", "left": "0px"},
                            display_header_footer=True,
                            header_template="<span></span>",  # empty — suppresses Chromium's default title/url header
                            footer_template="""
                                <div style="width:100%; font-family:'Helvetica Neue', Helvetica, Arial, sans-serif;
                                            font-size:8pt; color:#71717a; text-align:right; padding-right:12mm;">
                                    Page <span class="pageNumber"></span> of <span class="totalPages"></span>
                                </div>
                            """,
                        )
                        return pdf_bytes
                    finally:
                        # This ensures the browser ALWAYS closes, even if an error occurs
                        await browser.close()

            # In Streamlit, use asyncio to run this:
            # pdf_bytes = asyncio.run(get_pdf_bytes_playwright(html_code))
                
            
            pdf_bytes = asyncio.run(get_pdf_bytes_playwright(html_code))


            
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
