#!/usr/bin/env python3
"""DOES THE EMULATOR'S OWN STAND WARM?  The pre-registered next action of ADR 0181 section 7.3.

WHY THIS EXISTS
---------------
ADR 0181 settled that the learned count model is a STAND DIAGNOSTIC: handed LPJmL-FIT's own
stand it delivers 0.292 of FIT's area-weighted warming response, and the STAND columns carry
essentially all of it (slope 0.994) while the direct climate channel gives 0.016 and the flux
channel 0.037. A map driven by the stand can only produce a warming count if the stand it is
handed warms. FIT's own stand shifts ~0.30 of a cell's own within-leg sd per feature between
the legs (ADR 0181 PANEL 1, 51 432 cells).

**Whether each rung-2 arm's OWN stand does the same was never measured.** That is this script.
It reads only dumps already on disk -- no LPJmL run, no forest, no training.

REFERENCE BASIS (stated before any number is read; residual-diagnosis section 1)
--------------------------------------------------------------------------------
source
    `/p/tmp/jamirp/S_rung2/S_r2s_<scen>_c<cell>_<arm>_roster_s<seed>_dump/roster_rank0000.txt`
    -- the rung-2 roster dumps (ADR 0175 harness, v6 hook). One cell per dump.
phase
    **`grow`** and only `grow`. `patches/lpjmlfit_rung2_hook_v5.patch` places it after this
    year's turnover/allocation/hazard and BEFORE anyone is taken out of the roster, i.e. at
    the rendezvous. That is the exact analogue of the runtime feature point: `slow.jl` builds
    `flux_feature_vector` from the GROWN pools, before `reconcile_demography!` removes
    anybody. `pre` (start of year), `mort` (post-hazard) and `post` (post-establishment) are
    all the wrong state and are ignored.
features
    the SIX stand features of `flux_feature_vector` (columns 5-10 of the DRF row), computed
    here per (year, patch) with the runtime's own formulas:
        hmean    = sum(height*fpc) / sum(fpc)        (fpc-weighted mean tree height)
        hmax     = max height over trees
        agb      = sum((leaf_c + sapwood_c + heartwood_c) * nind)   (= `FDiff.agb_ind` * nind)
        lai      = sum(leaf_c * sla * nind)
        fpc      = min(sum(fpc), 1)
        age_mean = sum(age * nind) / sum(nind)
    The dump's `T` records are trees only (`istree(pft)` in the writer; grass goes to `G`),
    and its `leaf_c`/`sapwood_c`/`heartwood_c` are `tree->ind.*.carbon`, i.e. PER INDIVIDUAL,
    so the *nind above is the runtime's own factor and not a double count.
    WARNING: `age` at `grow` is post-increment, where the DRF was trained on `mean(Age-1)`
    (ADR 0024). A constant -1 offset cancels in every statistic below (a difference of leg
    means, divided by a within-leg sd) and BOTH sides of every comparison come from this same
    parser, so it is harmless here. It would NOT be harmless in a LEVEL comparison.
reference
    the **`REC` arm at the same cells** -- the pure-observation path, i.e. LPJmL-FIT's own
    roster seen through the same hook, parsed by this same code. Deliberately NOT ADR 0181
    PANEL 1's global median: that is 51 432 cells and this is at most 15 (ADR 0124 -- put the
    truth's own row through your scorer before believing it).
leg shift
    per (cell, arm, seed) and per feature, over patch-year rows,
        z = [mean(ssp370 leg) - mean(historic leg)] / sqrt(0.5*(var_hist + var_ssp))
    byte-for-byte the basis of `slow_stand_forced_response_probe.jl` PANEL 1, so the numbers
    here land on the same axis as its ~0.30.
legs
    historic = 2000-2019 (20 yr), ssp370 = 2020-2100 (81 yr), 25 patches each. A
    (cell, arm, seed) whose two dumps are not BOTH complete is EXCLUDED and named -- 82 of
    510 runs died on `ERROR043 duplicate roster key` and cell 22732 hangs (line S STATE D).
seeds
    the arms are seed ensembles (S0/S0h/S1: 5 seeds; NP/REC: 1). A single seed is not an
    observable (ADR 0106), so the headline z is the across-seed MEAN and the across-seed
    spread of the shift magnitude is printed beside it.

WHAT THIS CANNOT SAY (and the handoff's wording needs this correction)
---------------------------------------------------------------------
In a rung-2 arm the **C grows the stand** and the emulator only decides who dies. So a
degraded stand shift here indicts the EMULATOR'S DEMOGRAPHY destroying a signal the C's
physics did put in -- it does NOT measure the Julia fast core, which never runs in this
configuration. The handoff's branch B.3 ("the defect is upstream in the fast core") is only
reachable through a rung-3 / coupled arm.

PRE-REGISTERED VERDICT (fixed here, before the run -- a threshold is not a verdict)
----------------------------------------------------------------------------------
BLESSED STATISTICS
    `RATIO` = median over scoreable cells of ||z_arm(cell,:)|| / ||z_REC(cell,:)|| over the
    six stand features, and `COSINE` = median over cells of the cosine between those two
    6-vectors. Magnitude alone can pass while the stand moves the wrong way, so BOTH are
    blessed and both are declared here, before the run.
PASS  (the stand warms like FIT's)  : RATIO >= 0.70 AND COSINE >= 0.50
FAIL  (the stand does not warm)     : RATIO <= 0.30
otherwise                           : PARTIAL -- print NO verdict branch, print what would
                                      settle it.
The verdict expression below reads exactly `ratio_med` and `cos_med`; nothing else may enter
it.

USAGE
    export DUMPS=/p/tmp/jamirp/S_rung2 CACHE=/p/tmp/jamirp/S_rung2_standwarm
    NCPUS=16 TIME=02:00:00 scripts/sbatch_python.sh S-standwarm \
        scripts/diagnose_rung2_stand_warming.py
Stage 1 (the ~38 GB text scan) caches one small `.npz` per dump, so re-analysis is seconds.
Exit 0 always: this is a measurement, not a gate.
"""

