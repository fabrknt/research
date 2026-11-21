# Where do Robinhood Chain's stock pools leak, by trading session? (2026-11-21)

Every Uniswap v4 swap on Robinhood Chain (chain 4663) in pools whose two sides are both stock tokens with a
Hyperliquid xyz (HIP-3) perp, or one such stock and USDG: 4,748 pools, 2.72M swaps, $671M, 2026-10-26 21:55 to
2026-11-21 05:20 UTC (25.3 days, blocks 98,743,268 to 119,637,415). Each swap is marked against the xyz perp
price and split by US trading session. This extends
[2026-11-13 Robinhood Chain stock dealer](../2026-11-13-robinhood-stock-dealer/) (nine names, 561 pools, to 11-13)
to 62 names and eight more days. Nothing was deployed and no transaction was sent.

The question: tokenized stocks trade 24/7 on one curve and one fee, while the underlying has market hours, an
external price, a weekend and an open. Do passive LPs leak to arbitrage because of that, and in which sessions?

## Results

Passive LP result per swap, fee included (+ = LPs gained). Reference = xyz perp, marked 5 minutes and 1 hour
later; "to reopen" = 5 minutes after the next US regular-session open (non-regular-hours swaps only).
ET sessions: regular 9:30–16:00, pre 4:00–9:30, after 16:00–20:00, overnight 20:00–4:00 (Sun 20:00 to Fri 4:00),
weekend Fri 20:00 to Sun 20:00. Bell windows overlap the sessions: open 9:15–9:45, close 15:45–16:15.

| session | volume | $/day | fee paid | price move, 1 h (before fee) | LP net, 5 min | LP net, 1 h | LP net to reopen |
|---|---|---|---|---|---|---|---|
| regular | $283.1M | $11.2M | 13.0 bp | −16.7 bp | −2.1 bp | **−3.7 bp (−$104K)** | |
| pre | $116.5M | $4.6M | 10.8 bp | −13.4 bp | −1.8 bp | −2.6 bp (−$31K) | −1.0 bp |
| after | $95.5M | $3.8M | 11.3 bp | −15.8 bp | −4.8 bp | −4.6 bp (−$44K) | **−15.6 bp (−$142K)** |
| overnight | $110.9M | $4.4M | 10.4 bp | −11.2 bp | −0.0 bp | −0.8 bp (−$9K) | +2.3 bp |
| weekend | $65.5M | $2.6M | 7.9 bp | −6.4 bp | +0.7 bp | +1.5 bp (+$10K) | +5.5 bp (+$34K) |
| **all** | **$671.3M** | **$26.5M** | **11.4 bp** | −14.1 bp | −1.8 bp (−$124K) | **−2.6 bp (−$177K)** | |
| open window | $57.9M | $2.3M | 14.6 bp | −30.4 bp | −6.3 bp | **−15.8 bp (−$91K)** | |
| Monday open | $11.5M | $0.5M | 14.2 bp | −19.6 bp | −1.6 bp | −5.4 bp | |
| close window | $30.2M | $1.2M | 12.1 bp | −24.2 bp | −16.6 bp | −12.1 bp (−$36K) | **−59.6 bp (−$95K)** |

1. **The leak is at the bells and after hours, not overnight or at the weekend.** The open window is 9% of
   volume and half of the 1-hour loss (−$91K of −$177K); the close window plus after-hours lose most when held
   to the next open (−$95K and −$142K). Overnight is flat at 1 h and slightly positive to the reopen; the weekend is the only session where LPs gain at both 5 min and 1 h.
   Fees (11.4 bp) cover about 80% of the price move against LPs (−14.1 bp) over the hour.
2. **The loss is direction, not time.** Swaps that move the pool toward the xyz price cost LPs −11.5 bp
   (−$490K over 1 h); swaps that move it away earn them +12.9 bp (+$313K). The same sign holds in every session
   (toward: −6.4 bp overnight to −17.8 bp after hours).
