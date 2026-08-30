"""Generate all figures for the HMHDL paper from the real experiment results."""
import os
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
FIG_DIR = os.path.join(BASE_DIR, "figures")
os.makedirs(FIG_DIR, exist_ok=True)

DATASETS = ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]


def load_results(name):
    with open(os.path.join(RESULTS_DIR, f"{name.replace(' ', '_')}_results.json")) as f:
        return json.load(f)


def load_lf_log(name):
    path = os.path.join(RESULTS_DIR, f"{name.replace(' ', '_')}_lionfish_log.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


# ---------------------------------------------------------------------
# Figure: confusion matrices (one figure per dataset)
# ---------------------------------------------------------------------
FIG_DPI = 600


def plot_confusion(name, cm, fname):
    cm = np.array(cm)
    fig, ax = plt.subplots(figsize=(4.2, 3.8))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(["Normal", "Attack"])
    ax.set_yticklabels(["Normal", "Attack"])
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")
    ax.set_title(f"Confusion Matrix — {name}")
    thresh = cm.max() / 2.0
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{cm[i, j]:,}", ha="center", va="center",
                     color="white" if cm[i, j] > thresh else "black", fontsize=11)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, fname), dpi=FIG_DPI)
    plt.close(fig)


# ---------------------------------------------------------------------
# Figure: loss curves, all 3 datasets side by side
# ---------------------------------------------------------------------
def plot_loss_curves(results):
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))
    for ax, name in zip(axes, DATASETS):
        d = results[name]
        ax.plot(range(1, len(d["loss_history"]) + 1), d["loss_history"], color="#c0392b")
        ax.set_title(name)
        ax.set_xlabel("Epoch")
        ax.set_ylabel("Training loss")
        ax.grid(alpha=0.3)
    fig.suptitle("Training Loss Curves")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "loss_curves.png"), dpi=FIG_DPI)
    plt.close(fig)


# ---------------------------------------------------------------------
# Figure: accuracy curves, all 3 datasets side by side
# ---------------------------------------------------------------------
def plot_acc_curves(results):
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))
    for ax, name in zip(axes, DATASETS):
        d = results[name]
        ax.plot(range(1, len(d["acc_history"]) + 1), d["acc_history"], color="#2471a3")
        ax.set_title(name)
        ax.set_xlabel("Epoch")
        ax.set_ylabel("Training accuracy")
        ax.set_ylim(0, 1.02)
        ax.grid(alpha=0.3)
    fig.suptitle("Training Accuracy Curves")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "accuracy_curves.png"), dpi=FIG_DPI)
    plt.close(fig)


# ---------------------------------------------------------------------
# Figure: Lionfish convergence (best-so-far val_acc across evaluations)
# ---------------------------------------------------------------------
def plot_lionfish_convergence(name, log, fname):
    if log is None:
        return
    accs = [e["val_acc"] for e in log]
    best_so_far = np.maximum.accumulate(accs)
    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    ax.plot(range(1, len(accs) + 1), accs, "o", alpha=0.4, label="candidate evaluation", color="#7f8c8d")
    ax.plot(range(1, len(best_so_far) + 1), best_so_far, "-", color="#c0392b", label="best-so-far")
    ax.set_xlabel("Candidate evaluation (population × iteration)")
    ax.set_ylabel("Quick validation accuracy")
    ax.set_title(f"Lionfish Optimization Convergence — {name}")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, fname), dpi=FIG_DPI)
    plt.close(fig)


# ---------------------------------------------------------------------
# Figure: cross-dataset summary bar chart (accuracy, F1, balanced accuracy)
# ---------------------------------------------------------------------
def plot_summary_bar(results):
    metrics = ["accuracy", "balanced_accuracy", "precision", "recall", "f1"]
    labels = ["Accuracy", "Balanced Acc.", "Precision", "Recall", "F1"]
    x = np.arange(len(metrics))
    width = 0.25
    fig, ax = plt.subplots(figsize=(8, 4.2))
    colors = ["#2471a3", "#c0392b", "#27ae60"]
    for i, name in enumerate(DATASETS):
        vals = [results[name][m] for m in metrics]
        ax.bar(x + (i - 1) * width, vals, width, label=name, color=colors[i])
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Test-set Performance Across Datasets")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "cross_dataset_summary.png"), dpi=FIG_DPI)
    plt.close(fig)


# ---------------------------------------------------------------------
# Figure: CV fold stability
# ---------------------------------------------------------------------
def plot_cv_stability(results):
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    for name in DATASETS:
        folds = results[name].get("fold_accs", [])
        if folds:
            ax.plot(range(1, len(folds) + 1), folds, marker="o", label=name)
    ax.set_xlabel("CV fold")
    ax.set_ylabel("Validation accuracy")
    ax.set_title("5-Fold Cross-Validation Stability")
    ax.set_ylim(0.8, 1.02)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "cv_stability.png"), dpi=FIG_DPI)
    plt.close(fig)


if __name__ == "__main__":
    results = {name: load_results(name) for name in DATASETS}

    for name in DATASETS:
        slug = name.replace("-", "_").replace(" ", "_").lower()
        plot_confusion(name, results[name]["confusion_matrix"], f"confusion_{slug}.png")
        lf_log = load_lf_log(name)
        plot_lionfish_convergence(name, lf_log, f"lionfish_convergence_{slug}.png")

    plot_loss_curves(results)
    plot_acc_curves(results)
    plot_summary_bar(results)
    plot_cv_stability(results)

    print("All figures saved to", FIG_DIR)
    for f in sorted(os.listdir(FIG_DIR)):
        print(" -", f)
