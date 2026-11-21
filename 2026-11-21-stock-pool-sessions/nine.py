"""Continuity check with the 11-13 study: the nine names, stock/USDG and stock/stock pools among those nine,
same window (to 2026-11-13 06:40 UTC), passive LP net bp at 5 min and 1 h; then the same set after 11-13."""
import os, pickle, sys, datetime as dt
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import rowtype  # noqa
NINE = {"NVDA", "TSLA", "SPY", "QQQ", "AAPL", "MSFT", "META", "AMZN", "GOOGL"}
cut = dt.datetime(2026, 11, 13, 6, 40, tzinfo=dt.timezone.utc).timestamp()
rows = [r for r in pickle.load(open(f"{H}/data/rows.pkl", "rb"))["rows"] if r.sym in NINE and (r.usdq or r.qsym in NINE)]
for nm, f in (("to 11-13", lambda r: r.t < cut), ("after 11-13", lambda r: r.t >= cut)):
    rs = [r for r in rows if f(r)]
    u = sum(r.usd for r in rs); d = (max(r.t for r in rs) - min(r.t for r in rs)) / 86400
    o = [f"{nm}: ${u/1e6:.1f}M over {d:.1f} d"]
    for h in (300, 3600):
        xs = [r for r in rs if r.lp.get(h) is not None]
        o.append(f"LP {h}s {sum(r.lp[h]*r.usd for r in xs)/sum(r.usd for r in xs)*1e4:.1f}bp")
    o.append(f"hookless share {sum(r.usd for r in rs if r.hooks == '0x'+'0'*40)/u:.0%}")
    print("  ".join(o))
