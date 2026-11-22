# Sealed hunches (from 2026-11-22)

Before there is anything to measure, there is a hunch: a market looks about to open, a need looks about
to arrive, an empty niche looks like it will stay empty. Those hunches decide where we measure next, so
they are worth keeping. Remembered later, though, only the ones that came true stay. So each hunch is
written down before it can be judged, only its hash is published, and it is opened when it is due,
hit or miss.

| file | what it holds |
|---|---|
| [`sealed.csv`](sealed.csv) | one row per hunch: id, when it was sealed (UTC), when it is due, the SHA-256 of the hunch file, and `prev`, the SHA-256 of `sealed.csv` above that row |
| [`stamps/`](stamps/) | a copy of `sealed.csv` each time it changed, with an [OpenTimestamps](https://opentimestamps.org) proof that the copy existed by a given Bitcoin block |
| [`opened/`](opened/) | the hunch file itself, published byte for byte once it is due |
| [`results.csv`](results.csv) | id, when it was opened, `hit`, `miss` or `void`, the confidence the hunch stated, a note |

## What a hunch says

Each one is a short file with fixed lines: `due`, `confidence` (a whole percent), a random `nonce` (so a
short text can't be found by hashing guesses), then *what I sense*, *why now*, *hit if* and *miss if*.
`hit if` must be filled in before it can be sealed: a hunch with no test can't be scored.

Hunches are about markets and needs (a venue opening, demand arriving, a gap staying open), not about
the price of a token.

## How to check one

```sh
python3 -I hunches/hunch.py verify                         # chain unbroken; each opened file matches its seal
ots verify hunches/stamps/sealed-20261122T013000Z.csv.ots  # that copy of the registry existed by that block
```

A hunch was sealed no later than the first stamped copy of `sealed.csv` that holds its row. The commit
date of a seal is ours to write; the Bitcoin block is not. A stamp shows "pending" for a few hours until a
block includes it.

What each piece catches, and what it doesn't:

- a sealed hunch rewritten later: its hash no longer matches, and `open` and `verify` refuse it;
- a row edited or removed from the middle of `sealed.csv`: every later row's `prev` breaks;
- the last row removed, or the registry rewritten from scratch: not caught by the chain; the stamped
  copies and this repo's public history still hold the row;
- many hunches sealed privately and only the winners published: not caught by anything here. What we
  offer against it is that every seal is pushed the day it is written and stamped by a workflow run you
  can see in Actions; a row whose first stamp is days after its `sealed_at` is one to distrust.

`void` is for a hunch whose own *hit if* can no longer be checked (the source went away), and `stats`
prints the score a second time with every void counted as a miss.

## How it runs

Written and sealed by hand, off GitHub (`$HUNCH_DIR`, default `~/.config/fabrknt/hunches`):

```sh
python3 -I hunches/hunch.py new          # blank hunch with id and nonce; prints its path
python3 -I hunches/hunch.py seal H-0001  # file becomes read-only, its hash goes into sealed.csv
git add hunches/sealed.csv && git commit -m "hunches: seal H-0001" && git push
```

[`.github/workflows/hunches.yml`](../.github/workflows/hunches.yml) runs `verify`, stamps a copy of the
registry whenever it changed, upgrades pending stamps daily, and opens an issue when a hunch is due. Opening is by hand:

```sh
python3 -I hunches/hunch.py open H-0001 hit "what happened, with a link"
python3 -I hunches/hunch.py stats        # hit rate and Brier score against the stated confidence
```

`open` refuses a file whose hash has changed. A hunch that can no longer be judged is opened as `void`,
never left sealed, so `stats` counts everything that was sealed.
Reviewed adversarially by Codex before publishing; its six findings are fixed or listed above as limits.

Written with an AI (Claude), which wrote the script and the workflow. The hunches are ours.
