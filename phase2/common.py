"""Shared utilities for the Phase 2 experiments (split-before-fit, hybrid model, LIRS / random search).

Everything that touches test data happens ONCE, at the very end of a run.
Hyperparameter search and early stopping use a validation split carved from the TRAINING partition only.
"""
import os, json, time, argparse, numpy as np, pandas as pd
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score,
                             roc_auc_score, average_precision_score, balanced_accuracy_score)

DATASETS = {   # edit --label-col / --order-col on the command line if your CSV headers differ
    'ECU':   dict(label='Type',  order='Time',       sub='Type of attack', drop=['Type of attack', 'No.', 'Source', 'Destination', 'Info']),
    'WUSTL': dict(label='label', order='Packet_num', sub=None, drop=[]),
}

# ------------------------------------------------------------------ data
def load(csv, label_col, drop_cols=(), attack_values=None, max_rows=None, seed=0, sub_col=None):
    df = pd.read_csv(csv, low_memory=False); df.columns = [c.strip() for c in df.columns]
    if max_rows and len(df) > max_rows: df = df.sample(max_rows, random_state=seed).sort_index()
    lab = df[label_col]
    if attack_values: y = lab.astype(str).isin(attack_values).astype(int)
    elif not pd.api.types.is_numeric_dtype(lab):
        y = (~lab.astype(str).str.strip().str.lower().isin(['normal', 'benign', '0'])).astype(int)
    else: y = (lab != 0).astype(int)
    sub = (df[sub_col] if sub_col and sub_col in df.columns else lab).astype(str).values                      # attack subtype, kept for per-class reports
    X = df.drop(columns=[c for c in [label_col, *drop_cols] if c in df.columns])
    return df, X, y.reset_index(drop=True), sub

def encode(X, keep_cols=None):
    """Drop address/free-text columns (>20 distinct strings), one-hot the rest."""
    X = X.copy()
    for c in list(X.columns):
        if not pd.api.types.is_numeric_dtype(X[c]) and X[c].nunique() > 20: X = X.drop(columns=c)
    X = pd.get_dummies(X, dtype=float).apply(pd.to_numeric, errors='coerce').fillna(0)
    return X

def split(n, y, kind='random', seed=42, order=None, test=0.3):
    idx = np.arange(n)
    if kind == 'temporal':
        o = np.argsort(pd.to_numeric(order, errors='coerce').fillna(0).values, kind='stable')
        k = int(n * (1 - test)); return o[:k], o[k:]
    return train_test_split(idx, test_size=test, stratify=y, random_state=seed)

def prep(Xtr, Xte):
    Xtr = np.asarray(Xtr, float); Xte = np.asarray(Xte, float)
    keep = Xtr.var(0) > 0; sc = StandardScaler().fit(Xtr[:, keep])
    return sc.transform(Xtr[:, keep]), sc.transform(Xte[:, keep]), keep

def metrics(y, p, s=None):
    m = dict(accuracy=accuracy_score(y, p), balanced_acc=balanced_accuracy_score(y, p),
             precision=precision_score(y, p, zero_division=0), recall=recall_score(y, p, zero_division=0),
             f1=f1_score(y, p, zero_division=0))
    if s is not None and len(np.unique(y)) == 2:
        m['roc_auc'] = roc_auc_score(y, s); m['pr_auc'] = average_precision_score(y, s)
    return m

# ------------------------------------------------------------------ model
BOUNDS = dict(blocks=(1, 3), filters=(16, 64), lstm=(8, 64), gru=(8, 64), dropout=(0.1, 0.5))
def decode(v):
    return dict(blocks=int(round(v[0])), filters=int(round(v[1])), lstm=int(round(v[2])),
                gru=int(round(v[3])), dropout=float(v[4]))

