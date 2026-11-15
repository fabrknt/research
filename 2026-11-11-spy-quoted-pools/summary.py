"""Join results with GeckoTerminal current TVL (estimate) -> annualized fee/TVL and LVR/TVL.
usage: python3 -I summary.py DATA_DIR RESULTS_JSON"""
import json, sys
D, RES = sys.argv[1], sys.argv[2]
tvl = {}
for p in json.load(open(f"{D}/gt_multi.json"))["data"]:
    tvl[p["attributes"]["address"].lower()[:10]] = float(p["attributes"]["reserve_in_usd"])
pools = {p["name"]: p for p in json.load(open(f"{D}/pools.json"))}
rows = json.load(open(RES))
print(f"{'pool':26} {'fee':>6} {'TVLnow$':>10} {'vol/TVL/d':>9} {'fee%TVL/yr':>10} {'LVR%TVL/yr':>10} {'fee/LVR':>7} {'σ':>6}")
for r in sorted(rows, key=lambda r: (r["stock"], r["quote"] != "SPY", r["pool"])):
    p = pools[r["pool"]]
    k = ("0x" + p["key"] if p["kind"] == "v4" else p["key"]).lower()[:10]
    T = tvl.get(k)
    if not T or not r["days"]: continue
    a = 365 / r["days"]
    print(f"{r['pool']:26} {r['feetier']:>6} {T:10,.0f} {r['vol_usd']/r['days']/T:9.2f} {r['fees_usd']*a/T:10.1%} {r['lvr_usd']*a/T:10.1%} {r['fee_over_lvr']:7.2f} {r['sigma_ann']:6.1%}")
