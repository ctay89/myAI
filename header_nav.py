"""Shared UI chrome for Stories / Settings / About pages."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ASSETS_DIR = Path(__file__).parent / "assets"
BOOK_ICON_FILE = ASSETS_DIR / "mascot_book.png"
FRAUNCES_FONT_FILE = ASSETS_DIR / "fonts" / "Fraunces-Variable.ttf"
LOGO_FILE = ASSETS_DIR / "yourstoriesai_logo.png"
if not LOGO_FILE.exists():
    LOGO_FILE = ASSETS_DIR / "yourtalesai_logo.png"
if not LOGO_FILE.exists():
    LOGO_FILE = ASSETS_DIR / "chuckai_logo.png"
ICON_FILE = BOOK_ICON_FILE if BOOK_ICON_FILE.exists() else ASSETS_DIR / "mascot_rabbit.png"
if not ICON_FILE.exists():
    ICON_FILE = ASSETS_DIR / "robot_clean.png"


def render_brand_sidebar(
    *,
    message: str | None = None,
    show_models: bool = False,
) -> None:
    """Left-nav chrome matching Stories: YourStoriesAI logo + collapse control."""
    if LOGO_FILE.exists():
        logo_kwargs: dict = {"size": "medium"}
        if ICON_FILE.exists():
            logo_kwargs["icon_image"] = str(ICON_FILE)
        st.logo(str(LOGO_FILE), **logo_kwargs)

    with st.sidebar:
        st.markdown(
            '<div class="nav-section-gap"></div>'
            '<div class="nav-divider"></div>',
            unsafe_allow_html=True,
        )
        if message:
            st.markdown(
                f'<p class="nav-sidebar-message">{html.escape(message)}</p>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="nav-divider"></div>',
                unsafe_allow_html=True,
            )
        elif show_models:
            from preferences import (
                display_model_name,
                image_model_label,
                image_model_style,
                list_ollama_models,
                resolve_image_model,
                resolve_preferred_auto_generate_images,
                resolve_preferred_image_model,
                resolve_preferred_model,
            )

            if "model" not in st.session_state:
                st.session_state.model = resolve_preferred_model(list_ollama_models())
            if "image_model" not in st.session_state:
                st.session_state.image_model = resolve_image_model(
                    resolve_preferred_image_model()
                )
            story_model_label = display_model_name(st.session_state.model)
            image_label = image_model_label(st.session_state.image_model)
            image_style = image_model_style(st.session_state.image_model)
            auto_images_label = (
                "On" if resolve_preferred_auto_generate_images() else "Off"
            )
            st.markdown('<p class="nav-label">Story model</p>', unsafe_allow_html=True)
            st.markdown(
                f'<p class="nav-model-readonly">{html.escape(story_model_label)}</p>',
                unsafe_allow_html=True,
            )
            st.markdown('<p class="nav-label">Image model</p>', unsafe_allow_html=True)
            st.markdown(
                f'<p class="nav-model-readonly">{html.escape(image_label)}</p>'
                f'<p class="nav-model-style">IMAGE MODEL TYPE: '
                f"{html.escape(image_style)}</p>",
                unsafe_allow_html=True,
            )
            st.markdown(
                '<p class="nav-label">Generate image per prompt</p>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<p class="nav-model-readonly">{html.escape(auto_images_label)}</p>',
                unsafe_allow_html=True,
            )

    st.markdown(
        """
        <style>
        :root {
            --nav-bg: #f3f8f9;
            --nav-border: #d4e4e8;
            --nav-text: #1a2b32;
            --nav-muted: #5a7380;
        }
        section[data-testid="stSidebar"] {
            padding-top: 0 !important;
            position: relative !important;
            background: var(--nav-bg) !important;
            border-right: 1px solid var(--nav-border) !important;
        }
        section[data-testid="stSidebar"] > div:first-child {
            display: flex !important;
            flex-direction: column;
            height: 100%;
            position: relative !important;
            padding-top: 0 !important;
            gap: 0 !important;
            background: var(--nav-bg) !important;
        }
        [data-testid="stSidebarHeader"] {
            padding-top: 0.55rem !important;
            padding-bottom: 0.15rem !important;
            margin: 0 !important;
            min-height: 0 !important;
            background: transparent !important;
            display: flex !important;
            align-items: center !important;
        }
        [data-testid="stSidebarHeader"] [data-testid="stLogo"],
        [data-testid="stSidebarHeader"] [data-testid="stSidebarLogo"],
        [data-testid="stSidebarHeader"] [data-testid="stSidebarCollapseButton"] {
            display: flex !important;
            align-items: center !important;
            background: transparent !important;
            box-shadow: none !important;
            border: none !important;
        }
        [data-testid="stSidebarHeader"] [data-testid="stLogo"] img,
        [data-testid="stSidebarHeader"] [data-testid="stSidebarLogo"] img,
        [data-testid="stSidebarHeader"] img {
            max-height: 1.65rem !important;
            height: 1.65rem !important;
            width: auto !important;
            object-fit: contain !important;
            background: transparent !important;
        }
        [data-testid="stLogo"],
        [data-testid="stSidebarLogo"],
        [data-testid="stLogo"] a,
        [data-testid="stSidebarLogo"] a {
            background: transparent !important;
            box-shadow: none !important;
        }
        [data-testid="stSidebarContent"] {
            padding: 0.35rem 0.85rem 1rem 0.85rem !important;
            margin-top: 0 !important;
            height: 100%;
            position: relative !important;
            background: transparent !important;
        }
        section[data-testid="stSidebar"] .nav-label {
            display: block !important;
            margin: 0.85rem 0 0.35rem 0 !important;
            padding: 0 !important;
            color: var(--nav-muted) !important;
            font-size: 0.68rem !important;
            font-weight: 700 !important;
            letter-spacing: 0.06em !important;
            text-transform: uppercase !important;
            line-height: 1.2 !important;
        }
        section[data-testid="stSidebar"] .nav-section-gap {
            height: 0.65rem;
        }
        section[data-testid="stSidebar"] .nav-divider {
            border: none !important;
            border-top: 1px solid var(--nav-border) !important;
            margin: 0.35rem 0 !important;
            width: 100%;
        }
        section[data-testid="stSidebar"] .nav-sidebar-message {
            display: block !important;
            margin: 0.85rem 0 !important;
            padding: 0 !important;
            color: var(--nav-text) !important;
            font-size: 0.92rem !important;
            font-weight: 500 !important;
            line-height: 1.45 !important;
        }
        section[data-testid="stSidebar"] .nav-model-style {
            display: block !important;
            margin: 0 0 0 0.35rem !important;
            padding: 0 !important;
            color: var(--nav-muted) !important;
            font-size: 0.84rem !important;
            font-weight: 600 !important;
            line-height: 1.25 !important;
            letter-spacing: 0.01em !important;
        }
        section[data-testid="stSidebar"] .nav-model-readonly {
            display: block !important;
            margin: 0 0 0.55rem 0.35rem !important;
            padding: 0 !important;
            color: var(--nav-text) !important;
            font-size: 0.9rem !important;
            font-weight: 500 !important;
            line-height: 1.3 !important;
            background: transparent !important;
            border: none !important;
            border-radius: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _fraunces_font_face_css() -> str:
    if not FRAUNCES_FONT_FILE.exists():
        return ""
    b64 = base64.b64encode(FRAUNCES_FONT_FILE.read_bytes()).decode("ascii")
    return f"""
    @font-face {{
        font-family: "FrauncesBrand";
        src: url("data:font/ttf;base64,{b64}") format("truetype");
        font-weight: 100 900;
        font-style: normal;
        font-display: swap;
    }}
    """


def render_branded_page_title(title: str, subtitle: str = "") -> None:
    """Centered page heading with book icon + Fraunces, matching the Stories hero."""
    icon_css = ""
    if BOOK_ICON_FILE.exists():
        b64 = base64.b64encode(BOOK_ICON_FILE.read_bytes()).decode("ascii")
        icon_url = f"data:image/png;base64,{b64}"
        icon_css = f"""
        [data-testid="stHeadingWithActionElements"] h1::before,
        .stHeading h1::before {{
            content: "";
            display: inline-block;
            width: 3.5rem;
            height: 3.5rem;
            margin-right: 0.75rem;
            flex-shrink: 0;
            background: url("{icon_url}") no-repeat center / contain;
        }}
        """

    # Style only — keep huge font/icon data out of the same block as body HTML,
    # which Streamlit otherwise escapes and shows as literal text.
    st.markdown(
        f"""
        <style>
        {_fraunces_font_face_css()}
        [data-testid="stHeadingWithActionElements"]:has(h1),
        .stHeading:has(h1) {{
            display: flex !important;
            justify-content: center !important;
            width: 100% !important;
        }}
        [data-testid="stHeadingWithActionElements"] h1,
        .stHeading h1 {{
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 0 !important;
            color: #1a2b32 !important;
            font-family: "FrauncesBrand", Georgia, "Palatino Linotype", serif !important;
            font-size: 2.15rem !important;
            font-weight: 750 !important;
            letter-spacing: -0.02em !important;
            text-align: center !important;
            line-height: 1.15 !important;
        }}
        [data-testid="stHeadingWithActionElements"]:has(h2),
        [data-testid="stHeadingWithActionElements"]:has(h3),
        .stHeading:has(h2),
        .stHeading:has(h3) {{
            display: flex !important;
            justify-content: flex-start !important;
            width: 100% !important;
        }}
        [data-testid="stHeadingWithActionElements"] h2,
        [data-testid="stHeadingWithActionElements"] h3,
        .stHeading h2,
        .stHeading h3 {{
            text-align: left !important;
            width: 100% !important;
        }}
        .ys-page-tagline {{
            margin: 0.15rem 0 2.25rem 0 !important;
            padding: 0 !important;
            color: #5a7380 !important;
            font-size: 1.08rem !important;
            font-weight: 500 !important;
            font-family: Georgia, "Palatino Linotype", "Book Antiqua", Palatino, serif !important;
            letter-spacing: 0.01em !important;
            line-height: 1.35 !important;
            font-style: italic !important;
            text-align: center !important;
        }}
        {icon_css}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title(title)
    if subtitle:
        st.markdown(
            f'<p class="ys-page-tagline">{html.escape(subtitle)}</p>',
            unsafe_allow_html=True,
        )


def apply_forest_background(*, include_chat_input: bool = False) -> None:
    """Apply the selected washed backdrop (Forest by default)."""
    from preferences import background_file, resolve_preferred_background

    bg_file = background_file(resolve_preferred_background())
    if not bg_file.exists():
        bg_file = ASSETS_DIR / "chat_bg_forest.png"
    if not bg_file.exists():
        return

    bg_b64 = base64.b64encode(bg_file.read_bytes()).decode("ascii")
    bg_url = f'url("data:image/png;base64,{bg_b64}")'
    forest_fill = (
        "linear-gradient(rgba(255, 255, 255, 0.55), rgba(255, 255, 255, 0.55)), "
        f"{bg_url}"
    )

    chat_input_css = ""
    if include_chat_input:
        chat_input_css = f"""
    [data-testid="stBottom"],
    [data-testid="stBottom"] > div,
    [data-testid="stBottomBlockContainer"],
    [data-testid="stBottomBlockContainer"] > div,
    .stBottomBlockContainer,
    [data-testid="stChatInputContainer"],
    [data-testid="stChatInputContainer"] > div {{
        background: transparent !important;
        background-color: transparent !important;
        background-image: none !important;
        box-shadow: none !important;
    }}
    [data-testid="stChatInput"] {{
        min-height: 6.5rem !important;
        align-items: stretch !important;
        overflow: hidden !important;
        border-radius: 0.85rem !important;
        background-image: {forest_fill} !important;
        background-size: cover !important;
        background-position: center bottom !important;
        background-repeat: no-repeat !important;
        background-color: transparent !important;
    }}
    [data-testid="stChatInput"] *,
    [data-testid="stChatInput"] > div,
    [data-testid="stChatInput"] div[data-baseweb="base-input"],
    [data-testid="stChatInput"] [data-baseweb="textarea"],
    [data-testid="stChatInput"] textarea {{
        background: transparent !important;
        background-color: transparent !important;
        background-image: none !important;
    }}
    [data-testid="stChatInput"] textarea {{
        min-height: 5.25rem !important;
        height: 5.25rem !important;
        max-height: 12rem !important;
        line-height: 1.45 !important;
        padding-top: 0.65rem !important;
        padding-bottom: 0.65rem !important;
        resize: vertical !important;
        overflow-y: auto !important;
        color: #1a2b32 !important;
        caret-color: #1a2b32 !important;
        background-image: {forest_fill} !important;
        background-size: cover !important;
        background-position: center bottom !important;
        background-repeat: no-repeat !important;
    }}
    [data-testid="stChatInput"] textarea::placeholder {{
        color: #5a7380 !important;
        opacity: 0.9 !important;
    }}
        """

    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: {bg_url} !important;
            background-size: cover !important;
            background-position: center center !important;
            background-repeat: no-repeat !important;
            background-attachment: fixed !important;
        }}
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        .main,
        .main .block-container,
        [data-testid="stMainBlockContainer"],
        section.main {{
            background: transparent !important;
            background-color: transparent !important;
        }}
        [data-testid="stHeader"] {{
            background: rgba(255, 255, 255, 0.72) !important;
            background-color: rgba(255, 255, 255, 0.72) !important;
            background-image: none !important;
            backdrop-filter: blur(8px) !important;
            -webkit-backdrop-filter: blur(8px) !important;
            border-bottom: none !important;
            box-shadow: none !important;
        }}
        [data-testid="stHeader"] > div,
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"] {{
            background: transparent !important;
            background-color: transparent !important;
            background-image: none !important;
            box-shadow: none !important;
        }}
        {chat_input_css}
        </style>
        """,
        unsafe_allow_html=True,
    )

    bg_data_url = f"data:image/png;base64,{bg_b64}"
    paint_chat = "true" if include_chat_input else "false"
    components.html(
        f"""
        <script>
        (function () {{
          var BG = {json.dumps(bg_data_url)};
          var FILL = 'linear-gradient(rgba(255,255,255,0.55), rgba(255,255,255,0.55)), url("' + BG + '")';
          var PAINT_CHAT = {paint_chat};
          function paint() {{
            var doc = window.parent.document;
            var app = doc.querySelector('.stApp');
            if (app) {{
              app.style.setProperty('background-image', 'url("' + BG + '")', 'important');
              app.style.setProperty('background-size', 'cover', 'important');
              app.style.setProperty('background-position', 'center center', 'important');
              app.style.setProperty('background-repeat', 'no-repeat', 'important');
              app.style.setProperty('background-attachment', 'fixed', 'important');
            }}
            var header = doc.querySelector('[data-testid="stHeader"]');
            if (header) {{
              header.style.setProperty('background', 'rgba(255, 255, 255, 0.72)', 'important');
              header.style.setProperty('background-color', 'rgba(255, 255, 255, 0.72)', 'important');
              header.style.setProperty('background-image', 'none', 'important');
              header.style.setProperty('backdrop-filter', 'blur(8px)', 'important');
              header.style.setProperty('-webkit-backdrop-filter', 'blur(8px)', 'important');
              header.style.setProperty('box-shadow', 'none', 'important');
            }}
            if (!PAINT_CHAT) return;
            var bottom = doc.querySelector('[data-testid="stBottom"]');
            if (bottom) {{
              bottom.style.setProperty('background', 'transparent', 'important');
              bottom.style.setProperty('background-color', 'transparent', 'important');
            }}
            var box = doc.querySelector('[data-testid="stChatInput"]');
            if (!box) return;
            box.style.setProperty('background-image', FILL, 'important');
            box.style.setProperty('background-size', 'cover', 'important');
            box.style.setProperty('background-position', 'center bottom', 'important');
            box.style.setProperty('background-color', 'transparent', 'important');
            box.style.setProperty('min-height', '6.5rem', 'important');
            box.querySelectorAll('div, textarea').forEach(function (el) {{
              el.style.setProperty('background-color', 'transparent', 'important');
              if (el.tagName === 'TEXTAREA') {{
                el.style.setProperty('background-image', FILL, 'important');
                el.style.setProperty('background-size', 'cover', 'important');
                el.style.setProperty('background-position', 'center bottom', 'important');
                el.style.setProperty('min-height', '5.25rem', 'important');
              }} else {{
                el.style.setProperty('background-image', 'none', 'important');
              }}
            }});
          }}
          paint();
          var doc = window.parent.document;
          if (!window.parent.__yourTalesChatBgObs) {{
            window.parent.__yourTalesChatBgObs = new MutationObserver(function () {{ paint(); }});
            window.parent.__yourTalesChatBgObs.observe(doc.body, {{ childList: true, subtree: true }});
          }}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def render_filler_page(title: str, blurb: str) -> None:
    """Minimal blank filler page (routed via st.navigation in app.py)."""
    apply_forest_background(include_chat_input=False)
    st.title(title)
    st.markdown(blurb)
    st.info("This page is a placeholder and will be filled in later.")
