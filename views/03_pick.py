"""Optional — Choose my own stocks: Industry → Stock → Risk label (brief §8.3, §6.2, §6.3). The recommendation is the main path."""
import pandas as pd
import streamlit as st

from src import charts as CH
from src import classify as CL
from src import config
from src import data as D
from src import ui
from src import universe as U

s = st.session_state
t = ui.universe_table()
med = float(t["vol_median"].iloc[0])
left, right = ui.split()
evs = ui.default_results()["events"]
TAG = {"High risk": ("🔴", "a"), "Low risk": ("🔵", "b"), "Moderate": ("🟡", "mid")}


def coverage_text(sym: str) -> str:
    fd = pd.Timestamp(t.loc[sym, "first_date"])
    n_ok = sum(1 for e in evs.values() if e["available"] and not e["id"].startswith("auto")
               and e["windows"]["standard"] and pd.Timestamp(e["windows"]["standard"][0]) >= fd)
    n_all = sum(1 for e in evs.values() if e["available"] and not e["id"].startswith("auto"))
    return "all events" if n_ok == n_all else f"{n_ok} of {n_all} events (data from {fd.year})"


def add(sym: str, to: str) -> None:
    other = "B" if to == "A" else "A"
    if sym in s[f"pick_{other}"]:
        st.session_state["pick_msg"] = f"{sym} is already in Portfolio {other} — a stock can't be in both."
        return
    if sym not in s[f"pick_{to}"]:
        if len(s[f"pick_{to}"]) >= config.MAX_STOCKS:
            st.session_state["pick_msg"] = f"Portfolio {to} already holds {config.MAX_STOCKS} stocks (the maximum)."
            return
        s[f"pick_{to}"] = s[f"pick_{to}"] + [sym]


with left:
    ui.hero("Choose my own stocks", f"A: {len(s['pick_A'])} · B: {len(s['pick_B'])} stocks",
            "Optional — start from the recommendation and swap companies in or out", "")
    if ui.is_recommended():
        ui.note("These are your <b>recommended portfolios</b>. Any change you make here is used on every screen until you "
                "go back to the recommendation.", "✨")
    else:
        ui.note("You're using <b>your own picks</b> on every screen.", "✏️", "warn")
    inds = sorted(t["industry"].unique())
    ind = st.selectbox("Industry", inds, index=inds.index("Fast Moving Consumer Goods") if "Fast Moving Consumer Goods" in inds else 0)
    sub = t[t["industry"] == ind].sort_values("risk_score", ascending=False)
    ui.list_rows([(TAG[r["label"]][0], ui.esc(r["company"]),
                   f"Moves {r['beta']:.1f}× the market · swings {r['volatility']:.0%} a year · {coverage_text(x)}",
                   ui.chip(r["label"], TAG[r["label"]][1]),
                   "in A" if x in s["pick_A"] else ("in B" if x in s["pick_B"] else "")) for x, r in sub.head(8).iterrows()])
    if len(sub) > 8:
        st.caption(f"Showing the 8 riskiest of {len(sub)} — all are in the list below.")
    sym = st.selectbox("Company", list(sub.index), format_func=lambda x: f"{t.loc[x, 'company']} ({t.loc[x, 'label']})")
    c1, c2 = st.columns(2)
    if c1.button("＋ Add to A (bold)", width="stretch"):
        add(sym, "A")
        st.rerun()
    if c2.button("＋ Add to B (steady)", width="stretch"):
        add(sym, "B")
        st.rerun()
    if s.get("pick_msg"):
        st.warning(s.pop("pick_msg"))
    ui.section("Your portfolios", "tap × to remove")
    allsyms = list(t.index)
    # widgets get their own keys; the picks live in non-widget state so they survive leaving this page
    for kk in ("A", "B"):
        s[f"ms_{kk}"] = list(s[f"pick_{kk}"])
    st.multiselect("Portfolio A · Bold", allsyms, key="ms_A", format_func=lambda x: t.loc[x, "company"],
                   on_change=lambda: s.update(pick_A=list(s["ms_A"])))
    st.multiselect("Portfolio B · Steady", allsyms, key="ms_B", format_func=lambda x: t.loc[x, "company"],
                   on_change=lambda: s.update(pick_B=list(s["ms_B"])))
    msgs = U.validate(s["pick_A"], s["pick_B"], t)
    for m in msgs:
        ui.note(m["text"], "⛔" if m["level"] == "error" else "⚠️", "bad" if m["level"] == "error" else "warn")
    if not msgs:
        ui.note(f"Both portfolios are ready: {config.MIN_STOCKS}–{config.MAX_STOCKS} stocks each, no overlap, labels match.", "✅", "good")
    if not ui.is_recommended() and st.button("↺ Back to the recommendation", key="reset_page", width="stretch"):
        ui.use_recommendation()
        st.rerun()
    if not any(m["level"] == "error" for m in msgs):
        ui.next_button("See today's weights and risk", "today")

