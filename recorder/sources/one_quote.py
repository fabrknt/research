"""One round of 2026-11-16-one-quote-vs-books (its collect.py, unchanged): Variational's listing rows and the
Lighter and Hyperliquid books for Variational's 40 busiest markets."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "2026-11-16-one-quote-vs-books"))
import collect  # noqa: E402

REMAP = 6 * 3600  # pick the 40 markets again every 6 hours
_markets: dict = {"at": 0.0, "list": None}


def run(state: dict) -> list[dict]:
    if _markets["list"] is None or time.time() - _markets["at"] > REMAP:
        _markets["list"] = collect.build_map(collect.get(collect.VAR, tries=12))
        _markets["at"] = time.time()
    return collect.round_(_markets["list"])
