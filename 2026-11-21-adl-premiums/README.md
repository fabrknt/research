# What would a cover against Hyperliquid's auto-deleveraging have paid out? (2026-11-21)

When a liquidation can't be absorbed, Hyperliquid auto-deleverages (ADL): it closes profitable
positions on the other side at the liquidated trader's price. We found no cover sold for this
(searched 2026-11-20). This counts the ADL fills in Hyperliquid's own fills archive from
2025-05-25 to 2026-11-20 and models what a simple cover would have paid: when a position is ADL'd,
pay what it costs to re-open it five minutes later.

```
./scan.sh                                        # every hourly fills file -> ~/out/*.csv, ADL fills only
cat ~/out/*.csv > all_adl.csv
python3 -I analyze.py all_adl.csv CTX_DIR results   # CTX_DIR: asset_ctxs/*.csv.lz4 from 20250525
```

**Answer: on the main dex it is catastrophe cover. Over these 18 months the modelled payouts come
to 38 bp a year of position notional, and without 2025-10-10 to 1.4 bp. On the HIP-3 dexes ADL is
routine (95 days, against 20 on the main dex) but small: the same cover would have paid $1.39M in
the 0.95 years since the first HIP-3 ADL, $1.12M of it on xyz, and more than half on one night
(xyz:EWZ, 2026-10-26, shorts closed at a price that had not moved since the weekend).**

## What was found

44,816 ADL fills, $2.37B of positions closed, on 113 days, across 264 coins (168 main dex, 96 HIP-3).