3. **A few days and names carry it.** 15 of 4,050 (name, day, session) cells hold −$136K of the −$405K in all
   losing cells: 2026-11-05 regular hours across SPY, META, MSTR, TSLA, HIMS, PLTR (SPY alone −$28.5K);
   INTC after hours on 10-29 (−$19.1K at 1 h, −$46K to reopen); GOOGL after hours on 10-28 (−$15.9K). By name:
   SPY −$35.9K (−$32.6K of it in regular hours), SKHY −$24.2K, INTC −$17.3K, GOOGL −$15.9K, NVDA −$14.9K.
4. **Volume fell after 11-13**: $19.8M/day to 11-13, $6.8M/day after; LPs went from −3.8 bp to +0.8 bp (1 h).
   On the 11-13 study's own set (nine names, stock/USDG and stock/stock) this run gives −1.6 bp (5 min) and
   −3.3 bp (1 h) up to 11-13, against −1.8 and −3.2 then (`results/nine_names.txt`).
5. Marked against the pool's own later price instead of xyz, the loss nearly disappears (−0.3 bp at 1 h overall)
   except in the bell windows (open −11.1 bp, close −11.0 bp): outside the bells the pools move little on their
   own, so most of the measured leak exists only relative to an external price.

### Session-aware pricing already exists here (Q4)

15% of the volume ($99.7M) went through hooks whose verified source sets the fee from the US session
(`results/session_hooks.txt`, `results/hooks_top20.json`):

| hook (verified name) | pools | volume | what it does | fee charged | LP net, 1 h |
|---|---|---|---|---|---|
| `SessionFeeHook` 0xc15b…6080 | SPCX, SKHY, BABA /USDG | $60.0M | four fees per session from `block.timestamp` and an owner schedule; "exempt senders (the arb team's swap contracts) pay 0" | 5.0 bp avg; **57% of its volume paid 0** | −5.7 bp |
| `FablesRWA` (Fables, 6 hooks; plus `FablesRamp` $0.1M) | 21 Fables pools in this set (NVDA, SPY, AAPL, TSLA, META, AMZN, MU, PLTR …) | $39.3M | calendar floors (regular / overnight / closed), opening descent, Monday spike, closing ramp, NYSE holidays 2026–30 baked in; keeper overrides | regular 11.2, open 19.0, Monday open 21.2, weekend 4.4 bp | −4.4 bp |
| `OttoFeeHookV2`, `HelmFeeHook`, `FeeHook` | a few | < $0.3M | session fee + move fee (Otto, Helm); oracle capture (FeeHook) | 14.8–43.1 bp | small samples |

On-chain configuration of Fables' NVDA/USDG (`results/fables_floor_config.json`): 10 bp regular, 8 bp
overnight, 3 bp closed, 40 bp after a closure decaying over 2 h, 22 bp around the close. Fables pools did not do
better than hookless pools of the same names: −4.4 bp vs −2.8 bp at 1 h (stock/USDG); at the open −40.0 bp vs
−38.2 bp.

Changes since 11-13: 36 new pools in the set (17 hooked, 7 new hooks), $147K of volume between them. New hooks:
`HelmFeeHook` (session + move fee + earnings window, PLTR and NVDA /USDG), `BellswapHook` (fee from the gap to a
reference feed, directional, fails closed on a stale feed; NVDA/USDG, $4 of volume), `MetricEquityHook` (fills
against Metric pools, 3 bp), `FablesRamp`, an arbitrage-plugin hook and an unverified one
(`results/hooks_new_since_1113.json`). Hooked share of volume: 15% (nine-name set: 91% hookless to 11-13, 95% after).

### What stock-specific information is worth (Q2)

`counterfactual.py`: a policy raises some swaps' fee; each swap then survives with probability
max(0, 1 − e × extra bp). e is an assumption: 0, 1%, 3% and 10% of volume lost per extra bp. Every policy is
compared with a **control that raises every swap's fee evenly to the same average fee**, so the difference is
what the information adds. At e = 0 the two are equal by construction (a pure transfer). 1-hour marks:

