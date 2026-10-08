"""Unit tests for every cleaning check in brief §5.2, each against a fixture containing the problem.

Fixtures in tests/fixtures/ are hand-made TEST DATA, never market data.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src import cleaning as C

FIX = Path(__file__).parent / "fixtures"


def load(name, **kw):
    return pd.read_csv(FIX / name, comment="#", parse_dates=["Date"], index_col="Date", **kw)


@pytest.fixture
def calendar():
    return pd.DatetimeIndex(load("calendar.csv").index)


@pytest.fixture
def nse():
    return C.nse_actions_frame(json.loads((FIX / "nse_actions.json").read_text()))


# ---------------------------------------------------------------- E. calendar
def test_duplicates_removed_keep_last():
    df = load("calendar_issues.csv")
    out, issues = C.normalise_index(df, "T")
    assert out.index.is_unique and out.index.is_monotonic_increasing
    assert out.loc["2024-01-03", "Close"] == 101.5
    assert [i.issue for i in issues] == ["duplicate date"]


def test_timezone_dropped():
    df = pd.DataFrame({"Close": [1.0, 2.0]},
                      index=pd.DatetimeIndex(["2024-01-02 00:00", "2024-01-03 00:00"]).tz_localize("Asia/Kolkata"))
    out, _ = C.normalise_index(df, "T")
    assert out.index.tz is None


def test_weekend_and_holiday_rows_dropped_special_session_kept(calendar):
    df, _ = C.normalise_index(load("calendar_issues.csv"), "T")
    out, issues = C.drop_non_sessions(df, calendar, "T")
    assert pd.Timestamp("2024-01-06") not in out.index  # Saturday, Nifty closed
    assert pd.Timestamp("2024-01-22") not in out.index  # holiday, Nifty closed
    assert pd.Timestamp("2024-01-20") in out.index  # special Saturday session, Nifty traded
    kinds = sorted(i.issue for i in issues)
    assert kinds == ["row on a non-trading day", "weekend row"]


def test_alignment_ffill_limit_and_missing_threshold(calendar):
    df, _ = C.normalise_index(load("calendar_issues.csv"), "T")
    df, _ = C.drop_non_sessions(df, calendar, "T")
    s, issues, keep = C.align_to_calendar(df["Close"], calendar, "T", max_ffill=2, max_missing_pct=0.02)
    # 2-day gap filled
    assert s.loc["2024-01-09"] == 103.0 and s.loc["2024-01-10"] == 103.0
    # 4-day gap: first two filled, last two missing
    assert s.loc["2024-01-15"] == 104.5 and s.loc["2024-01-16"] == 104.5
    assert np.isnan(s.loc["2024-01-17"]) and np.isnan(s.loc["2024-01-18"])
    assert not keep  # 6 of 20 days missing > 2%
    _, _, keep_loose = C.align_to_calendar(df["Close"], calendar, "T", max_missing_pct=0.5)
    assert keep_loose


def test_stale_runs_flag_and_exclude():
    s = load("stale.csv")["Close"]
    issues, keep = C.stale_runs(s, "T", flag_days=5, exclude_days=10)
    assert len(issues) == 2
    assert not keep
    issues2, keep2 = C.stale_runs(s.iloc[:11], "T")
    assert len(issues2) == 1 and keep2


def test_incomplete_last_row():
    df = pd.DataFrame({"Close": [1.0, 2.0]}, index=pd.to_datetime(["2024-01-02", "2024-01-03"]))
    out, issues = C.drop_incomplete_last_row(df, pd.Timestamp("2024-01-03 11:00"), "T")
    assert len(out) == 1 and len(issues) == 1
    out2, issues2 = C.drop_incomplete_last_row(df, pd.Timestamp("2024-01-03 18:00"), "T")
    assert len(out2) == 2 and not issues2


# ---------------------------------------------------------------- D. bad prints
def test_invalid_prices_to_missing():
    s = load("bad_prints.csv")["Close"]
    out, issues = C.invalid_prices(s, "T")
    assert np.isnan(out.loc["2024-01-03"]) and np.isnan(out.loc["2024-01-05"]) and np.isnan(out.loc["2024-01-08"])
    assert sum(i.issue == "zero, negative or missing price" for i in issues) == 2


def test_decimal_error_detected():
    s, _ = C.invalid_prices(load("bad_prints.csv")["Close"], "T")
    s = s.ffill()
    out, issues = C.decimal_errors(s, "T")
    assert [i.date for i in issues] == ["2024-01-10"]
    assert out.loc["2024-01-10"] == out.loc["2024-01-09"]


def test_spike_and_revert_vs_genuine_move():
    s, _ = C.invalid_prices(load("bad_prints.csv")["Close"], "T")
    s, _ = C.decimal_errors(s.ffill(), "T")
    out, issues = C.spike_and_revert(s, "T")
    bad = [i.date for i in issues if i.issue.startswith("spike-and-revert (bad")]
    assert bad == ["2024-01-15"]
    assert out.loc["2024-01-15"] == out.loc["2024-01-12"]
    # the genuine −25% on 01-18 does not revert → kept and flagged as large move
    assert out.loc["2024-01-18"] == 155.25
    flags = C.flag_large_moves(out, "T")
    assert [f.date for f in flags] == ["2024-01-18"]


def test_spike_near_corporate_action_not_removed():
    s, _ = C.invalid_prices(load("bad_prints.csv")["Close"], "T")
    s, _ = C.decimal_errors(s.ffill(), "T")
    out, issues = C.spike_and_revert(s, "T", action_dates={pd.Timestamp("2024-01-15")})
    assert out.loc["2024-01-15"] == 266.5
    assert any("near a corporate action" in i.issue for i in issues)


# ---------------------------------------------------------------- A. splits and bonuses
def test_parse_nse_subjects():
    assert C.parse_nse_action("Bonus 1:1") == ("bonus", 0.5)
    assert C.parse_nse_action("Bonus 1:2")[1] == pytest.approx(2 / 3)
    assert C.parse_nse_action("Bonus 2:1")[1] == pytest.approx(1 / 3)
    assert C.parse_nse_action("Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share") == ("split", 0.2)
    assert C.parse_nse_action("Face Value Split (Sub-Division) - From Rs 2/- Per Share To Re 1/- Per Share") == ("split", 0.5)
    assert C.parse_nse_action("Demerger")[0] == "demerger"
    assert C.parse_nse_action("Dividend - Rs 5 Per Share")[0] == "other"


def test_missing_split_detected_and_confirmed_by_nse(nse):
    df = load("splits.csv")
    raw = C.reconstruct_raw(df["missing_split"], pd.Series(0, index=df.index))
    jumps = C.detect_split_jumps(raw)
    assert len(jumps) == 1
    d, ratio, k = jumps[0]
    assert d == pd.Timestamp("2024-01-10") and k == 0.5
    hit = C.match_nse(nse, d, k)
    assert hit is not None and hit["subject"] == "Bonus 1:1"
    adj = C.apply_factors(raw, [(d, hit["factor"])])
    assert adj.pct_change().abs().max() < 0.05  # smooth after the fix
    assert C.check_double_adjustment(adj, [(d, 0.5)]) == []


def test_known_yahoo_split_reconstructs_raw_and_matches_nse(nse):
    df = load("splits.csv")
    raw = C.reconstruct_raw(df["known_split"], df["known_split_events"])
    assert raw.loc["2024-01-09"] == pytest.approx(515.0)  # 103 × 5 = the real pre-split print
    assert raw.loc["2024-01-10"] == pytest.approx(103.2)
    hit = C.match_nse(nse, pd.Timestamp("2024-01-10"), 1 / 5)
    assert hit is not None and hit["kind"] == "split"
    assert C.detect_split_jumps(df["known_split"]) == []  # Yahoo's close is clean


def test_wrong_exdate_detected_and_moved(nse):
    df = load("splits.csv")
    close, ev = df["late_split"], df["late_split_events"]
    # Yahoo's close shows a −50% then +100% pair around the recorded date
    r = close / close.shift(1)
    assert r.loc["2024-01-10"] == pytest.approx(0.501, abs=0.01) and r.loc["2024-01-11"] == pytest.approx(2.016, abs=0.01)
    raw = C.reconstruct_raw(close, ev)
    nse_hit = C.match_nse(nse, pd.Timestamp("2024-01-11"), 0.5)
    assert nse_hit["ex_date"] == pd.Timestamp("2024-01-10")
    assert C.check_wrong_exdate(raw, pd.Timestamp("2024-01-11"), nse_hit["ex_date"], 0.5)
    fixed = C.apply_factors(raw, [(nse_hit["ex_date"], 0.5)])
    assert fixed.pct_change().abs().max() < 0.05
    wrong = C.apply_factors(raw, [(pd.Timestamp("2024-01-11"), 0.5)])
    assert C.check_double_adjustment(wrong, [(pd.Timestamp("2024-01-11"), 0.5)])  # problem visible


def test_double_adjustment_detected():
    df = load("splits.csv")
    raw = C.reconstruct_raw(df["known_split"], df["known_split_events"])
    once = C.apply_factors(raw, [(pd.Timestamp("2024-01-10"), 0.2)])
    twice = C.apply_factors(once, [(pd.Timestamp("2024-01-10"), 0.2)])
    probs = C.check_double_adjustment(twice, [(pd.Timestamp("2024-01-10"), 0.2)])
    assert probs and "double" in probs[0][2]
    assert C.check_double_adjustment(once, [(pd.Timestamp("2024-01-10"), 0.2)]) == []


def test_dividend_factor_and_adjclose_check():
    df = load("dividends.csv")
    f = C.dividend_factor(df["Close"], df["Dividends"])
    mine = df["Close"] * f
    assert mine.loc["2024-01-04"] == pytest.approx(190.0)
    gap = C.compare_adjclose(mine, df["yahoo_adj"])
    assert gap.abs().max() < 1e-9
    gap_bad = C.compare_adjclose(mine, df["yahoo_adj_bad"])
    assert gap_bad.abs().max() > 0.005  # disagreement > 0.5% is reported


def test_implausible_dividend_flagged():
    df = load("dividends.csv")
    div = df["Dividends"].copy()
    div.loc["2024-01-08"] = 100  # 52% of the previous close
    assert len(C.suspicious_dividends(df["Close"], div, "T")) == 1


# ---------------------------------------------------------------- B. demergers
def test_demerger_drop_and_official_ratio(nse):
    s = load("demerger.csv")["Close"]
    ex = nse[nse["kind"] == "demerger"]["ex_date"].iloc[0]
    day, ratio = C.demerger_drop(s, ex)
    assert day == pd.Timestamp("2024-01-15") and ratio == pytest.approx(455 / 505)
    # with an official cost-of-acquisition ratio (say 90.5% stays with the parent)
    adj = C.apply_factors(s, [(day, 0.905)])
    assert abs(adj.pct_change().loc["2024-01-15"]) < 0.01


def test_demerger_without_ratio_neutralises_day():
    s = load("demerger.csv")["Close"]
    out, f = C.neutralise_day(s, pd.Timestamp("2024-01-15"))
    assert out.pct_change().loc["2024-01-15"] == pytest.approx(0.0)
    assert out.loc["2024-01-17"] == s.loc["2024-01-17"]


# ---------------------------------------------------------------- C. symbol changes
def test_stitch_old_and_new_symbols():
    df = load("stitch.csv")
    out, info = C.stitch(df["new"], df["old"], pd.Timestamp("2024-01-09"))
    assert info["ok"] and info["overlap_days"] == 2
    assert out.index[0] == pd.Timestamp("2024-01-03") and len(out) == 8
    _, info_bad = C.stitch(df["new_bad"], df["old"], pd.Timestamp("2024-01-09"))
    assert not info_bad["ok"]  # prices disagree by > 1% at the join


# ---------------------------------------------------------------- F. integrity
def test_checksum_and_restatement_diff():
    a = pd.DataFrame({"X": [1.0, 2.0, 3.0]}, index=pd.date_range("2024-01-01", periods=3))
    b = a.copy()
    assert C.checksum_frame(a) == C.checksum_frame(b)
    b.iloc[1, 0] = 2.1
    assert C.checksum_frame(a) != C.checksum_frame(b)
    d = C.diff_snapshots(a, b)
    assert len(d) == 1 and d["relative_change"].iloc[0] == pytest.approx(0.05)


# ---------------------------------------------------------------- anchoring to NSE official prices
def test_nse_frame_splits_combined_subjects_and_dividends():
    recs = [{"symbol": "T", "exDate": "31-May-2024",
             "subject": "Annual General Meeting/Special Dividend - Rs 8 Per Share /Dividend - Rs 20 Per Share"},
            {"symbol": "T", "exDate": "16-Jun-2025", "subject": "Bonus 4:1"},
            {"symbol": "T", "exDate": "16-Jun-2025",
             "subject": "Face Value Split (Sub-Division) - From Rs 2/- Per Share To Re 1/- Per Share"}]
    df = C.nse_actions_frame(recs)
    divs = C.nse_dividends(df)
    assert divs.loc["2024-05-31"] == pytest.approx(28.0)
    comb = C.combined_factors(df)
    assert len(comb) == 1 and comb["factor"].iloc[0] == pytest.approx(0.1)


def test_find_q_changes_and_outliers():
    idx = pd.date_range("2020-01-01", periods=8, freq="MS")
    q = pd.Series([2.0, 2.0, 2.0, 1.0, 1.0, 1.3, 1.0, 1.0], index=idx)
    changes, outliers = C.find_q_changes(q)
    assert changes == [(idx[2], idx[3])]
    assert outliers == [idx[5]]


def test_bisect_change_finds_exact_day_with_holes():
    days = list(pd.bdate_range("2020-01-02", periods=20))
    true_change = days[13]
    def q_at(d):
        if d == days[10]:
            return None  # no official file that day
        return 2.0 if d < true_change else 1.0
    assert C.bisect_change(days, 2.0, 1.0, q_at) == true_change


def test_piecewise_anchor_restores_official_level():
    idx = pd.bdate_range("2020-01-01", periods=6)
    yahoo_raw = pd.Series([50, 51, 52, 104, 105, 106.0], index=idx)  # Yahoo over-adjusted the first 3 days by 1/2
    q = C.piecewise_q(idx, [idx[3]], [2.0, 1.0])
    true_raw = yahoo_raw * q
    assert list(true_raw) == [100, 102, 104, 104, 105, 106]


@pytest.mark.parametrize("subject,kind,factor", [
    ("Fv Splt Frm Rs 10 To Re 1", "split", 0.1),
    ("Bonus - 1:1 And Face Value Split From Rs. 10 To Rs. 2", "bonus", 0.1),
    ("Bonus-1:1", "bonus", 0.5),
    ("Bonus 1:1 And Face Value Split From Rs.10/- To Rs.5/-", "bonus", 0.25),
    ("Fv Split Rs10 To Rs2", "split", 0.2),
])
def test_parse_nse_subject_variants(subject, kind, factor):
    k, f = C.parse_nse_action(subject)
    assert k == kind and f == pytest.approx(factor)


def test_rights_terms_and_factor():
    assert C.rights_terms("Rights 1:15 @ Premium Rs 1247") == (1, 15, 1247.0)
    assert C.rights_terms("Rights-Eq 1:5@Prem Rs1580") == (1, 5, 1580.0)
    assert C.rights_terms(" Rights 87:38 @ Premium Of Rs 2.50 Per Share") == (87, 38, 2.5)
    assert C.rights_terms("Rights - 4:25 Fully Paid Up Shares @ Premium Rs 500/- / 2:25 Partly Paid Up") is None
    assert C.parse_nse_action("Rights 1:1 @ Premium Rs 48/-")[0] == "rights"
    # 1-for-1 at ₹50 when the stock is at ₹150: TERP = (150 + 50) / 2 = 100 → factor 2/3
    assert C.rights_factor(1, 1, 50.0, 150.0) == pytest.approx(2 / 3)
    assert C.rights_factor(1, 1, 200.0, 150.0) is None


def test_more_subject_variants_and_percent_dividends():
    assert C.parse_nse_action("Fv Spl-Rs10tore1") == ("split", 0.1)
    assert C.parse_nse_action("Bon-1:1") == ("bonus", 0.5)
    assert C.parse_nse_action("Bon 5:1purpose Revised")[1] == pytest.approx(1 / 6)
    assert C.parse_nse_action("Scheme Of Arrangement - Bonus Debentures 6:1")[0] == "other"
    assert C.parse_nse_dividend("Div Fin-130%+Spl-25%", 2.0) == pytest.approx(3.1)
    assert C.parse_nse_dividend("Agm/Div-Rs.15 + Spl-Rs.20") == pytest.approx(35.0)
    assert C.parse_nse_dividend("Spl Div-Rs.80/- Per Share") == pytest.approx(80.0)


def test_spike_confirmed_by_exchange_is_kept():
    s, _ = C.invalid_prices(load("bad_prints.csv")["Close"], "T")
    s, _ = C.decimal_errors(s.ffill(), "T")
    out, issues = C.spike_and_revert(s, "T", confirm=lambda d: True)
    assert out.loc["2024-01-15"] == 266.5
    assert any("confirmed genuine" in i.issue for i in issues)
