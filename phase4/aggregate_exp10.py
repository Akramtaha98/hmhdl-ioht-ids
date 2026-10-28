"""Summarise exp10 (instrumented temporal-validation designs: 'tail' vs 'window'). Usage: python aggregate_exp10.py"""
import json,os,numpy as np
RES=os.path.join(os.path.dirname(os.path.abspath(__file__)),'results')
for ds in ['ECU','WUSTL']:
    d=json.load(open(f'{RES}/exp10_{ds}.json'))
    print('=====',ds)
    for des in ['tail','window']:
        R=[r for r in d['partA'] if r['design']==des]
        f=np.array
        h5=f([r['hybrid']['at_0_5']['accuracy'] for r in R])*100; g5=f([r['hgb']['at_0_5']['accuracy'] for r in R])*100
        ht=f([r['hybrid']['at_thr']['accuracy'] for r in R])*100; gt=f([r['hgb']['at_thr']['accuracy'] for r in R])*100
        ha=f([r['hybrid']['at_0_5']['roc_auc'] for r in R]); ga=f([r['hgb']['at_0_5']['roc_auc'] for r in R])
        print(des,'n_fit',R[0]['n_fit'],'n_val',R[0]['n_val'],'val attack share',round(R[0]['val_attack_share'],4),'best epoch',[r['best_epoch'] for r in R],'epochs run',[r['epochs_run'] for r in R])
        print('  hybrid@0.5 %.2f±%.2f [%.2f,%.2f]  hgb@0.5 %.2f±%.2f | hybrid@thr %.2f±%.2f [%.2f,%.2f]  hgb@thr %.2f±%.2f'%(h5.mean(),h5.std(ddof=1),h5.min(),h5.max(),g5.mean(),g5.std(ddof=1),ht.mean(),ht.std(ddof=1),ht.min(),ht.max(),gt.mean(),gt.std(ddof=1)))
        print('  ROC-AUC hybrid %.3f±%.3f  hgb %.3f±%.3f'%(ha.mean(),ha.std(ddof=1),ga.mean(),ga.std(ddof=1)))
        print('  hybrid test records above / equal to threshold',[(r['hybrid']['test_above_thr'],r['hybrid']['test_equal_thr']) for r in R])
