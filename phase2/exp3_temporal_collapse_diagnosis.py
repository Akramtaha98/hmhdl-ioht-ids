#!/usr/bin/env python3
"""EXPERIMENT 3 (issue 4): why does the hybrid collapse under the temporal split? Threshold / calibration / shift analysis.
Chronological split (earliest 70% train, latest 30% test, order column EXCLUDED from inputs). Validation = last 20% of train
(chronological). For hybrid and HistGB reports: AUC, PR-AUC (threshold-free), accuracy@0.5, accuracy/F1/recall at the threshold
chosen on validation, Brier, ECE, score distribution by class, KS shift between train and test scores, attack share per partition,
plus a reliability table. If AUC stays high while accuracy@0.5 collapses => miscalibration / threshold shift, not lost signal.
"""
import json, sklearn, numpy as np
from scipy.stats import ks_2samp
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import brier_score_loss, precision_recall_curve
from common import *
ap = common_args(__doc__); ap.add_argument('--hp', required=True); ap.add_argument('--epochs', type=int, default=80)
ap.add_argument('--patience', type=int, default=8); ap.add_argument('--seeds', nargs='*', type=int, default=[42, 43, 44])
a = ap.parse_args(); lab, order, drop = resolve(a); hp = json.loads(a.hp)
df, X, y, sub_t = load(a.csv, lab, drop + [order], a.attack_values, a.max_rows); X = encode(X); y = y.values
tr, te = split(len(X), y, 'temporal', order=df[order]); Xtr, Xte, _ = prep(X.iloc[tr], X.iloc[te]); ytr, yte = y[tr], y[te]
k = int(.8 * len(tr)); sub, val = np.arange(k), np.arange(k, len(tr))
def ece(y, s, b=10):
    q = np.minimum((s * b).astype(int), b - 1); return sum(abs(y[q == i].mean() - s[q == i].mean()) * (q == i).mean() for i in range(b) if (q == i).any())
def rel(y, s, b=10):
    q = np.minimum((s * b).astype(int), b - 1); return [dict(bin=i, n=int((q == i).sum()), mean_score=float(s[q == i].mean()), attack_rate=float(y[q == i].mean())) for i in range(b) if (q == i).any()]
def thr_best_f1(y, s):
    p, r, t = precision_recall_curve(y, s); f = 2 * p * r / (p + r + 1e-12); return float(t[np.nanargmax(f[:-1])])
def report(name, sv, st, str_):
    th = thr_best_f1(ytr[val], sv)
    return dict(model=name, threshold_from_val=th, at_0_5=metrics(yte, st > .5, st), at_val_threshold=metrics(yte, st > th, st),
                brier=brier_score_loss(yte, st), ece=ece(yte, st), mean_score_attack=float(st[yte == 1].mean()), mean_score_normal=float(st[yte == 0].mean()),
                ks_train_vs_test_scores=float(ks_2samp(str_, st).statistic), reliability=rel(yte, st))
out = dict(sklearn=sklearn.__version__, attack_share_train=float(ytr.mean()), attack_share_test=float(yte.mean()),
           attack_share_val=float(ytr[val].mean()), reports=[])
for s in a.seeds:
    m = fit(hp, Xtr[sub], ytr[sub], Xtr[val], ytr[val], a.epochs, a.patience, seed=s)
    out['reports'].append(dict(seed=s, **report('hybrid', predict(m, Xtr[val]), predict(m, Xte), predict(m, Xtr[sub]))))
    g = HistGradientBoostingClassifier(random_state=s).fit(Xtr[sub], ytr[sub])
    out['reports'].append(dict(seed=s, **report('hgb', g.predict_proba(Xtr[val])[:, 1], g.predict_proba(Xte)[:, 1], g.predict_proba(Xtr[sub])[:, 1])))
    for r in out['reports'][-2:]: print(s, r['model'], 'AUC', round(r['at_0_5']['roc_auc'], 4), 'acc@.5', round(r['at_0_5']['accuracy'], 4),
                                       'acc@val-thr', round(r['at_val_threshold']['accuracy'], 4), 'ECE', round(r['ece'], 4), flush=True)
save(f'{a.out}/exp3_{a.name}.json', out)
