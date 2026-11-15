# Do LPs win when a stock is quoted in SPY? (2026-11-11)

On Robinhood Chain, many stock tokens trade against SPY instead of a dollar. For each pool we read
every swap from the public RPC (`rpc.mainnet.chain.robinhood.com`), took the fees actually paid, and
estimated loss-versus-rebalancing (LVR) from the pool's own price path (Milionis et al., for
concentrated liquidity in range; see `analyze.py`).

```
bash fetch_all.sh                                   # swaps of the 23 pools -> data/swaps/
python3 -I blocktimes.py data/blocktimes.json       # block -> time
python3 -I analyze.py data 1786060800 1794355200 1  # 2026-08-03 .. 11-11, 1 h buckets
```

Not reproducible end to end yet: `analyze.py` also reads `data/pools.json` (each pool's name, tokens and
fee tier), which was not kept. The pool ids are the ones in `fetch_all.sh`; the token and fee of each are in
its `Initialize` event. Committed outputs: `out_aug3_1h.txt` (the numbers below), `out_aug3_4h.txt`, `out_aug3_24h.txt`, and the
same from 2026-09-28 (`out_sep28_*`, when the newer pools opened).

## Results (1 h buckets, 2026-08-03 to 11-11)

- The nine single-stock/SPY pools: $419M volume, $183K fees to LPs, about $370K LVR. Fees ÷ LVR is
  0.29 to 0.71 for every one of them.
- The same stocks quoted in USDG: 0.88 to 3.72, and each stock's best USDG pool beats its SPY pools.
- At the same 0.05% fee, NVDA/SPY 0.66 against NVDA/USDG 1.15.
- QQQ/SPY wins (1.53): the two move together, so little variance is left to lose to.
- Quoting a single stock in SPY removes less variance than one might hope (daily, `yahoo_vol.py`: 9–43%);
  the fee tiers on SPY pools (0.025–0.05%) are too low for what is left.

Limits: LVR is a model; no TVL history; about 100 days (44 for the pools opened 2026-09-28); other DEXes excluded.
`yahoo_vol.py` reads Yahoo's public daily closes; its output is not committed.
