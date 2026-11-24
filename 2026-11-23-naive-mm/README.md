# Does a last-trade market maker survive a real flow? (2026-11-23)

A post shared on Japanese X in 2026-11 (pasted to us as text; we have no link, so we make no claim about
what it reports) describes a short market-maker script. We take only the strategy it describes. It does
not predict prices: it takes the last
trade as the fair price, rests a bid a little below and an ask a little above, and after every trade
cancels both and quotes again. We ran that strategy, as the post describes it, on two markets with the
same exchange, the same quote size and the same rules: a simulated market of random bots, and Elysium's HYPE/USDC
flow next to Hyperliquid.

```
python3 -I fetch_funding.py   # HYPE hourly funding from HyperCore's public API -> data/ (for the hedge)
cargo run --release           # about a minute to build, a second to run; writes results/
```

## Answer

**The market decides, not the code.** In the random-bot market it wins when it quotes outside the
bots' spread. On Elysium it loses in every one of the 16 settings we tried. As posted, it loses mostly
not on the fill: quoting 20 bp or more from the last trade, its fills were at or above water five minutes
later (−6.4 bp at 10 bp). What it lost was the inventory: the tape sold more HYPE than it bought ($6.08M
against $5.46M), the strategy ended long in every Elysium setting, and HYPE fell 19% over the window.

| quote 30 bp from the last trade, $500 a side | A: random bots | B: Elysium HYPE/USDC |
|---|---|---|
| P&L a day (marked to the last price) | **+$1,150** | **−$227** |
| per dollar traded | +7.6 bp | −87.1 bp |
| per dollar traded, 5 min after each fill | +7.6 bp | +3.0 bp |
| volume a day | $1.51M | $26K |
| inventory at the end | $23.2K long | $13.4K long, bought on the way down |

Where Elysium's loss comes from, quoting 10 bp from the last trade (where it fills most):

| B, 10 bp | P&L a day | 5 min after each fill | most inventory held |
|---|---|---|---|
| as posted | −$5,291 | −6.4 bp | $125.8K long |
| inventory cap (the post also suggests one): stop quoting a side past $5K | −$294 | −6.1 bp | $5.5K |
| market rule: a fee by direction, paid to the maker (below) | −$2,088 | +6.7 bp | $74.0K long |
| quote around the reference price E instead of the last trade | −$1,997 | +2.1 bp | $105.1K long |

- **The fee by direction fixes the fill, not the inventory.** It turns the 5-minute result of a fill from
  −6.4 bp to +6.7 bp, because a taker trading toward E would have paid more than it got elsewhere and is
  replayed as going elsewhere. The inventory still ends $71.9K long.
- **The inventory cap does the most** (−$5,291 to −$294 a day at 10 bp) and is still negative at every
  spread.
- **Inside the bots' spread the strategy as posted loses on the random-bot market too** (−$1,872 a day at
  10 bp): the last trade sits 20 bp or more off the hidden price, so quoting around it is quoting around
  noise. It wins at 30 bp and above. The variants that see the hidden price (the fee by direction, quoting
  around it) win at 10 bp: +$2,499 and +$2,989 a day.
- **The two variants that use E are given hindsight** (below), and still lose on Elysium in every setting.
- Every setting is in `results/summary.txt`; hourly equity at 30 bp in `results/equity_hourly.csv`;
  the hedged runs in `results/hedged.txt`.

## Hedged on HyperCore (added 2026-11-24)

**Hedged, a few settings end above zero, and the best earns tens of dollars a day.** If every fill
is offset on HyperCore's HYPE perp, most of the inventory loss is offset: quoting 10 bp from the last trade, −$5,291 a day becomes
−$212 (perp at the taker fee, 4.5 bp) or −$418 (plus 10 bp slippage). With the perp costs, 7 of the 24
hedged settings end above zero and 17 still lose; the best is +$31 a day. Perp margin and liquidation
are not modelled. Bigger quotes hardly help: $5,000 a side
instead of $500 makes at most +$38 a day.

