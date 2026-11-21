# Swap, ModifyLiquidity and Initialize logs of those pools from Base's PoolManager -> data/pm_logs.json.
# Each batch of 200 pools is saved to data/pm_part_<i>.json, so a stopped run picks up where it left off.
import json,sys,time,os,hashlib
sys.path.insert(0,'.'); from rpc import *
PM="0x498581fF718922c3f8e6A244956aF099B2652b2b"
SW="0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f"
ML="0xf208f4912782fd25c7f114ca3723a2d5dd6f3bcc3ac8db5af63baa85f711d5ec"
IN="0xdd466e674ea557f56295e2d0218a125ea4b4f0f6f3307b95f85e6110838d6438"
ids=sorted({p[1] for p in json.load(open('data/pools.json'))})
out=[]; B=200
HEAD=int(sys.argv[1]) if len(sys.argv)>1 else int(call('eth_blockNumber',[]),16)
print('blocks',51_020_000,'to',HEAD,flush=True)
for i in range(0,len(ids),B):
    t=time.time()
    key=hashlib.sha256((','.join(ids[i:i+B])+f':{HEAD}').encode()).hexdigest()[:12]
    f=f'data/pm_part_{i}_{key}.json'  # tied to this batch's pool ids and end block
    if os.path.exists(f): out+=json.load(open(f)); print(i,'cached',flush=True); continue
    part=plogs(PM,[[SW,ML,IN],ids[i:i+B]],51_020_000,to=HEAD,workers=6)
    json.dump(part,open(f,'w')); out+=part
    print(i,len(out),round(time.time()-t),flush=True)
json.dump(out,open('data/pm_logs.json','w'))
