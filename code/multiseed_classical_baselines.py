"""
Multi-seed (>=4 seeds) classical baselines (Random Forest, HistGradientBoosting)
for all three datasets, on the SAME leakage-free split-before-fit preprocessed
data already checkpointed by pipeline.py (only the classifier's own internal
randomness — bootstrap sampling / feature subsampling / tree-growth order —
varies across seeds; the train/test partition itself is fixed, consistent with
how the paper's other seed-robustness checks are framed).

Addresses review item M2 / gate G13. Cheap (sklearn only, seconds per fit), so
run directly rather than as a background job.
"""
import os
import sys
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline as P

from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, precision_score,
                              recall_score, f1_score)

SEEDS = [42, 43, 44, 45, 46]
DATASETS = ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]


def eval_at_seed(clf_cls, kwargs_fn, Xtr, ytr, Xte, yte, seed):
    clf = clf_cls(**kwargs_fn(seed))
    clf.fit(Xtr, ytr)
    y_pred = clf.predict(Xte)
    return {
        "seed": seed,
        "accuracy": float(accuracy_score(yte, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(yte, y_pred)),
        "precision": float(precision_score(yte, y_pred, zero_division=0)),
        "recall": float(recall_score(yte, y_pred, zero_division=0)),
        "f1": float(f1_score(yte, y_pred, zero_division=0)),
    }


def summarize(per_seed):
    keys = ["accuracy", "balanced_accuracy", "precision", "recall", "f1"]
    mean = {k: float(np.mean([r[k] for r in per_seed])) for k in keys}
    std = {k: float(np.std([r[k] for r in per_seed])) for k in keys}
    return mean, std


def main():
    out = {}
    for name in DATASETS:
        prep_path = P.path_for(name, "prep.npz")
        if not os.path.exists(prep_path):
            out[name] = {"status": "SKIPPED", "reason": "no prep checkpoint available"}
            print(f"[multiseed_baselines] {name}: SKIPPED (no prep checkpoint)")
            continue
        Xtr, Xte, ytr, yte = P.load_prep(name)
        Xtr_flat = Xtr.reshape(Xtr.shape[0], -1)
        Xte_flat = Xte.reshape(Xte.shape[0], -1)

        rf_runs = [eval_at_seed(RandomForestClassifier,
                                 lambda s: dict(n_estimators=200, random_state=s, n_jobs=-1),
                                 Xtr_flat, ytr, Xte_flat, yte, s) for s in SEEDS]
        hgb_runs = [eval_at_seed(HistGradientBoostingClassifier,
                                  lambda s: dict(random_state=s),
                                  Xtr_flat, ytr, Xte_flat, yte, s) for s in SEEDS]

        rf_mean, rf_std = summarize(rf_runs)
        hgb_mean, hgb_std = summarize(hgb_runs)

        out[name] = {
            "seeds": SEEDS,
            "Random Forest": {"seeds": rf_runs, "mean": rf_mean, "std": rf_std},
            "Gradient Boosting (Hist)": {"seeds": hgb_runs, "mean": hgb_mean, "std": hgb_std},
        }
        print(f"[multiseed_baselines] {name}: RF acc {rf_mean['accuracy']*100:.2f}%±{rf_std['accuracy']*100:.2f}%, "
              f"HistGB acc {hgb_mean['accuracy']*100:.2f}%±{hgb_std['accuracy']*100:.2f}% "
              f"(n={len(SEEDS)} seeds)")

    out_path = os.path.join(P.RESULTS_DIR, "baselines_multiseed_all.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print("Saved:", out_path)


if __name__ == "__main__":
    main()
