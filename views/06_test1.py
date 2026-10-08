"""Page 6 — Time-travel test #1: does the risk label hold? (brief §8.6, §6.4, §6.7, §6.8)."""
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

left, right = ui.split()
with left:
    ui.hero("Time machine", "Travel back to a crash", "Same portfolios, same amount — see what would have happened", "crisis")
ui.event_selectors("t1")
ctx = ui.context()
k = ctx.ck()
regs = ctx.regimes()
odds = round(1 / (1 - ctx.conf))

with left:
    cr = ctx.crisis
    ev = ctx.crisis_ev
    w = ev["windows"].get(ctx.mode) or ev["windows"]["standard"]
    ui.note(f"<b>{ui.short(ev)}</b> · {w[0]} → {w[1]}<br>{ev['story']}", "🌪️", "bad")
    ui.section("Your money through the crash", "bought on day one")
    ui.show(CH.replay(cr["nifty"]["dates"], cr["A"]["replay"]["value"], cr["B"]["replay"]["value"], cr["nifty"]["value"],
                      ctx.amount_a, ctx.amount_b))
    ui.tiles([("A fell as low as", ui.inr_short(cr["A"]["replay"]["low"] * ctx.amount_a),
               f"−{ui.inr_short(cr['A']['replay']['largest_fall'] * ctx.amount_a)} at worst", "a"),
              ("B fell as low as", ui.inr_short(cr["B"]["replay"]["low"] * ctx.amount_b),
               f"−{ui.inr_short(cr['B']['replay']['largest_fall'] * ctx.amount_b)} at worst", "b")])
    ui.section("Did the labels hold?", f"worst {100 // odds if odds < 100 else 1}% of days")
    rows = []
    for name, reg, e_ in regs:
        held = RC.label_holds(reg["A"], reg["B"])
        ea, eb = ctx.h(reg["A"]["risk"]["Historical"][k]["es"]), ctx.h(reg["B"]["risk"]["Historical"][k]["es"])
        icon = {"Current": "📅", "Crisis": "🌪️", "Calm": "🌤️"}[name]
        rows.append((icon, f"{name}{' · ' + ui.short(e_) if e_ else ' · last 12 months'}",
                     f"Average loss on the worst days: A {ui.inr_short(ea * ctx.amount_a)} · B {ui.inr_short(eb * ctx.amount_b)}",
                     ui.chip("held ✓", "ok") if held else ui.chip("did not hold", "bad"), ""))
    ui.list_rows(rows)
    bh = RC.b_held_up(cr["B"])
    ui.note(f"In this crash, Portfolio B {'<b>beat the market</b> — smaller worst-day losses and a smaller fall than the Nifty 50.' if bh else '<b>did not beat the market</b> on both worst-day losses and the biggest fall.'}",
            "🛡️", "good" if bh else "warn")
    board = ctx.scoreboard()
    ui.section("Every crash and calm year we tested")
    if board is None:
        if st.button("Test my picks in every event", width="stretch"):
            board = ui.compute_scoreboard(ctx)
    if board:
        ui.list_rows([("🌪️" if r["type"] == "crisis" else "🌤️", ui.esc(r["event"]),
                       f"Worst fall: A −{ui.inr_short(r['fall_A'] * ctx.amount_a)} · B −{ui.inr_short(r['fall_B'] * ctx.amount_b)}",
                       ui.chip("✓ held", "ok") if r["label_held"] else ui.chip("✗", "bad"),
                       ("B beat market" if r["b_held_up"] else "B lagged market") if r["type"] == "crisis" else "") for r in board])
        n = sum(r["label_held"] for r in board)
        ui.verdict("🏁", f"Labels held in {n} of {len(board)} events",
                   f"Steady beat the market in {sum(r['b_held_up'] for r in board if r['type'] == 'crisis')} of "
                   f"{sum(r['type'] == 'crisis' for r in board)} crashes.")

if right is not None:
    with right:
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
