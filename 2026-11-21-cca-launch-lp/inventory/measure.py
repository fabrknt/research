"""migrate 済みのプールで、migrate から 24 時間の v4 Swap を取り、LP から見た markout を出す。
基準はプール自身の価格(swap 後の sqrtPriceX96 を時刻順に並べ、t+5分/1時間/24時間の時点の値)。
LP の損益(currency 建て) = -(利用者が受け取った token × P_h) - (利用者が受け取った currency)。v4 の Swap の amount は
利用者から見た増減で手数料込みなので、これが「手数料後」。手数料前 = 手数料後 - 手数料収入(入力側 × fee)。
usage: python3 measure.py CHAIN POOLID_or_TOKSYM -> data/swaps_CHAIN_POOLID.json と標準出力に要約"""
import json,sys,bisect,collections,rpc,logs,concurrent.futures as cf
from eth_abi import decode
SWAP="0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f"; MODL="0xf208f4912782fd25c7f114ca3723a2d5dd6f3bcc3ac8db5af63baa85f711d5ec"
BT={"ethereum":12,"unichain":1,"base":2,"arbitrum":0.25}
def s(h): v=int(h,16); return v-(1<<256) if v>>255 else v
def run(ch,a,horizon_h=48,with_from=True,b0=None):
    m=a["migr"]; pid=m["poolId"]; b0=b0 or m["block"]
    head=rpc.bn(ch); b1=min(head,b0+int(horizon_h*3600/BT[ch])+50)
    raw=logs.get_logs(ch,[SWAP,pid],b0,b1)
    bad=[l for l in raw if len(l["data"])<2+64*6]
    if bad:   # Routescan がまれに data を空で返す -> そのブロックを RPC で取り直す
        fix={}
        for n in sorted(set(l["n"] for l in bad)):
            for x in rpc.call(ch,"eth_getLogs",[dict(address=logs.PM[ch],topics=[SWAP,pid],fromBlock=hex(n),toBlock=hex(n))],tries=6):
                fix[(x["transactionHash"].lower(),int(x["logIndex"],16))]=x["data"]
        for l in bad: l["data"]=fix.get((l["tx"].lower(),l["i"]),l["data"])
    raw=[l for l in raw if len(l["data"])>=2+64*6]
    print('swaps',a['tokSym'],len(raw),'refetched',len(bad),file=sys.stderr,flush=True)
    tok=a["token"].lower(); 
    # 仮想トークン(Aztec 等)の場合 migrate 先は別トークンなので、currency でない側を token とみなす
    cur=a["currency"].lower(); c0,c1=m["currency0"].lower(),m["currency1"].lower()
    tokIs0 = (c1==cur) if cur in (c0,c1) else (c0==tok)
    dt=a["tokDec"] or 18; dc=a["curDec"] or 18
    if tok not in (c0,c1):  # 実トークンの decimals を読む
        real=c0 if tokIs0 else c1; dt=int(rpc.call(ch,"eth_call",[dict(to=real,data="0x313ce567"),"latest"]),16)
    def px(sp):
        p=(sp/2**96)**2
        return p*10**(dt-dc) if tokIs0 else (1/p)*10**(dt-dc) if p>0 else None
    t0=None
    # ブロック時刻: ログに無ければ最初と最後のブロックの時刻から線形に(L2 は等間隔、Arbitrum はほぼ)
    def bt(n): return int(rpc.call(ch,"eth_getBlockByNumber",[hex(n),False],tries=4)["timestamp"],16)
    tb0=bt(b0); tb1=bt(b1)
    rows=[]
    for l in sorted(raw,key=lambda x:(x["n"],x["i"])):
        w=[l["data"][2+k:2+k+64] for k in range(0,len(l["data"])-2,64)]
        a0,a1,sp,liq,fee=s(w[0]),s(w[1]),int(w[2],16)&((1<<160)-1),int(w[3],16)&((1<<128)-1),int(w[5],16)&0xffffff   # 手で解く(eth_abi は詰め物に厳しい)
        ut,uc=(a0,a1) if tokIs0 else (a1,a0)
        ut/=10**dt; uc/=10**dc
        if ut==0 or uc==0: continue
        t=l["t"] if l["t"] else tb0+(tb1-tb0)*(l["n"]-b0)/max(1,b1-b0)
        rows.append(dict(n=l["n"],i=l["i"],t=t,tx=l["tx"],router="0x"+l["topics"][2][26:],ut=ut,uc=uc,px=abs(uc/ut),after=px(sp),fee=fee/1e6,liq=liq))
    T=[r["t"] for r in rows]
    P0=px(m["sqrtPriceX96"])
    def P(t):
        i=bisect.bisect_right(T,t)-1
        return rows[i]["after"] if i>=0 else P0
    tend=tb0+86400
    day=[r for r in rows if r["t"]<tend]
    for r in day:
        r["feeRev"]=abs(r["uc"])*r["fee"] if r["uc"]<0 else abs(r["ut"])*r["fee"]*r["px"]
        for k,h in (("m5",300),("m1h",3600),("m24h",86400)):
            ph=P(r["t"]+h); r[k]=-(r["ut"]*ph)-r["uc"]       # 手数料後、currency 建て
    if with_from and day:
        def frm(h): return rpc.call(ch,"eth_getTransactionByHash",[h],tries=4)["from"].lower()
        txs=sorted(set(r["tx"] for r in day))
        print('tx lookups',len(txs),file=sys.stderr,flush=True)
        got=rpc.batch(ch,"eth_getTransactionByHash",[[h] for h in txs])
        fm={h:(g["from"].lower() if g else None) for h,g in zip(txs,got)}
        for h in [h for h in txs if fm[h] is None]: fm[h]=frm(h)
        for r in day: r["from"]=fm[r["tx"]]
    return dict(rows=rows,day=day,P0=P0,tb0=tb0,b0=b0,b1=b1,tokIs0=tokIs0)
