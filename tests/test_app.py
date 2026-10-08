"""streamlit.testing AppTest smoke tests: every page renders without an exception for three amounts, every event in
the dropdowns, both window modes, both confidence levels/horizons, custom picks and the phone layout."""
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["views/01_home.py", "views/02_how.py", "views/03_pick.py", "views/04_call.py", "views/05_weights.py",
         "views/06_test1.py", "views/07_test2.py", "views/08_verdict.py", "views/09_methodology.py"]
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
    at = app(phone=True)
    visit_all(at)


def test_backing_hidden():
    at = app(show_backing=False)
    visit_all(at, ["views/01_home.py", "views/06_test1.py"])
