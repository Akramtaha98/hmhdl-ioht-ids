#!/usr/bin/env python3
"""EXPERIMENT 5 (issue 6): re-run 2-4 published-STYLE IoMT detectors under the SAME split-before-fit / temporal protocol.
These are faithful-in-spirit re-implementations of the model families used by the cited ECU-IoHT / WUSTL papers (NOT the authors'
code - say so in the paper): (a) plain DNN (3 dense layers; Vijayakumar et al. style), (b) CNN-only, (c) LSTM-only (Judith et al. style),
(d) random forest, (e) histogram gradient boosting (XGBoost stand-in). Random AND temporal split, 3 seeds, validation early stopping.
If you have an authors' repository for any cited model, add it as one more entry in MODELS() - the protocol code stays the same.
"""
import sklearn, numpy as np
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from common import *
ap = common_args(__doc__); ap.add_argument('--epochs', type=int, default=60); ap.add_argument('--seeds', nargs='*', type=int, default=[42, 43, 44])
a = ap.parse_args(); lab, order, drop = resolve(a)
def keras_model(kind, n, seed):
    import tensorflow as tf; from tensorflow.keras import layers as L, models
    tf.keras.utils.set_random_seed(seed); i = L.Input((n, 1)); x = i
    if kind == 'dnn': x = L.Flatten()(x); [x := L.Dense(u, activation='relu')(x) for u in (128, 64, 32)]
    if kind == 'cnn': x = L.Conv1D(32, 3, activation='relu')(x); x = L.Conv1D(64, 3, activation='relu')(x); x = L.GlobalMaxPooling1D()(x)
    if kind == 'lstm': x = L.LSTM(64)(x)
    m = models.Model(i, L.Dense(1, activation='sigmoid')(L.Dropout(.2)(x))); m.compile('adam', 'binary_crossentropy'); return m
out = dict(sklearn=sklearn.__version__, runs=[])
for kind in ('random', 'temporal'):
    df, X, y, _ = load(a.csv, lab, drop + ([order] if kind == 'temporal' else []), a.attack_values, a.max_rows); X = encode(X); y = y.values
    for s in a.seeds:
        tr, te = split(len(X), y, kind, s, df[order] if order else None); Xtr, Xte, _ = prep(X.iloc[tr], X.iloc[te]); ytr, yte = y[tr], y[te]
        if kind == 'temporal': k = int(.8 * len(tr)); sub, val = np.arange(k), np.arange(k, len(tr))
        else: sub, val = train_test_split(np.arange(len(tr)), test_size=.2, stratify=ytr, random_state=s)
        for nm in ('dnn', 'cnn', 'lstm'):
            import tensorflow as tf; m = keras_model(nm, Xtr.shape[1], s)
            m.fit(Xtr[sub][..., None], ytr[sub], validation_data=(Xtr[val][..., None], ytr[val]), epochs=a.epochs, batch_size=128, verbose=0,
                  callbacks=[tf.keras.callbacks.EarlyStopping(patience=8, restore_best_weights=True)])
            p = m.predict(Xte[..., None], verbose=0).ravel(); out['runs'].append(dict(split=kind, seed=s, model=nm, **metrics(yte, p > .5, p)))
        for nm, mdl in (('rf', RandomForestClassifier(300, n_jobs=-1, random_state=s)), ('hgb', HistGradientBoostingClassifier(random_state=s))):
            mdl.fit(Xtr, ytr); p = mdl.predict_proba(Xte)[:, 1]; out['runs'].append(dict(split=kind, seed=s, model=nm, **metrics(yte, p > .5, p)))
        print(kind, s, [(r['model'], round(r['accuracy'], 4)) for r in out['runs'][-5:]], flush=True)
        save(f'{a.out}/exp5_{a.name}.json', out)
