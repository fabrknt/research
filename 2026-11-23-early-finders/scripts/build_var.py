import sys,json,datetime; sys.path.insert(0,'.')
import bts
from collections import Counter
users={}; creators=Counter(); arrlen=Counter(); bad=0
for l in open('cache/var_pools.jsonl'):
    r=json.loads(l); d=r['d'][2:]
    W=[d[i:i+64] for i in range(0,len(d),64)]
    creator='0x'+r['t'][1][-40:]; creators[creator]+=1
    pool='0x'+W[1][-40:]
    off=int(W[0],16)//32; n=int(W[off],16); arrlen[n]+=1
    parties=['0x'+W[off+1+k][-40:] for k in range(n)]
    for u in parties:
        if u not in users or r['b']<users[u]['b']:
            users[u]={'b':r['b'],'ts':bts.ts(r['b']),'pool':pool,'creator':creator}
print(creators.most_common(5)); print(arrlen)
print('unique party addresses',len(users))
ts=sorted(u['ts'] for u in users.values())
for d in ['2025-03-01','2025-06-01','2025-09-01','2025-12-17','2026-03-01','2026-06-01','2026-11-01']:
    t=datetime.datetime.strptime(d,'%Y-%m-%d').replace(tzinfo=datetime.timezone.utc).timestamp()
    print(d,sum(x<t for x in ts))
json.dump(users,open('cache/var_users.json','w'))
