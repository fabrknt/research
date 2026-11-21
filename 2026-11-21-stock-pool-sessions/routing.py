"""Who sends the flow, and does flow reach the hooked pools?

1. Swap.sender (the contract that called PoolManager.swap) by volume, for hookless / Fables / other hooked pools.
2. tx.to for a random sample of transactions (eth_getTransactionByHash), same split.
3. Names: Sourcify-verified contract names (chain 4663) for the top addresses.
4. Best-quote check on stock/USDG pairs: at each swap, every live pool of the pair is priced at its last
   post-swap price and its last observed LP fee (marginal price only: no depth); does the swap go to the
   cheapest pool, and how often is the cheapest a hooked one that the flow skips?
Reads data/pchunks (raw swaps) and data/rows.pkl. Writes results/routing.json.
"""
import csv, glob, json, os, pickle, random, sys, urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import call

H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H)
import rowtype  # noqa: F401 (unpickling)
Z = "0x" + "0" * 40
USDG = "0x5fc5360d0400a0fd4f2af552add042d716f1d168"
tokens = json.load(open(f"{H}/data/tokens.json"))
pools = {p["id"]: p for p in json.load(open(f"{H}/data/pools_sel.json"))}
fables = {p["id"] for p in json.load(open(f"{H}/data/fables_pools.json"))}
rows = pickle.load(open(f"{H}/data/rows.pkl", "rb"))["rows"]


def kind(pid):
    p = pools[pid]
    return "hookless" if p["hooks"] == Z else ("fables" if pid in fables else "other_hook")


_names = {}
EIP1967 = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"


def name(a):
    if a in _names:
        return _names[a]
    n = None
    try:
        req = urllib.request.Request(f"https://sourcify.dev/server/v2/contract/4663/{a}?fields=compilation",
                                     headers={"User-Agent": "curl/8.7.1"})
        n = json.load(urllib.request.urlopen(req, timeout=30))["compilation"].get("fullyQualifiedName")
    except Exception:
        pass
    if n is None:
        code = call("eth_getCode", [a, "latest"])
        impl = "0x" + call("eth_getStorageAt", [a, EIP1967, "latest"])[-40:] if code != "0x" else None
        if code == "0x":
            n = "EOA"
        elif code.startswith("0xef0100") and len(code) == 48:
            n = f"EIP-7702 account -> {name('0x' + code[8:])}"
        elif impl and int(impl, 16):
            n = f"proxy -> {name(impl)}"
        elif code.startswith("0x363d3d373d3d3d363d73"):
            n = f"minimal proxy -> {name('0x' + code[22:62])}"
        else:
            n = f"unverified contract ({(len(code) - 2) // 2} bytes)"
    _names[a] = n
    return n


out = {}
vol = defaultdict(float)
by = defaultdict(lambda: defaultdict(float))
for r in rows:
    k = kind(r["pool"])
    vol[k] += r["usd"]
    by[k][r["sender"]] += r["usd"]
tot = sum(vol.values())
print("volume by pool kind", {k: f"${v/1e6:.1f}M ({v/tot:.1%})" for k, v in vol.items()})
out["volume_by_kind_usd"] = {k: round(v) for k, v in vol.items()}
allsend = defaultdict(float)
for k in by:
    for s, v in by[k].items():
        allsend[s] += v
top = sorted(allsend, key=lambda s: -allsend[s])[:15]
out["senders"] = []
print("\nPoolManager callers (Swap.sender), top 15 by volume")
for s in top:
    o = {"address": s, "name": name(s), "share_all": round(allsend[s] / tot, 4)}
    for k in vol:
        o[f"share_of_{k}"] = round(by[k].get(s, 0) / vol[k], 4) if vol[k] else None
    out["senders"].append(o)
    print(f"  {s} {o['name'][:55]:55s} all {o['share_all']:6.1%}  " +
          "  ".join(f"{k} {o[f'share_of_{k}']:6.1%}" for k in sorted(vol)))
out["distinct_senders"] = {k: len(by[k]) for k in by}

# tx.to sample, stratified by pool kind (up to 1500 txs each, volume-weighted pick)
random.seed(1121)
txs = defaultdict(dict)
for r in rows:
    txs[kind(r["pool"])][r["tx"]] = txs[kind(r["pool"])].get(r["tx"], 0) + r["usd"]
sample = {}
for k, d in txs.items():
    items = list(d.items())
    n = min(int(os.environ.get("NTX", 1500)), len(items))
    pick = random.choices([i[0] for i in items], weights=[i[1] for i in items], k=n)
    sample[k] = list(dict.fromkeys(pick))


def getto(h):
    try:
        t = call("eth_getTransactionByHash", [h])
        return h, (t or {}).get("to"), (t or {}).get("from")
    except Exception:
        return h, None, None


