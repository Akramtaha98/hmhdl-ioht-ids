"""
Multi-seed Lionfish Optimization (LFO) vs. Random Search comparison, with a
slightly expanded (6-dimensional) search space, addressing reviewer point 6
/ Gemini Objective-3: a single run per optimizer cannot support a claim
either way, and the original 5-parameter space was narrow.

Design (kept deliberately budget-matched to the main experiment's Lionfish
search so this stays an apples-to-apples comparison, not a different,
bigger experiment):
  - Same per-candidate budget as the main search: N_CANDIDATES = 42
    (population 6 x (1 init + 6 iterations)), same QUICK_EPOCHS=3 quick-eval
    protocol used everywhere else in this paper.
  - Search space expanded from 5 to 6 dimensions by adding learning_rate
    (log-uniform, 1e-4 to 1e-2) -- directly answers the "narrow, low-
    dimensional space favors random search" critique without changing
    per-candidate training cost.
  - 3 independent seeds per optimizer (LFO, Random Search) per dataset,
    so the comparison supports a genuine paired statistical test (paired on
    seed index) instead of one run each.
  - Run on ECU-IoHT and WUSTL-EHMS-2020 only -- DSICU is already saturated
    (every method reaches ~100%) and adds no information to this
    comparison.

Usage: python3 lfo_vs_random_multiseed.py
Writes results/{name}_lfo_vs_rs_multiseed.json
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
from scipy import stats

RESULTS_DIR = P.RESULTS_DIR
RANDOM_STATE = P.RANDOM_STATE

# Expanded 6-D search space: original 5 + log10(learning_rate)
BOUNDS6 = dict(P.BOUNDS)
BOUNDS6["log_lr"] = (-4.0, -2.0)  # learning rate in [1e-4, 1e-2]
INT_PARAMS6 = list(P.INT_PARAMS)
N_CANDIDATES = 42
QUICK_EPOCHS = P.QUICK_EPOCHS
SEARCH_BATCH = P.SEARCH_BATCH
POP_SIZE = 6
ITERATIONS = 6
SEEDS = [42, 43, 44]
DATASETS = ["ECU-IoHT", "WUSTL-EHMS-2020"]


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
    params = clip6(cand)
    model = build_model6((Xtr.shape[1], 1), params["n_conv_blocks"], params["conv_filters"],
                          params["lstm_units"], params["gru_units"], params["dropout_rate"],
                          params["log_lr"])
    model.fit(Xtr, ytr, epochs=QUICK_EPOCHS, batch_size=SEARCH_BATCH, verbose=0)
    val_acc = model.evaluate(Xval, yval, verbose=0)[1]
    keras.backend.clear_session()
    return float(val_acc)


def run_lfo(seed, Xtr_opt, ytr_opt, Xval_opt, yval_opt):
    rng = np.random.default_rng(seed)
    population = [{k: rng.uniform(lo, hi) for k, (lo, hi) in BOUNDS6.items()}
                  for _ in range(POP_SIZE)]
    convergence = []  # best-so-far per eval index
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
    rng = np.random.default_rng(seed + 100000)  # distinct stream from LFO
    convergence = []
    best_acc = -1.0
    for _ in range(N_CANDIDATES):
        cand = {k: rng.uniform(lo, hi) for k, (lo, hi) in BOUNDS6.items()}
        acc = evaluate_candidate6(cand, Xtr_opt, ytr_opt, Xval_opt, yval_opt)
        best_acc = max(best_acc, acc)
        convergence.append(best_acc)
    return {"best_val_acc": best_acc, "convergence": convergence, "n_evals": len(convergence)}


def main():
    overall_t0 = time.time()
    all_results = {}
    for name in DATASETS:
        Xtr, Xte, ytr, yte = P.load_prep(name)
        Xtr_opt, Xval_opt, ytr_opt, yval_opt = train_test_split(
            Xtr, ytr, test_size=0.2, stratify=ytr, random_state=RANDOM_STATE
        )
        ds_results = {"lfo": [], "random_search": []}
        for seed in SEEDS:
            t0 = time.time()
            lfo_res = run_lfo(seed, Xtr_opt, ytr_opt, Xval_opt, yval_opt)
            print(f"[{name}] LFO seed={seed}: best_val_acc={lfo_res['best_val_acc']:.4f} "
                  f"n_evals={lfo_res['n_evals']} time={time.time()-t0:.1f}s "
                  f"total_elapsed={time.time()-overall_t0:.1f}s", flush=True)
            ds_results["lfo"].append(lfo_res)

            t0 = time.time()
            rs_res = run_random_search(seed, Xtr_opt, ytr_opt, Xval_opt, yval_opt)
            print(f"[{name}] RS  seed={seed}: best_val_acc={rs_res['best_val_acc']:.4f} "
                  f"n_evals={rs_res['n_evals']} time={time.time()-t0:.1f}s "
                  f"total_elapsed={time.time()-overall_t0:.1f}s", flush=True)
            ds_results["random_search"].append(rs_res)

            # Checkpoint after every seed pair in case of interruption.
            with open(os.path.join(RESULTS_DIR, f"{P.slug(name)}_lfo_vs_rs_multiseed.json"), "w") as f:
                json.dump({dn: dr for dn, dr in all_results.items()} | {name: ds_results}, f, indent=2)

        lfo_finals = [r["best_val_acc"] for r in ds_results["lfo"]]
        rs_finals = [r["best_val_acc"] for r in ds_results["random_search"]]
        diff = np.array(lfo_finals) - np.array(rs_finals)
        if np.allclose(diff, 0):
            w_stat, w_p = None, 1.0
        else:
            try:
                w_stat, w_p = stats.wilcoxon(lfo_finals, rs_finals)
                w_stat = float(w_stat)
            except ValueError:
                w_stat, w_p = None, 1.0
        t_stat, t_p = stats.ttest_rel(lfo_finals, rs_finals) if not np.allclose(diff, 0) else (None, 1.0)

        ds_results["summary"] = {
            "lfo_mean": float(np.mean(lfo_finals)), "lfo_std": float(np.std(lfo_finals)),
            "rs_mean": float(np.mean(rs_finals)), "rs_std": float(np.std(rs_finals)),
            "paired_t_stat": float(t_stat) if t_stat is not None else None,
            "paired_t_p": float(t_p),
            "wilcoxon_stat": w_stat, "wilcoxon_p": float(w_p),
            "n_seeds": len(SEEDS),
        }
        all_results[name] = ds_results
        with open(os.path.join(RESULTS_DIR, f"{P.slug(name)}_lfo_vs_rs_multiseed.json"), "w") as f:
            json.dump(ds_results, f, indent=2)
        print(f"[{name}] SUMMARY: LFO {ds_results['summary']['lfo_mean']:.4f}"
              f"+/-{ds_results['summary']['lfo_std']:.4f} vs RS "
              f"{ds_results['summary']['rs_mean']:.4f}+/-{ds_results['summary']['rs_std']:.4f}, "
              f"paired t p={ds_results['summary']['paired_t_p']:.4f}", flush=True)

    with open(os.path.join(RESULTS_DIR, "lfo_vs_rs_multiseed_all.json"), "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nALL DONE in {time.time()-overall_t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
