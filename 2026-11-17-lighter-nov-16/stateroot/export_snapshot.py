"""Turn Lighter's batch-166859 snapshot blobs into JSON lines for cmd/snapshotroot.

usage: export_snapshot.py SNAPSHOT_DIR OUT.jsonl

Line 1 is the public market details (from blob_0's header; every blob's header is checked to be the
same). Then one line per account: index, l1 address, type, non-zero positions as
[market, position, funding prefix sum], non-zero assets, pool shares and pool info.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from decode import MARKETS, decode, pub_data  # noqa: E402

MAX_ACCOUNT_INDEX = (1 << 48) - 2


def market_header(blob: bytes) -> list[dict]:
    pd = pub_data(blob)
    off = 2 + 32
    marks = [int.from_bytes(pd[off + 4 * i: off + 4 * i + 4], "big") for i in range(MARKETS)]
    off += MARKETS * 4
    funding = []
    for i in range(MARKETS):
        neg, abs_ = pd[off + 9 * i], int.from_bytes(pd[off + 9 * i + 1: off + 9 * i + 9], "big")
        funding.append(-abs_ if neg == 1 else abs_)
    off += MARKETS * 9
    quote = [int.from_bytes(pd[off + 2 * i: off + 2 * i + 2], "big") for i in range(MARKETS)]
    return [{"mark": m, "funding": f, "quote": q} for m, f, q in zip(marks, funding, quote)]


def main(snapshot: str, out: str) -> None:
    files = sorted(Path(snapshot).glob("blob_*.bin"), key=lambda p: int(p.stem.split("_")[1]))
    header = None
    n = 0
    with open(out, "w") as f:
        for path in files:
            blob = path.read_bytes()
            h = market_header(blob)
            if header is None:
                header = h
                f.write(json.dumps({"markets": h}) + "\n")
            elif h != header:
                raise SystemExit(f"{path.name}: market header differs from blob_0")
            d = decode(blob)
            if d["version"] != 0:
                raise SystemExit(f"{path.name}: version {d['version']}, expected 0")
            for a in d["accounts"]:
                f.write(json.dumps({
                    "i": a["account_index"],
                    "l1": a.get("l1_address"),
                    "t": a["account_type"],
                    "p": [[m, p["position_delta"], p["funding_prefix_sum_delta"]]
                          for m, p in sorted(a["positions"].items())
                          if p["position_delta"] or p["funding_prefix_sum_delta"]],
                    "a": [[k, v] for k, v in sorted(a["assets"].items()) if v],
                    "s": sorted([MAX_ACCOUNT_INDEX - diff, amt] for diff, amt in a["shares"].items()),
                    "pi": a.get("pool_info"),
                }) + "\n")
                n += 1
    print(f"{len(files)} blobs, {n} accounts -> {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
