# Build brief for Claude Code — "Portfolio Time Machine" (FRA Group Project 1)

## 0. Fill-ins (optional — sensible defaults apply if left blank)

* App name: **Portfolio Time Machine** — tagline: *"Does 'safe' stay safe when the market crashes?"*
* Team members (credits + presentation split): [Name 1], [Name 2], [Name 3], [Name 4]
* Credit line: PGDM, Great Lakes Institute of Management, Gurgaon
* GitHub account for deployment: [your GitHub username] — the live site will be `https://<username>.github.io/portfolio-time-machine/`. If `gh` is logged in, read it with `gh api user --jq .login`.
* Teammates' GitHub usernames (optional — added as collaborators): [ ]
* Our stock picks (National Stock Exchange (NSE) symbols), if already decided — Portfolio A: [ ] · Portfolio B: [ ]. If blank, use the data-driven picker in §6.3.
* Our official crisis and calm events for the assignment, if already decided: [ ]. If blank, use the regime finder in §6.4 and offer the event catalogue in §6.5.

## 1. Role, audience and ground rules

You are a senior quantitative developer and data-visualisation designer. Build a link-shareable Streamlit dashboard for our business-school financial risk group project and deploy it from my GitHub account to GitHub Pages (§11). It must work for three audiences:

1. Our professor — rigour; every number traceable to a formula and the data.
2. A recruiter opening the link cold — understands the project within 30 seconds.
3. A "client" with no finance background — plain language, rupee amounts, clear verdicts.

Ground rules:

* Work through every phase in §12 without stopping midway or leaving features half-built. Ask me only about true blockers (no internet access to the data sources, GitHub login). For anything else, choose a sensible default and log it in `DECISIONS.md`.
* Never fabricate, simulate or hard-code market data or findings. If data downloads fail after retries and fallbacks, stop and tell me. (Small hand-made fixtures inside `tests/fixtures/` that exercise the cleaning code are allowed; they are clearly labelled as test data and never shipped or shown as market data.)
* Every corporate-action adjustment (split, bonus, demerger ratio, symbol change) must come from a cited source — NSE, the company's exchange filing or yfinance's action history — recorded in `data/corporate_actions.csv`. Never guess a ratio; if it cannot be verified, exclude the affected stock or the affected day and log why.
* Everything is done in code — no manual spreadsheet steps.
* Analytics code in `src/` must not import Streamlit: pure, typed, documented functions that are unit-testable.
* If anything in this brief conflicts with §2, §2 wins.
* Save this brief as `docs/BRIEF.md` and re-read the relevant section before each phase.

## 2. Assignment requirements — all must be met

1. Two portfolios of at least 10 stocks each, with no stock in both:
   * Portfolio A — High Risk (going for return)
   * Portfolio B — Low Risk (playing it safe)
2. ₹15,00,000 (₹15 lakh) invested in each is the assignment default; the client must be able to set their own amount before anything else (§7, page "Start"), and change it at any time.
3. Make the call: show why A is high risk and B is low risk with numbers and logic (volatility, beta, market capitalisation, sector …) — not a vibe.
4. Time-travel test #1 — the risk label: choose one historical crisis and one calm period, with reasoning. Run Value at Risk (VaR) and Expected Shortfall (ES) for both portfolios in both periods. Did "high risk" behave like high risk? Did "low risk" hold up? Extra measures are allowed if justified.
5. Time-travel test #2 — the allocation: take the return the portfolio earns today. Rebuild the Markowitz efficient frontier with each historical period's data, aiming for that same return. Would the optimiser still pick our weights, or build something different?
6. A hosted, link-shareable dashboard, good enough for a résumé, that a recruiter understands quickly.
7. It must support a presentation of 15 minutes maximum.

Our team's official crisis and calm picks answer requirement 4. The event dropdown (§6.5) lets the client run the same tests on any other historical event as well.

## 3. Our team's design (from our planning notes) — implement faithfully

* **Amount first.** The very first thing the client sees in the dashboard is "How much would you like to invest?" Every rupee figure afterwards uses that answer.
* **Split screen on every page.** LEFT = "Client view": the app itself — inputs, rupee results, plain-language verdicts. RIGHT = "The Backing": the logic, the calculation with the actual numbers, a flowchart and graphics. The app explains itself while the client uses it.
* **The client journey:**
   0. Tell us how much you want to invest
   1. How the app works
   2. The stock universe — stocks with a full price history back to 2007 (§5.1)
   3. The client's option — choose Industry → Stock; each stock is tagged High risk or Low risk using beta and standard deviation
   4. Optimum weights for current times
   5. Pick a historical event from the dropdown (COVID-19 crash, 2008–09 Global Financial Crisis, …) and see how those choices test in it
   6. Weights at the time of crisis, calm and current — and VaR before and after
* **Three situations everywhere:** Current, Crisis (historical — any crisis event from the dropdown), Calm (historical — any calm event from the dropdown).
* Industry weights of each portfolio shown throughout.
* Client-friendly front; rigorous backing.

## 4. Stack and architecture

