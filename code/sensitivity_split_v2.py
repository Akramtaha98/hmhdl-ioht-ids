"""Revised alternative-split sensitivity analysis, fixing the two
independence/leakage-adjacent problems flagged in review:

  (1) Capture-order / identifier-like fields (`Time` for ECU-IoHT,
      `Packet_num` for WUSTL-EHMS-2020, `tcp.srcport`/`tcp.dstport` for
      DSICU) are used ONLY to sort/group records into the alternative
      train/test partitions. They are EXCLUDED from the model's input
      feature matrix, so the model can no longer use a coarse
      row/flow-identifier proxy as a shortcut.

  (2) Hyperparameters are no longer reused from the main (random-split)
      Lionfish search. Instead, a random search using the SAME budget as
      the main experiment (42 candidate evaluations, the same
      quick-evaluation protocol used elsewhere in this study: 3 epochs,
      batch 1024) is run using ONLY the alternative split's own training
      partition (an internal 80/20 sub-split of it for validation) -- so
      no information from the alternative split's test partition, and no
      hyperparameters selected under the main random split, enter this
      evaluation at any point.

The search budget (42 candidates) and the final training budget (up to 80
epochs, early-stopping patience 8) both match the main experiment exactly,
so this alternative-split result is not confounded by a smaller search or
training allowance than the main split received. The final model for each
alternative split is trained on that split's full training partition and
evaluated once on that split's held-out test partition.
"""
import os
import sys
import json
import time
import pickle
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                              f1_score, confusion_matrix, balanced_accuracy_score,
                              roc_auc_score, average_precision_score)

sys.path.insert(0, os.path.dirname(__file__))
from pipeline import build_model, RESULTS_DIR, CKPT_DIR, DATA_DIR, slug, RANDOM_STATE, BOUNDS, clip_candidate
from tensorflow import keras

# Matches the main experiment's budgets exactly: 42 candidate evaluations
# (same as the main Lionfish search and its random-search control) and up
# to 80 epochs / patience 8 for final training (same as pipeline.py's
# FINAL_EPOCHS/FINAL_PATIENCE), so the alternative-split result is not
# confounded by a smaller search or training budget than the main split.
N_CANDIDATES = 42
QUICK_EPOCHS = 3
SEARCH_BATCH = 1024
FINAL_EPOCHS = 80
FINAL_BATCH = 128
FINAL_PATIENCE = 8


def _finalize_split(Xtr_raw, Xte_raw, ytr, yte):
    train_std = Xtr_raw.std(axis=0)
    keep_mask = train_std > 1e-12
    Xtr_raw = Xtr_raw[:, keep_mask]
    Xte_raw = Xte_raw[:, keep_mask]

    selector = SelectKBest(score_func=f_classif, k=Xtr_raw.shape[1])
    selector.fit(Xtr_raw, ytr)
    Xtr_sel = selector.transform(Xtr_raw)
    Xte_sel = selector.transform(Xte_raw)

    scaler = StandardScaler()
    scaler.fit(Xtr_sel)
    Xtr_scaled = scaler.transform(Xtr_sel).astype(np.float32)
    Xte_scaled = scaler.transform(Xte_sel).astype(np.float32)

    Xtr_final = Xtr_scaled.reshape((Xtr_scaled.shape[0], Xtr_scaled.shape[1], 1))
    Xte_final = Xte_scaled.reshape((Xte_scaled.shape[0], Xte_scaled.shape[1], 1))
    return Xtr_final, Xte_final


def prep_ecu_temporal_noid():
    df = pd.read_csv(os.path.join(DATA_DIR, "ECU_IoHT.csv"))
    df = df.sort_values("Time").reset_index(drop=True)   # Time used to order rows only
    y = (df["Type"] == "Attack").astype(int).values
    X = df[["Length", "Protocol"]].copy()                 # Time NOT included as a feature
    X = pd.get_dummies(X, columns=["Protocol"], prefix="proto").astype(float).values
    n = len(df)
    cut = int(n * 0.7)
    Xtr_raw, Xte_raw = X[:cut], X[cut:]
    ytr, yte = y[:cut], y[cut:]
    return _finalize_split(Xtr_raw, Xte_raw, ytr, yte), ytr, yte


def prep_wustl_temporal_noid():
    df = pd.read_csv(os.path.join(DATA_DIR, "wustl-ehms-2020.csv"))
    df = df.sort_values("Packet_num").reset_index(drop=True)  # Packet_num used to order rows only
    y = df["label"].astype(int).values
    X = df.drop(columns=["label", "Packet_num"]).astype(float).values  # Packet_num NOT a feature
    n = len(df)
    cut = int(n * 0.7)
    Xtr_raw, Xte_raw = X[:cut], X[cut:]
    ytr, yte = y[:cut], y[cut:]
    return _finalize_split(Xtr_raw, Xte_raw, ytr, yte), ytr, yte


