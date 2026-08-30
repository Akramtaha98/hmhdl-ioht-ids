"""Alternative-split sensitivity analysis: replaces the main experiment's
record-level stratified random split with a harder, more realistic split
for each dataset, to test whether performance holds up when related
records cannot appear in both train and test:

  - ECU-IoHT: TEMPORAL split (train = earliest 70% of records by
    Wireshark capture Time, test = latest 30%).
  - WUSTL-EHMS-2020: TEMPORAL-STYLE split by Packet_num (train = earliest
    70% by packet sequence number, test = latest 30%).
  - DSICU: GROUP split by (tcp.srcport, tcp.dstport) flow/session pair
    (whole port-pair groups assigned to either train or test, so no
    flow's records appear in both partitions).

Reuses the SAME Lionfish-optimized hyperparameters already found for the
main (random-split) experiment -- this is a robustness check of the
architecture/hyperparameters under harder data partitioning, not a fresh
hyperparameter search. Trained at a reduced epoch budget (up to 20 epochs,
early stopping patience 5) for practicality; explicitly reported as a
smaller budget than the main results.
"""
import os
import sys
import json
import time
import pickle
import numpy as np
import pandas as pd
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                              f1_score, confusion_matrix, balanced_accuracy_score,
                              roc_auc_score, average_precision_score)

sys.path.insert(0, os.path.dirname(__file__))
from pipeline import build_model, RESULTS_DIR, CKPT_DIR, DATA_DIR, slug
from tensorflow import keras

SENS_EPOCHS = 20
SENS_BATCH = 128
SENS_PATIENCE = 5


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


def prep_ecu_temporal():
    df = pd.read_csv(os.path.join(DATA_DIR, "ECU_IoHT.csv"))
    df = df.sort_values("Time").reset_index(drop=True)
    y = (df["Type"] == "Attack").astype(int).values
    X = df[["Time", "Length", "Protocol"]].copy()
    X = pd.get_dummies(X, columns=["Protocol"], prefix="proto").astype(float).values
    n = len(df)
    cut = int(n * 0.7)
    Xtr_raw, Xte_raw = X[:cut], X[cut:]
    ytr, yte = y[:cut], y[cut:]
    return _finalize_split(Xtr_raw, Xte_raw, ytr, yte), ytr, yte


def prep_wustl_temporal():
    df = pd.read_csv(os.path.join(DATA_DIR, "wustl-ehms-2020.csv"))
    df = df.sort_values("Packet_num").reset_index(drop=True)
    y = df["label"].astype(int).values
    X = df.drop(columns=["label"]).astype(float).values
    n = len(df)
    cut = int(n * 0.7)
    Xtr_raw, Xte_raw = X[:cut], X[cut:]
    ytr, yte = y[:cut], y[cut:]
    return _finalize_split(Xtr_raw, Xte_raw, ytr, yte), ytr, yte


def prep_dsicu_group():
    df = pd.read_csv(os.path.join(DATA_DIR, "dsicu_mi.csv"))
    y = df["label"].astype(int).values
    X = df.drop(columns=["label"])
    groups = df.groupby(["tcp.srcport", "tcp.dstport"]).indices  # dict: (sport,dport)->row idx array
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
    print(f"[dsicu_group] {n_train_groups} train groups / {n_test_groups} test groups, "
          f"train_rows={train_mask.sum()} test_rows={test_mask.sum()}")
    return _finalize_split(Xtr_raw, Xte_raw, ytr, yte), ytr, yte


PREP_FUNCS = {
    "ECU-IoHT": prep_ecu_temporal,
    "WUSTL-EHMS-2020": prep_wustl_temporal,
    "DSICU": prep_dsicu_group,
}


def run_sensitivity(name, budget_sec=165):
    t0 = time.time()
    ckpt_state = os.path.join(CKPT_DIR, f"{slug(name)}_sens_state.pkl")
    ckpt_weights = os.path.join(CKPT_DIR, f"{slug(name)}_sens_model.weights.h5")
    ckpt_data = os.path.join(CKPT_DIR, f"{slug(name)}_sens_data.npz")

    if os.path.exists(ckpt_data):
        d = np.load(ckpt_data)
        Xtr, Xte, ytr, yte = d["Xtr"], d["Xte"], d["ytr"], d["yte"]
    else:
        (Xtr, Xte), ytr, yte = PREP_FUNCS[name]()
        np.savez_compressed(ckpt_data, Xtr=Xtr, Xte=Xte, ytr=ytr, yte=yte)

    with open(os.path.join(CKPT_DIR, f"{slug(name)}_best_params.json")) as f:
        best_params = json.load(f)["best_params"]

    model = build_model((Xtr.shape[1], 1), best_params["n_conv_blocks"], best_params["conv_filters"],
                         best_params["lstm_units"], best_params["gru_units"], best_params["dropout_rate"])

    if os.path.exists(ckpt_state):
        with open(ckpt_state, "rb") as f:
            state = pickle.load(f)
        model.load_weights(ckpt_weights)
    else:
        state = {"epoch_done": 0, "best_loss": np.inf, "bad_epochs": 0}

    while state["epoch_done"] < SENS_EPOCHS:
        hist = model.fit(Xtr, ytr, epochs=1, batch_size=SENS_BATCH, verbose=0)
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
        print(f"[sens] {name}: epoch {state['epoch_done']}/{SENS_EPOCHS} loss={loss:.4f} "
              f"elapsed={time.time()-t0:.1f}s")
        if state["bad_epochs"] >= SENS_PATIENCE:
            print(f"[sens] {name}: early stopping")
            break
        if time.time() - t0 > budget_sec:
            print(f"[sens] {name}: budget hit, checkpointed, rerun to continue")
            return False

    model.load_weights(ckpt_weights)
    y_prob = model.predict(Xte, verbose=0).ravel()
    y_pred = (y_prob >= 0.5).astype(int)
    metrics = {
        "split_type": {"ECU-IoHT": "temporal", "WUSTL-EHMS-2020": "temporal (Packet_num)",
                       "DSICU": "group (srcport,dstport)"}[name],
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
    }
    out_path = os.path.join(RESULTS_DIR, f"{slug(name)}_sensitivity.json")
    with open(out_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"[sens] {name}: COMPLETE acc={metrics['accuracy']:.4f} f1={metrics['f1']:.4f} "
          f"recall={metrics['recall']:.4f} -> {out_path}")
    return True


if __name__ == "__main__":
    name = sys.argv[1]
    budget = 165
    for i, a in enumerate(sys.argv):
        if a == "--budget":
            budget = int(sys.argv[i + 1])
    _ok = run_sensitivity(name, budget_sec=budget)
    sys.exit(0 if _ok else 1)
