"""Shared model preference load/save for Stories + Settings pages.

User prefs are stored per browser (cookie + localStorage) and mirrored into
``st.session_state`` for the active Streamlit session. Each machine and
browser keeps its own settings.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote

import ollama
import streamlit as st

import image_gen as _image_gen

DEFAULT_MODEL = "dolphin-mistral"
PRACTICAL_MODELS = [
    "dolphin-mistral",
    "dolphin-llama3",
    "wizard-vicuna-uncensored",
]
DEFAULT_PARAGRAPH_RANGE = "3-5"
PARAGRAPH_RANGE_OPTIONS = ["2-4", "3-5", "4-6", "5-7", "8-10"]
DEFAULT_AUTO_GENERATE_IMAGES = True
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

# Legacy shared file — read once to seed browser prefs on upgrade; never written.
_LEGACY_SETTINGS_FILE = Path(__file__).parent / "settings.json"
_LOCAL_STORAGE_KEY = "yourStoriesAI_settings"
_COOKIE_NAME = "yourStoriesAI_settings"
_SESSION_PREFS_KEY = "_user_prefs"
_HYDRATED_KEY = "_prefs_hydrated"
_USER_PREF_KEYS = (
    "model",
    "image_model",
    "paragraph_range",
    "auto_generate_images",
    "background",
    "user_avatar",
)

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


def _default_prefs() -> dict:
    return {
        "model": DEFAULT_MODEL,
        "image_model": DEFAULT_IMAGE_MODEL,
        "paragraph_range": DEFAULT_PARAGRAPH_RANGE,
        "auto_generate_images": DEFAULT_AUTO_GENERATE_IMAGES,
        "background": DEFAULT_BACKGROUND,
        "user_avatar": DEFAULT_USER_AVATAR,
    }


def _legacy_file_prefs() -> dict:
    """Optional one-time migration source from the old shared settings.json."""
    if not _LEGACY_SETTINGS_FILE.exists():
        return {}
    try:
        data = json.loads(_LEGACY_SETTINGS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: data[k] for k in _USER_PREF_KEYS if k in data}


def _normalize_prefs(raw: dict | None) -> dict:
    prefs = _default_prefs()
    if not isinstance(raw, dict):
        return prefs

    model = raw.get("model")
    if model:
        prefs["model"] = str(model)

    if raw.get("image_model"):
        prefs["image_model"] = resolve_image_model(str(raw["image_model"]))

    range_key = str(raw.get("paragraph_range") or DEFAULT_PARAGRAPH_RANGE)
    range_key = range_key.strip().replace("–", "-")
    prefs["paragraph_range"] = (
        range_key if range_key in PARAGRAPH_RANGE_OPTIONS else DEFAULT_PARAGRAPH_RANGE
    )

    if "auto_generate_images" in raw:
        prefs["auto_generate_images"] = bool(raw.get("auto_generate_images"))

    bg = str(raw.get("background") or DEFAULT_BACKGROUND).strip()
    prefs["background"] = bg if bg in BACKGROUND_OPTIONS else DEFAULT_BACKGROUND

    avatar = str(raw.get("user_avatar") or DEFAULT_USER_AVATAR).strip()
    if avatar in {"male_youth", "boy"}:
        avatar = "male_20"
    elif avatar in {"female_youth", "girl"}:
        avatar = "female_20"
    prefs["user_avatar"] = (
        avatar if avatar in USER_AVATAR_OPTIONS else DEFAULT_USER_AVATAR
    )
    return prefs


def _read_cookie_prefs() -> dict | None:
    try:
        raw = st.context.cookies.get(_COOKIE_NAME)
    except Exception:
        return None
    if not raw:
        return None
    try:
        data = json.loads(unquote(str(raw)))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _persist_browser_prefs(prefs: dict) -> None:
    """Write prefs to cookie + localStorage (no page reload)."""
    payload = json.dumps(prefs, ensure_ascii=False, separators=(",", ":"))
    st.iframe(
        f"""
        <script>
        (function () {{
          const KEY = {json.dumps(_LOCAL_STORAGE_KEY)};
          const COOKIE = {json.dumps(_COOKIE_NAME)};
          const raw = {json.dumps(payload)};
          try {{
            const win = window.parent;
            win.localStorage.setItem(KEY, raw);
            const maxAge = 60 * 60 * 24 * 365;
            win.document.cookie =
              COOKIE + "=" + encodeURIComponent(raw) +
              "; path=/; max-age=" + maxAge + "; SameSite=Lax";
          }} catch (e) {{}}
        }})();
        </script>
        """,
        height=1,
        width=1,
    )


def ensure_prefs_hydrated() -> None:
    """Load per-browser prefs into session_state (once per session)."""
    if st.session_state.get(_HYDRATED_KEY):
        return

    cookie_prefs = _read_cookie_prefs()
    if cookie_prefs is not None:
        prefs = _normalize_prefs(cookie_prefs)
    else:
        # First visit / no cookie yet: seed from legacy file defaults.
        prefs = _normalize_prefs({**_default_prefs(), **_legacy_file_prefs()})
        _persist_browser_prefs(prefs)

    st.session_state[_SESSION_PREFS_KEY] = prefs
    st.session_state[_HYDRATED_KEY] = True

    # Soft-migrate older localStorage-only installs into the cookie (no reload).
    st.iframe(
        f"""
        <script>
        (function () {{
          const KEY = {json.dumps(_LOCAL_STORAGE_KEY)};
          const COOKIE = {json.dumps(_COOKIE_NAME)};
          try {{
            const win = window.parent;
            const hasCookie = (win.document.cookie || "")
              .split(";")
              .some(function (part) {{
                return part.trim().indexOf(COOKIE + "=") === 0;
              }});
            if (hasCookie) return;
            const raw = win.localStorage.getItem(KEY);
            if (!raw) return;
            const maxAge = 60 * 60 * 24 * 365;
            win.document.cookie =
              COOKIE + "=" + encodeURIComponent(raw) +
              "; path=/; max-age=" + maxAge + "; SameSite=Lax";
          }} catch (e) {{}}
        }})();
        </script>
        """,
        height=1,
        width=1,
    )


def load_settings() -> dict:
    """Return current user prefs (session mirror of browser storage)."""
    stored = st.session_state.get(_SESSION_PREFS_KEY)
    if isinstance(stored, dict):
        return dict(stored)
    cookie_prefs = _read_cookie_prefs()
    if cookie_prefs is not None:
        return _normalize_prefs(cookie_prefs)
    return _normalize_prefs(_legacy_file_prefs())


def save_settings(settings: dict) -> None:
    """Persist user prefs to session state, cookie, and localStorage."""
    prefs = _normalize_prefs(settings)
    st.session_state[_SESSION_PREFS_KEY] = prefs
    _persist_browser_prefs(prefs)


def list_ollama_models() -> list[str]:
    """Return only the allowed chat models for the picker."""
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

    by_key: dict[str, str] = {}
    for name in live:
        key = display_model_name(name).lower()
        if key in allowed:
            by_key[key] = name

    ordered = [
        by_key.get(display_model_name(name).lower(), name)
        for name in PRACTICAL_MODELS
    ]
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
    return matched or (available[0] if available else DEFAULT_MODEL)


def set_preferred_model(model: str) -> None:
    """Persist chat model choice in this browser (survives refresh)."""
    settings = load_settings()
    settings["model"] = model
    save_settings(settings)


def set_preferred_image_model(model_key: str) -> None:
    """Persist image model choice and free VRAM from the previous pipeline."""
    key = resolve_image_model(model_key)
    settings = load_settings()
    settings["image_model"] = key
    save_settings(settings)
    clear_image_pipelines()


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


def resolve_preferred_auto_generate_images() -> bool:
    """Whether each story prompt should auto-generate an illustration."""
    settings = load_settings()
    if "auto_generate_images" not in settings:
        return DEFAULT_AUTO_GENERATE_IMAGES
    return bool(settings.get("auto_generate_images"))


def set_preferred_auto_generate_images(enabled: bool) -> None:
    """Persist auto-illustrate-each-prompt preference."""
    settings = load_settings()
    settings["auto_generate_images"] = bool(enabled)
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
