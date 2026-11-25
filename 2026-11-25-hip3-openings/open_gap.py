"""The first hours of a new Hyperliquid listing: its book against the oracle.

    python3 -I 2026-11-25-hip3-openings/open_gap.py --from 2026-11-24 --to 2026-11-26 xyz:SOXS xyz:TQQQ io:GOOGL

Reads the recorder's `events` books (every 10 s while a name is hot) and `hl_ctx` (each minute, for the oracle)
through recorder/read.py, which needs the private key. The opening is the first two-sided book after the
name's "new" trigger. For each window after it, the medians of: |mid - oracle| in bp, the spread in bp, the
notional an order could take at a price better than the oracle by more than FEE_BP ("crossable"), and the
notional within 50 bp of the mid on each side.
"""

import argparse
import bisect
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEE_BP = 10  # taker fee plus a little slippage, assumed for a HIP-3 market
NEAR = 0.005
WINDOWS = [("0-5m", 0, 300), ("5-15m", 300, 900), ("15-30m", 900, 1800), ("30-60m", 1800, 3600),
           ("1-6h", 3600, 6 * 3600), ("6-72h", 6 * 3600, 72 * 3600)]


def rows(source: str, since: str, until: str):
    p = subprocess.Popen([sys.executable, "-I", str(ROOT / "recorder/read.py"), source, "--from", since, "--to", until],
                         stdout=subprocess.PIPE, text=True)
    for line in p.stdout:
        yield json.loads(line)
    if p.wait():
        raise SystemExit(f"read.py {source} failed")


def hhmm(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%m-%d %H:%M:%S")


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--from", dest="since", required=True)
    a.add_argument("--to", dest="until", required=True)
    a.add_argument("names", nargs="+")
    args = a.parse_args()
    names = set(args.names)

    opened, books = {}, defaultdict(list)
    for r in rows("events", args.since, args.until):
        if r.get("name") not in names:
            continue
        if r["kind"] == "trigger" and r["why"] == "new":
            opened.setdefault(r["name"], r["t"])
        elif r["kind"] == "book" and "hl" in r:
            books[r["name"]].append(r)
    oracle = defaultdict(list)
    for r in rows("hl_ctx", args.since, args.until):
        for n, c in zip(r["names"], r["ctxs"]):
            if n in names:
                oracle[n].append((r["t"], float(c["oraclePx"])))

    for n in args.names:
        series = sorted(oracle[n])
        times = [t for t, _ in series]
        bs = sorted(books[n], key=lambda r: r["t"])
        if n not in opened:
            print(f"\n== {n}: no 'new' trigger in the range")
            continue
        first = next((r for r in bs if r["t"] >= opened[n] - 60 and r["hl"]["bids"] and r["hl"]["asks"]), None)
        if not first:
            print(f"\n== {n}: no two-sided book after it opened")
            continue
        t0 = first["t"]
        print(f"\n== {n}  opened {hhmm(opened[n])}  first two-sided book {hhmm(t0)}  books {len(bs)}")
        print("window   books  |dev|bp med   max   spread bp  crossable$ med    max   bids$ near  asks$ near")
        for label, lo, hi in WINDOWS:
            got = []
            for r in bs:
                if not lo <= r["t"] - t0 < hi:
                    continue
                i = bisect.bisect_right(times, r["t"]) - 1
                bids = [(float(p), float(s)) for p, s in r["hl"]["bids"]]
                asks = [(float(p), float(s)) for p, s in r["hl"]["asks"]]
                if i < 0 or not bids or not asks:
                    continue
                o = series[i][1]
                mid = (bids[0][0] + asks[0][0]) / 2
                k = 1 + FEE_BP / 1e4
                got.append((abs(mid / o - 1) * 1e4, (asks[0][0] / bids[0][0] - 1) * 1e4,
                            sum(p * s for p, s in asks if p * k < o) + sum(p * s for p, s in bids if p > o * k),
                            sum(p * s for p, s in bids if p >= mid * (1 - NEAR)),
                            sum(p * s for p, s in asks if p <= mid * (1 + NEAR))))
            if not got:
                print(f"{label:8} {0:5}  (no books: not hot, or not recorded)")
                continue
            med = lambda j: sorted(x[j] for x in got)[len(got) // 2]
            top = lambda j: max(x[j] for x in got)
            print(f"{label:8} {len(got):5} {med(0):11.1f} {top(0):6.1f} {med(1):10.1f} {med(2):14,.0f} {top(2):7,.0f}"
                  f" {med(3):11,.0f} {med(4):11,.0f}")


if __name__ == "__main__":
    main()
