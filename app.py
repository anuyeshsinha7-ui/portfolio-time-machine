"""Portfolio Time Machine — entry point (runs with `streamlit run app.py` and in the browser via stlite).

Navigation, the shared sidebar, session state and the amount-first gate.
"""
import streamlit as st

from src import config
from src import data as D
from src import ui

st.set_page_config(page_title=config.APP_NAME, page_icon="⏳", layout="wide", initial_sidebar_state="collapsed")
ui.init_state()
ui.inject_css()

_confirmed = st.session_state["amount_confirmed"]
PAGES = {
    "start": st.Page("views/00_start.py", title="Start — your amount", icon="💰", url_path="start", default=not _confirmed),
    "home": st.Page("views/01_home.py", title="Home — the 30-second verdict", icon="⏳", url_path="home", default=_confirmed),
    "how": st.Page("views/02_how.py", title="How this app works", icon="🧭", url_path="how"),
    "pick": st.Page("views/03_pick.py", title="Pick stocks", icon="🧺", url_path="pick"),
    "call": st.Page("views/04_call.py", title="The risk call", icon="⚖️", url_path="call"),
    "weights": st.Page("views/05_weights.py", title="Optimum weights today", icon="🎯", url_path="weights"),
    "test1": st.Page("views/06_test1.py", title="Test #1 — the risk label", icon="🌪️", url_path="test1"),
    "test2": st.Page("views/07_test2.py", title="Test #2 — the allocation", icon="🔁", url_path="test2"),
    "verdict": st.Page("views/08_verdict.py", title="Verdict & recommendation", icon="✅", url_path="verdict"),
    "method": st.Page("views/09_methodology.py", title="Methodology & data", icon="📚", url_path="methodology"),
}
st.session_state["_pages"] = PAGES

nav = st.navigation({"Start": [PAGES["start"], PAGES["home"], PAGES["how"]],
                     "Build": [PAGES["pick"], PAGES["call"], PAGES["weights"]],
                     "Time-travel tests": [PAGES["test1"], PAGES["test2"]],
                     "Decide": [PAGES["verdict"], PAGES["method"]]}, position="hidden")


# ---------------------------------------------------------------- sidebar
def _amount_changed(key: str, target: str) -> None:
    try:
        v = ui.parse_amount(st.session_state[key])
        msg = ui.validate_amount(v, config.AMOUNT_MIN, config.AMOUNT_MAX)
        if msg:
            st.session_state["amount_error"] = msg
            return
        st.session_state[target] = v
        if target == "amount_a" and st.session_state["amount_mode"] == "same_each":
            st.session_state["amount_b"] = v
        st.session_state.pop("amount_error", None)
    except ui.AmountError as e:
        st.session_state["amount_error"] = str(e)


def controls(where: str) -> None:
    """Every setting. Rendered in the sidebar on wide screens and in the ⚙️ settings sheet on phones."""
    s = st.session_state
    for kind in ("crisis", "calm"):  # an event the picks can't cover falls back to the official pick (before the widget exists)
        prob = ui.coverage_problem(s[f"{kind}_id"], s["pick_A"] + s["pick_B"], s["window_mode"])
        if prob:
            s[f"{kind}_unavailable"] = prob
            s[f"{kind}_id"] = ui.fallback_event(kind, s["pick_A"] + s["pick_B"], s["window_mode"])
    if s["amount_confirmed"]:
        mode = s["amount_mode"]
        if mode == "split_total":
            s["sb_total"] = ui.inr(s["amount_total"])
            st.text_input("Total amount (split equally)", key="sb_total", on_change=_amount_changed, args=("sb_total", "amount_total"))
        else:
            s["sb_a"] = ui.inr(s["amount_a"])
            st.text_input("Amount in Portfolio A" if mode == "separate" else "Amount in each portfolio", key="sb_a",
                          on_change=_amount_changed, args=("sb_a", "amount_a"))
            if mode == "separate":
                s["sb_b"] = ui.inr(s["amount_b"])
                st.text_input("Amount in Portfolio B", key="sb_b", on_change=_amount_changed, args=("sb_b", "amount_b"))
        if s.get("amount_error"):
            st.error(s["amount_error"])
        st.selectbox("Amount mode", list(config.AMOUNT_MODES), format_func=config.AMOUNT_MODES.get, key="amount_mode")
    labels = {e: ui.event_label_for(e, s["pick_A"] + s["pick_B"], s["window_mode"])
              for e in ui.event_options("crisis") + ui.event_options("calm")}
    st.selectbox("Which past **crisis** should we test against?", ui.event_options("crisis"), format_func=labels.get, key="crisis_id")
    if s["crisis_id"] == "custom":
        c = st.date_input("Crisis date range (at least 126 trading days)", value=s.get("custom_crisis", ()),
                          min_value=D.calendar()[0].date(), max_value=D.calendar()[-1].date(), key=f"cc_{where}")
        if isinstance(c, (list, tuple)) and len(c) == 2:
            s["custom_crisis"] = (str(c[0]), str(c[1]))
    st.selectbox("Which past **calm** period?", ui.event_options("calm"), format_func=labels.get, key="calm_id")
    if s["calm_id"] == "custom":
        m = st.date_input("Calm date range (at least 126 trading days)", value=s.get("custom_calm", ()),
                          min_value=D.calendar()[0].date(), max_value=D.calendar()[-1].date(), key=f"cm_{where}")
        if isinstance(m, (list, tuple)) and len(m) == 2:
            s["custom_calm"] = (str(m[0]), str(m[1]))
    for kind in ("crisis", "calm"):
        if s.get(f"{kind}_unavailable"):
            st.warning(f"That {kind} event can't be tested with your picks ({s.pop(f'{kind}_unavailable')}); switched to the nearest event they all cover.")
    st.segmented_control("Window", ["standard", "event_only"], key="window_mode",
                         format_func={"standard": "Standard (252 days)", "event_only": "Event only"}.get, required=True)
    st.segmented_control("Confidence level", [0.95, 0.99], key="conf", format_func=lambda c: f"{c:.0%}", required=True)
    st.segmented_control("Horizon", [1, 10], key="horizon", format_func=lambda h: f"{h} day" + ("s" if h > 1 else ""), required=True)
    st.toggle("Show the Backing", key="show_backing", help="Off = the client view only")
    st.toggle("📱 Full-screen app", key="phone", help="On: the app fills the screen, as on a real phone. Off: virtual phone + the working.")
    if st.button("Reset to team picks", width="stretch", key=f"reset_{where}"):
        ui.reset_team_picks()
        st.rerun()
    st.caption(f"Data as of **{D.as_of()}** · {ui.health_badge()}")


if not st.session_state["amount_confirmed"] and nav.title != PAGES["start"].title:
    st.switch_page(PAGES["start"])
ui.setup_frames(PAGES, nav.title, lambda: controls("sheet"))
nav.run()
ui.footer()
