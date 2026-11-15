"""在庫の偏り(利用者の正味の買い越し)と、hook 付きプールの出来高の割合。"""
import json, datetime as dt
from collections import defaultdict
import analyze  # noqa: 集計をもう一度走らせて rows と k を使う

rows = analyze.rows
days = (max(r["t"] for r in rows) - min(r["t"] for r in rows)) / 86400
net = defaultdict(float)
gross = defaultdict(float)
for r in rows:
    net[r["sym"]] += r["side"] * r["usd"]
    gross[r["sym"]] += r["usd"]
print(f"期間 {days:.1f} 日")
for s in sorted(gross, key=lambda s: -gross[s]):
    # 日ごとの正味の偏りの絶対値の平均
    d = defaultdict(float)
    for r in rows:
        if r["sym"] == s:
            d[int(r["t"] // 86400)] += r["side"] * r["usd"]
    absd = sum(abs(v) for v in d.values()) / len(d)
    print(f"{s:5s} 出来高/日 ${gross[s]/days/1e3:7.0f}K  正味(期間) ${net[s]/1e3:7.0f}K  日ごとの偏り平均 ${absd/1e3:6.0f}K")

hv = defaultdict(float)
for r in rows:
    hv[r["hooks"]] += r["usd"]
tot = sum(hv.values())
print("hook なし", f"{hv['0x' + '0' * 40] / tot:.0%}")
for h, v in sorted(hv.items(), key=lambda kv: -kv[1])[:8]:
    print(h, f"{v / tot:.1%}", f"${v/1e6:.1f}M")
fees = defaultdict(float)
for r in rows:
    fees["dynamic" if r["fee"] >= 0 and analyze.pools[r["pool"]]["fee"] == 0x800000 else analyze.pools[r["pool"]]["fee"]] += r["usd"]
print({k: f"{v/tot:.0%}" for k, v in sorted(fees.items(), key=lambda kv: -kv[1])})
