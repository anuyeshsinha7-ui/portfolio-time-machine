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
        st.markdown(f"#### VaR and ES: today vs each ticked period (historical, {ctx.conf:.0%}, {ctx.horizon}-day)")
        rows = []
        for eid, reg, ev, prob in results:
            if reg is None:
                continue
            for kk in ("A", "B"):
                d = RC.deviation(ctx.current[kk], reg[kk], k)
                rows.append({"Period": ev["name"], "Window": f"{reg['start']} → {reg['end']}", "P": kk,
                             "VaR today": ctx.h(d["var_now"]), "VaR then": ctx.h(d["var_then"]), "Δ VaR": ctx.h(d["var_change"]),
                             "ES today": ctx.h(d["es_now"]), "ES then": ctx.h(d["es_then"]), "Δ ES": ctx.h(d["es_change"]),
                             "ES ×": round(d["es_mult"], 2), "Vol then": reg[kk]["volatility"], "Max DD then": reg[kk]["max_drawdown"]})
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
        st.markdown("#### Verdict rules and the numbers behind them")
        st.markdown(f"* {RC.RULES['label_holds']}\n* {RC.RULES['b_held_up']}")
        rows = []
        for name, reg, e_ in regs:
            rows.append({"Period": name, "ES A": ctx.h(reg["A"]["risk"]["Historical"][k]["es"]), "ES B": ctx.h(reg["B"]["risk"]["Historical"][k]["es"]),
                         "Vol A": reg["A"]["volatility"], "Vol B": reg["B"]["volatility"], "ES99 Nifty": reg["B"]["nifty"]["es99"],
                         "MDD B": reg["B"]["max_drawdown"], "MDD Nifty": reg["B"]["nifty"]["max_drawdown"],
                         "A stocks still High": f"{reg['A']['stability']['same']}/{reg['A']['stability']['of']}" if reg["A"]["stability"] else "",
                         "B stocks still Low": f"{reg['B']['stability']['same']}/{reg['B']['stability']['of']}" if reg["B"]["stability"] else ""})
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="percent") for c in df.columns[1:8]})
        st.caption("Label stability re-runs the High/Low rule with each period's own data and universe median.")
        board_w = ctx.scoreboard()
        if board_w:
            st.markdown("#### All-events scoreboard")
            tbl = pd.DataFrame([{"Event": r["event"], "Type": r["type"], "Window": f"{r['start']} → {r['end']}", "ES99 A": r["es99_A"],
                                 "ES99 B": r["es99_B"], "Vol A": r["vol_A"], "Vol B": r["vol_B"], "MDD A": r["mdd_A"], "MDD B": r["mdd_B"],
                                 "Label held": "✓" if r["label_held"] else "✗",
                                 "B beat Nifty": ("✓" if r["b_held_up"] else "✗") if r["type"] == "crisis" else "—"} for r in board_w])
            st.dataframe(tbl, hide_index=True, width="stretch",
                         column_config={c: st.column_config.NumberColumn(format="percent") for c in tbl.columns[3:9]})
            ui.show(CH.scoreboard_heatmap(board_w, ctx.amount_a, ctx.amount_b))
        st.markdown("#### How the windows were found")
        for ev in (ctx.crisis_ev, ctx.calm_ev):
            anc = ev.get("anchor") or {}
            w = ev["windows"].get(ctx.mode) or ev["windows"]["standard"]
            if ev["type"] == "crisis" and anc.get("peak"):
                st.markdown(f"**{ev['name']}** — inside the search range the Nifty 50 peaked on **{anc['peak']}** and bottomed on "
                            f"**{anc['trough']}** (−{anc['fall']:.1%}). Standard window = {config.REGIME_DAYS} trading days starting "
                            f"{config.EVENT_PRE_DAYS} days before the peak → {w[0]} → {w[1]}.")
            elif ev["id"] == "auto_calm":
                st.markdown(f"**{ev['name']}** — the {config.REGIME_DAYS}-day window with the lowest Nifty 50 volatility in the whole "
                            f"sample ({anc['calm_vol']:.1%}) that overlaps neither the Current window nor the crisis → {w[0]} → {w[1]}.")
            elif anc.get("calm_start"):
                st.markdown(f"**{ev['name']}** — the calmest {config.CALM_ANCHOR_DAYS}-day stretch in the range ran {anc['calm_start']} → "
                            f"{anc['calm_end']} (Nifty volatility {anc['calm_vol']:.1%}); the standard window is the calmest "
                            f"{config.REGIME_DAYS}-day window centred in the range → {w[0]} → {w[1]}.")
            for n_ in ev.get("notes", []):
                st.caption(n_)
            if ev.get("source"):
                st.caption(f"Source: {ev['source']}")
        if ctx.mode == "event_only":
            st.warning("Event-only windows can be short: 99% VaR from fewer than 250 days rests on only a handful of bad days.")

        st.markdown("#### Regime finder evidence")
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
                df.columns = ["Start", "End", "Return", "Volatility", "Max drawdown", "Worst day", "VaR 99%"]
                st.markdown(f"Top 3 automatic **{kind}** candidates ({'deepest drawdown' if kind == 'crisis' else 'lowest volatility'}, "
                            "non-overlapping, 252 days):")
                st.dataframe(df, hide_index=True, width="stretch",
                             column_config={c: st.column_config.NumberColumn(format="percent") for c in df.columns[2:]})

        st.markdown(f"#### VaR and ES by method ({ctx.conf:.0%}, {ctx.horizon}-day)")
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
            st.caption("10-day figures use √10 scaling, which assumes independent, identically distributed days — in a crisis "
                       "losses cluster, so the true 10-day risk is usually larger.")
        st.latex(r"\text{VaR}_c = -q_{1-c}(r) \qquad \text{ES}_c = -\mathbb{E}[\,r \mid r \le q_{1-c}\,]")

        st.markdown("#### Return distributions in the crisis")
        h1, h2 = st.columns(2)
        for col, key, colr in ((h1, "A", CH.A), (h2, "B", CH.B)):
            r = ctx.crisis[key]
            with col:
                ui.show(CH.returns_hist(r["returns"]["port"], r["risk"]["Historical"][k]["var"], r["risk"]["Historical"][k]["es"],
                                        colr, key, ctx.conf))

        st.markdown("#### Breach test: would yesterday's VaR have warned you?")
        calib = st.radio("Calibrate VaR on", ["Calm window", "Current window"], horizontal=True, key="t1_calib")
        src = ctx.calm if calib.startswith("Calm") else ctx.current
        for key, colr in (("A", CH.A), ("B", CH.B)):
            bt = ST.breach_test(np.array(src[key]["returns"]["port"]), np.array(ctx.crisis[key]["returns"]["port"]), ctx.conf,
                                ctx.crisis[key]["returns"]["dates"])
            ui.show(CH.breach_timeline(ctx.crisis[key]["returns"]["dates"], ctx.crisis[key]["returns"]["port"], bt["var"], colr, key))
            st.markdown(f"Portfolio {key}: expected about **{bt['expected']:.1f}** breaches of the {ctx.conf:.0%} VaR "
                        f"({ui.pct(bt['var'], 2)}), got **{bt['breaches']}**. Kupiec likelihood ratio {bt['lr']:.1f}, "
                        f"p-value {bt['p_value']:.2g} → {'reject' if bt['reject_95'] else 'cannot reject'} that the VaR model is right.")
        st.latex(r"LR_{POF} = -2\ln\!\left[(1-p)^{T-x}p^{x}\right] + 2\ln\!\left[(1-\tfrac{x}{T})^{T-x}(\tfrac{x}{T})^{x}\right] \sim \chi^2_1")

        st.markdown("#### Extra measures, and why they are here")
        rows = []
        for name, reg, ev in regs:
            for key in ("A", "B"):
                r = reg[key]
                rows.append({"Period": name, "P": key, "Volatility": r["volatility"], "Beta": round(r["beta"], 2),
                             "Max drawdown": r["max_drawdown"], "Worst day": r["worst_day"], "Avg correlation": round(r["avg_pairwise_corr"], 2)})
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="percent") for c in ("Volatility", "Max drawdown", "Worst day")})
        st.markdown("* **Volatility** — part of the label rule, so it must be re-checked in each period.\n"
                    "* **Regime beta** — whether A still amplifies the market when it matters.\n"
                    "* **Maximum drawdown** — what a buy-and-hold investor actually lives through, not just one bad day.\n"
                    "* **Worst day** — the single loss that VaR and ES summarise.\n"
                    "* **Average correlation** — diversification fails when stocks start moving together.\n"
                    "* **Breach test (Kupiec)** — tells us whether a VaR fitted in good times would have warned us in bad times.\n"
                    "* **Label stability** — whether the High/Low rule itself still sorts the stocks the same way.")
        ui.concept_box("Value at Risk (VaR)",
                       f"On {ctx.conf:.0%} of days you should lose less than this. On the other {1 - ctx.conf:.0%} of days you lose more — VaR "
                       "doesn't say how much more.",
                       "VaR_c is the loss at the (1−c) quantile of the return distribution. Four ways to estimate it: historical "
                       "(sort the actual days), normal (mean and standard deviation), Monte Carlo with fat-tailed Student-t draws, "
                       "and Cornish–Fisher (adjusts the normal quantile for skew and kurtosis).",
                       "Banks and fund managers set limits with it; it is easy to explain in rupees.",
                       "Every 'bad day' rupee figure in this app.")
        ui.concept_box("Expected Shortfall (ES)",
                       "When a bad day does come, how much do you lose on average? ES answers what VaR leaves out.",
                       "The average loss on the days worse than VaR. Basel's trading-book rules (FRTB) use ES at 97.5%.",
                       "Two portfolios can share a VaR but have very different disasters; ES sees the difference.",
                       "The verdict cards above and the scoreboard (ES 99%).")
        ui.concept_box("Fat tails",
                       "Markets have more extreme days than the bell curve predicts — a −8% day 'should' happen once in centuries but "
                       "happened several times in 2008 and 2020.",
                       f"Excess kurtosis > 0. The fitted Student-t degrees of freedom here: A {ctx.crisis['A']['risk']['t_dof']:.1f}, "
                       f"B {ctx.crisis['B']['risk']['t_dof']:.1f} in the crisis (lower = fatter tails; the normal is ∞).",
                       "The normal method understates crisis risk — compare its column with the historical one above.",
                       "The VaR/ES method table and the return histograms.")
        ui.concept_box("Correlations in a crisis",
                       "In a panic, investors sell everything at once, so stocks that usually move independently fall together.",
                       f"Average pairwise correlation of A: current {ctx.current['A']['avg_pairwise_corr']:.2f} → crisis "
                       f"{ctx.crisis['A']['avg_pairwise_corr']:.2f}; B: {ctx.current['B']['avg_pairwise_corr']:.2f} → "
                       f"{ctx.crisis['B']['avg_pairwise_corr']:.2f}.",
                       "Diversification is weakest exactly when it is needed most.",
                       "The 'Avg correlation' column of the extra-measures table.")
