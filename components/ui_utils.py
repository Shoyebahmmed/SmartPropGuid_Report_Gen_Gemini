import os
import time
import base64
import html
import streamlit as st


class ProgressLoader:
    """
    Full-screen progress overlay for a multi-step pipeline (fetching HTAG
    data, generating a report...).

    The caller moves through real steps with stage(); each step owns a slice
    of the bar (start -> end percent). Inside a step the bar eases from start
    toward end over that step's typical duration, purely in CSS (no reruns),
    and never crosses into the next step's slice until the code actually
    reaches it -- so the motion is smooth but the position stays honest:
    a slow API call just makes the bar settle near the end of its slice.
    A live elapsed-seconds counter shows the app is still working.
    """

    def __init__(self, title: str, steps: list):
        self.title = title
        self.steps = list(steps)
        self.skipped = set()
        self.started_at = time.monotonic()
        self.renders = 0
        self.placeholder = st.empty()
        self.stage(0, steps[0] if steps else "", start=0, end=4, expected_seconds=3)

    def skip(self, index: int):
        """Marks a step as not applicable for this run (shown struck through)."""
        self.skipped.add(index)

    def stage(self, index: int, message: str, start: int, end: int, expected_seconds: float = 10):
        self.renders += 1
        elapsed = int(time.monotonic() - self.started_at)
        # Animation names alternate per render so the browser restarts the
        # easing from this stage's start instead of continuing the old one.
        flip = self.renders % 2
        items = []
        for i, label in enumerate(self.steps):
            if i in self.skipped:
                state = "skipped"
            elif i < index:
                state = "done"
            elif i == index:
                state = "active"
            else:
                state = "pending"
            items.append(f'<li class="lp-step lp-{state}"><span class="lp-dot"></span>{html.escape(label)}</li>')

        self.placeholder.markdown(
            f'''<div class="loader-overlay"><div class="loader-container">
                <div class="lp-title">{html.escape(self.title)}</div>
                <div class="lp-percent" style="--from:{start};--to:{max(start, end - 1)};--dur:{expected_seconds}s;animation-name:lp-ease{flip};"></div>
                <div class="loader-progress-wrap">
                    <div class="loader-progress-fill" style="--from:{start};--to:{max(start, end - 1)};--dur:{expected_seconds}s;animation-name:lp-ease{flip},loader-flow;"></div>
                </div>
                <p class="loader-text">{html.escape(message)}</p>
                <ul class="lp-steps">{"".join(items)}</ul>
                <div class="lp-elapsed" style="--t0:{elapsed};animation-name:lp-tick{flip};"></div>
            </div></div>''',
            unsafe_allow_html=True,
        )

    def finish(self, message: str = "Done!"):
        self.stage(len(self.steps), message, start=100, end=101, expected_seconds=0.1)

    def stop(self):
        self.placeholder.empty()


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
    def start_loader(title: str, steps: list) -> "ProgressLoader":
        """Opens the full-screen progress overlay. See ProgressLoader."""
        return ProgressLoader(title, steps)

    @staticmethod
    def stop_loader(loader):
        if loader:
            loader.stop()

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
            .zinc-card h4, .block-container h3,
            div[data-testid="stVerticalBlockBorderWrapper"] h4 {{
                font-family: 'Playfair Display', serif !important;
            }}

            /* Loader – a full-screen blurred, unclickable overlay (like a
               modal) holding ProgressLoader's step list and progress bar.
               --p is a registered integer so it can be animated (eased) and
               also printed as the percentage via a CSS counter. */
            @property --p {{ syntax: '<integer>'; inherits: false; initial-value: 0; }}
            @property --t {{ syntax: '<integer>'; inherits: false; initial-value: 0; }}
            @keyframes lp-ease0 {{ from {{ --p: var(--from); }} to {{ --p: var(--to); }} }}
            @keyframes lp-ease1 {{ from {{ --p: var(--from); }} to {{ --p: var(--to); }} }}
            @keyframes lp-tick0 {{ from {{ --t: var(--t0); }} to {{ --t: calc(var(--t0) + 3600); }} }}
            @keyframes lp-tick1 {{ from {{ --t: var(--t0); }} to {{ --t: calc(var(--t0) + 3600); }} }}
            .lp-title {{
                font-family: 'Playfair Display', serif;
                font-size: 1.15rem;
                font-weight: 700;
                color: {text_color};
                margin-bottom: 0.4rem;
            }}
            .lp-percent {{
                font-size: 2.2rem;
                font-weight: 700;
                color: {accent_color};
                font-variant-numeric: tabular-nums;
                animation-duration: var(--dur);
                animation-timing-function: cubic-bezier(0.15, 0.7, 0.3, 1);
                animation-fill-mode: forwards;
                counter-reset: pct var(--p);
            }}
            .lp-percent::after {{ content: counter(pct) "%"; }}
            .lp-steps {{
                list-style: none;
                width: 100%;
                margin: 1.1rem 0 0;
                padding: 0.9rem 0 0;
                border-top: 1px solid {border_color};
            }}
            .lp-step {{
                display: flex;
                align-items: center;
                gap: 0.6rem;
                font-size: 0.84rem;
                padding: 0.22rem 0;
                color: {text_dim};
            }}
            .lp-dot {{
                flex: 0 0 auto;
                width: 16px;
                height: 16px;
                border-radius: 50%;
                border: 2px solid {border_color};
                box-sizing: border-box;
            }}
            .lp-done {{ color: {text_muted}; }}
            .lp-done .lp-dot {{
                background: {accent_color};
                border-color: {accent_color};
                position: relative;
            }}
            .lp-done .lp-dot::after {{
                content: "";
                position: absolute;
                left: 4px; top: 1px;
                width: 4px; height: 8px;
                border: solid #162338;
                border-width: 0 2px 2px 0;
                transform: rotate(45deg);
            }}
            .lp-active {{ color: {text_color}; font-weight: 600; }}
            .lp-active .lp-dot {{
                border-color: {border_color};
                border-top-color: {accent_color};
                animation: loader-spin 0.8s linear infinite;
            }}
            .lp-skipped {{ text-decoration: line-through; opacity: 0.55; }}
            .lp-elapsed {{
                margin-top: 0.9rem;
                font-size: 0.75rem;
                color: {text_dim};
                font-variant-numeric: tabular-nums;
                animation-duration: 3600s;
                animation-timing-function: linear;
                animation-fill-mode: forwards;
                counter-reset: secs var(--t);
            }}
            .lp-elapsed::after {{ content: counter(secs) "s elapsed"; }}
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
                border-radius: 16px;
                width: min(380px, calc(100vw - 32px));
                box-shadow: 0 12px 40px rgba(0,0,0,0.4);
            }}
            @keyframes loader-spin {{
                to {{ transform: rotate(360deg); }}
            }}
            .loader-progress-wrap {{
                width: 100%;
                height: 8px;
                background: {border_color};
                border-radius: 4px;
                overflow: hidden;
                margin-top: 0.7rem;
            }}
            .loader-progress-fill {{
                height: 100%;
                width: calc(var(--p) * 1%);
                border-radius: 4px;
                background: linear-gradient(90deg, #b58b33, #d7b35e, #f0d9a8, #d7b35e, #b58b33);
                background-size: 200% 100%;
                /* animation-name is set inline: lp-ease0/1 (width) + loader-flow (shimmer) */
                animation-duration: var(--dur), 1.8s;
                animation-timing-function: cubic-bezier(0.15, 0.7, 0.3, 1), linear;
                animation-iteration-count: 1, infinite;
                animation-fill-mode: forwards, none;
            }}
            @keyframes loader-flow {{
                0% {{ background-position: 0% 0; }}
                100% {{ background-position: -200% 0; }}
            }}
            .loader-text {{
                margin: 0.8rem 0 0;
                font-size: 0.85rem;
                letter-spacing: 0.02em;
                text-align: center;
                color: {text_muted};
                min-height: 2.4em;
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

            /* Custom Card container -- .zinc-card is a legacy raw-HTML class
               kept only in case any old markup still references it. Every
               card in this app is now a real st.container(border=True), so
               it's styled the same way via its actual DOM wrapper instead:
               a raw '<div class="zinc-card">' from one st.markdown call and
               its '</div>' from a separate call never really wrap anything
               (each st.* call is its own DOM node) -- they render as their
               own stray empty boxes rather than containing the widgets
               drawn "inside" them. st.container(border=True) has no such
               trap: everything drawn in its `with` block is real DOM
               content inside its wrapper. */
            .zinc-card,
            div[data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlock"] {{
                background-color: {card_color} !important;
                border: 1px solid {border_color} !important;
                border-radius: 12px !important;
                padding: 1.75rem !important;
                gap: 1rem !important;
                transition: border-color 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }}
            div[data-testid="stVerticalBlockBorderWrapper"] {{
                margin-bottom: 1.5rem;
            }}
            .zinc-card:hover,
            div[data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlock"]:hover {{
                border-color: {accent_color} !important;
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
            /* Auto-filled read-only fields (Postcode / State): keep the value
               fully readable -- Streamlit's default disabled styling fades it
               to near-invisible -- with a faint gold tint marking it auto-filled. */
            .stTextInput input:disabled {{
                color: {text_color} !important;
                -webkit-text-fill-color: {text_color} !important;
                opacity: 1 !important;
                font-weight: 600 !important;
                background-color: transparent !important;
                border: none !important;
                cursor: default !important;
            }}
            /* ...the grey disabled background is painted by the input's
               wrapper div, so the tint goes there. */
            .stTextInput div:has(> input:disabled) {{
                background-color: rgba(215, 179, 94, 0.10) !important;
                border: 1px dashed rgba(215, 179, 94, 0.45) !important;
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
            .stTextInput input::placeholder,
            .stSelectbox input::placeholder,
            .stTextArea textarea::placeholder {{
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

            /* Chip pickers (st.pills: priorities, prompt suggestions) --
               rendered as button[data-variant="pills"] inside a
               stButtonGroup. Selected = solid brand gold, so a picked chip
               reads as "yes, this", never as an error/red state. */
            [data-testid="stButtonGroup"] button[data-variant="pills"] {{
                background-color: {bg_subtle} !important;
                border: 1px solid {border_color} !important;
                border-radius: 999px !important;
                transition: all 0.15s ease !important;
            }}
            [data-testid="stButtonGroup"] button[data-variant="pills"] p {{
                color: {text_color} !important;
            }}
            [data-testid="stButtonGroup"] button[data-variant="pills"]:hover {{
                border-color: {accent_color} !important;
            }}
            [data-testid="stButtonGroup"] button[data-variant="pills"][aria-pressed="true"] {{
                background-color: {accent_color} !important;
                border-color: {accent_color} !important;
                box-shadow: 0 2px 8px rgba(215, 179, 94, 0.35) !important;
            }}
            [data-testid="stButtonGroup"] button[data-variant="pills"][aria-pressed="true"] p {{
                color: #162338 !important;
                font-weight: 600 !important;
            }}

            /* Primary call-to-action buttons (Generate AI Report, Next) --
               solid brand gold so they stand out from the navy secondary
               buttons instead of blending in. */
            button[data-testid="stBaseButton-primary"] {{
                background: linear-gradient(135deg, #e3c477 0%, {accent_color} 55%, #c49a42 100%) !important;
                border: 1px solid #c49a42 !important;
                color: #162338 !important;
                font-weight: 700 !important;
                box-shadow: 0 6px 18px rgba(215, 179, 94, 0.28) !important;
                transition: transform 0.15s ease, box-shadow 0.15s ease !important;
            }}
            button[data-testid="stBaseButton-primary"]:hover {{
                transform: translateY(-1px);
                box-shadow: 0 10px 24px rgba(215, 179, 94, 0.4) !important;
            }}
            button[data-testid="stBaseButton-primary"] p,
            button[data-testid="stBaseButton-primary"] span {{
                color: #162338 !important;
                font-weight: 700 !important;
            }}
            /* The big calls to action: Generate AI Report and Download PDF */
            .st-key-generate_btn button,
            .st-key-download_pdf_btn button {{
                min-height: 4.2rem !important;
                border-radius: 12px !important;
            }}
            .st-key-generate_btn button p,
            .st-key-download_pdf_btn button p {{
                font-size: 1.15rem !important;
                letter-spacing: 0.01em;
            }}

            /* HTAG fetch: gold-outline secondary action -- branded, but
               visually below the solid-gold primary buttons. */
            .st-key-htag_fetch_btn button {{
                min-height: 3rem !important;
                background: rgba(215, 179, 94, 0.08) !important;
                border: 1.5px solid {accent_color} !important;
                border-radius: 10px !important;
                transition: background 0.15s ease !important;
            }}
            .st-key-htag_fetch_btn button:hover {{
                background: rgba(215, 179, 94, 0.18) !important;
            }}
            .st-key-htag_fetch_btn button p,
            .st-key-htag_fetch_btn button span {{
                color: {accent_color} !important;
                font-weight: 600 !important;
            }}

            /* Read-only location summary chips (Tab 1 + Tab 2) */
            .loc-chip {{
                display: inline-flex;
                align-items: center;
                gap: 0.4rem;
                padding: 0.35rem 0.75rem;
                margin: 0 0.4rem 0.4rem 0;
                border-radius: 999px;
                background: rgba(215, 179, 94, 0.12);
                border: 1px solid rgba(215, 179, 94, 0.35);
                color: {text_color};
                font-size: 0.85rem;
            }}
            .loc-chip b {{ color: {accent_color}; font-weight: 600; }}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)
