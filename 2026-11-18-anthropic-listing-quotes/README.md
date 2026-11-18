# Anthropic listing: Binance, Bitget and OKX quotes (2026-11-18 to 11-21)

The reference prices for HL Price Guard's Anthropic IPO case
([fabrknt/hl-price-guard, cases/anthropic-ipo-2026](https://github.com/fabrknt/hl-price-guard/tree/main/cases/anthropic-ipo-2026)).
Its Cloudflare recorder reads the Hyperliquid markets and OKX every minute; Binance and Bitget answer
403 to Cloudflare, so they are recorded here, on GitHub's machines, through the reported pricing
(11-18) and first trade (11-19).

- `collect.py`: one round a minute; each venue's response stored as quoted (no share-count basis
  applied), errors included. Both of Binance's and Bitget's symbols are read (`ANTHROPICUSDT`, and
  `ANTUSDT` after the move to about 13.1B shares).
- `.github/workflows/anthropic-listing-collect.yml`: an hour of rounds per job, each job starting the
  next, until 2026-11-21.
- `fetch_actions.sh`: downloads and decrypts the hourly artifacts (the quotes are third-party API
  data and are not published).

Results go into the hl-price-guard case after the listing.

Measured with an AI (Claude), which wrote the scripts and ran them. Not financial advice.
