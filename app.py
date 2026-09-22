"""YourStoriesAI entrypoint — routes Stories, Settings, and About."""

from pathlib import Path

import streamlit as st

from preferences import ensure_prefs_hydrated

ASSETS_DIR = Path(__file__).parent / "assets"
ICON_FILE = ASSETS_DIR / "mascot_book.png"
if not ICON_FILE.exists():
    ICON_FILE = ASSETS_DIR / "mascot_rabbit.png"

st.set_page_config(
    page_title="YourStoriesAI",
    page_icon=str(ICON_FILE) if ICON_FILE.exists() else None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load per-browser settings from localStorage into this session.
ensure_prefs_hydrated()

pages = [
    st.Page("home.py", title="Stories", default=True),
    st.Page("pages/Settings.py", title="Settings"),
    st.Page("pages/About.py", title="About"),
]

pg = st.navigation(pages, position="top")
pg.run()
