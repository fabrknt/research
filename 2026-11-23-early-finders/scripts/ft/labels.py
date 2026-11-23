import json,os,time,requests
first=json.load(open('ft/first_by_recipient.json'))
c=json.load(open('ft/cohort_ft.json')); A=set(a[2:] for a in c['A'])
cands=['0x'+to for to,d in first.items() if sum(1 for x in d if x in A)>=2]
F='ft/labels.json'; L=json.load(open(F)) if os.path.exists(F) else {}
S=requests.Session()
todo=[a for a in cands if a not in L]
print(len(cands),len(todo),flush=True)
for i in range(0,len(todo),40):
    ch=todo[i:i+40]
    try:
        r=S.get('https://metadata.services.blockscout.com/api/v1/metadata',params={'addresses':','.join(ch),'chainId':42161},timeout=40).json()['addresses']
    except Exception as e: r={}
    rl={k.lower():v for k,v in r.items()}
    for a in ch:
        tags=rl.get(a,{}).get('tags',[])
        L.setdefault(a,{})['tags']=[(t.get('name'),t.get('tagType'),(json.loads(t['meta']).get('projectName') if t.get('meta') else None)) for t in tags]
    for a in ch:
        try:
            j=S.get(f'https://sourcify.dev/server/v2/contract/42161/{a}',params={'fields':'compilation'},timeout=30)
            L[a]['sourcify']=j.json().get('compilation',{}).get('name') if j.status_code==200 else None
        except Exception: L[a]['sourcify']=None
    json.dump(L,open(F,'w')); print(i,flush=True)
print('DONE')
