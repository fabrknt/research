# Is one dealer's quote dearer than an order book? (2026-11-16, collecting)

Variational's Omni has one market maker (OLP) quoting every trade, with no fee: the spread is the price.
Lighter and Hyperliquid are order books. This study asks what a market order of $1k, $100k and $1M
costs on each, for the same markets, in US market hours, outside them and at weekends.

**Status: collecting since 2026-11-16 08:48 UTC (every 5 minutes, with no end date since 2026-11-21). Weekday results
so far below; no weekend yet.** From 2026-11-16 13:00 UTC the collection runs on GitHub Actions
(`.github/workflows/one-quote-collect.yml`), so a laptop going to sleep doesn't stop it: each job
collects for an hour and then starts the next one itself (GitHub's hourly schedule fired once in the
first ten hours, so it is only the backup). The snapshots are third-party API data, so each hour's are
encrypted to `.github/one-quote-data.pub.pem` before they are kept, as a workflow artifact (90 days)
and in a release per month (`one-quote-data-YYYYMM`, kept); `fetch_actions.sh` downloads and decrypts
them with the private key, which is kept off GitHub. Variational keeps no public history of its quotes,
so the record only exists if it keeps running; set the repo variable `ONE_QUOTE_STOP=1` to stop it.
The first answer goes here and on [fabrknt.com/research](https://fabrknt.com/research) once the data
covers a weekend.

Gaps: 2026-11-16 14:02–22:50 UTC (the schedule did not fire) and 2026-11-17 08:40–14:16 UTC (a 429
from Variational at start-up failed a job and the next was never started; fixed so a failed hour still
keeps its data and starts the next).

## Results so far (weekdays, 2026-11-16 08:47 – 11-18 07:58 UTC)

356 rounds, 15,529 market-rounds (`results/interim-20261118.txt`). Median cost of a market order in bp
of mid, taker fee included, over the rounds where all three venues filled the size; the last column is
how often each venue was cheapest.

| group | session | size | Variational | Lighter | Hyperliquid | cheapest |
|---|---|---|---|---|---|---|
| crypto | US open | $1k | 3.89 | **1.47** | 5.22 | Lighter 88% |
| crypto | US open | $1M | 9.89 | **7.96** | 9.65 | Lighter 67% |
| crypto | US closed | $1M | 9.76 | **7.57** | 9.53 | Lighter 80% |
| stock | US open | $100k | 6.71 | 3.61 | **2.45** | Hyperliquid 67% |
| stock | US open | $1M | 16.89 | 18.09 | **4.28** | Hyperliquid 100% (n=44) |
| stock | US closed | $100k | 7.12 | **2.80** | 3.52 | Lighter 67% |
| stock | US closed | $1M | 21.65 | 22.35 | **7.18** | Hyperliquid 97% (n=196) |
| index/commodity | US open | $1M | **1.50** | 4.36 | 3.17 | Variational 59% |
| index/commodity | US closed | $1M | **2.44** | 4.26 | 3.20 | Variational 62% |

- Crypto: Lighter (no taker fee) is cheapest at every size and session.
- Stocks: from $100k up in US hours, Hyperliquid's HIP-3 books are cheapest; one dealer's quote is
  the dearest or close to it at $1M.
- One dealer's quote wins only at $1M on indices and commodities (gold, oil, S&P), where it can hedge
  on deep outside markets. The weekend, when those markets close, tests that reading.

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
python3 collect.py 2880 300          # 10 days, every 5 minutes, on this machine
cd walk && cargo build --release && cd ..
sh fetch_actions.sh                  # the hourly Actions runs, from releases and artifacts (needs the private key)
cat data/snap-*.jsonl data/actions/*/data/snap-*.jsonl | walk/target/release/walk > data/walks.jsonl
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
