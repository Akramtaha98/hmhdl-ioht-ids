"""Random-search baseline for the hyperparameter search (same budget as
Lionfish: population 6 x (1 init + 6 iterations) = 42 candidate
evaluations), to test whether Lionfish outperforms unguided sampling.

Also: fast architecture-ablation screen using the SAME quick-evaluation
protocol as the Lionfish search (3 epochs, batch 1024, 80/20 split of the
training partition) -- CNN-only, CNN-LSTM, CNN-GRU, CNN-LSTM-GRU (no
attention), full hybrid, and full hybrid with default (non-optimized)
hyperparameters.
"""
import sys
import os
import json
import time
import numpy as np
from sklearn.model_selection import train_test_split

sys.path.insert(0, os.path.dirname(__file__))
from pipeline import (load_prep, BOUNDS, INT_PARAMS, RANDOM_STATE, QUICK_EPOCHS,
                       SEARCH_BATCH, clip_candidate, RESULTS_DIR, slug)
from tensorflow import keras
from tensorflow.keras import layers

N_CANDIDATES = 42  # matches Lionfish: 6 (init pop) + 6 iters * 6 = 42


def build_model_variant(input_shape, variant, n_conv_blocks, conv_filters,
                         lstm_units, gru_units, dropout_rate):
    """Same as pipeline.build_model but with switchable layers for ablation."""
    inputs = keras.Input(shape=input_shape)
    x = inputs
    if variant != "no_cnn":
        for _ in range(n_conv_blocks):
            x = layers.Conv1D(conv_filters, kernel_size=3, padding="same")(x)
            x = layers.LeakyReLU(alpha=0.3)(x)
            x = layers.BatchNormalization()(x)

    if variant in ("cnn_only",):
        pass
    elif variant in ("cnn_lstm",):
        x = layers.LSTM(lstm_units, return_sequences=True)(x)
    elif variant in ("cnn_gru",):
        x = layers.GRU(gru_units, return_sequences=True)(x)
    elif variant in ("cnn_lstm_gru", "cnn_lstm_gru_default"):
        x = layers.LSTM(lstm_units, return_sequences=True)(x)
        x = layers.GRU(gru_units, return_sequences=True)(x)
    elif variant in ("full", "full_default"):
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


def random_search(name, budget_sec=150):
    t0 = time.time()
    ckpt_path = os.path.join(os.path.dirname(RESULTS_DIR), "checkpoints", f"{slug(name)}_randsearch_ckpt.pkl")
    import pickle
    Xtr, Xte, ytr, yte = load_prep(name)
    Xtr_opt, Xval_opt, ytr_opt, yval_opt = train_test_split(
        Xtr, ytr, test_size=0.2, stratify=ytr, random_state=RANDOM_STATE
    )

    if os.path.exists(ckpt_path):
        with open(ckpt_path, "rb") as f:
            state = pickle.load(f)
        print(f"[randsearch] resuming {name} from {len(state['log'])}/{N_CANDIDATES}")
    else:
        state = {"log": [], "best_acc": -1, "best_params": None}

    rng = np.random.default_rng(RANDOM_STATE + 999)  # different stream than Lionfish
    # burn the rng forward to match how many candidates already evaluated
    for _ in range(len(state["log"])):
        {k: rng.uniform(lo, hi) for k, (lo, hi) in BOUNDS.items()}

    while len(state["log"]) < N_CANDIDATES:
        cand = clip_candidate({k: rng.uniform(lo, hi) for k, (lo, hi) in BOUNDS.items()})
        model = build_model_variant((Xtr_opt.shape[1], 1), "full", cand["n_conv_blocks"],
                                     cand["conv_filters"], cand["lstm_units"], cand["gru_units"],
                                     cand["dropout_rate"])
        model.fit(Xtr_opt, ytr_opt, epochs=QUICK_EPOCHS, batch_size=SEARCH_BATCH, verbose=0)
        val_acc = float(model.evaluate(Xval_opt, yval_opt, verbose=0)[1])
        keras.backend.clear_session()
        state["log"].append({"candidate": cand, "val_acc": val_acc})
        if val_acc > state["best_acc"]:
            state["best_acc"] = val_acc
            state["best_params"] = cand
        with open(ckpt_path, "wb") as fo:
            pickle.dump(state, fo)
        print(f"[randsearch] {name}: {len(state['log'])}/{N_CANDIDATES} val_acc={val_acc:.4f} "
              f"best_so_far={state['best_acc']:.4f} elapsed={time.time()-t0:.1f}s")
        if time.time() - t0 > budget_sec:
            print(f"[randsearch] {name}: budget hit, checkpointed, rerun to continue")
            return False

    out_path = os.path.join(RESULTS_DIR, f"{slug(name)}_randsearch.json")
    with open(out_path, "w") as f:
        json.dump({"best_val_acc": state["best_acc"], "best_params": state["best_params"],
                    "n_candidates": len(state["log"])}, f, indent=2)
    print(f"[randsearch] {name}: COMPLETE best_val_acc={state['best_acc']:.4f} -> {out_path}")
    return True


