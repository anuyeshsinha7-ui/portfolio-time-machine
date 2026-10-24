"""Closing screen: thank you, with a short video."""
import sys

import streamlit as st

from src import config
from src import ui

left, right = ui.split()
with left:
    ui.hero("Thank you", "Thank you! 🙏", config.CREDIT_LINE, "")
    if sys.platform == "emscripten":  # in the browser (stlite): play the file published next to the site
        st.html("<video src='../thank-you.mp4' controls autoplay muted playsinline loop "
                "style='width:100%;border-radius:18px;display:block'></video>")
    else:  # streamlit run app.py (offline backup)
        st.video(str(config.ROOT / "assets" / "thank-you.mp4"), autoplay=True, muted=True, loop=True)
    st.caption("Tap the video to turn the sound on.")
    ui.section("The team")
    ui.list_rows([("👤", ui.esc(n), r, "", "") for n, r in config.TEAM_ROLLS])
    st.page_link(st.session_state["_pages"]["start"], label="Start again with a new amount", icon="↩️")

if right is not None:
    with right:
        st.markdown("#### Portfolio Time Machine")
        st.markdown(f"Does 'safe' stay safe when the market crashes? {config.CREDIT_LINE}. "
                    f"Live site: {config.LIVE_URL} · Source code: {config.REPO_URL}")
