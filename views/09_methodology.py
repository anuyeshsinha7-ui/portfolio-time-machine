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
    ui.tiles([("Companies checked", f"{meta['n_constituents']}", "today's Nifty 500", ""),
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
        st.markdown("#### How clean the data is")
        cats = {"A_split_bonus": "Splits, bonuses, rights, dividends", "B_demerger": "Demergers", "C_symbol": "Name changes and new listings",
                "D_bad_print": "Wrong prices and odd jumps", "E_calendar": "Missing days and prices that didn't change", "F_integrity": "Checks on the saved data"}
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Stocks checked", meta["n_constituents"])
        c2.metric("Core (since 2007)", meta["n_core"])
        c3.metric("Extended", meta["n_extended"])
        c4.metric("Excluded", meta["n_excluded"])
        fixed = rep["action"].astype(str).str.contains("replaced|applied|adjusted|dropped|filled|set to missing|rescaled|treated|used NSE|added",
                                                       case=False)
        summ = rep.assign(fixed=fixed).groupby("category").agg(Found=("issue", "size"), Stocks=("ticker", "nunique"),
                                                               Fixed=("fixed", "sum")).reset_index()
        summ["category"] = summ["category"].map(cats)
        st.dataframe(summ.rename(columns={"category": "Check"}), hide_index=True, width="stretch")
        spots = pd.read_csv(config.DATA_DIR / "spot_checks.csv")
        st.caption(f"Random checks against the NSE's official closing prices: {int(spots['within_1pct'].sum())} of {len(spots)} "
                   f"within 1%. Data fingerprint (checksum): {meta['prices_sha256'][:12]}…")
        q = st.text_input("Search the full cleaning report (stock, problem, date…)", key="dq_search")
        view = rep if not q else rep[rep.apply(lambda r: q.lower() in " ".join(map(str, r.values)).lower(), axis=1)]
        st.dataframe(view.drop(columns=[c for c in ("fixed", "excluded") if c in view.columns]), hide_index=True, width="stretch", height=320)
        st.caption(f"{len(view):,} of {len(rep):,} rows.")
        st.markdown("#### The crises and calm periods we can test")
        st.dataframe(pd.DataFrame([{"Event": e["name"], "Type": e["type"], "Used?": "yes" if e["available"] else "no",
                                    "Window (standard)": " → ".join(e["windows"]["standard"] or []), "Data check": e.get("support", ""),
                                    "Source": e.get("source", "")} for e in ctx.events.values()]), hide_index=True, width="stretch")
        st.markdown("#### What this analysis can't tell you")
        for t_, d_ in RC.LIMITATIONS:
            st.markdown(f"* **{t_}.** {d_}")
        st.markdown("#### The formulas")
        st.latex(r"r_t = \frac{P_t}{P_{t-1}} - 1 \quad r_{p,t} = \sum_i w_i r_{i,t} \quad \mu = 252\,\bar r \quad \sigma = \sqrt{252}\,s")
        st.latex(r"\beta = \frac{\operatorname{Cov}(r, r_m)}{\operatorname{Var}(r_m)} \quad \text{MDD} = \max_t\Big(1 - \frac{W_t}{\max_{s\le t} W_s}\Big)")
        st.latex(r"\text{Sharpe} = \frac{\mu - r_f}{\sigma} \quad \text{Sortino} = \frac{\mu - r_f}{\sigma_{\text{down}}}")
        st.latex(r"z_{CF} = z + \tfrac{(z^2-1)S}{6} + \tfrac{(z^3-3z)K}{24} - \tfrac{(2z^3-5z)S^2}{36}")
        st.markdown(f"""
* **Returns** are simple daily returns, with 252 trading days in a year. VaR, ES and the best-mix line keep the **weights fixed**
  (as if you topped up every day). The rupee crisis replay **buys once and holds** from the first day of the period.
* **Labels** use the last {config.CLASSIFICATION_YEARS} years. The tests use older periods, so they check the labels on data the
  labels never saw.
* **Risk-free rate** {config.RISK_FREE_RATE:.4%}: {config.RISK_FREE_SOURCE} ({config.RISK_FREE_URL}).
* **About the Nifty:** our stock prices include reinvested dividends, but the Nifty 50 index does not, so beta and comparisons with the
  Nifty slightly favour the stocks.
* **Ledoit–Wolf shrinkage** (a way to steady the covariance estimate) is in the code as an option, built in NumPy and checked
  against scikit-learn in the tests.
""")
        st.markdown("#### Glossary")
        st.dataframe(pd.DataFrame([
            ("VaR", "Value at Risk: the loss you stay under on c% of days"), ("ES", "Expected Shortfall: the average loss on the worst (1−c)% of days"),
            ("MDD", "Maximum drawdown: the biggest fall from a high point to a low point"), ("NSE", "National Stock Exchange of India"),
            ("FRTB", "Fundamental Review of the Trading Book (Basel rules for banks; ES at 97.5%)"), ("SLSQP", "Sequential Least Squares Programming (the optimiser method)"),
            ("SPOS", "Special pre-open session (how the NSE sets prices on the day of a demerger)"), ("NBFC", "Non-banking financial company"),
            ("FPI", "Foreign portfolio investor"), ("VIX", "Volatility index (India VIX = how much the market expects the Nifty to swing)"),
            ("RBI", "Reserve Bank of India"), ("T-bill", "Treasury bill (short-term government debt)"),
            ("CF", "Cornish–Fisher: adjusts the bell curve for lopsided and extreme days"), ("POF", "Proportion of failures (Kupiec's test)"),
        ], columns=["Term", "Meaning"]), hide_index=True, width="stretch")
        st.markdown("#### What's in each data file")
        st.dataframe(pd.DataFrame([
            ("data/prices.csv.gz", "Closing price per stock with dividends reinvested, on Nifty 50 trading days"),
            ("data/benchmark.csv.gz", "Nifty 50 close and India VIX"),
            ("data/universe.csv", "Symbol, company, sector, size, status (core, extended or excluded) and why"),
            ("data/corporate_actions.csv", "Every split, bonus, rights issue and demerger, with its ratio and source"),
            ("data/symbol_changes.csv", "Old and new NSE symbols for today's companies"),
            ("data/excluded_returns.csv", "Single days we left out (demergers with no official ratio, unexplained split-sized jumps)"),
            ("data/data_quality_report.csv", "Every problem found: stock, date, problem, evidence, what we did, source"),
            ("data/events.json", "The list of crises and calm periods: date ranges, stories, sources"),
            ("results/default.json", "Results worked out in advance for the default portfolios in every period"),
        ], columns=["File", "Contents"]), hide_index=True, width="stretch")
        corp = pd.read_csv(config.DATA_DIR / "corporate_actions.csv")
        st.markdown(f"#### Splits, bonuses and other company actions we applied ({int(corp['applied'].sum())})")
        st.dataframe(corp, hide_index=True, width="stretch", height=260)