ABLATION_VARIANTS = ["cnn_only", "cnn_lstm", "cnn_gru", "cnn_lstm_gru", "full", "full_default"]
DEFAULT_PARAMS = {"n_conv_blocks": 2, "conv_filters": 32, "lstm_units": 32,
                   "gru_units": 32, "dropout_rate": 0.3}


def run_ablation(name, budget_sec=150):
    import pickle
    t0 = time.time()
    ckpt_path = os.path.join(os.path.dirname(RESULTS_DIR), "checkpoints", f"{slug(name)}_ablation_ckpt.pkl")
    Xtr, Xte, ytr, yte = load_prep(name)
    Xtr_opt, Xval_opt, ytr_opt, yval_opt = train_test_split(
        Xtr, ytr, test_size=0.2, stratify=ytr, random_state=RANDOM_STATE
    )
    with open(os.path.join(os.path.dirname(RESULTS_DIR), "checkpoints", f"{slug(name)}_best_params.json")) as f:
        best_params = json.load(f)["best_params"]

    if os.path.exists(ckpt_path):
        with open(ckpt_path, "rb") as f:
            results = pickle.load(f)
    else:
        results = {}

    for variant in ABLATION_VARIANTS:
        if variant in results:
            print(f"[ablation] {name}/{variant}: already done, skipping")
            continue
        params = DEFAULT_PARAMS if variant == "full_default" else best_params
        model = build_model_variant((Xtr_opt.shape[1], 1), variant, params["n_conv_blocks"],
                                     params["conv_filters"], params["lstm_units"],
                                     params["gru_units"], params["dropout_rate"])
        model.fit(Xtr_opt, ytr_opt, epochs=QUICK_EPOCHS, batch_size=SEARCH_BATCH, verbose=0)
        val_acc = float(model.evaluate(Xval_opt, yval_opt, verbose=0)[1])
        n_params = int(model.count_params())
        keras.backend.clear_session()
        results[variant] = {"val_acc": val_acc, "n_params": n_params}
        with open(ckpt_path, "wb") as fo:
            pickle.dump(results, fo)
        print(f"[ablation] {name}/{variant}: val_acc={val_acc:.4f} params={n_params} "
              f"elapsed={time.time()-t0:.1f}s")
        if time.time() - t0 > budget_sec:
            print(f"[ablation] {name}: budget hit, checkpointed, rerun to continue")
            return False

    out_path = os.path.join(RESULTS_DIR, f"{slug(name)}_ablation.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[ablation] {name}: COMPLETE -> {out_path}")
    return True


if __name__ == "__main__":
    mode = sys.argv[1]
    name = sys.argv[2]
    budget = 150
    for i, a in enumerate(sys.argv):
        if a == "--budget":
            budget = int(sys.argv[i + 1])
    if mode == "randsearch":
        _ok = random_search(name, budget_sec=budget)
    elif mode == "ablation":
        _ok = run_ablation(name, budget_sec=budget)
    else:
        raise ValueError(mode)
    sys.exit(0 if _ok else 1)
