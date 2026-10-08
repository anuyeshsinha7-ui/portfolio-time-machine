"""Page 2 — How this app works (brief §8.2)."""
import pandas as pd
import streamlit as st

from src import config
from src import data as D
from src import ui

ui.page_header("how", "How this app works", "Your journey through the app, and what happens behind each step.")
left, right = ui.split()
meta = D.metadata()

with left:
    st.markdown(f"""
0. **Tell us how much you want to invest.** Every rupee figure follows your amount.
1. **The 30-second verdict** on Home — the answer first, details after.
2. **The stock universe.** Today's Nifty 200 companies; {meta['n_core']} of them have a clean price history all the way back to
   September 2007, so they can be tested in every crisis since the 2008 crash.
3. **Your choice — Industry → Stock.** Each stock carries a *High risk* or *Low risk* tag from two numbers: how much it moves
   with the market (**beta**) and how much it swings on its own (**volatility**).
4. **Optimum weights for today.** We work out how much of your money goes into each stock — the high-risk portfolio aims for the
   best return per unit of risk, the low-risk one for the smallest swings — and turn that into whole shares you could buy.
5. **Pick a historical event** — the 2008 crash, COVID-19, the taper tantrum… — and watch how both portfolios would have fared.
6. **Weights at the time of crisis, calm and today**, and the money you could lose on a bad day **before and after** re-optimising.
7. **Verdict** — does the risk label hold, are the weights robust, and which portfolio fits the loss you can live with.
""")
    st.info("Three situations appear everywhere: **Current** (the latest 12 months), **Crisis** (a historical crash you choose) "
            "and **Calm** (a historical quiet spell you choose).")

if right is not None:
    with right:
        st.markdown("#### Where you are")
        ui.flowchart("how")
        st.markdown("#### Data sources")
        st.markdown(f"""
* **Prices:** Yahoo Finance via the `yfinance` library — daily closes from {meta['history_start']} to {meta['as_of']},
  downloaded once and frozen (no market data is downloaded while you use the app).
* **Official checks:** NSE bhavcopies (the exchange's daily price files) and NSE's corporate-action and symbol-change records.
* **Universe:** NSE's Nifty 200 and Nifty 100 constituent lists (industry and market-cap bucket).
* **Risk-free rate:** {config.RISK_FREE_SOURCE}.
""")
        st.markdown("#### Cleaning, in one picture")
        st.graphviz_chart("""
digraph C { rankdir=TB; bgcolor="transparent"; node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10,
 fillcolor="#FFFFFF", color="#C9CED8"]; edge [color="#9AA1AE", arrowsize=.6];
 y [label="Yahoo raw closes\\n+ split & dividend history"]; a [label="Anchor to NSE official closes\\n(monthly checks, bisect to the day)"];
 s [label="Re-apply splits, bonuses, rights\\nfrom NSE records"]; d [label="Demergers: NSE price-discovery ratio\\nor drop that day"];
 b [label="Bad ticks, decimal errors,\\nstale prices (checked vs NSE)"]; c [label="Align to Nifty 50 calendar\\n(fill ≤ 2 days, ≤ 2% missing)"];
 v [label="Dividends reinvested\\n→ total-return prices", fillcolor="#FCE9E4", color="#E8735A"];
 y -> a -> s -> d -> b -> c -> v; }""", width="stretch")
        st.markdown("#### Key assumptions")
        st.dataframe(pd.DataFrame([
            ("Trading days per year", config.TRADING_DAYS), ("Risk label window", f"{config.CLASSIFICATION_YEARS} years (trailing)"),
            ("Regime window", f"{config.REGIME_DAYS} trading days ≈ 12 months"),
            ("Crisis window start", f"{config.EVENT_PRE_DAYS} trading days before the pre-crash peak"),
            ("Weight bounds", f"{config.W_MIN:.0%} – {config.W_MAX:.0%} per stock"), ("Industry cap", f"{config.INDUSTRY_MAX:.0%}"),
            ("Risk-free rate", f"{config.RISK_FREE_RATE:.2%} (91-day T-bill)"), ("VaR confidence", "95% and 99%; ES also at 97.5%"),
            ("Monte Carlo", f"{config.MC_DRAWS:,} Student-t draws, seed {config.SEED}"),
            ("Bootstrap", f"{config.BOOTSTRAP_RESAMPLES} resamples (build) · {config.BLOCK_DAYS}-day blocks"),
        ], columns=["Assumption", "Value"]).astype(str), hide_index=True, width="stretch")
