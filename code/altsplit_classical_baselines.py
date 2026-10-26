"""Classical baselines (random forest, histogram gradient boosting) on the SAME alternative splits
used by sensitivity_split_v2.py (temporal for ECU-IoHT / WUSTL-EHMS-2020, flow-grouped for DSICU,
identifier-like fields excluded as features, preprocessing fit on the training partition only).

Usage (from the repo root):  python3 code/altsplit_classical_baselines.py [ECU-IoHT WUSTL-EHMS-2020 DSICU]
Writes results/{Dataset}_altsplit_baselines.json and prints a summary table.
Needs data/ECU_IoHT.csv, data/wustl-ehms-2020.csv, data/dsicu_mi.csv. Runs in minutes on CPU.
"""
import os, sys, json
from unittest.mock import MagicMock
# TensorFlow is not needed for classical baselines; stub it so the repo's split code imports without it.
for _m in ('tensorflow', 'tensorflow.keras', 'tensorflow.keras.layers'):
    sys.modules.setdefault(_m, MagicMock())
import numpy as np
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score,
                             roc_auc_score, average_precision_score)

sys.path.insert(0, os.path.dirname(__file__))
from pipeline import RESULTS_DIR, slug
from sensitivity_split_v2 import PREP_FUNCS, SPLIT_LABEL   # reuse the exact split/prep code

SEEDS = [42, 43, 44]
names = sys.argv[1:] or list(PREP_FUNCS)
for name in names:
    (Xtr, Xte), ytr, yte = PREP_FUNCS[name]()
    Xtr, Xte = Xtr.reshape(len(Xtr), -1), Xte.reshape(len(Xte), -1)
    print(f"\n{name} [{SPLIT_LABEL[name]}]  train={len(ytr)} (attack {ytr.mean():.3f})  test={len(yte)} (attack {yte.mean():.3f})")
    out = {"split": SPLIT_LABEL[name], "n_train": int(len(ytr)), "n_test": int(len(yte)), "models": {}}
    for mname, make in (("random_forest", lambda s: RandomForestClassifier(300, n_jobs=-1, random_state=s)),
                        ("hist_gradient_boosting", lambda s: HistGradientBoostingClassifier(random_state=s))):
        runs = []
        for s in SEEDS:
            m = make(s).fit(Xtr, ytr); p = m.predict(Xte); pr = m.predict_proba(Xte)[:, 1]
            runs.append(dict(seed=s, accuracy=accuracy_score(yte, p), precision=precision_score(yte, p, zero_division=0),
                             recall=recall_score(yte, p, zero_division=0), f1=f1_score(yte, p, zero_division=0),
                             roc_auc=roc_auc_score(yte, pr) if len(set(yte)) > 1 else None,
                             pr_auc=average_precision_score(yte, pr)))
        mean = {k: float(np.mean([r[k] for r in runs])) for k in ("accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc")}
        std = {k: float(np.std([r[k] for r in runs])) for k in mean}
        out["models"][mname] = {"runs": runs, "mean": mean, "std": std}
        print(f"  {mname:24s} acc={mean['accuracy']:.4f} prec={mean['precision']:.4f} rec={mean['recall']:.4f} f1={mean['f1']:.4f}")
    with open(os.path.join(RESULTS_DIR, f"{slug(name)}_altsplit_baselines.json"), "w") as f:
        json.dump(out, f, indent=2)
print("\nSaved results/*_altsplit_baselines.json")
