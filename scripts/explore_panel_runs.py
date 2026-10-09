#!/usr/bin/env python3
"""explore_panel_runs.py -- LINE X: MORE DATA for the panel venue, produced because the measured data curves say it
still helps (explore_panel_a7.py `curves_seen`, 2026-10-09: pass on a held-out climate model rises 0.114 -> 0.137 ->
0.148 -> 0.162 with 1..4 training models, 0.097 -> 0.152 -> 0.162 with 1..3 training runs, and drops 0.162 -> 0.142
without the hottest scenario -- no curve flat at its last step). Owner, 2026-10-09: "do everything you need ...
including producing more data if that is mandatory and we have solid results that support the assumption that more
data gives the breakthrough".

WHAT (same panel, same binary, same config as line S's campaign -- scripts/trackd_panel.py on line/S, ADR 0246 --
whose configuration code is COPIED here unchanged in substance; nothing of line S is edited or written):
  * five more ISIMIP3b climate models x {ssp126, ssp370, ssp585}: CanESM5, CNRM-CM6-1, CNRM-ESM2-1, EC-Earth3, MIROC6
    (orderA forcing via LPJmL's regridclm, gated by re-deriving the ground-truth MPI ssp370 tas file byte-identically);
  * for members 1-4 (1/2 from the global restart_2019, 3/4 from line S's panel hist restart_2019, read-only);
  * two NEW independent members 5 and 6: own 1000-yr spin-up per block with random_seed 5 / 6, 2000-2019, then all 15
    old + 15 new climate legs and ctl_obs (its daily precipitation is written so the drawn weather years can be
    recovered exactly, explore_panel_lstm.ctl_sequence).
DIFFERENCES from line S's runs, all inert to the physics: LPJ_IND_ALL_HEIGHTS is NOT set (the `ind` table holds the
production population, trees > 5 m -- the only one any score reads; ~1/4 of the rows), no daily outputs except prec on
ctl_obs, no lai/fpc/swc NetCDFs beyond what the collector needs. One SLURM job per member runs its legs one after another
on ONE node (105 blocks side by side), followed by a collector job (line S's scripts/trackd_collect_panel.py, run
unchanged with --panel/--out pointing here).
ROOT: /p/tmp/jamirp/xpanel_runs (raw, scratch) ; tables: /p/projects/open/Jamir/esm_land_emulator_data/xpanel_runs.

PREDICTION, written before any of these runs exists (tested by explore_panel_a7.py once the data is in):
  A7r on the 5 ORIGINAL held-out models' ssp370 (test m4, as in `seen`), trained on the other 9 models x 3 scenarios
  + ctl_obs and runs m1, m2, m3, m5, m6: mean pass >= 0.162 + 0.02 (from the curves: ~1.2 doublings of models at
  +0.013-0.026 each, ~0.7 doublings of runs at ~+0.017); the bar (0.5 x ceiling_mean AND above the lookup) passed
  on >= 12 of the 13 HG test cases. FALSIFIER: gain < 0.01 -> the data curves saturate here and more panel data is not
  the lever.

Usage: python scripts/explore_panel_runs.py forcing|make|check|submit|status
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = "/p/tmp/jamirp/xpanel_runs"
PANEL = os.path.join(ROOT, "panel")
FORCING = os.path.join(ROOT, "forcing")
TABLES = "/p/projects/open/Jamir/esm_land_emulator_data/xpanel_runs"
S_PANEL = "/p/tmp/jamirp/trackD/panel"  # line S's runs: read-only (m3/m4 hist restarts)
S_FORCING = "/p/tmp/jamirp/trackD/forcing"  # line S's orderA forcing for the first five models: read-only
S_LPJROOT = "/p/tmp/jamirp/trackD/cbuild/lpjml56fit_snapshot"  # the panel binary snapshot: read-only
S_COLLECT = "/p/projects/open/Jamir/wt-S/scripts/trackd_collect_panel.py"
GT = "/p/projects/waldspektrum/priesner/clustering/global"
HIST = f"{GT}/Historical/ground_truth/model_output/transient_2000_2019_npatch25_nspinup1000_nspinyear30_random_seed{{m}}"
TEMPLATE = HIST.format(m=1) + "/scripts_for_running_the_model/lpjml_2000_2019.js"
CO2_CONST = f"{GT}/global_co2_ann_1700_2019_const_2100.txt"
CO2_TRENDY = "/p/projects/lpjml/inputs/co2/global/TRENDY/v12/global_co2_ann_1700_2022.txt"
MODULES = "intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 openssl/3.6.0 netcdf-c curl/8.4.0 expat/2.5.0"
BLOCKS_CSV = os.path.join(REPO, "test", "testitems", "references", "S_D0_panel_blocks.csv")
OLD_GCMS = ["gfdl-esm4", "ipsl-cm6a-lr", "mpi-esm1-2-hr", "mri-esm2-0", "ukesm1-0-ll"]
NEW_GCMS = {"canesm5": "CanESM5", "cnrm-cm6-1": "CNRM-CM6-1", "cnrm-esm2-1": "CNRM-ESM2-1", "ec-earth3": "EC-Earth3",
            "miroc6": "MIROC6"}
SCENS = ["ssp126", "ssp370", "ssp585"]
OLD_LEGS = [f"{g}_{s}" for g in OLD_GCMS for s in SCENS]
NEW_LEGS = [f"{g}_{s}" for g in NEW_GCMS for s in SCENS]
NEW_MEMBERS = (5, 6)
HIST_FILES = {"temp": "temperature_test.clm", "prec": "precipitation_test.clm", "lwnet": "long_wave_radiation_test.clm",
              "swdown": "short_wave_radiation_test.clm", "humid": "humid_test.clm"}
VARKEY = {"temp": "tas", "prec": "pr", "lwnet": "lwnet", "swdown": "rsds", "humid": "huss"}


def blocks():
    with open(BLOCKS_CSV) as f:
        return [(int(r["block"]), int(r["start"]), int(r["end"])) for r in csv.DictReader(f)]


def sub1(pat, rep, s, count=1, flags=0):
    s2, n = re.subn(pat, rep, s, count=count, flags=flags)
    assert n == count, f"pattern found {n}x, expected {count}: {pat}"
    return s2


def legs_of(member):
    if member in NEW_MEMBERS:
        return ["spinup", "hist", *OLD_LEGS, *NEW_LEGS, "ctl_obs"]
    return list(NEW_LEGS)


# ---------------------------------------------------------------- forcing
def stage_forcing(_a):
    """Job file: regridclm of the five new models (gate first), output under FORCING/<scen>/."""
    os.makedirs(os.path.join(ROOT, "_jobs"), exist_ok=True)
    gl = " ".join(NEW_GCMS.values())
    j = f"""#!/bin/bash
