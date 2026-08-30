"""
Leakage-free preprocessing + Hybrid CNN-LSTM-GRU-Attention pipeline
for the HMHDL (Lionfish-optimized) IoHT intrusion detection paper.

Datasets: ECU-IoHT, WUSTL-EHMS-2020, DSICU
Protocol: split-before-fit (train/test split BEFORE any fitting of
feature-selector or scaler), matching the leakage-free discipline
used in the companion QI-AWNS paper.

STAGED / CHECKPOINTED EXECUTION
--------------------------------
Each stage is runnable independently from the command line and resumes
from a checkpoint if interrupted (the sandbox this runs in caps a single
process to a few minutes of wall-clock time, so long experiments must be
split into resumable stages):

    python3 pipeline.py prep      <name>
    python3 pipeline.py search    <name>   [--budget SECONDS]
    python3 pipeline.py cv        <name>   [--budget SECONDS]
    python3 pipeline.py train     <name>   [--budget SECONDS]
    python3 pipeline.py evaluate  <name>

name in {"ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"}
"""
import os
import sys
import json
import time
import pickle
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                              f1_score, confusion_matrix, balanced_accuracy_score)

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

RANDOM_STATE = 42
# All paths are relative to the project root (the parent directory of this
# file's own `code/` folder), so this pipeline runs unmodified regardless of
# where the project is checked out.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
FIG_DIR = os.path.join(BASE_DIR, "figures")
CKPT_DIR = os.path.join(BASE_DIR, "checkpoints")

for d in (RESULTS_DIR, FIG_DIR, CKPT_DIR):
    os.makedirs(d, exist_ok=True)

tf.random.set_seed(RANDOM_STATE)
np.random.seed(RANDOM_STATE)


def slug(name):
    return name.replace(" ", "_")


def path_for(name, suffix):
    return os.path.join(CKPT_DIR, f"{slug(name)}_{suffix}")


# --------------------------------------------------------------------------
# Dataset loaders -> return raw X (DataFrame), y (ndarray of 0/1)
# --------------------------------------------------------------------------
def load_ecu():
    df = pd.read_csv(os.path.join(DATA_DIR, "ECU_IoHT.csv"))
    y = (df["Type"] == "Attack").astype(int).values
    X = df[["Time", "Length", "Protocol"]].copy()
    X = pd.get_dummies(X, columns=["Protocol"], prefix="proto")
    return X, y


def load_wustl():
    df = pd.read_csv(os.path.join(DATA_DIR, "wustl-ehms-2020.csv"))
    y = df["label"].astype(int).values
    X = df.drop(columns=["label"]).copy()
    return X, y


def load_dsicu():
    df = pd.read_csv(os.path.join(DATA_DIR, "dsicu_mi.csv"))
    y = df["label"].astype(int).values
    X = df.drop(columns=["label"]).copy()
    return X, y


LOADERS = {"ECU-IoHT": load_ecu, "WUSTL-EHMS-2020": load_wustl, "DSICU": load_dsicu}


# --------------------------------------------------------------------------
# STAGE 1: split-before-fit preprocessing -> checkpoint to .npz
# --------------------------------------------------------------------------
def stage_prep(name, k_features=None, test_size=0.3):
    X, y = LOADERS[name]()
    X = X.astype(float).values
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=RANDOM_STATE
    )

    train_std = Xtr.std(axis=0)
    keep_mask = train_std > 1e-12
    Xtr = Xtr[:, keep_mask]
    Xte = Xte[:, keep_mask]

    n_features = Xtr.shape[1]
    if k_features is None:
        k_features = n_features
    k_features = min(k_features, n_features)

    selector = SelectKBest(score_func=f_classif, k=k_features)
    selector.fit(Xtr, ytr)
    Xtr_sel = selector.transform(Xtr)
    Xte_sel = selector.transform(Xte)

    scaler = StandardScaler()
    scaler.fit(Xtr_sel)
    Xtr_scaled = scaler.transform(Xtr_sel).astype(np.float32)
    Xte_scaled = scaler.transform(Xte_sel).astype(np.float32)

    Xtr_final = Xtr_scaled.reshape((Xtr_scaled.shape[0], Xtr_scaled.shape[1], 1))
    Xte_final = Xte_scaled.reshape((Xte_scaled.shape[0], Xte_scaled.shape[1], 1))

    np.savez_compressed(path_for(name, "prep.npz"),
                         Xtr=Xtr_final, Xte=Xte_final, ytr=ytr, yte=yte)
    print(f"[prep] {name}: train={Xtr_final.shape} test={Xte_final.shape} "
          f"selected_features={Xtr_final.shape[1]} (kept {keep_mask.sum()}/{len(keep_mask)} raw cols)")


