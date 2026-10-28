# Phase 4 experiments (IEEE Access / Jurnal Kejuruteraan revision)

| Exp | What it does | Raw output | Manuscript |
|---|---|---|---|
| exp10 | Instrumented reruns of the two time-respecting validation designs ("tail" and "window") on ECU-IoHT and WUSTL-EHMS-2020: per-epoch loss curves, threshold ties, confusion matrices, same-seed repeats (seeds 42-46) | `results/exp10_ECU.json`, `results/exp10_WUSTL.json` | Sec. IV-K, Table XIX, Fig. 5 |
| exp11 | Full tune-and-train procedure repeated on 5 reseeded 70/30 splits (seeds 100-104): LIRS vs random search vs fixed Table IV configuration vs HGB, with the Nadeau-Bengio corrected resampled t-test (k=5, df=4) | `results/exp11_ECU_{a,b,c}.json`, `results/exp11_WUSTL_all.json` | Sec. IV-J, Table XVIII |

Logs: `logs/p4_gpu{0,1,2}.log` (three GPUs run in parallel).

Reproduce the summary numbers (CPU only, needs numpy + scipy):

    python aggregate_exp10.py
    python aggregate_exp11.py

Notes
* The 43.02% temporal accuracy comes from scores tied exactly at the validation threshold under the strict `>` rule (`test_equal_thr` in exp10 results).
* The scripts that generated the raw JSON files (`exp10_*.py`, `exp11_*.py`) are in this folder alongside the aggregation scripts.
