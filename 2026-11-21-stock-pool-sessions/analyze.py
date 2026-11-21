"""Passive-LP markout of every swap in the selected stock pools, split by US trading session.

Extends ../2026-11-13-robinhood-stock-dealer/analyze.py (same reference, same k ratio, same LP sign):
  fair(t)  = Hyperliquid xyz perp price x k (k = median of pool price / HL price, per symbol and UTC day,
             from stock/USDG pools; SPY- and QQQ-quoted names through SPY's or QQQ's k)
  LP P&L   = side x (exec - fair(t+h)) / fair(t+h) x usd     (fee included; side = +1 when the user buys the stock)
  gross    = LP P&L - fee                                    (what the LP would make at zero fee)
  pool ref = the same with fair(t+h) replaced by the pool's own price after its last swap before t+h
Horizons: 60 s, 300 s, 3600 s, and "reopen" = 5 min after the next US regular-session open (non-RTH swaps).
Writes data/rows.pkl (compact rows for counterfactual.py / routing.py) and results/sessions.json.
"""
import bisect, csv, glob, json, os, pickle, statistics, sys, datetime as dt
from collections import defaultdict
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coins import HL_COIN
from rowtype import Row

H = os.path.dirname(os.path.abspath(__file__))
ET = ZoneInfo("America/New_York")
HOR = [60, 300, 3600]
ZERO = "0x" + "0" * 40

tokens = json.load(open(f"{H}/data/tokens.json"))
pools = {p["id"]: p for p in json.load(open(f"{H}/data/pools_sel.json"))}
fables = {p["id"] for p in json.load(open(f"{H}/data/fables_pools.json"))}
anchors = sorted((int(k), v) for k, v in json.load(open(f"{H}/data/anchors.json")).items())
ab = [a[0] for a in anchors]
cand = json.load(open(f"{H}/data/hl_candles.json"))


def btime(b):
    i = max(1, min(bisect.bisect_left(ab, b), len(ab) - 1))
    (b0, t0), (b1, t1) = anchors[i - 1], anchors[i]
    return t0 + (t1 - t0) * (b - b0) / (b1 - b0)


class Ref:
    """Finest candle available at t (1m, then 5m, then 15m); open->close interpolated inside the candle."""

    def __init__(self, coin):
        self.series = []
        for iv, w in (("1m", 60), ("5m", 300), ("15m", 900)):
            cs = cand.get(f"{coin}_{iv}", [])
            self.series.append(([c[0] / 1000 for c in cs], cs, w))

    def __call__(self, t):
        for ts, cs, w in self.series:
            i = bisect.bisect_right(ts, t) - 1
            if 0 <= i < len(cs) and t < ts[i] + w and cs[i][3] > 0:
                return cs[i][1] + (cs[i][2] - cs[i][1]) * (t - ts[i]) / w
        return None


refs = {s: Ref(c) for s, c in HL_COIN.items()}


def session(t):
    """rth 9:30-16:00 ET Mon-Fri; pre 4:00-9:30; after 16:00-20:00; overnight 20:00-4:00 (Sun 20:00 to Fri 4:00);
    weekend Fri 20:00 to Sun 20:00 (Robinhood's 24/5 window closes over it). No NYSE holiday falls in the window."""
    d = dt.datetime.fromtimestamp(t, ET)
    wd, hm = d.weekday(), d.hour * 60 + d.minute
    if wd == 5 or (wd == 4 and hm >= 20 * 60) or (wd == 6 and hm < 20 * 60):
        return "weekend"
    if wd == 6:
        return "overnight"
    if 9 * 60 + 30 <= hm < 16 * 60:
        return "rth"
    if 4 * 60 <= hm < 9 * 60 + 30:
        return "pre"
    if 16 * 60 <= hm < 20 * 60:
        return "after"
    return "overnight"


def bell(t):
    """Windows around the bells (overlapping the sessions above): open 9:15-9:45, close 15:45-16:15 ET, weekdays.
    'monday_open' is the open window on a Monday."""
    d = dt.datetime.fromtimestamp(t, ET)
    if d.weekday() > 4:
        return None
    hm = d.hour * 60 + d.minute
    if 9 * 60 + 15 <= hm < 9 * 60 + 45:
        return "monday_open" if d.weekday() == 0 else "open"
    if 15 * 60 + 45 <= hm < 16 * 60 + 15:
        return "close"
    return None


def next_open(t):
    d = dt.datetime.fromtimestamp(t, ET)
    day = d.date()
    for i in range(0, 8):
        x = day + dt.timedelta(days=i)
        if x.weekday() > 4:
            continue
        o = dt.datetime(x.year, x.month, x.day, 9, 30, tzinfo=ET).timestamp()
        if o > t:
            return o
    return None


def load_swaps():
    rows = []
    files = sorted(glob.glob(f"{H}/data/pchunks/*.csv"))
    if os.environ.get("TEST"):
        files = files[:int(os.environ["TEST"])]
    for f in files:
        for r in csv.reader(open(f)):
            rows.append((int(r[0]), int(r[1]), r[2], r[3], int(r[4]), int(r[5]), int(r[6]), int(r[7]), int(r[9]), r[10]))
    rows.sort()
    return rows


def pick(p):
    t0, t1 = tokens[p["currency0"]], tokens[p["currency1"]]
    if t0.get("usd") or t1.get("usd"):
        return not t0.get("usd")
    idx = ("SPY", "QQQ")
    if t1["sym"] in idx and t0["sym"] not in idx:
        return True
    if t0["sym"] in idx and t1["sym"] not in idx:
        return False
    return t0["sym"] == "QQQ" if {t0["sym"], t1["sym"]} == {"SPY", "QQQ"} else True


