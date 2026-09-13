# -*- coding: utf-8 -*-
"""Build the MDPI IoT journal manuscript (.docx) using the generic MDPI
Word template body styles, using the real, leakage-free experimental
results. IoT accepts free-format submission, so exact per-journal
template cosmetics (the front-matter box below the title, filled in by
MDPI editorial staff at production time) are not required at submission;
this script's own front-matter box still carries JCP's placeholder
citation string as a leftover from an earlier target-journal draft and
should be refreshed by MDPI's production team on acceptance regardless
of which MDPI journal is targeted."""
import re
import os
import json
import shutil
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement, parse_xml

from references import REFS, KEY_TO_NUM, OLD_NUM_TO_KEY, cite

# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------
# This script is included for transparency (it shows exactly how every
# number in the manuscript's text/tables was pulled from results/*.json and
# inserted), not as something reviewers need to re-run. It requires MDPI's
# official jcp-template.dot file, which is not redistributed here for
# licensing reasons; place a copy at TEMPLATE_PATH below (or point the
# JCP_TEMPLATE_PATH environment variable at it) if you want to rebuild the
# .docx yourself. All other paths are relative to the project root.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = os.environ.get("JCP_TEMPLATE_PATH", os.path.join(BASE_DIR, "jcp-template.dot"))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
FIG_DIR = os.path.join(BASE_DIR, "figures")
WORK_TEMPLATE_COPY = os.path.join(BASE_DIR, "code", "_jcp_template_working.docx")
OUT_PATH = os.path.join(BASE_DIR, "HMHDL_MDPI_JCP_manuscript_template.docx")

shutil.copyfile(TEMPLATE_PATH, WORK_TEMPLATE_COPY)

# The .dot template's main part is registered as a "template" content type;
# python-docx only accepts the "document" content type. Patch it in place
# (rewrite the zip with the corrected [Content_Types].xml) before opening.
import zipfile

_tmp_fixed = WORK_TEMPLATE_COPY + ".fixed"
with zipfile.ZipFile(WORK_TEMPLATE_COPY, "r") as zin:
    with zipfile.ZipFile(_tmp_fixed, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "[Content_Types].xml":
                data = data.replace(
                    b"application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml",
                    b"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
                )
            zout.writestr(item, data)
os.replace(_tmp_fixed, WORK_TEMPLATE_COPY)

_BRACKET_RE = re.compile(r"\[(\d+(?:\s*[–—\-,]\s*\d+)*)\]")


def _format_nums(nums):
    nums = sorted(set(nums))
    parts = []
    i = 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        if j > i:
            parts.append(f"{nums[i]}–{nums[j]}")
        else:
            parts.append(str(nums[i]))
        i = j + 1
    return ",".join(parts)


def renumber(text):
    def repl(m):
        body = m.group(1)
        old_nums = []
        for chunk in re.split(r",", body):
            chunk = chunk.strip()
            range_m = re.match(r"^(\d+)\s*[–—\-]\s*(\d+)$", chunk)
            if range_m:
                lo, hi = int(range_m.group(1)), int(range_m.group(2))
                old_nums.extend(range(lo, hi + 1))
            elif chunk.isdigit():
                old_nums.append(int(chunk))
        new_nums = []
        for n in old_nums:
            key = OLD_NUM_TO_KEY.get(n)
            if key and key in KEY_TO_NUM:
                new_nums.append(KEY_TO_NUM[key])
        if not new_nums:
            return m.group(0)
        return f"[{_format_nums(new_nums)}]"
    return _BRACKET_RE.sub(repl, text)


# ---------------------------------------------------------------------
# Cleaned-up replacement text for the related-work paragraphs (original
# indices 19-53). The source draft's auto-summarized related-work prose
# contained numerous grammar/run-on errors (missing verbs, citations
# glued mid-sentence, garbled clauses -- e.g. idx 19 originally read
# "...Decision Prognostication Four machine learning methods..." and
# idx 24 read "...attracted from (2026)."). These rewrites preserve the
# exact same facts (verified against Table 1 in Section 2) and the same
# trailing bracket citation number (so renumber() maps them correctly),
# but present them as clean, reviewer-ready prose.
# ---------------------------------------------------------------------
ORIG_OVERRIDE = {
    19: "Pang et al. compared four machine learning methods -- XGBoost, logistic regression, "
        "and support vector machine -- for predicting in-hospital mortality risk in critically "
        "ill ICU patients using DSICU stay data. The XGBoost model achieved the best performance "
        "(AUC = 0.918, 95% CI [0.915, 0.922]; accuracy = 0.834; sensitivity = 0.822; "
        "specificity = 0.846), with random downsampling applied to address class imbalance. The "
        "authors note that their single-center retrospective design requires validation through "
        "prospective multicenter studies, and that the downsampling method used may carry a "
        "residual risk of clinical information loss or selection bias [6].",
    20: "Karboub and Tabaa designed a dynamic machine-learning framework to predict discharge "
        "readiness and length of stay (LOS) for cardiovascular disease patients in intensive care "
        "units, in order to optimize medical resource allocation. Their ensemble GLRM architecture "
        "achieved the best experimental performance (98% average prediction accuracy, 0.0004 mean "
        "residual), identifying discharge location, admission source, diagnosis, drug therapy, and "
        "LOS as the strongest drivers of clinical transfer decisions. The authors report a key "
        "limitation: reduced predictive performance for patients with a length of stay exceeding "
        "three days [26].",
    21: "Hempel et al. proposed a stepwise DSICU length-of-stay framework that first applies binary "
        "classification to separate short stays (<4 days) from long stays, and then restricts "
        "regression modeling to the subset predicted to be at risk for a long stay. Whereas a "
        "standalone regression model performed poorly across the full 21-day stay range because "
        "prediction error grows sharply with stay length, the stepwise approach substantially "
        "improved prediction accuracy, with SVM and Random Forest outperforming other methods at a "
        "mean absolute percentage error (MAPE) of approximately 33%. The main limitation the "
        "authors identify is that long-stay trajectories beyond the modeled horizon could not be "
        "tracked [27].",
    22: "Koumantakis et al. conducted a meta-analysis of ICU length-of-stay and outcome-prediction "
        "models built with LSTM, RNN, GRU, and Transformer architectures. The pooled estimate "
        "across studies was a mean area under the receiver operating characteristic curve (AUROC) "
        "of 0.79 (95% CI = 0.73-0.85) with extremely high heterogeneity (I2 = 99.96%), while models "
        "restricted to disease-specific ICU subpopulations achieved a significantly higher and more "
        "consistent mean AUROC of 0.92 (95% CI = 0.88-0.94, p = 0.002; I2 = 17.1%). Across the "
        "literature reviewed, the authors identify an overall high risk of bias as the principal "
        "limitation [28].",
    24: "Krishna Kumari et al. proposed MREQGAN-DSA, a hybrid quantum-driven and bio-inspired "
        "intrusion detection framework for IoMT networks that targets higher-level threats such as "
        "DoS, probing, and man-in-the-middle attacks, combining quantum-inspired feature "
        "representations with Duck Swarm Algorithm-based hyperparameter optimization. Evaluated "
        "across DSICU, WUSTL-EHMS-2020, and ECU-IoHT, the framework achieved average "
        "classification accuracies of 99.81% and 99.77% with strong precision, recall, and "
        "F1-score, and low computational overhead relative to comparable ensembles. The authors "
        "note that the architectural complexity of the quantum components and their computational "
        "footprint remain a barrier to lightweight deployment, motivating further work on compact "
        "quantum operators [29].",
    27: "Vijayakumar et al. built a deep neural network (DNN) classifier for ECU-IoHT, reporting "
        "99.85% classification accuracy. A key limitation the authors identify is that the model's "
        "centralized training requirement conflicts with regulatory constraints on patient-data "
        "confidentiality, and that classification performance drops substantially -- recall "
        "falling by roughly 60% -- for low-frequency DoS attack instances [30].",
    28: "Areia et al. introduced IoT-TrafficData, an open, annotated benchmark combining benign "
        "traffic from three protocols (CoAP, MQTT, HTTP) across ten medical device models with "
        "malicious traffic from eight attack vectors, including four DoS variants, ARP spoofing, "
        "CAM-table overflow, and reconnaissance scans. Evaluating six supervised classifiers "
        "(decision tree, random forest, naive Bayes, logistic regression, SVM, and DNN) on this "
        "benchmark, they report F1-scores consistently above 99%. A notable limitation is that the "
        "naive Bayes classifier's performance degraded substantially relative to the other "
        "models [31].",
    29: "Algethami and Alshamrani proposed a hybrid deep-learning intrusion detection architecture "
        "(HANN-BLSTM) to secure the transmission of sensitive health data across heterogeneous "
        "IoMT domains. Evaluated on both binary and multiclass attack tasks -- ARP spoofing, DoS, "
        "Nmap port scans, and Smurf floods -- the model achieved a 99.85% mean weighted accuracy "
        "in the multiclass setting. The most significant limitation the authors report is reduced "
        "precision specifically on Smurf-attack detection, which they suggest may require "
        "additional architectural depth or continual-learning capability to generalize to "
        "unmapped, zero-day attack variants [32].",
    30: "Alohali et al. proposed EloHTSCD-SEGO, an AI-based anomaly detection framework for "
        "heterogeneous IoMT devices designed to secure systems against covert data exfiltration. "
        "Evaluated on the ECU-IoHT benchmark, the framework reached a best classification accuracy "
        "of 99.33% with an optimized processing time of 10.92 minutes, outperforming "
        "state-of-the-art deep-learning and LightGBM baselines. The authors identify reliance on a "
        "static dataset -- which may not capture the real-world diversity of attack behavior -- as "
        "a key limitation [33].",
    31: "Mosaiyebzadeh et al. designed a privacy-preserving federated learning framework for "
        "securing IoMT device traffic, evaluating feedforward DNN and CNN architectures against "
        "membership-inference and model-poisoning attacks; the CNN variant achieved the best "
        "accuracy at 95.48%. The authors report that the framework's performance is "
        "architecturally sensitive to gradient-noise tuning, with precision dropping noticeably "
        "under certain noise settings [34].",
    33: "Alharbi and Khan benchmarked five traditional machine-learning algorithms -- decision "
        "tree, random forest, naive Bayes, k-nearest neighbors, and logistic regression -- for "
        "IoMT intrusion detection, finding that random forest achieved the highest classification "
        "accuracy at 98%. The authors identify the framework's reliance on a down-sampled, static "
        "data schema as its key limitation, noting that this schema may not accurately represent "
        "the nonlinear, real-time load characteristics of live clinical network traffic [35].",
    35: "The same MREQGAN-DSA framework proposed by Krishna Kumari et al. was also evaluated on "
        "ECU-IoHT, where it achieved a mean classification accuracy of 99.81%. As with the DSICU "
        "and WUSTL-EHMS-2020 evaluations, the authors note that the architectural complexity of "
        "the quantum-inspired components and their computational overhead limit real-time "
        "deployment on resource-constrained edge medical equipment, motivating further work on "
        "lightweight, compressed quantum operator approximations [29].",
    38: "Tauqeer et al. compared three supervised machine-learning algorithms -- random forest, "
        "gradient boosting, and SVM -- for identifying spoofing, data-injection, and "
        "man-in-the-middle attacks on the WUSTL-EHMS-2020 dataset, reporting classification "
        "accuracies of 96.9%, 96.5%, and 95.85% respectively, with random forest performing best. "
        "The authors identify the framework's dependence on a single, centralized server-based "
        "training paradigm as its principal limitation, with no cryptographic or federated "
        "protection layer evaluated [36].",
    39: "Judith et al. proposed a deep-learning framework for classifying man-in-the-middle "
        "attacks in IoMT traffic, combining principal component analysis (PCA) with a fully "
        "connected multilayer perceptron (MLP). Evaluated on WUSTL-EHMS-2020, the PCA-MLP "
        "classifier outperformed classical machine-learning baselines with an overall accuracy of "
        "96.39%. The authors report that the main drawback is a higher false-positive rate in "
        "complex, multi-class threat settings, where overlapping or noisy traffic signatures make "
        "it harder for the model to maintain sharp decision boundaries [37].",
    41: "Shaikh et al. presented RCLNet, a data-efficient framework combining convolutional neural "
        "network layers for spatial feature extraction with LSTM blocks for temporal dependency "
        "modeling. Evaluated on the WUSTL-EHMS-2020 healthcare dataset, RCLNet reached a "
        "near-perfect classification accuracy of 99.78% with a strong sensitivity-specificity "
        "trade-off. The authors' main caveat is that the model was validated only on static, "
        "historical traffic distributions, without evaluation under non-stationary real-time "
        "streaming conditions or zero-day attack drift [38].",
    43: "Wu et al. proposed an ensemble deep-learning framework for cyberattack detection in IoMT "
        "traffic, combining multiple stacked models through cross-tabulation and "
        "model-distillation techniques; the best-performing StackMean architecture achieved "
        "94.29% classification accuracy on WUSTL-EHMS-2020. The authors note that running multiple "
        "parallel neural networks and meta-classifiers simultaneously introduces substantial "
        "computational and memory overhead, increasing inference latency in ways that may hinder "
        "deployment on low-power edge medical devices [39].",
    45: "Krishna Kumari et al. proposed MREQGAN-DSA, a hybrid quantum-driven and bio-inspired "
        "intrusion detection framework combining quantum-inspired multi-relational graph-attention "
        "feature representations with Duck Swarm Algorithm-based hyperparameter optimization, "
        "targeting higher-level IoMT threats such as DoS, probing, and man-in-the-middle attacks. "
        "Evaluated on NSL-KDD and WUSTL-EHMS-2020, the architecture achieved near-perfect detection, "
        "with average accuracy of 99.81% on NSL-KDD and 99.77% on WUSTL-EHMS-2020, and an inference "
        "time of 24.9 seconds on "
        "WUSTL-EHMS-2020. The authors attribute the framework's main bottleneck to the mathematical "
        "and structural complexity of its quantum-inspired components, which increases resource "
        "consumption and leaves cross-domain generalizability to decentralized, multi-center "
        "clinical deployments unproven [29].",
    47: "Balhareth et al. proposed ML-FSID-FIS, an interpretable security framework for IoMT "
        "networks that combines a three-way, multi-level feature-selection approach with a fuzzy "
        "inference system to model uncertainty in traffic flows and flag malicious activity. "
        "Evaluated on ECU-IoHT, the approach achieved a best overall classification accuracy of "
        "99.33%. The authors identify two limitations: the static nature of its fuzzy membership "
        "functions, and the high manual overhead required to configure its rule base, both of "
        "which constrain real-time scalability on high-volume streams and self-adaptation to "
        "unmapped or evolving attack classes [40].",
    49: "Abid introduced a four-layer, trust-based collective machine-learning framework combining "
        "k-nearest neighbors, random forest, and SVM classifiers. Evaluated on the multimodal "
        "WUSTL-EHMS-2020 dataset, a hard-voting ensemble of the three classifiers achieved the "
        "highest overall accuracy at 95.00%. The author identifies the framework's static, "
        "hard-threshold trust computation as its main limitation, noting that it may allow "
        "sophisticated, slowly evolving insider attacks to evade fixed decision boundaries [41].",
    51: "Aversano et al. proposed SurIoT, a lightweight, explainable generative framework "
        "evaluated on several datasets, including a high-fidelity simulated ICU scenario and the "
        "IoMT-Traffic-Data corpus, achieving near-lossless reconstruction of decision-tree "
        "boundaries. Despite improving on several limitations of prior systems, SurIoT's rule "
        "generation is restricted to axis-aligned linear inequalities and stateless parameters; "
        "performance drops to an 83.08% F1-score under slow-rate DoS attacks, where the lack of "
        "temporal context and connection-state tracking allows valid TCP handshake sequences to "
        "overlap with attack traffic [42].",
    53: "Abdelhaq et al. proposed a hybrid ensemble combining Extreme Gradient Boosting (XGBoost) "
        "and SVM classifiers to strengthen cyberattack detection and preserve data integrity in "
        "IoMT networks. Cross-validated on WUSTL-EHMS-2020, the framework achieved a robust "
        "classification accuracy of 98.04%. The authors identify its dependence on a centralized "
        "data-aggregation and training pipeline -- unvalidated in decentralized or federated "
        "medical contexts with patient-privacy constraints -- along with added initialization "
        "latency from its dual-stage configuration, as its main limitations [43].",
    10: "To address these limitations, this study evaluates a Lionfish-optimized CNN-LSTM-GRU-"
        "Attention framework for binary IoMT intrusion detection under a split-aware protocol. The "
        "pipeline first removes redundant records and non-informative fields, ranks the retained "
        "variables by an ANOVA F-test, and standardizes them. Lionfish Optimization then searches "
        "for an effective combination of the number of Conv1D blocks, convolutional filter count, "
        "LSTM units, GRU units, and dropout rate (Table 3); it is compared directly against random "
        "search at a matched budget rather than assumed to be superior. One architectural point is "
        "flagged here rather than deferred to the Limitations: the LSTM and GRU layers in this "
        "architecture operate on the dataset's native tabular feature-column order, not a genuine "
        "temporal sequence of packets or events, so their contribution is best understood as an "
        "additional nonlinear feature-mixing stage rather than a model of true temporal dynamics "
        "(Section 3.4 explains this design choice in full, and Section 4.8's ablation quantifies how "
        "much each layer actually contributes). The resulting configuration is evaluated on three "
        "heterogeneous benchmarks — ECU-IoHT, WUSTL-EHMS-2020, and DSICU — alongside same-split "
        "classical baselines, an architecture ablation, and alternative-split sensitivity checks, so "
        "that the model's apparent performance can be weighed against simpler and more rigorously "
        "validated alternatives rather than reported in isolation. The main contributions of this "
        "study are as follows:",
    11: "A unified CNN-LSTM-GRU-Attention architecture is developed to learn ordered feature "
        "interactions and nonlinear feature representations within one trainable model; because the "
        "input is a tabular feature vector rather than a genuine temporal sequence (Section 3.4), we "
        "do not claim it learns long-term temporal dependencies, and its contribution relative to "
        "simpler variants is measured directly by ablation (Section 4.8) rather than assumed.",
    12: "A Lionfish Optimization procedure is integrated to search the architecture's Conv1D block "
        "count, filter count, LSTM/GRU unit counts, and dropout rate systematically, reducing "
        "dependence on manual trial-and-error tuning, and is compared directly against random search "
        "at a matched evaluation budget rather than assumed to be superior (Section 4.9).",
    13: "A consistent preprocessing pipeline combines duplicate removal, split-before-fit "
        "partitioning, ANOVA feature ranking, and z-score standardization to improve data quality and "
        "reduce irrelevant variation; the ANOVA step ranks the retained non-constant features but "
        "does not discard any of them (Section 3.2).",
    14: "A split-before-fit evaluation protocol is applied uniformly across three heterogeneous "
        "IoMT benchmarks — ECU-IoHT, WUSTL-EHMS-2020, and DSICU — and used to test the proposed "
        "architecture and optimizer against matched-split classical baselines (Section 4.7), a "
        "matched-budget random-search optimizer control run as both a single-run and a three-seed "
        "comparison (Section 4.9), a corrected resampled significance test across independently "
        "reseeded splits (Section 4.13), and alternative (temporal or flow-grouped) splits with "
        "identifier-like fields excluded and hyperparameters re-searched per split (Section 4.10). "
        "On two of the three benchmarks, this protocol shows a substantially simpler classical model "
        "outperforms the proposed hybrid architecture, and that the Lionfish optimizer does not "
        "outperform unguided random search at a matched budget — a demonstration that a single "
        "split-before-fit accuracy number is not, by itself, sufficient evidence of deployable "
        "generalization, and that the evaluation protocol itself, rather than the architecture or "
        "optimizer, is this study's principal contribution.",
    15: "The remainder of the paper is organized as follows. Section 2 reviews related "
        "intrusion-detection studies and identifies the unresolved gaps. Section 3 presents the "
        "datasets, preprocessing stages, Lionfish Optimization procedure, and hybrid network "
        "architecture. Section 4 reports the experimental findings, including matched classical "
        "baselines, the architecture ablation, the random-search optimizer control, statistical "
        "significance testing, the alternative-split sensitivity analysis, and follow-up "
        "class-imbalance-mitigation, sliding-window-sequence, and reseeded-split significance "
        "experiments. Section 5 discusses these findings and their limitations. Section 6 concludes "
        "the paper and outlines directions for further research.",
    59: "The proposed framework addresses these gaps through a compact and integrated design. ANOVA "
        "feature ranking orders predictors by an F-test score without discarding any of them (Section "
        "3.2), while z-score standardization reduces scale-related bias. The CNN component captures "
        "local interactions, and the LSTM, GRU, and attention layers provide additional nonlinear "
        "feature-mixing stages over the dataset's native feature-column order rather than a model of "
        "genuine temporal dependencies (Section 3.4). Lionfish Optimization replaces manual "
        "architectural-parameter selection with a data-driven search process, evaluated against "
        "random search rather than assumed to be superior (Section 4.9). Finally, evaluation on "
        "ECU-IoHT, WUSTL-EHMS-2020, and DSICU provides broader evidence of cross-dataset consistency "
        "than studies restricted to one traffic source.",
}


with open(f"{RESULTS_DIR}/intro_relwork_paras.json") as f:
    ORIG_PARAS = json.load(f)


def orig(idx):
    if idx in ORIG_OVERRIDE:
        return ORIG_OVERRIDE[idx].replace(" -- ", " — ")
    return ORIG_PARAS[idx - 5].strip()


def load(name):
    with open(f"{RESULTS_DIR}/{name.replace(' ', '_')}_results.json") as f:
        return json.load(f)


R = {n: load(n) for n in ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]}
FINAL_EPOCHS_CAP = 80  # matches pipeline.py FINAL_EPOCHS


