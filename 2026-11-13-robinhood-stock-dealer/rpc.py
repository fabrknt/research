"""Robinhood Chain の公開 RPC への最小の JSON-RPC と getLogs の分割取得。"""
import json, time, urllib.request

RPC = "https://rpc.mainnet.chain.robinhood.com"


class RangeError(RuntimeError):
    """範囲や件数が多すぎるという RPC のエラー。範囲を縮めて取り直す。"""


def call(method, params, retries=20):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for i in range(retries):
        try:
            req = urllib.request.Request(RPC, body, {"Content-Type": "application/json", "User-Agent": "curl/8.7.1"})
            r = json.load(urllib.request.urlopen(req, timeout=60))
        except Exception:
            # 429 や一時的な失敗は、待って同じ範囲で取り直す。
            if i == retries - 1:
                raise
            time.sleep(min(30, 2 ** i))
            continue
        if "error" in r:
            msg = str(r["error"])
            if any(w in msg for w in ("range", "spans", "too many", "limit", "exceed")):
                raise RangeError(msg)
            raise RuntimeError(msg)
        return r["result"]


def block(n):
    return call("eth_getBlockByNumber", [hex(n), False])


def logs(address, topics, start, end, step=2_000_000):
    """[start, end] を step ずつ取る。多すぎると言われたら半分に割る。"""
    out, a = [], start
    while a <= end:
        b = min(a + step - 1, end)
        try:
            out += call("eth_getLogs", [{"address": address, "topics": topics,
                                         "fromBlock": hex(a), "toBlock": hex(b)}])
            a = b + 1
        except RangeError:
            if step <= 1000:
                raise
            step //= 2
    return out
