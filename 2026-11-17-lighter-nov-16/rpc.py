"""A few Ethereum JSON-RPC calls with the standard library. RPC defaults to rpc.mevblocker.io."""

import json
import os
import time
import urllib.request
from datetime import datetime, timezone

RPC = os.environ.get("RPC", "https://rpc.mevblocker.io")
ZKLIGHTER = "0x3b4d794a66304f130a4db8f2551b0070dfcf5ca7"
USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
# keccak256 of the event signatures
TOPIC_COMMIT = "0x181b25ea9d4d730f30d779f3d2099c03b26b653c889d33eef253d54baaacbd0d"  # BatchCommit(uint64,uint32,uint64)
TOPIC_VERIFY = "0x5c836e1ff20ea85c52b6e3d2ef0124d3304bf3b37cc8fb0e2c84ae7d44c0593e"  # BatchVerification(uint64,uint32,uint64)
TOPIC_TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"  # Transfer(address,address,uint256)


def call(method: str, params: list):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    # Some public RPCs refuse urllib's default user agent.
    req = urllib.request.Request(RPC, body, {"Content-Type": "application/json", "User-Agent": "curl/8"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                out = json.load(r)
            if "error" in out:
                raise RuntimeError(out["error"])
            return out["result"]
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))


def logs(address: str, topics: list, from_block: int, to_block, step: int = 2000) -> list:
    """eth_getLogs in chunks; to_block may be "latest"."""
    end = int(call("eth_blockNumber", []), 16) if to_block == "latest" else to_block
    out = []
    for lo in range(from_block, end + 1, step):
        hi = min(lo + step - 1, end)
        out += call("eth_getLogs", [{"address": address, "topics": topics,
                                     "fromBlock": hex(lo), "toBlock": hex(hi)}])
    return out


def block_time(block: int) -> int:
    return int(call("eth_getBlockByNumber", [hex(block), False])["timestamp"], 16)


def utc(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
