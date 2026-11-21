"""Every BidSubmitted of the graduated CCAs that raised $10k or more (14 auctions), from the auction contract's logs.
BidSubmitted(uint256 indexed id, address indexed owner, uint256 priceQ96, uint128 amount)
(continuous-clearing-auction ce78b4d, src/interfaces/IContinuousClearingAuction.sol:103).
priceQ96 is the bid's max price, currency per token in raw units times 2^96; amount is the currency put in.
usage: python3 -I bids.py -> data/bids.json"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rpc, logs, time
def slow(ch, method, params, tries=8):
    """Base's free RPC rate-limits hard; back off for minutes instead of failing."""
    for k in range(60):
        try: return rpc.call(ch, method, params, tries=tries)
        except RuntimeError as e:
            if ch != "base" or "429" not in str(e): raise
            time.sleep(30)
    raise RuntimeError("base still rate-limited")

BID = "0x650baad5cd8ca09b8f580be220fa04ce2ba905a041f764b6a3fe2c848eb70540"
C = json.load(open("data/catalog.json"))
M = {}
for ch in ("ethereum", "base", "unichain", "arbitrum"):
    for a in json.load(open(f"data/migr_{ch}.json")): M[(ch, a["auction"].lower())] = a
T = [c for c in C if c["graduated"] and (c["raisedUSD"] or 0) >= 1e4]
out = {}
if os.path.exists("data/bids.json"): out = json.load(open("data/bids.json"))
for c in T:
    key = f'{c["chain"]}:{c["auction"]}'
    if key in out: continue
    a = M[(c["chain"], c["auction"].lower())]
    dt, dc = a["tokDec"] or 18, a["curDec"] or 18
    ch = c["chain"]
    if ch == "ethereum":
        raw = logs.get_logs(ch, [BID], c["startBlock"], c["endBlock"] + 10, address=c["auction"])
    else:
        st = {"base": 1000, "unichain": 100000, "arbitrum": 100000}[ch]
        raw = []; b = c["startBlock"]
        while b <= c["endBlock"] + 10:
            e = min(b + st - 1, c["endBlock"] + 10)
            raw += [logs.norm(x) for x in slow(ch, "eth_getLogs", [dict(address=c["auction"], topics=[BID], fromBlock=hex(b), toBlock=hex(e))], tries=8)]
            b = e + 1
    bids = []
    for l in raw:
        d = l["data"][2:]
        if len(d) < 128: continue
        p = int(d[:64], 16) / 2**96 * 10**(dt - dc); amt = int(d[64:128], 16) / 10**dc
        bids.append(dict(n=l["n"], id=int(l["topics"][1], 16), owner="0x" + l["topics"][2][26:], maxPrice=p, amount=amt))
    out[key] = dict(chain=ch, tok=c["tok"], auction=c["auction"], clearing=c["clearing"], raisedUSD=c["raisedUSD"], raised=c["raised"],
                    cur=a["curSym"], startBlock=c["startBlock"], endBlock=c["endBlock"], bids=bids)
    print(ch, c["tok"], len(bids), "bids", len(set(b["owner"] for b in bids)), "owners", file=sys.stderr, flush=True)
    json.dump(out, open("data/bids.json", "w"))
