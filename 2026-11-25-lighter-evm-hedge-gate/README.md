# Can a contract refuse to quote unless the dealer is hedged on Lighter? (2026-11-25)

Lighter opened a public devnet of Lighter EVM on 2026-11-23 (devnet 1.3.0): an EVM rollup beside
Lighter Core, the order book, proven with OpenVM and settled to Ethereum together with Core.
Contracts read Core state synchronously through a precompile (`READ_CORE`) and write to Core
asynchronously ([docs](https://docs.lighter.xyz/evm)). We asked one question: can a contract quote
a price only while the dealer actually holds a hedge on Core, and how fast does it notice when the
hedge goes away?

```
DEALER_KEY=0x... TAKER_KEY=0x... ./run.sh   # two throwaway devnet keys; fund the dealer at the faucet first
python3 -I lag.py                            # 3 min: Core tip vs the Core block the EVM reads
```

## Answer

**Yes, and it noticed in one block.** [`HedgeGate`](src/HedgeGate.sol) reads the dealer's ETH-PERP
position with `READ_CORE` inside the quoting transaction and reverts unless the position covers the
size in the right direction. With the dealer long 0.01 ETH:

| call | result |
|---|---|
| `check(100, long)` (0.01 ETH) | hedged, position 100 |
| `check(101, long)` | not hedged |
| `check(100, short)` | not hedged |
| `quote(100, long)`, a transaction | accepted, 49,061 gas, `Quoted` event records the position read |
| `quote(150, long)` | reverts `NotHedged(100, 150, true)` |

Then the dealer closed its long from Lighter EVM. Core matched the close in Core block 160366; the
first EVM block whose parent Core block is 160366 (EVM 156866) already refuses
([trace](results/gate-trace.txt)). Blocks are about one second on both sides.

**The Core block the EVM reads is at most one block behind.** Over 90 samples two seconds apart, the
parent Core block was the Core tip 64 times and one block behind 26 times, never more
([lag.txt](results/lag.txt)). Each sample takes about 1.1 s to fetch both, so part of the one-block
lag may be our measurement.

## What it does not show

- **Only the moment of the quote.** The gate proves a hedge existed in the Core block the quote read.
  Nothing stops the dealer from closing it one block later. Proving the hedge stays on needs
  something else, such as locking the collateral or a penalty when it is removed.
- **Master accounts only.** `READ_CORE` resolves an address to its master account; a hedge held in a
  subaccount cannot be read.
- **An empty devnet.** All five markets had no orders and no trades when we started. Our two accounts
  made the only fills, and our writes were EVM-to-Core requests 0 to 3 after the reset. Lag under
  load is not measured.
- **The trust is the sequencer's choice of Core block.** The read is of the Core block the sequencer
  pinned for that EVM block, not of anything final on Ethereum. The docs say Core re-orgs carry over
  to the EVM blocks that read them.

## Transactions (Lighter EVM devnet, chain 19529)

| step | tx | EVM block |
|---|---|---|
| dealer deposits 45 USDC to Core | `0x654071eacfc1bbd720c52555d660c8420439b681010ccd4ac7e018d366e532c7` | 156720 |
| taker deposits 45 USDC to Core | `0x73b2602aaf9fc7ee79e91a11ab0ba8f443f22e8b5ff5d6f86a3613210cc54950` | 156724 |
| dealer rests a bid, 0.01 ETH at 1646.96 | `0xa7f650ceb3c220a3c2e67bfed1b157422c4ad96a8379690a8bd149890cb3109e` | 156766 |
| taker sells IOC into it | `0x69c0955b87d075cdc18a50c4b1bf7468517a755b83aac75ad4dafdf15c3c378e` | 156774 |
| gate deployed at `0xeEC872fF39c7Cf986a05C1D53decD94A5aB6588C` | `0xbdec36472ed85fb81517e274df066982fa87509fb53a3a8fc24c92bd7cb4be6d` | 156808 |
| taker rests a bid (to close against) | `0xff0cb44e8f651d2fe3306d0fe34b19fda9088e9fc2a1259fd04b90e97e164813` | 156857 |
| dealer closes, reduce-only IOC | `0xcc8104c0a03302a563577be18bbed07680e18fe26700782d291cfa7d25f1bcf7` | 156865 |

The devnet resets at each release, so these may stop resolving.

## Method

Two throwaway accounts, funded from the devnet faucet, deposited 45 USDC each into Core through
`EvmInteropManager.sendToCore`; the first deposit creates an EVM-controlled Core master account. The
dealer rested a good-til-time bid on ETH-PERP and the taker sold into it with an immediate-or-cancel
order, both sent from Lighter EVM through `EvmToCoreEntrypoint.createOrder`. Positions were read
with `READ_CORE` selector `0x0007` and checked against the Core API's trades. The block-by-block
trace re-runs `check` with `eth_call` at each past block; nodes keep Core state for the parent Core
blocks of about the latest 64 EVM blocks.

Unlike the other studies here, this one signs transactions, on a devnet with test funds only. The
keys are not in this repo.
