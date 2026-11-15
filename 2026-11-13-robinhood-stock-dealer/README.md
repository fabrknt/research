# Can a dealer quote Robinhood Chain's stocks? (2026-11-13)

Every Uniswap v4 swap on Robinhood Chain (chain 4663) in pools holding one of nine stock tokens, read
from the public RPC, then replayed against a dealer that quotes Hyperliquid's HIP-3 price ± s bp and
hedges there. Nothing was deployed.

```
python3 find_pools.py      # v4 pools holding one of the nine stocks (Initialize events) -> data/pools.json
python3 symbols.py         # the tokens most often on the other side
#   from pools.json, keep stock×USDG and stock×stock pools in data/pools_sel.json (561 pools)
python3 fetch_swaps.py     # the Swap events over the 17 days with HL 5-minute candles -> data/swaps.json
python3 fetch_candles.py   # HIP-3 candles (HL keeps the latest 5,000)
python3 analyze.py 5       # passive LP vs dealer, hedge cost 5 bp -> data/result.json
python3 summary.py 300     # by session and stock, priced 300 s later
python3 extras.py          # inventory and hooked-pool share
SET=other python3 analyze.py 5   # the single-stock/SPY pools
```

Our outputs are in `results/` (the scripts write to `data/`, which is not committed).

## Results (2026-10-27 to 11-13, v4 only)

- The nine stocks' stock×USDG and stock×stock pools traded $274M in 17 days (about $16M a day).
- 93% of the volume went through pools with no hook; most fees are 1–5 bp.
- Passive LPs, fees included: −1.8 bp priced 5 minutes later, −3.2 bp an hour later.
- A dealer at HL ± s beats the pool on 6% of the volume at s = 20 bp, 3% at s = 30 bp.
- In US market hours the dealer loses (s = 20: −9.6 bp an hour later); overnight it wins (+11 bp).
  Weekends trade $1.4M a day.
- Users were net sellers over the 17 days (NVDA −$0.84M): stock tokens cannot be redeemed, so a dealer would pile them up.
- **Single-stock/SPY pools** (AMD, MU, HIMS, TSM, INTC, PLTR; 17 pools, 7 days, $29M): where the dealer
  beats the pool, it loses an hour later: s = 10 −17.9 bp, s = 20 −15.3 bp, s = 30 −10.1 bp. The HIP-3
  price is slower than the pool, so the dealer fills the trades where the pool was right. Only MU and
  weekends were positive.
- By direction (`results/analyze_dir.txt`): swaps that move the pool toward the HL price cost LPs −7.8 bp,
  swaps that move it away earn them +8.1 bp.

Limits: the reference is 1- and 5-minute candles (a few bp of noise); the dealer is assumed to take only the
orders where it quotes better, without modelling routing or order splitting; v4 only; 17 days.
