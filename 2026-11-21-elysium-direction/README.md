# Do Elysium's pools lose to arbitrage against Hyperliquid's price? (2026-11-21)

Elysium is Kinetiq's Arbitrum Orbit chain that settles to HyperEVM (chain 99901, mainnet 2026-11-09). Its pools
are ordinary Uniswap v3/v4-style pools: none of them reads Hyperliquid's order book or oracle when it prices a swap
(the on-chain HyperCore reads are announced for an ArbOS upgrade about four weeks after mainnet). We measured what
passive LPs in the two largest Hyperliquid-priced pairs lose, split by whether each trade moved its pool toward or
away from the HyperCore price, and what pricing from that price would have changed.

Window: 2026-11-18 00:00 to 2026-11-21 05:00 UTC (3.21 days; blocks 7,659,260 to 9,045,572). Every swap log on
the chain (1,300,897), from the public RPC `https://rpc.elysium.kinetiq.xyz`; HyperCore 1-minute candles from the
public info API (it keeps the latest ~5,000 minutes, which sets the window).

```
python3 -I hl_candles.py HYPE @107 @334                                   # HyperCore candles -> data/hl/
python3 -I backfill.py 2026-11-18T00:00:00Z 2026-11-21T05:00:00Z data/logs # every v4/v3/v2 swap log (~1 GB, ~25 min)
python3 -I trades.py 600                                                  # decode, identify the top 600 venues -> results/venues.txt
python3 -I analyze.py HYPE; python3 -I analyze.py KNTQ                     # Q1 -> results/leak_*.txt, data/rows_*.json
python3 -I counterfactual.py HYPE; python3 -I counterfactual.py KNTQ       # Q2 in place / quoting -> results/counterfactual_*.txt
for f in HYPE_E HYPE_HL KNTQ_E KNTQ_HL; do python3 -I poolsim.py data/rows_$f.json > results/poolsim_$f.txt; done  # Q2 replay
python3 -I sources.py 300                                                 # Q3 who sends the flow -> results/sources.txt
```

## Results

| | HYPE/USDC | KNTQ/HYPE |
|---|---|---|
| volume, matched to HyperCore | $3.60M/day, 12 venues, 57,396 trades | $0.86M/day, 6 venues, 10,976 trades |
| Elysium vs HyperCore, median | −19 bp (daily −13 to −26) | +3 bp (daily −28 to +34) |
| LP fees | $3,431/day | $3,349/day |
| LP loss before fees, 5 min after, vs HyperCore mid | −$5,856/day (−16.4 bp) | −$6,574/day (−78 bp) |
| LP P&L fees included, 5 min, vs HyperCore | **−$2,425/day (−6.8 bp)**: fees cover 59% of the loss | **−$3,225/day (−38 bp)**: fees cover 51% |
| same vs the local basis E | −$2,671/day (−7.5 bp) | −$2,668/day (−32 bp) |
| toward trades (vs HyperCore): share of volume, LP bp pre-fee / fees incl. | 58%, **−35.1 / −24.1** | 72%, **−123 / −82** |
| away trades | 42%, **+8.9 / +16.6** | 28%, **+36 / +74** |
| toward, by size (< $100 / $100–1k / $1k–10k), LP bp fees incl. | −19 / −24 / −27 | −57 / −57 / −145 |
| how much of the 5-min loss is already there at the trade (0 s markout) | 54% | 46% |

- **The leak is there, and it is directional.** Against the HyperCore mid, trades that move a pool toward it cost
  LPs 35 bp before fees and 24 bp after; trades that move it away pay LPs 9 bp before fees and 17 bp after. Fees
  (median 12 bp in the main v3 pool 0x9779, 10 bp in 0xd329, 0 in the largest v4 pool) do not cover the toward side.
  Larger toward trades lose a little more per dollar; the loss is spread across sizes ($100–1k carries most of it
  because it carries most of the volume). About half the loss is visible at the trade itself, against the mid of
  the same minute: the pool was already stale when it was hit.
- **It is smaller than on 11-09..11.** That study found −80 bp toward / +70 bp away (pre-fee, 5 min, against E)
  and LPs about +$15K/day overall (numbers from that study, not rerun here). Against the same E now: −21 / +2 bp and −$2.7K/day. The Elysium–HyperCore gap
  closed from −152 bp (median, 11-11) to −13…−26 bp, and the asymmetry shrank with it.
