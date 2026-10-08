"""Page 9 — Methodology and data (brief §8.9, §5.2 Data health)."""
import pandas as pd
import streamlit as st

from src import config
from src import data as D
from src import export as X
from src import recommend as RC
from src import ui

ctx = ui.context()
left, right = ui.split()
meta = D.metadata()
rep = pd.read_csv(config.DATA_DIR / "data_quality_report.csv")
spots = pd.read_csv(config.DATA_DIR / "spot_checks.csv")
anchor = pd.read_csv(config.DATA_DIR / "nse_anchor.csv")
corp = pd.read_csv(config.DATA_DIR / "corporate_actions.csv")

with left:
    ui.hero("About the data", "Checked against the exchange", f"Prices as of {meta['as_of']} · history since {meta['history_start'][:4]}", "calm")
    ui.tiles([("Companies checked", f"{meta['n_constituents']}", "today's Nifty 200", ""),
              ("Price errors fixed", f"{len(anchor)}", f"in {anchor['ticker'].nunique()} companies", ""),
              ("Splits, bonuses & more", f"{int(corp['applied'].sum())}", "rebuilt from NSE records", ""),
              ("Spot checks passed", f"{int(spots['within_1pct'].sum())}/{len(spots)}", "vs NSE's official prices", "")])
    ui.section("What we did")
    ui.list_rows([("🔍", "Matched every price to NSE", "Monthly checks against the exchange's own daily files, fixed to the exact day.", "", ""),
                  ("✂️", "Rebuilt splits & bonuses", "So a 1:1 bonus never looks like a 50% crash.", "", ""),
                  ("🧩", "Handled demergers", "Reliance–Jio Financial, ITC–ITC Hotels and more, using NSE's own price-discovery.", "", ""),
                  ("💰", "Added dividends back", "Returns include the cash companies paid out.", "", ""),
                  ("🧹", "Removed bad prints", "Stale prices, wrong ticks and pre-listing rows checked and fixed.", "", "")])
    ui.note("Every fix — what, when, the evidence and the source — is listed in the full report in the working panel.", "📄")
    xl = X.workbook({"portfolios": ctx.P, "evidence": ctx.evidence, "regimes": ctx.regimes(), "scoreboard": ctx.scoreboard(),
                     "universe": ui.universe_table(), "events": ctx.events, "amounts": (ctx.amount_a, ctx.amount_b)})
    st.download_button("⬇️ Download all results (Excel)", xl, file_name=f"portfolio_time_machine_{D.as_of()}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch", type="primary")
    st.caption("Educational project — not investment advice. Data: Yahoo Finance (via yfinance) and NSE.")

