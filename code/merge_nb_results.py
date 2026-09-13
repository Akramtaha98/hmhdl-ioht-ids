"""Merges the per-dataset reseeded_splits_nb_test_<name>.json files (written
separately by reseeded_splits_nb_test.py to avoid a write race between the
two concurrent subprocesses) into the single results/reseeded_splits_nb_test.json
that GATES.md's G17 check expects."""
import json
import os

RESULTS_DIR = "/tmp/Paper3/results"
out = {}
for name, slug in [("ECU-IoHT", "ECU-IoHT"), ("WUSTL-EHMS-2020", "WUSTL-EHMS-2020")]:
    path = os.path.join(RESULTS_DIR, f"reseeded_splits_nb_test_{slug}.json")
    if not os.path.exists(path):
        print(f"NOT READY: {path}")
        raise SystemExit(1)
    with open(path) as f:
        out[name] = json.load(f)

out_path = os.path.join(RESULTS_DIR, "reseeded_splits_nb_test.json")
with open(out_path, "w") as f:
    json.dump(out, f, indent=2)
print("Merged into:", out_path)
