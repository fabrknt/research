"""Fables pools (FablesPoolRegistry.activePools(), registry address from DefiLlama's open-source adapter
DefiLlama-Adapters/projects/fables) -> data/fables_pools.json."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import call

REG = "0x159a113e012593d9b3cc63ad45e30f0467e13ef3"
SEL = "0x" + "c9c4f1a1"  # placeholder replaced below


def selector(sig):
    # keccak is not in the stdlib; selector computed with the RPC's web3_sha3
    return call("web3_sha3", ["0x" + sig.encode().hex()])[:10]


if __name__ == "__main__":
    sel = selector("activePools()")
    r = bytes.fromhex(call("eth_call", [{"to": REG, "data": sel}, "latest"])[2:])
    w = lambda i: r[32 * i:32 * i + 32]
    off = int.from_bytes(w(0), "big") // 32
    n = int.from_bytes(w(off), "big")
    out = []
    for j in range(n):
        base = off + 1 + 7 * j  # static tuple: 5 key words + id + active
        k = [w(base + i) for i in range(7)]
        ts = int.from_bytes(k[3], "big")
        out.append({"currency0": "0x" + k[0][12:].hex(), "currency1": "0x" + k[1][12:].hex(),
                    "fee": int.from_bytes(k[2], "big"), "tickSpacing": ts if ts < 2**255 else ts - 2**256,
                    "hooks": "0x" + k[4][12:].hex(), "id": "0x" + k[5].hex(), "active": bool(k[6][-1])})
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/fables_pools.json"), "w"), indent=1)
    print(sel, n, "pools;", len({p["hooks"] for p in out}), "hooks")
    for p in out[:5]:
        print(p)
