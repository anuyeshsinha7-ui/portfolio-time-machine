"""Page 2 — How this app works (brief §8.2)."""
import pandas as pd
import streamlit as st

from src import config
from src import data as D
from src import ui

left, right = ui.split()
meta = D.metadata()

with left:
    ui.hero("How it works", "6 simple steps", "From your amount to a clear answer", "")
    steps = [("Tell us your amount", "Every result is shown in rupees on it."),
             ("Choose sectors & size", "Tick the sectors and company sizes you like."),
             ("Get your recommendation", f"We pick the top {config.PICK_N} bold and top {config.PICK_N} steady companies for you "
              "(you can still choose your own)."),
             ("See what to buy", "Exact rupees and number of shares for each company."),
             ("Travel back in time", "Replay the 2008 crash, COVID-19 and more on today's portfolios."),
             ("Get your answer", "Does 'safe' stay safe? Which portfolio fits the loss you can live with?")]
    st.html("<div class='app-steps'>" + "".join(f"<div class='app-step'><div class='n'>{i}</div><div><div class='t1'>{a}</div>"
                                                 f"<div class='t2'>{b}</div></div></div>" for i, (a, b) in enumerate(steps, 1)) + "</div>")
    ui.section("Three moments we compare")
    ui.list_rows([("📅", "Today", "The latest 12 months", "", ""),
                  ("🌪️", "A crash", "Pick any past crisis", "", ""),
                  ("🌤️", "A calm year", "Pick any quiet spell", "", "")])
    ui.note(f"Built on {meta['n_core'] + meta['n_extended']} Nifty 500 companies, every price double-checked against the "
            "stock exchange's own records.", "🔍", "good")

if right is not None:
    with right:
        st.markdown("#### Where this screen fits")
        ui.flowchart("how")
        st.markdown("#### Data sources")
        st.markdown(f"""
* **Prices:** Yahoo Finance, through the `yfinance` library. Daily closing prices from {meta['history_start']} to {meta['as_of']}.
  We downloaded them once and saved them, so the app downloads nothing while you use it.
* **Official checks:** the NSE's daily price files (bhavcopies) and its records of splits, bonuses, demergers and name changes.
* **Which stocks:** the NSE's Nifty 500 list (for sectors) and its Nifty 100, Midcap 150 and Smallcap 250 lists (for large, mid
  and small companies).
* **Risk-free rate:** {config.RISK_FREE_SOURCE}.
""")
        st.markdown("#### How we cleaned the prices")
        st.graphviz_chart("""
digraph C { rankdir=TB; bgcolor="transparent"; node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10,
 fillcolor="#161D2C", color="#3A4560"]; edge [color="#6B7690", arrowsize=.6];
 y [label="Yahoo raw closes\\n+ split & dividend history"]; a [label="Anchor to NSE official closes\\n(monthly checks, bisect to the day)"];
 s [label="Re-apply splits, bonuses, rights\\nfrom NSE records"]; d [label="Demergers: NSE price-discovery ratio\\nor drop that day"];
 b [label="Bad ticks, decimal errors,\\nstale prices (checked vs NSE)"]; c [label="Align to Nifty 50 calendar\\n(fill ≤ 2 days, ≤ 2% missing)"];
 v [label="Dividends reinvested\\n→ total-return prices", fillcolor="#3A2420", color="#E8735A"];
 y -> a -> s -> d -> b -> c -> v; }""", width="stretch")
        st.markdown("#### The settings we used")
        st.dataframe(pd.DataFrame([
            ("Trading days in a year", config.TRADING_DAYS), ("Data used for risk labels", f"the last {config.CLASSIFICATION_YEARS} years"),
            ("Length of each test period", f"{config.REGIME_DAYS} trading days (about 12 months)"),
            ("Where a crisis period starts", f"{config.EVENT_PRE_DAYS} trading days before the market's peak"),
            ("Weight per stock", f"{config.W_MIN:.0%} to {config.W_MAX:.0%}"), ("Most in one sector", f"{config.INDUSTRY_MAX:.0%}"),
            ("Risk-free rate", f"{config.RISK_FREE_RATE:.2%} (91-day Treasury bill)"), ("VaR confidence", "95% and 99% (ES also at 97.5%)"),
            ("Monte Carlo", f"{config.MC_DRAWS:,} random Student-t draws, seed {config.SEED}"),
            ("Bootstrap", f"{config.BOOTSTRAP_RESAMPLES} reshuffles of the data, in {config.BLOCK_DAYS}-day blocks"),
        ], columns=["Assumption", "Value"]).astype(str), hide_index=True, width="stretch")
