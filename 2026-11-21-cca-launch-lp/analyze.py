"""Per migrated pool: price path against the clearing price, volume, fees, and the CCA's own full-range position against
holding at 24 h and 72 h; who traded; what came in through routers; whether auction bidders were the day-1 sellers;
and two simple counterfactuals (a range around the clearing price, a fee that starts high and steps down).
usage: python3 -I analyze.py -> results/analyze.txt, results/pools.json"""
import json, sys, os, glob, math, bisect, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rpc
LAB = json.load(open("results/labels.json")) if os.path.exists("results/labels.json") else {}
BIDS = json.load(open("data/bids.json"))
CAT = {(c["chain"], c["auction"].lower()): c for c in json.load(open("data/catalog.json"))}
LP = {x["poolId"]: x for x in json.load(open("data/lp_all.json"))}
MIG = {}
for ch in ("ethereum", "base", "unichain", "arbitrum"):
    for a in json.load(open(f"data/migr_{ch}.json")):
        if a.get("migr"): MIG[a["migr"]["poolId"]] = a
out_lines = []
def P(*a):
    s = " ".join(str(x) for x in a); out_lines.append(s); print(s)
def dec(ch, addr):
    if addr == "0x0000000000000000000000000000000000000000": return 18
    return int(rpc.call(ch, "eth_call", [dict(to=addr, data="0x313ce567"), "latest"]), 16)
def label(ch, a):
    l = LAB.get(f"{ch}:{a}")
    return l["cat"] if l else "unlabeled"
FLAGS = ["afterRemoveReturnsDelta", "afterAddReturnsDelta", "afterSwapReturnsDelta", "beforeSwapReturnsDelta", "afterDonate", "beforeDonate",
         "afterSwap", "beforeSwap", "afterRemove", "beforeRemove", "afterAdd", "beforeAdd", "afterInitialize", "beforeInitialize"]
