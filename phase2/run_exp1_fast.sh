#!/usr/bin/env bash
export TF_FORCE_GPU_ALLOW_GROWTH=true OMP_NUM_THREADS=8 TF_NUM_INTRAOP_THREADS=8
ECU=data/ECU-IoHT.csv; WUSTL=data/wustl-ehms-2020.csv
mkdir -p logs results; i=0
run() {  # name csv split seeds...
  local name=$1 csv=$2 split=$3; shift 3
  local tag="${name}_${split}_$(echo $@ | tr ' ' '-')"
  CUDA_VISIBLE_DEVICES=$((i % 3)) python exp1_val_earlystop_bigbudget.py --name $name --csv $csv --split $split \
    --search-seeds "$@" --out results/g_$tag > logs/$tag.log 2>&1 &
  i=$((i+1))
}
for s in 42 43 44 45 46; do run ECU $ECU random $s; done
for s in 42 43 44;       do run ECU $ECU temporal $s; done
run WUSTL $WUSTL random 42 43 44;   run WUSTL $WUSTL random 45 46
run WUSTL $WUSTL temporal 42 43 44; run WUSTL $WUSTL temporal 45 46
wait
python merge_exp1.py
