"""Re-checks the MAIN (random-split) experiment with capture-order /
identifier-like fields removed from the feature set, to test whether the
headline numbers depend on fields that behave more like a row/flow
identifier than a deployable security signal:

  - ECU-IoHT: drop `Time` (kept as a legitimate feature in the main
    experiment, but also used to define the temporal sensitivity split).
  - WUSTL-EHMS-2020: drop `Packet_num` (a raw packet sequence number).
  - DSICU: drop `tcp.srcport` and `tcp.dstport` (used to define the
    flow-grouped sensitivity split; a specific port pair can be close to
    a unique flow identifier when many pairs have very few records).

Reuses the SAME Lionfish-optimized hyperparameters already found for the
main experiment (dropping a handful of input features does not change
which architecture/dropout configuration was selected, and re-searching
was not the point of this check); only the preprocessing and final
training/evaluation are redone.
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
from pipeline import build_model, RESULTS_DIR, CKPT_DIR, DATA_DIR, slug, RANDOM_STATE
from sklearn.model_selection import train_test_split
from tensorflow import keras

NOID_EPOCHS = 40
NOID_BATCH = 128
NOID_PATIENCE = 6


def _finalize(Xtr_raw, Xte_raw, ytr, yte):
    train_std = Xtr_raw.std(axis=0)
    keep_mask = train_std > 1e-12
    Xtr_raw = Xtr_raw[:, keep_mask]
    Xte_raw = Xte_raw[:, keep_mask]
    selector = SelectKBest(score_func=f_classif, k=Xtr_raw.shape[1])
    selector.fit(Xtr_raw, ytr)
    Xtr_sel, Xte_sel = selector.transform(Xtr_raw), selector.transform(Xte_raw)
    scaler = StandardScaler()
    scaler.fit(Xtr_sel)
    Xtr_scaled = scaler.transform(Xtr_sel).astype(np.float32)
    Xte_scaled = scaler.transform(Xte_sel).astype(np.float32)
    return (Xtr_scaled.reshape(*Xtr_scaled.shape, 1), Xte_scaled.reshape(*Xte_scaled.shape, 1))


def prep_ecu_noid():
    df = pd.read_csv(os.path.join(DATA_DIR, "ECU_IoHT.csv"))
    y = (df["Type"] == "Attack").astype(int).values
    X = df[["Length", "Protocol"]].copy()  # dropped: Time
    X = pd.get_dummies(X, columns=["Protocol"], prefix="proto").astype(float).values
    idx = np.arange(len(y))
    idx_tr, idx_te = train_test_split(idx, test_size=0.3, stratify=y, random_state=RANDOM_STATE)
    Xtr, Xte = _finalize(X[idx_tr], X[idx_te], y[idx_tr], y[idx_te])
    return Xtr, Xte, y[idx_tr], y[idx_te]


def prep_wustl_noid():
    df = pd.read_csv(os.path.join(DATA_DIR, "wustl-ehms-2020.csv"))
    y = df["label"].astype(int).values
    X = df.drop(columns=["label", "Packet_num"]).astype(float).values  # dropped: Packet_num
    idx = np.arange(len(y))
    idx_tr, idx_te = train_test_split(idx, test_size=0.3, stratify=y, random_state=RANDOM_STATE)
    Xtr, Xte = _finalize(X[idx_tr], X[idx_te], y[idx_tr], y[idx_te])
    return Xtr, Xte, y[idx_tr], y[idx_te]


def prep_dsicu_noid():
    df = pd.read_csv(os.path.join(DATA_DIR, "dsicu_mi.csv"))
    y = df["label"].astype(int).values
    X = df.drop(columns=["label", "tcp.srcport", "tcp.dstport"]).astype(float).values  # dropped: ports
    idx = np.arange(len(y))
    idx_tr, idx_te = train_test_split(idx, test_size=0.3, stratify=y, random_state=RANDOM_STATE)
    Xtr, Xte = _finalize(X[idx_tr], X[idx_te], y[idx_tr], y[idx_te])
    return Xtr, Xte, y[idx_tr], y[idx_te]


PREP_FUNCS = {"ECU-IoHT": prep_ecu_noid, "WUSTL-EHMS-2020": prep_wustl_noid, "DSICU": prep_dsicu_noid}
DROPPED = {"ECU-IoHT": "Time", "WUSTL-EHMS-2020": "Packet_num", "DSICU": "tcp.srcport, tcp.dstport"}


def run(name, budget_sec=165):
    t0 = time.time()
    ckpt_state = os.path.join(CKPT_DIR, f"{slug(name)}_noid_state.pkl")
    ckpt_weights = os.path.join(CKPT_DIR, f"{slug(name)}_noid_model.weights.h5")
    ckpt_data = os.path.join(CKPT_DIR, f"{slug(name)}_noid_data.npz")

    if os.path.exists(ckpt_data):
        d = np.load(ckpt_data)
        Xtr, Xte, ytr, yte = d["Xtr"], d["Xte"], d["ytr"], d["yte"]
    else:
        Xtr, Xte, ytr, yte = PREP_FUNCS[name]()
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

    while state["epoch_done"] < NOID_EPOCHS:
        hist = model.fit(Xtr, ytr, epochs=1, batch_size=NOID_BATCH, verbose=0)
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
        print(f"[noid] {name}: epoch {state['epoch_done']}/{NOID_EPOCHS} loss={loss:.4f} "
              f"elapsed={time.time()-t0:.1f}s")
        if state["bad_epochs"] >= NOID_PATIENCE:
            print(f"[noid] {name}: early stopping")
            break
        if time.time() - t0 > budget_sec:
            print(f"[noid] {name}: budget hit, checkpointed, rerun to continue")
            return False

    model.load_weights(ckpt_weights)
    y_prob = model.predict(Xte, verbose=0).ravel()
    y_pred = (y_prob >= 0.5).astype(int)
    metrics = {
        "dropped_features": DROPPED[name],
        "accuracy": float(accuracy_score(yte, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(yte, y_pred)),
        "precision": float(precision_score(yte, y_pred, zero_division=0)),
        "recall": float(recall_score(yte, y_pred, zero_division=0)),
        "f1": float(f1_score(yte, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(yte, y_prob)) if len(set(yte)) > 1 else None,
        "pr_auc": float(average_precision_score(yte, y_prob)) if len(set(yte)) > 1 else None,
        "epochs_run": state["epoch_done"],
        "n_features": int(Xtr.shape[1]),
    }
    out_path = os.path.join(RESULTS_DIR, f"{slug(name)}_noid.json")
    with open(out_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"[noid] {name}: COMPLETE acc={metrics['accuracy']:.4f} f1={metrics['f1']:.4f} -> {out_path}")
    return True


if __name__ == "__main__":
    name = sys.argv[1]
    budget = 165
    for i, a in enumerate(sys.argv):
        if a == "--budget":
            budget = int(sys.argv[i + 1])
    _ok = run(name, budget_sec=budget)
    sys.exit(0 if _ok else 1)
