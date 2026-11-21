"""ADL-filtered fill lines on stdin -> one CSV row per ADL fill.

Two archive formats: node_fills_by_block (one block per line, `events` = [user, fill]
pairs) and the older node_fills (one [user, fill] pair per line, no block number).
"""
import csv, json, sys

w = csv.writer(sys.stdout)
for line in sys.stdin:
    b = json.loads(line)
    if isinstance(b, list):
        block, events = "", [b]
    else:
        block, events = b["block_number"], b["events"]
    for user, f in events:
        if f.get("dir") != "Auto-Deleveraging":
            continue
        liq = f.get("liquidation") or {}
        w.writerow([f["time"], block, f["coin"], f["px"], f["sz"], f["side"],
                    f["startPosition"], f["closedPnl"], user,
                    liq.get("liquidatedUser", ""), liq.get("markPx", ""), liq.get("method", "")])
