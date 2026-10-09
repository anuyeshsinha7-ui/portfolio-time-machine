"""Analytics engine tests (brief §10, §13): beta, optimiser constraints and cross-checks,
VaR/ES orderings, Kupiec, allocation, event anchoring."""
import numpy as np
import pandas as pd
import pytest

from src import allocation as AL
from src import config
from src import data as D
from src import events as EV
from src import metrics as M
from src import optimize as O
from src import stats_tests as ST
from src import universe as U
from src import var_es as V


@pytest.fixture(scope="module")
def picks():
    return U.default_portfolios()


@pytest.fixture(scope="module")
def current_A(picks):
    cal = D.calendar()
    R = D.window(D.returns(), cal[-252], cal[-1])[picks["A"]]
    return R


# ---------------------------------------------------------------- metrics
def test_nifty_beta_to_itself_is_one():
    m = D.market_returns()
    assert round(M.beta(m, m), 2) == 1.00


def test_metric_definitions():
    r = pd.Series([0.01, -0.02, 0.03, -0.01, 0.0])
    assert M.ann_vol(r) == pytest.approx(r.std(ddof=1) * np.sqrt(252))
    assert M.max_drawdown(pd.Series([0.1, -0.5, 0.2])) == pytest.approx(0.5)
    assert M.max_drawdown(pd.Series([-0.1, 0.05])) == pytest.approx(0.1)


def test_ledoit_wolf_matches_sklearn():
    sk = pytest.importorskip("sklearn.covariance")
    rng = np.random.default_rng(0)
    X = rng.standard_normal((120, 8)) @ rng.standard_normal((8, 8)) * 0.01
    ours, d = M.ledoit_wolf(X)
    ref = sk.LedoitWolf().fit(X)
    assert d == pytest.approx(ref.shrinkage_, rel=1e-6)
    assert np.allclose(ours, ref.covariance_, rtol=1e-6)


def test_no_overlap_and_size(picks):
    assert len(picks["A"]) == config.PICK_N and len(picks["B"]) == config.PICK_N
    assert not set(picks["A"]) & set(picks["B"])
    t = U.classification()
    assert (t.loc[picks["A"], "label"] == "High risk").all()
    assert (t.loc[picks["B"], "label"] == "Low risk").all()
    assert t.loc[picks["A"], "industry"].value_counts().max() <= config.MAX_PER_INDUSTRY_PICK
    assert t.loc[picks["A"], "industry"].nunique() >= 4 and t.loc[picks["B"], "industry"].nunique() >= 4


# ---------------------------------------------------------------- optimiser
def _setup(R):
    cons = O.build_constraints([D.universe().loc[s, "industry"] for s in R.columns])
    mu = (R.mean() * 252).to_numpy()
    S = (R.cov() * 252).to_numpy()
    return mu, S, cons


def _ok(w, cons):
    assert abs(w.sum() - 1) < 1e-6
    assert (w >= cons.w_min - 1e-6).all() and (w <= cons.w_max + 1e-6).all()
    for idx in cons.groups.values():
        assert w[idx].sum() <= cons.ind_max + 1e-6


def test_min_variance_feasible_and_matches_cvxpy(current_A):
    cp = pytest.importorskip("cvxpy")
    mu, S, cons = _setup(current_A)
    w = O.min_variance(mu, S, cons)
    _ok(w, cons)
    x = cp.Variable(len(mu))
    A = cons.A_ind(len(mu))
    prob = cp.Problem(cp.Minimize(cp.quad_form(x, cp.psd_wrap(S))),
                      [cp.sum(x) == 1, x >= cons.w_min, x <= cons.w_max, A @ x <= cons.ind_max])
    prob.solve()
    assert w @ S @ w == pytest.approx(prob.value, rel=1e-4)


def test_max_sharpe_matches_cvxpy_reformulation(current_A):
    cp = pytest.importorskip("cvxpy")
    mu, S, cons = _setup(current_A)
    rf = config.RISK_FREE_RATE
    w, fb = O.max_sharpe(mu, S, cons)
    _ok(w, cons)
    n = len(mu)
    A = cons.A_ind(n)
    y, k = cp.Variable(n), cp.Variable()
    prob = cp.Problem(cp.Minimize(cp.quad_form(y, cp.psd_wrap(S))),
                      [(mu - rf) @ y == 1, cp.sum(y) == k, k >= 0, y >= cons.w_min * k, y <= cons.w_max * k,
                       A @ y <= cons.ind_max * k])
    prob.solve()
    wc = y.value / k.value
    sh = lambda v: (mu @ v - rf) / np.sqrt(v @ S @ v)
    assert sh(w) >= sh(wc) - 1e-4
    # and no point on the frontier grid beats it
    fr = O.frontier(mu, S, cons)
    assert sh(w) >= max((fr["rets"] - rf) / fr["vols"]) - 1e-4


