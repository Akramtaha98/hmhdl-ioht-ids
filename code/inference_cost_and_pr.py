"""
Single-process-per-dataset job that:
  1. Retrains the final hybrid CNN-LSTM-GRU-Attention model (Lionfish-optimized
     hyperparameters) once, exactly as in stage_train/stage_evaluate.
  2. Retrains the two classical baselines (Random Forest, HistGradientBoosting)
     used elsewhere in the paper.
  3. Measures wall-clock inference latency (mean per-sample, batch-of-1000) and
     peak RSS memory during inference, plus serialized model size on disk, for
     all three models.
  4. Saves test-set predicted probabilities for the hybrid model and the
     class-weighted-BCE variant (WUSTL-EHMS-2020 only) so a PR-curve figure can
     be plotted without retraining again.

Addresses review items M5 (inference cost table) and M9 (PR curves), and feeds
G15/G16. Run as its own OS process per dataset (see run_single_seed_pair.py for
why: CPU-only Keras leaks memory across sequential model builds within one
long-lived process).

Usage: python3 inference_cost_and_pr.py <dataset_name>
"""
import os
import sys
import json
import time
import pickle
import resource
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline as P

from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import precision_recall_curve, average_precision_score
from tensorflow import keras

RESULTS_DIR = P.RESULTS_DIR
CKPT_DIR = P.CKPT_DIR


def peak_rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0  # KB->MB on Linux


def time_inference(predict_fn, X, n_repeats=5):
    # warm-up
    predict_fn(X[:min(len(X), 1000)])
    times = []
    for _ in range(n_repeats):
        t0 = time.perf_counter()
        predict_fn(X)
        times.append(time.perf_counter() - t0)
    total_s = float(np.mean(times))
    per_sample_ms = 1000.0 * total_s / len(X)
    return total_s, per_sample_ms


def main():
    name = sys.argv[1]
    Xtr, Xte, ytr, yte = P.load_prep(name)
    best_params, _ = P.load_best_params(name)
    n_selected = Xtr.shape[1]

    out = {"dataset": name}

    # ---------------- Hybrid model: retrain to the same final-train recipe ----------------
    rss_before = peak_rss_mb()
    model = P.build_model((n_selected, 1), **{k: best_params[k] for k in
                          ["n_conv_blocks", "conv_filters", "lstm_units", "gru_units", "dropout_rate"]})
    es = keras.callbacks.EarlyStopping(monitor="loss", patience=P.FINAL_PATIENCE, restore_best_weights=True)
    t0 = time.time()
    model.fit(Xtr, ytr, epochs=P.FINAL_EPOCHS, batch_size=P.FINAL_BATCH, verbose=0, callbacks=[es])
    train_time = time.time() - t0

    model_path = os.path.join(CKPT_DIR, f"{P.slug(name)}_hybrid_for_cost.keras")
    model.save(model_path)
    model_size_mb = os.path.getsize(model_path) / (1024 * 1024)

    def hybrid_predict(X):
        return model.predict(X, verbose=0, batch_size=1024)

    total_s, per_sample_ms = time_inference(hybrid_predict, Xte)
    y_prob_hybrid = hybrid_predict(Xte).ravel()
    rss_after = peak_rss_mb()

    out["hybrid"] = {
        "n_params": int(model.count_params()),
        "model_size_mb": round(model_size_mb, 4),
        "train_time_sec": round(train_time, 2),
        "inference_total_sec_full_test_set": round(total_s, 4),
        "inference_ms_per_sample": round(per_sample_ms, 5),
        "n_test": int(len(Xte)),
        "peak_rss_mb": round(rss_after, 2),
        "peak_rss_delta_mb": round(rss_after - rss_before, 2),
    }
    np.save(os.path.join(RESULTS_DIR, f"{P.slug(name)}_hybrid_test_probs.npy"), y_prob_hybrid)
    os.remove(model_path)  # only needed the size measurement
    keras.backend.clear_session()

    # ---------------- Classical baselines: RF and HistGB ----------------
    Xtr_flat = Xtr.reshape(Xtr.shape[0], -1)
    Xte_flat = Xte.reshape(Xte.shape[0], -1)

    for label, clf_cls, kwargs in [
        ("random_forest", RandomForestClassifier, dict(n_estimators=200, random_state=42, n_jobs=-1)),
        ("hist_gb", HistGradientBoostingClassifier, dict(random_state=42)),
    ]:
        rss_before = peak_rss_mb()
        clf = clf_cls(**kwargs)
        t0 = time.time()
        clf.fit(Xtr_flat, ytr)
        train_time = time.time() - t0

        pkl_path = os.path.join(CKPT_DIR, f"{P.slug(name)}_{label}_for_cost.pkl")
        with open(pkl_path, "wb") as f:
            pickle.dump(clf, f)
        model_size_mb = os.path.getsize(pkl_path) / (1024 * 1024)

        def clf_predict(X, _clf=clf):
            return _clf.predict_proba(X)[:, 1]

        total_s, per_sample_ms = time_inference(clf_predict, Xte_flat)
        y_prob = clf_predict(Xte_flat)
        rss_after = peak_rss_mb()

        out[label] = {
            "model_size_mb": round(model_size_mb, 4),
            "train_time_sec": round(train_time, 2),
            "inference_total_sec_full_test_set": round(total_s, 4),
            "inference_ms_per_sample": round(per_sample_ms, 5),
            "n_test": int(len(Xte_flat)),
            "peak_rss_mb": round(rss_after, 2),
            "peak_rss_delta_mb": round(rss_after - rss_before, 2),
        }
        np.save(os.path.join(RESULTS_DIR, f"{P.slug(name)}_{label}_test_probs.npy"), y_prob)
        os.remove(pkl_path)

    out_path = os.path.join(RESULTS_DIR, f"{P.slug(name)}_inference_cost.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"[inference_cost] {name}: wrote {out_path}")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
