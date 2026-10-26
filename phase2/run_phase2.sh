#!/usr/bin/env bash
# Order matters: exp1 first (gives the LIRS/random hyperparameters you then pass to exp2/3/6 as --hp).
# Quick smoke test of any script: add --max-rows 5000 --budget 6 --search-seeds 42 --epochs 3
set -e
ECU=data/ECU-IoHT.csv; WUSTL=data/wustl-ehms-2020.csv
# 1. validation early stopping + larger budget, LIRS vs random (both datasets, random split; ECU also temporal)
python exp1_val_earlystop_bigbudget.py --name ECU   --csv $ECU
python exp1_val_earlystop_bigbudget.py --name WUSTL --csv $WUSTL
python exp1_val_earlystop_bigbudget.py --name ECU   --csv $ECU   --split temporal
python exp1_val_earlystop_bigbudget.py --name WUSTL --csv $WUSTL --split temporal
# 2. take the best-validation LIRS config from results/exp1_*_random.json and paste it here:
HP_ECU='{"blocks":3,"filters":49,"lstm":50,"gru":29,"dropout":0.272}'     # <-- REPLACE with your exp1 output
HP_WUSTL='{"blocks":3,"filters":49,"lstm":50,"gru":29,"dropout":0.272}'   # <-- REPLACE with your exp1 output
python exp2_ten_reseeds_nb_test.py --name ECU   --csv $ECU   --hp "$HP_ECU"
python exp2_ten_reseeds_nb_test.py --name WUSTL --csv $WUSTL --hp "$HP_WUSTL"
# 3. temporal-collapse diagnosis (ECU = the collapse; WUSTL for the recall collapse)
python exp3_temporal_collapse_diagnosis.py --name ECU   --csv $ECU   --hp "$HP_ECU"
python exp3_temporal_collapse_diagnosis.py --name WUSTL --csv $WUSTL --hp "$HP_WUSTL"
# 4. public replacement dataset
python exp4_public_dataset_CICIoMT2024.py --path data/CICIoMT2024
# 5. published-style models
python exp5_published_style_models.py --name ECU   --csv $ECU
python exp5_published_style_models.py --name WUSTL --csv $WUSTL
# 6. per-class ECU + single-environment record
python exp6_per_class_ECU.py --name ECU --csv $ECU --hp "$HP_ECU"
python make_tables.py
