"""Check Lighter's batch-166859 snapshot against the API, without hashing.

usage: check_snapshot.py SNAPSHOT_DIR CUTOFF_UNIX [SAMPLE]

SNAPSHOT_DIR holds blob_0.bin .. blob_555.bin from desertexit/blobs.zip (lighter-prover 2bbc3089).
In the snapshot the "deltas" are full values. An account whose last transaction (API
`transaction_time`) is before CUTOFF_UNIX should still hold exactly the snapshot's positions.
"""

import random
import sys
import time
from decimal import Decimal
from pathlib import Path

from decode import decode
from replay import get

# The account endpoint answers with a human-verification page when asked too fast (2026-11-17).
PACE_SECONDS = 0.6


def main(snapshot: str, cutoff: float, sample: int) -> None:
    accounts = {}
    for f in sorted(Path(snapshot).glob("blob_*.bin"), key=lambda p: int(p.stem.split("_")[1])):
        for a in decode(f.read_bytes())["accounts"]:
            open_positions = {m: p["position_delta"] for m, p in a["positions"].items() if p["position_delta"]}
            if open_positions:
                accounts[a["account_index"]] = open_positions
    # Only accounts with an open position: an all-zero account matching proves nothing.
    print(f"snapshot accounts with an open position: {len(accounts)}")

    decimals = {o["market_id"]: o["supported_size_decimals"] for o in get("orderBooks")["order_books"]}
    random.seed(166859)
    match = mismatch = skipped = missing = nonzero = pairs = 0
    for i in random.sample(sorted(accounts), sample):
        time.sleep(PACE_SECONDS)
        try:
            found = get(f"account?by=index&value={i}").get("accounts") or []
        except RuntimeError:  # includes the API's human-verification page when asked too fast
            found = []
        if not found:
            missing += 1
            continue
        acct = found[0]
        if not acct["transaction_time"] or acct["transaction_time"] / 1e6 >= cutoff:
            skipped += 1
            continue
        api = {}
        for p in acct["positions"]:
            size = Decimal(p["position"]) * p["sign"]
            if size:
                api[p["market_id"]] = int(size.scaleb(decimals[p["market_id"]]))
        ours = {m: v for m, v in accounts[i].items() if v}
        if ours == api:
            match += 1
            nonzero += bool(ours)
            pairs += len(ours)
        else:
            mismatch += 1
            print("MISMATCH", i, "snapshot", ours, "api", api)
    print(f"sampled {sample}: compared {match + mismatch}, match {match}, mismatch {mismatch}; "
          f"skipped {skipped} (traded after the snapshot), missing or refused {missing}; "
          f"matches with open positions {nonzero} ({pairs} account-market pairs)")


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 300)