from __future__ import annotations

import math
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

DUMPS = os.environ.get("DUMPS", "/p/tmp/jamirp/S_rung2")
CACHE = os.environ.get("CACHE", "/p/tmp/jamirp/S_rung2_standwarm")
OUT_CSV = os.environ.get("OUT_CSV", os.path.join(CACHE, "stand_warming_per_cell.csv"))
NCPUS = int(os.environ.get("NCPUS", "16"))
#: `ssp370frz` freezes only the 4 boundary columns fed to the emulator (ADR 0178) while the C
#: still runs transient forcing, so it is NOT a frozen-climate control for the STAND.
#: Off by default; FRZ=1 adds it.
WITH_FRZ = os.environ.get("FRZ", "0") == "1"

DUMP_RE = re.compile(
    r"^S_r2s_(historic|ssp370frz|ssp370)_c(\d+)_(REC|NP|S0h|S0|S1)_roster_s(\d+)_dump$"
)

#: the six stand features, in `flux_feature_vector` order (its columns 5-10)
FEATS = ("hmean", "hmax", "agb", "lai", "fpc", "age_mean")
NF = len(FEATS)

LEG_YEARS = {"historic": (2000, 2019), "ssp370": (2020, 2100), "ssp370frz": (2020, 2100)}
NPATCH = 25

