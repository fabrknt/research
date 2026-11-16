# Is one dealer's quote dearer than an order book? (2026-11-16, collecting)

Variational's Omni has one market maker (OLP) quoting every trade, with no fee: the spread is the price.
Lighter and Hyperliquid are order books. This study asks what a market order of $1k, $100k and $1M
costs on each, for the same markets, in US market hours, outside them and at weekends.

**Status: collecting since 2026-11-16 08:48 UTC (every 5 minutes, 10 days). No results yet.** From
2026-11-16 13:00 UTC the collection runs hourly on GitHub Actions (`.github/workflows/one-quote-collect.yml`),
so a laptop going to sleep doesn't stop it. The snapshots are third-party API data, so each hour's are
encrypted to `.github/one-quote-data.pub.pem` before they are kept as a workflow artifact;
`fetch_actions.sh` downloads and decrypts them with the private key, which is kept off GitHub. The
answer goes here and on [fabrknt.com/research](https://fabrknt.com/research) once the window covers
US market hours and a weekend.

## What is read (public APIs, no keys)

| venue | endpoint | what |
|---|---|---|
| Variational | `GET /metadata/v2/stats` | bid/ask at the minimum size, $1k, $100k and $1M (large markets only), per market |
| Lighter | `GET /api/v1/orderBookOrders?limit=250` | resting orders, up to 250 a side |
| Hyperliquid | `POST /info` `l2Book` | 20 levels a side, at full precision and at `nSigFigs: 4` |

The 40 busiest Variational markets that also trade on Lighter or Hyperliquid (HIP-3 dexes included,
the busiest one per name), in `data/markets.json`.

## Run

```
python3 collect.py 1                 # one round -> data/snap-YYYYMMDD.jsonl, data/markets.json
python3 collect.py 2880 300          # 10 days, every 5 minutes
cd walk && cargo build --release && cd ..
cat data/snap-*.jsonl | walk/target/release/walk > data/walks.jsonl
python3 summary.py
python3 check_coarse.py              # is Hyperliquid's coarser book an upper bound?
```

From a fresh clone, one round, the build and both reports take about a minute (2026-11-16).

`walk` loads each saved book into [`rdk-clob`](https://github.com/psyto/rdk) and prices the market
orders with `Book::quote_market` (pinned by git rev; rdk is not on crates.io yet).

## Method

- Cost of a size = half the round trip, in bp of a reference mid, plus the taker fee:
  `((buy − ref) + (ref − sell)) / 2 / ref + fee`. `ref` is the median of the venues' mids in that
  round; a venue more than 1% away is a different instrument (Variational's `US500-PERP` is
  ETF-sized, not the index) and is dropped for that round.
- Medians are over the rounds where every venue compared quoted or filled the size.
- Variational quotes older than 120 s are dropped (its docs say quotes may be cached up to 600 s).
- When Hyperliquid's 20 levels cannot fill a size, the 4-significant-figure book is walked instead.
- Taker fees (checked 2026-11-16): Variational 0 ([docs](https://docs.variational.io/omni/trading/fees));
  Lighter 0 (`taker_fee` in `/api/v1/orderBooks`, standard account); Hyperliquid 4.5 bp on its own
  perps (base tier), 0.9 bp on HIP-3 markets in growth mode.

## Limits

- Lighter's 250 orders and Hyperliquid's 20 levels may not reach $1M; such rounds are counted and
  left out of the medians, which favours the deeper moments.
- Hyperliquid's 4-significant-figure book is an upper bound: on the 1,026 size-rounds that both books
  filled (2026-11-16, first 14 rounds), it was never cheaper than the full-precision walk, and dearer
  by a median of 1.0 bp (max 8.8 bp; `check_coarse.py`, `results/coarse-check-20261116.txt`).
  Rounds that fall back to it overstate Hyperliquid's cost.
- A quote is not a fill: Variational can re-quote (last look), and Lighter's standard accounts have
  a taker delay. Neither is modelled.
- Snapshots of the three venues are taken a few seconds apart.
