import json,sys,os,requests,time
sys.path.insert(0,'.')
from rpc import *
SS=requests.Session()
rows=json.load(open('ft/new_cands.json')); idx=json.load(open('ft/llama_addr_index.json'))
F='ft/enrich.json'; E=json.load(open(F)) if os.path.exists(F) else {}
IMPL='0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc'; BEACON='0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeee59ff6cb3582b35133d50'
def ecall(to,sel):
    try:
        r=call('arb','eth_call',[{'to':to,'data':sel},'latest']); b=bytes.fromhex(r[2:])
        if len(b)>=96: n=int.from_bytes(b[32:64],'big'); return b[64:64+n].decode(errors='ignore')
        if len(b)==32: return b.rstrip(b'\0').decode(errors='ignore') or ('0x'+b[-20:].hex())
    except Exception: return None
def sname(a):
    try:
        j=SS.get(f'https://sourcify.dev/server/v2/contract/42161/{a}',params={'fields':'compilation'},timeout=30)
        return j.json().get('compilation',{}).get('name') if j.status_code==200 else None
    except Exception: return None
for r in rows:
    a=r['a']
    if a in E: continue
    e={}
    s=call('arb','eth_getStorageAt',[a,IMPL,'latest']); impl='0x'+s[-40:] if int(s,16) else None
    if not impl:
        s=call('arb','eth_getStorageAt',[a,BEACON,'latest'])
        if int(s,16):
            b='0x'+s[-40:]; impl=ecall(b,'0x5c60da1b')
    e['impl']=impl; e['impl_name']=sname(impl) if impl and impl.startswith('0x') and len(impl)==42 else None
    e['name']=ecall(a,'0x06fdde03'); e['symbol']=ecall(a,'0x95d89b41')
    e['llama']=sorted(set(idx.get(a.lower(),[])+(idx.get(impl.lower(),[]) if impl and len(impl)==42 else [])))
    E[a]=e; json.dump(E,open(F,'w')); print(a[:12],e,flush=True)
print('DONE')
