import os
import streamlit as st
from dotenv import load_dotenv

# Budget bracket options for the intake form, mapped to their (min, max) bounds
# in dollars (None = open-ended). Single source of truth for both the
# selectbox options (form.py) and the listings filter (services.py), so the
# two can never drift.
BUDGET_RANGES = {
    "Under $500k": (None, 500_000),
    "$500k–$800k": (500_000, 800_000),
    "$800k–$1.2M": (800_000, 1_200_000),
    "$1.2M–$1.5M": (1_200_000, 1_500_000),
    "$1.5M–$2M": (1_500_000, 2_000_000),
    "$2M–$2.5M": (2_000_000, 2_500_000),
    "$2.5M–$3M": (2_500_000, 3_000_000),
    "$3M–$4M": (3_000_000, 4_000_000),
    "$4M–$5M": (4_000_000, 5_000_000),
    "Above $5M": (5_000_000, None),
}
BUDGET_OPTIONS = list(BUDGET_RANGES.keys())


class AppConfig:
    def __init__(self):
        # Calculate project root (one level up from the components directory)
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Both paths were previously hardcoded to a specific developer's
        # machine (C:\Users\ahmma\...), which breaks Submit/postcode-autoload
        # for anyone else. excel_path resolves to the tracked file in the
        # repo root; split_dir defaults to a folder inside the repo (create
        # it and drop in postcode_<min>_to_<max>.csv files to enable postcode
        # auto-load -- this data was never committed, so the feature no-ops
        # gracefully without it).
        self.excel_path = os.path.join(self.project_root, "SPG_Customer_Intake_Form.xlsx")
        self.split_dir = os.path.join(self.project_root, "Property_Data_Split")

    def load_env(self):
        # Load environment variables from Cred.env or .env relative to script directory
        cred_path = os.path.join(self.project_root, "Cred.env")
        env_path = os.path.join(self.project_root, ".env")

        if os.path.exists(cred_path):
            load_dotenv(cred_path, override=True)
        elif os.path.exists(env_path):
            load_dotenv(env_path, override=True)

    @property
    def anthropic_api_key(self) -> str:
        return os.environ.get("ANTHROPIC_API_KEY", "")

    @property
    def htag_api_key(self) -> str:
        return os.environ.get("HTAG_API_KEY", "")

    @property
    def claude_model(self) -> str:
        return os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

    def get_asset_path(self, filename: str) -> str:
        return os.path.join(self.project_root, filename)


class SessionState:
    FORM_DEFAULTS = {
        "full_name": "",
        "phone": "",
        "email": "",
        "property_type": "House",
        "suburb": "",
        "postcode": "",
        "state": "",
        "budget": "Under $500k",
        "intention": "Live in",
    }

    def initialize_defaults(self):
        if "theme" not in st.session_state:
            st.session_state.theme = "dark"

        if "data_source_mode" not in st.session_state:
            st.session_state.data_source_mode = "📁 Upload Data File (CSV / Excel)"

        if "htag_data" not in st.session_state:
            st.session_state.htag_data = None

        if "generated_report_html" not in st.session_state:
            st.session_state.generated_report_html = None

        if "generated_pdf_bytes" not in st.session_state:
            st.session_state.generated_pdf_bytes = None

        if "df_data" not in st.session_state:
            st.session_state.df_data = None

        # Form field defaults
        for k, v in self.FORM_DEFAULTS.items():
            if k not in st.session_state:
                st.session_state[k] = v

    @property
    def theme(self) -> str:
        return st.session_state.get("theme", "dark")

    @theme.setter
    def theme(self, value: str):
        st.session_state.theme = value

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"

    @property
    def data_source_mode(self) -> str:
        return st.session_state.get("data_source_mode", "📁 Upload Data File (CSV / Excel)")

    @data_source_mode.setter
    def data_source_mode(self, value: str):
        st.session_state.data_source_mode = value

    @property
    def htag_data(self):
        return st.session_state.get("htag_data")

    @htag_data.setter
    def htag_data(self, value):
        st.session_state.htag_data = value

    @property
    def generated_report_html(self):
        return st.session_state.get("generated_report_html")

    @generated_report_html.setter
    def generated_report_html(self, value):
        st.session_state.generated_report_html = value

    @property
    def generated_pdf_bytes(self):
        return st.session_state.get("generated_pdf_bytes")

    @generated_pdf_bytes.setter
    def generated_pdf_bytes(self, value):
        st.session_state.generated_pdf_bytes = value

    @property
    def df_data(self):
        return st.session_state.get("df_data")

    @df_data.setter
    def df_data(self, value):
        st.session_state.df_data = value

    def reset_form(self):
        for k in self.FORM_DEFAULTS.keys():
            if k in st.session_state:
                del st.session_state[k]
        if "priorities_pills" in st.session_state:
            del st.session_state["priorities_pills"]
