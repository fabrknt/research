#!/bin/sh
# Download the encrypted hourly quotes the anthropic-listing-collect workflow saved, decrypt them with the
# private key (kept off GitHub) and unpack them under data/actions/<run id>/. Collection ended 2026-11-21;
# all 97 hours were copied from the workflow artifacts (gone after 90 days) into the release
# anthropic-listing-data-202611 on 2026-11-22, which is kept for good.
#     sh fetch_actions.sh [key.pem]     # default key: ~/.config/fabrknt/research-data-key.pem
set -eu
KEY=${1:-$HOME/.config/fabrknt/research-data-key.pem}
REPO=fabrknt/research
TAG=anthropic-listing-data-202611
cd "$(dirname "$0")"
mkdir -p data/actions
for asset in $(gh release view "$TAG" -R "$REPO" --json assets -q '.assets[].name'); do
  id=${asset%.tar}
  out=data/actions/$id
  [ -d "$out/data" ] && continue
  mkdir -p "$out"
  gh release download "$TAG" -R "$REPO" -p "$asset" -O - | tar xf - -C "$out"
  openssl pkeyutl -decrypt -inkey "$KEY" -pkeyopt rsa_padding_mode:oaep -in "$out/key.bin.enc" -out "$out/key.bin"
  openssl enc -d -aes-256-cbc -pbkdf2 -in "$out/data.tgz.enc" -pass file:"$out/key.bin" | tar xzf - -C "$out"
  rm -f "$out/key.bin"
  echo "run $id: $(cat "$out"/data/quotes-*.jsonl | wc -l) rounds"
done
