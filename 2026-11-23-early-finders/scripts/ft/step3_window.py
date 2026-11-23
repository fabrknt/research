import json,sys,os,time,bisect,datetime
sys.path.insert(0,'.')
from rpc import *
import bts
TOK=['0xaf88d065e77c8cC2239327C5EDb3A432268e5831','0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8','0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9','0x82aF49447D8a07e3bd95BD0d56f35241523fBab1']
def blk_at(ts):
    i=bisect.bisect_left([a[1] for a in bts.A],ts); i=max(1,min(i,len(bts.A)-1))
    (b0,t0),(b1,t1)=bts.A[i-1],bts.A[i]; return int(b0+(ts-t0)*(b1-b0)/(t1-t0))
AUG1=blk_at(datetime.datetime(2023,8,1,tzinfo=datetime.timezone.utc).timestamp())
NITRO=22207818
def q(addr,fr,to,toks=TOK):
    out=[]
    for t in toks:
        out+=call('arb','eth_getLogs',[{'address':t,'topics':[TRANSFER,None,pad(addr)],'fromBlock':hex(fr),'toBlock':hex(to)}])
    return out
FEB23=58000000; JUN23=100000000
def any_before(addr,end):
    s=FEB23
    while s<end:
        e=min(end,s+10000000-1)
        toks=[TOK[1]]+([TOK[0]] if e>=JUN23 else [])
        try: l=q(addr,s,e,toks)
        except RuntimeError as ex:
            if 'exceeds limit' in str(ex) or 'timed out' in str(ex): return True
            raise
        if l: return True
        s=e+1
    return False
def first_inflow(addr,start,end):
    s=start; span=10000000
    while s<end:
        e=min(end,s+span-1)
        try: l=q(addr,s,e)
        except RuntimeError: span=max(1000,span//4); continue
        if l:
            if span<=200000 or len(l)<5000: return min(int(x['blockNumber'],16) for x in l)
            span=max(1000,span//10); continue
        s=e+1
    return None
def window(addr,fb,maxsenders=500):
    end=blk_at(bts.ts(fb)+60*86400); s=fb; span=2000000; seen={}
    while s<=end and len(seen)<maxsenders:
        e=min(end,s+span-1)
        try: l=q(addr,s,e)
        except RuntimeError: span=max(500,span//4); continue
        for x in sorted(l,key=lambda x:(int(x['blockNumber'],16),int(x['logIndex'],16))):
            fr=x['topics'][1][-40:]
            if fr not in seen: seen[fr]=int(x['blockNumber'],16)
        s=e+1
        if len(l)<3000: span=min(10000000,span*2)
    return seen,end
DEP=json.load(open('ft/deploy.json'))
cands=json.load(open(sys.argv[1])); MODE=sys.argv[2] if len(sys.argv)>2 else 'first'
F='ft/windows.json'; R=json.load(open(F)) if os.path.exists(F) else {}
for a in cands:
    if a in R and (MODE!='window' or 'senders' in R[a] or R[a].get('old') or R[a].get('eoa')): continue
    if a in R and MODE=='window' and R[a].get('first'):
        seen,end=window(a,R[a]['first']); R[a]['senders']=seen; json.dump(R,open(F,'w')); print(a,'win',len(seen),flush=True); continue
    try:
        code=call('arb','eth_getCode',[a,'latest'])
        if code=='0x' or code.startswith('0xef0100'): R[a]={'eoa':True}
        elif (DEP.get(a) is not None and DEP[a]<AUG1) or (DEP.get(a) is None and any_before(a,AUG1)): R[a]={'old':True}
        else:
            fb=first_inflow(a,max(AUG1,DEP.get(a) or 0),352944240+30000000)
            if fb is None: R[a]={'old':False,'first':None}
            else:
                R[a]={'old':False,'first':fb,'first_ts':bts.ts(fb)}
                if MODE=='window':
                    seen,end=window(a,fb); R[a]['senders']=seen
    except Exception as ex: R[a]={'err':str(ex)[:200]}
    json.dump(R,open(F,'w')); print(a,{k:(v if k!='senders' else len(v)) for k,v in R[a].items()},flush=True)
print('DONE',flush=True)
