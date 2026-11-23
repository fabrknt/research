import subprocess,time
def running(pat):
    out=subprocess.run(['ps','-axo','command'],capture_output=True,text=True).stdout.splitlines()
    return any(l.startswith('python3') and pat in l for l in out)
while running('lighter_lookup.py cache/lookup_A'): time.sleep(15)
subprocess.run(['python3','lighter_lookup.py','cache/lookup_B.json'])
while running('hl_check.py') or running('chain_hl.py'): time.sleep(15)
subprocess.run(['python3','mk_lt.py'])
subprocess.run(['python3','lighter_lookup.py','cache/lookup_LC.json'])
print('ALLDONE',flush=True)
