import json,sys,collections,statistics; sys.path.insert(0,'.')
from analyze import *
e=json.load(open('cache/early_sets.json')); A=set(e['A100_all'])
w=json.load(open('cache/hl_wallets_to_may2024.json'))
# local signals on all A
tiny=set(a for a in A if sum(1 for x in w[a]['amts'] if x<50)>=3)
# burst: same first-deposit amount (rounded to $1) within same 1h bucket, >=5 wallets
hf=json.load(open('cache/hl_first.json'))
buck=collections.defaultdict(list)
for a in A:
    buck[(round(hf['amt100'][a]),int(hf['first100'][a]//3600))].append(a)
burst=set(a for k,v in buck.items() if len(v)>=4 for a in v)
print('A total',len(A),'tiny-repeat',len(tiny),'burst-cluster',len(burst))
fund=json.load(open('cache/farm_funding.json'))
src_count=collections.Counter()
for a,r in fund.items():
    for s in set(x[0] for x in r['srcs']): src_count[s]+=1
shared=set(a for a,r in fund.items() if any(src_count[x[0]]>=2 for x in r['srcs']))
nonces=[r['nonce'] for r in fund.values()]
hi=set(a for a,r in fund.items() if r['nonce']>=3000)
print('funding sample',len(fund),'with any USDC inflow found',sum(1 for r in fund.values() if r['srcs']),'shared-source(>=2 in sample)',len(shared),'top sources',src_count.most_common(8))
print('nonce median',statistics.median(nonces),'p90',sorted(nonces)[int(.9*len(nonces))],'>=3000',len(hi))
json.dump({'tiny':sorted(tiny),'burst':sorted(burst),'shared_sample':sorted(shared),'hi_nonce_sample':sorted(hi),'src_top':src_count.most_common(30)},open('cache/farm_flags.json','w'))
