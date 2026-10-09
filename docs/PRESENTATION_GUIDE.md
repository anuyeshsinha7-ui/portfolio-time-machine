# Presentation guide — 15 minutes

Live site: https://anuyeshsinha7-ui.github.io/portfolio-time-machine/ · Backup: `streamlit run app.py` (offline) + `docs/screenshots/`.
All numbers below are for **₹15,00,000 in each portfolio** and the official periods: crisis = **2008 crash (deepest in the data)**
(2007-12-06 → 2008-12-17), calm = **2017–18 calm (calmest year in the data)** (2017-01-30 → 2018-02-01). Regenerate with
`python scripts/write_docs.py` after any data refresh.

## Run of show

| Time | Speaker | Page | What to do and say |
|---|---|---|---|
| 0:00–1:00 | [Name 1] | Landing → Start | Hook: "Does 'safe' stay safe when the market crashes?" Type an amount on the landing page (try 15 lakh), open the dashboard, show it arrives on Start. |
| 1:00–3:00 | [Name 1] | Pick stocks → The risk call | The rule (beta ≥ 1 and volatility ≥ median). A: weighted beta **1.59**, volatility **33.7%**; B: **0.58**, **11.3%**. σA/σB = **2.97**, 95% CI **2.75–3.24** → statistically backed. |
| 3:00–4:30 | [Name 2] | Optimum weights | A = max Sharpe (expected return 39.1%, Sharpe 1.17); B = min variance (volatility 11.1%). Show the frontier and whole-share allocation. VaR before/after: B's 99% VaR 2.42% → 2.29%. |
| 4:30–8:30 | [Name 3] | Test #1 | Crisis replay: ₹15,00,000 in A falls to **₹4,75,428**, B to **₹11,16,596**, Nifty −57.6%. ES99: A **10.0%** vs B **7.1%** → label held. Breach test: VaR fitted in calm → A **18**, B **35** breaches vs ≈2.5 expected. **Switch the event live to COVID-19** (ES99 A 11.9% vs B 8.2%). Scoreboard: label held in **13/13** events; B beat the Nifty in **6/10** crises. |
| 8:30–12:00 | [Name 4] | Test #2 | Target = 39.1% for A, −0.7% for B. In the crisis A's target is **unreachable**; turnover **41%** (₹6.21 lakh) vs noise p95 51%. B: **reachable**, turnover 44% vs 41%. Show bootstrap bands. |
| 12:00–13:30 | [Name 4] | Verdict | Label: **Yes**; 'safe stayed safe': **Partly**. Enter a loss limit (e.g. ₹4 lakh) and show which portfolio fits. Review trigger. |
| 13:30–15:00 | all | — | Buffer / questions. |

## Ten questions faculty are likely to ask

1. **Why these periods?** We did not choose them by hand: the crisis is the deepest Nifty 50 drawdown in the data and the calm year is the
   lowest-volatility 252-day window that overlaps neither. Both are equal length (252 days, as in Basel's stressed VaR). The dropdown lets you
   test 13 other data-checked events.
2. **Why historical VaR as the primary method?** It assumes no distribution, so it captures the fat tails and skew of real crisis days; we
   show normal, Student-t Monte Carlo and Cornish–Fisher beside it — the normal method visibly understates crisis risk.
3. **Isn't Markowitz unstable?** Yes — that is Test #2's point. We measure the instability with a block bootstrap and only call a regime
   shift real if turnover beats the 95th percentile of noise. The 2%/25% bounds and the 40% industry cap also stop corner solutions.
4. **Survivorship bias?** Today's Nifty 500 looked back to 2007 excludes companies that failed or dropped out, so history flatters both
   portfolios, most in 2008. We state it on the Methodology page.
5. **Why 2% and 25% bounds?** 2% keeps all 10+ stocks genuinely held (otherwise the optimiser concentrates in 3–4 names); 25% stops
   one stock dominating. Feasibility is checked and relaxed with a warning.
6. **Why √10 scaling?** It is the regulatory convention, but it assumes independent days; in crises losses cluster, so true 10-day risk is
   usually larger — we show the caveat on screen.
7. **How were splits and demergers handled?** Yahoo's prices were anchored to NSE's official closes month by month (59 hidden level
   errors in 43 stocks found and fixed). Every split, bonus and rights issue was rebuilt from NSE's records; demergers since 2023 use NSE's
   special pre-open price-discovery ratio (e.g. Reliance 20 Jul 2023: ₹2,580 vs ₹2,841.85); older ones drop that single day's return.
8. **Why is the label decided on the last three years?** So the time-travel tests are out of sample — the label is set today and tested on
   the past. Full-history values are shown as a robustness check.
9. **Is the volatility difference significant?** Yes: the 95% bootstrap interval for σA/σB (2.75–3.24) lies entirely above 1.
10. **Why is A's beta only 0.85 in the crisis window?** Labels are set on today's data. Re-running the rule on crisis-window
    data, only 3 of 15 of A's stocks were High risk then, while 15
    of 15 of B's stayed Low risk. A was still the riskier portfolio on outcomes (higher ES, volatility and
    drawdown), so the label held — but "high beta" is not a permanent property of a stock.

## If the venue Wi-Fi fails

1. Run locally: `conda activate fra && streamlit run app.py` (identical code and data; no internet needed after install).
2. Or open the screenshots in `docs/screenshots/` (desktop and phone, every page).
3. Freeze the snapshot before the presentation (do not re-run `fetch_data.py`), so the slides, this guide and the site match.
