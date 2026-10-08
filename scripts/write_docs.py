"""Write docs/METHODOLOGY.md from config + results/default.json, so the numbers the team quotes always match the site.
Run after scripts/precompute.py. (The speaker guide and script come from scripts/write_talk.py, kept off the public repo.)"""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import config as C  # noqa: E402
from src import recommend as RC  # noqa: E402
from src.fmt import pct  # noqa: E402

AMT = C.AMOUNT_A


def methodology(res: dict, meta: dict) -> str:
    ev = res["events"]
    rows = "\n".join(f"| {e['name']} | {e['type']} | {e['search'][0]} → {e['search'][1]} | "
                     f"{' → '.join(e['windows']['standard']) if e['windows']['standard'] else '—'} | "
                     f"{'yes' if e['available'] else 'no — ' + '; '.join(e['notes'])} | {e.get('support', '')} | {e['source']} |"
                     for k, e in ev.items() if not k.startswith("auto"))
    return f"""# Methodology

Snapshot as of **{meta['as_of']}**; history from **{meta['history_start']}** (the first Nifty 50 date on Yahoo, `^NSEI`).
Every number on the site comes from the code in `src/` applied to the committed snapshot in `data/`.

## 1. Data

* **Universe:** today's Nifty 500 (NSE constituent list) with NSE's Industry field; market-cap bucket = Large cap (Nifty 100), Mid cap (Midcap 150), Small cap (Smallcap 250),
  "Flexi" = all three. **Core** universe ({meta['n_core']} stocks) = continuous clean history from {meta['history_start']}; **extended**
  ({meta['n_extended']}) = at least 3 years, usable for custom picks; {meta['n_excluded']} excluded.
* **Prices:** Yahoo Finance daily closes (`auto_adjust=False`) with dividend and split history, anchored to NSE bhavcopy closes and
  rebuilt into total-return prices — see [DATA_QUALITY.md](DATA_QUALITY.md).
* **Benchmark:** Nifty 50 (`^NSEI`), gaps filled from NSE's official index closes. It is a *price* index while stock prices include
  dividends, so beta and "vs Nifty 50" comparisons slightly favour the stocks.
* **Returns:** simple daily returns rₜ = Pₜ/Pₜ₋₁ − 1 (so a portfolio return is exactly Σ wᵢrᵢ); 252 trading days a year.
* **Risk-free rate:** {C.RISK_FREE_RATE:.4%} — {C.RISK_FREE_SOURCE} ({C.RISK_FREE_URL}).

## 2. Stock metrics (any window)

Annualised return μ = mean daily return × 252 (CAGR also reported); volatility σ = daily standard deviation × √252;
beta = Cov(r, r_Nifty) ÷ Var(r_Nifty); maximum drawdown from a ₹1 wealth path; downside deviation below the risk-free rate;
Sharpe = (μ − r_f)/σ; Sortino = (μ − r_f)/σ_down; skewness; excess kurtosis.

## 3. The risk call

Labels are set on **today's data — the trailing {C.CLASSIFICATION_YEARS} years** — so both time-travel tests are out of sample.

* **High risk** = beta ≥ 1.0 **and** volatility ≥ universe median ({pct(res['evidence']['vol_median'])} in this snapshot).
* **Low risk** = beta < 1.0 **and** volatility < universe median. Everything else = Moderate.
* Composite risk score = average of the beta percentile and the volatility percentile.
* **Recommendation (default picker):** A = the top {C.PICK_N} High-risk stocks by composite score, B = the {C.PICK_N} Low-risk stocks
  with the lowest score, inside the client's sectors and sizes (default: all), full-history stocks first, at most
  {C.MAX_PER_INDUSTRY_PICK} per industry (so at least 3 industries each), no overlap. Hand-picking ({C.MIN_STOCKS}–{C.MAX_STOCKS} stocks) is optional.
* **Portfolio evidence:** weighted beta Σwᵢβᵢ, portfolio volatility √(wᵀΣw), maximum drawdown, average pairwise correlation,
  market-cap mix, industry weights and a **moving-block bootstrap** 95% confidence interval for σA/σB ({C.BOOTSTRAP_RESAMPLES}
  resamples of the same dates for both portfolios, {C.BLOCK_DAYS}-day blocks). The call is statistically backed if the whole interval
  is above 1.

## 4. Regimes and events

* Equal-length windows of **{C.REGIME_DAYS} trading days** (≈ 12 months, mirroring the 12-month stress period behind Basel's stressed VaR).
* **Current** = the latest {C.REGIME_DAYS} days ({res['current']['start']} → {res['current']['end']}).
* **Crisis (auto)** = the window around the deepest Nifty 50 drawdown, starting {C.EVENT_PRE_DAYS} trading days before the pre-crash peak.
* **Calm (auto)** = the lowest-volatility {C.REGIME_DAYS}-day window overlapping neither Current nor the auto crisis.
* **Catalogue events** (`data/events.json`) have *search ranges*; the window is anchored on the data — crisis: the deepest peak-to-trough
  fall inside the range; calm: the calmest stretch. *Standard* windows are {C.REGIME_DAYS} days (crisis: from {C.EVENT_PRE_DAYS} days
  before the peak; calm: the calmest {C.REGIME_DAYS}-day window centred in the range). *Event-only* windows run peak → trough (calm: the
  calmest {C.CALM_ANCHOR_DAYS}-day stretch), padded to at least {C.MIN_WINDOW_DAYS} days. No window overlaps Current; a crisis is kept only
  if the Nifty 50 fell at least 7% inside its range.

| Event | Type | Search range | Standard window | Used | Data check | Source |
|---|---|---|---|---|---|---|
{rows}

## 5. Optimisation (Markowitz)

μ = mean daily simple return × 252; Σ = sample covariance × 252 (Ledoit–Wolf shrinkage available, implemented in NumPy).
Constraints in every window: Σw = 1; {C.W_MIN:.0%} ≤ wᵢ ≤ {C.W_MAX:.0%}; industry weight ≤ {C.INDUSTRY_MAX:.0%}; feasibility is checked and
relaxed with a visible warning if needed. **A = maximum expected return** (a linear program, `scipy.optimize.linprog`), **B = global
minimum variance**, **C = maximum Sharpe ratio over A's and B's stocks together** (minimum weight {C.C_W_MIN:.0%}, since 30 × 2% would lock
60% into an equal split). B and C are solved with SciPy SLSQP (analytic gradients, several feasible starting points, tight tolerances),
every constraint re-checked after the solve; the test suite cross-checks them against cvxpy (maximum Sharpe via the convex
reformulation) and the frontier grid, and A against random feasible portfolios. Parametric VaR is also shown by the matrix method
taught in class: Σ = DᵀD/(N−1), σ²ₚ = wᵀΣw, μₚ = wᵀμ, VaR = μₚ + zσₚ (daily), which equals the 'Parametric normal' method exactly. Frontier: R_min = minimum-variance return,
R_max = highest achievable return (linear program, `scipy.optimize.linprog`), {C.FRONTIER_POINTS} targets in between; plus
{C.RANDOM_PORTFOLIOS:,} random feasible portfolios.

## 6. VaR and ES

Losses are positive fractions; ₹ figures = fraction × the client's amount. 1-day horizon; 10-day via √10 (assumes i.i.d. days).
Confidence 95% and 99%, plus ES at 97.5% (Basel FRTB).

1. **Historical simulation** (primary, the class convention): VaR = −(the (1−c) percentile of daily returns, linear interpolation as in
   Excel `PERCENTILE` / pandas `quantile`); ES = −(mean of the returns at or below that percentile).
2. **Parametric normal:** VaR = −(μ + σz), ES = −μ + σφ(z)/(1−c).
3. **Monte Carlo, multivariate Student-t:** {C.MC_DRAWS:,} draws, degrees of freedom fitted by maximum likelihood to the window's portfolio
   returns and floored at {C.T_DOF_FLOOR:g}, covariance matched to the sample, seed {C.SEED}.
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
moving-block bootstrap of the current window ({C.BOOTSTRAP_RESAMPLES} resamples, {C.BLOCK_DAYS}-day blocks) re-solving the same problem →
90% weight bands and a turnover noise distribution; a shift is significant if its turnover exceeds the noise 95th percentile.

## 9. Recommendation rules

{chr(10).join(f'* **{k.replace("_", " ").capitalize()}.** {v}' for k, v in RC.RULES.items())}

## 10. Limitations

{chr(10).join(f'* **{a}.** {b}' for a, b in RC.LIMITATIONS)}
"""


def main() -> None:
    res = json.loads((C.RESULTS_DIR / "default.json").read_text())
    meta = json.loads((C.DATA_DIR / "metadata.json").read_text())
    (C.DOCS_DIR / "METHODOLOGY.md").write_text(methodology(res, meta))
    print("wrote docs/METHODOLOGY.md")


if __name__ == "__main__":
    main()
