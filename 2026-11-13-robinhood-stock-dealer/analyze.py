"""受け身の LP と「HIP-3 の値段 ± s bp で出す dealer」の損益を、時間帯ごとに比べる。

各 swap について:
  fair(t)   = HIP-3 の株 perps の値段 × k(トークンごとの換算比。プールの値段と HL の値段の比の中央値)
  LP の損益 = 利用者の約定値段と fair(t+h) の差(手数料込み、利用者と逆向き)
  dealer    = fair(t) ± s で出す。利用者にとってプールより良い値段なら、その注文を取ったとみなす。
              損益 = s − (fair(t+h)/fair(t) − 1)×向き − ヘッジ費用 c
金額はすべて USD。SPY 建て・QQQ 建ての相手側は HL の SP500・XYZ100 で USD に直す。
"""
import json, bisect, statistics, sys, datetime as dt
from collections import defaultdict
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
HL_COIN = {"NVDA": "NVDA", "TSLA": "TSLA", "AAPL": "AAPL", "MSFT": "MSFT", "META": "META",
           "AMZN": "AMZN", "GOOGL": "GOOGL", "SPY": "SP500", "QQQ": "XYZ100",
           "AMD": "AMD", "MU": "MU", "HIMS": "HIMS", "TSM": "TSM", "INTC": "INTC", "PLTR": "PLTR"}
# SET=other のときは、9 銘柄以外の株×SPY(fetch_all.py の 7 日分から作る)を測る
import os
SUF = "_" + os.environ["SET"] if os.environ.get("SET") else ""
SPREADS = [5, 10, 20, 30, 50, 100]
HORIZONS = [0, 60, 300, 3600]
HEDGE_BPS = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0

tokens = json.load(open(f"data/tokens{SUF}.json"))  # addr(lower) -> {sym, dec, usd: bool}
pools = {p["id"]: p for p in json.load(open(f"data/pools_sel{SUF}.json"))}
swaps = json.load(open(f"data/swaps{SUF}.json"))
anchors = sorted((int(k), v) for k, v in json.load(open("data/anchors.json")).items())
ab = [a[0] for a in anchors]
cand = json.load(open("data/hl_candles.json"))


def btime(b):
    i = max(1, min(bisect.bisect_left(ab, b), len(ab) - 1))
    (b0, t0), (b1, t1) = anchors[i - 1], anchors[i]
    return t0 + (t1 - t0) * (b - b0) / (b1 - b0)


class Ref:
    """1 分足があればそれ、なければ 5 分足。足の中は open→close を線形補間する。"""

    def __init__(self, coin):
        self.series = []
        for iv, w in (("1m", 60), ("5m", 300)):
            cs = cand[f"{coin}_{iv}"]
            self.series.append(([c[0] / 1000 for c in cs], cs, w))

    def __call__(self, t):
        for ts, cs, w in self.series:
            i = bisect.bisect_right(ts, t) - 1
            if 0 <= i < len(cs) and t < ts[i] + w and cs[i][3] > 0:
                f = (t - ts[i]) / w
                return cs[i][1] + (cs[i][2] - cs[i][1]) * f
        return None


refs = {s: Ref(c) for s, c in HL_COIN.items()}


def session(t):
    d = dt.datetime.fromtimestamp(t, ET)
    wd, hm = d.weekday(), d.hour * 60 + d.minute
    if wd == 5 or (wd == 4 and hm >= 16 * 60) or (wd == 6 and hm < 20 * 60):
        return "weekend"
    if wd < 5 and 9 * 60 + 30 <= hm < 16 * 60:
        return "rth"
    return "offhours"


