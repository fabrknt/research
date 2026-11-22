"""Wintermute receiving a token BitGo has just added: the trace that came hours before Robinhood listings.

Study: 2026-11-22-listing-precursors. Buying every BitGo addition loses against BTC; none of 128 tokens that
Wintermute never received was listed, and in CASHCAT, RE and BILL Wintermute's first receipt came 0.1-1.5 days
before the listing. So this watches, in real time, only tokens BitGo added in the last WATCH_DAYS.

At each process start and every REFRESH_S it reads BitGoJS's token definitions (modules/statics on master)
for Ethereum, Base, Arbitrum and Robinhood Chain. Ids present at the first read are the baseline and never
watched; an id that appears later is watched for WATCH_DAYS (tokenized stocks and stablecoins skipped), and
its first scan starts at the block of the previous read, so a receipt between BitGo's merge and this read is
not missed. A read that brings more than BULK new ids is taken as a reformat and joins the baseline unwatched.
An id is never watched twice.

Every run (300 s) it asks each chain's public RPC for Transfer logs of the watched contracts into the
labelled Wintermute addresses below (Etherscan labels and Blockscout metadata tags, 2026-11-22), from the
block after the last one read, up to CONFIRM blocks behind the head (no alert from a block that may reorg).
A range the RPC rejects is halved (and widened again after a success, the width kept in state["spans"]); at
most MAX_CALLS calls a run, and the rest is left as backlog
(status behind_blocks) rather than skipped. The first receipt of a watched token gives a "wintermute" row; a new
Robinhood Chain addition gives an "added" row. If NTFY_TOPIC is set, both are also pushed to
https://ntfy.sh/<topic> (the topic is a secret; it is the only place names leave the encrypted rows), tried
three times; a push that still fails is counted in status push_failed.

Rows: {"kind": "added", "id", "name", "chain", "contract"} and
{"kind": "wintermute", "id", "name", "chain", "contract", "to", "tx", "block", "added_t"}.
The state is published unencrypted and BitGo's token list is public, so ids are kept only as HMACs under the
LISTING_WATCH_KEY secret (without it the source does nothing): state["base"] ids never to watch,
state["watch"] hmac -> {chain, added, from, seen}, state["blocks"] the scan cursor and state["read_block"] each
chain's head at the last BitGo read.
"""

import hashlib
import hmac
import os
import re
import time
import urllib.request

from common import fetch

BITGO = "https://raw.githubusercontent.com/BitGo/BitGoJS/master/modules/statics/src/"
FILES_API = "https://api.github.com/repos/BitGo/BitGoJS/contents/modules/statics/src/coins"
EXTRA = ["allCoinsAndTokens.ts", "coins.ts"]
RPC = {
    "eth": "https://ethereum-rpc.publicnode.com",
    "baseeth": "https://base-rpc.publicnode.com",
    "arbeth": "https://arb1.arbitrum.io/rpc",
    "hoodeth": "https://rpc.mainnet.chain.robinhood.com",
}
MAX_SPAN = {"eth": 2_000, "baseeth": 10_000, "arbeth": 50_000, "hoodeth": 50_000}  # blocks per getLogs call
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
WINTERMUTE = [  # labelled trading and treasury wallets; exploiter, negotiator and look-alike names left out
    "0x0000006daea1723962647b7e189d311d757fb793", "0x000002cba8dfb0a86a47a415592835e17fac080a",
    "0x5cddebd8a7b3bc60156550187bf5465b1c3290f5", "0xf8191d98ae98d2f7abdfb63a9b0b812b93c873aa",
    "0xce84449a8ebec019ac110a4b6662e55d0fd9f228", "0xdbf5e9c5206d0db70a90108bf936da60221dc080",
    "0x18ec285a48499a67a35bf38ecfa17542e94c603a", "0x51c72848c68a965f66fa7a88855f9f7784502a7f",
    "0x4f3a120e72c76c22ae802d129f599bfdbc31cb81", "0x280027dd00ee0050d3f9d168efd6b40090009246",
    "0x0087bb802d9c0e343f00510000729031ce00bf27", "0xe1769227ef92659c0c8505531ba77cf4b2746ce3",
    "0x27920e8039d2b6e93e36f5d5f53b998e2e631a70",
    # Blockscout "related_level_1" cluster tags, lower confidence
    "0x8e914fe8984e232cb5ea448c8fd83a6f9a5c6c9f", "0x18c5fb0518c81510e80d4d350bc3a8778c548d6a",
    "0x0e5e696d19029ceb1e199fead470d71901de9407", "0x06920c9fc643de77b99cb7670a944ad31eaaa260",
    "0xb8a56efab668bf7b84752b9285940b78a58ba5c4", "0xa9dcd7a6e00cff04a91b7509e3a2cdd144ddad77",
    "0xdbefb887662ca19cd485381f3386fe5f8537b910",
]
CONFIRM = {"eth": 3, "baseeth": 30, "arbeth": 120, "hoodeth": 120}
MAX_CALLS = 40
WATCH_DAYS = 30
REFRESH_S = 6 * 3600
BULK = 100
TOKEN = re.compile(r"\(\s*'[0-9a-f-]{36}',\s*'(eth|baseeth|arbeth|hoodeth):([a-z0-9._-]+)',\s*'([^']*)',"
                   r"\s*\d+,\s*'(0x[0-9a-fA-F]{40})'")
