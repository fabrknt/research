import json
out=[]
for f,thr in [('cache/hlcheck_late.jsonl',None),('cache/hlcheck_ctrl.jsonl',None)]:
    for l in open(f):
        r=json.loads(l)
        if r['n']==0: out.append(r['a'])
json.dump(out,open('cache/lookup_LC.json','w')); print(len(out))
