# Checks behind the write-up: the quote token, the hooks' current fee rate and swap validator, the sample
# (pools per market, outcomes, dates, swap fees), swaps after endOfTrading, and who adds the pools' liquidity.
import json,collections,statistics,subprocess,sys
sys.path.insert(0,'.'); from rpc import RPC
def cc(to,sig): return subprocess.run(["cast","call",to,sig,"--rpc-url",RPC],capture_output=True,text=True).stdout.strip()
TYD="0xb13cf163d916917d9cd6e836905ca5f12a1def4b"
print("quote token:",cc(TYD,"symbol()(string)"),cc(TYD,"name()(string)"),"decimals",cc(TYD,"decimals()(uint8)"))
for h in sorted({p[0] for p in json.load(open('data/pools.json'))}):
    print("hook",h,"feeNumerator (/10000):",cc(h,"feeNumerator()(uint256)"),"swapValidator:",cc(h,"swapValidator()(address)"))
M=json.load(open('data/markets.json')); pools=M['pools']; mk=M['markets']
L=json.load(open('data/pm_logs.json'))
SW="0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f"
ML="0xf208f4912782fd25c7f114ca3723a2d5dd6f3bcc3ac8db5af63baa85f711d5ec"
def s(h):
    v=int(h,16); return v-(1<<256) if v>=1<<255 else v
res={pid for pid,p in pools.items() if mk.get(p.get('market')) and mk[p['market']]['getCurrentStatus']==7 and mk[p['market']]['winningPosition'] in (1,2,3)}
import datetime
pm=collections.Counter(pools[p]['market'] for p in res)
fin=[mk[m] for m in pm]
print("pools in data/pools.json:",len(json.load(open('data/pools.json'))),"; resolved markets:",len(pm),"; pools per resolved market:",dict(collections.Counter(pm.values())))
print("winningPosition:",dict(collections.Counter(m['winningPosition'] for m in fin)),"; with finalizedAt set:",sum(1 for m in fin if m['finalizedAt']),
      "; statuses with finalizedAt set (all markets):",dict(collections.Counter(m['getCurrentStatus'] for m in mk.values() if m['finalizedAt'])))
d0=lambda x: datetime.datetime.fromtimestamp(x,datetime.timezone.utc).strftime('%Y-%m-%d')
print("endOfTrading:",d0(min(m['endOfTrading'] for m in fin)),"to",d0(max(m['endOfTrading'] for m in fin)))
print("swap fee field (pips) in these pools' Swap events:",dict(collections.Counter(int(l['data'][2:][320:384],16) for l in L if l['topics'][0]==SW and l['topics'][1] in res)),
      "; pool fee at Initialize:",dict(collections.Counter(pools[p]['fee'] for p in res)))
d=[];before=0
for l in L:
    pid=l['topics'][1]
    if pid not in res or l['topics'][0]!=SW: continue
    m=mk[pools[pid]['market']]; t=int(l['blockTimestamp'],16)
    if t>m['endOfTrading']:
        d.append((t-m['endOfTrading'])/3600)
        if m['resolutionProposedAt'] and t<m['resolutionProposedAt']: before+=1
d.sort()
print("swaps after endOfTrading:",len(d),"hours after it: p10",round(d[len(d)//10],1),"median",round(statistics.median(d),1),"p90",round(d[len(d)*9//10],1),
      "; before resolution was proposed:",before)
add=collections.Counter(); pos=set()
for l in L:
    if l['topics'][0]!=ML or l['topics'][1] not in res: continue
    w=l['data'][2:]; w=[w[i:i+64] for i in range(0,len(w),64)]; dl=s(w[2]); snd="0x"+l['topics'][2][-40:]
    if dl>0: add[snd]+=dl
    if snd=="0x7c5f5a4bbd8fd63184577525326123b519429bdc": pos.add(w[3])
tot=sum(add.values())
print("liquidity added, by caller:",{k:round(v/tot,3) for k,v in add.most_common()},"; PositionManager positions:",len(pos))
