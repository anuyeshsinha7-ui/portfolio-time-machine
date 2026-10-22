"""Step 7 — Verdict: does the label hold in the periods you tested, are the weights robust, which portfolio fits you."""
import numpy as np
import pandas as pd
import streamlit as st

from src import charts as CH
from src import config
from src import recommend as RC
from src import ui

ctx = ui.context()
s = st.session_state
left, right = ui.split()
# the verdict is judged on the periods the client ticked on the Backtest screen
ticked = []
for eid in s["bt_events"]:
    reg, ev, prob = ui.regime_for(ctx, eid)
    if reg is not None:
        ticked.append((eid, reg, ev))
board = [{"event": ev["name"], "type": ev["type"], "label_held": RC.label_holds(r["A"], r["B"]), "b_held_up": RC.b_held_up(r["B"]),
          "es_A": r["A"]["risk"]["Historical"][config.RULE_KEY]["es"], "es_B": r["B"]["risk"]["Historical"][config.RULE_KEY]["es"],
          "vol_A": r["A"]["volatility"], "vol_B": r["B"]["volatility"], "mdd_A": r["A"]["max_drawdown"], "mdd_B": r["B"]["max_drawdown"],
          "fall_A": r["A"]["replay"]["largest_fall"], "fall_B": r["B"]["replay"]["largest_fall"],
          "nifty_fall": r["nifty"]["largest_fall"], "start": r["start"], "end": r["end"]} for eid, r, ev in ticked] or None
boot = ctx.bootstrap()
lv = RC.label_verdict(ctx.crisis, ctx.calm, board or [])
bv = RC.b_verdict(ctx.crisis, board or [])
TONE = {"Yes": "ok", "Partly": "mid", "No": "bad", "Robust": "ok", "Partly robust": "mid", "Regime-dependent": "bad"}
trig = RC.review_trigger(list(np.diff(np.log(ctx.crisis["nifty"]["value"]))))
mret = ui.nifty_close().pct_change().dropna()
now_vol = float(mret.iloc[-63:].std() * np.sqrt(252))

with left:
    ui.hero("Your answer", "Does 'safe' stay safe?",
            f"Judged on the {len(board) if board else 0} period{'s' if board and len(board) != 1 else ''} you ticked on the Backtest screen", "")
    ui.portfolio_badge()
    rows = [("🚀", "Is A really the bold one?",
             f"Riskier in the chosen crash: {'yes' if lv['crisis'] else 'no'} · calm year: {'yes' if lv['calm'] else 'no'}"
             + (f" · ticked periods: {lv['events_held']}/{lv['events_total']}" if board else ""), ui.chip(lv["verdict"], TONE[lv["verdict"]]), ""),
            ("🛡️", "Did steady stay safe?",
             f"Beat the market in the chosen crash: {'yes' if bv['crisis'] else 'no'}"
             + (f" · in {bv['crises_held']} of {bv['crises_total']} crashes" if board else ""), ui.chip(bv["verdict"], TONE[bv["verdict"]]), "")]
    if boot:
        for key in ("A", "B", "C"):
            rb = RC.robustness(ctx.crisis[key]["test2"]["turnover"], ctx.calm[key]["test2"]["turnover"], boot[key]["turnover_p95"])
            rows.append(("🔁", f"Are {key}'s weights robust?", "Would the optimiser really rebuild it in other times?",
                         ui.chip(rb["verdict"], TONE[rb["verdict"]]), ""))
    ui.list_rows(rows)
    ui.section("Which portfolio fits you?")
    opts = sorted({round(ctx.amount_a * f / 1000) * 1000 for f in [x / 100 for x in range(5, 81, 5)]})
    if s.get("tolerance") not in opts:
        s["tolerance"] = min(opts, key=lambda o: abs(o - 0.25 * ctx.amount_a))
    tol = st.select_slider("The biggest fall I could live with", options=opts, key="tolerance", format_func=ui.inr_short)
    f = RC.fit(tol, {kk: ctx.crisis[kk]["replay"]["largest_fall"] for kk in ("A", "B", "C")},
               {kk: ctx.amount(kk) for kk in ("A", "B", "C")}, {kk: ctx.P[kk]["expected_return"] for kk in ("A", "B", "C")})
    ui.list_rows([(ui.PLAN[kk][2], f"Portfolio {ui.NAMES[kk]}", f"worst fall in the {ui.short(ctx.crisis_ev)}",
                   f"{ui.inr_short(f['worst'][kk])} lost", ui.chip("fits", "ok") if kk in f["fits"] else ui.chip("too big", "bad"))
                  for kk in ("A", "B", "C")])
    st.caption(f"Your limit: a fall of {ui.inr_short(tol)}")
    if f["pick"]:
        others = [x for x in f["fits"] if x != f["pick"]]
        ui.verdict(ui.PLAN[f["pick"]][2], f"Portfolio {ui.NAMES[f['pick']]} fits you",
                   f"Its worst fall in the crash stayed within your {ui.inr_short(tol)}, and of the portfolios that did"
                   f"{' (' + ', '.join(others) + ' too)' if others else ''} it expects the highest return: "
                   f"{ui.pct(ctx.P[f['pick']]['expected_return'])} a year.")
    else:
        ui.verdict("✋", "None fits at this amount", f"To keep a crash like this within {ui.inr_short(tol)}, put at most "
                   f"<b>{ui.inr_short(f['max_amount_safest'])}</b> in Portfolio {ui.NAMES[f['safest']]}, the one that fell least.")
    ui.section("When to check again")
    ui.note(f"Review your weights if the market's 3-month ups-and-downs rise above <b>{ui.pct(trig)}</b> (the calmest it got during the "
            f"crash). Today: <b>{ui.pct(now_vol)}</b> — {'time to review.' if now_vol > trig else 'all clear.'}",
            "🔔", "warn" if now_vol > trig else "good")
    ui.section("Good to know")
    ui.list_rows([("🕰️", "History isn't a promise", "Past crashes may not look like the next one.", "", ""),
                  ("🏆", "Today's winners only", "Companies that failed since 2007 aren't in the test, which flatters history.", "", ""),
                  ("💸", "Before costs and tax", "Brokerage, STT and capital-gains tax are not included.", "", ""),
                  ("🎓", "Educational project", "Not investment advice.", "", "")])

