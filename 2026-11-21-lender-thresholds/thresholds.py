"""Do the liquidation thresholds Solana lenders set on tokenized stocks survive the moves the stocks
have made while their market was shut?

    python3 -I thresholds.py   # -> results/lenders.csv, closures.csv, exceedances.csv, printed tables

Two inputs, both read live:

1. Each lender's parameters today. Kamino (on-chain): the reserves of its three stock markets
   (xStocks, Sentora xStocks, Backpack), listed by Kamino's API and decoded from the reserve
   accounts (loan-to-value and liquidation threshold, u8 percent at offset 4872 and 4873; the
   largest liquidation bonus, u16 bp at 4876). Jupiter Lend: its public borrow-vault API
   (collateralFactor, liquidationThreshold and liquidationPenalty, in 0.1% / 0.1% / 0.01%).
2. Daily bars for each underlying from Yahoo's chart API, split- and dividend-adjusted (open
   scaled by adjclose / close), from the first bar Yahoo has. A closure is one previous close to
   the next open; it is a weekend if the open is on a Monday 3 days later, a holiday if longer,
   and a weeknight otherwise (the kind says when the market was shut, not why the price moved).

A position sitting exactly at the liquidation threshold LT when the market shuts is still covered
by a full liquidation at the open after a fall D if

    LT (1 + b) (1 + i) <= (1 - D) (1 - s)

adapted from the condition LlamaRisk used for Aave V4's Equities Hub (2026-09-21), on daily bars
close to open rather than its off-hours minute paths: b the liquidation bonus or penalty, i the
interest over the closure (24% a year over 92.6 h, 0.25%, as LlamaRisk), s the cost of selling
the seized collateral (1%). The break-even fall is D* = 1 - LT (1 + b) (1 + i) / (1 - s); a
closure with a larger fall fails this coverage test. The test assumes nothing is liquidated
between the close and the open; what a lender on a live out-of-hours price could do earlier, and
at what cost, is not measured.

Only derived numbers (bp, dates, counts) are written. No prices.
"""
import base64
import csv
import datetime as dt
import json
import os
import statistics
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
HERE = os.path.dirname(os.path.abspath(__file__))
KAMINO = {
    "Kamino xStocks": "5wJeMrUYECGq41fxRESKALVcHnNX26TAWy4W98yULsua",
    "Kamino Sentora xStocks": "8BNUWRSibVasaAmhYpBCFpGgMisGKfVAf9ho3Cmf6vjr",
    "Kamino Backpack": "4iRHKGsTq3e4uut6e4PfyV9AEbNuXaMu9JaSP378p9qy",
}
INTEREST = 0.24 * 92.6 / (365 * 24)
SLIPPAGE = 0.01
# token symbol -> Yahoo ticker of the underlying
UNDERLYING = {
    "SPYx": "SPY", "QQQx": "QQQ", "TSLAx": "TSLA", "NVDAx": "NVDA", "AAPLx": "AAPL", "GOOGLx": "GOOGL",
    "METAx": "META", "MSTRx": "MSTR", "HOODx": "HOOD", "CRCLx": "CRCL", "SKHY": "SKHY", "MU": "MU",
    "SNDK": "SNDK", "SPCX": None,  # SpaceX: no listed underlying
}


def get(url, body=None):
    req = urllib.request.Request(url, json.dumps(body).encode() if body else None, UA)
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def rpc(method, params):
    return get("https://api.mainnet-beta.solana.com", {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})["result"]


def lenders():
    rows = []
    for name, market in KAMINO.items():
        reserves = get(f"https://api.kamino.finance/kamino-market/{market}/reserves/metrics?env=mainnet-beta")
        accounts = rpc("getMultipleAccounts", [[r["reserve"] for r in reserves], {"encoding": "base64"}])["value"]
        for r, a in zip(reserves, accounts):
            b = base64.b64decode(a["data"][0])
            if b[4872] != round(float(r["maxLtv"]) * 100):
                raise SystemExit(f"{name} {r['liquidityToken']}: LTV at 4872 is {b[4872]}, the API says {r['maxLtv']}")
            if r["liquidityToken"] in UNDERLYING:
                rows.append({"lender": name, "token": r["liquidityToken"], "ltv": b[4872] / 100, "lt": b[4873] / 100,
                             "bonus": int.from_bytes(b[4876:4878], "little") / 1e4,
                             "supply_usd": round(float(r["totalSupplyUsd"]))})
    for v in get("https://lite-api.jup.ag/lend/v1/borrow/vaults"):
        t = v["supplyToken"]["symbol"]
        if t in UNDERLYING:
            supply = int(v["totalSupply"]) / 10 ** v["supplyToken"]["decimals"] * float(v["supplyToken"]["price"])
            rows.append({"lender": f"Jupiter Lend ({v['borrowToken']['symbol']})", "token": t,
                         "ltv": int(v["collateralFactor"]) / 1000, "lt": int(v["liquidationThreshold"]) / 1000,
                         "bonus": int(v["liquidationPenalty"]) / 1e4, "supply_usd": round(supply)})
    return rows


