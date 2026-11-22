"""What it costs to trade Solana xStocks at size, against the Hyperliquid xyz perp for the same share.

usage: python3 -I recorder/read.py xstocks_quotes --from A --to B > xq.jsonl
       python3 -I 2026-11-22-xstocks-depth/analyze.py xq.jsonl

Per name and size, medians over the recorded runs, split into US market hours (Mon-Fri 14:30-21:00 UTC,
no holiday calendar) and the rest:
  rt     round trip on Jupiter's best route: buy with USD, sell that back, bp of USD lost
  buy    price paid per share vs the xyz mid, bp (raw-unit price divided by the scaledUiAmount multiplier)
  sell   price received per share vs the xyz mid, bp
  hedge  walking the xyz book for the same USD, bp from mid, buy and sell averaged ("-" when the
         20 levels the API returns don't hold it)
  nc     share of runs whose best route has any leg not labelled as a curve pool (CURVE). It overcounts
         prop AMMs: a route that goes USDC -> SOL -> xStock counts its prop AMM SOL/USDC leg too (the
         recorder keeps each leg's pool account, not its mints)
"""

import json
import statistics as st
import sys
import time
from collections import defaultdict

CURVE = {"Raydium CLMM", "Whirlpool", "Meteora DLMM", "Raydium", "Byreal", "Orca", "Meteora", "Raydium CPMM"}


def walk(levels, usd):
    got = cost = 0.0
    for l in levels:
        p, s = float(l["px"]), float(l["sz"])
        take = min(s, (usd - cost) / p)
        got, cost = got + take, cost + take * p
        if cost >= usd - 1e-6:
            return cost / got
    return None


def session(t):
    g = time.gmtime(t)
    m = g.tm_hour * 60 + g.tm_min
    return "open" if g.tm_wday < 5 and 870 <= m < 1260 else "closed"


def main(path):
    rows = [json.loads(l) for l in open(path)]
    mult, book = {}, {}
    pend = {}
    out = defaultdict(lambda: defaultdict(list))
    for r in rows:
        k = r.get("kind")
        if k == "mint" and "sym" in r:
            c = r.get("scaled") or {}
            m = float(c.get("multiplier", 1))
            if c and r["t"] >= c.get("newMultiplierEffectiveTimestamp", 0):
                m = float(c["newMultiplier"])
            mult[r["sym"]] = m
        elif k == "hl_book" and r.get("levels"):
            b, a = r["levels"]
            book[r["sym"]] = (r["levels"], (float(b[0]["px"]) + float(a[0]["px"])) / 2)
        elif k == "quote" and r["venue"] == "any" and "out" in r:
            sym, usd = r["sym"], r["usd"]
            if r["side"] == "buy":
                pend[(sym, usd)] = r
                continue
            b = pend.pop((sym, usd), None)
            if not b:
                continue
            key = (sym, usd, session(r["t"]))
            m = mult.get(sym, 1.0)
            shares = b["out"] / 1e8 * m
            sold = r["out"] / 1e6
            out[key]["rt"].append((usd - sold) / usd * 1e4)
            labels = {x[0] for x in b["route"]} | {x[0] for x in r["route"]}
            out[key]["nc"].append(bool(labels - CURVE))
            if sym in book:
                lv, mid = book[sym]
                out[key]["buy"].append((usd / shares / mid - 1) * 1e4)
                out[key]["sell"].append((sold / shares / mid - 1) * 1e4)
                pa, pb = walk(lv[1], usd), walk(lv[0], usd)
                if pa and pb:
                    out[key]["hedge"].append(((pa / mid - 1) + (1 - pb / mid)) / 2 * 1e4)
    print(f"{'name':7} {'usd':>7} {'sess':6} {'n':>4} {'rt':>7} {'buy':>7} {'sell':>7} {'hedge':>6} {'nc':>5}")
    for (sym, usd, ses), v in sorted(out.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])):
        med = lambda a: f"{st.median(a):7.1f}" if a else "      -"
        print(f"{sym:7} {usd:>7} {ses:6} {len(v['rt']):>4} {med(v['rt'])} {med(v['buy'])} {med(v['sell'])}"
              f" {med(v['hedge'])[1:]} {sum(v['nc']) / len(v['nc']):5.0%}")


if __name__ == "__main__":
    main(sys.argv[1])
