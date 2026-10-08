"""trackd_convert_germany.py — convert the Track-D2 Germany re-runs (scripts/trackd_germany_rerun.py) to parquet with
LINE X's own converter (scripts/explore_de_convert.py, used unchanged), so the result has exactly the layout,
dtypes, row order and gates of the production tables line X already reads.

Only the converter's paths and its member list are redirected:
  source   /p/tmp/jamirp/trackD/germany_rh/<GCM>_<scen>_s<seed>/output/ind.csv   (2045-2100, ALL heights)
  output   /p/projects/open/Jamir/esm_land_emulator_data/trackD/germany_rh/ind/<GCM>/<scen>/s<seed>/w2045/cb=NN/
           (+ ind_dev/, _gates/, _census/, _gates.csv beside it)
The window label is `w2045` (one file covers 2045-2100). Unlike the production tables the rows include the trees
<= 5 m (filter Height > 5 for the production format) and 2045-2070 now has a tree table at all.

Usage:  python scripts/trackd_convert_germany.py list | run <idx> | collect
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_convert as cv  # noqa: E402

RUNS = "/p/tmp/jamirp/trackD/germany_rh"
OUT = "/p/projects/open/Jamir/esm_land_emulator_data/trackD/germany_rh"
cv.OUT_ROOT = f"{OUT}/ind"
cv.DEV_ROOT = f"{OUT}/ind_dev"
cv.GATE_DIR = f"{cv.OUT_ROOT}/_gates"
cv.CENSUS_DIR = f"{cv.OUT_ROOT}/_census"
cv.DUPKEY_DIR = f"{cv.OUT_ROOT}/_dupkeys"
cv.GATES_CSV = f"{cv.OUT_ROOT}/_gates.csv"


def manifest() -> list[dict]:
    out = []
    for gcm in ("MPI-ESM1-2-HR", "ACCESS-CM2"):
        for scen in ("ssp126", "ssp245", "ssp370"):
            for seed in (1, 2):
                member = f"{gcm}_{scen}_s{seed}_w2045"
                out.append(dict(
                    idx=len(out), gcm=gcm, scen=scen, seed=seed, window="w2045",
                    src=f"{RUNS}/{gcm}_{scen}_s{seed}/output/ind.csv", member=member,
                    out_dir=f"{cv.OUT_ROOT}/{gcm}/{scen}/s{seed}/w2045",
                    dev_file=f"{cv.DEV_ROOT}/{member}.parquet",
                    gate_json=f"{cv.GATE_DIR}/{member}.json",
                    census_file=f"{cv.CENSUS_DIR}/{member}.parquet",
                ))  # fmt: skip
    return out


cv.manifest = manifest

if __name__ == "__main__":
    for d in (cv.OUT_ROOT, cv.DEV_ROOT, cv.GATE_DIR, cv.CENSUS_DIR, cv.DUPKEY_DIR):
        os.makedirs(d, exist_ok=True)
    stage = sys.argv[1]
    if stage == "list":
        for m in manifest():
            print(m["idx"], m["member"], m["src"])
    elif stage == "run":
        sys.exit(cv.run(int(sys.argv[2])))
    elif stage == "collect":
        cv.collect()
