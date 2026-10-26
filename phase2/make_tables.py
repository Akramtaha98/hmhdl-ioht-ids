#!/usr/bin/env python3
"""Print compact summary tables from results/*.json (copy into the paper)."""
import glob, json, numpy as np
f = lambda v: f'{np.mean(v):.4f} ± {np.std(v, ddof=1) if len(v) > 1 else 0:.4f}'
for p in sorted(glob.glob('results/exp1_*.json')):
    d = json.load(open(p)); print('\n==', p)
    for m in ('lirs', 'random'):
        r = [x for x in d['runs'] if x['method'] == m]
        if r: print(f"{m:7s} val {f([x['best_search_val_acc'] for x in r])}  test acc {f([x['test']['accuracy'] for x in r])}  F1 {f([x['test']['f1'] for x in r])}  (n={len(r)})")
for p in sorted(glob.glob('results/exp2_*.json')):
    d = json.load(open(p)); print('\n==', p); [print(k, {a: round(b, 5) if isinstance(b, float) else b for a, b in d[k].items()}) for k in ('nb_accuracy', 'nb_f1', 'nb_recall')]
for p in sorted(glob.glob('results/exp3_*.json')):
    d = json.load(open(p)); print('\n==', p, 'attack share train/val/test', round(d['attack_share_train'], 3), round(d['attack_share_val'], 3), round(d['attack_share_test'], 3))
    for m in ('hybrid', 'hgb'):
        r = [x for x in d['reports'] if x['model'] == m]
        print(f"{m:7s} AUC {f([x['at_0_5']['roc_auc'] for x in r])} acc@0.5 {f([x['at_0_5']['accuracy'] for x in r])} acc@valthr {f([x['at_val_threshold']['accuracy'] for x in r])} ECE {f([x['ece'] for x in r])} KS {f([x['ks_train_vs_test_scores'] for x in r])}")
for p in sorted(glob.glob('results/exp5_*.json')):
    d = json.load(open(p)); print('\n==', p)
    for sp in ('random', 'temporal'):
        for m in sorted({x['model'] for x in d['runs']}):
            r = [x for x in d['runs'] if x['split'] == sp and x['model'] == m]
            if r: print(f"{sp:8s} {m:5s} acc {f([x['accuracy'] for x in r])} F1 {f([x['f1'] for x in r])} recall {f([x['recall'] for x in r])}")
