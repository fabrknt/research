import sys,json,random,time,os; sys.path.insert(0,'.')
from rpc import *
e=json.load(open('cache/early_sets.json'))
random.seed(21); samp=random.sample(e['A_sample'],400)
# first >=100 deposit block per wallet
fb={}
for f in ['cache/old_usdce.jsonl','cache/b2_s1.jsonl']:
    for l in open(f):
        r=json.loads(l); a='0x'+r['t'][1][-40:]
        if a in samp and (a not in fb or r['b']<fb[a]): fb[a]=r['b']
F='cache/farm_funding.json'
res=json.load(open(F)) if os.path.exists(F) else {}
for i,a in enumerate(samp):
    if a in res: continue
    b=fb[a]; srcs=[]
    for tok in ['0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8','0xaf88d065e77c8cC2239327C5EDb3A432268e5831']:
        lo=max(0,b-4000000)
        try: l=call('arb','eth_getLogs',[{'address':tok,'topics':[TRANSFER,None,pad(a)],'fromBlock':hex(lo),'toBlock':hex(b)}])
        except Exception as ex: l=[]
        srcs+=[('0x'+x['topics'][1][-40:],int(x['data'],16)/1e6,int(x['blockNumber'],16)) for x in l]
    nonce=int(call('arb','eth_getTransactionCount',[a,'latest']),16)
    res[a]={'srcs':srcs,'nonce':nonce,'first_b':b}
    if i%25==0: json.dump(res,open(F,'w')); print(i,flush=True)
    time.sleep(0.2)
json.dump(res,open(F,'w'))
