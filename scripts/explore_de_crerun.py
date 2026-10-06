"""explore_de_crerun.py — LINE X, Germany emulator: re-run the ORIGINAL model (LPJmL-FIT) for a contiguous cell
range of one Germany production member, with the `ind` table written for EVERY tree (incl. the < 5 m saplings
the production output never prints).

Owner, 2026-10-05: "if you need the sapling data from trees below 5 m, just make new simulations for the cells you
need, where you write out the output you need".

Binary: /p/tmp/jamirp/X_de/cbuild/lpjml_dec2025 = the LPJmL-FIT source at commit fcd3a30 (2025-12-17, the build
every Dec-2025 production segment ran: log banner "Version 5.6.004 (Dec 17 2025)") + ONE opt-in writer switch,
LPJ_IND_ALL_HEIGHTS (cbuild/dec2025_ind_all_heights.patch; inert unless the env var is set). LPJROOT points at
that clone, so the parameter files are the ones committed with that source (byte-identical to the live tree's
param_lpjmlfit.js / par/lpjparam_fit.js / par/pft_lpjmlfit.js / par/soil_20m.js / lpjmlfit.js).
⚠ The ssp245 segments ran a Feb-2026 build (inheritance fix b2e5ca9) — do NOT re-run ssp245 with this binary.

Config: the production config of the member, unchanged except (1) "startgrid"/"endgrid" = the cell range, (2) the
run years / output year / restart file / no restart writing, (3) the output list reduced to `ind` + `globalflux`
(writer-only changes). Decomposition: the production runs put 9067 cells on 2048 tasks = the first 875 tasks get
5 cells, the rest 4; a range that starts at 0 and ends at 5k-1 (k <= 875) on k tasks reproduces the production
task -> cell assignment exactly (ADR 0041: a subset re-run's trajectory can depend on the decomposition).

Usage:
  python explore_de_crerun.py make --gcm MPI-ESM1-2-HR --scen ssp370 --seed 2 --start 0 --end 1999 --ntasks 400 \
      --first 2015 --last 2016 --tag gate [--time 01:00:00] [--submit]
  -> /p/tmp/jamirp/X_de/crerun/<gcm>_<scen>_s<seed>_c<start>-<end>_<first>-<last>_<tag>/{lpjml.js, run.jcf, output/}
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess

PROD = "/p/projects/waldspektrum/data/LPJmLFIT/productionruns_jamir"
XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
LPJROOT = os.path.join(XDE, "cbuild", "lpjml_dec2025")
MODULES = "intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 openssl/3.6.0 netcdf-c curl/8.4.0 expat/2.5.0"


def prod_config(gcm, scen, seed):
    d = os.path.join(PROD, gcm, scen, f"random_seed_{seed}")
    f = (os.path.join(d, f"lpjml_{gcm}_Historical.js") if scen == "Historical"
         else os.path.join(d, f"lpjml_2044_{gcm}_{scen}.js"))
    assert os.path.exists(f), f
    return d, f


def sub1(pat, rep, s, flags=0):
    s2, n = re.subn(pat, rep, s, count=1, flags=flags)
    assert n == 1, f"pattern not found exactly once: {pat}"
    return s2


def make_config(a, out_dir):
    d, f = prod_config(a.gcm, a.scen, a.seed)
    s = open(f).read()
    assert '"relative_humidity": true' in s, "production segment without relative_humidity (the post-2070 defect)"
    # (1) cell range
    s = sub1(r'"startgrid"\s*:\s*"all",', f'"startgrid" : {a.start}, "endgrid" : {a.end},', s)
    # (3) output list of the FROM_RESTART branch: keep ind + globalflux only
    i0 = s.index("#ifdef FROM_RESTART\n\n  \"output\"")
    # drop /* ... */ comments first (cpp would): the Historical configs comment out a run of output entries that
    # SPANS an "#ifdef WITH_SPITFIRE / #else / #endif", so the section's "#else" must be searched for outside
    # comments, and the line filter below must not see a "/*{ "id" ..." opener without its "}}*/" (ERROR228)
    s = s[:i0] + re.sub(r"/\*.*?\*/", "", s[i0:], flags=re.S)
    i1 = s.index("\n#else", i0)
    block = s[i0:i1]
    keep = []
    for ln in block.split("\n"):
        if '{ "id"' in ln and not ln.lstrip().startswith("//"):
            if '"id" : "ind"' in ln:
                ln = re.sub(r'"name" : "[^"]+"', '"name" : "output/ind.csv"', ln)
            elif '"id" : "globalflux"' in ln:
                ln = re.sub(r'"name" : "[^"]+"', '"name" : "output/globalflux.csv"', ln)
            else:
                continue
        keep.append(ln)
    s = s[:i0] + "\n".join(keep) + s[i1:]
    assert s.count('"id" : "ind"') >= 1
    # (2) run settings of the FROM_RESTART branch (the text after the last "#else")
    j = s.rindex("\n#else")
    head, tail = s[:j], s[j:]
    tail = sub1(r'"firstyear"\s*:\s*\d+', f'"firstyear": {a.first}', tail)
    tail = sub1(r'"lastyear"\s*:\s*\d+', f'"lastyear" : {a.last}', tail)
    tail = sub1(r'"outputyear"\s*:\s*\d+', f'"outputyear": {a.output_year or a.first}', tail)
    restart = a.restart or default_restart(a, d, tail)
    assert os.path.exists(restart), restart
    tail = sub1(r'"restart_filename"\s*:\s*"[^"]+"', f'"restart_filename" : "{restart}"', tail)
    tail = sub1(r'"write_restart"\s*:\s*true', '"write_restart" : false', tail)
    s = head + tail
    os.makedirs(os.path.join(out_dir, "output"), exist_ok=True)
    # the production config #includes the member's input file with the cpp QUOTE form => same directory
    inp = re.search(r'#include "(input_[^"]+\.js)"', s).group(1)
    with open(os.path.join(out_dir, inp), "w") as fo:
        fo.write(open(os.path.join(d, inp)).read())
    with open(os.path.join(out_dir, "lpjml.js"), "w") as fo:
        fo.write(s)
    return restart


def default_restart(a, d, tail):
    if a.scen == "Historical":
        assert a.first == 1950, "the Historical member restarts from its own 1950 spin-up restart"
        return os.path.join(d, "restart", "restart_1950_nv.lpj")
    assert a.first == 2015, "an ssp member restarts from its Historical member's 2014 restart"
    return os.path.join(PROD, a.gcm, "Historical", f"random_seed_{a.seed}", "restart", "restart_2014_nv.lpj")


def make_jcf(a, out_dir, ncell):
    tag = f"X-crr-{a.tag}"
    j = f"""#!/bin/bash
