"""
Runs ONE (dataset, seed) LFO+RandomSearch pair in its own process, then
merges the result into results/{name}_lfo_vs_rs_multiseed.json.

This exists because the original lfo_vs_random_multiseed.py leaked memory
across many sequential Keras model builds inside a single long-lived
process (despite calling keras.backend.clear_session() after every
candidate) and was OOM-killed by the container's cgroup partway through.
Running each seed-pair as its own subprocess guarantees the OS fully
reclaims all memory when the process exits, at the cost of re-loading data
each time (a few seconds, negligible next to ~15-40 min of training).

Usage: python3 run_single_seed_pair.py <dataset_name> <seed>
"""
import os
import sys
import json
import time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline as P

from sklearn.model_selection import train_test_split
from tensorflow import keras
from tensorflow.keras import layers

RESULTS_DIR = P.RESULTS_DIR
RANDOM_STATE = P.RANDOM_STATE

BOUNDS6 = dict(P.BOUNDS)
BOUNDS6["log_lr"] = (-4.0, -2.0)
INT_PARAMS6 = list(P.INT_PARAMS)
N_CANDIDATES = 42
QUICK_EPOCHS = P.QUICK_EPOCHS
SEARCH_BATCH = P.SEARCH_BATCH
POP_SIZE = 6
ITERATIONS = 6


def clip6(cand):
    out = {}
    for k, v in cand.items():
        lo, hi = BOUNDS6[k]
        v = min(max(v, lo), hi)
        out[k] = int(round(v)) if k in INT_PARAMS6 else float(v)
    return out


def build_model6(input_shape, n_conv_blocks, conv_filters, lstm_units, gru_units,
                  dropout_rate, log_lr):
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
    lr = 10 ** log_lr
    model.compile(optimizer=keras.optimizers.Adam(learning_rate=lr),
                  loss="binary_crossentropy", metrics=["accuracy"])
    return model


def evaluate_candidate6(cand, Xtr, ytr, Xval, yval):
    import gc
    params = clip6(cand)
    model = build_model6((Xtr.shape[1], 1), params["n_conv_blocks"], params["conv_filters"],
                          params["lstm_units"], params["gru_units"], params["dropout_rate"],
                          params["log_lr"])
    model.fit(Xtr, ytr, epochs=QUICK_EPOCHS, batch_size=SEARCH_BATCH, verbose=0)
    val_acc = model.evaluate(Xval, yval, verbose=0)[1]
    del model
    keras.backend.clear_session()
    gc.collect()
    return float(val_acc)


def run_lfo(seed, Xtr_opt, ytr_opt, Xval_opt, yval_opt):
    rng = np.random.default_rng(seed)
    population = [{k: rng.uniform(lo, hi) for k, (lo, hi) in BOUNDS6.items()}
                  for _ in range(POP_SIZE)]
    convergence = []
    global_best_fit = np.inf
    fitness = []
    for cand in population:
        acc = evaluate_candidate6(cand, Xtr_opt, ytr_opt, Xval_opt, yval_opt)
        f = 1.0 - acc
        fitness.append(f)
        global_best_fit = min(global_best_fit, f)
        convergence.append(1.0 - global_best_fit)
    personal_best = list(population)
    personal_best_fit = fitness

    for t in range(1, ITERATIONS + 1):
        E = rng.uniform(0.1, 1.0)
        a = rng.uniform(0, 1)
        C = rng.uniform(0.5, 1.5)
        D = 1.0 - np.exp(-E * t)
        VS = np.exp(-a * C)
        M = rng.uniform(0.2, 1.0)
        H = D * VS * M
        Hu = D * VS * M * H * E
        eta = 0.5
        prey = {k: rng.uniform(lo, hi) for k, (lo, hi) in BOUNDS6.items()}
        new_population = []
        for cand in population:
            new_cand = {}
            for k in BOUNDS6:
                lo, hi = BOUNDS6[k]
                step = Hu * eta * (prey[k] - cand[k])
                new_cand[k] = min(max(cand[k] + step, lo), hi)
            new_population.append(new_cand)
        for i, cand in enumerate(new_population):
            acc = evaluate_candidate6(cand, Xtr_opt, ytr_opt, Xval_opt, yval_opt)
            f = 1.0 - acc
            if f < personal_best_fit[i]:
                personal_best[i] = cand
                personal_best_fit[i] = f
            global_best_fit = min(global_best_fit, f)
            convergence.append(1.0 - global_best_fit)
        population = new_population

    return {"best_val_acc": 1.0 - global_best_fit, "convergence": convergence,
            "n_evals": len(convergence)}


def run_random_search(seed, Xtr_opt, ytr_opt, Xval_opt, yval_opt):
    rng = np.random.default_rng(seed + 100000)
    convergence = []
    best_acc = -1.0
    for _ in range(N_CANDIDATES):
        cand = {k: rng.uniform(lo, hi) for k, (lo, hi) in BOUNDS6.items()}
        acc = evaluate_candidate6(cand, Xtr_opt, ytr_opt, Xval_opt, yval_opt)
        best_acc = max(best_acc, acc)
        convergence.append(best_acc)
    return {"best_val_acc": best_acc, "convergence": convergence, "n_evals": len(convergence)}


def main():
    name = sys.argv[1]
    seed = int(sys.argv[2])
    t0 = time.time()

    Xtr, Xte, ytr, yte = P.load_prep(name)
    Xtr_opt, Xval_opt, ytr_opt, yval_opt = train_test_split(
        Xtr, ytr, test_size=0.2, stratify=ytr, random_state=RANDOM_STATE
    )

    lfo_res = run_lfo(seed, Xtr_opt, ytr_opt, Xval_opt, yval_opt)
    print(f"[{name}] LFO seed={seed}: best_val_acc={lfo_res['best_val_acc']:.4f} "
          f"n_evals={lfo_res['n_evals']} time={time.time()-t0:.1f}s", flush=True)

    t1 = time.time()
    rs_res = run_random_search(seed, Xtr_opt, ytr_opt, Xval_opt, yval_opt)
    print(f"[{name}] RS  seed={seed}: best_val_acc={rs_res['best_val_acc']:.4f} "
          f"n_evals={rs_res['n_evals']} time={time.time()-t1:.1f}s "
          f"total={time.time()-t0:.1f}s", flush=True)

    out_path = os.path.join(RESULTS_DIR, f"{P.slug(name)}_lfo_vs_rs_multiseed.json")
    if os.path.exists(out_path):
        with open(out_path) as f:
            ds_results = json.load(f)
        # Strip any stale "summary" block; will be recomputed once all seeds done.
        ds_results.pop("summary", None)
        ds_results.setdefault("lfo", [])
        ds_results.setdefault("random_search", [])
    else:
        ds_results = {"lfo": [], "random_search": []}

    # Avoid duplicate entries if this seed was already run.
    ds_results["lfo"] = [r for r in ds_results["lfo"]]
    ds_results.setdefault("lfo_seeds", [])
    ds_results.setdefault("rs_seeds", [])
    if seed not in ds_results["lfo_seeds"]:
        ds_results["lfo"].append(lfo_res)
        ds_results["lfo_seeds"].append(seed)
    if seed not in ds_results["rs_seeds"]:
        ds_results["random_search"].append(rs_res)
        ds_results["rs_seeds"].append(seed)

    with open(out_path, "w") as f:
        json.dump(ds_results, f, indent=2)
    print(f"Checkpointed -> {out_path}")


if __name__ == "__main__":
    main()
