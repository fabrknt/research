# Lighter's full state, replayed from Ethereum blobs (from 2026-11-18)

Carry Lighter's state forward from its published batch-166859 snapshot (2026-05-02) to today, applying
each batch's blob in order, so that today's state root can be recomputed and any account's leaf proved
against it without Lighter's API. Builds on [2026-11-17-lighter-nov-16](../2026-11-17-lighter-nov-16/),
whose decoder and state-root code it reuses.

- `replay_state.py`: snapshot export or a saved state in; applies the next batches for N minutes; state out.
  Blobs come from Blobscan (2 at a time, about 33 batches a minute).
- `.github/workflows/lighter-state-replay.yml`: runs it on GitHub's machines, an hour per job, each job
  resuming from the last one's state. About 100,000 batches to catch up (about 52 hours). The state is
  seeded from a BUSL-1.1 file, so it is kept as an encrypted artifact and not published.

## Check so far

2026-11-18: replayed 200 batches locally (166860 to 167059, 6 min), then hashed the result with the
old layout (`../2026-11-17-lighter-nov-16/stateroot`, 9 min 43 s). It is the root committed for batch
167059 (`newStateRoot`, word 19 of `commitBatch`'s calldata; `newValidiumRoot` is word 20):

```
accounts 878443
elements in order, each little-endian    0x0b747f77da1efd80ee42bae59c398cdcac32b0f5341a8510d1f4d3d96253b09b match=true
on-chain state root                      0x0b747f77da1efd80ee42bae59c398cdcac32b0f5341a8510d1f4d3d96253b09b
```

## Open

- Since 2026-09-20 (batch 236132) the state root is `H(account root, market details hash, market data
  tree root, validium root)`, and each account leaf carries the root of its binary options positions.
  The blob schema says each market delta carries the slot's full state, so both trees should be
  rebuildable from the replayed state; the tree shapes are still to be read.
- 7 state-root replacements happened after the snapshot (179913 to 257643). If any changed account
  state that is not in the blobs, the replayed root will stop matching there.

Measured with an AI (Claude), which wrote the scripts and ran them. Not financial advice.
