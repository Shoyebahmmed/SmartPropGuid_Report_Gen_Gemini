import os
import base64
import streamlit as st

class UiHelper:
    @staticmethod
    def get_border_color(theme: str) -> str:
        return "#26374f" if theme == "dark" else "#e8ddc4"

    @staticmethod
    def get_bg_subtle_color(theme: str) -> str:
        return "#13233b" if theme == "dark" else "#f6f1e7"

    @staticmethod
    def get_logo_data_uri(config) -> str:
        """Base64-embeds LOGO.png so it can be dropped straight into an
        st.markdown(unsafe_allow_html=True) block -- Streamlit has no
        built-in way to reference a local file path from raw HTML."""
        path = config.get_asset_path("LOGO.png")
        if not os.path.exists(path):
            return ""
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png;base64,{b64}"

    @staticmethod
    def start_loader(message: str, theme: str = "dark", percent: int = 5):
        """Creates the loader placeholder and renders its first stage.
        Call update_loader() on the returned placeholder as the report
        pipeline actually reaches each later stage -- see update_loader()."""
        placeholder = st.empty()
        UiHelper.update_loader(placeholder, message, percent, theme)
        return placeholder

    @staticmethod
    def update_loader(placeholder, message: str, percent: int, theme: str = "dark"):
        """
        Re-renders the same loader placeholder with a new stage label and
        percentage. The percentage is driven by real checkpoints the report
        generation code has actually reached (data prep done, AI response
        received, PDF compiled, etc. -- see report_generation.py) rather than
        a timer guessing elapsed time, so the bar's position always reflects
        genuine pipeline progress. The gold fill's diagonal shimmer animation
        is purely decorative "still working" motion layered on top of that
        real width -- it doesn't claim to know sub-progress within a stage
        (e.g. how far through Claude's response we are), since that isn't
        observable without response streaming.
        """
        is_dark = theme == "dark"
        text_color = "#f4f1ea" if is_dark else "#162338"
        text_muted = "#9c9484" if is_dark else "#7c7360"
        percent = max(0, min(100, percent))

        # Rendered as a fixed full-viewport overlay (not an inline block) so
        # the rest of the app is visibly dimmed/blurred and can't be clicked
        # while a report is generating.
        placeholder.markdown(
            f'''<div class="loader-overlay">
                    <div class="loader-container">
                        <div class="loader-spinner"></div>
                        <div class="loader-percent" style="color: {text_color};">{percent}%</div>
                        <div class="loader-progress-wrap">
                            <div class="loader-progress-fill" style="width: {percent}%;"></div>
                        </div>
                        <p class="loader-text" style="color: {text_muted};">{message}</p>
                    </div>
                </div>''',
            unsafe_allow_html=True,
        )

    @staticmethod
    def stop_loader(placeholder):
        if placeholder:
            placeholder.empty()

    @staticmethod
    def inject_custom_css(theme: str):
        is_dark = theme == "dark"
        # Brand palette extracted from LOGO.png (gold/taupe house-and-road
        # mark) and the PDF report's own navy+gold design -- dark mode uses
        # the report's cover navy as its base instead of a generic zinc-black,
        # and light mode leans warm/cream instead of cool grey, so the web
        # app, the logo, and the PDF report all read as one consistent brand.
        bg_color = "#0d1622" if is_dark else "#fffdf9"
        bg_subtle = UiHelper.get_bg_subtle_color(theme)
        card_color = "#162338" if is_dark else "#ffffff"
        card_hover = "#1c2d4a" if is_dark else "#f8f4ec"
        border_color = "#26374f" if is_dark else "#e8ddc4"
        border_subtle = "#1a2941" if is_dark else "#f1ece0"
        text_color = "#f4f1ea" if is_dark else "#162338"
        text_muted = "#9c9484" if is_dark else "#7c7360"
        text_dim = "#6f6858" if is_dark else "#a89b80"
        accent_color = "#d7b35e"

        css = f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@600;700&family=JetBrains+Mono:wght@400;500&display=swap');

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

            /* Section headings use the report's serif to tie web UI + PDF together */
            .zinc-card h4, .block-container h3 {{
                font-family: 'Playfair Display', serif !important;
            }}

            /* Loader – a full-screen blurred, unclickable overlay (like a
               modal) holding a real, stage-driven progress bar (see
               UiHelper.update_loader) plus a standard spinning ring so the
               page still visibly "feels alive" between stage checkpoints,
               not just a bar that sits still. */
            .loader-overlay {{
                position: fixed;
                inset: 0;
                background: rgba(13, 22, 34, 0.45);
                backdrop-filter: blur(6px);
                -webkit-backdrop-filter: blur(6px);
                z-index: 9999;
                display: flex;
                align-items: center;
                justify-content: center;
            }}
            .loader-container {{
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 2rem 2.25rem;
                background: {card_color};
                border: 1px solid {border_color};
                border-radius: 14px;
                width: 300px;
                box-shadow: 0 12px 40px rgba(0,0,0,0.4);
            }}
            .loader-spinner {{
                width: 42px;
                height: 42px;
                border-radius: 50%;
                border: 4px solid {bg_subtle};
                border-top-color: {accent_color};
                animation: loader-spin 0.85s linear infinite;
                margin-bottom: 1rem;
            }}
            @keyframes loader-spin {{
                to {{ transform: rotate(360deg); }}
            }}
            .loader-percent {{
                font-family: 'DM Sans', sans-serif;
                font-size: 1.4rem;
                font-weight: 700;
            }}
            .loader-progress-wrap {{
                width: 100%;
                height: 8px;
                background: {bg_subtle};
                border-radius: 4px;
                overflow: hidden;
                margin-top: 0.7rem;
            }}
            .loader-progress-fill {{
                height: 100%;
                border-radius: 4px;
                background: linear-gradient(90deg, #b58b33, #d7b35e, #f0d9a8, #d7b35e, #b58b33);
                background-size: 200% 100%;
                animation: loader-flow 1.8s linear infinite;
                transition: width 0.6s ease;
            }}
            @keyframes loader-flow {{
                0% {{ background-position: 0% 0; }}
                100% {{ background-position: -200% 0; }}
            }}
            .loader-text {{
                margin-top: 0.9rem;
                font-size: 0.85rem;
                letter-spacing: 0.02em;
                text-align: center;
            }}

            /* Tabs (pill-style navigation) -- current Streamlit renders these as
               react-aria components (role="tab"/"tablist"), not the older
               BaseWeb widgets, so they're targeted by role/data-testid here. */
            [data-testid="stTab"] {{
                background: transparent !important;
                color: {text_muted} !important;
                font-size: 0.88rem !important;
                font-weight: 500 !important;
                padding: 0.6rem 1.2rem !important;
                border: 1px solid transparent !important;
                border-radius: 8px !important;
                transition: all 0.2s ease !important;
            }}
            [data-testid="stTab"]:hover {{
                color: {text_color} !important;
                background: {card_hover} !important;
            }}
            [data-testid="stTab"][aria-selected="true"] {{
                color: {text_color} !important;
                background: {card_color} !important;
                border-color: {border_color} !important;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important;
            }}
            .react-aria-SelectionIndicator {{
                display: none !important;
            }}
            [role="tablist"] {{
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
                gap: 12px;
                margin-bottom: 1.5rem;
            }}
            .brand-logo-img {{
                height: 48px;
                width: auto;
                flex-shrink: 0;
            }}
            .brand-logo {{
                font-family: 'Playfair Display', serif;
                font-size: 1.6rem;
                font-weight: 700;
                color: {text_color};
                letter-spacing: -0.02em;
            }}
            .brand-title {{
                font-size: 1.6rem;
                font-weight: 700;
                color: {accent_color};
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
                background: rgba(215, 179, 94, 0.12);
                border: 1px solid rgba(215, 179, 94, 0.3);
            }}

            /* Streamlit widget overrides — selectbox, text input, multiselect.
               Current Streamlit's selectbox is a react-aria ComboBox (a text
               input with role="combobox" inside a role="group" wrapper), not
               the older BaseWeb select -- targeted here by those ARIA roles
               since the emotion-cache class names are unstable across builds. */
            .stTextInput>div>div>input,
            .stTextInput input,
            .stSelectbox [role="group"],
            .stMultiSelect [role="group"] {{
                background-color: {bg_subtle} !important;
                border: 1px solid {border_color} !important;
                color: {text_color} !important;
                border-radius: 8px !important;
            }}
            .stSelectbox input,
            .stMultiSelect input {{
                background-color: transparent !important;
                color: {text_color} !important;
            }}
            /* Dropdown flyout (rendered in a portal) and its options */
            [role="listbox"] {{
                background-color: {card_color} !important;
                border: 1px solid {border_color} !important;
            }}
            [role="option"] {{
                color: {text_color} !important;
            }}
            [role="option"]:hover,
            [role="option"][data-focused="true"] {{
                background-color: {card_hover} !important;
            }}

            /* Text area (Pre-Sales Operator Instructions prompt box) */
            .stTextArea textarea {{
                background-color: {bg_subtle} !important;
                border: 1px solid {border_color} !important;
                color: {text_color} !important;
                border-radius: 8px !important;
            }}

            /* File uploader dropzone */
            [data-testid="stFileUploaderDropzone"] {{
                background-color: {bg_subtle} !important;
                border: 1px dashed {border_color} !important;
            }}
            [data-testid="stFileUploaderDropzone"] span,
            [data-testid="stFileUploaderDropzone"] small,
            [data-testid="stFileUploaderDropzone"] div {{
                color: {text_muted} !important;
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

            /* Theme toggle button — light card bg + dark text in light, navy card bg + cream text in dark */
            [data-testid="stBaseButton-secondary"] button,
            button[kind="secondary"],
            .stButton > button {{
                background-color: {"#1c2d4a" if is_dark else "#ffffff"} !important;
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

            /* Checkbox box (the square) — border and background match theme.
               The real <input type="checkbox"> is visually hidden (clip-rect
               accessibility pattern); the visible square is the plain <div>
               immediately after it, so it's targeted structurally rather
               than by the unstable emotion-cache class Streamlit gives it. */
            .stCheckbox label > span + div {{
                background-color: {bg_subtle} !important;
                border-color: {border_color} !important;
            }}
            /* Checked state — brand gold accent. React-aria puts
               data-selected="true" on the <label> once checked. */
            .stCheckbox label[data-selected="true"] > span + div {{
                background-color: {accent_color} !important;
                border-color: {accent_color} !important;
            }}
            .stCheckbox label[data-selected="true"] > span + div svg {{
                color: #162338 !important;
            }}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)
