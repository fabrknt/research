"""72 hours of v4 Swap and ModifyLiquidity for each migrated pool that had real trading (auction >= $10k, >= 100 swaps on day 1),
plus each swap's tx sender (from) and entry contract (to). The window starts at the migrate block, or at the first swap
when the pool sat untraded for the first 48 h (Aztec, FOLD/ETH).
usage: python3 -I swaps72.py -> data/swaps72_<chain>_<poolId10>.json"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rpc, logs, time
def slow(ch, method, params, tries=8):
    """Base's free RPC rate-limits hard; back off for minutes instead of failing."""
    for k in range(60):
        try: return rpc.call(ch, method, params, tries=tries)
        except RuntimeError as e:
            if ch != "base" or "429" not in str(e): raise
            time.sleep(30)
    raise RuntimeError("base still rate-limited")

SWAP = "0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f"
MODL = "0xf208f4912782fd25c7f114ca3723a2d5dd6f3bcc3ac8db5af63baa85f711d5ec"
BT = {"ethereum": 12, "unichain": 1, "base": 2, "arbitrum": 0.25}
H = 72
def s(h): v = int(h, 16); return v - (1 << 256) if v >> 255 else v
def targets():
    L = [x for x in json.load(open("data/lp_all.json")) if (x.get("raisedUSD") or 0) >= 1e4 and x.get("n", 0) >= 100]
    M = {}
    for ch in ("ethereum", "base", "unichain", "arbitrum"):
        for a in json.load(open(f"data/migr_{ch}.json")):
            if a.get("migr"): M[a["migr"]["poolId"]] = a
    return [(x, M[x["poolId"]]) for x in L]
def fetch_range(ch, topics, b0, b1):
    if ch == "ethereum": return logs.get_logs(ch, topics, b0, b1)
    out = []; b = b0; st = logs.STEP[ch]
    while b <= b1:
        e = min(b + st - 1, b1)
        out += [logs.norm(x) for x in slow(ch, "eth_getLogs", [dict(address=logs.PM[ch], topics=topics, fromBlock=hex(b), toBlock=hex(e))], tries=8)]
        b = e + 1
        if ch == "base": time.sleep(0.6)
    return out
def bt(ch, n): return int(rpc.call(ch, "eth_getBlockByNumber", [hex(n), False], tries=4)["timestamp"], 16)
def one(x, a):
    ch = x["chain"]; m = a["migr"]; pid = m["poolId"]
    fn = f"data/swaps72_{ch}_{pid[:10]}.json"
    if os.path.exists(fn): return
    b0 = x.get("firstSwapBlock") or m["block"]
    b1 = b0 + int(H * 3600 / BT[ch]) + 50
    sw = fetch_range(ch, [SWAP, pid], b0, b1)
    bad = [l for l in sw if len(l["data"]) < 2 + 64 * 6]
    for n in sorted(set(l["n"] for l in bad)):   # Routescan sometimes returns empty data; refetch that block over RPC
        fix = {(y["transactionHash"].lower(), int(y["logIndex"], 16)): y["data"] for y in
               slow(ch, "eth_getLogs", [dict(address=logs.PM[ch], topics=[SWAP, pid], fromBlock=hex(n), toBlock=hex(n))], tries=6)}
        for l in bad:
            if l["n"] == n: l["data"] = fix.get((l["tx"].lower(), l["i"]), l["data"])
    sw = [l for l in sw if len(l["data"]) >= 2 + 64 * 6]
    ml = fetch_range(ch, [MODL, pid], m["block"], b1)
    tb0, tb1 = bt(ch, b0), bt(ch, b1)
    def ts(l): return l["t"] if l["t"] else tb0 + (tb1 - tb0) * (l["n"] - b0) / max(1, b1 - b0)
    rows = []
    for l in sorted(sw, key=lambda l: (l["n"], l["i"])):
        w = [l["data"][2 + k:2 + k + 64] for k in range(0, len(l["data"]) - 2, 64)]
        rows.append(dict(n=l["n"], i=l["i"], t=ts(l), tx=l["tx"], sender="0x" + l["topics"][2][26:], a0=s(w[0]), a1=s(w[1]),
                         sp=int(w[2], 16) & ((1 << 160) - 1), liq=int(w[3], 16) & ((1 << 128) - 1), tick=s(w[4]), fee=int(w[5], 16) & 0xffffff))
    mods = []
    for l in sorted(ml, key=lambda l: (l["n"], l["i"])):
        w = [l["data"][2 + k:2 + k + 64] for k in range(0, len(l["data"]) - 2, 64)]
        mods.append(dict(n=l["n"], t=ts(l), tx=l["tx"], sender="0x" + l["topics"][2][26:], tl=s(w[0]), tu=s(w[1]), dL=s(w[2])))
    txs = sorted(set(r["tx"] for r in rows))
    got = rpc.batch(ch, "eth_getTransactionByHash", [[h] for h in txs])
    info = {}
    for h, g in zip(txs, got):
        if g is None: g = rpc.call(ch, "eth_getTransactionByHash", [h], tries=4)
        info[h] = ((g["from"] or "").lower(), (g.get("to") or "").lower())
    for r in rows: r["from"], r["to"] = info[r["tx"]]
    json.dump(dict(chain=ch, tok=x["tok"], poolId=pid, b0=b0, b1=b1, tb0=tb0, migrBlock=m["block"], usdper=x["usdper"], rows=rows, mods=mods), open(fn, "w"))
    print(ch, x["tok"], len(rows), "swaps", len(mods), "mods", file=sys.stderr, flush=True)

for x, a in sorted(targets(), key=lambda t: t[0]["chain"] == "base"):   # Base last: its free RPC rate-limits
    try: one(x, a)
    except Exception as e: print("failed", x["chain"], x["tok"], e, file=sys.stderr, flush=True)
