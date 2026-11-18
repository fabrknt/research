"""Carry Lighter's full state forward from the batch-166859 snapshot, one Ethereum blob at a time.

usage: replay_state.py STATE_IN STATE_OUT MINUTES

STATE_IN is a state file (below) or `snapshot:ACCOUNTS.jsonl` for the export of the batch-166859
snapshot (../2026-11-17-lighter-nov-16/stateroot/export_snapshot.py). Applies the next batches' blobs
in order for up to MINUTES, then writes STATE_OUT. Stops at the first missing or out-of-order batch,
so a later run can resume from STATE_OUT.

State file (gzip JSON lines):
  line 1  {"batch", "l1_block", "markets": [{mark, funding, quote}] (the last blob's header),
           "slots": {market_index: the slot's last market delta}}
  then    one account per line: {"i", "l1", "t", "p": [[market, position, funding]], "a": [[asset, bal]],
           "s": [[pool, shares]], "pi": {total_shares, operator_shares} | null, "b": [[slot, size]]}
"""

import gzip
import json
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "2026-11-17-lighter-nov-16"))
from decode import decode  # noqa: E402
from rpc import TOPIC_COMMIT, ZKLIGHTER, call, logs  # noqa: E402

sys.path.insert(0, str(HERE.parent / "2026-11-17-lighter-nov-16" / "stateroot"))
from export_snapshot import market_header  # noqa: E402

SNAPSHOT_BATCH, SNAPSHOT_L1_BLOCK = 166859, 25007824
MAX_ACCOUNT_INDEX = (1 << 48) - 2
BLOB_BYTES = 131072
PARALLEL = 2  # Blobscan rate-limits; 2 at a time is what fetch.sh found to work


def fetch_blob(tx: str, out: Path) -> bool:
    """One blob per commit transaction: its versioned hash -> each of Blobscan's storage references in turn."""
    for attempt in range(4):
        try:
            vh = call("eth_getTransactionByHash", [tx])["blobVersionedHashes"][0]
            req = urllib.request.Request(f"https://api.blobscan.com/blobs/{vh}", headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=30) as r:
                urls = [x["url"] for x in json.load(r)["dataStorageReferences"] if x.get("url")]
            for url in urls:
                try:
                    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "curl/8"}),
                                                timeout=60) as r:
                        data = r.read()
                except Exception:
                    continue
                if len(data) == BLOB_BYTES:
                    out.write_bytes(data)
                    return True
        except Exception:
            pass
        time.sleep(2 * (attempt + 1))
    return False


def load(path: str):
    if path.startswith("snapshot:"):
        with open(path.removeprefix("snapshot:")) as f:
            head = json.loads(f.readline())
            meta = {"batch": SNAPSHOT_BATCH, "l1_block": SNAPSHOT_L1_BLOCK, "markets": head["markets"], "slots": {}}
            accounts = {}
            for line in f:
                a = json.loads(line)
                a["b"] = []
                accounts[a["i"]] = a
        return meta, accounts
    with gzip.open(path, "rt") as f:
        meta = json.loads(f.readline())
        accounts = {a["i"]: a for a in map(json.loads, f)}
    return meta, accounts


def save(path: str, meta: dict, accounts: dict) -> None:
    tmp = path + ".tmp"
    with gzip.open(tmp, "wt", compresslevel=6) as f:
        f.write(json.dumps(meta) + "\n")
        for i in sorted(accounts):
            f.write(json.dumps(accounts[i], separators=(",", ":")) + "\n")
    os.replace(tmp, path)


def add(pairs: list, key: int, delta: int, width: int = 2) -> list:
    """pairs: [[key, value]] (or [[key, v1, v2]]); add delta(s), drop all-zero entries, keep sorted."""
    d = {p[0]: p[1:] for p in pairs}
    old = d.get(key, [0] * (width - 1))
    new = [o + x for o, x in zip(old, delta if isinstance(delta, list) else [delta])]
    if any(new):
        d[key] = new
    else:
        d.pop(key, None)
    return [[k, *v] for k, v in sorted(d.items())]


