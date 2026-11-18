"""The state root and validium root Lighter committed on Ethereum for one batch.

usage: roots.py STATE_FILE      # the batch and L1 block a replay_state.py state file stopped at
       roots.py BATCH L1_BLOCK  # or name them

Prints `newStateRoot newValidiumRoot batch`: words 19 and 20 of the last commitBatch for that batch,
ready to pass to ../2026-11-17-lighter-nov-16/stateroot (cmd/snapshotroot).
"""

import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "2026-11-17-lighter-nov-16"))
from rpc import TOPIC_COMMIT, ZKLIGHTER, call, logs  # noqa: E402


def roots(batch: int, block: int) -> tuple[str, str]:
    commits = [x for x in logs(ZKLIGHTER, [TOPIC_COMMIT], block, block)
               if int(x["data"][2:66], 16) == batch and not x.get("removed")]
    if not commits:
        raise SystemExit(f"no commit of batch {batch} in block {block}")
    data = call("eth_getTransactionByHash", [commits[-1]["transactionHash"]])["input"][10:]
    word = lambda i: "0x" + data[64 * i: 64 * i + 64]
    return word(19), word(20)


if __name__ == "__main__":
    if len(sys.argv) == 2:
        with gzip.open(sys.argv[1], "rt") as f:
            meta = json.loads(f.readline())
        batch, block = meta["batch"], meta["l1_block"]
    else:
        batch, block = int(sys.argv[1]), int(sys.argv[2])
    print(*roots(batch, block), batch)
