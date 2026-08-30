#!/usr/bin/env bash
# Orchestrates the full experiment pipeline from raw data to every result
# file referenced in the manuscript's tables and figures.
#
# IMPORTANT: several stages are individually resumable/checkpointed and were
# originally run inside a sandboxed environment that caps a single process
# to a few minutes of wall-clock time (see each script's --budget flag).
# On a normal workstation you can usually let a stage run to completion in
# one call; if a stage prints "budget hit, checkpointed, rerun to continue",
# simply re-run the same command and it will resume from its last
# checkpoint. Expect the full run (all three datasets, every stage) to take
# on the order of 1-2 hours on a modern CPU-only machine; no GPU is required
# or used.
#
# Usage:
#   cd supplementary/
#   bash run_all.sh
set -e
cd "$(dirname "$0")"
CODE=code
DATASETS=("ECU-IoHT" "WUSTL-EHMS-2020" "DSICU")

echo "=== 0. Place raw datasets in data/ before running this script ==="
echo "    data/ECU_IoHT.csv, data/wustl-ehms-2020.csv, data/dsicu_mi.csv"
echo "    (see README.md for sources, licenses, and SHA-256 hashes)"

for name in "${DATASETS[@]}"; do
  echo "=== 1. Split-before-fit preprocessing: $name ==="
  python3 "$CODE/pipeline.py" prep "$name"
done

for name in "${DATASETS[@]}"; do
  echo "=== 2. Lionfish hyperparameter search: $name ==="
  until python3 "$CODE/pipeline.py" search "$name" --budget 150; do :; done
done

for name in "${DATASETS[@]}"; do
  echo "=== 3. 5-fold cross-validation: $name ==="
  until python3 "$CODE/pipeline.py" cv "$name" --budget 150; do :; done
done

for name in "${DATASETS[@]}"; do
  echo "=== 4. Final model training: $name ==="
  until python3 "$CODE/pipeline.py" train "$name" --budget 150; do :; done
  echo "=== 4b. Final test-set evaluation: $name ==="
  python3 "$CODE/pipeline.py" evaluate "$name"
done

for name in "${DATASETS[@]}"; do
  echo "=== 5. Same-split classical baselines + extra metrics: $name ==="
  python3 "$CODE/baselines_and_metrics.py" "$name" both
  python3 "$CODE/baselines_and_metrics.py" "$name" baseline_extra
done

for name in "${DATASETS[@]}"; do
  echo "=== 6. Random-search optimizer control: $name ==="
  until python3 "$CODE/search_comparison.py" randsearch "$name" --budget 150; do :; done
  echo "=== 6b. Architecture ablation: $name ==="
  until python3 "$CODE/search_comparison.py" ablation "$name" --budget 150; do :; done
done

for name in "${DATASETS[@]}"; do
  echo "=== 7. Alternative-split sensitivity analysis, version 1 (reused hyperparams, IDs kept): $name ==="
  until python3 "$CODE/sensitivity_split.py" "$name" --budget 150; do :; done
done

for name in "${DATASETS[@]}"; do
  echo "=== 8. No-identifier check on the MAIN split: $name ==="
  until python3 "$CODE/no_identifier_check.py" "$name" --budget 150; do :; done
done

for name in "${DATASETS[@]}"; do
  echo "=== 9. Alternative-split sensitivity analysis, version 2 (independent search, IDs removed): $name ==="
  until python3 "$CODE/sensitivity_split_v2.py" search "$name" --budget 150; do :; done
  until python3 "$CODE/sensitivity_split_v2.py" train "$name" --budget 150; do :; done
done

for name in "${DATASETS[@]}"; do
  echo "=== 10. Repeated seeds (43, 44, 45) on the main split: $name ==="
  for seed in 43 44 45; do
    until python3 "$CODE/repeated_seeds.py" run "$name" "$seed" --budget 150; do :; done
  done
  python3 "$CODE/repeated_seeds.py" summarize "$name"
done

echo "=== 11. Export split indices (main + alternative splits) ==="
python3 "$CODE/export_split_indices.py"

echo "=== 12. Generate figures ==="
python3 "$CODE/make_figures.py"

echo "=== Done. All result JSON files are in results/, figures in figures/. ==="
echo "=== To rebuild the manuscript .docx itself you additionally need MDPI's"
echo "=== official jcp-template.dot (not redistributed here); see"
echo "=== code/build_manuscript_mdpi_template.py for details. ==="