#SBATCH --job-name=X-xp-regrid
#SBATCH --account=waldspektrum
#SBATCH --partition=standard
#SBATCH --qos=short
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=06:00:00
#SBATCH --output={REPO}/logs/X-xp-regrid.%j.out
set -euo pipefail
source /etc/profile.d/00-modulepath.sh; source /etc/profile.d/modules.sh
module purge; module load intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 netcdf-c curl/8.4.0 expat/2.5.0
export LD_LIBRARY_PATH=/p/system/packages_rhel9/libraries/json-c/0.13.1/lib:${{LD_LIBRARY_PATH:-}}
export PATH=/p/projects/biodiversity/bloh/git/master_bsq/bin:$PATH
GRID_OLD=/p/projects/biodiversity/input_VERSION2/grid.bin
GRID_NEW={GT}/soil_code_test.grid.clm
SRC=/p/projects/lpjml/input/scenarios/ISIMIP3bv2
OUT={FORCING}
mkdir -p $OUT/ssp126 $OUT/ssp370 $OUT/ssp585 $OUT/_gate
echo "=== GATE: re-derive MPI-ESM1-2-HR ssp370 tas orderA ==="
regridclm $GRID_OLD $GRID_NEW $SRC/ssp370/MPI-ESM1-2-HR/tas_mpi-esm1-2-hr_ssp370_2015-2100.clm $OUT/_gate/tas_gate.clm
cmp -s $OUT/_gate/tas_gate.clm {GT}/ssp370/tas_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm && echo "GATE PASS" || {{ echo "GATE FAIL"; exit 3; }}
rm -f $OUT/_gate/tas_gate.clm
jobs=$(mktemp)
for sc in {" ".join(SCENS)}; do for g in {gl}; do gl=$(echo $g | tr 'A-Z' 'a-z'); for v in tas pr lwnet rsds huss; do
  dst=$OUT/$sc/${{v}}_${{gl}}_${{sc}}_2015-2100_orderA.clm; [ -s $dst ] && continue
  fl=""; [ $v = huss ] && fl="-size4"
  echo "regridclm $fl $GRID_OLD $GRID_NEW $SRC/$sc/$g/${{v}}_${{gl}}_${{sc}}_2015-2100.clm $dst.part && mv $dst.part $dst" >> $jobs
