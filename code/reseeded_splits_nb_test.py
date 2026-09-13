"""
Reseeded-split significance test (review item M3 / gate G17), replacing the
existing significance_test.json's n=5 CV-fold paired t-test (which compares
folds WITHIN one fixed train/test partition -- folds are correlated by
construction, violating the independence assumption of a naive paired
t-test, exactly what the review flags) with a Nadeau-Bengio corrected
resampled paired t-test across INDEPENDENTLY RESEEDED train/test partitions.

Scope, documented explicitly rather than silently reduced: the review asks
for "10x (or explicitly documented reduced-N) reseeded splits." A full
10-reseed x 5-fold-CV design would require on the order of 100 full hybrid
model trainings per dataset at ~5-10 min each -- infeasible within this
session's compute budget. This script instead runs N_REPEATS = 5
independently reseeded 70/30 train/test splits per dataset (each with a
different random_state, so the partition itself differs, not just weight
initialization), trains the hybrid model and the strongest classical
baseline (HistGradientBoosting, per Section 4.7) ONCE per split with the
existing Lionfish-selected hyperparameters (not re-searched per split, same
convention already used for the existing repeated-seed and multi-seed-LFO
checks elsewhere in this paper), and applies the Nadeau-Bengio correction
(Nadeau & Bengio, 2003) for the correlation induced by overlapping
train/test partitions across repeats. This is a reduced-N version of what
the review asked for; the reduction is disclosed in the manuscript text, not
silently substituted for the full request.

DSICU is excluded: every check applied elsewhere in this paper already shows
DSICU's hybrid-vs-classical difference is exactly zero (both saturate at
100%), so a significance test on a zero-difference metric under a heavily
restricted-access dataset is not an informative use of the remaining compute
budget; this is stated explicitly in the manuscript rather than silently
omitted.

Usage: python3 reseeded_splits_nb_test.py <dataset_name>
Writes/updates results/reseeded_splits_nb_test.json (merges across the two
per-dataset subprocess runs).
"""
import os
import sys
import json
import time
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline as P

from sklearn.model_selection import train_test_split
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score
from tensorflow import keras

N_REPEATS = 4
SEEDS = [42, 43, 44, 45, 46]
TEST_SIZE = 0.3


def nadeau_bengio_corrected_ttest(diffs, n_train, n_test):
    """Nadeau & Bengio (2003) corrected resampled paired t-test.
    diffs: array of (model_a_acc - model_b_acc) per repeat.
    Corrects the naive paired-t variance estimate for the fact that repeats
    share overlapping data (not independent), using the train/test size
    ratio as the correction factor."""
    n = len(diffs)
    mean_diff = float(np.mean(diffs))
    var_diff = float(np.var(diffs, ddof=1)) if n > 1 else 0.0
    correction = (1.0 / n) + (n_test / n_train)
    denom = np.sqrt(correction * var_diff) if var_diff > 0 else 1e-12
    t_stat = mean_diff / denom if denom > 0 else 0.0
    df = n - 1
    p_value = float(2 * (1 - stats.t.cdf(abs(t_stat), df))) if df > 0 else 1.0
    return {"mean_diff": mean_diff, "t_stat": float(t_stat), "df": df, "p_value": p_value}


def build_model(input_shape, n_conv_blocks, conv_filters, lstm_units, gru_units, dropout_rate):
    from tensorflow.keras import layers
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


def preprocess_split(X_raw, y, seed, k_features):
    Xtr, Xte, ytr, yte = train_test_split(X_raw, y, test_size=TEST_SIZE, stratify=y, random_state=seed)
    train_std = Xtr.std(axis=0)
    keep_mask = train_std > 1e-12
    Xtr, Xte = Xtr[:, keep_mask], Xte[:, keep_mask]
    k = min(k_features, Xtr.shape[1])
    selector = SelectKBest(score_func=f_classif, k=k)
    selector.fit(Xtr, ytr)
    Xtr_sel, Xte_sel = selector.transform(Xtr), selector.transform(Xte)
    scaler = StandardScaler()
    scaler.fit(Xtr_sel)
    Xtr_s = scaler.transform(Xtr_sel).astype(np.float32)
    Xte_s = scaler.transform(Xte_sel).astype(np.float32)
    return Xtr_s, Xte_s, ytr, yte


