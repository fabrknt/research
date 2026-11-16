"""Is Hyperliquid's 4-significant-figure book an upper bound on the full-precision walk?

For every round and size that both books fill, cost(coarse) - cost(full) in bp of the full mid.
    python3 check_coarse.py       # reads data/walks.jsonl
"""
import collections
import json
import os
import statistics

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
W = collections.defaultdict(dict)
for line in open(os.path.join(D, "walks.jsonl")):
    w = json.loads(line)
    W[(w["t"], w["var"])][w["venue"]] = w
diff = collections.defaultdict(list)
for v in W.values():
    if "hl" not in v or "hl_coarse" not in v:
        continue
    f, c = v["hl"], v["hl_coarse"]
    mid = (f["bid"] + f["ask"]) / 2
    for a, b in zip(f["sizes"], c["sizes"]):
        if None in (a["buy"], a["sell"], b["buy"], b["sell"]):
            continue
        cost = lambda s: ((s["buy"] - mid) + (mid - s["sell"])) / 2 / mid * 1e4
        diff[a["usd"]].append(cost(b) - cost(a))
print(len({t for t, _ in W}), "rounds")
for usd, xs in sorted(diff.items()):
    xs.sort()
    print(f"${usd:>9,.0f} n={len(xs):4}  coarse - full, bp: min {xs[0]:.2f}  median {statistics.median(xs):.2f}"
          f"  max {xs[-1]:.2f}  coarse cheaper: {sum(x < -0.01 for x in xs)}")
