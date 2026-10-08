"""Every assumption of the project in one place (brief §6.0).

Nothing in ``src/`` imports Streamlit; the app and the scripts read these values.
Edit here, rebuild with ``scripts/precompute.py``, and every page follows.
"""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
RESULTS_DIR = ROOT / "results"
DOCS_DIR = ROOT / "docs"

# ---------------------------------------------------------------- app identity
APP_NAME = "Portfolio Time Machine"
TAGLINE = "Does 'safe' stay safe when the market crashes?"
TEAM = ["[Name 1]", "[Name 2]", "[Name 3]", "[Name 4]"]
CREDIT_LINE = "PGDM, Great Lakes Institute of Management, Gurgaon"
GITHUB_USER = "anuyeshsinha7-ui"
REPO_NAME = "portfolio-time-machine"
REPO_URL = f"https://github.com/{GITHUB_USER}/{REPO_NAME}"
LIVE_URL = f"https://{GITHUB_USER}.github.io/{REPO_NAME}/"

# ---------------------------------------------------------------- amounts (₹)
AMOUNT_A = 15_00_000
AMOUNT_B = 15_00_000
AMOUNT_MODE = "same_each"  # "same_each" | "split_total" | "separate"
AMOUNT_MODES = {
    "same_each": "The same amount in each portfolio",
    "split_total": "One total, split half-and-half between A and B",
    "separate": "Two separate amounts",
}
AMOUNT_MIN = 10_000
AMOUNT_MAX = 100_00_00_000
AMOUNT_PRESETS = [1_00_000, 5_00_000, 15_00_000, 50_00_000, 1_00_00_000]

# ---------------------------------------------------------------- data
HISTORY_START = "2007-09-17"
UNIVERSE = "NIFTY 200"
BENCHMARK = "^NSEI"
VIX = "^INDIAVIX"
TRADING_DAYS = 252
FALLBACK_HISTORY_YEARS = 15

# ---------------------------------------------------------------- classification & regimes
CLASSIFICATION_YEARS = 3
REGIME_DAYS = 252
EVENT_PRE_DAYS = 21
EVENT_WINDOW_MODE = "standard"  # "standard" | "event_only"
MIN_WINDOW_DAYS = 126
CALM_ANCHOR_DAYS = 126  # length of the lowest-volatility stretch that anchors a calm event
EVENTS_FILE = DATA_DIR / "events.json"
OFFICIAL_CRISIS_EVENT = "auto"  # an id from events.json, or "auto"
OFFICIAL_CALM_EVENT = "auto"

# ---------------------------------------------------------------- risk measures
CONFIDENCE = [0.95, 0.99]
ES_BASEL = 0.975
HORIZONS = [1, 10]
MC_DRAWS = 10_000
T_DOF_FLOOR = 3.0
BOOTSTRAP_RESAMPLES = 500
BOOTSTRAP_RESAMPLES_BROWSER = 200
BLOCK_DAYS = 5
SEED = 42

# ---------------------------------------------------------------- optimisation
W_MIN = 0.02
W_MAX = 0.25
INDUSTRY_MAX = 0.40
MIN_STOCKS = 10
MAX_STOCKS = 20
MAX_PER_INDUSTRY_PICK = 3
OBJECTIVE_A = "max_sharpe"
OBJECTIVE_B = "min_variance"
FRONTIER_POINTS = 60
RANDOM_PORTFOLIOS = 5_000
RANDOM_PORTFOLIOS_BROWSER = 2_000

# Latest 91-day Treasury bill cut-off yield (Reserve Bank of India auction of 7 Oct 2026,
# press release 2026-2027/1268). Annual, simple. See DECISIONS.md.
RISK_FREE_RATE = 0.055747
RISK_FREE_SOURCE = (
    "Reserve Bank of India, '91-Day, 182-Day and 364-Day T-Bill Auction Result: Cut-off', "
    "press release 2026-2027/1268, 7 Oct 2026 — 91-day implicit yield 5.5747%"
)
RISK_FREE_URL = "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63746"

# ---------------------------------------------------------------- portfolios (empty → data-driven picker)
PORTFOLIO_A: list[str] = []
PORTFOLIO_B: list[str] = []

# ---------------------------------------------------------------- cleaning
MAX_FFILL = 2
MAX_MISSING_PCT = 0.02
JUMP_FLAG = 0.20
SPIKE_REVERT = 0.15
SPIKE_REVERT_TOL = 0.03
STALE_DAYS = 5
STALE_EXCLUDE_DAYS = 10
SPLIT_TOLERANCE = 0.03
ADJ_MISMATCH_TOL = 0.005
STITCH_TOL = 0.01
SPLIT_RATIOS = {  # price ratio P_t / P_{t-1} → description
    1 / 2: "split 1:2 or bonus 1:1",
    1 / 3: "split 1:3 or bonus 2:1",
    1 / 4: "split 1:4 or bonus 3:1",
    1 / 5: "split 1:5 (e.g. face value ₹10 → ₹2)",
    1 / 10: "split 1:10 (e.g. face value ₹10 → ₹1)",
    2 / 3: "bonus 1:2",
    3 / 4: "bonus 1:3",
}

# ---------------------------------------------------------------- colours (one system, brief §9)
COLOR_A = "#E8735A"  # warm coral
COLOR_B = "#3B7DD8"  # cool blue
COLOR_NIFTY = "#8A8F98"  # grey
COLOR_CRISIS = "#D64545"
COLOR_CALM = "#2E9E5B"
COLOR_CRISIS_FILL = "rgba(214,69,69,0.13)"
COLOR_CALM_FILL = "rgba(46,158,91,0.13)"
COLOR_INK = "#E6E9EF"
COLOR_MUTED = "#9AA3B5"
COLOR_BG = "#0B0F17"
COLOR_PANEL = "#161D2C"
COLOR_ACCENT = "#E8735A"

FOOTER = (
    "Educational project — not investment advice. "
    "Data: Yahoo Finance (via yfinance) and NSE, as of {date}."
)
