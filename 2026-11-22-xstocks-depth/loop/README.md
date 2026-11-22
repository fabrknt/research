# The xStocks loop (from 2026-11-22)

Every 6 hours an agent (Claude Code, headless, in [`xstocks-loop.yml`](../../.github/workflows/xstocks-loop.yml))
reads what the recorder has kept on Solana xStocks at size, against the Hyperliquid xyz perp, tests one
question on it, and writes the result here. Nobody has to read the data for the study to move.

## The question and the gate

Is there room for a dealer (a prop AMM on Solana, hedged on xyz) where the curve pools are thin?

- **Room**: per side, what Jupiter's best route charges at $10k-$100k against the xyz mid, minus the cost
  of hedging the same USD on the xyz book (`r_buy` and `r_sell` in [`table.py`](table.py)). Inventory,
  funding and margin come out of it.
- **Go on** if, by 2026-11-29 (a full week with five US sessions), room stays at tens of bp on one side or more
  in US market hours too, on names that trade hundreds of thousands of dollars a day.
- **Stop** if room in US hours is under 10 bp on every name at $10k and $100k, or if it lives only where the
  xyz book can't hold the hedge (`hedge` is `-`).
- Outside US hours the hedge is a 24-hour perp whose Sunday price did not predict Monday's
  ([weekend gaps](../../2026-11-21-weekend-gaps/)); room there is not counted for the gate.

## What the agent may do

- Read: this folder, the table (`table.py` over the hourly medians the recorder appends to
  `summary.a.jsonl` / `summary.b.jsonl` in the release `xstocks-loop`, about 4.4 kB an hour; no quote, route
  or book reaches it), and the rest of the repo.
- Run: `python3 -I` on the scripts in this folder, including new ones it writes here.
- Write: `experiments/<name>.md`, `findings.md` and `<name>.py` here, nothing else. One note per run;
  `findings.md` only for what the numbers settle. A second job, which runs none of it, checks the files and
  commits them ([`.github/xstocks_loop_take.py`](../../.github/xstocks_loop_take.py)).
- Not: trade, hold a write token (its job has a read-only one), reach the raw recordings (encrypted to a key
  kept off GitHub), or change anything outside these files. A turn stops at $1.50 of API use; at most 4 a day.

## What it does not see yet

- The time between a fill on Solana and the hedge on xyz, and how much it varies: the hedge cost here
  is the book at the same moment, so a moving market is not in it.
- Inventory: what holding a share token costs (its mint can be paused, and its issuer can move it).
- Whether a route that fills is the quote: Jupiter's quote, not the landed swap.
