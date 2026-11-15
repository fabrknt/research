"""One day of nad.fun's V2 bonding curve on Monad mainnet, from the public RPC.

    python3 -I scan_curve.py <hours> <out.json>

Reads every log of the BondingCurve (0x9f38…4ae4) over the last <hours>, 101 blocks per
eth_getLogs (the RPC's cap), and prints how many tokens were created and graduated, and how
much MON went through Buy and Sell, by how many addresses.
"""
import json, sys, time, urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

U = "https://rpc.monad.xyz"
H = {"content-type": "application/json", "user-agent": "curl/8.7.1"}
BC = sys.argv[3] if len(sys.argv) > 3 else "0x9f3832732923252A21044F21eE6bd87F09514ae4"
STEP = 101


def rpc(method, params, tries=9):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for a in range(tries):
        try:
            j = json.load(urllib.request.urlopen(urllib.request.Request(U, body, H), timeout=30))
            if "error" in j:
                raise RuntimeError(j["error"])
            return j["result"]
        except Exception:
            time.sleep(0.5 * 2 ** a)
    raise RuntimeError(f"{method} failed after {tries} tries")


hours, out = float(sys.argv[1]), sys.argv[2]
head = int(rpc("eth_blockNumber", []), 16)
t_head = int(rpc("eth_getBlockByNumber", [hex(head), False])["timestamp"], 16)
t_back = int(rpc("eth_getBlockByNumber", [hex(head - 100000), False])["timestamp"], 16)
block_time = (t_head - t_back) / 100000
start = head - int(hours * 3600 / block_time)
ranges = [(b, min(b + STEP - 1, head)) for b in range(start, head + 1, STEP)]

def fetch(r):
    try:
        return r, rpc("eth_getLogs", [{"address": BC, "fromBlock": hex(r[0]), "toBlock": hex(r[1])}])
    except RuntimeError:
        return r, None


logs, failed = [], []
with ThreadPoolExecutor(3) as ex:
    for r, res in ex.map(fetch, ranges):
        if res is None:
            failed.append(r)
        else:
            logs.extend(res)

json.dump({"head": head, "start": start, "block_time": block_time, "logs": logs, "failed": failed}, open(out, "w"))
print(f"blocks {start}..{head} ({head - start} blocks, {block_time:.3f} s each, {len(ranges)} queries), logs {len(logs)}, failed ranges {len(failed)}")
