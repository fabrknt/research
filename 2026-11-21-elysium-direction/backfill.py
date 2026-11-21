"""Elysium swap logs (v4, v3, v2, DLMM) for a UTC window, from the public RPC, 1,000-block chunks on 4 threads.
Adapted from the earlier Elysium backfill.py. usage: backfill.py START_ISO END_ISO OUTDIR
Writes OUTDIR/part_<block>.jsonl, one compact log per line with its block timestamp."""
import sys, os, json, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import *
from concurrent.futures import ThreadPoolExecutor
iso = lambda s: int(datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
t0, t1, out = iso(sys.argv[1]), iso(sys.argv[2]), sys.argv[3]
os.makedirs(out, exist_ok=True)
b0, b1 = block_at(t0), block_at(t1) - 1
print("blocks", b0, b1, flush=True)
chunks = [(s, min(s + 999, b1)) for s in range(b0, b1 + 1, 1000)]
def job(c):
    p = f"{out}/part_{c[0]}.jsonl"
    if os.path.exists(p): return
    L = get_logs({"topics": [[V4, V3, V2, DLMM]]}, *c)
    with open(p + ".tmp", "w") as f:
        for l in L:
            f.write(json.dumps({"a": l["address"], "tp": l["topics"], "d": l["data"], "n": int(l["blockNumber"], 16), "i": int(l["logIndex"], 16),
                                "t": int(l["blockTimestamp"], 16), "h": l["transactionHash"]}, separators=(",", ":")) + "\n")
    os.rename(p + ".tmp", p)
done = 0
with ThreadPoolExecutor(4) as ex:
    for _ in ex.map(job, chunks):
        done += 1
        if done % 200 == 0: print(done, "/", len(chunks), flush=True)
print("done", flush=True)
