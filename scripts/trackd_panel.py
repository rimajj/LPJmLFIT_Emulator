"""trackd_panel.py — Track D1/D3/D4 (EXECUTION_PLAN.md rev. 2, ADR 0096): run the ORIGINAL model (LPJmL-FIT) on the
fixed global stratified panel (S_D0_panel_blocks.csv, 105 blocks x 10 contiguous orderA cells) under many
climates and four independent members, so that the warming response can be separated from place.

MEMBERS. 1 and 2 = the two existing ground-truth members (their global restart_1999 / restart_2019 files).
3 and 4 = NEW members: each block is spun up from scratch (1000 yr, the production spin-up branch) with
random_seed 3 / 4 — a second seed is a second spin-up (ADR 0041; under restart the seed is inert) — then runs
2000-2019 and writes its own restart_2019.

LEGS (all 2020-2100 from the member's restart_2019, constant CO2 409.63 ppm as in every future ground-truth run):
  <gcm>_<scen>  real ISIMIP3b climate, 5 models x {ssp126, ssp370, ssp585}  (D4; ssp585 and whole models are the
                held-out tests — the plan's synthetic x0.5/x1.5 rescaling is REPLACED by these real scenarios,
                because stylised perturbations do not transfer to real scenarios, R00430)
  ctl_obs       observed GSWP3-W5E5 weather of 1990-2019, years shuffled, recycled to 2100      (D1, primary control)
  ctl_mpi370    MPI-ESM1-2-HR ssp370 weather of 2015-2034, shuffled, recycled to 2100           (D1, same-model control)
  hist          2000-2019 observed weather (members 3/4 need it for their 2019 state; members 1/2 re-run it on the
                panel for a four-member daily spread)
  spinup        members 3/4 only.

CONFIG. Every run is the production Historical config of member 1 (sections I/II = the physics, byte-identical to
the SSP370 config) with only these edits: random_seed, startgrid/endgrid, the input file, the output list, years,
restart paths, and — for the two controls only — fix_climate (iterate.c: years > fix_climate_year read a shuffled
year of the interval). Binary: a snapshot of /home/jamirp/lpjml56fit (source b2e5ca9, the build line the ground truth
ran) with only the writer switches LPJ_IND_ALL_HEIGHTS / LPJ_IND_TRUE_GPP on (inert to the physics, ADR 0130) and
the rung-2 demography hooks explicitly unset.

OUTPUTS per run: ind (all heights, true per-tree GPP), globalflux, monthly npp, vegc, monthly swc, annual
lai_stand / fpc_stand; DAILY prec, transp, evap, interc, runoff, swe, rootmoist, pet, npp, gpp (+ whc_nat) for the
legs in DAILY_LEGS.

JOBS. One SLURM job per (member, leg) runs all 105 blocks side by side on one node (one process per block).
Members 3/4: spinup -> hist -> legs, chained with afterok. Scenario legs wait for the forcing job.

Usage:
  python scripts/trackd_panel.py make   [--members 1 2 3 4] [--legs ...]      # write configs + job files
  python scripts/trackd_panel.py check                                       # lpjcheck one block per (member, leg)
  python scripts/trackd_panel.py submit --forcing-job <jobid>                 # submit everything with dependencies
  python scripts/trackd_panel.py status                                      # completed blocks per (member, leg)
Root: $TRACKD_ROOT/panel (default /p/tmp/jamirp/trackD/panel).
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import shutil
import subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.environ.get("TRACKD_ROOT", "/p/tmp/jamirp/trackD")
PANEL = os.path.join(ROOT, "panel")
GT = "/p/projects/waldspektrum/priesner/clustering/global"
HIST = f"{GT}/Historical/ground_truth/model_output/transient_2000_2019_npatch25_nspinup1000_nspinyear30_random_seed{{m}}"
TEMPLATE = HIST.format(m=1) + "/scripts_for_running_the_model/lpjml_2000_2019.js"
FORCING = os.path.join(ROOT, "forcing")
CO2_CONST = f"{GT}/global_co2_ann_1700_2019_const_2100.txt"
CO2_TRENDY = "/p/projects/lpjml/inputs/co2/global/TRENDY/v12/global_co2_ann_1700_2022.txt"
SRC_ROOT = "/home/jamirp/lpjml56fit"
LPJROOT = os.path.join(ROOT, "cbuild", "lpjml56fit_snapshot")
MODULES = "intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 openssl/3.6.0 netcdf-c curl/8.4.0 expat/2.5.0"
BLOCKS_CSV = os.path.join(REPO, "test", "testitems", "references", "S_D0_panel_blocks.csv")
GCMS = ["gfdl-esm4", "ipsl-cm6a-lr", "mpi-esm1-2-hr", "mri-esm2-0", "ukesm1-0-ll"]
SCENS = ["ssp126", "ssp370", "ssp585"]
SCEN_LEGS = [f"{g}_{s}" for g in GCMS for s in SCENS]
LEGS = SCEN_LEGS + ["ctl_obs", "ctl_mpi370"]
DAILY_LEGS = {
    "hist",
    "mpi-esm1-2-hr_ssp126",
    "mpi-esm1-2-hr_ssp370",
    "mpi-esm1-2-hr_ssp585",
    "ukesm1-0-ll_ssp370",
    "ctl_obs",
}
HIST_FILES = {
    "temp": "temperature_test.clm",
    "prec": "precipitation_test.clm",
    "lwnet": "long_wave_radiation_test.clm",
    "swdown": "short_wave_radiation_test.clm",
    "humid": "humid_test.clm",
}
VARKEY = {"temp": "tas", "prec": "pr", "lwnet": "lwnet", "swdown": "rsds", "humid": "huss"}
CONTROLS = {"ctl_obs": (1990, 2019), "ctl_mpi370": (2015, 2034)}


def blocks():
    with open(BLOCKS_CSV) as f:
        return [(int(r["block"]), int(r["start"]), int(r["end"])) for r in csv.DictReader(f)]


def sub1(pat, rep, s, count=1, flags=0):
    s2, n = re.subn(pat, rep, s, count=count, flags=flags)
    assert n == count, f"pattern found {n}x, expected {count}: {pat}"
    return s2


# ---------------------------------------------------------------- inputs
def forcing_files(leg):
    if leg in ("hist", "spinup", "ctl_obs"):
        return {k: f"{GT}/{v}" for k, v in HIST_FILES.items()}
    gcm, scen = ("mpi-esm1-2-hr", "ssp370") if leg == "ctl_mpi370" else leg.split("_")
    return {
        k: f"{FORCING}/{scen}/{VARKEY[k]}_{gcm}_{scen}_2015-2100_orderA.clm" for k in HIST_FILES
    }


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
    with open(p, "w") as fo:
        fo.write(body)
    return p


# ---------------------------------------------------------------- outputs
def output_list(leg):
    o = [
        '    { "id" : "grid",       "file" : { "fmt" : "cdf", "name" : "output/grid.nc" }},',
        '    { "id" : "ind",        "file" : { "fmt" : "txt", "name" : "output/ind.csv" }},',
        '    { "id" : "globalflux", "file" : { "fmt" : "txt", "name" : "output/globalflux.csv" }},',
        '    { "id" : "vegc",       "file" : { "fmt" : "cdf", "name" : "output/vegc.nc" }},',
        '    { "id" : "swc",        "file" : { "fmt" : "cdf", "name" : "output/mswc.nc" }},',
        '    { "id" : "lai_stand",  "file" : { "fmt" : "cdf", "name" : "output/lai_stand.nc" }},',
        '    { "id" : "fpc_stand",  "file" : { "fmt" : "cdf", "name" : "output/fpc_stand.nc" }},',
    ]
    if (
        leg not in DAILY_LEGS
    ):  # an output id may appear once: daily legs carry daily npp instead of monthly
        o.insert(
            3, '    { "id" : "npp",        "file" : { "fmt" : "cdf", "name" : "output/mnpp.nc" }},'
        )
    if leg in DAILY_LEGS:
        for oid in [
            "prec",
            "transp",
            "evap",
            "interc",
            "runoff",
            "swe",
            "rootmoist",
            "pet",
            "npp",
            "gpp",
        ]:
            o.append(
                f'    {{ "id" : "{oid}", "file" : {{ "fmt" : "cdf", "name" : "output/d_{oid}.nc", '
                f'"timestep" : "daily" }}}},'
            )
        o.append(
            '    { "id" : "whc_nat",    "file" : { "fmt" : "cdf", "name" : "output/whc_nat.nc" }},'
        )
    return "\n".join(o)


# ---------------------------------------------------------------- config
def restart_paths(member, leg, b):
    """(restart to read, restart to write or None) for one block run."""
    own = lambda lg, y: os.path.join(
        PANEL, f"m{member}", lg, f"b{b:03d}", "restart", f"restart_{y}.lpj"
    )  # noqa: E731
    if leg == "spinup":
        return None, own("spinup", 1999)
    if leg == "hist":
        read = (
            HIST.format(m=member) + "/restart/restart_1999.lpj"
            if member in (1, 2)
            else own("spinup", 1999)
        )
        return read, (own("hist", 2019) if member in (3, 4) else None)
    read = (
        HIST.format(m=member) + "/restart/restart_2019.lpj"
        if member in (1, 2)
        else own("hist", 2019)
    )
    return read, None


def make_config(member, leg, b, s, e, inp):
    t = open(TEMPLATE).read()
    t = sub1(r'"random_seed"\s*:\s*\d+', f'"random_seed" : {member}', t)
    t = sub1(r'#include "[^"]*input_2000_2019\.js"', f'#include "{inp}"', t, count=2)
    t = sub1(r'"startgrid"\s*:\s*"all",', f'"startgrid" : {s}, "endgrid" : {e},', t)
    if leg in CONTROLS:
        y0, y1 = CONTROLS[leg]
        t = sub1(
            r'"fix_climate"\s*:\s*false,',
            f'"fix_climate" : true, "fix_climate_year" : 2019, "fix_climate_interval" : [{y0},{y1}], '
            f'"fix_climate_shuffle" : true,',
            t,
        )
    # FROM_RESTART output list
    i0 = t.index('#ifdef FROM_RESTART\n\n  "output" :')
    j0 = t.index("[", i0)
    j1 = t.index("],", j0)
    t = t[: j0 + 1] + "\n" + output_list(leg) + "\n  " + t[j1:]
    read, write = restart_paths(member, leg, b)
    k = t.rindex("#else")
    head, tail = t[:k], t[k:]
    if leg == "spinup":
        head = sub1(
            r'"write_restart_filename"\s*:\s*"restart/restart_1999.lpj"',
            f'"write_restart_filename" : "{write}"',
            head,
        )
    else:
        first, last = (2000, 2019) if leg == "hist" else (2020, 2100)
        tail = sub1(r'"firstyear"\s*:\s*\d+', f'"firstyear": {first}', tail)
        tail = sub1(r'"lastyear"\s*:\s*\d+', f'"lastyear" : {last}', tail)
        tail = sub1(r'"outputyear"\s*:\s*\d+', f'"outputyear": {first}', tail)
        tail = sub1(r'"restart_filename"\s*:\s*"[^"]+"', f'"restart_filename" : "{read}"', tail)
        if write:
            tail = sub1(
                r'"write_restart_filename"\s*:\s*"[^"]+"',
                f'"write_restart_filename" : "{write}"',
                tail,
            )
            tail = sub1(r'"restart_year"\s*:\s*\d+', f'"restart_year": {last}', tail)
        else:
            tail = sub1(r'"write_restart"\s*:\s*true', '"write_restart" : false', tail)
    return head + tail


def leg_dir(member, leg):
    return os.path.join(PANEL, f"m{member}", leg)


def make(members, legs):
    snapshot()
    bl = blocks()
    for member in members:
        mlegs = (
            (["spinup"] if member in (3, 4) else [])
            + ["hist"]
            + [lg for lg in legs if lg not in ("hist", "spinup")]
        )
        for leg in mlegs:
            inp = write_input(leg)
            d = leg_dir(member, leg)
            for b, s, e in bl:
                bd = os.path.join(d, f"b{b:03d}")
                os.makedirs(os.path.join(bd, "output"), exist_ok=True)
                os.makedirs(os.path.join(bd, "restart"), exist_ok=True)
                with open(os.path.join(bd, "lpjml.js"), "w") as fo:
                    fo.write(make_config(member, leg, b, s, e, inp))
            write_job(member, leg, len(bl))
    print(f"configs written under {PANEL}")


def write_job(member, leg, nblk):
    d = leg_dir(member, leg)
    flag = "" if leg == "spinup" else "-DFROM_RESTART"
    time = "06:00:00" if leg == "spinup" else ("01:30:00" if leg == "hist" else "04:00:00")
    j = f"""#!/bin/bash
