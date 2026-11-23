import subprocess,time
def running(pat):
    out=subprocess.run(['ps','-axo','command'],capture_output=True,text=True).stdout.splitlines()
    return any(l.startswith('python3') and pat in l for l in out)
while running('farmers.py') or running('var_verify.py'): time.sleep(15)
subprocess.run(['python3','codecheck.py','cache/code_in.json'])
print('CODEDONE',flush=True)
