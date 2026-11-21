# What happens to the pool after a Uniswap CCA? Launch-day LP results (2026-11-21)

Uniswap's Continuous Clearing Auction (CCA) sells a token over many blocks at one clearing price per block. If the sale
graduates, a liquidity strategy calls `migrate()` and seeds a Uniswap v4 pool at the final clearing price. We counted every
CCA created through the four official factories on Ethereum, Base, Unichain and Arbitrum, read every bid of 13 of the 14 that
graduated with $10k or more (not UMIA's, on Base), and followed the seven pools that actually traded (six for 72 hours,
UMIA for 24): price against the clearing
price, volume, fees, the strategy's own LP position against holding, who traded and through which contracts.
Everything comes from public RPCs and keyless explorer APIs. No transactions were sent.

```
# inventory (run once from this directory with PYTHONPATH=. ; needs eth_abi, the only non-stdlib dependency; the Base scan takes about 2 h)
python3 inventory/fetch_auctions.py; python3 inventory/scan_rpc_auctions.py base 38441212 8; python3 inventory/scan_rpc_auctions.py arbitrum 400000000
python3 inventory/enrich.py; for c in ethereum base unichain arbitrum; do python3 inventory/find_migration.py $c 1000; done; python3 inventory/catalog.py
# this note (stdlib only)
python3 -I bids.py       # every BidSubmitted of the 14 graduated auctions >= $10k -> data/bids.json
python3 -I swaps72.py    # 72 h of Swap and ModifyLiquidity for the pools that traded, with tx from/to -> data/swaps72_*.json
python3 -I labels.py     # names of the contracts that carried the volume (Blockscout on Ethereum, Sourcify elsewhere)
python3 -I counts.py     # -> results/inventory.txt, results/auctions_ge10k.csv
python3 -I analyze.py    # -> results/analyze.txt, results/pools.json
# UMIA's 24 h row (Base) comes from the inventory step's day-1 measurement:
python3 inventory/run_measure.py base 9   # -> data/lp_base.json (merged into data/lp_all.json)
```

`data/` is not committed (the scripts fetch it again). `results/` is.

## Results

### 1. Inventory: few CCAs of any size

| chain | CCAs created | graduated | migrated to v4 (of those searched) | graduated >= $10k | graduated >= $100k |
|---|---|---|---|---|---|
| Ethereum | 402 | 91 | 18 | 9 | 7 |
| Base | 495 | 141 | 9 | 2 | 2 |
| Unichain | 131 | 22 | 8 | 1 | 0 |
| Arbitrum | 86 | 36 | 1 | 2 | 1 |
| **total** | **1,114** | **290** | **36** | **14** | **10** |

- 2025-11-13 to 2026-11-21. Graduated auctions raised $75.5M in all; Aztec alone is $58.9M (78%).
- Aztec is confirmed: 21,218 bids from 16,741 addresses, $58.88M raised, clearing price 1.551e-5 ETH per AZTEC.
  The next largest are UMIA (Base, $6.11M), rCAP ($3.84M), wOCT ($2.72M, 1,867 bids / 812 addresses), STRATO ($1.34M) and FOLD/ETH ($0.94M).
- Of the 10 above $100k, 7 migrated to a v4 pool. 3 sent the proceeds to a Safe instead (rCAP, FOLD/USDC, rIDOS).
  Of the 7, STRATO traded 7 times in its first day and RNBW not at all in its first week, so 5 large pools plus 2 small ones
  (BFX $38k, BWLK $23k) are all the launch-day trading there is to measure. The full list is `results/auctions_ge10k.csv`.
