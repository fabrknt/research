# map pools (from Initialize in window) -> outcome token -> market; read market state (current state)
import json,sys,subprocess
sys.path.insert(0,'.'); from rpc import *
IN="0xdd466e674ea557f56295e2d0218a125ea4b4f0f6f3307b95f85e6110838d6438"
L=json.load(open('data/pm_logs.json'))
TYD="0xb13cf163d916917d9cd6e836905ca5f12a1def4b"
def ec(to,sig):
    sel=subprocess.run(["cast","sig",sig],capture_output=True,text=True).stdout.strip()
    return call("eth_call",[{"to":to,"data":sel},"latest"])
pools={}
for l in L:
    if l['topics'][0]==IN:
        c0="0x"+l['topics'][2][-40:]; c1="0x"+l['topics'][3][-40:]
        d=l['data'][2:]; w=[d[i:i+64] for i in range(0,len(d),64)]
        pools[l['topics'][1]]={"c0":c0,"c1":c1,"fee":int(w[0],16),"ts":int(w[1],16),"hook":"0x"+w[2][-40:],"initBlock":int(l['blockNumber'],16),"initTime":int(l['blockTimestamp'],16)}
print("pools with Initialize in window:",len(pools))
mk={}
for pid,p in pools.items():
    tok=p['c1'] if p['c0'].lower()==TYD else p['c0']
    p['token']=tok; p['tydIs0']=p['c0'].lower()==TYD
    try: p['market']="0x"+ec(tok,"owner()")[-40:]
    except Exception as e: p['market']=None; continue
    m=p['market']
    if m not in mk:
        r={}
        for f in ["endOfTrading()","winningPosition()","getCurrentStatus()","resolutionProposedAt()","finalizedAt()","createdAt()","yesToken()","noToken()"]:
            try: r[f[:-2]]=ec(m,f)
            except Exception as e: r[f[:-2]]=None
        for k in ["endOfTrading","winningPosition","getCurrentStatus","resolutionProposedAt","finalizedAt","createdAt"]:
            r[k]=int(r[k],16) if r[k] else None
        for k in ["yesToken","noToken"]: r[k]="0x"+r[k][-40:] if r[k] else None
        try:
            q=subprocess.run(["cast","call",m,"marketQuestion()(string)","--rpc-url",RPC],capture_output=True,text=True).stdout.strip()
        except Exception: q=""
        r['q']=q; mk[m]=r
    side='YES' if mk[m]['yesToken'] and mk[m]['yesToken'].lower()==tok.lower() else 'NO'
    p['side']=side
json.dump({"pools":pools,"markets":mk},open('data/markets.json','w'),indent=1)
import collections
print("markets:",len(mk), collections.Counter((v['getCurrentStatus'],v['winningPosition']) for v in mk.values()))
