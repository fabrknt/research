"""Q3 routing: who sends HYPE/USDC flow to each venue. Adapted from the earlier Elysium sources.py.
usage: sources.py [N=300]  (reads data/trades.jsonl, data/pools.json) -> results/sources.txt
Per venue (top 10 by USD, plus every hooked v4 HYPE/USDC pool with volume), samples up to N trades weighted by USD
(fixed seed), reads each transaction's `to`, and names it from the explorer's verified-source ContractName where there is one."""
import sys, os, json, random, collections, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import R, WHYPE, USDC, NATIVE
N = int(sys.argv[1]) if len(sys.argv) > 1 else 300
db = json.load(open("data/pools.json"))["pools"]; H = {WHYPE, NATIVE}
hu = {k for k, p in db.items() if "t0" in p and ((p["t0"] in H and p["t1"] == USDC) or (p["t0"] == USDC and p["t1"] in H))}
def batch(calls):
    res = [None] * len(calls); todo = list(range(len(calls)))
    for rnd in range(10):
        nxt = []
        for i in range(0, len(todo), 20):
            ch = todo[i:i + 20]
            body = [{"jsonrpc": "2.0", "id": k, "method": calls[k][0], "params": calls[k][1]} for k in ch]
            try:
                r = urllib.request.Request(R, json.dumps(body).encode(), {"content-type": "application/json", "user-agent": "curl/8"})
                for x in json.load(urllib.request.urlopen(r, timeout=60)):
                    (res.__setitem__(x["id"], x["result"]) if x.get("result") is not None else nxt.append(x["id"]))
            except Exception: nxt += ch
            time.sleep(0.2)
        todo = nxt
        if not todo: break
        time.sleep(3)
    return res
EXP = "https://elysium.kinetiq.xyz/explorer/api?module=contract&action=getsourcecode&address="
NAMES = {"0x4337084d9e255ff0702461cf8895ce9e3b5ff108": "ERC-4337 EntryPoint v0.8 (smart accounts via a bundler)",
         "0x5567954cd026cebfe486062cb75848e0f1c12e58": "Relay (relay.link) router, identified from its bytecode (RelayerWitness, RelayApprovalProxy)",
         "0x0000000000001ff3684f28c67538d4d072c22734": "0x AllowanceHolder (Matcha/0x API)",
         "0x6131b5fae19ea4f9d964eac0408e4408b66337b5": "KyberSwap MetaAggregationRouterV2"}
cache_f = "data/names.json"; cache = json.load(open(cache_f)) if os.path.exists(cache_f) else {}
def name(a):
    if a in NAMES: return NAMES[a]
    if a not in cache:
        try:
            j = json.load(urllib.request.urlopen(urllib.request.Request(EXP + a, headers={"user-agent": "curl/8"}), timeout=30))
            cache[a] = j["result"][0].get("ContractName") or "unverified"
        except Exception: cache[a] = "?"
        json.dump(cache, open(cache_f, "w"))
    return cache[a]
byv = collections.defaultdict(list)
for line in open("data/trades.jsonl"):
    r = json.loads(line)
    if r["key"] in hu and r["usd"] >= 1: byv[r["key"]].append((r["usd"], r["h"]))
tot = collections.Counter({k: sum(x[0] for x in L) for k, L in byv.items()})
pick = [k for k, _ in tot.most_common(10)] + [k for k in tot if db[k].get("hooks", "0x" + "0" * 40) != "0x" + "0" * 40 and db[k]["kind"] == "v4" and k not in [x for x, _ in tot.most_common(10)] and tot[k] > 1000]
TXF = "data/txs.json"; TXC = json.load(open(TXF)) if os.path.exists(TXF) else {}
prof = collections.defaultdict(lambda: {"usd": 0.0, "from": set(), "tx": set()})
random.seed(7); out = []; agg = collections.Counter(); aggtot = 0
for k in pick:
    L = byv[k]; s = random.choices(L, weights=[x[0] for x in L], k=min(N, len(L)))
    hs = sorted({x[1] for x in s}); need = [h for h in hs if h not in TXC]
    TXC.update({h: ({"to": t["to"], "from": t["from"]} if t else None) for h, t in zip(need, batch([("eth_getTransactionByHash", [h]) for h in need]))})
    txs = {h: TXC[h] for h in hs}
    for amt, h in s:
        if txs.get(h): prof[txs[h]["to"]]["usd"] += amt; prof[txs[h]["to"]]["from"].add(txs[h]["from"]); prof[txs[h]["to"]]["tx"].add(h)
    to = collections.Counter(); frm = set()
    for amt, h in s:
        t = txs.get(h)
        if t: to[t["to"]] += amt; frm.add(t["from"])
    S = sum(to.values()) or 1; p = db[k]
    out.append(f"\n## {p['kind']} {k[:10]}{('…' + k[42:52]) if len(k) > 42 else ''} fee {p.get('fee')} hooks {p.get('hooks', '-')}  total ${tot[k]:,.0f}  sample {len(s)}, {len(hs)} txs, {len(frm)} senders")
    for a, x in to.most_common(8): out.append(f"  {x / S * 100:5.1f}%  {a}  {name(a)}")
    for a, x in to.items(): agg[a] += x / S * tot[k]
    aggtot += tot[k]
