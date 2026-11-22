"""Closed-session cells at $1k/$10k: per hour, best side room (max of r_buy, r_sell) and the Solana-vs-xyz offset
((buy+sell)/2). Asks whether room is steady across hours or a few hours.
usage: python3 -I offset.py loop.summary.jsonl"""
import json, sys, statistics as st
from collections import defaultdict
c = defaultdict(lambda: defaultdict(list)); seen = set(); sess = set()
for l in open(sys.argv[1]):
    if not l.strip():
        continue
    h = json.loads(l)
    if h.get("start") is None or h["start"] in seen:
        continue
    seen.add(h["start"])
    for x in h["cells"]:
        sess.add(x["sess"])
        if x["usd"] == 100000 or x.get("r_buy") is None or x.get("r_sell") is None:
            continue
        k = (x["sym"], x["usd"])
        c[k]["off"].append((x["buy"] + x["sell"]) / 2)
        c[k]["best"].append(max(x["r_buy"], x["r_sell"]))
print("sessions seen:", sorted(sess), "hours:", len(seen))
print(f"{'name':7}{'usd':>7}{'n':>3}{'off_med':>8}{'off_min':>8}{'off_max':>8}{'best_med':>9}{'best_min':>9}{'hrs>=10':>8}")
for k, v in sorted(c.items()):
    print(f"{k[0]:7}{k[1]:>7}{len(v['best']):>3}{st.median(v['off']):8.1f}{min(v['off']):8.1f}{max(v['off']):8.1f}"
          f"{st.median(v['best']):9.1f}{min(v['best']):9.1f}{sum(b >= 10 for b in v['best']):8}")
