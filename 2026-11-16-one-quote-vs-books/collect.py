"""Every few minutes, save Variational's quotes and the Lighter and Hyperliquid books for the same markets.

Variational publishes one dealer's bid/ask at $1k, $100k and $1M (GET /metadata/v2/stats, no key).
Lighter: the resting orders, up to 250 a side (GET /api/v1/orderBookOrders, no key).
Hyperliquid: l2Book, 20 levels a side, at full precision and at 4 significant figures (nSigFigs=4) to see further out.

    python3 collect.py 2880 300     # 2880 rounds, every 300 s (10 days) -> data/snap-YYYYMMDD.jsonl
"""
import json
import os
import sys
import time
import urllib.request

VAR = "https://omni-client-api.prod.ap-northeast-1.variational.io/metadata/v2/stats"
LIT = "https://mainnet.zklighter.elliot.ai/api/v1"
HL = "https://api.hyperliquid.xyz/info"

# Variational base -> name on Hyperliquid's HIP-3 dexes, where it differs.
HL_ALIAS = {"US100": "XYZ100", "US500": "SP500", "XAU": "GOLD", "XAG": "SILVER",
            "USOIL": "CL", "UKOIL": "BRENTOIL", "SKHY": "SKHX"}
TOP = 40  # Variational markets by 24h volume
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def get(url, body=None, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                         headers={"content-type": "application/json",
                                                  "user-agent": "fabrknt-research"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # 429s and timeouts: wait (as long as a 429 asks, at least) and retry
            if i == tries - 1:
                raise
            wait = 2 + 3 * i
            if getattr(e, "code", None) == 429:
                try:
                    wait = max(wait, float(json.load(e).get("retry_after_seconds", 0)) + 1)
                except Exception:
                    pass
            time.sleep(wait)


def hl(body):
    return get(HL, body)


def build_map(var):
    """Pick, for each of Variational's top markets, the Lighter market and the busiest HL coin of the same name."""
    lit = {o["symbol"]: o["market_id"] for o in get(LIT + "/orderBooks")["order_books"]
           if o["status"] == "active" and o["market_type"] == "perp"}
    hlvol = {}
    m, c = hl({"type": "metaAndAssetCtxs"})
    for u, x in zip(m["universe"], c):
        hlvol.setdefault(u["name"], []).append((float(x["dayNtlVlm"]), u["name"]))
    for d in hl({"type": "perpDexs"}):
        if not d:
            continue
        m, c = hl({"type": "metaAndAssetCtxs", "dex": d["name"]})
        for u, x in zip(m["universe"], c):
            base = u["name"].split(":", 1)[1]
            hlvol.setdefault(base, []).append((float(x["dayNtlVlm"]), u["name"]))
    listings = sorted(var["listings"], key=lambda x: -float(x["volume_24h"]))
    out = []
    for x in listings:
        base = x["ticker"].rsplit("-", 1)[0]
        hlc = hlvol.get(HL_ALIAS.get(base, base)) or hlvol.get(base)
        row = {"var": x["ticker"], "lighter": lit.get(base),
               "hl": max(hlc)[1] if hlc else None}
        if row["lighter"] is not None or row["hl"]:
            out.append(row)
        if len(out) == TOP:
            break
    return out


def var_stats():
    return get(VAR, tries=6)


def round_(markets):
    t = time.time()
    var = var_stats()
    byt = {x["ticker"]: x for x in var["listings"]}
    rows = []
    for mk in markets:
        v = byt.get(mk["var"], {})
        # "listing" is the whole row (funding, open interest, volume, ...), kept from 2026-11-21
        row = {"t": t, "var": mk["var"], "mark": v.get("mark_price"), "quotes": v.get("quotes"), "listing": v}
        if mk["lighter"] is not None:
            try:
                d = get(f"{LIT}/orderBookOrders?market_id={mk['lighter']}&limit=250")
                row["lighter"] = {"asks": [(o["price"], o["remaining_base_amount"]) for o in d["asks"]],
                                  "bids": [(o["price"], o["remaining_base_amount"]) for o in d["bids"]],
                                  "t": time.time()}
            except Exception as e:
                row["lighter_err"] = str(e)
            time.sleep(0.4)
        if mk["hl"]:
            try:
                for key, extra in (("hl", {}), ("hl_coarse", {"nSigFigs": 4})):
                    d = hl({"type": "l2Book", "coin": mk["hl"], **extra})
                    row[key] = {"bids": [(l["px"], l["sz"]) for l in d["levels"][0]],
                                "asks": [(l["px"], l["sz"]) for l in d["levels"][1]],
                                "t": d["time"] / 1000}
            except Exception as e:
                row["hl_err"] = str(e)
        rows.append(row)
    return rows


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    every = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    os.makedirs(OUT, exist_ok=True)
    markets = build_map(get(VAR, tries=12))  # a 429 here used to end the run (2026-11-17)
    with open(os.path.join(OUT, "markets.json"), "w") as f:
        json.dump(markets, f, indent=1)
    print(len(markets), "markets", flush=True)
    for i in range(n):
        start = time.time()
        try:
            rows = round_(markets)
            day = time.strftime("%Y%m%d", time.gmtime(start))
            with open(os.path.join(OUT, f"snap-{day}.jsonl"), "a") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")
            print(time.strftime("%H:%M:%S"), i, len(rows), round(time.time() - start, 1), "s", flush=True)
        except Exception as e:
            print("round failed", i, e, flush=True)
        if i < n - 1:
            time.sleep(max(5, every - (time.time() - start)))


if __name__ == "__main__":
    main()
