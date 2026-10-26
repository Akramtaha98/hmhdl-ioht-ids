#!/usr/bin/env bash
# Experiment 1 on 3 GPUs in parallel (separate --out folders; merge afterwards with merge_exp1.py)
export TF_FORCE_GPU_ALLOW_GROWTH=true
ECU=data/ECU-IoHT.csv; WUSTL=data/wustl-ehms-2020.csv
mkdir -p logs results
# GPU 0: ECU random split, seeds 42-44
( export CUDA_VISIBLE_DEVICES=0
  python exp1_val_earlystop_bigbudget.py --name ECU --csv $ECU --search-seeds 42 43 44 --out results/g0 > logs/g0.log 2>&1 ) &
# GPU 1: ECU random split, seeds 45-46, then ECU temporal seed 42
( export CUDA_VISIBLE_DEVICES=1
  python exp1_val_earlystop_bigbudget.py --name ECU --csv $ECU --search-seeds 45 46 --out results/g1 > logs/g1.log 2>&1
  python exp1_val_earlystop_bigbudget.py --name ECU --csv $ECU --split temporal --search-seeds 42 --out results/g1 >> logs/g1.log 2>&1 ) &
# GPU 2: WUSTL (small, fast) random + temporal, then ECU temporal seeds 43-44
( export CUDA_VISIBLE_DEVICES=2
  python exp1_val_earlystop_bigbudget.py --name WUSTL --csv $WUSTL --out results/g2 > logs/g2.log 2>&1
  python exp1_val_earlystop_bigbudget.py --name WUSTL --csv $WUSTL --split temporal --out results/g2 >> logs/g2.log 2>&1
  python exp1_val_earlystop_bigbudget.py --name ECU --csv $ECU --split temporal --search-seeds 43 44 --out results/g2b >> logs/g2.log 2>&1 ) &
wait
python merge_exp1.py
