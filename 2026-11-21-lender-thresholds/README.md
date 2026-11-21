# Do Solana lenders' thresholds on tokenized stocks survive the moves made while the market was shut? (2026-11-21)

Four Solana lending markets take tokenized stocks as collateral: Kamino's xStocks, Sentora xStocks and
Backpack markets, and Jupiter Lend. This reads each one's liquidation threshold and bonus today
(Kamino from its reserve accounts on-chain, Jupiter from its public API) and checks it against
every close-to-open move the underlying stock has made since Yahoo's first daily bar (1993 for SPY,
1998 for MSTR, 2010 for TSLA).

```
python3 -I thresholds.py     # -> results/lenders.csv, closures.csv, exceedances.csv (about 30 s)
```

**Answer: no weekend or holiday since 1993 fell far enough to fail the coverage test below at any
of today's settings.** The closures that did were all weeknights: NVIDIA four times (2002–2018)
against the 73–75% thresholds, and Apple once (2000-09-29) against Kamino's 50%. The thinnest
weekend margin is Jupiter's SPYx and QQQx at 85%: the test fails past an 11.3% fall, and SPY fell
10.4% into the open on 2020-03-16.

## The test
A position sitting exactly at the liquidation threshold LT when the market shuts is still covered
by a full liquidation at the open after a fall D if `LT (1 + b) (1 + i) <= (1 - D) (1 - s)`. This
is adapted from the condition LlamaRisk used for Aave V4's Equities Hub (Aave governance,
2026-09-21), with the cost of the sale written out. It is not a replication: LlamaRisk runs every
off-hours minute on minute bars through five minutes after the next open and adds an oracle
deviation allowance; this uses daily bars, close to open. It uses four inputs:

- `b`: the liquidation bonus or penalty. Kamino's largest bonus is 10%; Jupiter's penalty is 3%.
- `i`: interest over the longest closure, 0.25% (24% a year over 92.6 h, as LlamaRisk).
- `s`: the cost of selling the seized tokens, 1%.
- `D`: the move from the previous close to the next open, split- and dividend-adjusted.

The break-even fall is `D* = 1 − LT (1 + b)(1 + i) / (1 − s)`.

| lender | token | LT | bonus | supplied | D* | worst close→open fall | closures past D* | of them weekend/holiday |
|---|---|---|---|---|---|---|---|---|
| Jupiter Lend (USDC) | SPYx | 85% | 3% | $6.4M | 11.3% | 10.4% (2020-03-16, weekend) | 0 | 0 |
| Jupiter Lend (USDC) | QQQx | 85% | 3% | $0.6M | 11.3% | 9.5% (2020-03-16, weekend) | 0 | 0 |
| Jupiter Lend (USDC) | TSLAx | 75% | 3% | $0.8M | 21.8% | 14.9% (2020-09-08, holiday) | 0 | 0 |
| Jupiter Lend (USDC) | NVDAx | 75% | 3% | $1.1M | 21.8% | 30.6% (2004-08-06) | 3 | 0 |
| Kamino Sentora xStocks | SPYx | 79% | 10% | $3.2M | 12.0% | 10.4% | 0 | 0 |
| Kamino Sentora xStocks | QQQx | 78% | 10% | $1.1M | 13.1% | 9.5% | 0 | 0 |
| Kamino Sentora xStocks | NVDAx | 73% | 10% | $0.9M | 18.7% | 30.6% | 4 | 0 |
| Kamino xStocks | SPYx | 75% | 10% | $3.5M | 16.5% | 10.4% | 0 | 0 |
| Kamino xStocks | QQQx | 72% | 10% | $3.4M | 19.8% | 9.5% | 0 | 0 |
| Kamino xStocks | GOOGLx | 70% | 10% | $3.2M | 22.0% | 11.7% (2026-10-29) | 0 | 0 |
| Kamino xStocks | TSLAx | 65% | 10% | $2.3M | 27.6% | 14.9% | 0 | 0 |
| Kamino xStocks | NVDAx | 65% | 10% | $1.6M | 27.6% | 30.6% | 2 | 0 |
| Kamino xStocks | MSTRx | 40% | 10% | $6.4M | 55.4% | 51.8% (2000-03-20, weekend) | 0 | 0 |
| Kamino xStocks | HOODx | 40% | 10% | $0.2M | 55.4% | 17.8% (2024-08-05, weekend) | 0 | 0 |
| Kamino xStocks | AAPLx | 50% | 10% | $0.3M | 44.3% | 47.3% (2000-09-29) | 1 | 0 |

Jupiter's JupUSD vaults have the same settings as its USDC vaults. `results/lenders.csv` has every
reserve, including CRCLx and METAx at Kamino and MU, SKHY and SNDK at Backpack, all far inside their
break-even. Supply is the lender's own figure, read on 2026-11-21; it changes with every run.

Which weeknights passed D* (`results/exceedances.csv` has every close-to-open move over 10%):
- NVIDIA fell 27.1% (2002-07-31), 30.6% (2004-08-06), 28.0% (2008-07-03) and 19.3% (2018-11-16).
  The last one is past D* only at Sentora's 73%.
- Apple fell 47.3% on 2000-09-29.

## What it says
- **Weekends are not where the test fails.** Every lender's threshold clears the worst weekend or
  holiday in the record. The tightest are Jupiter's SPYx and QQQx at 85%: a 0.9-point margin over
  SPY's March 2020 open, and 1.9 points over QQQ's.
- **Weeknights are, for a lender that cannot liquidate until the open.** The test assumes nothing
  happens between the close and the open. A move after an evening report usually shows up in
  after-hours trading, and a lender whose oracle follows it can liquidate earlier, but whether the
  seized tokens can be sold then, and at what cost, is not measured here. A frozen price does not
  by itself stop liquidations either; it only stops them from seeing the move.
- **The settings already differ by name, unlike the two tiers we assumed.** Kamino holds MSTRx and
  HOODx at 40%, AAPLx at 50%, GOOGLx at 70% and SPYx at 75%. Jupiter has only the two tiers (85% for
  the ETFs, 75% for TSLA and NVDA), but lists no MSTR, COIN or HOOD.
- **Small differences carry weight at 85%.** At Jupiter's 3% penalty, each point of LT moves D* by
  about 1.0 point. Moving the ETFs to 83% would give 13.4%, which covers SPY's worst weekend with
  3 points to spare.

## Limits
- Daily bars give no intraday path. "Close → open" stands in for "the last price the lender could
  liquidate at → the first price it can", which is right only for a lender frozen across the
  closure.
- Old open prices in Yahoo's data are less reliable than recent ones. The 2000 MSTR and AAPL falls
  are real events (a restatement, a profit warning), but their exact size here is Yahoo's.
- Kamino's bonus rises from 5% to 10% as a position gets worse. Using 10% makes D* smaller, so the
  test is stricter than a liquidation at 5% would be.
- `s` = 1% is flat. LlamaRisk measured $0.3–1.1M of depth within 2% for Base stock tokens; the
  xStocks depth on Solana was not measured here.
- Kamino's offsets were found by matching the LTV the API reports against the reserve bytes; the
  script checks that match on every run and stops if it breaks.
