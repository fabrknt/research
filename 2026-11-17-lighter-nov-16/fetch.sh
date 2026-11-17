#!/bin/bash
# Fetch Lighter's batch blobs committed to Ethereum between two L1 blocks.
# usage: ./fetch.sh FROM_BLOCK TO_BLOCK OUT_DIR
# writes OUT_DIR/commits.tsv (batch tx l1_block) and OUT_DIR/blob_<batch>.bin
# needs: cast (Foundry), curl, python3
set -euo pipefail

RPC=${RPC:-https://rpc.mevblocker.io} # publicnode has returned empty getLogs without an error
ZKLIGHTER=0x3b4d794a66304f130a4db8f2551b0070dfcf5ca7
FROM=$1 TO=$2 OUT=$3
mkdir -p "$OUT"

TOPIC=$(cast keccak "BatchCommit(uint64,uint32,uint64)")
cast logs --from-block "$FROM" --to-block "$TO" --address $ZKLIGHTER "$TOPIC" --rpc-url "$RPC" --json |
  python3 -c '
import json, sys
for l in json.load(sys.stdin):
    print(int(l["data"][2:66], 16), l["transactionHash"], int(l["blockNumber"], 16))' > "$OUT/commits.tsv"

fetch_one() {
  local batch=$1 tx=$2 f="$OUT/blob_$1.bin" hash url
  [ -s "$f" ] && [ "$(wc -c < "$f")" -eq 131072 ] && return 0
  for _ in 1 2 3; do
    # One blob per commit transaction. Blobscan lists storage references; older blobs list Google
    # first without a URL, so take the first reference that has one (IPFS).
    hash=$(cast tx "$tx" --rpc-url "$RPC" --json |
      python3 -c 'import json,sys; print(json.load(sys.stdin)["blobVersionedHashes"][0])') || true
    url=$(curl -s -m 30 "https://api.blobscan.com/blobs/$hash" |
      python3 -c 'import json,sys; print(next(r["url"] for r in json.load(sys.stdin)["dataStorageReferences"] if r.get("url")))') || true
    if [ -n "${url:-}" ] && curl -s -m 60 -L -o "$f" "$url" && [ "$(wc -c < "$f")" -eq 131072 ]; then
      return 0
    fi
    sleep 2
  done
  rm -f "$f" # an error page saved in its place would pass for a blob next time
  echo "failed: batch $batch" >&2
}
export -f fetch_one
export RPC OUT

# Blobscan rate-limits; 2 at a time finishes 200 blobs in a few minutes.
awk '{print $1, $2}' "$OUT/commits.tsv" | xargs -P 2 -n 2 bash -c 'fetch_one "$0" "$1"'
echo "$(wc -l < "$OUT/commits.tsv") commits, $(ls "$OUT"/blob_*.bin 2>/dev/null | wc -l) blobs in $OUT"
