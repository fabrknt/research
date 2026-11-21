# How far does a stock move over the weekend, and how much of it does Hyperliquid see first? (2026-11-21, recording)

A lender that takes tokenized stocks as collateral has to choose a haircut for the weekend, when the
stock market is shut but the token, and Hyperliquid's HIP-3 perps on trade.xyz, keep trading. This
records, for 22 US names (SP500, XYZ100 and 20 single stocks), how far the price moves from Friday's
close to Monday's open, and how far xyz's price still is from the open on Sunday at 20:00 UTC, on
Monday at 07:00 UTC and an hour before the open.

```
python3 -I weekend.py     # every weekend still in reach -> results/weekends.csv (about 30 s)
```

**Status: recording, every weekday at 16:00 UTC (`.github/workflows/weekend-gaps.yml`).** Hyperliquid
serves only the latest 5,000 candles (about 52 days at 15 minutes), so the committed file is the
record; a run adds only the weekends it doesn't have yet. It starts with the seven weekends from
2026-10-02 to 2026-11-13 (154 rows).

Columns, all in bp: `gap_bp` = open ÷ close − 1; `err_<point>_bp` = open ÷ xyz's price at that point − 1,
so 0 means xyz had already found the open. No prices are written (they are third-party API data).

First seven weekends, |value| over the 154 rows:

| | median | p90 | max |
|---|---|---|---|
| gap, Friday close → open | 129 | 498 | 730 |
| still to go at Sunday 20:00 UTC | 107 | 475 | 1,024 |
| still to go at Monday 07:00 UTC | 106 | 340 | 694 |
| still to go an hour before the open | 91 | 279 | 486 |

Definitions and limits:

- "Close" is xyz's price at 16:00 New York (13:00 on an early close) on the last trading day before the weekend; "open" is xyz's
  price at 09:45 New York (the close of the first 15-minute candle), when the perp has the real market
  to follow. Both are xyz's prices, not the exchange's prints, and the open includes the first 15 minutes
  of trading, which is part of what is still to go an hour before.
- Full-day NYSE closures on a Friday or a Monday, and the Fridays that close at 13:00, are listed in
  `weekend.py` up to 2027.
- 15-minute candles: each point is the close of the candle that ends there.
