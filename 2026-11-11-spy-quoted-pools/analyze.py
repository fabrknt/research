"""Per-pool fees vs LVR from on-chain Swap events (Robinhood Chain 4663).

For every swap we know (from the event): amounts, post-swap sqrtPriceX96, in-range liquidity L, fee.
Hourly buckets:
  fees_h  = sum over swaps of input_amount * fee  (converted to USD)
  LVR_h   = r_h^2 * L * sqrtP / 4                 (Milionis et al. LVR for CL liquidity in range,
            r_h = hourly log change of pool price, L/sqrtP = values at end of previous hour)
Full-range-equivalent yields (per unit capital of a full-range LP):
  fee_yield = fees / (2 L sqrtP)    lvr_yield = LVR / (2 L sqrtP)   (= sigma^2/8)
usage: python3 -I analyze.py DATA_DIR START_TS END_TS
"""
import json, math, sys, bisect, datetime

D = sys.argv[1]
START = int(sys.argv[2]); END = int(sys.argv[3])
BK = int(sys.argv[4]) * 3600 if len(sys.argv) > 4 else 3600   # bucket length (sampling interval for r)
Q96 = 2 ** 96
SPY = "0x117cc2133c37b721f49de2a7a74833232b3b4c0c"; USDG = "0x5fc5360d0400a0fd4f2af552add042d716f1d168"
DEC = {SPY: 18, USDG: 6}

bt = {int(k): v for k, v in json.load(open(f"{D}/blocktimes.json")).items()}
bks = sorted(bt)
def ts_of(b):
    i = bisect.bisect_right(bks, b) - 1; i = max(0, min(i, len(bks) - 2))
    b0, b1 = bks[i], bks[i + 1]
    return bt[b0] + (bt[b1] - bt[b0]) * (b - b0) / (b1 - b0)

def s(x):  # signed 256
    v = int(x, 16); return v - 2 ** 256 if v >= 2 ** 255 else v

def load(kind, key, fee_static=None):
    for line in open(f"{D}/swaps/{kind}_{key}.jsonl"):
        b, li, tx, t, d = json.loads(line); d = d[2:]; w = [d[i:i + 64] for i in range(0, len(d), 64)]
        a0, a1, sp, L = s(w[0]), s(w[1]), int(w[2], 16), int(w[3], 16)
        if kind == "v4":
            fee = fee_static if fee_static else int(w[5], 16); a0, a1 = -a0, -a1  # LP fee = static pool fee (event fee includes protocol fee)   # v4 emits caller delta; flip to pool-side (+ = into pool)
        else:
            fee = fee_static
        yield (b, li, a0, a1, sp, L, fee)