done; done; done
echo "=== converting $(wc -l < $jobs) files ==="
xargs -P 8 -I{{}} bash -c '{{}}' < $jobs; rm -f $jobs
fail=0
for sc in {" ".join(SCENS)}; do for g in {gl}; do gl=$(echo $g | tr 'A-Z' 'a-z'); for v in tas pr lwnet rsds huss; do
  f=$OUT/$sc/${{v}}_${{gl}}_${{sc}}_2015-2100_orderA.clm; s=$SRC/$sc/$g/${{v}}_${{gl}}_${{sc}}_2015-2100.clm
  [ -s $f ] || {{ echo MISSING $f; fail=1; continue; }}
  [ "$(stat -L -c %s $f)" = "$(stat -L -c %s $s)" ] || {{ echo SIZE MISMATCH $f; fail=1; }}
done; done; done
[ $fail = 0 ] && {{ echo "ALL FORCING PRESENT"; touch $OUT/_done; }} || {{ echo "FORCING INCOMPLETE"; exit 4; }}
echo "=== JOB DONE ==="
"""
    p = os.path.join(ROOT, "_jobs", "regrid.jcf")
    open(p, "w").write(j)
    print(p)


def forcing_files(leg):
    if leg in ("hist", "spinup", "ctl_obs"):
        return {k: f"{GT}/{v}" for k, v in HIST_FILES.items()}
    gcm, scen = leg.split("_")
    base = S_FORCING if gcm in OLD_GCMS else FORCING
    return {k: f"{base}/{scen}/{VARKEY[k]}_{gcm}_{scen}_2015-2100_orderA.clm" for k in HIST_FILES}


def write_input(leg):
    os.makedirs(os.path.join(PANEL, "inputs"), exist_ok=True)
    co2 = CO2_TRENDY if leg in ("hist", "spinup") else CO2_CONST
    f = forcing_files(leg)
    body = f'''"inpath" : "{GT}/",
"soilmap" : [null,"clay", "silty clay", "sandy clay", "clay loam", "silty clay loam",
             "sandy clay loam", "loam", "silt loam", "sandy loam", "silt",
             "loamy sand", "sand", "rock and ice"],
"input" :
{{
  "soil" :      {{ "fmt" : "raw", "name" : "soil_code_test.soil.bin"}},
  "coord" :     {{ "fmt" : "clm", "name" : "soil_code_test.grid.clm"}},
  "soildepth" : {{ "fmt" : "clm", "name" : "soil_depth_test.clm"}},
  "temp" :      {{ "fmt" : "clm", "name" : "{f["temp"]}"}},
  "prec" :      {{ "fmt" : "clm", "name" : "{f["prec"]}"}},
  "lwnet" :     {{ "fmt" : "clm", "name" : "{f["lwnet"]}"}},
  "swdown" :    {{ "fmt" : "clm", "name" : "{f["swdown"]}"}},
  "humid" :     {{ "fmt" : "clm", "name" : "{f["humid"]}"}},
  "co2" :       {{ "fmt" : "txt", "name" : "{co2}"}},
}},
'''
    p = os.path.join(PANEL, "inputs", f"{leg}.js")
    open(p, "w").write(body)
    return p


def output_list(leg):
    o = ['    { "id" : "grid",       "file" : { "fmt" : "cdf", "name" : "output/grid.nc" }},',
         '    { "id" : "ind",        "file" : { "fmt" : "txt", "name" : "output/ind.csv" }},',
         '    { "id" : "globalflux", "file" : { "fmt" : "txt", "name" : "output/globalflux.csv" }},',
         '    { "id" : "vegc",       "file" : { "fmt" : "cdf", "name" : "output/vegc.nc" }},',
         '    { "id" : "swc",        "file" : { "fmt" : "cdf", "name" : "output/mswc.nc" }},',
         '    { "id" : "lai_stand",  "file" : { "fmt" : "cdf", "name" : "output/lai_stand.nc" }},']
    if leg == "ctl_obs":
        o.append('    { "id" : "prec", "file" : { "fmt" : "cdf", "name" : "output/d_prec.nc", "timestep" : "daily" }},')
    return "\n".join(o)


def restart_paths(member, leg, b):
    own = lambda lg, y: os.path.join(PANEL, f"m{member}", lg, f"b{b:03d}", "restart", f"restart_{y}.lpj")  # noqa: E731
    if leg == "spinup":
        return None, own("spinup", 1999)
    if leg == "hist":
        return own("spinup", 1999), own("hist", 2019)  # new members only
    if member in (1, 2):
        return HIST.format(m=member) + "/restart/restart_2019.lpj", None
    if member in (3, 4):
        return os.path.join(S_PANEL, f"m{member}", "hist", f"b{b:03d}", "restart", "restart_2019.lpj"), None
    return own("hist", 2019), None


def make_config(member, leg, b, s, e, inp):
    t = open(TEMPLATE).read()
    t = sub1(r'"random_seed"\s*:\s*\d+', f'"random_seed" : {member}', t)
    t = sub1(r'#include "[^"]*input_2000_2019\.js"', f'#include "{inp}"', t, count=2)
    t = sub1(r'"startgrid"\s*:\s*"all",', f'"startgrid" : {s}, "endgrid" : {e},', t)
    if leg == "ctl_obs":
        t = sub1(r'"fix_climate"\s*:\s*false,', '"fix_climate" : true, "fix_climate_year" : 2019, '
                 '"fix_climate_interval" : [1990,2019], "fix_climate_shuffle" : true,', t)
    i0 = t.index('#ifdef FROM_RESTART\n\n  "output" :')
    j0 = t.index("[", i0)
    j1 = t.index("],", j0)
    t = t[: j0 + 1] + "\n" + output_list(leg) + "\n  " + t[j1:]
    read, write = restart_paths(member, leg, b)
    k = t.rindex("#else")
    head, tail = t[:k], t[k:]
    if leg == "spinup":
        head = sub1(r'"write_restart_filename"\s*:\s*"restart/restart_1999.lpj"', f'"write_restart_filename" : "{write}"',
                    head)
    else:
        first, last = (2000, 2019) if leg == "hist" else (2020, 2100)
        tail = sub1(r'"firstyear"\s*:\s*\d+', f'"firstyear": {first}', tail)
        tail = sub1(r'"lastyear"\s*:\s*\d+', f'"lastyear" : {last}', tail)
        tail = sub1(r'"outputyear"\s*:\s*\d+', f'"outputyear": {first}', tail)
        tail = sub1(r'"restart_filename"\s*:\s*"[^"]+"', f'"restart_filename" : "{read}"', tail)
        if write:
            tail = sub1(r'"write_restart_filename"\s*:\s*"[^"]+"', f'"write_restart_filename" : "{write}"', tail)
            tail = sub1(r'"restart_year"\s*:\s*\d+', f'"restart_year": {last}', tail)
        else:
            tail = sub1(r'"write_restart"\s*:\s*true', '"write_restart" : false', tail)
    return head + tail


def stage_make(a):
    if not os.path.exists(os.path.join(ROOT, "cbuild")):
        os.makedirs(ROOT, exist_ok=True)
        os.symlink(os.path.dirname(S_LPJROOT), os.path.join(ROOT, "cbuild"))  # the collector reads PROVENANCE here
    bl = blocks()
    for member in a.members:
        for leg in legs_of(member):
            inp = write_input(leg)
            for b, s, e in bl:
                bd = os.path.join(PANEL, f"m{member}", leg, f"b{b:03d}")
                os.makedirs(os.path.join(bd, "output"), exist_ok=True)
                os.makedirs(os.path.join(bd, "restart"), exist_ok=True)
                open(os.path.join(bd, "lpjml.js"), "w").write(make_config(member, leg, b, s, e, inp))
        write_job(member, len(bl))
    print(f"configs under {PANEL}")


def write_job(member, nblk):
    legs = legs_of(member)
    hours = 8 if member in NEW_MEMBERS else 4
    lines = []
    waited = False
    for leg in legs:
        if leg in NEW_LEGS and not waited:
            waited = True
            lines.append(f'''
for i in $(seq 1 240); do [ -f {FORCING}/_done ] && break; sleep 60; done
[ -f {FORCING}/_done ] || {{ echo "forcing never arrived"; exit 2; }}''')
        d = os.path.join(PANEL, f"m{member}", leg)
        flag = "" if leg == "spinup" else "-DFROM_RESTART"
        lines.append(f'''
d={d}
if [ -f $d/status.json ] && grep -q '"ok": {nblk}' $d/status.json; then echo "{leg} already done"; else
for bd in $d/b*/; do srun -n1 -c1 --exact --chdir="$bd" $LPJROOT/bin/lpjml {flag} lpjml.js > "$bd/lpjml.log" 2>&1 & done
wait
ok=0; for bd in $d/b*/; do grep -q "lpjml successfully terminated, 10 grid cells processed." "$bd/lpjml.log" && ok=$((ok+1)); done
echo "{{\\"member\\": {member}, \\"leg\\": \\"{leg}\\", \\"ok\\": $ok, \\"n\\": {nblk}}}" > $d/status.json
echo "$(date +%T) {leg}: $ok of {nblk} blocks"
{"[ $ok = " + str(nblk) + " ] || { echo 'spin-up/hist incomplete: stopping'; exit 1; }" if leg in ("spinup", "hist") else ""}
fi''')
    j = f"""#!/bin/bash
