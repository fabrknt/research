"""AuctionCreated の configData を解き、各オークションの今の状態(集めた額・約定値・graduated)を eth_call で読む。
usage: python3 enrich.py -> data/auctions.json"""
import json,glob,sys,rpc,concurrent.futures as cf
from eth_abi import decode
raw=json.load(open("data/auctions_raw.json"))
for p in glob.glob("data/auctions_rpc_*.json"): raw+=json.load(open(p))["items"]
SEL=dict(currencyRaised="0x998ba4fc",clearingPrice="0x32a0f2d7",isGraduated="0x9e5f2602",totalCleared="0x3e9d9174")
IDX={"ethereum":0,"unichain":0,"arbitrum":0,"base":0}
def ec(ch,to,data):
    try: return rpc.call(ch,"eth_call",[dict(to=to,data=data),"latest"],i=IDX[ch],tries=3)
    except Exception: return None
def u(h): return int(h,16) if h and h!="0x" else None
def sym(h):
    if not h or h=="0x": return None
    b=bytes.fromhex(h[2:])
    try: return decode(["string"],b)[0]
    except Exception: return b.rstrip(b"\0").decode(errors="ignore")
tokcache={}
def tokinfo(ch,t):
    if t=="0x"+"0"*40: return ("ETH",18)
    k=(ch,t)
    if k not in tokcache: tokcache[k]=(sym(ec(ch,t,"0x95d89b41")),u(ec(ch,t,"0x313ce567")))
    return tokcache[k]
def one(a):
    d=bytes.fromhex(a["data"][2:])
    amount,cfg=decode(["uint256","bytes"],d)
    p=decode(["(address,address,address,uint64,uint64,uint64,uint256,address,uint256,uint128,bytes)"],cfg)[0]
    a.update(amount=amount,currency=p[0].lower(),tokensRecipient=p[1],fundsRecipient=p[2],startBlock=p[3],endBlock=p[4],claimBlock=p[5],
             floorPriceQ96=p[8],requiredCurrencyRaised=p[9],validationHook=p[7])
    for k,s in SEL.items(): a[k]=u(ec(a["chain"],a["auction"],s))
    a["tokSym"],a["tokDec"]=tokinfo(a["chain"],a["token"]); a["curSym"],a["curDec"]=tokinfo(a["chain"],a["currency"])
    return a
import os
done={(x["chain"],x["auction"]):x for x in json.load(open("data/auctions.json"))} if os.path.exists("data/auctions.json") else {}
todo=[a for a in raw if (a["chain"],a["auction"]) not in done]   # 済んだ物は読み直さない
print("todo",len(todo),file=sys.stderr)
with cf.ThreadPoolExecutor(6) as ex: out=list(done.values())+list(ex.map(one,todo))
json.dump(out,open("data/auctions.json","w"),indent=1)
print(len(out))
