import sys,json,os,bisect; sys.path.insert(0,'.')
from rpc import *
F='./cache/arb_anchors.json'
def anchors():
    if os.path.exists(F): return json.load(open(F))
    a=[]
    n=int(call('arb','eth_blockNumber',[]),16)
    for b in list(range(40000000,n,1000000))+[n]:
        a.append([b,block_ts('arb',b)]); time.sleep(0.15)
    json.dump(a,open(F,'w')); return a
A=anchors(); BS=[x[0] for x in A]
def ts(b):
    i=bisect.bisect_right(BS,b)-1; i=max(0,min(i,len(A)-2))
    (b0,t0),(b1,t1)=A[i],A[i+1]
    return t0+(b-b0)*(t1-t0)/(b1-b0)
