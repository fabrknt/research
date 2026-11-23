import sys,json,os,time; sys.path.insert(0,'.')
from rpc import *
F='cache/is_contract.json'
res=json.load(open(F)) if os.path.exists(F) else {}
addrs=[a for a in json.load(open(sys.argv[1])) if a not in res]
for i in range(0,len(addrs),20):
    ch=addrs[i:i+20]
    for k in range(10):
        try:
            r=S.post(URLS['arb'],json=[{'jsonrpc':'2.0','id':j,'method':'eth_getCode','params':[a,'latest']} for j,a in enumerate(ch)],timeout=60).json()
            if isinstance(r,list) and all('result' in x for x in r): break
        except Exception: pass
        time.sleep(3+k)
    else: continue
    for x in r: c=x['result']; res[ch[x['id']]]=('eoa' if c=='0x' else ('7702' if c.startswith('0xef0100') else 'contract'))
    if i%400==0: json.dump(res,open(F,'w')); print(i,len(addrs),flush=True)
    time.sleep(0.8)
json.dump(res,open(F,'w'))
