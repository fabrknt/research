import json,sys,math,collections,statistics
sys.path.insert(0,'.')
from analyze import wilson
m=json.load(open('ft/mapped.json')); H=json.load(open('ft/llama_hist.json')); AG=json.load(open('ft/age.json'))
c=json.load(open('ft/cohort_ft.json')); A=set(a[2:] for a in c['A']); L=set(a[2:] for a in c['L'])
nA,nL=len(A),len(L)
def succ(slug):
    h=H.get(slug) if slug else None
    if not h or 'err' in h: return False,False,None,None
    prim=h['peak']>=5e7 and (h['last'] or 0)>=1e6
    tok=bool(h.get('gecko_id')) or (h.get('symbol') not in (None,'-',''))
    return prim,tok,h['peak'],h['last']
units=collections.defaultdict(lambda:{'contracts':[],'early':0,'totA':0})
for a,v in m.items():
    if v.get('exclude'): continue
    key=v['protocol'] if v['protocol']!='unidentified' else 'unid:'+a[:10]
    u=units[key]; u['contracts'].append(a); u['early']=max(u['early'],v['early']); u['totA']=max(u['totA'],v['totA'])
    u.update({k:v.get(k) for k in ('slug','type','established')})
rows=[]
for k,u in units.items():
    prim,tok,peak,last=succ(u['slug'])
    # cohort share in first 500 senders, best contract
    best=None
    for a in u['contracts']:
        s=AG.get(a,{}).get('senders')
        if s:
            first500=[x for x,_ in sorted(s.items(),key=lambda t:t[1])[:500]]
            na=sum(1 for x in first500 if x in A); nl=sum(1 for x in first500 if x in L)
            r=(na,nl,len(first500))
            if best is None or r[0]>best[0]: best=r
    rows.append(dict(protocol=k,slug=u['slug'],type=u['type'],established=u['established'],early=u['early'],totA=u['totA'],prim=prim,tok=tok,peak=peak,last=last,w=best,n_contracts=len(u['contracts'])))
json.dump(rows,open('ft/units.json','w'),indent=0)
def rate(rs,key):
    k=sum(1 for r in rs if r[key]); n=len(rs); p,lo,hi=wilson(k,n); return f"{k}/{n} = {p:.0%} [{lo:.0%}-{hi:.0%}]"
for label,flt in [('ALL units',lambda r:True),('truly-new protocols only',lambda r:not r['established'])]:
    U=[r for r in rows if flt(r)]
    X=[r for r in U if r['early']>=5]; N=[r for r in U if r['early']<5]
    print(f"== {label}: units {len(U)}; crossers {len(X)}; non-crossers {len(N)}")
    print('  primary success: crossers',rate(X,'prim'),'| non-crossers',rate(N,'prim'),'| all',rate(U,'prim'))
    print('  token launched : crossers',rate(X,'tok'),'| non-crossers',rate(N,'tok'),'| all',rate(U,'tok'))
    for t in [10,20]:
        Y=[r for r in U if r['early']>=t]; print(f'  early>={t}:',rate(Y,'prim'),'token',rate(Y,'tok'))
    idt=[r for r in X if not r['protocol'].startswith('unid')]
    print('  crossers identified only: primary',rate(idt,'prim'),'token',rate(idt,'tok'))
print()
X=[r for r in rows if r['early']>=5]
for r in sorted(X,key=lambda r:-r['early']):
    w=r['w']; ws=f"A {w[0]}/{w[2]} ({w[0]/max(1,w[2]):.1%}), late {w[1]}/{w[2]}, rel.rep {((w[0]/nA)/max(1e-9,(w[1]/nL))) if w[1] else float('inf'):.1f}x" if w else 'n/a'
    print(f"{r['protocol'][:28]:28} {r['type']:18} est={str(r['established'])[0]} early={r['early']:3d} prim={str(r['prim'])[0]} tok={str(r['tok'])[0]} peak=${(r['peak'] or 0)/1e6:,.0f}M last=${(r['last'] or 0)/1e6:,.1f}M | {ws}")
# share vs success
ws=[(r['w'][0]/r['w'][2],r['prim']) for r in X if r['w'] and r['w'][2]]
s1=[x for x,p in ws if p]; s0=[x for x,p in ws if not p]
print('\ncohort share in first 500: success median',statistics.median(s1) if s1 else None,'n',len(s1),'| failure median',statistics.median(s0) if s0 else None,'n',len(s0))
er=[(r['early'],r['prim']) for r in X]
print('early count: success median',statistics.median([e for e,p in er if p]) if any(p for e,p in er) else None,'failure median',statistics.median([e for e,p in er if not p]))
tc=collections.Counter(r['type'] for r in X); ts=collections.Counter(r['type'] for r in X if r['prim'])
print('crosser types',tc.most_common(),'successes by type',ts.most_common())
perp=[r for r in X if 'perp' in (r['type'] or '')]; nonp=[r for r in X if 'perp' not in (r['type'] or '')]
print('perp-like crossers',rate(perp,'prim'),'token',rate(perp,'tok'),'| non-perp crossers',rate(nonp,'prim'),'token',rate(nonp,'tok'))
