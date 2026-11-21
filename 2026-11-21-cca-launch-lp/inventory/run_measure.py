"""migr_CHAIN.json のうち migrate 済みを raisedUSD の大きい順に N 件測る。 usage: python3 run_measure.py CHAIN N -> data/lp_CHAIN.json"""
import json,sys,bisect,measure
ch=sys.argv[1]; N=int(sys.argv[2])
eth=json.load(open("data/eth_usd_daily.json"))["prices"]; ET=[p[0]/1000 for p in eth]
def ethusd(t): i=max(0,min(len(ET)-1,bisect.bisect_left(ET,t))); return eth[i][1]
A=[a for a in json.load(open(f"data/migr_{ch}.json")) if a.get("status")=="migrated"]
A.sort(key=lambda a:-(a["raisedUSD"] or 0))
out=[]
for a in A[:N]:
    res=measure.run(ch,a)
    if not res["day"]:   # migrate 後 48 時間に取引なし(Aztec など移転制限つき) -> 最初の swap から 24 時間を測る
        import logs
        fs=logs.first_log(ch,[measure.SWAP,a["migr"]["poolId"]],a["migr"]["block"],a["migr"]["block"]+{"ethereum":7200,"unichain":86400,"base":43200,"arbitrum":345600}[ch]*(120 if ch=="ethereum" else 7))
        if fs: a["firstSwapBlock"]=fs["n"]; res=measure.run(ch,a,b0=a["firstSwapBlock"])
    usdper=ethusd(res["tb0"]) if a["curSym"] in ("ETH","WETH") else 1.0
    sm=measure.summarize(a,res,usdper); sm.update(chain=ch,tok=a["tokSym"],cur=a["curSym"],auction=a["auction"],poolId=a["migr"]["poolId"],hooks=a["migr"]["hooks"],
        migrBlock=a["migr"]["block"],migrTx=a["migr"]["tx"],raisedUSD=a["raisedUSD"],usdper=usdper,firstSwapBlock=a.get("firstSwapBlock"))
    json.dump(res["day"],open(f"data/swaps_{ch}_{a['migr']['poolId'][:10]}.json","w"))
    print(json.dumps({k:v for k,v in sm.items() if k!="top5"}),flush=True)
    out.append(sm)
json.dump(out,open(f"data/lp_{ch}.json","w"),indent=1)
