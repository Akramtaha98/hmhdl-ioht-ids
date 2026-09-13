"""Merge the per-dataset Figure 1a-c (Lionfish convergence) and Figure 4a-c
(confusion matrices) into single multi-panel figures with one caption each,
addressing review item P1/G18.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

FIG_DIR = "/tmp/Paper3/figures"

PANEL_SETS = [
    (
        [f"{FIG_DIR}/lionfish_convergence_ecu_ioht.png",
         f"{FIG_DIR}/lionfish_convergence_wustl_ehms_2020.png",
         f"{FIG_DIR}/lionfish_convergence_dsicu.png"],
        ["(a) ECU-IoHT", "(b) WUSTL-EHMS-2020", "(c) DSICU"],
        f"{FIG_DIR}/lionfish_convergence_merged.png",
    ),
    (
        [f"{FIG_DIR}/confusion_ecu_ioht.png",
         f"{FIG_DIR}/confusion_wustl_ehms_2020.png",
         f"{FIG_DIR}/confusion_dsicu.png"],
        ["(a) ECU-IoHT", "(b) WUSTL-EHMS-2020", "(c) DSICU"],
        f"{FIG_DIR}/confusion_merged.png",
    ),
]

for paths, labels, out_path in PANEL_SETS:
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.6))
    for ax, path, label in zip(axes, paths, labels):
        img = mpimg.imread(path)
        ax.imshow(img)
        ax.axis("off")
        ax.set_title(label, fontsize=11, fontweight="bold", pad=6)
    plt.tight_layout()
    plt.savefig(out_path, dpi=600, bbox_inches="tight")
    plt.close(fig)
    print("Saved:", out_path)
