"""Shared model preference load/save for Stories + Settings pages."""

from __future__ import annotations

import json
from pathlib import Path

import ollama
import streamlit.components.v1 as components

import image_gen as _image_gen

DEFAULT_MODEL = "dolphin-mistral"
PRACTICAL_MODELS = [
    "dolphin-mistral",
    "dolphin-llama3",
    "wizard-vicuna-uncensored",
]
DEFAULT_PARAGRAPH_RANGE = "3-5"
PARAGRAPH_RANGE_OPTIONS = ["2-4", "3-5", "4-6", "5-7", "8-10"]
DEFAULT_BACKGROUND = "forest"
BACKGROUND_OPTIONS: dict[str, dict[str, str]] = {
    "forest": {
        "label": "Forest",
        "file": "chat_bg_forest.png",
    },
    "sci_fi": {
        "label": "Sci-Fi",
        "file": "chat_bg_sci_fi.png",
    },
    "urban": {
        "label": "Urban",
        "file": "chat_bg_urban.png",
    },
    "steampunk": {
        "label": "Victorian Steampunk",
        "file": "chat_bg_steampunk.png",
    },
}
DEFAULT_USER_AVATAR = "male_20"
USER_AVATAR_OPTIONS: dict[str, dict[str, str]] = {
    "male_20": {
        "label": "Young man",
        "file": "avatar_user_male_20.png",
    },
    "male_35": {
        "label": "Man",
        "file": "avatar_user_male_35.png",
    },
    "male_55": {
        "label": "Older man",
        "file": "avatar_user_male_55.png",
    },
    "female_20": {
        "label": "Young woman",
        "file": "avatar_user_female_20.png",
    },
    "female_35": {
        "label": "Woman",
        "file": "avatar_user_female_35.png",
    },
    "female_55": {
        "label": "Older woman",
        "file": "avatar_user_female_55.png",
    },
}
SETTINGS_FILE = Path(__file__).parent / "settings.json"

clear_image_pipelines = _image_gen.clear_image_pipelines
resolve_image_model = _image_gen.resolve_image_model
image_model_keys = _image_gen.image_model_keys
image_model_label = _image_gen.image_model_label
image_model_style = _image_gen.image_model_style
DEFAULT_IMAGE_MODEL = _image_gen.DEFAULT_IMAGE_MODEL


def display_model_name(name: str) -> str:
    return name.removesuffix(":latest")


def dedupe_models(names: list[str]) -> list[str]:
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


def list_ollama_models() -> list[str]:
    """Return only the allowed chat models for the picker."""
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

    ordered = [
        by_key.get(display_model_name(name).lower(), name)
        for name in PRACTICAL_MODELS
    ]

    if live:
        settings["models"] = ordered
        save_settings(settings)

    return ordered or [DEFAULT_MODEL]


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
    components.html(
        f"""
        <script>
        try {{
          localStorage.setItem("yourStoriesAI_model", {json.dumps(model)});
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
          localStorage.setItem("yourStoriesAI_image_model", {json.dumps(key)});
        }} catch (e) {{}}
        </script>
        """,
        height=0,
        width=0,
    )


def resolve_preferred_image_model() -> str:
    settings = load_settings()
    return resolve_image_model(settings.get("image_model") or DEFAULT_IMAGE_MODEL)


def paragraph_range_label(key: str) -> str:
    """Display range with an en-dash (e.g. 3–5)."""
    raw = str(key or DEFAULT_PARAGRAPH_RANGE).strip().replace("–", "-")
    return raw.replace("-", "–")


def resolve_preferred_paragraph_range() -> str:
    """Load saved paragraph-range preference (min-max), default 3-5."""
    settings = load_settings()
    raw = str(settings.get("paragraph_range") or DEFAULT_PARAGRAPH_RANGE)
    key = raw.strip().replace("–", "-")
    if key in PARAGRAPH_RANGE_OPTIONS:
        return key
    return DEFAULT_PARAGRAPH_RANGE


def set_preferred_paragraph_range(range_key: str) -> None:
    """Persist paragraphs-per-prompt range (e.g. '3-5')."""
    key = str(range_key or DEFAULT_PARAGRAPH_RANGE).strip().replace("–", "-")
    if key not in PARAGRAPH_RANGE_OPTIONS:
        key = DEFAULT_PARAGRAPH_RANGE
    settings = load_settings()
    settings["paragraph_range"] = key
    save_settings(settings)


def background_keys() -> list[str]:
    return list(BACKGROUND_OPTIONS.keys())


def background_label(key: str) -> str:
    cfg = BACKGROUND_OPTIONS.get(key) or BACKGROUND_OPTIONS[DEFAULT_BACKGROUND]
    return str(cfg["label"])


def background_file(key: str) -> Path:
    cfg = BACKGROUND_OPTIONS.get(key) or BACKGROUND_OPTIONS[DEFAULT_BACKGROUND]
    return Path(__file__).parent / "assets" / str(cfg["file"])


def resolve_preferred_background() -> str:
    """Load saved chat background preference; default Forest."""
    settings = load_settings()
    key = str(settings.get("background") or DEFAULT_BACKGROUND).strip()
    if key in BACKGROUND_OPTIONS:
        path = background_file(key)
        if path.exists():
            return key
    return DEFAULT_BACKGROUND


def set_preferred_background(key: str) -> None:
    """Persist chat background choice."""
    choice = str(key or DEFAULT_BACKGROUND).strip()
    if choice not in BACKGROUND_OPTIONS:
        choice = DEFAULT_BACKGROUND
    settings = load_settings()
    settings["background"] = choice
    save_settings(settings)


def user_avatar_keys() -> list[str]:
    return list(USER_AVATAR_OPTIONS.keys())


def user_avatar_label(key: str) -> str:
    cfg = USER_AVATAR_OPTIONS.get(key) or USER_AVATAR_OPTIONS[DEFAULT_USER_AVATAR]
    return str(cfg["label"])


def user_avatar_file(key: str) -> Path:
    cfg = USER_AVATAR_OPTIONS.get(key) or USER_AVATAR_OPTIONS[DEFAULT_USER_AVATAR]
    return Path(__file__).parent / "assets" / str(cfg["file"])


def resolve_preferred_user_avatar() -> str:
    """Load saved user avatar preference; default Young man."""
    settings = load_settings()
    key = str(settings.get("user_avatar") or DEFAULT_USER_AVATAR).strip()
    # Migrate removed youth options to the new adult defaults
    if key in {"male_youth", "boy"}:
        key = "male_20"
    elif key in {"female_youth", "girl"}:
        key = "female_20"
    if key in USER_AVATAR_OPTIONS and user_avatar_file(key).exists():
        return key
    return DEFAULT_USER_AVATAR


def set_preferred_user_avatar(key: str) -> None:
    """Persist user chat avatar choice."""
    choice = str(key or DEFAULT_USER_AVATAR).strip()
    if choice not in USER_AVATAR_OPTIONS:
        choice = DEFAULT_USER_AVATAR
    settings = load_settings()
    settings["user_avatar"] = choice
    save_settings(settings)
