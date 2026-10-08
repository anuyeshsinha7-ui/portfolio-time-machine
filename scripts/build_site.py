"""Assemble _site/ for GitHub Pages: the static landing page, the stlite app and every file it needs.

    _site/index.html          landing page (static HTML generated from results/default.json)
    _site/app/index.html      stlite loader (Streamlit running on Pyodide in the browser)
    _site/app/files/...       app.py, src/, views/, .streamlit/config.toml, data snapshot, results

Nothing here is maintained by hand: the file list is generated from the repository.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import config  # noqa: E402

SITE = ROOT / "_site"
STLITE_VERSION = "1.9.2"
REQUIREMENTS = ["numpy", "pandas", "scipy", "plotly==5.24.1", "openpyxl==3.1.5"]

APP_FILES = ["app.py", ".streamlit/config.toml"]
APP_GLOBS = ["src/*.py", "views/*.py"]
DATA_FILES = ["data/prices.csv.gz", "data/benchmark.csv.gz", "data/universe.csv", "data/metadata.json",
              "data/excluded_returns.csv", "data/events.json", "data/data_quality_report.csv",
              "data/corporate_actions.csv", "data/symbol_changes.csv", "data/spot_checks.csv", "data/nse_anchor.csv",
              "results/default.json", "results/universe.json"]
SKIP_SRC = {"src/cleaning.py"}  # local build only


def app_file_list() -> list[str]:
    files = list(APP_FILES)
    for g in APP_GLOBS:
        files += sorted(str(p.relative_to(ROOT)) for p in ROOT.glob(g) if str(p.relative_to(ROOT)) not in SKIP_SRC)
    return files + DATA_FILES


def write_loader(files: list[str]) -> None:
    theme = {"theme.base": "dark", "theme.primaryColor": config.COLOR_ACCENT, "theme.backgroundColor": config.COLOR_BG,
             "theme.secondaryBackgroundColor": config.COLOR_PANEL, "theme.textColor": config.COLOR_INK,
             "theme.font": "sans serif", "client.toolbarMode": "minimal"}
    file_map = {f: {"url": f"files/{f}"} for f in files}
    tpl = (ROOT / "site_src" / "app" / "index.html").read_text()
    html = (tpl.replace("{{STLITE_VERSION}}", STLITE_VERSION)
               .replace("{{FILES}}", json.dumps(file_map, indent=1))
               .replace("{{REQUIREMENTS}}", json.dumps(REQUIREMENTS))
               .replace("{{CONFIG}}", json.dumps(theme))
               .replace("{{APP_NAME}}", config.APP_NAME))
    (SITE / "app" / "index.html").write_text(html)


def main() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "app" / "files").mkdir(parents=True)
    files = app_file_list()
    for f in files:
        dst = SITE / "app" / "files" / f
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / f, dst)
    write_loader(files)
    import build_landing  # noqa: E402  (scripts/ is on the path when run as a script)
    build_landing.main(SITE)
    for extra in (ROOT / "site_src" / "static").glob("*") if (ROOT / "site_src" / "static").exists() else []:
        shutil.copy2(extra, SITE / extra.name)
    (SITE / ".nojekyll").write_text("")
    total = sum(p.stat().st_size for p in SITE.rglob("*") if p.is_file())
    print(f"_site built: {len(files)} app files, {total / 1e6:.1f} MB")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
