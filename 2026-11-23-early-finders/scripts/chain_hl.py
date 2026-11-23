import subprocess,time
def running(pat):
    out=subprocess.run(['ps','-axo','command'],capture_output=True,text=True).stdout.splitlines()
    return any(l.startswith('python3') and pat in l for l in out)
while running('hl_check.py cache/hlcheck_late_in'): time.sleep(15)
subprocess.run(['python3','hl_check.py','cache/hlcheck_ctrl_in.json','cache/hlcheck_ctrl.jsonl'])
print('HLDONE',flush=True)