def hourly(rows, lp_frac=1.0):
    """returns dict hour -> (fee0_raw, fee1_raw, last sqrtP, last L, vol0_raw_abs, n)"""
    H = {}
    for b, li, a0, a1, sp, L, fee in rows:
        h = int(ts_of(b) // BK)
        f0 = a0 * fee / 1e6 * lp_frac if a0 > 0 else 0.0
        f1 = a1 * fee / 1e6 * lp_frac if a1 > 0 else 0.0
        e = H.get(h)
        if e is None: H[h] = [f0, f1, sp, L, abs(a0), 1, (b, li)]
        else:
            e[0] += f0; e[1] += f1; e[4] += abs(a0); e[5] += 1
            if (b, li) > e[6]: e[2] = sp; e[3] = L; e[6] = (b, li)
    return H

# SPY/USD hourly from the two SPY/USDG v4 pools (token0=SPY 18d, token1=USDG 6d)
spy_px = {}
for key in ["fe2a80bb5618fd14984b92ca6d45bf5ba67443ddb1435e28b2e48df2fc1526cd", "e5923c8a8be481ec89a2ca784a2bbfa4235de6d88f92260fd66b660c4babf907"]:
    try: HH = hourly(load("v4", key))
    except FileNotFoundError: continue
    for h, e in HH.items():
        p = (e[2] / Q96) ** 2 * 1e12
        if h not in spy_px or e[5] > spy_px[h][1]: spy_px[h] = (p, e[5])
spy_hours = sorted(spy_px)
def spy_usd(h):
    i = bisect.bisect_right(spy_hours, h) - 1
    return spy_px[spy_hours[max(i, 0)]][0]

def analyze(name, kind, key, t0, t1, fee_static=None, lp_frac=1.0):
    rows = load(kind, key, fee_static)
    H = hourly(rows, lp_frac)
    hs = [h for h in sorted(H)]
    # quote token is whichever of (t0, t1) is SPY or USDG
    def usd_per_raw(tok, h):
        if tok == USDG: return 1e-6
        if tok == SPY: return spy_usd(h) / 1e18
        return None
    fees_usd = lvr_usd = vol_usd = 0.0; fy = ly = 0.0
    Vs = []
    r2 = []  # hourly log-return squared series
    prev = None; first = last = None; nsw = 0
    h_start = START // BK; h_end = END // BK
    for h in hs:
        if h < h_start or h > h_end:
            if h < h_start: prev = (H[h][2], H[h][3])
            continue
        f0, f1, sp, L, v0, n, _ = H[h]
        P = (sp / Q96) ** 2  # raw1 per raw0
        # USD per raw0 / raw1
        u0 = usd_per_raw(t0, h); u1 = usd_per_raw(t1, h)
        if u0 is None: u0 = u1 * P
        if u1 is None: u1 = u0 / P
        fees_h = f0 * u0 + f1 * u1
        fees_usd += fees_h; vol_usd += v0 * u0; nsw += n
        if prev is not None:
            spp, Lp = prev
            r = 2 * math.log(sp / spp)
            r2.append(r * r)
            lvr_raw1 = r * r * Lp * (spp / Q96) / 4
            lvr_usd += lvr_raw1 * u1
            V = 2 * Lp * (spp / Q96) * u1  # full-range-equivalent value of active liquidity (USD)
            Vs.append(V)
        if first is None: first = (h, P)
        last = (h, P)
        prev = (sp, L)
    days = (min(h_end, last[0]) - max(h_start, first[0])) * BK / 86400 if first else 0
    sig = math.sqrt(sum(r2) / (days / 365)) if days > 0 else float("nan")
    k = last[1] / first[1] if first else float("nan")
    il_fr = 2 * math.sqrt(k) / (1 + k) - 1
    return dict(pool=name, swaps=nsw, days=round(days, 1), vol_usd=vol_usd, fees_usd=fees_usd, lvr_usd=lvr_usd,
                fee_over_lvr=fees_usd / lvr_usd if lvr_usd else float("nan"), sigma_ann=sig,
                fr_fee_yield_ann=fees_usd / (sum(Vs) / len(Vs)) / days * 365 if days and Vs else 0, fr_lvr_ann=lvr_usd / (sum(Vs) / len(Vs)) / days * 365 if days and Vs else 0, meanV=sum(Vs) / len(Vs) if Vs else 0,
                il_fullrange=il_fr, price_ratio=k)

if __name__ == "__main__":
    pools = json.load(open(f"{D}/pools.json"))
    out = []
    for p in pools:
        try:
            r = analyze(p["name"], p["kind"], p["key"], p["t0"], p["t1"], p.get("fee"), p.get("lp_frac", 1.0))
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        r.update(stock=p["stock"], quote=p["quote"], feetier=p["feetier"])
        out.append(r)
    json.dump(out, open(f"{D}/results_{START}_{END}_{BK//3600}h.json", "w"), indent=1)
    print(f"bucket {BK//3600}h  window {datetime.datetime.utcfromtimestamp(START)} -> {datetime.datetime.utcfromtimestamp(END)} UTC")
    hdr = f"{'pool':28} {'fee':>6} {'days':>5} {'swaps':>7} {'volume$':>12} {'fees$':>10} {'LVR$':>10} {'fee/LVR':>7} {'σ ann':>6} {'FR fee%':>7} {'FR LVR%':>7} {'FR IL':>6}"
    print(hdr)
    for r in sorted(out, key=lambda r: (r["stock"], r["quote"])):
        print(f"{r['pool']:28} {r['feetier']:>6} {r['days']:5.0f} {r['swaps']:7d} {r['vol_usd']:12,.0f} {r['fees_usd']:10,.0f} {r['lvr_usd']:10,.0f} {r['fee_over_lvr']:7.2f} {r['sigma_ann']:6.1%} {r['fr_fee_yield_ann']:7.1%} {r['fr_lvr_ann']:7.1%} {r['il_fullrange']:6.2%}")
