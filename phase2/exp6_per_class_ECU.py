#!/usr/bin/env python3
"""EXPERIMENT 6 (issues 7-8): per-attack-subtype results for ECU-IoHT under the random AND temporal split (hybrid vs HistGB vs RF),
with the sklearn version recorded in the output (run EVERYTHING in one environment: pip install -r requirements.txt).
Subtypes absent from the training partition (typical under a temporal split) are flagged: their recall cannot be learned.
"""
import json, sklearn, numpy as np
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from common import *
ap = common_args(__doc__); ap.add_argument('--hp', required=True); ap.add_argument('--epochs', type=int, default=80); ap.add_argument('--seed', type=int, default=42)
a = ap.parse_args(); lab, order, drop = resolve(a); hp = json.loads(a.hp); out = dict(sklearn=sklearn.__version__)
for kind in ('random', 'temporal'):
    df, X, y, sub_t = load(a.csv, lab, drop + ([order] if kind == 'temporal' else []), a.attack_values, a.max_rows, sub_col=DATASETS['ECU']['sub']); X = encode(X); y = y.values
    tr, te = split(len(X), y, kind, a.seed, df[order]); Xtr, Xte, _ = prep(X.iloc[tr], X.iloc[te]); ytr, yte = y[tr], y[te]
    if kind == 'temporal': k = int(.8 * len(tr)); sub, val = np.arange(k), np.arange(k, len(tr))
    else: sub, val = train_test_split(np.arange(len(tr)), test_size=.2, stratify=ytr, random_state=a.seed)
    m = fit(hp, Xtr[sub], ytr[sub], Xtr[val], ytr[val], a.epochs, 8, seed=a.seed)
    P = {'hybrid': predict(m, Xte) > .5, 'hgb': HistGradientBoostingClassifier(random_state=a.seed).fit(Xtr, ytr).predict(Xte),
         'rf': RandomForestClassifier(300, n_jobs=-1, random_state=a.seed).fit(Xtr, ytr).predict(Xte)}
    ste, str_ = sub_t[te], sub_t[tr]; rows = []
    for t in np.unique(ste):
        msk = (ste == t) & (yte == 1)
        if msk.sum() == 0: continue
        rows.append(dict(subtype=t, n_test=int(msk.sum()), n_train=int((str_ == t).sum()),
                                         **{f'recall_{k}': float(v[msk].mean()) for k, v in P.items()}))
    nm = (y[te] == 0)
    out[kind] = dict(per_subtype=rows, specificity={k: float(1 - v[nm].mean()) for k, v in P.items()}, overall={k: metrics(yte, v) for k, v in P.items()})
    print(kind); [print('  ', r) for r in rows]
save(f'{a.out}/exp6_ECU_per_class.json', out)
