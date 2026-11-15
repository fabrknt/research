"""プールの相手側に多いトークンの記号と桁数を調べる。"""
import json
from collections import Counter
from rpc import call

STOCKS = json.load(open("data/stocks.json"))  # sym -> addr


def erc20(a, sel):
    if a == "0x" + "0" * 40:
        return {"0x95d89b41": "ETH", "0x313ce567": 18}[sel]
    r = call("eth_call", [{"to": a, "data": sel}, "latest"])
    b = bytes.fromhex(r[2:])
    if sel == "0x313ce567":
        return int.from_bytes(b[:32], "big")
    n = int.from_bytes(b[32:64], "big")
    return b[64:64 + n].decode(errors="ignore")


if __name__ == "__main__":
    T = {a.lower() for a in STOCKS.values()}
    c = Counter()
    for x in json.load(open("data/pools.json")):
        for k in ("currency0", "currency1"):
            if x[k] not in T:
                c[x[k]] += 1
    for a, n in c.most_common(12):
        print(a, n, erc20(a, "0x95d89b41"), erc20(a, "0x313ce567"))