#SBATCH --job-name=S-D-m{member}-{leg[:14]}
#SBATCH --account=waldspektrum
#SBATCH --partition=standard
#SBATCH --qos=short
#SBATCH --nodes=1
#SBATCH --ntasks={nblk}
#SBATCH --cpus-per-task=1
#SBATCH --time={time}
#SBATCH --output={d}/job.%j.out
source /etc/profile.d/00-modulepath.sh; source /etc/profile.d/modules.sh
module purge; module load {MODULES}
export LPJROOT={LPJROOT}
export LPJ_IND_ALL_HEIGHTS=1 LPJ_IND_TRUE_GPP=1
unset LPJ_RUNG2_DIR LPJ_RUNG2_APPLY_DIR
hostname > {d}/node.txt; lscpu | grep 'Model name' >> {d}/node.txt
echo "member={member} leg={leg} LPJROOT=$LPJROOT md5=$(md5sum $LPJROOT/bin/lpjml | cut -c1-32)"
for bd in {d}/b*/; do
  srun -n1 -c1 --exact --chdir="$bd" $LPJROOT/bin/lpjml {flag} lpjml.js > "$bd/lpjml.log" 2>&1 &
done
wait
ok=0; bad=""
for bd in {d}/b*/; do
  if grep -q "lpjml successfully terminated, 10 grid cells processed." "$bd/lpjml.log"; then ok=$((ok+1)); else bad="$bad $(basename $bd)"; fi
