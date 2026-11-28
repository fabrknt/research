"""Closed-labelled hours from 27 Nov 21:00 UTC on (after the half-day close, Friday night and Saturday), $10k, per name:
n, median and min of min(r_buy, r_sell), hours >=10, and median hedge bp. Same for real session hours (23/24/25, 27 before 18:00)
for comparison. Not for the gate (outside US hours); shows whether the pool state persists.
usage: python3 -I weekend.py loop.summary.jsonl"""
import json, sys, statistics as st, datetime as d
from collections import defaultdict
hs = {}
for l in open(sys.argv[1]):
    if l.strip():
        h = json.loads(l)
        if h.get("start") is not None:
            hs.setdefault(h["start"], h)
W = defaultdict(list); R = defaultdict(list); H = defaultdict(list)
hrs = []
for k in sorted(hs):
    t = d.datetime.fromtimestamp(k, d.timezone.utc)
    real = t.day in (23, 24, 25) or (t.day == 27 and t.hour < 18)
    wk = (t.day == 27 and t.hour >= 21) or t.day == 28
    if wk:
        hrs.append(t.strftime("%d %H:%M"))
    for c in hs[k]["cells"]:
        if c["usd"] != 10000 or c.get("r_buy") is None or c.get("r_sell") is None:
            continue
        v = min(c["r_buy"], c["r_sell"])
        if real and c["sess"] == "open":
            R[c["sym"]].append(v)
        elif wk and c["sess"] == "closed":
            W[c["sym"]].append(v)
            if c.get("hedge") is not None:
                H[c["sym"]].append(c["hedge"])
print("weekend-window hours:", len(hrs), hrs[0], "to", hrs[-1])
print(f"{'name':7}{'wk n':>5}{'med':>7}{'min':>7}{'>=10':>5}{'hedge':>7} | real med  >=10/n")
for s in sorted(W):
    v = W[s]; r = R.get(s, [])
    hd = f"{st.median(H[s]):7.1f}" if H.get(s) else "      -"
    rr = f"{st.median(r):8.1f} {sum(x >= 10 for x in r):>4}/{len(r)}" if r else "       -"
    print(f"{s:7}{len(v):>5}{st.median(v):7.1f}{min(v):7.1f}{sum(x >= 10 for x in v):>5}{hd} | {rr}")
