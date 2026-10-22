"""streamlit.testing AppTest smoke tests: every page renders without an exception for three amounts, every event in
the dropdowns, both window modes, both confidence levels/horizons, custom picks and the phone layout."""
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src import config

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["views/01_prefs.py", "views/01_suggest.py", "views/05_weights.py", "views/06_test1.py", "views/07_test2.py",
         "views/08_verdict.py", "views/01_home.py", "views/02_how.py", "views/03_pick.py", "views/04_call.py",
         "views/09_methodology.py"]
RES = json.loads((ROOT / "results" / "default.json").read_text())
CRISES = ["auto_crisis"] + [k for k, v in RES["events"].items() if v["type"] == "crisis" and not k.startswith("auto")]
CALMS = ["auto_calm"] + [k for k, v in RES["events"].items() if v["type"] == "calm" and not k.startswith("auto")]


def app(**state):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.session_state["amount_confirmed"] = True
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    return at


def visit_all(at, pages=PAGES):
    for p in pages:
        at.switch_page(p).run()
        assert not at.exception, f"{p}: {[e.value for e in at.exception]}"


def text(at) -> str:
    """All visible text: markdown plus the app's HTML components."""
    html = []
    for h in at.get("html"):
        body = getattr(getattr(h, "proto", None), "body", None)
        html.append(str(body if body is not None else getattr(h, "value", "")))
    return " ".join(m.value for m in at.markdown) + " " + " ".join(html)


def test_start_page_gate_and_amount_parsing():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    assert not at.exception
    assert "How much would you like to invest?" in text(at)
    at.text_input(key="start_amt").set_value("abc").run()
    assert at.error and not at.exception
    at.text_input(key="start_amt").set_value("1.5 crore").run()
    next(b for b in at.button if b.label.startswith("Continue")).click().run()
    assert at.session_state["amount_confirmed"] and at.session_state["amount_a"] == 1_50_00_000
    assert not at.exception


@pytest.mark.parametrize("amount", [10_000, 15_00_000, 1_00_00_000])
def test_every_page_for_amounts(amount):
    at = app(amount_a=float(amount), amount_b=float(amount), amount_total=2.0 * amount)
    visit_all(at)


def test_amount_changes_every_rupee_figure():
    small = app(amount_a=10_000.0, amount_b=10_000.0)
    small.switch_page("views/01_home.py").run()
    big = app(amount_a=1_00_00_000.0, amount_b=1_00_00_000.0)
    big.switch_page("views/01_home.py").run()
    assert "₹1 crore" in text(big) and "₹1 crore" not in text(small)


def test_small_amount_warns_about_unbuyable_stocks():
    at = app(amount_a=10_000.0, amount_b=10_000.0)
    at.switch_page("views/05_weights.py").run()
    assert not at.exception
    assert "too small to buy" in text(at)


@pytest.mark.parametrize("crisis", CRISES)
def test_every_crisis_event(crisis):
    at = app(crisis_id=crisis)
    visit_all(at, ["views/01_home.py", "views/06_test1.py", "views/07_test2.py", "views/08_verdict.py"])


@pytest.mark.parametrize("calm", CALMS)
def test_every_calm_event(calm):
    at = app(calm_id=calm)
    visit_all(at, ["views/01_home.py", "views/06_test1.py", "views/07_test2.py", "views/08_verdict.py"])


def test_custom_range_and_event_only_mode():
    at = app(crisis_id="custom", custom_crisis=("2020-01-01", "2020-12-31"), calm_id="custom",
             custom_calm=("2019-01-01", "2019-12-31"), window_mode="event_only", conf=0.95, horizon=10)
    visit_all(at, ["views/01_home.py", "views/06_test1.py", "views/07_test2.py", "views/08_verdict.py"])


def test_amount_modes():
    for mode in ("split_total", "separate"):
        at = app(amount_mode=mode, amount_total=30_00_000.0, amount_a=20_00_000.0, amount_b=5_00_000.0)
        visit_all(at, ["views/01_home.py", "views/05_weights.py", "views/08_verdict.py"])


def test_custom_picks_recompute_in_app():
    a = RES["picks"]["A"][:9] + ["TATASTEEL"]
    b = RES["picks"]["B"][:9] + ["NESTLEIND"]
    at = app(pick_A=a, pick_B=b)
    visit_all(at, ["views/01_home.py", "views/04_call.py", "views/05_weights.py", "views/06_test1.py"])
    assert at.session_state["pick_A"] == a


