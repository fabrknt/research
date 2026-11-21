# Logs of Trueo's five TruthMarketHook contracts on Base -> data/hook_logs.json (FeeCollected: the hook's fee).
import json,sys,collections,time,os
sys.path.insert(0,'.'); from rpc import *
os.makedirs('data',exist_ok=True)
H=["0x1cfead8e66cebc5e51093dfd247ad34f841740c4","0x3e83479b2276ecfb7c7181f67b5d092d3511e0c4","0x6ae11676c7b3ec082989ce12ba462d46180fc0c4","0x7b0957aec2fb2a6cadef57a537a9d086849b60c4","0x8a86f6e03e3a8e31b8f57baa06aeca9a532500c4"]
t=time.time()
L=plogs(H,None,51_020_000)
c=collections.Counter((l['address'].lower(),l['topics'][0]) for l in L)
for k,v in c.most_common(): print(k,v)
print(len(L),time.time()-t)
json.dump(L,open('data/hook_logs.json','w'))
