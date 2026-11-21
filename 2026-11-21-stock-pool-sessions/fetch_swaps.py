"""Every Uniswap v4 Swap on Robinhood Chain between two blocks, all pools, with sqrtPrice, liquidity and logIndex.

Based on ../2026-11-13-robinhood-stock-dealer/fetch_all.py (same chunking: the public RPC returns at most
10,000 logs per call, so 12,000 blocks ≈ 20 minutes per call). Resumable: one CSV per chunk in data/chunks/.
Usage: python3 -I fetch_swaps.py <from_block> <to_block>
Columns: block, logIndex, pool, sender, amount0, amount1, sqrtPriceX96, liquidity, tick, fee, tx
"""
import csv, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ThreadPoolExecutor
from rpc import logs

PM = "0x8366a39CC670B4001A1121B8F6A443A643e40951"
SWAP = "0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f"
STEP = 12_000
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def s(w):
    v = int(w, 16)
    return v - 2**256 if v >= 2**255 else v


def get(ch):
    out = []
    for l in logs(PM, [SWAP], ch[0], ch[1], step=STEP):
        d = l["data"][2:]
        w = [d[i:i + 64] for i in range(0, len(d), 64)]
        out.append((int(l["blockNumber"], 16), int(l["logIndex"], 16), l["topics"][1], "0x" + l["topics"][2][26:],
                    s(w[0]), s(w[1]), int(w[2], 16), int(w[3], 16), s(w[4]), int(w[5], 16), l["transactionHash"]))
    return out


def run(ch):
    path = f"{D}/chunks/{ch[0]}.csv"
    if os.path.exists(path):
        return 0
    rows = get(ch)
    with open(path + ".tmp", "w", newline="") as f:
        csv.writer(f).writerows(rows)
    os.replace(path + ".tmp", path)
    return len(rows)


if __name__ == "__main__":
    a, b = int(sys.argv[1]), int(sys.argv[2])
    os.makedirs(f"{D}/chunks", exist_ok=True)
    chunks = [(x, min(x + STEP - 1, b)) for x in range(a, b + 1, STEP)]
    print("chunks", len(chunks), file=sys.stderr, flush=True)
    t0 = time.time()
    n = 0
    with ThreadPoolExecutor(3) as ex:
        for i, k in enumerate(ex.map(run, chunks)):
            n += k
            if i % 25 == 0:
                print(i, len(chunks), n, round(time.time() - t0), file=sys.stderr, flush=True)
    print("done", file=sys.stderr)