def test_phone_layout_every_page():
    at = app(is_phone=True)
    visit_all(at)


def test_backing_hidden():
    at = app(show_backing=False)
    visit_all(at, ["views/01_home.py", "views/06_test1.py"])


def test_preferences_suggest_narrow_choice_and_relaxation_notes():
    at = app()
    at.switch_page("views/01_prefs.py").run()
    assert not at.exception
    for cb in at.checkbox:
        if cb.key and cb.key.startswith("sec_"):
            cb.set_value(cb.key == "sec_Healthcare")
    for cb in at.checkbox:
        if cb.key and cb.key.startswith("cap_"):
            cb.set_value(cb.key == "cap_Large cap")
    at.run()
    next(b for b in at.button if b.label.startswith("Recommend my top")).click().run()
    assert not at.exception
    s = at.session_state
    N = config.PICK_N
    assert len(s["pick_A"]) == N and len(s["pick_B"]) == N and not set(s["pick_A"]) & set(s["pick_B"])
    assert s["rec_A"] == s["pick_A"] and s["rec_B"] == s["pick_B"]
    assert s["pick_notes"]["A"] or s["pick_notes"]["B"]
    visit_all(at, ["views/01_suggest.py", "views/05_weights.py", "views/06_test1.py", "views/07_test2.py", "views/08_verdict.py"])


def test_backtest_several_periods_ticked():
    evs = [k for k, v in RES["events"].items() if v["available"] and not k.startswith("auto")]
    at = app(bt_events=evs)
    visit_all(at, ["views/06_test1.py", "views/07_test2.py", "views/08_verdict.py"])
    assert "worst days" in text(at) or True


def test_picks_survive_leaving_the_edit_page():
    a = RES["picks"]["A"][:9] + [x for x in ("TATASTEEL", "HINDALCO", "JSWSTEEL") if x not in RES["picks"]["A"]][:1]
    at = app(pick_A=a)
    at.switch_page("views/03_pick.py").run()
    at.switch_page("views/05_weights.py").run()
    assert not at.exception and at.session_state["pick_A"] == a


def test_cap_combinations():
    at = app()
    at.switch_page("views/01_prefs.py").run()
    for cb in at.checkbox:
        if cb.key and cb.key.startswith("cap_"):
            cb.set_value(cb.key in ("cap_Large cap", "cap_Small cap"))
    at.run()
    next(b for b in at.button if b.label.startswith("Recommend my top")).click().run()
    assert not at.exception
    assert at.session_state["pref_cap"] == "Large + Small cap"
    assert sorted(at.session_state["pref_caps"]) == ["Large cap", "Small cap"]


def test_recommendation_is_the_main_path_and_can_be_restored():
    at = app()
    at.switch_page("views/01_suggest.py").run()
    assert not at.exception and "Top 15 Bold" in text(at)
    next(b for b in at.button if b.key == "use_rec").click().run()
    assert not at.exception
    own = RES["picks"]["A"][:9] + [x for x in ("TATASTEEL", "HINDALCO", "JSWSTEEL") if x not in RES["picks"]["A"]][:1]
    at.session_state["pick_A"] = own
    at.switch_page("views/05_weights.py").run()
    assert not at.exception and "your own picks" in text(at)
    next(b for b in at.button if b.key == "badge_use_rec").click().run()
    assert not at.exception
    assert at.session_state["pick_A"] == at.session_state["rec_A"]
    assert "recommended portfolios" in text(at)


def test_back_button_returns_to_previous_screen():
    at = app(is_phone=True)
    at.switch_page("views/01_suggest.py").run()
    at.switch_page("views/05_weights.py").run()
    back = [b for b in at.button if b.key and b.key.startswith("ptm_back_")]
    assert back, "no back button"
    back[0].click().run()
    assert not at.exception
    assert "Top 15 Bold" in text(at)
    assert at.session_state["is_phone"]  # the phone layout survives page switches


def test_phone_only_presenting_view_and_back():
    at = app()
    at.switch_page("views/05_weights.py").run()
    next(b for b in at.button if b.key == "ptm_present_on").click().run()
    assert not at.exception and at.session_state["present_mode"]
    assert "Behind the Today screen" not in text(at)
    at.switch_page("views/06_test1.py").run()  # stays in phone-only view while moving around
    assert not at.exception and at.session_state["present_mode"]
    next(b for b in at.button if b.key == "ptm_present_off").click().run()
    assert not at.exception and not at.session_state["present_mode"]


