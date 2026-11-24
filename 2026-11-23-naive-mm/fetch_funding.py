"""HYPE perp hourly funding on HyperCore for a tape's window (free public info API, no key; it keeps the history).
usage: python3 -I fetch_funding.py [TAPE.csv] [OUT.csv]
       defaults: tape/elysium_hype_usdc.csv -> data/funding_hype.csv (hour_start_unix_s,rate); data/ is git-ignored"""
import json, os, sys, urllib.request
tape = sys.argv[1] if len(sys.argv) > 1 else "tape/elysium_hype_usdc.csv"
out = sys.argv[2] if len(sys.argv) > 2 else "data/funding_hype.csv"
ts = [int(l.split(",", 1)[0]) for l in open(tape).read().splitlines()[1:]]
T0, T1 = ts[0], ts[-1]  # the tape's first and last trade
body = {"type": "fundingHistory", "coin": "HYPE", "startTime": (T0 - 3600) * 1000, "endTime": (T1 + 3600) * 1000}
req = urllib.request.Request("https://api.hyperliquid.xyz/info", json.dumps(body).encode(),
                             {"content-type": "application/json", "user-agent": "curl/8"})
rows = json.load(urllib.request.urlopen(req, timeout=60))
os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
with open(out, "w") as f:
    f.write("t,rate\n")
    for r in rows:
        f.write(f"{int(r['time']) // 1000},{r['fundingRate']}\n")
print(len(rows), "hours,", rows[0]["time"], "to", rows[-1]["time"])
