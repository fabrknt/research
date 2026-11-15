# Is there retail speculation on Monad? (2026-11-15)

One day of nad.fun's V2 bonding curve (`0x9f38…4ae4`), Monad's launchpad, read in full from the
public RPC (`rpc.monad.xyz`, 101 blocks per `eth_getLogs`).

```
python3 -I scan_curve.py 24 day.json   # fetch the last 24 h of the curve's logs (about 3 minutes)
python3 -I analyze.py day.json         # count them
```

Committed: `day.json` (the logs we read, blocks 122,066,786–122,352,113) and `result.txt`:

```
window: blocks 122066786..122352113 = 24.0 h, failed ranges: 0
created: 5 tokens by 2 creators; graduated: 0
trades: 179 buys, 150 sells, by 60 addresses
MON through the curve: 22,872
```

22,872 MON is about $360 at $0.0158 (MON on 2026-11-15). `topics.txt` and `topics3.txt` hold the event
signatures of the V2 and V3 curves; `day3.json` is the V3 curve (`0xA728…0aCE`) over the same day (6 logs).

Limits: one day; the V3 curve and trading after graduation (on DEX pools) are counted separately or not at all.