| policy (avg fee after) | e = 1%/bp | e = 3%/bp | e = 10%/bp | volume lost (e = 1/3/10%) |
|---|---|---|---|---|
| session schedule: regular 3, pre/after/overnight/weekend 5, open 20, Monday open 30, close 15 bp (13.95 bp) | +$158K | +$138K | +$117K | 2.5 / 7.5 / 18.8% |
| control +2.59 bp everywhere (13.95 bp) | +$169K | +$168K | +$167K | 2.5 / 7.5 / 25.2% |
| toward-reference swaps pay 0.5 × distance (13.07 bp) | **+$158K** | **+$196K** | **+$245K** | 1.6 / 4.2 / 9.2% |
| control +1.68 bp everywhere (13.07 bp) | +$111K | +$112K | +$118K | 1.6 / 4.9 / 16.4% |
| toward-reference swaps pay 1.0 × distance (15.75 bp) | +$322K | +$340K | +$375K | 4.3 / 10.5 / 21.6% |
| control +4.44 bp everywhere (15.75 bp) | +$283K | +$272K | +$233K | 4.3 / 12.9 / 43.1% |

"+$" = LP P&L improvement over 25 days against the actual −$177K. 5-minute marks give the same ordering
(`results/counterfactual_300.txt`).

- **The calendar adds nothing beyond its fee level**: the session schedule does worse than charging the same
  average fee to everyone, at every e > 0: under this model, concentrating the surcharge in the bells and
  off-hours sheds paying volume without shedding proportionally more of the flow that moves the price.
- **Distance from the external price does**: charging only the swaps that close a gap to xyz, in proportion to
  the gap, avoids $47–127K more than the matched control at e = 1–10%, and loses less volume (1.6–9.2% vs 1.6–16.4%).

### Routing (Q3)

`routing.py`, `routing_extra.py`:
- 85% of the volume is in hookless pools, 6% Fables, 9% other hooks.
- The two largest PoolManager callers carry 42% of all volume and **0.0% of any hooked pool's**:
  0x520e…8aa7 (25.7% of all volume, unverified, 84 signers in 200 sampled txs) and 0x278d…d8f2 (16.1%, a 609-byte
  unverified contract, 37 signers in 200, top signer 15.5%). Both are called directly as tx.to.
- Uniswap's UniversalRouter (two deployments) sends 5.9% of all volume and 10.0% of Fables' volume; KyberSwap's
  MetaAggregationRouterV2 appears as tx.to on 2.9% of sampled Fables transactions. 13.5% of volume is in
  transactions that touch more than one of these pools.
- `SessionFeeHook`'s zero-fee volume comes from two contracts (0xc348…8a48, 33% of the hook's volume;
  0x6353…982c, 21%), which are also its two largest callers.