#SBATCH --job-name={tag}
#SBATCH --account=waldspektrum
#SBATCH --partition={a.partition}
#SBATCH --qos={a.qos}
#SBATCH --ntasks={a.ntasks}
#SBATCH --cpus-per-task={a.cpus_per_task}
{"#SBATCH --exclusive" if a.exclusive else ""}
{f"#SBATCH --nodes={a.nodes}" if a.nodes else ""}
#SBATCH --time={a.time}
#SBATCH --output={out_dir}/lpjml.%j.out
#SBATCH --error={out_dir}/lpjml.%j.err
source /etc/profile.d/00-modulepath.sh; source /etc/profile.d/modules.sh
module purge; module load {MODULES}
export LPJROOT={LPJROOT}
export LPJ_IND_ALL_HEIGHTS=1
echo "LPJROOT=$LPJROOT LPJ_IND_ALL_HEIGHTS=$LPJ_IND_ALL_HEIGHTS cells={a.start}-{a.end} ntasks={a.ntasks}"
cd {out_dir}
mpirun $LPJROOT/bin/lpjml -DFROM_RESTART {out_dir}/lpjml.js
grep -q "lpjml successfully terminated, {ncell} grid cells processed." {out_dir}/lpjml.$SLURM_JOB_ID.out \\
  && echo "=== RUN OK ===" || {{ echo "=== RUN FAILED (no completion line) ==="; exit 1; }}
"""
    p = os.path.join(out_dir, "run.jcf")
    with open(p, "w") as fo:
        fo.write(j)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["make"])
    ap.add_argument("--gcm", required=True)
    ap.add_argument("--scen", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--end", type=int, required=True)
    ap.add_argument("--ntasks", type=int, required=True)
    ap.add_argument("--first", type=int, required=True)
    ap.add_argument("--last", type=int, required=True)
    ap.add_argument("--output-year", type=int, default=None)
    ap.add_argument("--restart", default=None)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--time", default="02:00:00")
    ap.add_argument("--partition", default="standard")
    ap.add_argument("--qos", default="short")
    ap.add_argument("--exclusive", action="store_true")
    # 2 => twice the memory per MPI task (MaxMemPerCPU is fixed at 5468 MB); one 320-cell ssp370 run was OOM-killed
    ap.add_argument("--cpus-per-task", type=int, default=1)
    # 1 => all tasks on ONE node. A re-run spread over nodes of DIFFERENT processor types reproduces production in
    # the first year only to ~99.3-99.9 % of rows and then diverges (19 of 21 mixed runs failed the gate, all 22
    # single-type runs passed, 2026-10-06); one node is one processor type. 64 tasks fit the priority partition.
    ap.add_argument("--nodes", type=int, default=None)
    ap.add_argument("--submit", action="store_true")
    a = ap.parse_args()
    assert a.scen != "ssp245", "ssp245 ran the Feb-2026 build; this binary is the Dec-2025 one"
    ncell = a.end - a.start + 1
    if a.start == 0 and ncell % 5 == 0 and ncell // 5 <= 875 and a.ntasks != ncell // 5:
        print(f"WARNING: {a.ntasks} tasks do not reproduce the production decomposition ({ncell // 5} would)")
    name = f"{a.gcm}_{a.scen}_s{a.seed}_c{a.start}-{a.end}_{a.first}-{a.last}_{a.tag}"
    out_dir = os.path.join(XDE, "crerun", name)
    restart = make_config(a, out_dir)
    p = make_jcf(a, out_dir, ncell)
    print(f"{out_dir}\n  restart {restart}\n  jcf {p}")
    if a.submit:
        print(subprocess.run(["sbatch", p], capture_output=True, text=True, check=True).stdout.strip())


if __name__ == "__main__":
    main()
