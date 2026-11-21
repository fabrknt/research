# What do LPs lose before a prediction market resolves? Trueo on Base (2026-11-21)

Trueo (formerly Truemarkets) runs each YES and NO outcome as a Uniswap v4 pool against TYD (True Yield
Dollar, 6 decimals) on Base, through its `TruthMarketHook`. We read every swap and liquidity change of
those pools from Base's public RPC (`base-rpc.publicnode.com`), blocks 51,020,000 (2026-09-08) to
60,197,443 (2026-11-21), and valued each pool's flows at the final outcome.

```
python3 -I hooks.py              # the five hooks' logs (FeeCollected) -> data/hook_logs.json
python3 -I pools.py 60197443     # pools initialized against TYD through those hooks -> data/pools.json (480)
python3 -I pm_logs.py 60197443   # their Swap/ModifyLiquidity/Initialize from the PoolManager (about 15 min)
python3 -I markets.py            # pool -> outcome token -> market; each market's current state (needs `cast`)
python3 -I analyze.py            # loss vs fees per market, timed against endOfTrading
python3 -I timing.py             # the same loss timed against when resolution was proposed
python3 -I checks.py             # quote token, fee rate, swaps after endOfTrading, who adds liquidity
```

Committed: `results/pools.txt`, `results/analyze.txt`, `results/timing.txt`, `results/checks.txt` and `results/markets.json`
(one row per resolved market). The logs (`data/`, about 60 MB) are not committed; the scripts fetch them again.

## How it is measured

- Pools: every `Initialize` in the window with TYD as one currency and a TruthMarketHook as the hook (480;
  6 more TYD pools use other hooks or none). Markets: those finalized (status 7, the only status with
  `finalizedAt` set). That is 104 markets, each with both its YES and its NO pool, endOfTrading 2026-09-11 to 11-17.
- A YES token is worth 1 TYD if YES won, 0 if not. Four markets have `winningPosition` 3; we value both
  sides at 0.5 there, our assumption. Each swap's TYD and token amounts, valued that way, are what the
  swapper took out of the pool. Summed over a market, that is what the pool's liquidity lost against simply
  holding what it put in: net flows valued at the outcome, not a model of adverse selection.
- The LP fee is estimated as each swap's TYD leg times the fee in its `Swap` event (1 pip in every pool).
  The hook's fee (`FeeCollected`) is minted to Trueo's fee collector (`TruthMarketHook.sol`, verified on
  Sourcify), not credited to LPs. Fees charged in outcome tokens are valued at the outcome.

## Results

- Loss against holding: $126,558 on $773,361 of volume (16.4%).
- LP fees: an estimated $0.77. The hook's fees, valued at the outcome, came to $6,576 (0.85% of volume);
  the loss is 19.24 times that. Had all of it gone to LPs, with the same trades, it would have covered 5.2%.
- Swaps keep going after endOfTrading: 1,022 of them, a median 100 h after it, 818 before resolution was
  proposed. So we also time the loss against the proposal (a median 24 h after endOfTrading):
  4.2% of it in the last hour before, 5.5% in the last 6 h, 32.3% in 24 h, 53.4% in 72 h, 79.4% in 7 days.
- In 28 of the 30 markets that lost most, the LP positions (not the limit orders) held less than 5% of their
  peak liquidity when resolution was proposed (raw v4 liquidity units, summed over the market's two pools in time order).
- The 20 markets that lost most carry 89% of the loss. The median loss per market is $27; the median volume is $209.

## Limits

- The loss is the pool's: LP positions and the limit orders Trueo's OrderManager places in the same pool
  (10% of the liquidity added). We don't split the two, so we can't say which positions lost what, or when they left.
- 90% of the liquidity comes through Uniswap's PositionManager (7,848 positions). We didn't check who owns them,
  so we can't say whether they are outside LPs or Trueo's own.
- The timing uses when resolution was proposed, not when the answer became known.
- Markets whose pools were created before 2026-09-08 are left out. About ten weeks, one venue; the markets are
  mostly weekly crypto questions (revenue, hacks), where the answer comes out over days.
