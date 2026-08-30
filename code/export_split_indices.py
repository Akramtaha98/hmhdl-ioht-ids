"""Exports the exact train/test row indices used for (1) the main (random,
stratified) split reported in Section 4, and (2) each dataset's alternative
(harder) split used in the Section 4.9 sensitivity analysis, for
reproducibility. All splits are deterministic given the fixed seed(s) used
throughout this project, and are saved here explicitly so a reviewer does
not have to trust that determinism blindly.
"""
import os
import sys
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline import LOADERS, RANDOM_STATE, DATA_DIR, BASE_DIR

OUT_DIR = os.path.join(BASE_DIR, "split_indices")
os.makedirs(OUT_DIR, exist_ok=True)


def export_main_splits():
    for name in ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]:
        X, y = LOADERS[name]()
        idx = np.arange(len(y))
        idx_tr, idx_te = train_test_split(idx, test_size=0.3, stratify=y, random_state=RANDOM_STATE)
        slug = name.replace(" ", "_")
        pd.DataFrame({"row_index": idx_tr}).to_csv(os.path.join(OUT_DIR, f"{slug}_train_indices.csv"), index=False)
        pd.DataFrame({"row_index": idx_te}).to_csv(os.path.join(OUT_DIR, f"{slug}_test_indices.csv"), index=False)
        print(f"[main split] {name}: exported {len(idx_tr)} train / {len(idx_te)} test row indices "
              f"(0-indexed, into the raw CSV as loaded by pipeline.LOADERS['{name}'])")


def export_alt_splits():
    import pandas as pd

    # ECU-IoHT: temporal split, sorted by Time, earliest 70% train
    df = pd.read_csv(os.path.join(DATA_DIR, "ECU_IoHT.csv"))
    order = df.sort_values("Time").index.to_numpy()  # original-row-index order after temporal sort
    cut = int(len(order) * 0.7)
    pd.DataFrame({"orig_row_index": order[:cut]}).to_csv(
        os.path.join(OUT_DIR, "ECU-IoHT_altsplit_train_indices.csv"), index=False)
    pd.DataFrame({"orig_row_index": order[cut:]}).to_csv(
        os.path.join(OUT_DIR, "ECU-IoHT_altsplit_test_indices.csv"), index=False)
    print(f"[alt split] ECU-IoHT (temporal, by Time): {cut} train / {len(order)-cut} test "
          "original-CSV row indices")

    # WUSTL-EHMS-2020: temporal-style split, sorted by Packet_num, earliest 70% train
    df = pd.read_csv(os.path.join(DATA_DIR, "wustl-ehms-2020.csv"))
    order = df.sort_values("Packet_num").index.to_numpy()
    cut = int(len(order) * 0.7)
    pd.DataFrame({"orig_row_index": order[:cut]}).to_csv(
        os.path.join(OUT_DIR, "WUSTL-EHMS-2020_altsplit_train_indices.csv"), index=False)
    pd.DataFrame({"orig_row_index": order[cut:]}).to_csv(
        os.path.join(OUT_DIR, "WUSTL-EHMS-2020_altsplit_test_indices.csv"), index=False)
    print(f"[alt split] WUSTL-EHMS-2020 (temporal, by Packet_num): {cut} train / {len(order)-cut} test "
          "original-CSV row indices")

    # DSICU: group split by (tcp.srcport, tcp.dstport), shuffled group assignment, seed 42
    df = pd.read_csv(os.path.join(DATA_DIR, "dsicu_mi.csv"))
    groups = df.groupby(["tcp.srcport", "tcp.dstport"]).indices
    group_keys = list(groups.keys())
    rng = np.random.default_rng(42)
    rng.shuffle(group_keys)
    n_total = len(df)
    target_train = int(n_total * 0.7)
    train_idx = []
    running = 0
    for k in group_keys:
        idx = groups[k]
        if running < target_train:
            train_idx.append(idx)
            running += len(idx)
    train_idx = np.concatenate(train_idx)
    train_mask = np.zeros(n_total, dtype=bool)
    train_mask[train_idx] = True
    pd.DataFrame({"orig_row_index": np.where(train_mask)[0]}).to_csv(
        os.path.join(OUT_DIR, "DSICU_altsplit_train_indices.csv"), index=False)
    pd.DataFrame({"orig_row_index": np.where(~train_mask)[0]}).to_csv(
        os.path.join(OUT_DIR, "DSICU_altsplit_test_indices.csv"), index=False)
    print(f"[alt split] DSICU (group, by srcport/dstport, seed 42): {train_mask.sum()} train / "
          f"{(~train_mask).sum()} test original-CSV row indices")


if __name__ == "__main__":
    export_main_splits()
    export_alt_splits()
