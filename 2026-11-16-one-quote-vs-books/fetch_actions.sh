#!/bin/sh
# Download the encrypted hourly snapshots the one-quote-collect workflow saved, decrypt them with the
# private key (kept off GitHub) and unpack them under data/actions/<run id>/.
#     sh fetch_actions.sh [key.pem]     # default key: ~/.config/fabrknt/research-data-key.pem
set -eu
KEY=${1:-$HOME/.config/fabrknt/research-data-key.pem}
cd "$(dirname "$0")"
mkdir -p data/actions
for id in $(gh run list -R fabrknt/research -w one-quote-collect -s success -L 500 --json databaseId -q '.[].databaseId'); do
  out=data/actions/$id
  [ -d "$out/data" ] && continue
  mkdir -p "$out"
  gh run download "$id" -R fabrknt/research -D "$out" >/dev/null 2>&1 || { echo "no artifact: $id"; continue; }
  enc=$(find "$out" -name data.tgz.enc | head -1)
  dir=$(dirname "$enc")
  openssl pkeyutl -decrypt -inkey "$KEY" -pkeyopt rsa_padding_mode:oaep -in "$dir/key.bin.enc" -out "$dir/key.bin"
  openssl enc -d -aes-256-cbc -pbkdf2 -in "$enc" -pass file:"$dir/key.bin" | tar xzf - -C "$out"
  rm -f "$dir/key.bin"
  echo "run $id: $(cat "$out"/data/snap-*.jsonl | wc -l) market-rounds"
done
