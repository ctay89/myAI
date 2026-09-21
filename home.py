import base64
import html
import importlib
import json
import re
import uuid
from pathlib import Path

import ollama
import streamlit as st
import streamlit.components.v1 as components

import image_gen as _image_gen
from header_nav import apply_forest_background
from preferences import (
    DEFAULT_IMAGE_MODEL,
    DEFAULT_MODEL,
    PRACTICAL_MODELS,
    dedupe_models as _dedupe_models,
    display_model_name,
    image_model_keys,
    image_model_label,
    image_model_style,
    list_ollama_models,
    load_settings,
    match_available_model,
    paragraph_range_label,
    resolve_image_model,
    resolve_preferred_auto_generate_images,
    resolve_preferred_model,
    resolve_preferred_paragraph_range,
    save_settings,
    set_preferred_image_model,
    set_preferred_model,
)

# Streamlit can keep a stale image_gen in memory after edits; refresh if needed
if (
    not hasattr(_image_gen, "generate_image")
    or not hasattr(_image_gen, "IMAGE_MODELS")
    or not hasattr(_image_gen, "image_model_style")
):
    _image_gen = importlib.reload(_image_gen)

generate_image = _image_gen.generate_image
clear_image_pipelines = _image_gen.clear_image_pipelines
# Re-bind after possible reload
image_model_keys = _image_gen.image_model_keys
image_model_label = _image_gen.image_model_label
image_model_style = _image_gen.image_model_style
resolve_image_model = _image_gen.resolve_image_model
DEFAULT_IMAGE_MODEL = _image_gen.DEFAULT_IMAGE_MODEL

STORY_PHASES = ("premise", "appearances", "start", "writing")

APPEARANCES_ASK = (
    "Great premise. Describe how the main characters (and any important creatures "
    "or places) should look — or say **generic** if you want me to invent their "
    "appearances."
)
START_ASK = (
    "Where should we begin? Tell me the opening moment or place to start the story."
)

HISTORY_FILE = Path(__file__).parent / "chat_history.json"
SETTINGS_FILE = Path(__file__).parent / "settings.json"
IMAGE_DIR = Path(__file__).parent / "generated"
ASSETS_DIR = Path(__file__).parent / "assets"
AVATAR_USER = ASSETS_DIR / "avatar_user.png"
AVATAR_ASSISTANT = ASSETS_DIR / "avatar_assistant.png"
ICON_FILE = ASSETS_DIR / "mascot_book.png"
if not ICON_FILE.exists():
    ICON_FILE = ASSETS_DIR / "mascot_rabbit.png"
if not ICON_FILE.exists():
    ICON_FILE = ASSETS_DIR / "robot_clean.png"
LOGO_FILE = ASSETS_DIR / "yourstoriesai_logo.png"
# Fall back to prior marks if the new logo is missing
if not LOGO_FILE.exists():
    LOGO_FILE = ASSETS_DIR / "yourtalesai_logo.png"
if not LOGO_FILE.exists():
    LOGO_FILE = ASSETS_DIR / "chuckai_logo.png"
CHAT_BG_FILE = ASSETS_DIR / "chat_bg_forest.png"
APP_NAME = "YourStoriesAI"


def chat_avatar(role: str) -> str | None:
    """Custom chat bubble avatar; falls back to Streamlit default if missing."""
    if role == "user":
        from preferences import resolve_preferred_user_avatar, user_avatar_file

        path = user_avatar_file(resolve_preferred_user_avatar())
        if not path.exists():
            path = AVATAR_USER
    else:
        path = AVATAR_ASSISTANT
    return str(path) if path.exists() else None


def default_story() -> dict:
    return {
        "phase": "premise",
        "premise": "",
        "appearances": "",
        "start_point": "",
    }


def ensure_story(chat: dict) -> dict:
    """Attach / migrate per-story phase metadata on a chat dict."""
    story = chat.get("story")
    if not isinstance(story, dict):
        msgs = chat.get("messages") or []
        has_user = any(m.get("role") == "user" for m in msgs)
        has_asst = any(m.get("role") == "assistant" for m in msgs)
        story = default_story()
        if has_user and has_asst:
            story["phase"] = "writing"
            for message in msgs:
                if message.get("role") == "user":
                    story["premise"] = (message.get("content") or "").strip()
                    break
        chat["story"] = story
    else:
        if story.get("phase") not in STORY_PHASES:
            story["phase"] = "premise"
        for key in ("premise", "appearances", "start_point"):
            story.setdefault(key, "")
        chat["story"] = story
    return chat["story"]


def _new_chat(title: str = "New Story", messages: list[dict] | None = None) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "title": title,
        "messages": messages or [],
        "story": default_story(),
    }


def load_store() -> dict:
    """Load multi-story store. Migrates old flat message list if needed."""
    if not HISTORY_FILE.exists():
        return {"chats": [], "active_id": None}

    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"chats": [], "active_id": None}

    chats: list[dict] = []
    active_id = None

    # Old format: flat list of {role, content}
    if isinstance(data, list):
        if data and "role" in data[0]:
            title = next(
                (m["content"] for m in data if m.get("role") == "user"),
                "New Story",
            )
            chat = _new_chat(title=_title_from(title), messages=data)
            chats = [chat]
            active_id = chat["id"]
        elif data and "id" in data[0] and "messages" in data[0]:
            chats = data
            active_id = data[0]["id"]
    elif isinstance(data, dict) and "chats" in data:
        chats = data.get("chats") or []
        active_id = data.get("active_id")

    for chat in chats:
        if isinstance(chat, dict):
            ensure_story(chat)

    return {"chats": chats, "active_id": active_id}


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
        return text or "New Story"
    return text[: max_len - 1] + "…"


def _merge_truncated_title(title: str, fragment: str) -> str:
    """Rejoin a truncated sidebar title with the surviving prompt fragment."""
    title = (title or "").strip()
    fragment = " ".join((fragment or "").strip().split())
    if not title and not fragment:
        return "New Story"
    if not fragment:
        return title.rstrip("…").rstrip("...").strip() or "New Story"
    if not title:
        return fragment

    truncated = title.endswith("…") or title.endswith("...")
    stem = title[:-1].strip() if title.endswith("…") else title
    if title.endswith("..."):
        stem = title[:-3].strip()

    if not truncated:
        # Prefer the longer complete string
        if fragment.lower().startswith(stem.lower()) or stem.lower() in fragment.lower():
            return fragment if len(fragment) >= len(stem) else stem
        return fragment

    frag_l = fragment.lower()
    stem_l = stem.lower()
    if frag_l.startswith(stem_l):
        return fragment
    # Longest suffix of stem that is a prefix of fragment
    for n in range(min(len(stem), len(fragment)), 0, -1):
        if frag_l.startswith(stem_l[-n:]):
            return stem[:-n] + fragment
    # Title still has original lead-in the fragment lost (e.g. "show a picture and …")
    if stem_l[:12] not in frag_l:
        return f"{stem} {fragment}".replace("  ", " ").strip()
    return fragment


def chat_full_prompt(chat: dict) -> str:
    """Full original prompt text for sidebar hover tooltips."""
    title = (chat.get("title") or "").strip()
    stored = (chat.get("title_full") or "").strip()
    first = ""
    original = ""
    for message in chat.get("messages") or []:
        if message.get("role") != "user":
            continue
        original = (message.get("original_content") or "").strip()
        first = (message.get("content") or "").strip()
        break

    if original:
        best = " ".join(original.split())
    else:
        best = _merge_truncated_title(title, stored or first)

    # Prefer a recovered/fuller string over a short rewritten title_full
    if best and len(best) > len(stored):
        chat["title_full"] = best
    elif not stored and best:
        chat["title_full"] = best
    return best or stored or first or title or "New Story"


