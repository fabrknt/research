# Same LP P&L, but timed against when resolution was proposed (R), since swaps continue after endOfTrading.
import json,collections,statistics
D='data/'
L=json.load(open(D+'pm_logs.json')); M=json.load(open(D+'markets.json'))
SW="0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f"
ML="0xf208f4912782fd25c7f114ca3723a2d5dd6f3bcc3ac8db5af63baa85f711d5ec"
OMS={"0x8e5e63f69bf7ef2a24f5247c2bfc3946b95e3da7","0x1cdb1c43eb64e99780ea9d3c7162c23432c59a1a","0x9003892e8c528ef153ceb79e23c330d3f450e1d4","0xe57475c7773b9fdc8a7b99b6bed507725dd62178"}
TYD="0xb13cf163d916917d9cd6e836905ca5f12a1def4b"
def s(h):
    v=int(h,16); return v-(1<<256) if v>=1<<255 else v
pools=M['pools']; mk=M['markets']
ev=collections.defaultdict(list)
for l in L: ev[l['topics'][1]].append(l)
BK=[1,6,24,72,168]
agg=collections.defaultdict(lambda: collections.defaultdict(float))
liqev=collections.defaultdict(list)  # market -> LP (not OrderManager) liquidity changes across its pools
for pid,p in pools.items():
    m=mk.get(p.get('market'))
    if not m or m['getCurrentStatus']!=7 or m['winningPosition'] not in (1,2,3): continue
    wp=m['winningPosition']; v=0.5 if wp==3 else (1.0 if (wp==1)==(p['side']=='YES') else 0.0)
    T=m['endOfTrading']; R=m['resolutionProposedAt'] or T
    a=agg[p['market']]; a['T']=T; a['R']=R
    for l in sorted(ev[pid],key=lambda x:(int(x['blockNumber'],16),int(x['logIndex'],16))):
        t=int(l['blockTimestamp'],16); d=l['data'][2:]; w=[d[i:i+64] for i in range(0,len(d),64)]
        if l['topics'][0]==SW:
            a0,a1=s(w[0]),s(w[1]); tyd,tok=((a0,a1) if p['tydIs0'] else (a1,a0))
            pnl=tok/1e18*v+tyd/1e6; a['pnl']+=pnl; a['vol']+=abs(tyd)/1e6
            if t>R: a['afterR']+=pnl
            for b in BK:
                if R-b*3600<t<=R: a[f'R{b}']+=pnl
        elif l['topics'][0]==ML:
            snd="0x"+l['topics'][2][-40:]
            if snd not in OMS: liqev[p['market']].append((int(l['blockNumber'],16),int(l['logIndex'],16),t,s(w[2])))
mk_rows=[]
for mid,a in agg.items():
    # Raw v4 liquidity units summed over the market's pools in time order, not capital.
    liq=peak=left0=left24=0
    for _,_,t,dl in sorted(liqev[mid]):
        liq+=dl; peak=max(peak,liq)
        if t<=a['R']: left0=liq
        if t<=a['R']-24*3600: left24=liq
    r=dict(pnl=a['pnl'],vol=a['vol'],afterR=a['afterR'],peak=peak,left0=left0,left24=left24,**{f'R{b}':a[f'R{b}'] for b in BK},
           q=mk[mid]['q'][:70],gapRT=(a['R']-a['T'])/3600)
    mk_rows.append(r)
tot=sum(r['pnl'] for r in mk_rows)
print("markets",len(mk_rows),"LP loss vs hold",round(tot,2),"volume",round(sum(r['vol'] for r in mk_rows),2))
print("median hours from endOfTrading to resolution proposed:",round(statistics.median(r['gapRT'] for r in mk_rows),1))
for b in BK: print(f"share of LP loss in the {b} h before resolution was proposed:",round(sum(r[f'R{b}'] for r in mk_rows)/tot,3))
print("share after resolution was proposed:",round(sum(r['afterR'] for r in mk_rows)/tot,3))
top=sorted(mk_rows,key=lambda r:-r['pnl'])[:30]
fr0=[r['left0']/r['peak'] for r in top if r['peak']]; fr24=[r['left24']/r['peak'] for r in top if r['peak']]
print("top 30 by loss: median LP liquidity (raw units, all its pools) left at R / its peak",round(statistics.median(fr0),3),"; at R-24h",round(statistics.median(fr24),3),
      "; nearly all gone (<5%) at R:",sum(x<0.05 for x in fr0),"of",len(fr0))
json.dump(mk_rows,open('results/markets.json','w'),indent=1)
