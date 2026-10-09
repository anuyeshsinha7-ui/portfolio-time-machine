# Methodology

Snapshot as of **2026-10-08**; history from **2007-09-17** (the first Nifty 50 date on Yahoo, `^NSEI`).
Every number on the site comes from the code in `src/` applied to the committed snapshot in `data/`.

## 1. Data

* **Universe:** today's Nifty 500 (NSE constituent list) with NSE's Industry field; market-cap bucket = Large cap (Nifty 100), Mid cap (Midcap 150), Small cap (Smallcap 250),
  "Flexi" = all three. **Core** universe (231 stocks) = continuous clean history from 2007-09-17; **extended**
  (200) = at least 3 years, usable for custom picks; 70 excluded.
* **Prices:** Yahoo Finance daily closes (`auto_adjust=False`) with dividend and split history, anchored to NSE bhavcopy closes and
  rebuilt into total-return prices — see [DATA_QUALITY.md](DATA_QUALITY.md).
* **Benchmark:** Nifty 50 (`^NSEI`), gaps filled from NSE's official index closes. It is a *price* index while stock prices include
  dividends, so beta and "vs Nifty 50" comparisons slightly favour the stocks.
* **Returns:** simple daily returns rₜ = Pₜ/Pₜ₋₁ − 1 (so a portfolio return is exactly Σ wᵢrᵢ); 252 trading days a year.
* **Risk-free rate:** 5.5747% — Reserve Bank of India, '91-Day, 182-Day and 364-Day T-Bill Auction Result: Cut-off', press release 2026-2027/1268, 7 Oct 2026 — 91-day implicit yield 5.5747% (https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63746).

## 2. Stock metrics (any window)

Annualised return μ = mean daily return × 252 (CAGR also reported); volatility σ = daily standard deviation × √252;
beta = Cov(r, r_Nifty) ÷ Var(r_Nifty); maximum drawdown from a ₹1 wealth path; downside deviation below the risk-free rate;
Sharpe = (μ − r_f)/σ; Sortino = (μ − r_f)/σ_down; skewness; excess kurtosis.

## 3. The risk call

Labels are set on **today's data — the trailing 3 years** — so both time-travel tests are out of sample.

* **High risk** = beta ≥ 1.0 **and** volatility ≥ universe median (35.1% in this snapshot).
* **Low risk** = beta < 1.0 **and** volatility < universe median. Everything else = Moderate.
* Composite risk score = average of the beta percentile and the volatility percentile.
* **Recommendation (default picker):** A = the top 15 High-risk stocks by composite score, B = the 15 Low-risk stocks
  with the lowest score, inside the client's sectors and sizes (default: all), full-history stocks first, at most
  5 per industry (so at least 3 industries each), no overlap. Hand-picking (10–20 stocks) is optional.
* **Portfolio evidence:** weighted beta Σwᵢβᵢ, portfolio volatility √(wᵀΣw), maximum drawdown, average pairwise correlation,
  market-cap mix, industry weights and a **moving-block bootstrap** 95% confidence interval for σA/σB (500
  resamples of the same dates for both portfolios, 5-day blocks). The call is statistically backed if the whole interval
  is above 1.

## 4. Regimes and events