out["tx_to_sample"] = {}
print("\ntx.to, volume-weighted sample of transactions")
for k, hs in sample.items():
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(getto, hs))
    c = Counter((t or "").lower() for _, t, _ in res)
    nfrom = len({f for _, _, f in res})
    lst = [{"to": a, "name": name(a) if a else None, "share": round(n / len(res), 3)} for a, n in c.most_common(8)]
    out["tx_to_sample"][k] = {"n": len(res), "distinct_from": nfrom, "top": lst}
    print(f" {k}: n={len(res)} distinct tx.from={nfrom}")
    for x in lst:
        print(f"    {x['share']:6.1%} {x['to']} {str(x['name'])[:60]}")

# txs touching more than one pool (split routing)
pools_per_tx = defaultdict(set)
for r in rows:
    pools_per_tx[r["tx"]].add(r["pool"])
multi = sum(r["usd"] for r in rows if len(pools_per_tx[r["tx"]]) > 1)
out["volume_share_in_multi_pool_txs"] = round(multi / tot, 3)
print(f"\nvolume in txs touching >1 selected pool: {multi/tot:.1%}")

# best-quote check on stock/USDG pairs
raw = []
for f in glob.glob(f"{H}/data/pchunks/*.csv"):
    for r in csv.reader(open(f)):
        pid = r[2]
        p = pools.get(pid)
        if p and USDG in (p["currency0"], p["currency1"]):
            raw.append((int(r[0]), int(r[1]), pid, int(r[4]), int(r[5]), int(r[6]), int(r[7]), int(r[9])))
raw.sort()
active = Counter(x[2] for x in raw)
state = {}  # pid -> (price usd per stock after, lp fee, liquidity)
stats = defaultdict(lambda: defaultdict(float))
for (blk, li, pid, a0, a1, sq, liq, fee) in raw:
    p = pools[pid]
    stock0 = p["currency1"] == USDG
    sym = tokens[p["currency0" if stock0 else "currency1"]]["sym"]
    t0, t1 = tokens[p["currency0"]], tokens[p["currency1"]]
    p01 = (sq / 2 ** 96) ** 2 * 10 ** (t0["dec"] - t1["dec"])
    px = p01 if stock0 else (1 / p01 if p01 else 0)
    a_st = a0 if stock0 else a1
    usd = abs(a1 if stock0 else a0) / 1e6
    buy = a_st > 0
    cands = {q: s for q, s in state.items() if s[3] == sym and s[4] > 0 and active[q] >= 100}
    if len(cands) >= 2 and pid in cands:
        # cost of this swap's size in each pool: mid x (1 +- fee) x (1 +- usd / virtual USDG reserve)
        eff = {q: (s[0] * (1 + s[1] / 1e6) * (1 + usd / s[4]) if buy
                   else -s[0] * (1 - s[1] / 1e6) * max(0.0, 1 - usd / s[4])) for q, s in cands.items()}
        best = min(eff, key=eff.get)
        bk = kind(best)
        st = stats[bk]
        st["usd"] += usd
        st["to_best"] += usd if pid == best else 0
        # gap between where it went and the best, bp
        st["gap_bp_x_usd"] += (eff[pid] - eff[best]) / abs(eff[best]) * 1e4 * usd
        stats["all"]["usd"] += usd
        stats["all"]["to_best"] += usd if pid == best else 0
    if px:
        # virtual USDG reserve at the current price for the in-range liquidity (Swap.liquidity, after the swap)
        rs = sq / 2 ** 96
        vres = (liq * rs if p["currency1"] == USDG else liq / rs) / 1e6 if rs else 0
        state[pid] = (px, fee, liq, sym, vres)
out["best_quote"] = {}
print("\nbest-quote check (stock/USDG pairs with >= 2 live pools; price incl. last LP fee and the swap's own impact on in-range liquidity; no tick crossing, no splitting)")
for k, st in stats.items():
    if st["usd"]:
        o = {"usd": round(st["usd"]), "share_to_best": round(st["to_best"] / st["usd"], 3),
             "avg_gap_to_best_bp": round(st.get("gap_bp_x_usd", 0) / st["usd"], 1) if k != "all" else None}
        out["best_quote"][f"best_is_{k}" if k != "all" else "all"] = o
        print(f"  best pool is {k:10s}: ${st['usd']/1e6:7.1f}M of swaps, {o['share_to_best']:.0%} went to it"
              + (f", avg {o['avg_gap_to_best_bp']}bp worse when not" if o['avg_gap_to_best_bp'] is not None else ""))
json.dump(out, open(f"{H}/results/routing.json", "w"), indent=1)
