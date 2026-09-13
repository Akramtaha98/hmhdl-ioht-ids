"""
Class-imbalance fix for WUSTL-EHMS-2020, v2: compares plain class-weighted
BCE against focal loss, and reports a full precision/recall/F1 threshold
sweep (not just one cherry-picked point) so the true achievable trade-off
is visible rather than implied.

Same architecture, same split, same protocol discipline as v1
(recall_fix_wustl.py): trains on 85% of the train partition with its own
training-loss early stopping (matching stage_train's protocol), holds out
15% of TRAIN ONLY for threshold selection, and touches the test set exactly
once at the end.

Usage: python3 recall_fix_wustl_v2.py
Writes results/WUSTL-EHMS-2020_recall_fix_v2.json
"""
import os
import sys
import json
import time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline as P

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from sklearn.model_selection import train_test_split
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                              f1_score, confusion_matrix, balanced_accuracy_score,
                              precision_recall_curve, roc_auc_score, average_precision_score)

RANDOM_STATE = 42
tf.random.set_seed(RANDOM_STATE)
np.random.seed(RANDOM_STATE)

NAME = "WUSTL-EHMS-2020"
RESULTS_DIR = P.RESULTS_DIR


def focal_loss(gamma=2.0, alpha=0.25):
    def loss_fn(y_true, y_pred):
        y_true = tf.cast(y_true, tf.float32)
        eps = keras.backend.epsilon()
        y_pred = tf.clip_by_value(y_pred, eps, 1.0 - eps)
        pt = tf.where(tf.equal(y_true, 1), y_pred, 1 - y_pred)
        alpha_t = tf.where(tf.equal(y_true, 1), alpha, 1 - alpha)
        loss = -alpha_t * tf.pow(1.0 - pt, gamma) * tf.math.log(pt)
        return tf.reduce_mean(loss)
    return loss_fn


def build_model(input_shape, n_conv_blocks, conv_filters, lstm_units, gru_units, dropout_rate, loss):
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
    model.compile(optimizer="adam", loss=loss, metrics=["accuracy"])
    return model


def train_variant(name, loss, class_weight, Xtr_fit, ytr_fit, arch_kwargs, n_selected):
    model = build_model((n_selected, 1), **arch_kwargs, loss=loss)
    best_loss = np.inf
    bad_epochs = 0
    patience = 8
    best_weights = None
    epochs_run = 0
    for epoch in range(80):
        fit_kwargs = dict(epochs=1, batch_size=128, verbose=0)
        if class_weight is not None:
            fit_kwargs["class_weight"] = class_weight
        hist = model.fit(Xtr_fit, ytr_fit, **fit_kwargs)
        loss_val = float(hist.history["loss"][0])
        epochs_run += 1
        if loss_val < best_loss - 1e-5:
            best_loss = loss_val
            bad_epochs = 0
            best_weights = model.get_weights()
        else:
            bad_epochs += 1
        if bad_epochs >= patience:
            break
    if best_weights is not None:
        model.set_weights(best_weights)
    return model, epochs_run


def threshold_sweep(y_true, y_prob, thresholds):
    rows = []
    for t in thresholds:
        y_pred = (y_prob >= t).astype(int)
        rows.append({
            "threshold": float(t),
            "precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, zero_division=0)),
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        })
    return rows


def main():
    t0 = time.time()
    Xtr, Xte, ytr, yte = P.load_prep(NAME)
    best_params, _ = P.load_best_params(NAME)
    n_selected = Xtr.shape[1]
    arch_kwargs = {k: best_params[k] for k in
                   ["n_conv_blocks", "conv_filters", "lstm_units", "gru_units", "dropout_rate"]}

    Xtr_fit, Xval, ytr_fit, yval = train_test_split(
        Xtr, ytr, test_size=0.15, stratify=ytr, random_state=RANDOM_STATE
    )

    n_pos = int(ytr_fit.sum())
    n_neg = int(len(ytr_fit) - n_pos)
    class_weight = {0: 1.0, 1: n_neg / n_pos}

    results = {}
    for variant_name, loss, cw in [
        ("class_weighted_bce", "binary_crossentropy", class_weight),
        ("focal_loss", focal_loss(2.0, 0.25), None),
    ]:
        vt0 = time.time()
        model, epochs_run = train_variant(variant_name, loss, cw, Xtr_fit, ytr_fit, arch_kwargs, n_selected)
        vtime = time.time() - vt0

        yval_prob = model.predict(Xval, verbose=0).ravel()
        prec, rec, thr = precision_recall_curve(yval, yval_prob)
        f1s = 2 * prec * rec / (prec + rec + 1e-12)
        best_idx = int(np.nanargmax(f1s[:-1])) if len(thr) > 0 else 0
        best_threshold = float(thr[best_idx]) if len(thr) > 0 else 0.5

        yte_prob = model.predict(Xte, verbose=0).ravel()
        sweep_thresholds = [0.1, 0.2, 0.3, 0.4, 0.5, best_threshold]
        sweep = threshold_sweep(yte, yte_prob, sorted(set(sweep_thresholds)))

        results[variant_name] = {
            "epochs_run": epochs_run,
            "train_time_sec": vtime,
            "roc_auc_test": float(roc_auc_score(yte, yte_prob)),
            "pr_auc_test": float(average_precision_score(yte, yte_prob)),
            "validation_selected_threshold": best_threshold,
            "test_at_validation_threshold": threshold_sweep(yte, yte_prob, [best_threshold])[0],
            "test_at_default_0.5": threshold_sweep(yte, yte_prob, [0.5])[0],
            "test_threshold_sweep": sweep,
        }
        print(variant_name, "done in", vtime, "s")

    baseline_recall = 0.5521172638436482
    baseline_f1 = 0.6793587174348698
    baseline_precision = 0.8828125
    baseline_roc_auc = None
    try:
        with open(os.path.join(RESULTS_DIR, f"{P.slug(NAME)}_extra_metrics.json")) as f:
            extra = json.load(f)
        baseline_roc_auc = extra.get("roc_auc")
    except Exception:
        pass

    out = {
        "dataset": NAME,
        "architecture": arch_kwargs,
        "baseline_main_experiment": {
            "recall": baseline_recall, "precision": baseline_precision,
            "f1": baseline_f1, "roc_auc": baseline_roc_auc,
            "note": "plain BCE, default 0.5 threshold, from the main experiment (Table 6)",
        },
        "variants": results,
        "total_wall_time_sec": time.time() - t0,
    }
    out_path = os.path.join(RESULTS_DIR, f"{P.slug(NAME)}_recall_fix_v2.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
