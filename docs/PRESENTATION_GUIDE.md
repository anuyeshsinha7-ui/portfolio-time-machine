# Presentation guide — 15 minutes

Live site: https://anuyeshsinha7-ui.github.io/portfolio-time-machine/ · Backup: `streamlit run app.py` (offline) + `docs/screenshots/`.
All numbers below are for **₹15,00,000 in each portfolio** and the official periods: crisis = **2008 crash (deepest in the data)**
(2007-12-06 → 2008-12-17), calm = **2017–18 calm (calmest year in the data)** (2017-01-30 → 2018-02-01). Regenerate with
`python scripts/write_docs.py` after any data refresh.

## Run of show

| Time | Speaker | Page | What to do and say |
|---|---|---|---|
| 0:00–1:00 | Anu Yesh Sinha | Landing → Start | Hook: "Does 'safe' stay safe when the market crashes?" Type an amount on the landing page (try 15 lakh), open the dashboard, show it arrives on Start. |
| 1:00–3:00 | Rishabh Agrawal | Pick stocks → The risk call | The rule (beta ≥ 1 and volatility ≥ median). A: weighted beta **1.57**, volatility **34.1%**; B: **0.58**, **11.4%**. σA/σB = **2.99**, 95% CI **2.74–3.26** → statistically backed. |
| 3:00–4:30 | Ritul Bokde | Optimum weights | A = max return (expected return 35.8%, volatility 29.2%); B = min variance (volatility 11.2%); C = max Sharpe over both sets (return 38.2%, Sharpe 1.47). Walk the matrix steps wᵀΣw → VaR on the Backing. Show the frontier and whole-share allocation. VaR before/after: B's 99% VaR 1.91% → 1.83%. |
| 4:30–8:30 | Liash Roy | Test #1 | Crisis replay: ₹15,00,000 in A falls to **₹4,67,565**, B to **₹11,03,649**, Nifty −57.6%. ES99: A **9.5%** vs B **6.8%** → label held. Breach test: VaR fitted in calm → A **25**, B **37** breaches vs ≈2.5 expected. **Switch the event live to COVID-19** (ES99 A 11.5% vs B 6.7%). Scoreboard: label held in **13/13** events; B beat the Nifty in **6/10** crises. |
| 8:30–12:00 | Baidurja Biswas | Test #2 | Target = 35.8% for A, −0.1% for B. In the crisis A's target is **unreachable**; turnover **46%** (₹6.9 lakh) vs noise p95 56%. B: **reachable**, turnover 43% vs 43%. Show bootstrap bands. |
| 12:00–13:30 | Kasutabh Datta | Verdict | Label: **Yes**; 'safe stayed safe': **Partly**. Enter a loss limit (e.g. ₹4 lakh) and show which portfolio fits. Review trigger. |
| 13:30–15:00 | all | — | Buffer / questions. |

## Ten questions faculty are likely to ask

1. **Why these periods?** We did not choose them by hand: the crisis is the deepest Nifty 50 drawdown in the data and the calm year is the
   lowest-volatility 252-day window that overlaps neither. Both are equal length (252 days, as in Basel's stressed VaR). The dropdown lets you
   test 13 other data-checked events.
2. **Why historical VaR as the primary method?** It assumes no distribution, so it captures the fat tails and skew of real crisis days; we
   show normal, Student-t Monte Carlo and Cornish–Fisher beside it — the normal method visibly understates crisis risk.
3. **Isn't Markowitz unstable?** Yes — that is Test #2's point. We measure the instability with a block bootstrap and only call a regime
   shift real if turnover beats the 95th percentile of noise. The 2%/25% bounds and the 40% industry cap limit corner solutions;
   A's maximum-return mix is still a corner by nature (25% in the three best past performers), which is why it is the high-risk one.
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
9. **Is the volatility difference significant?** Yes: the 95% bootstrap interval for σA/σB (2.74–3.26) lies entirely above 1.
10. **Why is A's beta only 0.86 in the crisis window?** Labels are set on today's data. Re-running the rule on crisis-window
    data, only 3 of 15 of A's stocks were High risk then, while 15
    of 15 of B's stayed Low risk. A was still the riskier portfolio on outcomes (higher ES, volatility and
    drawdown), so the label held — but "high beta" is not a permanent property of a stock.

## If the venue Wi-Fi fails

1. Run locally: `conda activate fra && streamlit run app.py` (identical code and data; no internet needed after install).
2. Or open the screenshots in `docs/screenshots/` (desktop and phone, every page).
3. Freeze the snapshot before the presentation (do not re-run `fetch_data.py`), so the slides, this guide and the site match.
