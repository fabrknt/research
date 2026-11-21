"""Every Lighter batch blob committed to Ethereum since the last run: one row per commit, the blob base64.

Commits come from the BatchCommit logs of ZkLighter, blobs from Blobscan (the code of
2026-11-18-lighter-state-replay). state["block"] is the last L1 block fully recorded and state["done"] the
commit transactions already recorded in the block after it. A blob that can't be fetched yet stops the run
there (status incomplete), so the next run, within 10 minutes, starts from it and nothing is recorded twice.
"""

import base64
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "2026-11-17-lighter-nov-16"))
sys.path.insert(0, str(ROOT / "2026-11-18-lighter-state-replay"))
from rpc import TOPIC_COMMIT, ZKLIGHTER, call, logs  # noqa: E402
from replay_state import fetch_blob  # noqa: E402

START_BACK = 300    # first run: start about an hour back
CONFIRM = 3         # leave the newest blocks for the next run (reorgs)
MAX_PER_RUN = 40    # a run every 10 minutes sees about 5 commits
L1_BLOCK_S = 12


def run(state: dict) -> list[dict]:
    head = int(call("eth_blockNumber", []), 16) - CONFIRM
    start = state.get("block", head - START_BACK)
    done = set(state.get("done", []))
    rows, block, partial = [], head, []
    if head > start:
        commits = sorted((int(x["blockNumber"], 16), x["logIndex"], int(x["data"][2:66], 16), x["transactionHash"])
                         for x in logs(ZKLIGHTER, [TOPIC_COMMIT], start + 1, head) if not x.get("removed"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "blob.bin"
            for blk, _, batch, tx in commits:
                if blk == start + 1 and tx in done:
                    continue
                if len(rows) >= MAX_PER_RUN or not fetch_blob(tx, path):
                    block = blk - 1  # retry from this commit; the ones before it in its block are done
                    partial = [t for b, _, _, t in commits if b == blk and t in done] + \
                              [r["tx"] for r in rows if r["l1_block"] == blk]
                    break
                rows.append({"t": time.time(), "batch": batch, "tx": tx, "l1_block": blk,
                             "blob": base64.b64encode(path.read_bytes()).decode()})
    else:
        block, partial = start, list(done)
    state["block"], state["done"] = block, partial
    state["status"] = {"incomplete": block < head, "behind_s": max(0, head - block) * L1_BLOCK_S}
    return rows
