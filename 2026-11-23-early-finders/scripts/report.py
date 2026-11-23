import json,sys,os,collections; sys.path.insert(0,'.')
from analyze import *
e=json.load(open('cache/early_sets.json')); hf=json.load(open('cache/hl_first.json'))
lc=json.load(open('cache/late_cand.json'))
late_true=[json.loads(l)['a'] for l in open('cache/hlcheck_late.jsonl') if json.loads(l)['n']==0]
late_chk=[json.loads(l)['a'] for l in open('cache/hlcheck_late.jsonl')]
ctrl_rows=[json.loads(l) for l in open('cache/hlcheck_ctrl.jsonl')] if os.path.exists('cache/hlcheck_ctrl.jsonl') else []
ctrl_true=[r['a'] for r in ctrl_rows if r['n']==0]
B_full=[a for a in hf['first_any'] if D('2023-11-01')<=hf['first_any'][a]<D('2024-05-01') and a in hf['first100'] and hf['first100'][a]<D('2024-05-01')]
groups={
 'A_early_HL_preNov2023 (sample)':e['A_sample'][:2000],
 'B_HL_points_S1_Nov23-Apr24 (sample)':e['B_sample'][:600],
 'Late_HL_first_2025H1':late_true,
 'Control_Arb_Oct2023_never_HL':ctrl_true,
}
def iseoa(a): return code.get(a) in ('eoa','7702')
out={}
for eo in [False,True]:
  for nm,g in groups.items():
    gg=[a for a in g if (iseoa(a) if eo else True) and a in look]
    o=outcomes(gg); n=len(gg)
    out[(nm,eo)]=o
    pL=wilson(o['lE'],n); pV=wilson(o['vE'],n); pLA=wilson(o['lA'],n); pVA=wilson(o['vA'],n); pLS=wilson(o['lS'],n); pVS=wilson(o['vS'],n)
    print(f"{'EOA ' if eo else 'ALL '}{nm}: n={n} | Lighter pre-public {o['lE']} {pL[0]:.3%} [{pL[1]:.3%},{pL[2]:.3%}] | Lighter pre-Jun25 {o['lS']} {pLS[0]:.3%} | Lighter ever {o['lA']} {pLA[0]:.3%} | Var pre-points {o['vE']} {pV[0]:.3%} [{pV[1]:.3%},{pV[2]:.3%}] | Var pre-Sep25 {o['vS']} {pVS[0]:.3%} | Var ever {o['vA']} {pVA[0]:.3%} | both-early {o['both']} | leadL med {o['leadL'][0]:.0f}d [{o['leadL'][1]:.0f},{o['leadL'][2]:.0f}] | leadV(vs public) {o['leadV'][0]:.0f}d [{o['leadV'][1]:.0f},{o['leadV'][2]:.0f}] ; vs points {o['leadVp'][0]:.0f}d")
  base=[k for k in groups if k.startswith('Late')][0]
  for nm in groups:
    if nm==base: continue
    a=out[(nm,eo)]; b=out[(base,eo)]
    print('  lift',nm,'vs Late: Lighter',['%.2f'%x for x in rr(a['lE'],a['n'],b['lE'],b['n'])],'Var',['%.2f'%x for x in rr(a['vE'],a['n'],b['vE'],b['n'])], 'Lighter-ever',['%.2f'%x for x in rr(a['lA'],a['n'],b['lA'],b['n'])])
print('late checked',len(late_chk),'true-new',len(late_true),'ctrl checked',len(ctrl_rows),'never-HL',len(ctrl_true))
print('IDX_L_PUBLIC',IDX_L_PUBLIC,'IDX_L_STRICT',IDX_L_STRICT)
# size-matched: first qualifying deposit >= $1000
lcand=json.load(open('cache/late_cand.json'))
A1k=[a for a in groups['A_early_HL_preNov2023 (sample)'] if a in look and hf['amt100'].get(a,0)>=1000]
L1k=[a for a in late_true if a in look and lcand[a]['amt']>=1000]
A_small=[a for a in groups['A_early_HL_preNov2023 (sample)'] if a in look and hf['amt100'].get(a,0)<1000]
L_small=[a for a in late_true if a in look and lcand[a]['amt']<1000]
for nm,g in [('A first dep>=1k',A1k),('Late first dep>=1k',L1k),('A first dep 100-1k',A_small),('Late first dep 100-1k',L_small)]:
    o=outcomes(g); n=len(g); pL=wilson(o['lE'],n); pV=wilson(o['vE'],n)
    print(f"SIZE {nm}: n={n} Lighter-early {o['lE']} {pL[0]:.1%} [{pL[1]:.1%},{pL[2]:.1%}] Var-early {o['vE']} {pV[0]:.1%} [{pV[1]:.1%},{pV[2]:.1%}]")
import statistics as st
print('median first deposit A', st.median(hf['amt100'][a] for a in groups['A_early_HL_preNov2023 (sample)'] if a in look), 'late', st.median(lcand[a]['amt'] for a in late_true if a in look))
# save cohorts
cohorts={'definitions':{
 'A_early_HL':'first HL bridge deposit >=$100 before 2023-11-01 (old bridge 0xc67e..73a4, USDC.e). Full list; Lighter-tested subset = A_sample[:2000]',
 'B_points_S1':'first HL deposit 2023-11-01..2024-04-30, with a >=$100 deposit before 2024-05-01 (random sample)',
 'Late_HL_2025H1':'first-ever HL ledger event (HL API) at/after a >=$100 Bridge2 deposit on one of six sampled days (15th of Jan..Jun 2025)',
 'Control_never_HL':'EOA that sent >=$100 USDC/USDC.e on Arbitrum during 3h windows on 2023-10-10 and 2023-10-20, with zero HL ledger events ever'},
 'A_early_HL_full':e['A100_all'],'A_early_HL_lighter_tested':[a for a in e['A_sample'][:2000] if a in look],
 'B_points_S1_sample':[a for a in e['B_sample'][:600] if a in look],'Late_HL_2025H1':late_true,'Control_never_HL':ctrl_true,
 'A_early_found_Lighter_prepublic':out[(list(groups)[0],False)]['lE_list'],'A_early_found_Variational_prepoints':out[(list(groups)[0],False)]['vE_list']}
json.dump(cohorts,open('cohorts.json','w'),indent=0)