json.dump(TXC, open(TXF, "w"))
# direction of each entry's flow against the HyperCore mid (rows from analyze.py HYPE, reference HL)
tow = collections.defaultdict(lambda: [0.0, 0.0, 0.0])  # toward USD, all USD, LP P&L 5 min
txto = {h: t["to"] for h, t in TXC.items() if t}
for r in json.load(open("data/rows_HYPE_HL.json")):
    a = txto.get(r["h"])
    if a: tow[a][0] += r["usd"] * r["toward"]; tow[a][1] += r["usd"]; tow[a][2] += r["lp5"]
out.append("\n## Entry profile (sampled txs): distinct senders, and over every HYPE/USDC trade in those txs: toward share vs HL and LP P&L at 5 min vs HL")
out.append("| tx.to | name | senders in sample | txs in sample | toward share (USD) | LP P&L bp, 5 min |\n|---|---|---|---|---|---|")
for a, x in sorted(prof.items(), key=lambda kv: -kv[1]["usd"])[:20]:
    t = tow.get(a, [0, 0, 0])
    out.append(f"| {a} | {name(a)} | {len(x['from'])} | {len(x['tx'])} | {t[0] / t[1]:.0%} | {t[2] / t[1] * 1e4:+.1f} |" if t[1] else f"| {a} | {name(a)} | {len(x['from'])} | {len(x['tx'])} | - | - |")
out.insert(0, "Where HYPE/USDC flow enters, by tx.to (USD-weighted sample per venue)")
out.append("\n## All sampled venues, weighted by venue volume")
for a, x in agg.most_common(15): out.append(f"  {x / aggtot * 100:5.1f}%  {a}  {name(a)}")
open("results/sources.txt", "w").write("\n".join(out) + "\n"); print("\n".join(out))
# classes of entry, weighted by venue volume: named aggregators/intent routers; Uniswap UniversalRouter and 4337
# smart accounts (apps and wallets); unverified contracts with <= 5 senders in the sample (bot-like); the rest
AGG = {"0x6131b5fae19ea4f9d964eac0408e4408b66337b5", "0x5567954cd026cebfe486062cb75848e0f1c12e58", "0x0000000000001ff3684f28c67538d4d072c22734",
       "0x24e6da91aa4a8fee2447f542c92e006243bd6dc5", "0xcfbaa9cfce952ca4f4069874ff1df8c05e37a3c7", "0x0729e2a4716d9f7dd17858d5d504426d228697f7"}
def cls(a):
    if a in AGG: return "aggregator / intent router (Kyber, Relay, 0x, LI.FI, Enso, solver 0x0729)"
    if name(a) == "UniversalRouter" or a == "0x4337084d9e255ff0702461cf8895ce9e3b5ff108": return "Uniswap UniversalRouter or 4337 smart account"
    if name(a) == "unverified" and len(prof[a]["from"]) <= 5: return "unverified contract, <= 5 senders (bot-like)"
    return "other"
C = collections.Counter(); TW = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
for a, x in agg.items(): C[cls(a)] += x
for a, t in tow.items():
    if a in prof: c = TW[cls(a)]; c[0] += t[0]; c[1] += t[1]; c[2] += t[2]
extra = ["\n## Entry classes", "| class | share of HYPE/USDC volume | toward share vs HL | LP P&L bp, 5 min vs HL |", "|---|---|---|---|"]
for c, x in C.most_common():
    t = TW[c]; extra.append(f"| {c} | {x / aggtot:.0%} | {t[0] / t[1]:.0%} | {t[2] / t[1] * 1e4:+.1f} |" if t[1] else f"| {c} | {x / aggtot:.0%} | - | - |")
open("results/sources.txt", "a").write("\n".join(extra) + "\n"); print("\n".join(extra))
