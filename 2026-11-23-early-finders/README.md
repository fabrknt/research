# Do the wallets that found Hyperliquid early also find the next winner? (2026-11-23)

The idea: people who found Hyperliquid, Lighter or Variational early should be likely to find the next
strong protocol, so their wallets could be followed. Checked in two steps.

1. Pick the cohort from Hyperliquid data only.
2. Ask whether it was early at the later winners.
3. Ask the question that decides whether the idea is usable: when the cohort piles into a new protocol, does
   that protocol succeed more often than others?

**Answer: no lift was shown.** The cohort is early at many new protocols, so it is also early at the
winners. But protocols it piled into succeeded about as often as the base rate. The difference is not
significant, and the interval is wide (9–39%), so a small edge is not ruled out; a usable one was not found.

## Cohort

- Wallets whose first deposit of $100 or more into Hyperliquid's Arbitrum bridge came before its points
  program began on 2023-11-01: 6,385 wallets.
- Deposits went to the first bridge `0xc67e9efd…73a4` (USDC.e, Feb 2023 to Jan 2024).
  Bridge2 `0x2Df1c51E…3dF7` went live on 2023-12-02.
- The $100 floor removed 7,478 wallets (54%).
- The wallet lists are not committed; the scripts rebuild them from public logs. Numbers not in the
  printed outputs (the dust filter, the samples, the base rate, unidentified contracts) are in
  [`results/notes.md`](results/notes.md), the full working notes.

## Step 1: early at Lighter and Variational

| Group | n | At Lighter before its public launch (2025-10-02) | At Variational before points began (2025-12-17) |
|---|---|---|---|
| Early Hyperliquid (before 2023-11) | 2,000 sampled | 11.2% [9.9–12.7] | 8.1% [7.0–9.4] |
| Hyperliquid points season 1 (2023-11 to 2024-04) | 600 | 6.8% | 3.7% |
| Late Hyperliquid (first activity in H1 2025) | 614 | 4.1% [2.8–5.9] | 1.8% [1.0–3.2] |
| Arbitrum wallets active in Oct 2023, never on Hyperliquid | 690 | 0.3% | 0.3% |

- Early vs late: 2.75× at Lighter (1.84–4.12) and 4.5× at Variational (2.5–8.3).
- At Lighter before June 2025 the gap is 5.3% vs 0.8%.
- The lift holds after dropping wallets flagged as airdrop farmers and when restricted to EOAs.
- It is weaker among first deposits of $1k or more (10.3% vs 6.7%).
- 89% of the early cohort did not find Lighter early.

How each was measured:

- **Lighter** (`0x3B4D794a…5ca7`, Ethereum): dates come from each wallet's Lighter account index via
  Lighter's API, mapped to time with deposit events (to about 4 days). Free Ethereum RPCs refuse old log ranges.
- **Variational** (factory `0x0F820B9a…074C`, Arbitrum): one pool per user, so it was read from pool
  creation events, for all 6,385 wallets.

## Step 2: do the cohort's pile-ins succeed?

The success rule was written before any candidate or outcome was looked at:
[`results/PREREGISTERED_RULE.txt`](results/PREREGISTERED_RULE.txt). Shell quoting dropped the "$50" and "$1"
from that file. As set at the time, success means a DefiLlama TVL peak of $50M or more, and still $1M or more
in Nov 2026.

How it was measured:

- Every outgoing USDC, USDC.e, USDT0 and WETH transfer from 1,500 wallets sampled from the cohort after
  dropping flagged farmers (6,064 left), on Arbitrum (2023-11 to 2025-02), read from public RPC logs.
- Recipients kept: contracts other than routers, pools, bridges, tokens and exchange deposit addresses.
- A protocol counts as "piled into" when 5 or more sampled wallets arrived within 60 days of a contract's
  start (its deployment, or its first own log when the deployment was not found). For a protocol with
  several contracts, the contract with the most early wallets counts; wallets are not summed across them.
  New protocols are limited to 2023-11 to 2024-12, so outcomes had time to show.

| Group | Succeeded | 95% interval |
|---|---|---|
| New protocols the cohort piled into | 5 / 25 = 20% | 9–39% |
| New protocols the cohort touched, fewer than 5 early | 3 / 50 = 6% | 2–16% |
| All DefiLlama Arbitrum protocols listed 2023-11 to 2024-12 | 30 / 215 = 14% | |

- Against the base rate: p = 0.38. Against the cohort's other new protocols: p = 0.11.
The next two points use all 31 pile-ins, including new contracts of older protocols (Compound V3,
Radiant and others): 6 succeeded, 25 failed.

- **A higher cohort share did not mean success.** Among the first 500 token senders to the contract
  within its first 60 days (fewer where fewer came), the median
  cohort share was 0.5% for successes and 1.0% for failures. Cega (3.6%) and nftperp (3.0%) had the highest
  shares, and both failed.
- **Most pile-ins failed.** The two largest, Reya (156 early wallets) and Aevo (105), succeeded. The next
  four failed: Pike 42 (exploited), Blackwing 33, Cega 20 and nftperp 20. Perp venues: 2 of 7 succeeded.
- On a "launched a token" rule, among new protocols only: 32% (8/25) vs 22% (11/50), also not significant.

Reading: early Hyperliquid wallets arrive early at many new protocols, which is consistent with chasing
points or airdrops, though the data does not show why they go. That is why they were early at Lighter and
Variational, but by this test they did not pick the ones that lasted. Following them did not show a
signal. The only thing left is very large pile-ins at new perp venues, and that rests on 2 wins out of 7.

## Limits

- Arbitrum only, and four tokens only: native ETH, Ethereum mainnet, Base and other chains are not seen.
- Outflows run to 2025-02, not 2025-06: the public RPC allowed about one query a second.
- 36 of 92 recipient protocols could not be identified, 10 of them among the pile-ins; by the rule they
  count as failures. Leaving out the 6 that are fully unknown, precision is 5 / 19 = 26%.
- Infrastructure was filtered by labels, so unlabelled routers or pools may remain.
- Points campaigns, node sales and token sales rarely have TVL, so the TVL rule counts most of them as
  failures.
- "5 or more" in the 1,500-wallet sample is roughly 20 or more in the full cohort.

## Files

- `scripts/`: step 1 (`scan_*`, `lighter_*`, `build_*`, `farmers.py`, `report.py`).
- `scripts/ft/`: step 2 (`scan_out*`, `step1_parse.py` to `step5.py`, `labels.py`, `llama_hist.py`).
  Run them from this folder; they cache to `cache/` and `ft/`, which are not committed. They were written
  for a one-off run and are kept as they ran.
- `results/`: printed outputs, `report_output.txt` (step 1) and `step5_output.txt` (step 2), and
  `notes.md`, the full working notes, with sources for the contracts and every number above.
