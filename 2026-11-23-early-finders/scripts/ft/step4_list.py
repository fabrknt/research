import json,sys,datetime; sys.path.insert(0,'.'); sys.path.insert(0,'ft')
import bts
from excl import label
L=json.load(open('ft/labels.json')); first=json.load(open('ft/first_by_recipient.json')); D=json.load(open('ft/deploy.json'))
AG=json.load(open('ft/age.json'))
c=json.load(open('ft/cohort_ft.json')); A=set(a[2:] for a in c['A'])
k=json.load(open('ft/step3_in.json'))
NOV=145877584; DEC31=int(bts.A[0][0]) # placeholder
import bisect
def blk_at(ts):
    i=bisect.bisect_left([a[1] for a in bts.A],ts); (b0,t0),(b1,t1)=bts.A[i-1],bts.A[i]; return int(b0+(ts-t0)*(b1-b0)/(t1-t0))
JAN25=blk_at(datetime.datetime(2025,1,1,tzinfo=datetime.timezone.utc).timestamp())
rows=[]
for a in k:
    birth=D.get(a) or (AG.get(a,{}).get('first_log'))
    if AG.get(a,{}).get('kind')=='eoa': continue
    if not birth: continue
    if not (NOV<=birth<JAN25): continue
    end=blk_at(bts.ts(birth)+60*86400)
    d=first[a[2:]]
    early=sum(1 for x,b in d.items() if x in A and b<=end)
    tot=sum(1 for x in d if x in A)
    rows.append({'a':a,'birth':datetime.datetime.utcfromtimestamp(bts.ts(birth)).strftime('%Y-%m-%d'),'early':early,'totA':tot,'label':label(L,a)})
rows.sort(key=lambda r:-r['early'])
json.dump(rows,open('ft/new_cands.json','w'),indent=0)
if __name__=='__main__':
    print('new candidates',len(rows),'crossers(>=5 early)',sum(r['early']>=5 for r in rows))
    for r in rows: print(r['a'][:12],r['birth'],r['early'],r['totA'],r['label'][:80])
