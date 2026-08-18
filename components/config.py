import os
import google.generativeai as genai
import streamlit as st
from dotenv import load_dotenv

class AppConfig:
    def __init__(self):
        # Calculate project root (one level up from the components directory)
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.excel_path = r"C:\Users\ahmma\.gemini\antigravity-ide\scratch\SmartPropGuid_Report_Gen_Gemini\SPG_Customer_Intake_Form.xlsx"
        self.split_dir = r"C:\Users\ahmma\Desktop\Property_Data_Split"
        
    def load_env(self):
        # Load environment variables from Cred.env or .env relative to script directory
        cred_path = os.path.join(self.project_root, "Cred.env")
        env_path = os.path.join(self.project_root, ".env")

        if os.path.exists(cred_path):
            load_dotenv(cred_path, override=True)
        elif os.path.exists(env_path):
            load_dotenv(env_path, override=True)

        # Initialize Gemini API if key is present
        api_key = self.api_key
        if api_key:
            genai.configure(api_key=api_key)

    @property
    def api_key(self) -> str:
        return os.environ.get("GEMINI_API_KEY", "")

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
        "budget": "Under $500k",
        "intention": "Live in",
    }

    def initialize_defaults(self):
        if "theme" not in st.session_state:
            st.session_state.theme = "dark"

        if "ai_provider" not in st.session_state:
            st.session_state.ai_provider = "Google Gemini"

        if "data_source_mode" not in st.session_state:
            st.session_state.data_source_mode = "📁 Upload Data File (CSV / Excel)"

        if "htag_data" not in st.session_state:
            st.session_state.htag_data = None

        if "generated_report_html" not in st.session_state:
            st.session_state.generated_report_html = None

        if "df_data" not in st.session_state:
            st.session_state.df_data = None

        if "template_content" not in st.session_state:
            st.session_state.template_content = ""

        # Form field defaults
        for k, v in self.FORM_DEFAULTS.items():
            if k not in st.session_state:
                st.session_state[k] = v

        # Checkbox defaults
        for i in range(11):
            if f"priority_{i}" not in st.session_state:
                st.session_state[f"priority_{i}"] = False

    @property
    def theme(self) -> str:
        return st.session_state.get("theme", "dark")

    @theme.setter
    def theme(self, value: str):
        st.session_state.theme = value

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"

    @property
    def ai_provider(self) -> str:
        return st.session_state.get("ai_provider", "Google Gemini")

    @ai_provider.setter
    def ai_provider(self, value: str):
        st.session_state.ai_provider = value

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
    def df_data(self):
        return st.session_state.get("df_data")

    @df_data.setter
    def df_data(self, value):
        st.session_state.df_data = value

    @property
    def template_content(self) -> str:
        return st.session_state.get("template_content", "")

    @template_content.setter
    def template_content(self, value: str):
        st.session_state.template_content = value

    def reset_form(self):
        for k in self.FORM_DEFAULTS.keys():
            if k in st.session_state:
                del st.session_state[k]
        for i in range(11):
            key = f"priority_{i}"
            if key in st.session_state:
                del st.session_state[key]
