import requests,json,time,sys,os
S=requests.Session()
inp=sys.argv[1]
F='cache/lighter_lookup.jsonl'
done=set()
if os.path.exists(F):
    for l in open(F): done.add(json.loads(l)['a'])
addrs=[a for a in json.load(open(inp)) if a not in done]
out=open(F,'a')
for i,a in enumerate(addrs):
    for k in range(8):
        try:
            r=S.get('https://mainnet.zklighter.elliot.ai/api/v1/accountsByL1Address',params={'l1_address':a},timeout=30)
            if r.status_code==429: time.sleep(10*(k+1)); continue
            j=r.json(); break
        except Exception as e: time.sleep(5)
    else:
        continue
    if j.get('code')==200:
        subs=j.get('sub_accounts',[])
        main=[s['index'] for s in subs if s.get('account_type')==0]
        rec={'a':a,'found':True,'main_idx':min(main) if main else min(s['index'] for s in subs),'n_sub':len(subs),'collateral':max([float(s.get('collateral') or 0) for s in subs] or [0])}
    elif j.get('code')==21100: rec={'a':a,'found':False}
    else: rec={'a':a,'err':str(j)[:100]}
    out.write(json.dumps(rec)+'\n'); out.flush()
    if i%500==0: print(i,len(addrs),flush=True)
    time.sleep(0.45)