def prep_dsicu_group_noid():
    df = pd.read_csv(os.path.join(DATA_DIR, "dsicu_mi.csv"))
    y = df["label"].astype(int).values
    X = df.drop(columns=["label", "tcp.srcport", "tcp.dstport"])  # ports NOT a feature
    groups = df.groupby(["tcp.srcport", "tcp.dstport"]).indices    # ports used to group rows only
    group_keys = list(groups.keys())
    rng = np.random.default_rng(42)
    rng.shuffle(group_keys)

    n_total = len(df)
    target_train = int(n_total * 0.7)
    train_idx = []
    running = 0
    train_keys = set()
    for k in group_keys:
        idx = groups[k]
        if running < target_train:
            train_idx.append(idx)
            train_keys.add(k)
            running += len(idx)
    train_idx = np.concatenate(train_idx)
    train_mask = np.zeros(n_total, dtype=bool)
    train_mask[train_idx] = True
    test_mask = ~train_mask

    Xv = X.astype(float).values
    Xtr_raw, Xte_raw = Xv[train_mask], Xv[test_mask]
    ytr, yte = y[train_mask], y[test_mask]
    n_train_groups = len(train_keys)
    n_test_groups = len(group_keys) - n_train_groups
    print(f"[dsicu_group_noid] {n_train_groups} train groups / {n_test_groups} test groups, "
          f"train_rows={train_mask.sum()} test_rows={test_mask.sum()}")
    return _finalize_split(Xtr_raw, Xte_raw, ytr, yte), ytr, yte


PREP_FUNCS = {
    "ECU-IoHT": prep_ecu_temporal_noid,
    "WUSTL-EHMS-2020": prep_wustl_temporal_noid,
    "DSICU": prep_dsicu_group_noid,
}
SPLIT_LABEL = {
    "ECU-IoHT": "temporal (Time dropped as feature)",
    "WUSTL-EHMS-2020": "temporal (Packet_num dropped as feature)",
    "DSICU": "group / srcport,dstport (ports dropped as feature)",
}


def _get_data(name):
    ckpt_data = os.path.join(CKPT_DIR, f"{slug(name)}_sens2_data.npz")
    if os.path.exists(ckpt_data):
        d = np.load(ckpt_data)
        return d["Xtr"], d["Xte"], d["ytr"], d["yte"]
    (Xtr, Xte), ytr, yte = PREP_FUNCS[name]()
    np.savez_compressed(ckpt_data, Xtr=Xtr, Xte=Xte, ytr=ytr, yte=yte)
    return Xtr, Xte, ytr, yte


def run_search(name, budget_sec=165):
    """Independent compact random search inside the alt split's OWN training
    partition only (80/20 sub-split for search validation)."""
    t0 = time.time()
    ckpt_path = os.path.join(CKPT_DIR, f"{slug(name)}_sens2_search_ckpt.pkl")
    Xtr, Xte, ytr, yte = _get_data(name)
    Xtr_opt, Xval_opt, ytr_opt, yval_opt = train_test_split(
        Xtr, ytr, test_size=0.2, stratify=ytr, random_state=RANDOM_STATE
    )

    if os.path.exists(ckpt_path):
        with open(ckpt_path, "rb") as f:
            state = pickle.load(f)
        print(f"[sens2-search] resuming {name} from {len(state['log'])}/{N_CANDIDATES}")
    else:
        state = {"log": [], "best_acc": -1, "best_params": None}

    # independent RNG stream, seeded distinctly from both the main Lionfish
    # search (RANDOM_STATE) and the main random-search control (RANDOM_STATE+999)
    rng = np.random.default_rng(RANDOM_STATE + 4242)
    for _ in range(len(state["log"])):
        {k: rng.uniform(lo, hi) for k, (lo, hi) in BOUNDS.items()}

    while len(state["log"]) < N_CANDIDATES:
        cand = clip_candidate({k: rng.uniform(lo, hi) for k, (lo, hi) in BOUNDS.items()})
        model = build_model((Xtr_opt.shape[1], 1), cand["n_conv_blocks"], cand["conv_filters"],
                             cand["lstm_units"], cand["gru_units"], cand["dropout_rate"])
        model.fit(Xtr_opt, ytr_opt, epochs=QUICK_EPOCHS, batch_size=SEARCH_BATCH, verbose=0)
        val_acc = float(model.evaluate(Xval_opt, yval_opt, verbose=0)[1])
        keras.backend.clear_session()
        state["log"].append({"candidate": cand, "val_acc": val_acc})
        if val_acc > state["best_acc"]:
            state["best_acc"] = val_acc
            state["best_params"] = cand
        with open(ckpt_path, "wb") as fo:
            pickle.dump(state, fo)
        print(f"[sens2-search] {name}: {len(state['log'])}/{N_CANDIDATES} val_acc={val_acc:.4f} "
              f"best_so_far={state['best_acc']:.4f} elapsed={time.time()-t0:.1f}s")
        if time.time() - t0 > budget_sec:
            print(f"[sens2-search] {name}: budget hit, checkpointed, rerun to continue")
            return False

    with open(os.path.join(CKPT_DIR, f"{slug(name)}_sens2_best_params.json"), "w") as f:
        json.dump({"best_params": state["best_params"], "best_val_acc_quick": state["best_acc"],
                    "n_candidates": len(state["log"])}, f, indent=2)
    print(f"[sens2-search] {name}: COMPLETE best_val_acc={state['best_acc']:.4f} "
          f"best_params={state['best_params']}")
    return True


