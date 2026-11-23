import sys,json,random,time,os; sys.path.insert(0,'.')
from rpc import *
from analyze import *
e=json.load(open('cache/early_sets.json')); lc=json.load(open('cache/late_cand.json'))
A=[a for a in e['A100_all'] if a in var and var[a]['ts']<V_POINTS]
Lt=[a for a,x in lc.items() if x['amt']>=100 and a in var and var[a]['ts']<V_POINTS]
random.seed(4); S_=random.sample(A,150)+random.sample(Lt,150)
F='cache/var_verify.json'; res=json.load(open(F)) if os.path.exists(F) else {}
for i,a in enumerate(S_):
    if a in res: continue
    b=var[a]['b']; pool=var[a]['pool']
    def gl(t1,t2):
        for span in [1500000,500000,150000,50000]:
            try: return call('arb','eth_getLogs',[{'address':'0xaf88d065e77c8cC2239327C5EDb3A432268e5831','topics':[TRANSFER,t1,t2],'fromBlock':hex(b-20000),'toBlock':hex(b+span)}])
            except Exception: pass
        return []
    l=gl(pad(a),None)
    outs=[('0x'+x['topics'][2][-40:],int(x['data'],16)/1e6,int(x['blockNumber'],16)) for x in l]
    l2=gl(None,pad(pool))
    ins=[('0x'+x['topics'][1][-40:],int(x['data'],16)/1e6) for x in l2]
    res[a]={'grp':'A' if a in A else 'late','outs':outs[:30],'pool_in':ins[:30]}
    if i%25==0: json.dump(res,open(F,'w')); print(i,flush=True)
    time.sleep(0.2)
json.dump(res,open(F,'w'))
