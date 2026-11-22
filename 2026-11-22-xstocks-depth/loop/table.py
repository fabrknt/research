"""The table the loop reads: the hourly medians in summary.jsonl (written by analyze.py --hour in the recorder
job), folded per name, size and session.

usage: python3 -I 2026-11-22-xstocks-depth/loop/table.py summary.jsonl [--since 2026-11-22] [--by day]

Columns are the median over hours of each hour's median (an hour counts once, however many runs it had):
  hours  hours with that cell
  rt     round trip on Jupiter's best route, bp of USD lost
  buy    paid per share vs the xyz mid, bp (above the mid: positive, a cost to the buyer)
  sell   received per share vs the xyz mid, bp (below the mid: negative, a cost to the seller).
         buy - sell is about rt; (buy + sell) / 2 is where Solana's price sits against the xyz mid, so a
         positive sell means the token's price is above the perp's (AAPLx $1k on Sunday 2026-11-22: +9.0)
  hedge  walking the xyz book for the same USD, bp from mid ("-": the 20 levels don't hold it)
  r_buy  per run, what the buyer paid above the xyz mid less what buying the same USD on xyz costs a dealer
         who sold to them, bp; computed only on runs whose xyz book held that USD, then medians as above
  r_sell the mirror for a seller (received below the mid, less selling the same USD on xyz)
  h_b/h_s hours with an r_buy / r_sell: the coverage of the two columns before them
         Both before inventory, funding and margin; the gate in README.md asks whether they stay at tens of bp
--by day adds the UTC day to the key, to see a weekday next to the weekend.
"""

import argparse
import json
import statistics as st
import time
from collections import defaultdict
from datetime import datetime, timezone


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--since", default="2026-11-01")
    ap.add_argument("--by", choices=["day"])
    a = ap.parse_args()
    since = datetime.fromisoformat(a.since).replace(tzinfo=timezone.utc).timestamp()
    cells, seen, first, last = defaultdict(lambda: defaultdict(list)), set(), None, None
    for line in open(a.path):
        if not line.strip():
            continue
        h = json.loads(line)
        if h.get("start") is None or h["start"] < since or h["start"] in seen:
            continue
        seen.add(h["start"])
        first, last = min(first or h["start"], h["start"]), max(last or h["end"], h["end"])
        d = time.strftime("%m-%d", time.gmtime(h["start"]))
        for c in h["cells"]:
            key = (c["sym"], c["usd"], c["sess"]) + ((d,) if a.by else ())
            for k in ("rt", "buy", "sell", "hedge", "r_buy", "r_sell"):
                if c.get(k) is not None:
                    cells[key][k].append(c[k])
    if not seen:
        print("no hours")
        return
    print(f"{len(seen)} hours, {time.strftime('%Y-%m-%d %H:%M', time.gmtime(first))} to "
          f"{time.strftime('%Y-%m-%d %H:%M', time.gmtime(last))} UTC")
    print(f"{'name':7} {'usd':>7} {'sess':6} " + ("day   " if a.by else "")
          + f"{'hours':>5} {'rt':>7} {'buy':>7} {'sell':>7} {'hedge':>6} {'r_buy':>7} {'r_sell':>7} {'h_b':>4} {'h_s':>4}")
    med = lambda v: st.median(v) if v else None
    fmt = lambda x, w=7: f"{x:{w}.1f}" if x is not None else " " * (w - 1) + "-"
    for key, v in sorted(cells.items()):
        rt, by, sl, hg, rb, rs = (med(v[k]) for k in ("rt", "buy", "sell", "hedge", "r_buy", "r_sell"))
        print(f"{key[0]:7} {key[1]:>7} {key[2]:6} " + (f"{key[3]}  " if a.by else "")
              + f"{len(v['rt']):>5} {fmt(rt)} {fmt(by)} {fmt(sl)} {fmt(hg, 6)} {fmt(rb)} {fmt(rs)} {len(v['r_buy']):>4} {len(v['r_sell']):>4}")


if __name__ == "__main__":
    main()