#SBATCH --job-name=X-xp-m{member}
#SBATCH --account=waldspektrum
#SBATCH --partition=standard
#SBATCH --qos=short
#SBATCH --nodes=1
#SBATCH --ntasks={nblk}
#SBATCH --cpus-per-task=1
#SBATCH --time={hours:02d}:00:00
#SBATCH --output={REPO}/logs/X-xp-m{member}.%j.out
source /etc/profile.d/00-modulepath.sh; source /etc/profile.d/modules.sh
module purge; module load {MODULES}
export LPJROOT={S_LPJROOT}
export LPJ_IND_TRUE_GPP=1
unset LPJ_IND_ALL_HEIGHTS LPJ_RUNG2_DIR LPJ_RUNG2_APPLY_DIR
hostname; lscpu | grep 'Model name'
echo "member={member} LPJROOT=$LPJROOT md5=$(md5sum $LPJROOT/bin/lpjml | cut -c1-32)"
{"".join(lines)}
echo "=== JOB DONE member={member} ==="
"""
    os.makedirs(os.path.join(ROOT, "_jobs"), exist_ok=True)
    open(os.path.join(ROOT, "_jobs", f"run_m{member}.jcf"), "w").write(j)
    col = f"""#!/bin/bash
#SBATCH --job-name=X-xp-col-m{member}
#SBATCH --account=waldspektrum
#SBATCH --partition=standard
#SBATCH --qos=short
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=200G
#SBATCH --time=06:00:00
#SBATCH --output={REPO}/logs/X-xp-col-m{member}.%j.out
export POLARS_MAX_THREADS=16
for leg in {" ".join(lg for lg in legs if lg != "spinup")}; do
  st={PANEL}/m{member}/$leg/status.json
  if [ -f {TABLES}/m{member}/$leg/manifest.json ]; then continue; fi
  if [ -f $st ] && grep -q '"ok": {nblk}' $st; then
    /home/jamirp/.conda/envs/py311_new/bin/python {S_COLLECT} {member} $leg --panel {PANEL} --out {TABLES} || echo "COLLECT FAILED $leg"
  else echo "SKIP $leg (incomplete)"; fi
