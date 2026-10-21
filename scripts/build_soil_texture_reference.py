#!/usr/bin/env python3
"""Per-soil-code texture table of the panel build, for the daily network's soil input (ADR 0348).

Reads the panel binary snapshot's ``par/soil_20m.js`` through ``cpp -P`` exactly as LPJmL does
(as ``build_mort_params_reference.py::cpp_json``) and maps the input soil codes onto it with the
run's own ``soilmap`` (``scripts/explore_panel_runs.py``): code k is the k-th name of
``[null, "clay", ..., "rock and ice"]``, looked up in ``soilpar`` by name (``newgrid.c:449``).

Writes ``config/soil_texture_by_code.csv`` (code, name, sand, silt, clay,
Ks mm/h, Sf mm, w_pwp, w_fc, w_sat). ``CHECK=1`` verifies the committed file instead of writing it.
"""

import csv
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LPJROOT = Path("/p/tmp/jamirp/trackD/cbuild/lpjml56fit_snapshot")  # the panel binary snapshot
SOILMAP = [None, "clay", "silty clay", "sandy clay", "clay loam", "silty clay loam",
           "sandy clay loam", "loam", "silt loam", "sandy loam", "silt", "loamy sand", "sand",
           "rock and ice"]  # fmt: skip
OUT = ROOT / "config" / "soil_texture_by_code.csv"
COLS = ["sand", "silt", "clay", "Ks", "Sf", "w_pwp", "w_fc", "w_sat"]


def cpp_json(path):
    """As ``build_mort_params_reference.py::cpp_json`` (``cpp -P``, strip trailing commas, wrap in
    braces), plus the bare trailing-dot numbers (``200.``) this file uses and ``json`` rejects."""
    s = subprocess.run(["cpp", "-P", str(path)], capture_output=True, text=True, check=True,
                       stdin=subprocess.DEVNULL).stdout.strip().rstrip(",")  # fmt: skip
    s = re.sub(r",(\s*[}\]])", r"\1", s)
    s = re.sub(r"(\d)\.(?=\s*[,\]}\s])", r"\1.0", s)
    return json.loads("{" + s + "}")


def rows():
    parsed = cpp_json(LPJROOT / "par" / "soil_20m.js")
    byname = {s["name"]: s for s in parsed["soilpar"]}
    # the soilmap is matched to soilpar BY NAME (soilpar also holds an unmapped "clay (light)")
    assert all(n in byname for n in SOILMAP[1:]), "a soilmap name is missing from soilpar"
    return [
        {"code": k, "name": n, **{c: float(byname[n][c]) for c in COLS}}
        for k, n in enumerate(SOILMAP)
        if n is not None
    ]


def main():
    rs = rows()
    if os.environ.get("CHECK"):
        with open(OUT) as f:
            got = list(csv.DictReader(f))
        assert len(got) == len(rs)
        for g, r in zip(got, rs, strict=True):
            assert int(g["code"]) == r["code"] and g["name"] == r["name"]
            assert all(float(g[c]) == r[c] for c in COLS), (g, r)
        print(f"OK: {OUT} matches {LPJROOT}/par/soil_20m.js")
        return
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["code", "name", *COLS], lineterminator="\n")
        w.writeheader()
        w.writerows(rs)
    print(f"wrote {OUT} ({len(rs)} soil codes)")


if __name__ == "__main__":
    main()
