"""ミーム×株プールの流量: 出来高、プールの年齢、集中、launchpad(hook)、router、株トークンの正味の需要。

金額は株側の量 × HL の値段 × k(analyze.py の換算比)で USD に直す。
"""
import bisect, csv, json, statistics, sys, datetime as dt
from collections import defaultdict, Counter
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
HL_COIN = {"NVDA": "NVDA", "TSLA": "TSLA", "AAPL": "AAPL", "MSFT": "MSFT", "META": "META",
           "AMZN": "AMZN", "GOOGL": "GOOGL", "SPY": "SP500", "QQQ": "XYZ100"}
K = json.load(open("data/result.json"))["k"]
USDG = "0x5fc5360d0400a0fd4f2af552add042d716f1d168"
stocks = {v.lower(): k for k, v in json.load(open("data/stocks.json")).items()}
# Robinhood の株トークン全部(203 銘柄)。9 銘柄以外も「株」として分ける。
ALL_RH = {}
for a in json.load(open("data/rhj_assets.json"))["assets"]:
    for d in a["deployments"]:
        if d["chainId"] == 4663:
            ALL_RH[d["contractAddress"].lower()] = a["tokenSymbol"]
pools = {}
for p in json.load(open("data/pools.json")):
    pools[p["id"]] = p
cand = json.load(open("data/hl_candles.json"))
ser = {s: ([c[0] / 1000 for c in cand[f"{c_}_5m"]], [c[2] for c in cand[f"{c_}_5m"]]) for s, c_ in HL_COIN.items()}


def px(sym, t):
    ts, cs = ser[sym]
    i = max(0, min(bisect.bisect_right(ts, t) - 1, len(cs) - 1))
    return cs[i] * K[sym]


def kind(p):
    a, b = p["currency0"], p["currency1"]
    sa, sb = a in stocks, b in stocks
    if sa and sb:
        return "stock×stock", None, None
    if USDG in (a, b):
        return "stock×USDG", None, None
    st, other = (a if sa else b), (b if sa else a)
    if other in ALL_RH:
        return "他の株×株", st, other
    if other == "0x" + "0" * 40:
        return "stock×ETH", st, other
    return "meme×stock", st, other


# ブロック → 時刻(anchors が無い範囲は、2 点から線形に外挿する)
anchors = sorted((int(k), v) for k, v in json.load(open("data/anchors.json")).items())
(b0, t0), (b1, t1) = anchors[0], anchors[-1]
rate = (t1 - t0) / (b1 - b0)
btime = lambda b: t1 + (b - b1) * rate

vol = defaultdict(float)          # kind -> usd
by_stock = defaultdict(float)     # meme×stock: quote stock -> usd
pool_vol = defaultdict(float)
age_vol = defaultdict(float)
hook_vol = defaultdict(float)
sender_vol = defaultdict(float)
net_stock = defaultdict(float)
other_stock = defaultdict(float)  # 他の株×株: 9 銘柄以外の株 -> usd    # 利用者が払った株(+)= ミームを買うための株の需要
day_vol = defaultdict(lambda: defaultdict(float))
txs_by_pool = defaultdict(int)
tmin, tmax = 1e18, 0
n = 0
for r in csv.DictReader(open("data/all_swaps.csv")):
    p = pools.get(r["pool"])
    if not p:
        continue
    kd, st, other = kind(p)
    b = int(r["block"]); t = btime(b)
    tmin, tmax = min(tmin, t), max(tmax, t)
    a0, a1 = int(r["a0"]), int(r["a1"])
    if kd in ("meme×stock", "stock×ETH", "他の株×株"):
        sym = stocks[st]
        a_st = (a0 if p["currency0"] == st else a1) / 1e18
        usd = abs(a_st) * px(sym, t)
        by_stock[sym] += usd
        net_stock[sym] += -a_st * px(sym, t)  # a_st<0 = 利用者が株を払った
    else:
        # 株×USDG・株×株は、片方の株側で USD に直す
        c0, c1 = p["currency0"], p["currency1"]
        if c0 in stocks:
            usd = abs(a0) / 1e18 * px(stocks[c0], t)
        else:
            usd = abs(a1) / 1e18 * px(stocks[c1], t)
    if usd > 5e6:  # 壊れた値(税付きトークンなど)は除く
        continue
    n += 1
    vol[kd] += usd
    day = dt.datetime.fromtimestamp(t, ET).strftime("%m-%d %a")
    day_vol[day][kd] += usd
    if kd == "他の株×株":
        other_stock[ALL_RH[other]] += usd
    if kd == "meme×stock":
        pool_vol[r["pool"]] += usd
        age_h = (b - p["block"]) * rate / 3600
        bucket = "<1h" if age_h < 1 else "1-24h" if age_h < 24 else "1-7d" if age_h < 168 else ">7d"
        age_vol[bucket] += usd
        hook_vol[p["hooks"]] += usd
        sender_vol[r["sender"]] += usd
        txs_by_pool[r["pool"]] += 1

days = (tmax - tmin) / 86400
tot = sum(vol.values())
print(f"期間 {days:.1f} 日  swap {n}  合計 ${tot/1e6:.1f}M (${tot/days/1e6:.2f}M/日)")
for kd, v in sorted(vol.items(), key=lambda kv: -kv[1]):
    print(f"  {kd:12s} ${v/1e6:7.1f}M  {v/tot:5.1%}  ${v/days/1e6:.2f}M/日")
print("\n日ごと")
for d in sorted(day_vol):
    print(" ", d, "  ".join(f"{k} ${v/1e6:.1f}M" for k, v in sorted(day_vol[d].items())))
mv = vol["meme×stock"]
print("\nミーム・他の株×株・ETH: 相手側の株(9 銘柄)")
for s, v in sorted(by_stock.items(), key=lambda kv: -kv[1]):
    print(f"  {s:5s} ${v/1e6:6.1f}M  正味で払われた株 ${net_stock[s]/1e6:+.2f}M")
print("\n他の株×株(9 銘柄以外の株を相手にした組)の上位")
for s_, v in sorted(other_stock.items(), key=lambda kv: -kv[1])[:12]:
    print(f"  {s_:6s} ${v/1e6:6.2f}M")
print("\nプールの年齢ごと(ミーム×株)")
for k in ("<1h", "1-24h", "1-7d", ">7d"):
    print(f"  {k:6s} {age_vol[k]/mv:5.1%}")
pv = sorted(pool_vol.values(), reverse=True)
print(f"\n取引のあったプール {len(pv)}  上位 10 {sum(pv[:10])/mv:.1%}  上位 100 {sum(pv[:100])/mv:.1%}  "
      f"$10K 超 {sum(1 for v in pv if v > 1e4)}  $100K 超 {sum(1 for v in pv if v > 1e5)}")
created = [p for p in pools.values() if kind(p)[0] == "meme×stock" and btime(p["block"]) >= tmin]
print(f"期間中に作られたミーム×株プール {len(created)}(1 日 {len(created)/days:.0f})")
print("\nhook(launchpad)ごと")
for h, v in sorted(hook_vol.items(), key=lambda kv: -kv[1])[:8]:
    print(f"  {h} {v/mv:5.1%} ${v/1e6:.1f}M")
print("\nrouter(Swap の sender)ごと")
for s, v in sorted(sender_vol.items(), key=lambda kv: -kv[1])[:8]:
    print(f"  {s} {v/mv:5.1%}")
json.dump({"top_pools": sorted(pool_vol.items(), key=lambda kv: -kv[1])[:200]}, open("data/meme_top_pools.json", "w"))
