"""HIP-3 (xyz:) 1m / 5m / 15m candles for every coin in coins.py -> data/hl_candles.json ({coin_iv: [[t_ms, o, c, v]]}).
Hyperliquid serves only the latest 5,000 candles per interval: 1m ≈ 3.5 days, 5m ≈ 17 days, 15m ≈ 52 days.
The 2026-11-13 study saved 1m/5m for 15 coins (~/src/rh-measure/data/hl_candles.json, read only); those are
merged in so 5m covers 10-27 onward for those coins."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hl import candles
from coins import HL_COIN

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OLD = os.path.expanduser("~/src/rh-measure/data/hl_candles.json")
now = int(time.time() * 1000)
out = {}
for coin in sorted(set(HL_COIN.values())):
    for iv, w in (("1m", 60_000), ("5m", 300_000), ("15m", 900_000)):
        cs = candles(f"xyz:{coin}", iv, now - 5000 * w, now)
        out[f"{coin}_{iv}"] = [[c["t"], float(c["o"]), float(c["c"]), float(c["v"])] for c in cs]
    print(coin, {iv: len(out[f"{coin}_{iv}"]) for iv in ("1m", "5m", "15m")}, flush=True)
old = json.load(open(OLD))
for key, cs in old.items():
    have = {c[0] for c in out.get(key, [])}
    out[key] = sorted(out.get(key, []) + [c for c in cs if c[0] not in have])
json.dump(out, open(f"{D}/hl_candles.json", "w"))
print("saved", now)