- **Quoting at the HyperCore mid is not the same as profit on Elysium.** A pool quoting HL mid ± 10–20 bp would
  have filled $0.8–1.5M/day, almost all of it users selling HYPE (Elysium trades below HyperCore), +$0.1–1.0K/day
  marked at the HyperCore mid but −$1.4–3.3K/day marked at Elysium's own price, while buying 13–22K HYPE/day
  that must leave Elysium (canonical withdrawal ~5.5 days) to be worth the HyperCore price.
  Quoting at E ± 10–20 bp fills $0.1–0.4M/day at +$0.16–0.32K/day (either mark). (`results/counterfactual_HYPE.txt`, part B.)
- **Directional fee, in place on the existing pools** (toward trades pay max(30 bp, distance) up to 300 bp):
  +$5.0K to +$5.6K/day for HYPE/USDC LPs against the HyperCore mid, from "every toward trade leaves" (58% of
  volume lost) to "nobody leaves" (no volume lost); the LP P&L goes from −$2.4K to +$2.6…3.1K/day in either case.
  Against E: +$3.2K to +$6.1K/day, losing 0–82% of volume. KNTQ: +$2.8K to +$5.1K/day vs HyperCore, 0–72% of volume.
- **The earlier "all 24 variants beat a fixed 30 bp" still holds: 96 of 96** (24 variants × 2 pairs × 2
  references). A new HYPE/USDC pool with a directional fee beats the same pool at a fixed 30 bp by +$0.7K to
  +$6.8K/day, routing 0.2–0.7M/day instead of 0.7–1.5M. But in absolute terms it is no longer reliably positive:
  −$2.3K to +$1.6K/day against E, −$0.6K to +$0.35K/day with the HyperCore mid as the reference (on 11-09..11:
  +$0.9K to +$1.6K/day without arbs). For KNTQ the directional pool is better by $1.8K–16.2K/day and still negative
  in every variant.
- **Routing (HYPE/USDC, 300 USD-weighted trades per venue).** By the transaction's `to`: 46% of volume enters
  through unverified contracts with ≤ 5 senders (bot-like), 17% through named aggregators and intent routers
  (KyberSwap 6.6%, Relay 5.7%, solver 0x0729 2.2%, 0x 2.0%, plus LI.FI and Enso), 7% through Uniswap's
  UniversalRouter or 4337 smart accounts, 30% other. The aggregator flow is 65% toward and costs LPs 10.7 bp;
  the UniversalRouter/4337 flow is 10% toward and pays LPs +54 bp (the app-direct flow is the benign part).
  **Hooked v4 pools do get aggregated flow**: the zero-fee hook pool (hook 0x506f) gets Kyber 6.9%, Relay 7.8%,
  4337 9.2%; the dynamic-fee hook pool (hook 0xba9d) gets Kyber 4.4%.
- **No directional-fee or HyperCore-priced hook is live in these pairs.** Uniswap's hooklist has no Elysium (99901)
  or HyperEVM (999) entry (PR #12104, "Add Elysium", open since 11-16); Labs' StablePair/VolatilePair addresses have
  no code on either chain. The HYPE/USDC dynamic-fee hooks with volume read 5 bp (0xba9d) and 4 bp (0x0559,
  KalosV4FeeHook: a fee and creator-fee hook with no oracle) from prices.

### Prior art (name search)

| project | prices from Hyperliquid's book/oracle? | where | status |
|---|---|---|---|
| nest AVR (v4 hooks, factory 0x24c1…) | stated goal: raise the fee when the pool drifts from the HL book; in the verified source the reference read returns `(false, 0)` until "native transport" exists, so today TWAP-deviation only | Elysium | live since ~11-13, TVL ~$1.6M |
| Metric (MetricOmm prop AMM) | its own model, pushed through `CompressedOracleV1`; HL not named as the input | Elysium (21 pools), HyperEVM, others | live, ~$440K TVL on Elysium |
| LiquidCore (Liquid Labs) | yes, HL read precompiles | HyperEVM | pools and router revert since ~11-07 |
| Harmonix | arbitrage vault Elysium ↔ HyperCore, not an AMM | Elysium | announced |
| Valantis STEX/HOT, BrownFi, WOOFi, HyperQuote, Hybra, Laminar, HyperBrick, Gliquid, Ultrasolid, HyperSwap, Project X, Kittenswap, Ramses, Curve, Upheaval, Aero, Kalos | no HL pricing found (LST redemption, Pyth/Chainlink, own oracle, RFQ, standard CL/ve(3,3)) | HyperEVM / Elysium | live |
| DODO PMM, Lifinity-style | not found on HyperEVM or Elysium | – | – |

Searched: Uniswap/hooklist (`chains.json`, all 5,271 entries for "elysium/hyperevm/hyperliquid/kinetiq", PRs and
issues), `eth_getCode` of the six StablePair/VolatilePair addresses on both RPCs, GitHub code search for v4 hooks
reading HL precompiles (`L1Read beforeSwap`, `0x…0807 beforeSwap`, `0x…0808 swap`, `spotPx sovereign pool`),
DefiLlama listings and adapters (nest-avr, liquidcore, metric-v1), Kinetiq's Elysium docs (what-is-elysium,
hypercore-market-data, building-on-elysium), docs of Metric, Liquid Labs, KyberSwap, 0x, Enso, Relay, LI.FI, and
22 web searches (Elysium prop AMM, HyperEVM oracle AMM / PMM, Valantis HOT, nest AVR, Metric, LiquidCore, WOOFi,
BrownFi, Hybra, Laminar, Gliquid, Ultrasolid, HyperBrick, OKX on Elysium). Aggregators listing Elysium: KyberSwap
("provisional"), Relay and LI.FI (in their chain APIs), Enso, HyperFlow; 0x/Matcha "announced" by Kinetiq but not on
0x's supported-chains page; OKX not found.

