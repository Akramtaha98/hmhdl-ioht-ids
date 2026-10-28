"""Summarise exp11 (full tune-and-train repeat on 5 reseeded splits) with the Nadeau-Bengio corrected resampled t-test. Usage: python aggregate_exp11.py"""
import json,os,numpy as np
from scipy import stats
RES=os.path.join(os.path.dirname(os.path.abspath(__file__)),'results')
def load(ds):
    if ds=='ECU':
        r=[]
        for t in 'abc': r+=json.load(open(f'{RES}/exp11_ECU_{t}.json'))['runs']
        return r
    return json.load(open(f'{RES}/exp11_WUSTL_all.json'))['runs']
for ds in ['ECU','WUSTL']:
    R=load(ds); print('=====',ds,len(R),'splits, seeds',[r['outer_seed'] for r in R])
    for m in ['lirs','random','fixed_table_iv','hgb_fit_subpartition','hgb_full_train']:
        s=f'{m:22s}'
        for met in ['accuracy','f1','recall','roc_auc']:
            v=np.array([r[m]['test'][met] for r in R]); s+=f' {met} {v.mean():.4f}±{v.std(ddof=1):.4f} |'
        print(s)
    k=len(R); ntr=R[0]['n_fit']+R[0]['n_val']; nte=R[0]['n_test']
    def nb(a,b):
        d=np.array(a)-np.array(b); var=d.var(ddof=1)
        t=d.mean()/np.sqrt((1/k+nte/ntr)*var); p=2*stats.t.sf(abs(t),k-1)
        return f'diff {d.mean()*100:+.2f} pts  t={t:.2f}  p_NB={p:.3g}  wins={int((d>0).sum())}/{k}'
    for met in ['accuracy','f1','recall']:
        g=lambda m:[r[m]['test'][met] for r in R]
        print(met)
        print('  HGB(full)-LIRS  ',nb(g('hgb_full_train'),g('lirs')))
        print('  HGB(full)-random',nb(g('hgb_full_train'),g('random')))
        print('  LIRS-random     ',nb(g('lirs'),g('random')))
        print('  fixed-LIRS      ',nb(g('fixed_table_iv'),g('lirs')))
