"""チェーンごとに、topic で絞った PoolManager のログを鍵なしで取る。
ethereum=Routescan(etherscan 互換) / unichain=Blockscout v1 / arbitrum=arb1 RPC(10万ブロック) / base=Tenderly 公開 RPC(1000 ブロック)"""
import json,urllib.request,time,sys,rpc
PM={"ethereum":"0x000000000004444c5dc75cB358380D2e3dE08A90","unichain":"0x1F98400000000000000000000000000000000004",
    "base":"0x498581fF718922c3f8e6A244956aF099B2652b2b","arbitrum":"0x360E68faCcca8cA495c1B759Fd9EEe466db9FB32"}
API={"ethereum":"https://api.routescan.io/v2/network/mainnet/evm/1/etherscan/api"}  # unichain の Blockscout は 429 が続いたので RPC に切り替えた
STEP={"arbitrum":100000,"base":1000,"unichain":100000}
PAGE={"ethereum":10000,"unichain":1000}
def _get(u):
    for k in range(12):
        try:
            d=json.load(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"research-script"}),timeout=90))
            if d.get("status")=="1" or d.get("message","").startswith("No records") or d.get("result")==[]: return d.get("result") or []
            last=d
        except Exception as e: last=e
        time.sleep(min(60,3*(k+1)**1.5))
    raise RuntimeError(f"{u} {last}")
def _int(v):
    if v in (None,"","0x"): return 0
    return int(v,16) if str(v).startswith("0x") else int(v)
def norm(l):
    g=lambda k,*alt: next((l[x] for x in (k,)+alt if x in l and l[x] not in (None,"")),None)
    ts=g("timeStamp","blockTimestamp")
    return dict(n=int(g("blockNumber"),16) if str(g("blockNumber")).startswith("0x") else int(g("blockNumber")),
                t=(int(ts,16) if str(ts).startswith("0x") else int(ts)) if ts is not None else None,
                i=_int(g("logIndex")),
                tx=g("transactionHash"),topics=[x for x in l["topics"] if x],data=l["data"])
def get_logs(ch,topics,frm,to,address=None):
    address=address or PM[ch]
    if ch in API:
        out=[];b=frm
        while b<=to:
            q=f"{API[ch]}?module=logs&action=getLogs&address={address}&fromBlock={b}&toBlock={to}"+("&page=1&offset=10000" if ch=="ethereum" else "")
            for k,t in enumerate(topics):
                if t: q+=f"&topic{k}={t}"
            ks=[k for k,t in enumerate(topics) if t]
            for a,c in zip(ks,ks[1:]): q+=f"&topic{a}_{c}_opr=and"
            r=[norm(x) for x in _get(q)]
            out+=r
            if len(r)<PAGE[ch]: break
            last=max(x["n"] for x in r); out=[x for x in out if x["n"]<last]; b=last   # ページの最後のブロックは取り直す
        return out
    out=[];b=frm;st=STEP[ch]
    while b<=to:
        e=min(b+st-1,to)
        r=rpc.call(ch,"eth_getLogs",[dict(address=address,topics=topics,fromBlock=hex(b),toBlock=hex(e))],tries=8)
        out+=[norm(x) for x in r]; b=e+1
    return out

def first_log(ch,topics,frm,to):
    """最初の 1 件だけ(ethereum は Routescan の offset=1、他は RPC を区間ごとに進めて最初に見つかった所で止める)。"""
    if ch in API:
        q=f"{API[ch]}?module=logs&action=getLogs&address={PM[ch]}&fromBlock={frm}&toBlock={to}&page=1&offset=1"
        ks=[k for k,t in enumerate(topics) if t]
        for k in ks: q+=f"&topic{k}={topics[k]}"
        for a,c in zip(ks,ks[1:]): q+=f"&topic{a}_{c}_opr=and"
        r=_get(q); return norm(r[0]) if r else None
    b=frm;st=STEP[ch]
    while b<=to:
        e=min(b+st-1,to); r=rpc.call(ch,"eth_getLogs",[dict(address=PM[ch],topics=topics,fromBlock=hex(b),toBlock=hex(e))],tries=8)
        if r: return norm(r[0])
        b=e+1
    return None