## How it is measured

- Venues: every v4 Swap (both PoolManagers, 0xe2e1… and 0x5c54…), v3 and v2 Swap log; the 600 most active
  venues identified (v4 from the PoolManager's `Initialize`, v3 by `token0()/token1()`). HYPE/USDC is WHYPE or native
  HYPE against USDC 0xb47c…; KNTQ/HYPE is KNTQ 0xe45a… against WHYPE or native HYPE. The next-largest venues by
  USD are KNTQ pools and launchpad tokens paired with HYPE (no HyperCore market), so KNTQ is the second pair.
- Reference: HyperCore HYPE perp; for KNTQ, spot KNTQ/USDC (@334, $3.3M/day on HyperCore vs $0.86M on Elysium)
  divided by the HYPE perp. Each minute is linear from the candle's open to its close. `HL` is that price;
  `E` multiplies it by the median (execution price / HL) of the pair's trades over the previous 30 minutes (the
  local basis, as in the 11-09..11 study).
- Direction: toward if the swap moved its pool's price (from `sqrtPriceX96`, after the pool's previous swap)
  closer to the reference at the trade.
- LP P&L of a trade at horizon h, fee included: −s × (ref(t+h) / execution price − 1) × USD, s = +1 when the
  user buys the base. The fee is read from the pool's own prices: a swap from price Pb to Pa at constant liquidity
  has no-fee average price √(Pb·Pa), and the fee is the execution price's distance from it (clipped to 0–300 bp).
  This reads dynamic fees and hook overrides that `fee()` and the v4 fee field do not (v3 0x9779 reports
  `fee()` 1479 and charges 12 bp).
- Counterfactuals: `counterfactual.py` A applies the directional fee in place with a share r ∈ [0, 1] of toward
  volume staying (the stated price sensitivity); B adds one pool quoting a mid ± h with linear depth, filled while
  its marginal price beats what the trader actually got. `poolsim.py` (copied from the 11-09..11 replay, unchanged)
  replays one new pool with its own price against the recorded flow: 2 depths × 3 arbitrage settings × one swap or
  split × 2 marks, fixed 30 bp vs directional.
- Routing: per venue, 300 trades sampled by USD (seed 7), `eth_getTransactionByHash` for each; names from the
  explorer's verified-source API (`elysium.kinetiq.xyz/explorer/api?module=contract&action=getsourcecode`).

## Limits

- **HyperCore at one-minute resolution.** The book archive with ~5 s snapshots is requester-pays, so not used; the
  candles cannot show sub-minute timing, so markouts at 0 s and 60 s blur, and arbitrage that happens within seconds
  is attributed to the minute. 3.2 days only (the candle API's reach).
- The HyperCore mid is not a price an Elysium LP can trade at: moving inventory costs the canonical withdrawal
  (~5.5 days) or a fast bridge (1.7–3.1% on 11-12). The E columns show the loss against Elysium's own price.
- Fees read from prices are approximate when a swap crosses ticks or a hook settles part of it itself. v2 pools
  and DLMM pools are not in the pair totals. Gas, hedging and bridge costs are left out.
- KNTQ's toward/away depends on a thinner HyperCore spot market; price discovery may sit partly on Elysium.
- Counterfactual A is static (it does not re-route the flow); B resets the quote before every trade (no latency);
  both assume the recorded trades would still happen. The share r and the replay's routing rule are assumptions,
  not measured elasticities.
- Routing by `tx.to` names the first contract called, not the final router; most top entries are unverified.
- "Bot-like" means an unverified contract with ≤ 5 distinct senders in the sample, nothing more.

Data access as of 11-21: the public RPC answers `eth_getLogs` with `blockTimestamp` and no key (10,000 logs per
call); the explorer's source API answers without a key; the HTML explorer is behind a Vercel checkpoint.