#: THE DRIFT CONTROL (declared here, before the run, alongside the thresholds). The headline z is
#: a difference of LEG MEANS, and a stand that merely drifts monotonically produces one without
#: any warming response at all — ADR 0178 already measured 94-100 % of the arms' apparent count
#: response as drift. So the same statistic is computed between the two HALVES OF THE HISTORIC
#: LEG, where both the arm and FIT run under the same historic forcing and there is no warming
#: excursion to find. It is reported as a RATE (per decade) because the half-leg centroids are
#: 10 yr apart while the two legs' centroids are ~50.5 yr apart. A drift rate as large as the
#: warming rate means the headline number is not a response to the forcing. This is a CONTROL,
#: not part of the verdict expression.
DRIFT_A = (2000, 2009)
DRIFT_B = (2010, 2019)
DRIFT_DECADES = 1.0                 # centroid separation of DRIFT_A -> DRIFT_B
WARM_DECADES = 5.05                 # centroid separation of the historic leg -> the ssp370 leg

# ── pre-registered thresholds (see the header; do not move these after a run) ─────────────────────
PASS_RATIO = 0.70
PASS_COSINE = 0.50
FAIL_RATIO = 0.30


# ── stage 1: one dump -> per (year, patch) stand features ─────────────────────────────────────────
def aggregate_dump(dumpdir: str) -> str | None:
    """Stream one dump's `grow` phase into per-(year, patch) stand features; cache as .npz.

    Returns the cache path, or None if the dump has no roster file. The cache key carries the roster
    file's size and mtime, so an interrupted or re-run dump is never served from a stale cache.
    """
    path = os.path.join(dumpdir, "roster_rank0000.txt")
    if not os.path.exists(path):
        return None
    st = os.stat(path)
    tag = os.path.basename(dumpdir)
    out = os.path.join(CACHE, "cache", f"{tag}.{st.st_size}.{int(st.st_mtime)}.npz")
    if os.path.exists(out):
        return out
    os.makedirs(os.path.dirname(out), exist_ok=True)

    # accumulators, keyed (year, patch): [sum_fpc, sum_h*fpc, sum_lai, sum_agb, max_h, sum_nind,
    #                                     sum_age*nind, ntree]
    acc: dict[tuple[int, int], list[float]] = {}
    idx: dict[str, int] = {}
    with open(path) as fh:
        for line in fh:
            if line.startswith("#H T"):
                # parse the header rather than hardcoding offsets: the writer's column set is a C
                # printf and has grown across hook versions (v3->v5).
                # the "#H T" line is "#H T phase lon lat ...", the data line "T grow <lon> ..." --
                # so the n-th NAME lives at field n+1 of a record (field 0 is the "T" tag itself).
                names = line.split()[2:]
                idx = {n: i + 1 for i, n in enumerate(names)}
                continue
            if line.startswith("P grow"):
                # enumerate patch-years INCLUDING tree-less patches (they emit no T record but are a
                # real all-zero stand row at runtime).
                f = line.split()          # P <phase> <lon> <lat> <year> <patch> <npatch> ...
                key = (int(f[4]), int(f[5]))
                if key not in acc:
                    acc[key] = [0.0] * 8
                continue
            if not line.startswith("T grow"):
                continue
            f = line.split()
            key = (int(f[idx["year"]]), int(f[idx["patch"]]))
            a = acc.get(key)
            if a is None:
                a = acc[key] = [0.0] * 8
            fpc = float(f[idx["fpc"]])
            h = float(f[idx["height"]])
            nind = float(f[idx["nind"]])
            leaf = float(f[idx["leaf_c"]])
            a[0] += fpc
            a[1] += h * fpc
            a[2] += leaf * float(f[idx["sla"]]) * nind
            a[3] += (leaf + float(f[idx["sapwood_c"]]) + float(f[idx["heartwood_c"]])) * nind
            if h > a[4]:
                a[4] = h
            a[5] += nind
            a[6] += float(f[idx["age"]]) * nind
            a[7] += 1.0

    keys = sorted(acc)
    rows = np.zeros((len(keys), 2 + NF + 1), dtype=np.float64)
    for i, (yr, pa) in enumerate(keys):
        a = acc[(yr, pa)]
        hmean = a[1] / a[0] if a[0] > 0 else 0.0
        age_mean = a[6] / a[5] if a[5] > 0 else 0.0
        rows[i] = (yr, pa, hmean, a[4], a[3], a[2], min(a[0], 1.0), age_mean, a[7])
    np.savez_compressed(out, rows=rows)
    return out