def load_extra(name, suffix):
    """Load an optional extra-results JSON (baselines/ablation/randsearch/
    sensitivity/extra_metrics); returns None if the file doesn't exist."""
    path = f"{RESULTS_DIR}/{name.replace(' ', '_')}_{suffix}.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


BASE = {n: load_extra(n, "baselines") for n in ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]}
ABL = {n: load_extra(n, "ablation") for n in ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]}
RANDS = {n: load_extra(n, "randsearch") for n in ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]}
SENS = {n: load_extra(n, "sensitivity") for n in ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]}
EXTRA = {n: load_extra(n, "extra_metrics") for n in ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]}
NOID = {n: load_extra(n, "noid") for n in ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]}
SENS2 = {n: load_extra(n, "sensitivity_v2") for n in ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]}
RSEED = {n: load_extra(n, "repeated_seeds") for n in ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]}
BASE_EXTRA = {n: load_extra(n, "baseline_extra_metrics") for n in ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]}
MULTISEED = {n: load_extra(n, "lfo_vs_rs_multiseed") for n in ["ECU-IoHT", "WUSTL-EHMS-2020"]}
SLIDING_WINDOW_V2 = load_extra("ECU-IoHT", "sliding_window_v2")
RECALL_FIX_V2 = load_extra("WUSTL-EHMS-2020", "recall_fix_v2")
with open(f"{RESULTS_DIR}/DSICU_per_feature_auc.json") as f:
    DSICU_AUC = json.load(f)
with open(f"{RESULTS_DIR}/baselines_multiseed_all.json") as f:
    MULTISEED_BASE = json.load(f)
INFCOST = {n: load_extra(n, "inference_cost") for n in ["ECU-IoHT", "WUSTL-EHMS-2020"]}
with open(f"{RESULTS_DIR}/per_attack_class_recall.json") as f:
    PER_ATTACK = json.load(f)
with open(f"{RESULTS_DIR}/wustl_pr_curve_ap.json") as f:
    WUSTL_PR_AP = json.load(f)
with open(f"{RESULTS_DIR}/reseeded_splits_nb_test.json") as f:
    NB_TEST = json.load(f)

_sig_path = f"{RESULTS_DIR}/significance_test.json"
SIG = None
if os.path.exists(_sig_path):
    with open(_sig_path) as f:
        SIG = json.load(f)

# ---------------------------------------------------------------------
# Open the official template and clear its placeholder body content,
# keeping headers/footers/styles/sectPr intact.
# ---------------------------------------------------------------------
doc = Document(WORK_TEMPLATE_COPY)
body = doc.element.body
sectPr = body.find(qn("w:sectPr"))

# The template's sectPr carries a stray <w:bidi/> (right-to-left section)
# flag, almost certainly a leftover from whoever last saved this .dot in an
# Arabic-locale Word install. Our content is English/LTR; left in place,
# this flips table column order (and can mirror margins) on render. Strip it.
_bidi_el = sectPr.find(qn("w:bidi"))
if _bidi_el is not None:
    sectPr.remove(_bidi_el)

# Save the front-matter "Academic Editor / Received / Citation / Copyright"
# floating box (first <w:tbl> in the body) before wiping the body, so we can
# reinsert it verbatim (this metadata block is filled in by MDPI editorial
# staff at production time, not by authors -- we keep it as-is per template
# convention, only refreshing the copyright year).
box_tbl = body.find(qn("w:tbl"))
box_xml = None
if box_tbl is not None:
    box_xml = box_tbl.xml.replace("© 2025 by the authors", "© 2026 by the authors")

for child in list(body):
    if child is not sectPr:
        body.remove(child)

_last_was_heading = [False]


def add_heading(text, level=1):
    style = {1: "MDPI21heading1", 2: "MDPI22heading2", 3: "MDPI23heading3"}[level]
    p = doc.add_paragraph(text, style=style)
    _last_was_heading[0] = True
    return p


def add_para(text, italic=False, bold=False, align=None, size=None, style=None):
    if style is None:
        style = "MDPI32textnoindent" if _last_was_heading[0] else "MDPI31text"
    _last_was_heading[0] = False
    p = doc.add_paragraph(style=style)
    r = p.add_run(text)
    r.italic = italic
    r.bold = bold
    if size:
        r.font.size = Pt(size)
    if align:
        p.alignment = align
    return p


def add_backmatter(label, text):
    _last_was_heading[0] = False
    p = doc.add_paragraph(style="MDPI62backmatter")
    r = p.add_run(f"{label}: ")
    r.bold = True
    p.add_run(text)
    return p


def add_table_caption(text):
    p = doc.add_paragraph(text, style="MDPI41tablecaption")
    return p


def add_figure_caption(text):
    p = doc.add_paragraph(text, style="MDPI51figurecaption")
    return p


def _set_table_three_line_borders(table, n_header_rows=1):
    tbl = table._tbl
    tblPr = tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge, sz in [("top", 8), ("bottom", 8)]:
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "auto")
        borders.append(el)
    for edge in ("left", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "none")
        el.set(qn("w:sz"), "0")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "auto")
        borders.append(el)
    tblPr.append(borders)
    # bottom border under the header row(s)
    for row in table.rows[:n_header_rows]:
        for cell in row.cells:
            tcPr = cell._tc.get_or_add_tcPr()
            tcBorders = OxmlElement("w:tcBorders")
            bottom = OxmlElement("w:bottom")
            bottom.set(qn("w:val"), "single")
            bottom.set(qn("w:sz"), "4")
            bottom.set(qn("w:space"), "0")
            bottom.set(qn("w:color"), "auto")
            tcBorders.append(bottom)
            tcPr.append(tcBorders)


def add_table(headers, rows, bold_cells=None):
    """bold_cells: optional set of (row_index, col_index) 0-indexed into `rows`
    (not counting the header row) whose text should render bold, for marking
    the winning value in a comparison table."""
    bold_cells = bold_cells or set()
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    bidiVisual = OxmlElement("w:bidiVisual")
    bidiVisual.set(qn("w:val"), "0")
    t._tbl.tblPr.insert(0, bidiVisual)
    # Mark the header row to repeat on every page the table continues onto
    # (Word's "Repeat Header Rows" property), so multi-page tables like
    # Table 8/9 don't lose their column headings after a page break.
    tr = t.rows[0]._tr
    trPr = tr.get_or_add_trPr()
    tblHeader = OxmlElement("w:tblHeader")
    tblHeader.set(qn("w:val"), "true")
    trPr.append(tblHeader)
    hdr = t.rows[0].cells
    for i, htext in enumerate(headers):
        hdr[i].text = ""
        p = hdr[i].paragraphs[0]
        p.style = doc.styles["MDPI42tablebody"]
        r = p.add_run(htext)
        r.bold = True
        r.font.size = Pt(8.5)
    for ridx, row in enumerate(rows):
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.style = doc.styles["MDPI42tablebody"]
            r = p.add_run(str(val))
            r.font.size = Pt(8.5)
            if (ridx, i) in bold_cells:
                r.bold = True
    _set_table_three_line_borders(t)
    doc.add_paragraph(style="MDPI31text")
    _last_was_heading[0] = False
    return t


def add_figure(path, caption, width_in=5.5):
    p = doc.add_paragraph(style="MDPI52figure")
    run = p.add_run()
    run.add_picture(path, width=Inches(width_in))
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fc = add_figure_caption(caption)
    fc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _last_was_heading[0] = False


_eq_counter = [0]


def add_equation(formula, label=None):
    """Numbered equation: formula text, right-tab-stopped equation number,
    using the template's own MDPI39equation paragraph style (which defines
    the tab stops for this layout) rather than a hand-built table."""
    _eq_counter[0] += 1
    n = _eq_counter[0]
    p = doc.add_paragraph(style="MDPI39equation")
    p.add_run(formula)
    p.add_run("\t" + f"({n})")
    _last_was_heading[0] = False
    return n


def add_algorithm_box(title, lines):
    """A bordered one-cell table containing a numbered-pseudocode algorithm
    block, styled to read as a self-contained 'Algorithm N' figure the way
    MDPI articles typically present pseudocode (no native 'algorithm' style
    ships in the template, so a bordered table stands in for one)."""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.rows[0].cells[0]
    _set_table_three_line_borders(tbl, n_header_rows=0)
    tblPr = tbl._tbl.tblPr
    for el in tbl._tbl.findall(qn("w:tblBorders")):
        for edge in el:
            edge.set(qn("w:sz"), "4")
    p0 = cell.paragraphs[0]
    r0 = p0.add_run(title)
    r0.bold = True
    for line in lines:
        p = cell.add_paragraph()
        p.add_run(line)
    _last_was_heading[0] = False
    return tbl


# =======================================================================
# TITLE PAGE
# =======================================================================
doc.add_paragraph("Article", style="MDPI11articletype")

title = ("Split-Aware Evaluation of Hybrid Deep Learning for IoMT Intrusion Detection: "
          "Matched Baselines, Optimizer Controls, and Alternative Splits")
doc.add_paragraph(title, style="MDPI12title")

doc.add_paragraph(
    "Hiba A. Tarish ¹², Rosilah Hassan ¹, Mustafa Musa Jaber ³*",
    style="MDPI13authornames",
)

# Front-matter Academic Editor / history / citation / copyright box, reused
# verbatim from the official template (filled in by MDPI editorial staff).
if box_xml is not None:
    box_el = parse_xml(box_xml)
    # insert right after the authors paragraph (which is now the last
    # element in the body before sectPr)
    body.insert(list(body).index(sectPr), box_el)

for line in [
    "¹ Centre for Cyber Security, Faculty of Information Science and Technology, "
    "Universiti Kebangsaan Malaysia (UKM), Bangi, Selangor, Malaysia",
    "² Civil Engineering Department, University of Technology, Baghdad, Iraq",
    "³ Informatics Institute for Postgraduate Studies, Iraqi Commission for Computers "
    "and Informatics, Baghdad, Iraq",
    "* Correspondence: mustafa.musa@iips.edu.iq",
]:
    doc.add_paragraph(line, style="MDPI16affiliation")

# =======================================================================
# ABSTRACT
# =======================================================================
abstract = (
    "Background: many IoMT intrusion-detection studies report near-perfect accuracy without rigorous "
    "evaluation. This evaluation-methodology study tests whether a proposed architecture survives "
    "scrutiny, rather than claiming superiority. Methods: we evaluate a Lionfish-tuned hybrid "
    "CNN-LSTM-GRU-Attention network under a split-before-fit protocol on ECU-IoHT and "
    "WUSTL-EHMS-2020, checked against multi-seed classical baselines, an architecture ablation, "
    "single-run and three-seed random-search controls, a corrected resampled significance test "
    "across reseeded splits, and budget-matched temporal splits with identifier-like fields excluded. "
    "Results: classical baselines matched or exceeded the hybrid model on both benchmarks; the "
    "corrected test confirmed this for WUSTL-EHMS-2020 but not yet for ECU-IoHT at the tested reseed "
    "count, despite the baseline winning every reseed. Random search matched or exceeded Lionfish "
    "across both a single-run and a three-seed follow-up. Removing identifier-like fields and moving "
    "to a temporal split both reduced performance materially, notably a recall drop on "
    "WUSTL-EHMS-2020 only partially recovered by a class-weighted loss. A restricted-access third "
    "benchmark reached perfect, artifact-like separability under every check and is reported as a "
    "cautionary case study, not a validated result. Conclusions: a split-before-fit protocol alone "
    "does not establish deployability; matched baselines, ablations, significance testing, and "
    "alternative splits together distinguish real generalization from artifacts, favoring simpler "
    "models over the proposed architecture and optimizer."
)
doc.add_paragraph(abstract, style="MDPI17abstract")

kw = doc.add_paragraph(style="MDPI18keywords")
r = kw.add_run("Keywords: ")
r.bold = True
kw.add_run(
    "Internet of Medical Things; IoMT security; intrusion detection; hybrid deep learning; Lionfish "
    "optimization; attention mechanism; split-before-fit evaluation; class imbalance; negative "
    "results; reproducibility; cybersecurity"
)

# =======================================================================
# 1. INTRODUCTION
# =======================================================================
add_heading("1. Introduction", level=1)

add_para(
    "The rapid growth of Internet of Things (IoT) deployments across domains such as "
    f"smart agriculture {cite('orig1')}, distributed cloud-edge infrastructure {cite('orig2')}, "
    f"5G-integrated networks {cite('orig4')}, and wearable physiological monitoring "
    f"{cite('orig5')} has been mirrored by a corresponding growth in IoT-specific security "
    f"research, including dataset augmentation for Internet of Medical Things (IoMT) "
    f"security {cite('orig3')}. This broader research program in IoT security and anomaly "
    f"detection includes prior work by members of this research group on deep-learning-"
    f"based intrusion detection for IoT architectures {cite('hassan_iot_anomaly_2021')}, "
    f"a survey of network security frameworks for Internet of Medical Things applications "
    f"{cite('hassan_iomt_survey_2024')}, and federated learning for cyber threat intelligence "
    f"{cite('hassan_fedcvae_2025')}, on which the present study builds. Beyond classical "
    f"threat models, quantum-resilient security frameworks for the Internet of Medical "
    f"Things have also recently been proposed {cite('quantum_iomt_2025')}."
)

for idx in range(6, 16):
    t = orig(idx)
    if t:
        add_para(renumber(t))

add_para(
    f"Distributed denial-of-service attacks in particular remain among the most "
    f"disruptive threats to IoT and IoMT networks, and have been the subject of extensive "
    f"review and detection work {cite('orig9', 'orig10')}. Beyond DDoS, general healthcare "
    f"intrusion detection has been surveyed broadly {cite('orig11')}, and AI-based IoMT "
    f"security specifically has been the subject of comprehensive review "
    f"{cite('orig12')}. Traditional classifiers such as decision trees {cite('orig15')} "
    f"and support vector machines {cite('orig16')} remain useful baselines because of their "
    f"modest computational requirements, though their capacity to model nonlinear temporal "
    f"attack patterns is limited compared to deep architectures."
)

# =======================================================================
# 2. RELATED WORK
# =======================================================================
add_heading("2. Related Work", level=1)

