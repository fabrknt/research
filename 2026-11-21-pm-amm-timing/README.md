# Would market-specific information have closed the LP leak? Trueo replayed (2026-11-21)

A follow-up to [Trueo LP loss](../2026-11-21-trueo-lp-loss/): the same 104 resolved markets on Base
(5,419 swaps, $773,361 of volume, $126,558 lost by the pools against holding). The thesis tested: a
prediction-market AMM ignores what it knows (when the market ends, how far the price is from 0 or 1, how the
price just moved), and that is why its LPs lose. We ask which of that information predicts the loss, and replay
every swap under fee and liquidity rules that use only it.

```
python3 -I extract.py    # one row per swap with ex-ante features -> data/trades.json (reads ../2026-11-21-trueo-lp-loss/data/)
python3 -I features.py   # which features predict the loss -> results/features.txt
python3 -I sim.py        # fee / liquidity rules replayed -> results/sim.txt
```

Run the five fetch scripts of `../2026-11-21-trueo-lp-loss/` first (its `data/` is not committed). `extract.py`
reproduces that study's totals exactly (`results/extract.txt`).

## Results

**1. Rules that use only what the pool knows cut the loss by a third at best, and cost a third or more of the
volume. None closes it.** Loss cut and volume kept, all 104 markets, under three assumptions about how traders
react (below). Full table in `results/sim.txt`.

| rule | no one reacts | walk, e=0 | walk, e=3 | walk, e=10 |
|---|---|---|---|---|
| flat extra fee 5% | +31% / 100% | +30% / 92% | +14% / 87% | −15% / 78% |
| flat extra fee 20% | +122% / 100% | +104% / 71% | +38% / 55% | −22% / 41% |
| close the pool at endOfTrading | +7% / 94% | same | same | same |
| pull liquidity 24 h before endOfTrading | +42% / 77% | same | same | same |
| pull liquidity 72 h before endOfTrading | +57% / 53% | same | same | same |
| fee 10% in the last 72 h (+ close) | +32% / 94% | +31% / 90% | +13% / 87% | −13% / 82% |
| fee = 1 × \|price move, 24 h\| | +61% / 100% | +52% / 89% | +16% / 82% | −15% / 74% |
| fee = 2 × \|price move, 6 h\| | +63% / 100% | +52% / 90% | +19% / 83% | −6% / 76% |
| pull liquidity when price outside [0.1, 0.9] | +3% / 69% | same | same | same |
| pull liquidity when price outside [0.2, 0.8] | +39% / 41% | same | same | same |
| fee 10% on swaps that move the price toward 0 or 1 | +39% / 100% | +35% / 85% | +24% / 83% | +8% / 81% |
| close at T + pull outside [0.1, 0.9] + 10% toward 0/1 | +37% / 65% | +37% / 64% | +28% / 63% | +13% / 61% |
| dynamic pm-AMM style: liquidity × √(time left), close at T | +34% / 64% | same | same | same |
| oracle (not ex ante): drop every swap that made money | +202% / 36% | | | |

Out of sample (each family's parameter chosen on the 52 markets that started first, under walk e=3, applied to the
other 52, which carry $98,372 of the loss):

| family | chosen | test: loss cut / volume kept |
|---|---|---|
| flat fee | 20% | +36% / 56% |
| close at endOfTrading | | +8% / 93% |
| pull before endOfTrading | 72 h | +55% / 58% |
| fee near endOfTrading | 10% in last 72 h | +11% / 87% |
| fee on recent move | 2 × \|move 24 h\| | +22% / 74% |
| price band pull | [0.2, 0.8] | +33% / 43% |
| fee toward 0/1 | 20% | +34% / 69% |
| dynamic pm-AMM style | | +32% / 65% |
| combination above | 10% | +27% / 61% |

A flat 20% fee does about as well out of sample as any rule that uses market information. For LPs to break even
with a flat fee: 16.4% if no one reacts, 19.1% (keeping 73% of the volume) if only informed traders walk away,
95.5% (24% kept) with e=3, never with e=10.