* **Hosting:** GitHub Pages on my GitHub account. A public repository, `portfolio-time-machine`, published by GitHub Actions to `https://<username>.github.io/portfolio-time-machine/`. Free, always on (it never goes to sleep), and no other hosting account is needed.
* GitHub Pages serves static files only, so Python runs in the visitor's browser through **stlite** (github.com/whitphx/stlite — Streamlit running on Pyodide, the WebAssembly build of Python). The same `app.py` also runs normally with `streamlit run app.py`, which is our offline backup. Read stlite's current README before writing the loader, pin the stlite version, and pin the local Streamlit version to the one that stlite release bundles so both behave the same.
* **Two layers on the site:**
   1. **Landing page** (`index.html`) — plain static HyperText Markup Language (HTML) generated at build time from the computed results: the 30-second verdict, A vs B cards, three headline findings, the pipeline flowchart, an **investment-amount field** ("How much would you invest?", Indian-formatted, default ₹15,00,000) next to the "Open the interactive dashboard" button, and the GitHub link. The button passes the amount to the dashboard as a query parameter (`app/?amount=1500000`); if stlite does not expose query parameters to the app, the dashboard's Start page asks again and the limitation is logged in `DECISIONS.md`. No Python and no heavy JavaScript libraries (small inline charts are fine), so it loads instantly on a phone.
   2. **Interactive dashboard** (`app/`) — the stlite app with every page in §8, showing a friendly loading message while the Python runtime downloads on the first visit.
* Python 3.11 or 3.12 locally. Use a dedicated conda environment if conda is available (I use Anaconda), otherwise a venv.
* **Browser-safe engine:** everything the dashboard imports must run in Pyodide — Streamlit (multipage via `st.navigation`), pandas, NumPy, SciPy (optimisation through `scipy.optimize`), Plotly (charts), openpyxl (Excel export) and the standard library (`statistics.NormalDist`, `math.erf`). No cvxpy, scikit-learn, pyarrow or yfinance in the app: implement Ledoit–Wolf shrinkage directly in NumPy, and use cvxpy only in local tests to cross-check the optimiser.
* **Formulas and flowcharts:** `st.latex` for formulas; flowcharts with `st.graphviz_chart` DOT strings. If stlite's bundled Streamlit lacks a feature, use the simplest equivalent (e.g. a sidebar page router instead of `st.navigation`, a pre-rendered Scalable Vector Graphics (SVG) flowchart instead of Graphviz) and log it in `DECISIONS.md`.
* yfinance only in the local fetch script (`requirements-dev.txt`), never in the deployed app or the GitHub Actions workflow.
* **Architecture rule — no market-data downloads at runtime.** Fetch once locally → clean (§5.2) → commit a compact snapshot (gzipped CSV or JavaScript Object Notation (JSON) files + `data/metadata.json` with the as-of date and a checksum) → the build and the app read the snapshot. Yahoo Finance rate-limits cloud servers (GitHub Actions included), and a frozen snapshot keeps the numbers in our slides identical to the site.
* **Precompute what the browser shouldn't:** universe metrics and the default portfolios' full results **for every event in the catalogue** (including the 500-resample bootstrap for the official crisis and calm picks) are computed at build time and shipped as JSON. The browser recomputes only when the client changes stocks, events or a custom date range. Amount changes never trigger recomputation — every ₹ figure is a percentage × the amount, plus the whole-share calculation.

```
portfolio-time-machine/
├── app.py                  # navigation, sidebar, shared session state, amount gate (runs locally and in stlite)
├── views/                  # one file per page: 00_start.py, 01_home.py … 09_methodology.py
├── src/
│   ├── config.py           # every assumption in one place (§6.0)
│   ├── data.py             # load snapshot, returns, windows
│   ├── cleaning.py         # corporate actions, bad ticks, gaps, alignment (§5.2) — local build only, pure functions
│   ├── universe.py         # industries, market-cap buckets, history filter
│   ├── events.py           # event catalogue loader, data-anchored event windows (§6.5)
│   ├── metrics.py          # volatility, beta, drawdown, Sharpe, Sortino, skew, kurtosis
│   ├── classify.py         # high / moderate / low risk rule
│   ├── regimes.py          # regime finder: current, auto crisis, auto calm
│   ├── optimize.py         # frontier, minimum variance, maximum Sharpe, target return (scipy.optimize)
│   ├── var_es.py           # four VaR/ES methods, horizon scaling
│   ├── stats_tests.py      # Kupiec test, block bootstrap
│   ├── allocation.py       # amount → ₹ per stock, whole shares, leftover cash, minimum sensible amount
│   ├── recommend.py        # verdict and recommendation rules
│   ├── narrative.py        # sentences generated from computed numbers
│   └── ui.py               # split layout, Finance Concept Box, flowchart, colours, rupee formatting, amount input
├── scripts/                # fetch_data.py · clean_data.py · precompute.py · run_analysis.py · build_site.py
├── site_src/               # landing-page template, stlite loader page (app/index.html), static assets
├── data/                   # snapshot, metadata.json, events.json, corporate_actions.csv, symbol_changes.csv, data_quality_report.csv
├── results/   tests/  tests/fixtures/
├── docs/                   # BRIEF.md · METHODOLOGY.md · DATA_QUALITY.md · RESULTS_SUMMARY.md · PRESENTATION_GUIDE.md · screenshots/
├── .github/workflows/deploy.yml   # tests → build → deploy to GitHub Pages
├── .streamlit/config.toml
└── requirements.txt · requirements-dev.txt · README.md · DECISIONS.md · PLAN.md
```

`scripts/build_site.py` assembles `_site/` (gitignored): the landing page, the app files, the data snapshot, the precomputed results and the stlite file list — generated automatically, never maintained by hand.

## 5. Data

### 5.1 Sources and history length

