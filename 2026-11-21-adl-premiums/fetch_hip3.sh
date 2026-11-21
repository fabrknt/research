#!/bin/bash
# For hip3.py: the HIP-3 fills in each hourly node_fills_by_block file that has a HIP-3 ADL, and in the
# hour after when the ADL is in the last 10 minutes. About 145 files, ~5 GB streamed (requester-pays,
# about $0.45 of transfer from outside ap-northeast-1). Resumable.
#     ./fetch_hip3.sh all_adl.csv OUT_DIR
set -euo pipefail
ADL=$1; OUT=$2
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT"
python3 -I - "$ADL" > "$OUT/hours.txt" <<'PY'
import csv, sys, datetime as dt
hrs = set()
for r in csv.reader(open(sys.argv[1])):
    if ":" in r[2]:
        t = dt.datetime.fromtimestamp(int(r[0]) / 1000, dt.timezone.utc)
        for m in (0, 10):
            hrs.add((t + dt.timedelta(minutes=m)).strftime("%Y%m%d/%-H"))
print("\n".join(sorted(hrs)))
PY
one() {
  out=$OUT/$(echo "$1" | tr '/' '_').csv
  [ -f "$out" ] && return 0
  ( set -o pipefail
    aws s3 cp "s3://hl-mainnet-node-data/node_fills_by_block/hourly/$1.lz4" - --request-payer requester --only-show-errors \
      | lz4 -dc | python3 -I "$HERE/hip3_fills.py" > "$out.tmp" ) && mv "$out.tmp" "$out" || { rm -f "$out.tmp"; echo "FAIL $1"; return 1; }
}
export -f one; export OUT HERE
xargs -P 6 -I{} bash -c 'one {}' < "$OUT/hours.txt"
echo "$(ls "$OUT"/*.csv | wc -l) of $(wc -l < "$OUT/hours.txt") hours"