def set_chat_title(chat: dict, text: str) -> None:
    """Set truncated sidebar title and keep the full prompt for hover tooltips."""
    cleaned = " ".join((text or "").strip().split())
    chat["title_full"] = cleaned or "New Story"
    chat["title"] = _title_from(cleaned)


def get_active_chat() -> dict | None:
    active_id = st.session_state.active_id
    for chat in st.session_state.chats:
        if chat["id"] == active_id:
            return chat
    return None


def resolve_image_path(image_rel: str) -> Path | None:
    path = Path(image_rel)
    if not path.is_absolute():
        path = Path(__file__).parent / path
    return path if path.exists() else None


def chat_image_paths(chat: dict) -> list[Path]:
    """Absolute paths of generated images referenced by a chat."""
    paths: list[Path] = []
    seen: set[Path] = set()
    for message in chat.get("messages") or []:
        image_rel = message.get("image")
        if not image_rel:
            continue
        path = Path(image_rel)
        if not path.is_absolute():
            path = Path(__file__).parent / path
        try:
            path = path.resolve()
        except OSError:
            continue
        # Only delete files inside the generated/ folder
        try:
            path.relative_to(IMAGE_DIR.resolve())
        except ValueError:
            continue
        if path in seen:
            continue
        seen.add(path)
        paths.append(path)
    return paths


def delete_chat_images(chat: dict) -> None:
    """Remove generated image files that belong to this chat."""
    for path in chat_image_paths(chat):
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass


def delete_chat(chat_id: str) -> None:
    doomed = next((c for c in st.session_state.chats if c["id"] == chat_id), None)
    if doomed is not None:
        delete_chat_images(doomed)
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


def clear_all_chats() -> None:
    """Delete every chat and its generated images, then start a fresh chat."""
    for chat in list(st.session_state.chats):
        delete_chat_images(chat)
    new_chat = _new_chat()
    st.session_state.chats = [new_chat]
    st.session_state.active_id = new_chat["id"]
    persist()


def _clear_history_dialog_body() -> None:
    st.markdown(
        "You are about to delete all Stories. Are you sure you want to do that?"
    )
    col_ok, col_cancel = st.columns(2)
    with col_ok:
        if st.button(
            "OK",
            key="confirm_clear_ok",
            type="primary",
            use_container_width=True,
        ):
            clear_all_chats()
            st.session_state.confirm_clear = False
            st.rerun()
    with col_cancel:
        if st.button(
            "Cancel",
            key="confirm_clear_cancel",
            use_container_width=True,
        ):
            st.session_state.confirm_clear = False
            st.rerun()


if hasattr(st, "dialog"):

    @st.dialog("Clear story history")
    def show_clear_history_confirmation() -> None:
        _clear_history_dialog_body()

else:

    def show_clear_history_confirmation() -> None:
        with st.sidebar:
            st.warning(
                "You are about to delete all Stories. Are you sure you want to do that?"
            )
            _clear_history_dialog_body()


def persist() -> None:
    save_store(st.session_state.chats, st.session_state.active_id)


def base_system_prompt() -> str:
    """Core writing instructions, using the Settings paragraph-range preference."""
    paragraphs = paragraph_range_label(resolve_preferred_paragraph_range())
    return (
        "You are YourStoriesAI, a short-story collaborator. Write vivid prose in exactly "
        f"{paragraphs} paragraphs per prompt. Stay consistent with the premise, character "
        "appearances, and prior scenes. When continuing, pick up exactly where the "
        "last scene left off and weave in the user's new direction. Write only story "
        "prose — no titles, preambles, or meta commentary. End every scene with the "
        "exact line: What happens next?"
    )


SCENE_CHOICE_PROMPT = "What happens next?"


def with_scene_choice_prompt(text: str) -> str:
    """Ensure scene prose ends with the interactive choice line."""
    cleaned = (text or "").rstrip()
    if not cleaned:
        return SCENE_CHOICE_PROMPT
    if cleaned.endswith(SCENE_CHOICE_PROMPT):
        return cleaned
    return f"{cleaned}\n\n{SCENE_CHOICE_PROMPT}"


def wants_generic_appearances(text: str) -> bool:
    lower = (text or "").strip().lower()
    if not lower:
        return True
    if lower in {
        "generic",
        "default",
        "whatever",
        "you decide",
        "you choose",
        "n/a",
        "na",
        "-",
    }:
        return True
    return bool(
        re.search(
            r"\b(generic|default|whatever|you (decide|choose|pick|invent)|"
            r"up to you|don'?t care|no preference|surprise me)\b",
            lower,
        )
    )


def story_system_prompt(chat: dict) -> str:
    """System prompt plus the story bible for consistency across scenes."""
    story = ensure_story(chat)
    parts = [base_system_prompt()]
    premise = (story.get("premise") or "").strip()
    appearances = (story.get("appearances") or "").strip()
    start_point = (story.get("start_point") or "").strip()
    if premise:
        parts.append(f"Premise:\n{premise}")
    if appearances:
        if wants_generic_appearances(appearances):
            parts.append(
                "Appearances:\nInvent fitting, consistent looks for characters "
                "and key places; keep them stable across scenes."
            )
        else:
            parts.append(f"Appearances:\n{appearances}")
    if start_point:
        parts.append(f"Opening start point:\n{start_point}")
    return "\n\n".join(parts)


def story_input_placeholder(phase: str) -> str:
    return {
        "premise": "Describe your story idea…",
        "appearances": "Describe characters, or say generic…",
        "start": "Where should the story begin?",
        "writing": "Continue, or steer the story…",
    }.get(phase, "Describe your story idea…")


def ollama_messages(
    messages: list[dict],
    *,
    include_system: bool = True,
    system_prompt: str | None = None,
) -> list[dict]:
    """Build the message list for Ollama, including prior turns in this story."""
    out: list[dict] = []
    if include_system:
        out.append({"role": "system", "content": system_prompt or base_system_prompt()})

    for m in messages:
        role = m.get("role")
        if role not in ("user", "assistant", "system"):
            continue
        content = (m.get("content") or "").strip()
        # So follow-ups know what an image reply actually depicted
        image_prompt = (m.get("image_prompt") or "").strip()
        if m.get("image") and image_prompt:
            note = f"[Generated image depicting: {image_prompt}]"
            content = f"{content}\n\n{note}".strip() if content else note
        if content:
            out.append({"role": role, "content": content})
    return out


def chat_completion(
    messages: list[dict],
    model: str,
    *,
    system_prompt: str | None = None,
) -> str:
    """Non-streaming reply using full conversation history."""
    response = ollama.chat(
        model=model,
        messages=ollama_messages(messages, system_prompt=system_prompt),
        stream=False,
    )
    return (response.message.content or "").strip()


def write_story_scene(chat: dict, model: str, *, opening: bool) -> str:
    """Generate the next scene using the configured paragraph range."""
    paragraphs = paragraph_range_label(resolve_preferred_paragraph_range())
    if opening:
        nudge = (
            f"Write the opening scene now in exactly {paragraphs} paragraphs, starting from "
            "the opening start point. Only story prose, then end with the exact "
            "line: What happens next?"
        )
    else:
        nudge = (
            f"Continue from where the last scene ended in exactly {paragraphs} paragraphs, "
            "following my latest direction. Only story prose, then end with the "
            "exact line: What happens next?"
        )
    # Ephemeral writing instruction — not stored in chat history
    msgs = list(chat["messages"]) + [{"role": "user", "content": nudge}]
    return chat_completion(
        msgs, model, system_prompt=story_system_prompt(chat)
    )


