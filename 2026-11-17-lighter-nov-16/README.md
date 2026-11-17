# What Ethereum shows about Lighter's November 16 (2026-11-17)

On 2026-11-16 two market-maker accounts on Lighter lost funds through leaked API keys. Lighter's
post-mortem ("Signing Safely on Lighter: Lessons from November 16") gives the cause: the accounts'
own signing code reused nonces, so the keys could be computed from public signatures. The protocol,
contracts and infrastructure were not affected.

This study does not repeat that. It asks what anyone can check from Ethereum alone: Lighter posts
every batch's account changes to Ethereum as a blob, commits a state root, and pays withdrawals out
of one contract (ZkLighter, `0x3b4d…5ca7`).

## Answer

1. **The pool route is in the blobs, and the first drain adds up to the cent.** For each account a
   public pool was created under the victim's own L1 address, an outside account (769455) put in
   9,999 USDC for 9,999,000 of its 10,000,000 shares, USDC went into the pool, and 769455 redeemed.
   Blobs carry each account's net change per batch, so the order of steps inside a batch does not
   show. In batch 269191 account 714710 (−7,382,824.88), the pool (−3,010,001.00) and 769455
   (−230.91) together lose 10,393,056.79 USDC, and 17 minutes later ZkLighter paid 10,393,056.79 USDC
   to 769455's address.
2. **The second drain left Lighter, but not to the attacker.** In batches 269212–269214 the same route
   moved 5,086,386.02 USDC from account 714723 to 769455, and 769455's whole balance, 5,096,588.02
   USDC, left Lighter. ZkLighter paid exactly that amount at 18:03:35 UTC to `0xb326…0a07`, not to
   769455's address, which has received nothing from ZkLighter since the first payout. `0xb326…0a07`
   passed 5,096,628.02 USDC on four minutes later and opened its own Lighter account (769566) at
   20:42. Lighter says about 5M USDC was returned; who holds `0xb326…0a07` is not visible on chain.
3. **Lighter stopped posting batches to Ethereum for 7 h 22 min**, from 10:32:11 to 17:54:11 UTC,
   right after the batch in which account 714723's positions were closed, and the second drain is in
   the first three batches after the pause. Batches are otherwise posted a median 84 s apart; there
   was also a 2 h 28 min pause the day before. The post-mortem mentions a Guardian pausing
   withdrawals, not the posting pause. That the pause was how the second drain was held back is our
   reading, not something Lighter has said.
4. **What Ethereum proves is minutes old, and can be hours old.** A posted batch is verified by a
   proof a median 14.2 min later (p95 19.8 min, 2026-11-15 to 11-17). Batches posted just before the
   pause waited up to 456.6 min.

## Timeline (2026-11-16, UTC, Ethereum block times)

