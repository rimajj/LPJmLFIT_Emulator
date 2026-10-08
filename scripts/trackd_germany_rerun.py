"""trackd_germany_rerun.py — Track D2 (EXECUTION_PLAN.md rev. 2, ADR 0096): re-run the ORIGINAL model (LPJmL-FIT)
for the Germany production members over 2045-2100 with the humidity setting that the production 2071-2100
segment lacked.

Why. Every production `lpjml_2100_*` / `lpjml_3100_*` segment config misses `"relative_humidity": true`
(present in the Historical / 2044 / 2070 / 3070 segments), `fscanconfig.c` defaults it FALSE, so 2071-2100 read
relative humidity as specific humidity => VPD 0 => water-stress mortality exactly 0 (lines/X/STATE.md, verified
three ways 2026-10-01). Those are the only years in which the Germany scenarios separate. The owner approved the
re-run on 2026-10-08 ("yes, produce all data that you need").

What a d2 run is. ONE continuous run 2045-2100 per member, from that member's production `restart_2044_nv.lpj`,
using the member's production 2045-2070 segment config (which has relative_humidity true and fix_climate false;
the 2071-2100 config differs from it only by the missing humidity key, a fix_climate block that acts only for
years > 2100 (`iterate.c`: `year > fix_climate_year`), and the `ind` output being on), with:
  * lastyear 2100, outputs from 2045, restart written at 2100 into the run directory;
  * the production output list unchanged except file names, PLUS the `ind` table (2045-2070 had none);
  * `LPJ_IND_ALL_HEIGHTS=1` (a writer-only switch, inert to the physics; gated in explore_de_crerun_gate.py), so
    the table also carries the trees <= 5 m the production writer drops. Filter `Height > 5` to recover the
    production format.
  * the production decomposition (2048 tasks over all 9067 cells) and the SAME model build the member's
    production run used: the ssp245 members ran the Feb-2026 build (source b2e5ca9), all others the Dec-2025 build
    (source fcd3a30). The build is read from the member's own production logs, not assumed.
The 2045-2070 years therefore re-simulate production with the per-tree table switched on; whether they reproduce
production exactly depends on the node types the job lands on (CLAUDE.md §3), and the collect step reports it.

Modes:
  gate  re-run cells 0-319 for 2015-2016 from the member's Historical 2014 restart on ONE node and compare every
        production `ind` row (scripts/explore_de_crerun_gate.py). Required once per BUILD before trusting it.
  d2    the 2045-2100 run described above.

Usage:
  python scripts/trackd_germany_rerun.py gate --gcm MPI-ESM1-2-HR --scen ssp245 --seed 1 [--submit]
  python scripts/trackd_germany_rerun.py d2   --gcm MPI-ESM1-2-HR --scen ssp370 --seed 1 [--submit] [--dependency J]
  python scripts/trackd_germany_rerun.py d2-all [--submit]         # all 12 members
Run directories: $TRACKD_ROOT/germany_rh/<gcm>_<scen>_s<seed>/ (default TRACKD_ROOT=/p/tmp/jamirp/trackD).
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess

PROD = "/p/projects/waldspektrum/data/LPJmLFIT/productionruns_jamir"
ROOT = os.environ.get("TRACKD_ROOT", "/p/tmp/jamirp/trackD")
BUILDS = {
    "dec2025": "/p/tmp/jamirp/X_de/cbuild/lpjml_dec2025",  # line X's gated rebuild of fcd3a30 + writer switch
    "feb2026": "/p/tmp/jamirp/trackD/cbuild/lpjml_feb2026",  # b2e5ca9 + the same writer switch
}
BANNER = {"Dec 17 2025": "dec2025", "Feb  5 2026": "feb2026"}
MODULES = "intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 openssl/3.6.0 netcdf-c curl/8.4.0 expat/2.5.0"
GCMS = ["MPI-ESM1-2-HR", "ACCESS-CM2"]
SCENS = ["ssp126", "ssp245", "ssp370"]
NCELL = 9067


def sub1(pat, rep, s, flags=0):
    s2, n = re.subn(pat, rep, s, count=1, flags=flags)
    assert n == 1, f"pattern not found exactly once: {pat}"
    return s2


def member_dir(gcm, scen, seed):
    d = os.path.join(PROD, gcm, scen, f"random_seed_{seed}")
    assert os.path.isdir(d), d
    return d


def production_build(d, segment):
    """The build banner of the production log that ran `lpjml_<segment>_*.js` in member dir d."""
    found = set()
    for f in glob.glob(os.path.join(d, "lpjml.*.out")):
        s = open(f, errors="replace").read(20000)
        if re.search(rf"lpjml_{segment}_[^ ]*\.js", s):
            m = re.search(r"Version 5\.6\.004 \(([A-Z][a-z]{2} [ 0-9]\d \d{4})\)", s)
            if m:
                found.add(m.group(1))
    assert len(found) == 1, f"{d} segment {segment}: build banners {found}"
    return BANNER[found.pop()]


def strip_comments_after(s, i0):
    return s[:i0] + re.sub(r"/\*.*?\*/", "", s[i0:], flags=re.S)


def edit_outputs(s, keep_all, rename):
    """Rewrite the FROM_RESTART output list. keep_all: keep every active entry (+ uncomment `ind`);
    else keep ind + globalflux only. rename(id) -> new file name."""
    i0 = s.index('#ifdef FROM_RESTART\n\n  "output"')
    s = strip_comments_after(s, i0)
    i1 = s.index("\n#else", i0)
    out = []
    for ln in s[i0:i1].split("\n"):
        m = re.search(r'\{ "id" : "([^"]+)"', ln)
        if m:
            oid = m.group(1)
            commented = ln.lstrip().startswith("//")
            if oid == "ind":
                ln = ln.replace("//", "", 1) if commented else ln
            elif commented or not (keep_all or oid == "globalflux"):
                continue
            ln = re.sub(r'"name" : "[^"]+"', f'"name" : "{rename(oid, ln)}"', ln)
        out.append(ln)
    s = s[:i0] + "\n".join(out) + s[i1:]
    assert s.count('"id" : "ind"') == 1, "expected exactly one active ind output"
    return s


def make_config(
    cfg_src, out_dir, *, first, last, outyear, restart, write_restart_year, start, end, keep_all
):
    s = open(cfg_src).read()
    assert '"relative_humidity": true' in s, (
        f"{cfg_src}: no relative_humidity (the defective segment?)"
    )
    assert re.search(r'"fix_climate"\s*:\s*false', s), f"{cfg_src}: fix_climate is on"
    if start is not None:
        s = sub1(r'"startgrid"\s*:\s*"all",', f'"startgrid" : {start}, "endgrid" : {end},', s)

    def rename(oid, ln):
        ext = "csv" if '"fmt" : "txt"' in ln else "nc"
        return f"output/{oid}.{ext}"

    s = edit_outputs(s, keep_all, rename)
    j = s.rindex("\n#else")
    head, tail = s[:j], s[j:]
    tail = sub1(r'"firstyear"\s*:\s*\d+', f'"firstyear": {first}', tail)
    tail = sub1(r'"lastyear"\s*:\s*\d+', f'"lastyear" : {last}', tail)
    tail = sub1(r'"outputyear"\s*:\s*\d+', f'"outputyear": {outyear}', tail)
    assert os.path.exists(restart), restart
    tail = sub1(r'"restart_filename"\s*:\s*"[^"]+"', f'"restart_filename" : "{restart}"', tail)
    if write_restart_year:
        wr = os.path.join(out_dir, "restart", f"restart_{write_restart_year}_nv.lpj")
        tail = sub1(
            r'"write_restart_filename"\s*:\s*"[^"]+"', f'"write_restart_filename" : "{wr}"', tail
        )
        tail = sub1(r'"restart_year"\s*:\s*\d+', f'"restart_year": {write_restart_year}', tail)
        os.makedirs(os.path.join(out_dir, "restart"), exist_ok=True)
    else:
        tail = sub1(r'"write_restart"\s*:\s*true', '"write_restart" : false', tail)
    s = head + tail
    os.makedirs(os.path.join(out_dir, "output"), exist_ok=True)
    d = os.path.dirname(cfg_src)
    inp = re.search(r'#include "(input_[^"]+\.js)"', s).group(1)
    with open(os.path.join(out_dir, inp), "w") as fo:
        fo.write(open(os.path.join(d, inp)).read())
    with open(os.path.join(out_dir, "lpjml.js"), "w") as fo:
        fo.write(s)


def make_jcf(
    out_dir, *, tag, build, ntasks, ncell, time, partition, qos, cpus, nodes, exclusive, dependency
):
    lpjroot = BUILDS[build]
    assert os.path.exists(os.path.join(lpjroot, "bin", "lpjml")), lpjroot
    lines = [
        "#!/bin/bash",
        f"#SBATCH --job-name={tag}",
        "#SBATCH --account=waldspektrum",
        f"#SBATCH --partition={partition}",
        f"#SBATCH --qos={qos}",
        f"#SBATCH --ntasks={ntasks}",
        f"#SBATCH --cpus-per-task={cpus}",
        f"#SBATCH --time={time}",
        f"#SBATCH --output={out_dir}/lpjml.%j.out",
        f"#SBATCH --error={out_dir}/lpjml.%j.err",
    ]
    if exclusive:
        lines.append("#SBATCH --exclusive")
    if nodes:
        lines.append(f"#SBATCH --nodes={nodes}")
    if dependency:
        lines.append(f"#SBATCH --dependency=afterok:{dependency}")
    lines += [
        "source /etc/profile.d/00-modulepath.sh; source /etc/profile.d/modules.sh",
        f"module purge; module load {MODULES}",
        f"export LPJROOT={lpjroot}",
        "export LPJ_IND_ALL_HEIGHTS=1",
        f'echo "LPJROOT=$LPJROOT build={build} LPJ_IND_ALL_HEIGHTS=$LPJ_IND_ALL_HEIGHTS ntasks={ntasks}"',
        "scontrol show hostnames $SLURM_JOB_NODELIST | head -50 > nodes.txt",
        f"cd {out_dir}",
        f"mpirun $LPJROOT/bin/lpjml -DFROM_RESTART {out_dir}/lpjml.js",
        f'grep -q "lpjml successfully terminated, {ncell} grid cells processed." {out_dir}/lpjml.$SLURM_JOB_ID.out \\',
        '  && echo "=== RUN OK ===" || { echo "=== RUN FAILED (no completion line) ==="; exit 1; }',
    ]
    p = os.path.join(out_dir, "run.jcf")
    with open(p, "w") as fo:
        fo.write("\n".join(lines) + "\n")
    return p


def submit(p):
    out = subprocess.run(["sbatch", p], capture_output=True, text=True, check=True).stdout.strip()
    print(out)
    return out.split()[-1]


def do_gate(a):
    d = member_dir(a.gcm, a.scen, a.seed)
    build = production_build(d, "2044")
    hist = os.path.join(
        PROD, a.gcm, "Historical", f"random_seed_{a.seed}", "restart", "restart_2014_nv.lpj"
    )
    out_dir = os.path.join(ROOT, "gate", f"{a.gcm}_{a.scen}_s{a.seed}_c0-319_2015-2016_{build}")
    make_config(
        os.path.join(d, f"lpjml_2044_{a.gcm}_{a.scen}.js"),
        out_dir,
        first=2015,
        last=2016,
        outyear=2015,
        restart=hist,
        write_restart_year=None,
        start=0,
        end=319,
        keep_all=False,
    )
    p = make_jcf(
        out_dir,
        tag=f"S-D2gate-{build}",
        build=build,
        ntasks=64,
        ncell=320,
        time="01:00:00",
        partition="standard",
        qos="short",
        cpus=2,
        nodes=1,
        exclusive=False,
        dependency=None,
    )
    print(f"{out_dir}\n  build {build}\n  jcf {p}")
    if a.submit:
        submit(p)


def do_d2(gcm, scen, seed, a):
    d = member_dir(gcm, scen, seed)
    build = production_build(d, "2100")
    assert production_build(d, "2070") == build, f"{d}: 2070 and 2100 segments ran different builds"
    out_dir = os.path.join(ROOT, "germany_rh", f"{gcm}_{scen}_s{seed}")
    make_config(
        os.path.join(d, f"lpjml_2070_{gcm}_{scen}.js"),
        out_dir,
        first=2045,
        last=2100,
        outyear=2045,
        restart=os.path.join(d, "restart", "restart_2044_nv.lpj"),
        write_restart_year=2100,
        start=None,
        end=None,
        keep_all=True,
    )
    p = make_jcf(
        out_dir,
        tag=f"S-D2-{gcm[:3]}-{scen}-s{seed}",
        build=build,
        ntasks=2048,
        ncell=NCELL,
        time=a.time,
        partition="standard",
        qos="short",
        cpus=1,
        nodes=None,
        exclusive=True,
        dependency=a.dependency,
    )
    print(f"{out_dir}  build={build}  jcf={p}")
    if a.submit:
        return submit(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["gate", "d2", "d2-all"])
    ap.add_argument("--gcm")
    ap.add_argument("--scen")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--time", default="08:00:00")
    ap.add_argument("--dependency", default=None)
    ap.add_argument("--submit", action="store_true")
    a = ap.parse_args()
    if a.mode == "gate":
        do_gate(a)
    elif a.mode == "d2":
        do_d2(a.gcm, a.scen, a.seed, a)
    else:
        for g in GCMS:
            for sc in SCENS:
                for sd in (1, 2):
                    do_d2(g, sc, sd, a)


if __name__ == "__main__":
    main()
