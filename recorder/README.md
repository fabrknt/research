# The recorder: what busy new markets show only once (from 2026-11-21)

Some of what venues show is gone a moment later and no one sells it: a dealer's quote that is in no
order book, open interest and oracle prices the API keeps no history of, blobs Ethereum drops after
18 days, the rules a venue ran under on a given day. The recorder keeps these, with free APIs only,
in one place: one job chain, one list of what is kept, one storage format, one reader, one daily check.

| source | every | what | why it is kept |
|---|---|---|---|
| `hl_ctx` | 1 min | Hyperliquid `metaAndAssetCtxs` for the main dex and every HIP-3 dex | open interest and oracle prices have no history in the API; candles reach back 5,000 bars |
| `one_quote` | 5 min | Variational's listing rows (quotes, funding, open interest, volume) with the Lighter and Hyperliquid books for the same 40 markets ([one quote vs books](../2026-11-16-one-quote-vs-books/)) | Variational keeps no public history of its quotes |
| `lighter_blobs` | 10 min | every Lighter batch blob committed to Ethereum | rebuilding Lighter's state ([state replay](../2026-11-18-lighter-state-replay/)) needs every blob; Ethereum drops them after about 18 days |
| `solana_quotes` | 1 min | Jupiter's free quote (api.jup.ag, lite-api as fallback; no key) for SOL/USDC at 10, 1,000 and 10,000 SOL and $1k, $100k and $1M, from each Solana prop AMM alone (BisonFi, GoonFi V2, SolFi V2, ZeroFi, Kipseli, Scorch) and Jupiter's best route | prop AMM quotes are in no order book, and Solana keeps no past account state to price them against later; HumidiFi and TesseraV had no route through this API on 2026-11-21 and are asked once a run to see when that changes |
| `rules` | daily | Hyperliquid perpDexs, meta (margin tables) per dex, spotMeta; Lighter orderBookDetails; every page of the Hyperliquid, Lighter and Variational docs | what the rules were when something happened; each row says whether the item changed since the day before |

The list, with the question each source is kept for, is [`sources.toml`](sources.toml). A source is one
file in [`sources/`](sources/) with a `run(state) -> rows` function; adding one is that file and one
`[[source]]` entry. A source goes in only when the question it answers fits in that one line.

## How it runs

[`.github/workflows/recorder.yml`](../.github/workflows/recorder.yml) runs [`record.py`](record.py) for 55
minutes, each source in its own thread at its own interval, then starts the next job itself. Each hour:

- rows go to `<source>.jsonl.gz`, encrypted together (AES-256, key wrapped with RSA-OAEP to
  `.github/one-quote-data.pub.pem`; the private key is kept off GitHub), because they are third-party API
  data this repo doesn't publish;
- the hour goes into the month's release `recorder-YYYYMM` as `<run id>-<attempt>.tar`, next to an unencrypted
  `count.json` (per source: calls that worked, were complete or failed, by exception type only, rows, and a
  small status such as how far behind; no data). Error messages go into the encrypted hour, since they can
  quote a third party's response;
- each source's state (when it last ran; for blobs, the last L1 block kept) goes into the `recorder-state`
  release, and moves on only once the hour is kept.

[`health.py`](health.py) runs daily ([`recorder-health.yml`](../.github/workflows/recorder-health.yml)):
from the last 24 hours' `count.json` it flags a source whose complete calls fall under 80% of what its
interval allows, one more than an hour behind (Lighter's blobs), rules items that failed all day, or a
chain that has stopped, as a comment on the open issue "recorder: gaps".

Set the repo variable `RECORDER_STOP=1` to stop it.

## Reading it

```
python3 -I recorder/read.py hl_ctx --from 2026-11-21 --to 2026-11-22 > hl_ctx.jsonl
```

Downloads the hours that overlap the range (cached under `recorder/data/`, git-ignored), decrypts them with
`~/.config/fabrknt/research-data-key.pem` (or `--key`) and prints that source's rows. Lighter blobs come with
their batch number; a batch committed twice appears twice, and the last commit wins.

## Size and limits

A local 2-minute trial (2026-11-21) wrote, gzipped: `hl_ctx` about 28 KB a call (11 dexes, 568 markets),
`one_quote` 85 KB a round, `rules` 0.7 MB a day (567 items), and Lighter blobs about 18.5 KB each
(131,072 bytes raw; about 740 a day). About 3 MB an hour, 2.5 GB a month, all in releases.

- Between two jobs there is a gap of a few minutes; `hl_ctx` covers about 90% of the minutes.
- A Variational listing without quotes at that moment has `quotes: null` (6 of 40 in the trial).
- Lighter blobs come through Blobscan, the code of the state replay; a blob Blobscan doesn't have yet is
  tried again in the next run, from that commit on, so none is skipped or kept twice.
- `solana_quotes` is what Jupiter would route, not each venue's own quote: a venue Jupiter doesn't route
  through lite-api (HumidiFi, TesseraV on 2026-11-21) is missing. One run takes about 40 s.
- What the recorder doesn't keep: anything that has to be bought, and the high-frequency capture around
  events (next).
