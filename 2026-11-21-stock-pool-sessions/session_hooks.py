"""Fees actually charged (Swap.fee) by the session-aware hooks, by session and bell window, and the LP result in
their pools. Hooks: every hook in results/hooks_top20.json whose verified source mentions sessions."""
import json, os, pickle, sys
from collections import defaultdict
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H)
import rowtype  # noqa: F401
hk = {x["hook"]: x["sourcify"]["name"].split(":")[-1] for x in json.load(open(f"{H}/results/hooks_top20.json"))
      if x["sourcify"] and "session" in x["sourcify"]["keywords"]}
rows = [r for r in pickle.load(open(f"{H}/data/rows.pkl", "rb"))["rows"] if r.hooks in hk]
tot_all = sum(r.usd for r in pickle.load(open(f"{H}/data/rows.pkl", "rb"))["rows"])
g = defaultdict(lambda: defaultdict(float))
for r in rows:
    for b in (r.sess, r.bell, "all"):
        if b is None:
            continue
        a = g[(hk[r.hooks], b)]
        a["usd"] += r.usd
        a["fee"] += r.fee * r.usd
        a["zero"] += r.usd if r.fee == 0 else 0
        if r.lp.get(3600) is not None:
            a["u1h"] += r.usd
            a["net1h"] += r.lp[3600] * r.usd
out = {}
print(f"session-aware hooks carry ${sum(r.usd for r in rows)/1e6:.1f}M of ${tot_all/1e6:.1f}M ({sum(r.usd for r in rows)/tot_all:.1%})")
for (name, b), a in sorted(g.items()):
    o = {"usd": round(a["usd"]), "fee_bp": round(a["fee"] / a["usd"] * 1e4, 1), "zero_fee_share": round(a["zero"] / a["usd"], 3),
         "lp_net_bp_1h": round(a["net1h"] / a["u1h"] * 1e4, 1) if a["u1h"] else None}
    out[f"{name}/{b}"] = o
    print(f"{name:16s} {b:12s} ${a['usd']/1e6:6.1f}M  avg fee {o['fee_bp']:5.1f}bp  fee=0 on {o['zero_fee_share']:5.1%}  LP 1h {o['lp_net_bp_1h']}bp")
json.dump(out, open(f"{H}/results/session_hooks.json", "w"), indent=1)
