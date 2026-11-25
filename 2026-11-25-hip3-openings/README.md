# How does a new Hyperliquid listing trade in its first hour? (2026-11-25, 3 openings)

The [listing precursors](../2026-11-22-listing-precursors/) study found HIP-3 names registered halted
hours to weeks before they trade. This asks what the opening itself looks like: is the book off the
oracle, by how much, and could anyone trade against it?

**Status: 3 openings, too few to judge. Re-run as the 14 names still halted open.**

## Lead time (registration to first trade)

From the recorder's `hl_ctx` (each minute, every dex) and `events` triggers, 2026-11-21 04:12 to 11-25 10:25 UTC.

| Name | Registered (seen halted) | Opened | Lead |
|---|---|---|---|
| xyz:SOXS | 11-23 03:05 | 11-24 15:17 | 36 h |
| xyz:TQQQ | 11-24 12:08 | 11-24 16:31 | 4.4 h |
| io:GOOGL | before 11-21 04:12 | 11-24 15:43 | ≥ 3.5 d |
| io:SOXL | 11-21 23:52 | not yet | ≥ 3.4 d |
| 13 xyz names (SMCI, SNOW, CATL, TENCENT, …) | before 11-21 04:12 | not yet | ≥ 4 d |

The deployer set the open-interest cap and funding multiplier while still halted 5–13 min before SOXS
opened and 85 min before TQQQ. Both opened during US market hours.

## The opening (books every 10 s against the minute oracle)

`crossable` = notional an order could take at a price better than the oracle by more than 10 bp (fee and
slippage assumed). `near` = book notional within 50 bp of the mid.

| | xyz:SOXS | xyz:TQQQ | io:GOOGL |
|---|---|---|---|
| Spread, first 5 min (median) | 420 bp | 490 bp | 10 bp |
| \|mid − oracle\|, first 30 min (median) | 36–68 bp | 63–106 bp | 5–9 bp |
| \|mid − oracle\| max | 495 bp | 469 bp | 84 bp |
| Crossable, first 5 min (max) | $24 | $14 | median $0 |
| Crossable, first 30 min (max) | $3.8K | $20K | $20K |
| Near the mid, each side | ~$0 | $0 | $67–70K |
| Volume, first 30 min | ~$16K | ~$23K | ~$29K |

- On the two xyz names the price looks far off, but the book is empty: there is almost nothing to take at
  the off price. Betting on the gap closing has no size.
- io:GOOGL had a market maker quoting from the first second (10 bp spread). Whether a maker is ready
  decides what the opening looks like.
- Quoting the xyz openings would have met about $20K of volume in 30 min: a few hundred dollars of spread
  at best.

A gap in the data: until [66f4407](../recorder/sources/events.py) listings shared the 8 hot slots with big
moves and were pushed out (SOXS 30 min–6 h, TQQQ after 6 h are missing). Listings now have their own slots.

## Re-run

```
python3 -I 2026-11-25-hip3-openings/open_gap.py --from 2026-11-24 --to 2026-11-26 xyz:SOXS xyz:TQQQ io:GOOGL
```

Needs the recorder's private key (see [recorder](../recorder/)).
