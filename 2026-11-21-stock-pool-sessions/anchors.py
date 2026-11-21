"""Block -> timestamp anchors every 10,000 blocks (blocks are ~0.105 s apart and near-constant, so swap times
are interpolated between anchors, as in ../2026-11-13-robinhood-stock-dealer/fetch_swaps.py).
Reuses ~/src/rh-measure/data/anchors.json (read only) and fetches the rest -> data/anchors.json.
Usage: python3 -I anchors.py <from_block> <to_block>"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ThreadPoolExecutor
from rpc import block
H = os.path.dirname(os.path.abspath(__file__))
a, b = int(sys.argv[1]), int(sys.argv[2])
old = {int(k): v for k, v in json.load(open(os.path.expanduser("~/src/rh-measure/data/anchors.json"))).items()}
want = [x for x in range(a - a % 10_000, b + 10_000, 10_000) if x <= b] + [b]
need = [x for x in want if x not in old]
with ThreadPoolExecutor(4) as ex:
    got = dict(zip(need, ex.map(lambda n: int(block(n)["timestamp"], 16), need)))
out = {x: old.get(x, got.get(x)) for x in want}
json.dump(out, open(f"{H}/data/anchors.json", "w"))
print(len(out), "anchors,", len(need), "fetched")