def apply(meta: dict, accounts: dict, d: dict, header: list) -> None:
    meta["markets"] = header
    for m in d["markets"]:
        meta["slots"][str(m["market_index"])] = m
    for x in d["accounts"]:
        i = x["account_index"]
        a = accounts.setdefault(i, {"i": i, "l1": None, "t": 0, "p": [], "a": [], "s": [], "pi": None, "b": []})
        if x.get("l1_address"):
            a["l1"] = x["l1_address"]
        if x["account_type"]:
            a["t"] = x["account_type"]
        if x.get("pool_info"):
            pi = a["pi"] or {"total_shares": 0, "operator_shares": 0}
            a["pi"] = {k: pi[k] + x["pool_info"][k] for k in pi}
        for m, p in x["positions"].items():
            a["p"] = add(a["p"], m, [p["position_delta"], p["funding_prefix_sum_delta"]], 3)
        for m, size in x["binary_options"].items():
            a["b"] = add(a["b"], m, size)
        for k, v in x["assets"].items():
            a["a"] = add(a["a"], k, v)
        for diff, v in x["shares"].items():
            a["s"] = add(a["s"], MAX_ACCOUNT_INDEX - diff, v)


def next_commits(after_block: int, want: int) -> list[tuple[int, str, int]]:
    """(batch, tx, l1_block) of the next commits after after_block, the last commit winning per batch."""
    head = int(call("eth_blockNumber", []), 16)
    found: dict[int, tuple[str, int]] = {}
    lo = after_block + 1
    while lo <= head and len(found) < want:
        hi = min(lo + 1999, head)
        for log in logs(ZKLIGHTER, [TOPIC_COMMIT], lo, hi):
            if not log.get("removed"):
                found[int(log["data"][2:66], 16)] = (log["transactionHash"], int(log["blockNumber"], 16))
        lo = hi + 1
    return sorted((b, tx, blk) for b, (tx, blk) in found.items())[:want]


def main(state_in: str, state_out: str, minutes: float) -> None:
    deadline = time.time() + 60 * minutes
    t0 = time.time()
    meta, accounts = load(state_in)
    print(f"loaded batch {meta['batch']}, {len(accounts)} accounts in {time.time() - t0:.0f} s", flush=True)
    work = Path(state_out).parent / "blobs"
    start = meta["batch"]
    while time.time() < deadline - 480:  # a round of 200 blobs takes about 6 min
        commits = next_commits(meta["l1_block"], 200)
        if not commits:
            print("caught up")
            break
        work.mkdir(exist_ok=True)
        with ThreadPoolExecutor(PARALLEL) as pool:
            list(pool.map(lambda c: fetch_blob(c[1], work / f"blob_{c[0]}.bin"), commits))
        # Blobscan rate-limits GitHub's machines now and then: go back for the misses, slower.
        for wait in (20, 60, 120):
            missing = [c for c in commits if not (work / f"blob_{c[0]}.bin").exists()]
            if not missing:
                break
            print(f"{len(missing)} blobs missing, retrying in {wait} s", flush=True)
            time.sleep(wait)
            for b, tx, _blk in missing:
                fetch_blob(tx, work / f"blob_{b}.bin")
        for b, _tx, blk in commits:
            if b != meta["batch"] + 1:
                raise SystemExit(f"expected batch {meta['batch'] + 1}, next commit is {b}")
            f = work / f"blob_{b}.bin"
            if not f.exists():
                print(f"blob for batch {b} missing; stopping here")
                save(state_out, meta, accounts)
                return
            blob = f.read_bytes()
            apply(meta, accounts, decode(blob), market_header(blob))
            meta["batch"], meta["l1_block"] = b, blk
            f.unlink()
        print(f"at batch {meta['batch']} (+{meta['batch'] - start}), {len(accounts)} accounts, "
              f"{(time.time() - t0) / 60:.1f} min", flush=True)
    save(state_out, meta, accounts)
    print(f"saved batch {meta['batch']} -> {state_out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]))
