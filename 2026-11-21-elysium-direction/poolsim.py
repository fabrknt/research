# Copied unmodified (apart from these two lines) from the earlier Elysium replay by the same author (11-13, 11-09..11 flow).
# Run here on fresh rows: python3 -I poolsim.py data/rows_PAIR_REF.json. Its "mark" column says E; for the _HL rows the mark is the HyperCore mid.
"""One new HYPE/USDC pool on Elysium with its own price, replayed against the recorded flow (11-09..11).
usage: poolsim.py ROWS.json   (rows from flowfee.py)

Depth: linear, L USD per bp of price move. Routing (a small-share approximation): each recorded trade
fills with this pool until the pool's marginal all-in price (price after the fill, with fee) reaches
the average price that trader actually got elsewhere, as an aggregator equalising marginal prices
would (this fills less than comparing average prices), with the trader's gross cash as the cap (buy: x(1+f) <= usd; sell: x(1-f) <= usd); the other pools'
prices are taken as recorded, so capturing part of a trade does not improve them.

The fee is set from the pool price before each swap, as the hook does. "one swap" sends each fill as one
swap; "split" sends it in 20 pieces, each paying the fee at the price it starts from, as a taker splitting
a toward-E trade would as the price nears E. More pieces lower the directional result a little further,
so 20 is an example, not a bound.

Arbitrage (a sensitivity, not an executable venue): before each trade, if this pool's all-in price is
past the median of the last 60 s of executions by more than c, an arb trades it back to that point.
Trades executed more than 5% from E are dropped (dead or mispriced pools). LP P&L of each fill is
marked five minutes later, to E (Elysium's basis over the following tape) and to
E with the basis frozen at the trade (the HyperCore mid at t+300 within 5 s: HyperCore's move only)."""
import json, sys, bisect, statistics as st
rows = [r for r in json.load(open(sys.argv[1])) if abs(r["px"] / r["e0"] - 1) < 0.05]
rows.sort(key=lambda r: r["t"])
days = (rows[-1]["t"] - rows[0]["t"]) / 86400
T = [r["t"] for r in rows]; PX = [r["px"] for r in rows]


def market(i):
    lo = bisect.bisect_left(T, T[i] - 60)
    w = PX[lo:i]
    return st.median(w) if len(w) >= 3 else None


M = [market(i) for i in range(len(rows))]


def sim(L, fee, c, pieces, mark):
    """fee(P, E, buy) -> fee fraction. Returns $/day: LP P&L from flow and arbs, volumes, fees."""
    P = rows[0]["px"]; out = dict(flow=0.0, arb=0.0, vflow=0.0, varb=0.0, fees=0.0)

    def fill(buy, target, cap, E, e5, kind):
        """Fill toward `target` (all-in price), spending at most `cap` of the taker's gross cash."""
        nonlocal P
        # each piece re-reads the fee at its starting price and takes its share of what is left to
        # the stop that fee gives; the last piece goes all the way
        for k in range(pieces):
            f = fee(P, E, buy)
            stop = target / (1 + f) if buy else target / (1 - f)
            mv = (stop / P - 1) if buy else (1 - stop / P)
            if mv <= 0: break
            x = mv * 1e4 * L / (pieces - k)
            gross = x * (1 + f) if buy else x * (1 - f)
            if cap is not None:
                if cap <= 0: break
                if gross > cap: x = cap / (1 + f) if buy else cap / (1 - f); gross = cap
                cap -= gross
            d = x / (L * 1e4)
            P1 = P * (1 + d) if buy else P * (1 - d)
            q = x / ((P + P1) / 2)  # HYPE moved
            pnl = (x * (1 + f) - q * e5) if buy else (q * e5 - x * (1 - f))
            out[kind] += pnl; out["v" + kind] += x; out["fees"] += x * f
            P = P1

    for i, r in enumerate(rows):
        e5 = r[mark]
        if M[i] and c is not None:
            fill(True, M[i] * (1 - c), None, r["e0"], e5, "arb")
            fill(False, M[i] * (1 + c), None, r["e0"], e5, "arb")
        fill(r["s"] > 0, r["px"], r["usd"], r["e0"], e5, "flow")
    return {k: v / days for k, v in out.items()}


def fixed(f): return lambda P, E, buy: f


def directional(away, floor, slope, cap):
    def fee(P, E, buy):
        if not ((P < E) if buy else (P > E)): return away
        return min(cap, max(floor, slope * abs(P / E - 1)))
    return fee


FIX = fixed(30e-4); DIR = directional(30e-4, 30e-4, 1, 300e-4)
print(f"{len(rows)} trades, {days:.2f} days, ${sum(r['usd'] for r in rows) / days:,.0f}/day of flow\n")
print("| mark | depth $/bp | arbs | sent as | fixed 30 bp: LP $/day (flow / arbs) | directional: LP $/day (flow / arbs) | directional minus fixed | flow volume fixed / directional |")
print("| --- | --- | --- | --- | --- | --- | --- | --- |")
for mark in ("e5", "e5f"):
    for L in (200, 800):
        for c in (None, 30e-4, 10e-4):
            for pieces in (1, 20):
                a = sim(L, FIX, c, pieces, mark); b = sim(L, DIR, c, pieces, mark)
                ta, tb = a["flow"] + a["arb"], b["flow"] + b["arb"]
                print(f"| {'E' if mark == 'e5' else 'E, basis frozen'} | {L} | {'none' if c is None else f'{c * 1e4:.0f} bp'} | {'one swap' if pieces == 1 else 'split'} "
                      f"| ${ta:,.0f} ({a['flow']:,.0f} / {a['arb']:,.0f}) | ${tb:,.0f} ({b['flow']:,.0f} / {b['arb']:,.0f}) | ${tb - ta:+,.0f} "
                      f"| ${a['vflow'] / 1e6:.2f}M / ${b['vflow'] / 1e6:.2f}M |", flush=True)
