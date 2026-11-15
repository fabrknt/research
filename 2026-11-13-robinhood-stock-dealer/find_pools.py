"""対象の株トークンを片側に持つ Uniswap v4 プールを Initialize イベントから集める。"""
import json, sys
from rpc import call, logs

PM = "0x8366a39CC670B4001A1121B8F6A443A643e40951"
INIT = "0xdd466e674ea557f56295e2d0218a125ea4b4f0f6f3307b95f85e6110838d6438"
TOKENS = {
    "NVDA": "0xd0601CE157Db5bdC3162BbaC2a2C8aF5320D9EEC",
    "TSLA": "0x322F0929c4625eD5bAd873c95208D54E1c003b2d",
    "SPY": "0x117cc2133c37B721F49dE2A7a74833232B3B4C0C",
    "QQQ": "0xD5f3879160bc7c32ebb4dC785F8a4F505888de68",
    "AAPL": "0xaF3D76f1834A1d425780943C99Ea8A608f8a93f9",
    "MSFT": "0xe93237C50D904957Cf27E7B1133b510C669c2e74",
    "META": "0xc0D6457C16Cc70d6790Dd43521C899C87ce02f35",
    "AMZN": "0x12f190a9F9d7D37a250758b26824B97CE941bF54",
    "GOOGL": "0x2e0847E8910a9732eB3fb1bb4b70a580ADAD4FE3",
}


def topic(addr):
    return "0x" + "0" * 24 + addr[2:].lower()


if __name__ == "__main__":
    head = int(call("eth_blockNumber", []), 16)
    # 公開 RPC は 1 つの位置に複数の値を入れると 10 万ブロックまでしか許さないので、1 値ずつ並列に取る。
    from concurrent.futures import ThreadPoolExecutor
    jobs = [[INIT, topic(a)] for a in TOKENS.values()] + [[INIT, None, topic(a)] for a in TOKENS.values()]
    with ThreadPoolExecutor(3) as ex:
        found = [l for r in ex.map(lambda t: logs(PM, t, 0, head), jobs) for l in r]
    pools = []
    for l in found:
        d = l["data"][2:]
        words = [d[i:i + 64] for i in range(0, len(d), 64)]
        pools.append({
            "id": l["topics"][1],
            "currency0": "0x" + l["topics"][2][26:],
            "currency1": "0x" + l["topics"][3][26:],
            "fee": int(words[0], 16),
            "tickSpacing": int(words[1], 16) if int(words[1], 16) < 2**23 else int(words[1], 16) - 2**256,
            "hooks": "0x" + words[2][24:],
            "block": int(l["blockNumber"], 16),
        })
    json.dump(pools, open("data/pools.json", "w"), indent=1)
    print(len(pools), "pools, head", head)
