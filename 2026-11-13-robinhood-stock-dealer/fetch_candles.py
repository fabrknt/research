"""HIP-3(xyz:)の 1 分足・5 分足を取り直して data/hl_candles.json に書く。各足は [t(ms), open, close, volume]。
HL の足は最新 5000 本までなので、1 分足は約 3.4 日、5 分足は約 17 日になる。"""
import json, time
from hl import candles
from analyze_coins import HL_COIN

now = int(time.time() * 1000)
out = {}
for coin in sorted(set(HL_COIN.values())):
    for iv, w in (("1m", 60_000), ("5m", 300_000)):
        cs = candles(f"xyz:{coin}", iv, now - 5000 * w, now)
        out[f"{coin}_{iv}"] = [[c["t"], float(c["o"]), float(c["c"]), float(c["v"])] for c in cs]
        print(coin, iv, len(cs), flush=True)
json.dump(out, open("data/hl_candles.json", "w"))