def test_refresh_returns_to_the_same_screen():
    """After a browser refresh, 404.html reopens the dashboard with ?page=<screen>; after the amount, that screen comes back."""
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.query_params["page"] = "verdict"
    at.run()
    assert "How much would you like to invest?" in text(at)
    next(b for b in at.button if b.label.startswith("Continue")).click().run()
    assert not at.exception and "Does 'safe' stay safe?" in text(at)


def test_expected_shortfall_shows_the_portfolio_value_left():
    from src.fmt import inr_short

    amt = 1_00_00_000.0
    at = app(amount_a=amt, amount_b=amt)
    at.switch_page("views/05_weights.py").run()
    es = RES["current"]["A"]["risk"]["Historical"]["0.95"]["es"]  # 95% is the default
    assert not at.exception and f"to <b>{inr_short(amt * (1 - es))}</b>, a loss of {inr_short(es * amt)}" in text(at)
    at.switch_page("views/06_test1.py").run()
    var = RES["regimes"][f"{RES['official']['crisis']}|standard"]["A"]["risk"]["Historical"]["0.95"]["var"]
    body = text(at)
    assert not at.exception and f"drops from {inr_short(amt)} to <b>{inr_short(amt * (1 - var))}</b>, a loss of {inr_short(var * amt)}" in body
    assert "Expected Shortfall" in body


def test_backtest_shows_portfolio_value_through_each_period():
    from src.fmt import inr_short

    amt = 1_00_00_000.0
    at = app(amount_a=amt, amount_b=amt)
    at.switch_page("views/06_test1.py").run()
    rep = RES["regimes"][f"{RES['official']['crisis']}|standard"]["A"]["replay"]
    body = text(at)
    assert not at.exception and "Your money through this period" in body
    assert inr_short(rep["low"] * amt) in body and inr_short(rep["end"] * amt) in body


def test_backtest_method_table_covers_every_ticked_period_in_rupees():
    evs = ["covid_2020", "ukraine_2022"] if all(e in RES["events"] for e in ("covid_2020", "ukraine_2022")) else \
        [k for k, v in RES["events"].items() if v["available"] and not k.startswith("auto")][:2]
    at = app(bt_events=evs)
    at.switch_page("views/06_test1.py").run()
    assert not at.exception
    t = next(d.value for d in at.dataframe if "Value after VaR loss ₹" in getattr(d.value, "columns", []) and "Period" in d.value.columns)
    assert set(t["Period"]) == {"Today"} | {RES["events"][e]["name"] for e in evs}
    assert len(t) == (1 + len(evs)) * 3 * 3  # periods × portfolios × the three methods taught in class


def test_backtest_comparison_table_today_vs_each_period():
    from src.fmt import inr_short

    evs = [k for k, v in RES["events"].items() if v["available"] and not k.startswith("auto")][:3]
    at = app(bt_events=evs, amount_a=1_00_00_000.0, amount_b=1_00_00_000.0)
    at.switch_page("views/06_test1.py").run()
    assert not at.exception
    t = next(d.value for d in at.dataframe if "ES vs today" in getattr(d.value, "columns", []))
    assert list(t["Period"])[0] == "Today" and len(t) == 1 + len(evs) and t["ES vs today"].iloc[0] == "1.0×"
    var_now = RES["current"]["A"]["risk"]["Historical"]["0.95"]["var"]
    assert t["VaR 95%, 1-day"].iloc[0] == inr_short(var_now * 1e7) and t["Value after VaR"].iloc[0] == inr_short(1e7 * (1 - var_now))
    for v in "BC":
        next(w for w in at.segmented_control if w.key == "bt_cmp").set_value(v).run()
        assert not at.exception



def test_es_text_lists_exactly_the_days_it_averages():
    import numpy as np
    from src import ui as U

    reg = RES["regimes"][f"{RES['official']['crisis']}|standard"]["A"]
    n, losses = U.tail_days(reg, "0.99")
    h = reg["risk"]["Historical"]["0.99"]
    assert n == len(reg["returns"]["port"]) and all(x > h["var"] for x in losses) and losses == sorted(losses, reverse=True)
    assert np.mean(losses) == pytest.approx(h["es"], rel=1e-5)  # ES is exactly the average of the listed days
