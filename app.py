import html
import importlib
import json
import re
import uuid
from pathlib import Path

import ollama
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image as PILImage

import image_gen as _image_gen

# Streamlit can keep a stale image_gen in memory after edits; refresh if needed
if not hasattr(_image_gen, "edit_image") or not hasattr(_image_gen, "IMAGE_MODELS"):
    _image_gen = importlib.reload(_image_gen)

edit_image = _image_gen.edit_image
generate_image = _image_gen.generate_image
clear_image_pipelines = _image_gen.clear_image_pipelines
image_model_keys = _image_gen.image_model_keys
image_model_label = _image_gen.image_model_label
resolve_image_model = _image_gen.resolve_image_model
DEFAULT_IMAGE_MODEL = _image_gen.DEFAULT_IMAGE_MODEL

DEFAULT_MODEL = "dolphin-llama3"
# Only these chat models are offered in the picker
PRACTICAL_MODELS = [
    "dolphin-llama3",
    "dolphin-mistral",
    "wizard-vicuna-uncensored",
]
HISTORY_FILE = Path(__file__).parent / "chat_history.json"
SETTINGS_FILE = Path(__file__).parent / "settings.json"
IMAGE_DIR = Path(__file__).parent / "generated"


def display_model_name(name: str) -> str:
    return name.removesuffix(":latest")


def _dedupe_models(names: list[str]) -> list[str]:
    """Keep unique models by display name; prefer tagged Ollama names."""
    by_key: dict[str, str] = {}
    for name in names:
        if not name:
            continue
        key = display_model_name(name).lower()
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = name
        elif name.endswith(":latest") or ":" in name:
            by_key[key] = name
    return list(by_key.values())


def list_ollama_models() -> list[str]:
    """
    Return only the allowed chat models for the picker.

    Prefers live Ollama names (with tags) when installed; falls back to the
    configured PRACTICAL_MODELS list.
    """
    settings = load_settings()
    cached = [str(m) for m in (settings.get("models") or []) if m]
    allowed = {display_model_name(m).lower() for m in PRACTICAL_MODELS}

    live: list[str] = []
    try:
        live = [
            m.model
            for m in ollama.list().models
            if getattr(m, "model", None)
        ]
    except Exception:
        live = []

    source = live or cached or []
    by_key: dict[str, str] = {}
    for name in source:
        key = display_model_name(name).lower()
        if key in allowed:
            by_key[key] = name

    # Keep picker order from PRACTICAL_MODELS; use live tag when available
    ordered = [
        by_key.get(display_model_name(name).lower(), name)
        for name in PRACTICAL_MODELS
    ]

    if live:
        settings["models"] = ordered
        save_settings(settings)

    return ordered or [DEFAULT_MODEL]


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_settings(settings: dict) -> None:
    SETTINGS_FILE.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def match_available_model(preferred: str, available: list[str]) -> str | None:
    """Find preferred model in available list, allowing :latest tag differences."""
    if not available:
        return None
    if preferred in available:
        return preferred
    preferred_display = display_model_name(preferred)
    for name in available:
        if display_model_name(name) == preferred_display:
            return name
    if preferred == DEFAULT_MODEL or preferred.startswith(DEFAULT_MODEL + ":"):
        for name in available:
            if name == DEFAULT_MODEL or name.startswith(DEFAULT_MODEL + ":"):
                return name
    return None


def resolve_preferred_model(available: list[str]) -> str:
    """Load saved model preference, else fall back to default / first available."""
    settings = load_settings()
    preferred = settings.get("model") or DEFAULT_MODEL
    matched = match_available_model(str(preferred), available)
    return matched or available[0]


def set_preferred_model(model: str) -> None:
    """Persist chat model choice locally (survives refresh / restart)."""
    settings = load_settings()
    settings["model"] = model
    save_settings(settings)
    # Mirror into browser localStorage
    components.html(
        f"""
        <script>
        try {{
          localStorage.setItem("chuckAI_model", {json.dumps(model)});
        }} catch (e) {{}}
        </script>
        """,
        height=0,
        width=0,
    )