| hedged, $500 a side, P&L a day | perp cost 4.5 bp | 14.5 bp |
|---|---|---|
| 30 bp, as posted | −$4 | −$30 |
| 30 bp, fee by direction | +$31 | +$14 |
| 50 bp, as posted | +$11 | +$3 |
| 50 bp, fee by direction | +$25 | +$20 |
| 30 bp, quote around E | −$318 | −$490 |

- **The hindsight in E was worth all of the "quote around E" result.** With E rebuilt from what is known
  at the trade (this minute's open times the median basis of earlier trades), quoting around it loses in
  every hedged setting (30 bp: −$318 a day at the 4.5 bp cost). With the hindsight E, the same runs
  made up to +$83 a day (30 bp: +$59). The fee by direction still holds with the causal E: at 30 bp,
  +$31 a day against +$38 with the hindsight one.
- The hedge trades at the open of the minute after each fill (0 to 60 s later, known only after it);
  until then it is not on the perp, and the equity path (max DD) marks the perp at the latest open
  already known. Funding is HYPE's hourly rate on HyperCore for the 76 hours that start inside the tape
  (78 fetched), mean +0.095 bp an hour, which a short collects; it adds −$2 to +$13 a day.
- "If basis closes" in `results/hedged.txt` marks the inventory at HyperCore's last price instead of
  Elysium's: it changes any row by at most $67 a day.
- Not counted: margin for the perp, the bridge to settle the inventory (the canonical withdrawal is
  about 5.5 days, a figure from [2026-11-21-elysium-direction](../2026-11-21-elysium-direction/), not
  from this replay), and the perp's own liquidation risk. The hedged settings that end above zero trade
  $5K to $37K a day, against $3.6M a day on the tape.

## A rising window (added 2026-11-24)

**At 10 bp it still lost while the price rose, and hedged, the best tested settings earned tens of
dollars a day in both windows.** We reran everything on Elysium's
HYPE/USDC flow from 2026-11-21 06:00 to 11-24 00:00 UTC (2.75 days, 32,346 swaps), while HYPE rose 13.3%
($56.30 to $63.81). Results in `results/w2-1121/`.

| 10 bp, $500 a side | falling window (11-18..21) | rising window (11-21..24) |
|---|---|---|
| as posted, P&L a day | −$5,291 | −$616 |
| as posted, 5 min after each fill | −6.4 bp | −7.3 bp |
| unhedged settings below zero | 16 of 16 | 10 of 16 |
| hedged settings above zero (causal E) | 7 of 24 | 6 of 24 |
| best hedged at $500 a side (causal E), P&L a day | +$31 | +$42 |

- Unhedged, the loss is far smaller when the price rises, but quoting 10 to 30 bp from the last trade
  still loses as posted (−$616, −$110, −$36 a day). At the narrowest quotes the average fill is
  below water five minutes later in both windows: −6.4 and −7.3 bp.
- The unhedged rows that use E (the fee by direction, quoting around E) use the E with up to a minute of
  hindsight, as in the first window, and here several of them end above zero. The hedged runs use E
  rebuilt without hindsight; there the best at $500 a side is +$42 a day (50 bp, fee by direction, 4.5 bp
  perp cost), and $5,000 a side makes +$54 at the 14.5 bp cost. The best unhedged row, +$387 a day
  (50 bp, quoting around the hindsight E), is not one we could have run live.
- Hedged with the causal E, the best tested settings earn tens of dollars a day in both windows.
- The random-bot rows in `results/w2-1121/summary.txt` reuse the first window's bot settings with this
  window's times and sizes; they are not a second test of the random-bot market.
- To build this window's tape: copy only the `*.py` files of
  [2026-11-21-elysium-direction](../2026-11-21-elysium-direction/) into an empty directory COPY (so no
  earlier `data/logs` is read), and from COPY run
  `hl_candles.py HYPE @107 @334`, `backfill.py 2026-11-21T05:00:00Z 2026-11-24T00:00:00Z data/logs`,
  `trades.py 600` and `analyze.py HYPE` (the candles must be fetched within about 3.5 days of the
  window). Then, back in `2026-11-23-naive-mm/`: `python3 -I build_tape.py COPY 1795240800 tape/elysium_hype_usdc_1121.csv`,
  `python3 -I fetch_funding.py tape/elysium_hype_usdc_1121.csv data/funding_hype_1121.csv` and
  `cargo run --release -- tape/elysium_hype_usdc_1121.csv data/funding_hype_1121.csv results/w2-1121`.
  The trades before 06:00 only seed the 30-minute basis. `build_tape.py` rebuilds the first window's
  tape byte for byte from that study's data.

## Method

- **Exchange**: [rdk-clob](https://github.com/psyto/rdk/tree/main/crates/clob), from the public repo at a
  fixed rev. Our bid and ask rest as limit orders. Each recorded trade arrives as an immediate-or-cancel
  taker at the price it actually got and fills against our quote when ours is at least as good, up to the
  trade's size. We are always first in line: no queue, no other makers, and the trade does not react to
  us. Fills are therefore an upper bound, as in a paper trade.
- **Strategy** (`src/strategy.rs`): after every trade, cancel both quotes and rest $500 a side at
  last trade × (1 ± d), d = 10, 20, 30, 50 bp. Variants: stop quoting the side that would add to an
  inventory past $5,000; quote around E instead of the last trade.
- **A, random bots** (`random_bot_market` in `src/main.rs`): bots trade at random, buy or sell with equal
  odds, crossing 20 bp (+ |N(0, 3 bp)|) from a hidden price. The hidden price moves 1.82 bp a trade
  (the standard deviation of the log change of E from one Elysium trade to the next, printed in
  `results/summary.txt`) and gives back 1% of its distance from the start each trade, so it does
  not trend. Times and sizes are Elysium's. Fixed seed.
- **B, Elysium**: `tape/elysium_hype_usdc.csv`, 57,393 HYPE/USDC swaps from 2026-11-18 00:00
  to 11-21 05:00 UTC (3.21 days), each with its time, side, average execution price and USD size, from
  [2026-11-21-elysium-direction](../2026-11-21-elysium-direction/) (`data/rows_HYPE_E.json`, trades more
  than 5% from E dropped). E is HyperCore's HYPE perp price (1-minute candles) times the median of
  Elysium's price over HyperCore's in the previous 30 minutes, as that study defines it. HyperCore's price
  inside a minute is interpolated from the minute's open to its **close**, which is not known until the
  minute ends: E carries up to a minute of hindsight. Only the fee by direction, quoting around E and the
  5-minute mark use it; the strategy as posted and the inventory cap never see E.
- **Market rule**: a taker trading toward E (buying from us below E, selling to us above it) pays the
  maker max(30 bp, our distance to E), at most 300 bp: the toward side of the defaults of
  [Shadowbook's `DirectionalFee` hook](https://github.com/fabrknt/shadowbook#directionalfee-a-second-hook)
  (30 bp floor, 1× the distance, at most 300 bp). The hook's 30 bp on trades away from E is left out.
  The taker takes our quote only if the all-in price is no worse than what it actually got.
- **Marks**: P&L is cash plus inventory at the market's last price. "5 min after each fill" marks each fill
  (plus its fee) to E at the last trade at or before 300 s after it (on Elysium up to a couple of minutes
  before the 300 s), and leaves out fills less than 300 s before the tape ends.
- **Inventory cap**: the side that would add to the inventory stops being quoted once the inventory is past
  $5,000; the fill that crosses it can take it a little past ($5.5K at most).

## Limits

- Which trades are in a tape is decided with the hindsight E: that study keeps trades it can price
  against HyperCore and within 5% of E, and `build_tape.py` drops trades more than 5% from E. Only `ec`
  and `h` are free of it as prices; the population is not.
- Two windows only: 3.21 days falling (HYPE $69.70 to $56.50) and 2.75 days rising ($56.30 to $63.81).
- Fills are an upper bound (first in line, the flow does not react). Elysium's trades were swaps against
  pools, not orders on a book; we replay them as if they could have come to us.
- The random-bot market is our construction, and its parameters set how well the strategy does there. We
  follow the post's description of the strategy; we have not seen its code.
- No fees for the maker other than the market rule, no gas, no latency.
