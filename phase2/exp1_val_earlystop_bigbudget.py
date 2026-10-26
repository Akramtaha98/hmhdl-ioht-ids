#!/usr/bin/env python3
"""EXPERIMENT 1 (issue 1): validation-based early stopping + larger tuning budget, LIRS vs random search.

* 20% of the TRAIN partition = validation set (stratified). Search fitness AND early stopping use it. Test is used once.
* Budget default 100 candidates x 5 quick epochs (paper: 42 x 3). Same budget for LIRS and random.
* --search-seeds independent repeats of each search; the best-by-validation config of each repeat is trained and tested.
Output: results/exp1_<NAME>.json (per repeat: best hp, val acc, test metrics)
"""
import sklearn, numpy as np, time
from common import *
ap = common_args(__doc__); ap.add_argument('--budget', type=int, default=100); ap.add_argument('--quick-epochs', type=int, default=5)
ap.add_argument('--search-seeds', nargs='*', type=int, default=[42, 43, 44, 45, 46]); ap.add_argument('--epochs', type=int, default=80)
ap.add_argument('--patience', type=int, default=8); ap.add_argument('--split', default='random', choices=['random', 'temporal'])
a = ap.parse_args(); lab, order, drop = resolve(a)
df, X, y, _ = load(a.csv, lab, drop + ([order] if a.split == 'temporal' and order else []), a.attack_values, a.max_rows)
X = encode(X); y = y.values
tr, te = split(len(X), y, a.split, 42, df[order] if order else None)
Xtr, Xte, _ = prep(X.iloc[tr], X.iloc[te]); ytr, yte = y[tr], y[te]
if a.split == 'temporal': k = int(.8 * len(tr)); sub, val = np.arange(k), np.arange(k, len(tr))     # chronological validation tail
else: sub, val = train_test_split(np.arange(len(tr)), test_size=.2, stratify=ytr, random_state=0)
out = dict(sklearn=sklearn.__version__, args=vars(a), runs=[])
for method in ('lirs', 'random'):
    for s in a.search_seeds:
        t0 = time.time(); hp, hist = search(method, a.budget, Xtr[sub], ytr[sub], Xtr[val], ytr[val], a.quick_epochs, s)
        m = fit(hp, Xtr[sub], ytr[sub], Xtr[val], ytr[val], a.epochs, a.patience, seed=s)
        pv = predict(m, Xtr[val]); pt = predict(m, Xte)
        r = dict(method=method, seed=s, hp=hp, best_search_val_acc=1 - min(hist), val=metrics(ytr[val], pv > .5, pv),
                 test=metrics(yte, pt > .5, pt), minutes=(time.time() - t0) / 60, history=hist)
        out['runs'].append(r); print(method, s, hp, 'val', round(r['val']['accuracy'], 4), 'test', round(r['test']['accuracy'], 4), flush=True)
        save(f'{a.out}/exp1_{a.name}_{a.split}.json', out)
