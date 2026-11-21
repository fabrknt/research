"""HIP-3 ADL fills + the HIP-3 fills around them -> modelled payouts of the same ADL cover as analyze.py.

Usage: hip3.py ADL_CSV FILLS_DIR OUT_DIR

asset_ctxs has no HIP-3 coins, so the "mark" here is the price of the first fill that is not an ADL
at least MIN_LAG seconds after the ADL fill (and at most MAX_LAG). FILLS_DIR holds time,coin,px,sz,dir
for HIP-3 coins, one CSV per hourly file of node_fills_by_block, for the hours with a HIP-3 ADL and the
hour after (fetch_hip3.sh). Same payout as analyze.py: the move in the position's favour, floored at 0,
capped at CAP. There is no open-interest history for HIP-3 either, so the per-year rate is against
today's open interest (metaAndAssetCtxs, read when this runs): a rough scale, not a rate.
"""
import bisect, collections, csv, glob, json, os, sys, urllib.request
from datetime import datetime, timezone

MIN_LAG, MAX_LAG = 300, 480
CAP = 0.20
API = "https://api.hyperliquid.xyz/info"


def day_of(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y%m%d")


def post(body):
    req = urllib.request.Request(API, json.dumps(body).encode(), {"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def open_interest_today(dexes):
    """dex -> 2 x OI x mark summed over its coins, now."""
    out = {}
    for dex in dexes:
        meta, ctxs = post({"type": "metaAndAssetCtxs", "dex": dex})
        out[dex] = sum(2 * float(c["openInterest"]) * float(c["markPx"])
                       for c in ctxs if c.get("markPx"))
    return out


def main(adl_csv, fills_dir, out_dir):
    fills = [(int(r[0]), r[2], float(r[3]), float(r[4]), r[5])
             for r in csv.reader(open(adl_csv)) if ":" in r[2]]
    trades = collections.defaultdict(list)          # coin -> [(t_ms, px)], non-ADL fills
    seen = set()
    for p in sorted(glob.glob(os.path.join(fills_dir, "*.csv"))):
        for t, coin, px, sz, d in csv.reader(open(p)):
            if d == "Auto-Deleveraging" or (t, coin, px, sz) in seen:
                continue
            seen.add((t, coin, px, sz))   # hourly files overlap by a few ms; a fill has two sides
            trades[coin].append((int(t), float(px)))
    for v in trades.values():
        v.sort()

    cell = collections.defaultdict(lambda: collections.defaultdict(float))
    for t, coin, px, sz, side in fills:
        n = px * sz
        c = cell[(day_of(t), coin)]
        c["fills"] += 1; c["notional"] += n
        c["short_notional"] += n if side == "B" else 0
        s = trades.get(coin, [])
        i = bisect.bisect_left(s, (t + MIN_LAG * 1000,))
        if i < len(s) and s[i][0] - t <= MAX_LAG * 1000:
            missed = (-1 if side == "B" else 1) * (s[i][1] - px) / px
            c["priced"] += n; c["missed_sum"] += n * missed
            c["positive_sum"] += n * max(missed, 0.0)
            c["payout"] += n * min(max(missed, 0.0), CAP)

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "hip3_by_day_coin.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["day", "coin", "dex", "adl_fills", "adl_notional_usd", "short_share",
                    "priced_notional_usd", "missed_sum_usd", "positive_sum_usd", "payout_usd"])
        for (day, coin), c in sorted(cell.items()):
            w.writerow([day, coin, coin.split(":")[0], int(c["fills"]), f"{c['notional']:.0f}",
                        f"{c['short_notional'] / c['notional']:.3f}", f"{c['priced']:.0f}",
                        f"{c['missed_sum']:.0f}", f"{c['positive_sum']:.0f}", f"{c['payout']:.0f}"])

    first = min(t for t, *_ in fills) / 1000
    years = (datetime.now(timezone.utc).timestamp() - first) / (365 * 86400)
    by_dex = collections.defaultdict(collections.Counter)
    for (day, coin), c in cell.items():
        d = by_dex[coin.split(":")[0]]
        d["notional"] += c["notional"]; d["priced"] += c["priced"]; d["payout"] += c["payout"]
    days = collections.defaultdict(set)
    for (day, coin) in cell:
        days[coin.split(":")[0]].add(day)
    oi = open_interest_today(sorted(by_dex))
    with open(os.path.join(out_dir, "hip3_by_dex.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["dex", "adl_days", "adl_notional_usd", "priced_notional_usd", "payout_usd",
                    "payout_per_adl_dollar", "payout_usd_per_year", "insured_notional_today_usd",
                    "payout_bp_per_year_at_today_oi"])
        for dex in sorted(by_dex, key=lambda k: -by_dex[k]["notional"]):
            d = by_dex[dex]
            per_year = d["payout"] / years
            w.writerow([dex, len(days[dex]), f"{d['notional']:.0f}", f"{d['priced']:.0f}", f"{d['payout']:.0f}",
                        f"{d['payout'] / d['priced']:.4f}" if d["priced"] else "", f"{per_year:.0f}",
                        f"{oi[dex]:.0f}", f"{per_year / oi[dex] * 1e4:.1f}" if oi[dex] else ""])
    with open(os.path.join(out_dir, "hip3_run.txt"), "w") as f:
        f.write(f"hip3 adl fills {len(fills)} from {datetime.fromtimestamp(first, timezone.utc):%Y-%m-%d} "
                f"({years:.2f} years), fill files {len(glob.glob(os.path.join(fills_dir, '*.csv')))}, "
                f"open interest read {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC\n")
    print(open(os.path.join(out_dir, "hip3_run.txt")).read(), end="")


main(*sys.argv[1:])
