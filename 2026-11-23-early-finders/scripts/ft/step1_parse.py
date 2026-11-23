import json,glob,collections,sys
sys.path.insert(0,'.')
c=json.load(open('ft/cohort_ft.json')); A=set(a[2:] for a in c['A']); L=set(a[2:] for a in c['L'])
first={}  # (to)->{from:first_block}
for f in glob.glob('ft/out_*_*.jsonl'):
    for l in open(f):
        b,tok,fr,to,v=json.loads(l)
        if not to: continue
        d=first.setdefault(to,{})
        if fr not in d or b<d[fr]: d[fr]=b
rec=[]
for to,d in first.items():
    na=sum(1 for x in d if x in A); nl=sum(1 for x in d if x in L)
    rec.append((to,na,nl,min(d.values())))
rec.sort(key=lambda r:-r[1])
print('recipients',len(rec),'with >=5 A senders',sum(r[1]>=5 for r in rec),'>=3',sum(r[1]>=3 for r in rec))
json.dump(first,open('ft/first_by_recipient.json','w'))
json.dump([r for r in rec if r[1]>=3],open('ft/recips_ge3.json','w'))