def discover() -> dict[tuple[str, int, int, str], str]:
    """-> {(arm, cell, seed, scenario): dumpdir} for every dump present."""
    got: dict[tuple[str, int, int, str], str] = {}
    for name in sorted(os.listdir(DUMPS)):
        m = DUMP_RE.match(name)
        if not m:
            continue
        scen, cell, arm, seed = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        if scen == "ssp370frz" and not WITH_FRZ:
            continue
        got[(arm, cell, seed, scen)] = os.path.join(DUMPS, name)
    return got


# ── stage 2: per (cell, arm, seed) leg statistics ─────────────────────────────────────────────────
def leg_stats(
        rows: np.ndarray, scen: str, window: tuple[int, int] | None = None
) -> tuple[np.ndarray, np.ndarray, str]:
    """Per-feature (mean, var) over the leg's patch-year rows + a coverage verdict string.

    `window` restricts to a sub-span of the leg (used by the DRIFT control, which splits the
    historic leg in half). Coverage is always judged against the FULL leg, so a dump that is
    complete for the control but truncated later is still excluded.
    """
    y0, y1 = LEG_YEARS[scen]
    yrs = rows[:, 0].astype(int)
    keep = (yrs >= y0) & (yrs <= y1)
    r = rows[keep]
    have = set(np.unique(r[:, 0].astype(int)).tolist())
    want = set(range(y0, y1 + 1))
    missing = sorted(want - have)
    npatch_bad = [
        int(y) for y in sorted(have) if int((r[:, 0].astype(int) == y).sum()) != NPATCH
    ]
    cov = "ok"
    if missing:
        cov = f"missing {len(missing)}/{len(want)} yr (first {missing[0]}, last {missing[-1]})"
    elif npatch_bad:
        cov = f"{len(npatch_bad)} yr not {NPATCH} patches (first {npatch_bad[0]})"
    if window is not None:
        w = r[:, 0].astype(int)
        r = r[(w >= window[0]) & (w <= window[1])]
        if r.shape[0] == 0:
            return np.zeros(NF), np.zeros(NF), cov
    x = r[:, 2 : 2 + NF]
    return x.mean(axis=0), x.var(axis=0), cov


def median(v: list[float]) -> float:
    return float(np.median(v)) if v else float("nan")


