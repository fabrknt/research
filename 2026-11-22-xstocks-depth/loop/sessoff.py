"""Per name at $10k, by session: median offset ((buy+sell)/2, Solana vs xyz mid) and median route spread
(rt) and best-side room. Asks whether NVDAx's low open room is price sitting on the xyz mid.
usage: python3 -I sessoff.py loop.summary.jsonl"""
import json, sys, statistics as st
from collections import defaultdict
c = defaultdict(lambda: defaultdict(list)); seen = set()
for l in open(sys.argv[1]):
    if not l.strip():
        continue
    h = json.loads(l)
    if h.get("start") is None or h["start"] in seen:
        continue
    seen.add(h["start"])
    for x in h["cells"]:
        if x["usd"] != 10000 or x.get("r_buy") is None or x.get("r_sell") is None:
            continue
        k = (x["sym"], x["sess"])
        c[k]["off"].append((x["buy"] + x["sell"]) / 2)
        c[k]["half"].append((x["buy"] - x["sell"]) / 2)
        c[k]["best"].append(max(x["r_buy"], x["r_sell"]))
print("hours", len(seen))
print(f"{'name':7}{'sess':>7}{'n':>4}{'off_med':>8}{'half_spread':>12}{'best_med':>9}{'best_min':>9}")
for k, v in sorted(c.items()):
    print(f"{k[0]:7}{k[1]:>7}{len(v['best']):>4}{st.median(v['off']):8.1f}{st.median(v['half']):12.1f}"
          f"{st.median(v['best']):9.1f}{min(v['best']):9.1f}")
