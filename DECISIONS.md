# Decisions and defaults

Every default chosen without asking the team. ⚠️ marks an item the team should double-check before presenting.

## Environment and stack

1. **Python 3.13 locally, not 3.11/3.12.** stlite 1.9.2 (latest release, 23 Sep 2026) runs Pyodide 0.29.3, which is Python 3.13.2 and ships a `cp313` Streamlit wheel. Using 3.13 locally keeps the offline backup (`streamlit run app.py`) and the browser on the same interpreter. Conda env: `fra`.
2. **Pinned versions.** stlite `@stlite/browser@1.9.2`; Streamlit 1.62.0 (the wheel bundled in that stlite release); pandas 2.3.3, NumPy 2.2.5, SciPy 1.14.1 (the Pyodide 0.29.3 builds); Plotly 5.24.1 and openpyxl 3.1.5 (pure-Python wheels installed from PyPI in the browser). Plotly 5.x follows stlite's own advice to avoid a micropip resolution clash with Altair.
3. **Risk-free rate = 5.5747% a year**, the 91-day Treasury bill implicit yield at cut-off in the Reserve Bank of India (RBI) auction of 7 Oct 2026 (press release 2026-2027/1268, <https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63746>). Used as a constant annual rate for Sharpe and Sortino ratios in every window (historical windows are compared on today's hurdle so only the market data changes).

## Data

4. **Universe = today's Nifty 200** (NSE list downloaded 8 Oct 2026, saved as `data/nse_nifty200_list.csv`); market-cap bucket from Nifty 100 membership. Survivorship bias is acknowledged on the methodology page.
5. **Three tiers instead of a hard cut.** *Core* (119 stocks) = continuous clean history from 17 Sep 2007 — the default A/B picker only uses these, so every catalogue event is testable. *Extended* (66) = at least 3 years of clean history; offered for custom picks, with earlier events greyed out and the reason shown. *Excluded* (15) = under 3 years. The 15-year fallback in the brief was not needed (well over 10 High-risk and 10 Low-risk core stocks).
6. **Yahoo anchored to NSE official prices.** Yahoo's split-adjusted `Close` turned out to contain 59 hidden level errors in 43 stocks (missing, wrong-ratio or unrecorded adjustments). Every stock is therefore anchored to NSE bhavcopy closes on the first trading day of each month, with day-level bisection wherever the level steps. `scripts/clean_data.py` downloads the official files it needs into `data/raw/bhav/` (local build only).
7. **Corporate actions rebuilt from NSE records**, confirmed by the ex-date price move (the move must sit closer, in log terms, to the action's factor than to "no change"). Where NSE's feed has no record but Yahoo's action history does (Bharti Airtel, Jul 2009), Yahoo's record is used and cited.
8. **Rights issues are adjusted** (theoretical ex-rights price from NSE's terms and face value) although the brief does not list them: unadjusted deep-discount rights issues (e.g. M&M Financial, Jul 2020) would otherwise show as fake one-day crashes. Partly-paid issues and warrants are not adjusted.
9. **Demergers:** from 30 Apr 2023 (NSE Indices' methodology using the special pre-open session price) the official ratio = ex-date discovered opening price ÷ previous close, both from NSE bhavcopies (Reliance/JFS, ITC/ITC Hotels, Siemens/Siemens Energy, Tata Motors PV/CV, HUL/Kwality Wall's, Vedanta). Earlier demergers with a large drop have that single day's return dropped (`data/excluded_returns.csv`), as the brief allows. ⚠️ Check `data/corporate_actions.csv` rows with type `demerger`.
10. **Dividends from NSE records** (₹ per share; older notices quoted as % of face value are converted), reinvested on the ex-date. This is why our total-return series differs from Yahoo's `Adj Close` by more than 0.5% for most stocks; each difference is logged with its reason.
11. **Stale runs over 10 days:** if NSE's bhavcopy shows trading at other prices, Yahoo's data is wrong and the days are replaced with NSE closes (GE Vernova T&D, 2016–17); if NSE shows no trading, it was a real suspension/relisting gap and the stock's usable history starts after it (Patanjali 2019–20; Colgate's symbol switch in Dec 2007). This keeps the brief's continuity rule while not deleting stocks that are fine for later events.
12. **Yahoo rows before an NSE listing are dropped** (e.g. Nestlé India only listed on NSE on 8 Jan 2010; Yahoo's flat ".NS" prices before that are not NSE trades; Bajaj Auto / Bajaj Finserv before their 26 May 2008 listing).
13. **COLGATE → COLPAL** (Dec 2007) is missing from NSE's symbol-change list; established from NSE bhavcopies (price moves match exactly, clean hand-over). ⚠️ Team to eyeball.
14. **Spike-and-revert ticks are checked against NSE before removal.** Nine of the ten rule hits were real moves on crash/rebound days (confirmed by NSE's close) and were kept; one (Motherson, 9 Jan 2009) was removed.
15. **18 Mar 2025:** Yahoo repeated the previous day's close with zero volume for nearly every stock; NSE traded normally, so that session's closes come from NSE's bhavcopy.
16. **Six Nifty 50 sessions in 2010–2012** are missing from Yahoo and NSE has no index-close file for them; they are left out of the calendar (stock returns merge into the next session). Later gaps (13 days) are filled from NSE's official index closes.
17. **Downloads per ticker, not one big batch.** `yf.Ticker().history(..., actions=True)` returns prices and the action history in one call; retries use exponential back-off.

## Analytics

18. **Official crisis and calm = the automatic picks** (§0 left blank): crisis = deepest Nifty 50 drawdown window (6 Dec 2007 → 17 Dec 2008, the Global Financial Crisis; Nifty −60% peak to trough); calm = lowest-volatility 252-day window not overlapping Current or the crisis (30 Jan 2017 → 1 Feb 2018, Nifty volatility 9%). ⚠️ The team can override with `OFFICIAL_CRISIS_EVENT` / `OFFICIAL_CALM_EVENT` in `src/config.py`.
19. **Event support threshold:** a catalogue crisis is kept only if the Nifty 50 fell at least 7% peak to trough inside its search range. The **US tariff shock (Mar–Apr 2025)** fell only 6.4% and is shown as unavailable; its fall is part of the 2024–25 foreign-investor sell-off event. The Adani–Hindenburg sell-off passes at 7.1%, but its 252-day standard window is mostly calm (it overlaps the Low-VIX stretch) — use the "event only" window mode for it. ⚠️
20. **Calm windows:** the lowest-volatility 252-day window whose midpoint lies inside the search range (standard mode) and the lowest-volatility 126-day stretch (event-only mode). Centring on the 126-day stretch instead would have pulled the Nov 2016 demonetisation fall into the "2017 calm".
21. **Overlap with Current:** a window that would overlap the latest 252 days is slid earlier (same length) if the event still fits, otherwise marked unavailable.
22. **The scoreboard covers the 13 data-supported catalogue events**; the two auto picks are left out because they duplicate catalogue windows (GFC, 2017). "B beat the Nifty" is only judged for crises.
23. **Evidence for the call uses the same trailing 3 years as the labels** (weighted beta, √(wᵀΣw), drawdown, correlation, bootstrap σA/σB). Today's weights are optimised on the latest 252 days (Current window).
24. **Bootstrap for Test #2** resamples the Current window (5-day moving blocks) and re-solves the same target-return problem; turnover is measured against the Current-window solution of that problem (which equals today's weights). 500 resamples at build time, 200 in the browser.
25. **Max-Sharpe solved directly with SLSQP** (analytic gradients, several feasible starts) and cross-checked in tests against the convex reformulation in cvxpy and the best point on the frontier grid; minimum variance cross-checked against cvxpy.
26. **Monte Carlo Student-t:** degrees of freedom fitted by maximum likelihood to the window's standardised portfolio returns, floored at 3; asset scale matrix Σ·(ν−2)/ν so the simulated covariance equals the sample covariance; seed 42, 10,000 draws.
27. **Historical VaR** = the k-th worst return with k = ⌊n(1−c)⌋ (e.g. 2nd worst of 252 at 99%); ES = mean of the k worst. Cornish–Fisher ES averages the (monotone-rearranged) CF quantile over the tail.
28. **Pure formatting helpers live in `src/fmt.py`** (not `ui.py`) so the analytics, narrative and landing-page builder can format rupees without importing Streamlit; `ui.py` re-exports them.

## Interface

29. **stlite boot proven before building pages:** a minimal app (Start + Home + sidebar dropdowns, all of `src/`) booted in headless Chromium from `_site/` in about 12 s; `st.navigation`, multi-file imports, `st.query_params` and `st.graphviz_chart` all work under stlite 1.9.2, so no fallbacks were needed. The landing page → dashboard amount hand-off (`app/?amount=…`) works.
30. **Browser packages:** numpy, pandas, scipy (Pyodide builds) + plotly 5.24.1 and openpyxl 3.1.5 (PyPI wheels).
31. **"Greyed-out" events:** Streamlit select boxes cannot disable single options, so an event the chosen stocks cannot cover is labelled "unavailable — {stock} listed in {year}" in the dropdown; picking it shows the reason and falls back to the official pick.
