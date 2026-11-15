import json, urllib.request, sys
RPC="https://rpc.mainnet.chain.robinhood.com"
import time
def call(m,p):
    for i in range(10):
        try: return _call(m,p)
        except Exception: time.sleep(3*(i+1))
    raise RuntimeError
def _call(m,p):
    req=urllib.request.Request(RPC,json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),{"content-type":"application/json","user-agent":"research"})
    return json.loads(urllib.request.urlopen(req,timeout=60).read())["result"]
latest=int(call("eth_blockNumber",[]),16)
out={}
for b in list(range(1,latest,250000))+[latest]:
    out[b]=int(call("eth_getBlockByNumber",[hex(b),False])["timestamp"],16)
json.dump(out,open(sys.argv[1],"w"))
print(len(out))
