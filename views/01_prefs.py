"""Step 2 — Preferences: which sectors and which market caps the client wants to invest in."""
import pandas as pd
import streamlit as st

from src import charts as CH
from src import ui
from src import universe as U

s = st.session_state
left, right = ui.split()
t = ui.universe_table()
sectors = ui.sector_list()
ICON = {"Financial Services": "🏦", "Information Technology": "💻", "Healthcare": "💊", "Fast Moving Consumer Goods": "🛒",
        "Automobile and Auto Components": "🚗", "Capital Goods": "🏗️", "Oil Gas & Consumable Fuels": "🛢️", "Metals & Mining": "⛏️",
        "Power": "⚡", "Consumer Services": "🛍️", "Consumer Durables": "📺", "Chemicals": "🧪", "Realty": "🏠", "Telecommunication": "📡",
        "Construction Materials": "🧱", "Construction": "🚧", "Services": "🧰", "Textiles": "🧵", "Media Entertainment & Publication": "🎬",
        "Diversified": "🧩", "Forest Materials": "🌲"}
CAP_HELP = {"Large cap": "top 100, most established", "Mid cap": "next 150, growing businesses",
            "Small cap": "next 250, smaller and faster-moving"}

with left:
    ui.hero("Your preferences", "Where would you like to invest?", "Tick the sectors you like and choose company size", "")
    ui.section("Sectors", "tick one or more")
    c1, c2 = st.columns(2)
    if c1.button("Select all", width="stretch"):
        for sec in sectors:
            s[f"sec_{sec}"] = True
    if c2.button("Clear", width="stretch"):
        for sec in sectors:
            s[f"sec_{sec}"] = False
    chosen = []
    for sec in sectors:
        key = f"sec_{sec}"
        if key not in s:
            s[key] = sec in s["pref_sectors"]
        n = int((t["industry"] == sec).sum())
        if st.checkbox(f"{ICON.get(sec, '•')} {sec} · {n}", key=key):
            chosen.append(sec)
    ui.section("Company size", "tick one or more")
    if st.button("All sizes (Flexi cap)", width="stretch"):
        for c_ in U.CAPS:
            s[f"cap_{c_}"] = True
    caps = []
    for c_ in U.CAPS:
        key = f"cap_{c_}"
        if key not in s:
            s[key] = c_ in s["pref_caps"]
        n_c = int((t["cap_bucket"] == c_).sum())
        if st.checkbox(f"{c_} — {CAP_HELP[c_]} · {n_c}", key=key):
            caps.append(c_)
    cap = U.cap_label(caps) if caps else ""
    pool = t[t["industry"].isin(chosen) & t["cap_bucket"].isin(caps)]
    hi, lo = int((pool["label"] == "High risk").sum()), int((pool["label"] == "Low risk").sum())
    if not chosen or not caps:
        ui.note("Tick at least one sector and one company size.", "☝️", "warn")
    else:
        ui.tiles([("Companies in your choice", f"{len(pool)}", f"{len(chosen)} sectors · {cap.lower()}", ""),
                  ("Bold · Steady candidates", f"{hi} · {lo}", "need 10 of each", "")])
        if hi < 10 or lo < 10:
            ui.note("Your choice is narrow, so we'll widen it a little to reach 10 stocks in each portfolio — "
                    "you'll see exactly how on the next screen.", "ℹ️", "warn")
    if st.button("Suggest my portfolios →", type="primary", width="stretch", disabled=not (chosen and caps)):
        res = U.pick_by_filters(t, chosen, caps)
        s["pref_sectors"], s["pref_caps"], s["pref_cap"] = chosen, caps, cap
        s["pick_A"], s["pick_B"] = res["A"], res["B"]
        s["pick_notes"] = {"A": res["notes_A"], "B": res["notes_B"]}
        for k in ("board_custom", "boot_custom"):
            s.pop(k, None)
        st.switch_page(s["_pages"]["suggest"])

if right is not None:
    with right:
        st.markdown("#### The universe: Nifty 500, by sector and size")
        st.markdown("Sizes follow NSE's own index families: **Large** = Nifty 100, **Mid** = Nifty Midcap 150, **Small** = Nifty "
                    "Smallcap 250. Tick any combination; all three together is **Flexi cap**.")
        tab = pd.crosstab(t["industry"], t["cap_bucket"]).reindex(columns=U.CAPS, fill_value=0)
        tab["Total"] = tab.sum(axis=1)
        st.dataframe(tab.sort_values("Total", ascending=False), width="stretch")
        st.markdown("#### Risk labels inside your current choice")
        if chosen:
            lab = pd.crosstab(pool["industry"], pool["label"]).reindex(columns=["High risk", "Moderate", "Low risk"], fill_value=0)
            st.dataframe(lab, width="stretch")
            ui.show(CH.beta_vol_scatter(pool, float(t["vol_median"].iloc[0]), [], []))
        st.markdown("#### How the suggestion works")
        st.markdown("1. Keep only your sectors and company sizes.\n"
                    "2. **Bold** = the 10 *High risk* stocks (beta ≥ 1 and volatility ≥ the universe median) with the highest composite "
                    "score; **Steady** = the 10 *Low risk* stocks with the lowest score. Score = average of the beta and volatility "
                    "percentiles.\n3. At most 3 per sector; stocks with price history back to 2007 first, so every crisis can be tested.\n"
                    "4. If your choice is too narrow, relax step by step — more than 3 per sector → closest *Moderate* stocks → other "
                    "sizes in your sectors → other sectors — and say so on screen.")
        ui.flowchart("pick")
