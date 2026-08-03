import streamlit as st
from components.config import AppConfig, SessionState
from components.services import ExcelService, DataService, GeminiService, PdfService, TemplateService
from components.form import FormComponent
from components.data_selection import DataSelectionComponent
from components.report_generation import ReportGenerationComponent
from components.ui_utils import UiHelper

class App:
    def __init__(self):
        # 1. Config & Session Initializations
        self.config = AppConfig()
        self.config.load_env()
        
        self.session = SessionState()
        self.session.initialize_defaults()
        
        # 2. Service Initializations
        self.excel_service = ExcelService(self.config)
        self.data_service = DataService(self.config)
        self.gemini_service = GeminiService(self.config)
        self.pdf_service = PdfService(self.config)
        self.template_service = TemplateService()
        
        # 3. Component Initializations
        self.form_component = FormComponent(self.session, self.excel_service)
        self.data_selection_component = DataSelectionComponent(self.session, self.config)
        self.report_generation_component = ReportGenerationComponent(
            self.session,
            self.config,
            self.data_service,
            self.gemini_service,
            self.pdf_service,
            self.template_service
        )

    def run(self):
        # Page configuration - Must be the first Streamlit command run in the app
        st.set_page_config(
            page_title="SmartPropGuid Report Generator",
            page_icon="◆",
            layout="wide",
            initial_sidebar_state="collapsed",
        )
        
        # Injects custom theme styling
        UiHelper.inject_custom_css(self.session.theme)
        
        # Header & Brand area
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
            theme_label = "☀️ Light Mode" if self.session.theme == "dark" else "🌙 Dark Mode"
            st.button(theme_label, on_click=self.session.toggle_theme, use_container_width=True)
            
        border_color = UiHelper.get_border_color(self.session.theme)
        st.markdown(f"<hr style='margin-top:0.5rem; margin-bottom:1.5rem; border-color:{border_color}'>", unsafe_allow_html=True)
        
        # Tabs Navigation
        tab_preferences, tab_upload, tab_generate = st.tabs([
            "📋 1. Customer Preferences", 
            "📂 2. Data & Template Upload", 
            "✨ 3. AI Report Generation"
        ])
        
        with tab_preferences:
            self.form_component.render()
            
        with tab_upload:
            custom_prompt = self.data_selection_component.render()
            
        with tab_generate:
            self.report_generation_component.render(custom_prompt)

if __name__ == "__main__":
    app = App()
    app.run()