def build(hp, n_feat, lr=1e-3, seed=0):
    import tensorflow as tf
    from tensorflow.keras import layers as L, models
    tf.keras.utils.set_random_seed(seed)
    i = L.Input((n_feat, 1)); x = i
    for b in range(hp['blocks']):
        x = L.Conv1D(hp['filters'], 3, padding='same', activation='relu')(x); x = L.BatchNormalization()(x)
    x = L.LSTM(hp['lstm'], return_sequences=True)(x)
    x = L.GRU(hp['gru'], return_sequences=True)(x)
    a = L.Softmax(axis=1)(L.Dense(1)(x)); x = L.Dot(axes=1)([a, x]); x = L.Flatten()(x)   # additive attention pooling
    x = L.Dropout(hp['dropout'])(x); o = L.Dense(1, activation='sigmoid')(x)
    m = models.Model(i, o); m.compile(tf.keras.optimizers.Adam(lr), 'binary_crossentropy', metrics=['accuracy'])
    return m

def fit(hp, Xtr, ytr, Xva, yva, epochs, patience, batch=128, lr=1e-3, seed=0, verbose=0):
    """Train with early stopping on VALIDATION loss (never on test)."""
    import tensorflow as tf
    m = build(hp, Xtr.shape[1], lr, seed)
    cb = [tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=patience, restore_best_weights=True)]
    m.fit(Xtr[..., None], ytr, validation_data=(Xva[..., None], yva), epochs=epochs,
          batch_size=batch, callbacks=cb, verbose=verbose)
    return m

def predict(m, X): return m.predict(X[..., None], batch_size=1024, verbose=0).ravel()

# ------------------------------------------------------------------ search (LIRS / random), validation-based
def fitness(v, Xs, ys, Xv, yv, epochs, seed):
    hp = decode(v); m = fit(hp, Xs, ys, Xv, yv, epochs, patience=epochs, batch=512, seed=seed)
    return 1 - float(((predict(m, Xv) > .5) == yv).mean())

def search(method, budget, Xs, ys, Xv, yv, epochs=5, seed=0, pop=10):
    """method: 'random' or 'lirs'. Same number of fitness evaluations for both. Returns (best_hp, history)."""
    rng = np.random.default_rng(seed); lo = np.array([b[0] for b in BOUNDS.values()], float); hi = np.array([b[1] for b in BOUNDS.values()], float)
    hist = []
    def ev(v):
        f = fitness(v, Xs, ys, Xv, yv, epochs, seed); hist.append(f); return f
    if method == 'random':
        best, bf = None, 9
        for _ in range(budget):
            v = rng.uniform(lo, hi); f = ev(v)
            if f < bf: best, bf = v, f
        return decode(best), hist
    P = rng.uniform(lo, hi, (pop, len(lo))); F = np.array([ev(v) for v in P]); pb, pf = P.copy(), F.copy()
    T = max(1, (budget - pop) // pop)
    for t in range(1, T + 1):
        E, a, C, M = rng.uniform(.1, 1), rng.uniform(0, 1), rng.uniform(.5, 1.5), rng.uniform(.2, 1)
        D = np.exp(-a * t / T); VS = C; H = D * VS * M; Hu = H * H * E       # simplified Hu (see paper Sec. III-C)
        prey = rng.uniform(lo, hi)
        for i in range(pop):
            P[i] = np.clip(P[i] + Hu * 0.5 * (prey - P[i]), lo, hi); f = ev(P[i])
            if f < pf[i]: pb[i], pf[i] = P[i].copy(), f
    return decode(pb[pf.argmin()]), hist
# NOTE: this is a compact re-implementation. To keep identical to the paper, replace `search(...,'lirs')`
# by the Lionfish routine in your repo's code/pipeline.py (the experiments only call search()).

def save(path, obj):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    json.dump(obj, open(path, 'w'), indent=1, default=float)

def common_args(desc):
    ap = argparse.ArgumentParser(description=desc)
    ap.add_argument('--name', required=True, choices=list(DATASETS) + ['CIC'])
    ap.add_argument('--csv', required=True); ap.add_argument('--label-col'); ap.add_argument('--order-col')
    ap.add_argument('--drop-cols', nargs='*', default=None); ap.add_argument('--attack-values', nargs='*')
    ap.add_argument('--max-rows', type=int, default=None, help='subsample for a quick smoke test')
    ap.add_argument('--out', default='results')
    return ap

def resolve(a):
    d = DATASETS.get(a.name, dict(label=None, order=None, sub=None, drop=[]))
    return (a.label_col or d['label'], a.order_col or d['order'], a.drop_cols if a.drop_cols is not None else d['drop'])