if right is not None:
    with right:
        st.markdown("#### Data health")
        cats = {"A_split_bonus": "Splits, bonuses, rights, dividends", "B_demerger": "Demergers", "C_symbol": "Symbol changes & listings",
                "D_bad_print": "Bad prints & outliers", "E_calendar": "Calendar, gaps, stale prices", "F_integrity": "Snapshot integrity"}
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Stocks checked", meta["n_constituents"])
        c2.metric("Core (since 2007)", meta["n_core"])
        c3.metric("Extended", meta["n_extended"])
        c4.metric("Excluded", meta["n_excluded"])
        fixed = rep["action"].astype(str).str.contains("replaced|applied|adjusted|dropped|filled|set to missing|rescaled|treated|used NSE|added",
                                                       case=False)
        summ = rep.assign(fixed=fixed).groupby("category").agg(Detections=("issue", "size"), Stocks=("ticker", "nunique"),
                                                               Fixed=("fixed", "sum")).reset_index()
        summ["category"] = summ["category"].map(cats)
        st.dataframe(summ.rename(columns={"category": "Check"}), hide_index=True, width="stretch")
        spots = pd.read_csv(config.DATA_DIR / "spot_checks.csv")
        st.caption(f"Spot checks against NSE's official closes: {int(spots['within_1pct'].sum())} of {len(spots)} within 1%. "
                   f"Snapshot checksum {meta['prices_sha256'][:12]}…")
        q = st.text_input("Search the full cleaning report (ticker, issue, date…)", key="dq_search")
        view = rep if not q else rep[rep.apply(lambda r: q.lower() in " ".join(map(str, r.values)).lower(), axis=1)]
        st.dataframe(view.drop(columns=[c for c in ("fixed", "excluded") if c in view.columns]), hide_index=True, width="stretch", height=320)
        st.caption(f"{len(view):,} of {len(rep):,} rows.")
        st.markdown("#### Event catalogue")
        st.dataframe(pd.DataFrame([{"Event": e["name"], "Type": e["type"], "Used?": "yes" if e["available"] else "no",
                                    "Window (standard)": " → ".join(e["windows"]["standard"] or []), "Data check": e.get("support", ""),
                                    "Source": e.get("source", "")} for e in ctx.events.values()]), hide_index=True, width="stretch")
        st.markdown("#### Limitations")
        for t_, d_ in RC.LIMITATIONS:
            st.markdown(f"* **{t_}.** {d_}")
        st.markdown("#### Definitions")
        st.latex(r"r_t = \frac{P_t}{P_{t-1}} - 1 \quad r_{p,t} = \sum_i w_i r_{i,t} \quad \mu = 252\,\bar r \quad \sigma = \sqrt{252}\,s")
        st.latex(r"\beta = \frac{\operatorname{Cov}(r, r_m)}{\operatorname{Var}(r_m)} \quad \text{MDD} = \max_t\Big(1 - \frac{W_t}{\max_{s\le t} W_s}\Big)")
        st.latex(r"\text{Sharpe} = \frac{\mu - r_f}{\sigma} \quad \text{Sortino} = \frac{\mu - r_f}{\sigma_{\text{down}}}")
        st.latex(r"z_{CF} = z + \tfrac{(z^2-1)S}{6} + \tfrac{(z^3-3z)K}{24} - \tfrac{(2z^3-5z)S^2}{36}")
        st.markdown(f"""
* **Simple returns**, 252 trading days a year. VaR/ES and the frontier use **constant weights** (rebalanced daily); the ₹ crisis replay
  uses **buy-and-hold** from the window's first day.
* **Labels** on the trailing {config.CLASSIFICATION_YEARS} years; tests run on the past, so they are out of sample.
* **Risk-free rate** {config.RISK_FREE_RATE:.4%}: {config.RISK_FREE_SOURCE} ({config.RISK_FREE_URL}).
* **Benchmark caveat:** stock prices include reinvested dividends; the Nifty 50 is a price index, so beta and 'vs Nifty' comparisons
  slightly favour the stocks.
* **Ledoit–Wolf shrinkage** is implemented in NumPy (available in the code as an option, checked against scikit-learn in tests).
""")
        st.markdown("#### Glossary")
        st.dataframe(pd.DataFrame([
            ("VaR", "Value at Risk — the loss not exceeded on c% of days"), ("ES", "Expected Shortfall — average loss on the worst (1−c)% of days"),
            ("MDD", "Maximum drawdown — largest peak-to-trough fall"), ("NSE", "National Stock Exchange of India"),
            ("FRTB", "Fundamental Review of the Trading Book (Basel rules; ES at 97.5%)"), ("SLSQP", "Sequential Least Squares Programming (optimiser)"),
            ("SPOS", "Special pre-open session (NSE price discovery on demerger ex-dates)"), ("NBFC", "Non-banking financial company"),
            ("FPI", "Foreign portfolio investor"), ("VIX", "Volatility index (India VIX = expected Nifty volatility)"),
            ("RBI", "Reserve Bank of India"), ("T-bill", "Treasury bill (short-term government debt)"),
            ("CF", "Cornish–Fisher expansion"), ("POF", "Proportion of failures (Kupiec's test)"),
        ], columns=["Term", "Meaning"]), hide_index=True, width="stretch")
        st.markdown("#### Data dictionary")
        st.dataframe(pd.DataFrame([
            ("data/prices.csv.gz", "Total-return close per stock, Nifty 50 trading calendar"),
            ("data/benchmark.csv.gz", "Nifty 50 close and India VIX"),
            ("data/universe.csv", "Symbol, company, industry, cap bucket, status (core/extended/excluded) and reason"),
            ("data/corporate_actions.csv", "Every split, bonus, rights issue and demerger, factor and source"),
            ("data/symbol_changes.csv", "Old → new NSE symbols affecting today's names"),
            ("data/excluded_returns.csv", "Single-day returns dropped (demergers without an official ratio)"),
            ("data/data_quality_report.csv", "Every detection: ticker, date, issue, evidence, action, source"),
            ("data/events.json", "Event catalogue: search ranges, stories, sources"),
            ("results/default.json", "Precomputed results for the team's portfolios × every event"),
        ], columns=["File", "Contents"]), hide_index=True, width="stretch")
        corp = pd.read_csv(config.DATA_DIR / "corporate_actions.csv")
        st.markdown(f"#### Corporate actions applied ({int(corp['applied'].sum())})")
        st.dataframe(corp, hide_index=True, width="stretch", height=260)
