"""Step 5 — Backtest: tick uncertain (and calm) periods; see how VaR and ES change versus today."""
import numpy as np
import pandas as pd
import streamlit as st

from src import charts as CH
from src import config
from src import data as D
from src import recommend as RC
from src import stats_tests as ST
from src import ui
from src import var_es as V

s = st.session_state
left, right = ui.split()
opts = ui.backtest_options()
evs_all = ui.default_results()["events"]
with left:
    ui.hero("Backtest", "What if a crisis hit?", "Tick the periods to test — same portfolios, same amount", "crisis")
    ui.portfolio_badge()
    ui.section("Uncertain times", "tick one or more")
    ticked = []
    for kind in ("crisis", "calm"):
        if kind == "calm":
            ui.section("Calm times", "for comparison")
        for eid in opts[kind]:
            key = f"bt_{eid}"
            if key not in s:
                s[key] = eid in s["bt_events"]
            ev = evs_all[eid]
            if st.checkbox(ui.compact_label(eid, s["pick_A"] + s["pick_B"], s["window_mode"]), key=key):
                ticked.append(eid)
    s["bt_events"] = ticked
    crises = [e for e in ticked if evs_all[e]["type"] == "crisis"]
    calms = [e for e in ticked if evs_all[e]["type"] == "calm"]
    if crises and s["crisis_id"] not in crises:
        s["crisis_id"] = crises[0]
    if calms and s["calm_id"] not in calms:
        s["calm_id"] = calms[0]
ctx = ui.context()
k = ctx.ck()
odds = round(1 / (1 - ctx.conf))
results = []
for eid in ticked:
    reg, ev, prob = ui.regime_for(ctx, eid)
    results.append((eid, reg, ev, prob))
regs = ctx.regimes()

with left:
    if not ticked:
        ui.note("Tick at least one period above.", "☝️", "warn")
    ui.section("How your risk changes", f"bad day = 1 in {odds} · {ctx.horizon}-day")
    for eid, reg, ev, prob in results:
        if reg is None:
            ui.note(f"<b>{ui.short(ev)}</b> can't be tested: {prob}.", "⛔", "warn")
            continue
        rows = []
        for kk in ("A", "B"):
            d = RC.deviation(ctx.current[kk], reg[kk], k)
            am = ctx.amount(kk)
            rows.append((ui.PLAN[kk][2], f"Portfolio {kk} · {ui.PLAN[kk][1].split(' · ')[0]}",
                         f"Bad day {ui.inr_short(ctx.h(d['var_now']) * am)} → <b>{ui.inr_short(ctx.h(d['var_then']) * am)}</b> · "
                         f"worst days {ui.inr_short(ctx.h(d['es_now']) * am)} → <b>{ui.inr_short(ctx.h(d['es_then']) * am)}</b>",
                         f"{d['es_mult']:.1f}×", "ES vs today"))
        held = RC.label_holds(reg["A"], reg["B"])
        icon = "🌪️" if ev["type"] == "crisis" else "🌤️"
        st.html(f"<div class='app-sec'><span class='t'>{icon} {ui.esc(ui.short(ev))}</span><span class='x'>"
                f"{ui.chip('A stayed riskier ✓', 'ok') if held else ui.chip('labels flipped', 'bad')}</span></div>")
        ui.list_rows(rows)
        if ev["type"] == "crisis":
            ui.note(f"Buy-and-hold low: A {ui.inr_short(reg['A']['replay']['low'] * ctx.amount_a)} · B "
                    f"{ui.inr_short(reg['B']['replay']['low'] * ctx.amount_b)} (Nifty fell {reg['nifty']['largest_fall']:.0%})", "📉")
    ok = [(eid, reg, ev) for eid, reg, ev, prob in results if reg is not None]
    if ok:
        lbl = ["Today"] + [ui.short(ev)[:18] for _, _, ev in ok]
        a_vals = [ctx.h(ctx.current["A"]["risk"]["Historical"][k]["es"]) * ctx.amount_a] + \
                 [ctx.h(r["A"]["risk"]["Historical"][k]["es"]) * ctx.amount_a for _, r, _ in ok]
        b_vals = [ctx.h(ctx.current["B"]["risk"]["Historical"][k]["es"]) * ctx.amount_b] + \
                 [ctx.h(r["B"]["risk"]["Historical"][k]["es"]) * ctx.amount_b for _, r, _ in ok]
        ui.section("Worst-days loss, side by side")
        ui.show(CH.risk_compare(lbl, a_vals, b_vals, None, rupees=True))
        if crises:
            cr = ctx.crisis
            ui.section(f"Your money through {ui.short(ctx.crisis_ev)}", "bought on day one")
            if len(crises) > 1:
                s["bt_focus"] = s["crisis_id"]
                st.selectbox("Show the replay for", crises, key="bt_focus", format_func=lambda e: ui.short(evs_all[e]),
                             on_change=lambda: s.update(crisis_id=s["bt_focus"]))
            ui.show(CH.replay(cr["nifty"]["dates"], cr["A"]["replay"]["value"], cr["B"]["replay"]["value"], cr["nifty"]["value"],
                              ctx.amount_a, ctx.amount_b))
    ui.next_button("How should the weights change?", "test2")