rows = []
for s in swaps:
    p = pools[s["pool"]]
    t0, t1 = tokens[p["currency0"]], tokens[p["currency1"]]
    # 株を 1 つ選ぶ: 片側が USD ならもう片側。両側が株なら SPY・QQQ でない方(どちらも SPY・QQQ なら QQQ)。
    if t0.get("usd") or t1.get("usd"):
        stock_is0 = not t0.get("usd")
    elif t1["sym"] in ("SPY", "QQQ") and t0["sym"] not in ("SPY", "QQQ"):
        stock_is0 = True
    elif t0["sym"] in ("SPY", "QQQ") and t1["sym"] not in ("SPY", "QQQ"):
        stock_is0 = False
    else:
        stock_is0 = t0["sym"] == "QQQ"
    st, qt = (t0, t1) if stock_is0 else (t1, t0)
    a_st = (s["a0"] if stock_is0 else s["a1"]) / 10 ** st["dec"]
    a_qt = (s["a1"] if stock_is0 else s["a0"]) / 10 ** qt["dec"]
    if a_st == 0 or a_qt == 0:
        continue
    t = btime(s["block"])
    r0 = refs[st["sym"]](t)
    q0 = 1.0 if qt.get("usd") else refs[qt["sym"]](t)
    if r0 is None or q0 is None:
        continue
    fut = {}
    for h in HORIZONS:
        r = refs[st["sym"]](t + h)
        q = 1.0 if qt.get("usd") else refs[qt["sym"]](t + h)
        fut[h] = None if r is None or q is None else (r, q)
    rows.append({"sym": st["sym"], "qsym": qt["sym"], "usdq": bool(qt.get("usd")), "pool": s["pool"], "t": t,
                 "px_q": abs(a_qt) / abs(a_st),  # 株 1 つあたりの相手側の量(手数料込み)
                 "r0": r0, "q0": q0, "side": 1 if a_st > 0 else -1, "fut": fut, "a_qt": abs(a_qt),
                 "fee": s["fee"], "hooks": p["hooks"], "sender": s["sender"],
                 # 約定後のプールの値段(株 1 つあたりの相手側の量)。向きの判定に使う。
                 "after_q": (s["sqrtP"] / 2 ** 96) ** 2 * 10 ** (t0["dec"] - t1["dec"]) if stock_is0
                 else 1 / ((s["sqrtP"] / 2 ** 96) ** 2 * 10 ** (t0["dec"] - t1["dec"])),
                 "order": (s["block"], s.get("logIndex", 0))})

# 換算比 k(トークンの USD 値段 ÷ HL の値段)を、USD 建てのプールから順に決める。
# USD 建てのプールが無い組(SET=other)では、SPY の換算比を 9 銘柄の計測から引き継ぐ。
k = {"SPY": json.load(open("data/result.json"))["k"]["SPY"]} if SUF else {}
for _ in range(4):
    for sym in HL_COIN:
        if sym in k:
            continue
        xs = []
        for r in rows:
            if r["sym"] != sym:
                continue
            if r["usdq"]:
                xs.append(r["px_q"] / r["r0"])
            elif r["qsym"] in k:
                xs.append(r["px_q"] * r["q0"] * k[r["qsym"]] / r["r0"])
        if len(xs) >= 50:
            k[sym] = statistics.median(xs)
    # 相手側(SPY など)の k が分かれば、それを株として見た行からも k を逆に決められる
    for sym in HL_COIN:
        if sym in k:
            continue
        xs = [r["r0"] * k[r["sym"]] / (r["px_q"] * r["q0"]) for r in rows if r["qsym"] == sym and r["sym"] in k]
        if len(xs) >= 50:
            k[sym] = statistics.median(xs)
print("k", {s: round(v, 5) for s, v in k.items()})

kept, dropped = [], 0.0
for r in rows:
    if r["sym"] not in k or (not r["usdq"] and r["qsym"] not in k):
        continue
    qk = 1.0 if r["usdq"] else k[r["qsym"]]
    r["usd"] = r["a_qt"] * r["q0"] * qk
    r["exec"] = r["px_q"] * r["q0"] * qk
    r["qk"] = qk
    fair0 = r["r0"] * k[r["sym"]]
    if abs(r["exec"] / fair0 - 1) > 0.05:
        dropped += r["usd"]
        continue
    kept.append(r)
print("dropped usd (>5% off)", round(dropped), "kept usd", round(sum(r["usd"] for r in kept)))
rows = kept

