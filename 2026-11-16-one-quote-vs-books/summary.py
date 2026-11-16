"""What a market order costs on Variational (one dealer's quote) vs Lighter and Hyperliquid (books).

Cost of a size = half the round trip, in bp of a reference mid, plus the taker fee:
    ((buy - ref) + (ref - sell)) / 2 / ref + fee
ref = median of the three venues' mids in that round; a venue more than 1% from it is a different
instrument (US500-PERP is an ETF-sized contract, not the index) and is dropped for that round.

    python3 summary.py              # reads data/snap-*.jsonl and data/walks.jsonl
"""
import glob
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
NY = ZoneInfo("America/New_York")
SIZES = {1e3: "size_1k", 1e5: "size_100k", 1e6: "size_1m"}
LABEL = {1e3: "$1k", 1e5: "$100k", 1e6: "$1M"}
STALE_S = 120  # Variational caches quotes for up to 600 s; older than this is not a live price

# Taker fees in bp (checked 2026-11-16).
# Variational: "There are no trading fees on Omni" (docs.variational.io/omni/trading/fees).
# Lighter: taker_fee 0.0000 on every market in /api/v1/orderBooks (standard account).
# Hyperliquid: 4.5 bp base tier on its own perps; HIP-3 markets with growthMode enabled 0.9 bp.
def fee(venue, coin):
    if venue == "var" or venue == "lighter":
        return 0.0
    return 0.9 if ":" in coin else 4.5


def group(ticker):
    base = ticker.rsplit("-", 1)[0]
    if ticker.endswith("-SWAP") or base in ("XAU", "XAG", "CL", "US500", "QQQ", "SOXL", "EWY"):
        return "index/commodity"
    if base in ("NVDA", "GOOGL", "MU", "SKHY", "SPCX", "TSLA", "SNDK", "AAPL", "AMZN", "MSTR",
                "CRCL", "AMD", "NBIS", "MSFT"):
        return "stock"
    return "crypto"


def session(t):
    ny = datetime.fromtimestamp(t, timezone.utc).astimezone(NY)
    if ny.weekday() >= 5:
        return "weekend"
    mins = ny.hour * 60 + ny.minute
    return "US open" if 570 <= mins < 960 else "US closed"


def main():
    hlcoin = {m["var"]: m["hl"] for m in json.load(open(os.path.join(D, "markets.json")))}
    snaps = {}
    for f in sorted(glob.glob(os.path.join(D, "snap-*.jsonl"))):
        for line in open(f):
            r = json.loads(line)
            snaps[(r["t"], r["var"])] = r
    walks = defaultdict(dict)
    for line in open(os.path.join(D, "walks.jsonl")):
        w = json.loads(line)
        walks[(w["t"], w["var"])][w["venue"]] = w

    cost = defaultdict(list)       # (group, session, size, venue) -> [bp]
    cheapest = defaultdict(lambda: defaultdict(int))  # (group, session, size) -> venue -> rounds
    missing = defaultdict(lambda: [0, 0])  # (venue, size) -> [unfilled, tried]
    stale = [0, 0]
    rounds = set()
    for key, r in snaps.items():
        t, tk = key
        q = r.get("quotes") or {}
        w = walks.get(key, {})
        mids = {}
        if "base" in q:
            stale[1] += 1
            # "2026-11-16T08:43:00.644392182Z": nanoseconds, cut to microseconds
            upd = datetime.fromisoformat(q["updated_at"].rstrip("Z")[:26]).replace(tzinfo=timezone.utc)
            if t - upd.timestamp() > STALE_S:
                stale[0] += 1
            else:
                mids["var"] = (float(q["base"]["bid"]) + float(q["base"]["ask"])) / 2
        for v in ("lighter", "hl"):
            if v in w:
                mids[v] = (w[v]["bid"] + w[v]["ask"]) / 2
        if len(mids) < 2:
            continue
        ref = statistics.median(mids.values())
        live = {v for v, m in mids.items() if abs(m / ref - 1) < 0.01}
        if len(live) < 2 or "var" not in live:
            continue
        rounds.add(t)
        g, s = group(tk), session(t)
        for usd, qk in SIZES.items():
            here = {}
            if qk in q:
                b, a = float(q[qk]["bid"]), float(q[qk]["ask"])
                here["var"] = ((a - ref) + (ref - b)) / 2 / ref * 1e4
            short = False
            for v in ("lighter", "hl"):
                if v not in live:
                    continue
                # HL shows 20 levels; when they run out, walk the 4-significant-figure book instead
                # (never cheaper than the full book where both fill: an upper bound, ~1 bp dearer)
                books = [w[v]] + ([w["hl_coarse"]] if v == "hl" and "hl_coarse" in w else [])
                sz = None
                for bk in books:
                    sz = next(x for x in bk["sizes"] if x["usd"] == usd)
                    if sz["buy"] is not None and sz["sell"] is not None:
                        break
                missing[(v, usd)][1] += 1
                if sz["buy"] is None or sz["sell"] is None:
                    missing[(v, usd)][0] += 1
                    short = True
                    continue
                here[v] = ((sz["buy"] - ref) + (ref - sz["sell"])) / 2 / ref * 1e4
            # compare only rounds where every venue quoted or filled the size
            if short or "var" not in here:
                continue
            for v in list(here):
                here[v] += fee(v, hlcoin.get(tk) or "")
                cost[(g, s, usd, v)].append(here[v])
            if len(here) > 1:
                cheapest[(g, s, usd)][min(here, key=here.get)] += 1

    print(f"{len(rounds)} rounds, {len(snaps)} market-rounds; Variational quotes older than {STALE_S}s: "
          f"{stale[0]}/{stale[1]} (dropped)")
    print("\nmedian cost of a market order, bp of mid, fee included (n = market-rounds)")
    print(f"{'group':16} {'session':10} {'size':>6}  {'Variational':>12} {'Lighter':>10} {'Hyperliquid':>12}  cheapest: var/lighter/hl")
    for g in ("crypto", "stock", "index/commodity"):
        for s in ("US open", "US closed", "weekend"):
            for usd in SIZES:
                cells = []
                for v in ("var", "lighter", "hl"):
                    xs = cost.get((g, s, usd, v), [])
                    cells.append(f"{statistics.median(xs):6.2f} ({len(xs)})" if xs else "-")
                ch = cheapest.get((g, s, usd), {})
                tot = sum(ch.values())
                if not tot:
                    continue
                share = "/".join(f"{100 * ch.get(v, 0) / tot:.0f}%" for v in ("var", "lighter", "hl"))
                print(f"{g:16} {s:10} {LABEL[usd]:>6}  {cells[0]:>12} {cells[1]:>10} {cells[2]:>12}  {share}")
    print("\nbook too thin in the saved levels to fill the size (Lighter 250 orders a side, HL 20 levels):")
    for (v, usd), (a, b) in sorted(missing.items()):
        print(f"  {v:8} ${usd:>9,.0f}: {a}/{b}")


if __name__ == "__main__":
    sys.exit(main())
