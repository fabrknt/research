"""lp_*.json と migr_*.json から REPORT 用の表を作る。 usage: python3 tables.py"""
import json,glob,math
mig={}
for f in glob.glob("data/migr_*.json"):
    for a in json.load(open(f)): mig[(a["chain"],a["auction"])]=a
def lpsize(a):
    """migrate の位置(全範囲 1 本が普通)の currency 側の量。全範囲なら TVL ≈ 2 倍。"""
    m=a["migr"]; sp=m["sqrtPriceX96"]/2**96; cur=a["currency"].lower()
    curIs0= m["currency0"].lower()==cur
    tot=0
    for tl,tu,L in m["positions"]:
        sa=1.0001**(tl/2); sb=1.0001**(tu/2); s=min(max(sp,sa),sb)
        a0=L*(sb-s)/(s*sb); a1=L*(s-sa)
        tot+= a0 if curIs0 else a1
    return tot/10**(a["curDec"] or 18)
def ilfee(a,r):
    """CCA が置いた全範囲の位置だけの 24 時間の損益: (位置の価値 - そのまま持っていた場合) と、その位置の手数料の取り分。currency 建て。"""
    m=a["migr"]; pos=[p for p in m["positions"] if p[2]>0]
    if not pos or not r.get("n"): return None
    full=all(p[0]<=-887000 and p[1]>=887000 for p in pos)
    if not full: return None
    Lc=sum(p[2] for p in pos)
    sw=json.load(open(f"data/swaps_{r['chain']}_{m['poolId'][:10]}.json"))
    fee=sum(x["feeRev"]*min(1,Lc/x["liq"]) for x in sw if x["liq"])
    P0=r["P0"]; P24=r["P24"]; k=P24/P0
    c=lpsize(a); hodl0=2*c            # 全範囲は両側同額 -> currency 建てで 2c
    hodl24=c+c*k; v24=2*c*k**0.5
    return dict(il=(v24-hodl24),feeCCA=fee,ratio=k,hodl0=hodl0)
rows=[]
for f in sorted(x for x in glob.glob("data/lp_*.json") if not x.endswith("lp_all.json")):
    for r in json.load(open(f)):
        a=mig[(r["chain"],r["auction"])]; c=lpsize(a); r["lpCurSide"]=c; r["lpTVLUSD"]=2*c*r["usdper"]
        x=ilfee(a,r)
        if x: r.update(ilUSD=x["il"]*r["usdper"],feeCCAUSD=x["feeCCA"]*r["usdper"],p24ratio=x["ratio"])
        rows.append(r)
rows.sort(key=lambda r:-(r["raisedUSD"] or 0))
H="| chain | token | 集めた額 USD | LP(全範囲) TVL USD | fee | swap 件数 | 出来高 USD | 手数料 USD | 5分 後/前 | 1時間 後/前 | 24時間 後/前 | 上位5の割合 | 送り手数 | 最初の5ブロックの出来高割合 |"
print(H); print("|"+"---|"*14)
for r in rows:
    if not r.get("n"): print(f"| {r['chain']} | {r['tok']} | {r['raisedUSD'] or 0:,.0f} | {r['lpTVLUSD']:,.0f} | | 0 | | | | | | | | |"); continue
    f=lambda k:f"{r[k+'_postUSD']:,.0f} / {r[k+'_preUSD']:,.0f}"
    print(f"| {r['chain']} | {r['tok']} | {r['raisedUSD'] or 0:,.0f} | {r['lpTVLUSD']:,.0f} | {r['feeTier']/1e4:.2f}% | {r['n']} | {r['volUSD']:,.0f} | {r['feeUSD']:,.0f} | {f('m5')} | {f('m1h')} | {f('m24h')} | {r.get('top5share',0):.0%} | {r.get('uniqFrom','')} | {r['first5blkVolShare']:.0%} |")
tot=lambda k:sum(r.get(k,0) or 0 for r in rows)
print("\n合計: 出来高",round(tot("volUSD")),"手数料",round(tot("feeUSD")),"24h 後",round(tot("m24h_postUSD")),"24h 前",round(tot("m24h_preUSD")),"1h 後",round(tot("m1h_postUSD")),"5m 後",round(tot("m5_postUSD")),"TVL",round(tot("lpTVLUSD")))
print("\n| chain | token | TVL USD | P24/P0 | 位置の IL(対 HODL) USD | 位置の手数料 USD | 差引 USD | 差引/TVL |")
print("|---|---|---|---|---|---|---|---|")
for r in rows:
    if "ilUSD" in r: print(f"| {r['chain']} | {r['tok']} | {r['lpTVLUSD']:,.0f} | {r['p24ratio']:.3f} | {r['ilUSD']:,.0f} | {r['feeCCAUSD']:,.0f} | {r['ilUSD']+r['feeCCAUSD']:,.0f} | {(r['ilUSD']+r['feeCCAUSD'])/r['lpTVLUSD']:.1%} |")
json.dump(rows,open("data/lp_all.json","w"),indent=1)
