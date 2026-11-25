import json,time,urllib.request
R="https://evm-rpc.devnet.lighterevm.axiom.xyz"; C="https://core-api.devnet.lighterevm.axiom.xyz/api/v1/currentHeight"
def rpc(m,p):
    r=urllib.request.Request(R,json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),{"content-type":"application/json"})
    return json.load(urllib.request.urlopen(r,timeout=10))["result"]
for i in range(90):
    try:
        t0=time.time(); core=json.load(urllib.request.urlopen(C,timeout=10))["height"]
        b=rpc("eth_getBlockByNumber",["latest",False]); t1=time.time()
        print(f"{t0:.1f} core_tip={core} evm={int(b['number'],16)} parent={int(b['extraData'],16)} lag={core-int(b['extraData'],16)} evm_age={t1-int(b['timestamp'],16):.1f} rtt={t1-t0:.2f}",flush=True)
    except Exception as e: print("err",e,flush=True)
    time.sleep(2)
