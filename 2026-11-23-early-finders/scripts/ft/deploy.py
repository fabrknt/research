import json,requests,os,sys
sys.path.insert(0,'ft')
from excl import *
S=requests.Session()
L=json.load(open('ft/labels.json')); first=json.load(open('ft/first_by_recipient.json'))
c=json.load(open('ft/cohort_ft.json')); A=set(a[2:] for a in c['A'])
cands=['0x'+to for to,d in first.items() if sum(1 for x in d if x in A)>=2]
keep=[a for a in cands if a in L and not excluded(L,a)]
json.dump(keep,open('ft/step3_in.json','w'))
F='ft/deploy.json'; D=json.load(open(F)) if os.path.exists(F) else {}
for a in keep:
    if a in D: continue
    try:
        r=S.get(f'https://sourcify.dev/server/v2/contract/42161/{a}',params={'fields':'deployment'},timeout=30)
        D[a]=int(r.json()['deployment']['blockNumber']) if r.status_code==200 and r.json().get('deployment',{}).get('blockNumber') else None
    except Exception: D[a]=None
json.dump(D,open(F,'w')); print('kept',len(keep),'deploy known',sum(D.get(a) is not None for a in keep))
