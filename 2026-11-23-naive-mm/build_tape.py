"""Build a tape for the replay from the 2026-11-21-elysium-direction pipeline's output.
usage: python3 -I build_tape.py WORKDIR FROM_UNIX_S OUT.csv
  WORKDIR = a directory where that study's steps were run for the window (it reads
  WORKDIR/data/rows_HYPE_E.json and WORKDIR/data/hl/HYPE.json); trades before FROM are dropped
  (they only seed the 30-minute basis).
Columns: t, side (the taker's), px (average execution price), usd, e (that study's E: HyperCore
perp interpolated inside the minute toward its close, times the median basis of the previous 30
minutes: up to a minute of hindsight), h (HyperCore perp, open of the minute after the trade: the
hedge price), ec (E from what is known at the trade: this minute's open times the median of
price / its minute's open over earlier trades in the previous 30 minutes; the open alone when
fewer than 5 such trades)."""
import bisect, json, statistics as st, sys

work, start, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
rows = json.load(open(f"{work}/data/rows_HYPE_E.json"))
c = {int(k): v for k, v in json.load(open(f"{work}/data/hl/HYPE.json")).items()}
rows = [r for r in rows if abs(r["px"] / r["e0"] - 1) < 0.05]
rows.sort(key=lambda r: r["t"])  # stable: keeps chain order within a second
T = [r["t"] for r in rows]
G = [float(f"{r['px']:.6f}") / c[int(r["t"]) // 60][0] for r in rows]  # px as written to the tape
n = 0
with open(out, "w") as f:
    f.write("t,side,px,usd,e,h,ec\n")
    for i, r in enumerate(rows):
        if r["t"] < start:
            continue
        t = r["t"]
        lo, hi = bisect.bisect_left(T, t - 1800), bisect.bisect_left(T, t)
        o = c[int(t) // 60][0]
        ec = o * st.median(G[lo:hi]) if hi - lo >= 5 else o
        h = c[int(t) // 60 + 1][0]
        f.write(f"{t},{'buy' if r['s'] > 0 else 'sell'},{r['px']:.6f},{r['usd']:.2f},{r['e0']:.6f},{h:.6f},{ec:.6f}\n")
        n += 1
print(n, "trades ->", out)
