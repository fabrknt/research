"""Read each Fables pool's on-chain session fee floors (FablesRWA.floorConfig(poolId), verified source on
Sourcify, chain 4663) -> results/fables_floor_config.json. Pools whose hook is not a FablesRWA return nothing."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import call
H = os.path.dirname(os.path.abspath(__file__))
FIELDS = ["openFloor", "overnightFloor", "closedFloor", "spikeMult", "closedSpike", "descentWindow",
          "closeFloor", "closeBefore", "closeAfter"]
sel = call("web3_sha3", ["0x" + "floorConfig(bytes32)".encode().hex()])[:10]
tok = json.load(open(f"{H}/data/tokens.json")) if os.path.exists(f"{H}/data/tokens.json") else {}
out = []
for p in json.load(open(f"{H}/data/fables_pools.json")):
    try:
        r = call("eth_call", [{"to": p["hooks"], "data": sel + p["id"][2:]}, "latest"], retries=3)
    except Exception as e:
        r = None
    cfg = None
    if r and len(r) >= 2 + 64 * 9:
        b = bytes.fromhex(r[2:])
        v = [int.from_bytes(b[32 * i:32 * i + 32], "big") for i in range(9)]
        if any(v):
            cfg = dict(zip(FIELDS, v))
    s0 = tok.get(p["currency0"], {}).get("sym", p["currency0"][:8]); s1 = tok.get(p["currency1"], {}).get("sym", p["currency1"][:8])
    out.append({"pair": f"{s0}/{s1}", "id": p["id"], "hooks": p["hooks"], "floorConfig_pips": cfg})
    if cfg:
        print(f"{s0}/{s1}", p["hooks"][:10], cfg)
json.dump(out, open(f"{H}/results/fables_floor_config.json", "w"), indent=1)
print(sum(1 for o in out if o["floorConfig_pips"]), "of", len(out), "pools have a session floor config")
