"""Names for the contracts that carried day-1 volume (tx entry contract `to`, and the Swap event's `sender`, the contract that
called the PoolManager). Ethereum: Blockscout's verified contract name. Base: Blockscout is behind Cloudflare from here, so a
short table of well-known router deployments (source=known) plus Sourcify's verified names (source=sourcify) are used.
usage: python3 -I labels.py -> results/labels.json"""
import json, glob, collections, urllib.request, time, re
KNOWN = {  # same address on several chains unless noted; categories only
    "0x6ff5693b99212da76ad316178a184ab56d299b43": "Uniswap Universal Router",   # Base, v4 UR (Uniswap deployments page)
    "0x66a9893cc07d91d95644aedd05d03f95e1dba8af": "Uniswap Universal Router",   # Ethereum, v4 UR
    "0x111111125421ca6dc452d289314280a0f8842a65": "1inch",
    "0x9008d19f58aabd9ed0d60971565aa8510560ab41": "CoW Protocol",
    "0x0000000000001ff3684f28c67538d4d072c22734": "0x",
    "0x6131b5fae19ea4f9d964eac0408e4408b66337b5": "KyberSwap",
    "0x6a000f20005980200259b80c5102003040001068": "Velora (ParaSwap)",
    "0x19ceead7105607cd444f5ad10dd51356436095a1": "Odos",   # Base
    "0xcf5540fffcdc3d510b18bfca6d2b9987b0772559": "Odos",   # Ethereum
    "0x663dc15d3c1ac63ff12e45ab68fea3f0a883c251": "deBridge",   # Ethereum, proxy whose implementation Blockscout names DeBridgeRouter
}
RULES = [("UniV4StandardModule", "Arrakis Modular vault module"), ("DeBridgeRouter", "deBridge"), ("EntryPoint", "ERC-4337 smart wallet"), ("Tycho", "Tycho router (solvers)"), ("RedSnwapper", "Sushi (RedSnwapper)"),
         ("HookAdapter", "aggregator adapter (unattributed)"), ("UniswapV4Adapter", "aggregator adapter (unattributed)"),
         ("RelayApproval", "Relay"), ("DeBridge", "deBridge"), ("^PoolManager$", "PoolManager called directly"), ("LiFi", "LI.FI"), ("Multicall", "Multicall3"),
         ("UniversalRouter", "Uniswap Universal Router"), ("AggregationRouter", "1inch"), ("Settler", "0x"), ("AllowanceHolder", "0x"),
         ("GPv2", "CoW Protocol"), ("Odos", "Odos"), ("MetaAggregation", "KyberSwap"), ("Augustus", "Velora (ParaSwap)"),
         ("Reactor", "UniswapX"), ("MetaSwap", "MetaMask"), ("DexRouter", "OKX"), ("LiFi", "LI.FI"), ("Bebop", "Bebop"),
         ("RelayRouter", "Relay"), ("RelayReceiver", "Relay"), ("Banana", "Telegram bot"), ("Maestro", "Telegram bot"), ("Sigma", "Telegram bot"),
         ("V4Router", "Uniswap v4 router (other)"), ("PositionManager", "Uniswap PositionManager"), ("Rainbow", "Rainbow"),
         ("ZeroEx", "0x"), ("Enso", "Enso"), ("Bungee", "Bungee"), ("Socket", "Bungee"), ("Kyber", "KyberSwap"), ("Pendle", "Pendle")]
def bs(addr):
    for k in range(2):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(f"https://eth.blockscout.com/api/v2/addresses/{addr}", headers={"User-Agent": "research-script"}), timeout=20))
            impl = [i.get("name") for i in (d.get("implementations") or []) if i.get("name")]
            name = d.get("name")
            if impl and name and "Proxy" in name: name = f"{name}->{impl[0]}"
            return name, d.get("is_contract"), d.get("is_verified")
        except Exception:
            time.sleep(2 + 2 * k)
    return None, None, None
CID = {"base": 8453, "unichain": 130, "arbitrum": 42161}
def sf(ch, addr):
    """Sourcify v2: the verified contract's name (Base's Blockscout and Basescan are not reachable without a browser)."""
    for k in range(2):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(f"https://sourcify.dev/server/v2/contract/{CID[ch]}/{addr}?fields=compilation", headers={"User-Agent": "research-script"}), timeout=20))
            return (d.get("compilation") or {}).get("name"), None, None
        except Exception:
            time.sleep(2)
    return None, None, None
vol = collections.Counter()
for fn in glob.glob("data/swaps72_*.json"):
    D = json.load(open(fn)); ch = D["chain"]
    t0 = D["tb0"]
    tot = collections.Counter()
    for r in D["rows"]:
        if r["t"] - t0 >= 86400: continue
        tot[r["to"]] += 1; tot[r["sender"]] += 1
    for a, c in tot.most_common(60):
        if c >= 3: vol[(ch, a)] += 1
    for x in D["mods"]: vol[(ch, x["sender"])] += 1   # who adds and removes liquidity
import os
out = json.load(open("results/labels.json")) if os.path.exists("results/labels.json") else {}
import concurrent.futures as cf
todo = [(ch, a) for (ch, a) in vol if f"{ch}:{a}" not in out]
with cf.ThreadPoolExecutor(8) as ex:
    looked = dict(zip(todo, ex.map(lambda t: bs(t[1]) if t[0] == "ethereum" else sf(t[0], t[1]), todo)))
for (ch, a) in todo:
    cat = KNOWN.get(a); name = None; src = "known" if cat else None
    name, isc, ver = looked[(ch, a)]
    if True:
        if name and not cat:
            cat = next((c for pat, c in RULES if re.search(pat, name, re.I)), None) or f"other verified: {name}"
            src = "blockscout" if ch == "ethereum" else "sourcify"
    out[f"{ch}:{a}"] = dict(cat=cat or "unlabeled", name=name, src=src)
    print(ch, a, name, cat, flush=True)
for k, v in out.items():   # re-derive categories from names so rule changes apply to cached entries
    a_ = k.split(":")[1]
    if a_ in KNOWN: v["cat"] = KNOWN[a_]
    elif v["src"] in ("blockscout", "sourcify") and v["name"]:
        v["cat"] = next((c for pat, c in RULES if re.search(pat, v["name"], re.I)), None) or f"other verified: {v['name']}"
json.dump(out, open("results/labels.json", "w"), indent=1)
