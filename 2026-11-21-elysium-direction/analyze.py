"""Q1 leak: passive LP P&L vs fees, by direction against the HyperCore price and by trade size.
usage: analyze.py PAIR   PAIR = HYPE (HYPE/USDC, WHYPE or native) or KNTQ (KNTQ/HYPE)
reads data/trades.jsonl, data/pools.json, data/hl/*.json -> results/leak_PAIR.txt, data/rows_PAIR_E.json, data/rows_PAIR_HL.json

Reference prices from HyperCore 1-minute candles, linear from each minute's open to its close:
  HYPE: the HYPE perp. KNTQ: spot KNTQ/USDC (@334) / HYPE perp, in HYPE per KNTQ.
  HL = that HyperCore price itself.
  E  = HL x the median (Elysium execution price / HL) over the previous 30 minutes of this pair's trades: the
       local basis, the measure of the earlier 11-09..11 study (flowfee.py).
Direction: "toward" when the trade moves its pool's price closer to the reference (pool price before = after the
pool's previous swap, from sqrtPriceX96), "away" otherwise.
LP P&L, fee included, at horizon h: -s * (ref(t+h) / px - 1) * USD, s = +1 when the user buys the base token.
Fee: from the pool's own prices, per trade: the no-fee average price of a swap from price Pb to Pa at constant
liquidity is sqrt(Pb*Pa); fee = s * USD * (1 - sqrt(Pb*Pa) / px). This reads the fee actually charged (v3 forks
here have dynamic fees; v4 hooks may override). Pre-fee P&L = P&L - fee."""
import sys, os, json, bisect, collections, statistics as st, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import WHYPE, USDC, NATIVE
PAIR = sys.argv[1]
KNTQ = "0xe45a355d9e9cad2ad85f2d03e3ee3102a036acf0"
H = {WHYPE, NATIVE}
db = json.load(open("data/pools.json"))["pools"]
ld = lambda f: {int(k): v for k, v in json.load(open(f"data/hl/{f}.json")).items()}
def interp(c, t):
    m = int(t // 60); x = c.get(m)
    return x[0] + (x[1] - x[0]) * ((t - m * 60) / 60) if x else None
hype = ld("HYPE")
if PAIR == "HYPE":
    BASE, QUOTE = H, {USDC}
    ref = lambda t: interp(hype, t)
    usd_of = lambda q, t: abs(q)
else:
    BASE, QUOTE = {KNTQ}, H; kq = ld("at334")
    def ref(t):
        a, b = interp(kq, t), interp(hype, t)
        return a / b if a and b else None
    usd_of = lambda q, t: abs(q) * interp(hype, t)
venues = {k for k, p in db.items() if "t0" in p and ((p["t0"] in BASE and p["t1"] in QUOTE) or (p["t0"] in QUOTE and p["t1"] in BASE))}
tr = []
for line in open("data/trades.jsonl"):
    r = json.loads(line)
    if r["key"] not in venues or not r["sp"]: continue
    p = db[r["key"]]; bfirst = p["t0"] in BASE
    b, q = (r["a0"], r["a1"]) if bfirst else (r["a1"], r["a0"])
    x = (r["sp"] / 2 ** 96) ** 2 * 10 ** (p["s0"][1] - p["s1"][1])  # token1 per token0
    r["after"] = x if bfirst else (1 / x if x else None)
    r["s"] = 1 if b > 0 else -1; r["px"] = abs(q / b); r["m"] = ref(r["t"])
    if not r["m"] or not r["after"]: continue
    r["usd"] = usd_of(q, r["t"])
    if abs(r["px"] / r["m"] - 1) < 0.05 and r["usd"] >= 1: tr.append(r)
tr.sort(key=lambda r: (r["n"], r["i"]))
T = [r["t"] for r in tr]; G = [r["px"] / r["m"] for r in tr]
def basis(t):
    lo, hi = bisect.bisect_left(T, t - 1800), bisect.bisect_left(T, t)
    return st.median(G[lo:hi]) if hi - lo >= 5 else None
def E(t):
    m, g = ref(t), basis(t)
    return m * g if m and g else None
days = (T[-1] - T[0]) / 86400
HZ = (0, 60, 300, 3600)
prev = {}; rows = {"E": [], "HL": []}; keep = []
for r in tr:
    before = prev.get(r["key"]); prev[r["key"]] = r["after"]
    if before is None: continue
    avg0 = (before * r["after"]) ** 0.5
    f = r["s"] * (1 - avg0 / r["px"])
    r["feebp"] = f * 1e4; r["feeusd"] = max(0.0, min(f, 0.03)) * r["usd"]  # clipped: multi-range swaps and hook pools can misread
    keep.append(r)
    for rf in ("E", "HL"):
        fn = E if rf == "E" else ref
        R0 = fn(r["t"] - 0.001)
        if not R0: continue
        r["tow_" + rf] = abs(r["after"] / R0 - 1) < abs(before / R0 - 1)
        for hz in HZ:
            R = fn(r["t"] + hz)
            if R: r[f"lp{hz}_{rf}"] = -r["s"] * (R / r["px"] - 1) * r["usd"]
        R5 = fn(r["t"] + 300); g0 = basis(r["t"] - 0.001); m5 = ref(r["t"] + 300)
        e5f = (m5 * g0 if rf == "E" else m5) if m5 and g0 else None
        if R5 and e5f:
            rows[rf].append(dict(t=r["t"], px=r["px"], e0=R0, e5=R5, e5f=e5f, pool=r["key"], fee=r["feeusd"] / r["usd"] * 1e4, usd=r["usd"], s=r["s"],
                                 toward=r["tow_" + rf], dev=(before / R0 - 1) * 1e4, hl0=ref(r["t"] - 0.001), hl5=m5, E0=E(r["t"] - 0.001), E5=E(r["t"] + 300),
                                 lp5=r[f"lp300_{rf}"], feeusd=r["feeusd"], h=r["h"]))
tr = keep
for rf in rows: json.dump(rows[rf], open(f"data/rows_{PAIR}_{rf}.json", "w"))
out = []; pr = lambda *a: out.append(" ".join(str(x) for x in a))
def short(k):
    p = db[k]; return f"v4 {k[42:50]} hook {p['hooks'][:6]}" if p["kind"] == "v4" else f"v3 {k[:8]}"
vol = collections.Counter()
for r in tr: vol[r["key"]] += r["usd"]
g = lambda t: time.strftime("%Y-%m-%d %H:%M", time.gmtime(t))
pr(f"{PAIR} pair on Elysium: {len(tr)} trades in {len(vol)} venues, {days:.2f} days ({g(T[0])} to {g(T[-1])} UTC), ${sum(vol.values()) / days:,.0f}/day")
pr(f"median (execution price / HyperCore reference - 1): {st.median((x - 1) * 1e4 for x in G):+.1f} bp; by UTC day: " +
   ", ".join(f"{d} {st.median(v):+.0f}" for d, v in sorted(collections.defaultdict(list, {}).items())))
byday = collections.defaultdict(list)
for t, x in zip(T, G): byday[g(t)[:10]].append((x - 1) * 1e4)
pr("  by UTC day: " + ", ".join(f"{d} {st.median(v):+.0f} bp" for d, v in sorted(byday.items())))
pr("\n## Venues (top 12 by USD)\n| venue | nominal fee pips | fee read from prices, median bp | trades | USD/day | fees $/day | LP P&L $/day vs E, 5 min (fee incl.) | vs HL, 5 min | median trade $ |\n|---|---|---|---|---|---|---|---|---|")
top = [k for k, _ in vol.most_common(12)]
for k in top:
    R = [r for r in tr if r["key"] == k]
    pr(f"| {short(k)} | {db[k].get('fee')} | {st.median(r['feebp'] for r in R):.1f} | {len(R)} | ${vol[k] / days:,.0f} | ${sum(r['feeusd'] for r in R) / days:,.0f} | "
       f"${sum(r.get('lp300_E', 0) for r in R) / days:+,.0f} | ${sum(r.get('lp300_HL', 0) for r in R) / days:+,.0f} | ${st.median(r['usd'] for r in R):,.0f} |")
def table(title, groups, rf):
    pr(f"\n## {title}, reference {rf} ($/day; bp per $ of volume)\n| group | trades | USD/day | fees $/day | pre-fee P&L at 0 s / 60 s / 5 min / 1 h | P&L fee incl., 5 min | bp pre-fee, 5 min | bp fee incl., 5 min |\n|---|---|---|---|---|---|---|---|")
    for name, R in groups:
        R = [r for r in R if f"lp300_{rf}" in r and f"lp3600_{rf}" in r]
        if not R: continue
        U = sum(r["usd"] for r in R); F = sum(r["feeusd"] for r in R)
        pre = [sum(r[f"lp{hz}_{rf}"] - r["feeusd"] for r in R) / days for hz in HZ]
        p5 = sum(r[f"lp300_{rf}"] for r in R)
        pr(f"| {name} | {len(R)} | ${U / days:,.0f} | ${F / days:,.0f} | {' / '.join(f'{x:+,.0f}' for x in pre)} | ${p5 / days:+,.0f} | {(p5 - F) / U * 1e4:+.1f} | {p5 / U * 1e4:+.1f} |")
size = lambda u: "< $100" if u < 100 else "$100–1k" if u < 1e3 else "$1k–10k" if u < 1e4 else "≥ $10k"
SZ = ("< $100", "$100–1k", "$1k–10k", "≥ $10k")
for rf in ("HL", "E"):
    gr = [("all", tr)] + [(d, [r for r in tr if r.get("tow_" + rf) == (d == "toward")]) for d in ("toward", "away")]
    gr += [(f"{d}, {s}", [r for r in tr if r.get("tow_" + rf) == (d == "toward") and size(r["usd"]) == s]) for d in ("toward", "away") for s in SZ]
    gr += [(f"{d}, {short(k)}", [r for r in tr if r["key"] == k and r.get("tow_" + rf) == (d == "toward")]) for k in top[:4] for d in ("toward", "away")]
    table("Direction and size", gr, rf)
open(f"results/leak_{PAIR}.txt", "w").write("\n".join(out) + "\n"); print("\n".join(out))
