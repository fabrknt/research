"""Elysium public RPC helpers (no key). Adapted from the earlier Elysium measurement scripts (common.py, backfill.py, gap_hourly.py)."""
import json, time, urllib.request
R = "https://rpc.elysium.kinetiq.xyz"
V4 = "0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f"
V3 = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"
V2 = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"
DLMM = "0xad7d6f97abf51ce18e17a38f4d70e975be9c0708474987bb3e26ad21bd93ca70"
INIT = "0xdd466e674ea557f56295e2d0218a125ea4b4f0f6f3307b95f85e6110838d6438"
WHYPE = "0xba876237b0f021a6c6d852d6c26e107997cc5e81"; USDC = "0xb47c4c8f73f009cc0c0d3f92b388d13e293f0b65"; NATIVE = "0x" + "0" * 40
s256 = lambda h: (lambda v: v - (1 << 256) if v >> 255 else v)(int(h, 16))
class TooMany(Exception): pass
class RpcError(Exception): pass  # a JSON-RPC error answer (e.g. a reverted eth_call): not retried
def rpc(m, p, tries=10):
    err = None
    for i in range(tries):
        try:
            r = urllib.request.Request(R, json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode(), {"content-type": "application/json", "user-agent": "curl/8"})
            j = json.load(urllib.request.urlopen(r, timeout=60))
            if "error" in j:
                if j["error"].get("code") == -32005 or "10000" in str(j["error"]): raise TooMany(j["error"])
                raise RpcError(j["error"])
            return j["result"]
        except (TooMany, RpcError): raise
        except Exception as e: err = e; time.sleep(min(30, 2 ** i))
    raise err
def ts(n): return int(rpc("eth_getBlockByNumber", [hex(n), False])["timestamp"], 16)
def block_at(t):
    lo, hi = 1, int(rpc("eth_blockNumber", []), 16)
    while lo < hi:
        m = (lo + hi) // 2
        if ts(m) < t: lo = m + 1
        else: hi = m
    return lo
def get_logs(flt, s, e):
    """eth_getLogs over [s, e], halving the range when the RPC's 10,000-log limit is hit."""
    try: return rpc("eth_getLogs", [dict(flt, fromBlock=hex(s), toBlock=hex(e))])
    except TooMany:
        if s == e: raise
        m = (s + e) // 2; return get_logs(flt, s, m) + get_logs(flt, m + 1, e)
def call(to, data, block="latest"): return rpc("eth_call", [{"to": to, "data": data}, block])
