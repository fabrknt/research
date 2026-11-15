"""data/result.json を時間帯ごと・銘柄ごとにまとめる。"""
import json, sys
from collections import defaultdict

res = json.load(open("data/result.json"))
H = int(sys.argv[1]) if len(sys.argv) > 1 else 300
SP = [10, 20, 30, 50, 100]
rows = [r for r in res["rows"] if r["h"] == H]


def line(name, rs):
    usd = sum(r["usd"] for r in rs)
    lp = sum(r["lp_bps"] * r["usd"] for r in rs) / usd
    parts = [f"{name:16s} 出来高 ${usd/1e6:6.1f}M  LP {lp:6.1f}bp"]
    for sp in SP:
        u = sum(r[f"d{sp}_share"] * r["usd"] for r in rs)
        pnl = sum(r[f"d{sp}_pnl"] for r in rs)
        parts.append(f"s{sp}: 取る{u/usd:4.0%} {pnl/u*1e4 if u else 0:6.1f}bp ${pnl/1e3:6.1f}K")
    print(" | ".join(parts))


print(f"h={H}s ヘッジ {res['hedge_bps']}bp  (17 日分)")
for sess in ("rth", "offhours", "weekend"):
    line(sess, [r for r in rows if r["session"] == sess])
line("all", rows)
print()
for sym in sorted({r["sym"] for r in rows}):
    line(sym, [r for r in rows if r["sym"] == sym])
