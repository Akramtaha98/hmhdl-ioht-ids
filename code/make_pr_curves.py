"""
PR curve figure for WUSTL-EHMS-2020: hybrid (main experiment) vs. gradient
boosting (strongest classical baseline) vs. the class-weighted-BCE variant
(Section 4.11's partial recall fix). Review item M9 / gate G16.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import precision_recall_curve, average_precision_score

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline as P

FIG_DIR = P.FIG_DIR
RESULTS_DIR = P.RESULTS_DIR
NAME = "WUSTL-EHMS-2020"

_, _, _, yte = P.load_prep(NAME)

series = [
    ("Hybrid CNN-LSTM-GRU-Attention (main experiment)",
     np.load(os.path.join(RESULTS_DIR, f"{P.slug(NAME)}_hybrid_test_probs.npy")), "#1f77b4"),
    ("Histogram Gradient Boosting (strongest classical baseline)",
     np.load(os.path.join(RESULTS_DIR, f"{P.slug(NAME)}_hist_gb_test_probs.npy")), "#ff7f0e"),
    ("Hybrid, class-weighted BCE variant (Section 4.11)",
     np.load(os.path.join(RESULTS_DIR, f"{P.slug(NAME)}_class_weighted_bce_test_probs.npy")), "#2ca02c"),
]

fig, ax = plt.subplots(figsize=(6.3, 5.2))
for label, probs, color in series:
    precision, recall, _ = precision_recall_curve(yte, probs)
    ap = average_precision_score(yte, probs)
    ax.plot(recall, precision, label=f"{label} (AP={ap:.3f})", color=color, linewidth=1.8)

baseline = float(yte.sum()) / len(yte)
ax.axhline(baseline, color="gray", linestyle="--", linewidth=1, label=f"No-skill baseline (AP={baseline:.3f})")

ax.set_xlabel("Recall")
ax.set_ylabel("Precision")
ax.set_title("Precision-Recall Curves — WUSTL-EHMS-2020 (Attack class)")
ax.set_xlim(0, 1)
ax.set_ylim(0, 1.02)
ax.legend(loc="lower left", fontsize=8)
ax.grid(alpha=0.3)
plt.tight_layout()

out_path = os.path.join(FIG_DIR, "wustl_pr_curves.png")
plt.savefig(out_path, dpi=600, bbox_inches="tight")
print("Saved:", out_path)

# Also save the AP numbers for the manuscript text.
import json
ap_summary = {label: float(average_precision_score(yte, probs)) for label, probs, _ in series}
ap_summary["no_skill_baseline"] = baseline
with open(os.path.join(RESULTS_DIR, "wustl_pr_curve_ap.json"), "w") as f:
    json.dump(ap_summary, f, indent=2)
print(json.dumps(ap_summary, indent=2))
