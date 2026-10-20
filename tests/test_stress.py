"""Stress tests: walk the app forwards and backwards, and press random controls in random order (a seeded "monkey"),
checking after every single step that no page raises. Complements the page-by-page smoke tests in test_app.py."""
import json
import random
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import TESTING_KEY

ROOT = Path(__file__).resolve().parent.parent
RES = json.loads((ROOT / "results" / "default.json").read_text())
FLOW = ["views/01_prefs.py", "views/01_suggest.py", "views/05_weights.py", "views/06_test1.py", "views/07_test2.py",
        "views/08_verdict.py", "views/01_home.py", "views/02_how.py", "views/03_pick.py", "views/04_call.py",
        "views/09_methodology.py"]
CHOICES = {  # segmented controls / pills: key → values the app offers
    "w_which": ["A", "B", "C"], "t2_which": ["A", "B", "C"], "bt_cmp": ["A", "B", "C"], "window_mode": ["standard", "event_only"],
    "conf": [0.95, 0.99], "horizon": [1, 10], "start_mode": ["same_each", "split_total", "separate"],
}
AMOUNTS = ["15 lakh", "1.5 crore", "10,000", "abc", "", "5", "99999999999", "2,50,000"]


def app(**state):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300)
    at.session_state["amount_confirmed"] = True
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    return at


def ok(at, step):
    assert not at.exception, f"{step}: {[e.value for e in at.exception]}"


@pytest.mark.parametrize("phone", [False, True])
def test_forward_then_backward_through_every_page(phone):
    at = app(is_phone=phone)
    for p in FLOW + FLOW[::-1]:
        at.switch_page(p).run()
        ok(at, p)


def test_back_button_all_the_way_home():
    at = app(is_phone=True)
    for p in FLOW[:6]:
        at.switch_page(p).run()
    for _ in range(8):  # press ‹ until there is nowhere left to go back to
        back = [b for b in at.button if b.key and b.key.startswith("ptm_back_")]
        if not back:
            break
        back[0].click().run()
        ok(at, "back")


def _act(at, rng: random.Random) -> str:
    """One random user action on the current page; returns a label for the failure message."""
    kinds = []
    kinds += [("seg", w) for w in at.segmented_control if w.key in CHOICES]
    kinds += [("cb", w) for w in at.checkbox]
    kinds += [("sel", w) for w in at.selectbox if len(w.options) > 1]
    kinds += [("radio", w) for w in at.radio]
    kinds += [("txt", w) for w in at.text_input if w.key in ("start_amt", "start_amt_b", "sb_a", "sb_b", "sb_total")]
    kinds += [("btn", w) for w in at.button if w.key and not w.key.startswith("ptm_present")]
    kinds += [("tog", w) for w in at.toggle]
    if not kinds or rng.random() < 0.25:
        p = rng.choice(FLOW)
        at.switch_page(p).run()
        return f"go {p}"
    kind, w = rng.choice(kinds)
    v = None
    if kind == "seg":
        v = rng.choice(CHOICES[w.key])
        w.set_value(v).run()
    elif kind == "cb":
        w.set_value(not w.value).run()
    elif kind in ("sel", "radio"):
        i = rng.randrange(len(w.options))
        # AppTest stores the shown labels and maps them back through format_func; identity makes that lookup work for any
        # formatter (the app re-registers its real one on the next run)
        w.root.session_state[TESTING_KEY][w.id] = lambda x: x
        (w.select_index(i) if kind == "sel" else w.set_value(w.options[i])).run()
        v = i
    elif kind == "txt":
        v = rng.choice(AMOUNTS)
        w.set_value(v).run()
    elif kind == "tog":
        w.set_value(not w.value).run()
    else:
        v = w.label
        w.click().run()
    return f"{kind} {w.key or getattr(w, 'label', '')} → {v if kind != 'cb' else 'toggle'}"


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_random_clicks_never_crash(seed):
    rng = random.Random(seed)
    at = app(is_phone=seed == 3)
    log = []
    for _ in range(60):
        log.append(_act(at, rng))
        assert not at.exception, f"after {log[-8:]}: {[e.value for e in at.exception]}"


