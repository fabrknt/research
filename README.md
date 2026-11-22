# Fabrknt research

What we measured before deciding whether to build a market, with the scripts and the small results
needed to check the numbers, and the [recorder](recorder/) that keeps what new markets show only once. Each study is written up on [fabrknt.com/research](https://fabrknt.com/research);
this repo holds what produced it. Newest first.

| date | study | write-up | answer |
|---|---|---|---|
| 2026-11-22 | [Sealed hunches](hunches/) | (as they come due) | Hunches about markets and needs, written before they can be judged: only the hash is published, stamped on Bitcoin, and each is opened when due, hit or miss |
| 2026-11-21 | [Recorder](recorder/) | (infrastructure) | Recording, free APIs only, in one job chain: Hyperliquid asset ctxs for every dex each minute, Variational quotes with the Lighter and HL books every 5 min, every Lighter blob, Solana prop AMM quotes each minute, books every 10–30 s for 72 h around big moves and new listings, each venue's rules and docs daily |
| 2026-11-21 | [Stock pools by session](2026-11-21-stock-pool-sessions/) | [Where do LPs leak on new markets: in the hours, or in the direction of the trade?](https://fabrknt.com/research/lp-leak-four-markets) | $671M on Robinhood Chain over 25 days: LPs −2.6 bp at 1 h, half of it at the open. Swaps closing the gap to xyz cost LPs −11.5 bp; a fee on that distance beats a flat fee, a session schedule doesn't |
| 2026-11-21 | [Elysium direction](2026-11-21-elysium-direction/) | [Where do LPs leak on new markets: in the hours, or in the direction of the trade?](https://fabrknt.com/research/lp-leak-four-markets) | HYPE/USDC LPs −$2.4K/day after fees; toward-HyperCore trades −24 bp, away +17 bp. The gap shrank from −152 bp to about −20 bp since 11-11; a directional fee still beats a fixed 30 bp in 96 of 96 replays |
| 2026-11-21 | [CCA launch LP](2026-11-21-cca-launch-lp/) | [Where do LPs leak on new markets: in the hours, or in the direction of the trade?](https://fabrknt.com/research/lp-leak-four-markets) | 1,114 CCAs on 4 chains, 10 graduated with $100k or more (Aztec 78% of the money). Launch-day LP losses came from price collapses; the auction's bids didn't predict day 1, and concentrating at the clearing price made every pool worse |
| 2026-11-21 | [PM AMM timing](2026-11-21-pm-amm-timing/) | [Where do LPs leak on new markets: in the hours, or in the direction of the trade?](https://fabrknt.com/research/lp-leak-four-markets) | Trueo's 104 markets replayed: rules using time to resolution, price and direction cut 22–55% of the LP loss out of sample and lose 13–57% of volume; a flat 20% fee does about as well |
| 2026-11-21 | [Trueo LP loss](2026-11-21-trueo-lp-loss/) | [What do LPs lose before a prediction market resolves?](https://fabrknt.com/research/trueo-lp-loss) | $126,558 lost against holding by the pools of 104 resolved markets; LP fees an estimated $0.77, and the hook's fees, all of them with the same trades, would have covered 5.2%. 79% of the loss in the 7 days before resolution was proposed, 5.5% in the last 6 h |
| 2026-11-21 | [ADL premiums](2026-11-21-adl-premiums/) | [What would a cover against Hyperliquid's auto-deleveraging have paid?](https://fabrknt.com/research/adl-premiums) | A cover paying the 5-minute re-hedge after ADL: main dex 38 bp/year, 1.4 without 2025-10-10; HIP-3 $1.39M in 0.95 years, over half on one stale-price night (xyz:EWZ) |
| 2026-11-21 | [Weekend gaps](2026-11-21-weekend-gaps/) | (after more weekends) | Recording every weekend: 22 US names, Friday close to Monday open. First seven: median 129 bp; Hyperliquid's xyz an hour before the open still 91 bp away |
| 2026-11-18 | [Lighter state replay](2026-11-18-lighter-state-replay/) | (after catch-up) | Running: Lighter's full state carried from the May snapshot to today, one Ethereum blob at a time; matches the committed root at batches 167059 and 167259 |
| 2026-11-18 | [Anthropic listing quotes](2026-11-18-anthropic-listing-quotes/) | (after the listing) | Collecting: Binance, Bitget and OKX quotes through the pricing and first trade, until 11-21 |
| 2026-11-17 | [Lighter's November 16](2026-11-17-lighter-nov-16/) | [What does Ethereum show about Lighter's November 16?](https://fabrknt.com/research/lighter-nov-16) | First drain to the cent (10,393,056.79 USDC to the attacker); the second was posted after a 7 h 22 min pause and paid to another address |
| 2026-11-16 | [One quote vs books](2026-11-16-one-quote-vs-books/) | (after a weekend) | Collecting, no end date (moving into the recorder). Weekdays so far: crypto, Lighter cheapest; stocks from $100k in US hours, Hyperliquid HIP-3; Variational's one dealer wins only on $1M indices and commodities |
| 2026-11-15 | [Monad retail](2026-11-15-monad-retail/) | [Is there retail speculation on Monad?](https://fabrknt.com/research/monad-retail) | 60 traders and $360 a day on nad.fun's curve: not yet |
| 2026-11-13 | [Robinhood Chain stock dealer](2026-11-13-robinhood-stock-dealer/) | [Can a dealer quote Robinhood Chain's stocks?](https://fabrknt.com/research/robinhood-stock-dealer) | No: −10 to −18 bp an hour after each fill on single-stock/SPY pools |
| 2026-11-11 | [SPY-quoted pools](2026-11-11-spy-quoted-pools/) | [Do LPs win when a stock is quoted in SPY?](https://fabrknt.com/research/spy-quoted-pools) | No for single stocks (fees 0.29–0.71 of LVR); yes for QQQ/SPY |

Studies that live in another public repo: [B20 stocks registered and never minted](https://github.com/psyto/summon-stocks#numbers)
(`scripts/count_b20.py`) and [Anthropic's IPO across four HIP-3 markets](https://github.com/fabrknt/hl-price-guard/tree/main/cases/anthropic-ipo-2026).

Every study reads public chain data (public RPCs, no keys) and public APIs. Large dumps and data from
third-party APIs (swap dumps, price candles, token lists) are not committed: the scripts fetch them again.
What can't be fetched again (quotes, open interest, books at a moment) the recorder keeps, encrypted, in
this repo's releases; only the holder of the private key, kept off GitHub, can read it.
Small sets of public chain logs are committed where they are the whole input of a result
(`2026-11-15-monad-retail/day.json`: one day of one contract's events, with the addresses as they are on chain). Some sources
only keep recent history (Hyperliquid candles: the latest 5,000), so a rerun later reads a different
window; the committed results are what we measured.

Measured with an AI (Claude), which wrote the scripts and ran them; every number in a write-up is a
line of the committed output. Not financial advice.

License: Apache-2.0.