| time | batch | in the blob / on Ethereum |
|---|---|---|
| 09:47:23 | 269187 | account 714723: USDC −2,397,901.81 |
| 09:49:23 | 269188 | new public pool 281474976415757 with L1 address `0x0d1d…8f6f` (account 714710's); 769455 puts in 9,999 USDC for 9,999,000 shares |
| 09:51:11 | 269189 | account 714710 closes positions in 9 markets: USDC −11,680,420.91; all accounts in the batch +8,514.06 |
| 09:53:11 | 269190 | account 714710: USDC −3,704,456.44; pool 281474976415757: +3,000,001.00 |
| 09:54:35 | 269191 | 714710 −7,382,824.88; 769455 redeems its 9,999,000 shares; pool −3,010,001.00; all accounts −10,393,208.69 |
| 10:10:11 | (L1) | ZkLighter pays 2,397,901.81 USDC to `0x66cf…2068` (account 714723's own address) |
| 10:11:47 | (L1) | ZkLighter pays 10,393,056.79 USDC to `0xb3ff…e387` (account 769455's address) |
| 10:32:11 | 269211 | account 714723 closes positions in 8 markets. Last batch posted for 7 h 22 min |
| 17:54:11 | 269212 | new public pool 281474976415701 with L1 address `0x66cf…2068` (account 714723's); 769455 puts in 9,999 USDC for 9,999,000 shares |
| 17:54:35 | 269213 | 714723 −5,086,386.02; 769455 redeems, +5,096,387.02; all accounts +64.66 |
| 17:54:59 | 269214 | 769455 −5,096,588.02; all accounts −5,072,780.21 |
| 18:03:35 | (L1) | ZkLighter pays 5,096,588.02 USDC to `0xb326…0a07` |
| to 11-17 07:50 | (L1) | nothing more from ZkLighter to `0xb3ff…e387` |

Trades only move USDC between Lighter accounts, so a batch's total over all accounts is near zero
unless USDC leaves. The victims' large losses in 269189 and 269190 went to other accounts (the batch
totals are +8,514.06 and −127,324.60); they are not counted here as stolen. What left Lighter is read
from ZkLighter's USDC payouts.

## Can the blobs be trusted?

Checked, from Ethereum data and Lighter's published snapshot:

- **Decoding**: blobs decoded from Lighter's published schema rebuild account positions that match
  Lighter's API, market by market (29 of 29 accounts compared, 2026-11-16; 36 of 36 accounts with
  open positions in the snapshot, 2026-11-17).
- **State root**: Lighter's published snapshot of all 877,921 accounts at batch 166859
  (2026-05-02) hashes, with Lighter's Apache-2.0 Poseidon2, to exactly the state root Lighter
  committed on Ethereum for that batch.
- **Root replacements**: Lighter replaced its state root 19 times. The 6 in 2025 (to 2025-09-29) had
  no proof; the 13 since 2025-11-02, including all 7 after the snapshot, each passed a SNARK verifier
  (read with `debug_traceTransaction`).

Not checked: what circuit each of those verifiers checks; the validium root (state not in blobs,
such as order books), which is taken as given; the state-root layout used since 2026-09-20, which
adds a market data tree.

## Run

Needs Python 3.10+, `cast` (Foundry) and `curl` for `fetch.sh`, and Go 1.23 for `stateroot/`. No API
keys. Public RPC by default (`rpc.mevblocker.io`; set `RPC` to change it).

```sh
# the 29 batches from 09:47 to 17:55 UTC (Blobscan rate-limits; run again to fill any that failed)
./fetch.sh 26426780 26429220 /tmp/lighter-nov16

python3 trace.py /tmp/lighter-nov16 714710 714723 769455
python3 transfers.py 26426780 0xb3fffca23d4444eE73349825ACD84f7b5020e387 \
  0x66cf2f85115cc20bf439720927c1f93de9672068 0xb32653392752dc8348b498346984ae9934de0a07
python3 gaps.py 26419000 26432000
```

Output on 2026-11-17 (trace, abridged to the lines in the timeline):

```
269188 2026-11-16 09:49:23 account 769455, USDC -9,999.00, shares {281474976415757: 9999000}
269188 2026-11-16 09:49:23 account 281474976415757, USDC +10,000.00, pool_info {'total_shares': 10000000, 'operator_shares': 1000}, l1 0x0d1d09312665d31ed68231b88079a245e0458f6f
269191 2026-11-16 09:54:35 account 714710, USDC -7,382,824.88
269191 2026-11-16 09:54:35 account 769455, USDC -230.91, shares {281474976415757: -9999000}
269191 2026-11-16 09:54:35 account 281474976415757, USDC -3,010,001.00, pool_info {'total_shares': -10000000, 'operator_shares': -1000}
269191 2026-11-16 09:54:35 all 921 accounts in the batch: USDC -10,393,208.69
269212 2026-11-16 17:54:11 account 281474976415701, USDC +10,001.00, pool_info {'total_shares': 10000000, 'operator_shares': 1000}, l1 0x66cf2f85115cc20bf439720927c1f93de9672068
269213 2026-11-16 17:54:35 account 714723, USDC -5,086,386.02
269213 2026-11-16 17:54:35 account 769455, USDC +5,096,387.02, shares {281474976415701: -9999000}
269214 2026-11-16 17:54:59 account 769455, USDC -5,096,588.02
```

```
to 0xb3fffca23d4444eE73349825ACD84f7b5020e387: 1 transfers
  block 26426910 2026-11-16 10:11:47 10,393,056.79 USDC tx 0x5b6f27ded0e9a66ef6fa107083e28db9914e46d7635cc5112d760b9cb2f958c9
to 0x66cf2f85115cc20bf439720927c1f93de9672068: 1 transfers
  block 26426902 2026-11-16 10:10:11 2,397,901.81 USDC tx 0x871e0a8f1b73c5b872d7a450336ade76ead80714e4d257f0ba2a67dff9911d6d
to 0xb32653392752dc8348b498346984ae9934de0a07: 3 transfers
  block 26429260 2026-11-16 18:03:35 5,096,588.02 USDC tx 0xcafa5c2b2e27f278f2bd1e9765a741747bcb4f54e79803074c31dd845ef0a404
  block 26430166 2026-11-16 21:05:11 10.00 USDC tx 0x13b9b79c5a322cb60c9b73ba924a01ce65cfe958eefee7bdde227d0f3cbec91a
  block 26430395 2026-11-16 21:51:11 134,198.31 USDC tx 0x35173f261ff4e625d024a2dbd798b31ad51f757a25f28f925248e538bfb5ea62
```

```
commits 1432 (batches 268368..269799), 2026-11-15 07:47:23 to 2026-11-17 03:12:11
  gap 2h 28m 36s after batch 268483: 2026-11-15 11:06:23 to 2026-11-15 13:34:59
  gap 7h 22m 00s after batch 269211: 2026-11-16 10:32:11 to 2026-11-16 17:54:11
  gap 0h 49m 48s after batch 269444: 2026-11-16 19:49:35 to 2026-11-16 20:39:23
median gap between commits 84 s
verified 1426: median 14.2 min after commit, p95 19.8 min, max 456.6 min
```

The state root, from Lighter's snapshot (`desertexit/blobs.zip` in elliottech/lighter-prover at
2bbc3089, unzipped):

```sh
python3 stateroot/export_snapshot.py SNAPSHOT_DIR /tmp/accounts.jsonl      # 26 s, 242 MB
cd stateroot && go run ./cmd/snapshotroot /tmp/accounts.jsonl \
  0x43af97459fc0ea7420c4039201a9f36a8d3e2ca30a5d10300070bc9d5c46de4e \
  0x867d1b1d60f530c3ea8f5ea921763ead3f1d105ae91554dcbc879054903fe6de       # about 10 min
```

```
accounts 877921
elements in order, each little-endian    0x43af97459fc0ea7420c4039201a9f36a8d3e2ca30a5d10300070bc9d5c46de4e match=true
on-chain state root                      0x43af97459fc0ea7420c4039201a9f36a8d3e2ca30a5d10300070bc9d5c46de4e
```

The two values are `newStateRoot` and `newValidiumRoot` of `commitBatch` for batch 166859 (tx
0xcf54c5a2…e782, block 25007824). How the root is built is in [stateroot/README.md](stateroot/README.md).

Checks against Lighter's API (live state, so a later run compares fewer accounts):

```sh
python3 replay.py /tmp/lighter-blobs /tmp/lighter-blobs/commits.tsv 1794824520   # after ./fetch.sh 26425212 26427012 /tmp/lighter-blobs
python3 check_snapshot.py SNAPSHOT_DIR 1794824520
```

## Files

- `decode.py`: one blob → mark prices and per-account deltas (positions, assets, pool shares).
  Written from `desertexit/README.md` in elliottech/lighter-prover; none of its code is copied
  (BUSL-1.1).
- `fetch.sh`: `BatchCommit` events on ZkLighter → each batch's blob from Blobscan.
- `trace.py`, `transfers.py`, `gaps.py`, `rpc.py`: the incident, ZkLighter's USDC payouts, posting
  pauses and proof delay.
- `replay.py`, `check_snapshot.py`: decoded positions against Lighter's API.
- `stateroot/`: the snapshot hashed into the committed state root, with
  `github.com/elliottech/poseidon_crypto` v0.0.19 (Apache-2.0).

Addresses are shortened in the text and given in full where they are inputs to the scripts; all are
public on Ethereum. Account numbers are Lighter's. Blobs and the snapshot are not committed: the
scripts fetch them again.

Measured with an AI (Claude), which wrote the scripts and ran them; every number here is a line of
their output. Not financial or security advice.