add_heading("2.1. Background: ICU Telemetry Data — Clinical-Outcome Prediction vs. Intrusion Detection", level=2)
add_para(
    "DSICU is an intrusion-detection benchmark (Normal/Attack labels on MQTT/TCP telemetry), but no "
    "published intrusion-detection study on this specific capture was identified in our search. The "
    "four studies below instead use MIMIC-IV, a separate, widely used public ICU database, for "
    "clinical-outcome prediction (in-hospital mortality risk, length of stay) rather than "
    "attack/intrusion classification. We summarize them only as background on the broader landscape "
    "of machine learning applied to ICU telemetry data; because their task, labels, and metrics "
    "differ fundamentally from intrusion detection, they are not included in the direct performance "
    "comparison in Section 5.1 (Table 14)."
)
for idx in [19, 20, 21, 22]:
    t = orig(idx)
    if t:
        add_para(renumber(t))

add_para(
    "No published intrusion-detection study evaluated on DSICU specifically was identified in our "
    "search; Section 2.3 discusses the one closely related quantum-driven framework that shares one "
    "benchmark (WUSTL-EHMS-2020) with the present study, but it was not evaluated on DSICU or "
    "ECU-IoHT and is not cited as DSICU-related work here."
)

add_heading("2.2. Related Work on ECU-IoHT Data", level=2)
for idx in [27, 28, 29, 30, 31, 33]:
    t = orig(idx)
    if t:
        add_para(renumber(t))

add_heading("2.3. Related Work on WUSTL-EHMS-2020 Data", level=2)
for idx in [38, 39, 41, 43, 45, 47, 49, 51, 53]:
    t = orig(idx)
    if t:
        add_para(renumber(t))

add_para(
    "Table 1 summarizes the studies reviewed above. The Task column flags studies that solve a "
    "different problem (ICU clinical-outcome prediction on MIMIC-IV) from the intrusion/attack "
    "detection task addressed in this paper; those rows are background context only and are not "
    "carried into the direct comparison tables in Section 5.1."
)
add_table_caption("Table 1. Summary of related work on ICU telemetry, ECU-IoHT, and WUSTL-EHMS-2020.")
rel_rows = [
    ["Pang et al. (2022)", "XGBoost, SVM, LogR, DT", "MIMIC-IV", "Outcome prediction (not comparable)", "92.2%", "Random downsampling risks clinical information loss."],
    ["Karboub & Tabaa (2022)", "Dynamic ML-SGD Regression", "MIMIC-IV", "Outcome prediction (not comparable)", "98%", "Reduced precision for long-stay (LOS > 3 d) patients."],
    ["Hempel et al. (2023)", "LinR, SVM, RF, XGBoost", "MIMIC-IV", "Outcome prediction (not comparable)", "MAPE ≈ 33%", "Compressing time-series to mean values drops granularity."],
    ["Koumantakis et al. (2025)", "LSTM, RNN, GRU", "MIMIC-IV (meta-analysis)", "Outcome prediction (not comparable)", "92%", "Overall high risk of bias (meta-analysis)."],
    ["Krishna Kumari et al. (2026)", "MREQGAN-DSA", "NSL-KDD, WUSTL-EHMS-2020", "Intrusion detection", "99.81% / 99.77%", "High architectural/compute overhead from quantum components; not evaluated on DSICU or ECU-IoHT despite some secondary summaries describing it as multi-dataset across those benchmarks."],
    ["Vijayakumar et al. (2023)", "DNN", "ECU-IoHT", "Intrusion detection", "99.85%", "Degrades on non-Gaussian/skewed raw features."],
    ["Areia et al. (2024)", "DT, RF, NB, LogR, SVM, DNN", "ECU-IoHT", "Intrusion detection", "RF/DT 99%", "Statistical instability across classifiers."],
    ["Algethami & Alshamrani (2024)", "HANN-BLSTM", "ECU-IoHT", "Intrusion detection", "99.85%", "Lower precision on Smurf-attack detection."],
    ["Alohali et al. (2025)", "EloHTSCD-SEGO", "ECU-IoHT", "Intrusion detection", "99.33%", "No evaluation of edge computational cost."],
    ["Mosaiyebzadeh et al. (2025)", "CNN / DNN", "ECU-IoHT / WUSTL", "Intrusion detection", "95.48% / 93.20%", "Sensitive to gradient-noise tuning."],
    ["Alharbi & Khan (2025)", "CNN-LSTM", "ECU-IoHT", "Intrusion detection", "98%", "No decentralized/privacy-constraint evaluation."],
    ["Tauqeer et al. (2022)", "RF, Gradient Boosting, SVM", "WUSTL-EHMS-2020", "Intrusion detection", "96.9% / 96.5% / 95.85%", "No cryptographic or federated protection layer."],
    ["Judith et al. (2023)", "PCA + MLP (ReLU/Sigmoid)", "WUSTL-EHMS-2020", "Intrusion detection", "96.39%", "Higher false positives on overlapping traffic signatures."],
    ["Shaikh et al. (2024)", "RCLNet", "WUSTL-EHMS-2020", "Intrusion detection", "99.78%", "Degrades under non-stationary streaming drift."],
    ["Wu et al. (2025)", "Deep learning + Kernel PCA", "WUSTL-EHMS-2020", "Intrusion detection", "94.29%", "High inference latency on low-power edge nodes."],
    ["Balhareth et al. (2026)", "ML-FSID-FIS", "WUSTL-EHMS-2020", "Intrusion detection", "93.0%", "Evaluated on a single-dataset protocol only."],
    ["Abid (2026)", "KNN, RF, SVM (hard voting)", "WUSTL-EHMS-2020", "Intrusion detection", "95%", "Hard voting limits minority-class sensitivity."],
    ["Aversano et al. (2026)", "SurIoT", "WUSTL-EHMS-2020", "Intrusion detection", "99.85%", "Drops to 83.08% under slow-rate DoS attacks."],
    ["Abdelhaq et al. (2026)", "XGBoost-PCA + SVM", "WUSTL-EHMS-2020", "Intrusion detection", "98.04%", "Relies on a centralized training paradigm."],
]
add_table(["Author(s)", "Methodology", "Dataset(s)", "Task", "Reported Result", "Limitations / Gaps"], rel_rows)

for idx in [58, 59]:
    t = orig(idx)
    if t:
        add_para(renumber(t))

# =======================================================================
# 3. MATERIALS AND METHODS
# =======================================================================
add_heading("3. Materials and Methods", level=1)
add_para(
    "This study designs, tunes, and evaluates a hybrid deep-learning intrusion detection framework "
    "for IoMT and telemetry-enabled healthcare data. Every stage — feature selection, scaling, "
    "hyperparameter search, and model training — is fit exclusively on a training partition that is "
    "created before any of these steps run (split-before-fit), so that no information from the "
    "held-out test partition can influence model configuration or reported performance."
)

add_heading("3.1. Datasets", level=2)
# NOTE: corrected -- the DSICU feature file was verified (Section 5.3) to be
# UNSELECTED raw protocol data, byte-identical to an earlier unselected
# export; it had NOT undergone prior mutual-information-based selection.
add_para(
    f"Three benchmark datasets were used, two public and one restricted-access. ECU-IoHT "
    f"{cite('ecu_dataset')} is a raw packet-capture export of "
    "111,207 records from an IoMT testbed, containing timestamp, protocol, packet length, and "
    "categorical Normal/Attack labels; source/destination IP addresses and free-text packet "
    "descriptions were excluded as features because they do not generalize across deployments. "
    f"WUSTL-EHMS-2020 {cite('wustl_dataset')} provides 16,318 pre-extracted network-flow and "
    "physiological features "
    "(37 columns) with a binary label; its attack class is a genuine minority (2,046 of 16,318 "
    "records, 12.5%). DSICU is an MQTT/TCP telemetry capture of 188,694 records with 17 raw "
    "protocol-level features and a binary label; its filename carries an “_mi” suffix suggesting "
    "prior mutual-information-based feature selection, but this was verified in Section 5.5 to be a "
    "misleading label — the supplied file is byte-identical to an independently produced, unselected "
    "export of the same capture, so no feature-selection step had in fact been applied before it "
    "reached this study's own split-before-fit pipeline. Unlike ECU-IoHT and WUSTL-EHMS-2020, which "
    "are publicly available from their original publishers, DSICU is not publicly redistributable and "
    "is available from the corresponding author on reasonable request (see the Data Availability "
    "Statement)."
)
add_table_caption(
    "Table 2. Dataset summary after split-before-fit preprocessing (70%/30% stratified split "
    "and train-only removal of zero-variance columns; no columns were dropped by the ANOVA "
    "ranking step itself, see Section 3.2). ECU-IoHT's 13 retained features expand from its 3 "
    "raw fields (timestamp, packet length, protocol) after one-hot encoding of the categorical "
    "Protocol field."
)
ds_rows = [
    ["ECU-IoHT", "111,207", "13", "77,844 / 33,363", "Attack 78.9% / Normal 21.1%"],
    ["WUSTL-EHMS-2020", "16,318", "30", "11,422 / 4,896", "Attack 12.5% / Normal 87.5%"],
    ["DSICU", "188,694", "16", "132,085 / 56,609", "Attack 42.5% / Normal 57.5%"],
]
add_table(["Dataset", "Total Records", "Non-Constant Features Retained", "Train / Test Split", "Class Balance"], ds_rows)

add_heading("3.2. Split-Before-Fit Preprocessing", level=2)
add_para(
    "We use \"split-before-fit\" rather than the broader term \"leakage-free\" throughout this "
    "paper to describe the preprocessing protocol precisely: for each dataset, records were split "
    "70%/30% into train and test partitions using stratified sampling on the label "
    "(random_state = 42) before any other processing occurred. Within the training partition only, "
    "columns with zero variance were dropped (their ANOVA F-statistic is undefined), an ANOVA "
    "F-test (SelectKBest, scikit-learn) ranked the remaining columns — no columns were discarded by "
    "this ranking step itself, since k was set to retain all non-constant features — and a z-score "
    "StandardScaler was fit. Both the ranking step and the scaler were then applied, unmodified, to "
    "the test partition. ECU-IoHT's categorical Protocol field was one-hot encoded before ranking. "
    "Each sample was reshaped to "
    f"(features, 1) for input to the Conv1D front end of the network. This discipline "
    f"is motivated by the broader data-stream literature, where concept drift and novel-"
    f"class detection make it easy for evaluation statistics computed across an entire dataset to "
    f"leak information about samples a deployed model would not yet have seen {cite('orig7', 'orig8')}, "
    f"and by prior systematic comparisons of deep-learning method selection under such constraints "
    f"{cite('orig21')}. Importantly, split-before-fit preprocessing only rules out one specific "
    "leakage mechanism — fitting a feature selector or scaler on data the model will later be "
    "tested on. It does not by itself guarantee that individual train and test records are "
    "otherwise unrelated: under simple random stratified splitting, records from the same network "
    "flow, device, or narrow time window can still appear in both partitions. Section 4.10 and "
    "Section 5.4 evaluate this directly with a sensitivity analysis that replaces the random split "
    "with a temporal or flow-grouped split for each dataset."
)

add_heading("3.3. Lionfish Optimization Algorithm", level=2)
add_para(
    "Five architectural hyperparameters — number of Conv1D blocks, convolutional filter count, "
    "LSTM units, GRU units, and dropout rate — were tuned with a population-based Lionfish "
    "metaheuristic inspired by lionfish hunting behavior, rather than manual trial-and-error, "
    f"following the broader precedent of nature-inspired metaheuristics for automated "
    f"hierarchical deep-learning hyperparameter search in other data-driven prediction domains "
    f"{cite('orig14', 'orig24')}. A "
    "population of 6 candidate configurations was initialized uniformly at random within the bounds "
    "in Table 3. At each of 6 iterations t = 1, …, 6, an environmental factor E ~ U(0.1, 1.0), "
    "exploration age a ~ U(0, 1), and certainty term C ~ U(0.5, 1.5) are drawn, from which a decay "
    "(exploration-to-exploitation) factor D, a vision-sharpness (velocity/speed) term VS, and an "
    "intentional-movement magnitude M ~ U(0.2, 1.0) are computed:"
)
add_equation("D(t) = 1 − exp(−E · t)")
add_equation("VS = exp(−a · C)")
add_equation("H = D · VS · M")
add_para(
    "The compound hunting factor Hu then scales each candidate's step toward a randomly generated "
    "prey position p in hyperparameter space, with a fixed step-size multiplier η = 0.5:"
)
add_equation("Hu = D · VS · M · H · E")
add_equation("x_i(t+1) = clip( x_i(t) + Hu · η · ( p(t) − x_i(t) ),  lower_i, upper_i )")
add_para(
    "where x_i(t) is candidate i's position (the 5-dimensional hyperparameter vector) at iteration "
    "t, p(t) is an independently resampled prey position drawn uniformly from the same bounds as "
    "the initial population, and clip(·, lower_i, upper_i) projects each coordinate back into its "
    "bound from Table 3 (rounding to the nearest integer for the four integer-valued "
    "hyperparameters). Each candidate was evaluated by building the hybrid network with that "
    "configuration, training for 3 epochs on 80% of the training partition (batch size 1024), and "
    "measuring accuracy on the remaining 20% (held out from the training partition only, never "
    "touching the test partition); fitness was one minus this validation accuracy (Equation (6)). "
    "Personal-best and global-best positions were tracked across iterations and the global-best "
    "position was returned as the final hyperparameter configuration. Algorithm 1 summarizes the "
    "full procedure."
)
add_equation("fitness(x_i) = 1 − Accuracy_val( f_θ(x_i) )")
add_algorithm_box(
    "Algorithm 1. Lionfish Optimization for hyperparameter search.",
    [
        "Input: bounds {(lower_k, upper_k)} for k = 1..5 (Table 3); population size N = 6; "
        "iterations T = 6; quick-eval epochs = 3; training data (X_opt, y_opt), validation data "
        "(X_val, y_val)",
        "Output: best hyperparameter configuration x*",
        "1:  Initialize population {x_1, ..., x_N}, each x_i ~ U(lower, upper) elementwise",
        "2:  For each x_i in population: evaluate fitness(x_i) via Equation (6); "
        "set personal_best_i = x_i, personal_best_fit_i = fitness(x_i)",
        "3:  global_best = argmin_i personal_best_fit_i",
        "4:  For t = 1 to T:",
        "5:      Sample E ~ U(0.1, 1.0), a ~ U(0, 1), C ~ U(0.5, 1.5), M ~ U(0.2, 1.0)",
        "6:      Compute D(t), VS, H, Hu via Equations (1)-(4)",
        "7:      Sample a new prey position p(t) ~ U(lower, upper) elementwise",
        "8:      For each candidate x_i in population:",
        "9:          x_i ← clip(x_i + Hu · η · (p(t) − x_i), lower, upper)   [Equation (5), η = 0.5]",
        "10:         Evaluate fitness(x_i) via Equation (6)",
        "11:         If fitness(x_i) < personal_best_fit_i: update personal_best_i, "
        "personal_best_fit_i",
        "12:     global_best = argmin over all personal_best_i of personal_best_fit_i",
        "13: Return x* = global_best",
    ],
)
add_table_caption("Table 3. Search space for the Lionfish Optimization Algorithm.")
lf_rows = [
    ["Number of Conv1D blocks", "1", "3"],
    ["Conv1D filters per block", "16", "64"],
    ["LSTM units", "16", "64"],
    ["GRU units", "16", "64"],
    ["Dropout rate", "0.1", "0.5"],
]
add_table(["Hyperparameter", "Lower Bound", "Upper Bound"], lf_rows)

add_table_caption("Table 4. Lionfish-optimized hyperparameters selected per dataset.")
best_rows = []
for name in ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]:
    p = R[name]["lionfish_best_params"]
    best_rows.append([name, p["n_conv_blocks"], p["conv_filters"], p["lstm_units"],
                       p["gru_units"], f"{p['dropout_rate']:.3f}"])
add_table(["Dataset", "Conv Blocks", "Filters", "LSTM Units", "GRU Units", "Dropout"], best_rows)

add_heading("3.4. Hybrid CNN-LSTM-GRU-Attention Architecture", level=2)
add_para(
    "Using the optimized hyperparameters, each classifier is assembled as a single forward pipeline "
    "(Figure 1). The standardized, feature-selected input passes through the optimized number of "
    "Conv1D blocks (kernel size 3, same padding), each followed by a LeakyReLU activation (α = 0.3) "
    f"and batch normalization, to extract local feature interactions, consistent with established "
    f"convolutional feature-extraction principles {cite('orig17')} and their application to "
    f"lightweight time-series processing {cite('orig22')}:"
)
add_figure(f"{FIG_DIR}/architecture_diagram.png",
           "Figure 1. Hybrid CNN-LSTM-GRU-Attention architecture, with the output tensor shape "
           "annotated at each stage.", width_in=3.3)
add_equation("h = LeakyReLU_{0.3}( BatchNorm( W ∗ x + b ) )")
add_para(
    f"where ∗ denotes 1-D convolution, W and b are the layer's learned filter weights and bias, and "
    f"LeakyReLU_0.3(z) = z for z ≥ 0 and 0.3z otherwise. The convolutional output feeds an LSTM "
    f"layer (return_sequences = True) for long-range temporal dependencies {cite('orig18')}, followed "
    f"by a GRU layer (return_sequences = True) for faster-adapting temporal dynamics, whose "
    f"trade-offs relative to LSTM are well documented in comparative sequence-learning reviews "
    f"{cite('orig23')}. A 4-head self-attention block "
    f"then attends over the GRU output (query Q = key K = value V = the GRU output sequence), with "
    f"a residual connection and layer normalization, drawing on attention-driven representation "
    f"learning for anomaly detection {cite('orig25')}:"
)
add_equation("Attention(Q, K, V) = softmax( Q Kᵀ / √d_k ) V")
add_para(
    "where d_k is the per-head key dimension (d_k = max(4, gru_units / 4) in this architecture, so "
    "that the 4 attention heads jointly span the full GRU output width), and the block output is "
    "LayerNorm(Attention(Q,K,V) + V) (residual connection). Global average pooling compresses the "
    "sequence to a fixed-length vector, a dropout layer regularizes it at the optimized rate, and a "
    "single sigmoid unit produces the binary Normal/Attack prediction. All models were compiled with "
    "the Adam optimizer, minimizing binary cross-entropy loss (Equation (9)) for the main "
    "experiment, or one of two class-imbalance-aware alternatives evaluated in Section 4.11: "
    "class-weighted binary cross-entropy (Equation (10)) or focal loss (Equation (11), γ = 2.0, "
    "α = 0.25)."
)
add_equation("L_BCE = −[ y·log(p) + (1−y)·log(1−p) ]")
add_equation("L_wBCE = −[ w₁·y·log(p) + w₀·(1−y)·log(1−p) ],  w₁ = n₀/n₁, w₀ = 1")
add_equation("L_focal = −α_t·(1−p_t)^γ·log(p_t),  p_t = p if y=1 else 1−p,  α_t = α if y=1 else 1−α")
add_para(
    "where y is the true binary label, p is the model's predicted probability of the Attack class, "
    "and n₀, n₁ are the training-set counts of the Normal and Attack classes respectively (so w₁ "
    "up-weights the minority Attack class in proportion to its scarcity)."
)
add_para(
    "A design choice deserves explicit comment: the LSTM and GRU layers process the feature vector "
    "in the dataset's native column order (e.g., protocol, length, timestamp for ECU-IoHT), not a "
    "sequence of genuinely ordered events, packets, or time windows. This is common practice when "
    "adapting CNN-LSTM-GRU hybrids to tabular network-flow and telemetry data, where the Conv1D "
    "layers are the primary mechanism extracting local interactions between adjacent columns, and "
    "the recurrent layers act as an additional nonlinear feature-mixing stage over that Conv1D "
    "output rather than as a model of temporal dynamics across records. We do not claim the network "
    "learns genuine temporal structure across samples, only that this architecture is one way to "
    "compose convolutional, recurrent, and attention layers for tabular classification; Section 4.8 "
    "reports an ablation that isolates how much each layer type actually contributes for each "
    "dataset, and Section 5.5 revisits this design choice as a limitation rather than a strength of "
    "the architecture."
)

