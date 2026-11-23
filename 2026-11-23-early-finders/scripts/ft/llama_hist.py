import json,requests,os,sys,time
S=requests.Session()
F='ft/llama_hist.json'; H=json.load(open(F)) if os.path.exists(F) else {}
slugs=json.load(open(sys.argv[1]))
for s in slugs:
    if s in H: continue
    try:
        j=S.get(f'https://api.llama.fi/protocol/{s}',timeout=60).json()
        tv=j.get('tvl') or []
        peak=max((x.get('totalLiquidityUSD',0) for x in tv),default=0)
        last=tv[-1] if tv else {}
        H[s]={'name':j.get('name'),'category':j.get('category'),'peak':peak,'last':last.get('totalLiquidityUSD'),'last_date':last.get('date'),'gecko_id':j.get('gecko_id'),'symbol':j.get('symbol'),'deadUrl':j.get('deadUrl'),'deprecated':j.get('deprecated'),'parent':j.get('parentProtocol'),'listedAt':j.get('listedAt'),'chains':j.get('chains')}
    except Exception as e: H[s]={'err':str(e)[:100]}
    json.dump(H,open(F,'w')); time.sleep(0.3)
print('DONE',len(H))
