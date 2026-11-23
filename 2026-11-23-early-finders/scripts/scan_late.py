import sys,datetime,json,bisect; sys.path.insert(0,'.')
from rpc import *
import bts
B='0x2Df1c51E09aECF9cacB7bc98cB1742757f163dF7'
def blk(ts):
    i=bisect.bisect_left([a[1] for a in bts.A],ts)
    return find_block('arb',ts,bts.A[max(0,i-1)][0],bts.A[min(len(bts.A)-1,i)][0])
wins=[]
for m in range(1,7):
    s=datetime.datetime(2025,m,15,tzinfo=datetime.timezone.utc).timestamp()
    b0=blk(s); b1=blk(s+86400)
    wins.append((m,b0,b1)); print(m,b0,b1,flush=True)
    scan('arb','0xaf88d065e77c8cC2239327C5EDb3A432268e5831',[TRANSFER,None,pad(B)],b0,b1,f'cache/late_{m}.jsonl',span=50000,minspan=500,maxspan=400000)
json.dump(wins,open('cache/late_windows.json','w'))