add_heading("3.5. Training, Cross-Validation, and Test Evaluation", level=2)
add_para(
    "Model stability was assessed with stratified 5-fold cross-validation on the training partition "
    "only (up to 10 epochs per fold, batch size 512, early stopping on validation accuracy with "
    "patience 4), using the Lionfish-optimized hyperparameters for that dataset. A final model, "
    "built with the same hyperparameters, was then trained on the entire training partition (batch "
    "size 128, identical across all three datasets, up to 80 epochs, early stopping on training loss "
    "with patience 8) and evaluated exactly once on the held-out test partition. No hyperparameter, "
    "weight, or threshold decision was revised based on test-partition performance at any stage. "
    "Table 3a summarizes the batch size used at each training stage."
)
add_table_caption("Table 3a. Batch size used at each training stage (identical across all three datasets).")
add_table(
    ["Stage", "Batch Size", "Epoch Budget"],
    [
        ["Lionfish / random-search quick evaluation", "1024", "3 epochs"],
        ["5-fold cross-validation", "512", "up to 10 epochs, patience 4 (val. accuracy)"],
        ["Final model training", "128", "up to 80 epochs, patience 8 (training loss)"],
    ]
)

add_heading("3.6. Experimental Environment", level=2)
add_para(
    "The pipeline was implemented in Python 3.10 using TensorFlow/Keras 2.15 for the hybrid "
    "deep-learning architecture and scikit-learn 1.x for feature selection, scaling, splitting, and "
    "evaluation metrics. All experiments ran on CPU (no GPU acceleration) with a fixed random seed "
    "(42) applied to NumPy, TensorFlow, and all scikit-learn splitting operations."
)

# =======================================================================
# 4. RESULTS
# =======================================================================
add_heading("4. Results", level=1)

add_heading("4.1. Lionfish Optimization Convergence", level=2)
add_para(
    "Figure 2 shows the best-so-far quick-validation accuracy across the 42 candidate evaluations "
    "(6 population members × initial evaluation + 6 iterations × 6 re-evaluations) performed for "
    "each dataset. WUSTL-EHMS-2020 and ECU-IoHT converged to their best configuration within the "
    "first population evaluation and iteration 4, respectively, while DSICU reached a perfect quick-"
    "validation score in the very first iteration, foreshadowing the near-trivial separability "
    "discussed in Section 5."
)
add_figure(f"{FIG_DIR}/lionfish_convergence_merged.png",
           "Figure 2. Lionfish optimization convergence: (a) ECU-IoHT, (b) WUSTL-EHMS-2020, (c) DSICU.",
           width_in=6.3)

add_heading("4.2. Cross-Validation Stability", level=2)
add_table_caption("Table 5. Stratified 5-fold cross-validation results (train partition only).")
cv_rows = []
for name in ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]:
    d = R[name]
    folds = d.get("fold_accs", [])
    folds_str = ", ".join(f"{a:.4f}" for a in folds)
    cv_rows.append([name, folds_str, f"{d.get('cv_mean', 0):.4f}", f"{d.get('cv_std', 0):.4f}"])
add_table(["Dataset", "Per-Fold Validation Accuracy", "Mean", "Std. Dev."], cv_rows)
add_figure(f"{FIG_DIR}/cv_stability.png", "Figure 3. Cross-validation fold stability across datasets.")

add_heading("4.3. Statistical Significance Testing", level=2)
if SIG is not None:
    add_para(
        "The cross-validation folds in Table 5 make a paired significance test possible: we refit "
        "HistGradientBoostingClassifier — the strongest classical baseline on WUSTL-EHMS-2020 and "
        "the baseline used consistently across datasets for this test, though Random Forest is "
        "marginally stronger than gradient boosting on ECU-IoHT specifically (99.17% vs. 98.63%, "
        "Table 8) — on the identical five stratified folds (same split seed, same preprocessed "
        "features) used for the hybrid model's cross-validation stage, then compare the two sets of "
        "five paired fold accuracies with a paired t-test and a Wilcoxon signed-rank test. This "
        "directly tests whether the accuracy gap between the hybrid model and gradient boosting on "
        "ECU-IoHT and WUSTL-EHMS-2020 (Section 4.7) is attributable to chance; Section 4.13's "
        "reseeded-split significance test additionally covers Random Forest on both datasets."
    )
    sig_rows = []
    for name in ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]:
        s = SIG[name]
        t_p = s["paired_t_p"]
        w_p = s["wilcoxon_p"]
        t_p_str = f"{t_p:.4f}" if t_p >= 0.0001 else f"{t_p:.2e}"
        sig_rows.append([
            name,
            f"{s['hybrid_mean']*100:.2f}%",
            f"{s['gb_mean']*100:.2f}%",
            t_p_str,
            f"{w_p:.4f}",
        ])
    add_table_caption("Table 5b. Paired significance test: CV-stage hybrid model vs. gradient boosting on identical folds.")
    add_table(["Dataset", "Hybrid CV Mean", "Gradient Boosting CV Mean", "Paired t-test p",
               "Wilcoxon p"], sig_rows)
    add_para(
        "On ECU-IoHT, gradient boosting significantly exceeds the CV-stage hybrid model "
        f"({SIG['ECU-IoHT']['gb_mean']*100:.2f}% vs. {SIG['ECU-IoHT']['hybrid_mean']*100:.2f}%, "
        f"paired t-test p = {SIG['ECU-IoHT']['paired_t_p']:.2e}); the same holds for WUSTL-EHMS-2020 "
        f"({SIG['WUSTL-EHMS-2020']['gb_mean']*100:.2f}% vs. "
        f"{SIG['WUSTL-EHMS-2020']['hybrid_mean']*100:.2f}%, p = "
        f"{SIG['WUSTL-EHMS-2020']['paired_t_p']:.2e}). The Wilcoxon signed-rank test on both datasets "
        f"returns p = {SIG['ECU-IoHT']['wilcoxon_p']:.4f}, the minimum achievable value at n = 5 "
        "paired folds; it is directionally consistent with the t-test but, with only five folds, "
        "underpowered on its own. On DSICU, both models score a tied 100% on every fold, so no test "
        "applies (p = 1.0) — consistent with the near-trivial separability discussed in Section 5.3, "
        "not with a genuine advantage for either model. We emphasize a caveat: this test compares the "
        "cross-validation-stage hybrid model, trained under a 10-epoch/fold budget for tractability, "
        "against gradient boosting on the same folds — not the fully-trained final model reported in "
        "Table 6, which uses up to 80 epochs with early stopping and is evaluated once on the held-out "
        "test set rather than by cross-validation. The comparison therefore establishes that gradient "
        "boosting's edge over the hybrid architecture on ECU-IoHT and WUSTL-EHMS-2020 is statistically "
        "robust at the cross-validation stage, reinforcing rather than merely echoing the same-split "
        "comparison in Section 4.7."
    )

add_heading("4.4. Final Test-Set Performance", level=2)
add_table_caption("Table 6. Final held-out test-set performance, evaluated once per dataset.")
perf_rows = []
for name in ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]:
    d = R[name]
    perf_rows.append([name, f"{d['accuracy']*100:.2f}%", f"{d['balanced_accuracy']*100:.2f}%",
                       f"{d['precision']:.3f}", f"{d['recall']:.3f}", f"{d['f1']:.3f}",
                       d["n_params"], f"{d['train_time_sec']:.1f}", d["epochs_run"]])
add_table(["Dataset", "Accuracy", "Balanced Acc.", "Precision", "Recall", "F1", "Parameters",
           "Train Time (s)", "Epochs"], perf_rows)
add_para(
    "Table 6 reports seed 42. To characterize sensitivity to random weight initialization on this "
    "fixed main split — rather than treat a single seed as if it were a lucky or unlucky draw — we "
    "additionally trained three more seeds (43-45) on the identical main-split train/test partition "
    "and hyperparameters, under the exact same training budget as seed 42 (up to 80 epochs, "
    "early-stopping patience 8) so all four runs are directly comparable. We report mean ± standard "
    "deviation across the four seeds; this characterizes seed-to-seed variability on the fixed "
    "partition, not a confidence interval for expected generalization performance, since the "
    "train/test split itself is held constant across all four runs (Section 5.5): ECU-IoHT "
    f"{RSEED['ECU-IoHT']['mean']['accuracy']*100:.2f}% ± {RSEED['ECU-IoHT']['std']['accuracy']*100:.2f}% "
    f"accuracy (F1 = {RSEED['ECU-IoHT']['mean']['f1']:.3f} ± {RSEED['ECU-IoHT']['std']['f1']:.3f}), "
    "WUSTL-EHMS-2020 "
    f"{RSEED['WUSTL-EHMS-2020']['mean']['accuracy']*100:.2f}% ± {RSEED['WUSTL-EHMS-2020']['std']['accuracy']*100:.2f}% "
    f"accuracy (F1 = {RSEED['WUSTL-EHMS-2020']['mean']['f1']:.3f} ± {RSEED['WUSTL-EHMS-2020']['std']['f1']:.3f}), "
    "and DSICU "
    f"{RSEED['DSICU']['mean']['accuracy']*100:.2f}% ± {RSEED['DSICU']['std']['accuracy']*100:.2f}% accuracy "
    f"(F1 = {RSEED['DSICU']['mean']['f1']:.3f} ± {RSEED['DSICU']['std']['f1']:.3f}). ECU-IoHT and DSICU are "
    "stable across seeds; WUSTL-EHMS-2020's F1 varies somewhat more because the attack class is a "
    "genuine minority and the decision boundary is more sensitive to weight initialization, "
    "reinforcing that its single-seed headline number should be read with this spread in mind rather "
    "than as an exact figure."
)
add_figure(f"{FIG_DIR}/cross_dataset_summary.png", "Figure 4. Test-set performance across datasets and metrics.")

add_figure(f"{FIG_DIR}/confusion_merged.png",
           "Figure 5. Confusion matrices: (a) ECU-IoHT, (b) WUSTL-EHMS-2020, (c) DSICU.",
           width_in=6.3)

add_heading("4.5. Training Dynamics", level=2)
add_figure(f"{FIG_DIR}/training_curves_merged.png",
           "Figure 6. Final-model training dynamics: (top row) loss curves and (bottom row) accuracy "
           "curves for ECU-IoHT, WUSTL-EHMS-2020, and DSICU.", width_in=6.3)

add_heading("4.6. Extended Test-Set Metrics", level=2)
add_para(
    "Because accuracy alone can be uninformative under class imbalance (WUSTL-EHMS-2020's attack "
    "class is 12.5% of records), Table 7 reports probability-based and per-class metrics for the "
    "final model on each held-out test partition: ROC-AUC, PR-AUC (average precision), specificity "
    "(true-negative rate), and the false-negative rate (the fraction of attacks missed at the "
    "default 0.5 decision threshold)."
)
add_table_caption("Table 7. Extended test-set metrics for the final hybrid model.")
ext_rows = []
for name in ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]:
    e = EXTRA[name]
    ext_rows.append([name, f"{e['roc_auc']:.4f}", f"{e['pr_auc']:.4f}",
                      f"{e['specificity']:.4f}", f"{e['false_negative_rate']:.4f}",
                      f"{e['per_class']['attack']['recall']:.4f}"])
add_table(["Dataset", "ROC-AUC", "PR-AUC", "Specificity", "False-Negative Rate", "Attack Recall"], ext_rows)
add_para(
    f"On WUSTL-EHMS-2020, a false-negative rate of "
    f"{EXTRA['WUSTL-EHMS-2020']['false_negative_rate']:.3f} means the model misses roughly "
    f"{EXTRA['WUSTL-EHMS-2020']['false_negative_rate']*100:.0f}% of genuine attacks at the default "
    "threshold despite 93.46% overall accuracy — in a deployed IoMT monitoring context this would "
    "translate directly into undetected intrusion attempts, and accuracy alone would obscure this."
)

add_heading("4.6a. Per-Attack-Class Recall (ECU-IoHT)", level=2)
add_para(
    "A single pooled recall figure (Table 7) can hide large differences between attack subtypes. "
    "ECU-IoHT's raw capture labels each record with a specific attack subtype in addition to the "
    "binary Normal/Attack label, so Table 7a reports recall separately for each subtype on the "
    "held-out test partition. WUSTL-EHMS-2020 and DSICU do not carry an equivalent attack-subtype "
    "field in the data available to this study (WUSTL-EHMS-2020's provided file has only the binary "
    "label; DSICU's raw file was unavailable, per Section 5.5), so this breakdown is ECU-IoHT-only."
)
add_table_caption("Table 7a. Per-attack-subtype recall for the final hybrid model on ECU-IoHT (test partition).")
pa_rows = []
for r in PER_ATTACK["per_attack_type"]:
    pa_rows.append([r["attack_type"], str(r["n_test_samples"]), r["metric"].split(" (")[0].capitalize(),
                     f"{r['value']:.3f}"])
add_table(["Attack Subtype", "N (test)", "Metric", "Value"], pa_rows)
_dos_recall = next(r["value"] for r in PER_ATTACK["per_attack_type"] if r["attack_type"] == "DoS Attack")
_arp_recall = next(r["value"] for r in PER_ATTACK["per_attack_type"] if r["attack_type"] == "ARP Spoofing")
add_para(
    f"Recall is not uniform across attack subtypes: ARP Spoofing and Smurf Attack are both detected "
    f"perfectly (recall = 1.000), Nmap Port Scan is detected at 0.945, but DoS Attack — the rarest "
    f"subtype in the test partition at only {next(r['n_test_samples'] for r in PER_ATTACK['per_attack_type'] if r['attack_type']=='DoS Attack')} records — is detected only "
    f"{_dos_recall:.3f} of the time, more than half missed. The pooled "
    f"{EXTRA['ECU-IoHT']['per_class']['attack']['recall']:.4f} attack recall reported in Table 7 is "
    "therefore driven almost entirely by the numerically dominant "
    "Smurf Attack subtype and does not represent uniform detection performance across attack types; a "
    "deployment relying on this model should not assume DoS-style attacks are detected at the same "
    "rate as the headline recall figure implies."
)

add_heading("4.7. Same-Split Classical Baselines", level=2)
add_para(
    "To test whether the hybrid architecture outperforms substantially simpler models under the "
    "identical split-before-fit preprocessing and train/test partition, we trained four classical "
    "baselines — logistic regression, random forest, histogram-based gradient boosting, and a small "
    "multilayer perceptron (MLP) — on the same preprocessed features for each dataset, using default "
    "or lightly tuned scikit-learn hyperparameters (Table 8)."
)
add_table_caption("Table 8. Same-split classical baselines vs. the proposed hybrid model. "
                   "The highest accuracy in each dataset's group of rows is shown in bold.")
base_rows = []
group_bounds = []  # (start_row_idx, end_row_idx_inclusive, accuracy_col=2) per dataset, into base_rows
for name in ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]:
    group_start = len(base_rows)
    first_in_group = True
    for mname, m in BASE[name].items():
        base_rows.append([name if first_in_group else "", mname, f"{m['accuracy']*100:.2f}%",
                           f"{m['balanced_accuracy']*100:.2f}%",
                           f"{m['precision']:.3f}", f"{m['recall']:.3f}", f"{m['f1']:.3f}"])
        first_in_group = False
    d = R[name]
    base_rows.append(["", "Hybrid CNN-LSTM-GRU-Attention (this work)", f"{d['accuracy']*100:.2f}%",
                       f"{d['balanced_accuracy']*100:.2f}%", f"{d['precision']:.3f}", f"{d['recall']:.3f}",
                       f"{d['f1']:.3f}"])
    group_bounds.append((group_start, len(base_rows) - 1))

base_bold = set()
for start, end in group_bounds:
    accs = [float(base_rows[ri][2].rstrip("%")) for ri in range(start, end + 1)]
    best_acc = max(accs)
    for ri, acc in zip(range(start, end + 1), accs):
        if abs(acc - best_acc) < 1e-9:  # bold every row tied for the group's best (e.g. DSICU's 100% tie)
            base_bold.add((ri, 2))
add_table(["Dataset", "Model", "Accuracy", "Balanced Acc.", "Precision", "Recall", "F1"], base_rows,
          bold_cells=base_bold)
