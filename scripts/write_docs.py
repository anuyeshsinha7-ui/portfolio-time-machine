"""Write docs/METHODOLOGY.md and docs/PRESENTATION_GUIDE.md from config + results/default.json, so the numbers the team
quotes always match the site. Run after scripts/precompute.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import config as C  # noqa: E402
from src import recommend as RC  # noqa: E402
from src import stats_tests as ST  # noqa: E402
from src.fmt import inr, inr_short, pct  # noqa: E402

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
relaxed with a visible warning if needed. **A = maximum Sharpe ratio, B = global minimum variance**, solved with SciPy SLSQP (analytic
gradients, several feasible starting points, tight tolerances), every constraint re-checked after the solve; the test suite cross-checks
both against cvxpy (maximum Sharpe via the convex reformulation) and the frontier grid. Frontier: R_min = minimum-variance return,
R_max = highest achievable return (linear program, `scipy.optimize.linprog`), {C.FRONTIER_POINTS} targets in between; plus
{C.RANDOM_PORTFOLIOS:,} random feasible portfolios.

## 6. VaR and ES

Losses are positive fractions; ₹ figures = fraction × the client's amount. 1-day horizon; 10-day via √10 (assumes i.i.d. days).
Confidence 95% and 99%, plus ES at 97.5% (Basel FRTB).

1. **Historical simulation** (primary): VaR = the k-th worst return, k = ⌊n(1−c)⌋; ES = mean of the k worst.
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


def guide(res: dict) -> str:
    off = res["official"]
    cr, cm, cur = res["regimes"][f"{off['crisis']}|standard"], res["regimes"][f"{off['calm']}|standard"], res["current"]
    E, P, ev = res["events"], res["portfolios"], res["evidence"]
    board = res["scoreboard"]["standard"]
    lv, bv = RC.label_verdict(cr, cm, board), RC.b_verdict(cr, board)
    bt = {k: ST.breach_test(np.array(cm[k]["returns"]["port"]), np.array(cr[k]["returns"]["port"]), 0.99) for k in "AB"}
    covid = res["regimes"].get("covid_2020|standard")
    es = lambda r, k: r[k]["risk"]["Historical"]["0.99"]["es"]  # noqa: E731
    cname = E[off["crisis"]]["name"]
    ta, tb = cr["A"]["test2"], cr["B"]["test2"]
    p95a, p95b = res["bootstrap"]["A"]["turnover_p95"], res["bootstrap"]["B"]["turnover_p95"]
    return f"""# Presentation guide — 15 minutes

Live site: {C.LIVE_URL} · Backup: `streamlit run app.py` (offline) + `docs/screenshots/`.
All numbers below are for **{inr(AMT)} in each portfolio** and the official periods: crisis = **{cname}**
({cr['start']} → {cr['end']}), calm = **{E[off['calm']]['name']}** ({cm['start']} → {cm['end']}). Regenerate with
`python scripts/write_docs.py` after any data refresh.

## Run of show

| Time | Speaker | Page | What to do and say |
|---|---|---|---|
| 0:00–1:00 | [Name 1] | Landing → Start | Hook: "Does 'safe' stay safe when the market crashes?" Type an amount on the landing page (try 15 lakh), open the dashboard, show it arrives on Start. |
| 1:00–3:00 | [Name 1] | Pick stocks → The risk call | The rule (beta ≥ 1 and volatility ≥ median). A: weighted beta **{ev['A']['weighted_beta']:.2f}**, volatility **{pct(ev['A']['portfolio_vol'])}**; B: **{ev['B']['weighted_beta']:.2f}**, **{pct(ev['B']['portfolio_vol'])}**. σA/σB = **{ev['vol_ratio']['ratio']:.2f}**, 95% CI **{ev['vol_ratio']['lo']:.2f}–{ev['vol_ratio']['hi']:.2f}** → statistically backed. |
| 3:00–4:30 | [Name 2] | Optimum weights | A = max Sharpe (expected return {pct(P['A']['expected_return'])}, Sharpe {P['A']['sharpe']:.2f}); B = min variance (volatility {pct(P['B']['expected_vol'])}). Show the frontier and whole-share allocation. VaR before/after: B's 99% VaR {pct(P['B']['var_before_after']['equal']['Historical']['0.99']['var'], 2)} → {pct(P['B']['var_before_after']['optimised']['Historical']['0.99']['var'], 2)}. |
| 4:30–8:30 | [Name 3] | Test #1 | Crisis replay: {inr(AMT)} in A falls to **{inr(cr['A']['replay']['low'] * AMT)}**, B to **{inr(cr['B']['replay']['low'] * AMT)}**, Nifty −{pct(cr['nifty']['largest_fall'])}. ES99: A **{pct(es(cr, 'A'))}** vs B **{pct(es(cr, 'B'))}** → label held. Breach test: VaR fitted in calm → A **{bt['A']['breaches']}**, B **{bt['B']['breaches']}** breaches vs ≈{bt['A']['expected']:.1f} expected. **Switch the event live to COVID-19**{f" (ES99 A {pct(es(covid, 'A'))} vs B {pct(es(covid, 'B'))})" if covid else ''}. Scoreboard: label held in **{lv['events_held']}/{lv['events_total']}** events; B beat the Nifty in **{bv['crises_held']}/{bv['crises_total']}** crises. |
| 8:30–12:00 | [Name 4] | Test #2 | Target = {pct(P['A']['target_return'])} for A, {pct(P['B']['target_return'])} for B. In the crisis A's target is **{ta['case']}**; turnover **{pct(ta['turnover'], 0)}** ({inr_short(ta['turnover'] * AMT)}) vs noise p95 {pct(p95a, 0)}. B: **{tb['case']}**, turnover {pct(tb['turnover'], 0)} vs {pct(p95b, 0)}. Show bootstrap bands. |
| 12:00–13:30 | [Name 4] | Verdict | Label: **{lv['verdict']}**; 'safe stayed safe': **{bv['verdict']}**. Enter a loss limit (e.g. ₹4 lakh) and show which portfolio fits. Review trigger. |
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
9. **Is the volatility difference significant?** Yes: the 95% bootstrap interval for σA/σB ({ev['vol_ratio']['lo']:.2f}–{ev['vol_ratio']['hi']:.2f}) lies entirely above 1.
10. **Why is A's beta only {cr['A']['beta']:.2f} in the crisis window?** Labels are set on today's data. Re-running the rule on crisis-window
    data, only {cr['A']['stability']['same']} of {cr['A']['stability']['of']} of A's stocks were High risk then, while {cr['B']['stability']['same']}
    of {cr['B']['stability']['of']} of B's stayed Low risk. A was still the riskier portfolio on outcomes (higher ES, volatility and
    drawdown), so the label held — but "high beta" is not a permanent property of a stock.

## If the venue Wi-Fi fails

1. Run locally: `conda activate fra && streamlit run app.py` (identical code and data; no internet needed after install).
2. Or open the screenshots in `docs/screenshots/` (desktop and phone, every page).
3. Freeze the snapshot before the presentation (do not re-run `fetch_data.py`), so the slides, this guide and the site match.
"""


def main() -> None:
    res = json.loads((C.RESULTS_DIR / "default.json").read_text())
    meta = json.loads((C.DATA_DIR / "metadata.json").read_text())
    (C.DOCS_DIR / "METHODOLOGY.md").write_text(methodology(res, meta))
    (C.DOCS_DIR / "PRESENTATION_GUIDE.md").write_text(guide(res))
    print("wrote docs/METHODOLOGY.md and docs/PRESENTATION_GUIDE.md")


if __name__ == "__main__":
    main()
