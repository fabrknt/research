import requests,json,datetime,time
S=requests.Session()
def get(url,params):
    for i in range(6):
        try:
            r=S.get(url,params=params,timeout=25); r.raise_for_status(); return r.json()
        except Exception as e: print("err",e,flush=True); time.sleep(5+5*i)
    raise RuntimeError('fail')
B0,T0=21626161+3600,datetime.datetime(2025,1,15,tzinfo=datetime.timezone.utc).timestamp()
out=[]
DEP='0x493c3b8240368e8343bcd42cac5f4b8b161c06d061710e542a72f06a40ddd9d1'
# sample every ~7 days from 2025-01-15 to 2026-11
t=T0
while t<datetime.datetime(2026,1,10,tzinfo=datetime.timezone.utc).timestamp():
    b=int(B0+(t-T0)/12.08)
    params={'block_number':b,'index':0}
    pts=[]
    for p in range(1):
        r=get('https://eth.blockscout.com/api/v2/addresses/0x3B4D794a66304F130a4Db8F2551B0070dfCf5ca7/logs',params)
        for x in r['items']:
            if x['topics'][0] in (DEP,'0x15dce32b28da4e9abe948d3acb53e6764159ef75b454aa1030604232a8d366bb'):
                idx=int(x['data'][2:66],16)
                if idx<2**40: pts.append((x['block_timestamp'],idx,'0x'+x['data'][66+24:130]))
        params=r['next_page_params']
        if not params: break
    if pts:
        mx=max(p[1] for p in pts)
        out.append({'target':datetime.datetime.utcfromtimestamp(t).isoformat(),'latest_ts':pts[0][0],'max_idx':mx,'n':len(pts)})
        print(out[-1],flush=True)
    else: print('none',datetime.datetime.utcfromtimestamp(t),flush=True)
    json.dump(out,open('cache/lighter_cal.json','w'),indent=1)
    t+=4*86400
