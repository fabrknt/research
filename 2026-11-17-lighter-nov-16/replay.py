"""Replay Lighter blobs and compare positions of accounts created inside the window with the API.

usage: replay.py BLOB_DIR COMMITS_TSV CUTOFF_UNIX

COMMITS_TSV lines: batch tx block. Accounts are only compared when their whole history is in the
window (created inside it) and the API says their last transaction is before CUTOFF_UNIX, so the API
state should equal the last committed state.
"""

import json
import sys
import time
import urllib.request
from decimal import Decimal

from decode import decode

API = "https://mainnet.zklighter.elliot.ai/api/v1"


def get(path: str):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(f"{API}/{path}", timeout=20) as r:
                return json.load(r)
        except Exception:
            time.sleep(1 + attempt)
    raise RuntimeError(path)


def main(blob_dir: str, commits: str, cutoff: float) -> None:
    batches = sorted(int(line.split()[0]) for line in open(commits))
    created: dict[int, int] = {}
    positions: dict[int, dict[int, int]] = {}
    last_change: dict[int, int] = {}
    for b in batches:
        d = decode(open(f"{blob_dir}/blob_{b}.bin", "rb").read())
        for a in d["accounts"]:
            i = a["account_index"]
            if "l1_address" in a and i not in created:
                created[i] = b
                positions[i] = {}
            if i in created and a["positions"]:
                for m, p in a["positions"].items():
                    positions[i][m] = positions[i].get(m, 0) + p["position_delta"]
                last_change[i] = b

    decimals = {o["market_id"]: o["supported_size_decimals"]
                for o in get("orderBooks")["order_books"]}

    traded = [i for i in created if i in last_change]
    print(f"batches {batches[0]}..{batches[-1]} ({len(batches)}), accounts created {len(created)}, "
          f"of which traded {len(traded)}")
    match = mismatch = skipped = nonzero = markets = 0
    for i in traded:
        acct = get(f"account?by=index&value={i}")["accounts"][0]
        if acct["transaction_time"] / 1e6 >= cutoff:
            skipped += 1
            continue
        api = {}
        for p in acct["positions"]:
            size = Decimal(p["position"]) * p["sign"]
            if size:
                api[p["market_id"]] = int(size.scaleb(decimals[p["market_id"]]))
        ours = {m: v for m, v in positions[i].items() if v}
        if ours == api:
            match += 1
            nonzero += bool(ours)
            markets += len(ours)
        else:
            mismatch += 1
            print("MISMATCH", i, "ours", ours, "api", api)
    print(f"compared {match + mismatch}: match {match}, mismatch {mismatch}; "
          f"skipped {skipped} (last tx after cutoff); matches with open positions {nonzero} "
          f"({markets} account-market pairs)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]))
