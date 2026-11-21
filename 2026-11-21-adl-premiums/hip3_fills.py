"""node_fills_by_block lines on stdin -> time,coin,px,sz,dir for HIP-3 coins (name has ':')."""
import csv, json, sys
w = csv.writer(sys.stdout)
for line in sys.stdin:
    if '":' not in line or ':' not in line:
        continue
    b = json.loads(line)
    for _user, f in b["events"]:
        c = f["coin"]
        if ":" in c:
            w.writerow([f["time"], c, f["px"], f["sz"], f.get("dir", "")])
