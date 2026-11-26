"""Open-labelled hours split into real US session days (UTC day != 26) and 26 Nov (Thanksgiving, NYSE closed).
Per name at $10k: min(r_buy, r_sell) per hour, n, median, min, hours >=10, for each group.
usage: python3 -I holiday.py loop.summary.jsonl"""
import json, sys, statistics as st, datetime as d
from collections import defaultdict
hs = {}
for l in open(sys.argv[1]):
    if l.strip():
        h = json.loads(l)
        if h.get("start") is not None:
            hs.setdefault(h["start"], h)
G = defaultdict(list)
for k in sorted(hs):
    day = d.datetime.fromtimestamp(k, d.timezone.utc).day
    grp = "hol26" if day == 26 else "real"
    for c in hs[k]["cells"]:
        if c["sess"] == "open" and c["usd"] == 10000 and c.get("r_buy") is not None and c.get("r_sell") is not None:
            G[(c["sym"], grp)].append(min(c["r_buy"], c["r_sell"]))
print(f"{'name':7}{'grp':>6}{'n':>3}{'med':>7}{'min':>7}{'>=10':>5}")
for (s, g), v in sorted(G.items()):
    print(f"{s:7}{g:>6}{len(v):>3}{st.median(v):7.1f}{min(v):7.1f}{sum(x >= 10 for x in v):>5}")