**2. What predicts the loss (`results/features.txt`).** Per swap, loss/volume is the swapper's edge at the outcome.

- **Direction is the strongest ex-ante signal.** Swaps that push the price toward 0 or 1 are 64% of the volume and
  120% of the loss (edge 0.31); swaps toward 0.5 are 36% of the volume and earn LPs 20% of it back (edge −0.09).
  Trading with the 24 h move: Spearman +0.33 with edge.
- **Price level, but not where the band rule assumes.** Swaps at a price of 0.1–0.3 are 10% of the volume and 47% of
  the loss (edge 0.74); 0.3–0.7: 28% / 40%. Near the edges LPs earn: above 0.9 is 28% of the volume and −0.6% of the
  loss, below 0.05 is −2%. So pulling liquidity outside [0.1, 0.9] removes 31% of the volume and 3% of the loss.
  Spearman of price with edge −0.36, the largest single correlation. Out of sample, the price bucket alone puts 43% of
  the test loss in the 20% of volume it ranks worst.
- **Time to resolution, weakly.** 6–24 h before resolution was proposed: 14% of the volume, 27% of the loss (edge 0.31);
  3–7 days: 47% / 26%; but more than 7 days out: 13% / 21% (edge 0.27). Spearman +0.03. Out of sample the time bucket
  puts 39% of the test loss in the worst 20% of volume (45% against endOfTrading). The last 6 h before endOfTrading:
  1.6% of the volume, 0.8% of the loss.
- **Recent moves, market type, size, idle time: little.** |move 6 h| and |move 24 h| do not rank swaps out of sample
  (18% and 27% of the loss in the worst 20%, against 20% at random). By type, hack and weekly-revenue markets have edges
  0.23 and 0.19 against 0.04–0.08 for price and other questions, but out of sample type alone ranks swaps at 25%.
  Swaps after a pool sat idle for more than 24 h: edge 0.34 on 5% of the volume.
- **Per market (n=104)**, loss in dollars follows volume (Spearman +0.66); loss/volume follows volume-weighted
  distance from 0/1 (+0.35) and |move 24 h| (+0.32), not hours to resolution (−0.01).

**3. Other prediction-market AMMs: no live one prices with these signals.** A name search (2026-11-21) found
time- or price-dependent liquidity only on paper or in unaudited prototypes, with no LP numbers. The live venues
charge a flat fee or adjust depth by inventory or volume. Most rows come from docs and secondary pages, not contracts.

