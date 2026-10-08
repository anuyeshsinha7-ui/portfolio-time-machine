"""Page 0 — Start: the amount comes first (brief §7)."""
import pandas as pd
import streamlit as st

from src import allocation as AL
from src import config
from src import data as D
from src import ui

s = st.session_state
ui.page_header("start", "How much would you like to invest?",
               "Every rupee figure in this app — gains, losses, risk — is worked out on the amount you choose here.")
left, right = ui.split()

with left:
    if s.get("amount_from_link"):
        st.info(f"We picked up {ui.inr(s['amount_from_link'])} from the link you followed. Change it if you like.")
    mode = st.radio("How should we split it?", list(config.AMOUNT_MODES), format_func=config.AMOUNT_MODES.get,
                    key="start_mode", index=list(config.AMOUNT_MODES).index(s["amount_mode"]))
    st.caption("The assignment puts ₹15 lakh in each portfolio, so the same amount in each is the default.")
    base = s["amount_total"] if mode == "split_total" else s["amount_a"]
    if "start_amt" not in s:
        s["start_amt"] = ui.inr(base)
    st.write("**Pick a quick amount**")
    chips = st.pills("Quick amounts", config.AMOUNT_PRESETS, format_func=ui.inr_short, key="start_chip",
                     label_visibility="collapsed")
    if chips is not None and s.get("_last_chip") != chips:
        s["_last_chip"] = chips
        s["start_amt"] = ui.inr(chips)
    label = {"same_each": "Amount in each portfolio", "split_total": "Total amount (half goes to each)",
             "separate": "Amount in Portfolio A"}[mode]
    txt = st.text_input(label, key="start_amt", help="Type 15,00,000 or 15 lakh or 1.5 crore.")
    txt_b = None
    if mode == "separate":
        if "start_amt_b" not in s:
            s["start_amt_b"] = ui.inr(s["amount_b"])
        txt_b = st.text_input("Amount in Portfolio B", key="start_amt_b")
    errors, val_a, val_b = [], None, None
    try:
        val_a = ui.parse_amount(txt)
        m = ui.validate_amount(val_a, config.AMOUNT_MIN, config.AMOUNT_MAX)
        if m:
            errors.append(m)
    except ui.AmountError as e:
        errors.append(str(e))
    if txt_b is not None:
        try:
            val_b = ui.parse_amount(txt_b)
            m = ui.validate_amount(val_b, config.AMOUNT_MIN, config.AMOUNT_MAX)
            if m:
                errors.append("Portfolio B: " + m)
        except ui.AmountError as e:
            errors.append("Portfolio B: " + str(e))
    for e in errors:
        st.error(e)
    if not errors and val_a:
        if mode == "split_total":
            st.success(f"{ui.inr(val_a)} in total → {ui.inr(val_a / 2)} in Portfolio A and {ui.inr(val_a / 2)} in Portfolio B.")
        elif mode == "separate":
            st.success(f"{ui.inr(val_a)} in Portfolio A and {ui.inr(val_b)} in Portfolio B.")
        else:
            st.success(f"{ui.inr(val_a)} in Portfolio A and the same {ui.inr(val_a)} in Portfolio B.")
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
        st.switch_page(s["_pages"]["home"])

if right is not None:
    with right:
        res = ui.default_results()
        prices = D.latest_prices()
        st.markdown("#### Why the amount matters")
        st.markdown(
            "Risk numbers in this app start life as **percentages** of what you invest. To turn them into rupees we multiply by your "
            "amount, so the rupee figures scale in a straight line:")
        st.latex(r"\text{₹ at risk} = \text{loss (\%)} \times \text{amount}")
        st.markdown(
            "Doubling the money doubles the rupee risk; the percentages do not change. The **only non-linear step** is buying "
            "whole shares — you cannot buy 0.3 of a share — so small amounts drift from the target weights and leave some cash.")
        st.markdown("#### Smallest sensible amount for the current picks")
        rows = []
        for k in ("A", "B"):
            w = pd.Series(res["portfolios"][k]["weights"] if ui.is_default_picks() else ui.context().P[k]["weights"])
            m = AL.min_sensible_amount(w, prices)
            worst = (prices.reindex(w.index) / w).idxmax()
            rows.append(f"* **Portfolio {k}: {ui.inr(m)}** — set by **{worst}** "
                        f"(price {ui.inr(prices[worst], 2)} ÷ weight {ui.pct(w[worst])}). Below this, at least one stock can't be bought.")
        st.markdown("\n".join(rows))
        st.caption("Minimum sensible amount = max over stocks of (latest price ÷ target weight), rounded up to the next ₹1,000.")
        ui.flowchart("start")
