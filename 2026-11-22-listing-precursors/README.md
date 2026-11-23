# What public trace shows up before a listing, and how many days ahead? (2026-11-22, desk study)

A trader says he and friends made about $6M on CASHCAT and PONS in 2026 by reading BitGo's public
GitHub repo before Robinhood listed them. This checks that claim against the commits, then asks the
same question for Coinbase, Binance, Upbit and Hyperliquid: what was publicly visible before the
listing, how long before, can it be checked from a primary source today, and does anyone already
broadcast it.

**Status: desk study, with two live watchers since 2026-11-22/24 (see the end).** V = primary source seen (a GitHub PR or commit, a
Hyperliquid API or explorer response). R = reported only (press or an analyst's post).

## Summary

| Venue | Best public trace | Typical lead | Can be checked | False positives | Crowded? |
|---|---|---|---|---|---|
| Robinhood | BitGoJS adds the token to `modules/statics` | 3–8 weeks (CASHCAT 10 d) | V | >95% of BitGo additions are never listed by Robinhood | Yes, since 2026-11-15 press; a public watcher bot exists; PR titles now hide tokens |
| Coinbase | Coinbase's own roadmap post | ~1 week | official | "not guaranteed" | Public by design, price moves at the roadmap |
| Binance | its own Alpha → Futures → Spot steps | 14–60 d | official | Alpha→Spot only ~10–12% | Public by design |
| Upbit | a Bithumb listing first | median 33 d, shrinking to ~2 h | R | unknown | Yes |
| any CEX | wallets buying / HL perp OI spiking | minutes–1 day | R (after the fact) | high | Yes (Lookonchain, Arkham, Tree News, Kaiko) |
| **Hyperliquid HIP-3** | `registerAsset` makes the market appear in `meta`, halted, before `haltTrading false` | **15 min – 20 d** | **V** | low: registered names mostly open (YMTC is a counterexample) | **No dedicated public alert found** |

The old API-leak class (an exchange's API showing an asset before launch) has no reported case
since Coinbase changed its process in 2022.

## Robinhood and BitGo (V unless marked)

| Token | Listed (R) | BitGo trace | Lead |
|---|---|---|---|
| CASHCAT | 2026-08-06 | PR #9357 `hoodeth:cashcat`, opened 07-27 09:28Z, merged 07-28 07:09Z, branch "client-requested-tokens…priority-batch" | 10 d |
| PONS | ~2026-09-02 | PR #9603, opened and merged 08-31 | 2 d (after the trader says he started buying) |
| ASTER | 2025-10-16 | `bsc:aster`, 2025-09-24 | 22 d |
| AVNT | 2025-11-13 | `baseeth:avnt`, 2025-10-07 | 37 d |
| LIT | 2026-01-15 | `eth:lit`, 2025-12-19 | 27 d |
| SENT | 2026-07-09 | `eth:sent`, 2026-06-17 | 22 d |
| BILL (Bitstamp) | 2026-08-01 | `eth:bill`, 2026-06-03 | 59 d |
| SKR | ~2026-02-05 | `sol:skr`, 2026-03-11 | −34 d (BitGo after the listing) |

- BitGo adds about 30–160 mainnet tokens a month (300+ in Jul–Aug 2026 with tokenized stocks);
  Robinhood lists about 1–4. Of 11 non-stock `hoodeth:` tokens BitGo added, only CASHCAT became
  tradable.
- The timing in CASHCAT came from Wintermute's onchain moves (hours to 3 days ahead, R), not from GitHub.
- Since October 2026 a bot opens generic metadata PRs whose titles no longer name tokens.

## Hyperliquid HIP-3 (V)

| Market | First visible trace | Trading opens | Lead |
|---|---|---|---|
| new dex `io` | 500k HYPE delegated 08-12 14:32; dex created 08-17 22:12 | 08-19 10:58 | 6.8 d from the stake |
| xyz:ANT | registerAsset2 10-26 13:46 | 10-26 14:04 | 18 min (≥4.5 h before the earliest public post found) |
| xyz:PANW | 11-09 03:32 | 11-19 03:00 | ~10 d |
| xyz:TTWO | 10-20 14:08 | 11-09 15:27 | ~20 d |
| xyz:CVX / SNXX / XBI / MRNA | 09-17 / 09-10 / 08-22 / 08-19 | | 16 h / 4.9 d / 5.5 d / 31 min |
| spot EQANT | registerToken2 11-13 00:00 | 11-19 16:51 | ~6.7 d |

Registered on xyz and still halted on 2026-11-22 (mark = oracle = registration price, volume 0):
SMCI, SNOW, TENCENT, STX, MELI, YMTC.

Other visible traces: HYPE sent to the registering address 30 min – 3 d before a registration (gas);
failed registrations with names and prices; `setOpenInterestCaps` / `setFundingMultipliers` /
`setDeployerFees` minutes to hours before trading opens.

How: `POST https://api.hyperliquid.xyz/info {"type":"perpDexs"}` (deployers, sub-deployers),
`{"type":"metaAndAssetCtxs","dex":"xyz"}` (diff the universe), and
`POST https://rpc.hyperliquid.xyz/explorer {"type":"userDetails","user":<deployer>}` (last 300
signed actions with timestamps). Trading open cross-checked with `candleSnapshot`.

## Limits

- Robinhood, Coinbase, Binance and Upbit dates, all price moves and all profits are R.
- `userDetails` keeps only the last 300 actions per address; older history needs node data.
- Announcement times for xyz single-stock listings could not be found; lead is measured to trading open.
- `isDelisted: true` also covers truly delisted assets; a new name in a diff of `meta` is the clean signal.

## Backtest: buy every BitGo addition, hold N days (2026-11-22)

Universe: tokens first added to BitGoJS `modules/statics` from 2025-11-23 to 2026-11-20 (2,821 additions
parsed from git history → 391 with a CoinGecko id after dropping tokenized stocks, stablecoins,
wrapped assets and names BitGo already had). Entry = CoinGecko daily price on the UTC day after the
commit; returns are in excess of BTC. Only returns are kept, no prices (third-party data).

| Group | n | 7 d median | 14 d median | 30 d median | 30 d share up |
|---|---|---|---|---|---|
| all additions | 303–332 | −5.2% | −6.0% | −11.5% | 29% |
| later listed by Robinhood (VVV, BILL, SENT, CASHCAT) | 4 | −7.0% | +15.8% | +48.3% | 50% |
| Robinhood Chain (`hoodeth:`) tokens | 11–12 | −19.2% | −36.3% | −63.3% | 18% |

Entry → Robinhood listing day (not BTC-adjusted): VVV +87% (25 d), CASHCAT +121% (8 d),
SENT −20% (21 d), BILL −71% (49 d). LIT, RE, MEGA and CHIP were added to BitGo before the token
traded anywhere, so there was nothing to buy; LIT from its first price to listing day was −30%
against BTC. ZRO, SKR and AERO were already listed when BitGo added them on a new chain.

Reading: the trace hits about 1 in 80 (4 of ~330 buyable), and two of the four hits lost money
anyway. The mean token return against BTC is −6.8% at 7 days and −12.4% at 30 days (an equal-weight
basket, rebalanced per entry, before costs): new tokens tend to fall, whatever BitGo does. Shorting
them was not tested (it needs a perp per token, and funding).

## Adding Wintermute's wallets (2026-11-22)

20 labelled Wintermute addresses (Etherscan labels, Blockscout metadata tags); first receipt of each
BitGo-added token on Ethereum (complete), Robinhood Chain and Arbitrum (RPC logs, addresses with
activity there only). Base effectively not covered (keyless quota), Solana and BSC not checked.
155 EVM tokens.

| Group | n | Robinhood listed later | 7 d median | 30 d median |
|---|---|---|---|---|
| BitGo only | 155 | 5 (3%) | −7.9% | −10.9% |
| BitGo and Wintermute holds it within 14 d | 24 | 4 (17%) | −1.7% | −6.7% |
| no receipt seen (labelled wallets, chains covered) | 128 | 0 | −8.6% | −13.0% |

- None of the 128 tokens with no receipt seen was listed. The other 3 of 155 had a first receipt more than
  14 days after BitGo's addition. Coverage is partial (labelled wallets only, Base barely), so this is
  "no receipt seen", not "never received".
- In most hits Wintermute held the token long before (VVV, SENT, ZRO): a mature token with a market
  maker, not timing.
- Where Wintermute first received the token just before the listing, the gap was hours: CASHCAT 0.4 d,
  RE 0.1 d, BILL 1.5 d. Hourly prints from an hour after the receipt: CASHCAT +27% by the next 00:00
  UTC and +44% by 12:00; BILL +10% to +33% over the next 1–2 days. n = 2–3, anecdotal.
- Hypothesis, not a result: if the trace pays at all, it is within hours, so it needs watching live
  (BitGo adds a token, then Wintermute's wallets for it). Two or three past cases cannot show it pays;
  `recorder/sources/listing_watch.py` now collects new cases.

## Live watchers (2026-11-22 and 11-24)

Both run in the [recorder](../recorder/), write encrypted rows, and push to a private ntfy topic.

- `listing_watch` (from 11-22): Wintermute receiving a token BitGo added in the last 30 days, on Ethereum,
  Base, Arbitrum and Robinhood Chain, checked every 5 min. It also pushes each new Robinhood Chain token
  BitGo adds.
- `events` (pushes from 11-24): Hyperliquid HIP-3 names, checked about once a minute.
  - **Registered:** a name appears halted.
  - **Opening prep:** while it is still halted, the deployer changes its open-interest cap or funding
    settings (`perpDexs`).
  - **Open:** trading starts.

  The books every 10 s around each opening are already kept, to measure how far the first 30 minutes trade
  from the oracle and how fast that closes.

Between 11-22 and 11-24, xyz registered 8 more names, all still halted: ACN, SNAP, NU, CATL, INNOLIGHT,
AMEC, IBIDEN and SOXS.

Following the wallets that found Hyperliquid early was checked too, and failed: see
[2026-11-23-early-finders](../2026-11-23-early-finders/).