def summarize(a,res,usdper):
    d=res["day"]; m=a["migr"]
    if not d: return dict(n=0)
    vol=sum(abs(r["uc"]) for r in d); fee=sum(r["feeRev"] for r in d)
    out=dict(n=len(d),vol=vol,volUSD=vol*usdper,feeUSD=fee*usdper,feeTier=m["fee"],
             buys=sum(1 for r in d if r["ut"]>0),buyVolShare=sum(abs(r["uc"]) for r in d if r["ut"]>0)/vol)
    for k in ("m5","m1h","m24h"):
        post=sum(r[k] for r in d); out[k+"_postUSD"]=post*usdper; out[k+"_preUSD"]=(post-fee)*usdper
        out[k+"_post_bp"]=post/vol*1e4; out[k+"_pre_bp"]=(post-fee)/vol*1e4
    if "from" in d[0]:
        byf=collections.Counter()
        for r in d: byf[r["from"]]+=abs(r["uc"])
        out["uniqFrom"]=len(byf); out["top5share"]=sum(v for _,v in byf.most_common(5))/vol
        out["top5"]=[(k,v/vol) for k,v in byf.most_common(5)]
    b0=res["b0"]
    same=[r for r in d if r["n"]==b0]; first5=[r for r in d if r["n"]<=b0+5]; first5m=[r for r in d if r["t"]<res["tb0"]+300]
    out.update(sameBlockN=len(same),sameBlockVolShare=sum(abs(r["uc"]) for r in same)/vol,
               first5blkN=len(first5),first5blkVolShare=sum(abs(r["uc"]) for r in first5)/vol,
               first5blk_m24h_postUSD=sum(r["m24h"] for r in first5)*usdper,
               first5minVolShare=sum(abs(r["uc"]) for r in first5m)/vol,
               P0=res["P0"],P24=d[-1]["after"],firstSwapBlockDelta=d[0]["n"]-b0)
    return out
