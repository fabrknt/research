# Anthropic listing: Binance, Bitget and OKX quotes (2026-11-18 to 11-21)

The reference prices for HL Price Guard's Anthropic IPO case
([fabrknt/hl-price-guard, cases/anthropic-ipo-2026](https://github.com/fabrknt/hl-price-guard/tree/main/cases/anthropic-ipo-2026)).
Its Cloudflare recorder reads the Hyperliquid markets and OKX every minute; Binance and Bitget answer
403 to Cloudflare, so they are recorded here through the reported pricing (11-18) and first trade (11-19).

Where each venue answers from (measured 2026-11-18):

| venue | GitHub's machines | Cloudflare | a laptop outside the US |
|---|---|---|---|
| Binance | HTTP 451 on every round (US) | HTTP 403, also from Osaka (KIX) | yes |
| Bitget | yes | HTTP 403 | yes |
| OKX | yes | yes | yes |

So the workflow records Bitget and OKX (and the Binance errors), and Binance is recorded by running
`collect.py` on a laptop (`caffeinate -i python3 -I collect.py 5600 60`, about four days; it stops
while the lid is closed).

- `collect.py`: one round a minute; each venue's response stored as quoted (no share-count basis
  applied), errors included. Both of Binance's and Bitget's symbols are read (`ANTHROPICUSDT`, and
  `ANTUSDT` after the move to about 13.1B shares).
- `.github/workflows/anthropic-listing-collect.yml`: an hour of rounds per job, each job starting the
  next, until 2026-11-21. Bitget answers `ANTUSDT` to either symbol.
- `worker/`: the Cloudflare test (2026-11-19), a Durable Object placed in Asia-Pacific reading Binance once
  a minute. Every round was 403, so Binance blocks Cloudflare by address rather than by location;
  it stopped after three rounds.
- CoinGecko's derivatives list carries Binance's `ANTUSDT` (11 to 13 minutes old when read), so
  `collect.py` also stores its Anthropic rows every 5 rounds (from 2026-11-19): a coarse backup for
  minutes the laptop recorder misses, not a substitute for it around the first trade.
- `fetch_actions.sh`: downloads and decrypts the hourly quotes from the release
  `anthropic-listing-data-202611` (copied there from the 90-day workflow artifacts on 2026-11-22; the quotes
  are third-party API data, encrypted and not published in the clear).

Results (2026-11-20): ["What happened" in the hl-price-guard case](https://github.com/fabrknt/hl-price-guard/tree/main/cases/anthropic-ipo-2026#what-happened-replayed-2026-11-20).
In short: nothing moved toward the $83 offering price, the perps were 0.3% under the $111.50
first trade a minute before it, and the largest by-rule step was Paragon's switch to an external
feed 15 minutes later (−5.4%).

Measured with an AI (Claude), which wrote the scripts and ran them. Not financial advice.
