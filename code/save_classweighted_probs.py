"""
Retrains WUSTL-EHMS-2020's class-weighted-BCE variant (identical protocol to
recall_fix_wustl_v2.py's "class_weighted_bce" arm) and saves the held-out
test-set predicted probabilities, so a PR curve can include it alongside the
hybrid main-experiment model and gradient boosting (review item M9 / gate
G16). recall_fix_wustl_v2.py itself only saved summary metrics, not the raw
probability array, so this reruns just that one variant to get it.
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline as P

from tensorflow import keras
from tensorflow.keras import layers
from sklearn.model_selection import train_test_split

RANDOM_STATE = 42
NAME = "WUSTL-EHMS-2020"


def build_model(input_shape, n_conv_blocks, conv_filters, lstm_units, gru_units, dropout_rate):
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


def main():
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

    model = build_model((n_selected, 1), **arch_kwargs)
    best_loss, bad_epochs, patience, best_weights = np.inf, 0, 8, None
    for epoch in range(80):
        hist = model.fit(Xtr_fit, ytr_fit, epochs=1, batch_size=128, verbose=0, class_weight=class_weight)
        loss_val = float(hist.history["loss"][0])
        if loss_val < best_loss - 1e-5:
            best_loss, bad_epochs, best_weights = loss_val, 0, model.get_weights()
        else:
            bad_epochs += 1
        if bad_epochs >= patience:
            break
    if best_weights is not None:
        model.set_weights(best_weights)

    yte_prob = model.predict(Xte, verbose=0).ravel()
    out_path = os.path.join(P.RESULTS_DIR, f"{P.slug(NAME)}_class_weighted_bce_test_probs.npy")
    np.save(out_path, yte_prob)
    print("Saved:", out_path, "epochs_run:", epoch + 1)


if __name__ == "__main__":
    main()