def hook_flags(h): v = int(h, 16) & 0x3fff; return [FLAGS[i] for i in range(14) if v >> i & 1][::-1]   # v4 Hooks.sol permission bits
RES = []
for fn in sorted(glob.glob("data/swaps72_*.json")):
    D = json.load(open(fn)); ch = D["chain"]; pid = D["poolId"]; a = MIG[pid]; m = a["migr"]; lp = LP[pid]
    cur = a["currency"].lower(); c0, c1 = m["currency0"].lower(), m["currency1"].lower()
    tokIs0 = (c1 == cur) if cur in (c0, c1) else (c0 == a["token"].lower())
    dt = dec(ch, c0 if tokIs0 else c1); dc = dec(ch, c1 if tokIs0 else c0)
    usd = D["usdper"]
    def px(sp):  # currency per token, human units
        p = (sp / 2**96) ** 2
        return p * 10**(dt - dc) if tokIs0 else (1 / p) * 10**(dt - dc)
    Pc = CAT[(ch, a["auction"].lower())]["clearing"]; P0 = px(m["sqrtPriceX96"])
    tl, tu, Lpos = m["positions"][0]
    rows = []
    for r in D["rows"]:
        ut, uc = (r["a0"], r["a1"]) if tokIs0 else (r["a1"], r["a0"])
        ut /= 10**dt; uc /= 10**dc
        if ut == 0 or uc == 0: continue
        f = r["fee"] / 1e6; p_after = px(r["sp"]); pxe = abs(uc / ut)
        feeC = abs(uc) * f if uc < 0 else abs(ut) * f * pxe   # fee on the input side, in currency
        rows.append(dict(r, ut=ut, uc=uc, f=f, after=p_after, pxe=pxe, feeC=feeC, dt_h=(r["t"] - D["tb0"]) / 3600))
    T = [r["t"] for r in rows]
    def price_at(t):
        i = bisect.bisect_right(T, t) - 1
        return rows[i]["after"] if i >= 0 else P0
    tb0 = D["tb0"]
    # full-range position value from L (raw sqrt units)
    def amounts_full(sp, L):
        s = sp / 2**96; a0 = L / s; a1 = L * s
        tok, curr = (a0 / 10**dt, a1 / 10**dc) if tokIs0 else (a1 / 10**dt, a0 / 10**dc)
        return tok, curr
    tok0, cur0 = amounts_full(m["sqrtPriceX96"], Lpos)
    TVL0 = cur0 + tok0 * P0
    # the CCA position: full range, the migrate's L. A full-range removal of at least half that L is taken as the CCA position leaving
    # (the PositionManager is shared, and the position's salt is not kept, so this is a size match, not an owner match).
    removed = [x for x in D["mods"] if x["dL"] < 0 and x["tl"] == tl and x["tu"] == tu and -x["dL"] >= 0.5 * Lpos]
    rem_h = [(x["t"] - tb0) / 3600 for x in removed]
    t_rem = rem_h[0] if rem_h else None
    lpSenders = collections.Counter(label(ch, x["sender"]) + " " + x["sender"][:10] for x in D["mods"] if x["dL"] > 0 and x["tx"] != m["tx"])
    res = dict(chain=ch, tok=D["tok"] if D["tok"] != "VAZT" else "AZTEC", pool=pid, hooks=m["hooks"], hooked=m["hooks"] != "0x" + "0" * 40, hookFlags=hook_flags(m["hooks"]),
               fee=m["fee"], Pc=Pc, P0=P0, TVL0usd=TVL0 * usd, raisedUSD=lp["raisedUSD"], usdper=usd,
               ccaRemoved_h=[round(h, 2) for h in rem_h], ccaRemovedFrac=[round(-x["dL"] / Lpos, 3) for x in removed], otherLPadds=sum(1 for x in D["mods"] if x["dL"] > 0 and x["tx"] != m["tx"]))
    # same-block add-and-remove of the same range (just-in-time liquidity) within 72 h
    adds = collections.defaultdict(int); jit = 0
    for x in D["mods"]:
        k_ = (x["n"], x["tl"], x["tu"], abs(x["dL"]))
        if x["dL"] > 0: adds[k_] += 1
        elif adds.get(k_): jit += 1; adds[k_] -= 1
    res["pAtRemoval"] = None
    res["jitPairs72"] = jit; res["lpSenders"] = lpSenders.most_common(6)
    # price path
    for h in (5 / 60, 1, 6, 24, 72): res[f"p_{h:g}h"] = price_at(tb0 + h * 3600) / Pc
    for H in (24, 72):
        w = [r for r in rows if r["dt_h"] < H]
        res[f"max{H}"] = max([r["after"] for r in w] + [P0]) / Pc; res[f"min{H}"] = min([r["after"] for r in w] + [P0]) / Pc
        res[f"n{H}"] = len(w); res[f"vol{H}"] = sum(abs(r["uc"]) for r in w) * usd; res[f"fees{H}"] = sum(r["feeC"] for r in w) * usd
        He = min(H, t_rem) if t_rem is not None else H    # the position is only followed until it is removed
        res[f"posHorizon{H}"] = He
        if He <= 0:
            for k_ in ("il", "posFees", "posNet"): res[f"{k_}{H}"] = None
            res[f"posNet{H}_pct"] = None; res[f"ccaFeeShare{H}"] = None; continue
        k = price_at(tb0 + He * 3600) / P0
        il = TVL0 * (math.sqrt(k) - (1 + k) / 2)       # full-range value minus holding the deposit, currency
        share = sum(r["feeC"] * min(1, Lpos / r["liq"]) for r in w if r["liq"] > 0 and r["dt_h"] < He)
        res[f"il{H}"] = il * usd; res[f"posFees{H}"] = share * usd; res[f"posNet{H}"] = (il + share) * usd
        res[f"posNet{H}_pct"] = (il + share) / TVL0 * 100
        res[f"ccaFeeShare{H}"] = share / max(1e-18, sum(r["feeC"] for r in w))
    # markouts at 5 min (LP side, after fees, the pool's own price) for day 1
    d1 = [r for r in rows if r["dt_h"] < 24]
    for r in d1: r["m5"] = -(r["ut"] * price_at(r["t"] + 300)) - r["uc"]
    res["m5_24h"] = sum(r["m5"] for r in d1) * usd
    if t_rem is not None: res["pAtRemoval"] = round(price_at(tb0 + t_rem * 3600) / Pc, 3)
    res["m1h_24h"] = sum(-(r["ut"] * price_at(r["t"] + 3600)) - r["uc"] for r in d1) * usd
    res["m24h_24h"] = sum(-(r["ut"] * price_at(r["t"] + 86400)) - r["uc"] for r in d1) * usd
    res["firstSwap_h"] = rows[0]["dt_h"] if rows else None
    vol = sum(abs(r["uc"]) for r in d1)
    # who traded
    byf = collections.Counter(); bys = collections.Counter(); byto = collections.Counter()
    for r in d1: byf[r["from"]] += abs(r["uc"]); bys[r["sender"]] += abs(r["uc"]); byto[r["to"]] += abs(r["uc"])
    res["traders"] = len(byf); res["top5from"] = sum(v for _, v in byf.most_common(5)) / vol
    res["topSenders"] = [(k, round(v / vol, 3), label(ch, k)) for k, v in bys.most_common(6)]
    res["topTo"] = [(k, round(v / vol, 3), label(ch, k)) for k, v in byto.most_common(6)]
    cat = collections.Counter()
    for r in d1:
        c1_ = label(ch, r["to"]); c2_ = label(ch, r["sender"])
        c = c1_ if c1_ != "unlabeled" else c2_
        if c == "unlabeled" and r["to"] == r["sender"]: c = "own contract (to == swap sender)"
        cat[c] += abs(r["uc"])
    res["routing"] = {k: round(v / vol, 3) for k, v in cat.most_common()}
    AGG = {"CoW Protocol", "1inch", "0x", "KyberSwap", "OKX", "Velora (ParaSwap)", "MetaMask", "LI.FI", "Relay", "Sushi (RedSnwapper)",
           "Tycho router (solvers)", "aggregator adapter (unattributed)", "deBridge", "Odos", "UniswapX", "Bebop", "Enso", "Bungee", "Rainbow"}
    grp = collections.Counter()
    for k, v in cat.items():
        g = ("Uniswap Universal Router" if k == "Uniswap Universal Router" else "aggregators, solvers, bridges" if k in AGG
             else "own contract (to == swap sender)" if k.startswith("own contract") else "ERC-4337 smart wallet" if k.startswith("ERC-4337") else "unattributed")
        grp[g] += v
    res["routingGroups"] = {k: round(v / vol, 3) for k, v in grp.most_common()}
    # arbitrage-looking: profitable to the trader after fees at 5 min
    res["arbShareVol"] = sum(abs(r["uc"]) for r in d1 if r["m5"] < 0) / vol
    # bidders
    bk = f"{ch}:{a['auction']}"
    if bk in BIDS:
        B = BIDS[bk]["bids"]; owners = set(b["owner"].lower() for b in B)
        amt = sum(b["amount"] for b in B)
        res["bids"] = len(B); res["bidders"] = len(owners)
        won = [b for b in B if b["maxPrice"] >= Pc * (1 - 1e-9)]
        res["winners"] = len(set(b["owner"] for b in won))
        for mult in (1, 1.5, 2, 3, 5):
            res[f"demand_ge_{mult:g}x"] = sum(b["amount"] for b in B if b["maxPrice"] >= Pc * mult) / amt
        mp = sorted(b["maxPrice"] / Pc for b in won); wamt = sorted(((b["maxPrice"] / Pc, b["amount"]) for b in won))
        tot = sum(x[1] for x in wamt); acc = 0; med = None
        for p_, a_ in wamt:
            acc += a_
            if acc >= tot / 2: med = p_; break
        res["winnerMaxPrice_median_byAmount"] = med
        sells = [r for r in d1 if r["ut"] < 0]; buys = [r for r in d1 if r["ut"] > 0]
        sv = sum(abs(r["uc"]) for r in sells); bv = sum(abs(r["uc"]) for r in buys)
        res["sellVolFromBidders"] = sum(abs(r["uc"]) for r in sells if r["from"] in owners) / sv if sv else None
        res["buyVolFromBidders"] = sum(abs(r["uc"]) for r in buys if r["from"] in owners) / bv if bv else None
        res["sellShare"] = sv / (sv + bv)
        # where the 24h low fell inside the winners' max-price distribution
        # bid currency that was refunded (max below clearing) but whose max was at or above the 24 h pool price
        p24 = res["p_24h"]
        res["refundedAbove24hUSD"] = sum(b["amount"] for b in B if p24 * Pc <= b["maxPrice"] < Pc * (1 - 1e-9)) * usd
        res["day1BuyUSD"] = bv * usd
    # baseline for the counterfactuals: the CCA's full-range position kept for the whole window
    for H in (24, 72):
        w = [r for r in rows if r["dt_h"] < H]; k = price_at(tb0 + H * 3600) / P0
        res[f"keptFull{H}"] = (TVL0 * (math.sqrt(k) - (1 + k) / 2) + sum(r["feeC"] * min(1, Lpos / r["liq"]) for r in w if r["liq"] > 0)) * usd
    # counterfactual A: same capital in [Pc/k, Pc*k], same price path, same swaps; fee share = Lc / (L_active - Lfull + Lc) in range
    for kk in (2, 4):
        pa, pb = Pc / kk, Pc * kk
        sa, sb = math.sqrt(pa), math.sqrt(pb)
        def amts(p, L):
            s_ = math.sqrt(min(max(p, pa), pb))
            return L * (1 / s_ - 1 / sb), L * (s_ - sa)   # token, currency (human sqrt units)
        x1, y1 = amts(P0, 1.0); Lc = TVL0 / (x1 * P0 + y1); x0, y0 = amts(P0, Lc)
        # full-range L in the same human sqrt units
        Lf_h = math.sqrt(tok0 * cur0)
        for H in (24, 72):
            ph = price_at(tb0 + H * 3600); xh, yh = amts(ph, Lc)
            ilc = (xh * ph + yh) - (x0 * ph + y0)
            fe = 0
            for r in rows:
                if r["dt_h"] >= H or r["liq"] <= 0: continue
                if not (pa <= r["after"] <= pb): continue
                frac_full = min(1, Lpos / r["liq"]); other = 1 - frac_full
                # in relative terms: active = Lf_h/frac_full; replace Lf_h by Lc
                act_other = Lf_h * other / frac_full if frac_full > 0 else 0
                fe += r["feeC"] * Lc / (act_other + Lc)
            res[f"cfA_k{kk}_net{H}"] = (ilc + fe) * usd; res[f"cfA_k{kk}_il{H}"] = ilc * usd; res[f"cfA_k{kk}_fees{H}"] = fe * usd
    # counterfactual B: fee 3% for the first hour, 1% hours 1-6, the pool's fee after (never below the pool fee).
    # A trade that was profitable to its sender at 5 min (after the old fee) is kept only if it stays profitable after the
    # extra fee; other trades are kept with probability r (1.0 and 0.5). LP P&L per kept trade = old 5-min markout + extra fee.
    def newfee(h, f): return max(f, 0.03 if h < 1 else 0.01 if h < 6 else f)
    for keep in (1.0, 0.5):
        pnl = 0; kept = 0
        for r in d1:
            extra = (newfee(r["dt_h"], r["f"]) - r["f"]) * abs(r["uc"]) if r["uc"] < 0 else (newfee(r["dt_h"], r["f"]) - r["f"]) * abs(r["ut"]) * r["pxe"]
            gain = -r["m5"]
            if extra == 0: pnl += r["m5"]; kept += abs(r["uc"]); continue
            if gain > 0:
                if gain - extra > 0: pnl += r["m5"] + extra; kept += abs(r["uc"])
            else:
                pnl += keep * (r["m5"] + extra); kept += keep * abs(r["uc"])
        res[f"cfB_keep{keep:g}_m5"] = pnl * usd; res[f"cfB_keep{keep:g}_volKept"] = kept / vol
    # pnl is linear in the kept share r of the other trades: pnl(r) = A + r B. Break-even r: same as actual.
    A_ = res["cfB_keep1_m5"] - 2 * (res["cfB_keep1_m5"] - res["cfB_keep0.5_m5"]); B_ = 2 * (res["cfB_keep1_m5"] - res["cfB_keep0.5_m5"])
    res["cfB_breakeven_keep"] = (res["m5_24h"] - A_) / B_ if B_ else None
    RES.append(res)