def run_train_eval(name, budget_sec=165):
    t0 = time.time()
    ckpt_state = os.path.join(CKPT_DIR, f"{slug(name)}_sens2_state.pkl")
    ckpt_weights = os.path.join(CKPT_DIR, f"{slug(name)}_sens2_model.weights.h5")
    Xtr, Xte, ytr, yte = _get_data(name)

    bp_path = os.path.join(CKPT_DIR, f"{slug(name)}_sens2_best_params.json")
    if not os.path.exists(bp_path):
        print(f"[sens2-train] {name}: search not complete yet, run search stage first")
        return False
    with open(bp_path) as f:
        best_params = json.load(f)["best_params"]

    model = build_model((Xtr.shape[1], 1), best_params["n_conv_blocks"], best_params["conv_filters"],
                         best_params["lstm_units"], best_params["gru_units"], best_params["dropout_rate"])

    if os.path.exists(ckpt_state):
        with open(ckpt_state, "rb") as f:
            state = pickle.load(f)
        model.load_weights(ckpt_weights)
    else:
        state = {"epoch_done": 0, "best_loss": np.inf, "bad_epochs": 0}

    while state["epoch_done"] < FINAL_EPOCHS:
        hist = model.fit(Xtr, ytr, epochs=1, batch_size=FINAL_BATCH, verbose=0)
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
        print(f"[sens2-train] {name}: epoch {state['epoch_done']}/{FINAL_EPOCHS} loss={loss:.4f} "
              f"elapsed={time.time()-t0:.1f}s")
        if state["bad_epochs"] >= FINAL_PATIENCE:
            print(f"[sens2-train] {name}: early stopping")
            break
        if time.time() - t0 > budget_sec:
            print(f"[sens2-train] {name}: budget hit, checkpointed, rerun to continue")
            return False

    model.load_weights(ckpt_weights)
    y_prob = model.predict(Xte, verbose=0).ravel()
    y_pred = (y_prob >= 0.5).astype(int)
    metrics = {
        "split_type": SPLIT_LABEL[name],
        "hyperparam_source": f"independent random search ({N_CANDIDATES} candidates, matched to the main experiment's budget) inside this split's own training partition",
        "best_params": best_params,
        "accuracy": float(accuracy_score(yte, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(yte, y_pred)),
        "precision": float(precision_score(yte, y_pred, zero_division=0)),
        "recall": float(recall_score(yte, y_pred, zero_division=0)),
        "f1": float(f1_score(yte, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(yte, y_prob)) if len(set(yte)) > 1 else None,
        "pr_auc": float(average_precision_score(yte, y_prob)) if len(set(yte)) > 1 else None,
        "confusion_matrix": confusion_matrix(yte, y_pred).tolist(),
        "epochs_run": state["epoch_done"],
        "n_train": int(len(ytr)), "n_test": int(len(yte)),
        "n_features": int(Xtr.shape[1]),
    }
    out_path = os.path.join(RESULTS_DIR, f"{slug(name)}_sensitivity_v2.json")
    with open(out_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"[sens2-train] {name}: COMPLETE acc={metrics['accuracy']:.4f} f1={metrics['f1']:.4f} "
          f"recall={metrics['recall']:.4f} -> {out_path}")
    return True


if __name__ == "__main__":
    stage = sys.argv[1]
    name = sys.argv[2]
    budget = 165
    for i, a in enumerate(sys.argv):
        if a == "--budget":
            budget = int(sys.argv[i + 1])
    if stage == "search":
        _ok = run_search(name, budget_sec=budget)
    elif stage == "train":
        _ok = run_train_eval(name, budget_sec=budget)
    else:
        raise ValueError(stage)
    sys.exit(0 if _ok else 1)