- Best-quote check (each stock/USDG swap against every live pool of the pair, priced at last price × last fee ×
  the swap's own impact on in-range liquidity): when a hookless pool is cheapest, 76% of that flow goes to it;
  when a Fables pool is cheapest, 49% does, and the rest pays on average only 2.7 bp more. **No clear evidence
  that routers avoid hooked pools**; the hooked pools that are skipped are near-ties. The evidence is rather
  that the largest flow sources (direct-called contracts) never use them.

### Prior art searched (Q4)

Searched (web, 2026-11-21): "Uniswap v4 hook dynamic fee market hours tokenized stocks"; "AMM session-aware fee
tokenized equities weekend closed market oracle"; "tokenized stock AMM LP loss weekend gap market hours hook";
"Fables DEX Robinhood Chain hooks fees time volatility"; "Fables ve(3,3) … trading calendar … contract address";
"Bellswap Uniswap v4 hook reference feed tokenized stocks"; "Helm fee hook tokenised stock Robinhood Chain";
"loss-versus-rebalancing tokenized equities overnight weekend". On chain: Sourcify-verified source of the top
20 hooks by volume and of every hook new since 11-13.

Found, all with session-aware fees for tokenized stocks:
- **Fables** (live on Robinhood Chain, DefiLlama ~$10M/day volume across all its pools): `FablesRWA` calendar hook
  as above; docs say "the two bells are where a tokenised stock's LP loss concentrates"
  ([docs](https://www.fables.fi/docs/dynamic-fees), contracts on Sourcify, registry 0x159a…3ef3).
- **SessionFeeHook** (0xc15b…6080, live, $60M here), **OttoFeeHookV2**, **HelmFeeHook**, **BellswapHook** (live, verified).
- **StockShield** (ETHGlobal HackMoney 2026, testnet): regime fees 5–50 bp across seven sessions, gap auctions at
  the open ([showcase](https://ethglobal.com/showcase/stockshield-eth-2wuvy)).
- Adjacent: Arrakis price-convergence hook (equity feed as reference, not on this chain); Chainlink tokenized
  equity feeds (session-aware smoothing, weekend treated as zero-liquidity); Uniswap's VolatilePair/StablePair
  hooks (volatility, not session). No independent measurement of tokenized-stock LP loss by session was found.

## Method

```
python3 -I find_pools.py 119637415        # every v4 Initialize -> data/pools_all.json (1,167,633 pools)
python3 -I tokens.py                      # stock tokens with an xyz perp (+ USDG) -> data/tokens.json
python3 -I fables.py                      # Fables registry -> data/fables_pools.json
python3 -I select_pools.py                # both sides in tokens.json -> data/pools_sel.json (4,748)
python3 -I fetch_pool_swaps.py 98743268 119637415   # Swap events of those pools -> data/pchunks/
python3 -I anchors.py 98743268 119637415  # block timestamps
python3 -I fetch_candles.py               # xyz 1m/5m/15m candles
python3 -I analyze.py                     # per-swap marks -> data/rows.pkl
python3 -I sessions.py > results/sessions.txt
python3 -I counterfactual.py 300 ; python3 -I counterfactual.py 3600
python3 -I routing.py ; python3 -I routing_extra.py
python3 -I hooks.py results/hooks_top20.json --top 20 ; python3 -I session_hooks.py ; python3 -I fables_config.py
python3 -I nine.py
```

- Same marks as the 11-13 study: fair = xyz price × k, k = median of (pool price / xyz price) per name and UTC day
  from stock/USDG pools (SPY → SP500, QQQ → XYZ100; SPY- and QQQ-quoted names through their k). LP result =
  side × (fill − fair at t+h) / fair at t+h, fee included. Fee = Swap.fee. Swaps more than 5% from the reference
  dropped ($0.23M).
- Direction: the pool's price after the previous swap in that pool vs after this one, compared with xyz at t.
- `rpc.py` and `hl.py` are copied unchanged from the 11-13 study; the 11-13 candles and block anchors
  (`~/src/rh-measure/data`, read only) are merged in.

## Limits

- **Reference.** Hyperliquid keeps the latest 5,000 candles: 1-minute marks exist only for 11-09 onward (15 names)
  and 11-17 onward (the rest); 5-minute from 10-26 for 15 names and from 11-03 for the other 47; 15-minute before
  that. Candle interpolation adds a few bp of noise. The xyz perp is itself thin at weekends, so weekend marks
  partly measure the perp; "to reopen" is the cleaner weekend test. k per day absorbs basis but also any
  persistent mispricing.
- 25 days, one big down day (11-05) and a few after-hours moves on dates consistent with earnings (not checked
  against an earnings calendar) dominate the totals. No NYSE holiday fell in the window.
- v4 only (v2/v3 excluded, as in 11-13). Names without an xyz perp are excluded. Hook fees taken outside the LP fee
  (hooks that keep part of the input) are not counted as user cost; the LP side is unaffected.
- Counterfactual: uniform elasticity (informed and uninformed flow equally price-sensitive), each swap's price
  path unchanged, all pools of a name moving together (one pool raising fees alone would just lose flow to the
  hookless pools), fee capped at 1%. The e values are assumptions, not estimates.
- Routing: most callers are unverified contracts and are reported by address only; the best-quote check ignores
  tick crossing, order splitting and gas, so it cannot prove avoidance either way.
