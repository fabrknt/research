# Lighter's full state, replayed from Ethereum blobs (from 2026-11-18)

Carry Lighter's state forward from its published batch-166859 snapshot (2026-05-02) to today, applying
each batch's blob in order, so that today's state root can be recomputed and any account's leaf proved
against it without Lighter's API. Builds on [2026-11-17-lighter-nov-16](../2026-11-17-lighter-nov-16/),
whose decoder and state-root code it reuses.

- `replay_state.py`: snapshot export or a saved state in; applies the next batches for N minutes; state out.
  Blobs come from Blobscan (2 at a time, about 30 batches a minute); missing ones are fetched again up to
  three times, slower, and a failed RPC call keeps what was applied so the next run resumes from it.
- `roots.py`: the state root and validium root committed for the batch a state file stopped at (or any
  batch), to check the state with `../2026-11-17-lighter-nov-16/stateroot`.
- `.github/workflows/lighter-state-replay.yml`: runs it on GitHub's machines, an hour per job, each job
  resuming from the last good state and starting the next (10 minutes later after a failure, since
  GitHub's schedule fires hours late and is no fallback). About 100,000 batches to catch up (about 55
  hours). The state is seeded from a BUSL-1.1 file, so it is kept as an encrypted artifact and not
  published.

## Check so far

2026-11-18: replayed locally and hashed with the old layout (`../2026-11-17-lighter-nov-16/stateroot`,
about 10 min each). Both are the roots committed for those batches (`newStateRoot`, word 19 of
`commitBatch`'s calldata; `newValidiumRoot` is word 20, read with `roots.py`):

```
batch 167059  accounts 878443  0x0b747f77da1efd80ee42bae59c398cdcac32b0f5341a8510d1f4d3d96253b09b match=true
batch 167259  accounts 878787  0x2783abf9346315aa395ed6626018ced5f79432359b2f608a64eac4fad3642f87 match=true
```

Check a saved state the same way:

```sh
cd ../2026-11-17-lighter-nov-16/stateroot
go run ./cmd/snapshotroot state.jsonl.gz $(python3 ../../2026-11-18-lighter-state-replay/roots.py state.jsonl.gz | cut -d' ' -f1,2)
```

On GitHub: the first hour-long job replayed 1,600 batches (167335 to 168935) in 53 min.

## Open

- Since 2026-09-20 (batch 236132) the state root also hashes in a market data tree, and each account
  leaf carries the root of its binary options positions. Both trees are now read and written
  (`-layout 2026-09` in the stateroot README); they are checked once the replay passes 236132.
- 7 state-root replacements happened after the snapshot (179913 to 257643). If any changed account
  state that is not in the blobs, the replayed root will stop matching there.

Measured with an AI (Claude), which wrote the scripts and ran them. Not financial advice.
