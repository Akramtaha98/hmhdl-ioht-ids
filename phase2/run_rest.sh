#!/usr/bin/env bash
export TF_FORCE_GPU_ALLOW_GROWTH=true OMP_NUM_THREADS=8
ECU=data/ECU-IoHT.csv; WUSTL=data/wustl-ehms-2020.csv
HE=$(cat results/hp_ECU.json); HW=$(cat results/hp_WUSTL.json); mkdir -p logs
( export CUDA_VISIBLE_DEVICES=0; python exp2_ten_reseeds_nb_test.py --name ECU --csv $ECU --hp "$HE" > logs/e2_ecu.log 2>&1
  python exp6_per_class_ECU.py --name ECU --csv $ECU --hp "$HE" > logs/e6.log 2>&1 ) &
( export CUDA_VISIBLE_DEVICES=1; python exp2_ten_reseeds_nb_test.py --name WUSTL --csv $WUSTL --hp "$HW" > logs/e2_wustl.log 2>&1
  python exp3_temporal_collapse_diagnosis.py --name ECU --csv $ECU --hp "$HE" > logs/e3_ecu.log 2>&1 ) &
( export CUDA_VISIBLE_DEVICES=2; python exp3_temporal_collapse_diagnosis.py --name WUSTL --csv $WUSTL --hp "$HW" > logs/e3_wustl.log 2>&1
  python exp5_published_style_models.py --name WUSTL --csv $WUSTL > logs/e5_wustl.log 2>&1 ) &
( export CUDA_VISIBLE_DEVICES=0; python exp5_published_style_models.py --name ECU --csv $ECU > logs/e5_ecu.log 2>&1 ) &
wait
