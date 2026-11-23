# Does a last-trade market maker survive a real flow? (2026-11-23)

A post shared on Japanese X in 2026-11 (pasted to us as text; we have no link, so we make no claim about
what it reports) describes a short market-maker script. We take only the strategy it describes. It does
not predict prices: it takes the last
trade as the fair price, rests a bid a little below and an ask a little above, and after every trade
cancels both and quotes again. We ran that strategy, as the post describes it, on two markets with the
same exchange, the same quote size and the same rules: a simulated market of random bots, and Elysium's HYPE/USDC
flow next to Hyperliquid.

```
cargo run --release      # about a minute to build, a second to run; writes results/
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
- Every setting is in `results/summary.txt`; hourly equity at 30 bp in `results/equity_hourly.csv`.

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

- One window of 3.21 days, and in it HYPE fell from $69.70 to $56.50 on Elysium. A window with a rising or
  flat price would show the inventory differently; the 5-minute numbers depend less on it.
- Fills are an upper bound (first in line, the flow does not react). Elysium's trades were swaps against
  pools, not orders on a book; we replay them as if they could have come to us.
- The random-bot market is our construction, and its parameters set how well the strategy does there. We
  follow the post's description of the strategy; we have not seen its code.
- No fees for the maker other than the market rule, no gas, no latency.