def scene_prompt_from_story(messages: list[dict], story_request: str, model: str) -> str:
    """Build a concise image-generation prompt that matches the story scene."""
    expand_msgs = ollama_messages(messages) + [
        {
            "role": "user",
            "content": (
                "Write one detailed image-generation prompt that illustrates the main "
                "moment from this scene. Focus on characters, setting, mood, and key "
                "visual details — not the full plot.\n\n"
                f"{story_request}\n\n"
                "Reply with ONLY the image prompt — no quotes or explanation."
            ),
        }
    ]
    try:
        response = ollama.chat(model=model, messages=expand_msgs, stream=False)
        expanded = (response.message.content or "").strip().strip('"').strip("'")
        if "\n" in expanded:
            expanded = expanded.split("\n")[0].strip().strip('"').strip("'")
        return expanded or story_request[:200]
    except Exception:
        return story_request[:200]


def illustrate_scene(
    chat: dict, scene_text: str, model: str
) -> tuple[object | None, str | None, str, Exception | None]:
    """
    Create a scene illustration.

    Returns (pil_image_or_none, relative_path_or_none, draw_prompt, error_or_none).
    """
    story = ensure_story(chat)
    appearances = (story.get("appearances") or "").strip() or "generic"
    if wants_generic_appearances(appearances):
        appearance_note = "Invent fitting character and setting looks."
    else:
        appearance_note = appearances

    draw_prompt = ""
    try:
        draw_prompt = scene_prompt_from_story(
            chat["messages"],
            f"Appearances:\n{appearance_note}\n\nScene to illustrate:\n{scene_text}",
            model,
        )
        image = generate_image(
            draw_prompt,
            model_key=st.session_state.image_model,
        )
        return image, save_generated_image(image, draw_prompt), draw_prompt, None
    except Exception as e:
        return None, None, draw_prompt, e


def save_generated_image(image, prompt: str) -> str:
    """Save PIL image under generated/ and return a relative path string."""
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.png"
    path = IMAGE_DIR / filename
    image.save(path)
    return str(Path("generated") / filename)


def render_message(message: dict) -> None:
    role = message["role"]
    with st.chat_message(role, avatar=chat_avatar(role)):
        image_rel = message.get("image")
        if image_rel:
            image_path = Path(image_rel)
            if not image_path.is_absolute():
                image_path = Path(__file__).parent / image_path
            if image_path.exists():
                st.image(str(image_path), use_container_width=True)
        st.markdown(message["content"])


def append_assistant_message(
    chat: dict,
    content: str,
    *,
    image: str | None = None,
    image_prompt: str = "",
) -> dict:
    msg: dict = {"role": "assistant", "content": content}
    if image:
        msg["image"] = image
        if image_prompt:
            msg["image_prompt"] = image_prompt
    chat["messages"].append(msg)
    return msg


def sync_chat_title(active: dict, text: str) -> None:
    set_chat_title(active, text)
    for chat in st.session_state.chats:
        if chat["id"] == active["id"]:
            set_chat_title(chat, text)
            break


