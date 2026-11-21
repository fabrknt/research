# Every pool Base's PoolManager initialized against TYD through one of Trueo's TruthMarketHooks, from
# 2026-09-08 (block 51,020,000) -> data/pools.json as [hook, poolId]. Initialize is indexed by the two
# currencies, so we ask for TYD as currency0 and as currency1.
import json,sys,os
sys.path.insert(0,'.'); from rpc import *
os.makedirs('data',exist_ok=True)
PM="0x498581fF718922c3f8e6A244956aF099B2652b2b"
IN="0xdd466e674ea557f56295e2d0218a125ea4b4f0f6f3307b95f85e6110838d6438"
TYDT="0x000000000000000000000000b13cf163d916917d9cd6e836905ca5f12a1def4b"
HOOKS={"0x1cfead8e66cebc5e51093dfd247ad34f841740c4","0x3e83479b2276ecfb7c7181f67b5d092d3511e0c4","0x6ae11676c7b3ec082989ce12ba462d46180fc0c4","0x7b0957aec2fb2a6cadef57a537a9d086849b60c4","0x8a86f6e03e3a8e31b8f57baa06aeca9a532500c4"}
HEAD=int(sys.argv[1]) if len(sys.argv)>1 else int(call('eth_blockNumber',[]),16)
L=plogs(PM,[IN,None,TYDT],51_020_000,to=HEAD)+plogs(PM,[IN,None,None,TYDT],51_020_000,to=HEAD)
pools=set(); other=0
for l in L:
    hook="0x"+l['data'][2:][128+24:192]
    if hook.lower() in HOOKS: pools.add((hook.lower(),l['topics'][1]))
    else: other+=1
print("Initialize with TYD:",len(L),"through a TruthMarketHook:",len(pools),"other hooks or none:",other)
json.dump(sorted(pools),open('data/pools.json','w'))
