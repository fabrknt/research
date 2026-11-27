"""Open-labelled hours split: real = 23/24/25 Nov and 27 Nov before 18:00 UTC (half-day close 13:00 ET);
excluded = 26 Nov (holiday) and 27 Nov from 18:00 UTC. Per name at $10k: min(r_buy, r_sell) per hour (n, median, min, hours >=10)
for real hours, the same for 27 Nov real hours alone, and the min over real hours of max(r_buy, r_sell) at $10k and $100k.
usage: python3 -I friday.py loop.summary.jsonl"""
import json, sys, statistics as st, datetime as d
from collections import defaultdict
hs = {}
for l in open(sys.argv[1]):
    if l.strip():
        h = json.loads(l)
        if h.get("start") is not None:
            hs.setdefault(h["start"], h)
M = defaultdict(list); F = defaultdict(list); B = defaultdict(list)
nreal = defaultdict(int)
for k in sorted(hs):
    t = d.datetime.fromtimestamp(k, d.timezone.utc)
    if not (t.day in (23, 24, 25) or (t.day == 27 and t.hour < 18)):
        continue
    if any(c["sess"] == "open" for c in hs[k]["cells"]):
        nreal[t.day] += 1
    for c in hs[k]["cells"]:
        if c["sess"] != "open" or c.get("r_buy") is None or c.get("r_sell") is None:
            continue
        if c["usd"] == 10000:
            v = min(c["r_buy"], c["r_sell"])
            M[c["sym"]].append(v)
            if t.day == 27:
                F[c["sym"]].append(v)
        B[(c["sym"], c["usd"])].append(max(c["r_buy"], c["r_sell"]))
print("real open hours by day:", dict(nreal), "total", sum(nreal.values()))
print(f"{'name':7}{'n':>3}{'med':>7}{'min':>7}{'>=10':>5} | fri n{'med':>7}{'min':>7} | best-side min $10k / $100k")
for s in sorted(M):
    v = M[s]; f = F.get(s, [])
    fm = f"{st.median(f):7.1f}{min(f):7.1f}" if f else "      -      -"
    b1 = B.get((s, 10000)); b2 = B.get((s, 100000))
    print(f"{s:7}{len(v):>3}{st.median(v):7.1f}{min(v):7.1f}{sum(x >= 10 for x in v):>5} | {len(f):>5}{fm} | "
          f"{min(b1):.1f} / {('%.1f' % min(b2)) if b2 else '-'}")
