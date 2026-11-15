# Fabrknt research

What we measured before deciding whether to build a market, with the scripts and the small results
needed to check the numbers. Each study is written up on [fabrknt.com/research](https://fabrknt.com/research);
this repo holds what produced it. Newest first.

| date | study | write-up | answer |
|---|---|---|---|
| 2026-11-15 | [Monad retail](2026-11-15-monad-retail/) | [Is there retail speculation on Monad?](https://fabrknt.com/research/monad-retail) | 60 traders and $360 a day on nad.fun's curve: not yet |
| 2026-11-13 | [Robinhood Chain stock dealer](2026-11-13-robinhood-stock-dealer/) | [Can a dealer quote Robinhood Chain's stocks?](https://fabrknt.com/research/robinhood-stock-dealer) | No: −10 to −18 bp an hour after each fill on single-stock/SPY pools |
| 2026-11-11 | [SPY-quoted pools](2026-11-11-spy-quoted-pools/) | [Do LPs win when a stock is quoted in SPY?](https://fabrknt.com/research/spy-quoted-pools) | No for single stocks (fees 0.29–0.71 of LVR); yes for QQQ/SPY |

Studies that live in another public repo: [B20 stocks registered and never minted](https://github.com/psyto/summon-stocks#numbers)
(`scripts/count_b20.py`) and [Anthropic's IPO across four HIP-3 markets](https://github.com/fabrknt/hl-price-guard/tree/main/cases/anthropic-ipo-2026).

Every study reads public chain data (public RPCs, no keys) and public APIs. Large dumps and data from
third-party APIs (swap dumps, price candles, token lists) are not committed: the scripts fetch them again.
Small sets of public chain logs are committed where they are the whole input of a result
(`2026-11-15-monad-retail/day.json`: one day of one contract's events, with the addresses as they are on chain). Some sources
only keep recent history (Hyperliquid candles: the latest 5,000), so a rerun later reads a different
window; the committed results are what we measured.

Measured with an AI (Claude), which wrote the scripts and ran them; every number in a write-up is a
line of the committed output. Not financial advice.

License: Apache-2.0.
