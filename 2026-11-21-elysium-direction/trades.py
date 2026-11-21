"""Decode every v4/v3/v2 swap in data/logs into trades, identify the top venues, and price each in USD.
usage: trades.py [TOP_KEYS=600]  -> data/trades.jsonl, results/venues.txt
A trade row: t (block time), n, i, h (tx), key (venue), base/quote token, db (user's base change), dq (user's quote change),
fee (pips: v4 from the Swap event incl. dynamic fees, v3 from fee()), sp (sqrtPriceX96 after), L (liquidity after)."""
import sys, os, json, glob, collections, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import *
import pools as P
TOP = int(sys.argv[1]) if len(sys.argv) > 1 else 600
FILES = sorted(glob.glob("data/logs/part_*.jsonl"), key=lambda f: int(f.split("_")[-1].split(".")[0]))
def stream():
    for f in FILES:
        for line in open(f): yield json.loads(line)
key = lambda l: l["a"] + (l["tp"][1] if l["tp"][0] == V4 else "")
cnt = collections.Counter(); first = last = None; nlogs = 0
for l in stream():
    nlogs += 1; first = first or l; last = l
    if l["tp"][0] in (V4, V3, V2): cnt[key(l)] += 1
print("logs", nlogs, file=sys.stderr)
db = P.ident([k for k, _ in cnt.most_common(TOP)], P.load())
hl = {int(k): v for k, v in json.load(open("data/hl/HYPE.json")).items()}
def hmid(t):
    m = int(t // 60); c = hl.get(m)
    if not c: return None
    return c[0] + (c[1] - c[0]) * ((t - m * 60) / 60)   # open at the minute's start, close at its end
STABLE = {USDC}
HYPEs = {WHYPE, NATIVE}
out = open("data/trades.jsonl", "w"); vol = collections.Counter(); n_tr = collections.Counter()
for l in stream():
    k = key(l); p = db["pools"].get(k)
    if not p or "t0" not in p: continue
    w = [l["d"][2 + j:2 + j + 64] for j in range(0, len(l["d"]) - 2, 64)]
    tp = l["tp"][0]
    if tp == V4: u0, u1, sp, L, fee = s256(w[0]), s256(w[1]), int(w[2], 16), int(w[3], 16), int(w[5], 16)
    elif tp == V3: u0, u1, sp, L, fee = -s256(w[0]), -s256(w[1]), int(w[2], 16), int(w[3], 16), p.get("fee")
    elif tp == V2: u0, u1, sp, L, fee = int(w[2], 16) - int(w[0], 16), int(w[3], 16) - int(w[1], 16), None, None, 3000
    else: continue
    if u0 == 0 or u1 == 0 or (u0 > 0) == (u1 > 0): continue
    d0, d1 = p["s0"][1], p["s1"][1]
    a0, a1 = u0 / 10 ** d0, u1 / 10 ** d1
    t = l["t"]; m = hmid(t)
    usd = abs(a0) if p["t0"] in STABLE else abs(a1) if p["t1"] in STABLE else (abs(a0) * m if p["t0"] in HYPEs and m else abs(a1) * m if p["t1"] in HYPEs and m else 0)
    vol[k] += usd; n_tr[k] += 1
    out.write(json.dumps(dict(t=t, n=l["n"], i=l["i"], h=l["h"], key=k, a0=a0, a1=a1, fee=fee, sp=sp, L=L, usd=round(usd, 2)), separators=(",", ":")) + "\n")
out.close()
days = (last["t"] - first["t"]) / 86400
os.makedirs("results", exist_ok=True)
with open("results/venues.txt", "w") as f:
    f.write(f"{nlogs} swap logs, {days:.2f} days, blocks {first['n']}..{last['n']}\n")
    f.write("venues by USD volume (USD only where one side is USDC or HYPE/WHYPE; HYPE at the HyperCore perp mid)\n")
    f.write("| venue | pair | fee (pips, last) | hooks | trades | USD/day |\n|---|---|---|---|---|---|\n")
    for k, v in vol.most_common(40):
        p = db["pools"][k]
        f.write(f"| {k[:10]}{'…' + k[42:52] if len(k) > 42 else ''} | {p['s0'][0]}/{p['s1'][0]} | {p.get('fee')} | {p.get('hooks', p['kind'])[:10]} | {n_tr[k]} | ${v / days:,.0f} |\n")
print(open("results/venues.txt").read())
