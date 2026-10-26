# Phase 2 experiments (new runs for the IEEE Access revision)

Put the dataset CSVs in `data/` (ECU-IoHT.csv, wustl-ehms-2020.csv, and the CICIoMT2024 folder). If your CSV headers differ,
pass `--label-col` / `--order-col` (defaults: ECU label=`Type`, order=`Time`; WUSTL label=`Target`, order=`Packet_num`).

    python -m venv .venv && source .venv/bin/activate      # Python 3.10
    pip install -r requirements.txt                        # ONE environment for every number (issue 8)
    bash run_phase2.sh                                      # or run the scripts one by one (see below)

Smoke test first (2 minutes): add `--max-rows 5000 --budget 6 --search-seeds 42 --epochs 3` to any script.

| # | Script | Reviewer issue it closes | Writes | Paper change |
|---|---|---|---|---|
| 1 | `exp1_val_earlystop_bigbudget.py` | early stopping on test/train loss; tiny budget (42x3 ep) | results/exp1_* | Sec. III-E + IV-J: validation early stopping, 100x5 budget, 5 search repeats LIRS vs random (mean ± SD) |
| 2 | `exp2_ten_reseeds_nb_test.py` | only 4 reseeds, ECU p=0.478 | results/exp2_* | Table XVIII with 10 reseeds, NB-corrected p for accuracy, F1, recall |
| 3 | `exp3_temporal_collapse_diagnosis.py` | unexplained temporal collapse | results/exp3_* | new subsection: AUC vs accuracy@0.5 vs accuracy@validation-threshold, ECE, score shift |
| 4 | `exp4_public_dataset_CICIoMT2024.py` | restricted DSICU | results/exp4_* | replace Appendix/third dataset by CICIoMT2024 (hybrid + 4 baselines, per-family recall) |
| 5 | `exp5_published_style_models.py` | no comparison to published models | results/exp5_* | Table: DNN / CNN / LSTM / RF / HGB under the same protocol (label them "re-implementations") |
| 6 | `exp6_per_class_ECU.py` | per-class ECU results; single sklearn version | results/exp6_* | per-subtype recall under random and temporal splits |

`python make_tables.py` prints summary tables from `results/`.

## How to read the outcomes (what you may then claim)
* Exp 3: if ROC-AUC stays high (≥0.97) while accuracy@0.5 drops and accuracy at the validation-chosen threshold recovers, the
  collapse is **calibration / threshold shift**, not lost signal. If AUC also drops, the model really failed to generalise.
* Exp 1: if LIRS still does not beat random search at 100 evaluations over 5 repeats, keep the negative result (it is publishable).
* Exp 2: only claim "baseline significantly better" where NB p < 0.05 with 10 reseeds; otherwise say "not significant".
* Exp 4: report CICIoMT2024 as the third benchmark instead of DSICU; DSICU stays a one-paragraph appendix (or is dropped).
* Note: `common.search(..., 'lirs')` is a compact re-implementation of LIRS. To keep it identical to the paper, swap in the
  Lionfish routine from your repo's `code/pipeline.py`; the experiments call only `search()`.
* Exp 5 models are re-implementations of the cited model families, not the authors' code; say so in the text.
* After the runs, send me `results/` (JSON files) and I will regenerate every table, number, figure and the abstract.
