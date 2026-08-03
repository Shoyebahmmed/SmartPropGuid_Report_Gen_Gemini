import os
import pandas as pd
import streamlit as st
from components.config import SessionState, AppConfig

class DataSelectionComponent:
    def __init__(self, session: SessionState, config: AppConfig):
        self.session = session
        self.config = config

    def render(self) -> str:
        st.markdown("### Manual Data Compilation & Predefined Layouts")
        st.markdown("Upload the source documents gathered by your operator for Step 3.")
        
        col_data, col_template = st.columns(2)
        text_muted = "#71717a"
        
        with col_data:
            st.markdown('<div class="zinc-card">', unsafe_allow_html=True)
            st.markdown("<h4>1. Source Data File (CSV / Excel)</h4>", unsafe_allow_html=True)
            st.markdown(f"<p style='font-size:0.8rem; color:{text_muted};'>Upload the property listings, demographics or market statistics file compiled manually.</p>", unsafe_allow_html=True)
            
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
                self.session.df_data = None
                
            st.markdown('</div>', unsafe_allow_html=True)
            
        with col_template:
            st.markdown('<div class="zinc-card">', unsafe_allow_html=True)
            st.markdown("<h4>2. Predefined Report Template (HTML)</h4>", unsafe_allow_html=True)
            st.markdown(f"<p style='font-size:0.8rem; color:{text_muted};'>Upload your customized corporate report HTML template. Leave empty to use the system default template.</p>", unsafe_allow_html=True)
            
            uploaded_template = st.file_uploader(
                "Select custom HTML template",
                type=["html", "htm"],
                key="template_uploader"
            )
            
            # Load custom or default template
            default_template_path = self.config.get_asset_path("sample_template.html")
            
            if uploaded_template is not None:
                try:
                    uploaded_template.seek(0)
                    self.session.template_content = uploaded_template.read().decode("utf-8")
                    st.success(f"Custom template loaded: `{uploaded_template.name}`")
                except Exception as e:
                    st.error(f"Error reading template: {e}")
            else:
                if os.path.exists(default_template_path):
                    with open(default_template_path, "r", encoding="utf-8") as f:
                        self.session.template_content = f.read()
                    st.info("ℹ️ Using default SmartPropGuid template.")
                else:
                    self.session.template_content = ""
                    st.warning("⚠️ System default template not found. Please upload a template.")
                    
            template_content = self.session.template_content
            
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
        
        return custom_prompt