def set_preferred_image_model(model_key: str) -> None:
    """Persist image model choice and free VRAM from the previous pipeline."""
    key = resolve_image_model(model_key)
    settings = load_settings()
    settings["image_model"] = key
    save_settings(settings)
    clear_image_pipelines()
    components.html(
        f"""
        <script>
        try {{
          localStorage.setItem("chuckAI_image_model", {json.dumps(key)});
        }} catch (e) {{}}
        </script>
        """,
        height=0,
        width=0,
    )


def _new_chat(title: str = "New Chat", messages: list[dict] | None = None) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "title": title,
        "messages": messages or [],
    }


def load_store() -> dict:
    """Load multi-chat store. Migrates old flat message list if needed."""
    if not HISTORY_FILE.exists():
        return {"chats": [], "active_id": None}

    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"chats": [], "active_id": None}

    # Old format: flat list of {role, content}
    if isinstance(data, list):
        if data and "role" in data[0]:
            title = next(
                (m["content"] for m in data if m.get("role") == "user"),
                "New Chat",
            )
            chat = _new_chat(title=_title_from(title), messages=data)
            return {"chats": [chat], "active_id": chat["id"]}
        if data and "id" in data[0] and "messages" in data[0]:
            return {
                "chats": data,
                "active_id": data[0]["id"],
            }
        return {"chats": [], "active_id": None}

    if isinstance(data, dict) and "chats" in data:
        return {
            "chats": data.get("chats") or [],
            "active_id": data.get("active_id"),
        }

    return {"chats": [], "active_id": None}


