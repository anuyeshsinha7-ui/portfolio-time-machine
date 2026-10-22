"""Full audit + optimisation check — run before every commit and push.

    python scripts/audit.py            everything, including the real-browser test of the built site (~5 min)
    python scripts/audit.py --quick    skip the browser test
    python scripts/audit.py --deep     also Safari's engine + Firefox, 360 px phone layout, every link, the Excel download
                                       and a random-click stress run (~15 min) — run before a release

Exits non-zero if any check fails. Speed figures are reported; a page slower than SLOW_PAGE_S fails the check.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import cleaning as CLN  # noqa: E402
from src import config  # noqa: E402
from src import data as D  # noqa: E402
from src import engine as E  # noqa: E402
from src import regimes as RG  # noqa: E402
from src.fmt import pct  # noqa: E402

PY = sys.executable
SLOW_PAGE_S = 3.0  # native render time; the browser is ~5× slower
fails: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(("  PASS " if ok else "  FAIL ") + msg, flush=True)
    if not ok:
        fails.append(msg)


def run(cmd: list[str], timeout: int = 1800) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout + p.stderr


def section(t: str) -> None:
    print(f"\n== {t}", flush=True)


def deep() -> None:
    """Checks that take longer: other browser engines, phone layout, links, download, random clicks."""
    section("Other browser engines (WebKit = Safari, Firefox)")
    for engine in ("webkit", "firefox"):
        code, out = run([PY, "tests/e2e_site.py", "--browser", engine, "--port", "8794" if engine == "webkit" else "8795"], timeout=2400)
        boots = [line.strip() for line in out.splitlines() if "booted" in line]
        check(code == 0 and "ALL PAGES OK" in out, f"{engine}: every page renders · " + " · ".join(boots)
              + ("" if code == 0 else " · " + " | ".join(out.strip().splitlines()[-3:])))

    section("Phone layout, links, Excel download (Chrome)")
    sys.path.insert(0, str(ROOT / "tests"))
    from e2e_site import NAV_PHONE, PAGES, click_nav, serve
    from playwright.sync_api import sync_playwright

    srv = serve(ROOT / "_site", 8796)
    base = "http://127.0.0.1:8796"
    try:  # one failure here is reported, not allowed to stop the rest of the audit
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            page = b.new_context(viewport={"width": 360, "height": 780}, is_mobile=True, has_touch=True).new_page()
            page.goto(base + "/")
            check(not page.evaluate("document.documentElement.scrollWidth > innerWidth + 1"), "landing page: no sideways scroll at 360 px")
            hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
            import urllib.request
            bad = []
            for h in sorted(set(hrefs)):
                if h.startswith(("http://", "https://")):
                    for attempt in range(2):  # one retry: a network blip is not a broken link
                        try:
                            urllib.request.urlopen(urllib.request.Request(h, headers={"User-Agent": "Mozilla/5.0"}), timeout=20)
                            break
                        except Exception as e:  # noqa: BLE001
                            if attempt:
                                bad.append(f"{h} ({e})")
                            time.sleep(3)
            check(not bad, f"{len(set(hrefs))} landing-page links open" + (f": {bad}" if bad else ""))
            page.goto(base + "/app/", wait_until="domcontentloaded")
            page.wait_for_selector("text=How much would you like to invest?", timeout=240_000)
            page.get_by_role("button", name="Continue →").click()
            page.get_by_text(PAGES[0][1]).first.wait_for(timeout=120_000)
            wide = []
            for key, head in PAGES:
                if key != "prefs":
                    click_nav(page, NAV_PHONE[key], True)
                    page.get_by_text(head).first.wait_for(timeout=120_000)
                    page.wait_for_timeout(600)
                if page.evaluate("document.documentElement.scrollWidth > innerWidth + 1"):
                    wide.append(key)
            check(not wide, "every screen fits 360 px without sideways scroll" + (f": {wide}" if wide else ""))
            dpage = b.new_page(viewport={"width": 1440, "height": 950}, accept_downloads=True)
            dpage.goto(base + "/app/", wait_until="domcontentloaded")
            dpage.wait_for_selector("text=How much would you like to invest?", timeout=240_000)
            dpage.get_by_role("button", name="Continue →").click()
            dpage.get_by_text(PAGES[0][1]).first.wait_for(timeout=120_000)
            click_nav(dpage, NAV_PHONE["methodology"], False)
            dpage.get_by_text(dict(PAGES)["methodology"]).first.wait_for(timeout=120_000)
            with dpage.expect_download(timeout=120_000) as d:
                dpage.locator("[data-testid='stDownloadButton'] button").first.click()
            xl = pd.ExcelFile(d.value.path())
            w = pd.read_excel(xl, "Weights today")
            check(set(w["Portfolio"]) == {"A", "B", "C"}, f"Excel download opens: {len(xl.sheet_names)} sheets, A/B/C weights inside")
            b.close()
    except Exception as e:  # noqa: BLE001
        check(False, f"phone/links/download check stopped: {str(e).splitlines()[0]}")
    finally:
        srv.shutdown()

    section("Random clicks (seeded), incl. newly listed stocks and empty settings")
    import random

    from test_stress import RES as SRES
    from test_stress import _act, app
    evs = [k for k, v in SRES["events"].items() if v["available"] and not k.startswith("auto")]
    crashes = []
    for seed in range(4):
        rng = random.Random(100 + seed)
        extra = dict(pick_A=SRES["picks"]["A"][:12] + ["JBMA"], pick_B=SRES["picks"]["B"][:12] + ["STARHEALTH"],
                     bt_events=evs[:6]) if seed % 2 else {}
        at = app(is_phone=seed == 3, **extra)
        log = []
        for _ in range(100):
            if rng.random() < 0.05:
                at.session_state[rng.choice(["conf", "horizon", "window_mode"])] = None
            log.append(_act(at, rng))
            if at.exception:
                crashes.append(f"seed {seed}: {log[-3:]} → {at.exception[0].value}")
                break
    check(not crashes, "400 random actions, no crash" + (f": {crashes}" if crashes else ""))


def main() -> None:
    quick = "--quick" in sys.argv
    t0 = time.time()

    section("Tests and code")
    code, out = run([PY, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"])
    check(code == 0, out.strip().splitlines()[-1])
    code, out = run([PY, "-m", "pyflakes", "app.py", "src", "views", "scripts", "tests"])
    if "No module named pyflakes" in out:
        print("  SKIP lint (pyflakes not installed in this environment)")
    else:
        real = [line for line in out.splitlines() if line and "'.fmt.pct' imported but unused" not in line]  # re-exported
        check(not real, "lint clean" if not real else "lint: " + "; ".join(real[:5]))

    section("Privacy and security")
    tracked = run(["git", "ls-files"])[1].splitlines()
    leaks = [f for f in tracked if any(k in f for k in ("PRESENTATION_", "write_talk", "Faculty", ".env"))]
    check(not leaks, "no speaker notes, course files or env files tracked" + (f": {leaks}" if leaks else ""))
    code, out = run(["git", "grep", "-nIE", r"(ghp_|github_pat_|sk-[A-Za-z0-9]{20}|AKIA[0-9A-Z]{16})", "--", ".", ":!*.csv", ":!scripts/audit.py"])  # not its own pattern
    check(code != 0, "no keys or tokens in tracked files")

    section("Data")
    meta = json.loads((config.DATA_DIR / "metadata.json").read_text())
    check(CLN.checksum_frame(D.prices()) == meta["prices_sha256"] and CLN.checksum_frame(D.benchmark()) == meta["benchmark_sha256"],
          "snapshot matches its fingerprint")
    check(str(D.calendar()[-1].date()) == meta["as_of"], f"returns end on the as-of date {meta['as_of']}")
    m = D.market_returns()
    check(abs(np.cov(m, m)[0, 1] / m.var() - 1) < 1e-9, "Nifty 50 beta to itself = 1")

    section("Assignment rules and risk numbers")
    res = json.loads((config.RESULTS_DIR / "default.json").read_text())
    P, u = res["portfolios"], D.universe()
    a, b = set(P["A"]["symbols"]), set(P["B"]["symbols"])
    check(len(a) >= 10 and len(b) >= 10 and not a & b, f"A {len(a)} / B {len(b)} stocks, no overlap")
    for k, p in P.items():
        w, c = pd.Series(p["weights"]), p["constraints"]
        top = w.groupby(u.loc[w.index, "industry"]).sum().max()
        check(abs(w.sum() - 1) < 1e-5 and w.min() >= c["w_min"] - 1e-6 and w.max() <= c["w_max"] + 1e-6 and top <= c["ind_max"] + 1e-6,
              f"{k} ({p['objective']}) weights: sum {w.sum():.6f}, {w.min():.1%}–{w.max():.1%}, top sector {top:.0%}")
    vr = res["evidence"]["vol_ratio"]
    check(vr["lo"] > 1, f"A riskier than B: σA/σB {vr['ratio']:.2f} (95% {vr['lo']:.2f}–{vr['hi']:.2f})")
    figs = []

    def walk(o):
        if isinstance(o, dict):
            if "var" in o and "es" in o and isinstance(o["var"], float):
                figs.append((o["var"], o["es"]))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(res)
    check(all(v > 0 and e >= v - 1e-12 for v, e in figs), f"{len(figs)} stored VaR/ES figures positive with ES ≥ VaR")
    cases = {r[k]["test2"]["case"] for r in res["regimes"].values() for k in "ABC" if r[k].get("available")}
    check({"reachable"} <= cases and all(k in res["bootstrap"] for k in "ABC"), f"Test #2 cases {sorted(cases)}, noise check for A/B/C")

    section("Optimiser vs cvxpy (independent solver)")
    try:
        import cvxpy as cp

        cs, ce = RG.current_window(D.calendar())
        for k, p in P.items():
            syms = p["symbols"]
            R, _ = E.window_returns(syms, cs, ce)
            mu, S = E.mu_sigma(R)
            cons = E.constraints_of(p)
            w, n, A = np.array([p["weights"][s] for s in syms]), len(syms), cons.A_ind(len(syms))
            base = [cp.sum(x := cp.Variable(n)) == 1, x >= cons.w_min, x <= cons.w_max, A @ x <= cons.ind_max]
            if p["objective"] == "max_return":
                cp.Problem(cp.Maximize(mu @ x), base).solve()
                check(mu @ w >= mu @ x.value - 1e-6, f"{k} max return {mu @ w:.6f} vs cvxpy {mu @ x.value:.6f}")
            elif p["objective"] == "min_variance":
                cp.Problem(cp.Minimize(cp.quad_form(x, cp.psd_wrap(S))), base).solve()
                check(w @ S @ w <= x.value @ S @ x.value * (1 + 1e-4), f"{k} min variance {w @ S @ w:.8f} vs cvxpy {x.value @ S @ x.value:.8f}")
            else:
                rf = config.RISK_FREE_RATE
                y, t = cp.Variable(n), cp.Variable()
                cp.Problem(cp.Minimize(cp.quad_form(y, cp.psd_wrap(S))),
                           [(mu - rf) @ y == 1, cp.sum(y) == t, t >= 0, y >= cons.w_min * t, y <= cons.w_max * t, A @ y <= cons.ind_max * t]).solve()
                sh = lambda v: (mu @ v - rf) / np.sqrt(v @ S @ v)  # noqa: E731
                check(sh(w) >= sh(y.value / t.value) - 1e-4, f"{k} max Sharpe {sh(w):.6f} vs cvxpy {sh(y.value / t.value):.6f}")
    except ImportError:
        print("  SKIP cvxpy not installed")

    section("Numbers agree across documents")
    off = res["official"]
    cr = res["regimes"][f"{off['crisis']}|standard"]
    es = [cr[k]["risk"]["Historical"][config.RULE_KEY]["es"] for k in "AB"]
    want = [pct(x) for x in es] + [f"{P['C']['sharpe']:.2f}"]  # the landing page prints 1 decimal
    summary = (config.DOCS_DIR / "RESULTS_SUMMARY.md").read_text()
    in_sum = [pct(x, 2) for x in es] + [want[2]]  # the summary prints 2 decimals
    check(all(v in summary for v in in_sum), f"results summary quotes crisis ES95 {in_sum[0]} / {in_sum[1]} and C Sharpe {in_sum[2]}")
    landing = ROOT / "_site" / "index.html"
    if landing.exists():
        check(all(v in landing.read_text() for v in want), "landing page quotes the same figures")

    section("Reproducible results")
    before = hashlib.sha256((config.RESULTS_DIR / "default.json").read_bytes()).hexdigest()
    code, out = run([PY, "scripts/precompute.py"])
    after = hashlib.sha256((config.RESULTS_DIR / "default.json").read_bytes()).hexdigest()
    check(code == 0 and before == after, "re-running the precompute gives byte-identical results")

    section("Speed (native render per page; the browser is ~5× slower)")
    from streamlit.testing.v1 import AppTest

    pages = ["views/01_prefs.py", "views/01_suggest.py", "views/05_weights.py", "views/06_test1.py", "views/07_test2.py",
             "views/08_verdict.py", "views/01_home.py", "views/02_how.py", "views/03_pick.py", "views/04_call.py", "views/09_methodology.py"]
    for label, state in (("recommended picks", {}),
                         ("own picks", {"pick_A": res["picks"]["A"][:12], "pick_B": res["picks"]["B"][:11]})):
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=600)
        at.session_state["amount_confirmed"], at.session_state["is_phone"] = True, False
        for k, v in state.items():
            at.session_state[k] = v
        at.run()
        times = {}
        for pg in pages + pages:  # second lap = what a click costs once the caches are warm
            t = time.time()
            at.switch_page(pg).run()
            times[pg] = time.time() - t
            if at.exception:
                fails.append(f"{pg} raised {at.exception[0].value}")
        slow = {Path(k).stem: round(v, 2) for k, v in sorted(times.items(), key=lambda x: -x[1])[:3]}
        check(max(times.values()) < SLOW_PAGE_S, f"{label}: slowest warm pages {slow} (limit {SLOW_PAGE_S}s)")
    size = sum(p.stat().st_size for p in (ROOT / "_site").rglob("*") if p.is_file()) / 1e6 if (ROOT / "_site").exists() else 0
    print(f"  INFO site payload {size:.1f} MB (results/default.json {(config.RESULTS_DIR / 'default.json').stat().st_size / 1e6:.2f} MB)")

    if not quick:
        section("Real browser: built site, desktop + phone, refresh")
        code, out = run([PY, "scripts/build_site.py"])
        check(code == 0, "site builds")
        code, out = run([PY, "tests/e2e_site.py"], timeout=1800)
        boots = [line.strip() for line in out.splitlines() if "booted" in line]
        check(code == 0 and "ALL PAGES OK" in out, "every page renders in a real browser; refresh returns to the same screen · "
              + " · ".join(boots))

    if "--deep" in sys.argv:
        deep()
    print(f"\n{'ALL CHECKS PASSED' if not fails else f'{len(fails)} FAILED'} in {time.time() - t0:.0f}s")
    for f in fails:
        print("  ✗", f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
