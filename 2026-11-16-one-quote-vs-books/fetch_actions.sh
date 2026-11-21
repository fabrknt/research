#!/bin/sh
# Download the encrypted hourly snapshots the one-quote-collect workflow saved, decrypt them with the
# private key (kept off GitHub) and unpack them under data/actions/<run id>/. Hours come from the monthly
# releases (one-quote-data-YYYYMM, kept for good) and, for runs from before those existed, from the
# workflow artifacts (gone after 90 days).
#     sh fetch_actions.sh [key.pem]     # default key: ~/.config/fabrknt/research-data-key.pem
set -eu
KEY=${1:-$HOME/.config/fabrknt/research-data-key.pem}
REPO=fabrknt/research
cd "$(dirname "$0")"
mkdir -p data/actions

unpack() {  # $1 = run id; data.tgz.enc and key.bin.enc are under data/actions/$1
  out=data/actions/$1
  enc=$(find "$out" -name data.tgz.enc | head -1)
  dir=$(dirname "$enc")
  openssl pkeyutl -decrypt -inkey "$KEY" -pkeyopt rsa_padding_mode:oaep -in "$dir/key.bin.enc" -out "$dir/key.bin"
  openssl enc -d -aes-256-cbc -pbkdf2 -in "$enc" -pass file:"$dir/key.bin" | tar xzf - -C "$out"
  rm -f "$dir/key.bin"
  echo "run $1: $(cat "$out"/data/snap-*.jsonl | wc -l) market-rounds"
}

for tag in $(gh release list -R "$REPO" -L 200 --json tagName -q '.[].tagName | select(startswith("one-quote-data-"))'); do
  for asset in $(gh release view "$tag" -R "$REPO" --json assets -q '.assets[].name'); do
    id=${asset%.tar}
    [ -d "data/actions/$id/data" ] && continue
    mkdir -p "data/actions/$id"
    gh release download "$tag" -R "$REPO" -p "$asset" -O - | tar xf - -C "data/actions/$id"
    unpack "$id"
  done
done

for id in $(gh run list -R "$REPO" -w one-quote-collect -s success -L 500 --json databaseId -q '.[].databaseId'); do
  [ -d "data/actions/$id/data" ] && continue
  mkdir -p "data/actions/$id"
  gh run download "$id" -R "$REPO" -D "data/actions/$id" >/dev/null 2>&1 || { echo "no artifact: $id"; continue; }
  unpack "$id"
done