* **Universe:** NSE Nifty 200 constituents with NSE's "Industry" classification. NSE publishes constituent lists as Comma-Separated Values (CSV) files (e.g. `ind_nifty200list.csv` and `ind_nifty100list.csv` on its archives site — send a browser User-Agent). Market-cap bucket from membership: in Nifty 100 → Large cap, otherwise Mid cap. Fallbacks: yfinance sector data → a curated list in `data/universe_fallback.csv`, flagged in `DECISIONS.md` for us to verify.
* **Prices:** daily closes from yfinance (`.NS` tickers). Download **both** the raw close (`auto_adjust=False`: `Close` and `Adj Close`) **and** the action history (`Ticker.actions`: dividends and splits), because §5.2 rebuilds and checks the adjustment itself rather than trusting Yahoo blindly.
* **History length:** from **2007-09-17** (the first Nifty 50 date on Yahoo, `^NSEI`) to the latest completed trading day, so the 2008–09 Global Financial Crisis can be tested. `HISTORY_START` in `config.py`; confirm the true first date from the downloaded benchmark.
* **Benchmark:** Nifty 50 (`^NSEI`). If Yahoo's `^NSEI` series has gaps, fill them from NSE's official index history (niftyindices.com) and log every filled date. Optional: India Volatility Index (India VIX, `^INDIAVIX`) for regime evidence — skip quietly if unavailable.
* **Eligibility:** a stock enters the core universe only if it has continuous history from `HISTORY_START` (so every event in the catalogue is testable for every stock). If this leaves fewer than 10 qualifying High-risk or Low-risk stocks, fall back to a 15-year continuous-history filter, mark pre-2011 events as "partial coverage" in the dropdown, and log it. For custom picks, any event a stock does not fully cover is greyed out in the dropdown with the reason (e.g. "{stock} listed in {year} — not available for this event").
* **Downloads:** batch downloads with retries and exponential back-off; cache raw files in `data/raw/` (gitignored — only the cleaned snapshot is committed). Last-resort fallback: read one CSV per ticker from `data/manual_csv/` and tell me exactly which files to download.
* Use simple returns for portfolio maths (a portfolio return equals Σ wᵢrᵢ only for simple returns). 252 trading days per year.

### 5.2 Cleaning — handle every inconsistency, prove it, log it

Write each check as a pure function in `src/cleaning.py`, run them in order in `scripts/clean_data.py`, unit-test each one against a small fixture that contains the problem, and record every detection and fix in `data/data_quality_report.csv` (ticker, date, issue, evidence, action, source) and a readable `docs/DATA_QUALITY.md`.

**A. Stock splits and bonus issues**
* Build the adjustment factor yourself from the raw close and the split/bonus events, and compare it with Yahoo's `Adj Close`. Report any stock where the two disagree by more than 0.5% on any day.
* **Missing split detection:** on raw closes, flag any day where Pₜ / Pₜ₋₁ is within ±3% of a typical split or bonus ratio — 1/2, 1/3, 1/4, 1/5, 1/10 (splits, e.g. face value ₹10 → ₹1) and 1/2, 2/3, 3/4, 1/3 (bonus 1:1, 1:2, 1:3, 2:1) — with no matching event in Yahoo's action history. Confirm against NSE corporate actions (`nseindia.com` corporate-actions data, browser User-Agent and cookies) and add the verified event to `data/corporate_actions.csv`.
* **Double or wrong adjustment:** after adjustment, no return on a known action date may still look like the split ratio, and no return may equal the inverse ratio (sign of a double adjustment). Fix by re-adjusting from raw prices.
* **Wrong ex-date:** if Yahoo applies the split one day early or late (a spike on one day and a reversal the next around the event), move the adjustment to the official ex-date from NSE.

**B. Demergers, spin-offs and capital reductions** (Yahoo usually does **not** adjust these — e.g. Reliance → Jio Financial Services, ITC → ITC Hotels)
* Detect large one-day drops on announced record dates. Adjust the pre-event history using the official cost-of-acquisition apportionment (or the special pre-open price-discovery ratio) published by the company or NSE, and cite the source. If no official ratio can be found, drop that single day's return (treated as missing, not as a loss) and log it.

