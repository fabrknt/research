# Q1: replay every swap under fee / liquidity rules that use only what the pool knows at the time.
# Each swap keeps its size and price (no path effects). An extra fee f (fraction of the TYD leg) goes to LPs.
# Response models:
#   static   : every swap still happens and pays f (upper bound on what the fee recovers)
#   walk(e)  : a swap that made money at the outcome happens only if its edge (P&L/volume) > f, else it is
#              not made; a swap that lost money (noise) happens with probability exp(-e*f), e = elasticity
#              (e=3: a 10% fee keeps 74% of noise volume; e=10 keeps 37%). Edge is measured after the fact,
#              so this treats informed traders as knowing their realized edge - an assumption, not data.
# "pull" rules remove the swap entirely (no LP liquidity to trade against).
import json,math,collections
R=json.load(open('data/trades.json'))
def run(rows,rule,model,e=0.0):
    loss=vol=fee=0.0
    for r in rows:
        a=rule(r)
        if a=='pull': continue
        sc=1.0
        if isinstance(a,tuple): sc,a=a[1],0.0   # ('scale',k): liquidity scaled by k; swap size and P&L scale with it
        f=a or 0.0; p,v=r['pnl']*sc,r['vol']*sc
        if model=='static' or f==0: k=1.0
        elif p>0: k=1.0 if p/v>f else 0.0
        else: k=math.exp(-e*f)
        loss+=k*(p-f*v); vol+=k*v; fee+=k*f*v
    return loss,vol,fee
toward=lambda r: abs(r['post']-.5)>abs(r['pre']-.5)
RULES=collections.OrderedDict()
RULES['baseline']=lambda r:0
for f in (.01,.02,.05,.10,.20): RULES[f'flat fee {f:.0%}']=(lambda f: lambda r:f)(f)
RULES['close at endOfTrading']=lambda r:'pull' if r['hT']<0 else 0
for h in (6,24,72): RULES[f'pull last {h}h before endOfTrading + close']=(lambda h: lambda r:'pull' if r['hT']<h else 0)(h)
for h,f in ((24,.05),(24,.10),(72,.05),(72,.10)): RULES[f'fee {f:.0%} in last {h}h + close']=(lambda h,f: lambda r:'pull' if r['hT']<0 else (f if r['hT']<h else 0))(h,f)
for n in ('mv6','mv24'):
    for k in (0.5,1,2): RULES[f'fee = {k}x|move {n[2:]}h| (cap 50%)']=(lambda n,k: lambda r:min(.5,k*abs(r[n])))(n,k)
for lo in (.05,.1,.2): RULES[f'pull outside [{lo},{1-lo:.2f}]']=(lambda lo: lambda r:'pull' if not lo<=r['pre']<=1-lo else 0)(lo)
for f in (.02,.05,.10,.20): RULES[f'fee {f:.0%} on swaps toward 0/1']=(lambda f: lambda r:f if toward(r) else 0)(f)
RULES['combo: close at T + pull outside [0.1,0.9] + 5% toward 0/1']=lambda r:'pull' if r['hT']<0 or not .1<=r['pre']<=.9 else (.05 if toward(r) else 0)
RULES['combo: close at T + pull outside [0.1,0.9] + 10% toward 0/1']=lambda r:'pull' if r['hT']<0 or not .1<=r['pre']<=.9 else (.10 if toward(r) else 0)
# dynamic pm-AMM (Paradigm, 2024): liquidity ~ sqrt(time left). Here: k = sqrt(hours to endOfTrading / hours from the
# market's first swap to endOfTrading), closed after endOfTrading. Swap size and P&L scale with k (crude).
first={}
for r in R: first[r['market']]=min(first.get(r['market'],1e18),r['t'])
def pmamm(r):
    if r['hT']<0: return 'pull'
    life=r['hT']+(r['t']-first[r['market']])/3600
    return ('scale',(r['hT']/life)**.5 if life>0 else 1.0)