agg = defaultdict(lambda: defaultdict(float))
for r in rows:
    kk = k[r["sym"]]
    fair0 = r["r0"] * kk
    for h, f in r["fut"].items():
        if f is None:
            continue
        # 相手側が株なら、受け取った相手側の量の値打ちも t+h の値段で測る
        fair_h = f[0] * kk * (r["q0"] / f[1])
        # 受け身の LP: 利用者が買えば LP は株を exec で売った。fair_h との差が LP の損益。
        lp = r["side"] * (r["exec"] - fair_h) / fair_h * r["usd"]
        key = (r["sym"], session(r["t"]), h)
        a = agg[key]
        a["n"] += 1
        a["usd"] += r["usd"]
        a["lp"] += lp
        a["net_side_usd"] += r["side"] * r["usd"]
        move = r["side"] * (fair_h / fair0 - 1)  # 利用者側に有利な値動き
        for sp in SPREADS:
            quote = fair0 * (1 + r["side"] * sp / 1e4)
            better = quote < r["exec"] if r["side"] > 0 else quote > r["exec"]
            if better:
                a[f"d{sp}_usd"] += r["usd"]
                a[f"d{sp}"] += r["usd"] * (sp / 1e4 - move - HEDGE_BPS / 1e4)

out = []
for (sym, sess, h), a in sorted(agg.items()):
    o = {"sym": sym, "session": sess, "h": h, "n": int(a["n"]), "usd": round(a["usd"]),
         "lp_bps": round(a["lp"] / a["usd"] * 1e4, 1), "net_side_usd": round(a["net_side_usd"])}
    for sp in SPREADS:
        u = a[f"d{sp}_usd"]
        o[f"d{sp}_share"] = round(u / a["usd"], 2)
        o[f"d{sp}_bps"] = round(a[f"d{sp}"] / u * 1e4, 1) if u else None
        o[f"d{sp}_pnl"] = round(a[f"d{sp}"])
    out.append(o)
json.dump({"k": k, "hedge_bps": HEDGE_BPS, "rows": out}, open(f"data/result{SUF}.json", "w"), indent=1)
for o in out:
    if o["h"] in (300, 3600):
        print(o["sym"], o["session"], o["h"], o["n"], o["usd"], "LP", o["lp_bps"],
              "| d10", o["d10_share"], o["d10_bps"], "| d20", o["d20_share"], o["d20_bps"],
              "| d50", o["d50_share"], o["d50_bps"])


# 向き別: 約定でプールの値段が HL の基準(fair0)に近づいたか遠ざかったかで、受け身の LP の損益を分ける。
# 約定前のプールの値段は、同じプールの直前の約定後の値段。
prev = {}
dirs = defaultdict(lambda: defaultdict(float))
for r in sorted(rows, key=lambda r: r["order"]):
    before = prev.get(r["pool"])
    prev[r["pool"]] = r["after_q"]
    if before is None:
        continue
    kk = k[r["sym"]]
    fair0 = r["r0"] * kk
    to_usd = r["q0"] * r["qk"]
    toward = abs(r["after_q"] * to_usd / fair0 - 1) < abs(before * to_usd / fair0 - 1)
    for h, f in r["fut"].items():
        if f is None:
            continue
        fair_h = f[0] * kk * (r["q0"] / f[1])
        lp = r["side"] * (r["exec"] - fair_h) / fair_h * r["usd"]
        for key in ((toward, session(r["t"]), h), (toward, "all", h)):
            d = dirs[key]
            d["usd"] += r["usd"]
            d["lp"] += lp
            d["fee"] += r["fee"] / 1e6 * r["usd"]
print("\n向き別の受け身の LP(手数料込み / 手数料前、bp)")
for (toward, sess, h), d in sorted(dirs.items(), key=lambda x: (x[0][1], x[0][2], not x[0][0])):
    if h in (300, 3600):
        print(f"{sess:9} h={h:5} {'近づける' if toward else '遠ざける'} usd={d['usd']:>13,.0f}  "
              f"LP {d['lp'] / d['usd'] * 1e4:6.1f}  手数料前 {(d['lp'] - d['fee']) / d['usd'] * 1e4:6.1f}")
