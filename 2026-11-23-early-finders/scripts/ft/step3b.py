import json,sys,os,time,bisect,datetime
sys.path.insert(0,'.')
from rpc import *
import bts
TOK=['0xaf88d065e77c8cC2239327C5EDb3A432268e5831','0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8','0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9','0x82aF49447D8a07e3bd95BD0d56f35241523fBab1']
def blk_at(ts):
    i=bisect.bisect_left([a[1] for a in bts.A],ts); i=max(1,min(i,len(bts.A)-1))
    (b0,t0),(b1,t1)=bts.A[i-1],bts.A[i]; return int(b0+(ts-t0)*(b1-b0)/(t1-t0))
NITRO=22207818; HEAD=int(call('arb','eth_blockNumber',[]),16)
def first_own_log(a):
    s=58000000; span=10000000
    while s<295000000:
        e=min(HEAD,s+span-1)
        try: l=call('arb','eth_getLogs',[{'address':a,'fromBlock':hex(s),'toBlock':hex(e)}])
        except RuntimeError as ex:
            if span<=20000: return s
            span//=4; continue
        if l: return min(int(x['blockNumber'],16) for x in l)
        s=e+1
        if s<145877584 and span<10000000: span=10000000
    return None
def window(a,fb,maxs=500):
    end=blk_at(bts.ts(fb)+60*86400); s=fb; span=500000; seen={}
    while s<=end and len(seen)<maxs:
        e=min(end,s+span-1); logs=[]; ok=True
        for t in TOK:
            try: logs+=call('arb','eth_getLogs',[{'address':t,'topics':[TRANSFER,None,pad(a)],'fromBlock':hex(s),'toBlock':hex(e)}])
            except RuntimeError: ok=False; break
        if not ok: span=max(2000,span//4); continue
        for x in sorted(logs,key=lambda x:(int(x['blockNumber'],16),int(x['logIndex'],16))):
            fr=x['topics'][1][-40:]
            if fr not in seen: seen[fr]=int(x['blockNumber'],16)
        s=e+1
        if len(logs)<2000: span=min(4000000,span*2)
    return seen
mode=sys.argv[2]; cands=json.load(open(sys.argv[1])); BIRTH=json.load(open('ft/deploy.json'))
F='ft/age.json'; R=json.load(open(F)) if os.path.exists(F) else {}
for a in cands:
    r=R.get(a,{})
    try:
        if 'kind' not in r:
            code=call('arb','eth_getCode',[a,'latest'])
            r['kind']='eoa' if code=='0x' or code.startswith('0xef0100') else 'contract'
        if r['kind']=='contract' and 'first_log' not in r and not BIRTH.get(a):
            r['first_log']=first_own_log(a)
        b0=BIRTH.get(a) or r.get('first_log')
        if mode=='window' and b0 and 'senders' not in r:
            r['senders']=window(a,b0)
    except Exception as ex: r['err']=str(ex)[:150]
    R[a]=r; json.dump(R,open(F,'w')); print(a,{k:(v if k!='senders' else len(v)) for k,v in r.items()},flush=True)
print('DONE',flush=True)
