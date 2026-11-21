# Per market: what the pool's liquidity lost against holding, valued at the final outcome; the LP fee the
# pool paid; the hook's fee (it goes to Trueo's fee collector, not to LPs); timing against endOfTrading.
import json,sys,collections,statistics
D='data/'
L=json.load(open(D+'pm_logs.json')); M=json.load(open(D+'markets.json')); H=json.load(open(D+'hook_logs.json'))
tx_from={}
SW="0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f"
ML="0xf208f4912782fd25c7f114ca3723a2d5dd6f3bcc3ac8db5af63baa85f711d5ec"
FC='0x5899c71e3fe835a574423906759f5d29719430494c095837bff7e180adac2a4c'
OMS={"0x8e5e63f69bf7ef2a24f5247c2bfc3946b95e3da7","0x1cdb1c43eb64e99780ea9d3c7162c23432c59a1a","0x9003892e8c528ef153ceb79e23c330d3f450e1d4","0xe57475c7773b9fdc8a7b99b6bed507725dd62178"}
TYD="0xb13cf163d916917d9cd6e836905ca5f12a1def4b"
def s(h,bits=256):
    v=int(h,16); return v-(1<<256) if v>=1<<255 else v
pools=M['pools']; mk=M['markets']
ev=collections.defaultdict(list)
for l in L: ev[l['topics'][1]].append(l)
hookfee=collections.defaultdict(float)  # TYD-denominated hook fee (token-denominated valued at final later)
hookfee_tok=collections.defaultdict(float)
for l in H:
    if l['topics'][0]==FC:
        cur="0x"+l['topics'][2][-40:]; amt=int(l['data'],16)
        if cur==TYD: hookfee[l['topics'][1]]+=amt/1e6
        else: hookfee_tok[l['topics'][1]]+=amt/1e18
rows=[]
BK=[1,6,24,72]
for pid,p in pools.items():
    m=mk.get(p.get('market')); 
    if not m: continue
    st,wp=m['getCurrentStatus'],m['winningPosition']
    if st!=7 or wp not in (1,2,3): continue
    side=p['side']; v = 0.5 if wp==3 else (1.0 if (wp==1)==(side=='YES') else 0.0)
    T=m['endOfTrading']
    r=dict(pid=pid,market=p['market'],q=m['q'][:60],side=side,v=v,T=T,hook=p['hook'],fee=p['fee'],
           trader_pnl=0.0,vol=0.0,nsw=0,lpfee=0.0,post_T_pnl=0.0,post_T_vol=0.0,first=None,last=None,
           **{f'pnl_{b}h':0.0 for b in BK},**{f'vol_{b}h':0.0 for b in BK},traders=set(),
           liq_peak=0,liq_atT=0,liq_lp=0,liq_om=0,lp_salts=set(),removed_beforeT=0)
    liq=0; liq_lp=0
    for l in sorted(ev[pid],key=lambda x:(int(x['blockNumber'],16),int(x['logIndex'],16))):
        t=int(l['blockTimestamp'],16); d=l['data'][2:]; w=[d[i:i+64] for i in range(0,len(d),64)]
        if l['topics'][0]==SW:
            a0,a1=s(w[0]),s(w[1]); fee=int(w[5],16)
            atyd,atok=(a0,a1) if p['tydIs0'] else (a1,a0)
            tyd=atyd/1e6; tok=atok/1e18
            pnl=tok*v+tyd   # swapper perspective: positive = received
            vol=abs(tyd)
            # lp fee in TYD-equivalent: on input leg
            if tyd<0: lf=-tyd*fee/1e6
            else: lf=-tok*fee/1e6*(abs(tyd)/abs(tok) if tok else 0)
            r['nsw']+=1; r['vol']+=vol; r['lpfee']+=lf
            r['first']=r['first'] or t; r['last']=t
            if t>T: r['post_T_pnl']+=pnl; r['post_T_vol']+=vol
            r['trader_pnl']+=pnl
            for b in BK:
                if T-b*3600 < t <= T: r[f'pnl_{b}h']+=pnl; r[f'vol_{b}h']+=vol
            if l['transactionHash'] in tx_from: r['traders'].add(tx_from[l['transactionHash']])
        elif l['topics'][0]==ML:
            dl=s(w[2]); snd="0x"+l['topics'][2][-40:]
            liq+=dl
            if snd not in OMS:
                liq_lp+=dl; r['lp_salts'].add(w[3])
                if dl<0 and t<=T: r['removed_beforeT']+=-dl
            else: r['liq_om']+=max(dl,0)
            r['liq_peak']=max(r['liq_peak'],liq_lp)
            if t<=T: r['liq_atT']=liq_lp
    r['hookfee']=hookfee.get(pid,0)+hookfee_tok.get(pid,0)*v
    r['traders']=len(r['traders']); r['lp_salts']=len(r['lp_salts'])
    rows.append(r)