add_para(
    "On ECU-IoHT, random forest (99.17% accuracy, F1 = 0.995) and histogram gradient boosting "
    "(98.63%, F1 = 0.991) both matched or exceeded the hybrid model (98.31%, F1 = 0.989). On "
    "WUSTL-EHMS-2020, histogram gradient boosting reached 97.26% accuracy and F1 = 0.881 — "
    "substantially higher than the hybrid model's 93.46% accuracy and F1 = 0.679 — with markedly "
    "better recall (0.809 vs. 0.552). On DSICU, all four classical baselines also reached 100% "
    "accuracy on the same split, matching the hybrid model exactly. We report this directly: on two "
    "of three benchmarks, a classical ensemble method is a stronger choice than the proposed hybrid "
    "deep architecture under this evaluation protocol, and on the third neither approach is "
    "distinguishable because the task is close to trivially separable on this split. Because "
    "gradient boosting is the practical winner on WUSTL-EHMS-2020, we computed the same "
    "probability-based metrics for it as for the hybrid model rather than reporting accuracy/F1 "
    "alone: ROC-AUC = "
    f"{BASE_EXTRA['WUSTL-EHMS-2020']['Gradient Boosting (Hist)']['roc_auc']:.3f}, PR-AUC = "
    f"{BASE_EXTRA['WUSTL-EHMS-2020']['Gradient Boosting (Hist)']['pr_auc']:.3f}, specificity = "
    f"{BASE_EXTRA['WUSTL-EHMS-2020']['Gradient Boosting (Hist)']['specificity']:.3f}, and a "
    "false-negative rate of "
    f"{BASE_EXTRA['WUSTL-EHMS-2020']['Gradient Boosting (Hist)']['false_negative_rate']:.3f}, "
    "compared with the hybrid model's ROC-AUC = "
    f"{EXTRA['WUSTL-EHMS-2020']['roc_auc']:.3f}, PR-AUC = {EXTRA['WUSTL-EHMS-2020']['pr_auc']:.3f}, and "
    f"false-negative rate = {EXTRA['WUSTL-EHMS-2020']['false_negative_rate']:.3f}. Gradient boosting is "
    "therefore ahead of the hybrid model on every one of these metrics on this benchmark, not only "
    "on accuracy and F1."
)

add_heading("4.7a. Multi-Seed Robustness of the Classical Baselines", level=2)
add_para(
    "Table 8's single-seed classical-baseline comparison could in principle be a lucky (or unlucky) "
    "draw of the ensemble methods' own internal randomness (bootstrap sampling for random forest; "
    "tree-growth order and subsampling for histogram gradient boosting). To check this, we retrained "
    f"both classical baselines at {len(MULTISEED_BASE['ECU-IoHT']['seeds'])} seeds "
    f"({', '.join(str(s) for s in MULTISEED_BASE['ECU-IoHT']['seeds'])}) on the identical "
    "split-before-fit train/test partition used everywhere else in this study — only the classifier's "
    "own internal randomness varies across seeds, not the data partition itself (Table 8a)."
)
ms_rows = []
for name in ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]:
    d = MULTISEED_BASE[name]
    for mname in ["Random Forest", "Gradient Boosting (Hist)"]:
        m = d[mname]
        ms_rows.append([
            name, mname,
            f"{m['mean']['accuracy']*100:.2f}% ± {m['std']['accuracy']*100:.2f}%",
            f"{m['mean']['f1']:.3f} ± {m['std']['f1']:.3f}",
            f"{m['mean']['recall']:.3f} ± {m['std']['recall']:.3f}",
        ])
add_table_caption(f"Table 8a. Multi-seed ({len(MULTISEED_BASE['ECU-IoHT']['seeds'])}-seed) classical-baseline "
                   "robustness check on the identical split-before-fit partition (mean ± std. dev.).")
add_table(["Dataset", "Model", "Accuracy", "F1", "Recall"], ms_rows)
add_para(
    "The multi-seed means are within a fraction of a percentage point of the single-seed Table 8 "
    "figures on every dataset, and standard deviations are small "
    f"(≤{max(d[m]['std']['accuracy'] for d in [MULTISEED_BASE[n] for n in MULTISEED_BASE] for m in ['Random Forest','Gradient Boosting (Hist)'])*100:.2f} "
    "percentage points on accuracy across all six dataset/model combinations), so the classical-"
    "baseline advantage over the hybrid model on ECU-IoHT and WUSTL-EHMS-2020 (Section 4.7) and the "
    "DSICU ceiling effect (Section 5.5) are both robust to the classifier's own random initialization, "
    "not artifacts of a single lucky seed."
)

add_heading("4.8. Exploratory Architecture Ablation", level=2)
add_para(
    "To screen the contribution of each architectural component, we compared CNN-only, "
    "CNN+LSTM, CNN+GRU, CNN+LSTM+GRU (no attention), the full hybrid (with attention), and the full "
    "hybrid with default, non-Lionfish-tuned hyperparameters (Table 9), using the same "
    "quick-evaluation protocol as the Lionfish search itself (3 epochs, batch size 1024, on an "
    "80/20 split of the training partition, a single run per variant) for a fast, budget-matched "
    "comparison rather than a full retraining of every variant. We call this an exploratory "
    "screen, not a definitive isolation of each component's contribution: a single 3-epoch run per "
    "variant carries meaningful run-to-run variance (Section 5.5), and a component that looks "
    "unhelpful here could still matter with a longer training budget or repeated runs."
)
add_table_caption("Table 9. Architecture ablation (quick-evaluation validation accuracy).")
abl_label = {"cnn_only": "CNN only", "cnn_lstm": "CNN + LSTM", "cnn_gru": "CNN + GRU",
             "cnn_lstm_gru": "CNN + LSTM + GRU (no attention)", "full": "Full hybrid (with attention)",
             "full_default": "Full hybrid, default hyperparameters"}
abl_rows = []
for name in ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]:
    first_in_group = True
    for variant in ["cnn_only", "cnn_lstm", "cnn_gru", "cnn_lstm_gru", "full", "full_default"]:
        v = ABL[name][variant]
        abl_rows.append([name if first_in_group else "", abl_label[variant], f"{v['val_acc']:.4f}",
                          f"{v['n_params']:,}"])
        first_in_group = False
add_table(["Dataset", "Variant", "Val. Accuracy", "Parameters"], abl_rows)
add_para(
    "On ECU-IoHT, each added component improved quick-evaluation accuracy monotonically (CNN-only "
    "0.792 → +LSTM 0.823 → +GRU 0.888 → +LSTM+GRU 0.907 → full hybrid with attention 0.930), and "
    "Lionfish-tuned hyperparameters mattered substantially more than any single layer (full hybrid "
    "0.930 vs. the same architecture with default hyperparameters, 0.789). On WUSTL-EHMS-2020 the "
    "pattern is noisier and smaller in magnitude: CNN+LSTM+GRU without attention (0.884) slightly "
    "outperformed the full model with attention (0.879), suggesting attention adds little or "
    "possibly mildly hurts on this benchmark at this budget. On DSICU, CNN+LSTM alone (0.996) and "
    "the full hybrid (0.988) both performed well, while CNN+LSTM+GRU without attention was "
    "unstable (0.833) at this reduced 3-epoch budget — a reminder that single-run, low-epoch "
    "ablation screens carry meaningful run-to-run variance and are reported here as a fast "
    "component screen, not a precision estimate of each component's true contribution."
)

add_heading("4.9. Lionfish vs. Random Search", level=2)
add_para(
    "To test whether the Lionfish metaheuristic outperforms unguided sampling, we ran a plain random "
    "search over the same five-dimensional hyperparameter space with the same evaluation budget (42 "
    "candidate evaluations: 6 initial + 6 iterations × 6) and the same quick-evaluation protocol, "
    "using an independently seeded random stream (Table 10). This first pass is a single run per "
    "optimizer per dataset; it is sufficient to show Lionfish does not have a clear, consistent "
    "advantage at this budget, but not sufficient to characterize the full distribution of either "
    "method's outcomes."
)
add_table_caption("Table 10. Lionfish vs. random search at a matched 42-candidate evaluation budget (single run).")
ls_rows = []
for name in ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]:
    lf_acc = R[name]["lionfish_best_val_acc_quick"]
    rs_acc = RANDS[name]["best_val_acc"]
    ls_rows.append([name, f"{lf_acc:.4f}", f"{rs_acc:.4f}", f"{lf_acc-rs_acc:+.4f}"])
add_table(["Dataset", "Lionfish Best Val. Acc.", "Random Search Best Val. Acc.", "Difference (Lionfish − Random)"], ls_rows)
add_para(
    "Lionfish did not outperform random search at this matched budget on any dataset: the two were "
    "effectively tied on ECU-IoHT (+0.0001) and DSICU (0.0000, both saturating at a perfect "
    "quick-validation score), and random search was actually better on WUSTL-EHMS-2020 (−0.0101, "
    "i.e., random search reached 0.915 vs. Lionfish's 0.905)."
)
add_para(
    "Because a single run per method cannot support a statistical claim either way, we followed up "
    "with a three-seed (42, 43, 44), budget-matched comparison on ECU-IoHT and WUSTL-EHMS-2020 (DSICU "
    "was excluded as already saturated at a perfect score for every method), using an expanded "
    "six-dimensional search space that adds the learning rate (log-uniform over "
    "[1×10⁻⁴, 1×10⁻²]) to the original five architecture hyperparameters, directly addressing the "
    "possibility that a narrow, low-dimensional space simply favors random sampling. Each of the six "
    "(dataset, seed) combinations was run to completion at the same 42-candidate budget, and the "
    "paired best-validation-accuracy values across seeds were compared with a paired t-test and a "
    "Wilcoxon signed-rank test (Table 10a)."
)
add_table_caption(
    "Table 10a. Lionfish vs. random search, three-seed comparison on a six-dimensional search space "
    "(architecture hyperparameters + learning rate), 42-candidate budget per run."
)
ms_rows = []
for name in ["ECU-IoHT", "WUSTL-EHMS-2020"]:
    s = MULTISEED[name]["summary"]
    lfo_vals = ", ".join(f"{r['best_val_acc']:.4f}" for r in MULTISEED[name]["lfo"])
    rs_vals = ", ".join(f"{r['best_val_acc']:.4f}" for r in MULTISEED[name]["random_search"])
    ms_rows.append([name, lfo_vals, rs_vals,
                     f"{s['lfo_mean']:.4f} ± {s['lfo_std']:.4f}",
                     f"{s['rs_mean']:.4f} ± {s['rs_std']:.4f}",
                     f"{s['paired_t_p']:.3f}", f"{s['wilcoxon_p']:.3f}"])
add_table(["Dataset", "Lionfish (seeds 42/43/44)", "Random Search (seeds 42/43/44)",
           "Lionfish Mean ± SD", "Random Search Mean ± SD", "Paired t-test p", "Wilcoxon p"], ms_rows)
add_para(
    "On ECU-IoHT, random search won on all three seeds (mean 0.9312 ± 0.0009 vs. Lionfish's 0.9276 "
    f"± 0.0026), though the gap is not statistically significant at this sample size "
    f"(paired t-test p = {MULTISEED['ECU-IoHT']['summary']['paired_t_p']:.3f}, Wilcoxon p = "
    f"{MULTISEED['ECU-IoHT']['summary']['wilcoxon_p']:.3f}). On WUSTL-EHMS-2020 the two methods were "
    "essentially tied (Lionfish 0.9234 ± 0.0007 vs. random search 0.9227 ± 0.0004, "
    f"p = {MULTISEED['WUSTL-EHMS-2020']['summary']['paired_t_p']:.3f}). We note explicitly that n = 3 "
    "paired seeds is a small sample: the Wilcoxon signed-rank test has a p-value floor of 0.25 at "
    "n = 3 regardless of effect size, so neither test result should be read as strong statistical "
    "evidence in either direction — only as a description of the observed seeds. Taken together with "
    "the single-run result above and the expanded search space, this three-seed follow-up finds no "
    "evidence that Lionfish provides a genuine optimization advantage over random search at this "
    "evaluation budget on either benchmark tested; if anything, the point estimates on ECU-IoHT "
    "trend in random search's favor. We report this directly rather than retaining an unsupported "
    "superiority claim for the optimizer that gives this framework its name."
)

add_heading("4.10. Sensitivity Analysis: Alternative Splits", level=2)
add_para(
    "Section 3.2 noted that split-before-fit preprocessing does not, by itself, prevent related "
    "records (e.g., from the same flow, device, or narrow time window) from appearing in both the "
    "training and test partitions under simple random stratified splitting. To test this directly, "
    "we replaced the main experiment's random split with a harder, more realistic split for each "
    "dataset: a temporal split for ECU-IoHT (train = earliest 70% of records by capture time, test = "
    "latest 30%), a temporal-style split for WUSTL-EHMS-2020 (ordered by packet sequence number), and "
    "a flow-grouped split for DSICU (whole (source port, destination port) groups assigned to either "
    "partition, so no flow's records appear in both)."
)
add_para(
    "We report two versions of this analysis. Version 1 (initial pass) reused the same "
    "Lionfish-optimized hyperparameters found under the main random split, kept the split-defining "
    "field (Time, Packet_num, or the port pair) as a model input feature, and retrained at a reduced "
    "budget (up to 20 epochs, early stopping patience 5). On review, all three choices are "
    "methodologically weaker than they should be: reusing hyperparameters selected under the main "
    "split is not fully independent of the alternative split's test partition, since records now in "
    "an alternative split's test set may have contributed to the main split's training partition used "
    "for that hyperparameter search; using the same field both to define the split and as a predictor "
    "lets the model potentially exploit a coarse row-order or flow proxy rather than genuine signal; "
    "and a smaller search/training budget than the main experiment means any resulting gap cannot be "
    "attributed to split difficulty alone. Version 2 (revised) fixes all three issues: hyperparameters "
    "are instead found by an independent random search restricted to each alternative split's own "
    "training partition only, using the exact same 42-candidate evaluation budget and quick-evaluation "
    "protocol as the main Lionfish search and its random-search control (Section 4.9); the "
    "split-defining field is excluded from the model's input features in every alternative-split "
    "experiment, used solely to sort or group records into partitions; and the final model is trained "
    "for up to 80 epochs with early-stopping patience 8, identical to the main experiment's training "
    "budget (Section 3.5). Version 2 matches the main experiment in candidate-evaluation and "
    "final-training budget, but uses independently run random search rather than Lionfish for the "
    "alternative-split hyperparameters; Section 4.9 found no single-run evidence that Lionfish is "
    "superior to random search at this budget, so this substitution is unlikely by itself to explain "
    "a large gap, though it has not been tested by running Lionfish itself within each alternative "
    "split. With the search and training budgets matched, any remaining gap between the main split "
    "and version 2's alternative-split result is attributable to the split and/or the optimizer "
    "substitution, rather than to a smaller search or training allowance."
)
add_para(
    "As a separate check, we also re-ran the MAIN experiment (random split, full 40-epoch retraining "
    "budget, the same Lionfish-selected hyperparameters) with the identifier-like field excluded from "
    "the feature set, to isolate its contribution independent of any split choice. Removing Time left "
    f"ECU-IoHT accuracy essentially unchanged (98.31% → {NOID['ECU-IoHT']['accuracy']*100:.2f}%, "
    f"F1 = {NOID['ECU-IoHT']['f1']:.3f}), and removing the port fields left DSICU unchanged "
    f"(100.00% → {NOID['DSICU']['accuracy']*100:.2f}%, F1 = {NOID['DSICU']['f1']:.3f}) — in both "
    "cases the field was not doing meaningful work on the main split either. Removing Packet_num, by "
    f"contrast, reduced WUSTL-EHMS-2020 accuracy from 93.46% to {NOID['WUSTL-EHMS-2020']['accuracy']*100:.2f}% "
    f"and F1 from 0.679 to {NOID['WUSTL-EHMS-2020']['f1']:.3f}, indicating that Packet_num carried "
    "real, non-trivial signal on this benchmark rather than acting purely as a row-order shortcut; we "
    "report this as a genuine, if modest, dependence on a field a deployed system may not always have "
    "in this exact form, rather than as evidence of leakage."
)
add_table_caption("Table 11. Sensitivity analysis: performance under alternative (harder) splits vs. the main random split.")
SPLIT_TYPE_LABEL = {"ECU-IoHT": "temporal", "WUSTL-EHMS-2020": "temporal (Packet_num)",
                     "DSICU": "group (ports)"}
sens_rows = []
for name in ["ECU-IoHT", "WUSTL-EHMS-2020", "DSICU"]:
    s = SENS[name]
    s2 = SENS2[name]
    d = R[name]
    sens_rows.append([name, SPLIT_TYPE_LABEL[name], f"{d['accuracy']*100:.2f}%",
                       f"{s['accuracy']*100:.2f}%", f"{s2['accuracy']*100:.2f}%",
                       f"{d['recall']:.3f}", f"{s['recall']:.3f}", f"{s2['recall']:.3f}"])
add_table(["Dataset", "Alt. Split Type", "Main Split Acc.", "Alt-Split Acc. (v1: reused params, IDs kept)",
           "Alt-Split Acc. (v2: independent search, IDs removed)", "Main Recall",
           "Alt-Split Recall (v1)", "Alt-Split Recall (v2)"], sens_rows)