if right is not None:
    with right:
        st.markdown(f"#### VaR and ES today vs in each period you ticked (historical, {ctx.conf:.0%}, {ctx.horizon}-day)")
        st.markdown("We keep today's weights and replay them on the daily returns of each period. The change (Δ) is the "
                    "period's number minus today's. 'ES ×' is how many times bigger ES was then.")
        rows = []
        for eid, reg, ev, prob in results:
            if reg is None:
                continue
            for kk in ("A", "B"):
                d = RC.deviation(ctx.current[kk], reg[kk], k)
                rows.append({"Period": ev["name"], "Window": f"{reg['start']} → {reg['end']}", "P": kk,
                             "VaR today": ctx.h(d["var_now"]), "VaR then": ctx.h(d["var_then"]), "Δ VaR": ctx.h(d["var_change"]),
                             "ES today": ctx.h(d["es_now"]), "ES then": ctx.h(d["es_then"]), "Δ ES": ctx.h(d["es_change"]),
                             "ES ×": round(d["es_mult"], 2), "Volatility then": reg[kk]["volatility"], "Biggest fall then": reg[kk]["max_drawdown"]})
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, hide_index=True, width="stretch", column_config={
                c: st.column_config.NumberColumn(format="percent") for c in df.columns if c not in ("Period", "Window", "P", "ES ×")})
            st.latex(r"\Delta\text{VaR} = \text{VaR}_{\text{period}} - \text{VaR}_{\text{today}}, \quad "
                     r"\text{same weights } w_{\text{today}}, \ \text{returns of that period}")
            ui.show(CH.risk_compare(["Today"] + [ev["name"].split(" (")[0][:18] for _, r, ev, p_ in results if r is not None],
                                    [ctx.h(ctx.current["A"]["risk"]["Historical"][k]["var"])] +
                                    [ctx.h(r["A"]["risk"]["Historical"][k]["var"]) for _, r, ev, p_ in results if r is not None],
                                    [ctx.h(ctx.current["B"]["risk"]["Historical"][k]["var"])] +
                                    [ctx.h(r["B"]["risk"]["Historical"][k]["var"]) for _, r, ev, p_ in results if r is not None],
                                    f"VaR {ctx.conf:.0%} (% of the portfolio)"))
        st.markdown("#### The rules for the verdict, and the numbers they use")
        st.markdown(f"* {RC.RULES['label_holds']}\n* {RC.RULES['b_held_up']}")
        rows = []
        for name, reg, e_ in regs:
            rows.append({"Period": name, "ES A": ctx.h(reg["A"]["risk"]["Historical"][k]["es"]), "ES B": ctx.h(reg["B"]["risk"]["Historical"][k]["es"]),
                         "Volatility A": reg["A"]["volatility"], "Volatility B": reg["B"]["volatility"], "Nifty ES 99%": reg["B"]["nifty"]["es99"],
                         "Biggest fall B": reg["B"]["max_drawdown"], "Biggest fall Nifty": reg["B"]["nifty"]["max_drawdown"],
                         "A stocks still High": f"{reg['A']['stability']['same']}/{reg['A']['stability']['of']}" if reg["A"]["stability"] else "",
                         "B stocks still Low": f"{reg['B']['stability']['same']}/{reg['B']['stability']['of']}" if reg["B"]["stability"] else ""})
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="percent") for c in df.columns[1:8]})
        st.caption("'Still High' and 'still Low' re-run the High/Low rule using each period's own prices and its own middle volatility.")
        board_w = ctx.scoreboard()
        if board_w:
            st.markdown("#### Every period in the list, side by side")
            tbl = pd.DataFrame([{"Event": r["event"], "Type": r["type"], "Window": f"{r['start']} → {r['end']}", "ES99 A": r["es99_A"],
                                 "ES99 B": r["es99_B"], "Volatility A": r["vol_A"], "Volatility B": r["vol_B"], "Biggest fall A": r["mdd_A"],
                                 "Biggest fall B": r["mdd_B"],
                                 "Label held": "✓" if r["label_held"] else "✗",
                                 "B beat Nifty": ("✓" if r["b_held_up"] else "✗") if r["type"] == "crisis" else "—"} for r in board_w])
            st.dataframe(tbl, hide_index=True, width="stretch",
                         column_config={c: st.column_config.NumberColumn(format="percent") for c in tbl.columns[3:9]})
            ui.show(CH.scoreboard_heatmap(board_w, ctx.amount_a, ctx.amount_b))
        st.markdown("#### How we chose the dates for each period")
        for ev in (ctx.crisis_ev, ctx.calm_ev):
            anc = ev.get("anchor") or {}
            w = ev["windows"].get(ctx.mode) or ev["windows"]["standard"]
            if ev["type"] == "crisis" and anc.get("peak"):
                st.markdown(f"**{ev['name']}**: in this range the Nifty 50 hit its high on **{anc['peak']}** and its low on "
                            f"**{anc['trough']}**, a fall of {anc['fall']:.1%}. The period is {config.REGIME_DAYS} trading days, starting "
                            f"{config.EVENT_PRE_DAYS} days before the high: {w[0]} to {w[1]}.")
            elif ev["id"] == "auto_calm":
                st.markdown(f"**{ev['name']}**: the {config.REGIME_DAYS}-day stretch with the lowest Nifty 50 volatility in all our data "
                            f"({anc['calm_vol']:.1%}) that doesn't overlap today's period or the crisis: {w[0]} to {w[1]}.")
            elif anc.get("calm_start"):
                st.markdown(f"**{ev['name']}**: the calmest {config.CALM_ANCHOR_DAYS}-day stretch in this range ran from {anc['calm_start']} "
                            f"to {anc['calm_end']} (Nifty volatility {anc['calm_vol']:.1%}). We use the calmest "
                            f"{config.REGIME_DAYS}-day period centred in the range: {w[0]} to {w[1]}.")
            for n_ in ev.get("notes", []):
                st.caption(n_)
            if ev.get("source"):
                st.caption(f"Source: {ev['source']}")
        if ctx.mode == "event_only":
            st.warning("Event-only periods can be short. A 99% VaR from fewer than 250 days rests on only a few bad days.")

        st.markdown("#### Finding crises and calm periods in the data")
        close = ui.nifty_close()
        bench = D.benchmark()
        evs = [dict(e, short=e["name"].split(" (")[0][:22]) for e in ctx.events.values() if e["available"] and not e["id"].startswith("auto")]
        vix = bench["INDIAVIX"].dropna() if "INDIAVIX" in bench else None
        ui.show(CH.nifty_history(close, evs, vix, current=(ctx.current["start"], ctx.current["end"])))
        rf = ctx.res["regime_finder"]
        for kind in ("crisis", "calm"):
            df = pd.DataFrame(rf[f"{kind}_candidates"])
            if len(df):
                df = df[["start", "end", "return", "volatility", "max_drawdown", "worst_day", "var99"]]
                df.columns = ["Start", "End", "Return", "Volatility", "Biggest fall", "Worst day", "VaR 99%"]
                st.markdown(f"The top 3 **{kind}** periods the app found by itself "
                            f"({'biggest fall' if kind == 'crisis' else 'lowest volatility'}, 252 days each, no overlaps):")
                st.dataframe(df, hide_index=True, width="stretch",
                             column_config={c: st.column_config.NumberColumn(format="percent") for c in df.columns[2:]})

        st.markdown(f"#### VaR and ES by method ({ctx.conf:.0%}, {ctx.horizon}-day)")
        st.markdown("Historical uses the real days. Normal assumes a bell curve. Monte Carlo draws random days from a curve with "
                    "more extreme days (Student-t). Cornish–Fisher adjusts the bell curve for lopsided and extreme days.")
        rows = []
        for name, reg, ev in regs:
            for key in ("A", "B"):
                r = reg[key]["risk"]
                row = {"Period": name, "Portfolio": key}
                for m in V.METHODS:
                    row[f"VaR · {m}"] = ctx.h(r[m][k]["var"])
                    row[f"ES · {m}"] = ctx.h(r[m][k]["es"])
                row["ES 97.5% (Basel)"] = ctx.h(r["Historical"]["0.975"]["es"])
                rows.append(row)
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="percent") for c in df.columns[2:]})
        if ctx.horizon == 10:
            st.caption("10-day figures are the 1-day figures × √10. That assumes each day is independent of the last. In a crisis, "
                       "bad days come in bunches, so the real 10-day risk is usually bigger.")
        st.latex(r"\text{VaR}_c = -q_{1-c}(r) \qquad \text{ES}_c = -\mathbb{E}[\,r \mid r \le q_{1-c}\,]")

        st.markdown("#### How daily returns were spread out in the crisis")
        h1, h2 = st.columns(2)
        for col, key, colr in ((h1, "A", CH.A), (h2, "B", CH.B)):
            r = ctx.crisis[key]
            with col:
                ui.show(CH.returns_hist(r["returns"]["port"], r["risk"]["Historical"][k]["var"], r["risk"]["Historical"][k]["es"],
                                        colr, key, ctx.conf))

        st.markdown("#### Would a VaR set in good times have warned you?")
        st.markdown("We set VaR using a calm or recent period, then count how often the crisis losses went past it.")
        calib = st.radio("Set VaR using", ["Calm window", "Current window"], horizontal=True, key="t1_calib")
        src = ctx.calm if calib.startswith("Calm") else ctx.current
        for key, colr in (("A", CH.A), ("B", CH.B)):
            bt = ST.breach_test(np.array(src[key]["returns"]["port"]), np.array(ctx.crisis[key]["returns"]["port"]), ctx.conf,
                                ctx.crisis[key]["returns"]["dates"])
            ui.show(CH.breach_timeline(ctx.crisis[key]["returns"]["dates"], ctx.crisis[key]["returns"]["port"], bt["var"], colr, key))
            st.markdown(f"Portfolio {key}: we expected about **{bt['expected']:.1f}** days worse than the {ctx.conf:.0%} VaR "
                        f"({ui.pct(bt['var'], 2)}) and got **{bt['breaches']}**. Kupiec test: likelihood ratio {bt['lr']:.1f}, "
                        f"p-value {bt['p_value']:.2g}, so "
                        f"{'the VaR was clearly too low for the crisis' if bt['reject_95'] else 'we cannot say the VaR was wrong'}.")
        st.latex(r"LR_{POF} = -2\ln\!\left[(1-p)^{T-x}p^{x}\right] + 2\ln\!\left[(1-\tfrac{x}{T})^{T-x}(\tfrac{x}{T})^{x}\right] \sim \chi^2_1")

        st.markdown("#### Other measures, and why we show them")
        rows = []
        for name, reg, ev in regs:
            for key in ("A", "B"):
                r = reg[key]
                rows.append({"Period": name, "P": key, "Volatility": r["volatility"], "Beta": round(r["beta"], 2),
                             "Biggest fall": r["max_drawdown"], "Worst day": r["worst_day"], "Avg correlation": round(r["avg_pairwise_corr"], 2)})
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="percent") for c in ("Volatility", "Biggest fall", "Worst day")})
        st.markdown("* **Volatility**: it is part of the label rule, so we check it again in each period.\n"
                    "* **Beta in the period**: does A still move more than the market when it matters?\n"
                    "* **Biggest fall**: what you would actually live through if you bought and held, not just one bad day.\n"
                    "* **Worst day**: the single biggest daily loss.\n"
                    "* **Average correlation**: spreading money across stocks stops helping when they all move together.\n"
                    "* **Kupiec test**: would a VaR set in good times have warned you in bad times?\n"
                    "* **Still High / still Low**: does the High/Low rule still sort the stocks the same way?")
        ui.concept_box("Value at Risk (VaR)",
                       f"On {ctx.conf:.0%} of days you should lose less than this. On the other {1 - ctx.conf:.0%} of days you lose more, "
                       "and VaR doesn't say how much more.",
                       "VaR_c is the loss at the (1−c) point of the spread of returns. We estimate it four ways: historical "
                       "(sort the real days), normal (average and standard deviation), Monte Carlo with Student-t draws (more "
                       "extreme days), and Cornish–Fisher (adjusts the normal for lopsided and extreme days).",
                       "Banks and fund managers use it to set limits, and it is easy to explain in rupees.",
                       "Every 'bad day' rupee figure in this app.")
        ui.concept_box("Expected Shortfall (ES)",
                       "When a really bad day comes, how much do you lose on average? ES answers the question VaR leaves open.",
                       "The average loss on the days worse than VaR. The Basel rules for banks (FRTB) use ES at 97.5%.",
                       "Two portfolios can have the same VaR but very different worst days. ES shows the difference.",
                       "The verdict cards above and the scoreboard (ES 99%).")
        ui.concept_box("Fat tails",
                       "Markets have more extreme days than a bell curve says they should. By the bell curve, a −8% day should "
                       "happen once in centuries, but it happened several times in 2008 and 2020.",
                       f"Excess kurtosis above 0. The Student-t degrees of freedom we fitted for the crisis: A "
                       f"{ctx.crisis['A']['risk']['t_dof']:.1f}, B {ctx.crisis['B']['risk']['t_dof']:.1f} (lower means more extreme "
                       "days; a bell curve would be ∞).",
                       "The normal method makes crisis risk look smaller than it was. Compare its column with the historical one above.",
                       "The VaR/ES method table and the return histograms.")
        ui.concept_box("Correlations in a crisis",
                       "In a panic, investors sell everything at once, so stocks that usually move on their own all fall together.",
                       f"Average correlation between pairs of stocks in A: today {ctx.current['A']['avg_pairwise_corr']:.2f} → crisis "
                       f"{ctx.crisis['A']['avg_pairwise_corr']:.2f}; B: {ctx.current['B']['avg_pairwise_corr']:.2f} → "
                       f"{ctx.crisis['B']['avg_pairwise_corr']:.2f}.",
                       "Spreading your money across stocks helps least at the very moment you need it most.",
                       "The 'Avg correlation' column of the extra-measures table.")
