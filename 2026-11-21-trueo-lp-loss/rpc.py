import json, subprocess, time, sys
RPC="https://base-rpc.publicnode.com"
class RpcErr(Exception): pass
def call(method, params, tries=12):
    body=json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params})
    last=None
    for t in range(tries):
        p=subprocess.run(["curl","-s","-m","90","-X","POST",RPC,"-H","Content-Type: application/json","--data-binary","@-","-w","\n%{http_code}"],input=body,capture_output=True,text=True)
        txt,_,code=p.stdout.rpartition("\n")
        if code=="429" or code.startswith("5") or code=="000": last=code; time.sleep(3*(t+1)); continue
        try: r=json.loads(txt)
        except Exception: last=(code,txt[:200]); time.sleep(2); continue
        if 'error' in r: raise RpcErr(r['error'])
        return r['result']
    raise Exception(f"rpc fail {last}")
def logs(addr=None, topics=None, frm=0, to=None, step=2_000_000):
    to=to or int(call("eth_blockNumber",[]),16)
    out=[]; b=frm
    while b<=to:
        e=min(b+step-1,to)
        f={"fromBlock":hex(b),"toBlock":hex(e)}
        if addr: f["address"]=addr
        if topics: f["topics"]=topics
        try:
            out+=call("eth_getLogs",[f]); b=e+1
        except RpcErr as ex:
            print("shrink",step,str(ex)[:120],file=sys.stderr)
            if step<=500: raise
            step//=4
    return out

from concurrent.futures import ThreadPoolExecutor
def plogs(addr, topics, frm, to=None, step=50_000, workers=6):
    to=to or int(call("eth_blockNumber",[]),16)
    rngs=[(b,min(b+step-1,to)) for b in range(frm,to+1,step)]
    def one(r):
        f={"fromBlock":hex(r[0]),"toBlock":hex(r[1])}
        if addr: f["address"]=addr
        if topics: f["topics"]=topics
        try: return call("eth_getLogs",[f])
        except RpcErr as e:
            m=(r[0]+r[1])//2
            if r[1]-r[0]<100: raise
            return one((r[0],m))+one((m+1,r[1]))
    with ThreadPoolExecutor(workers) as ex:
        res=list(ex.map(one,rngs))
    return [l for x in res for l in x]