* Equal-length windows of **252 trading days** (≈ 12 months, mirroring the 12-month stress period behind Basel's stressed VaR).
* **Current** = the latest 252 days (2025-09-30 → 2026-10-08).
* **Crisis (auto)** = the window around the deepest Nifty 50 drawdown, starting 21 trading days before the pre-crash peak.
* **Calm (auto)** = the lowest-volatility 252-day window overlapping neither Current nor the auto crisis.
* **Catalogue events** (`data/events.json`) have *search ranges*; the window is anchored on the data — crisis: the deepest peak-to-trough
  fall inside the range; calm: the calmest stretch. *Standard* windows are 252 days (crisis: from 21 days
  before the peak; calm: the calmest 252-day window centred in the range). *Event-only* windows run peak → trough (calm: the
  calmest 126-day stretch), padded to at least 126 days. No window overlaps Current; a crisis is kept only
  if the Nifty 50 fell at least 7% inside its range.

| Event | Type | Search range | Standard window | Used | Data check | Source |
|---|---|---|---|---|---|---|
| Global Financial Crisis (2008–09) | crisis | 2008-01-01 → 2009-03-31 | 2007-12-06 → 2008-12-17 | yes | Nifty 50 fell 59.9% peak to trough inside the search range | https://en.wikipedia.org/wiki/2008_financial_crisis |
| European debt crisis and US credit downgrade (2011) | crisis | 2010-11-01 → 2011-12-31 | 2010-10-08 → 2011-10-14 | yes | Nifty 50 fell 27.9% peak to trough inside the search range | https://en.wikipedia.org/wiki/August_2011_stock_markets_fall |
| Taper tantrum and rupee crash (2013) | crisis | 2013-05-01 → 2013-09-30 | 2013-04-15 → 2014-04-23 | yes | Nifty 50 fell 14.6% peak to trough inside the search range | https://en.wikipedia.org/wiki/Taper_tantrum |
| China devaluation and global sell-off (2015–16) | crisis | 2015-03-01 → 2016-02-29 | 2015-01-30 → 2016-02-08 | yes | Nifty 50 fell 22.5% peak to trough inside the search range | https://en.wikipedia.org/wiki/2015%E2%80%932016_stock_market_selloff |
| Demonetisation (2016) | crisis | 2016-11-01 → 2016-12-31 | 2016-09-28 → 2017-10-04 | yes | Nifty 50 fell 8.3% peak to trough inside the search range | https://en.wikipedia.org/wiki/2016_Indian_banknote_demonetisation |
| IL&FS default and NBFC crisis (2018) | crisis | 2018-08-01 → 2018-10-31 | 2018-07-26 → 2019-08-07 | yes | Nifty 50 fell 14.6% peak to trough inside the search range | https://en.wikipedia.org/wiki/Infrastructure_Leasing_%26_Financial_Services |
| COVID-19 crash (2020) | crisis | 2020-01-01 → 2020-03-31 | 2019-12-13 → 2020-12-15 | yes | Nifty 50 fell 38.4% peak to trough inside the search range | https://en.wikipedia.org/wiki/2020_stock_market_crash |
| Russia–Ukraine war and rate hikes (2022) | crisis | 2021-10-01 → 2022-06-30 | 2021-09-16 → 2022-09-20 | yes | Nifty 50 fell 17.2% peak to trough inside the search range | https://en.wikipedia.org/wiki/2022_stock_market_decline |
| Adani–Hindenburg sell-off (2023) | crisis | 2023-01-01 → 2023-03-31 | 2022-12-05 → 2023-12-11 | yes | Nifty 50 fell 7.1% peak to trough inside the search range | https://en.wikipedia.org/wiki/Hindenburg_Research |
| Foreign-investor sell-off correction (2024–25) | crisis | 2024-09-01 → 2025-03-31 | 2024-08-28 → 2025-09-01 | yes | Nifty 50 fell 15.8% peak to trough inside the search range | NSDL FPI Monitor, foreign portfolio investment net equity flows Oct 2024 – Feb 2025 (https://www.fpi.nsdl.co.in/) |
| US tariff shock (2025) | crisis | 2025-03-01 → 2025-04-30 | 2024-09-25 → 2025-09-29 | no — standard: moved 103 trading days earlier so it does not overlap the Current window; dropped: the Nifty 50 data does not support this as a crisis (fall under the threshold) | Nifty 50 fell 6.4% peak to trough inside the search range | https://en.wikipedia.org/wiki/Liberation_Day_tariffs |
| Low-volatility rally (2017) | calm | 2017-01-01 → 2017-12-31 | 2017-01-30 → 2018-02-01 | yes | lowest 126-day Nifty 50 volatility in the range 7.8% vs full-sample median 15.4% | https://www.nseindia.com/reports-indices-historical-vix |
| Post-election steady market (2014) | calm | 2014-06-01 → 2015-02-28 | 2013-12-02 → 2014-12-15 | yes | lowest 126-day Nifty 50 volatility in the range 12.3% vs full-sample median 15.4% | https://en.wikipedia.org/wiki/2014_Indian_general_election |
| Low-VIX stretch (2023–24) | calm | 2023-04-01 → 2024-03-31 | 2022-11-25 → 2023-12-01 | yes | lowest 126-day Nifty 50 volatility in the range 8.1% vs full-sample median 15.4% | https://www.nseindia.com/reports-indices-historical-vix |

## 5. Optimisation (Markowitz)

μ = mean daily simple return × 252; Σ = sample covariance × 252 (Ledoit–Wolf shrinkage available, implemented in NumPy).
Constraints in every window: Σw = 1; 2% ≤ wᵢ ≤ 25%; industry weight ≤ 40%; feasibility is checked and
relaxed with a visible warning if needed. **A = maximum Sharpe ratio, B = global minimum variance**, solved with SciPy SLSQP (analytic
gradients, several feasible starting points, tight tolerances), every constraint re-checked after the solve; the test suite cross-checks
both against cvxpy (maximum Sharpe via the convex reformulation) and the frontier grid. Frontier: R_min = minimum-variance return,
R_max = highest achievable return (linear program, `scipy.optimize.linprog`), 60 targets in between; plus
5,000 random feasible portfolios.

## 6. VaR and ES

Losses are positive fractions; ₹ figures = fraction × the client's amount. 1-day horizon; 10-day via √10 (assumes i.i.d. days).
Confidence 95% and 99%, plus ES at 97.5% (Basel FRTB).

1. **Historical simulation** (primary): VaR = the k-th worst return, k = ⌊n(1−c)⌋; ES = mean of the k worst.
2. **Parametric normal:** VaR = −(μ + σz), ES = −μ + σφ(z)/(1−c).
3. **Monte Carlo, multivariate Student-t:** 10,000 draws, degrees of freedom fitted by maximum likelihood to the window's portfolio
   returns and floored at 3, covariance matched to the sample, seed 42.
4. **Cornish–Fisher:** z_CF = z + (z²−1)S/6 + (z³−3z)K/24 − (2z³−5z)S²/36; ES averages the monotone CF quantile over the tail.

VaR and the frontier use constant (daily-rebalanced) weights; the ₹ crisis replay is buy-and-hold from the window start.
Tests enforce ES ≥ VaR and 99% ≥ 95% for every method.

## 7. Test #1 — does the label hold?

Today's weights applied to the current, crisis and calm windows. For each portfolio × period: VaR/ES (all methods), volatility,
regime beta, maximum drawdown, worst day, average pairwise correlation. **The label holds** if A's historical ES and volatility both exceed
B's; **B held up** if its crisis ES and drawdown were below the Nifty 50's. **Label stability** re-runs the rule on each period's data.
**Breach test:** 95%/99% historical VaR calibrated on the calm and current windows, breaches counted in the crisis, Kupiec's
proportion-of-failures likelihood ratio (χ², 1 d.f.).

## 8. Test #2 — would the optimiser still pick our weights?

Target = μ_current · w_today. In each period: minimise wᵀΣ_period w s.t. μ_period·w ≥ min(target, R_max,period) and the same constraints;
the case is *reachable*, *below the minimum-variance return* (optimiser picks minimum variance) or *unreachable* (closest = R_max).
Reported: weights, industry weights, turnover ½Σ|Δw| (also in ₹), the efficiency gap (extra volatility of today's weights vs the
efficient portfolio with the same period return) and VaR/ES before (today's weights) and after (period-optimal). **Noise check:**
moving-block bootstrap of the current window (500 resamples, 5-day blocks) re-solving the same problem →
90% weight bands and a turnover noise distribution; a shift is significant if its turnover exceeds the noise 95th percentile.

## 9. Recommendation rules

* **Label holds.** The high-risk label holds in a period if Portfolio A's Expected Shortfall (99%, historical) and its volatility are both higher than Portfolio B's.
* **B held up.** Portfolio B 'held up' in a crisis if its Expected Shortfall (99%, historical) and its biggest fall were both smaller than the Nifty 50's in the same period.
* **Yes partly no.** Label verdict. Yes: the label held in the chosen crisis, the chosen calm period and at least 80% of all periods in the list. Partly: it held in at least one chosen period or at least half of all periods. Otherwise No.
* **Robust.** The weights are robust in a period if the share of money you would need to move to reach that period's best weights is no more than the 95th percentile of what random noise in the data alone would make you move (measured by reshuffling today's data).
* **Fit.** A portfolio fits you if its worst fall in rupees in a crisis replay (on your amount) is no bigger than the fall you said you could live with. If both fit, we suggest A because it is expected to earn more. If only B fits, we suggest B. If neither fits, we show the largest amount that keeps B's worst fall within your limit.
* **Trigger.** When to look again: review the weights when the Nifty 50's 3-month volatility goes above the lowest 3-month volatility seen during the chosen crisis.
* **As is.** We call it recommended as it is when all four checks pass. (1) A is clearly riskier than B: the 95% bootstrap range for A's volatility divided by B's stays above 1. (2) A is expected to earn more than a safe Treasury bill (Sharpe above 0). (3) B moved less than the Nifty 50 over the latest 12 months. (4) Both portfolios meet every weight limit without loosening any. If a check fails, we say 'recommended with caution' and name the check.

## 10. Limitations

* **Survivorship bias.** We look at today's Nifty 500 companies back to 2007, so companies that left the index or failed are missing. This matters more the further back the period goes, so the 2008 results make both portfolios look best.
* **Estimation error.** Expected returns and how stocks move together are worked out from only 252 days, so they are rough. The noise bands on the Rebalance screen show how much the weights move from noise alone.
* **Assumptions about returns.** Historical VaR assumes the past period is a fair guide. The normal method ignores extreme days. Student-t and Cornish–Fisher are approximations. Multiplying by √10 for 10 days assumes each day is independent of the last.
* **Costs and taxes.** We leave out brokerage, market impact, securities transaction tax and capital-gains tax.
* **Benchmark mismatch.** Our stock prices include reinvested dividends, but the Nifty 50 index does not, so comparisons with the Nifty slightly favour the stocks.
* **Data.** Any data problems we could not fix are listed in the data-quality report (on the About the data screen).
