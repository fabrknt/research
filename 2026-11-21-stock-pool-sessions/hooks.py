"""Inspect hook contracts: v4 permission flags (lowest 14 address bits), dynamic-fee pools, code size, the
TIMESTAMP opcode in runtime code (crude: anything time-aware must read it), and Sourcify-verified source
(name; whether the source mentions sessions/market hours/oracles).
Usage: python3 -I hooks.py <out.json> <hook> [<hook> ...]
       python3 -I hooks.py <out.json> --top N     (the N hooks with the most volume in data/rows.pkl)"""
import json, os, re, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import call

FLAGS = ["afterRemoveLiquidityReturnDelta", "afterAddLiquidityReturnDelta", "afterSwapReturnDelta",
         "beforeSwapReturnDelta", "afterDonate", "beforeDonate", "afterSwap", "beforeSwap", "afterRemoveLiquidity",
         "beforeRemoveLiquidity", "afterAddLiquidity", "beforeAddLiquidity", "afterInitialize", "beforeInitialize"]
KW = r"session|market ?hours|weekend|holiday|opening bell|trading ?hours|nyse|block\.timestamp|oracle|chainlink|pyth|redstone"


def opcodes_has_timestamp(code):
    b = bytes.fromhex(code[2:])
    i = 0
    while i < len(b):
        op = b[i]
        if op == 0x42:
            return True
        i += 1 + (op - 0x5f if 0x60 <= op <= 0x7f else 0)
    return False


def sourcify(a):
    try:
        req = urllib.request.Request(f"https://sourcify.dev/server/v2/contract/4663/{a}?fields=sources,compilation",
                                     headers={"User-Agent": "curl/8.7.1"})
        d = json.load(urllib.request.urlopen(req, timeout=30))
    except Exception:
        return None
    src = "\n".join(v["content"] for k, v in d.get("sources", {}).items() if "lib/" not in k and "node_modules" not in k)
    hits = sorted({m.lower() for m in re.findall(KW, src, re.I)})
    return {"name": d["compilation"].get("fullyQualifiedName"), "keywords": hits}


if __name__ == "__main__":
    out = []
    hooks, vol = sys.argv[2:], {}
    if hooks and hooks[0] == "--top":
        import pickle
        from collections import defaultdict
        H = os.path.dirname(os.path.abspath(__file__))
        import rowtype  # noqa: F401
        v = defaultdict(float)
        for r in pickle.load(open(f"{H}/data/rows.pkl", "rb"))["rows"]:
            if r.hooks != "0x" + "0" * 40:
                v[r.hooks] += r.usd
        tot = sum(v.values())
        hooks = sorted(v, key=lambda h: -v[h])[:int(hooks[1])]
        vol = {h: (round(v[h]), round(v[h] / tot, 4)) for h in hooks}
    for h in hooks:
        v = int(h, 16) & 0x3FFF
        flags = [f for i, f in enumerate(FLAGS) if v >> i & 1]
        code = call("eth_getCode", [h, "latest"])
        o = {"hook": h, "flags": flags, "code_bytes": (len(code) - 2) // 2,
             "timestamp_opcode": opcodes_has_timestamp(code) if len(code) > 2 else None, "sourcify": sourcify(h)}
        if h in vol:
            o["volume_usd"], o["share_of_hooked_volume"] = vol[h]
        out.append(o)
        print(json.dumps(o))
    json.dump(out, open(sys.argv[1], "w"), indent=1)
