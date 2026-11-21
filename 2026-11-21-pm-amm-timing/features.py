# Q2: which ex-ante information predicts LP loss? Per-swap buckets (loss/volume = the swapper's edge at the
# outcome), Spearman correlations, the same per market, and an out-of-sample check (fit buckets on the
# markets that ended first, test on the rest).
import json,collections,statistics
R=json.load(open('data/trades.json'))
def rank(x):
    o=sorted(range(len(x)),key=lambda i:x[i]); r=[0]*len(x); i=0
    while i<len(o):
        j=i
        while j+1<len(o) and x[o[j+1]]==x[o[i]]: j+=1
        for k in range(i,j+1): r[o[k]]=(i+j)/2
        i=j+1
    return r
def sp(a,b):
    ra,rb=rank(a),rank(b); ma,mb=statistics.fmean(ra),statistics.fmean(rb)
    num=sum((x-ma)*(y-mb) for x,y in zip(ra,rb)); den=(sum((x-ma)**2 for x in ra)*sum((y-mb)**2 for y in rb))**.5
    return num/den if den else float('nan')
TOT=sum(r['pnl'] for r in R); VOL=sum(r['vol'] for r in R)
F={
 'hours to resolution proposed': (lambda r:r['hR'], [(-1e9,0,'after'),(0,6,'0-6h'),(6,24,'6-24h'),(24,72,'1-3d'),(72,168,'3-7d'),(168,1e9,'>7d')]),
 'hours to endOfTrading':        (lambda r:r['hT'], [(-1e9,0,'after'),(0,6,'0-6h'),(6,24,'6-24h'),(24,72,'1-3d'),(72,168,'3-7d'),(168,1e9,'>7d')]),
 'price before swap':            (lambda r:r['pre'],[(0,.05,'<.05'),(.05,.1,'.05-.1'),(.1,.3,'.1-.3'),(.3,.7,'.3-.7'),(.7,.9,'.7-.9'),(.9,.95,'.9-.95'),(.95,9,'>.95')]),
 '|move| last 6h':               (lambda r:abs(r['mv6']),[(0,.005,'<.5pt'),(.005,.05,'.5-5pt'),(.05,.15,'5-15pt'),(.15,9,'>15pt')]),
 '|move| last 24h':              (lambda r:abs(r['mv24']),[(0,.005,'<.5pt'),(.005,.05,'.5-5pt'),(.05,.15,'5-15pt'),(.15,9,'>15pt')]),
 'swap size (TYD)':              (lambda r:r['vol'],[(0,10,'<10'),(10,100,'10-100'),(100,500,'100-500'),(500,1e12,'>500')]),
 'hours since pool last traded': (lambda r:r['gap'] if r['gap'] is not None else 1e6,[(0,.1,'<6min'),(.1,1,'6min-1h'),(1,24,'1-24h'),(24,1e12,'>24h')]),
 'price impact |post-pre|':      (lambda r:abs(r['post']-r['pre']),[(0,.005,'<.5pt'),(.005,.03,'.5-3pt'),(.03,.1,'3-10pt'),(.1,9,'>10pt')]),
}
out=[]
def P(*a): s=' '.join(str(x) for x in a); print(s); out.append(s)
P(f"swaps {len(R)}, LP loss {TOT:,.0f}, volume {VOL:,.0f}, loss/volume {TOT/VOL:.3f}")
P("\n## Per swap, by bucket: share of swaps, of volume, of LP loss; loss/volume")
for name,(f,bk) in F.items():
    P(f"\n{name}"); P(f"{'bucket':>10} {'swaps':>6} {'vol%':>6} {'loss%':>6} {'loss/vol':>8}")
    for lo,hi,lab in bk:
        g=[r for r in R if lo<=f(r)<hi]; v=sum(r['vol'] for r in g); l=sum(r['pnl'] for r in g)
        P(f"{lab:>10} {len(g):6d} {v/VOL*100:6.1f} {l/TOT*100:6.1f} {l/v if v else float('nan'):8.3f}")
P("\nmarket type"); P(f"{'kind':>13} {'mkts':>4} {'swaps':>6} {'vol%':>6} {'loss%':>6} {'loss/vol':>8}")
for k in sorted({r['kind'] for r in R}):
    g=[r for r in R if r['kind']==k]; v=sum(r['vol'] for r in g); l=sum(r['pnl'] for r in g)
    P(f"{k:>13} {len({r['market'] for r in g}):4d} {len(g):6d} {v/VOL*100:6.1f} {l/TOT*100:6.1f} {l/v:8.3f}")
P("\nswap direction (ex ante: buying vs selling the outcome token; toward 0/1 = post price farther from 0.5 than pre)")
for lab,f in [('buy',lambda r:r['buy']),('sell',lambda r:not r['buy']),('toward 0/1',lambda r:abs(r['post']-.5)>abs(r['pre']-.5)),('toward 0.5',lambda r:abs(r['post']-.5)<=abs(r['pre']-.5))]:
    g=[r for r in R if f(r)]; v=sum(r['vol'] for r in g); l=sum(r['pnl'] for r in g)
    P(f"{lab:>12} swaps {len(g):5d} vol% {v/VOL*100:5.1f} loss% {l/TOT*100:6.1f} loss/vol {l/v:.3f}")