add_para(
    f"On ECU-IoHT, accuracy under the temporal split rose substantially from version 1 to version 2 "
    f"({SENS['ECU-IoHT']['accuracy']*100:.1f}% → {SENS2['ECU-IoHT']['accuracy']*100:.1f}%), with "
    f"recall staying high throughout ({SENS['ECU-IoHT']['recall']:.3f} → {SENS2['ECU-IoHT']['recall']:.3f}). "
    "Because version 2 is now budget-matched to the main experiment in search size and training "
    "length, this increase is attributable specifically to removing the hyperparameter-reuse and "
    "identifier-feature confounds, not to a larger search or training allowance. "
    f"{SENS2['ECU-IoHT']['accuracy']*100:.1f}% still remains well below the main split's "
    "98.27% ± 0.08%, so — with the hyperparameter-reuse and identifier-feature confounds removed and "
    "the budget matched — the remaining difference of roughly 12-13 percentage points is consistent "
    "with a temporal generalization gap, smaller than version 1 suggested but real, although the use "
    "of random search rather than Lionfish in the alternative split remains a secondary methodological "
    "difference. On WUSTL-EHMS-2020, recall stayed low under the temporal "
    f"split at matched budget ({SENS2['WUSTL-EHMS-2020']['recall']:.3f}, comparable to version 1's "
    f"{SENS['WUSTL-EHMS-2020']['recall']:.3f}), and accuracy was, if anything, slightly lower under "
    f"the matched-budget version ({SENS2['WUSTL-EHMS-2020']['accuracy']*100:.1f}% vs. "
    f"{SENS['WUSTL-EHMS-2020']['accuracy']*100:.1f}%), consistent with the longer training budget "
    "fitting the majority class more aggressively on this small alternative-split training partition "
    "(11,422 records) without recovering minority-class recall. Either way, low recall under a "
    "temporal split is a consistent finding in the evaluated alternative-split analysis, regardless of "
    "hyperparameter source or training budget — though, with a single alternative split per dataset, "
    "we stop short of calling it reproducible in the stronger sense of holding across multiple "
    "independent alternative splits. On DSICU, accuracy remained at or effectively at 100% in both "
    "versions "
    f"({SENS['DSICU']['accuracy']*100:.2f}% vs. {SENS2['DSICU']['accuracy']*100:.2f}%), including "
    "version 2 with the port fields completely excluded from the feature set, hyperparameters "
    "searched independently inside the group split's own training partition, and a training budget "
    "matched to the main experiment — a stringent test within the available data against a feature-, "
    "hyperparameter-, or budget-driven artifact, and DSICU still passes it. This is consistent with "
    "capture-specific correlation and is not explained by the tested preprocessing, identifier-"
    "feature, or split-design artifacts. We stop short of calling this \"flow-independent\": a (source "
    "port, destination port) pair is a coarse proxy for a true connection or session identifier, not a "
    "guarantee that every related record was kept together, so this result should be read as "
    "robustness to one reasonable grouping choice, not a proof of flow-level independence."
)

add_heading("4.11. Class-Imbalance Mitigation for WUSTL-EHMS-2020", level=2)
add_para(
    "Section 4.6 showed the main WUSTL-EHMS-2020 model misses roughly "
    f"{EXTRA['WUSTL-EHMS-2020']['false_negative_rate']*100:.0f}% of genuine attacks at the default "
    "threshold, and Section 4.7 showed gradient boosting reaches materially higher recall (0.809) on "
    "the identical split. To test whether this gap is addressable within the hybrid architecture "
    "itself, rather than only by switching models, we retrained the final model with two "
    "class-imbalance-aware loss functions in place of plain binary cross-entropy: class-weighted "
    "binary cross-entropy (weighting the attack class by the inverse of its training-set frequency) "
    "and focal loss (γ = 2.0, α = 0.25). Both variants used the identical training protocol as the "
    "main experiment (up to 80 epochs, early stopping on training-loss plateau with patience 8, "
    "trained on the same 85% of the training partition), holding out the remaining 15% solely to "
    "select an F1-optimal decision threshold via the precision–recall curve — never touched during "
    "training or used to tune the loss itself — before evaluating once on the untouched test "
    "partition."
)
add_table_caption("Table 11a. Class-imbalance mitigation for WUSTL-EHMS-2020: test-set results at each variant's validation-selected threshold, vs. the unweighted baseline.")
rf = RECALL_FIX_V2["variants"]
cw = rf["class_weighted_bce"]
fl = rf["focal_loss"]
cw_t = cw["test_at_validation_threshold"]
fl_t = fl["test_at_validation_threshold"]
add_table(
    ["Variant", "Threshold", "Precision", "Recall", "F1", "ROC-AUC", "PR-AUC"],
    [
        ["Baseline (unweighted BCE, default 0.5)", "0.500", f"{R['WUSTL-EHMS-2020']['precision']:.3f}",
         f"{R['WUSTL-EHMS-2020']['recall']:.3f}", f"{R['WUSTL-EHMS-2020']['f1']:.3f}",
         f"{EXTRA['WUSTL-EHMS-2020']['roc_auc']:.3f}", f"{EXTRA['WUSTL-EHMS-2020']['pr_auc']:.3f}"],
        ["Class-weighted BCE (validation-selected)", f"{cw['validation_selected_threshold']:.3f}",
         f"{cw_t['precision']:.3f}", f"{cw_t['recall']:.3f}", f"{cw_t['f1']:.3f}",
         f"{cw['roc_auc_test']:.3f}", f"{cw['pr_auc_test']:.3f}"],
        ["Focal loss (validation-selected)", f"{fl['validation_selected_threshold']:.3f}",
         f"{fl_t['precision']:.3f}", f"{fl_t['recall']:.3f}", f"{fl_t['f1']:.3f}",
         f"{fl['roc_auc_test']:.3f}", f"{fl['pr_auc_test']:.3f}"],
    ],
)
add_para(
    f"Class-weighted BCE gives a genuine Pareto improvement over the baseline: recall rises from "
    f"{R['WUSTL-EHMS-2020']['recall']:.3f} to {cw_t['recall']:.3f} while F1 does not fall "
    f"(F1 = {cw_t['f1']:.3f} vs. the baseline's {R['WUSTL-EHMS-2020']['f1']:.3f}), and its ROC-AUC "
    f"({cw['roc_auc_test']:.3f}) exceeds the baseline's ({EXTRA['WUSTL-EHMS-2020']['roc_auc']:.3f}) as "
    "well, at a threshold selected on a held-out validation slice rather than cherry-picked against "
    "the test set. Focal loss, by contrast, did not help: its validation-selected threshold reaches "
    f"lower recall ({fl_t['recall']:.3f}) and a lower ROC-AUC ({fl['roc_auc_test']:.3f}, actually below "
    f"the baseline's {EXTRA['WUSTL-EHMS-2020']['roc_auc']:.3f}) than either the baseline or the "
    "class-weighted variant. Class-weighted BCE's improved recall (0.591) still falls well short of "
    "gradient boosting's 0.809 on the identical split (Section 4.7), so this is a genuine but partial "
    "fix: it narrows, without closing, the gap that motivates preferring the classical baseline on "
    "this benchmark, and we report it as an incremental, honestly bounded improvement rather than a "
    "resolution of the recall gap."
)

add_heading("4.12. True Sliding-Window Sequences for ECU-IoHT", level=2)
add_para(
    "Section 3.4 and Section 5.5 note that the recurrent layers in the main architecture see a "
    "reshaped feature vector — each scalar feature treated as one pseudo-timestep with a single "
    "channel — rather than a genuine sequence of ordered packets, and that this limits any claim of "
    "learned temporal dynamics. To test directly whether giving the model real multi-packet "
    "sequences changes this, we built sliding windows of T = 10 consecutive packets (each carrying "
    "its own feature vector, in capture-time order) for ECU-IoHT under the same temporal split used "
    "in Section 4.10, with each window labeled by its last packet's Attack/Normal status; the model "
    "then receives genuine shape (T, n_features) input, and the Conv1D/LSTM/GRU/attention stack "
    "operates over true packet order for the first time in this study."
)
add_para(
    "An initial attempt reused the main experiment's Lionfish-selected hyperparameters and kept the "
    "raw capture-time field as an input feature; it collapsed to predicting the majority class "
    "(59.1% accuracy, recall 0.980 but precision 0.584), indistinguishable from the already-known "
    "failure mode of the earlier, less rigorous version-1 temporal-split sensitivity pass "
    "(Section 4.10). This comparison was confounded on two counts also identified in Section 4.10: "
    "hyperparameters tuned for a different (random) split, and an absolute-timestamp feature whose "
    "distribution differs systematically between the early-time training partition and the late-time "
    "test partition. We therefore reran the sliding-window experiment matching every design choice of "
    "Section 4.10's fair, budget-matched version-2 temporal-split baseline: the capture-time field "
    "dropped from the feature set entirely, and the same independently-searched hyperparameters used "
    "for that 85.8%-accuracy baseline (Table 11), so the sliding-window result differs from that "
    "baseline in exactly one respect — genuine multi-packet sequences in place of the feature-axis "
    "pseudo-sequence — for a fair, apples-to-apples test of the sequencing hypothesis."
)
add_table_caption("Table 11b. True sliding-window sequences (T = 10) vs. the fair flat-feature baseline, ECU-IoHT temporal split, identical hyperparameters and features.")
sw = SLIDING_WINDOW_V2
sw_base = sw["fair_comparison_baseline_sensitivity_v2"]
add_table(
    ["Representation", "Accuracy", "Precision", "Recall", "F1", "ROC-AUC"],
    [
        ["Flat feature-axis-as-sequence (Section 4.10, v2)", f"{sw_base['accuracy']*100:.2f}%",
         f"{sw_base['precision']:.3f}", f"{sw_base['recall']:.3f}", f"{sw_base['f1']:.3f}",
         f"{SENS2['ECU-IoHT']['roc_auc']:.3f}"],
        ["True sliding-window sequence (T = 10)", f"{sw['accuracy']*100:.2f}%",
         f"{sw['precision']:.3f}", f"{sw['recall']:.3f}", f"{sw['f1']:.3f}", f"{sw['roc_auc']:.3f}"],
    ],
)
add_para(
    f"With every other confound matched, true sliding-window sequences underperformed the simpler "
    f"flat feature-axis representation on this benchmark: accuracy fell from {sw_base['accuracy']*100:.2f}% "
    f"to {sw['accuracy']*100:.2f}%, and F1 from {sw_base['f1']:.3f} to {sw['f1']:.3f}, driven by a "
    f"large drop in precision ({sw_base['precision']:.3f} to {sw['precision']:.3f}) alongside a "
    f"smaller recall change ({sw_base['recall']:.3f} to {sw['recall']:.3f}) — the windowed model "
    "leans further toward predicting the majority Attack class than the already imbalance-prone flat "
    "baseline. We read this as a genuine, if negative, finding for this specific architecture and "
    "windowing choice, not as evidence that temporal sequencing cannot help ECU-IoHT in general: a "
    "fixed window length of 10 packets, no exploration of alternative window lengths or "
    "stride/labeling schemes, and hyperparameters selected for the flat representation rather than "
    "re-searched for the windowed one are all plausible reasons a genuinely informative sequence "
    "representation could still under-deliver here. What this result does support is the narrower "
    "claim already made in Section 3.4 and Section 5.5: this study's specific architecture and its "
    "existing hyperparameters were not designed around, and do not obviously benefit from, a genuine "
    "temporal-sequence input, and simply supplying one is not sufficient by itself to improve results."
)

add_heading("4.13. Reseeded-Split Significance Testing (Nadeau-Bengio Corrected)", level=2)
add_para(
    "Section 4.3's paired significance test compares the hybrid model against gradient boosting "
    "across the 5 folds of a single stratified cross-validation split. Those 5 folds share most of "
    "their data with each other by construction (each fold's training data overlaps heavily with "
    "every other fold's), so treating them as 5 independent paired observations understates the true "
    "variance and can make a naive paired t-test overconfident. To address this directly, we "
    "additionally ran the comparison across "
    f"{NB_TEST['ECU-IoHT']['n_repeats']} independently reseeded 70/30 train/test splits per dataset "
    f"(seeds {', '.join(str(s) for s in NB_TEST['ECU-IoHT']['seeds'])} — a different random partition "
    "of the data each time, not merely a different weight-initialization seed on the same partition), "
    "training the hybrid model and histogram gradient boosting once per split with the same "
    "Lionfish-selected hyperparameters used throughout, and applying the Nadeau and Bengio "
    f"(2003) correction, which accounts for the residual data overlap across repeats "
    "(Table 11c). This is a reduced-N version of the fully independent 10-reseed design the "
    "manuscript's evaluation checklist calls for; we document the reduction explicitly rather than "
    "silently substituting a smaller experiment, due to this study's compute budget (the hybrid model "
    "alone required 45–65 minutes of CPU-only training per reseed on the larger benchmark)."
)
add_table_caption("Table 11c. Nadeau-Bengio corrected resampled paired t-test across "
                   f"{NB_TEST['ECU-IoHT']['n_repeats']} independently reseeded train/test splits: "
                   "hybrid model vs. histogram gradient boosting.")
nb_rows = []
for name in ["ECU-IoHT", "WUSTL-EHMS-2020"]:
    d = NB_TEST[name]
    nb = d["nadeau_bengio_test_hgb_minus_hybrid"]
    per_seed_accs = ", ".join(f"{r['hybrid_acc']*100:.2f}%" for r in d["per_seed"])
    nb_rows.append([
        name, per_seed_accs, f"{d['hybrid_mean_acc']*100:.2f}%", f"{d['hgb_mean_acc']*100:.2f}%",
        f"{nb['t_stat']:.3f}", str(nb["df"]), f"{nb['p_value']:.4f}",
    ])
add_table(
    ["Dataset", "Hybrid Accuracy per Reseed", "Hybrid Mean", "HistGB Mean", "NB t-stat", "df", "NB p-value"],
    nb_rows,
    bold_cells={(i, 6) for i, name in enumerate(["ECU-IoHT", "WUSTL-EHMS-2020"])
                if NB_TEST[name]["nadeau_bengio_test_hgb_minus_hybrid"]["p_value"] < 0.05}
)
_ecu_nb = NB_TEST["ECU-IoHT"]["nadeau_bengio_test_hgb_minus_hybrid"]
_wustl_nb = NB_TEST["WUSTL-EHMS-2020"]["nadeau_bengio_test_hgb_minus_hybrid"]
add_para(
    f"The corrected test changes the picture for ECU-IoHT specifically, and we report this directly "
    f"rather than downplaying it: across reseeded splits, the hybrid model's accuracy varies "
    f"considerably ({min(r['hybrid_acc'] for r in NB_TEST['ECU-IoHT']['per_seed'])*100:.2f}% to "
    f"{max(r['hybrid_acc'] for r in NB_TEST['ECU-IoHT']['per_seed'])*100:.2f}%) while gradient "
    f"boosting stays tightly clustered "
    f"({min(r['hgb_acc'] for r in NB_TEST['ECU-IoHT']['per_seed'])*100:.2f}%–"
    f"{max(r['hgb_acc'] for r in NB_TEST['ECU-IoHT']['per_seed'])*100:.2f}%), and at "
    f"n = {NB_TEST['ECU-IoHT']['n_repeats']} reseeded splits the Nadeau-Bengio corrected test does "
    f"not reach significance (p = {_ecu_nb['p_value']:.3f}) despite gradient boosting winning on "
    f"every individual reseed. This does not overturn the Section 4.7 finding that gradient boosting "
    "matched or exceeded the hybrid model on every reseed tested — it does — but it does mean the "
    "strength of that advantage, and its statistical robustness, is more properly stated as "
    "\"consistent but not yet established as statistically significant at this reseed count\" on "
    "ECU-IoHT specifically, in contrast to Section 4.3's uncorrected, fold-based test, which "
    "overstated confidence in exactly the way this section's more conservative design is meant to "
    f"guard against. On WUSTL-EHMS-2020, by contrast, the corrected test remains significant "
    f"(p = {_wustl_nb['p_value']:.3f}) at the same n = {NB_TEST['WUSTL-EHMS-2020']['n_repeats']}, "
    "consistent with Section 4.3's original finding and with the much larger, more consistent margin "
    "gradient boosting holds on that benchmark. We treat the ECU-IoHT result as an open question "
    "requiring the full 10-reseed design (or more) to resolve with confidence, not as a settled "
    "finding in either direction, and revise our claims about it accordingly relative to earlier "
    "sections of this manuscript."
)

add_heading("4.14. Inference Cost and Deployment Feasibility", level=2)
add_para(
    "A model's accuracy on a held-out test set does not by itself say whether it is practical to "
    "deploy on IoMT-relevant hardware. Table 11d reports, for the hybrid model and the two classical "
    "baselines on ECU-IoHT and WUSTL-EHMS-2020 (CPU-only, no GPU acceleration, matching Section 3.6), "
    "the serialized model size on disk, training time for the final model, and per-sample inference "
    "latency on the full held-out test partition."
)
infcost_rows = []
for name in ["ECU-IoHT", "WUSTL-EHMS-2020"]:
    ic = INFCOST[name]
    for mkey, mlabel in [("hybrid", "Hybrid CNN-LSTM-GRU-Attention"),
                          ("random_forest", "Random Forest"), ("hist_gb", "Histogram Gradient Boosting")]:
        m = ic[mkey]
        infcost_rows.append([
            name, mlabel, f"{m['model_size_mb']:.3f}",
            f"{m['train_time_sec']:.1f}",
            f"{m['inference_ms_per_sample']:.4f}",
        ])
add_table_caption("Table 11d. Inference cost and model size, CPU-only, ECU-IoHT and WUSTL-EHMS-2020.")
add_table(["Dataset", "Model", "Model Size (MB)", "Train Time (s)", "Inference (ms/sample)"], infcost_rows)
add_para(
    f"The hybrid model's per-sample inference latency "
    f"({INFCOST['ECU-IoHT']['hybrid']['inference_ms_per_sample']:.4f} ms on ECU-IoHT, "
    f"{INFCOST['WUSTL-EHMS-2020']['hybrid']['inference_ms_per_sample']:.4f} ms on WUSTL-EHMS-2020) is "
    f"an order of magnitude slower than either classical baseline on the same hardware "
    f"(histogram gradient boosting: "
    f"{INFCOST['ECU-IoHT']['hist_gb']['inference_ms_per_sample']:.4f} ms and "
    f"{INFCOST['WUSTL-EHMS-2020']['hist_gb']['inference_ms_per_sample']:.4f} ms respectively), and "
    f"its training time ({INFCOST['ECU-IoHT']['hybrid']['train_time_sec']:.0f} s and "
    f"{INFCOST['WUSTL-EHMS-2020']['hybrid']['train_time_sec']:.0f} s) is two to three orders of "
    "magnitude longer than either classical baseline's. Combined with Section 4.7's finding that the "
    "classical baselines matched or exceeded the hybrid model's accuracy on both of these benchmarks, "
    "this is a second, independent reason — beyond predictive performance — to prefer a classical "
    "baseline for a resource-constrained IoMT deployment on this evidence: it is simultaneously "
    "cheaper to train, faster to run, and at least as accurate."
)
add_para(
    "Figure 7 plots precision-recall curves for WUSTL-EHMS-2020's Attack class, comparing the hybrid "
    "model, histogram gradient boosting, and the class-weighted-BCE variant from Section 4.11, "
    "extending Table 7's single-threshold false-negative-rate figure into the full precision/recall "
    "trade-off curve requested for this comparison."
)
add_figure(f"{FIG_DIR}/wustl_pr_curves.png",
           f"Figure 7. Precision-recall curves for WUSTL-EHMS-2020's Attack class: hybrid model "
           f"(AP={WUSTL_PR_AP['Hybrid CNN-LSTM-GRU-Attention (main experiment)']:.3f}), histogram "
           f"gradient boosting (AP={WUSTL_PR_AP['Histogram Gradient Boosting (strongest classical baseline)']:.3f}), "
           f"and the class-weighted-BCE variant "
           f"(AP={WUSTL_PR_AP['Hybrid, class-weighted BCE variant (Section 4.11)']:.3f}).",
           width_in=5.0)
