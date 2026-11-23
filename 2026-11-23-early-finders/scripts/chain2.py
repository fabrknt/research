import subprocess,time
def running(pat):
    out=subprocess.run(['ps','-axo','command'],capture_output=True,text=True).stdout.splitlines()
    return any(l.startswith('python3') and pat in l for l in out)
while running('chain_hl.py') or running('hl_check.py'): time.sleep(15)
subprocess.run(['python3','hl_check.py','cache/hlcheck_late2_in.json','cache/hlcheck_late.jsonl'])
import json
o=[json.loads(l)['a'] for l in open('cache/hlcheck_late.jsonl') if json.loads(l)['n']==0]
json.dump(o,open('cache/lookup_late.json','w'))
while running('lighter_lookup.py'): time.sleep(15)
subprocess.run(['python3','lighter_lookup.py','cache/lookup_late.json'])
print('LATE2DONE',flush=True)