- All seven pools measured below were seeded with one full-range position (`positions` in the migrate's ModifyLiquidity).

### 2. Launch day and the first three days

Price is the pool's price over the clearing price (1.00 = clearing). The window starts at the migrate block, or at the
first swap for Aztec and FOLD/ETH, whose pools sat untraded for weeks (Aztec's swaps were locked by its strategy hook until
2026-02-12). "CCA position vs hold" is the strategy's full-range position, fees included, against holding what it deposited.
The 5-minute markout is the pool's loss to each swap valued at the pool's own price 5 minutes later, after fees.

| pool | raised | LP seeded | price at 5 min / 1 h / 24 h / 72 h | 72 h low / high | volume 24 h / 72 h | fees 24 h / 72 h | CCA position vs hold 24 h / 72 h | 5-min markout day 1 |
|---|---|---|---|---|---|---|---|---|
| AZTEC (ETH) | $58.9M | $16.5M | 0.80 / 0.72 / 0.73 / 0.73 | 0.64 / 1.00 | $9.29M / $25.1M | $4.6k / $12.6k | −$169k (−1.0%) / −$169k (−1.0%) | −$258k (−278 bp) |
| UMIA (Base)¹ | $6.11M | $2.44M | — / — / 1.58 / — | — | $8.08M / — | $80.8k / — | +$0.7k (0.0%) / — | −$163k (−202 bp) |
| wOCT (ETH) | $2.72M | $0.57M | 0.94 / 1.67 / 1.04 / 0.74 | 0.67 / 2.38 | $4.87M / $5.43M | $14.6k / $16.3k | +$14k (+2.5%) / +$11k (+1.8%) | −$87k (−179 bp) |
| FOLD (ETH) | $0.94M | $0.59M | 1.48 / 2.34 / 2.07 / 3.82 | 0.69 / 3.97 | $22.1M / $35.4M | $77.2k / $124k | moved to a managed vault before trading² | −$99k (−45 bp) |
| BALANCE (ETH) | $0.14M | $0.27M | 0.26 / 0.18 / 0.11 / 0.06 | 0.05 / 1.00 | $1.69M / $1.84M | $5.1k / $5.5k | −$59k (−21.7%) / −$74k (−27.4%) | −$35k (−209 bp) |
| BFX (ETH) | $38k | $38k | 1.09 / 1.36 / 0.01 / 0.01 | 0.00 / 2.39 | $73k / $90k | $0.8k / $1.0k | −$4k (−11%) to its removal at 3.1 h³ | −$4k (−508 bp) |
| BWLK (ETH) | $23k | $46k | 1.00 / 1.00 / 1.08 / 1.07 | 0.87 / 5.71 | $131k / $134k | $1.3k / $1.3k | +$1.3k (+2.7%) / +$1.3k (+2.8%) | −$33k (−2,484 bp) |

¹ UMIA: Base's free RPCs were rate-limited for the whole session, so UMIA's numbers are from an earlier scan of its first
24 h by the same method (no 72 h, no tx `to`, no bid list). ² FOLD/ETH: the full-range position (the migrate's exact L) was
withdrawn 0.92 h before the first swap, and liquidity was re-added from 0.02 h before it by a contract whose implementation
Blockscout names `UniV4StandardModuleV2Private` (an Arrakis Modular module; DefiLlama files it under arrakis-modular).
That module re-ranged 85 times in 72 h. If the full-range position had stayed: −$4k at 24 h, −$189k at 72 h.
³ BFX: 85% of the position was withdrawn at 3.1 h, while the price was 2.2x clearing and before it fell to 0.01; had it stayed, −$15k (−38%).

- **The CCA's own full-range position lost little to arbitrage in the large pools.** Aztec lost 1.0% of $16.5M in a day,
  all of it from the price falling 27% (impermanent loss −$173k, fees +$4.6k at the 0.05% tier). UMIA's and wOCT's
  1% and 0.3% fees covered their loss. Large losses came where the token collapsed (BALANCE −89% in a day, BFX −99%):
  that is the price, not the flow.
- **The 5-minute markouts are negative everywhere** (−45 to −278 bp on the larger pools; −$516k on the six Ethereum
  pools plus −$163k on UMIA over $46M of day-1 volume), but about half comes back within the day: the same trades marked
  at 1 h are −$397k and at 24 h −$249k on the six Ethereum pools (UMIA: −$115k at 1 h, +$1.7k at 24 h). At 24 h, BALANCE's
  −$69k (a price collapse) is the largest single item after Aztec's −$166k. Short-horizon flow against the pool is real; it
  is at most a few hundred thousand dollars per launch, and only Aztec and UMIA are large enough for it to be that.
- **The pools fill with other liquidity quickly.** In 72 h: Aztec 114 other adds (104 same-block add/remove pairs, i.e.
  just-in-time liquidity), FOLD 227, BALANCE 159. The CCA position's share of day-1 fees: Aztec 0.99, wOCT 1.00, FOLD n/a,
  BALANCE 0.62, BFX 0.29 (to removal).
- **Who traded.** Aztec 760 sender addresses on day 1, top five 42% of volume; the others 52 to 9,356 senders with the
  top five at 10–14% (BWLK 46%). Trades that were profitable to their sender at 5 minutes after fees were 53–74% of
  volume. One unverified contract, 0x8f10b468…f996, is a top swap sender in FOLD (20%) and BALANCE (11%) on Ethereum and in
  UMIA (8.5%) on Base.

### 3. Does the auction say where the price goes?

| pool | bid currency with max price >= 1x / 1.5x / 2x / 5x clearing | winners | median winner limit (by amount) | day-1 sells by auction bidders | day-1 buys by bidders | price 24 h | refunded bids with limit >= 24 h price |
|---|---|---|---|---|---|---|---|
| AZTEC | 56% / 35% / 32% / 28% | 15,423 | 4.2x | 24% of sell volume | 1% | 0.73 | $13.5M (day-1 buys were $4.1M) |
| wOCT | 26% / 12% / 4% / 2% | 480 | 1.29x | 39% | 2% | 1.04 | 0 |
| FOLD | 100% / 21% / 9% / 3% | 216 | 1.14x | 9% | 0% | 2.07 | 0 |
| BALANCE | 19% / 6% / 3% / 1% | 171 | 1.26x | 6% | 8% | 0.11 | $0.43M (day-1 buys were $0.79M) |
| BFX | 44% / 27% / 13% / 5% | 109 | 1.98x | 15% | 25% | 0.01 | $36k |
| BWLK | 100% / 49% / 2% / 0% | 61 | 1.25x | 9% | 1% | 1.08 | 0 |

- **No simple signal.** In a uniform-price auction a high limit costs a bidder nothing, so limits are not valuations:
  Aztec's winners bid a median 4.2x the clearing price and the price still fell 27%. Pools whose demand above clearing was
  thin (BALANCE, wOCT) went down and up respectively. Six launches cannot settle this, but nothing in the bid book lines up
  with the day-1 path here.
- **Auction winners are a known share of the first sellers:** 24% of Aztec's day-1 sell volume came from addresses that bid
  (matched on the bid's `owner`, so tokens moved to another address first are missed). Bidders barely buy in the pool (0–8%,
  BFX 25%). Aztec had $13.5M of refunded bids whose limits were at or above the price the pool traded at 24 h later, against
  $4.1M of day-1 pool buying: the losing side of the book did not come back to buy.

### 4. Two counterfactuals (same trades, stated assumptions)

**A. Same capital in a range around the clearing price** ([clearing/k, clearing·k]), same price path, same swaps; the range
earns the fee share its liquidity would have had while in range. Baseline: the full-range position kept for the whole window.

| pool | full range kept 24 h / 72 h | range /2 to x2 | range /4 to x4 |
|---|---|---|---|
| AZTEC | −$169k / −$169k | −$587k / −$607k | −$342k / −$350k |
| wOCT | +$14k / +$11k | +$11k / −$6k | +$14k / +$5k |
| FOLD | −$4k / −$189k | −$159k / −$674k | −$51k / −$441k |
| BALANCE | −$59k / −$74k | −$116k / −$125k | −$106k / −$119k |
| BFX | −$15k / −$14k | −$18k / −$18k | −$18k / −$18k |
| BWLK | +$1.3k / +$1.3k | +$0.6k / +$0.6k | +$0.9k / +$1.0k |

Concentrating around the clearing price made every launch worse, because the price left the clearing price in both
directions (Aztec −27%, FOLD x2–x4, BALANCE /10) and a tighter range turns the same move into a larger loss. The extra fee
share did not make up for it. This is the result one expects unless the clearing price predicts where trading settles, and
section 3 found that it did not.

**B. A launch fee: 3% for the first hour, 1% from 1 h to 6 h, the pool's own fee after.** A day-1 trade that was profitable
to its sender at 5 minutes is kept only if it is still profitable after the extra fee; every other trade is kept with
probability r. LP result = the day-1 5-minute markout.

| pool | actual | r = 1 (others all stay) | r = 0.5 | r at which it breaks even |
|---|---|---|---|---|
| AZTEC | −$258k | −$173k (volume kept 84%) | −$186k (81%) | better at any r |
| wOCT | −$87k | −$21k (98%) | −$149k (78%) | 0.74 |
| FOLD | −$99k | +$198k (97%) | −$512k (80%) | 0.79 |
| BALANCE | −$35k | −$5k (94%) | −$46k (75%) | 0.63 |
| BFX | −$4k | −$3k (97%) | −$4k (93%) | 0.43 |
| BWLK | −$33k | −$33k (100%) | −$33k (100%) | 0.28 (its losing trades came about 20 h in, after the schedule) |

The fee schedule helps only if most of the non-arbitrage flow stays. Those trades are what pays the pool (FOLD's
were +623 ETH at 5 minutes against −667 ETH for the rest), so losing a quarter of them undoes the gain in every pool but
Aztec. For Aztec, where the flow against the pool was 74% of volume, the schedule saves about $72k–85k of $258k.

### 5. Routing: does flow reach these pools, hooked or not?

Day-1 volume by the contract the transaction called (`to`), falling back to the contract that called the PoolManager:

| pool | hook permissions | Universal Router | aggregators, solvers, bridges | own contract (to = swap caller) | other / unattributed |
|---|---|---|---|---|---|
| AZTEC | beforeInitialize, beforeSwap | 51% | 18% (CoW 17.7%) | 15% | 16% |
| UMIA¹ | beforeInitialize, afterInitialize, beforeAdd, beforeRemove, beforeSwap | 24% (two UR deployments) | 41% (0x `BaseSettler`) | — | 35% |
| wOCT | beforeInitialize | 51% | 13% (Kyber, OKX, 0x, Relay) | 23% | 12% |
| BALANCE | beforeInitialize | 11% | 19% (Relay, OKX, Kyber, 0x) | 26% | 44% |
| FOLD | none | 27% | 28% (Relay 17%, 1inch 4%) | 15% | 30% (incl. 4337 wallets 10%) |
| BFX | none | 36% | 33% (OKX 19%, MetaMask 8%) | 19% | 13% |
| BWLK | none | 23% | 5% | 17% | 55% (one proxy 53%) |

¹ UMIA by the PoolManager caller only (tx `to` not available), named with Sourcify.

- Aggregators did route into the two pools whose hook runs on every swap: CoW carried 17.7% of Aztec's first day,
  0x's Base settler 41% of UMIA's. Those hooks gate trading (Aztec's lock) and do not change the price, so this says
  aggregators include hooked pools whose hook does not alter the quote; it says nothing about hooks that do.
- The Universal Router (the Uniswap interface and integrators that use it) carried 11–51%; contracts that trade through
  themselves (bots) 15–26%. "Unattributed" is unverified contracts and upgradeable proxies whose implementation we could
  not name.

## Method

- Auctions: `AuctionCreated` from the four CCA factories in the continuous-clearing-auction README
  (v1.0.0 0x0000ccaDF55C911a2FbC0BB9d2942Aa77c6FAa1D, v1.1.0 0xCCccCcCAE7503Cac057829BF2811De42E16e0bD5,
  v2.0.0 0x00cCa200BF124dBfA848937c553864f4B4CE0632, v2.1.0 0x000000001F26a0044BaA66024e7b6599c61963F8; same on all four
  chains), from Blockscout (Ethereum, Unichain) and by scanning `eth_getLogs` (Base from block 38,441,212, Arbitrum from
  400,000,000). State (`currencyRaised`, `clearingPrice`, `isGraduated`) read with `eth_call`. USD at the end date's ETH/USD
  daily close (CoinGecko); USDC = $1. Auctions in a Base test token named "USD Coin" are excluded from the dollar counts.
- Migration: for graduated auctions raising $1k or more (43), the funds recipient's transactions within 30 days of the end
  (3 days on Base) are searched for a PoolManager `Initialize`; that gives poolId, hook, fee, initial price and positions.
  Graduated auctions under $1k (247) were not searched.
- Bids: `BidSubmitted(id, owner, priceQ96, amount)` from each auction between its start and end block.
  priceQ96 / 2^96 scaled by decimals is the bid's limit in currency per token; amount is currency committed.
- Pool: v4 `Swap` and `ModifyLiquidity` from the PoolManager filtered by poolId, 72 h. Swap amounts are the swapper's
  deltas, fee included. Fee revenue = input amount × the swap's fee. The CCA position's fee share = its L / the pool's
  active L reported in each Swap. CCA position vs hold = 2√k/(1+k) − 1 of the deposit (k = price ratio) plus its fee share.
  The position is followed until a full-range removal of at least half its L.
- Markout: LP P&L of a swap = −(token received by the swapper × pool price 5 min later) − (currency received by the swapper).
- Routing: `from` and `to` of each swap's transaction; the Swap event's `sender` (the contract that called the PoolManager).
  Names from Blockscout's verified contract name (Ethereum), Sourcify (Base), and a short list of known router addresses.

## Limits

- Only the four official factories. A team that deploys its own factory, or runs a CCA-like sale elsewhere, is not counted.
- Seven pools, two of which are under $50k. Aztec is 78% of the money raised. Any average here is mostly Aztec.
- UMIA (the second largest) is 24 h only and from an earlier scan of the same pool: Base's free RPCs (Tenderly's public
  gateway, mainnet.base.org) returned 429 for the whole session, and the others need keys or cap `eth_getLogs` at 10–100 blocks.
  UMIA's bids were not read either.
- The markouts and both counterfactuals use the pool's own later price, not an outside reference (there is no CEX price for
  most of these at launch), so "loss" means "the pool's price moved against the LP after the trade". Counterfactual A keeps
  the price path fixed when liquidity changes; a deeper pool would have moved less for the same trades. Counterfactual B
  drops whole trades rather than shrinking them, and r is an assumption, not a measurement.
- The CCA position is identified by its range and L, not by its NFT, because the position's salt was not kept; a full-range
  withdrawal of at least half that L by another LP would be misread as the CCA position leaving.
- Bidder matching uses the bid's `owner`; tokens claimed and moved to another address before selling are not matched.
- Contract names come from verified source only. Unverified bots and proxies stay unattributed; the aggregator share is a
  lower bound.

## Prior art searched

Searched: GitHub code search for `IInitializerHook`, `LBPStrategy clearingPrice hook` and "continuous clearing auction hook";
GitHub repository search "continuous clearing auction" (12 repos); Uniswap/awesome-cca; web search for post-auction
liquidity management, dynamic-fee launch hooks and market-making around the CCA clearing price; the v4 pools' own
liquidity providers (above).

- **Arrakis Pro** offers post-CCA management: it moves the full-range position into a managed v4 vault in one transaction,
  with an optional "Price Convergence" hook that moves the pool to a CEX listing price at open
  ([docs](https://docs.arrakis.finance/uniswap-cca), [blog 2026-02-04](https://arrakis.finance/blog/uniswap-cca)). The page
  does not say the auction's bid book or clearing price set the range or fees. FOLD/ETH used an Arrakis Modular module on
  chain (above); its day-1 5-minute markout was the smallest of the seven (−45 bp).
- **Uniswap liquidity-launcher v3** lets the launching team pass its own `IInitializerHook` and up to 10 positions; its
  example hooks are `InitializerHook` and `GatedSwapHook`. The pools measured here all used one full-range position.
- **programmablehq/PROGRAMMABLE `BoundedDynamicFeeHookV1`**: an `IInitializerHook` that sets the LP fee from 0.30% to 1.00%
  by tick movement since the last block. It does not read the auction.
- Hackathon and tooling repos that use `IInitializerHook` or CCA data: hrsh22/ethonline-26, OffGrid0xDAO/r00t.fund,
  prism-toggle-ai/Prophit, 40-Acres/ace, kay9T/kay9-protocol, 0xdevant/liquidity-launcher-strategies, dzmbs/uniswap-cca-indexer,
  Shubham-Singh-Shoora/Beacon-. None found that takes the clearing price or bid distribution into the post-launch pool's range
  or fee.
