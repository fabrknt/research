"""data/pools.json のプールについて、HL の 5 分足がある期間の v4 Swap を取る。"""
import json, sys
from concurrent.futures import ThreadPoolExecutor
from rpc import call, logs, block

PM = "0x8366a39CC670B4001A1121B8F6A443A643e40951"
SWAP = "0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f"


def s128(w):
    v = int(w, 16)
    return v - 2**256 if v >= 2**255 else v


def find_block(ts, lo, hi):
    """timestamp が ts 以上になる最初のブロック。"""
    while lo < hi:
        mid = (lo + hi) // 2
        if int(block(mid)["timestamp"], 16) < ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


pools = json.load(open("data/pools_sel.json"))
candles = json.load(open("data/hl_candles.json"))
start_ts = candles["NVDA_5m"][0][0] // 1000
head = int(call("eth_blockNumber", []), 16)
start = find_block(start_ts, head - 30_000_000, head)
print("blocks", start, head, file=sys.stderr)

# ブロック時刻は 1 万ブロックごとの見本から線形補間する(ブロック間隔はほぼ一定 0.1 秒)。
anchors = {}
for b in range(start - start % 10_000, head + 10_000, 10_000):
    bb = min(b, head)
    anchors[bb] = int(block(bb)["timestamp"], 16)
json.dump(anchors, open("data/anchors.json", "w"))


def get(p):
    out = []
    for l in logs(PM, [SWAP, p["id"]], start, head):
        d = l["data"][2:]
        w = [d[i:i + 64] for i in range(0, len(d), 64)]
        out.append({"pool": p["id"], "block": int(l["blockNumber"], 16), "tx": l["transactionHash"],
                    "sender": "0x" + l["topics"][2][26:],
                    "a0": s128(w[0]), "a1": s128(w[1]), "sqrtP": int(w[2], 16),
                    "liq": int(w[3], 16), "fee": int(w[5], 16)})
    return out


with ThreadPoolExecutor(3) as ex:
    swaps = [s for r in ex.map(get, pools) for s in r]
json.dump(swaps, open("data/swaps.json", "w"))
print(len(swaps), "swaps", file=sys.stderr)
