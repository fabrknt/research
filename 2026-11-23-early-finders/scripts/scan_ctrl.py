import sys,datetime,json,bisect; sys.path.insert(0,'.')
from rpc import *
import bts
def blk(ts):
    i=bisect.bisect_left([a[1] for a in bts.A],ts)
    return find_block('arb',ts,bts.A[max(0,i-1)][0],bts.A[min(len(bts.A)-1,i)][0])
for day in [10,20]:
    s=datetime.datetime(2023,10,day,12,tzinfo=datetime.timezone.utc).timestamp()
    b0=blk(s); b1=blk(s+3*3600)
    print(day,b0,b1,flush=True)
    for tok,nm in [('0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8','usdce'),('0xaf88d065e77c8cC2239327C5EDb3A432268e5831','usdc')]:
        scan('arb',tok,[TRANSFER],b0,b1,f'cache/ctrl_{day}_{nm}.jsonl',span=2000,minspan=100,maxspan=20000)
