import streamlit as st

class UiHelper:
    @staticmethod
    def get_border_color(theme: str) -> str:
        return "#1e1e24" if theme == "dark" else "#e4e4e7"

    @staticmethod
    def start_loader(message: str, theme: str = "dark"):
        is_dark = theme == "dark"
        bg_subtle = "#0c0c0f" if is_dark else "#f9fafb"
        accent_color = "#2563eb"
        text_color = "#fafafa" if is_dark else "#09090b"
        
        placeholder = st.empty()
        placeholder.markdown(
            f'''<div class="loader-container">
                    <div class="loader" style="border: 4px solid {bg_subtle}; border-top: 4px solid {accent_color};"></div>
                    <p class="loader-text" style="color: {text_color};">{message}</p>
                </div>''',
            unsafe_allow_html=True,
        )
        return placeholder

    @staticmethod
    def stop_loader(placeholder):
        if placeholder:
            placeholder.empty()

    @staticmethod
    def inject_custom_css(theme: str):
        is_dark = theme == "dark"
        bg_color = "#09090b" if is_dark else "#ffffff"
        bg_subtle = "#0c0c0f" if is_dark else "#f9fafb"
        card_color = "#0c0c0f" if is_dark else "#ffffff"
        card_hover = "#131316" if is_dark else "#f4f4f5"
        border_color = "#1e1e24" if is_dark else "#e4e4e7"
        border_subtle = "#16161a" if is_dark else "#f0f0f2"
        text_color = "#fafafa" if is_dark else "#09090b"
        text_muted = "#71717a"
        text_dim = "#52525b" if is_dark else "#a1a1aa"
        accent_color = "#2563eb"

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
                background-color: {bg_color} !important;
                color: {text_color} !important;
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
                border: 4px solid {bg_subtle};
                border-top: 4px solid {accent_color};
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
                color: {text_color};
                font-size: 1.1rem;
                text-align: center;
            }}

            /* Tabs (pill-style navigation) */
            button[data-baseweb="tab"] {{
                background: transparent !important;
                color: {text_muted} !important;
                font-size: 0.88rem !important;
                font-weight: 500 !important;
                padding: 0.6rem 1.2rem !important;
                border: 1px solid transparent !important;
                border-radius: 8px !important;
                transition: all 0.2s ease !important;
            }}
            button[data-baseweb="tab"]:hover {{
                color: {text_color} !important;
                background: {card_hover} !important;
            }}
            button[data-baseweb="tab"][aria-selected="true"] {{
                color: {text_color} !important;
                background: {card_color} !important;
                border-color: {border_color} !important;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important;
            }}
            [data-baseweb="tab-highlight"], [data-baseweb="tab-border"] {{
                display: none !important;
            }}
            [data-baseweb="tab-list"] {{
                gap: 6px !important;
                background: {bg_subtle} !important;
                border: 1px solid {border_color} !important;
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
                background-color: {card_color};
                border: 1px solid {border_color};
                border-radius: 12px;
                padding: 1.75rem;
                margin-bottom: 1.5rem;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }}
            .zinc-card:hover {{
                border-color: {accent_color};
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
                color: {text_color};
                letter-spacing: -0.03em;
            }}
            .brand-subtitle {{
                font-size: 0.88rem;
                color: {text_muted};
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
                color: {accent_color};
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
                background-color: {bg_subtle} !important;
                border: 1px solid {border_color} !important;
                color: {text_color} !important;
                border-radius: 8px !important;
            }}
            /* Selectbox dropdown option text */
            [data-baseweb="select"] span,
            [data-baseweb="select"] div {{
                color: {text_color} !important;
            }}
            /* Placeholder text color */
            .stTextInput input::placeholder {{
                color: {text_dim} !important;
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
                border: 1px solid {border_color};
            }}
            .data-table th {{
                background: {bg_subtle};
                color: {text_muted};
                text-align: left;
                padding: 0.75rem 1rem;
                font-size: 0.78rem;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                border-bottom: 1px solid {border_color};
            }}
            .data-table td {{
                padding: 0.8rem 1rem;
                color: {text_color};
                background: {card_color};
                border-bottom: 1px solid {border_subtle};
            }}
            .data-table tr:last-child td {{
                border-bottom: none;
            }}
            
            /* Previews */
            .preview-box {{
                background-color: {bg_subtle};
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 1rem;
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.8rem;
                overflow-x: auto;
                white-space: pre-wrap;
                color: {text_color};
            }}

            /* Theme toggle button — white bg + black text in light, dark bg + white text in dark */
            [data-testid="stBaseButton-secondary"] button,
            button[kind="secondary"],
            .stButton > button {{
                background-color: {"#1e1e24" if is_dark else "#ffffff"} !important;
                color: {text_color} !important;
                border: 1px solid {border_color} !important;
            }}
            [data-testid="stBaseButton-secondary"] button *,
            [data-testid="stBaseButton-secondary"] button p,
            [data-testid="stBaseButton-secondary"] button span,
            .stButton > button p,
            .stButton > button span {{
                color: {text_color} !important;
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
                color: {text_color} !important;
            }}

            /* Checkbox box (the square) — border and background match theme */
            [data-baseweb="checkbox"] > div:first-child,
            [data-testid="stCheckbox"] [data-baseweb="checkbox"] > div {{
                background-color: {bg_subtle} !important;
                border-color: {border_color} !important;
            }}
            /* Checked state — keep accent blue */
            [data-baseweb="checkbox"][aria-checked="true"] > div:first-child {{
                background-color: {accent_color} !important;
                border-color: {accent_color} !important;
            }}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)
