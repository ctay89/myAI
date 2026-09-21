"""About — YourStoriesAI."""

import streamlit as st

from header_nav import (
    apply_forest_background,
    render_brand_sidebar,
    render_branded_page_title,
)

render_brand_sidebar(
    message=(
        "This is the About section, where you can learn more about "
        "YourStoriesAI, and what it's all about."
    )
)
apply_forest_background(include_chat_input=False)

render_branded_page_title("About", "Want to know more about YourStoriesAI?")

st.markdown(
    """
Do you remember Choose Your Own Adventure books? Well, I do. They were so
exciting, and being part of the story made you feel like you had some skin in
the game. Well, with AI, you can be a much bigger part of the story.

Start wherever you want — characters, setting, basic story — and let AI fill in
the blanks. Then it will ask you for input to carry the story forward.
<u>What do you do?</u> You are involved!

So join in on the action, drama, comedy, or whatever you're looking for,
because the story is yours. Have as much fun with it as you want.

And it's all using uncensored AI, so the only boundaries are your imagination.

So dive in, and have fun!
""",
    unsafe_allow_html=True,
)
