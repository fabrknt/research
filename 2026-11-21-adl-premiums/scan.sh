#!/bin/bash
# Stream every hourly fills file through lz4 + grep, keep only ADL fills. Resumable.
# Needs AWS credentials (the bucket is requester-pays). Run it on an EC2 instance in
# ap-northeast-1, where the bucket is, so the ~385 GB never leaves the region.
[ -f ~/creds.env ] && source ~/creds.env
mkdir -p ~/out
one() {  # $1 = prefix/day/hour.lz4
  out=~/out/$(echo "$1" | tr '/' '_').csv
  [ -f "$out" ] && return
  # pipefail: a failed download must not pass as an hour with no ADL (grep's 1 = no match)
  ( set -o pipefail
    aws s3 cp "s3://hl-mainnet-node-data/$1" - --request-payer requester --only-show-errors \
      | lz4 -dc | { grep -F 'Auto-Deleveraging' || [ $? -eq 1 ]; } | python3 ~/extract.py > "$out.tmp" ) \
    && mv "$out.tmp" "$out" || echo "FAIL $1" >> ~/fail.log
}
export -f one
rm -f ~/DONE ~/fail.log
set -o pipefail
: > ~/keys.txt
for p in node_fills/hourly node_fills_by_block/hourly; do
  aws s3 ls "s3://hl-mainnet-node-data/$p/" --recursive --request-payer requester \
    | awk '{print $4}' | grep '\.lz4$' >> ~/keys.txt || { echo "listing $p failed"; exit 1; }
done
wc -l ~/keys.txt
xargs -P 8 -I{} bash -c 'one {}' < ~/keys.txt
# DONE only when every listed key has its output and nothing failed
missing=0
while read -r k; do [ -f ~/out/$(echo "$k" | tr '/' '_').csv ] || missing=$((missing + 1)); done < ~/keys.txt
echo "missing $missing"
[ ! -s ~/fail.log ] && [ "$missing" -eq 0 ] && echo finished > ~/DONE