def main() -> int:
    os.makedirs(CACHE, exist_ok=True)
    got = discover()
    print("=" * 100)
    print("DOES THE EMULATOR'S OWN STAND WARM?  rung-2 arms vs FIT's own (REC) at the SAME cells")
    print("  ADR 0181 §7.3's pre-registered next action. Dumps on disk only — no LPJmL run.")
    print(f"  dumps={DUMPS}  cache={CACHE}  frz={'in' if WITH_FRZ else 'out'}")
    print(f"  phase=grow  features={FEATS}")
    print(f"  PRE-REGISTERED: PASS if RATIO>={PASS_RATIO} AND COSINE>={PASS_COSINE};"
          f" FAIL if RATIO<={FAIL_RATIO}; else PARTIAL")
    print("=" * 100)
    arms = sorted({k[0] for k in got})
    cells = sorted({k[1] for k in got})
    print(f"\ndiscovered {len(got)} dumps · arms {arms} · {len(cells)} cells · "
          f"seeds {sorted({k[2] for k in got})}")

    # ── stage 1 ───────────────────────────────────────────────────────────────────────────────────
    dirs = sorted(set(got.values()))
    cdir = os.path.join(CACHE, "cache")
    have = set(os.listdir(cdir)) if os.path.isdir(cdir) else set()
    ncached = sum(1 for d in dirs
                  if any(f.startswith(os.path.basename(d) + ".") for f in have))
    print(f"\n-- stage 1: aggregating {len(dirs)} dumps ({ncached} already cached) "
          f"on {NCPUS} workers ...")
    sys.stdout.flush()
    caches: dict[str, str] = {}
    with ProcessPoolExecutor(max_workers=NCPUS) as ex:
        for d, c in zip(dirs, ex.map(aggregate_dump, dirs, chunksize=1), strict=True):
            if c is not None:
                caches[d] = c
    print(f"   cached {len(caches)}/{len(dirs)}")
    sys.stdout.flush()

    # ── coverage gate ─────────────────────────────────────────────────────────────────────────────
    stats: dict[tuple[str, int, int, str], tuple[np.ndarray, np.ndarray]] = {}
    half: dict[tuple[str, int, int, str], tuple[np.ndarray, np.ndarray]] = {}
    excluded: list[str] = []
    for key, d in sorted(got.items()):
        c = caches.get(d)
        if c is None:
            excluded.append(f"{key} : no roster file")
            continue
        rows = np.load(c)["rows"]
        if rows.size == 0:
            excluded.append(f"{key} : empty dump")
            continue
        mu, va, cov = leg_stats(rows, key[3])
        if cov != "ok":
            excluded.append(f"{key} : {cov}")
            continue
        stats[key] = (mu, va)
        if key[3] == "historic":
            # the DRIFT CONTROL's two half-legs (see DRIFT_A / DRIFT_B)
            half[(key[0], key[1], key[2], "A")] = leg_stats(rows, "historic", DRIFT_A)[:2]
            half[(key[0], key[1], key[2], "B")] = leg_stats(rows, "historic", DRIFT_B)[:2]

    print(f"\n-- COVERAGE GATE: {len(stats)} complete legs, {len(excluded)} excluded")
    for e in excluded:
        print(f"   EXCLUDED  {e}")

    # ── PANEL 0 — liveness (ADR 0179: run this FIRST) ─────────────────────────────────────────────
    print("\n" + "-" * 100)
    print("-- PANEL 0  LIVENESS. Within-leg sd of each stand feature over its own leg mean.")
    print("            A feature CONSTANT inside a leg would report 'no warming' for the wrong")
    print("            reason. Any exact zero here invalidates that feature's shift below.")
    print(f"   {'arm':<6}{'leg':<11}" + "".join(f"{f:>12}" for f in FEATS)
          + f"{'legs':>8}{'dead':>6}")
    for arm in arms:
        for scen in ("historic", "ssp370", "ssp370frz"):
            sel = [(k, v) for k, v in stats.items() if k[0] == arm and k[3] == scen]
            if not sel:
                continue
            cv = np.array([[math.sqrt(v[1][f]) / abs(v[0][f]) if v[0][f] != 0 else 0.0
                            for f in range(NF)] for _, v in sel])
            dead = int((cv == 0.0).sum())
            print(f"   {arm:<6}{scen:<11}"
                  + "".join(f"{np.median(cv[:, f]):>12.4f}" for f in range(NF))
                  + f"{len(sel):>8}{dead:>6}")

    # ── the leg shift z, per (arm, cell, seed) ────────────────────────────────────────────────────
    z: dict[tuple[str, int, int], np.ndarray] = {}
    for (arm, cell, seed, scen), (mu, va) in stats.items():
        if scen != "historic":
            continue
        s = stats.get((arm, cell, seed, "ssp370"))
        if s is None:
            continue
        sd = np.sqrt(0.5 * (va + s[1]))
        with np.errstate(divide="ignore", invalid="ignore"):
            zz = np.where(sd > 0, (s[0] - mu) / np.where(sd > 0, sd, 1.0), 0.0)
        z[(arm, cell, seed)] = zz

    # the DRIFT CONTROL's shift, on the same sd basis, between the two halves of the historic leg
    zd: dict[tuple[str, int, int], np.ndarray] = {}
    for (arm, cell, seed, tagA) in list(half):
        if tagA != "A":
            continue
        a = half[(arm, cell, seed, "A")]
        b = half.get((arm, cell, seed, "B"))
        s = stats.get((arm, cell, seed, "ssp370"))
        if b is None or s is None:
            continue
        # the SAME sd basis as the headline z (the full-leg pooled sd), so the two are comparable
        sd = np.sqrt(0.5 * (stats[(arm, cell, seed, "historic")][1] + s[1]))
        zd[(arm, cell, seed)] = np.where(sd > 0, (b[0] - a[0]) / np.where(sd > 0, sd, 1.0), 0.0)

    def ens(src: dict[tuple[str, int, int], np.ndarray]) -> tuple[dict, dict]:
        """Seed-ensemble mean z per (arm, cell) + the across-seed spread of its magnitude."""
        acc: dict[tuple[str, int], list[np.ndarray]] = {}
        for (arm, cell, _seed), zz in src.items():
            acc.setdefault((arm, cell), []).append(zz)
        mean, spread = {}, {}
        for k, lst in acc.items():
            a = np.array(lst)
            mean[k] = a.mean(axis=0)
            norms = np.linalg.norm(a, axis=1)
            spread[k] = float(norms.std()) if len(norms) > 1 else 0.0
        return mean, spread

    zbar, zspread = ens(z)
    zdbar, _ = ens(zd)

    rec_cells = sorted({c for (a, c) in zbar if a == "REC"})
    print("\n" + "-" * 100)
    print("-- PANEL 1  FIT'S OWN STAND at these cells (arm REC = the pure-observation path).")
    print("            Signed leg shift z in units of that cell's own within-leg sd.")
    print("            ADR 0181 PANEL 1's global median |z| per feature: ~0.30, 51 432 cells.")
    print(f"   {'cell':>7}" + "".join(f"{f:>12}" for f in FEATS) + f"{'||z||':>10}")
    for c in rec_cells:
        zz = zbar[("REC", c)]
        print(f"   {c:>7}" + "".join(f"{zz[f]:>12.3f}" for f in range(NF))
              + f"{np.linalg.norm(zz):>10.3f}")
    if rec_cells:
        m = np.array([zbar[("REC", c)] for c in rec_cells])
        print(f"   {'med|z|':>7}"
              + "".join(f"{np.median(np.abs(m[:, f])):>12.3f}" for f in range(NF))
              + f"{np.median(np.linalg.norm(m, axis=1)):>10.3f}")

    # ── PANEL 2 — each arm against REC on the SAME cells ──────────────────────────────────────────
    print("\n" + "-" * 100)
    print("-- PANEL 2  EACH ARM'S OWN STAND vs FIT'S, same cells. RATIO = ||z_arm||/||z_REC||,")
    print("            COSINE = direction agreement of the two 6-vectors. seed-ensemble mean z;")
    print("            'sd||z||' is the across-seed spread of the arm's own shift magnitude.")
    print("            DRIFTrate/WARMrate: the same shift per decade inside the HISTORIC leg (the")
    print(f"            declared control, {DRIFT_A[0]}-{DRIFT_A[1]} vs"
          f" {DRIFT_B[0]}-{DRIFT_B[1]}) over the warming rate. ~1 ⇒ the")
    print("            headline shift is the arm's ongoing drift, not a response to the forcing.")
    print("            The per-feature columns are the arm's own SIGNED median z (NOT a ratio: a")
    print("            per-feature ratio explodes wherever FIT's own shift is near zero).")
    print(f"   {'arm':<6}{'cells':>6}{'RATIO':>9}{'COSINE':>9}{'|z|arm':>9}{'|z|REC':>9}"
          f"{'sdSEED':>8}{'DRIFT/WARM':>11}  " + "".join(f"{f:>9}" for f in FEATS))
    csv_rows: list[str] = []
    verdicts: dict[str, tuple[float, float, int]] = {}
    rec_drift = float("nan")
    for arm in arms:
        shared = sorted({c for (a, c) in zbar if a == arm} & set(rec_cells))
        if not shared:
            continue
        ratios, coss, na, nr, spreads, drifts = [], [], [], [], [], []
        perfeat: list[list[float]] = [[] for _ in range(NF)]
        for c in shared:
            za, zr = zbar[(arm, c)], zbar[("REC", c)]
            aa, rr = float(np.linalg.norm(za)), float(np.linalg.norm(zr))
            if rr <= 0:
                continue
            ratios.append(aa / rr)
            coss.append(float(np.dot(za, zr) / (aa * rr)) if aa > 0 else 0.0)
            na.append(aa)
            nr.append(rr)
            spreads.append(zspread[(arm, c)])
            zdd = zdbar.get((arm, c))
            if zdd is not None and aa > 0:
                drifts.append((float(np.linalg.norm(zdd)) / DRIFT_DECADES)
                              / (aa / WARM_DECADES))
            for f in range(NF):
                perfeat[f].append(za[f])
            csv_rows.append(
                f"{arm},{c},{aa:.6f},{rr:.6f},{aa / rr:.6f},"
                + ",".join(f"{za[f]:.6f}" for f in range(NF)) + ","
                + ",".join(f"{zr[f]:.6f}" for f in range(NF))
            )
        ratio_med, cos_med = median(ratios), median(coss)
        if arm == "REC":
            rec_drift = median(drifts)
        else:
            verdicts[arm] = (ratio_med, cos_med, len(ratios))
        print(f"   {arm:<6}{len(ratios):>6}{ratio_med:>9.3f}{cos_med:>9.3f}{median(na):>9.3f}"
              f"{median(nr):>9.3f}{median(spreads):>8.3f}{median(drifts):>11.3f}  "
              + "".join(f"{np.median(perfeat[f]):>9.3f}" for f in range(NF)))
    print(f"   (REC's own drift/warm ratio is {rec_drift:.3f} — FIT is not drift-free either, so"
          " read the arms against THAT, not against 0.)")

    # ── PANEL 3 — the verdict, on the blessed statistics only ─────────────────────────────────────
    print("\n" + "-" * 100)
    print("-- PANEL 3  VERDICT on the PRE-REGISTERED statistics (ratio_med, cos_med) only.")
    for arm, (ratio_med, cos_med, n) in verdicts.items():
        if n < 5:
            verdict = f"NO VERDICT — only {n} scoreable cells (pre-registered minimum 5)"
        elif ratio_med >= PASS_RATIO and cos_med >= PASS_COSINE:
            verdict = ("PASS — this arm's stand warms like FIT's. The stand carries the "
                       "signal and the count map still loses it ⇒ the defect is inside S "
                       "(size: ADR 0181's 0.292).")
        elif ratio_med <= FAIL_RATIO:
            verdict = ("FAIL — this arm's stand does not warm. A stand-driven count map cannot "
                       "recover the response; the emulator's demography is destroying it "
                       "upstream of the map.")
        else:
            verdict = ("PARTIAL — no pre-registered branch applies. What would settle it: the "
                       "same statistic on more cells, and a per-feature attribution of which "
                       "stand column loses the shift.")
        print(f"   {arm:<6} RATIO={ratio_med:.3f}  COSINE={cos_med:.3f}  n={n}  ->  {verdict}")

    if csv_rows:
        os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
        with open(OUT_CSV, "w") as fh:
            fh.write("arm,cell,norm_arm,norm_rec,ratio,"
                     + ",".join(f"z_arm_{f}" for f in FEATS) + ","
                     + ",".join(f"z_rec_{f}" for f in FEATS) + "\n")
            fh.write("\n".join(csv_rows) + "\n")
        print(f"\nwrote {len(csv_rows)} per-cell rows -> {OUT_CSV}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