done
echo "completed $ok of {nblk} blocks"; [ -n "$bad" ] && echo "FAILED:$bad"
echo "{{\\"member\\": {member}, \\"leg\\": \\"{leg}\\", \\"ok\\": $ok, \\"n\\": {nblk}}}" > {d}/status.json
[ "$ok" = "{nblk}" ] && echo "=== LEG OK ===" || {{ echo "=== LEG INCOMPLETE ==="; exit 1; }}
"""
    with open(os.path.join(d, "run.jcf"), "w") as fo:
        fo.write(j)


def snapshot():
    """Copy the binary + parameter files once, so a later rebuild of the source tree cannot change this campaign."""
    if os.path.exists(os.path.join(LPJROOT, "bin", "lpjml")):
        return
    os.makedirs(os.path.join(LPJROOT, "bin"), exist_ok=True)
    for x in ("lpjml", "lpjcheck"):
        shutil.copy2(os.path.join(SRC_ROOT, "bin", x), os.path.join(LPJROOT, "bin", x))
    for f in glob.glob(os.path.join(SRC_ROOT, "*.js")):
        shutil.copy2(f, LPJROOT)
    shutil.copytree(os.path.join(SRC_ROOT, "par"), os.path.join(LPJROOT, "par"))
    head = subprocess.run(
        ["git", "-C", SRC_ROOT, "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    md5 = subprocess.run(
        ["md5sum", os.path.join(LPJROOT, "bin", "lpjml")], capture_output=True, text=True
    ).stdout
    with open(os.path.join(LPJROOT, "PROVENANCE.txt"), "w") as fo:
        fo.write(
            f"snapshot of {SRC_ROOT} (HEAD {head} + its uncommitted opt-in patches)\nbin/lpjml md5 {md5}"
        )


def check():
    """lpjcheck every (member, leg) whose restart already exists (members 1/2, and the spin-ups); for the later legs
    of members 3/4 (their restarts do not exist yet) assert the config equals member 1's except the seed and the
    restart paths."""
    env = dict(os.environ, LPJROOT=LPJROOT)

    def norm(path):
        r = subprocess.run(
            ["cpp", "-P", "-DFROM_RESTART", f"-I{LPJROOT}", path], capture_output=True, text=True
        )
        return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]

    for d in sorted(glob.glob(os.path.join(PANEL, "m*", "*"))):
        bd = os.path.join(d, "b000")
        if not os.path.isdir(bd):
            continue
        leg, member = os.path.basename(d), int(os.path.basename(os.path.dirname(d))[1:])
        if member in (1, 2) or leg == "spinup":
            args = [os.path.join(LPJROOT, "bin", "lpjcheck")] + (
                [] if leg == "spinup" else ["-DFROM_RESTART"]
            )
            r = subprocess.run(args + ["lpjml.js"], cwd=bd, capture_output=True, text=True, env=env)
            last = (r.stdout + r.stderr).strip().splitlines()[-1][:100]
            print(f"{d.replace(PANEL + '/', ''):32s} lpjcheck rc={r.returncode} {last}")
        else:
            a, b = (
                norm(os.path.join(PANEL, "m1", leg, "b000", "lpjml.js")),
                norm(os.path.join(bd, "lpjml.js")),
            )
            diff = [(x, y) for x, y in zip(a, b, strict=True) if x != y]
            allowed = all(
                re.search(r"random_seed|restart_filename|write_restart|restart_year", x)
                for x, _ in diff
            )
            print(
                f"{d.replace(PANEL + '/', ''):32s} vs m1: {len(diff)} differing lines, only seed/restart: {allowed}"
            )


def submit(forcing_job):
    jobs = {}

    def sb(member, leg, dep):
        p = os.path.join(leg_dir(member, leg), "run.jcf")
        cmd = ["sbatch"] + ([f"--dependency=afterok:{dep}"] if dep else []) + [p]
        jid = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.split()[-1]
        jobs[f"m{member}/{leg}"] = jid
        return jid

    for member in (1, 2, 3, 4):
        if not os.path.isdir(leg_dir(member, "hist")):
            continue
        pre = sb(member, "spinup", None) if member in (3, 4) else None
        h = sb(member, "hist", pre)
        for leg in LEGS:
            if not os.path.isdir(leg_dir(member, leg)):
                continue
            deps = [
                x
                for x in (
                    h if member in (3, 4) else None,
                    forcing_job if leg in SCEN_LEGS else None,
                )
                if x
            ]
            sb(member, leg, ":".join(deps) if deps else None)
    with open(os.path.join(PANEL, "jobs.json"), "w") as fo:
        json.dump(jobs, fo, indent=1)
    print(json.dumps(jobs, indent=1))


def status():
    for d in sorted(glob.glob(os.path.join(PANEL, "m*", "*"))):
        st = os.path.join(d, "status.json")
        n = len(glob.glob(os.path.join(d, "b*")))
        ok = json.load(open(st))["ok"] if os.path.exists(st) else "-"
        print(f"{d.replace(PANEL + '/', ''):32s} {ok}/{n}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["make", "check", "submit", "status"])
    ap.add_argument("--members", type=int, nargs="+", default=[1, 2, 3, 4])
    ap.add_argument("--legs", nargs="+", default=LEGS)
    ap.add_argument("--forcing-job", default=None)
    a = ap.parse_args()
    {
        "make": lambda: make(a.members, a.legs),
        "check": check,
        "submit": lambda: submit(a.forcing_job),
        "status": status,
    }[a.stage]()


if __name__ == "__main__":
    main()
