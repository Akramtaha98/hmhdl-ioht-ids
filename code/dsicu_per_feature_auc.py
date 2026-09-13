"""
DSICU per-feature AUC diagnostic (review item M6 / gate G12).

The raw DSICU CSV (dsicu_mi.csv) is a restricted-access clinical file not
present in this environment's data/ directory (consistent with the
manuscript's framing of DSICU as a restricted-access third benchmark). What
IS available is the already-split-before-fit-preprocessed checkpoint
(checkpoints/DSICU_prep.npz): 16 features that survived variance filtering
and SelectKBest(f_classif) selection, standardized, for the SAME train/test
partition used to report DSICU results elsewhere in the paper.

This is disclosed explicitly: the original clinical feature NAMES cannot be
recovered in this environment (they were dropped during the earlier
prep/checkpoint step and the raw CSV with headers is not available here), so
this diagnostic reports selected-feature INDEX (1-16, in SelectKBest's
retained order) rather than a semantic feature name. That is still
sufficient to answer the diagnostic question the review is actually asking:
is there a single feature (of the surviving, already-selected 16) that is
by itself near-perfectly separating, which would explain DSICU's
near-trivial separability independent of the hybrid architecture.
"""
import os
import sys
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline as P
from sklearn.metrics import roc_auc_score

Xtr, Xte, ytr, yte = P.load_prep("DSICU")
Xtr_flat = Xtr.reshape(Xtr.shape[0], -1)  # (n, 16)
n_features = Xtr_flat.shape[1]

per_feature = []
for i in range(n_features):
    col = Xtr_flat[:, i]
    try:
        auc = roc_auc_score(ytr, col)
    except ValueError:
        auc = float("nan")
    # AUC is direction-agnostic for this diagnostic: a feature that is
    # perfectly separating "backwards" (AUC near 0) is just as informative
    # as one perfectly separating "forwards" (AUC near 1).
    separating_auc = max(auc, 1 - auc) if not np.isnan(auc) else float("nan")
    per_feature.append({
        "selected_feature_index": i + 1,
        "auc_vs_label": round(float(auc), 6),
        "separating_power_auc": round(float(separating_auc), 6),
    })

per_feature_sorted = sorted(per_feature, key=lambda r: -r["separating_power_auc"])
top = per_feature_sorted[0]

out = {
    "dataset": "DSICU",
    "note": (
        "Raw DSICU feature names are not recoverable in this environment "
        "(restricted-access CSV not present); features are reported by "
        "their 1-indexed position among the 16 features SelectKBest(f_classif) "
        "retained on the training partition of the main split. AUC is computed "
        "on the raw standardized feature value directly against the training "
        "label, single-feature, no model fit -- i.e., 'if you thresholded this "
        "one column alone, how well would it separate the classes.'"
    ),
    "n_features_checked": n_features,
    "per_feature": per_feature_sorted,
    "max_single_feature_auc": top["separating_power_auc"],
    "near_perfect_single_feature_found": bool(top["separating_power_auc"] >= 0.98),
    "interpretation": (
        f"The strongest single surviving feature (index {top['selected_feature_index']} of "
        f"{n_features}) achieves AUC = {top['separating_power_auc']:.4f} against the label by "
        "itself, with no model. "
        + ("This confirms near-trivial separability is attributable to at least one feature "
           "carrying label-identifying information already, independent of the hybrid "
           "architecture's capacity, consistent with the paper's cautionary framing of DSICU."
           if top["separating_power_auc"] >= 0.98 else
           "No single surviving feature is near-perfectly separating on its own, so DSICU's "
           "high reported accuracy is not trivially explained by one dominant feature; the "
           "cautionary framing in Section 5 should be read as a protocol/feature-provenance "
           "concern rather than a single-feature leakage finding.")
    ),
}

out_path = os.path.join(P.RESULTS_DIR, "DSICU_per_feature_auc.json")
with open(out_path, "w") as f:
    json.dump(out, f, indent=2)
print(json.dumps(out, indent=2))
print("Saved:", out_path)
