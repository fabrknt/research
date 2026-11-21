"""Identify swap venues: v4 pool id -> (currency0, currency1, fee, hooks, tickSpacing) from the PoolManager's
Initialize log; v3 pool -> token0/token1/fee by eth_call; token symbol/decimals. Cached in data/pools.json.
Import ident(keys) or run: pools.py LOGS.json"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import *
P = "data/pools.json"
def load(): return json.load(open(P)) if os.path.exists(P) else {"pools": {}, "tokens": {}}
def sym(t, db):
    if t in db["tokens"]: return db["tokens"][t]
    if t == NATIVE: v = ["HYPE", 18]
    else:
        try:
            r = call(t, "0x95d89b41")[2:]; n = int(r[64:128], 16) if len(r) >= 128 else 0
            s = bytes.fromhex(r[128:128 + 2 * n]).decode(errors="replace") if n else bytes.fromhex(r[:64]).rstrip(b"\0").decode(errors="replace")
            d = int(call(t, "0x313ce567"), 16)
        except Exception: s, d = "?", 18
        v = [s, d]
    db["tokens"][t] = v; return v
def ident(keys, db):
    """keys: v4 as PM+id (42+66 chars), v3/v2/dlmm as address."""
    new = [k for k in keys if k not in db["pools"]]
    v4 = {}
    for k in new:
        if len(k) > 42: v4.setdefault(k[:42], []).append(k[42:])
    for pm, ids in v4.items():
        for i in range(0, len(ids), 50):
            for l in get_logs({"address": pm, "topics": [INIT, ids[i:i + 50]]}, 1, int(rpc("eth_blockNumber", []), 16)):
                d = l["data"][2:]
                db["pools"][pm + l["topics"][1]] = {"kind": "v4", "t0": "0x" + l["topics"][2][26:], "t1": "0x" + l["topics"][3][26:],
                    "fee": int(d[0:64], 16), "ts": s256(d[64:128]), "hooks": "0x" + d[128 + 24:192], "init": int(l["blockNumber"], 16)}
    for k in new:
        if len(k) == 42:
            try:
                t0, t1 = ("0x" + call(k, s)[-40:] for s in ("0x0dfe1681", "0xd21220a7"))
                try: fee = int(call(k, "0xddca3f43"), 16)
                except Exception: fee = None
                db["pools"][k] = {"kind": "v3", "t0": t0, "t1": t1, "fee": fee}
            except Exception: db["pools"][k] = {"kind": "?"}
    for k in keys:
        p = db["pools"].get(k, {})
        for t in ("t0", "t1"):
            if t in p: p["s" + t[1]] = sym(p[t], db)
    json.dump(db, open(P, "w"), indent=0)
    return db
if __name__ == "__main__":
    L = json.load(open(sys.argv[1]))
    keys = sorted({l["address"] + (l["topics"][1] if l["topics"][0] == V4 else "") for l in L})
    db = ident(keys, load())
    print(len(keys), "keys")
