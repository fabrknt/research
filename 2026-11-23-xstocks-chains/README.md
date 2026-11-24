# Tokenized US shares: which chain and issuer has size (from 2026-11-23)

The xStocks prop AMM idea ([2026-11-22-xstocks-depth](../2026-11-22-xstocks-depth/)) assumed Solana is
where tokenized shares trade and that the gap is size: past $10k, Solana's routes are curve pools and a $100k
round trip costs hundreds of bp. But in October Solana had about 31% of tokenized-stock DEX volume, with
Robinhood Chain, BNB Chain and Base close behind, and BNB Chain led by market cap (mostly Binance's bStocks).
So: for the same shares, what does size cost on each chain and issuer?

## First snapshot: 2026-11-23 07:20–07:30 UTC (Monday, US market closed)
One run of the recorder's `evm_stock_quotes` (KyberSwap, BNB Chain / Ethereum / Arbitrum / Robinhood Chain,
every issuer that has the share there) and `xstocks_quotes` (Jupiter, Solana). Round trip = buy with the chain's
dollar token, sell back what the buy would get; cost in bp. One observation each: `compare.py` re-prints it from
the snapshot, and from the recorder's hours once there are more.

| share | $100k cheapest | bp | Solana xStocks $100k (bp) |
|---|---|---|---|
| NVDA | BNB bStocks | 14 | 144 |
| TSLA | BNB bStocks | 20 | 171 |
| QQQ | BNB bStocks | 11 | 264 |
| SPY | Robinhood Chain, Robinhood | 11 | 142 |
| GOOGL | Robinhood Chain, Robinhood | 19 | 439 |
| AAPL | Ethereum, Ondo | 44 | 399 |
| MSFT | Ethereum, Ondo | 25 | 446 |
| META | Ethereum, Ondo | 49 | 539 |
| CRCL | BNB bStocks | 69 | 211 |
| MSTR | Ethereum, Ondo | 72 | (no MSTR route at $100k) |
| COIN | Ethereum, Ondo | 90 | 8,713 |

- **At $100k the EVM issuers cost 11–123 bp; Solana xStocks 142–8,713 bp.** The EVM routes are prop AMMs and
  RFQ/PMM makers: Metric, Kipseli, Flux, LiquidFi, LunarBase on BNB; Kyber's `pmm-20` (alone, for AAPL, AMZN,
  MSFT) and Goliath on Ethereum; Metric and TideFi on Robinhood Chain.
- **At $10k they are close**: 2–73 bp for the cheapest of each share; Solana was the cheapest for MSTR and
  within 4–49 bp of the cheapest for the rest (NVDA 10 vs 6, MSFT 23 vs 17, GOOGL 55 vs 10, COIN 104 vs 55).
- **xStocks on EVM chains had almost no liquidity in this snapshot**: a $10k round trip loses 26–100% on BNB, Ethereum and
  Arbitrum. Ondo on BNB is the same, and Ondo on Robinhood Chain routes $10k for most names (24–92 bp; QQQ
  not) but not $100k. In this snapshot each issuer's routable size sat on one chain: xStocks on Solana, bStocks
  on BNB, Ondo on Ethereum, Robinhood's tokens on Robinhood Chain.
- Robinhood Chain has many unrelated tokens with the same tickers, some named "Robinhood Token": the addresses
  used are the ones that routed $10k (`robinhood_tokens.json`). A route shows liquidity, not the issuer; that
  these are Robinhood's own tokens is not confirmed from Robinhood.

What this suggests for the prop AMM idea, from one closed-hours snapshot of indicative routes: the size gap may
be specific to **Solana xStocks**, while the other issuers' home chains already route $100k through several
prop makers. If the recorder's US-hours runs agree, that narrows the opening (one issuer, one chain) rather than
removing it; it is the chain where Hadron stops at $2–8k.

## Not shown yet
- **US hours.** The recorder asks every 30 minutes from 2026-11-23; `compare.py --read FROM TO` uses its hours.
- **Whether a quote fills.** These are aggregator routes. PMM/RFQ legs (`pmm-*`) are a maker's indicative quote
  through Kyber and can be refused or requoted at execution; Jupiter's are routes on on-chain pools.
- **Fungibility.** The issuers' tokens are different claims (different custodians, eligibility, redemption);
  a cheaper Ondo AAPL on Ethereum does not make Solana's AAPLx cheaper, except through someone who holds both.

The snapshot's raw rows are not published (third-party API data; the recorder keeps its rows encrypted), so
the table above cannot be rebuilt from this folder; `compare.py --read` rebuilds the same view from the
recorder's hours for anyone with the data key.

## Files
- `tokens.json`: CoinGecko platform addresses per share and issuer (2026-11-23).
- `robinhood_tokens.json`: the Robinhood Chain token per ticker that routed $10k of USDG.
- `compare.py`: the table above, from a snapshot or from the recorder.
