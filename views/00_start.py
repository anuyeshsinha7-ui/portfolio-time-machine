"""Screen 0 — Start: the amount comes first (brief §7). Onboarding screen of the customer app."""
import pandas as pd
import streamlit as st

from src import allocation as AL
from src import config
from src import data as D
from src import ui

s = st.session_state
left, right = ui.split()

with left:
    st.html("<div class='app-onb'><div class='logo'>⏳</div><div class='h'>How much would you like to invest?</div>"
            "<div class='p'>We'll show every gain, loss and risk in rupees on this amount.</div></div>")
    if s.get("amount_from_link"):
        ui.note(f"We picked up <b>{ui.inr(s['amount_from_link'])}</b> from your link. Change it if you like.", "🔗")
    if "start_amt" not in s:
        base = s["amount_total"] if s["amount_mode"] == "split_total" else s["amount_a"]
        s["start_amt"] = ui.inr(base)
    chips = st.pills("Quick amounts", config.AMOUNT_PRESETS, format_func=ui.inr_short, key="start_chip", label_visibility="collapsed")
    if chips is not None and s.get("_last_chip") != chips:
        s["_last_chip"] = chips
        s["start_amt"] = ui.inr(chips)
    modes = {"same_each": "Same in both", "split_total": "Split one total", "separate": "Different amounts"}
    mode = st.segmented_control("How to invest it", list(modes), format_func=modes.get, key="start_mode",
                                default=s["amount_mode"], required=True)
    label = {"same_each": "Amount in each portfolio", "split_total": "Total — half goes to each",
             "separate": "Amount in Portfolio A"}[mode]
    txt = st.text_input(label, key="start_amt", placeholder="e.g. 15 lakh", help="Type 15,00,000 or 15 lakh or 1.5 crore.")
    txt_b = None
    if mode == "separate":
        if "start_amt_b" not in s:
            s["start_amt_b"] = ui.inr(s["amount_b"])
        txt_b = st.text_input("Amount in Portfolio B", key="start_amt_b")
    errors, val_a, val_b = [], None, None
    for which, raw in (("", txt), ("Portfolio B: ", txt_b)):
        if raw is None:
            continue
        try:
            v = ui.parse_amount(raw)
            m = ui.validate_amount(v, config.AMOUNT_MIN, config.AMOUNT_MAX)
            if m:
                errors.append(which + m)
            if which:
                val_b = v
            else:
                val_a = v
        except ui.AmountError as e:
            errors.append(which + str(e))
    for e in errors:
        st.error(e)
    if not errors and val_a:
        a_amt, b_amt = AL.split_amounts(mode, val_a, val_b)
        ui.tiles([("Portfolio A · Bold", ui.inr_short(a_amt), "aims for higher returns", "a"),
                  ("Portfolio B · Steady", ui.inr_short(b_amt), "plays it safe", "b")])
    if st.button("Continue →", type="primary", disabled=bool(errors), width="stretch"):
        s["amount_mode"] = mode
        if mode == "split_total":
            s["amount_total"] = val_a
            s["amount_a"] = s["amount_b"] = val_a / 2
        else:
            s["amount_a"] = val_a
            s["amount_b"] = val_b if mode == "separate" else val_a
            s["amount_total"] = s["amount_a"] + s["amount_b"]
        s["amount_confirmed"] = True
        st.switch_page(s["_pages"]["prefs"])
    st.caption("Educational project — not investment advice.")

if right is not None:
    with right:
        res = ui.default_results()
        prices = D.latest_prices()
        st.markdown("#### Why the amount comes first")
        st.markdown("Every risk number starts life as a **percentage** of what you invest; rupees are that percentage × your amount:")
        st.latex(r"\text{₹ at risk} = \text{loss (\%)} \times \text{amount}")
        st.markdown("Doubling the money doubles the rupee risk; the percentages do not change, so changing the amount never re-runs "
                    "the analysis. The **only non-linear step** is buying whole shares, so small amounts drift from the target "
                    "weights and leave some cash.")
        st.markdown("#### Smallest sensible amount for the current picks")
        rows = []
        for k in ("A", "B"):
            w = pd.Series(res["portfolios"][k]["weights"] if ui.is_default_picks() else ui.context().P[k]["weights"])
            m = AL.min_sensible_amount(w, prices)
            worst = (prices.reindex(w.index) / w).idxmax()
            rows.append((f"Portfolio {k}", ui.inr(m), worst, ui.inr(prices[worst], 2), ui.pct(w[worst])))
        st.dataframe(pd.DataFrame(rows, columns=["Portfolio", "Minimum sensible amount", "Set by", "Share price", "Target weight"]),
                     hide_index=True, width="stretch")
        st.caption("Minimum sensible amount = max over stocks of (latest price ÷ target weight), rounded up to the next ₹1,000. "
                   "Below it at least one stock can't be bought; the app warns but carries on.")
        st.markdown("#### Amount modes")
        st.markdown("* **Same in both** (default, matches the assignment: ₹15 lakh in each)\n"
                    "* **Split one total** — half in A, half in B\n* **Different amounts** — set each separately")
        st.markdown("#### The pipeline")
        ui.flowchart("start")