def save_store(chats: list[dict], active_id: str | None) -> None:
    HISTORY_FILE.write_text(
        json.dumps(
            {"chats": chats, "active_id": active_id},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _title_from(text: str, max_len: int = 40) -> str:
    text = " ".join(text.strip().split())
    if len(text) <= max_len:
        return text or "New Chat"
    return text[: max_len - 1] + "…"


def get_active_chat() -> dict | None:
    active_id = st.session_state.active_id
    for chat in st.session_state.chats:
        if chat["id"] == active_id:
            return chat
    return None


def delete_chat(chat_id: str) -> None:
    st.session_state.chats = [
        c for c in st.session_state.chats if c["id"] != chat_id
    ]
    if not st.session_state.chats:
        new_chat = _new_chat()
        st.session_state.chats = [new_chat]
        st.session_state.active_id = new_chat["id"]
    elif st.session_state.active_id == chat_id:
        st.session_state.active_id = st.session_state.chats[0]["id"]
    persist()


def persist() -> None:
    save_store(st.session_state.chats, st.session_state.active_id)


def ollama_messages(messages: list[dict]) -> list[dict]:
    """Strip non-text fields before sending to Ollama."""
    return [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m.get("role") in ("user", "assistant", "system") and m.get("content")
    ]


def parse_image_prompt(text: str) -> str | None:
    """
    Return the image subject if this looks like a *new* image request, else None.

    Supports `/image …` and any prompt that begins with "show"
    (including "show me…", "show a picture…", etc.).
    """
    stripped = text.strip()
    lower = stripped.lower()

    # Longer / more specific patterns first; bare "show …" last
    prefixes = [
        r"^/image\s*",
        r"^show\s+me\s+(?:a\s+|an\s+)?(?:picture|image|photo)\s*(?:of\s+)?",
        r"^show\s+(?:a\s+|an\s+)?(?:picture|image|photo)\s*(?:of\s+)?",
        r"^show\s+me\s+",
        r"^show\s+",
    ]
    for pattern in prefixes:
        match = re.match(pattern, lower)
        if match:
            return stripped[match.end() :].strip()
    return None


def parse_image_edit_prompt(text: str) -> str | None:
    """Return edit instruction if this looks like an image-edit request."""
    stripped = text.strip()
    lower = stripped.lower()
    prefixes = [
        r"^/edit\s*",
        r"^change\s+",
        r"^make\s+it\s+",
        r"^make\s+the\s+",
        r"^edit\s+",
        r"^modify\s+",
        r"^update\s+(?:the\s+)?image\s*(?:to\s+|with\s+)?",
        r"^regenerate\s+(?:it\s+)?(?:with\s+|as\s+)?",
        r"^redo\s+(?:it\s+)?(?:with\s+|as\s+)?",
        r"^add\s+",
        r"^remove\s+",
        r"^replace\s+",
        r"^now\s+make\s+",
        r"^can\s+you\s+(?:change|edit|modify|add|remove)\s+",
    ]
    for pattern in prefixes:
        match = re.match(pattern, lower)
        if match:
            rest = stripped[match.end() :].strip()
            # Keep full natural phrasing for img2img; fall back to whole text
            return rest or stripped
    return None


def is_likely_chat(text: str) -> bool:
    """Heuristic: treat questions / chatty asks as LLM chat, not image edits."""
    lower = text.strip().lower()
    if "?" in lower:
        return True
    return bool(
        re.match(
            r"^(what|why|how|who|when|where|explain|summarize|write|"
            r"tell me (?!about the image)|do you|can you (?:explain|tell|help|write|say)|"
            r"please (?:explain|tell|write))\b",
            lower,
        )
    )


def last_image_message(messages: list[dict]) -> dict | None:
    for message in reversed(messages):
        if message.get("role") == "assistant" and message.get("image"):
            return message
    return None


def resolve_image_path(image_rel: str) -> Path | None:
    path = Path(image_rel)
    if not path.is_absolute():
        path = Path(__file__).parent / path
    return path if path.exists() else None


def save_generated_image(image, prompt: str) -> str:
    """Save PIL image under generated/ and return a relative path string."""
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.png"
    path = IMAGE_DIR / filename
    image.save(path)
    return str(Path("generated") / filename)


def render_message(message: dict) -> None:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        image_rel = message.get("image")
        if image_rel:
            image_path = Path(image_rel)
            if not image_path.is_absolute():
                image_path = Path(__file__).parent / image_path
            if image_path.exists():
                st.image(str(image_path), use_container_width=True)


st.title("chuckAI")

st.markdown(
    """
    <style>
    /* Remove top whitespace / centering in the sidebar */
    section[data-testid="stSidebar"] {
        padding-top: 0 !important;
        position: relative !important;
    }
    section[data-testid="stSidebar"] > div:first-child {
        display: flex !important;
        flex-direction: column;
        height: 100%;
        position: relative !important;
        padding-top: 0 !important;
        gap: 0 !important;
    }
    [data-testid="stSidebarHeader"] {
        padding-top: 0.4rem !important;
        padding-bottom: 0 !important;
        margin: 0 !important;
        min-height: 0 !important;
    }
    [data-testid="stSidebarContent"] {
        padding-top: 0 !important;
        margin-top: 0 !important;
        padding-bottom: 0.75rem !important;
        height: 100%;
        position: relative !important;
    }
    [data-testid="stSidebarContent"] > div {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    /* Spacer + gray rule above Model / Image */
    section[data-testid="stSidebar"] .nav-section-gap {
        height: 0.55rem;
    }
    section[data-testid="stSidebar"] .nav-divider {
        border: none !important;
        border-top: 1px solid rgba(49, 51, 63, 0.25) !important;
        margin: 0 !important;
        width: 100%;
    }
    /* Model / Image pickers: hug content, both flush left */
    [data-testid="stSidebar"] [data-testid="stPopover"] {
        display: block !important;
        width: 100% !important;
    }
    [data-testid="stSidebar"] [data-testid="stPopover"] > div {
        display: flex !important;
        justify-content: flex-start !important;
        width: 100% !important;
    }
    [data-testid="stSidebar"] [data-testid="stPopover"] > button,
    [data-testid="stSidebar"] [data-testid="stPopover"] button {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: #1c61a5 !important;
        font-size: 0.8rem !important;
        font-weight: 400 !important;
        padding: 0.15rem 0 !important;
        min-height: 0 !important;
        height: auto !important;
        width: auto !important;
        max-width: 100% !important;
        margin: 0 !important;
        margin-left: 0 !important;
        justify-content: flex-start !important;
        text-align: left !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    [data-testid="stSidebar"] [data-testid="stPopover"] button > div,
    [data-testid="stSidebar"] [data-testid="stPopover"] button [data-testid="stMarkdownContainer"] {
        width: auto !important;
        flex: 0 1 auto !important;
        justify-content: flex-start !important;
        text-align: left !important;
        margin: 0 !important;
    }
    [data-testid="stSidebar"] [data-testid="stPopover"] button p {
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        text-align: left !important;
        width: auto !important;
        margin: 0 !important;
    }
    [data-testid="stSidebar"] [data-testid="stPopover"] button:hover {
        text-decoration: underline !important;
        color: #0b3d6e !important;
        background: transparent !important;
    }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
        display: none !important;
    }

    /* All sidebar controls look like compact text links */
    section[data-testid="stSidebar"] .stButton {
        width: 100% !important;
        text-align: left !important;
    }
    section[data-testid="stSidebar"] button {
        background: transparent !important;
        background-color: transparent !important;
        border: none !important;
        border-width: 0 !important;
        box-shadow: none !important;
        outline: none !important;
        padding: 0.15rem 0 !important;
        min-height: 0 !important;
        height: auto !important;
        font-size: 0.85rem !important;
        font-weight: 400 !important;
        line-height: 1.35 !important;
        color: #1c61a5 !important;
        display: flex !important;
        justify-content: flex-start !important;
        align-items: center !important;
        text-align: left !important;
        width: 100% !important;
        max-width: 100% !important;
        overflow: hidden !important;
    }
    /* Force left alignment on Streamlit's inner button wrappers */
    section[data-testid="stSidebar"] button > div,
    section[data-testid="stSidebar"] button [data-testid="stMarkdownContainer"] {
        width: 100% !important;
        max-width: 100% !important;
        display: flex !important;
        justify-content: flex-start !important;
        align-items: center !important;
        text-align: left !important;
    }
    section[data-testid="stSidebar"] button:hover {
        color: #0b3d6e !important;
        background: transparent !important;
        border: none !important;
        text-decoration: underline !important;
    }
    section[data-testid="stSidebar"] button p {
        margin: 0 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        text-align: left !important;
        width: 100% !important;
    }
    /* Active chat */
    section[data-testid="stSidebar"] button[kind="primary"],
    section[data-testid="stSidebar"] button[data-testid="baseButton-primary"] {
        color: #0b3d6e !important;
        font-weight: 600 !important;
        text-decoration: none !important;
    }
    /* Right-aligned nav action links */
    section[data-testid="stSidebar"] .nav-right-link {
        display: block !important;
        text-align: right !important;
        margin: 0.15rem 0 !important;
        padding: 0 !important;
    }
    section[data-testid="stSidebar"] .nav-right-link a {
        color: #1c61a5 !important;
        text-decoration: none !important;
        font-size: 0.85rem !important;
        line-height: 1.35 !important;
    }
    section[data-testid="stSidebar"] .nav-right-link a:hover {
        color: #0b3d6e !important;
        text-decoration: underline !important;
    }
    /* Chat row: title left, trash far right */
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
        gap: 0.15rem !important;
        align-items: center !important;
    }
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] [data-testid="column"]:last-child .stButton {
        width: auto !important;
        display: flex !important;
        justify-content: flex-end !important;
    }
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] [data-testid="column"]:last-child button {
        justify-content: center !important;
        width: auto !important;
        min-width: 1.25rem !important;
        padding: 0.15rem 0.1rem !important;
        font-size: 0.75rem !important;
        opacity: 0.7;
    }
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] [data-testid="column"]:last-child button:hover {
        opacity: 1;
        text-decoration: none !important;
    }
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] [data-testid="column"]:last-child button > div,
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] [data-testid="column"]:last-child button [data-testid="stMarkdownContainer"] {
        width: auto !important;
        justify-content: center !important;
    }
    section[data-testid="stSidebar"] hr {
        display: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "chats" not in st.session_state:
    store = load_store()
    st.session_state.chats = store["chats"]
    st.session_state.active_id = store["active_id"]
    if not st.session_state.chats:
        chat = _new_chat()
        st.session_state.chats = [chat]
        st.session_state.active_id = chat["id"]
        persist()
    elif st.session_state.active_id not in {c["id"] for c in st.session_state.chats}:
        st.session_state.active_id = st.session_state.chats[0]["id"]

# If a chat still says "New Chat" but has a first prompt, use that prompt as the title
for chat in st.session_state.chats:
    if chat.get("title") in ("New Chat", "New chat", "", None) and chat.get("messages"):
        first_user = next(
            (m["content"] for m in chat["messages"] if m.get("role") == "user"),
            None,
        )
        if first_user:
            chat["title"] = _title_from(first_user)

if "chats_visible" not in st.session_state:
    st.session_state.chats_visible = True

available_models = list_ollama_models()
if "model" not in st.session_state:
    st.session_state.model = resolve_preferred_model(available_models)
    # Seed settings file if missing so the choice sticks
    if not load_settings().get("model"):
        set_preferred_model(st.session_state.model)
elif st.session_state.model not in available_models and available_models:
    match = match_available_model(st.session_state.model, available_models)
    st.session_state.model = match or available_models[0]
    set_preferred_model(st.session_state.model)

if "image_model" not in st.session_state:
    st.session_state.image_model = resolve_image_model(
        load_settings().get("image_model") or DEFAULT_IMAGE_MODEL
    )
    if not load_settings().get("image_model"):
        set_preferred_image_model(st.session_state.image_model)
else:
    st.session_state.image_model = resolve_image_model(st.session_state.image_model)

# Handle right-aligned nav links (?nav=new / ?nav=clear)
nav_action = st.query_params.get("nav")
if nav_action == "new":
    chat = _new_chat()
    st.session_state.chats.insert(0, chat)
    st.session_state.active_id = chat["id"]
    persist()
    st.query_params.clear()
    st.rerun()
elif nav_action == "clear":
    new_chat = _new_chat()
    st.session_state.chats = [new_chat]
    st.session_state.active_id = new_chat["id"]
    persist()
    st.query_params.clear()
    st.rerun()

history_path = str(HISTORY_FILE.resolve())

with st.sidebar:
    st.markdown(
        '<p class="nav-right-link"><a href="?nav=new" target="_self">Start New Chat</a></p>',
        unsafe_allow_html=True,
    )

    chats_label = "Chats >"
    if st.button(
        chats_label,
        key="toggle_chats",
        use_container_width=True,
        type="tertiary",
    ):
        st.session_state.chats_visible = not st.session_state.chats_visible
        st.rerun()

    if st.session_state.chats_visible:
        for chat in list(st.session_state.chats):
            is_active = chat["id"] == st.session_state.active_id
            title = chat["title"] or "New Chat"
            label = f"• {title}"
            col_open, col_del = st.columns([8, 1], gap="small")
            with col_open:
                if st.button(
                    label,
                    key=f"open_{chat['id']}",
                    use_container_width=True,
                    type="primary" if is_active else "tertiary",
                ):
                    st.session_state.active_id = chat["id"]
                    persist()
                    st.rerun()
            with col_del:
                if st.button(
                    ":material/delete:",
                    key=f"del_{chat['id']}",
                    use_container_width=True,
                    type="tertiary",
                    help="Delete this chat",
                ):
                    delete_chat(chat["id"])
                    st.rerun()

    st.markdown(
        f'<p class="nav-right-link" title="{html.escape(history_path)}">'
        f'<a href="?nav=clear" target="_self">Clear Chat History</a></p>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="nav-section-gap"></div>'
        '<div class="nav-divider"></div>'
        '<div class="nav-section-gap"></div>',
        unsafe_allow_html=True,
    )

    model_label = display_model_name(st.session_state.model)
    with st.popover(model_label, use_container_width=False):
        st.caption("Available models")
        # Ensure current choice is in the list even if tags differ
        options = _dedupe_models(available_models + [st.session_state.model])
        try:
            current_index = options.index(st.session_state.model)
        except ValueError:
            matched = match_available_model(st.session_state.model, options)
            current_index = options.index(matched) if matched in options else 0
            if matched:
                st.session_state.model = matched

        choice = st.radio(
            "model_choice",
            options,
            index=current_index,
            format_func=display_model_name,
            label_visibility="collapsed",
        )
        if choice != st.session_state.model:
            st.session_state.model = choice
            set_preferred_model(choice)
            st.rerun()

    image_keys = image_model_keys()
    image_label = image_model_label(st.session_state.image_model)
    with st.popover(image_label, use_container_width=False):
        st.caption("Image models")
        try:
            image_index = image_keys.index(st.session_state.image_model)
        except ValueError:
            image_index = 0
            st.session_state.image_model = image_keys[0]

        image_choice = st.radio(
            "image_model_choice",
            image_keys,
            index=image_index,
            format_func=image_model_label,
            label_visibility="collapsed",
        )
        if image_choice != st.session_state.image_model:
            st.session_state.image_model = image_choice
            set_preferred_image_model(image_choice)
            st.rerun()

active = get_active_chat()
messages = active["messages"] if active else []

for message in messages:
    render_message(message)

prompt = st.chat_input(
    'Chat, "show me a dolphin", or after an image: "make it jumping"'
)

if prompt and active:
    prior_messages = list(active["messages"])
    active["messages"].append({"role": "user", "content": prompt})

    # First prompt becomes the sidebar title
    user_msgs = [m for m in active["messages"] if m["role"] == "user"]
    if len(user_msgs) == 1:
        new_title = _title_from(prompt)
        active["title"] = new_title
        for chat in st.session_state.chats:
            if chat["id"] == active["id"]:
                chat["title"] = new_title
                break

    with st.chat_message("user"):
        st.markdown(prompt)

    image_prompt = parse_image_prompt(prompt)
    edit_prompt = parse_image_edit_prompt(prompt)
    prev_image_msg = last_image_message(prior_messages)
    prev_image_path = (
        resolve_image_path(prev_image_msg["image"]) if prev_image_msg else None
    )

    # After an image: treat follow-ups as edits unless it's a new image or chat
    followup_edit = (
        prev_image_path is not None
        and image_prompt is None
        and not is_likely_chat(prompt)
    )
    if edit_prompt is None and followup_edit:
        edit_prompt = prompt.strip()

    if image_prompt is not None:
        if not image_prompt:
            reply = (
                "Say what to draw, e.g. `show me a dolphin` "
                "or `/image a dolphin jumping`"
            )
            with st.chat_message("assistant"):
                st.markdown(reply)
            active["messages"].append({"role": "assistant", "content": reply})
        else:
            try:
                with st.chat_message("assistant"):
                    with st.spinner("Generating image…"):
                        image = generate_image(
                            image_prompt,
                            model_key=st.session_state.image_model,
                        )
                    image_rel = save_generated_image(image, image_prompt)
                    caption = f"Generated for: *{image_prompt}*"
                    st.markdown(caption)
                    st.image(image, use_container_width=True)
                active["messages"].append(
                    {
                        "role": "assistant",
                        "content": caption,
                        "image": image_rel,
                        "image_prompt": image_prompt,
                    }
                )
            except Exception as e:
                reply = f"Image generation failed: {e}"
                with st.chat_message("assistant"):
                    st.markdown(reply)
                active["messages"].append({"role": "assistant", "content": reply})
        persist()
        st.rerun()

    if edit_prompt is not None and prev_image_path is not None:
        try:
            base_prompt = (prev_image_msg or {}).get("image_prompt") or ""
            if base_prompt:
                full_prompt = f"{base_prompt}, {edit_prompt}"
            else:
                full_prompt = edit_prompt

            with st.chat_message("assistant"):
                with st.spinner("Updating image…"):
                    init = PILImage.open(prev_image_path)
                    image = edit_image(
                        full_prompt,
                        init,
                        model_key=st.session_state.image_model,
                    )
                image_rel = save_generated_image(image, full_prompt)
                caption = f"Updated image: *{edit_prompt}*"
                st.markdown(caption)
                st.image(image, use_container_width=True)
            active["messages"].append(
                {
                    "role": "assistant",
                    "content": caption,
                    "image": image_rel,
                    "image_prompt": full_prompt,
                }
            )
        except Exception as e:
            reply = f"Image edit failed: {e}"
            with st.chat_message("assistant"):
                st.markdown(reply)
            active["messages"].append({"role": "assistant", "content": reply})
        persist()
        st.rerun()

    if edit_prompt is not None and prev_image_path is None:
        reply = (
            "No previous image to edit. Create one first, e.g. "
            "`show me a dolphin`, then try `make it jumping`."
        )
        with st.chat_message("assistant"):
            st.markdown(reply)
        active["messages"].append({"role": "assistant", "content": reply})
        persist()
        st.rerun()

    def stream_reply():
        try:
            stream = ollama.chat(
                model=st.session_state.model,
                messages=ollama_messages(active["messages"]),
                stream=True,
            )
            for chunk in stream:
                token = chunk.message.content
                if token:
                    yield token
        except Exception as e:
            yield (
                f"Could not reach Ollama: {e}\n\n"
                "Make sure Ollama is running, then try again."
            )

    with st.chat_message("assistant"):
        reply = st.write_stream(stream_reply())

    active["messages"].append({"role": "assistant", "content": reply})
    persist()
    st.rerun()