if right is not None:
    with right:
        st.markdown("#### The rules behind each answer")
        for name, rule in RC.RULES.items():
            st.markdown(f"* **{name.replace('_', ' ').capitalize()}.** {rule}")
        st.markdown("#### The numbers the rules used")
        st.markdown("ES 95% is the average loss on the days that lost more than the 95% VaR (the worst 5% of days). Biggest fall "
                    "is the largest drop from a high point.")
        rows = []
        for nm, reg, ev in ctx.regimes():
            rows.append({"Period": nm, "ES 95% A": reg["A"]["risk"]["Historical"][config.RULE_KEY]["es"],
                         "ES 95% B": reg["B"]["risk"]["Historical"][config.RULE_KEY]["es"], "Volatility A": reg["A"]["volatility"],
                         "Volatility B": reg["B"]["volatility"], "ES 95% Nifty": reg["B"]["nifty"]["es"],
                         "Biggest fall B": reg["B"]["max_drawdown"], "Biggest fall Nifty": reg["B"]["nifty"]["max_drawdown"],
                         "Label held": RC.label_holds(reg["A"], reg["B"]), "B beat Nifty": RC.b_held_up(reg["B"])})
        df = pd.DataFrame(rows)
        st.dataframe(ui.pct_df(df, df.columns[1:8]), hide_index=True, width="stretch")
        st.markdown("#### What this analysis can't tell you")
        for t_, d_ in RC.LIMITATIONS:
            st.markdown(f"* **{t_}.** {d_}")
        if board:
            ui.show(CH.scoreboard_heatmap(board, ctx.amount_a, ctx.amount_b))
        st.markdown("#### How we pick a portfolio for you")
        st.markdown("1. For each portfolio, take its biggest fall in the chosen crisis (bought on day one and held) × your amount.\n"
                    "2. Keep the portfolios whose fall stays within your limit.\n"
                    "3. Of those, suggest the one with the highest expected return.\n"
                    "4. If none fits, say how much could go into the one that fell least.")
        st.dataframe(ui.pct_df(pd.DataFrame([{"Portfolio": ui.NAMES[kk], "Worst fall": ctx.crisis[kk]["replay"]["largest_fall"],
                                    "Worst fall ₹": ui.inr(f["worst"][kk]), "Within limit": kk in f["fits"],
                                    "Expected return": ctx.P[kk]["expected_return"]} for kk in ("A", "B", "C")]), ("Worst fall", "Expected return")),
                     hide_index=True, width="stretch")