def main():
    swaps = load_swaps()
    print("swaps", len(swaps), file=sys.stderr)
    raw = []
    last_after = {}  # pool -> (t, after price in quote units)
    pool_hist = defaultdict(lambda: ([], []))  # pool -> (times, after prices) for the pool-ref markout
    for (blk, li, pid, sender, a0, a1, sq, liq, fee, tx) in swaps:
        p = pools.get(pid)
        if p is None:
            continue
        stock0 = pick(p)
        t0, t1 = tokens[p["currency0"]], tokens[p["currency1"]]
        st, qt = (t0, t1) if stock0 else (t1, t0)
        a_st = (a0 if stock0 else a1) / 10 ** st["dec"]
        a_qt = (a1 if stock0 else a0) / 10 ** qt["dec"]
        p01 = (sq / 2 ** 96) ** 2 * 10 ** (t0["dec"] - t1["dec"])  # currency1 per currency0
        after = p01 if stock0 else (1 / p01 if p01 else 0)
        t = btime(blk)
        before = last_after.get(pid)
        last_after[pid] = after
        ph = pool_hist[pid]
        ph[0].append(t)
        ph[1].append(after)
        if a_st == 0 or a_qt == 0 or after == 0:
            continue
        # v4 Swap amounts are the caller's balance delta: > 0 means the user received it (as in the 11-13 study).
        side = 1 if a_st > 0 else -1
        raw.append((t, pid, st["sym"], qt["sym"], bool(qt.get("usd")), abs(a_qt) / abs(a_st), abs(a_qt), side,
                    fee, p["hooks"], sender, tx, before, after, blk))
    print("rows", len(raw), file=sys.stderr)

    # k per symbol per UTC day (pool price in USD / HL price)
    day = lambda t: int(t // 86400)
    k = defaultdict(dict)
    kall = {}
    for it in range(4):
        obs = defaultdict(list)
        for (t, pid, sym, qsym, usdq, pxq, aq, side, fee, hk, snd, tx, bef, aft, blk) in raw:
            r0 = refs[sym](t)
            if r0 is None:
                continue
            if usdq:
                obs[(sym, day(t))].append(pxq / r0)
            elif qsym in kall:
                q0 = refs[qsym](t)
                if q0:
                    obs[(sym, day(t))].append(pxq * q0 * k[qsym].get(day(t), kall[qsym]) / r0)
            # the reverse: a known stock gives the quote's k
            if not usdq and sym in kall and qsym not in kall:
                q0 = refs[qsym](t)
                if q0:
                    obs[(qsym, day(t), "rev")].append(r0 * k[sym].get(day(t), kall[sym]) / (pxq * q0))
        for key, xs in obs.items():
            sym, d = key[0], key[1]
            if len(key) == 3 and sym in kall:
                continue
            if len(xs) >= 20 and d not in k[sym]:
                k[sym][d] = statistics.median(xs)
        for sym in list(k):
            if k[sym]:
                kall[sym] = statistics.median(k[sym].values())
    print("k (median over days)", {s: round(v, 4) for s, v in sorted(kall.items())}, file=sys.stderr)

    def kk(sym, t):
        return k[sym].get(day(t), kall.get(sym))

    out = []
    dropped = 0.0
    for (t, pid, sym, qsym, usdq, pxq, aq, side, fee, hk, snd, tx, bef, aft, blk) in raw:
        if sym not in kall or (not usdq and qsym not in kall):
            continue
        r0 = refs[sym](t)
        q0 = 1.0 if usdq else refs[qsym](t)
        if r0 is None or q0 is None:
            continue
        qk = 1.0 if usdq else kk(qsym, t)
        ks = kk(sym, t)
        usd = aq * q0 * qk
        execu = pxq * q0 * qk
        fair0 = r0 * ks
        if abs(execu / fair0 - 1) > 0.05:
            dropped += usd
            continue
        fut = {}
        ts = list(HOR)
        sess = session(t)
        no = next_open(t) + 300 if sess != "rth" else None
        for h in ts + (["reopen"] if no else []):
            th = t + h if h != "reopen" else no
            r = refs[sym](th)
            q = 1.0 if usdq else refs[qsym](th)
            if r is None or q is None:
                fut[h] = None
                continue
            fair_h = r * kk(sym, th) * (q0 / q) if not usdq else r * kk(sym, th)
            fut[h] = side * (execu - fair_h) / fair_h  # LP return incl. fee
        # pool-ref markout: same pool's price at t+h (quote units)
        pr = {}
        tsl, pl = pool_hist[pid]
        for h in (300, 3600):
            i = bisect.bisect_right(tsl, t + h) - 1
            mid = pl[i]
            # a pool whose later price is >5% from this fill was emptied or re-seeded: no pool-ref markout
            pr[h] = side * (pxq - mid) / mid if mid and abs(pxq / mid - 1) <= 0.05 else None
        d_bp = None
        if bef:
            d_bp = (bef * q0 * qk / fair0 - 1) * 1e4  # pool vs reference before the swap, bp
        toward = None
        if bef:
            toward = abs(aft * q0 * qk / fair0 - 1) < abs(bef * q0 * qk / fair0 - 1)
        out.append(Row(t=t, pool=pid, sym=sym, qsym=qsym, usdq=usdq, usd=usd, side=side, fee=fee / 1e6, hooks=hk,
                       fables=pid in fables, sender=snd, tx=tx, sess=sess, bell=bell(t), lp=fut, pool_lp=pr,
                       d_bp=d_bp, toward=toward, blk=blk))
    print("dropped usd (>5% from reference)", round(dropped), "kept", round(sum(r.usd for r in out)), file=sys.stderr)
    pickle.dump({"rows": out, "k": kall}, open(f"{H}/data/rows.pkl", "wb"))


if __name__ == "__main__":
    main()
