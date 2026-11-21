"""公開 RPC の薄い道具(鍵なし)。"""
import json,urllib.request,time,sys
RPC={"ethereum":["https://rpc.mevblocker.io","https://rpc.flashbots.net","https://ethereum-rpc.publicnode.com"],
     "base":["https://gateway.tenderly.co/public/base","https://base.gateway.tenderly.co"],
     "arbitrum":["https://arb1.arbitrum.io/rpc","https://arb1.arbitrum.io/rpc"],
     "unichain":["https://gateway.tenderly.co/public/unichain","https://mainnet.unichain.org"]}
def call(ch,method,params,i=0,tries=6):
    last=None
    for k in range(tries):
        url=RPC[ch][(i+k)%len(RPC[ch])]
        try:
            r=json.load(urllib.request.urlopen(urllib.request.Request(url,data=json.dumps(dict(jsonrpc="2.0",id=1,method=method,params=params)).encode(),
                headers={"content-type":"application/json","User-Agent":"research-script"}),timeout=60))
            if "error" in r: last=r["error"]; 
            else: return r["result"]
        except Exception as e: last=e
        time.sleep(1+k)
    raise RuntimeError(f"{ch} {method} {last}")
def bn(ch): return int(call(ch,"eth_blockNumber",[]),16)
def code_at(ch,a,b): return call(ch,"eth_getCode",[a,hex(b)])
def deploy_block(ch,a):
    lo,hi=0,bn(ch)
    if code_at(ch,a,hi) in ("0x",""): return None
    while lo<hi:
        m=(lo+hi)//2
        if code_at(ch,a,m) in ("0x",""): lo=m+1
        else: hi=m
    return lo
def logs(ch,addr,topics,frm,to,step=50000):
    out=[];b=frm
    while b<=to:
        e=min(b+step-1,to)
        try: r=call(ch,"eth_getLogs",[dict(address=addr,topics=topics,fromBlock=hex(b),toBlock=hex(e))])
        except RuntimeError as ex:
            if step>500: step//=4; continue
            raise
        out+=r; b=e+1
    return out
BATCH={"ethereum":"https://ethereum-rpc.publicnode.com","unichain":"https://gateway.tenderly.co/public/unichain","base":"https://gateway.tenderly.co/public/base","arbitrum":"https://arb1.arbitrum.io/rpc"}
def batch(ch,method,plist,size=None):
    size=size or (10 if "tenderly" in BATCH[ch] else 50)
    """JSON-RPC の batch。取れなかったものは None。"""
    out=[None]*len(plist)
    for s in range(0,len(plist),size):
        req=[dict(jsonrpc="2.0",id=s+k,method=method,params=p) for k,p in enumerate(plist[s:s+size])]
        for k in range(6):
            try:
                r=json.load(urllib.request.urlopen(urllib.request.Request(BATCH[ch],data=json.dumps(req).encode(),
                    headers={"content-type":"application/json","User-Agent":"research-script"}),timeout=90))
                if isinstance(r,dict): raise RuntimeError(r)
                for x in r:
                    if "result" in x: out[x["id"]]=x["result"]
                break
            except Exception as e: time.sleep(2+3*k)
    return out
