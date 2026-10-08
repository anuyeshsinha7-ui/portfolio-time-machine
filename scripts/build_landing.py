"""Static landing page (placeholder; replaced in P4)."""
from pathlib import Path


def main(site: Path) -> None:
    (site / "index.html").write_text('<!doctype html><meta charset="utf-8"><a href="app/?amount=1500000">Open</a>')