def install_sidebar_logo_tooltip(
    full_text: str = f"{APP_NAME} - How can we start your story today?",
    icon_text: str = "How can we start your story today?",
) -> None:
    """Native title tooltips on sidebar / header logos (full mark + book icon)."""
    components.html(
        f"""
        <script>
        (function () {{
          var fullTip = {json.dumps(full_text)};
          var iconTip = {json.dumps(icon_text)};
          var doc = window.parent.document;

          function setTip(el, tip) {{
            if (!el) return;
            el.setAttribute("title", tip);
            if (el.tagName === "IMG") return;
            var img = el.querySelector("img");
            if (img) img.setAttribute("title", tip);
            var link = el.closest("a") || el.querySelector("a");
            if (link) link.setAttribute("title", tip);
          }}

          function apply() {{
            // Expanded sidebar wordmark
            [
              doc.querySelector('[data-testid="stSidebarHeader"] [data-testid="stSidebarLogo"]'),
              doc.querySelector('[data-testid="stSidebarHeader"] [data-testid="stLogo"]'),
              doc.querySelector('[data-testid="stSidebarLogo"]')
            ].forEach(function (el) {{ setTip(el, fullTip); }});

            // Little mascot in collapsed sidebar / app header (icon_image)
            [
              doc.querySelector('[data-testid="stHeader"] [data-testid="stLogo"]'),
              doc.querySelector('[data-testid="stHeader"] [data-testid="stLogoLink"]'),
              doc.querySelector('[data-testid="stHeader"] img'),
              doc.querySelector('[data-testid="stSidebarCollapsed"] [data-testid="stLogo"]'),
              doc.querySelector('[data-testid="stSidebarCollapsed"] img'),
              doc.querySelector('[data-testid="stSidebarCollapsed"] [data-testid="stSidebarLogo"]')
            ].forEach(function (el) {{ setTip(el, iconTip); }});

            // Any remaining sidebar-header images (robot-only mark)
            doc.querySelectorAll(
              '[data-testid="stSidebarHeader"] img, [data-testid="stHeader"] img'
            ).forEach(function (img) {{
              if (!img.getAttribute("title")) img.setAttribute("title", iconTip);
            }});
          }}

          apply();
          setTimeout(apply, 50);
          setTimeout(apply, 250);
          setTimeout(apply, 800);

          // Re-apply when the collapsed header robot appears/disappears
          var timer = null;
          try {{
            var obs = new MutationObserver(function () {{
              if (timer) clearTimeout(timer);
              timer = setTimeout(apply, 80);
            }});
            obs.observe(doc.body, {{ childList: true, subtree: true }});
          }} catch (e) {{}}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def install_nav_chat_tooltips(tips: dict[str, str]) -> None:
    """
    Attach native browser title tooltips to sidebar chat buttons.

    Streamlit's help= popovers overlay neighboring rows and block clicks;
    title= does not.
    """
    if not tips:
        return
    components.html(
        f"""
        <script>
        (function () {{
          var tips = {json.dumps(tips)};
          var doc = window.parent.document;

          function apply() {{
            Object.keys(tips).forEach(function (id) {{
              var text = tips[id];
              if (!text) return;
              var openWrap = doc.querySelector('[class*="st-key-open_' + id + '"]');
              if (openWrap) {{
                var btn = openWrap.querySelector("button");
                if (btn) btn.setAttribute("title", text);
              }}
              var delWrap = doc.querySelector('[class*="st-key-del_' + id + '"]');
              if (delWrap) {{
                var dbtn = delWrap.querySelector("button");
                if (dbtn) dbtn.setAttribute("title", "Delete this chat");
              }}
            }});
          }}

          apply();
          setTimeout(apply, 50);
          setTimeout(apply, 250);
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def install_scroll_controls(*, force_bottom: bool = False) -> None:
    """
    Jump-to-bottom control + optional scroll-on-submit.

    Uses a real in-page anchor (works without JS). JS only shows/hides the
    button when scrolled up, and force-scrolls after a new prompt.
    """
    # End-of-chat target for the floating control / force scroll
    st.markdown('<div id="chuckai-chat-end"></div>', unsafe_allow_html=True)
    # Native link — scrolls even if iframe scripts are blocked
    st.markdown(
        '<a href="#chuckai-chat-end" id="chuckai-scroll-bottom" '
        'title="Scroll to bottom" aria-label="Scroll to bottom">▼</a>',
        unsafe_allow_html=True,
    )
    components.html(
        f"""
        <div style="height:1px;width:1px;overflow:hidden;opacity:0;">.</div>
        <script>
        (function () {{
          var w = window.parent;
          var doc = w.document;
          var FORCE = {str(force_bottom).lower()};
          var BTN_ID = "chuckai-scroll-bottom";
          var END_ID = "chuckai-chat-end";

          function endEl() {{
            return doc.getElementById(END_ID);
          }}

          function findScroller() {{
            var tip =
              endEl() ||
              doc.querySelector('[data-testid="stChatMessage"]:last-of-type') ||
              doc.querySelector('[data-testid="stChatInput"]') ||
              doc.querySelector('[data-testid="stMain"]') ||
              doc.body;
            var best = doc.scrollingElement || doc.documentElement;
            var bestScore = -1;
            var el = tip;
            while (el) {{
              try {{
                var style = w.getComputedStyle(el);
                var oy = style.overflowY;
                var can =
                  oy === "auto" ||
                  oy === "scroll" ||
                  oy === "overlay" ||
                  (el.scrollHeight || 0) > (el.clientHeight || 0) + 20;
                if (can) {{
                  var score = (el.scrollHeight || 0) - (el.clientHeight || 0);
                  if (score > bestScore) {{
                    bestScore = score;
                    best = el;
                  }}
                }}
              }} catch (e) {{}}
              if (el === doc.documentElement || el === doc.body) break;
              el = el.parentElement;
            }}
            return best;
          }}

          function scrollToBottom(smooth) {{
            var target = endEl();
            if (target) {{
              try {{
                target.scrollIntoView({{
                  behavior: smooth ? "smooth" : "instant",
                  block: "end",
                }});
              }} catch (e1) {{
                try {{
                  target.scrollIntoView(false);
                }} catch (e2) {{}}
              }}
            }}
            var scroller = findScroller();
            try {{
              scroller.scrollTop = scroller.scrollHeight;
            }} catch (e3) {{}}
            try {{
              w.scrollTo(0, Math.max(
                doc.body.scrollHeight,
                doc.documentElement.scrollHeight
              ));
            }} catch (e4) {{}}
          }}

          function distanceFromBottom() {{
            var el = findScroller();
            return Math.max(0, (el.scrollHeight || 0) - (el.scrollTop || 0) - (el.clientHeight || 0));
          }}

          function setButtonVisible(show) {{
            var btn = doc.getElementById(BTN_ID);
            if (!btn) return;
            // Move onto body so position:fixed isn't trapped by Streamlit transforms
            if (btn.parentElement !== doc.body) {{
              doc.body.appendChild(btn);
            }}
            if (show) {{
              btn.classList.add("is-up");
              btn.classList.remove("at-bottom");
            }} else {{
              btn.classList.remove("is-up");
              btn.classList.add("at-bottom");
            }}
          }}

          function updateButton() {{
            var end = endEl();
            // Prefer whether the end anchor is on screen (most reliable)
            if (end) {{
              var scroller = findScroller();
              var rootRect =
                scroller === doc.scrollingElement ||
                scroller === doc.documentElement ||
                scroller === doc.body
                  ? {{ top: 0, bottom: w.innerHeight, left: 0, right: w.innerWidth }}
                  : scroller.getBoundingClientRect();
              var rect = end.getBoundingClientRect();
              // Treat as "at bottom" if the end marker is within ~120px of the
              // visible bottom (chat input sits over the lower edge)
              var nearBottom =
                rect.top < rootRect.bottom - 8 &&
                rect.bottom > rootRect.top + 8 &&
                rect.bottom <= rootRect.bottom + 120;
              setButtonVisible(!nearBottom);
              return;
            }}
            setButtonVisible(distanceFromBottom() > 24);
          }}

          if (w.__chuckAIScrollAC) {{
            try {{ w.__chuckAIScrollAC.abort(); }} catch (e) {{}}
          }}
          w.__chuckAIScrollAC = new AbortController();
          var signal = w.__chuckAIScrollAC.signal;
          doc.addEventListener("scroll", updateButton, {{
            capture: true,
            passive: true,
            signal: signal,
          }});
          w.addEventListener("scroll", updateButton, {{ passive: true, signal: signal }});
          w.addEventListener("resize", updateButton, {{ passive: true, signal: signal }});

          // IntersectionObserver: hide whenever #chuckai-chat-end is in view
          try {{
            if (w.__chuckAIScrollIO) {{
              w.__chuckAIScrollIO.disconnect();
            }}
            var end = endEl();
            if (end && "IntersectionObserver" in w) {{
              w.__chuckAIScrollIO = new w.IntersectionObserver(
                function (entries) {{
                  entries.forEach(function (entry) {{
                    // Visible at/near bottom → hide arrow; otherwise show
                    setButtonVisible(!entry.isIntersecting);
                  }});
                }},
                {{
                  root: null,
                  // Expand bottom so the sticky chat input still counts as "at bottom"
                  rootMargin: "0px 0px 140px 0px",
                  threshold: 0,
                }}
              );
              w.__chuckAIScrollIO.observe(end);
            }}
          }} catch (eIO) {{}}

          if (!w.__chuckAIScrollTimer) {{
            w.__chuckAIScrollTimer = w.setInterval(function () {{
              try {{ updateButton(); }} catch (e) {{}}
            }}, 400);
          }}

          w.chuckAIScrollToBottom = scrollToBottom;
          // Start hidden; only show after we confirm the user is scrolled up
          setButtonVisible(false);
          updateButton();

          if (FORCE) {{
            scrollToBottom(false);
            setButtonVisible(false);
            var n = 0;
            if (w.__chuckAIForceTimer) {{
              try {{ w.clearInterval(w.__chuckAIForceTimer); }} catch (e) {{}}
            }}
            w.__chuckAIForceTimer = w.setInterval(function () {{
              scrollToBottom(false);
              setButtonVisible(false);
              n += 1;
              if (n >= 50) {{
                w.clearInterval(w.__chuckAIForceTimer);
                w.__chuckAIForceTimer = null;
                updateButton();
              }}
            }}, 200);
          }}
        }})();
        </script>
        """,
        height=1,
        width=1,
    )




if LOGO_FILE.exists():
    _logo_kwargs: dict = {"size": "medium"}
    if ICON_FILE.exists():
        _logo_kwargs["icon_image"] = str(ICON_FILE)
    st.logo(str(LOGO_FILE), **_logo_kwargs)
    install_sidebar_logo_tooltip()
    _logo_b64 = base64.b64encode(LOGO_FILE.read_bytes()).decode("ascii")
    st.markdown(
        f'<div class="chuckai-hero">'
        f'<img src="data:image/png;base64,{_logo_b64}" '
        f'alt="{APP_NAME}" width="360" />'
        f'<p class="chuckai-tagline">How can we start your story today?</p>'
        f"</div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f'<div class="chuckai-hero">'
        f"<h1>YourStories<span>AI</span></h1>"
        f'<p class="chuckai-tagline">How can we start your story today?</p>'
        f"</div>",
        unsafe_allow_html=True,
    )

apply_forest_background(include_chat_input=True)

st.markdown(
    """
    <style>
    :root {
        --nav-bg: #f3f8f9;
        --nav-border: #d4e4e8;
        --nav-text: #1a2b32;
        --nav-muted: #5a7380;
        --nav-accent: #0d8a9a;
        --nav-accent-soft: rgba(42, 168, 184, 0.14);
        --nav-hover: rgba(42, 168, 184, 0.10);
    }

    /* Sidebar shell */
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
    /* Compact YourStoriesAI mark inline with the sidebar collapse control */
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
    [data-testid="stSidebarContent"] > div {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }

    /* Section labels */
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

    /* Primary sidebar actions: New chat / Clear history */
    section[data-testid="stSidebar"] [class*="st-key-nav_new_chat"],
    section[data-testid="stSidebar"] .st-key-nav_new_chat {
        margin: 0.15rem 0 0.55rem 0 !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_clear_history"],
    section[data-testid="stSidebar"] .st-key-nav_clear_history {
        margin-top: 1.15rem !important;
        margin-bottom: 0.55rem !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_new_chat"] button,
    section[data-testid="stSidebar"] .st-key-nav_new_chat button,
    section[data-testid="stSidebar"] [class*="st-key-nav_clear_history"] button,
    section[data-testid="stSidebar"] .st-key-nav_clear_history button {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 0.35rem !important;
        width: 100% !important;
        box-sizing: border-box !important;
        padding: 0.55rem 0.75rem !important;
        border-radius: 0.55rem !important;
        background: var(--nav-accent) !important;
        background-color: var(--nav-accent) !important;
        color: #fff !important;
        font-size: 0.84rem !important;
        font-weight: 600 !important;
        text-decoration: none !important;
        line-height: 1.25 !important;
        border: none !important;
        box-shadow: none !important;
        cursor: pointer !important;
        text-align: center !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_new_chat"] button:hover,
    section[data-testid="stSidebar"] .st-key-nav_new_chat button:hover,
    section[data-testid="stSidebar"] [class*="st-key-nav_clear_history"] button:hover,
    section[data-testid="stSidebar"] .st-key-nav_clear_history button:hover {
        background: #0a7382 !important;
        background-color: #0a7382 !important;
        color: #fff !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_new_chat"] button p,
    section[data-testid="stSidebar"] .st-key-nav_new_chat button p,
    section[data-testid="stSidebar"] [class*="st-key-nav_clear_history"] button p,
    section[data-testid="stSidebar"] .st-key-nav_clear_history button p {
        text-align: center !important;
        width: 100% !important;
        color: inherit !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    section[data-testid="stSidebar"] .nav-subtle {
        display: block !important;
        margin: 0.45rem 0 0.15rem 0 !important;
        padding: 0 !important;
        text-align: left !important;
    }
    section[data-testid="stSidebar"] .nav-subtle a {
        color: var(--nav-muted) !important;
        text-decoration: none !important;
        font-size: 0.78rem !important;
        line-height: 1.35 !important;
    }
    section[data-testid="stSidebar"] .nav-subtle a:hover {
        color: var(--nav-accent) !important;
        text-decoration: underline !important;
    }

    /* Model / Image pickers — selectbox: left text + arrow on one line */
    section[data-testid="stSidebar"] [class*="st-key-nav_models"] [data-testid="stSelectbox"],
    section[data-testid="stSidebar"] .st-key-nav_models [data-testid="stSelectbox"] {
        margin: 0 !important;
        padding: 0 !important;
        cursor: pointer !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_models"] [data-testid="stSelectbox"] *,
    section[data-testid="stSidebar"] .st-key-nav_models [data-testid="stSelectbox"] *,
    section[data-testid="stSidebar"] [class*="st-key-nav_models"] [data-baseweb="select"],
    section[data-testid="stSidebar"] .st-key-nav_models [data-baseweb="select"],
    section[data-testid="stSidebar"] [class*="st-key-nav_models"] [data-baseweb="select"] *,
    section[data-testid="stSidebar"] .st-key-nav_models [data-baseweb="select"] * {
        cursor: pointer !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_models"] [data-baseweb="select"] > div,
    section[data-testid="stSidebar"] .st-key-nav_models [data-baseweb="select"] > div {
        background: transparent !important;
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        min-height: 2rem !important;
        height: auto !important;
        padding-left: 0.35rem !important;
        padding-right: 0.25rem !important;
        border-radius: 0.45rem !important;
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        justify-content: space-between !important;
        cursor: pointer !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_models"] [data-baseweb="select"] > div:hover,
    section[data-testid="stSidebar"] .st-key-nav_models [data-baseweb="select"] > div:hover {
        background: var(--nav-hover) !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_models"] [data-baseweb="select"] [data-testid="stMarkdownContainer"],
    section[data-testid="stSidebar"] .st-key-nav_models [data-baseweb="select"] [data-testid="stMarkdownContainer"],
    section[data-testid="stSidebar"] [class*="st-key-nav_models"] [data-baseweb="select"] [data-testid="stMarkdownContainer"] p,
    section[data-testid="stSidebar"] .st-key-nav_models [data-baseweb="select"] [data-testid="stMarkdownContainer"] p {
        text-align: left !important;
        justify-content: flex-start !important;
        margin: 0 !important;
        color: var(--nav-text) !important;
        font-size: 0.84rem !important;
        font-weight: 500 !important;
        line-height: 1.35 !important;
        white-space: nowrap !important;
    }
    /* Native chevron on the same row, far right */
    section[data-testid="stSidebar"] [class*="st-key-nav_models"] [data-baseweb="select"] svg,
    section[data-testid="stSidebar"] .st-key-nav_models [data-baseweb="select"] svg {
        display: inline-block !important;
        visibility: visible !important;
        width: 1.1rem !important;
        height: 1.1rem !important;
        color: var(--nav-muted) !important;
        flex-shrink: 0 !important;
        cursor: pointer !important;
    }
    /* IMAGE MODEL dropdown + type line: fixed offset so spacing never jumps on rerun */
    section[data-testid="stSidebar"] [class*="st-key-nav_image_model"],
    section[data-testid="stSidebar"] .st-key-nav_image_model {
        position: relative !important;
        padding-bottom: 1.9rem !important;
        margin-bottom: 0.15rem !important;
        box-sizing: border-box !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_image_model"] [data-testid="stVerticalBlock"],
    section[data-testid="stSidebar"] .st-key-nav_image_model [data-testid="stVerticalBlock"] {
        gap: 0 !important;
        position: static !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_image_model"] [data-testid="stElementContainer"],
    section[data-testid="stSidebar"] .st-key-nav_image_model [data-testid="stElementContainer"] {
        margin: 0 !important;
        padding: 0 !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_image_model"] [data-testid="stSelectbox"],
    section[data-testid="stSidebar"] .st-key-nav_image_model [data-testid="stSelectbox"] {
        margin: 0 !important;
        padding: 0 !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_image_model"] [data-testid="stElementContainer"]:has(.nav-model-style),
    section[data-testid="stSidebar"] .st-key-nav_image_model [data-testid="stElementContainer"]:has(.nav-model-style) {
        position: absolute !important;
        left: 0 !important;
        right: 0 !important;
        top: 2.8rem !important;
        bottom: auto !important;
        height: auto !important;
        min-height: 0 !important;
        max-height: none !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: visible !important;
        pointer-events: none !important;
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
    /* Hand cursor on open model-menu options (portaled outside sidebar) */
    div[data-baseweb="popover"] [role="listbox"] *,
    div[data-baseweb="popover"] [role="option"],
    ul[role="listbox"] li {
        cursor: pointer !important;
    }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
        display: none !important;
    }

    /* Sidebar chat/action buttons only — do not style popover / selectbox internals */
    section[data-testid="stSidebar"] .stButton {
        width: 100% !important;
        text-align: left !important;
    }
    section[data-testid="stSidebar"] .stButton > button {
        background: transparent !important;
        background-color: transparent !important;
        border: none !important;
        border-width: 0 !important;
        box-shadow: none !important;
        outline: none !important;
        padding: 0.4rem 0.5rem !important;
        min-height: 0 !important;
        height: auto !important;
        font-size: 0.84rem !important;
        font-weight: 500 !important;
        line-height: 1.35 !important;
        color: var(--nav-text) !important;
        display: flex !important;
        justify-content: flex-start !important;
        align-items: center !important;
        text-align: left !important;
        width: 100% !important;
        max-width: 100% !important;
        overflow: hidden !important;
        border-radius: 0.45rem !important;
    }
    section[data-testid="stSidebar"] .stButton > button > div,
    section[data-testid="stSidebar"] .stButton > button [data-testid="stMarkdownContainer"] {
        width: 100% !important;
        max-width: 100% !important;
        display: flex !important;
        justify-content: flex-start !important;
        align-items: center !important;
        text-align: left !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        color: var(--nav-accent) !important;
        background: var(--nav-hover) !important;
        border: none !important;
        text-decoration: none !important;
    }
    section[data-testid="stSidebar"] .stButton > button p {
        margin: 0 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        text-align: left !important;
        width: 100% !important;
    }
    /* Default tertiary chat rows — normal case */
    section[data-testid="stSidebar"] .stButton button[kind="tertiary"],
    section[data-testid="stSidebar"] .stButton button[data-testid="baseButton-tertiary"],
    section[data-testid="stSidebar"] .stButton button[data-testid="stBaseButton-tertiary"] {
        color: var(--nav-text) !important;
        font-size: 0.84rem !important;
        font-weight: 500 !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        padding: 0.4rem 0.5rem !important;
    }
    /* Active chat */
    section[data-testid="stSidebar"] .stButton button[kind="primary"],
    section[data-testid="stSidebar"] .stButton button[data-testid="baseButton-primary"],
    section[data-testid="stSidebar"] .stButton button[data-testid="stBaseButton-primary"] {
        color: var(--nav-accent) !important;
        font-weight: 600 !important;
        text-decoration: none !important;
        background: var(--nav-accent-soft) !important;
    }
    section[data-testid="stSidebar"] .stButton button[kind="primary"]:hover,
    section[data-testid="stSidebar"] .stButton button[data-testid="baseButton-primary"]:hover,
    section[data-testid="stSidebar"] .stButton button[data-testid="stBaseButton-primary"]:hover {
        background: rgba(42, 168, 184, 0.22) !important;
        color: #0a7382 !important;
    }

    /* Teal action buttons must win over generic transparent sidebar buttons */
    section[data-testid="stSidebar"] [class*="st-key-nav_new_chat"] .stButton > button,
    section[data-testid="stSidebar"] .st-key-nav_new_chat .stButton > button,
    section[data-testid="stSidebar"] [class*="st-key-nav_clear_history"] .stButton > button,
    section[data-testid="stSidebar"] .st-key-nav_clear_history .stButton > button {
        background: var(--nav-accent) !important;
        background-color: var(--nav-accent) !important;
        color: #fff !important;
        justify-content: center !important;
        text-align: center !important;
        padding: 0.55rem 0.75rem !important;
        border-radius: 0.55rem !important;
        font-weight: 600 !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_new_chat"] .stButton > button:hover,
    section[data-testid="stSidebar"] .st-key-nav_new_chat .stButton > button:hover,
    section[data-testid="stSidebar"] [class*="st-key-nav_clear_history"] .stButton > button:hover,
    section[data-testid="stSidebar"] .st-key-nav_clear_history .stButton > button:hover {
        background: #0a7382 !important;
        background-color: #0a7382 !important;
        color: #fff !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_new_chat"] .stButton > button > div,
    section[data-testid="stSidebar"] [class*="st-key-nav_new_chat"] .stButton > button [data-testid="stMarkdownContainer"],
    section[data-testid="stSidebar"] .st-key-nav_new_chat .stButton > button > div,
    section[data-testid="stSidebar"] .st-key-nav_new_chat .stButton > button [data-testid="stMarkdownContainer"],
    section[data-testid="stSidebar"] [class*="st-key-nav_clear_history"] .stButton > button > div,
    section[data-testid="stSidebar"] [class*="st-key-nav_clear_history"] .stButton > button [data-testid="stMarkdownContainer"],
    section[data-testid="stSidebar"] .st-key-nav_clear_history .stButton > button > div,
    section[data-testid="stSidebar"] .st-key-nav_clear_history .stButton > button [data-testid="stMarkdownContainer"] {
        width: 100% !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_new_chat"] .stButton > button p,
    section[data-testid="stSidebar"] .st-key-nav_new_chat .stButton > button p,
    section[data-testid="stSidebar"] [class*="st-key-nav_clear_history"] .stButton > button p,
    section[data-testid="stSidebar"] .st-key-nav_clear_history .stButton > button p {
        text-align: center !important;
        color: #fff !important;
        width: 100% !important;
    }

    /* Chat list: collapse Streamlit's default row gap only inside this block */
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="stVerticalBlock"],
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="stVerticalBlock"] {
        gap: 0 !important;
        row-gap: 0 !important;
    }
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="stElementContainer"],
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="stElementContainer"] {
        margin: 0 !important;
        padding: 0 !important;
    }
    /*
     * Streamlit 1.60: help= wraps the button itself in stTooltipIcon /
     * stTooltipHoverTarget (not a separate "?" icon). Never display:none those.
     */
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="stTooltipIcon"],
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="stTooltipIcon"],
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="stTooltipHoverTarget"],
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="stTooltipHoverTarget"] {
        display: flex !important;
        align-items: center !important;
        width: 100% !important;
        max-width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
        min-width: 0 !important;
        visibility: visible !important;
        opacity: 1 !important;
    }

    /* Full-width chat row: title + trash share one highlight bar */
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="stHorizontalBlock"],
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="stHorizontalBlock"] {
        gap: 0.15rem !important;
        align-items: center !important;
        margin: -0.12rem 0 !important;
        padding: 0 0.35rem 0 0.25rem !important;
        border-radius: 0.4rem !important;
        overflow: visible !important;
        min-height: 1.35rem !important;
        background: transparent !important;
        width: 100% !important;
        box-sizing: border-box !important;
        display: flex !important;
        flex-wrap: nowrap !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="stHorizontalBlock"]:hover,
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="stHorizontalBlock"]:hover {
        background: var(--nav-hover) !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="stHorizontalBlock"]:has(button[kind="primary"]),
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="stHorizontalBlock"]:has([data-testid="baseButton-primary"]),
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="stHorizontalBlock"]:has([data-testid="stBaseButton-primary"]),
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="stHorizontalBlock"]:has(button[kind="primary"]),
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="stHorizontalBlock"]:has([data-testid="baseButton-primary"]),
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="stHorizontalBlock"]:has([data-testid="stBaseButton-primary"]) {
        background: var(--nav-accent-soft) !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="stHorizontalBlock"]:has(button[kind="primary"]):hover,
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="stHorizontalBlock"]:has([data-testid="baseButton-primary"]):hover,
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="stHorizontalBlock"]:has([data-testid="stBaseButton-primary"]):hover,
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="stHorizontalBlock"]:has(button[kind="primary"]):hover,
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="stHorizontalBlock"]:has([data-testid="baseButton-primary"]):hover,
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="stHorizontalBlock"]:has([data-testid="stBaseButton-primary"]):hover {
        background: rgba(42, 168, 184, 0.22) !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="column"],
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="column"] {
        overflow: visible !important;
        padding: 0 !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="column"]:first-child,
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="column"]:first-child {
        flex: 1 1 auto !important;
        min-width: 0 !important;
        width: auto !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="column"]:last-child,
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="column"]:last-child {
        flex: 0 0 2.25rem !important;
        min-width: 2.25rem !important;
        width: 2.25rem !important;
        max-width: 2.25rem !important;
        margin-left: auto !important;
        overflow: visible !important;
        display: flex !important;
        justify-content: flex-end !important;
        align-items: center !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] button,
    section[data-testid="stSidebar"] .st-key-nav_chats button {
        padding-top: 0.05rem !important;
        padding-bottom: 0.05rem !important;
        padding-left: 0.3rem !important;
        padding-right: 0.3rem !important;
        min-height: 1.25rem !important;
        height: auto !important;
        line-height: 1.1 !important;
        cursor: pointer !important;
        background: transparent !important;
        background-color: transparent !important;
        color: var(--nav-text) !important;
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] button:focus,
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] button:focus-visible,
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] button:active,
    section[data-testid="stSidebar"] .st-key-nav_chats button:focus,
    section[data-testid="stSidebar"] .st-key-nav_chats button:focus-visible,
    section[data-testid="stSidebar"] .st-key-nav_chats button:active,
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="stTooltipHoverTarget"]:focus,
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="stTooltipHoverTarget"]:focus-visible,
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="stTooltipIcon"]:focus,
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="stTooltipIcon"]:focus-visible,
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="stTooltipHoverTarget"]:focus,
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="stTooltipHoverTarget"]:focus-visible,
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="stTooltipIcon"]:focus,
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="stTooltipIcon"]:focus-visible {
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] button p,
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] button span,
    section[data-testid="stSidebar"] .st-key-nav_chats button p,
    section[data-testid="stSidebar"] .st-key-nav_chats button span {
        color: inherit !important;
        visibility: visible !important;
        opacity: 1 !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] button[kind="primary"],
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] button[data-testid="baseButton-primary"],
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] button[data-testid="stBaseButton-primary"],
    section[data-testid="stSidebar"] .st-key-nav_chats button[kind="primary"],
    section[data-testid="stSidebar"] .st-key-nav_chats button[data-testid="baseButton-primary"],
    section[data-testid="stSidebar"] .st-key-nav_chats button[data-testid="stBaseButton-primary"] {
        color: var(--nav-accent) !important;
        font-weight: 600 !important;
        background: transparent !important;
        background-color: transparent !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] button[kind="primary"]:hover,
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] button[data-testid="baseButton-primary"]:hover,
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] button[data-testid="stBaseButton-primary"]:hover,
    section[data-testid="stSidebar"] .st-key-nav_chats button[kind="primary"]:hover,
    section[data-testid="stSidebar"] .st-key-nav_chats button[data-testid="baseButton-primary"]:hover,
    section[data-testid="stSidebar"] .st-key-nav_chats button[data-testid="stBaseButton-primary"]:hover {
        color: #0a7382 !important;
        background: transparent !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="column"]:last-child button,
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="column"]:last-child button {
        justify-content: center !important;
        width: 2rem !important;
        min-width: 2rem !important;
        max-width: 2rem !important;
        margin-left: auto !important;
        margin-right: 0.1rem !important;
        padding: 0.2rem 0.15rem !important;
        opacity: 0.55;
        color: var(--nav-muted) !important;
        border-radius: 0.35rem !important;
        overflow: visible !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="column"]:last-child button svg,
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="column"]:last-child button svg {
        display: inline-block !important;
        visibility: visible !important;
        width: 1.2rem !important;
        height: 1.2rem !important;
        min-width: 1.2rem !important;
        color: inherit !important;
        fill: currentColor !important;
        overflow: visible !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="column"]:last-child button:hover,
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="column"]:last-child button:hover {
        opacity: 1;
        color: #b42318 !important;
        background: rgba(180, 35, 24, 0.08) !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="column"]:last-child button > div,
    section[data-testid="stSidebar"] [class*="st-key-nav_chats"] [data-testid="column"]:last-child button [data-testid="stMarkdownContainer"],
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="column"]:last-child button > div,
    section[data-testid="stSidebar"] .st-key-nav_chats [data-testid="column"]:last-child button [data-testid="stMarkdownContainer"] {
        width: auto !important;
        justify-content: center !important;
    }
    section[data-testid="stSidebar"] hr {
        display: none !important;
    }

    /* Logo sits tight under the top bar */
    [data-testid="stImage"] {
        margin-bottom: 0.35rem !important;
        background: transparent !important;
    }
    [data-testid="stImage"] img {
        border-radius: 0 !important;
        background: transparent !important;
    }
    [data-testid="stLogo"] img,
    [data-testid="stSidebarLogo"] img,
    [data-testid="stHeader"] img {
        background: transparent !important;
    }
    .chuckai-hero {
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        text-align: center !important;
        width: 100% !important;
        margin: 0.15rem 0 0.5rem 0 !important;
        padding: 0 !important;
        gap: 0.15rem !important;
    }
    .chuckai-hero img {
        display: block !important;
        margin: 0 auto !important;
        background: transparent !important;
        max-width: 400px !important;
        height: auto !important;
    }
    .chuckai-hero h1 {
        margin: 0 !important;
        color: var(--nav-text) !important;
        font-size: 1.85rem !important;
        font-weight: 700 !important;
        font-family: Georgia, "Palatino Linotype", "Book Antiqua", Palatino, serif !important;
        letter-spacing: -0.02em !important;
    }
    .chuckai-hero h1 span {
        color: var(--nav-accent) !important;
        font-family: "Segoe UI", Corbel, Calibri, sans-serif !important;
        font-weight: 700 !important;
    }
    .chuckai-tagline {
        margin: 0 !important;
        padding: 0 !important;
        color: var(--nav-muted) !important;
        font-size: 1.08rem !important;
        font-weight: 500 !important;
        font-family: Georgia, "Palatino Linotype", "Book Antiqua", Palatino, serif !important;
        letter-spacing: 0.01em !important;
        line-height: 1.35 !important;
        font-style: italic !important;
    }

    /* Left-align main chat column (Streamlit centers it by default) */
    .main .block-container,
    [data-testid="stMainBlockContainer"] {
        max-width: 72rem !important;
        margin-left: 0 !important;
        margin-right: auto !important;
        padding-left: 3rem !important;
        padding-right: 1.5rem !important;
    }

    /* Keep the bottom prompt field on the same left edge as messages */
    [data-testid="stBottomBlockContainer"],
    [data-testid="stBottom"] .block-container,
    .stBottomBlockContainer {
        max-width: 72rem !important;
        margin-left: 0 !important;
        margin-right: auto !important;
        padding-left: 3rem !important;
        padding-right: 1.5rem !important;
    }
    [data-testid="stChatInput"],
    [data-testid="stChatInputContainer"] {
        max-width: 100% !important;
        margin-left: 0 !important;
        padding-left: 0 !important;
    }
    /* Chat prompt outline: darker gray instead of Streamlit primary red */
    [data-testid="stChatInput"] {
        border-color: #6a7a82 !important;
        box-shadow: none !important;
        outline: none !important;
        border-radius: 0.85rem !important;
    }
    [data-testid="stChatInput"]:focus,
    [data-testid="stChatInput"]:focus-within {
        border-color: #55656d !important;
        box-shadow: none !important;
        outline: none !important;
    }
    [data-testid="stChatInput"] > div {
        border-color: #55656d !important;
        background: transparent !important;
        background-color: transparent !important;
    }
    /* Fallback height if forest bg CSS did not load */
    [data-testid="stChatInput"] textarea {
        min-height: 5.25rem !important;
    }
    [data-testid="stBottom"],
    [data-testid="stBottomBlockContainer"] {
        background: transparent !important;
        background-color: transparent !important;
    }

    /* Smaller chat avatars */
    [data-testid="stChatMessageAvatarUser"],
    [data-testid="stChatMessageAvatarAssistant"],
    [data-testid="stChatMessageAvatar"] {
        width: 1.25rem !important;
        height: 1.25rem !important;
        min-width: 1.25rem !important;
        min-height: 1.25rem !important;
        flex-shrink: 0 !important;
    }
    [data-testid="stChatMessageAvatarUser"] img,
    [data-testid="stChatMessageAvatarAssistant"] img,
    [data-testid="stChatMessageAvatar"] img {
        width: 1.25rem !important;
        height: 1.25rem !important;
        object-fit: cover !important;
    }

    /* Assistant flush left; user prompts nudged in a bit */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
        margin-left: 0 !important;
        padding-left: 0 !important;
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        margin-left: 1.15rem !important;
        padding-left: 0 !important;
    }

    /* Jump-to-bottom — hidden at bottom; only show when scrolled up (.is-up) */
    #chuckai-scroll-bottom {
        position: fixed !important;
        right: 1.35rem !important;
        bottom: 8.25rem !important;
        z-index: 2147483647 !important;
        width: 2.55rem !important;
        height: 2.55rem !important;
        border: none !important;
        border-radius: 999px !important;
        background: var(--nav-accent, #2aa8b8) !important;
        color: #fff !important;
        font-size: 1rem !important;
        line-height: 1 !important;
        text-decoration: none !important;
        box-shadow: 0 4px 14px rgba(14, 70, 80, 0.28) !important;
        cursor: pointer !important;
        opacity: 0 !important;
        pointer-events: none !important;
        transform: translateY(0.4rem) !important;
        transition: opacity 0.18s ease, transform 0.18s ease, background 0.15s ease !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 0 !important;
        box-sizing: border-box !important;
        visibility: hidden !important;
    }
    #chuckai-scroll-bottom.is-up {
        opacity: 1 !important;
        pointer-events: auto !important;
        transform: translateY(0) !important;
        visibility: visible !important;
    }
    #chuckai-scroll-bottom:hover {
        background: #0a7382 !important;
        color: #fff !important;
        text-decoration: none !important;
    }
    #chuckai-chat-end {
        height: 1px !important;
        width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
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

# Keep full original prompts available for sidebar hover tooltips
for chat in st.session_state.chats:
    full = chat_full_prompt(chat)
    if full:
        chat["title_full"] = full
    if chat.get("title") in ("New Chat", "New chat", "New Story", "New story", "", None) and chat.get("title_full"):
        chat["title"] = _title_from(chat["title_full"])
    ensure_story(chat)

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

# Confirmation dialog for clearing all chats (opened by sidebar button)
if st.session_state.get("confirm_clear"):
    show_clear_history_confirmation()

history_path = str(HISTORY_FILE.resolve())

with st.sidebar:
    if st.button(
        "＋ START NEW STORY",
        key="nav_new_chat",
        use_container_width=True,
    ):
        chat = _new_chat()
        st.session_state.chats.insert(0, chat)
        st.session_state.active_id = chat["id"]
        persist()
        st.rerun()

    st.markdown('<p class="nav-label">Stories</p>', unsafe_allow_html=True)

    try:
        _chat_box = st.container(key="nav_chats")
    except TypeError:
        _chat_box = st.container()
    nav_tips: dict[str, str] = {}
    with _chat_box:
        for chat in list(st.session_state.chats):
            is_active = chat["id"] == st.session_state.active_id
            title = chat["title"] or "New Story"
            full_prompt = chat_full_prompt(chat)
            if full_prompt:
                nav_tips[chat["id"]] = full_prompt
            col_open, col_del = st.columns([6.5, 1.35], gap="small")
            with col_open:
                if st.button(
                    title,
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
                ):
                    delete_chat(chat["id"])
                    st.rerun()
    install_nav_chat_tooltips(nav_tips)

    if st.button(
        "CLEAR STORY HISTORY",
        key="nav_clear_history",
        use_container_width=True,
        help=history_path,
    ):
        st.session_state.confirm_clear = True
        st.rerun()

    st.markdown(
        '<div class="nav-section-gap"></div>'
        '<div class="nav-divider"></div>',
        unsafe_allow_html=True,
    )

    try:
        _model_box = st.container(key="nav_models")
    except TypeError:
        _model_box = st.container()
    with _model_box:
        story_model_label = display_model_name(st.session_state.model)
        image_label = image_model_label(st.session_state.image_model)
        image_style = image_model_style(st.session_state.image_model)
        auto_images = resolve_preferred_auto_generate_images()
        auto_images_label = "On" if auto_images else "Off"
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

active = get_active_chat()
if active:
    ensure_story(active)
messages = active["messages"] if active else []
story_phase = ensure_story(active)["phase"] if active else "premise"

for message in messages:
    render_message(message)

prompt = st.chat_input(story_input_placeholder(story_phase))


def _write_and_illustrate(chat: dict, *, opening: bool) -> None:
    """Write a scene, illustrate it, show it, and persist the assistant message."""
    model = st.session_state.model
    reply = ""
    image = None
    image_rel = None
    draw_prompt = ""
    image_error = None

    try:
        with st.spinner("Writing the scene…"):
            reply = write_story_scene(chat, model, opening=opening)
    except Exception as e:
        fail = (
            f"Could not write the scene: {e}\n\n"
            "Make sure Ollama is running, then try again."
        )
        with st.chat_message("assistant", avatar=chat_avatar("assistant")):
            st.markdown(fail)
        append_assistant_message(chat, fail)
        persist()
        st.rerun()

    if resolve_preferred_auto_generate_images():
        try:
            with st.spinner("Illustrating the scene…"):
                image, image_rel, draw_prompt, image_error = illustrate_scene(
                    chat, reply, model
                )
        except Exception as e:
            image_error = e

    content = with_scene_choice_prompt(reply)
    if image_error is not None:
        content = f"{content}\n\n*(Image generation failed: {image_error})*"

    with st.chat_message("assistant", avatar=chat_avatar("assistant")):
        if image is not None:
            st.image(image, use_container_width=True)
        st.markdown(content)

    append_assistant_message(
        chat,
        content,
        image=image_rel,
        image_prompt=draw_prompt,
    )
    persist()
    st.rerun()


if prompt and active:
    story = ensure_story(active)
    phase = story["phase"]
    active["messages"].append({"role": "user", "content": prompt})

    with st.chat_message("user", avatar=chat_avatar("user")):
        st.markdown(prompt)

    install_scroll_controls(force_bottom=True)

    if phase == "premise":
        story["premise"] = prompt.strip()
        story["phase"] = "appearances"
        sync_chat_title(active, prompt)
        with st.chat_message("assistant", avatar=chat_avatar("assistant")):
            st.markdown(APPEARANCES_ASK)
        append_assistant_message(active, APPEARANCES_ASK)
        persist()
        st.rerun()
    elif phase == "appearances":
        story["appearances"] = prompt.strip()
        story["phase"] = "start"
        with st.chat_message("assistant", avatar=chat_avatar("assistant")):
            st.markdown(START_ASK)
        append_assistant_message(active, START_ASK)
        persist()
        st.rerun()
    elif phase == "start":
        story["start_point"] = prompt.strip()
        story["phase"] = "writing"
        _write_and_illustrate(active, opening=True)
    else:
        # writing — continue / redirect from where we left off
        _write_and_illustrate(active, opening=False)

else:
    # Idle view: keep jump-to-bottom control available
    install_scroll_controls(force_bottom=False)
