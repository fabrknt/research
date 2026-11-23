import json,sys; sys.path.insert(0,'.')
from analyze import *
e=json.load(open('cache/early_sets.json')); f=json.load(open('cache/farm_flags.json'))
shared=set(json.load(open('cache/farm_shared_eoa_wallets.json'))); fund=json.load(open('cache/farm_funding.json'))
hi=set(a for a,r in fund.items() if r['nonce']>=3000)
tiny=set(f['tiny']); burst=set(f['burst'])
A=[a for a in e['A_sample'][:2000] if a in look]
def line(nm,g):
    o=outcomes(g); n=len(g); pL=wilson(o['lE'],n); pV=wilson(o['vE'],n)
    print(f"{nm}: n={n} Lighter-early {o['lE']} {pL[0]:.1%} [{pL[1]:.1%},{pL[2]:.1%}]  Var-early {o['vE']} {pV[0]:.1%} [{pV[1]:.1%},{pV[2]:.1%}]")
    return o
line('A all looked-up',A)
fl=set(a for a in A if a in tiny or a in burst)
line('A flagged tiny-repeat or burst (full-cohort signals)',[a for a in A if a in fl])
line('A minus tiny/burst',[a for a in A if a not in fl])
S=[a for a in A if a in fund]
fs=set(a for a in S if a in tiny or a in burst or a in shared or a in hi)
line('A farmer-sample (looked-up part)',S)
line('  sample flagged any (tiny/burst/shared-EOA-funder/nonce>=3000)',[a for a in S if a in fs])
line('  sample unflagged',[a for a in S if a not in fs])
print('flag counts in sample:',{k:len([a for a in S if a in s]) for k,s in [('tiny',tiny),('burst',burst),('shared',shared),('nonce3000',hi)]})