add_para(
    f"Average precision confirms the pattern already visible in Table 8's accuracy/F1 comparison and "
    f"Section 4.11's threshold sweep: gradient boosting "
    f"(AP={WUSTL_PR_AP['Histogram Gradient Boosting (strongest classical baseline)']:.3f}) dominates "
    f"the hybrid model's precision-recall trade-off at essentially every operating point, and the "
    f"class-weighted-BCE variant "
    f"(AP={WUSTL_PR_AP['Hybrid, class-weighted BCE variant (Section 4.11)']:.3f}) improves only "
    f"marginally on the main experiment's hybrid model "
    f"(AP={WUSTL_PR_AP['Hybrid CNN-LSTM-GRU-Attention (main experiment)']:.3f}) — consistent with "
    "Section 4.11's own framing of the class-weighted loss as a genuine but partial fix, not a "
    "resolution of the underlying gap to gradient boosting."
)

# =======================================================================
# 5. DISCUSSION
# =======================================================================
add_heading("5. Discussion", level=1)

add_heading("5.1. Comparative Analysis", level=2)
add_para(
    "Tables 12–14 place the split-before-fit test results alongside previously published figures on "
    "each benchmark. Because the comparators were not necessarily evaluated under an equivalently "
    "strict split-before-fit protocol, these comparisons should be read as context rather than "
    "like-for-like benchmarking."
)

add_table_caption("Table 12. Comparison on WUSTL-EHMS-2020.")
wustl_rows = [
    ["Tauqeer et al. (2022)", "RF / GB / SVM", "96.90% / 96.50% / 95.85%"],
    ["Judith et al. (2023)", "PCA-MLP", "96.39%"],
    ["Shaikh et al. (2024)", "RCLNet", "99.78%"],
    ["Wu et al. (2025)", "DL + Kernel PCA", "94.29%"],
    ["Balhareth et al. (2026)", "ML-FSID-FIS", "93.00%"],
    ["Abid (2026)", "KNN/RF/SVM (hard vote)", "95.00%"],
    ["Aversano et al. (2026)", "SurIoT", "99.85%"],
    ["Abdelhaq et al. (2026)", "XGBoost-PCA + SVM", "98.04%"],
    ["Mosaiyebzadeh et al. (2025)", "DNN", "93.20%"],
    ["Krishna Kumari et al. (2026)", "MREQGAN-DSA", "99.77%"],
    ["This work (split-before-fit)", "CNN-LSTM-GRU-Attention", "93.46% (F1 = 0.679)"],
]
add_table(["Author(s)", "Methodology", "Reported Accuracy"], wustl_rows)
add_para(
    "On WUSTL-EHMS-2020, the split-before-fit result (93.46% accuracy, F1 = 0.679) sits at the lower end "
    "of the range of published figures, most of which report 94–100% accuracy without stating "
    "whether feature selection or scaling was fit before or after partitioning. The gap is most "
    "visible in recall (0.552): the minority attack class (12.5% of records) is genuinely difficult "
    "to separate from this feature set once the model is prevented from seeing test-partition "
    "statistics during preprocessing. We report this weaker, honest number deliberately, since it is "
    "more useful to practitioners than a number that cannot be reproduced under an independent "
    "split-before-fit evaluation."
)

add_table_caption("Table 13. Comparison on ECU-IoHT.")
ecu_rows = [
    ["Vijayakumar et al. (2023)", "DNN", "99.85%"],
    ["Areia et al. (2024)", "RF / DT", "99.00%"],
    ["Algethami & Alshamrani (2024)", "HANN-BLSTM", "99.85%"],
    ["Alohali et al. (2025)", "EloHTSCD-SEGO", "99.33%"],
    ["Mosaiyebzadeh et al. (2025)", "CNN", "95.48%"],
    ["Alharbi & Khan (2025)", "CNN-LSTM", "98.00%"],
    ["This work (split-before-fit)", "CNN-LSTM-GRU-Attention", "98.31% (F1 = 0.989)"],
]
add_table(["Author(s)", "Methodology", "Reported Accuracy"], ecu_rows)
add_para(
    "On ECU-IoHT, the split-before-fit result (98.31% accuracy, F1 = 0.989) is competitive with, though "
    "not the highest among, published figures, most of which report 98–99.9%. The 5-fold "
    "cross-validation mean (92.77%, ± 1.09%) is noticeably lower than the single-split test "
    "accuracy, which is expected: cross-validation trains on only 4/5 of the training partition per "
    f"fold with fewer epochs, while the final model trains on the full partition for up to "
    f"{FINAL_EPOCHS_CAP} epochs, stopping early (via a loss-plateau patience criterion) after "
    f"{R['ECU-IoHT']['epochs_run']} epochs for ECU-IoHT."
)

add_para(
    "Table 14 is restricted to studies performing the same intrusion/attack-detection task on DSICU "
    "or a comparable multi-dataset benchmark that includes it; the MIMIC-IV clinical-outcome-"
    "prediction studies in Table 1 solve a different task with different metrics (e.g., MAPE on a "
    "regression target) and are not included here."
)
add_table_caption("Table 14. Comparison on DSICU (intrusion-detection task only).")
dsicu_rows = [
    ["This work (split-before-fit)", "CNN-LSTM-GRU-Attention", "100.00% (F1 = 1.000)"],
]
add_table(["Author(s)", "Methodology", "Reported Result"], dsicu_rows)
add_para(
    "No directly comparable published intrusion-detection result on DSICU specifically is included "
    "here: on verification against the publisher's record, the MREQGAN-DSA study previously cited in "
    "this context (Krishna Kumari et al.) reports results on NSL-KDD and WUSTL-EHMS-2020 only, not "
    "DSICU, and citing it here would misattribute a result it did not report; it is instead cited "
    "correctly in Section 2.3 and Table 12 against its actual WUSTL-EHMS-2020 evaluation."
)
add_para(
    "On DSICU, the split-before-fit result matches the highest published figures at 100% accuracy across "
    f"every cross-validation fold and the held-out test partition, with near-zero training loss "
    f"reached within {R['DSICU']['epochs_run']} epochs. Section 5.5 verifies that this is not an artifact of upstream feature-selection "
    "leakage — the provided feature file was confirmed to be unselected raw protocol data — and "
    "attributes it instead to near-deterministic correlations between protocol-level features and the "
    "label in this particular capture. Section 4.7 shows the same conclusion holds for classical "
    "baselines (logistic regression, random forest, gradient boosting, and an MLP all also reach "
    "100% on the same split), and Section 4.10's flow-grouped sensitivity split shows it is not an "
    "artifact of related records appearing in both partitions either."
)

add_para(
    "Table 15 makes the evaluation-protocol gap underlying Tables 12–14 explicit rather than implicit. "
    "For each comparator, it audits whether the source publication states that (a) the train/test "
    "split preceded any fitting of feature selection or scaling, (b) obviously identifying features "
    "(e.g., IP/MAC addresses, ports, timestamps as raw values) were excluded, (c) results were "
    "compared against a same-split classical baseline, (d) any optimizer/tuning method used was "
    "controlled against an unguided alternative at a matched budget, and (e) results were checked "
    "against an alternative (e.g., temporal or grouped) split. Because most published intrusion-"
    "detection papers in this space do not report these protocol details at all, most cells below are "
    "\"Not stated\" rather than \"No\" — we could not confirm the protocol was absent, only that the "
    "source publication does not say either way. This is itself the point the audit is meant to make: "
    "headline accuracy numbers in Tables 12–14 are being compared across very different (and mostly "
    "undisclosed) levels of methodological rigor, which is exactly why this manuscript reports its own "
    "protocol in full (Section 3.2) rather than relying on accuracy alone."
)
add_table_caption("Table 15. Protocol audit of the comparators in Tables 12–14 and this work.")
protocol_rows = [
    ["This work", "Yes", "Yes", "Yes", "Yes", "Yes"],
    ["Tauqeer et al. (2022)", "Not stated", "Not stated", "Not stated", "N/A (no tuning method reported)", "Not stated"],
    ["Judith et al. (2023)", "Not stated", "Not stated", "Not stated", "N/A", "Not stated"],
    ["Shaikh et al. (2024)", "Not stated", "Not stated", "Not stated", "Not stated", "Not stated"],
    ["Wu et al. (2025)", "Not stated", "Not stated", "Not stated", "Not stated", "Not stated"],
    ["Balhareth et al. (2026)", "Not stated", "Not stated", "Not stated", "Not stated", "Not stated"],
    ["Abid (2026)", "Not stated", "Not stated", "Yes (multi-classifier)", "N/A", "Not stated"],
    ["Aversano et al. (2026)", "Not stated", "Not stated", "Not stated", "Not stated", "Not stated"],
    ["Abdelhaq et al. (2026)", "Not stated", "Not stated", "Not stated", "Not stated", "Not stated"],
    ["Mosaiyebzadeh et al. (2025)", "Not stated", "Not stated", "Not stated", "N/A", "Not stated"],
    ["Krishna Kumari et al. (2026)", "Not stated", "Not stated", "Not stated", "Not stated", "Not stated"],
    ["Vijayakumar et al. (2023)", "Not stated", "Not stated", "Not stated", "N/A", "Not stated"],
    ["Areia et al. (2024)", "Not stated", "Not stated", "Not stated", "N/A", "Not stated"],
    ["Algethami & Alshamrani (2024)", "Not stated", "Not stated", "Not stated", "Not stated", "Not stated"],
    ["Alohali et al. (2025)", "Not stated", "Not stated", "Not stated", "Not stated", "Not stated"],
    ["Alharbi & Khan (2025)", "Not stated", "Not stated", "Not stated", "N/A", "Not stated"],
]
add_table(
    ["Author(s)", "Split-before-fit?", "Identifier features excluded?",
     "Same-split baseline comparison?", "Optimizer control?", "Alternative split tested?"],
    protocol_rows
)

add_heading("5.2. Do the Hybrid Architecture and Lionfish Optimizer Help?", level=2)
add_para(
    "Sections 4.7–4.9 tested two implicit claims behind the proposed method: that the hybrid "
    "CNN-LSTM-GRU-Attention architecture is a good choice for this task, and that the Lionfish "
    "optimizer finds better hyperparameters than unguided search. Neither claim holds uniformly. "
    "Classical baselines trained on the identical split matched or exceeded the hybrid model on two "
    "of three benchmarks — random forest and histogram gradient boosting on ECU-IoHT, and gradient "
    "boosting by a wide margin on WUSTL-EHMS-2020 (97.26% accuracy and F1 = 0.881 vs. the hybrid "
    "model's 93.46% and 0.679, with recall of 0.809 vs. 0.552) — and tied it on DSICU, where the "
    "task is close to trivially separable for every method tried. The ablation in Section 4.8 shows "
    "the architecture's components do help relative to a bare CNN on ECU-IoHT, but attention "
    "specifically did not help on WUSTL-EHMS-2020 at the tested budget, and Lionfish-tuned "
    "hyperparameters mattered far more than which layers were present. The random-search control in "
    "Section 4.9 shows Lionfish did not outperform unguided sampling at a matched budget on any "
    "dataset, and was measurably worse on WUSTL-EHMS-2020; a follow-up three-seed comparison over an "
    "expanded six-dimensional space (Section 4.9, Table 10a) confirms this rather than reversing it — "
    "random search matched or slightly beat Lionfish on both benchmarks retested, with the gap not "
    "statistically significant at three seeds. Taken together, these results do not "
    "support treating the hybrid architecture or the Lionfish optimizer as the source of whatever "
    "predictive value this framework has; the more defensible contribution is the evaluation "
    "protocol itself, and the willingness to report where classical, cheaper models are the better "
    "engineering choice. Section 4.11's class-weighted loss experiment shows the WUSTL-EHMS-2020 "
    "recall gap is partially, though not fully, addressable within the hybrid architecture itself, "
    "and Section 4.12's sliding-window experiment shows that supplying the recurrent layers with a "
    "genuine temporal sequence, rather than the feature-axis pseudo-sequence used throughout the "
    "main experiment, did not by itself improve ECU-IoHT results under a fair, confound-matched "
    "comparison — a further indication that this specific architecture's apparent strengths are not "
    "well explained by genuine sequence modeling."
)

add_heading("5.3. Cross-Dataset Interpretation", level=2)
add_para(
    "The three-way performance gap — 100% on DSICU, 98.31% on ECU-IoHT, 93.46% on WUSTL-EHMS-2020 "
    "for the hybrid model — is consistent with differences in task difficulty and feature "
    "separability rather than a demonstrated difference in model capacity, since the identical "
    "architecture and search procedure produced all three results and classical baselines show the "
    "same ordering (Section 4.7). ECU-IoHT's usable feature set is small (protocol, packet length, "
    "and timestamp) but strongly informative, because several attack types in this dataset (notably "
    "ICMP-based Smurf floods) are close to perfectly correlated with the Protocol field. "
    "WUSTL-EHMS-2020 combines network-flow and physiological vital-sign features with a genuine "
    "12.5% minority attack class, which is the harder and more realistic setting of the three. We "
    "phrase this as an association rather than a causal claim: no experiment here isolates task "
    "difficulty from other differences between the three benchmarks (feature count, capture "
    "protocol, class balance, and dataset size all vary simultaneously)."
)

add_heading("5.4. Sensitivity Analysis: What Alternative Splits Reveal", level=2)
add_para(
    "Section 4.10's alternative-split results change the interpretation of the main findings in an "
    "important way, and the revised (version 2) protocol — independent per-split hyperparameter "
    "search, removal of the identifier-like split-defining field from the feature set, and a training "
    "budget matched to the main experiment (42-candidate search, up to 80 epochs) — changes that "
    "interpretation further still. ECU-IoHT's apparently strong 98.27% ± 0.08% accuracy under random "
    f"splitting fell to {SENS2['ECU-IoHT']['accuracy']*100:.1f}% under a temporal split even with "
    "hyperparameter reuse, the Time feature, and any budget shortfall all removed as confounds "
    f"(compared with {SENS['ECU-IoHT']['accuracy']*100:.1f}% in the earlier, less rigorous version 1 "
    f"pass), with recall staying high throughout ({SENS2['ECU-IoHT']['recall']:.3f}). Some of version "
    "1's apparent collapse was attributable to reusing hyperparameters tuned for the main split's "
    "class balance and to a smaller search/training budget rather than to the architecture failing to "
    "generalize across time; with those confounds removed and the budget matched, the remaining "
    "roughly 12-13 percentage-point gap is best read as a genuine temporal generalization limitation "
    "that a random split cannot reveal, because train and test windows share the same overall class "
    "balance by construction. This means the headline ECU-IoHT number in Section 4.4, while correctly "
    "computed under a split-before-fit protocol, still overstates how the model would perform if "
    "deployed forward in time on this capture, by a real but smaller margin than the initial "
    "sensitivity pass suggested. WUSTL-EHMS-2020's recall stayed low under the temporal split at "
    f"matched budget ({SENS2['WUSTL-EHMS-2020']['recall']:.3f}, comparable to version 1's "
    f"{SENS['WUSTL-EHMS-2020']['recall']:.3f}), reinforcing that this benchmark's minority attack "
    "class is genuinely hard to generalize to under any reasonable split, independent of "
    "hyperparameter source, the Packet_num feature, or training budget. DSICU is the one dataset "
    "whose result we consider robust in the strongest sense available in this study: it remained "
    f"almost perfectly separable ({SENS2['DSICU']['accuracy']*100:.2f}% accuracy) even under a "
    "flow-grouped split, with the port fields entirely excluded from its features, hyperparameters "
    "searched independently inside that split's own training partition, and a training budget matched "
    "to the main experiment — the combination of tests best positioned to catch a feature-, "
    "hyperparameter-, or budget-driven artifact, and DSICU still passes it. We therefore do not treat "
    "\"split-before-fit\" as a synonym for \"leakage-free\" or \"generalizes to deployment\": it rules "
    "out one specific and common leakage mechanism, and the alternative-split results show that "
    "ruling out that one mechanism was not sufficient for ECU-IoHT even after the sensitivity "
    "protocol itself was tightened to remove every confound we could identify."
)

