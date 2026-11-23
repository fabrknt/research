import sys,json,datetime; sys.path.insert(0,'.')
import bts
from collections import defaultdict
def load(f,tok):
    for l in open(f):
        r=json.loads(l); yield {'addr':'0x'+r['t'][1][-40:],'b':r['b'],'ts':bts.ts(r['b']),'amt':int(r['d'],16)/1e6,'tx':r['tx'],'route':tok}
dep=list(load('cache/old_usdce.jsonl','old_bridge_usdce'))+list(load('cache/b2_s1.jsonl','bridge2_usdc'))
by=defaultdict(list)
for d in dep: by[d['addr']].append(d)
NOV1=datetime.datetime(2023,11,1,tzinfo=datetime.timezone.utc).timestamp()
MAY1=datetime.datetime(2024,5,1,tzinfo=datetime.timezone.utc).timestamp()
w={}
for a,ds in by.items():
    ds.sort(key=lambda d:d['b'])
    w[a]={'first_ts':ds[0]['ts'],'first_amt':ds[0]['amt'],'first_tx':ds[0]['tx'],'first_route':ds[0]['route'],'n_dep':len(ds),'max_amt':max(d['amt'] for d in ds),'sum_amt':sum(d['amt'] for d in ds),'amts':[round(d['amt'],2) for d in ds[:50]]}
json.dump(w,open('cache/hl_wallets_to_may2024.json','w'))
A=[a for a,x in w.items() if x['first_ts']<NOV1]
B=[a for a,x in w.items() if NOV1<=x['first_ts']<MAY1]
print('wallets with first deposit pre-Nov1-2023:',len(A),' Nov1-2023..May1-2024:',len(B))
# dust filter: total deposited (in window up to May 2024) >= 100
for nm,L in [('A',A),('B',B)]:
    keep=[a for a in L if w[a]['max_amt']>=100]
    print(nm,'max single deposit>=100:',len(keep),'removed',len(L)-len(keep))