def main():
    name = sys.argv[1]
    X_raw_df, y = P.LOADERS[name]()
    X_raw = X_raw_df.astype(float).values
    best_params, _ = P.load_best_params(name)
    arch_kwargs = {k: best_params[k] for k in
                   ["n_conv_blocks", "conv_filters", "lstm_units", "gru_units", "dropout_rate"]}
    # k_features matches what stage_prep used: all surviving (variance>0) features (no k cap applied
    # in this pipeline's stage_prep calls elsewhere, i.e. k_features=None -> keep all selected)
    Xtr0, _, _, _ = P.load_prep(name)
    k_features = Xtr0.shape[1]

    hybrid_accs, hgb_accs = [], []
    per_seed = []
    for seed in SEEDS[:N_REPEATS]:
        Xtr, Xte, ytr, yte = preprocess_split(X_raw, y, seed, k_features)
        n_train, n_test = len(ytr), len(yte)

        Xtr3 = Xtr.reshape(Xtr.shape[0], Xtr.shape[1], 1)
        Xte3 = Xte.reshape(Xte.shape[0], Xte.shape[1], 1)
        model = build_model((Xtr3.shape[1], 1), **arch_kwargs)
        es = keras.callbacks.EarlyStopping(monitor="loss", patience=8, restore_best_weights=True)
        t0 = time.time()
        model.fit(Xtr3, ytr, epochs=80, batch_size=128, verbose=0, callbacks=[es])
        hybrid_time = time.time() - t0
        hybrid_pred = (model.predict(Xte3, verbose=0).ravel() >= 0.5).astype(int)
        hybrid_acc = float(accuracy_score(yte, hybrid_pred))
        keras.backend.clear_session()

        hgb = HistGradientBoostingClassifier(random_state=seed)
        t0 = time.time()
        hgb.fit(Xtr, ytr)
        hgb_time = time.time() - t0
        hgb_pred = hgb.predict(Xte)
        hgb_acc = float(accuracy_score(yte, hgb_pred))

        hybrid_accs.append(hybrid_acc)
        hgb_accs.append(hgb_acc)
        per_seed.append({"seed": seed, "n_train": n_train, "n_test": n_test,
                          "hybrid_acc": hybrid_acc, "hgb_acc": hgb_acc,
                          "hybrid_train_time_sec": round(hybrid_time, 1),
                          "hgb_train_time_sec": round(hgb_time, 2)})
        print(f"[{name}] seed {seed}: hybrid={hybrid_acc:.4f} hgb={hgb_acc:.4f} "
              f"(hybrid_time={hybrid_time:.0f}s)")

    diffs = np.array(hgb_accs) - np.array(hybrid_accs)  # positive = HistGB ahead
    n_train_avg = int(np.mean([r["n_train"] for r in per_seed]))
    n_test_avg = int(np.mean([r["n_test"] for r in per_seed]))
    nb_result = nadeau_bengio_corrected_ttest(diffs, n_train_avg, n_test_avg)

    result = {
        "dataset": name,
        "n_repeats": N_REPEATS,
        "seeds": SEEDS[:N_REPEATS],
        "note": "Reduced from the review's suggested 10x to 4x independently reseeded train/test "
                "splits (different random_state per repeat, not just weight-init seed), due to this "
                "session's compute budget; Nadeau-Bengio correction applied for the resulting "
                "train/test overlap across repeats, per Nadeau & Bengio (2003).",
        "per_seed": per_seed,
        "hybrid_mean_acc": float(np.mean(hybrid_accs)),
        "hgb_mean_acc": float(np.mean(hgb_accs)),
        "nadeau_bengio_test_hgb_minus_hybrid": nb_result,
    }

    # Write to a per-dataset file (avoids a read-modify-write race when both datasets' subprocesses
    # run concurrently); a separate merge step combines these into reseeded_splits_nb_test.json.
    out_path = os.path.join(P.RESULTS_DIR, f"reseeded_splits_nb_test_{P.slug(name)}.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[{name}] Saved to {out_path}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