add_heading("5.5. Limitations", level=2)
add_para(
    "Several limitations should be considered when interpreting these results. First, we verified "
    "the provenance of DSICU's provided feature file (dsicu_mi.csv) by comparing it directly against "
    "the research group's earlier duplicate-removed export of the same capture (dsicu_A_cleaned.csv): "
    "the two files are byte-identical across all 188,694 records and 17 raw protocol-level columns. "
    "No mutual-information, chi-squared, or other feature-selection step had therefore been applied "
    "to this file before it reached the present study's own split-before-fit pipeline, and the “_mi” "
    "suffix in its filename does not reflect prior feature selection. DSICU's perfect separability is "
    "consequently attributed to the same mechanism identified for ECU-IoHT: a small set of protocol-"
    "level features (TCP/MQTT header fields) that are close to perfectly correlated with the Normal/"
    "Attack label in this particular capture, corroborated by the flow-grouped sensitivity split "
    "(Section 4.10) and by classical baselines reaching the same ceiling (Section 4.7). As a direct "
    f"diagnostic, we computed the single-feature AUC of each of the {DSICU_AUC['n_features_checked']} "
    "surviving (post-selection, standardized) features against the training label, with no model fit "
    "(Table 16). The strongest single feature alone reaches "
    f"AUC = {DSICU_AUC['max_single_feature_auc']:.3f}, short of near-perfect (≥0.98) on its own but "
    "still far above chance, indicating the separating signal is concentrated in a small number of "
    "protocol-adjacent fields rather than requiring the hybrid architecture's representational "
    "capacity to find; the original clinical feature names could not be recovered for this diagnostic "
    "(see Table 16 note), so it is reported by feature index rather than semantic label. This should "
    "still be replicated on an independently captured DSICU-like dataset before being treated as a "
    "general property of the detection task, and given all of this, DSICU is reported throughout this "
    "paper as a cautionary case study rather than as evidence for the architecture's effectiveness."
)
add_table_caption(
    "Table 16. DSICU per-feature diagnostic: single-feature AUC against the training label for each "
    "of the 16 post-selection, standardized features (no model fit; features identified by their "
    "1-indexed position among the SelectKBest-retained set, since original clinical feature names "
    "were not recoverable from the restricted-access source file in this analysis environment)."
)
add_table(
    ["Feature Index", "AUC vs. Label (raw direction)", "Separating Power (max(AUC, 1-AUC))"],
    [[str(r["selected_feature_index"]), f"{r['auc_vs_label']:.3f}", f"{r['separating_power_auc']:.3f}"]
     for r in DSICU_AUC["per_feature"][:5]] +
    [["...", "...", "(remaining 11 features in Supplementary Materials)"]]
)
add_para(
    "Second, the recurrent layers in the hybrid architecture process features in the dataset's "
    "native column order rather than a genuine temporal sequence (Section 3.4); the ablation "
    "(Section 4.8) confirms each layer contributes something on ECU-IoHT but not uniformly across "
    "datasets, and we do not interpret the LSTM/GRU components as having learned real temporal "
    "dynamics. Third, as Sections 4.7–4.9 show directly, classical baselines matched or exceeded the "
    "hybrid model on two of three benchmarks, and the Lionfish optimizer did not outperform random "
    "search at a matched budget on any benchmark, a finding a follow-up three-seed test over an "
    "expanded search space (Section 4.9) did not overturn; readers should not take the architecture "
    "or optimizer choices in this paper as validated improvements over simpler alternatives. That "
    "three-seed test is itself a small sample — n = 3 paired seeds cannot support strong statistical "
    "claims of equivalence any more than of superiority — so \"no evidence of a Lionfish advantage\" "
    "should be read as the honest limit of what this evaluation can establish, not as proof the two "
    "methods perform identically in general. Fourth, "
    "the main experiment uses a record-level random stratified split; Section 4.10's alternative-split "
    "sensitivity analysis shows this materially overstates ECU-IoHT performance and moderately "
    "overstates WUSTL-EHMS-2020 recall, so the Section 4.4 numbers should be read as an upper bound "
    "under an easier partitioning scheme rather than an estimate of forward-deployment performance. "
    "Fifth, while Section 4.4 reports four seeds on the main split's train/test partition and finds "
    "tight variation for ECU-IoHT and DSICU and moderate variation for WUSTL-EHMS-2020's F1, this "
    "only characterizes sensitivity to weight initialization on one fixed partition; it does not "
    "substitute for repeated re-splitting. Section 4.3's paired significance test across five matched "
    "cross-validation folds within a single split originally suggested gradient boosting's edge was "
    "not attributable to chance on either ECU-IoHT or WUSTL-EHMS-2020, but folds within one split are "
    "not independent, so Section 4.13 reran the comparison across four independently reseeded "
    "train/test splits with a Nadeau-Bengio correction for that residual dependence. The corrected "
    "test confirms gradient boosting's advantage on WUSTL-EHMS-2020, but on ECU-IoHT it does not "
    "reach significance at this reseed count even though gradient boosting won every individual "
    "reseed, so we now state the ECU-IoHT baseline comparison as consistent but not yet "
    "statistically established, revising the more confident claim the uncorrected test had supported. "
    "This is itself a demonstration of the review's underlying concern: an evaluation protocol's "
    "statistical rigor can change which findings hold up, and a full 10-reseed (or larger) version of "
    "Section 4.13's design remains future work to resolve ECU-IoHT's case with more confidence. Sixth, the "
    "architecture ablation and random-search control both use a reduced-epoch quick-evaluation "
    "protocol (3 epochs) for practicality, and a single run per configuration; the noisy DSICU "
    "CNN+LSTM+GRU result in Section 4.8 (0.833, versus 0.988–0.996 for adjacent variants) illustrates "
    "the run-to-run variance this budget can produce, so the ablation and random-search findings "
    "should be read as directional rather than precise estimates."
)
add_para(
    "An earlier, smaller-scale pass through the main pipeline (Lionfish population 5, 5 iterations, "
    "2-epoch quick evaluation; 5-fold cross-validation with up to 6 epochs per fold; final training "
    "capped at 40 epochs) was re-run at the larger scale reported above (population 6, 6 iterations, "
    "3-epoch quick evaluation; up to 10 epochs per cross-validation fold; final training capped at "
    "80 epochs) to check whether the smaller search budget had materially understated performance. "
    "The two passes agreed closely: ECU-IoHT moved from 98.27% to 98.31% test accuracy, "
    "WUSTL-EHMS-2020 from 93.32% to 93.46% (F1 from 0.665 to 0.679), and DSICU remained at 100.00% "
    "in both passes. This consistency across a roughly 1.4-fold increase in search and training "
    "budget suggests the main-experiment results are not simply an artifact of an under-tuned "
    "search — though it does not bear on the separate finding that Lionfish itself did not beat "
    "random search at matched budget (Section 4.9), nor on the alternative-split degradation "
    "(Section 4.10)."
)

# =======================================================================
# 6. CONCLUSIONS
# =======================================================================
add_heading("6. Conclusions", level=1)
add_para(
    "This study evaluated a Lionfish-tuned hybrid CNN-LSTM-GRU-Attention framework for intrusion "
    "detection in IoMT and telemetry-enabled healthcare environments under a split-before-fit "
    "protocol across three benchmarks, and then subjected that evaluation to same-split classical "
    "baselines, an exploratory architecture ablation, a single-run random-search control for the "
    "optimizer, repeated-seed evaluation at a matched training budget, capture-order/identifier-feature "
    "removal, and a sensitivity analysis using temporal and flow-grouped alternative splits evaluated "
    "with independently searched hyperparameters at the same search and training budget as the main "
    "experiment. The hybrid model reached 98.27% ± 0.08% accuracy (F1 = 0.989 ± 0.001) over four seeds "
    "on ECU-IoHT, 100.00% ± 0.00% on DSICU, and a more modest 93.73% ± 0.17% accuracy "
    "(F1 = 0.692 ± 0.009) on WUSTL-EHMS-2020. However, classical baselines matched or exceeded it on "
    "ECU-IoHT and WUSTL-EHMS-2020 — including on probability-based metrics such as ROC-AUC and PR-AUC, "
    "not only accuracy and F1 — the Lionfish optimizer did not outperform random search at a matched "
    "budget, and even after removing identifier-like features, searching hyperparameters independently "
    "inside each alternative split, and matching the alternative-split training budget to the main "
    "experiment's, a temporal split still reduced ECU-IoHT accuracy to 85.8% and left WUSTL-EHMS-2020 "
    "recall at 0.385. A paired significance test on matched cross-validation folds within a single "
    "split initially suggested both baseline advantages were not attributable to chance "
    "(p = 0.00047 and p = 0.00203 for ECU-IoHT and WUSTL-EHMS-2020, respectively), but a more "
    "conservative Nadeau-Bengio corrected test across four independently reseeded train/test splits "
    f"(Section 4.13) confirms this for WUSTL-EHMS-2020 (p = {_wustl_nb['p_value']:.3f}) while finding "
    f"it not yet statistically established at this reseed count for ECU-IoHT (p = {_ecu_nb['p_value']:.3f}), "
    "despite gradient boosting winning on every individual reseed — a finding we report as an open "
    "question rather than resolve, and a concrete illustration of why evaluation-protocol rigor can "
    "change a paper's conclusions. Only DSICU's near-perfect separability held up "
    "under every check applied, including a flow-grouped split with the split-defining port fields "
    "excluded from the feature set entirely, hyperparameters searched independently within it, and a "
    "training budget matched to the main experiment — the combination of tests best positioned to "
    "expose a preprocessing, feature, hyperparameter-transfer, or budget-driven artifact, yet unable "
    "to fully explain the result given the dataset's restricted-access provenance; we therefore treat "
    "DSICU's perfect score as an unresolved artifact requiring independent replication, not a "
    "validated finding. We followed up on two of these open questions directly rather than leaving "
    "them solely to future work. A three-seed, budget-matched comparison over an expanded "
    "six-dimensional search space confirmed that random search matches or slightly exceeds Lionfish "
    "on both benchmarks retested, with the gap not statistically significant at this sample size — "
    "reinforcing rather than reversing the single-run finding. A class-weighted loss recovered a "
    "genuine, validation-selected improvement in WUSTL-EHMS-2020's attack-class recall (0.591 vs. "
    "the baseline's 0.552) without sacrificing F1 or ROC-AUC, though it still falls well short of "
    "gradient boosting's recall (0.809) on the identical split. A true sliding-window sequence "
    "representation for ECU-IoHT, tested under a fair, confound-matched protocol against the "
    "existing temporal-split baseline, underperformed the simpler feature-axis representation, "
    "indicating that this architecture's results are not explained by genuine sequence modeling "
    "either. We report all of this directly, including the instances where "
    "simpler methods outperformed the proposed architecture and where the proposed optimizer showed "
    "no measurable advantage, because we believe the paper's most useful contribution is not a claim "
    "that this specific hybrid architecture is state of the art, but a demonstration of how much "
    "additional evidence — beyond a single split-before-fit accuracy number — is needed before an "
    "IoMT intrusion-detection result should be trusted as reflecting genuine, deployable "
    "generalization."
)

add_heading("Future Work", level=2)
add_para(
    "Priority should go to closing the gaps this study's own additional checks surfaced rather than "
    "to further architecture engineering. First, ECU-IoHT's temporal-split collapse (Section 4.10) "
    "points to threshold recalibration under class-balance shift as a concrete, tractable next step "
    "(e.g., periodic threshold re-estimation or calibration against a rolling class-balance "
    "estimate) before any deployment claim on time-ordered traffic. Second, since classical "
    "baselines matched or beat the hybrid model on two of three benchmarks (Section 4.7), future "
    "work on this problem should default to a strong gradient-boosting baseline and require any deep "
    "architecture to justify its added complexity against it, rather than assuming a hybrid deep "
    "network is the right starting point. Third, the Lionfish-vs-random-search result (Section 4.9) "
    "was retested with a three-seed, six-dimensional follow-up that confirmed rather than reversed "
    "the original finding; a still larger evaluation budget, more seeds, and a higher-dimensional or "
    "qualitatively harder search space remain open directions for testing whether an advantage for "
    "Lionfish emerges under conditions not covered here. Fourth, the DSICU finding should be "
    "replicated on an independently captured dataset of the same protocol mix to confirm its "
    "near-perfect separability generalizes beyond this single capture. Fifth, while this study's "
    "paired significance test (Section 4.3) already confirms the classical-baseline advantage on "
    "ECU-IoHT and WUSTL-EHMS-2020 within the cross-validation folds of a single split, the framework "
    "should further be evaluated across many independently reseeded train/test splits with the same "
    "significance testing applied. Sixth, a class-weighted loss (Section 4.11) recovered a genuine, "
    "if partial, improvement in the WUSTL-EHMS-2020 recall gap; closing the remaining gap to "
    "gradient boosting's recall likely requires combining this with the classical model's feature "
    "representation, cost-sensitive decision thresholds tuned per deployment context, or the "
    "generative approaches to synthetic minority-class augmentation that have shown promise in other "
    f"imbalanced medical data-reconstruction settings {cite('orig19')}. Seventh, the true "
    "sliding-window sequence experiment (Section 4.12) tested one fixed window length and labeling "
    "scheme; a systematic sweep over window length, stride, and label definition, together with "
    "hyperparameters re-searched specifically for the windowed representation rather than reused from "
    "the flat baseline, is needed before concluding that genuine temporal sequencing cannot help "
    "ECU-IoHT under any configuration."
)

# =======================================================================
# BACK MATTER (MDPI required sections)
# =======================================================================
add_backmatter(
    "Abbreviations",
    "The following abbreviations are used in this manuscript: IoMT, Internet of Medical Things; "
    "IoHT, Internet of Health Things; CNN, Convolutional Neural Network; LSTM, Long Short-Term "
    "Memory; GRU, Gated Recurrent Unit; BCE, Binary Cross-Entropy; wBCE, class-weighted Binary "
    "Cross-Entropy; ROC, Receiver Operating Characteristic; AUC, Area Under the Curve; PR, "
    "Precision-Recall; RF, Random Forest; HistGB, Histogram-based Gradient Boosting; MLP, "
    "Multi-Layer Perceptron; LFO, Lionfish Optimization; RS, Random Search; CV, Cross-Validation; "
    "NB test, Nadeau-Bengio corrected resampled t-test; DSICU, the restricted-access dataset used "
    "in this study as a cautionary case study (see Section 5); ECU-IoHT, ECU Internet of Health "
    "Things dataset; WUSTL-EHMS-2020, Washington University in St. Louis Enhanced Healthcare "
    "Monitoring System 2020 dataset."
)
add_backmatter(
    "Supplementary Materials",
    "The following supporting information is provided with this submission: preprocessing, model, "
    "Lionfish optimization, classical-baseline, ablation, random-search, sensitivity-analysis, "
    "class-imbalance-mitigation, multi-seed optimizer-comparison, and sliding-window-sequence code "
    "(code/); every raw result file underlying each table and figure, including cross-"
    "validation folds, Lionfish and random-search logs, ablation results, classical-baseline "
    "results, extended probability-based metrics, alternative-split sensitivity results, the "
    "class-weighted/focal-loss recall-mitigation results, the three-seed Lionfish-vs-random-search "
    "comparison, and the true sliding-window sequence results (results/); and the exact 0-indexed "
    "train/test row indices used for the main split for each "
    "dataset (split_indices/), packaged as HMHDL_supplementary_materials.zip with an accompanying "
    "README."
)
add_backmatter(
    "Author Contributions",
    "Conceptualization, H.A.T. and M.M.J.; methodology, H.A.T.; software, H.A.T.; validation, H.A.T. "
    "and M.M.J.; formal analysis, H.A.T.; investigation, H.A.T.; data curation, H.A.T.; writing—"
    "original draft preparation, H.A.T.; writing—review and editing, R.H. and M.M.J.; "
    "visualization, H.A.T.; supervision, R.H.; project administration, M.M.J. All "
    "authors have read and agreed to the published version of the manuscript."
)
add_backmatter("Funding", "This research received no external funding.")
add_backmatter(
    "Institutional Review Board Statement",
    "Not applicable. This study analyzed previously de-identified network and telemetry benchmark "
    "datasets (ECU-IoHT, WUSTL-EHMS-2020, DSICU), including two public datasets (ECU-IoHT, "
    "WUSTL-EHMS-2020) and one restricted-access dataset (DSICU; see the Data Availability Statement), "
    "and did not involve new data collection from human or animal subjects."
)
add_backmatter("Informed Consent Statement", "Not applicable.")
add_backmatter(
    "Data Availability Statement",
    "The ECU-IoHT and WUSTL-EHMS-2020 datasets analyzed in this study are third-party public "
    "benchmarks available from their original publishers. The DSICU dataset was obtained from prior "
    "work by the authors' research group and is available from the corresponding author on request, "
    "subject to the terms under which it was obtained. All code (preprocessing, model, Lionfish "
    "optimization, classical baselines, ablation, random search, and sensitivity analysis), the "
    "exact train/test split indices for both the main split and every alternative split, the random "
    "seeds used, and every raw result file underlying the manuscript's tables and figures are "
    "provided as Supplementary Materials accompanying this submission, so the reported numbers do "
    "not depend on data availability alone to be checked."
)
add_backmatter(
    "Acknowledgments",
    "In accordance with the journal's policy on the use of generative AI, the authors disclose that "
    "Claude Sonnet 5 (Anthropic; model identifier claude-sonnet-5) was used both in this study's "
    "methodology and in manuscript preparation. As a methodology tool, it served as a coding "
    "assistant to help design and implement the preprocessing pipeline, the same-split "
    "classical-baseline comparison (Section 4.7), the architecture ablation (Section 4.8), the "
    "random-search optimizer control (Section 4.9), the alternative-split sensitivity analysis "
    "(Section 4.10), the identifier-feature-removal check (Section 5.5), the paired statistical "
    "significance test (Section 4.3), the class-imbalance-mitigation and sliding-window-sequence "
    "experiments (Section 4.11-4.12), and the multi-seed classical-baseline, inference-cost, and "
    "per-attack-class recall analyses. All experimental design decisions — which comparisons to run, "
    "which datasets and splits to use, how to interpret the results — were made by the authors; the "
    "tool's role was implementation support under author direction. All code was reviewed by the "
    "authors, and all reported numbers were generated by running that code against the study's own "
    "data; no results, citations, or experimental findings were generated by the AI tool "
    "independently of the code it helped implement. As a manuscript-preparation tool, it was used "
    "for drafting assistance and results-reporting formatting. The authors have reviewed and edited "
    "all AI-assisted output and take full responsibility for the validity of all methods, results, "
    "and content reported in this publication."
)
add_backmatter("Conflicts of Interest", "The authors declare no conflicts of interest.")

# =======================================================================
# REFERENCES (auto-numbered by the template's MDPI81references style)
# =======================================================================
add_heading("References", level=1)
_last_was_heading[0] = False
for key, formatted in REFS:
    p = doc.add_paragraph(formatted, style="MDPI81references")

# ---------------------------------------------------------------------
# Clean up document metadata (the template's core properties still say
# "Type of the Paper (Article" / author "MDPI").
# ---------------------------------------------------------------------
cp = doc.core_properties
cp.title = title
cp.author = "Hiba A. Tarish, Rosilah Hassan, Mustafa Musa Jaber"
cp.subject = "Internet of Medical Things intrusion detection"
cp.last_modified_by = "Hiba A. Tarish"

doc.save(OUT_PATH)
print("Saved:", OUT_PATH)
