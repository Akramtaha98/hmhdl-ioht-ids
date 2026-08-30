"""Same-split classical ML baselines + extra probability-based metrics for
the final hybrid model, computed WITHOUT retraining the hybrid (reloads
saved weights). Addresses reviewer requests for in-paper same-split
baselines and richer metrics (ROC-AUC, PR-AUC, per-class, specificity, FNR).

Usage: python3 baselines_and_metrics.py <dataset_name> [baselines|metrics|both]
"""
import sys
import os
import json
import time
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
CKPT_DIR = os.path.join(BASE_DIR, "checkpoints")


def slug(name):
    return name.replace(" ", "_")


def load_prep(name):
    d = np.load(os.path.join(CKPT_DIR, f"{slug(name)}_prep.npz"))
    return d["Xtr"], d["Xte"], d["ytr"], d["yte"]


def run_baselines(name):
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
    from sklearn.neural_network import MLPClassifier
    from sklearn.metrics import (accuracy_score, balanced_accuracy_score, precision_score,
                                  recall_score, f1_score)

    Xtr, Xte, ytr, yte = load_prep(name)
    n_tr, n_feat, _ = Xtr.shape
    Xtr_flat = Xtr.reshape(n_tr, n_feat)
    Xte_flat = Xte.reshape(Xte.shape[0], n_feat)

    models = {
        "Logistic Regression": LogisticRegression(max_iter=300, random_state=42),
        "Random Forest": RandomForestClassifier(n_estimators=200, n_jobs=-1, random_state=42),
        "Gradient Boosting (Hist)": HistGradientBoostingClassifier(random_state=42),
        "MLP": MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=150,
                              early_stopping=True, random_state=42),
    }

    out_path = os.path.join(RESULTS_DIR, f"{slug(name)}_baselines.json")
    results = {}
    if os.path.exists(out_path):
        with open(out_path) as f:
            results = json.load(f)

    for mname, model in models.items():
        if mname in results:
            print(f"[baseline] {name}/{mname}: already done, skipping")
            continue
        t0 = time.time()
        model.fit(Xtr_flat, ytr)
        pred = model.predict(Xte_flat)
        results[mname] = {
            "accuracy": float(accuracy_score(yte, pred)),
            "balanced_accuracy": float(balanced_accuracy_score(yte, pred)),
            "precision": float(precision_score(yte, pred, zero_division=0)),
            "recall": float(recall_score(yte, pred, zero_division=0)),
            "f1": float(f1_score(yte, pred, zero_division=0)),
            "train_time_sec": time.time() - t0,
        }
        with open(out_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"[baseline] {name}/{mname}: acc={results[mname]['accuracy']:.4f} "
              f"f1={results[mname]['f1']:.4f} time={results[mname]['train_time_sec']:.1f}s")

    print(f"[baseline] {name}: all baselines complete -> {out_path}")


def run_baseline_extra_metrics(name):
    """Retrains each classical baseline (cheap, <3s each) and computes the
    same probability-based metrics reported for the hybrid model
    (ROC-AUC, PR-AUC, specificity, FNR, per-class precision/recall/F1), so
    baselines that match or beat the hybrid model -- e.g. gradient boosting
    on WUSTL-EHMS-2020 -- can be compared on equal footing rather than only
    on accuracy/F1."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
    from sklearn.neural_network import MLPClassifier
    from sklearn.metrics import (roc_auc_score, average_precision_score,
                                  precision_recall_fscore_support, confusion_matrix)

    Xtr, Xte, ytr, yte = load_prep(name)
    n_tr, n_feat, _ = Xtr.shape
    Xtr_flat = Xtr.reshape(n_tr, n_feat)
    Xte_flat = Xte.reshape(Xte.shape[0], n_feat)

    models = {
        "Logistic Regression": LogisticRegression(max_iter=300, random_state=42),
        "Random Forest": RandomForestClassifier(n_estimators=200, n_jobs=-1, random_state=42),
        "Gradient Boosting (Hist)": HistGradientBoostingClassifier(random_state=42),
        "MLP": MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=150,
                              early_stopping=True, random_state=42),
    }

    out_path = os.path.join(RESULTS_DIR, f"{slug(name)}_baseline_extra_metrics.json")
    results = {}
    for mname, model in models.items():
        model.fit(Xtr_flat, ytr)
        y_prob = model.predict_proba(Xte_flat)[:, 1]
        y_pred = (y_prob >= 0.5).astype(int)
        roc_auc = float(roc_auc_score(yte, y_prob)) if len(set(yte)) > 1 else None
        pr_auc = float(average_precision_score(yte, y_prob)) if len(set(yte)) > 1 else None
        prec, rec, f1, support = precision_recall_fscore_support(yte, y_pred, zero_division=0)
        tn, fp, fn, tp = confusion_matrix(yte, y_pred).ravel()
        specificity = float(tn / (tn + fp)) if (tn + fp) > 0 else float("nan")
        fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else float("nan")
        fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else float("nan")
        results[mname] = {
            "roc_auc": roc_auc, "pr_auc": pr_auc,
            "per_class": {
                "normal": {"precision": float(prec[0]), "recall": float(rec[0]), "f1": float(f1[0])},
                "attack": {"precision": float(prec[1]), "recall": float(rec[1]), "f1": float(f1[1])},
            },
            "specificity": specificity, "false_negative_rate": fnr, "false_positive_rate": fpr,
        }
        print(f"[baseline-extra] {name}/{mname}: ROC-AUC={roc_auc} PR-AUC={pr_auc} "
              f"specificity={specificity:.4f} FNR={fnr:.4f}")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[baseline-extra] {name}: COMPLETE -> {out_path}")


def run_extra_metrics(name):
    from tensorflow import keras
    from sklearn.metrics import (roc_auc_score, average_precision_score,
                                  precision_recall_fscore_support, confusion_matrix)

    Xtr, Xte, ytr, yte = load_prep(name)
    model = keras.models.load_model(os.path.join(CKPT_DIR, f"{slug(name)}_final_model.keras"))
    y_prob = model.predict(Xte, verbose=0).ravel()
    y_pred = (y_prob >= 0.5).astype(int)

    roc_auc = float(roc_auc_score(yte, y_prob))
    pr_auc = float(average_precision_score(yte, y_prob))
    prec, rec, f1, support = precision_recall_fscore_support(yte, y_pred, zero_division=0)
    tn, fp, fn, tp = confusion_matrix(yte, y_pred).ravel()
    specificity = float(tn / (tn + fp)) if (tn + fp) > 0 else float("nan")
    fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else float("nan")
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else float("nan")

    out = {
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "per_class": {
            "normal": {"precision": float(prec[0]), "recall": float(rec[0]),
                       "f1": float(f1[0]), "support": int(support[0])},
            "attack": {"precision": float(prec[1]), "recall": float(rec[1]),
                       "f1": float(f1[1]), "support": int(support[1])},
        },
        "specificity": specificity,
        "false_negative_rate": fnr,
        "false_positive_rate": fpr,
        "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
    }
    out_path = os.path.join(RESULTS_DIR, f"{slug(name)}_extra_metrics.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"[extra] {name}: ROC-AUC={roc_auc:.4f} PR-AUC={pr_auc:.4f} "
          f"specificity={specificity:.4f} FNR={fnr:.4f} -> {out_path}")


if __name__ == "__main__":
    name = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "both"
    if mode in ("baselines", "both"):
        run_baselines(name)
    if mode in ("metrics", "both"):
        run_extra_metrics(name)
    if mode == "baseline_extra":
        run_baseline_extra_metrics(name)
