"""全オークションの一覧と月別件数。 usage: python3 catalog.py -> data/catalog.json と標準出力(月別表)"""
import json,glob,bisect,collections,datetime,rpc
A=json.load(open("data/auctions.json"))
eth=json.load(open("data/eth_usd_daily.json"))["prices"]; ET=[p[0]/1000 for p in eth]
def ethusd(t): i=max(0,min(len(ET)-1,bisect.bisect_left(ET,t))); return eth[i][1]
STABLE={"USDC","USDT","USD₮0","USDT0","DAI","USDS"}
anch={}
def anchors(ch):
    if ch not in anch:
        hd=rpc.bn(ch); pts=[]
        for n in ([min(x["block"] for x in A if x["chain"]==ch)-1, hd] if ch in("base","unichain") else
                  [int(min(x["block"] for x in A if x["chain"]==ch)+k*(hd-min(x["block"] for x in A if x["chain"]==ch))/24) for k in range(25)]):
            pts.append((n,int(rpc.call(ch,"eth_getBlockByNumber",[hex(n),False])["timestamp"],16)))
        anch[ch]=sorted(pts)
    return anch[ch]
def btime(ch,n):
    p=anchors(ch); N=[x[0] for x in p]; i=min(max(bisect.bisect_left(N,n),1),len(p)-1)
    (n0,t0),(n1,t1)=p[i-1],p[i]; return t0+(t1-t0)*(n-n0)/(n1-n0)
mig={}
for f in glob.glob("data/migr_*.json"):
    for a in json.load(open(f)): mig[(a["chain"],a["auction"])]=a
rows=[]
for a in A:
    ch=a["chain"]; t=btime(ch,a["block"]); te=btime(ch,a["endBlock"]); ts=btime(ch,a["startBlock"])
    x=(a["currencyRaised"] or 0)/10**(a["curDec"] or 18)
    usd=x*ethusd(te) if a["curSym"] in("ETH","WETH") else x if a["curSym"] in STABLE else None
    cp=a["clearingPrice"]; cph=cp/2**96*10**((a["tokDec"] or 18)-(a["curDec"] or 18)) if cp else None
    m=mig.get((ch,a["auction"]),{})
    mm=m.get("migr") or {}
    rows.append(dict(chain=ch,ver=a["ver"],auction=a["auction"],token=a["token"],tok=a["tokSym"],cur=a["curSym"],created=datetime.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d"),
        start=datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M"),end=datetime.datetime.utcfromtimestamp(te).strftime("%Y-%m-%d %H:%M"),
        startBlock=a["startBlock"],endBlock=a["endBlock"],raised=x,raisedUSD=usd,clearing=cph,graduated=a["isGraduated"],
        fundsRecipient=a["fundsRecipient"],status=m.get("status"),migrBlock=mm.get("block"),migrTx=mm.get("tx"),poolId=mm.get("poolId"),hooks=mm.get("hooks"),fee=mm.get("fee"),positions=mm.get("positions")))
json.dump(rows,open("data/catalog.json","w"),indent=1)
mon=collections.defaultdict(lambda:[0,0,0,0])
for r in rows:
    k=r["created"][:7]; mon[k][0]+=1; mon[k][1]+=r["graduated"]==1
    mon[k][2]+=(r["graduated"]==1 and (r["raisedUSD"] or 0)>=10000); mon[k][3]+=(r["graduated"]==1 and (r["raisedUSD"] or 0)>=100000)
print("month created graduated grad>=$10k grad>=$100k")
for k in sorted(mon): print(k,*mon[k])
c=collections.Counter(r["chain"] for r in rows); g=collections.Counter(r["chain"] for r in rows if r["graduated"]==1)
print("by chain",dict(c),"graduated",dict(g))
print("total raised USD (graduated, priced):",sum(r["raisedUSD"] or 0 for r in rows if r["graduated"]==1))
