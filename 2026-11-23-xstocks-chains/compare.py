"""Round-trip cost of tokenized US shares by chain and issuer, from rows of the recorder's evm_stock_quotes
(KyberSwap: BNB Chain, Ethereum, Arbitrum, Robinhood Chain) and xstocks_quotes (Jupiter: Solana).

    python3 -I compare.py SNAPSHOT.json            # {"evm": [rows], "sol": [rows]}, e.g. one local run
    python3 -I compare.py --read FROM TO           # the recorder's hours in [FROM, TO) via recorder/read.py

A round trip is: buy `usd` of the share with the chain's dollar token, sell back what the buy would get;
cost = 1 - dollars back / usd, in bp. Quotes are each aggregator's best route at that moment, not a fill.
Printed per share: the cheapest chain/issuer at $10k and $100k, and every venue that took part in that route.
"""

import collections, json, statistics, subprocess, sys
from pathlib import Path

DEC = {"bsc": 18, "ethereum": 6, "arbitrum": 6, "robinhood": 6, "solana": 6}


def pairs(rows, chain_of, key_of, venue_of):
    """(key, usd) -> list of (cost_bp, venues); a buy row followed by its sell row."""
    out, last = collections.defaultdict(list), {}
    for r in rows:
        if r.get("kind") != "quote":
            continue
        k = (key_of(r), r["usd"])
        if r["side"] == "buy":
            last[k] = r
            continue
        b = last.pop(k, None)
        if not b or "out" not in b or "out" not in r or r.get("amount") != b["out"]:
            continue
        back = r["out"] / 10 ** DEC[chain_of(r)]
        out[k].append((1e4 * (1 - back / r["usd"]), sorted(set(venue_of(b)) | set(venue_of(r)))))
    return out


def load(argv):
    if argv[0] == "--read":
        rd = Path(__file__).resolve().parent.parent / "recorder" / "read.py"
        get = lambda s: [json.loads(l) for l in subprocess.run(
            [sys.executable, "-I", str(rd), s, "--from", argv[1], "--to", argv[2]],
            capture_output=True, text=True, check=True).stdout.splitlines() if l.strip()]
        return get("evm_stock_quotes"), get("xstocks_quotes")
    d = json.load(open(argv[0]))
    return d["evm"], d["sol"]


def main(argv):
    evm, sol = load(argv)
    e = pairs(evm, lambda r: r["chain"], lambda r: (r["chain"], r["issuer"], r["share"]),
              lambda r: [v[0] for v in r.get("route", [])])
    s = pairs([r for r in sol if r.get("venue") == "any"], lambda r: "solana",
              lambda r: ("solana", "xstocks", r["sym"].rstrip("x")), lambda r: [v[0] for v in r.get("route", [])])
    allp = {**e, **s}
    shares = sorted({k[0][2] for k in allp})
    for usd in (10_000, 100_000):
        print(f"\n${usd:,} round trip, median bp over the runs (n): cheapest first, then the rest")
        for sh in shares:
            cells = []
            for (key, u), v in allp.items():
                if u != usd or key[2] != sh:
                    continue
                med = statistics.median(c for c, _ in v)
                venues = sorted({x for _, vs in v for x in vs})
                cells.append((med, f"{key[0]}/{key[1]}", len(v), venues))
            if not cells:
                continue
            cells.sort()
            best = cells[0]
            rest = ", ".join(f"{c[1]} {c[0]:.0f}" for c in cells[1:])
            print(f"  {sh:6s} {best[1]:20s} {best[0]:7.0f} bp (n={best[2]}) via {','.join(best[3])}")
            if rest:
                print(f"  {'':6s}   others: {rest}")


if __name__ == "__main__":
    main(sys.argv[1:])
