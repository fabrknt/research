"""Rank all swap venues in a short window by USD volume (legs priced only when one side is USDC or HYPE).
usage: sample_rank.py START_UNIX SECONDS"""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import *
from concurrent.futures import ThreadPoolExecutor
t0, dur = int(sys.argv[1]), int(sys.argv[2])
b0, b1 = block_at(t0), block_at(t0 + dur) - 1
print("blocks", b0, b1, file=sys.stderr)
ch = [(s, min(s + 999, b1)) for s in range(b0, b1 + 1, 1000)]
with ThreadPoolExecutor(4) as ex: L = sum(ex.map(lambda c: get_logs({"topics": [[V4, V3, V2, DLMM]]}, *c), ch), [])
print("logs", len(L), file=sys.stderr)
cnt = collections.Counter(); by = collections.Counter()
for l in L:
    k = l["address"] + (l["topics"][1] if l["topics"][0] == V4 else "")
    cnt[(l["topics"][0][:10], k)] += 1
json.dump(L, open("data/sample_logs.json", "w"))
for (t, k), n in cnt.most_common(40): print(t, k, n)