if right is not None:
    with right:
        st.markdown(f"#### {ind}: every stock, three-year numbers")
        show = pd.DataFrame({"Company": sub["company"], "Beta": sub["beta"].round(2), "Volatility": sub["volatility"],
                             "Label": sub["label"], "Score": sub["risk_score"].round(0), "Cap": sub["cap_bucket"],
                             "Events covered": [coverage_text(x) for x in sub.index]})
        st.dataframe(show, width="stretch", column_config={"Volatility": st.column_config.NumberColumn(format="percent")})
        r = t.loc[sym]
        st.markdown(f"#### The rule, worked for {sym}")
        st.latex(r"\beta_i = \frac{\operatorname{Cov}(r_i, r_m)}{\operatorname{Var}(r_m)} \qquad "
                 r"\sigma_i = \operatorname{sd}(r_i)\times\sqrt{252}")
        cal = D.calendar()
        R = D.window(D.returns(), cal[-config.CLASSIFICATION_YEARS * 252], cal[-1])
        m = D.window(D.market_returns(), cal[-config.CLASSIFICATION_YEARS * 252], cal[-1])
        both = pd.concat([R[sym], m], axis=1).dropna()
        cov = both.cov().iloc[0, 1]
        var_m = both.iloc[:, 1].var()
        sd = both.iloc[:, 0].std()
        st.markdown(f"Using {len(both)} daily returns from {both.index[0].date()} to {both.index[-1].date()}:")
        st.latex(rf"\beta_{{\text{{{sym}}}}} = \frac{{{cov:.3e}}}{{{var_m:.3e}}} = {cov / var_m:.2f} \qquad "
                 rf"\sigma = {sd:.4f}\times\sqrt{{252}} = {sd * 252 ** 0.5:.1%}".replace("%", r"\%"))
        verdict = CL.label(r["beta"], r["volatility"], med)
        st.markdown(f"β {'≥' if r['beta'] >= 1 else '<'} 1.0 and σ {'≥' if r['volatility'] >= med else '<'} median ({ui.pct(med)}) → "
                    f"**{verdict}** (composite risk score {r['risk_score']:.0f}/100).")
        st.caption(CL.rule_text(med))
        ui.show(CH.beta_vol_scatter(t, med, s["pick_A"], s["pick_B"], highlight=sym))
        st.markdown("#### Robustness: 3 years vs full history")
        rob = t.loc[[x for x in s["pick_A"] + s["pick_B"] if x in t.index], ["beta", "beta_full", "volatility", "vol_full", "label", "label_full"]]
        rob.columns = ["Beta 3y", "Beta full", "Vol 3y", "Vol full", "Label 3y", "Label full"]
        st.dataframe(rob, width="stretch", column_config={"Beta 3y": st.column_config.NumberColumn(format="%.2f"),
                     "Beta full": st.column_config.NumberColumn(format="%.2f"),
                     "Vol 3y": st.column_config.NumberColumn(format="percent"), "Vol full": st.column_config.NumberColumn(format="percent")})
        same = (rob["Label 3y"] == rob["Label full"]).sum()
        st.caption(f"{same} of {len(rob)} picks keep the same label on their full history (since 2007 or listing).")
        ui.concept_box("Beta", "If the whole market rises 1%, a stock with beta 1.5 tends to rise about 1.5% — and falls 1.5% when the "
                       "market falls 1%. It measures how strongly a stock rides the market's waves.",
                       "The slope of the stock's daily returns on the Nifty 50's daily returns: covariance ÷ market variance.",
                       "High-beta stocks amplify market crashes; low-beta stocks cushion them.",
                       "The vertical axis of the scatter above, the label rule, and weighted beta on The risk call.")
        ui.concept_box("Volatility", "How bumpy the ride is. A stock with 40% volatility typically ends a year 40% above or below its "
                       "average — a 20% stock half as far.",
                       "Standard deviation of daily returns × √252 (trading days in a year).",
                       "Bigger swings mean bigger possible losses over any horizon, even if the stock doesn't follow the market.",
                       "The horizontal axis of the scatter, the label rule, and every portfolio volatility in the app.")
