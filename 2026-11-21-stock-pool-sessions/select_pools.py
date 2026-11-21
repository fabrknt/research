"""Pools whose two currencies are both in data/tokens.json (stock tokens with an xyz perp, and USDG), at least
one a stock -> data/pools_sel.json. Prints what is new since the 11-13 study (block 113,161,616)."""
import json, os
from collections import Counter
H = os.path.dirname(os.path.abspath(__file__))
tok = json.load(open(f"{H}/data/tokens.json"))
fab = {p["id"] for p in json.load(open(f"{H}/data/fables_pools.json"))}
sel = [p for p in json.load(open(f"{H}/data/pools_all.json"))
       if p["currency0"] in tok and p["currency1"] in tok and not (tok[p["currency0"]].get("usd") and tok[p["currency1"]].get("usd"))]
json.dump(sel, open(f"{H}/data/pools_sel.json", "w"))
Z = "0x" + "0" * 40
new = [p for p in sel if p["block"] > 113161616]
print(len(sel), "pools;", sum(p["hooks"] != Z for p in sel), "hooked;", sum(p["id"] in fab for p in sel), "Fables")
print("new since 11-13:", len(new), "hooked", sum(p["hooks"] != Z for p in new), "distinct new hooks",
      len({p["hooks"] for p in new if p["hooks"] != Z}))
print("hooks by pool count", Counter(p["hooks"] for p in sel if p["hooks"] != Z).most_common(15))