RULES['dynamic pm-AMM style: liquidity x sqrt(time left), close at T']=pmamm
RULES['oracle (not ex ante): drop every swap that made money']=lambda r:'pull' if r['pnl']>0 else 0
B=run(R,RULES['baseline'],'static')
out=[]
def P(s): print(s); out.append(s)
P(f"baseline LP loss {B[0]:,.0f} on volume {B[1]:,.0f}")
P("loss cut = 1 - new loss / baseline loss; vol kept = new volume / baseline volume; fee = extra fee paid to LPs ($)")
P(f"| rule | static: loss cut / vol kept | walk e=0 | walk e=3 | walk e=10 | fee $ (e=3) |")
P("|---|---|---|---|---|---|")
res={}
for name,rule in RULES.items():
    cells=[]
    for model,e in (('static',0),('walk',0),('walk',3),('walk',10)):
        l,v,f=run(R,rule,model,e); cells.append(f"{1-l/B[0]:+.0%} / {v/B[1]:.0%}"); res[(name,model,e)]=(l,v,f)
    P(f"| {name} | "+" | ".join(cells)+f" | {res[(name,'walk',3)][2]:,.0f} |")
# out of sample: pick each family's best parameter on the first half of markets (walk e=3), report the second half
bym=collections.defaultdict(list)
for r in R: bym[r['market']].append(r)
order=sorted(bym,key=lambda m:min(r['t'] for r in bym[m])); tr=set(order[:len(order)//2])
TR=[r for r in R if r['market'] in tr]; TE=[r for r in R if r['market'] not in tr]
fam=collections.defaultdict(list)
for name in RULES:
    if name.startswith(('baseline','oracle','combo')): continue
    key=name.split(' ')[0]+(' '+name.split(' ')[-1] if 'toward' in name else '')
    key={'flat':'flat fee','close':'close at T','pull':'pull (time or band)','fee':'fee (time/move/direction)'}.get(name.split(' ')[0],name)
    if 'toward' in name: key='directional fee'
    elif 'move' in name: key='move fee'
    elif 'last' in name and name.startswith('fee'): key='time fee'
    elif 'outside' in name: key='price band pull'
    elif 'before endOfTrading' in name: key='time pull'
    fam[key].append(name)
fam['combo']=[n for n in RULES if n.startswith('combo')]
bTR=run(TR,RULES['baseline'],'static'); bTE=run(TE,RULES['baseline'],'static')
P(f"\nOut of sample: train = first {len(tr)} markets by first swap (loss {bTR[0]:,.0f}), test = other {len(order)-len(tr)} (loss {bTE[0]:,.0f}); chosen on train by loss cut under walk e=3")
P("| family | chosen on train | train loss cut / vol kept | test loss cut / vol kept |"); P("|---|---|---|---|")
for k,names in fam.items():
    best=min(names,key=lambda n:run(TR,RULES[n],'walk',3)[0])
    a=run(TR,RULES[best],'walk',3); b=run(TE,RULES[best],'walk',3)
    P(f"| {k} | {best} | {1-a[0]/bTR[0]:+.0%} / {a[1]/bTR[1]:.0%} | {1-b[0]/bTE[0]:+.0%} / {b[1]/bTE[1]:.0%} |")
# what is left: the fee alone needed to break even, per model
P("\nFlat extra fee at which LPs break even (loss <= 0):")
for model,e in (('static',0),('walk',0),('walk',3),('walk',10)):
    be=next((f/1000 for f in range(0,1001) if run(R,lambda r,f=f/1000:f,model,e)[0]<=0),None)
    P(f"  {model} e={e}: {be if be is None else f'{be:.1%}'}"+("" if be is None else f", volume kept {run(R,lambda r:be,model,e)[1]/B[1]:.0%}"))
open('results/sim.txt','w').write('\n'.join(out)+'\n')