def closures(ticker):
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ticker)}"
         f"?interval=1d&period1=0&period2={int(dt.datetime(2026, 11, 21).timestamp())}&events=div,split")
    r = get(u)["chart"]["result"][0]
    q, adj = r["indicators"]["quote"][0], r["indicators"]["adjclose"][0]["adjclose"]
    bars = []
    for t, o, c, a in zip(r["timestamp"], q["open"], q["close"], adj):
        if o and c and a:
            bars.append((dt.datetime.fromtimestamp(t, dt.timezone.utc).date(), o * a / c, a))
    out = []
    for (d0, _, c0), (d1, o1, _) in zip(bars, bars[1:]):
        days = (d1 - d0).days
        kind = "weekend" if days == 3 and d1.weekday() == 0 else "holiday" if days > 1 else "weeknight"
        out.append((d0, d1, kind, o1 / c0 - 1))
    return out


def main():
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    params = lenders()
    gaps = {}
    for ticker in sorted({UNDERLYING[p["token"]] for p in params if UNDERLYING[p["token"]]}):
        gaps[ticker] = closures(ticker)

    with open(os.path.join(HERE, "results", "closures.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "first", "kind", "n", "p99_fall_bp", "max_fall_bp", "max_fall_open", "max_rise_bp", "max_rise_open"])
        print("closure moves, previous close -> next open (adjusted)")
        for ticker, g in gaps.items():
            for kind in ("weeknight", "weekend", "holiday", "any"):
                sel = [x for x in g if kind == "any" or x[2] == kind]
                if not sel:
                    continue
                falls = sorted(-x[3] for x in sel)
                lo, hi = min(sel, key=lambda x: x[3]), max(sel, key=lambda x: x[3])
                p99 = falls[int(0.99 * (len(falls) - 1))]
                w.writerow([ticker, g[0][0], kind, len(sel), round(p99 * 1e4), round(-lo[3] * 1e4), lo[1],
                            round(hi[3] * 1e4), hi[1]])
                print(f"  {ticker:5} {kind:9} n={len(sel):5} since {g[0][0]}  p99 fall {p99:6.1%}  "
                      f"max fall {-lo[3]:6.1%} ({lo[1]})  max rise {hi[3]:6.1%} ({hi[1]})")

    with open(os.path.join(HERE, "results", "exceedances.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "close_day", "open_day", "kind", "move_bp"])  # every |move| over 10%
        for ticker, g in gaps.items():
            for d0, d1, kind, x in g:
                if abs(x) > 0.10:
                    w.writerow([ticker, d0, d1, kind, round(x * 1e4)])

    with open(os.path.join(HERE, "results", "lenders.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["lender", "token", "ltv", "lt", "bonus", "supply_usd", "breakeven_fall_bp", "history_from",
                    "max_fall_bp", "worst_open", "closures_over_breakeven", "weekend_holiday_over_breakeven", "lt_max_on_max_fall"])
        print("\nlenders today: break-even fall D* and how often a closure fell further")
        for p in sorted(params, key=lambda p: (p["lender"], p["token"])):
            t = UNDERLYING[p["token"]]
            dstar = 1 - p["lt"] * (1 + p["bonus"]) * (1 + INTEREST) / (1 - SLIPPAGE)
            if not t or p["lt"] == 0:
                print(f"  {p['lender']:26} {p['token']:6} LT {p['lt']:.0%}: no underlying history")
                continue
            g = gaps[t]
            worst = min(g, key=lambda x: x[3])
            over = [x for x in g if -x[3] > dstar]
            over_wh = [x for x in over if x[2] != "weeknight"]
            lt_max = (1 + worst[3]) * (1 - SLIPPAGE) / ((1 + p["bonus"]) * (1 + INTEREST))
            w.writerow([p["lender"], p["token"], p["ltv"], p["lt"], p["bonus"], p["supply_usd"], round(dstar * 1e4),
                        g[0][0], round(-worst[3] * 1e4), worst[1], len(over), len(over_wh), round(lt_max, 4)])
            print(f"  {p['lender']:26} {p['token']:6} LTV {p['ltv']:.0%} LT {p['lt']:.0%} bonus {p['bonus']:.1%} "
                  f"${p['supply_usd']:>10,}  D* {dstar:5.1%}  worst {-worst[3]:5.1%} ({worst[1]})  "
                  f"over D*: {len(over)} ({len(over_wh)} weekend/holiday)  LT max {lt_max:.0%}")


if __name__ == "__main__":
    main()
