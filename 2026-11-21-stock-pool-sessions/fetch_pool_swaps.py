"""Swap events of the selected pools only (data/pools_sel.json), using an OR of pool ids in topic 1.
The public RPC accepts several values in one topic position only for ranges up to 100,000 blocks, so the
range is cut into 100k-block spans (≈ 2.9 hours each); ids are sent in groups of GROUP.
Resumable: one CSV per span in data/pchunks/. Columns as fetch_swaps.py.
Usage: python3 -I fetch_pool_swaps.py <from_block> <to_block>
"""
import csv, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ThreadPoolExecutor
from rpc import logs
from fetch_swaps import PM, SWAP, s

H = os.path.dirname(os.path.abspath(__file__))
SPAN, GROUP = 100_000, 990


def run(job):
    a, b = job
    path = f"{H}/data/pchunks/{a}.csv"
    if os.path.exists(path):
        return 0
    ids = [p["id"] for p in json.load(open(f"{H}/data/pools_sel.json"))]
    rows = []
    for g in range(0, len(ids), GROUP):
        for l in logs(PM, [SWAP, ids[g:g + GROUP]], a, b, step=SPAN):
            d = l["data"][2:]
            w = [d[i:i + 64] for i in range(0, len(d), 64)]
            rows.append((int(l["blockNumber"], 16), int(l["logIndex"], 16), l["topics"][1], "0x" + l["topics"][2][26:],
                         s(w[0]), s(w[1]), int(w[2], 16), int(w[3], 16), s(w[4]), int(w[5], 16), l["transactionHash"]))
    with open(path + ".tmp", "w", newline="") as f:
        csv.writer(f).writerows(rows)
    os.replace(path + ".tmp", path)
    return len(rows)


if __name__ == "__main__":
    a, b = int(sys.argv[1]), int(sys.argv[2])
    os.makedirs(f"{H}/data/pchunks", exist_ok=True)
    jobs = [(x, min(x + SPAN - 1, b)) for x in range(a, b + 1, SPAN)]
    t0, n = time.time(), 0
    with ThreadPoolExecutor(int(os.environ.get("THREADS", 3))) as ex:
        for i, k in enumerate(ex.map(run, jobs)):
            n += k
            if i % 10 == 0:
                print(i, len(jobs), n, round(time.time() - t0), file=sys.stderr, flush=True)
    print("done", n, file=sys.stderr)
