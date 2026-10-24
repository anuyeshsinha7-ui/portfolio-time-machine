"""Closing screen: thank you, with a short video."""
import sys

import streamlit as st

from src import config
from src import ui

left, right = ui.split()
with left:
    ui.hero("Thank you", "Thank you! 🙏", config.CREDIT_LINE, "")
    if sys.platform == "emscripten":  # in the browser (stlite): play the file published next to the site
        # starts with sound (the visitor just clicked to get here); if the browser still refuses, plays muted with a hint
        st.html("<video id='ptm-thanks' src='../thank-you.mp4' controls playsinline loop "
                "style='width:100%;border-radius:18px;display:block'></video>"
                "<div id='ptm-thanks-note' style='display:none;font-size:13px;opacity:.7;margin-top:6px'>"
                "Tap the video to turn the sound on.</div>"
                "<script>const v = document.getElementById('ptm-thanks'); v.muted = false;"
                "v.play().catch(() => { v.muted = true; v.play();"
                " document.getElementById('ptm-thanks-note').style.display = 'block'; });</script>",
                unsafe_allow_javascript=True)
    else:  # streamlit run app.py (offline backup)
        st.video(str(config.ROOT / "assets" / "thank-you.mp4"), autoplay=True, loop=True)
    ui.section("The team")
    ui.list_rows([("👤", ui.esc(n), r, "", "") for n, r in config.TEAM_ROLLS])
    st.page_link(st.session_state["_pages"]["start"], label="Start again with a new amount", icon="↩️")

if right is not None:
    with right:
        st.markdown("#### Portfolio Time Machine")
        st.markdown(f"Does 'safe' stay safe when the market crashes? {config.CREDIT_LINE}. "
                    f"Live site: {config.LIVE_URL} · Source code: {config.REPO_URL}")