RES.sort(key=lambda r: -r["raisedUSD"])
json.dump(RES, open("results/pools.json", "w"), indent=1)
f = lambda v: "n/a" if v is None else f"{v:,.0f}"
f2 = lambda v: "n/a" if v is None else f"{v:.2f}"
def pn(r, H):
    if r[f"posNet{H}"] is None: return "n/a (removed before trading)"
    t = "" if r[f"posHorizon{H}"] == H else f" [to removal at {r[f'posHorizon{H}']:.1f} h]"
    return f'{f(r[f"posNet{H}"])} ({r[f"posNet{H}_pct"]:.1f}%){t}'
P("pool | chain | raised$ | TVL0$ | bids | bidders | p5m/Pc p1h p24h p72h | max/min 72h | vol24$ | fees24$ | posNet24$ (%) | posNet72$ (%)")
for r in RES:
    P(f'{r["tok"]} | {r["chain"]} | {f(r["raisedUSD"])} | {f(r["TVL0usd"])} | {r.get("bids")} | {r.get("bidders")} | '
      f'{r["p_0.0833333h"]:.2f} {r["p_1h"]:.2f} {r["p_24h"]:.2f} {r["p_72h"]:.2f} | {r["max72"]:.2f}/{r["min72"]:.2f} | {f(r["vol24"])} | {f(r["fees24"])} | '
      f'{pn(r, 24)} | {pn(r, 72)}')
