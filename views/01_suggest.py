"""Step 3 — Recommended for you: the top Bold and Steady stocks by beta and standard deviation; hand-picking is optional."""
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
CAPC = {"Large cap": "Large", "Mid cap": "Mid", "Small cap": "Small"}

with left:
    nA, nB = len(s["rec_A"]), len(s["rec_B"])
    nsec = len(s["pref_sectors"])
    ui.hero("Recommended for you", f"Top {nA} Bold · Top {nB} Steady",
            f"{nsec} sector{'s' if nsec != 1 else ''} · {s['pref_cap'].lower()} · ranked by beta and standard deviation", "")
    a_amt, b_amt = ui.amounts()
    ui.tiles([("Portfolio A · Bold", ui.inr_short(a_amt), f"{nA} high-risk stocks", "a"),
              ("Portfolio B · Steady", ui.inr_short(b_amt), f"{nB} low-risk stocks", "b")])
    if not ui.is_recommended():
        ui.note("You're currently using <b>your own picks</b>. The rest of the app switches back to this recommendation when "
                "you tap the button below.", "✏️", "warn")
    for k in ("A", "B"):
        nm, tg, ic, tone, risk = ui.PLAN[k]
        syms = s[f"rec_{k}"]
        sub = t.loc[[x for x in syms if x in t.index]]
        ui.section(f"{ic} {nm} · top {len(syms)}", "riskiest first" if k == "A" else "steadiest first")
        ui.list_rows([(f"{i}", ui.esc(r["company"]),
                       f"{ui.esc(r['industry'])} · moves {r['beta']:.1f}× market · swings {r['volatility']:.0%}/yr",
                       ui.chip(r["label"].replace(" risk", ""), "a" if r["label"] == "High risk" else ("b" if r["label"] == "Low risk" else "mid")),
                       CAPC.get(r["cap_bucket"], "")) for i, (x, r) in enumerate(sub.iterrows(), 1)])
        for n_ in s["pick_notes"].get(k, []):
            ui.note(f"To reach {len(syms)} stocks we {n_}.", "ℹ️", "warn")
    ui.note("<b>Why these?</b> Bold stocks move strongly with the market (beta ≥ 1) and swing a lot (above-median standard "
            "deviation); we take the highest-scoring ones. Steady stocks do the opposite; we take the lowest-scoring ones.", "💡")
    if st.button("Use these — see today's weights and risk →", type="primary", width="stretch", key="use_rec"):
        ui.use_recommendation()
        st.switch_page(s["_pages"]["today"])
    ui.section("Prefer to decide yourself?", "optional")
    c1, c2 = st.columns(2)
    with c1:
        st.page_link(s["_pages"]["prefs"], label="Change sectors or sizes", icon="↩️")
    with c2:
        st.page_link(s["_pages"]["pick"], label="Choose my own stocks", icon="✏️")

if right is not None:
    with right:
        st.markdown("#### The rule, in numbers")
        st.latex(r"\beta_i = \frac{\operatorname{Cov}(r_i, r_m)}{\operatorname{Var}(r_m)} \qquad "
                 r"\sigma_i = \operatorname{sd}(r_i)\times\sqrt{252}")
        st.markdown(CL.rule_text(med) + f" Measured on the last {config.CLASSIFICATION_YEARS} years of daily returns against the Nifty 50.")
        rows = []
        for k in ("A", "B"):
            for rank, x in enumerate(s[f"rec_{k}"], 1):
                if x in t.index:
                    r = t.loc[x]
                    rows.append({"Portfolio": k, "Rank": rank, "Symbol": x, "Sector": r["industry"], "Cap": r["cap_bucket"], "Beta": round(r["beta"], 2),
                                 "Volatility": r["volatility"], "Label": r["label"], "Score": round(r["risk_score"], 1),
                                 "History from": r["first_date"], "Beta (full)": round(r["beta_full"], 2), "Label (full)": r["label_full"]})
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, width="stretch", column_config={"Volatility": st.column_config.NumberColumn(format="percent")})
        ui.show(CH.beta_vol_scatter(t, med, s["rec_A"], s["rec_B"]))
        st.caption("Dashed lines: beta = 1 and the universe median volatility. Bold picks sit top-right, Steady picks bottom-left. "
                   "Rank = order of the composite score (average of the beta and volatility percentiles) within your choice; stocks "
                   "with history back to 2007 are ranked first so every crisis can be tested.")
        sym = st.selectbox("Worked example for", s["rec_A"] + s["rec_B"], key="sugg_example")
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
