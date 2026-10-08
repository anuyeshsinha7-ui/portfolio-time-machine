# Plan — Portfolio Time Machine

Source of truth: [`docs/BRIEF.md`](docs/BRIEF.md). Assignment rules (§2) win any conflict.
Decisions and defaults taken along the way: [`DECISIONS.md`](DECISIONS.md).

## Environment (checked in P0, 8 Oct 2026)

| Item | Status |
|---|---|
| Python | conda env `fra`, Python 3.13 (matches Pyodide 0.29.3 inside stlite 1.9.2) |
| Browser runtime | stlite `@stlite/browser@1.9.2` → Streamlit 1.62.0, Pyodide 0.29.3 (pandas 2.3.3, NumPy 2.2.5, SciPy 1.14.1) |
| GitHub | `gh` logged in as `anuyeshsinha7-ui`, scopes repo + workflow |
| Yahoo Finance | reachable (chart API 200) |
| NSE archives | reachable (`ind_nifty200list.csv`, `symbolchange.csv`) |
| NSE corporate-actions API | reachable with a browser User-Agent and Referer |
| niftyindices.com | reachable |
| Risk-free rate | RBI 91-day T-bill cut-off 5.5747% (auction of 7 Oct 2026) |

## Phases

| Phase | Output | Exit test |
|---|---|---|
| P0 Setup | repo skeleton, env, PLAN, DECISIONS, brief saved | env imports work |
| P1 Data | `scripts/fetch_data.py`, `src/cleaning.py`, `scripts/clean_data.py`, snapshot + metadata, quality report, corporate actions + symbol changes with sources | cleaning unit tests; summary sanity-checked |
| P2 Analytics | `src/*` engine, `data/events.json`, `scripts/precompute.py`, `scripts/run_analysis.py` | unit tests (beta of Nifty = 1, weights sum to 1, bounds, ES ≥ VaR …); numbers sanity-checked |
| P3 Interface frame | `app.py`, `src/ui.py`, Start page + one page under stlite | minimal app boots in stlite in a real browser |
| P4 Pages 0–9 | `views/00_start.py … 09_methodology.py` | AppTest renders every page |
| P5 Documents | METHODOLOGY, DATA_QUALITY, RESULTS_SUMMARY, PRESENTATION_GUIDE, Excel export, screenshots | files generated from results |
| P6 QA | full pytest, AppTest pages × amounts × events, Playwright on `_site/`, acceptance checklist | all green |
| P7 Deploy | public repo, Actions workflow, Pages, live checks, README polish | live site works; Actions run green |

## Data flow

```
yfinance + NSE ──fetch_data.py──▶ data/raw/ (gitignored)
                 clean_data.py ─▶ data/prices.csv.gz, data/benchmark.csv.gz, data/universe.csv,
                                  data/metadata.json, data/data_quality_report.csv,
                                  data/corporate_actions.csv, data/symbol_changes.csv
                 precompute.py ─▶ results/*.json  (default portfolios × every event)
                 build_site.py ─▶ _site/ (landing page + stlite app + snapshot + results)
```