**C. Mergers, symbol changes and re-listings**
* Map renamed symbols through `data/symbol_changes.csv` (e.g. `ZOMATO → ETERNAL`, `MCDOWELL-N → UNITDSPR`, `ADANITRANS → ADANIENSOL`, `LTI → LTIM` — verify each from NSE's symbol-change list). If Yahoo's history for the new symbol starts suspiciously late, fetch the old symbol, stitch the two series, and check that prices agree within 1% at the join.
* Companies that absorbed another (e.g. HDFC Bank after the HDFC Ltd merger) keep their own price series; note the structural break in `DECISIONS.md`.
* Companies with a relisting gap or a long suspension fail the continuity rule and are excluded with the reason.

**D. Bad prints and outliers**
* Flag any daily move beyond ±20% (the widest NSE price band) for review.
* **Spike-and-revert:** |rₜ| > 15% followed by rₜ₊₁ ≈ −rₜ (within 3 percentage points) with no corporate action → bad tick; replace the price with missing and forward-fill.
* **Decimal errors:** prices that jump by ×10, ×100 or ÷10, ÷100 and revert → bad tick.
* Zero, negative, or missing (NaN) prices → missing.
* Genuine large moves (results day, circuit hits on real news) are kept; the report must say why each flagged move was kept or fixed.

**E. Calendar, gaps and alignment**
* Normalise the index to plain dates (drop the time zone), sort, and remove duplicate dates (keep the last, log it).
* Drop weekend rows that are not real NSE sessions; keep special sessions (Muhurat trading, budget-day Saturdays) only if the Nifty 50 also traded that day.
* Align every stock to the Nifty 50 trading calendar. Forward-fill at most 2 consecutive gaps; drop stocks missing more than 2% of days in the full sample.
* **Stale prices:** 5 or more identical consecutive closes → flag as suspended or illiquid; if the run exceeds 10 days, exclude the stock.
* Drop the final row if the data was fetched before the market closed (an incomplete day).

**F. Snapshot integrity**
* Save a checksum of the cleaned snapshot in `data/metadata.json`. When the data is refreshed, diff the new snapshot against the old one and report any historical prices Yahoo has silently restated.
* Spot-check at least 20 random (stock, date) pairs against NSE's historical prices where reachable, and record the result.

**G. Benchmark caveat:** stock prices are dividend-adjusted but `^NSEI` is a price index, so beta and the "vs Nifty 50" comparisons slightly favour the stocks. State this on the methodology page.

The app shows a **Data health** summary on page 9: how many stocks were checked, how many issues were found per category, what was fixed, what was excluded, and a searchable table of the full report.

## 6. Analytics specification

### 6.0 Defaults in `config.py` (all editable)

`AMOUNT_A = AMOUNT_B = 15_00_000` · `AMOUNT_MODE = "same_each"` (or `"split_total"`, `"separate"`) · `AMOUNT_MIN = 10_000` · `AMOUNT_MAX = 100_00_00_000` · `AMOUNT_PRESETS = [1_00_000, 5_00_000, 15_00_000, 50_00_000, 1_00_00_000]` · `HISTORY_START = "2007-09-17"` · `UNIVERSE = "NIFTY 200"` · `BENCHMARK = "^NSEI"` · `CLASSIFICATION_YEARS = 3` · `REGIME_DAYS = 252` · `EVENT_PRE_DAYS = 21` · `EVENT_WINDOW_MODE = "standard"` (or `"event_only"`) · `MIN_WINDOW_DAYS = 126` · `EVENTS_FILE = "data/events.json"` · `OFFICIAL_CRISIS_EVENT = OFFICIAL_CALM_EVENT = "auto"` · `CONFIDENCE = [0.95, 0.99]` · `W_MIN = 0.02` · `W_MAX = 0.25` · `INDUSTRY_MAX = 0.40` · `MIN_STOCKS = 10` · `MAX_PER_INDUSTRY_PICK = 3` · `OBJECTIVE_A = "max_sharpe"` · `OBJECTIVE_B = "min_variance"` · `RISK_FREE_RATE` (§6.6) · `MC_DRAWS = 10_000` · `BOOTSTRAP_RESAMPLES = 500` (build time) · `BOOTSTRAP_RESAMPLES_BROWSER = 200` (custom picks in the browser) · `BLOCK_DAYS = 5` · `SEED = 42` · `PORTFOLIO_A = PORTFOLIO_B = []` (empty → picker) · Cleaning: `MAX_FFILL = 2` · `MAX_MISSING_PCT = 0.02` · `JUMP_FLAG = 0.20` · `SPIKE_REVERT = 0.15` · `STALE_DAYS = 5` · `STALE_EXCLUDE_DAYS = 10` · `SPLIT_TOLERANCE = 0.03` · `ADJ_MISMATCH_TOL = 0.005`

### 6.1 Stock metrics (for any window)

Annualised return and volatility (daily standard deviation × √252), beta to the Nifty 50 (covariance ÷ market variance of daily returns), maximum drawdown, downside deviation, Sharpe and Sortino ratios, skewness, excess kurtosis.

### 6.2 Risk classification — "make the call"

* Decide labels on today's data: the trailing 3 years. This keeps both time-travel tests out-of-sample — the label is set now and tested against the past. Show full-history values alongside as a robustness check.
* Rule: **High risk** = beta ≥ 1.0 and volatility ≥ universe median. **Low risk** = beta < 1.0 and volatility < universe median. Everything else = **Moderate**.
* Composite risk score = average of the beta percentile and the volatility percentile, used for ranking within each label.

### 6.3 Building A and B

* **Default picker** (when §0 has no picks): A = the 10 highest-scoring High-risk stocks; B = the 10 lowest-scoring Low-risk stocks; at most 3 per industry, so each portfolio spans at least 4 industries; no overlap. If fewer than 10 qualify, relax to composite-score terciles and log it.
* **Client customisation** (page 3): 10–20 stocks per portfolio; overlap is blocked; a stock whose label doesn't match its portfolio triggers a warning but is allowed; "Reset to team picks" button.
* **Portfolio-level evidence for the call:** weighted beta, portfolio volatility √(wᵀΣw), maximum drawdown, average pairwise correlation, market-cap mix, industry weights, and a block-bootstrap 95% confidence interval for the volatility ratio σA/σB (resampling the same dates for both portfolios) — the call is statistically backed if the whole interval sits above 1.

### 6.4 Regimes — current, auto crisis, auto calm

* Equal-length windows (default 252 trading days ≈ 12 months, mirroring the 12-month stress period behind Basel's stressed VaR), so differences are not artefacts of sample size.
* **Current** = the latest 252 trading days.
* **Crisis (auto)** = the 252-day window around the deepest Nifty 50 drawdown in the full sample, starting about 21 trading days before the pre-crash peak. With history from 2007 this is likely the 2008–09 Global Financial Crisis — confirm from the data.
* **Calm (auto)** = the 252-day window, overlapping neither current nor crisis, with the lowest Nifty 50 realised volatility.
* **Regime finder evidence:** full-history Nifty 50 chart with every catalogue event shaded and text-labelled; rolling 12-month volatility; drawdown; India VIX if available; a table of each window's return, volatility, maximum drawdown, worst day and VaR, listing the top 3 candidates of each type so we can defend or override (`OFFICIAL_CRISIS_EVENT` / `OFFICIAL_CALM_EVENT`).

### 6.5 Event catalogue and the event dropdown

* Ship a curated catalogue in `data/events.json`. Each entry: `id`, `name`, `type` (crisis / calm), `search_start`, `search_end`, a two-sentence plain-language story ("what happened and why Indian stocks cared"), and a cited source. Starting list — verify every date range against the Nifty 50 data and a reputable source before including it, and drop or adjust any the data does not support:

  | Event | Type | Search range |
  |---|---|---|
  | Global Financial Crisis (2008–09) | Crisis | Jan 2008 – Mar 2009 |
  | European debt crisis and US credit downgrade (2011) | Crisis | Nov 2010 – Dec 2011 |
  | Taper tantrum and rupee crash (2013) | Crisis | May 2013 – Sep 2013 |
  | China devaluation and global sell-off (2015–16) | Crisis | Mar 2015 – Feb 2016 |
  | Demonetisation (2016) | Crisis | Nov 2016 – Dec 2016 |
  | IL&FS default and NBFC crisis (2018) | Crisis | Aug 2018 – Oct 2018 |
  | COVID-19 crash (2020) | Crisis | Jan 2020 – Mar 2020 |
  | Russia–Ukraine war and rate hikes (2022) | Crisis | Oct 2021 – Jun 2022 |
  | Adani–Hindenburg sell-off (2023) | Crisis | Jan 2023 – Mar 2023 |
  | Foreign-investor sell-off correction (2024–25) | Crisis | Sep 2024 – Mar 2025 |
  | US tariff shock (2025) | Crisis | Mar 2025 – Apr 2025 |
  | Low-volatility rally (2017) | Calm | Jan 2017 – Dec 2017 |
  | Post-election steady market (2014) | Calm | Jun 2014 – Feb 2015 |
  | Low-VIX stretch (2023–24) | Calm | Apr 2023 – Mar 2024 |

  Add any later event the data clearly supports, using the same rules.
* **Data-anchored windows, not typed dates.** For a crisis, find the Nifty 50 peak inside the search range and the trough after it. For a calm event, find the lowest-volatility stretch inside the range. Then build the window two ways:
  * **Standard (default):** 252 trading days starting `EVENT_PRE_DAYS` before the peak — equal length to every other window, so comparisons are fair.
  * **Event only:** peak to trough, padded symmetrically to at least `MIN_WINDOW_DAYS` (126). Show a warning that 99% VaR from fewer than 250 days rests on only a handful of bad days.
* **Overlap rule:** an event window may not overlap the Current window; flag partial overlaps with the auto crisis or another event in the dropdown label.
* **The dropdown** (sidebar on every page, and repeated at the top of pages 6 and 7): "Which past event should we test against?" with grouped options —
  * *Crises:* every crisis in the catalogue, plus "Auto: deepest drawdown"
  * *Calm periods:* every calm event, plus "Auto: calmest year"
  * *Custom:* a date range (minimum 126 trading days)

  Two selectors — one crisis, one calm — default to our team's official picks (§0 or auto). Each option shows its dates and Nifty 50 fall in the label, e.g. "COVID-19 crash · Jan 2020 – Jan 2021 · Nifty −38%". The selected event's story appears as a short card on the left; the anchoring logic (peak, trough, window) appears on the right.
* **All-events scoreboard** (page 6 and page 8): one table and one heatmap of A vs B across every event — ES 99%, volatility, maximum drawdown, ₹ worst fall on the client's amount, and whether the label held. Precomputed for the default portfolios at build time; recomputed with a progress bar for custom picks.

### 6.6 Optimisation (Markowitz)

* Per window: μ = mean daily simple return × 252; Σ = sample covariance × 252 (Ledoit–Wolf shrinkage as an advanced toggle).
* **Constraints, identical in every window:** weights sum to 1; 2% ≤ wᵢ ≤ 25% (keeps all 10+ stocks genuinely held, stops concentration); industry weight ≤ 40%. Check feasibility (n × W_MIN ≤ 1 ≤ n × W_MAX, industry caps achievable) and auto-relax with a visible warning.
* **Today's weights:** A = maximum Sharpe ratio portfolio (return-seeking); B = global minimum-variance portfolio (safety-first). Solve every optimisation with `scipy.optimize` (SLSQP with tight tolerances and several starting points) and check every constraint after each solve. In local tests, cross-check each solution type against cvxpy — maximum Sharpe via the standard convex reformulation — and against the best point on the frontier grid. If no feasible portfolio beats the risk-free rate, fall back to minimum variance and say so.
* **Risk-free rate:** the latest 91-day Treasury bill yield. Look it up (Financial Benchmarks India or Reserve Bank of India auction data) and record value, source and date in `DECISIONS.md` and on the methodology page. If you cannot verify it, use a clearly labelled placeholder and flag it.
* **Efficient frontier:** R_min = return of the minimum-variance portfolio; R_max = the highest return achievable under the constraints (a linear program via `scipy.optimize.linprog`); 60 targets in between, each minimising variance. Add a cloud of 5,000 random feasible portfolios for the chart.

### 6.7 VaR and ES

* **Four methods:** Historical simulation (primary — assumes no distribution); Parametric normal; Monte Carlo with a multivariate Student-t (10,000 draws, degrees of freedom fitted to the window's portfolio returns and floored at 3, covariance matched, fixed seed — captures the fat tails the normal misses); Cornish–Fisher (adjusts for skewness and kurtosis).
* Confidence 95% and 99% (selector), plus ES at 97.5% (the Basel Fundamental Review of the Trading Book standard). Horizon 1 day; 10 days via √10 scaling, with its caveat shown.
* Report losses as positive percentages **and** in ₹ on the client's amount. ES ≥ VaR and 99% ≥ 95% must always hold (tests).
* VaR and frontier maths use constant weights (daily rebalanced); the ₹ crisis replay uses buy-and-hold from the window start. Document both.

### 6.8 Time-travel test #1 — does the label hold?

* Apply today's weights to the selected crisis, selected calm and current returns. For each portfolio × regime: VaR and ES (all methods), volatility, regime beta, maximum drawdown, worst day, average pairwise correlation.
* **Verdict rules** (shown in the Backing): the label holds in a regime if A's historical ES and volatility both exceed B's; "B held up" if its crisis ES and maximum drawdown were smaller than the Nifty 50's.
* **Label stability:** re-run the §6.2 rule with each regime's data — how many of A's stocks were still High risk, and how many of B's still Low risk?
* **Breach test:** calibrate 95% and 99% historical VaR on the calm window and on the current window; count breaches inside the crisis window; run Kupiec's proportion-of-failures test (likelihood ratio, chi-square with 1 degree of freedom, p-value). Plain verdict, e.g. "expected about 3 breaches, got {n}".
* **Crisis replay:** ₹ path of A, B and the Nifty 50 starting from the client's amount through the crisis window; lowest value and largest ₹ fall.
* Every extra measure carries a one-line justification on screen.

### 6.9 Time-travel test #2 — would the optimiser still pick our weights?

* **Target return** = today's expected annual return of today's weights (μ_current · w_current).
* For each historical regime: minimise wᵀΣ_regime w subject to μ_regime · w ≥ min(target, R_max of that regime) and the same constraints. Report which case applies:
   * **Reachable** → the portfolio at the target.
   * **Target below the regime's minimum-variance return** → the optimiser picks minimum variance (beats the target with less risk).
   * **Target above R_max** → "unreachable in this regime; the closest it gets is {x}%". This is a finding, not an error.
* Compare current vs crisis vs calm: weights per stock, industry weights, turnover = ½ Σ|Δw| ("share of the portfolio you would have to trade", also in ₹ on the client's amount), and the efficiency gap — extra volatility today's weights carried in that regime versus the efficient portfolio with the same regime return (plot today's weights on each regime's frontier).
* **Real shift or estimation noise?** Moving-block bootstrap of the current window (500 resamples at build time, 200 for custom picks in the browser; 5-day blocks); on each resample, rerun exactly this target-return optimisation. This gives a 90% band per weight and a noise distribution of turnover. A regime shift is significant if its turnover exceeds the 95th percentile of noise turnover; mark stocks whose regime weight falls outside its band.
* **VaR before and after:** in each regime, VaR and ES with today's weights (before) vs the regime-optimal weights (after). Also on page 5: equal weights (before optimising) vs optimised weights (after).

### 6.10 Investment amount → rupees

* One function turns the amount into ₹ per stock (weight × amount), whole-share counts at the latest snapshot price (rounded down), the money actually invested, leftover cash, and the realised weights after rounding.
* If the amount is too small to buy at least one share of every stock at its target weight, list the stocks that cannot be bought, show the realised weights, and state the smallest amount that buys every stock (the "minimum sensible amount"). Never block the client — warn and carry on.
* Amount modes: the same amount in each portfolio (default, matches the assignment), one total split between A and B, or two separate amounts.
* The Backing explains that VaR and ES in ₹ = the percentage × the amount, so doubling the money doubles the rupee risk but leaves the percentages unchanged.

### 6.11 Investability verdict and recommendation

* Per portfolio: did the label hold (Yes / Partly / No, with evidence) in the selected events and across the all-events scoreboard; are the weights robust (turnover vs noise); worst case in ₹ on the client's amount (crisis-replay low and crisis ES).
* **Client input:** the largest ₹ fall they could live with → which portfolio fits. Suggest a review trigger, e.g. revisit weights when Nifty 50 rolling volatility enters the crisis-regime range.
* All verdict sentences are generated from computed numbers by transparent rules shown in the Backing — no hard-coded findings.
* **Limitations:** survivorship bias (today's constituents looked back to 2007 — stronger the further back the event), estimation error, distribution assumptions, no transaction costs or taxes, price-index benchmark vs dividend-adjusted stock prices, residual data issues listed in the data-quality report.

## 7. The amount-first flow

* On the first visit, the dashboard opens on **Start** before any other page. Left: a single friendly question — "How much would you like to invest?" — an Indian-formatted number input (accepts "15,00,000", "15 lakh", "1.5 crore"), quick-pick chips from `AMOUNT_PRESETS`, the amount mode (same in each / split / separate), validation between `AMOUNT_MIN` and `AMOUNT_MAX` with a plain message, and a "Continue" button. Right (Backing): why the amount matters (₹ figures scale linearly; whole-share rounding is the only non-linear part) and the minimum sensible amount for the current picks.
* Pre-fill from the landing page's query parameter if present, otherwise ₹15,00,000.
* After "Continue", store the amount in session state and go to Home. The sidebar keeps an editable amount on every page; changing it updates every ₹ figure, verdict sentence and chart immediately without recomputing the analytics.
* A "Change amount" link on Home returns to Start.

## 8. Pages — LEFT: Client view | RIGHT: The Backing

**Sidebar on every page:** investment amount (and mode), confidence level, horizon, **crisis-event dropdown, calm-event dropdown**, window mode (standard / event only), "Show the Backing" toggle (off = client view at full width), "Reset to team picks", data as-of date and a Data health badge.

0. **Start — your amount.** Per §7.
1. **Home — the 30-second verdict.** Left: the question in one line; A vs B cards in the client's ₹; three headline findings generated from results (template: "In the {crisis name}, Portfolio A's 1-day 99% Expected Shortfall was {x}% ({₹y} on your {₹amount}) vs {z}% for B — the high-risk label {held / did not hold}"); how to explore in three bullets; team credits; GitHub link. Right: the full pipeline flowchart. The static landing page (§4) shows this same verdict without waiting for Python.
2. **How this app works.** Left: the journey in plain words. Right: the flowchart (on every page, highlight the current step), data sources, cleaning steps in one diagram, key assumptions.
3. **Pick stocks: Industry → Stock → Risk label.** Left: industry selector → stock table (beta, volatility, label, cap bucket, event coverage) → add to A or B; live validation badges. Right: beta and standard-deviation formulas with a worked example for the selected stock using its real numbers; beta-vs-volatility scatter with quadrant lines (High = top-right, Low = bottom-left); the rule; 3-year vs full-history robustness. Concept Boxes: Beta, Volatility.
4. **The risk call.** Left: A vs B evidence cards and industry weights. Right: worked portfolio beta and volatility calculations, correlation heatmaps, the volatility-ratio confidence interval. Concept Box: Diversification.
5. **Optimum weights today.** Left: weights, ₹ allocation on the client's amount, whole-share counts and leftover cash, VaR before vs after optimisation. Right: the optimisation problem in LaTeX, constraints, frontier chart (random cloud, minimum variance, maximum Sharpe, individual stocks, chosen point). Concept Boxes: Efficient frontier, Sharpe ratio.
6. **Test #1 — the risk label.** Top: the crisis and calm dropdowns with the selected events' story cards. Left: crisis-replay ₹ chart from the client's amount, verdict card per regime, label stability, all-events scoreboard. Right: regime-finder evidence and event-anchoring logic, VaR/ES by method, return histograms with VaR/ES lines, breach timeline with the Kupiec test, extra measures with justifications. Concept Boxes: VaR, ES, Fat tails, Correlations in a crisis.
7. **Test #2 — the allocation.** Top: the same dropdowns. Left: weights across current, crisis and calm; industry-weight shift; turnover (% and ₹); VaR before and after; plain verdict. Right: frontier overlay with the target line and today's-weights markers, case logic, bootstrap-band chart. Concept Box: Estimation error.
8. **Verdict and recommendation** — per §6.11, including the all-events scoreboard.
9. **Methodology and data.** Definitions, a glossary with every abbreviation in full, data dictionary, the event catalogue with sources, **Data health** (§5.2) with the full cleaning report, limitations, and a download of every results table as one Excel workbook.

## 9. Design and writing standards

* **Finance Concept Box** — a reusable, visually distinct callout with four parts: *In plain words* (an everyday analogy first) → *Formally* (definition and formula) → *Why an investor cares* → *Where you see it here*. Write for a smart reader with no finance background.
* Plain language before jargon. Write every abbreviation in full at its first use on each page. The left panel speaks to the client ("your ₹15 lakh", using their actual amount); the right panel can be technical.
* **Indian number formatting** through one helper: ₹15,00,000 · ₹1.25 lakh · ₹1.2 crore — and one parser for amount input ("15 lakh", "1.5cr", "15,00,000") (both unit-tested).
* **One colour system:** A = warm coral, B = cool blue, Nifty 50 = grey; crisis shading red, calm shading green, always labelled with text (not colour alone). Defined once in `ui.py` and `.streamlit/config.toml`, with the same theme passed to stlite and used on the landing page.
* **Single source of truth:** the Backing shows the same computed numbers as the client view — never re-typed values.
* **Mobile:** columns must stack cleanly; charts readable at about 380 px wide; the amount input and event dropdowns usable with a thumb.
* **Speed:** the landing page loads in about 2 seconds on a phone. In the dashboard, precomputed results (all catalogue events) render as soon as Python has started; recomputation for custom picks or custom ranges is cached with `st.cache_data`; the custom-pick bootstrap runs on demand with a progress bar. Measure the dashboard's first load, keep it under about 20 seconds on a normal connection, and keep the browser package list and shipped JSON lean.
* **Footer:** "Educational project — not investment advice. Data: Yahoo Finance (via yfinance) and NSE, as of {date}."

## 10. Deliverables

* The working app and a pytest suite, including:
  * unit tests for every cleaning check in §5.2 (each with a fixture containing the problem), the amount parser and formatter, the whole-share allocator and the event-window anchoring;
  * a `streamlit.testing` AppTest smoke test that renders every page without errors, for at least three amounts (₹10,000, ₹15,00,000, ₹1 crore) and for every event in the dropdown;
  * a Playwright smoke test that opens the built site (the landing page, the amount hand-off, plus every dashboard page under stlite) and fails on any Python error.
* `README.md`: the live `github.io` link at the top, a GitHub Actions status badge, three screenshots, what it does in three lines, how to run, method summary, data-cleaning summary, stack, team.
* `docs/METHODOLOGY.md`, `docs/DATA_QUALITY.md`, `DECISIONS.md`, and `docs/RESULTS_SUMMARY.md` (every headline number for the team to quote, including the all-events scoreboard, generated by `scripts/run_analysis.py`).
* `docs/PRESENTATION_GUIDE.md`: a 15-minute run-of-show mapped to pages (≈ 1 min hook incl. entering an amount · 2 min the call · 1.5 min optimum weights · 4 min test #1 incl. switching events live · 3.5 min test #2 · 1.5 min verdict · 1.5 min buffer), the numbers to say, speaker-split placeholders, the 10 questions faculty are most likely to ask with crisp answers (why these periods, why historical VaR, Markowitz instability, survivorship bias, the 2%/25% bounds, √10 scaling, how splits and demergers were handled …), and a backup plan in case the venue Wi-Fi fails (run `streamlit run app.py` locally, plus screenshots).
* `docs/screenshots/`: desktop and phone-width captures of every page (Playwright, if it installs).

## 11. Deployment — GitHub Pages on my GitHub account

* `git init` and commit at the end of every phase. Check `gh auth status`; if `gh` is not logged in, ask me to run `gh auth login` once (the only manual step), then carry on.
* Create the public repository under my account and push (`gh repo create <username>/portfolio-time-machine --public --source . --push`). Public keeps GitHub Pages free and lets the repository double as a portfolio piece.
* Add `.github/workflows/deploy.yml`: on every push to `main` (and on manual run) → set up Python with the pinned versions → run pytest → run `scripts/precompute.py` and `scripts/build_site.py` into `_site/` → Playwright smoke test of `_site/` (if it proves flaky in the workflow, keep it as a local pre-push check and say so) → upload with `actions/upload-pages-artifact` → publish with `actions/deploy-pages`, granting the `pages: write` and `id-token: write` permissions those actions need. The workflow never downloads market data and never re-runs the cleaning step (it uses the committed snapshot).
* Set GitHub Pages to deploy from GitHub Actions (`gh api -X POST repos/<username>/portfolio-time-machine/pages -f build_type=workflow`); if that call fails, give me the exact clicks (Settings → Pages → Source: GitHub Actions).
* Every link and asset path must be relative, because the site is served from the `/portfolio-time-machine/` subpath.
* After the first deploy, watch the run (`gh run watch`), open the live address, and confirm the landing page, the amount hand-off and every dashboard page render. Then set the repository's website field to the live address, add topics (finance, risk-management, value-at-risk, streamlit), put the live link at the top of the README, and add any teammates from §0 as collaborators.
* README section "Updating the site": redeploy = push to `main`; refresh data = run `scripts/fetch_data.py` then `scripts/clean_data.py` locally, review the data-quality diff, commit the new snapshot, push. Freeze the snapshot before the presentation so the slides and the site match.

## 12. Phases — do all of them, in order; test and commit after each

* **P0 Setup and plan:** check Python, conda, git, the GitHub login (`gh auth status`), and internet access to Yahoo Finance and NSE (including the corporate-actions and symbol-change data); write `PLAN.md`; save this brief to `docs/BRIEF.md`.
* **P1 Data:** download pipeline, the full §5.2 cleaning pipeline with its tests, corporate-actions and symbol-change tables with sources, snapshot, data-quality report. Print a summary (stocks downloaded, issues found by category, fixed, excluded) and sanity-check it before moving on.
* **P2 Analytics engine and unit tests:** including the event catalogue with data-anchored windows and the amount allocator. `run_analysis.py` prints every result, including the all-events scoreboard; sanity-check the numbers before building any interface.
* **P3 Interface framework:** amount-first Start page, split layout, navigation, sidebar with event dropdowns, Concept Box, flowchart, formatting — and prove a minimal version (Start + one page + the event dropdown) boots under stlite before building every page.
* **P4 Pages 0–9.**
* **P5 Documents:** presentation guide, data-quality write-up, Excel export, screenshots.
* **P6 Quality assurance:** full tests, AppTest on every page × amounts × events, Playwright on the built site, clean-environment run, the checklist below; fix everything.
* **P7 Deploy:** repository, workflow, Pages setting, live checks and repository polish (§11).

## 13. Acceptance checklist — every box must pass

* [ ] The dashboard asks for the investment amount first; the landing page's amount carries through; changing the amount in the sidebar updates every ₹ figure, whole-share count and verdict sentence.
* [ ] Amounts below the minimum sensible amount warn with the unbuyable stocks listed; invalid inputs show a plain message and never crash.
* [ ] A and B each hold 10+ stocks with zero overlap.
* [ ] Every "high risk / low risk" claim shows a number beside it.
* [ ] The data-quality report covers splits, bonus issues, demergers, symbol changes, bad ticks, decimal errors, stale prices, gaps, duplicates and calendar alignment; every fix cites a source; no unexplained daily move beyond ±20% remains in the snapshot.
* [ ] Yahoo's `Adj Close` and our rebuilt adjustment agree within 0.5% for every kept stock, or the difference is explained.
* [ ] The crisis and calm dropdowns list every verified catalogue event (incl. the 2008–09 Global Financial Crisis and the COVID-19 crash), the auto picks and a custom range; every page updates when the event changes; events a stock can't cover are greyed out with a reason.
* [ ] VaR and ES for both portfolios in the selected crisis, calm and current windows, by four methods; ES ≥ VaR and 99% ≥ 95% everywhere.
* [ ] The all-events scoreboard shows A vs B across every catalogue event.
* [ ] Test #2 shows the target return, handles all three cases, and reports turnover with bootstrap significance.
* [ ] VaR before and after appears on page 5 and page 7.
* [ ] Weights and industry weights shown for current, crisis and calm.
* [ ] Every page has the client view on the left and the Backing (logic, real-number calculation, flowchart, graphic) on the right.
* [ ] Tests: the Nifty 50's beta to itself = 1.00; weights sum to 1 within 1e-6; all bounds respected.
* [ ] No market-data calls at runtime (the only runtime downloads are the stlite and Python packages); no synthetic data; data as-of date visible.
* [ ] Home explains the project to a recruiter in under 30 seconds, with no unexplained jargon.
* [ ] Works at phone width.
* [ ] Verdict text regenerates when stocks, amounts or events change.
* [ ] The live site at `https://<username>.github.io/portfolio-time-machine/` works: landing page in about 2 seconds, the dashboard boots in the browser, every page renders, and the GitHub Actions run is green.
* [ ] `streamlit run app.py` works locally as the offline backup.

When everything passes, give me: the live `github.io` link, the repository link, a summary of the headline results (including the all-events scoreboard), the data-cleaning summary (issues found, fixed, excluded), and the list of assumptions in `DECISIONS.md` and corporate-action adjustments in `data/corporate_actions.csv` our team should double-check.
