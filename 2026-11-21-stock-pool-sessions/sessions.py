"""Tables from data/rows.pkl: passive-LP result by session, bell window, name, pool kind and direction.
Prints and writes results/sessions.json. Sign: + = LPs gained, − = LPs lost. bp of volume."""
import json, os, pickle, sys
from collections import defaultdict

H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H)
import rowtype  # noqa: F401 (unpickling)
Z = "0x" + "0" * 40
d = pickle.load(open(f"{H}/data/rows.pkl", "rb"))
rows = d["rows"]
t0, t1 = min(r["t"] for r in rows), max(r["t"] for r in rows)
days = (t1 - t0) / 86400
HS = [60, 300, 3600, "reopen"]
SESS = ["rth", "pre", "after", "overnight", "weekend"]
BELLS = ["open", "monday_open", "close"]


def kind(r):
    return "hookless" if r["hooks"] == Z else ("fables" if r["fables"] else "other_hook")


def agg(rs):
    o = {"n": len(rs), "usd": sum(r["usd"] for r in rs)}
    if not o["usd"]:
        return o
    o["usd_per_day"] = o["usd"] / days
    o["fee_bp"] = sum(r["fee"] * r["usd"] for r in rs) / o["usd"] * 1e4
    for h in HS:
        xs = [r for r in rs if r["lp"].get(h) is not None]
        u = sum(r["usd"] for r in xs)
        if u:
            net = sum(r["lp"][h] * r["usd"] for r in xs)
            fee = sum(r["fee"] * r["usd"] for r in xs)
            o[f"net_bp_{h}"] = net / u * 1e4
            o[f"gross_bp_{h}"] = (net - fee) / u * 1e4
            o[f"net_usd_{h}"] = net
            o[f"cov_{h}"] = u / o["usd"]
    for h in (300, 3600):
        xs = [r for r in rs if r["pool_lp"].get(h) is not None]
        u = sum(r["usd"] for r in xs)
        o[f"poolref_net_bp_{h}"] = sum(r["pool_lp"][h] * r["usd"] for r in xs) / u * 1e4 if u else None
    return o


def line(name, o):
    if not o.get("usd"):
        return f"{name:22s} no volume"
    s = f"{name:22s} ${o['usd']/1e6:7.1f}M (${o['usd_per_day']/1e6:5.2f}M/d) fee {o['fee_bp']:5.1f}bp |"
    for h in (300, 3600):
        if f"net_bp_{h}" in o:
            s += f" {h}s: gross {o[f'gross_bp_{h}']:6.1f} net {o[f'net_bp_{h}']:6.1f}bp ${o[f'net_usd_{h}']/1e3:7.1f}K |"
    if "net_bp_reopen" in o:
        s += f" reopen: net {o['net_bp_reopen']:6.1f}bp ${o['net_usd_reopen']/1e3:7.1f}K |"
    if o.get("poolref_net_bp_3600") is not None:
        s += f" pool-ref 1h {o['poolref_net_bp_3600']:6.1f}bp"
    return s


res = {"days": round(days, 2), "from": t0, "to": t1, "k": d["k"]}
import datetime as dt
from zoneinfo import ZoneInfo
print(f"{dt.datetime.utcfromtimestamp(t0):%Y-%m-%d %H:%M} to {dt.datetime.utcfromtimestamp(t1):%Y-%m-%d %H:%M} UTC, "
      f"{days:.1f} days, {len(rows):,} swaps, ${sum(r['usd'] for r in rows)/1e6:.1f}M")
print("\n== by session (all selected pools)")
res["session"] = {}
for s in SESS:
    o = agg([r for r in rows if r["sess"] == s])
    res["session"][s] = o
    print(line(s, o))
o = agg(rows)
res["session"]["all"] = o
print(line("all", o))
print("\n== bell windows (subsets of the sessions above)")
res["bell"] = {}
for b in BELLS:
    o = agg([r for r in rows if r["bell"] == b])
    res["bell"][b] = o
    print(line(b, o))

