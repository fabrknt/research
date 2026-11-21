# One row per swap in the 104 resolved Trueo markets (same sample and valuation as ../2026-11-21-trueo-lp-loss),
# with ex-ante features: hours to endOfTrading / resolution proposed, pool price before the swap, recent price
# moves in that pool, size, direction, market type. The outcome is used only for the loss (trader P&L).
import json,collections,bisect,re
SRC='../2026-11-21-trueo-lp-loss/data/'
L=json.load(open(SRC+'pm_logs.json')); M=json.load(open(SRC+'markets.json'))
SW="0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f"
IN="0xdd466e674ea557f56295e2d0218a125ea4b4f0f6f3307b95f85e6110838d6438"
def s(h):
    v=int(h,16); return v-(1<<256) if v>=1<<255 else v
def kind(q):
    q=q.lower()
    if 'hack' in q or 'exploit' in q: return 'hack' if 'week' in q else 'other'
    if 'revenue' in q and 'week' in q: return 'revenue_week'
    if 'revenue' in q or 'volume' in q or 'tvl' in q: return 'metric_month'
    if re.search(r' above \$| hit \$| reach \$| at \$|price|below \$|trade below|trade at',q): return 'price'
    return 'other'
pools=M['pools']; mk=M['markets']
ev=collections.defaultdict(list)
for l in L: ev[l['topics'][1]].append(l)
def px(sq,tydIs0):
    r=(sq/2**96)**2
    return 1e12/r if tydIs0 else r*1e12   # outcome-token price in TYD
rows=[]
for pid,p in pools.items():
    m=mk.get(p.get('market'))
    if not m or m['getCurrentStatus']!=7 or m['winningPosition'] not in (1,2,3): continue
    wp=m['winningPosition']; v=0.5 if wp==3 else (1.0 if (wp==1)==(p['side']=='YES') else 0.0)
    T=m['endOfTrading']; R=m['resolutionProposedAt'] or T
    hist_t=[];hist_p=[]; price=None
    for l in sorted(ev[pid],key=lambda x:(int(x['blockNumber'],16),int(x['logIndex'],16))):
        t=int(l['blockTimestamp'],16); d=l['data'][2:]; w=[d[i:i+64] for i in range(0,len(d),64)]
        if l['topics'][0]==IN:
            price=px(int(w[3],16),p['tydIs0']); hist_t.append(t); hist_p.append(price); continue
        if l['topics'][0]!=SW: continue
        a0,a1=s(w[0]),s(w[1]); atyd,atok=(a0,a1) if p['tydIs0'] else (a1,a0)
        tyd=atyd/1e6; tok=atok/1e18; post=px(int(w[2],16),p['tydIs0'])
        pre=price if price is not None else post
        def ago(hrs):
            i=bisect.bisect_right(hist_t,t-hrs*3600)-1
            return hist_p[i] if i>=0 else (hist_p[0] if hist_p else pre)
        gap=(t-hist_t[-1])/3600 if hist_t else None
        rows.append(dict(pool=pid,market=p['market'],kind=kind(m['q']),t=t,hT=(T-t)/3600,hR=(R-t)/3600,
            pre=pre,post=post,mv1=pre-ago(1),mv6=pre-ago(6),mv24=pre-ago(24),gap=gap,
            buy=tok>0,vol=abs(tyd),pnl=tok*v+tyd,exec=abs(tyd/tok) if tok else None,v=v))
        price=post; hist_t.append(t); hist_p.append(post)
json.dump(rows,open('data/trades.json','w'))
print("swaps",len(rows),"markets",len({r['market'] for r in rows}),"loss",round(sum(r['pnl'] for r in rows),2),"vol",round(sum(r['vol'] for r in rows),2))
# sanity: execution price lies between pre and post price
ok=sum(1 for r in rows if r['exec'] and min(r['pre'],r['post'])*0.97<=r['exec']<=max(r['pre'],r['post'])*1.03)
print("exec price within [pre,post] (+-3%):",ok,"of",sum(1 for r in rows if r['exec']))
print("kinds:",collections.Counter(r['kind'] for r in rows))
