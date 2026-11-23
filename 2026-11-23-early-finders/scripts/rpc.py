import requests, json, time, os, sys
URLS={'arb':'https://arb1.arbitrum.io/rpc','eth':'https://ethereum-rpc.publicnode.com'}
S=requests.Session()
def call(chain,method,params,retries=12):
    for i in range(retries):
        try:
            r=S.post(URLS[chain],json={'jsonrpc':'2.0','id':1,'method':method,'params':params},timeout=60)
            j=r.json()
            if 'error' in j:
                if j['error'].get('code') in (429,-32005) or 'Too Many' in str(j['error']):
                    time.sleep(2+i*3); continue
                raise RuntimeError(json.dumps(j['error'])[:300])
            return j['result']
        except RuntimeError: raise
        except Exception as e:
            time.sleep(1+i*2)
    raise RuntimeError('net fail')
def block_ts(chain,n):
    return int(call(chain,'eth_getBlockByNumber',[hex(n),False])['timestamp'],16)
def find_block(chain,ts,lo=0,hi=None):
    if hi is None: hi=int(call(chain,'eth_blockNumber',[]),16)
    while lo<hi:
        m=(lo+hi)//2
        if block_ts(chain,m)<ts: lo=m+1
        else: hi=m
    return lo
def pad(a): return '0x'+'0'*24+a.lower()[2:]
TRANSFER='0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
def scan(chain,address,topics,start,end,cachefile,span=2000000,minspan=1000,maxspan=50000000):
    """generic getLogs with adaptive span, appends to jsonl cache, resumable"""
    state_f=cachefile+'.state'
    cur=start
    if os.path.exists(state_f): cur=int(open(state_f).read())+1
    out=open(cachefile,'a')
    while cur<=end:
        to=min(end,cur+span-1)
        try:
            logs=call(chain,'eth_getLogs',[{'address':address,'topics':topics,'fromBlock':hex(cur),'toBlock':hex(to)}])
        except RuntimeError as e:
            if span<=minspan: print('fail at',cur,e); time.sleep(5); continue
            span=max(minspan,span//2); continue
        for l in logs:
            out.write(json.dumps({'b':int(l['blockNumber'],16),'tx':l['transactionHash'],'t':l['topics'],'d':l['data'],'a':l['address']})+'\n')
        out.flush(); open(state_f,'w').write(str(to))
        cur=to+1
        if len(logs)<5000: span=min(maxspan,int(span*1.5))
        sys.stdout.write(f'\r{cachefile} {cur}/{end} span={span} n={len(logs)}   '); sys.stdout.flush()
    print()
