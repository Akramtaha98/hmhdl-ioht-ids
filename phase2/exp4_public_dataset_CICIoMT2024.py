#!/usr/bin/env python3
"""EXPERIMENT 4 (issue 5): replace DSICU by a PUBLIC benchmark, CICIoMT2024 (Univ. of New Brunswick / CIC).
Download the CSV folder (WiFi_and_MQTT / Bluetooth ... 'train' and 'test' CSVs) and pass --path to a folder or a single CSV.
Binary task: label 'Benign' vs everything else. --per-file caps rows per CSV for CPU feasibility (default 20,000).
Random split-before-fit (70/30) + the cleaner PREDEFINED train/test split if the folder has train/ and test/ sub-folders.
Runs: hybrid (search budget as in exp1, validation early stopping), LR, RF, HistGB, MLP. Per-attack-family recall is saved.
"""
import os, glob, json, sklearn, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.neural_network import MLPClassifier
from common import *
ap = argparse.ArgumentParser(); ap.add_argument('--path', required=True); ap.add_argument('--label-col', default='label')
ap.add_argument('--per-file', type=int, default=20000); ap.add_argument('--budget', type=int, default=60)
ap.add_argument('--quick-epochs', type=int, default=4); ap.add_argument('--epochs', type=int, default=60); ap.add_argument('--out', default='results')
ap.add_argument('--seeds', nargs='*', type=int, default=[42, 43, 44])
a = ap.parse_args()
def read(p):
    fs = sorted(glob.glob(os.path.join(p, '**', '*.csv'), recursive=True)) if os.path.isdir(p) else [p]; parts = []
    for f in fs:
        d = pd.read_csv(f, low_memory=False); d.columns = [c.strip() for c in d.columns]
        d['_family'] = os.path.basename(f).replace('.csv', ''); parts.append(d.sample(min(len(d), a.per_file), random_state=0))
    return pd.concat(parts, ignore_index=True)
df = read(a.path); lab = a.label_col if a.label_col in df.columns else next(c for c in df.columns if c.lower() == 'label')
y = (~df[lab].astype(str).str.lower().str.contains('benign')).astype(int).values; fam = df[lab].astype(str).values
X = encode(df.drop(columns=[lab, '_family'])); print(len(X), 'rows, attack share', y.mean().round(3), 'features', X.shape[1])
out = dict(sklearn=sklearn.__version__, rows=len(X), runs=[])
for s in a.seeds:
    tr, te = split(len(X), y, 'random', s); Xtr, Xte, _ = prep(X.iloc[tr], X.iloc[te]); ytr, yte = y[tr], y[te]
    sub, val = train_test_split(np.arange(len(tr)), test_size=.2, stratify=ytr, random_state=s)
    res = dict(seed=s)
    hp, _ = search('lirs', a.budget, Xtr[sub], ytr[sub], Xtr[val], ytr[val], a.quick_epochs, s)
    m = fit(hp, Xtr[sub], ytr[sub], Xtr[val], ytr[val], a.epochs, 8, seed=s); p = predict(m, Xte); res['hybrid'] = dict(hp=hp, **metrics(yte, p > .5, p))
    pred = {'hybrid': p > .5}
    for nm, mdl in (('LR', LogisticRegression(max_iter=1000)), ('RF', RandomForestClassifier(300, n_jobs=-1, random_state=s)),
                    ('HGB', HistGradientBoostingClassifier(random_state=s)), ('MLP', MLPClassifier((128, 64), early_stopping=True, random_state=s))):
        mdl.fit(Xtr, ytr); sc = mdl.predict_proba(Xte)[:, 1]; res[nm] = metrics(yte, sc > .5, sc); pred[nm] = sc > .5
    fte = fam[te]; res['per_family_recall'] = {f: {k: float(pred[k][fte == f].mean()) for k in pred} for f in np.unique(fte) if f.lower() != 'benign'}
    out['runs'].append(res); print(s, {k: round(v['accuracy'], 4) for k, v in res.items() if isinstance(v, dict) and 'accuracy' in v}, flush=True)
    save(f'{a.out}/exp4_CICIoMT2024.json', out)