json.dump(rows,open(D+'pool_results.json','w'),indent=1)
# aggregate per market
byM=collections.defaultdict(list)
for r in rows: byM[r['market']].append(r)
mrows=[]
for m,rs in byM.items():
    a={k:sum(r[k] for r in rs) for k in ['trader_pnl','vol','nsw','lpfee','hookfee','post_T_pnl','post_T_vol']+[f'pnl_{b}h' for b in BK]+[f'vol_{b}h' for b in BK]}
    a['market']=m; a['q']=rs[0]['q']; a['T']=rs[0]['T']; a['hook']=rs[0]['hook']
    a['peak']=sum(r['liq_peak'] for r in rs); a['atT']=sum(r['liq_atT'] for r in rs)
    a['traders']=sum(r['traders'] for r in rs)
    a['lp_salts']=sum(r['lp_salts'] for r in rs)
    mrows.append(a)
json.dump(mrows,open(D+'market_results.json','w'),indent=1)
act=[a for a in mrows if a['nsw']>0]
print("resolved markets w/ full life in window:",len(mrows),"with swaps:",len(act))
tot={k:sum(a[k] for a in act) for k in ['trader_pnl','vol','lpfee','hookfee','post_T_pnl','post_T_vol']+[f'pnl_{b}h' for b in BK]}
for k,v in tot.items(): print(f"{k:12s} {v:14.2f}")
gross=tot['trader_pnl']+tot['lpfee']
print("LP net loss vs hold (=trader pnl):",round(tot['trader_pnl'],2)," gross loss before LP fee:",round(gross,2),
      " LP fee cover of gross:",round(tot['lpfee']/gross,4) if gross>0 else None)
print("LP fee here is an estimate: each swap's TYD leg x the fee in its Swap event.")
print("hook fee, valued at the outcome (to Trueo's fee collector) / LP loss:",round(tot['hookfee']/tot['trader_pnl'],4)," / volume:",round(tot['hookfee']/tot['vol'],4),
      " LP loss / hook fee:",round(tot['trader_pnl']/tot['hookfee'],2))
print("LP loss / volume:",round(tot['trader_pnl']/tot['vol'],4))
srt=sorted(act,key=lambda a:-a['trader_pnl'])
print("top 20 markets' share of LP loss:",round(sum(a['trader_pnl'] for a in srt[:20])/tot['trader_pnl'],3),
      " median loss per market:",round(statistics.median(a['trader_pnl'] for a in act),1),"; median volume per market:",round(statistics.median(a['vol'] for a in act),1))
for b in BK: print(f"share of LP loss in the {b} h before endOfTrading:",round(tot[f'pnl_{b}h']/tot['trader_pnl'],3) if tot['trader_pnl'] else None)
print("\nper-market (sorted by LP loss):")
print(f"{'LPloss':>9} {'last1h':>8} {'last6h':>8} {'last24h':>8} {'last72h':>8} {'postT':>8} {'vol':>9} {'lpfee':>6} {'hookfee':>7} {'nsw':>4} {'trd':>4} {'liq@T/peak':>10} q")
for a in sorted(act,key=lambda a:-a['trader_pnl']):
    fr=a['atT']/a['peak'] if a['peak'] else float('nan')
    print(f"{a['trader_pnl']:9.0f} {a['pnl_1h']:8.0f} {a['pnl_6h']:8.0f} {a['pnl_24h']:8.0f} {a['pnl_72h']:8.0f} {a['post_T_pnl']:8.0f} {a['vol']:9.0f} {a['lpfee']:6.1f} {a['hookfee']:7.0f} {a['nsw']:4d} {a['traders']:4d} {fr:10.2f} {a['q']}")
fr=[a['atT']/a['peak'] for a in act if a['peak']]
print("\nmedian liquidity remaining at endOfTrading / peak (non-OrderManager LP):",statistics.median(fr) if fr else None, "n=",len(fr), " share >=0.5:",sum(x>=0.5 for x in fr)/len(fr) if fr else None)
