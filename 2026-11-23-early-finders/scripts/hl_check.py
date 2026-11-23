import requests,json,time,sys,os
# input: json list of [addr, end_ms]; output jsonl: addr, end_ms, n_before, first_time, first_type
S=requests.Session()
inp,F=sys.argv[1],sys.argv[2]
done=set()
if os.path.exists(F):
    for l in open(F): done.add(json.loads(l)['a'])
items=[x for x in json.load(open(inp)) if x[0] not in done]
out=open(F,'a')
for i,(a,end) in enumerate(items):
    q={'type':'userNonFundingLedgerUpdates','user':a,'startTime':0}
    if end: q['endTime']=end
    for k in range(10):
        try:
            r=S.post('https://api.hyperliquid.xyz/info',json=q,timeout=30)
            if r.status_code==429: time.sleep(15*(k+1)); continue
            x=r.json(); break
        except Exception: time.sleep(5)
    else: continue
    rec={'a':a,'end':end,'n':len(x),'first_time':x[0]['time'] if x else None,'first_type':x[0]['delta']['type'] if x else None}
    out.write(json.dumps(rec)+'\n'); out.flush()
    if i%200==0: print(i,len(items),flush=True)
    time.sleep(0.9)
