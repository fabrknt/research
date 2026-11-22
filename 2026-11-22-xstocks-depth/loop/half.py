"""Best-side room (max r_buy,r_sell) at $1k/$10k, median/min in first vs second half of the hours seen.
usage: python3 -I half.py loop.summary.jsonl"""
import json, sys, statistics as st
from collections import defaultdict
hs = {}
for l in open(sys.argv[1]):
    if l.strip():
        h = json.loads(l)
        if h.get("start") is not None:
            hs.setdefault(h["start"], h)
ks = sorted(hs)
m = len(ks) // 2
sess = sorted({x["sess"] for h in hs.values() for x in h["cells"]})
print("hours", len(ks), "first", ks[0], "split", ks[m], "last", ks[-1], "sess", sess)
c = defaultdict(lambda: ([], []))
for i, k in enumerate(ks):
    for x in hs[k]["cells"]:
        if x["usd"] == 100000 or x.get("r_buy") is None or x.get("r_sell") is None:
            continue
        c[(x["sym"], x["usd"])][i >= m].append(max(x["r_buy"], x["r_sell"]))
print(f"{'name':7}{'usd':>7}{'n1':>4}{'med1':>7}{'min1':>7}{'n2':>4}{'med2':>7}{'min2':>7}")
for k, (a, b) in sorted(c.items()):
    if a and b:
        print(f"{k[0]:7}{k[1]:>7}{len(a):>4}{st.median(a):7.1f}{min(a):7.1f}{len(b):>4}{st.median(b):7.1f}{min(b):7.1f}")