SKIP = re.compile(r"xstock|tokenized|ondo|stock|backed|\binc\b|corp|etf|treasury|•|usd|eur|jpy|gbp|dollar|euro",
                  re.I)

_cache = {"at": 0.0, "tokens": {}}  # id -> (name, chain, contract); per process


def h(s: str) -> str:
    return hmac.new(os.environ["LISTING_WATCH_KEY"].encode(), s.encode(), hashlib.sha256).hexdigest()[:20]


def pad(a: str) -> str:
    return "0x" + "0" * 24 + a[2:].lower()


def rpc(chain: str, method: str, params: list):
    d = fetch(RPC[chain], {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if "error" in d:
        raise RuntimeError(f"{chain} {method}: {d['error'].get('message', '')[:120]}")
    return d["result"]


def read_bitgo() -> dict:
    files = ["coins/" + f["name"] for f in fetch(FILES_API)
             if f["name"].endswith(".ts") and not f["name"].startswith("ofc")] + EXTRA
    tokens = {}
    for f in files:
        for m in TOKEN.finditer(fetch(BITGO + f, raw=True)):
            chain, sym, name, addr = m.groups()
            tokens.setdefault(f"{chain}:{sym}", (name, chain, addr.lower()))
    if len(tokens) < 500:  # a partial or changed layout: don't let it reset the baseline
        raise RuntimeError(f"only {len(tokens)} BitGo tokens parsed")
    return tokens


def notify(title: str, body: str) -> bool:
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        return True
    for i in range(3):
        try:
            req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode(),
                                         headers={"Title": title, "Priority": "high", "user-agent": "fabrknt-research"})
            urllib.request.urlopen(req, timeout=15).read()
            return True
        except Exception:
            time.sleep(2 + 3 * i)
    return False  # the row is still the record


def get_logs(chain: str, addrs: list, a: int, b: int) -> list:
    return rpc(chain, "eth_getLogs", [{"address": addrs, "fromBlock": hex(a), "toBlock": hex(b),
                                       "topics": [TRANSFER, None, [pad(w) for w in WINTERMUTE]]}])


def run(state: dict) -> list[dict]:
    if not os.environ.get("LISTING_WATCH_KEY"):
        state["status"] = {"incomplete": False, "disabled": True}
        return []
    now, rows, pushes = time.time(), [], []
    base, watch = set(state.get("base", [])), state.get("watch", {})
    blocks, read_block, failed = state.get("blocks", {}), state.get("read_block", {}), []
    heads = {}
    for chain in RPC:
        try:
            heads[chain] = int(rpc(chain, "eth_blockNumber", []), 16) - CONFIRM[chain]
        except Exception:
            failed.append(chain)
    if now - _cache["at"] > REFRESH_S or not _cache["tokens"]:
        _cache.update(tokens=read_bitgo(), at=now)
        fresh = [i for i in _cache["tokens"] if h(i) not in base and h(i) not in watch]
        bulk = not base or len(fresh) > BULK
        for i in fresh:
            name, chain, addr = _cache["tokens"][i]
            if bulk or SKIP.search(name) or SKIP.search(i.split(":")[1]):
                base.add(h(i))
                continue
            start = read_block.get(chain, blocks.get(chain, heads.get(chain, 0)))
            watch[h(i)] = {"chain": chain, "added": now, "from": start, "seen": False}
            if chain == "hoodeth":
                rows.append({"kind": "added", "id": i, "name": name, "chain": chain, "contract": addr})
                pushes.append((f"BitGo added {i}", f"{name} {addr}\nRobinhood Chain token, now watching Wintermute for it"))
        read_block.update(heads)

    by_hash = {h(i): (i, *v) for i, v in _cache["tokens"].items()}
    spans = state.get("spans", {})
    behind = 0
    for chain, head in heads.items():
        live = {k: by_hash[k] for k, w in watch.items() if w["chain"] == chain and not w["seen"] and k in by_hash}
        cursor = blocks.get(chain, head)
        if live:  # new watches start where their read began, before the shared cursor
            cursor = min([cursor] + [watch[k]["from"] for k in live if watch[k]["from"] < cursor])
        else:
            blocks[chain] = head
            continue
        calls, span = 0, spans.get(chain, MAX_SPAN[chain])
        try:
            start = cursor + 1
            while start <= head and calls < MAX_CALLS:
                end = min(head, start + span - 1)
                todo = [k for k in live if watch[k]["from"] < end and not watch[k]["seen"]]
                if todo:
                    by_addr = {live[k][3]: k for k in todo}
                    calls += 1
                    try:
                        logs = get_logs(chain, sorted(by_addr), start, end)
                    except Exception:  # rejected (JSON-RPC error or HTTP 4xx/5xx after fetch's retries): halve, same start
                        if span == 1:
                            raise
                        span = max(1, span // 2)
                        continue
                    span = min(MAX_SPAN[chain], span * 2)  # widen again after a success
                    for lg in logs:
                        k = by_addr.get(lg["address"].lower())
                        if not k or watch[k]["seen"] or int(lg["blockNumber"], 16) <= watch[k]["from"]:
                            continue
                        i, name, _, addr = live[k]
                        watch[k]["seen"] = True
                        to = "0x" + lg["topics"][2][-40:]
                        rows.append({"kind": "wintermute", "id": i, "name": name, "chain": chain, "contract": addr,
                                     "to": to, "tx": lg["transactionHash"], "block": int(lg["blockNumber"], 16),
                                     "added_t": watch[k]["added"]})
                        days = (now - watch[k]["added"]) / 86400
                        pushes.append((f"Wintermute received {i}", f"{name} {addr}\nto {to} tx {lg['transactionHash']}\n"
                                                                   f"{days:.1f} d after BitGo added it"))
                for k in todo:  # each watch's own start moves with the scan
                    watch[k]["from"] = max(watch[k]["from"], end)
                blocks[chain] = max(blocks.get(chain, 0), end)
                start = end + 1
        except Exception:
            failed.append(chain)
        spans[chain] = span  # what is left past MAX_CALLS is backlog for the next run
        lag = [watch[k]["from"] for k in live if not watch[k]["seen"]] + [blocks.get(chain, head)]
        behind += max(0, head - min(lag))

    for k in [k for k, w in watch.items() if now - w["added"] >= WATCH_DAYS * 86400
              and (w["seen"] or (w["chain"] in heads and w["from"] >= heads[w["chain"]]))]:
        base.add(k)  # done: never watched again
        del watch[k]
    push_failed = sum(not notify(t, b) for t, b in pushes)
    state["base"], state["watch"], state["blocks"], state["read_block"] = sorted(base), watch, blocks, read_block
    state["spans"] = spans
    state["status"] = {"incomplete": bool(failed) or behind > 0, "watching": sum(not w["seen"] for w in watch.values()),
                       "failed_chains": failed, "behind_blocks": behind, "push_failed": push_failed}
    return rows
