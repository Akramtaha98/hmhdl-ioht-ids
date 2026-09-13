"""
Sliding-window ECU-IoHT experiment, v2: fixes two confounds identified after
reviewing v1's result (sliding_window_ecu.py, which collapsed to predicting
the majority class and showed no improvement over the flat baseline):

  1. Drops the raw "Time" feature (an absolute wall-clock value that differs
     systematically between the early-time train partition and late-time
     test partition under this temporal split) -- matching the design
     already used in the existing, fairer sensitivity_v2 comparison.
  2. Uses the SAME independently-searched hyperparameters as that fairer
     comparison (ECU-IoHT_sensitivity_v2.json: hyperparameters found by a
     42-candidate random search INSIDE this split's own training partition,
     not reused from the main random-split experiment) instead of reusing
     the main experiment's hyperparameters, which were tuned for a
     different split and were the dominant cause of v1's collapse.

This isolates the one remaining variable of interest: does giving the model
genuine multi-packet sequences (T=10 real timesteps) instead of the
feature-axis-as-pseudo-sequence framing improve on the already-fixed,
already-fair 85.8% accuracy reported in sensitivity_v2.json?

Usage: python3 sliding_window_ecu_v2.py [window_length]
Writes results/ECU-IoHT_sliding_window_v2.json
"""
import os
import sys
import json
import time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline as P

from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                              f1_score, confusion_matrix, balanced_accuracy_score,
                              roc_auc_score, average_precision_score)
from tensorflow import keras
from tensorflow.keras import layers

NAME = "ECU-IoHT"
WINDOW_LEN = int(sys.argv[1]) if len(sys.argv) > 1 else 10
SENS_EPOCHS = 20
SENS_BATCH = 128
SENS_PATIENCE = 5
DATA_DIR = P.DATA_DIR
RESULTS_DIR = P.RESULTS_DIR


def build_windowed_model(input_shape, n_conv_blocks, conv_filters, lstm_units,
                          gru_units, dropout_rate):
    inputs = keras.Input(shape=input_shape)
    x = inputs
    for _ in range(n_conv_blocks):
        x = layers.Conv1D(conv_filters, kernel_size=3, padding="same")(x)
        x = layers.LeakyReLU(negative_slope=0.3)(x)
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


def make_windows(X, y, T):
    n = X.shape[0]
    n_windows = n - T + 1
    Xw = np.lib.stride_tricks.sliding_window_view(X, T, axis=0)
    Xw = np.transpose(Xw, (0, 2, 1))
    yw = y[T - 1:]
    return Xw.astype(np.float32), yw


def main():
    t0 = time.time()
    df = pd.read_csv(os.path.join(DATA_DIR, "ECU_IoHT.csv"))
    df = df.sort_values("Time").reset_index(drop=True)
    y_all = (df["Type"] == "Attack").astype(int).values
    # Time DROPPED (matches sensitivity_v2's design) -- only Length + one-hot
    # Protocol remain, avoiding the absolute-timestamp distribution shift
    # between the early-time train partition and late-time test partition.
    X_all = df[["Length", "Protocol"]].copy()
    X_all = pd.get_dummies(X_all, columns=["Protocol"], prefix="proto").astype(float).values

    n = len(df)
    cut = int(n * 0.7)
    Xtr_raw, Xte_raw = X_all[:cut], X_all[cut:]
    ytr_raw, yte_raw = y_all[:cut], y_all[cut:]

    train_std = Xtr_raw.std(axis=0)
    keep_mask = train_std > 1e-12
    Xtr_raw = Xtr_raw[:, keep_mask]
    Xte_raw = Xte_raw[:, keep_mask]

    scaler = StandardScaler()
    scaler.fit(Xtr_raw)
    Xtr_scaled = scaler.transform(Xtr_raw).astype(np.float32)
    Xte_scaled = scaler.transform(Xte_raw).astype(np.float32)

    Xtr_win, ytr_win = make_windows(Xtr_scaled, ytr_raw, WINDOW_LEN)
    Xte_win, yte_win = make_windows(Xte_scaled, yte_raw, WINDOW_LEN)
    print(f"Windowed shapes: train={Xtr_win.shape} test={Xte_win.shape}", flush=True)

    with open(os.path.join(RESULTS_DIR, "ECU-IoHT_sensitivity_v2.json")) as f:
        sens_v2 = json.load(f)
    arch_kwargs = {k: sens_v2["best_params"][k] for k in
                   ["n_conv_blocks", "conv_filters", "lstm_units", "gru_units", "dropout_rate"]}

    model = build_windowed_model((WINDOW_LEN, Xtr_win.shape[2]), **arch_kwargs)
    es = keras.callbacks.EarlyStopping(monitor="loss", patience=SENS_PATIENCE, restore_best_weights=True)
    hist = model.fit(Xtr_win, ytr_win, epochs=SENS_EPOCHS, batch_size=SENS_BATCH,
                      verbose=0, callbacks=[es])
    train_time = time.time() - t0
    epochs_run = len(hist.history["loss"])

    y_prob = model.predict(Xte_win, verbose=0).ravel()
    y_pred = (y_prob >= 0.5).astype(int)

    result = {
        "dataset": NAME,
        "experiment": "true_sliding_window_sequences_v2_time_dropped_fair_hparams",
        "window_length": WINDOW_LEN,
        "n_train_windows": int(Xtr_win.shape[0]),
        "n_test_windows": int(Xte_win.shape[0]),
        "architecture": arch_kwargs,
        "epochs_run": epochs_run,
        "train_time_sec": train_time,
        "accuracy": float(accuracy_score(yte_win, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(yte_win, y_pred)),
        "precision": float(precision_score(yte_win, y_pred, zero_division=0)),
        "recall": float(recall_score(yte_win, y_pred, zero_division=0)),
        "f1": float(f1_score(yte_win, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(yte_win, y_prob)),
        "pr_auc": float(average_precision_score(yte_win, y_prob)),
        "confusion_matrix": confusion_matrix(yte_win, y_pred).tolist(),
        "fair_comparison_baseline_sensitivity_v2": {
            "description": "flat feature-axis-as-sequence model, SAME temporal split, "
                            "SAME independently-searched hyperparameters, Time also dropped",
            "accuracy": sens_v2["accuracy"], "f1": sens_v2["f1"],
            "recall": sens_v2["recall"], "precision": sens_v2["precision"],
        },
    }

    out_path = os.path.join(RESULTS_DIR, "ECU-IoHT_sliding_window_v2.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps({k: v for k, v in result.items()}, indent=2))
    print(f"Saved -> {out_path}")
    print(f"Total wall time: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
