"""Step 3 — Suggested portfolios: the Bold and Steady stocks picked by beta and standard deviation."""
import pandas as pd
import streamlit as st

from src import charts as CH
from src import classify as CL
from src import config
from src import data as D
from src import ui

s = st.session_state
left, right = ui.split()
t = ui.universe_table()
med = float(t["vol_median"].iloc[0])
CAPC = {"Large cap": "L", "Mid cap": "M", "Small cap": "S"}

with left:
    ui.hero("Suggested for you", "2 portfolios · 20 companies",
            f"{len(s['pref_sectors'])} sector{'s' if len(s['pref_sectors']) != 1 else ''} · {s['pref_cap'].lower()} · picked by beta and "
            "standard deviation", "")
    for k in ("A", "B"):
        nm, tg, ic, tone, risk = ui.PLAN[k]
        syms = s[f"pick_{k}"]
        sub = t.loc[[x for x in syms if x in t.index]]
        ui.section(f"{ic} {nm} · {tg.split(' · ')[0]}", f"{len(syms)} stocks")
        ui.list_rows([(CAPC.get(r["cap_bucket"], "•"), ui.esc(r["company"]),
                       f"{ui.esc(r['industry'])} · moves {r['beta']:.1f}× market · swings {r['volatility']:.0%}/yr",
                       ui.chip(r["label"].replace(" risk", ""), "a" if r["label"] == "High risk" else ("b" if r["label"] == "Low risk" else "mid")),
                       f"score {r['risk_score']:.0f}") for x, r in sub.iterrows()])
        for n_ in s["pick_notes"].get(k, []):
            ui.note(f"To reach 10 stocks we {n_}.", "ℹ️", "warn")
    ui.note("<b>Why these?</b> Bold stocks move strongly with the market (beta ≥ 1) and swing a lot (above-median standard "
            "deviation). Steady stocks do the opposite.", "💡")
    c1, c2 = st.columns(2)
    with c1:
        st.page_link(s["_pages"]["prefs"], label="Change preferences", icon="↩️")
    with c2:
        st.page_link(s["_pages"]["pick"], label="Edit stocks by hand", icon="✏️")
    ui.next_button("See today's weights and risk", "today")

if right is not None:
    with right:
        st.markdown("#### The rule, in numbers")
        st.latex(r"\beta_i = \frac{\operatorname{Cov}(r_i, r_m)}{\operatorname{Var}(r_m)} \qquad "
                 r"\sigma_i = \operatorname{sd}(r_i)\times\sqrt{252}")
        st.markdown(CL.rule_text(med) + f" Measured on the last {config.CLASSIFICATION_YEARS} years of daily returns against the Nifty 50.")
        rows = []
        for k in ("A", "B"):
            for x in s[f"pick_{k}"]:
                if x in t.index:
                    r = t.loc[x]
                    rows.append({"Portfolio": k, "Symbol": x, "Sector": r["industry"], "Cap": r["cap_bucket"], "Beta": round(r["beta"], 2),
                                 "Volatility": r["volatility"], "Label": r["label"], "Score": round(r["risk_score"], 1),
                                 "History from": r["first_date"], "Beta (full)": round(r["beta_full"], 2), "Label (full)": r["label_full"]})
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, width="stretch", column_config={"Volatility": st.column_config.NumberColumn(format="percent")})
        ui.show(CH.beta_vol_scatter(t, med, s["pick_A"], s["pick_B"]))
        st.caption("Dashed lines: beta = 1 and the universe median volatility. Bold picks sit top-right, Steady picks bottom-left.")
        sym = st.selectbox("Worked example for", s["pick_A"] + s["pick_B"], key="sugg_example")
        cal = D.calendar()
        R = D.window(D.returns(), cal[-config.CLASSIFICATION_YEARS * 252], cal[-1])
        m = D.window(D.market_returns(), cal[-config.CLASSIFICATION_YEARS * 252], cal[-1])
        both = pd.concat([R[sym], m], axis=1).dropna()
        cov, var_m, sd = both.cov().iloc[0, 1], both.iloc[:, 1].var(), both.iloc[:, 0].std()
        st.latex(rf"\beta = \frac{{{cov:.3e}}}{{{var_m:.3e}}} = {cov / var_m:.2f} \qquad "
                 rf"\sigma = {sd:.4f}\times\sqrt{{252}} = {sd * 252 ** 0.5 * 100:.1f}\%")
        ui.concept_box("Beta and standard deviation",
                       "Beta says how much a stock rides the market's waves; standard deviation says how bumpy its own ride is.",
                       "β = Cov(r, r_Nifty) ÷ Var(r_Nifty); σ = daily standard deviation × √252.",
                       "High on both means bigger gains in good times and bigger losses in bad ones.",
                       "The scatter above and every stock row on the phone.")
