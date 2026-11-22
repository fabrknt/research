"""What it costs to trade Solana xStocks at size, against the Hyperliquid xyz perp for the same share.

usage: python3 -I recorder/read.py xstocks_quotes --from A --to B > xq.jsonl
       python3 -I 2026-11-22-xstocks-depth/analyze.py xq.jsonl
       python3 -I 2026-11-22-xstocks-depth/analyze.py --hour xstocks_quotes.jsonl.gz   # one JSON line

--hour is what the recorder job runs on the hour it just recorded, before encrypting it: the medians only
(no quote, route or book), appended to the release assets xstocks-loop/summary.{a,b}.jsonl for the loop (loop/).

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

import gzip
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


def collect(rows):
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
        elif k == "hl_book":
            # Each run reads a name's book just before its quotes. A book that failed or has an empty side
            # drops the name's last one, so the quotes after it are never priced against a stale mid.
            lv = r.get("levels")
            if lv and len(lv) == 2 and lv[0] and lv[1]:
                book[r["sym"]] = (lv, (float(lv[0][0]["px"]) + float(lv[1][0]["px"])) / 2)
            else:
                book.pop(r.get("sym"), None)
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
                buy, sell = (usd / shares / mid - 1) * 1e4, (sold / shares / mid - 1) * 1e4
                out[key]["buy"].append(buy)
                out[key]["sell"].append(sell)
                pa, pb = walk(lv[1], usd), walk(lv[0], usd)
                if pa and pb:
                    out[key]["hedge"].append(((pa / mid - 1) + (1 - pb / mid)) / 2 * 1e4)
                # room per side, from the same run: what the buyer paid above the mid, less what buying the
                # same USD on xyz costs a dealer who sold to them (and the mirror for a seller)
                if pa:
                    out[key]["r_buy"].append(buy - (pa / mid - 1) * 1e4)
                if pb:
                    out[key]["r_sell"].append(-sell - (1 - pb / mid) * 1e4)
    return out


def read(path):
    with (gzip.open if path.endswith(".gz") else open)(path, "rt") as f:
        return [json.loads(l) for l in f if l.strip()]


def hour(path):
    rows = read(path)
    med = lambda a: round(st.median(a), 1) if a else None
    cells = [{"sym": sym, "usd": usd, "sess": ses, "n": len(v["rt"]), "rt": med(v["rt"]), "buy": med(v["buy"]),
              "sell": med(v["sell"]), "hedge": med(v["hedge"]), "r_buy": med(v["r_buy"]),
              "r_sell": med(v["r_sell"]), "n_buy": len(v["r_buy"]), "n_sell": len(v["r_sell"]),
              "nc": round(sum(v["nc"]) / len(v["nc"]), 2) if v["nc"] else None}
             for (sym, usd, ses), v in sorted(collect(rows).items())]
    ts = [r["t"] for r in rows if "t" in r]
    print(json.dumps({"start": min(ts, default=None), "end": max(ts, default=None), "cells": cells}))


def main(path):
    out = collect(read(path))
    print(f"{'name':7} {'usd':>7} {'sess':6} {'n':>4} {'rt':>7} {'buy':>7} {'sell':>7} {'hedge':>6} {'nc':>5}")
    for (sym, usd, ses), v in sorted(out.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])):
        med = lambda a: f"{st.median(a):7.1f}" if a else "      -"
        print(f"{sym:7} {usd:>7} {ses:6} {len(v['rt']):>4} {med(v['rt'])} {med(v['buy'])} {med(v['sell'])}"
              f" {med(v['hedge'])[1:]} {sum(v['nc']) / len(v['nc']):5.0%}")


if __name__ == "__main__":
    hour(sys.argv[2]) if sys.argv[1] == "--hour" else main(sys.argv[1])