done
echo "=== JOB DONE ==="
"""
    open(os.path.join(ROOT, "_jobs", f"collect_m{member}.jcf"), "w").write(col)


def stage_check(_a):
    env = dict(os.environ, LPJROOT=S_LPJROOT)
    src = "source /etc/profile.d/00-modulepath.sh; source /etc/profile.d/modules.sh; module purge; module load " + MODULES
    for d in sorted(glob.glob(os.path.join(PANEL, "m*", "*"))):
        bd = os.path.join(d, "b000")
        leg, member = os.path.basename(d), int(os.path.basename(os.path.dirname(d))[1:])
        read, _ = restart_paths(member, leg, 0) if leg != "spinup" else (None, None)
        if read and not os.path.exists(read):
            print(f"{d.replace(PANEL + '/', ''):34s} restart not yet produced (chained) -- config parse only")
            flag = "-DFROM_RESTART"
            r = subprocess.run(["cpp", "-P", flag, f"-I{S_LPJROOT}", "lpjml.js"], cwd=bd, capture_output=True, text=True)
            print("   cpp rc", r.returncode)
            continue
        flag = "" if leg == "spinup" else "-DFROM_RESTART"
        cmd = f"{src}; {S_LPJROOT}/bin/lpjcheck {flag} lpjml.js"
        r = subprocess.run(["bash", "-c", cmd], cwd=bd, capture_output=True, text=True, env=env)
        last = (r.stdout + r.stderr).strip().splitlines()[-1][:110] if (r.stdout + r.stderr).strip() else ""
        print(f"{d.replace(PANEL + '/', ''):34s} lpjcheck rc={r.returncode} {last}")


def stage_submit(a):
    jobs = {}
    for member in a.members:
        dep = [f"--dependency=afterok:{a.forcing_job}"] if a.forcing_job else []
        # --nodes=1-105: the one-node pin matters only for reproducing an existing run row by row (CLAUDE.md sec. 3);
        # these are NEW runs, and a whole free node waited ~3 days in the queue (2026-10-09)
        run = subprocess.run(["sbatch", "--parsable", "--nodes=1-105", *dep,
                              os.path.join(ROOT, "_jobs", f"run_m{member}.jcf")],
                             capture_output=True, text=True, check=True).stdout.strip()
        col = subprocess.run(["sbatch", "--parsable", f"--dependency=afterany:{run}",
                              os.path.join(ROOT, "_jobs", f"collect_m{member}.jcf")],
                             capture_output=True, text=True, check=True).stdout.strip()
        jobs[f"m{member}"] = {"run": run, "collect": col}
    f = os.path.join(ROOT, "jobs.json")
    old = json.load(open(f)) if os.path.exists(f) else {}
    old.update(jobs)
    json.dump(old, open(f, "w"), indent=1)
    print(json.dumps(jobs, indent=1))


def stage_status(_a):
    for d in sorted(glob.glob(os.path.join(PANEL, "m*", "*"))):
        st = os.path.join(d, "status.json")
        ok = json.load(open(st))["ok"] if os.path.exists(st) else "-"
        coll = os.path.exists(os.path.join(TABLES, os.path.relpath(d, PANEL), "manifest.json"))
        print(f"{d.replace(PANEL + '/', ''):34s} {ok}/105 {'collected' if coll else ''}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["forcing", "make", "check", "submit", "status"])
    ap.add_argument("--members", type=int, nargs="+", default=[1, 2, 3, 4, 5, 6])
    ap.add_argument("--forcing-job", default=None)
    a = ap.parse_args()
    {"forcing": stage_forcing, "make": stage_make, "check": stage_check, "submit": stage_submit,
     "status": stage_status}[a.stage](a)