def load_prep(name):
    d = np.load(path_for(name, "prep.npz"))
    return d["Xtr"], d["Xte"], d["ytr"], d["yte"]


# --------------------------------------------------------------------------
# Hybrid CNN-LSTM-GRU-Attention model builder
# --------------------------------------------------------------------------
def build_model(input_shape, n_conv_blocks, conv_filters, lstm_units, gru_units, dropout_rate):
    inputs = keras.Input(shape=input_shape)
    x = inputs
    for _ in range(n_conv_blocks):
        x = layers.Conv1D(conv_filters, kernel_size=3, padding="same")(x)
        x = layers.LeakyReLU(alpha=0.3)(x)
        x = layers.BatchNormalization()(x)

    x = layers.LSTM(lstm_units, return_sequences=True)(x)
    x = layers.GRU(gru_units, return_sequences=True)(x)

    attn = layers.MultiHeadAttention(num_heads=4, key_dim=max(4, gru_units // 4))(x, x, x)
    x = layers.LayerNormalization()(attn + x)

    x = layers.GlobalAveragePooling1D()(x)
    x = layers.Dropout(dropout_rate)(x)
    outputs = layers.Dense(1, activation="sigmoid")(x)

    model = keras.Model(inputs, outputs)
    model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
    return model


# --------------------------------------------------------------------------
# Lionfish Optimization Algorithm (population-based metaheuristic)
# --------------------------------------------------------------------------
BOUNDS = {
    "n_conv_blocks": (1, 3),
    "conv_filters": (16, 64),
    "lstm_units": (16, 64),
    "gru_units": (16, 64),
    "dropout_rate": (0.1, 0.5),
}
INT_PARAMS = ["n_conv_blocks", "conv_filters", "lstm_units", "gru_units"]
POP_SIZE = 6
ITERATIONS = 6
QUICK_EPOCHS = 3
SEARCH_BATCH = 1024


def clip_candidate(cand):
    out = {}
    for k, v in cand.items():
        lo, hi = BOUNDS[k]
        v = min(max(v, lo), hi)
        out[k] = int(round(v)) if k in INT_PARAMS else float(v)
    return out


def evaluate_candidate(cand, Xtr, ytr, Xval, yval):
    params = clip_candidate(cand)
    model = build_model((Xtr.shape[1], 1), params["n_conv_blocks"], params["conv_filters"],
                         params["lstm_units"], params["gru_units"], params["dropout_rate"])
    model.fit(Xtr, ytr, epochs=QUICK_EPOCHS, batch_size=SEARCH_BATCH, verbose=0)
    val_acc = model.evaluate(Xval, yval, verbose=0)[1]
    keras.backend.clear_session()
    return 1.0 - val_acc, float(val_acc)


def stage_search(name, budget_sec=150):
    t0 = time.time()
    ckpt_path = path_for(name, "search_ckpt.pkl")
    Xtr, Xte, ytr, yte = load_prep(name)
    Xtr_opt, Xval_opt, ytr_opt, yval_opt = train_test_split(
        Xtr, ytr, test_size=0.2, stratify=ytr, random_state=RANDOM_STATE
    )

    if os.path.exists(ckpt_path):
        with open(ckpt_path, "rb") as f:
            state = pickle.load(f)
        print(f"[search] resuming {name} from iter {state['iter_done']}")
    else:
        rng = np.random.default_rng(RANDOM_STATE)
        population = [{k: rng.uniform(lo, hi) for k, (lo, hi) in BOUNDS.items()}
                      for _ in range(POP_SIZE)]
        state = {"rng_state": rng.bit_generator.state, "population": population,
                 "personal_best": None, "personal_best_fit": None,
                 "global_best": None, "global_best_fit": np.inf,
                 "iter_done": -1, "log": []}

    rng = np.random.default_rng(RANDOM_STATE)
    rng.bit_generator.state = state["rng_state"]

    if state["personal_best"] is None:
        fitness = []
        for cand in state["population"]:
            f, acc = evaluate_candidate(cand, Xtr_opt, ytr_opt, Xval_opt, yval_opt)
            fitness.append(f)
            state["log"].append({"iter": 0, "candidate": clip_candidate(cand), "val_acc": acc})
            if time.time() - t0 > budget_sec:
                state["rng_state"] = rng.bit_generator.state
                with open(ckpt_path, "wb") as fo:
                    pickle.dump(state, fo)
                print(f"[search] {name}: time budget hit during init pop, checkpointed, rerun to continue")
                return False
        state["personal_best"] = list(state["population"])
        state["personal_best_fit"] = fitness
        g_idx = int(np.argmin(fitness))
        state["global_best"] = dict(state["population"][g_idx])
        state["global_best_fit"] = fitness[g_idx]
        state["iter_done"] = 0

    for t in range(state["iter_done"] + 1, ITERATIONS + 1):
        E = rng.uniform(0.1, 1.0)
        a = rng.uniform(0, 1)
        C = rng.uniform(0.5, 1.5)
        D = 1.0 - np.exp(-E * t)
        VS = np.exp(-a * C)
        M = rng.uniform(0.2, 1.0)
        H = D * VS * M
        Hu = D * VS * M * H * E
        eta = 0.5
        prey = {k: rng.uniform(lo, hi) for k, (lo, hi) in BOUNDS.items()}

        new_population = []
        for cand in state["population"]:
            new_cand = {}
            for k in BOUNDS:
                lo, hi = BOUNDS[k]
                step = Hu * eta * (prey[k] - cand[k])
                new_cand[k] = min(max(cand[k] + step, lo), hi)
            new_population.append(new_cand)

        for i, cand in enumerate(new_population):
            f, acc = evaluate_candidate(cand, Xtr_opt, ytr_opt, Xval_opt, yval_opt)
            state["log"].append({"iter": t, "candidate": clip_candidate(cand), "val_acc": acc})
            if f < state["personal_best_fit"][i]:
                state["personal_best"][i] = cand
                state["personal_best_fit"][i] = f
            if time.time() - t0 > budget_sec:
                state["population"] = new_population
                state["rng_state"] = rng.bit_generator.state
                with open(ckpt_path, "wb") as fo:
                    pickle.dump(state, fo)
                print(f"[search] {name}: time budget hit mid-iter {t}, checkpointed, rerun to continue")
                return False

        state["population"] = new_population
        g_idx = int(np.argmin(state["personal_best_fit"]))
        if state["personal_best_fit"][g_idx] < state["global_best_fit"]:
            state["global_best_fit"] = state["personal_best_fit"][g_idx]
            state["global_best"] = dict(state["personal_best"][g_idx])
        state["iter_done"] = t
        state["rng_state"] = rng.bit_generator.state
        with open(ckpt_path, "wb") as fo:
            pickle.dump(state, fo)
        print(f"[search] {name}: iter {t}/{ITERATIONS} done, "
              f"best_val_acc={1-state['global_best_fit']:.4f}, elapsed={time.time()-t0:.1f}s")

    best_params = clip_candidate(state["global_best"])
    with open(path_for(name, "best_params.json"), "w") as f:
        json.dump({"best_params": best_params,
                    "best_val_acc_quick": 1.0 - state["global_best_fit"]}, f, indent=2)
    with open(os.path.join(RESULTS_DIR, f"{slug(name)}_lionfish_log.json"), "w") as f:
        json.dump(state["log"], f, indent=2)
    print(f"[search] {name}: COMPLETE. best_params={best_params}")
    return True


def load_best_params(name):
    with open(path_for(name, "best_params.json")) as f:
        d = json.load(f)
    return d["best_params"], d["best_val_acc_quick"]


# --------------------------------------------------------------------------
# STAGE 3: stratified k-fold CV for stability (checkpointed per fold)
# --------------------------------------------------------------------------
CV_FOLDS = 5
CV_EPOCHS = 10
CV_BATCH = 512


def stage_cv(name, budget_sec=150):
    t0 = time.time()
    ckpt_path = path_for(name, "cv_ckpt.pkl")
    Xtr, Xte, ytr, yte = load_prep(name)
    best_params, _ = load_best_params(name)
    n_selected = Xtr.shape[1]

    if os.path.exists(ckpt_path):
        with open(ckpt_path, "rb") as f:
            state = pickle.load(f)
    else:
        state = {"fold_accs": [], "fold_done": 0}

    skf = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    splits = list(skf.split(Xtr, ytr))

    for fold in range(state["fold_done"], CV_FOLDS):
        tr_idx, va_idx = splits[fold]
        model = build_model((n_selected, 1), **{k: best_params[k] for k in
                             ["n_conv_blocks", "conv_filters", "lstm_units", "gru_units", "dropout_rate"]})
        es = keras.callbacks.EarlyStopping(monitor="val_accuracy", patience=4, restore_best_weights=True)
        model.fit(Xtr[tr_idx], ytr[tr_idx], validation_data=(Xtr[va_idx], ytr[va_idx]),
                  epochs=CV_EPOCHS, batch_size=CV_BATCH, verbose=0, callbacks=[es])
        acc = float(model.evaluate(Xtr[va_idx], ytr[va_idx], verbose=0)[1])
        keras.backend.clear_session()
        state["fold_accs"].append(acc)
        state["fold_done"] = fold + 1
        with open(ckpt_path, "wb") as fo:
            pickle.dump(state, fo)
        print(f"[cv] {name}: fold {fold+1}/{CV_FOLDS} val_acc={acc:.4f} elapsed={time.time()-t0:.1f}s")
        if time.time() - t0 > budget_sec and fold + 1 < CV_FOLDS:
            print(f"[cv] {name}: time budget hit, checkpointed at fold {fold+1}, rerun to continue")
            return False

    cv_mean, cv_std = float(np.mean(state["fold_accs"])), float(np.std(state["fold_accs"]))
    with open(os.path.join(RESULTS_DIR, f"{slug(name)}_cv.json"), "w") as f:
        json.dump({"fold_accs": state["fold_accs"], "cv_mean": cv_mean, "cv_std": cv_std}, f, indent=2)
    print(f"[cv] {name}: COMPLETE. mean={cv_mean:.4f} std={cv_std:.4f}")
    return True


# --------------------------------------------------------------------------
# STAGE 4: final model training (resumable, epoch-by-epoch checkpointing)
# --------------------------------------------------------------------------
FINAL_EPOCHS = 80
FINAL_BATCH = 128
FINAL_PATIENCE = 8


def stage_train(name, budget_sec=150):
    t0 = time.time()
    ckpt_weights = path_for(name, "final_model.weights.h5")
    ckpt_state = path_for(name, "train_state.pkl")
    Xtr, Xte, ytr, yte = load_prep(name)
    best_params, _ = load_best_params(name)
    n_selected = Xtr.shape[1]

    model = build_model((n_selected, 1), **{k: best_params[k] for k in
                        ["n_conv_blocks", "conv_filters", "lstm_units", "gru_units", "dropout_rate"]})

    if os.path.exists(ckpt_state):
        with open(ckpt_state, "rb") as f:
            state = pickle.load(f)
        model.load_weights(ckpt_weights)
        print(f"[train] {name}: resuming from epoch {state['epoch_done']}")
    else:
        state = {"epoch_done": 0, "loss_history": [], "acc_history": [],
                  "best_loss": np.inf, "bad_epochs": 0, "train_time_sec": 0.0}

    while state["epoch_done"] < FINAL_EPOCHS:
        ep_t0 = time.time()
        hist = model.fit(Xtr, ytr, epochs=1, batch_size=FINAL_BATCH, verbose=0)
        ep_time = time.time() - ep_t0
        loss = float(hist.history["loss"][0])
        acc = float(hist.history["accuracy"][0])
        state["loss_history"].append(loss)
        state["acc_history"].append(acc)
        state["epoch_done"] += 1
        state["train_time_sec"] += ep_time

        if loss < state["best_loss"] - 1e-5:
            state["best_loss"] = loss
            state["bad_epochs"] = 0
            model.save_weights(ckpt_weights)
        else:
            state["bad_epochs"] += 1

        with open(ckpt_state, "wb") as fo:
            pickle.dump(state, fo)
        print(f"[train] {name}: epoch {state['epoch_done']}/{FINAL_EPOCHS} "
              f"loss={loss:.4f} acc={acc:.4f} ep_time={ep_time:.1f}s "
              f"total_elapsed={time.time()-t0:.1f}s")

        if state["bad_epochs"] >= FINAL_PATIENCE:
            print(f"[train] {name}: early stopping (no improvement for {FINAL_PATIENCE} epochs)")
            break
        if time.time() - t0 > budget_sec:
            print(f"[train] {name}: time budget hit at epoch {state['epoch_done']}, "
                  f"checkpointed, rerun to continue")
            return False

    model.load_weights(ckpt_weights)
    model.save(path_for(name, "final_model.keras"))
    print(f"[train] {name}: COMPLETE after {state['epoch_done']} epochs, "
          f"total_train_time={state['train_time_sec']:.1f}s")
    return True


# --------------------------------------------------------------------------
# STAGE 5: evaluation on held-out test set (once)
# --------------------------------------------------------------------------
def stage_evaluate(name):
    Xtr, Xte, ytr, yte = load_prep(name)
    best_params, best_val_acc_quick = load_best_params(name)
    model = keras.models.load_model(path_for(name, "final_model.keras"))
    with open(path_for(name, "train_state.pkl"), "rb") as f:
        train_state = pickle.load(f)

    y_prob = model.predict(Xte, verbose=0).ravel()
    y_pred = (y_prob >= 0.5).astype(int)

    cv_path = os.path.join(RESULTS_DIR, f"{slug(name)}_cv.json")
    cv_data = {}
    if os.path.exists(cv_path):
        with open(cv_path) as f:
            cv_data = json.load(f)

    metrics = {
        "dataset": name,
        "accuracy": float(accuracy_score(yte, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(yte, y_pred)),
        "precision": float(precision_score(yte, y_pred, zero_division=0)),
        "recall": float(recall_score(yte, y_pred, zero_division=0)),
        "f1": float(f1_score(yte, y_pred, zero_division=0)),
        "confusion_matrix": confusion_matrix(yte, y_pred).tolist(),
        "n_train": int(len(ytr)), "n_test": int(len(yte)),
        "n_selected_features": int(Xtr.shape[1]),
        "n_params": int(model.count_params()),
        "epochs_run": train_state["epoch_done"],
        "train_time_sec": train_state["train_time_sec"],
        "loss_history": train_state["loss_history"],
        "acc_history": train_state["acc_history"],
        "lionfish_best_params": best_params,
        "lionfish_best_val_acc_quick": best_val_acc_quick,
        **cv_data,
    }
    out_path = os.path.join(RESULTS_DIR, f"{slug(name)}_results.json")
    with open(out_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"[evaluate] {name}: accuracy={metrics['accuracy']:.4f} f1={metrics['f1']:.4f} "
          f"params={metrics['n_params']}")
    print(f"[evaluate] Saved -> {out_path}")
    return metrics


if __name__ == "__main__":
    stage = sys.argv[1]
    name = sys.argv[2]
    budget = 150
    for i, a in enumerate(sys.argv):
        if a == "--budget":
            budget = int(sys.argv[i + 1])

    _ok = True
    if stage == "prep":
        stage_prep(name)
    elif stage == "search":
        _ok = stage_search(name, budget_sec=budget)
    elif stage == "cv":
        _ok = stage_cv(name, budget_sec=budget)
    elif stage == "train":
        _ok = stage_train(name, budget_sec=budget)
    elif stage == "evaluate":
        stage_evaluate(name)
    else:
        raise ValueError(f"unknown stage {stage}")
    sys.exit(0 if _ok else 1)
