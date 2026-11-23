import json,math,random,datetime,statistics,os,sys
D=lambda s: datetime.datetime.strptime(s,'%Y-%m-%d').replace(tzinfo=datetime.timezone.utc).timestamp()
L_PUBLIC=D('2025-10-02'); V_POINTS=D('2025-12-17'); V_PUBLIC=D('2026-11-11'); V_STRICT=D('2025-09-01'); L_STRICT=D('2025-06-01')
cal=json.load(open('cache/lighter_cal.json'))
pts=[]; mx=0
for c in cal:
    t=datetime.datetime.fromisoformat(c['latest_ts'].replace('Z','+00:00')).timestamp()
    mx=max(mx,c['max_idx']); pts.append((t,mx))
def idx_at(t):
    best=0
    for tt,m in pts:
        if tt<=t: best=m
    return best
def time_of_idx(i):
    # first calibration time where envelope >= i (upper bound on creation time), interpolate
    prev=(pts[0][0]-4*86400,0)
    for tt,m in pts:
        if m>=i:
            t0,m0=prev
            return t0+(tt-t0)*((i-m0)/max(1,(m-m0)))
        prev=(tt,m)
    return None
IDX_L_PUBLIC=idx_at(L_PUBLIC); IDX_L_STRICT=idx_at(L_STRICT)
look={}
for l in open('cache/lighter_lookup.jsonl'):
    r=json.loads(l)
    if 'err' not in r: look[r['a'].lower()]=r
var=json.load(open('cache/var_users.json'))
code=json.load(open('cache/is_contract.json')) if os.path.exists('cache/is_contract.json') else {}
def wilson(k,n,z=1.96):
    if n==0: return (float('nan'),)*3
    p=k/n; d=1+z*z/n; c=(p+z*z/(2*n))/d; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return p,c-h,c+h
def rr(k1,n1,k0,n0):
    if k1==0 or k0==0: 
        k1+=.5;k0+=.5;n1+=1;n0+=1
    r=(k1/n1)/(k0/n0); se=math.sqrt(1/k1-1/n1+1/k0-1/n0)
    return r,r*math.exp(-1.96*se),r*math.exp(1.96*se)
def boot_median(xs,B=2000):
    if len(xs)<3: return (statistics.median(xs) if xs else float('nan'),float('nan'),float('nan'))
    random.seed(1); ms=sorted(statistics.median(random.choices(xs,k=len(xs))) for _ in range(B))
    return statistics.median(xs),ms[int(.025*B)],ms[int(.975*B)]
def outcomes(addrs):
    res={}
    lk=[a for a in addrs if a in look]
    n=len(lk)
    lE=[a for a in lk if look[a].get('found') and look[a]['main_idx']<=IDX_L_PUBLIC]
    lS=[a for a in lk if look[a].get('found') and look[a]['main_idx']<=IDX_L_STRICT]
    lA=[a for a in lk if look[a].get('found')]
    vE=[a for a in addrs if a in var and var[a]['ts']<V_POINTS]
    vS=[a for a in addrs if a in var and var[a]['ts']<V_STRICT]
    vA=[a for a in addrs if a in var]
    both=[a for a in lE if a in var and var[a]['ts']<V_POINTS]
    leadL=[(L_PUBLIC-time_of_idx(look[a]['main_idx']))/86400 for a in lE if time_of_idx(look[a]['main_idx'])]
    leadV=[(V_PUBLIC-var[a]['ts'])/86400 for a in vE]
    leadVp=[(V_POINTS-var[a]['ts'])/86400 for a in vE]
    return dict(n_l=n,n=len(addrs),lE=len(lE),lS=len(lS),lA=len(lA),vE=len(vE),vS=len(vS),vA=len(vA),both=len(both),leadL=boot_median(leadL),leadV=boot_median(leadV),leadVp=boot_median(leadVp),lE_list=lE,vE_list=vE)
