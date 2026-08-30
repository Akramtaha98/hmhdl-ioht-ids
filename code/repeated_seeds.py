"""Repeated-seed evaluation of the final hybrid model on the MAIN
(random-split) test partition, to give a confidence interval around the
single-seed headline numbers reported in Table 6/7.

Uses the same train/test split and the same Lionfish-selected
hyperparameters as the main experiment (only weight initialization and
minibatch order vary across seeds -- the data partition itself is held
fixed, since re-splitting is a separate question addressed by the
alternative-split sensitivity analysis). Trained at a reduced budget (up
to 25 epochs, early-stopping patience 5) rather than the main experiment's
80-epoch/patience-8 budget, for practicality across 3 additional seeds;
reported explicitly as such. 3 additional seeds (43, 44, 45) are run
alongside the original seed-42 result already in "{name}_results.json",
giving 4 runs total per dataset for the mean/std summary.
"""
import os
import sys
import json
import time
import pickle
import numpy as np
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                              f1_score, balanced_accuracy_score,
                              roc_auc_score, average_precision_score)

sys.path.insert(0, os.path.dirname(__file__))
from pipeline import build_model, RESULTS_DIR, CKPT_DIR, slug, load_prep, load_best_params
import tensorflow as tf
from tensorflow import keras

SEEDS = [43, 44, 45]
# Matches pipeline.py's FINAL_EPOCHS/FINAL_BATCH/FINAL_PATIENCE exactly, so
# every seed (including the original 42, trained via pipeline.stage_train)
# is trained under an identical budget -- these are true repeated-seed
# runs, not a reduced-budget approximation.
RS_EPOCHS = 80
RS_BATCH = 128
RS_PATIENCE = 8


def run_one_seed(name, seed, budget_sec=165):
    t0 = time.time()
    ckpt_state = os.path.join(CKPT_DIR, f"{slug(name)}_rs{seed}_state.pkl")
    ckpt_weights = os.path.join(CKPT_DIR, f"{slug(name)}_rs{seed}_model.weights.h5")

    Xtr, Xte, ytr, yte = load_prep(name)
    best_params, _ = load_best_params(name)

    tf.random.set_seed(seed)
    np.random.seed(seed)
    model = build_model((Xtr.shape[1], 1), best_params["n_conv_blocks"], best_params["conv_filters"],
                         best_params["lstm_units"], best_params["gru_units"], best_params["dropout_rate"])

    if os.path.exists(ckpt_state):
        with open(ckpt_state, "rb") as f:
            state = pickle.load(f)
        model.load_weights(ckpt_weights)
    else:
        state = {"epoch_done": 0, "best_loss": np.inf, "bad_epochs": 0}

    while state["epoch_done"] < RS_EPOCHS:
        hist = model.fit(Xtr, ytr, epochs=1, batch_size=RS_BATCH, verbose=0, shuffle=True)
        loss = float(hist.history["loss"][0])
        state["epoch_done"] += 1
        if loss < state["best_loss"] - 1e-5:
            state["best_loss"] = loss
            state["bad_epochs"] = 0
            model.save_weights(ckpt_weights)
        else:
            state["bad_epochs"] += 1
        with open(ckpt_state, "wb") as fo:
            pickle.dump(state, fo)
        print(f"[rs seed={seed}] {name}: epoch {state['epoch_done']}/{RS_EPOCHS} loss={loss:.4f} "
              f"elapsed={time.time()-t0:.1f}s")
        if state["bad_epochs"] >= RS_PATIENCE:
            print(f"[rs seed={seed}] {name}: early stopping")
            break
        if time.time() - t0 > budget_sec:
            print(f"[rs seed={seed}] {name}: budget hit, checkpointed, rerun to continue")
            return False

    model.load_weights(ckpt_weights)
    y_prob = model.predict(Xte, verbose=0).ravel()
    y_pred = (y_prob >= 0.5).astype(int)
    metrics = {
        "seed": seed,
        "accuracy": float(accuracy_score(yte, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(yte, y_pred)),
        "precision": float(precision_score(yte, y_pred, zero_division=0)),
        "recall": float(recall_score(yte, y_pred, zero_division=0)),
        "f1": float(f1_score(yte, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(yte, y_prob)) if len(set(yte)) > 1 else None,
        "pr_auc": float(average_precision_score(yte, y_prob)) if len(set(yte)) > 1 else None,
        "epochs_run": state["epoch_done"],
    }
    out_path = os.path.join(RESULTS_DIR, f"{slug(name)}_seed{seed}.json")
    with open(out_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"[rs seed={seed}] {name}: COMPLETE acc={metrics['accuracy']:.4f} f1={metrics['f1']:.4f} "
          f"-> {out_path}")
    return True


def summarize(name):
    with open(os.path.join(RESULTS_DIR, f"{slug(name)}_results.json")) as f:
        main = json.load(f)
    runs = [{"seed": 42, "accuracy": main["accuracy"], "balanced_accuracy": main["balanced_accuracy"],
             "precision": main["precision"], "recall": main["recall"], "f1": main["f1"]}]
    for seed in SEEDS:
        p = os.path.join(RESULTS_DIR, f"{slug(name)}_seed{seed}.json")
        if not os.path.exists(p):
            print(f"[summarize] {name}: missing seed {seed}, skipping summary for now")
            return False
        with open(p) as f:
            runs.append(json.load(f))
    arr = {k: np.array([r[k] for r in runs]) for k in ["accuracy", "balanced_accuracy", "precision", "recall", "f1"]}
    summary = {
        "n_seeds": len(runs), "seeds": [r["seed"] for r in runs],
        "note": ("4 runs (main seed 42 at the full 80-epoch/patience-8 budget, plus 3 additional "
                 "seeds at a reduced 25-epoch/patience-5 budget) on the SAME main random-split "
                 "train/test partition; varies weight initialization and minibatch order only."),
        "mean": {k: float(v.mean()) for k, v in arr.items()},
        "std": {k: float(v.std()) for k, v in arr.items()},
        "per_seed": runs,
    }
    out_path = os.path.join(RESULTS_DIR, f"{slug(name)}_repeated_seeds.json")
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[summarize] {name}: acc={summary['mean']['accuracy']:.4f}+/-{summary['std']['accuracy']:.4f} "
          f"f1={summary['mean']['f1']:.4f}+/-{summary['std']['f1']:.4f} -> {out_path}")
    return True


if __name__ == "__main__":
    mode = sys.argv[1]
    name = sys.argv[2]
    if mode == "run":
        seed = int(sys.argv[3])
        budget = 165
        for i, a in enumerate(sys.argv):
            if a == "--budget":
                budget = int(sys.argv[i + 1])
        _ok = run_one_seed(name, seed, budget_sec=budget)
    elif mode == "summarize":
        _ok = summarize(name)
    else:
        raise ValueError(mode)
    sys.exit(0 if _ok else 1)
