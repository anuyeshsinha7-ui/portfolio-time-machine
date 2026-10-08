"""Page 2 — How this app works (brief §8.2)."""
import pandas as pd
import streamlit as st

from src import config
from src import data as D
from src import ui

left, right = ui.split()
meta = D.metadata()

with left:
    ui.hero("How it works", "5 simple steps", "From your amount to a clear answer", "")
    steps = [("Tell us your amount", "Every result is shown in rupees on it."),
             ("Meet two portfolios", "A is bold, B is steady — 10 big Indian companies each."),
             ("See what to buy", "Exact rupees and number of shares for each company."),
             ("Travel back in time", "Replay the 2008 crash, COVID-19 and more on today's portfolios."),
             ("Get your answer", "Does 'safe' stay safe? Which portfolio fits the loss you can live with?")]
    st.html("<div class='app-steps'>" + "".join(f"<div class='app-step'><div class='n'>{i}</div><div><div class='t1'>{a}</div>"
                                                 f"<div class='t2'>{b}</div></div></div>" for i, (a, b) in enumerate(steps, 1)) + "</div>")
    ui.section("Three moments we compare")
    ui.list_rows([("📅", "Today", "The latest 12 months", "", ""),
                  ("🌪️", "A crash", "Pick any past crisis", "", ""),
                  ("🌤️", "A calm year", "Pick any quiet spell", "", "")])
    ui.note(f"Built on {meta['n_core'] + meta['n_extended']} Nifty 200 companies, every price double-checked against the "
            "stock exchange's own records.", "🔍", "good")

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
 fillcolor="#161D2C", color="#3A4560"]; edge [color="#6B7690", arrowsize=.6];
 y [label="Yahoo raw closes\\n+ split & dividend history"]; a [label="Anchor to NSE official closes\\n(monthly checks, bisect to the day)"];
 s [label="Re-apply splits, bonuses, rights\\nfrom NSE records"]; d [label="Demergers: NSE price-discovery ratio\\nor drop that day"];
 b [label="Bad ticks, decimal errors,\\nstale prices (checked vs NSE)"]; c [label="Align to Nifty 50 calendar\\n(fill ≤ 2 days, ≤ 2% missing)"];
 v [label="Dividends reinvested\\n→ total-return prices", fillcolor="#3A2420", color="#E8735A"];
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
