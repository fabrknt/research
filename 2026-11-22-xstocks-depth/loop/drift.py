"""Best-side room (max r_buy,r_sell) at $10k, median per ~8h block of hours seen, plus last 4 hours.
usage: python3 -I drift.py loop.summary.jsonl"""
import json, sys, statistics as st
from collections import defaultdict
hs = {}
for l in open(sys.argv[1]):
    if l.strip():
        h = json.loads(l)
        if h.get("start") is not None:
            hs.setdefault(h["start"], h)
ks = sorted(hs)
B = 8
nb = (len(ks) + B - 1) // B
c = defaultdict(lambda: [[] for _ in range(nb)])
for i, k in enumerate(ks):
    for x in hs[k]["cells"]:
        if x["usd"] != 10000 or x.get("r_buy") is None or x.get("r_sell") is None:
            continue
        c[x["sym"]][i // B].append(max(x["r_buy"], x["r_sell"]))
import datetime as d
print("blocks of", B, "hours; starts UTC:", [d.datetime.fromtimestamp(ks[b*B], d.timezone.utc).strftime("%d %H:%M") for b in range(nb)], "n hours", len(ks))
for s, bl in sorted(c.items()):
    print(f"{s:7}" + "".join(f"{st.median(b):8.1f}({len(b)})" if b else "      -   " for b in bl))
