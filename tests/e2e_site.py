"""Playwright smoke test of the built site (_site/): landing page, amount hand-off, every dashboard page under
stlite, on desktop and phone viewports. Fails on any Python exception shown by Streamlit.

    python tests/e2e_site.py [--screens docs/screenshots] [--port 8791]
Also collected by pytest when RUN_E2E=1 (test_e2e_site).
"""
from __future__ import annotations

import argparse
import functools
import http.server
import os
import socketserver
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = [("prefs", "Where would you like to invest?"), ("suggest", "Suggested for you"), ("weights", "Your portfolios right now"),
         ("test1", "What if a crisis hit?"), ("test2", "How should the weights change?"), ("verdict", "Does 'safe' stay safe?"),
         ("home", "Your money in two portfolios"), ("how", "5 simple steps"), ("pick", "Build your portfolios"),
         ("call", "Why A is the bold one"), ("methodology", "Checked against the exchange")]


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve(site: Path, port: int):
    srv = socketserver.TCPServer(("127.0.0.1", port), functools.partial(Quiet, directory=str(site)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def errors_on(page) -> list[str]:
    return [e.inner_text()[:600] for e in page.query_selector_all('[data-testid="stException"]')]


def click_nav(page, label: str, phone: bool) -> None:
    if True:  # desktop and phone both navigate through the app's tab bar
        tab = page.locator(".st-key-ptm_tabs").get_by_text(label, exact=True)
        if tab.count():
            tab.first.click()
            return
        body = page.locator('[data-testid="stPopoverBody"]').get_by_text(label, exact=True)
        if not (body.count() and body.first.is_visible()):
            page.locator(".st-key-ptm_tabs").get_by_role("button").last.click()
        body.first.click()


NAV_DESKTOP = {"home": "Home — the 30-second verdict", "how": "How this app works", "pick": "Pick stocks", "call": "The risk call",
               "weights": "Optimum weights today", "test1": "Test #1 — the risk label", "test2": "Test #2 — the allocation",
               "verdict": "Verdict & recommendation", "methodology": "Methodology & data"}
NAV_PHONE = {"prefs": "Choose", "suggest": "Suggested portfolios", "weights": "Today", "test1": "Backtest", "test2": "Rebalance",
             "verdict": "Verdict", "home": "Summary", "how": "How it works", "pick": "Edit stocks", "call": "The risk call",
             "methodology": "About the data"}


def run(site: Path, port: int = 8791, screens: Path | None = None, amount: int = 2500000, url: str | None = None) -> list[str]:
    from playwright.sync_api import sync_playwright

    problems: list[str] = []
    srv = None if url else serve(site, port)
    base = (url or f"http://127.0.0.1:{port}").rstrip("/")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for label, vp, phone in (("desktop", {"width": 1440, "height": 900}, False),
                                     ("phone", {"width": 390, "height": 844}, True)):
                ctx = browser.new_context(viewport=vp, device_scale_factor=2 if phone else 1, is_mobile=phone, has_touch=phone)
                page = ctx.new_page()
                page.on("pageerror", lambda e: problems.append(f"JS error: {e}"))
                # landing page and amount hand-off
                t0 = time.time()
                page.goto(base + "/")
                print(f"[{label}] landing page loaded in {time.time() - t0:.1f}s")
                if "Portfolio Time Machine" not in page.title():
                    problems.append(f"{label}: landing page title missing")
                if screens:
                    page.screenshot(path=str(screens / f"{label}_landing.png"), full_page=True)
                page.goto(base + f"/app/?amount={amount}")
                page.wait_for_selector("text=How much would you like to invest?", timeout=240_000)
                boot = time.time() - t0
                print(f"[{label}] dashboard booted in {boot:.1f}s")
                if "25,00,000" not in page.inner_text("body") and "25 lakh" not in page.inner_text("body"):
                    problems.append(f"{label}: amount from the landing page did not carry through")
                if screens:
                    page.screenshot(path=str(screens / f"{label}_00_start.png"), full_page=not phone)
                page.get_by_role("button", name="Continue →").click()
                page.get_by_text("Where would you like to invest?").first.wait_for(timeout=120_000)
                for key, heading in PAGES:
                    if key != "prefs":
                        click_nav(page, NAV_PHONE[key], phone)
                        page.get_by_text(heading).first.wait_for(timeout=120_000)
                    time.sleep(2.5)
                    err = errors_on(page)
                    if err:
                        problems.append(f"{label} {key}: {err}")
                    if screens:
                        page.screenshot(path=str(screens / f"{label}_{PAGES.index((key, heading)) + 1:02d}_{key}.png"),
                                        full_page=not phone)
                    print(f"[{label}] {key}: {'OK' if not err else 'ERROR'}")
                ctx.close()
            browser.close()
    finally:
        if srv:
            srv.shutdown()
    return problems


def test_e2e_site():
    import pytest

    if os.environ.get("RUN_E2E") != "1":
        pytest.skip("set RUN_E2E=1 to run the browser smoke test")
    assert run(ROOT / "_site") == []


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--screens", type=Path)
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--url", help="test a deployed site instead of _site/")
    a = ap.parse_args()
    if a.screens:
        a.screens.mkdir(parents=True, exist_ok=True)
    probs = run(ROOT / "_site", a.port, a.screens, url=a.url)
    print("\n".join(probs) if probs else "ALL PAGES OK")
    sys.exit(1 if probs else 0)
