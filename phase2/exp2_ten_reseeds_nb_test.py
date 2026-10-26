#!/usr/bin/env python3
"""EXPERIMENT 2 (issue 3): 10 independent re-seeded train/test splits + Nadeau-Bengio corrected resampled t-test,
hybrid (fixed hyperparameters, validation early stopping) vs HistGradientBoosting. Also reports accuracy AND F1.
Give the hyperparameters with --hp (e.g. '{"blocks":3,"filters":49,"lstm":50,"gru":29,"dropout":0.272}').
"""
import json, sklearn, numpy as np
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier
from common import *
ap = common_args(__doc__); ap.add_argument('--hp', required=True); ap.add_argument('--reseeds', type=int, default=10)
ap.add_argument('--epochs', type=int, default=80); ap.add_argument('--patience', type=int, default=8)
a = ap.parse_args(); lab, order, drop = resolve(a); hp = json.loads(a.hp)
df, X, y, _ = load(a.csv, lab, drop, a.attack_values, a.max_rows); X = encode(X); y = y.values
rows = []
for s in range(100, 100 + a.reseeds):
    tr, te = split(len(X), y, 'random', s); Xtr, Xte, _ = prep(X.iloc[tr], X.iloc[te]); ytr, yte = y[tr], y[te]
    sub, val = train_test_split(np.arange(len(tr)), test_size=.2, stratify=ytr, random_state=s)
    m = fit(hp, Xtr[sub], ytr[sub], Xtr[val], ytr[val], a.epochs, a.patience, seed=s); ph = predict(m, Xte)
    g = HistGradientBoostingClassifier(random_state=s).fit(Xtr, ytr); pg = g.predict_proba(Xte)[:, 1]
    rows.append(dict(seed=s, hybrid=metrics(yte, ph > .5, ph), hgb=metrics(yte, pg > .5, pg), n_train=len(tr), n_test=len(te)))
    print(s, round(rows[-1]['hybrid']['accuracy'], 4), round(rows[-1]['hgb']['accuracy'], 4), flush=True)
def nb(metric):
    d = np.array([r['hgb'][metric] - r['hybrid'][metric] for r in rows]); k = len(d); c = 1 / k + rows[0]['n_test'] / rows[0]['n_train']
    t = d.mean() / np.sqrt(c * d.var(ddof=1)) if d.var(ddof=1) > 0 else np.inf
    return dict(mean_diff_hgb_minus_hybrid=d.mean(), t=t, df=k - 1, p=2 * stats.t.sf(abs(t), k - 1), hgb_wins=int((d > 0).sum()), k=k)
out = dict(sklearn=sklearn.__version__, rows=rows, nb_accuracy=nb('accuracy'), nb_f1=nb('f1'), nb_recall=nb('recall'))
print(json.dumps({k: v for k, v in out.items() if k.startswith('nb')}, indent=1)); save(f'{a.out}/exp2_{a.name}.json', out)