def test_custom_picks_then_every_page_and_all_three_portfolios():
    a = RES["picks"]["A"][:12]
    b = RES["picks"]["B"][:10]
    at = app(pick_A=a, pick_B=b)
    for p in FLOW:
        at.switch_page(p).run()
        ok(at, p)
    for key in ("w_which", "t2_which"):
        at.switch_page("views/05_weights.py" if key == "w_which" else "views/07_test2.py").run()
        for v in "ABC":
            next(w for w in at.segmented_control if w.key == key).set_value(v).run()
            ok(at, f"{key}={v}")


def test_every_setting_combination_on_the_heavy_pages():
    at = app(bt_events=[k for k, v in RES["events"].items() if v["available"] and not k.startswith("auto")][:4])
    for mode in ("standard", "event_only"):
        for conf in (0.95, 0.99):
            for hz in (1, 10):
                at.session_state["window_mode"], at.session_state["conf"], at.session_state["horizon"] = mode, conf, hz
                for p in ("views/05_weights.py", "views/06_test1.py", "views/07_test2.py", "views/08_verdict.py"):
                    at.switch_page(p).run()
                    ok(at, f"{p} {mode} {conf} {hz}")


def test_bad_amount_inputs_never_crash():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    for v in AMOUNTS + ["-5 lakh", "1e9", "₹ 15,00,000", "fifteen"]:
        at.text_input(key="start_amt").set_value(v).run()
        ok(at, f"amount {v!r}")


def test_phone_rerenders_do_not_shrink_shared_charts():
    at = app(is_phone=True)
    for _ in range(15):  # the regime chart is cached; resizing it in place once shrank it a little more on every rerun
        at.switch_page("views/06_test1.py").run()
        ok(at, "test1 rerun")


def test_empty_settings_never_crash():
    """A tap on the selected option of a segmented control can hand back None; every page must still work."""
    at = app(conf=None, horizon=None, window_mode=None)
    for p in FLOW:
        at.switch_page(p).run()
        ok(at, p)
    assert at.session_state["conf"] == 0.95 and at.session_state["horizon"] == 1


def test_newly_listed_stocks_are_left_out_not_blocking():
    """Picks with stocks listed after a period starts: the period is tested without them, with a note."""
    a = RES["picks"]["A"][:13] + ["JBMA"]
    b = RES["picks"]["B"][:13] + ["STARHEALTH"]
    evs = [k for k, v in RES["events"].items() if v["available"] and not k.startswith("auto")]
    at = app(pick_A=a, pick_B=b, bt_events=evs)
    for p in ("views/06_test1.py", "views/07_test2.py", "views/08_verdict.py", "views/01_home.py", "views/05_weights.py"):
        at.switch_page(p).run()
        ok(at, p)
    at.switch_page("views/06_test1.py").run()
    body = " ".join(str(getattr(getattr(h, "proto", None), "body", "")) for h in at.get("html"))
    assert "Tested without" in body and "can't be tested" not in body


def test_period_greyed_out_when_more_than_five_stocks_too_new():
    import pandas as pd

    uni = pd.DataFrame(json.loads((ROOT / "results" / "universe.json").read_text())).set_index("symbol")
    new = [s for s in uni.index[pd.to_datetime(uni["first_date"]) > "2010-06-01"] if s not in RES["picks"]["B"]][:6]
    assert len(new) == 6
    for n_new, greyed in ((5, False), (6, True)):
        a = RES["picks"]["A"][:15 - n_new] + new[:n_new]
        at = app(pick_A=a, bt_events=["gfc_2008"] if "gfc_2008" in RES["events"] else [])
        at.switch_page("views/06_test1.py").run()
        ok(at, f"{n_new} new stocks")
        cb = next(c for c in at.checkbox if c.key == "bt_auto_crisis")
        assert cb.disabled == greyed and (not greyed or cb.value is False), (n_new, cb.disabled, cb.value)
