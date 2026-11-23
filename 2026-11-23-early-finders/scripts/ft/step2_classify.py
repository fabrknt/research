import json,sys,os,time,re
sys.path.insert(0,'.')
from rpc import *
first=json.load(open('ft/first_by_recipient.json'))
c=json.load(open('ft/cohort_ft.json')); A=set(a[2:] for a in c['A'])
idx=json.load(open('ft/llama_addr_index.json'))
cands=[to for to,d in first.items() if sum(1 for x in d if x in A)>=2]
F='ft/classify.json'; res=json.load(open(F)) if os.path.exists(F) else {}
def ecall(to,sel):
    try:
        r=call('arb','eth_call',[{'to':to,'data':sel},'latest'])
        b=bytes.fromhex(r[2:])
        if len(b)>=96: n=int.from_bytes(b[32:64],'big'); return b[64:64+n].decode(errors='ignore')
        if len(b)==32: return b.rstrip(b'\0').decode(errors='ignore')
    except Exception: return None
todo=[a for a in cands if a not in res]
print('cands',len(cands),'todo',len(todo),flush=True)
for i in range(0,len(todo),20):
    ch=['0x'+a for a in todo[i:i+20]]
    for k in range(12):
        try:
            r=S.post(URLS['arb'],json=[{'jsonrpc':'2.0','id':j,'method':'eth_getCode','params':[a,'latest']} for j,a in enumerate(ch)],timeout=60).json()
            if isinstance(r,list) and all('result' in x for x in r): break
        except Exception: pass
        time.sleep(2+k)
    else: continue
    for x in r:
        a=ch[x['id']]; code=x['result']
        kind='eoa' if code=='0x' else ('7702' if code.startswith('0xef0100') else ('proxy1167' if len(code)<=92 else 'contract'))
        rec={'kind':kind,'llama':idx.get(a.lower(),[])}
        if kind in ('contract','proxy1167'):
            rec['name']=ecall(a,'0x06fdde03'); rec['symbol']=ecall(a,'0x95d89b41')
        res[a[2:]]=rec
    json.dump(res,open(F,'w')); print(i,flush=True)
    time.sleep(0.5)
json.dump(res,open(F,'w')); print('DONE')
