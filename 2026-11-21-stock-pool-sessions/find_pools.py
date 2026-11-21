"""All Uniswap v4 pools on Robinhood Chain (every Initialize event, no topic filter) -> data/pools_all.json.

Decoding follows ../2026-11-13-robinhood-stock-dealer/find_pools.py.
Usage: python3 -I find_pools.py <to_block>
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ThreadPoolExecutor
from rpc import logs

PM = "0x8366a39CC670B4001A1121B8F6A443A643e40951"
INIT = "0xdd466e674ea557f56295e2d0218a125ea4b4f0f6f3307b95f85e6110838d6438"
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

if __name__ == "__main__":
    head = int(sys.argv[1])
    spans = [(a, min(a + 2_000_000 - 1, head)) for a in range(0, head + 1, 2_000_000)]
    with ThreadPoolExecutor(3) as ex:
        found = [l for r in ex.map(lambda s: logs(PM, [INIT], s[0], s[1], step=500_000), spans) for l in r]
    pools = []
    for l in found:
        d = l["data"][2:]
        w = [d[i:i + 64] for i in range(0, len(d), 64)]
        ts = int(w[1], 16)
        pools.append({"id": l["topics"][1], "currency0": "0x" + l["topics"][2][26:],
                      "currency1": "0x" + l["topics"][3][26:], "fee": int(w[0], 16),
                      "tickSpacing": ts if ts < 2**23 else ts - 2**256, "hooks": "0x" + w[2][24:],
                      "block": int(l["blockNumber"], 16), "tx": l["transactionHash"]})
    json.dump(pools, open(f"{D}/pools_all.json", "w"))
    print(len(pools), "pools to block", head)
