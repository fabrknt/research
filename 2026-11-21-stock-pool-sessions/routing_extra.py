"""Two checks behind routing.py: (1) for the two largest PoolManager callers, how many distinct tx.from in a
sample of their transactions (one or a few signers = a trading bot, many = a public router); (2) who pays
fee 0 in SessionFeeHook pools (its source: 'exempt senders (the arb team's swap contracts) pay 0')."""
import json, os, pickle, random, sys
from collections import Counter, defaultdict
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import rowtype  # noqa
from rpc import call
rows = pickle.load(open(f"{H}/data/rows.pkl", "rb"))["rows"]
random.seed(7)
out = {}
for snd in ("0x520ed467860d840ec6ca20f1dacb9c0fa5168aa7", "0x278d858f05b94576c1e6f73285886876ff6ef8d2"):
    txs = list({r.tx for r in rows if r.sender == snd})
    s = random.sample(txs, min(200, len(txs)))
    fr = Counter(call("eth_getTransactionByHash", [h])["from"] for h in s)
    out[snd] = {"txs": len(txs), "sampled": len(s), "distinct_from": len(fr), "top_from_share": round(fr.most_common(1)[0][1] / len(s), 3)}
    print(snd, out[snd])
SFH = "0xc15b155a3094934171a15625d1a80aba267b6080"
z = defaultdict(float); tot = 0.0
for r in rows:
    if r.hooks == SFH:
        tot += r.usd
        if r.fee == 0:
            z[r.sender] += r.usd
out["sessionfeehook_zero_fee_senders"] = {k: round(v / tot, 3) for k, v in sorted(z.items(), key=lambda kv: -kv[1])[:5]}
print("SessionFeeHook fee-0 volume by sender (share of the hook's volume):", out["sessionfeehook_zero_fee_senders"])
json.dump(out, open(f"{H}/results/routing_extra.json", "w"), indent=1)
