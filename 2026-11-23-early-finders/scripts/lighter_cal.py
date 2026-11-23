import requests,json,datetime,time,sys
S=requests.Session()
_get=S.get
def g(*a,**k):
    for i in range(6):
        try:
            r=_get(*a,**k); r.raise_for_status(); return r
        except Exception as e: time.sleep(5+5*i)
    raise RuntimeError('fail')
S.get=g
def bno(ts):
    r=S.get(f'https://eth.blockscout.com/api?module=block&action=getblocknobytime&timestamp={ts}&closest=before',timeout=60).json()
    return int(r['result']['blockNumber'])
out={}
dates=sys.argv[1:]
for d in dates:
    ts=int(datetime.datetime.strptime(d,'%Y-%m-%d').replace(tzinfo=datetime.timezone.utc).timestamp())
    b=bno(ts)
    # page backwards from block b: logs with block<=b
    params={'block_number':b,'index':0}
    idxs=[];addrs=[]
    for p in range(6):
        r=S.get('https://eth.blockscout.com/api/v2/addresses/0x3B4D794a66304F130a4Db8F2551B0070dfCf5ca7/logs',params=params,timeout=60).json()
        for x in r['items']:
            if x['topics'][0]=='0x493c3b8240368e8343bcd42cac5f4b8b161c06d061710e542a72f06a40ddd9d1':
                idx=int(x['data'][2:66],16); idxs.append(idx); addrs.append('0x'+x['data'][66+24:130])
        params=r['next_page_params']
        if not params: break
        time.sleep(0.5)
    small=[i for i in idxs if i<2**40]
    out[d]={'block':b,'n':len(idxs),'max_idx':max(small) if small else None,'sample':sorted(small)[-5:],'big':len(idxs)-len(small)}
    print(d,out[d],flush=True)
json.dump(out,open('cache/lighter_cal.json','w'),indent=1)
