"""Adaptive eth_getLogs fetcher for Robinhood Chain public RPC (stdlib only).
usage: python3 -I getlogs.py OUT.jsonl ADDRESS FROM TO TOPIC0 [TOPIC1]
Writes compact rows: block, logIndex, txhash, topics, data.
"""
import json, sys, time, urllib.request

RPC = "https://rpc.mainnet.chain.robinhood.com"
MAXSPAN = 10_000_000


def call(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for attempt in range(8):
        try:
            req = urllib.request.Request(RPC, body, {"content-type": "application/json", "user-agent": "research"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except Exception as e:  # network / 429
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("rpc failed")


def fetch(out, addr, frm, to, topics):
    stack = [(frm, to)]
    n = 0
    while stack:
        a, b = stack.pop()
        if b - a + 1 > MAXSPAN:
            mid = (a + b) // 2
            stack += [(mid + 1, b), (a, mid)]
            continue
        res = call("eth_getLogs", [{"address": addr, "fromBlock": hex(a), "toBlock": hex(b), "topics": topics}])
        if "error" in res:
            msg = res["error"].get("message", "")
            if a == b:
                raise RuntimeError(msg)
            mid = (a + b) // 2
            stack += [(mid + 1, b), (a, mid)]
            continue
        for x in res["result"]:
            out.write(json.dumps([int(x["blockNumber"], 16), int(x["logIndex"], 16), x["transactionHash"], x["topics"], x["data"]]) + "\n")
            n += 1
        sys.stderr.write(f"\r{a}-{b} total {n}   ")
    sys.stderr.write("\n")
    return n


if __name__ == "__main__":
    outp, addr, frm, to, t0 = sys.argv[1:6]
    topics = [t0] + ([sys.argv[6]] if len(sys.argv) > 6 else [])
    to = int(call("eth_blockNumber", [])["result"], 16) if to == "latest" else int(to)
    with open(outp, "w") as f:
        print(fetch(f, addr, int(frm), to, topics))
