"""
Per-attack-class recall table for ECU-IoHT (review item M4 / gate G14).

ECU-IoHT's raw CSV carries a "Type of attack" column with attack subtypes
(Smurf Attack, Nmap Port Scan, ARP Spoofing, DoS Attack, No Attack), so a
per-attack breakdown is possible for this dataset. WUSTL-EHMS-2020 only
carries a binary "label" column in the provided CSV -- no attack-subtype
field exists to break down -- so it is explicitly marked N/A here rather
than silently omitted; DSICU's raw file is unavailable in this environment
for the same restricted-access reason noted elsewhere, so it is marked N/A
for the same reason.

Requires: results/ECU-IoHT_hybrid_test_probs.npy (written by
inference_cost_and_pr.py) and split_indices/ECU-IoHT_test_indices.csv
(written by export_split_indices.py) to align predictions back to the
original per-row attack-subtype labels.
"""
import os
import sys
import json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline as P

RESULTS_DIR = P.RESULTS_DIR
BASE_DIR = P.BASE_DIR


def main():
    probs_path = os.path.join(RESULTS_DIR, "ECU-IoHT_hybrid_test_probs.npy")
    idx_path = os.path.join(BASE_DIR, "split_indices", "ECU-IoHT_test_indices.csv")
    if not os.path.exists(probs_path):
        print(f"NOT READY: {probs_path} does not exist yet (inference_cost_and_pr.py still running?)")
        sys.exit(1)
    if not os.path.exists(idx_path):
        print(f"NOT READY: {idx_path} does not exist")
        sys.exit(1)

    y_prob = np.load(probs_path)
    y_pred = (y_prob >= 0.5).astype(int)
    test_idx = pd.read_csv(idx_path)["row_index"].to_numpy()

    df = pd.read_csv(os.path.join(P.DATA_DIR, "ECU_IoHT.csv"))
    test_attack_type = df.loc[test_idx, "Type of attack"].to_numpy()
    test_true_label = (df.loc[test_idx, "Type"] == "Attack").astype(int).to_numpy()

    assert len(test_attack_type) == len(y_pred), \
        f"length mismatch: {len(test_attack_type)} attack-type rows vs {len(y_pred)} predictions"

    rows = []
    for atype in sorted(pd.unique(test_attack_type)):
        mask = test_attack_type == atype
        n = int(mask.sum())
        true_lab = test_true_label[mask]
        pred_lab = y_pred[mask]
        if atype == "No Attack":
            # "recall" is undefined for the negative class; report specificity instead
            specificity = float((pred_lab == 0).mean())
            rows.append({"attack_type": atype, "n_test_samples": n,
                         "metric": "specificity (fraction correctly labeled Normal)",
                         "value": round(specificity, 4)})
        else:
            recall = float((pred_lab == 1).mean())  # all rows here are true label=1 (Attack)
            rows.append({"attack_type": atype, "n_test_samples": n,
                         "metric": "recall (fraction correctly labeled Attack)",
                         "value": round(recall, 4)})

    out = {
        "dataset": "ECU-IoHT",
        "note": "WUSTL-EHMS-2020 and DSICU are not included: WUSTL-EHMS-2020's provided CSV carries "
                "only a binary label (no attack-subtype field), and DSICU's raw source file is "
                "unavailable in this environment (restricted-access dataset).",
        "per_attack_type": rows,
    }
    out_path = os.path.join(RESULTS_DIR, "per_attack_class_recall.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))
    print("Saved:", out_path)


if __name__ == "__main__":
    main()
