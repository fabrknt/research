"""HYPE perp hourly funding on HyperCore for the tape's window (free public info API, no key; it keeps the history).
usage: python3 -I fetch_funding.py -> data/funding_hype.csv (hour_start_unix_s,rate); data/ is git-ignored"""
import json, os, urllib.request
T0, T1 = 1794960068, 1795237196  # the tape's first and last trade
body = {"type": "fundingHistory", "coin": "HYPE", "startTime": (T0 - 3600) * 1000, "endTime": (T1 + 3600) * 1000}
req = urllib.request.Request("https://api.hyperliquid.xyz/info", json.dumps(body).encode(),
                             {"content-type": "application/json", "user-agent": "curl/8"})
rows = json.load(urllib.request.urlopen(req, timeout=60))
os.makedirs("data", exist_ok=True)
with open("data/funding_hype.csv", "w") as f:
    f.write("t,rate\n")
    for r in rows:
        f.write(f"{int(r['time']) // 1000},{r['fundingRate']}\n")
print(len(rows), "hours,", rows[0]["time"], "to", rows[-1]["time"])