P()
P("day-1 markouts (LP, after fees) at 5 min / 1 h / 24 h; first swap (h after window start); price when the CCA position left")
for r in RES:
    P(f'{r["tok"]}: {f(r["m5_24h"])} / {f(r["m1h_24h"])} / {f(r["m24h_24h"])} | first swap {r["firstSwap_h"]:.2f} h | {r.get("pAtRemoval")}')
P()
P("pool | vol72$ | fees72$ | il24$ il72$ | posFees24$ posFees72$ | m5 day1$ | arb-looking vol share | traders | top5 | removals(h) | other LP adds")
for r in RES:
    P(f'{r["tok"]} | {f(r["vol72"])} | {f(r["fees72"])} | {f(r["il24"])} {f(r["il72"])} | {f(r["posFees24"])} {f(r["posFees72"])} | {f(r["m5_24h"])} | '
      f'{r["arbShareVol"]:.2f} | {r["traders"]} | {r["top5from"]:.2f} | {r["ccaRemoved_h"]} {r["ccaRemovedFrac"]} | {r["otherLPadds"]} | jit {r["jitPairs72"]} | CCA fee share 24h {f2(r["ccaFeeShare24"])}')
P(); P("liquidity added by others within 72 h (label, count):")
for r in RES: P(f'{r["tok"]}: {r["lpSenders"]}')
P()
P("routing of day-1 volume (by tx entry contract, else swap sender):")
for r in RES: P(f'{r["tok"]} hook flags={r["hookFlags"]}: {r["routingGroups"]}')
P("detail:")
for r in RES: P(f'{r["tok"]}: {r["routing"]}')
P()
P("information: demand share with max price >= m x clearing | winners | median winner max price (by amount) | day-1 sell share | sells from bidders | buys from bidders | refunded bids with max >= 24h price $ | day-1 buy volume $")
for r in RES:
    if "bids" not in r: continue
    P(f'{r["tok"]}: ' + " ".join(f'{m}x={r[f"demand_ge_{m}x"]:.2f}' for m in ("1", "1.5", "2", "3", "5")) +
      f' | {r["winners"]} | {r["winnerMaxPrice_median_byAmount"]} | {r["sellShare"]:.2f} | {r["sellVolFromBidders"]:.2f} | {r["buyVolFromBidders"]:.2f} | {r["refundedAbove24hUSD"]:,.0f} | {r["day1BuyUSD"]:,.0f}')
P()
P("counterfactual A (range around clearing, same capital, same path): net vs hold 24h / 72h, actual full range first")
for r in RES:
    P(f'{r["tok"]}: full range kept {f(r["keptFull24"])} / {f(r["keptFull72"])} | x/2..2x {f(r["cfA_k2_net24"])} / {f(r["cfA_k2_net72"])} | x/4..4x {f(r["cfA_k4_net24"])} / {f(r["cfA_k4_net72"])}')
P()
P("counterfactual B (3% first hour, 1% to 6 h): day-1 5-min markout, actual vs keep-others 100% / 50%, and volume kept")
for r in RES:
    P(f'{r["tok"]}: actual {f(r["m5_24h"])} | {f(r["cfB_keep1_m5"])} (vol {r["cfB_keep1_volKept"]:.2f}) | {f(r["cfB_keep0.5_m5"])} (vol {r["cfB_keep0.5_volKept"]:.2f}) | break-even share of other trades kept {f2(r["cfB_breakeven_keep"])}')
open("results/analyze.txt", "w").write("\n".join(out_lines) + "\n")