def test_target_return_cases(current_A):
    mu, S, cons = _setup(current_A)
    r_max, _ = O.max_return(mu, cons)
    w_mv = O.min_variance(mu, S, cons)
    r_mv = mu @ w_mv
    assert O.solve_target_case(mu, S, cons, r_max + 0.5)["case"] == "unreachable"
    assert O.solve_target_case(mu, S, cons, r_mv - 0.5)["case"] == "below_minvar"
    mid = (r_mv + r_max) / 2
    res = O.solve_target_case(mu, S, cons, mid)
    assert res["case"] == "reachable" and res["ret"] >= mid - 1e-7
    _ok(res["weights"], cons)


def test_constraints_relaxed_when_infeasible():
    c = O.build_constraints(["X"] * 3)  # 3 stocks: 3 × 25% < 100%, one industry > 40%
    assert c.warnings and c.w_max >= 1 / 3 and c.ind_max >= 1.0 - 1e-9
    c2 = O.build_constraints(["A"] * 6 + ["B"] * 4)
    assert 0.5 - 1e-9 <= c2.ind_max <= 0.51  # two industries must share 100% → cap rises to 50%


def test_random_cloud_feasible(current_A):
    mu, S, cons = _setup(current_A)
    W = O.random_feasible(len(mu), cons, 500)
    assert len(W) == 500
    for w in W[:50]:
        _ok(w, cons)


def test_turnover():
    assert O.turnover([0.5, 0.5], [0.5, 0.5]) == 0
    assert O.turnover([1, 0], [0, 1]) == pytest.approx(1.0)


# ---------------------------------------------------------------- VaR / ES
def test_var_es_orderings_all_methods(current_A, picks):
    w = pd.Series(1 / len(picks["A"]), index=picks["A"])
    res = V.all_methods(current_A, w)
    for m in V.METHODS:
        for c in (0.95, 0.99, 0.975):
            assert res[m][c]["es"] >= res[m][c]["var"] - 1e-12, m
        assert res[m][0.99]["var"] >= res[m][0.95]["var"], m
        assert res[m][0.99]["es"] >= res[m][0.95]["es"], m


def test_historical_var_known_values():
    r = np.array([-0.05, -0.04, -0.03, -0.02, -0.01] + [0.01] * 95)
    v, e = V.historical(r, 0.95)
    assert v == pytest.approx(0.01) and e == pytest.approx(0.03)
    v99, e99 = V.historical(r, 0.99)
    assert v99 == pytest.approx(0.05) and e99 == pytest.approx(0.05)


def test_parametric_normal_formula():
    rng = np.random.default_rng(1)
    r = rng.normal(0, 0.01, 100_000)
    v, e = V.parametric_normal(r, 0.99)
    assert v == pytest.approx(2.326 * 0.01, rel=0.02)
    assert e == pytest.approx(2.665 * 0.01, rel=0.02)


def test_cornish_fisher_equals_normal_without_skew_kurtosis():
    rng = np.random.default_rng(2)
    r = rng.normal(0, 0.01, 200_000)
    v_cf, _ = V.cornish_fisher(r, 0.99)
    v_n, _ = V.parametric_normal(r, 0.99)
    assert v_cf == pytest.approx(v_n, rel=0.03)


def test_mc_student_t_reproducible_and_fat_tailed(current_A, picks):
    w = pd.Series(1 / len(picks["A"]), index=picks["A"])
    a, nu = V.mc_student_t(current_A, w, (0.99,))
    b, nu2 = V.mc_student_t(current_A, w, (0.99,))
    assert a == b and nu == nu2 and nu >= config.T_DOF_FLOOR


def test_horizon_scaling():
    assert V.scale_horizon(0.02, 10) == pytest.approx(0.02 * np.sqrt(10))


# ---------------------------------------------------------------- Kupiec and bootstrap
def test_kupiec():
    k = ST.kupiec(3, 250, 0.99)
    assert k["expected"] == pytest.approx(2.5)
    assert k["p_value"] > 0.5 and not k["reject_95"]
    k2 = ST.kupiec(15, 250, 0.99)
    assert k2["reject_95"]
    k0 = ST.kupiec(0, 250, 0.99)
    assert 0 < k0["p_value"] < 1


def test_block_bootstrap_indices():
    rng = np.random.default_rng(0)
    ix = ST.block_indices(100, 5, rng)
    assert len(ix) == 100 and ix.max() < 100
    # consecutive within blocks
    assert all(ix[i + 1] - ix[i] == 1 for i in range(0, 100, 5) for i in [i, i + 1, i + 2, i + 3] if i + 1 < 100)


