"""Token map: Robinhood stock tokens that have an xyz (HIP-3) perp, plus USDG -> data/tokens.json.
Source: ~/src/rh-measure/data/rhj_assets.json (Robinhood's asset list as saved on 2026-11-13, read only)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coins import HL_COIN
H = os.path.dirname(os.path.abspath(__file__))
a = json.load(open(os.path.expanduser("~/src/rh-measure/data/rhj_assets.json")))["assets"]
out = {"0x5fc5360d0400a0fd4f2af552add042d716f1d168": {"sym": "USDG", "dec": 6, "usd": True}}
for x in a:
    if x["tokenSymbol"] in HL_COIN:
        for d in x["deployments"]:
            if d["chainId"] == 4663:
                out[d["contractAddress"].lower()] = {"sym": x["tokenSymbol"], "dec": int(x["tokenDecimals"]),
                                                    "mult": float(x.get("currentMultiplier") or 1)}
json.dump(out, open(f"{H}/data/tokens.json", "w"), indent=1)
print(len(out), "tokens", sorted(v["sym"] for v in out.values()))