print("\n== by pool kind x session")
res["kind"] = {}
for k in ("hookless", "fables", "other_hook"):
    for s in SESS + ["all"]:
        o = agg([r for r in rows if kind(r) == k and (s == "all" or r["sess"] == s)])
        res["kind"][f"{k}/{s}"] = o
        print(line(f"{k}/{s}", o))

print("\n== by direction (swap moved the pool toward / away from the HL reference) x session")
res["direction"] = {}
for tw in (True, False):
    for s in SESS + ["all"]:
        o = agg([r for r in rows if r["toward"] is tw and (s == "all" or r["sess"] == s)])
        nm = ("toward" if tw else "away") + "/" + s
        res["direction"][nm] = o
        print(line(nm, o))

print("\n== by name (stock leg), sorted by net $ at 1 h; 12 largest losses")
syms = defaultdict(list)
for r in rows:
    syms[r["sym"]].append(r)
byname = {s: agg(rs) for s, rs in syms.items()}
res["name"] = byname
order = sorted(byname, key=lambda s: byname[s].get("net_usd_3600", 0))
for s in order[:12]:
    print(line(s, byname[s]))
print("   ... and the 5 largest gains")
for s in order[-5:]:
    print(line(s, byname[s]))
print("\n== name x session net $ at 1 h, the 8 largest losers")
res["name_session"] = {}
for s in order[:8]:
    parts = []
    for se in SESS:
        o = agg([r for r in syms[s] if r["sess"] == se])
        res["name_session"][f"{s}/{se}"] = o
        parts.append(f"{se} ${o.get('net_usd_3600', 0)/1e3:7.1f}K")
    print(f"{s:6s} " + " | ".join(parts))

print("\n== 15 largest (name, ET date, session) losses at 1 h")
ev = defaultdict(list)
for r in rows:
    ev[(r["sym"], dt.datetime.fromtimestamp(r["t"], ZoneInfo("America/New_York")).strftime("%Y-%m-%d %a"), r["sess"])].append(r)
evs = {k: agg(v) for k, v in ev.items()}
top = sorted(evs, key=lambda k: evs[k].get("net_usd_3600", 0))[:15]
res["events"] = []
allloss = sum(min(0, o.get("net_usd_3600", 0)) for o in evs.values())
for k in top:
    o = evs[k]
    res["events"].append({"sym": k[0], "date": k[1], "sess": k[2], **o})
    print(line(" ".join(k), o))
print(f"   these 15 of {len(evs)} (name, day, session) cells: ${sum(evs[k]['net_usd_3600'] for k in top)/1e3:.1f}K; "
      f"sum of all losing cells ${allloss/1e3:.1f}K")

print("\n== by period (the 11-13 study ended 2026-11-13 ~06:40 UTC)")
cut = dt.datetime(2026, 11, 13, 6, 40, tzinfo=dt.timezone.utc).timestamp()
res["period"] = {}
for nm, f in (("to 11-13", lambda r: r["t"] < cut), ("after 11-13", lambda r: r["t"] >= cut)):
    for s in SESS + ["all"]:
        o = agg([r for r in rows if f(r) and (s == "all" or r["sess"] == s)])
        res["period"][f"{nm}/{s}"] = o
        print(line(f"{nm}/{s}", o))

print("\n== same names, Fables (session-floor hooks) vs hookless pools, stock/USDG only")
fab_syms = {r["sym"] for r in rows if r["fables"] and r["usdq"]}
res["fables_vs_hookless"] = {}
for k in ("fables", "hookless"):
    for s_ in SESS + ["all"]:
        o = agg([r for r in rows if r["usdq"] and r["sym"] in fab_syms and kind(r) == k and (s_ == "all" or r["sess"] == s_)])
        res["fables_vs_hookless"][f"{k}/{s_}"] = o
        print(line(f"{k}/{s_}", o))
    for b in BELLS:
        o = agg([r for r in rows if r["usdq"] and r["sym"] in fab_syms and kind(r) == k and r["bell"] == b])
        res["fables_vs_hookless"][f"{k}/{b}"] = o
        print(line(f"{k}/{b}", o))
print("names:", sorted(fab_syms))

json.dump(res, open(f"{H}/results/sessions.json", "w"), indent=1, default=float)
