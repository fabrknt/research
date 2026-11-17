"""Follow accounts, and the pools they hold shares in, through a directory of blobs.

usage: trace.py BLOB_DIR ACCOUNT_INDEX...

BLOB_DIR is what fetch.sh wrote (commits.tsv and blob_<batch>.bin). For every batch, prints each
followed account's net change in that batch: USDC (asset 3), pool shares, pool info, how many
markets' positions changed, and the L1 address when the blob carries one; then the USDC change summed
over every account in the batch. A pool joins the followed set in the batch where a followed account
first holds its shares.
"""

import sys

from decode import decode
from rpc import block_time, utc

MAX_ACCOUNT_INDEX = (1 << 48) - 2  # blobs key pool shares by MAX_ACCOUNT_INDEX - pool index
USDC_ASSET = 3


def main(blob_dir: str, accounts: list[int]) -> None:
    follow = set(accounts)
    commits = [line.split() for line in open(f"{blob_dir}/commits.tsv")]
    for batch, _tx, l1_block in sorted(commits, key=lambda c: int(c[0])):
        d = decode(open(f"{blob_dir}/blob_{batch}.bin", "rb").read())
        rows = d["accounts"]
        for a in rows:
            if a["account_index"] in follow:
                follow |= {MAX_ACCOUNT_INDEX - k for k in a["shares"]}
        when = None
        for a in rows:
            i = a["account_index"]
            if i not in follow:
                continue
            when = when or utc(block_time(int(l1_block)))
            parts = [f"{batch} {when} account {i}"]
            usdc = a["assets"].get(USDC_ASSET)
            if usdc:
                parts.append(f"USDC {usdc / 1e6:+,.2f}")
            if a["shares"]:
                shares = {MAX_ACCOUNT_INDEX - k: v for k, v in a["shares"].items()}
                parts.append(f"shares {shares}")
            if a.get("pool_info"):
                parts.append(f"pool_info {a['pool_info']}")
            if a["positions"]:
                parts.append(f"positions changed in {len(a['positions'])} markets")
            if a.get("l1_address"):
                parts.append(f"l1 {a['l1_address']}")
            print(", ".join(parts))
        if when:
            # Trades only move USDC between accounts; a negative total is USDC leaving Lighter.
            total = sum(a["assets"].get(USDC_ASSET, 0) for a in rows)
            print(f"{batch} {when} all {len(rows)} accounts in the batch: USDC {total / 1e6:+,.2f}")


if __name__ == "__main__":
    main(sys.argv[1], [int(x) for x in sys.argv[2:]])
