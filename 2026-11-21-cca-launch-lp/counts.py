"""Inventory counts from data/catalog.json (built by inventory/*.py) and the bid counts from data/bids.json.
usage: python3 -I counts.py -> results/inventory.txt, results/auctions_ge10k.csv"""
import json, collections, csv
C = json.load(open("data/catalog.json")); B = json.load(open("data/bids.json"))
L = []
def P(*a): s = " ".join(str(x) for x in a); L.append(s); print(s)
FAKE = "0xfdf2d30db46f0d56e4c6aba6a8615ec4ce30f36f"   # Base test token named "USD Coin"; auctions in it are excluded
by = collections.defaultdict(collections.Counter)
for c in C:
    k = c["chain"]; by[k]["created"] += 1; by[k]["graduated"] += bool(c["graduated"])
    by[k]["migrated"] += c["status"] == "migrated"
    if c["graduated"] and (c["raisedUSD"] or 0) >= 1e4: by[k]["grad>=10k"] += 1
    if c["graduated"] and (c["raisedUSD"] or 0) >= 1e5: by[k]["grad>=100k"] += 1
P("chain | created | graduated | migrated to v4 | graduated >= $10k | graduated >= $100k")
tot = collections.Counter()
for k in ("ethereum", "base", "unichain", "arbitrum"):
    P(k, "|", " | ".join(str(by[k][x]) for x in ("created", "graduated", "migrated", "grad>=10k", "grad>=100k"))); tot.update(by[k])
P("total |", " | ".join(str(tot[x]) for x in ("created", "graduated", "migrated", "grad>=10k", "grad>=100k")))
g = sum((c["raisedUSD"] or 0) for c in C if c["graduated"])
P(f"graduated raised total ${g:,.0f}; largest share {max((c['raisedUSD'] or 0) for c in C if c['graduated'])/g:.1%}")
P(f"first auction created {min(c['created'] for c in C)}, last {max(c['created'] for c in C)}")
rows = []
for c in sorted(C, key=lambda c: -(c["raisedUSD"] or 0)):
    if not (c["graduated"] and (c["raisedUSD"] or 0) >= 1e4): continue
    b = B.get(f'{c["chain"]}:{c["auction"]}', {}).get("bids", [])
    rows.append(dict(chain=c["chain"], token=c["tok"], auction=c["auction"], start=c["start"], end=c["end"], raisedUSD=round(c["raisedUSD"]),
                     clearing=c["clearing"], bids=len(b), bidders=len(set(x["owner"] for x in b)), status=c["status"], poolId=c["poolId"], hooks=c["hooks"], fee=c["fee"]))
w = csv.DictWriter(open("results/auctions_ge10k.csv", "w"), fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
P(); P("graduated >= $10k: chain | token | raised $ | clearing | bids | bidders | status")
for r in rows: P(f'{r["chain"]} | {r["token"]} | {r["raisedUSD"]:,} | {r["clearing"]:.4g} | {r["bids"]} | {r["bidders"]} | {r["status"]}')
open("results/inventory.txt", "w").write("\n".join(L) + "\n")
s = [c for c in C if c["graduated"] and c["status"] is not None]
P(f"migration searched for {len(s)} graduated auctions (raised >= $1k, or in a currency without a USD price): "
  f"migrated {sum(c['status']=='migrated' for c in s)}, no migration found {sum(c['status']=='no_migration_found' for c in s)}, live {sum(c['status']=='live' for c in s)}; "
  f"graduated below $1k were not searched ({sum(1 for c in C if c['graduated'] and c['status'] is None)})")
open("results/inventory.txt", "w").write("\n".join(L) + "\n")
