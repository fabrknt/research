"""HyperCore 1-minute candles (free public info API; it keeps about the latest 5,000 per coin).
usage: hl_candles.py COIN [COIN ...] -> data/hl/COIN.json  ({minute: [open, close]} merged with what is there)"""
import json, os, sys, time, urllib.request
HL = "https://api.hyperliquid.xyz/info"
def post(body):
    for i in range(6):
        try:
            r = urllib.request.Request(HL, json.dumps(body).encode(), {"content-type": "application/json", "user-agent": "curl/8"})
            return json.load(urllib.request.urlopen(r, timeout=60))
        except Exception as e: err = e; time.sleep(2 ** i)
    raise err
os.makedirs("data/hl", exist_ok=True)
now = int(time.time()) * 1000
for coin in sys.argv[1:]:
    path = f"data/hl/{coin.replace('@','at')}.json"
    have = json.load(open(path)) if os.path.exists(path) else {}
    t = now - 5200 * 60000
    while t < now:  # the API returns at most 5,000 candles a call
        c = post({"type": "candleSnapshot", "req": {"coin": coin, "interval": "1m", "startTime": t, "endTime": min(now, t + 4000 * 60000)}})
        for x in c: have[str(int(x["t"]) // 60000)] = [float(x["o"]), float(x["c"]), float(x["h"]), float(x["l"])]
        t += 4000 * 60000
    json.dump(have, open(path, "w"))
    ks = sorted(map(int, have)); print(coin, len(ks), time.strftime("%m-%d %H:%M", time.gmtime(ks[0] * 60)), time.strftime("%m-%d %H:%M", time.gmtime(ks[-1] * 60)))
