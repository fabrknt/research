"""US-session ('open') hours: per name at $10k and $100k, best-side room = max(r_buy, r_sell) per hour; n, median, min,
hours >=10 and >=20 bp, plus the UTC span of open hours and hedge availability.
usage: python3 -I open.py loop.summary.jsonl"""
import json, sys, statistics as st, datetime as d
from collections import defaultdict
hs = {}
for l in open(sys.argv[1]):
    if l.strip():
        h = json.loads(l)
        if h.get("start") is not None:
            hs.setdefault(h["start"], h)
ts = lambda t: d.datetime.fromtimestamp(t, d.timezone.utc).strftime("%d %H:%M")
op = defaultdict(list)
for k in sorted(hs):
    for c in hs[k]["cells"]:
        op[c["sess"]].append(k) if c["sym"] == "AAPLx" and c["usd"] == 1000 else None
for s, v in op.items():
    print(s, len(v), ts(min(v)), ts(max(v)))
print("open hour starts:", [ts(k) for k in sorted(op.get("open", []))])
V = defaultdict(list)
H = defaultdict(int)
for k in sorted(hs):
    for c in hs[k]["cells"]:
        if c["sess"] != "open" or c["usd"] not in (10000, 100000):
            continue
        H[(c["sym"], c["usd"])] += 1
        if c.get("r_buy") is not None and c.get("r_sell") is not None:
            V[(c["sym"], c["usd"])].append(max(c["r_buy"], c["r_sell"]))
print(f"{'name':7}{'usd':>7}{'cells':>6}{'n':>3}{'med':>8}{'min':>8}{'>=10':>5}{'>=20':>5}")
for (s, u), v in sorted(V.items()):
    print(f"{s:7}{u:>7}{H[(s,u)]:>6}{len(v):>3}{st.median(v):8.1f}{min(v):8.1f}{sum(x>=10 for x in v):>5}{sum(x>=20 for x in v):>5}")
