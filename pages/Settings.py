"""Settings — model preferences."""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from header_nav import (
    apply_forest_background,
    render_brand_sidebar,
    render_branded_page_title,
)
from preferences import (
    PARAGRAPH_RANGE_OPTIONS,
    background_keys,
    background_label,
    dedupe_models,
    display_model_name,
    image_model_keys,
    image_model_label,
    image_model_style,
    list_ollama_models,
    match_available_model,
    paragraph_range_label,
    resolve_image_model,
    resolve_preferred_auto_generate_images,
    resolve_preferred_background,
    resolve_preferred_image_model,
    resolve_preferred_model,
    resolve_preferred_paragraph_range,
    resolve_preferred_user_avatar,
    set_preferred_auto_generate_images,
    set_preferred_background,
    set_preferred_image_model,
    set_preferred_model,
    set_preferred_paragraph_range,
    set_preferred_user_avatar,
    user_avatar_file,
    user_avatar_keys,
    user_avatar_label,
)

render_brand_sidebar(
    message=(
        "Here is the Settings page. You may adjust the settings for a different story writing "
        "experience here."
    )
)
apply_forest_background(include_chat_input=False)

render_branded_page_title("Settings", "Change your settings here.")

st.markdown(
    """
    <style>
    [class*="st-key-settings_form"],
    .st-key-settings_form {
        max-width: 40rem !important;
        margin: 0.35rem 0 0 0 !important;
        padding: 0.85rem 1.1rem 1rem 1.1rem !important;
        border-left: 3px solid #0d8a9a !important;
        background: linear-gradient(
            105deg,
            rgba(243, 248, 249, 0.88) 0%,
            rgba(255, 255, 255, 0.55) 100%
        ) !important;
        border-radius: 0 0.65rem 0.65rem 0 !important;
    }
    [class*="st-key-settings_form"] [data-testid="stVerticalBlock"],
    .st-key-settings_form [data-testid="stVerticalBlock"] {
        gap: 0.35rem !important;
    }
    [class*="st-key-settings_form"] [data-testid="stElementContainer"],
    .st-key-settings_form [data-testid="stElementContainer"] {
        margin: 0 !important;
    }
    .settings-kicker {
        margin: 0 0 0.55rem 0 !important;
        color: #0d8a9a !important;
        font-size: 0.72rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.08em !important;
        text-transform: uppercase !important;
        line-height: 1.2 !important;
    }
    .settings-kicker-section {
        margin: 1.15rem 0 0.65rem 0 !important;
        padding-top: 0.95rem !important;
        border-top: 1px solid rgba(13, 138, 154, 0.22) !important;
    }
    .settings-subgroup-rule {
        margin: 0.65rem 0 0.35rem 0 !important;
        border: none !important;
        border-top: 1px solid rgba(13, 138, 154, 0.14) !important;
        height: 0 !important;
    }
    .settings-field-label {
        margin: 0.45rem 0 0 !important;
        color: #1a2b32 !important;
        font-size: 0.92rem !important;
        font-weight: 650 !important;
        letter-spacing: -0.01em !important;
        line-height: 1.25 !important;
    }
    .settings-hint {
        margin: 0 0 0.15rem 0 !important;
        color: #5a7380 !important;
        font-size: 0.8rem !important;
        font-style: italic !important;
        line-height: 1.3 !important;
    }
    /* Teal toggle (replace Streamlit's default red) */
    [class*="st-key-settings_page_auto_generate_images"],
    .st-key-settings_page_auto_generate_images {
        margin-top: 0.35rem !important;
    }
    [class*="st-key-settings_page_auto_generate_images"] [data-testid="stCheckbox"],
    .st-key-settings_page_auto_generate_images [data-testid="stCheckbox"],
    [class*="st-key-settings_page_auto_generate_images"] [data-testid="stWidgetLabel"],
    .st-key-settings_page_auto_generate_images [data-testid="stWidgetLabel"] {
        margin: 0 !important;
    }
    [class*="st-key-settings_page_auto_generate_images"] [data-baseweb="checkbox"] > div,
    .st-key-settings_page_auto_generate_images [data-baseweb="checkbox"] > div,
    [class*="st-key-settings_page_auto_generate_images"] label[data-baseweb="checkbox"] > div:first-child,
    .st-key-settings_page_auto_generate_images label[data-baseweb="checkbox"] > div:first-child {
        background-color: #b7cdd3 !important;
    }
    [class*="st-key-settings_page_auto_generate_images"] [data-baseweb="checkbox"][aria-checked="true"] > div,
    .st-key-settings_page_auto_generate_images [data-baseweb="checkbox"][aria-checked="true"] > div,
    [class*="st-key-settings_page_auto_generate_images"] [data-baseweb="checkbox"][data-checked="true"] > div,
    .st-key-settings_page_auto_generate_images [data-baseweb="checkbox"][data-checked="true"] > div,
    [class*="st-key-settings_page_auto_generate_images"] label[data-baseweb="checkbox"][data-checked="true"] > div,
    .st-key-settings_page_auto_generate_images label[data-baseweb="checkbox"][data-checked="true"] > div,
    [class*="st-key-settings_page_auto_generate_images"] label[data-baseweb="checkbox"] > div[data-checked="true"],
    .st-key-settings_page_auto_generate_images label[data-baseweb="checkbox"] > div[data-checked="true"],
    [class*="st-key-settings_page_auto_generate_images"] input:checked + div,
    .st-key-settings_page_auto_generate_images input:checked + div,
    [class*="st-key-settings_page_auto_generate_images"] [aria-checked="true"] > div:first-child,
    .st-key-settings_page_auto_generate_images [aria-checked="true"] > div:first-child {
        background-color: #0d8a9a !important;
        background-image: none !important;
    }
    [class*="st-key-settings_form"] [data-baseweb="select"] > div,
    .st-key-settings_form [data-baseweb="select"] > div {
        background: rgba(255, 255, 255, 0.82) !important;
        border: 1px solid #c5d6db !important;
        border-radius: 0.5rem !important;
        min-height: 2.35rem !important;
        box-shadow: none !important;
        cursor: pointer !important;
    }
    [class*="st-key-settings_form"] [data-baseweb="select"] > div:hover,
    .st-key-settings_form [data-baseweb="select"] > div:hover {
        border-color: #0d8a9a !important;
    }
    [class*="st-key-settings_form"] [data-testid="stSelectbox"],
    .st-key-settings_form [data-testid="stSelectbox"],
    [class*="st-key-settings_form"] [data-testid="stSelectbox"] *,
    .st-key-settings_form [data-testid="stSelectbox"] *,
    [class*="st-key-settings_form"] [data-baseweb="select"],
    .st-key-settings_form [data-baseweb="select"],
    [class*="st-key-settings_form"] [data-baseweb="select"] *,
    .st-key-settings_form [data-baseweb="select"] *,
    [class*="st-key-settings_form"] [data-baseweb="select"] input,
    .st-key-settings_form [data-baseweb="select"] input,
    [class*="st-key-settings_form"] [data-baseweb="select"] div[role="combobox"],
    .st-key-settings_form [data-baseweb="select"] div[role="combobox"] {
        cursor: pointer !important;
    }
    /* Open dropdown options (portaled outside the form) */
    div[data-baseweb="popover"] [role="listbox"] *,
    div[data-baseweb="popover"] [role="option"],
    ul[role="listbox"] li {
        cursor: pointer !important;
    }
    [class*="st-key-settings_form"] [data-testid="stImage"] img,
    .st-key-settings_form [data-testid="stImage"] img {
        border-radius: 0.55rem !important;
    }
    /* Avatar buttons: image is the button itself */
    [class*="st-key-avatar_wrap_"],
    [class*="st-key-avatar_pick_btn_"] {
        max-width: 62% !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }
    [class*="st-key-avatar_pick_btn_"] [data-testid="stBaseButton-secondary"],
    [class*="st-key-avatar_pick_btn_"] [data-testid="stBaseButton-primary"],
    [class*="st-key-avatar_pick_btn_"] button {
        background-color: transparent !important;
        background-size: cover !important;
        background-position: center center !important;
        background-repeat: no-repeat !important;
        width: 100% !important;
        height: 0 !important;
        min-height: 0 !important;
        padding-top: 100% !important;
        padding-bottom: 0 !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
        border: 3px solid transparent !important;
        border-radius: 0.65rem !important;
        box-shadow: none !important;
        color: transparent !important;
        font-size: 0 !important;
        line-height: 0 !important;
        cursor: pointer !important;
        overflow: hidden !important;
    }
    [class*="st-key-avatar_wrap_sel_"] [class*="st-key-avatar_pick_btn_"] button,
    [class*="st-key-avatar_wrap_sel_"] button {
        border-color: #0d9488 !important;
        box-shadow: 0 0 0 1px rgba(13, 148, 136, 0.35) !important;
    }
    [class*="st-key-avatar_pick_btn_"] button:hover {
        opacity: 0.92 !important;
        border-color: rgba(13, 148, 136, 0.55) !important;
    }
    [class*="st-key-avatar_pick_btn_"] button p,
    [class*="st-key-avatar_pick_btn_"] button span,
    [class*="st-key-avatar_pick_btn_"] button div {
        display: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

available_models = list_ollama_models()

if "settings_story_model" not in st.session_state:
    st.session_state.settings_story_model = resolve_preferred_model(available_models)
if "settings_image_model" not in st.session_state:
    st.session_state.settings_image_model = resolve_preferred_image_model()
if "settings_paragraph_range" not in st.session_state:
    st.session_state.settings_paragraph_range = resolve_preferred_paragraph_range()
if "settings_auto_generate_images" not in st.session_state:
    st.session_state.settings_auto_generate_images = (
        resolve_preferred_auto_generate_images()
    )
if "settings_background" not in st.session_state:
    st.session_state.settings_background = resolve_preferred_background()
if "settings_user_avatar" not in st.session_state:
    st.session_state.settings_user_avatar = resolve_preferred_user_avatar()

story_options = dedupe_models(available_models + [st.session_state.settings_story_model])
try:
    story_index = story_options.index(st.session_state.settings_story_model)
except ValueError:
    matched = match_available_model(st.session_state.settings_story_model, story_options)
    story_index = story_options.index(matched) if matched in story_options else 0
    if matched:
        st.session_state.settings_story_model = matched

image_keys = image_model_keys()
try:
    image_index = image_keys.index(st.session_state.settings_image_model)
except ValueError:
    image_index = 0
    st.session_state.settings_image_model = image_keys[0]

try:
    range_index = PARAGRAPH_RANGE_OPTIONS.index(
        st.session_state.settings_paragraph_range
    )
except ValueError:
    range_index = PARAGRAPH_RANGE_OPTIONS.index("3-5")
    st.session_state.settings_paragraph_range = "3-5"

bg_keys = background_keys()
try:
    bg_index = bg_keys.index(st.session_state.settings_background)
except ValueError:
    bg_index = bg_keys.index("forest") if "forest" in bg_keys else 0
    st.session_state.settings_background = bg_keys[bg_index]

avatar_keys = user_avatar_keys()
try:
    avatar_index = avatar_keys.index(st.session_state.settings_user_avatar)
except ValueError:
    avatar_index = 0
    st.session_state.settings_user_avatar = avatar_keys[0]

try:
    form = st.container(key="settings_form")
except TypeError:
    form = st.container()

with form:
    st.markdown(
        '<p class="settings-kicker">Story writing</p>',
        unsafe_allow_html=True,
    )

    lab, ctl = st.columns([0.34, 0.66], gap="small")
    with lab:
        st.markdown(
            '<p class="settings-field-label">Story model</p>',
            unsafe_allow_html=True,
        )
    with ctl:
        story_choice = st.selectbox(
            "Story model",
            story_options,
            index=story_index,
            format_func=display_model_name,
            label_visibility="collapsed",
            key="settings_page_story_model",
        )

    lab, ctl = st.columns([0.34, 0.66], gap="small")
    with lab:
        st.markdown(
            '<p class="settings-field-label">Paragraphs per prompt</p>',
            unsafe_allow_html=True,
        )
    with ctl:
        range_choice = st.selectbox(
            "Paragraphs per prompt",
            PARAGRAPH_RANGE_OPTIONS,
            index=range_index,
            format_func=paragraph_range_label,
            label_visibility="collapsed",
            key="settings_page_paragraph_range",
        )

    lab, ctl = st.columns([0.34, 0.66], gap="small")
    with lab:
        st.markdown(
            '<p class="settings-field-label">Image model</p>',
            unsafe_allow_html=True,
        )
    with ctl:
        image_choice = st.selectbox(
            "Image model",
            image_keys,
            index=image_index,
            format_func=image_model_label,
            label_visibility="collapsed",
            key="settings_page_image_model",
        )
        st.markdown(
            f'<p class="settings-hint">'
            f"{image_model_style(image_choice)}</p>",
            unsafe_allow_html=True,
        )

    lab, ctl = st.columns([0.34, 0.66], gap="small")
    with lab:
        st.markdown(
            '<p class="settings-field-label">Generate image per prompt</p>',
            unsafe_allow_html=True,
        )
    with ctl:
        if "settings_page_auto_generate_images" not in st.session_state:
            st.session_state.settings_page_auto_generate_images = (
                st.session_state.settings_auto_generate_images
            )
        auto_images_choice = st.toggle(
            "Generate image per prompt",
            label_visibility="collapsed",
            key="settings_page_auto_generate_images",
        )

    st.markdown(
        '<p class="settings-kicker settings-kicker-section">Appearance</p>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<p class="settings-field-label">User avatar</p>',
        unsafe_allow_html=True,
    )
    # Migrate removed youth selections to the new default set
    if st.session_state.settings_user_avatar not in avatar_keys:
        st.session_state.settings_user_avatar = resolve_preferred_user_avatar()
        if st.session_state.settings_user_avatar not in avatar_keys:
            st.session_state.settings_user_avatar = avatar_keys[0]
        set_preferred_user_avatar(st.session_state.settings_user_avatar)

    if "settings_page_user_avatar" not in st.session_state:
        st.session_state.settings_page_user_avatar = (
            st.session_state.settings_user_avatar
        )
    elif st.session_state.settings_page_user_avatar not in avatar_keys:
        st.session_state.settings_page_user_avatar = (
            st.session_state.settings_user_avatar
        )

    male_keys = [k for k in avatar_keys if k.startswith("male_")]
    female_keys = [k for k in avatar_keys if k.startswith("female_")]

    current_avatar = st.session_state.settings_page_user_avatar
    if current_avatar not in avatar_keys:
        current_avatar = avatar_keys[0]
        st.session_state.settings_page_user_avatar = current_avatar

    def _avatar_button_css(key: str, path: Path) -> str:
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"""
        [class*="st-key-avatar_pick_btn_{key}"] button {{
            background-image: url("data:image/png;base64,{data}") !important;
        }}
        """

    def _render_avatar_row(row_keys: list[str]) -> str | None:
        css_chunks: list[str] = []
        for key in row_keys:
            path = user_avatar_file(key)
            if path.exists():
                css_chunks.append(_avatar_button_css(key, path))
        if css_chunks:
            st.markdown(
                f"<style>{''.join(css_chunks)}</style>",
                unsafe_allow_html=True,
            )

        cols = st.columns(3, gap="medium")
        clicked = None
        for col, key in zip(cols, row_keys):
            with col:
                selected = current_avatar == key
                wrap_key = (
                    f"avatar_wrap_sel_{key}"
                    if selected
                    else f"avatar_wrap_idle_{key}"
                )
                try:
                    wrap = st.container(key=wrap_key)
                except TypeError:
                    wrap = st.container()
                with wrap:
                    if st.button(
                        user_avatar_label(key),
                        key=f"avatar_pick_btn_{key}",
                        use_container_width=True,
                        help=user_avatar_label(key),
                    ):
                        clicked = key
        return clicked

    picked_male = _render_avatar_row(male_keys)
    picked_female = _render_avatar_row(female_keys)
    picked = picked_male or picked_female
    if picked and picked != current_avatar:
        st.session_state.settings_page_user_avatar = picked
        st.rerun()

    avatar_choice = st.session_state.settings_page_user_avatar

    lab, ctl = st.columns([0.34, 0.66], gap="small")
    with lab:
        st.markdown(
            '<p class="settings-field-label">Background image</p>',
            unsafe_allow_html=True,
        )
    with ctl:
        bg_choice = st.selectbox(
            "Background image",
            bg_keys,
            index=bg_index,
            format_func=background_label,
            label_visibility="collapsed",
            key="settings_page_background",
        )

if story_choice != st.session_state.settings_story_model:
    st.session_state.settings_story_model = story_choice
    set_preferred_model(story_choice)
    st.session_state.model = story_choice

if image_choice != st.session_state.settings_image_model:
    st.session_state.settings_image_model = image_choice
    set_preferred_image_model(image_choice)
    st.session_state.image_model = resolve_image_model(image_choice)

if range_choice != st.session_state.settings_paragraph_range:
    st.session_state.settings_paragraph_range = range_choice
    set_preferred_paragraph_range(range_choice)

if auto_images_choice != st.session_state.settings_auto_generate_images:
    st.session_state.settings_auto_generate_images = auto_images_choice
    set_preferred_auto_generate_images(auto_images_choice)

if avatar_choice != st.session_state.settings_user_avatar:
    st.session_state.settings_user_avatar = avatar_choice
    set_preferred_user_avatar(avatar_choice)

if bg_choice != st.session_state.settings_background:
    st.session_state.settings_background = bg_choice
    set_preferred_background(bg_choice)
    st.rerun()