| | ADL'd notional | share |
|---|---|---|
| 2025-10-10 (162 coins, 19,351 accounts, 21:16–21:42 UTC) | $2.10B | 89% |
| 2025-08-26 (XPL's first days) | $123M | 5% |
| every other day | $143M | 6% |

**The cost comes in the first minutes.** On 10-10 nearly every ADL'd dollar was a short closed near
the bottom. Against the first mark 5–6 minutes later, re-opening cost them 3.0% of notional on
average, gains and losses netted (6.2% counting only the moves that cost them, 3.9% with the 20%
cap). An hour later the same comparison is −12.7%: prices had come back, so ADL had saved them
money. The cover worth pricing is the re-hedge window, not the lost upside.

**What the cover pays per ADL'd dollar depends on the coin**: BTC 0.05%, ETH 0.20%, SOL 3.4%, HYPE
5.2%, and 10–19% for small coins such as PUMP, FARTCOIN, LINK and IP, whose ADL price was far
from where the market traded minutes later.

**Modelled payouts per year, per dollar of position** (both sides of open interest, over all 235
main-dex coins with marks, 168 of which had an ADL): **38.0 bp/year in total; 1.4 bp/year without
2025-10-10.** For most coins every dollar of ADL is on 10-10, so their number is that one day spread
over 18 months. The coins with ADL on other days were small or newly listed (XPL at launch, POPCAT
on 2025-11-12).

HIP-3 dexes (no HLP behind them, so ADL comes first): $90M on 95 days, xyz on 52 of them, then hyna
14, vntl 14, para 11, km 9, flx 8, cash 6, io 2. Biggest: xyz:BRENTOIL on 2026-03-23 ($33.2M),
xyz:SKHX (SK hynix) on 2026-07-27 ($25.4M), xyz:EWZ on 2026-10-26 ($7.7M).

## HIP-3 (added the same day)

`asset_ctxs` has no HIP-3 coins, so the price after the window is the first fill that is not an ADL
5–8 minutes later, read from the same fills archive (`fetch_hip3.sh`: the 145 hourly files with a
HIP-3 ADL and the hour after, ~5 GB streamed). Taking the median of the fills in that window
instead changes the total by 0.3% ($1,386k → $1,382k).

| dex | ADL days | ADL'd notional | modelled payout | per ADL'd dollar |
|---|---|---|---|---|
| xyz | 52 | $85.2M | $1,119k | 1.3% |
| para | 11 | $1.45M | $136k | 9.4% |
| flx | 8 | $2.65M | $98k | 3.7% |
| vntl | 14 | $0.30M | $29k | 12.1% |
| hyna, cash, io, km | 31 | $0.68M | $4k | |

**The large ADLs cost little; the costly one was a stale price.** xyz:BRENTOIL (2026-03-23, $33.2M)
and xyz:SKHX (2026-07-27, $25.4M) would have paid 0.1% and 0.2%. xyz:EWZ paid $782k, 56% of all
HIP-3 payouts: on Sunday 2026-10-25 from 23:17 UTC xyz traded at 40.456 with no change, at 00:05
UTC $7.6M of shorts were ADL'd at up to that price, and five minutes later EWZ traded at 34.2. The
cover worth pricing on HIP-3 is the gap when a closed market's price catches up, which is what
[weekend gaps](../2026-11-21-weekend-gaps/) records.

Rate: there is no open-interest history for HIP-3 here, so `results/hip3_by_dex.csv` divides by
today's (2026-11-21): 1.4 bp/year on xyz ($1.18M a year over $8.3B of insured notional, both sides).
Open interest was smaller for most of the period, so this understates the historical rate.


- `results/by_day_coin.csv`: per day and coin, ADL fills and notional, the short share, the first and
  last ADL time, then the notional with a mark after the window and, over it, the netted move, the
  moves that cost the position, the capped payout, and the netted move an hour later (all in USD).
  The dollar figures and percentages above are sums over these rows.
- `results/by_day.csv`: per day, fills, notional, coins and accounts (the account counts above).
- `results/by_coin.csv`: per main-dex coin with marks, exposure in dollar-years with and without
  2025-10-10, ADL notional, payout with and without that day, and both as bp/year. The `ALL` row
  is the total.
- `results/hip3_by_day_coin.csv`, `results/hip3_by_dex.csv`, `results/hip3_run.txt`: the HIP-3
  version (`hip3.py`), same columns where they apply.
- `results/run.txt`: input range and how late the marks were after each fill (min, median, p99,
  max: all between 5:00 and 6:00).
- `results/inventory.txt`: the archive listing (object counts and bytes).
- No addresses or individual fills are committed.

## Definitions and limits

- **Source**: Hyperliquid's own archive, `s3://hl-mainnet-node-data/node_fills` (2025-05-25 to
  07-27) and `node_fills_by_block` (from 2025-07-27): 13,070 hourly files when scanned, about
  385 GB (`results/inventory.txt`, listed a little later, has one more hour).
  Fills with `dir = "Auto-Deleveraging"`. Marks and open interest:
  `s3://hyperliquid-archive/asset_ctxs`, main dex only. Both buckets are requester-pays, so unlike
  the rest of this repo this needs an AWS account. We ran the scan on an EC2 instance in
  ap-northeast-1, the fills bucket's region, so nothing left the region; downloading the files
  instead would cost about $35 in transfer (385 GB at $0.09/GB, AWS's first-tier internet price).
- **Payout**: the move in the position's favour from the ADL price to the first mark at least 5
  minutes later (a short closed at 100 with the mark at 90 is paid 10%), floored at 0, capped at
  20% of notional. A fill with no mark within 8 minutes is left unpriced; on the main dex none was.
  No deductible, no load, no cost of capital: a seller would charge more.
- **Exposure**: either side can buy the cover, so the insured notional is 2 × open interest × mark,
  integrated over time (each 1-minute row counts until the next, at most 10 minutes, split at UTC
  midnight so a day can be left out exactly). The bp/year
  figures are historical payouts over that exposure, not a forward price.
- **One catastrophe**: 18 months with one systemic day. The numbers say "one 10-10 in 18 months";
  they can't tell whether that is once a year or once a decade. Per-coin numbers for coins with one or
  two ADL days are not estimates of a steady rate.
- **HIP-3 prices come from fills**: the next trade, not a mark; a thin market's next trade can be far
  from where size could be re-hedged. No open-interest history, so no historical rate.
- **What the run did not check**: the scan behind these results did not set `pipefail`, so a failed
  download would have looked like an hour without ADL. No file reported a failure; `scan.sh` now
  fails loudly and writes `DONE` only when every file has an output.
