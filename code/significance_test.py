"""
Paired statistical significance test: hybrid model vs. best classical
baseline (Gradient Boosting), on the IDENTICAL 5 stratified CV folds used
for the hybrid model's cross-validation stability check (Section 4.2 /
`pipeline.py cv`).

Rationale: the hybrid model's CV-stage folds (`results/{name}_cv.json`,
produced by `pipeline.py cv`) already give 5 fold-level accuracy values
per dataset under a fixed budget (10 epochs/fold). This script refits
HistGradientBoostingClassifier on the exact same fold splits (same
StratifiedKFold, same random_state=42, same preprocessed features from
`checkpoints/{name}_prep.npz`) so the two sets of 5 fold accuracies are
paired and directly comparable, then runs a paired t-test and a Wilcoxon
signed-rank test on the paired differences.

Caveat (report this alongside the numbers): the CV-stage hybrid model
uses only a 10-epoch/fold training budget for tractability, not the final
model's full 80-epoch/patience-8 budget reported in Table 6 -- so this
test targets the *CV-stage* hybrid vs. gradient boosting comparison, not
a comparison against the fully-trained final model.

Usage: python3 significance_test.py
Writes results/significance_test.json
"""
import os
import json
import numpy as np
from sklearn.model_selection import StratifiedKFold
from sklearn.ensemble import HistGradientBoostingClassifier
from scipy import stats

RANDOM_STATE = 42
CV_FOLDS = 5

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CKPT_DIR = os.path.join(BASE_DIR, "checkpoints")
RESULTS_DIR = os.path.join(BASE_DIR, "results")

DATASETS = ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]


def slug(name):
    return name.replace(" ", "_")


def main():
    out = {}
    for name in DATASETS:
        d = np.load(os.path.join(CKPT_DIR, f"{slug(name)}_prep.npz"))
        Xtr, ytr = d["Xtr"], d["ytr"]
        Xtr2d = Xtr.reshape(Xtr.shape[0], Xtr.shape[1])

        with open(os.path.join(RESULTS_DIR, f"{slug(name)}_cv.json")) as f:
            hybrid_cv = json.load(f)
        hybrid_folds = np.array(hybrid_cv["fold_accs"])

        skf = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
        splits = list(skf.split(Xtr2d, ytr))

        gb_folds = []
        for tr_idx, va_idx in splits:
            clf = HistGradientBoostingClassifier(random_state=42)
            clf.fit(Xtr2d[tr_idx], ytr[tr_idx])
            gb_folds.append(float(clf.score(Xtr2d[va_idx], ytr[va_idx])))
        gb_folds = np.array(gb_folds)

        diff = hybrid_folds - gb_folds
        if np.allclose(diff, 0):
            t_stat, t_p, w_stat, w_p = None, 1.0, None, 1.0
        else:
            t_stat, t_p = stats.ttest_rel(hybrid_folds, gb_folds)
            t_stat = float(t_stat)
            try:
                w_stat, w_p = stats.wilcoxon(hybrid_folds, gb_folds)
                w_stat = float(w_stat)
            except ValueError:
                w_stat, w_p = None, 1.0

        out[name] = {
            "hybrid_fold_accs": hybrid_folds.tolist(),
            "gb_fold_accs": gb_folds.tolist(),
            "hybrid_mean": float(hybrid_folds.mean()),
            "gb_mean": float(gb_folds.mean()),
            "paired_t_stat": t_stat,
            "paired_t_p": float(t_p),
            "wilcoxon_stat": w_stat,
            "wilcoxon_p": float(w_p),
        }
        print(name, out[name])

    with open(os.path.join(RESULTS_DIR, "significance_test.json"), "w") as f:
        json.dump(out, f, indent=2)
    print("Saved results/significance_test.json")


if __name__ == "__main__":
    main()