P("\n## Spearman rank correlation with the swap's edge (loss/volume), volume-unweighted, n=%d"%len(R))
edge=[r['pnl']/r['vol'] if r['vol'] else 0 for r in R]
for name,(f,_) in F.items(): P(f"{name:32s} {sp([f(r) for r in R],edge):+.3f}")
P(f"{'distance from 0/1 min(p,1-p)':32s} {sp([min(r['pre'],1-r['pre']) for r in R],edge):+.3f}")
P(f"{'signed move 24h x direction':32s} {sp([r['mv24']*(1 if r['buy'] else -1) for r in R],edge):+.3f}  (+ = trading with the recent move)")
# per market
bym=collections.defaultdict(list)
for r in R: bym[r['market']].append(r)
mf=[]
for m,g in bym.items():
    v=sum(r['vol'] for r in g); l=sum(r['pnl'] for r in g); g.sort(key=lambda r:r['t'])
    life=(g[-1]['t']-g[0]['t'])/3600
    vw=lambda f: sum(f(r)*r['vol'] for r in g)/v if v else 0
    mf.append(dict(loss=l,vol=v,lv=l/v if v else 0,life=life,n=len(g),
       dist=vw(lambda r:min(r['pre'],1-r['pre'])),mv=vw(lambda r:abs(r['mv24'])),hR=vw(lambda r:r['hR']),kind=g[0]['kind']))
P("\n## Per market (n=%d): Spearman with market loss/volume and with loss in $"%len(mf))
for k,lab in [('vol','volume'),('n','swaps'),('life','first-to-last swap hours'),('dist','vol-wtd distance from 0/1'),('mv','vol-wtd |move 24h|'),('hR','vol-wtd hours to resolution')]:
    P(f"{lab:30s} vs loss/vol {sp([x[k] for x in mf],[x['lv'] for x in mf]):+.3f}   vs loss$ {sp([x[k] for x in mf],[x['loss'] for x in mf]):+.3f}")
P(f"{'volume':30s} share of loss explained: top-20 by volume carry {sum(x['loss'] for x in sorted(mf,key=lambda x:-x['vol'])[:20])/TOT:.2f} of the loss")
# out of sample: markets ordered by their first swap; first half = train
mk_t={m:min(r['t'] for r in g) for m,g in bym.items()}; order=sorted(mk_t,key=mk_t.get); tr=set(order[:len(order)//2])
TR=[r for r in R if r['market'] in tr]; TE=[r for r in R if r['market'] not in tr]
P(f"\n## Out of sample: train = first {len(tr)} markets by first swap ({len(TR)} swaps), test = the other {len(order)-len(tr)} ({len(TE)} swaps)")
P("Each test swap gets the train-set loss/volume of its bucket; test loss share in the swaps ranked worst by that prediction.")
def bucket_of(f,bk,r):
    x=f(r)
    for lo,hi,lab in bk:
        if lo<=x<hi: return lab
cands=dict(F); cands['market type']=(lambda r:r['kind'],None)
def pred_fn(keys):
    tab=collections.defaultdict(lambda:[0,0])
    def key(r): return tuple(r['kind'] if F.get(k) is None and k=='market type' else bucket_of(F[k][0],F[k][1],r) for k in keys)
    for r in TR: t=tab[key(r)]; t[0]+=r['pnl']; t[1]+=r['vol']
    base=sum(r['pnl'] for r in TR)/sum(r['vol'] for r in TR)
    return lambda r: (tab[key(r)][0]/tab[key(r)][1]) if tab[key(r)][1]>50 else base
TEtot=sum(r['pnl'] for r in TE); TEvol=sum(r['vol'] for r in TE)
P(f"test loss {TEtot:,.0f} on volume {TEvol:,.0f}")
P(f"{'feature(s)':58s} {'vol in worst 20%':>16} {'loss there':>10} {'spearman':>8}")
for keys in [['hours to resolution proposed'],['hours to endOfTrading'],['price before swap'],['|move| last 6h'],['|move| last 24h'],['swap size (TYD)'],['hours since pool last traded'],['market type'],
             ['market type','hours to resolution proposed'],['market type','price before swap'],['hours to resolution proposed','price before swap','|move| last 24h']]:
    pf=pred_fn(keys); g=sorted(TE,key=lambda r:-pf(r)); acc=0;l=0
    for r in g:
        if acc>=0.2*TEvol: break
        acc+=r['vol']; l+=r['pnl']
    P(f"{' + '.join(keys):58s} {acc/TEvol*100:15.0f}% {l/TEtot*100:9.0f}% {sp([pf(r) for r in TE],[r['pnl']/r['vol'] if r['vol'] else 0 for r in TE]):+8.3f}")
open('results/features.txt','w').write('\n'.join(out)+'\n')
