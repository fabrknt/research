import json,sys,datetime; sys.path.insert(0,'.')
from analyze import *
e=json.load(open('cache/early_sets.json'))
A=[a for a in e['A_sample'][:2000] if a in look]
f=lambda t: datetime.datetime.utcfromtimestamp(t).strftime('%Y-%m-%d')
lt=sorted(time_of_idx(look[a]['main_idx']) for a in A if look[a].get('found') and time_of_idx(look[a]['main_idx']))
print('Lighter: A-tested n=',len(A),'; date when k cohort wallets had joined:',{k:f(lt[k-1]) for k in [1,5,10,25,50,100,200] if len(lt)>=k})
# total Lighter accounts at those dates (index envelope)
print('   Lighter total accounts by then:',{k:idx_at(lt[k-1]) for k in [5,10,25,50,100] if len(lt)>=k})
for nm,g in [('A full 6385',e['A100_all'])]:
    vt=sorted(var[a]['ts'] for a in g if a in var)
    tot=sorted(u['ts'] for u in var.values())
    import bisect
    print('Variational',nm,{k:(f(vt[k-1]),bisect.bisect_right(tot,vt[k-1])) for k in [1,5,10,25,50,100,200,500] if len(vt)>=k})
    # share of all Omni users that are early-HL, by period
    for d in ['2025-06-01','2025-09-01','2025-12-17','2026-11-11']:
        T=D(d); print('  by',d,'early-HL',sum(x<T for x in vt),'of all Omni',bisect.bisect_right(tot,T))
