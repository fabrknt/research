import json, math, sys, datetime
D=sys.argv[1]
def load(s,iv):
    r=json.load(open(f"{D}/{s}_{iv}.json"))["chart"]["result"][0]
    c=r["indicators"]["quote"][0]["close"]
    return {t:x for t,x in zip(r["timestamp"],c) if x}
def vol(series, per_year):
    r=[math.log(b/a) for a,b in zip(series,series[1:])]
    m=sum(r)/len(r)
    return math.sqrt(sum(x*x for x in r)/len(r)*per_year), len(r)
start=int(sys.argv[2]) if len(sys.argv)>2 else 1786060800  # 2026-08-03
spy=load("SPY","1d")
print("window from",datetime.datetime.utcfromtimestamp(start).date(),"daily closes, annualized (252)")
print(f"{'tkr':5} {'σ(stk/USD)':>11} {'σ(stk/SPY)':>11} {'ratio var':>9} {'corr':>6} n")
for s in ["NVDA","TSLA","PLTR","INTC","MSFT","HIMS","QQQ","SPY"]:
    x=load(s,"1d"); ts=sorted(t for t in x if t in spy and t>=start)
    a=[x[t] for t in ts]; b=[x[t]/spy[t] for t in ts]
    va,n=vol(a,252); vb,_=vol(b,252); vs,_=vol([spy[t] for t in ts],252)
    ra=[math.log(q/p) for p,q in zip(a,a[1:])]; rs=[math.log(spy[q]/spy[p]) for p,q in zip(ts,ts[1:])]
    ma=sum(ra)/len(ra); ms=sum(rs)/len(rs)
    cov=sum((u-ma)*(v-ms) for u,v in zip(ra,rs)); corr=cov/math.sqrt(sum((u-ma)**2 for u in ra)*sum((v-ms)**2 for v in rs))
    print(f"{s:5} {va:11.1%} {vb:11.1%} {(vb/va)**2:9.2f} {corr:6.2f} {n}  ret_usd={a[-1]/a[0]-1:+.1%} ret_spy={b[-1]/b[0]-1:+.1%}")
