# stateroot

Hash Lighter's published state into the state root Lighter committed on Ethereum, using only the
snapshot, the root's public inputs and Lighter's Apache-2.0 Poseidon2.

## Result (2026-11-17)

Lighter's batch-166859 snapshot (`desertexit/blobs.zip` in elliottech/lighter-prover 2bbc3089,
877,921 accounts) hashes to the state root committed for that batch:

```
account root        [8802015731705575273 5234796338736931719 15253987720197531101 2988705207643944001]
market details hash [12616800868909723380 5790140001069857984 10400615335195120189 1984489033210800512]
computed            0x43af97459fc0ea7420c4039201a9f36a8d3e2ca30a5d10300070bc9d5c46de4e
on-chain            0x43af97459fc0ea7420c4039201a9f36a8d3e2ca30a5d10300070bc9d5c46de4e
```

The on-chain values come from `commitBatch` in tx 0xcf54c5a2…e782 (Ethereum block 25007824,
2026-05-02 14:16:35 UTC): `newStateRoot` 0x43af…de4e, `newValidiumRoot` 0x867d…e6de.

What this shows: every account's positions, assets, pool shares and address in the snapshot, and
every market's mark price, funding prefix sum and quote multiplier, are exactly what Lighter
committed to Ethereum at batch 166859. The validium root is taken as given: it covers state that is
not in the snapshot or the blobs (order books and the like), so it is checked only as one of the three
inputs that must produce the committed root.

## How the root is built (batch 166859)

Read from lighter-prover at 2bbc3089 (BUSL-1.1) and re-written here; none of its code is copied.

- `state root = H2(H2(account root, market details hash), validium root)`, `H2` = Poseidon2 two-to-one.
- Account tree: 48 levels, leaf at the account index, bit i of the index picks the side at level i,
  empty subtrees hash up from the zero hash.
- Account leaf, three nested Poseidon2 sponge hashes (no padding):
  1. 256 position slots (255 markets and one always-empty) in 16 buckets of 16; each slot is the
     funding prefix sum then the position, each as four 16-bit little-endian limbs of the absolute
     value followed by a sign element (-1, 0, 1).
  2. `partial = H(16 bucket hashes, 16 (pool index, shares) pairs sorted by pool index and padded
     with zeros, total shares, operator shares)`.
  3. `leaf = H(partial, address as five 32-bit little-endian limbs, account type, asset root)`; the
     asset root is a 6-level tree over 64 slots, each non-zero slot `H(sign, three 32-bit limbs)`.
- Market details hash: for each of 255 markets, four 16-bit limbs of |funding prefix sum|, its sign,
  mark price, quote multiplier; one sponge hash over all of them.
- bytes32 on Ethereum = the four field elements in order, each 8 bytes little-endian (the other
  three packings tried do not match).

Poseidon2: `github.com/elliottech/poseidon_crypto` v0.0.19, `hash/poseidon2_goldilocks`
(Apache-2.0). Both of its Poseidon2 packages reproduce the empty-tree constants in the prover
(`cmd/variant`).

## The layout since binary options (`-layout 2026-09`)

Read from lighter-prover at fa85b33 (2026-11-02), the same way. Since 28ae613d (2026-09-20):

- `state root = H2(H2(H2(account root, market details hash), market data tree root), validium root)`
  (`verify_state_root` in `desertexit/circuits/src/inner_circuit.rs`).
- Account leaf: the root of the account's binary options positions goes between the account type and
  the asset root. That tree has 12 levels keyed by market slot (binary options use slots 1000 to
  2000); a leaf is `H(2, |size| as four 16-bit limbs, sign)`, a negative size being a NO position. An
  account with none has the prover's `EMPTY_MARKET_DATA_TREE_ROOT`, which the program recomputes
  and checks before hashing anything.
- Market data tree: 12 levels keyed by market slot; a leaf is `H(2, status, price, settlement cap,
  quote extension multiplier)`, or the zero hash when all four are zero (every perp and spot slot).
  Each blob's market delta carries a slot's full state, so the last one per slot is its leaf.
- The market details hash went into 16 buckets of 16 (255 markets and one empty), then one hash of
  the bucket hashes, in 38bea38 (2026-09-07). Which batch that took effect from is not checked, so
  the program tries both forms in either layout.

None of this is checked against a committed root yet: it needs the replayed state past batch 236132
([2026-11-18-lighter-state-replay](../../2026-11-18-lighter-state-replay/)).

## Run

```sh
python3 export_snapshot.py SNAPSHOT_DIR accounts.jsonl     # blobs.zip unzipped; 26 s, 242 MB
go run ./cmd/snapshotroot accounts.jsonl \
  0x43af97459fc0ea7420c4039201a9f36a8d3e2ca30a5d10300070bc9d5c46de4e \
  0x867d1b1d60f530c3ea8f5ea921763ead3f1d105ae91554dcbc879054903fe6de
go run ./cmd/variant                                       # which Poseidon2 package matches

# a state saved by replay_state.py, against the roots committed for its batch
go run ./cmd/snapshotroot [-layout 2026-09] state.jsonl.gz $(python3 ../../2026-11-18-lighter-state-replay/roots.py state.jsonl.gz | cut -d' ' -f1,2)
```

On an M-series laptop: 12 min 13 s for the first version, 9 min 41 s with empty position buckets and
empty asset subtrees reused (same root). One Poseidon2 two-to-one takes about 9 µs here.

## Not covered

- The root format changed after this batch: `StateRootUpdate` was emitted at 19 batches between
  2025-03 and 2026-11, 7 of them after 166859 (179913, 209596, 211824, 219572, 232672, 236132,
  257643). Since the binary-options change (prover 28ae613d, 2026-09-20) a market data tree is
  part of the root (`inner_circuit.rs` at HEAD). Checking a later root needs that layout.
- State-root replacements (traced on 2026-11-17 with `debug_traceTransaction` on eth.drpc.org):
  - The first 6 (batches 2693 to 51313, 2025-03-25 to 2025-09-29) called an older function
    (selector `0x31075b17`) and **no verifier**: the operator replaced the root without a proof.
  - The 13 since (batches 68289 to 257643, 2025-11-02 to 2026-11-01, selector `0x7271277e`) each
    called `Verify(bytes,uint256[])` on a different, freshly set verifier contract, which returned true.
    The verifiers are 7,051 to 7,162 bytes, all with different bytecode (different verifying keys) and
    calling the pairing precompile, which is what a SNARK verifier looks like. What circuit each one
    verifies, and who chose it, has not been checked: the verifier is set by a contract upgrade.
  - So from batch 166859 on, every root change was checked by a proof; before 2025-11, six were not.
    Starting from the batch-166859 snapshot avoids depending on those six.
