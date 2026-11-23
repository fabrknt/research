import sys,json,os,time; sys.path.insert(0,'.')
from rpc import *
TOK=['0xaf88d065e77c8cC2239327C5EDb3A432268e5831','0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8','0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9','0x82aF49447D8a07e3bd95BD0d56f35241523fBab1']
bi=int(sys.argv[1]); start,end=int(sys.argv[2]),int(sys.argv[3])
B=json.load(open('ft/cohort_ft.json'))['batches'][bi]
topics=[TRANSFER,[pad(a) for a in B]]
F=f'ft/out_{bi}_{start}.jsonl'; SF=F+'.state'
cur=int(open(SF).read())+1 if os.path.exists(SF) else start
span=100000; out=open(F,'a')
while cur<=end:
    to=min(end,cur+span-1)
    try: logs=call('arb','eth_getLogs',[{'address':TOK,'topics':topics,'fromBlock':hex(cur),'toBlock':hex(to)}])
    except RuntimeError as e:
        span=max(500,span//2); time.sleep(1); continue
    for l in logs:
        out.write(json.dumps([int(l['blockNumber'],16),l['address'][2:6],l['topics'][1][-40:],l['topics'][2][-40:] if len(l['topics'])>2 else '',l['data'][-32:]])+'\n')
    out.flush(); open(SF,'w').write(str(to)); cur=to+1
    if span<100000: span=min(100000,span*2)
    print(cur,len(logs),flush=True)
print('DONE',flush=True)