| design / venue | uses time / price level / recent moves? | status, numbers |
|---|---|---|
| Paradigm pm-AMM (Moallemi & Robinson, 2024-11) | dynamic version: liquidity ∝ √(time left) so that expected loss per unit time is flat; static version: deeper near 0.5 | paper ([paradigm.xyz/2024/11/pm-amm](https://www.paradigm.xyz/2024/11/pm-amm)) |
| Mattdgn/pm-amm (Solana) | L = L0·√(T−t), price-dependent | devnet code, 0% fee, simulations only ([github](https://github.com/Mattdgn/pm-amm)) |
| Orbswap Prediction (v4 hook, ETHGlobal hackathon) | invariant x^(1−P)·y^P = k, P set by the LP; no fee logic stated | hackathon ([showcase](https://ethglobal.com/showcase/orbswap-prediction-hyxb2)) |
| Trueo TruthMarketHook (Base) | no: one admin-set fee rate per hook | live; this sample: hook fee 0.85% of volume, loss 16.4% |
| XO Market, Precog | no: LS-LMSR, depth grows with volume | live; Precog TVL about $2.3K (DefiLlama) |
| Seer (outcome tokens on Swapr / Uniswap v3) | only the LP's chosen range; fixed fee tier | live |
| Limitless | no: flat 0.40% on AMM markets, the core is a CLOB | live; about $3K fees in 30 days (DefiLlama) |
| Overtime / Thales | quotes only between 5% and 95% (Thales positional 10–90%); inventory skew; odds from an outside feed | live |
| Polymarket (FPMM), Context Markets | AMMs retired for order books | — |
| Azuro, Drift BET, PNP, Sapience, Myriad, Hedgehog | no sign of these signals in docs | live or not found |
| v4 dynamic-fee hooks (Bunni, Arrakis, OpenZeppelin BaseDynamicFee) on outcome tokens | none found | — |

On LP results, the one source we found is a TUM master's thesis on Polymarket's AMM era (Singh, 2025-09). It finds
that realized impermanent loss eroded most LP profit, that LPs withdrew before resolution, and that CLOB market
making paid better. We read only the abstract. Papers seen only in search results and not checked: a uniform-loss
AMM (arXiv 2607.17428), fees for a prediction-market AMM (2307.08768), and a survey noting that pm-AMM's taper does
not handle jumps or early resolution (2510.15612).

We searched for: Paradigm pm-AMM and its implementations; "pm-AMM" with "Uniswap v4 hook"; TruthMarketHook /
Truemarkets fees; XO Market; Seer; Context Markets; Limitless; Myriad; PNP Exchange; Azuro; Overtime / Thales (AMM
skew, positional markets); Precog; Sapience / Foil; Drift BET; Hedgehog; "prediction market AMM fee near
resolution / dynamic fee outcome token hook"; and logit / LMSR time-decay papers. Not checked: Kalshi on-chain
(DFlow) and Gnosis Omen's FPMM.

**So:** information about the market narrows the leak but does not close it. Out of sample, the best rules cut a
third to a half of the loss (pull 72 h before the end: 55%) and lose 30–45% of the volume. A flat 20% fee does about
as well, so the features add little over a blunt fee. Even a filter that knew the outcome would have to drop 64% of
the volume.
The strongest signal, a swap's direction (toward 0/1), is one a pool sees, but a 20% fee on it still keeps only 69%
of the volume for a 34% cut.

## How it is measured

- Sample, valuation and loss are the parent study's: each swap's TYD and outcome-token amounts valued at the final
  outcome (both sides at 0.5 for the four markets with `winningPosition` 3); summed, that is what the pool lost
  against holding. Pool price comes from each `Swap`'s `sqrtPriceX96` (before a swap = the pool's previous price, or
  `Initialize`); every swap's execution price lies between its before and after price.
- Features use only what was known when the swap happened: hours to endOfTrading and to resolution proposed (the
  proposal time is known only afterwards, so only endOfTrading-based rules are replayed), the pool's price before the
  swap, its change over the previous 1/6/24 h, swap size and direction, hours since the pool last traded, and the
  market type from the question text (hack-this-week 16, revenue-this-week 15, monthly metric 15, price 19, other 39).
- Replay: every swap keeps its size and price; there are no path effects (a higher fee or thinner pool would move
  later prices and sizes). An extra fee is a fraction of the TYD leg and goes to LPs (the hook's existing 0.85% goes
  to Trueo, not LPs, and is left as it was). "Pull" removes the swap. The pm-AMM line scales each swap's size and
  loss by √(hours to endOfTrading / hours from the market's first swap to endOfTrading), a crude stand-in.
- Reaction (assumed, not measured): *no one reacts*: every swap still happens and pays. *Walk, e*: a swap that made
  money at the outcome happens only if its edge exceeds the fee; a swap that lost money happens with probability
  exp(−e × fee) (e=3: a 10% fee keeps 74% of that volume; e=10: 37%). Losing swaps are what pays LPs, so with high e
  a fee can make LPs worse off.

## Limits

- One venue, ten weeks, 104 markets; the 20 that lost most carry 89% of the loss and 50 swaps carry 56% of it, so
  every bucket rests on a few dozen trades. The out-of-sample split is one split, and the test half holds 78% of the loss.
- "Informed" is defined after the fact (made money at the outcome). The walk model lets such traders know their
  realized edge, which flatters fee rules for LPs at e=0 and is an assumption throughout.
- Volume kept is mechanical, not an estimate of demand; in particular the pull rules assume no one trades elsewhere
  in the pool (Trueo's OrderManager limit orders sit in the same pools and are not split out).
- The YES and NO pools of a market are replayed separately, though arbitrage links them.
