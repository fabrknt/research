"""Gaps between Lighter's batch commits on Ethereum, and how long each batch waited for its proof.

usage: gaps.py FROM_BLOCK TO_BLOCK [MIN_GAP_SECONDS]

Prints every gap between consecutive commits of at least MIN_GAP_SECONDS (default 600), the median
gap, and the median and 95th percentile of verification time minus commit time for batches both
committed and verified inside the range.
"""

import statistics
import sys

from rpc import TOPIC_COMMIT, TOPIC_VERIFY, ZKLIGHTER, logs, utc


def batches(topic: str, lo: int, hi: int) -> dict[int, int]:
    """batch number -> L1 timestamp. Both events carry (batch, size, end block), none indexed."""
    return {int(l["data"][2:66], 16): int(l["blockTimestamp"], 16)
            for l in logs(ZKLIGHTER, [topic], lo, hi) if not l.get("removed")}


def main(lo: int, hi: int, min_gap: int) -> None:
    commits, verifies = batches(TOPIC_COMMIT, lo, hi), batches(TOPIC_VERIFY, lo, hi)
    order = sorted(commits)
    print(f"commits {len(order)} (batches {order[0]}..{order[-1]}), "
          f"{utc(commits[order[0]])} to {utc(commits[order[-1]])}")
    gaps = []
    for prev, cur in zip(order, order[1:]):
        gap = commits[cur] - commits[prev]
        gaps.append(gap)
        if gap >= min_gap:
            print(f"  gap {gap // 3600}h {gap % 3600 // 60:02d}m {gap % 60:02d}s after batch {prev}: "
                  f"{utc(commits[prev])} to {utc(commits[cur])}")
    print(f"median gap between commits {statistics.median(gaps):.0f} s")
    lag = sorted(verifies[b] - commits[b] for b in commits if b in verifies)
    print(f"verified {len(lag)}: median {statistics.median(lag) / 60:.1f} min after commit, "
          f"p95 {lag[int(0.95 * (len(lag) - 1))] / 60:.1f} min, max {lag[-1] / 60:.1f} min")


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 600)