# ---------------------------------------------------------------- allocation
def test_whole_share_allocation():
    w = pd.Series({"X": 0.5, "Y": 0.3, "Z": 0.2})
    p = pd.Series({"X": 100.0, "Y": 3000.0, "Z": 7.0})
    res = AL.allocate(w, p, 10_000)
    t = res["table"]
    assert list(t["shares"]) == [50, 1, 285]
    assert res["invested"] == pytest.approx(5000 + 3000 + 1995)
    assert res["cash"] == pytest.approx(5)
    assert t["realised_weight"].sum() == pytest.approx(1.0)
    assert res["unbuyable"] == []
    small = AL.allocate(w, p, 5_000)
    assert small["unbuyable"] == ["Y"]
    assert AL.min_sensible_amount(w, p) == 10_000  # 3000 / 0.3


def test_amount_modes():
    assert AL.split_amounts("same_each", 15_00_000) == (15_00_000, 15_00_000)
    assert AL.split_amounts("split_total", 30_00_000) == (15_00_000, 15_00_000)
    assert AL.split_amounts("separate", 10_00_000, 5_00_000) == (10_00_000, 5_00_000)


# ---------------------------------------------------------------- events
def test_event_windows_anchored_on_data():
    close = D.benchmark()["NIFTY50"]
    evs = EV.resolve_all(close, D.market_returns())
    cal = close.index
    cur_start = cal[-252]
    for k, ev in evs.items():
        if not ev["available"]:
            continue
        s, e = ev["windows"]["standard"]
        n = ((cal >= s) & (cal <= e)).sum()
        assert n == config.REGIME_DAYS, k
        assert e < cur_start, f"{k} overlaps the Current window"
        so, eo = ev["windows"]["event_only"]
        assert ((cal >= so) & (cal <= eo)).sum() >= config.MIN_WINDOW_DAYS, k
    covid = evs["covid_2020"]
    assert covid["anchor"]["peak"].strftime("%Y-%m") == "2020-01"
    assert covid["anchor"]["trough"].strftime("%Y-%m-%d") == "2020-03-23"
    assert covid["anchor"]["fall"] == pytest.approx(0.38, abs=0.02)
    # standard crisis window starts 21 sessions before the peak
    p = cal.get_loc(covid["anchor"]["peak"])
    assert covid["windows"]["standard"][0] == cal[p - config.EVENT_PRE_DAYS]
    assert evs["auto_crisis"]["anchor"]["peak"].year == 2008


def test_anchor_crisis_on_toy_series():
    idx = pd.bdate_range("2020-01-01", periods=10)
    c = pd.Series([100, 105, 110, 100, 80, 70, 75, 90, 95, 60.0], index=idx)
    a = EV.anchor_crisis(c, idx[0], idx[8])
    assert a["peak"] == idx[2] and a["trough"] == idx[5] and a["fall"] == pytest.approx(1 - 70 / 110)


def test_custom_range_minimum_length():
    close = D.benchmark()["NIFTY50"]
    with pytest.raises(ValueError):
        EV.custom_event("2020-01-01", "2020-02-01", close, "crisis")
    ev = EV.custom_event("2019-01-01", "2019-12-31", close, "calm")
    assert ev["available"]


# ---------------------------------------------------------------- sector / market-cap picker
def test_pick_by_filters_respects_choice_and_relaxes_with_notes():
    t = U.classification()
    sectors = sorted(t["industry"].unique())
    res = U.pick_by_filters(t, sectors, "Large cap")
    N = config.PICK_N
    assert len(res["A"]) == N and len(res["B"]) == N and not set(res["A"]) & set(res["B"])
    if not res["notes_A"]:
        assert (t.loc[res["A"], "cap_bucket"] == "Large cap").all()
        assert (t.loc[res["A"], "label"] == "High risk").all()
    narrow = U.pick_by_filters(t, ["Healthcare"], "Large cap")
    assert len(narrow["A"]) == N and len(narrow["B"]) == N
    assert narrow["notes_A"] or narrow["notes_B"]  # one sector can't fill 15 + 15 without relaxing


def test_default_picks_are_all_sectors_flexi():
    t = U.classification()
    d = U.default_portfolios(t)
    f = U.pick_by_filters(t)
    assert d["A"] == f["A"] and d["B"] == f["B"]


def test_pick_by_cap_combination():
    t = U.classification()
    res = U.pick_by_filters(t, None, ["Large cap", "Small cap"])
    assert res["cap"] == "Large + Small cap"
    if not res["notes_A"]:
        assert set(t.loc[res["A"], "cap_bucket"]) <= {"Large cap", "Small cap"}
    assert U.cap_label(["Small cap", "Mid cap", "Large cap"]) == "Flexi cap"
