#!/usr/bin/env bash
# Builds and checks one crate of intrinsic-technologies/rustcrypto-fv, as its README says.
# Needs elan (Lean) and a GitHub SSH key (Lake fetches lean-x86 and lean-x86-proofs over SSH).
# Usage: ./run.sh [Crate] [workdir]   e.g. ./run.sh Sha2 ~/src/_ext
set -euo pipefail
crate=${1:-Sha2}
work=${2:-$PWD/.work}
rev=8aa4609   # the commit measured on 2026-11-25
here=$(cd "$(dirname "$0")" && pwd)

mkdir -p "$work" && cd "$work"
[[ -d rustcrypto-fv ]] || git clone https://github.com/intrinsic-technologies/rustcrypto-fv.git
cd rustcrypto-fv && git checkout --quiet "$rev"

# caffeinate keeps a Mac awake: a lid-closed sleep stalled the first run for about 2 hours.
keepawake() { if command -v caffeinate >/dev/null; then caffeinate -i -s "$@"; else "$@"; fi; }

(cd "$crate" && { time keepawake lake build "$crate.Statements"; } ) 2>&1 | tee "$here/statements.log"
(cd "$crate" && { time keepawake lake build "$crate.Proofs"; } ) 2>&1 | tee "$here/proofs.log"
{ time keepawake scripts/comparator-local.sh "$crate"; } 2>&1 | grep -v '^Exporting' | tee "$here/comparator.log"
