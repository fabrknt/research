"""What if the fee depended on stock-specific information (session, distance from an external reference)?

For each swap with a markout at horizon h: gross = LP return before fee, fee = the fee it paid.
A policy gives a new fee f' >= f. The swap still happens with probability
    r = max(0, 1 - e x (f' - f in bp))        e = volume lost per bp of extra fee (assumption, a range)
and the LP earns r x (gross + f') x usd. The same informed and uninformed swaps are kept or lost at the
same rate (no selection), which favours nothing; see README for why that is conservative/optimistic.
Assumes every pool of a stock moves together (otherwise the flow just goes to the cheaper pool).
Usage: python3 -I counterfactual.py [h=300]
"""
import json, os, pickle, sys
from collections import defaultdict

H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H)
import rowtype  # noqa: F401 (unpickling)
HZ = int(sys.argv[1]) if len(sys.argv) > 1 else 300
ELAST = [0.0, 0.01, 0.03, 0.10]
GRID = [0, 1, 2, 3, 5, 7.5, 10, 15, 20, 30, 50]
CAP = 100e-4  # no policy charges more than 1% (Helm's ceiling outside earnings windows)
SESS = ["rth", "pre", "after", "overnight", "weekend"]

rows = [r for r in pickle.load(open(f"{H}/data/rows.pkl", "rb"))["rows"] if r["lp"].get(HZ) is not None]
days = (max(r["t"] for r in rows) - min(r["t"] for r in rows)) / 86400


def key(r):
    return r["bell"] if r["bell"] else r["sess"]


def evaluate(fee_of, e):
    """-> LP P&L before, after, volume lost, and the volume-weighted fee charged (at e = 0)."""
    base = new = lost = feeu = 0.0
    for r in rows:
        f = r["fee"]
        g = r["lp"][HZ] - f
        f2 = max(f, min(CAP, fee_of(r)))
        keep = max(0.0, 1 - e * (f2 - f) * 1e4)
        base += (g + f) * r["usd"]
        new += keep * (g + f2) * r["usd"]
        lost += (1 - keep) * r["usd"]
        feeu += f2 * r["usd"]
    return base, new, lost, feeu / vol


vol = sum(r["usd"] for r in rows)
out = {"h": HZ, "days": round(days, 1), "volume_usd": round(vol), "policies": []}
print(f"h={HZ}s  {days:.1f} days  volume ${vol/1e6:.1f}M")

# 2. fixed schedules (one example of a session-only schedule and reference-distance surcharges)
FIXED = {"rth": 3, "pre": 5, "after": 5, "overnight": 5, "weekend": 5, "open": 20, "monday_open": 30, "close": 15}


def dist(r, a):
    """a x |pool - reference| before the swap, only on swaps that move the pool toward the reference.
    Distances above 500 bp are treated as unknown (stale or empty pools) and get no surcharge."""
    if not r["toward"] or r["d_bp"] is None or abs(r["d_bp"]) > 500:
        return 0.0
    return a * abs(r["d_bp"]) / 1e4


policies = {
    "session schedule (rth 3, ext/overnight/weekend 5, open 20, Monday open 30, close 15 bp)": lambda r: FIXED[key(r)] / 1e4,
    "distance: toward-reference swaps pay 0.5 x distance": lambda r: dist(r, 0.5),
    "distance: toward-reference swaps pay 1.0 x distance": lambda r: dist(r, 1.0),
    "session schedule + 0.5 x distance": lambda r: max(FIXED[key(r)] / 1e4, dist(r, 0.5)),
}
base_fee = sum(r["fee"] * r["usd"] for r in rows) / vol
print(f"actual volume-weighted fee {base_fee*1e4:.2f} bp")
for name, fn in policies.items():
    # control: the same average fee, added evenly to every swap (no stock-specific information)
    target = evaluate(fn, 0)[3]
    lo, hi = 0.0, 0.01
    for _ in range(40):
        c = (lo + hi) / 2
        if evaluate(lambda r, c=c: r["fee"] + c, 0)[3] < target:
            lo = c
        else:
            hi = c
    ctrl = lambda r, c=c: r["fee"] + c
    for nm, f in ((name, fn), (f"   control: +{c*1e4:.2f} bp on every swap (same avg fee)", ctrl)):
        for e in ELAST:
            b, n, l, fu = evaluate(f, e)
            out["policies"].append({"policy": nm, "elasticity_per_bp": e, "lp_before_usd": round(b),
                                    "lp_after_usd": round(n), "volume_lost_share": round(l / vol, 3),
                                    "avg_fee_bp": round(fu * 1e4, 2)})
            print(f"{nm[:62]:62s} e={e:4.0%}: avg fee {fu*1e4:5.2f}bp  LP ${b/1e3:8.1f}K -> ${n/1e3:8.1f}K  "
                  f"avoided ${(n-b)/1e3:7.1f}K  volume lost {l/vol:5.1%}")
json.dump(out, open(f"{H}/results/counterfactual_{HZ}.json", "w"), indent=1)
