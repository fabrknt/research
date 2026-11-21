"""ADL fills + asset_ctxs -> modelled payouts of an ADL cover, per coin and per day.

Usage: analyze.py ADL_CSV CTX_DIR OUT_DIR

The cover modelled: when a position is auto-deleveraged, it is paid what re-opening it costs
after a re-hedge window, i.e. the move in the position's favour from the ADL price to the first
mark at least MIN_LAG seconds later (a short closed at 100 with the mark at 90 is paid 10%).
Never negative, capped at CAP. A mark later than MAX_LAG leaves the fill unpriced.

Exposure: either side can buy the cover, so the insured notional is both sides of open
interest, 2 x OI x mark, integrated over time (each ctx row counts until the next one, at most
MAX_GAP seconds). The rate is payouts / exposure-years, over every main-dex coin with marks,
including coins that never had an ADL.
"""
import bisect, collections, csv, glob, os, subprocess, sys
from datetime import datetime, timezone

MIN_LAG, MAX_LAG = 300, 480   # re-hedge window: first mark 5-8 minutes after the fill
HOUR_LAG = 3600               # second horizon, for comparison
CAP = 0.20
MAX_GAP = 600                 # a ctx row stands for at most 10 minutes of exposure
SKIP_DAY = "20251010"

def day_of(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y%m%d")

def read_ctx(path):
    out = subprocess.run(["lz4", "-dc", path], capture_output=True, text=True, check=True).stdout
    return csv.DictReader(out.splitlines())

def next_day(d):
    t = datetime.strptime(d, "%Y%m%d").replace(tzinfo=timezone.utc).timestamp() + 86400
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y%m%d")

def add_exposure(expo, coin, t0, t1, notional):
    """Add notional x seconds over [t0, t1), split at UTC midnight."""
    while t0 < t1:
        cut = min(t1, (t0 // 86400 + 1) * 86400)
        expo[(coin, day_of(t0 * 1000))] += notional * (cut - t0)
        t0 = cut

def mark_after(series, t, lo, hi):
    i = bisect.bisect_left(series, (t + lo,))
    if i < len(series) and series[i][0] - t <= hi:
        return series[i][1], series[i][0] - t
    return None, None

def main(adl_csv, ctx_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    fills = [(int(r[0]), r[2], float(r[3]), float(r[4]), r[5], r[8])
             for r in csv.reader(open(adl_csv))]
    need_days = set()
    for t, *_ in fills:
        need_days |= {day_of(t), next_day(day_of(t))}

    # Exposure: integrate 2 x OI x mark over time, per coin and per day.
    expo = collections.defaultdict(float)        # (coin, day) -> dollar-seconds
    last = {}                                    # coin -> (t, notional)
    marks = collections.defaultdict(list)
    ctx_files = sorted(glob.glob(os.path.join(ctx_dir, "*.csv.lz4")))
    for p in ctx_files:
        keep = os.path.basename(p)[:8] in need_days
        for r in read_ctx(p):
            try:
                mark = float(r["mark_px"]); oi = float(r["open_interest"])
            except ValueError:
                continue
            coin = r["coin"]
            t = datetime.fromisoformat(r["time"].replace("Z", "+00:00")).timestamp()
            if coin in last:
                t0, n0 = last[coin]
                add_exposure(expo, coin, t0, t0 + min(t - t0, MAX_GAP), n0)
            last[coin] = (t, 2 * oi * mark)
            if keep:
                marks[coin].append((t, mark))
    for coin, (t0, n0) in last.items():
        add_exposure(expo, coin, t0, t0 + MAX_GAP, n0)
    for v in marks.values():
        v.sort()
    year = 365 * 86400

    # Payouts per (day, coin).
    cell = collections.defaultdict(lambda: collections.defaultdict(float))
    lags = []
    for t_ms, coin, px, sz, side, user in fills:
        n = px * sz; t = t_ms / 1000
        c = cell[(day_of(t_ms), coin)]
        c["fills"] += 1; c["notional"] += n
        c["short_notional"] += n if side == "B" else 0   # B = bought to close a short
        c["first"] = min(c.get("first", t), t); c["last"] = max(c.get("last", t), t)
        sign = -1 if side == "B" else 1
        s = marks.get(coin)
        m, lag = mark_after(s, t, MIN_LAG, MAX_LAG) if s else (None, None)
        if m is not None:
            missed = sign * (m - px) / px
            c["priced"] += n; c["missed_sum"] += n * missed
            c["positive_sum"] += n * max(missed, 0.0)
            c["payout"] += n * min(max(missed, 0.0), CAP)
            lags.append(lag)
        m1, _ = mark_after(s, t, HOUR_LAG, HOUR_LAG + MAX_LAG) if s else (None, None)
        if m1 is not None:
            c["priced_1h"] += n; c["missed_1h_sum"] += n * sign * (m1 - px) / px

    users_by_day = collections.defaultdict(set)
    for t_ms, coin, px, sz, side, user in fills:
        users_by_day[day_of(t_ms)].add(user)

    def iso(t):
        return datetime.fromtimestamp(t, timezone.utc).strftime("%H:%M:%S")

    with open(os.path.join(out_dir, "by_day_coin.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["day", "coin", "dex", "adl_fills", "adl_notional_usd", "short_share",
                    "first_utc", "last_utc", "priced_notional_usd", "missed_sum_usd",
                    "positive_sum_usd", "payout_usd", "priced_1h_notional_usd", "missed_1h_sum_usd"])
        for (day, coin), c in sorted(cell.items()):
            w.writerow([day, coin, coin.split(":")[0] if ":" in coin else "main",
                        int(c["fills"]), f"{c['notional']:.0f}",
                        f"{c['short_notional'] / c['notional']:.3f}",
                        iso(c["first"]), iso(c["last"]), f"{c['priced']:.0f}",
                        f"{c['missed_sum']:.0f}", f"{c['positive_sum']:.0f}", f"{c['payout']:.0f}",
                        f"{c['priced_1h']:.0f}", f"{c['missed_1h_sum']:.0f}"])

    with open(os.path.join(out_dir, "by_day.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["day", "adl_fills", "adl_notional_usd", "coins", "adl_accounts"])
        days = collections.defaultdict(lambda: [0, 0.0, set()])
        for (day, coin), c in cell.items():
            d = days[day]; d[0] += c["fills"]; d[1] += c["notional"]; d[2].add(coin)
        for day in sorted(days):
            n, v, coins = days[day]
            w.writerow([day, int(n), f"{v:.0f}", len(coins), len(users_by_day[day])])

    # Per coin over the whole period, main dex only (HIP-3 has no ctx rows).
    coins = sorted({c for c, _ in expo})
    with open(os.path.join(out_dir, "by_coin.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["coin", "exposure_usd_years", "exposure_usd_years_ex_20251010", "adl_notional_usd",
                    "adl_days", "payout_usd", "payout_usd_ex_20251010", "payout_bp_per_year",
                    "payout_bp_per_year_ex_20251010"])
        tot = collections.Counter()
        for coin in coins:
            ey = sum(v for (c, _), v in expo.items() if c == coin) / year
            ey_ex = sum(v for (c, d), v in expo.items() if c == coin and d != SKIP_DAY) / year
            mine = {d: c for (d, k), c in cell.items() if k == coin}
            adl = sum(c["notional"] for c in mine.values())
            pay = sum(c["payout"] for c in mine.values())
            pay_ex = sum(c["payout"] for d, c in mine.items() if d != SKIP_DAY)
            tot["ey"] += ey; tot["ey_ex"] += ey_ex; tot["pay"] += pay; tot["pay_ex"] += pay_ex
            tot["adl"] += adl
            w.writerow([coin, f"{ey:.0f}", f"{ey_ex:.0f}", f"{adl:.0f}", len(mine), f"{pay:.0f}", f"{pay_ex:.0f}",
                        f"{pay / ey * 1e4:.2f}" if ey else "", f"{pay_ex / ey_ex * 1e4:.2f}" if ey_ex else ""])
        w.writerow(["ALL", f"{tot['ey']:.0f}", f"{tot['ey_ex']:.0f}", f"{tot['adl']:.0f}", "", f"{tot['pay']:.0f}",
                    f"{tot['pay_ex']:.0f}", f"{tot['pay'] / tot['ey'] * 1e4:.2f}",
                    f"{tot['pay_ex'] / tot['ey_ex'] * 1e4:.2f}"])

    lags.sort()
    q = lambda p: lags[min(len(lags) - 1, int(p * len(lags)))] if lags else None
    with open(os.path.join(out_dir, "run.txt"), "w") as f:
        f.write(f"ctx files {len(ctx_files)} ({os.path.basename(ctx_files[0])[:8]}..{os.path.basename(ctx_files[-1])[:8]})\n")
        f.write(f"adl fills {len(fills)}, main-dex coins with marks {len(coins)}\n")
        f.write(f"mark lag after fill, seconds: min {q(0)} median {q(0.5)} p99 {q(0.99)} max {lags[-1] if lags else None}\n")
    print(open(os.path.join(out_dir, "run.txt")).read(), end="")

main(*sys.argv[1:])
