"""Q2: what pricing from the HyperCore book would have done, on the same flow.
usage: counterfactual.py PAIR  (reads data/rows_PAIR_E.json, data/rows_PAIR_HL.json from analyze.py) -> results/counterfactual_PAIR.txt

A. In place (static): the existing HYPE/USDC pools charge a directional fee on trades that move the pool toward the
   reference (max(30 bp, distance), capped at 300 bp; the rule of the earlier replay), away trades keep their fee.
   A share r of the toward volume stays and pays the higher fee; 1 - r goes elsewhere (and its LP P&L with it).
   r is the stated price sensitivity: 1 (nobody leaves) to 0 (every toward trade leaves).
B. Quoting around the HyperCore mid: one new pool quotes bid/ask = M x (1 -/+ h) with linear depth L USD per bp
   beyond that, M reset before every trade (no latency: an upper bound). Each recorded trade fills with it while
   its marginal price beats the price the trader actually got, capped at the trade's size (the routing rule of the
   earlier replay). M is the HyperCore mid (HL) or the local basis-adjusted E. Marked at HL and at E five minutes later.
   Net HYPE bought shows the inventory that has to leave Elysium (canonical withdrawal about 5.5 days)."""
import json, sys, collections
PAIR = sys.argv[1]
out = []; pr = lambda s="": out.append(s)
for ref in ("E", "HL"):
    rows = [r for r in json.load(open(f"data/rows_{PAIR}_{ref}.json")) if abs(r["px"] / r["e0"] - 1) < 0.05]
    days = (rows[-1]["t"] - rows[0]["t"]) / 86400
    tw = [r for r in rows if r["toward"]]; aw = [r for r in rows if not r["toward"]]
    P = lambda R: sum(r["lp5"] for r in R) / days
    V = lambda R: sum(r["usd"] for r in R) / days
    extra = sum(r["usd"] * max(0, min(300, max(30, abs(r["dev"]))) - r["fee"]) / 1e4 for r in tw) / days  # fee in rows is in bp
    pr(f"\n## A. Directional fee in place, reference {ref} ({days:.2f} days, ${V(rows):,.0f}/day)")
    pr(f"actual LP P&L at 5 min, fee incl.: ${P(rows):+,.0f}/day (toward ${P(tw):+,.0f} on ${V(tw):,.0f}; away ${P(aw):+,.0f} on ${V(aw):,.0f})")
    pr(f"extra fee the toward trades would pay if all stayed: ${extra:,.0f}/day (median distance {sorted(abs(r['dev']) for r in tw)[len(tw) // 2]:.0f} bp)")
    pr("| r (toward volume that stays) | LP P&L $/day | change vs actual | volume lost $/day | share of all volume lost |\n|---|---|---|---|---|")
    for rr in (1, 0.75, 0.5, 0.25, 0):
        p = P(aw) + rr * (P(tw) + extra)
        pr(f"| {rr} | ${p:+,.0f} | ${p - P(rows):+,.0f} | ${(1 - rr) * V(tw):,.0f} | {(1 - rr) * V(tw) / V(rows):.0%} |")
rows = [r for r in json.load(open(f"data/rows_{PAIR}_E.json")) if r["hl0"] and r["hl5"] and r["E0"] and r["E5"] and abs(r["px"] / r["e0"] - 1) < 0.05]
days = (rows[-1]["t"] - rows[0]["t"]) / 86400
pr(f"\n## B. Quote around a mid ± h ({len(rows)} trades, {days:.2f} days); $/day")
pr("| quote mid | h bp | depth $/bp | volume filled | of all | buys/sells filled | LP P&L marked HL 5 min | marked E 5 min | net base bought/day |\n|---|---|---|---|---|---|---|---|---|")
for mid in ("hl0", "E0"):
    for h in (5, 10, 20, 30):
        for L in (200, 800):
            v = vb = vs = pH = pE = net = 0
            for r in rows:
                M = r[mid]; buy = r["s"] > 0
                start = M * (1 + h / 1e4) if buy else M * (1 - h / 1e4)
                mv = (r["px"] / start - 1) if buy else (1 - r["px"] / start)
                if mv <= 0: continue
                x = min(mv * 1e4 * L, r["usd"]); d = x / (L * 1e4)
                p1 = start * (1 + d) if buy else start * (1 - d); q = x / ((start + p1) / 2)
                for mk, acc in (("hl5", "H"), ("E5", "E")):
                    pnl = (x - q * r[mk]) if buy else (q * r[mk] - x)
                    if acc == "H": pH += pnl
                    else: pE += pnl
                v += x; net += -q if buy else q
                if buy: vb += x
                else: vs += x
            tot = sum(r["usd"] for r in rows)
            pr(f"| {'HL' if mid == 'hl0' else 'E'} | {h} | {L} | ${v / days:,.0f} | {v / tot:.0%} | ${vb / days:,.0f} / ${vs / days:,.0f} | ${pH / days:+,.0f} | ${pE / days:+,.0f} | {net / days:+,.0f} |")
open(f"results/counterfactual_{PAIR}.txt", "w").write("\n".join(out) + "\n"); print("\n".join(out))
