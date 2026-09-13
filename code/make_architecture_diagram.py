"""Generate the hybrid CNN-LSTM-GRU-Attention architecture diagram (Figure 1)
for the manuscript, with tensor shapes annotated at each stage, addressing
review item B5/P9 ("there is no architecture diagram at all").
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.font_manager import FontProperties

FIG_DIR = "/tmp/Paper3/figures"

STAGES = [
    ("Input\n(n_features, 1)", "#e8e8e8"),
    ("Conv1D block × N\nkernel=3, same padding\n(n_features, filters)", "#cfe2f3"),
    ("LeakyReLU (α=0.3)\n+ BatchNorm", "#cfe2f3"),
    ("LSTM\n(return_sequences=True)\n(n_features, lstm_units)", "#d9ead3"),
    ("GRU\n(return_sequences=True)\n(n_features, gru_units)", "#d9ead3"),
    ("Multi-Head Attention\n(4 heads) + residual\n+ LayerNorm", "#fce5cd"),
    ("Global Average\nPooling 1D\n(gru_units,)", "#fff2cc"),
    ("Dropout\n(optimized rate)", "#f4cccc"),
    ("Dense(1, sigmoid)\nNormal / Attack", "#d0d0f0"),
]

fig, ax = plt.subplots(figsize=(4.2, 11.5))
ax.set_xlim(0, 10)
ax.set_ylim(0, len(STAGES) * 2 + 1)
ax.axis("off")

box_w, box_h = 8.2, 1.5
font = FontProperties(size=9)

y = len(STAGES) * 2 - 0.5
centers = []
for label, color in STAGES:
    box = FancyBboxPatch(
        (0.9, y - box_h / 2), box_w, box_h,
        boxstyle="round,pad=0.08,rounding_size=0.15",
        linewidth=1.2, edgecolor="#333333", facecolor=color,
    )
    ax.add_patch(box)
    ax.text(0.9 + box_w / 2, y, label, ha="center", va="center",
             fontproperties=font, linespacing=1.4)
    centers.append(y)
    y -= 2

for i in range(len(centers) - 1):
    y0 = centers[i] - box_h / 2
    y1 = centers[i + 1] + box_h / 2
    arrow = FancyArrowPatch((5, y0), (5, y1), arrowstyle="-|>",
                             mutation_scale=14, linewidth=1.2, color="#333333")
    ax.add_patch(arrow)

ax.text(5, len(STAGES) * 2 + 0.3, "Figure 1. Hybrid CNN-LSTM-GRU-Attention architecture",
        ha="center", va="center", fontsize=10, fontweight="bold")

plt.tight_layout()
out_path = f"{FIG_DIR}/architecture_diagram.png"
plt.savefig(out_path, dpi=600, bbox_inches="tight")
print("Saved:", out_path)
