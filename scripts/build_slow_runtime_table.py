#!/usr/bin/env python3
"""Build a RUNTIME-CONSISTENT Component-S training table for the production DRF — GLOBAL multi-cell.

The runtime feeds the DRF a feature row assembled by `flux_feature_vector` (src/components/slow.jl:499-503):

    [bm_inc_cell, growth_eff, water_stress, soilmoist, hmean, hmax, agb, lai, fpc, age_mean, n_prev,
     <boundary tail...>]

ADR 0020 §6 requires S be conditioned at runtime on the SAME channel it was trained on, so this table
reproduces that exact 11-head order + a per-cell slow-boundary tail. Each `ind` row is one living stem in
`individual=true`; emitted `npp`/`agb` are already per-m² (×nind baked in by the C writer), so per-patch
ROW SUMS give per-m² stand totals matching the runtime aggregates (no `nind` factor; CLAUDE.md §3).

RUNTIME-CONSISTENT features (was the Hainich-proxy demo; now real, ADR 0023/0024, global-table spec):
  bm_inc_cell = sum(npp)                         EXACT   (per-m², tree-only patch)
  water_stress= 1 - mean(wscal_mean)             EXACT-in-definition (fast.jl: 1 - wscal_mean)
  soilmoist   = ROOTMOIST / sum_{l<3} whcs[l]    REAL    join cell_year_soilmoist_ye_{scen}.parquet, built by
                                                          scripts/build_rootmoist_soilmoist_feature.py. The
                                                          whcs-weighted mean of the C's own `w` over the top
                                                          1 m at YEAR END == the runtime
                                                          `root_zone_soilmoist(state, fc.soil)` (slow.jl).
                                                          ADR 0035 REPLACED the old `swc`-based column: `swc`
                                                          is TOTAL water over SATURATION capacity
                                                          (update_daily.c:411), a DIFFERENT QUANTITY from the
                                                          runtime's plant-available fraction-of-WHC — not a
                                                          mere time-aggregation difference (ADR 0034's
                                                          diagnosis, corrected). Never re-point this at
                                                          cell_year_soilmoist_{scen}.parquet.
  hmean       = sum(Height*fpc_ind)/sum(fpc_ind) NEAR-EXACT (fpc-weighted mean height)
  hmax        = max(Height)                       EXACT
  agb         = sum(agb)                           CLOSE   (per-m²; minor C turn_litt/debt offset)
  lai         = PER-PATCH stand LAI                EXACT (to the ind writer's %g precision) — reconstructed
                                                          in-row from the emitted `LAI` + `fpc_ind` by
                                                          `patch_stand_lai_expr()` below, NOT joined. ADR 0035
                                                          replaced the C `LAI_STAND` join, which was a
                                                          patch-ensemble CELL-mean broadcast onto per-PATCH
                                                          rows while every other state column in the row is
                                                          per-patch. Validated against the C's own allometry
                                                          by scripts/diagnose_patch_lai_reconstruction.py
                                                          (median rel err 1.8e-8). Caveat, shared with every
                                                          other column here: the ind writer emits only stems
                                                          `height > height_min` (5 m), so this is the >5 m
                                                          stand LAI — 0.77..1.01 of the all-trees LAI_STAND
                                                          depending on biome. That is the training
                                                          population, consistently, by construction.
  growth_eff  = lai > 0 ? applied_npp/lai : 0     APPROX  numerator = APPLIED npp (npp>0 & Height>0 stems),
                                                          mirroring the runtime applied_cell/leaf_area
                                                          (fast.jl:353-369) — NOT total bm_inc_cell. The
                                                          zero-leaf-area branch MATCHES fast.jl:369 exactly
                                                          (`leaf_area > 0 ? … : zero(T)`); it must not be a
                                                          `max(lai, EPS)` divisor (ADR 0031 — that turned a
                                                          joined LAI_STAND==0 into applied_npp*1e6). Since
                                                          ADR 0035 the divisor is the SAME per-patch, >5 m
                                                          population as the numerator (it used to be a
                                                          cell-mean over all stems — a real inconsistency in
                                                          a primary mortality driver).
  fpc         = min(sum(fpc_ind), 1)               NEAR-EXACT
  age_mean    = mean(Age - 1)                      TRUE per-stem mean START-OF-YEAR age (ADR 0024; emitted
                                                          Age is post-increment, runtime feature is pre-aging).
  n_prev      = previous-year n_living (same Cell,Patch)  AR state
  target      = n_living                            demographic count
  boundary    = [gdd_5, tas_cold_month, soil_depth] + co2=369 (constant-CO2, ADR 0004). DEFAULT = per-CELL
                climatological mean (TIME-CONSTANT; matches the pre-0026 runtime `s.boundary` baked once).
                OPT-IN `BOUNDARY_WINDOW=W` (ADR 0026): per-(Cell,Year) TRANSIENT gdd5/tas_cold_month on a
                trailing-W-yr window (soil_depth static) so a warming cell's establishment gate SHIFTS over
                the transient; the runtime consumes it via `FluxDrivenSlowEmulator`'s `boundary_series`
                (train/inference stay consistent — same per-(cell,year) boundary in the table and the loop).

Cell-agnostic pooled training: ONE global forest (the .drf carries no cell identity), with all per-cell
context (boundary, n_init, age0) in a `cell_meta.parquet` SIDECAR the coupled driver reads to build one
`FluxDrivenSlowEmulator` per cell. Sound because the AR ratio target/n_prev (slow.jl:526) cancels count
magnitude, so pooling cells does not conflate their absolute densities.

MODE=copula STRUCT axes (opt-in `STRUCT_AXES`, default OFF, DIAGNOSTIC ONLY): besides the 4 production
recruit-TRAIT axes the copula table can carry per-stem stand-STRUCTURE targets — `STRUCT_AXES=1` ⇒
["agb", "Height"] — so the global emulator's BIOMASS and SIZE distributions get the same per-cell,
K-fold-BY-CELL out-of-sample validation the traits get. They are built/evaluated identically (one marginal
DRF per axis, conditioned on the runtime `live_flux_cond` subset) but must NEVER enter the serialized
production `.rcop`: line M pins that artifact and `slow.jl::make_recruit_to_pools` maps exactly the 4 trait
axes onto carbon pools (ADR 0025, a frozen cross-line contract). They are APPENDED after the production
axes — `naxes`/`axes` keep meaning the 4 production axes, the new `nstruct`/`struct_axes` manifest lines
describe the diagnostic tail — so the production axes' predictions stay BIT-IDENTICAL (guardrail 4; the
evaluator's per-axis RNG/forest seeds are functions of the axis INDEX). Both are existing columns of the
29-col `ind` table and already in the runtime's units: `agb` is per-m² (×nind baked in by the C writer,
CLAUDE.md §3) so a per-patch ROW SUM is the per-m² stand total, and `Height` is metres.

Writes to $OUT: X.f64 (row-major n×p Float64), y.f64 (n), manifest.txt, cell_meta.parquet. The X ROW ORDER
is deterministic (final sort on Cell,Patch,Year); the streaming aggregate SUMS jitter at ~1e-13 relative
(parallel partial-sum combine order under collect(engine="streaming") is not fixed) — bit-identical output
across runs is NOT guaranteed, only row order + values to ~1e-13.

Usage (SLURM — see slow-drf-pipeline skill §7 for sizing):
  # global historic:
  SCENARIO=historic SEED=1 OUT=/p/tmp/jamirp/emulator_global/slow_runtime_hist python3 scripts/build_slow_runtime_table.py
  # a biome-stratified subset (verification): CELLS=42490,<tropical>,<boreal>,<arid>
  # single-cell Hainich demo (also emits scalar meta for the committed .drf path): CELLS=42490
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import polars as pl

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "python" / "src"))
from lpjmlfit_emulator import data as ind_data  # noqa: E402

# FIT's COMPLETE tree set, IMPORTED — never re-declared here (ADR 0031). A local copy is what drifted:
# `[1,2,3,4,5]` dropped id 0 (tropical broadleaved evergreen) + id 6 (larch) = 32.5% of survivor tree stems and
# made 16.7% of tree-bearing cells invisible, so every table/artifact/fidelity number built before 2026-07-28
# is on that truncated population. Census: scripts/diagnose_ind_type_composition.py.
TREE_TYPES = list(ind_data.TREE_TYPES)
BASE = "/p/tmp/jamirp/emulator_global"
IND = {
    "historic": f"{BASE}/ind_hist_seed{{seed}}_all.parquet",
    "ssp370": f"{BASE}/ind_ssp370_seed{{seed}}_all.parquet",
}
# ADR 0035: the `_ye` tables are the ROOT-ZONE year-end soilmoist (build_rootmoist_soilmoist_feature.py).
# The pre-0035 `cell_year_soilmoist_{hist,ssp}.parquet` are on the C `swc` variable (fractional SATURATION)
# and are NOT interchangeable with these — they are retained only so the superseded artifacts stay
# reproducible. Never point SOIL_TBL_PATH back at them.
SOIL_TBL = {"historic": f"{BASE}/tables/cell_year_soilmoist_ye_hist.parquet",
            "ssp370": f"{BASE}/tables/cell_year_soilmoist_ye_ssp.parquet"}
CELL_YEAR_FEATS = f"{BASE}/tables/cell_year_feats.parquet"
# TRANSIENT boundary (ADR 0026): per-(Cell,Year) trailing-window gdd5/tas_cold_month (scripts/build_transient_boundary.py)
TRANSIENT_BOUNDARY = f"{BASE}/tables/cell_year_boundary_{{scenario}}_w{{w}}.parquet"
# TRANSIENT env tail (ADR 0108): per-(Cell,Year) trailing-window MOISTURE descriptors, same builder
# (`MOISTURE=1 scripts/build_transient_boundary.py`), same trailing-W-year basis as the boundary.
TRANSIENT_ENV = f"{BASE}/tables/cell_year_env_{{scenario}}_w{{w}}.parquet"
FIRSTYEAR = {"historic": 2000, "ssp370": 2020}

# runtime head order — MUST equal src/components/slow.jl::flux_feature_vector
HEAD_COLS = ["bm_inc_cell", "growth_eff", "water_stress", "soilmoist",
             "hmean", "hmax", "agb", "lai", "fpc", "age_mean", "n_prev"]
BOUNDARY_COLS = ["eco_diag_gdd_5", "tas_cold_month", "soil_depth", "co2"]
CO2_CONST = 369.0        # constant-CO2 regime (ADR 0004); the runtime boundary has no co2 input
EPS = 1.0e-6
# growth_eff sanity ceiling (ADR 0031). Measured maxima are 3.1e4 (seed1) / 4.3e4 (seed2) under the runtime
# zero-leaf-area rule; the old `max(lai, EPS)` divisor produced >=1e6 whenever lai==0 met positive npp.
GROWTH_EFF_MAX = float(os.environ.get("GROWTH_EFF_MAX", "1e6"))
MIN_YEARS = 3            # per-cell rows floor for a trustworthy n_init/age0 median

# MODE=copula (recruit-trait distribution, ADR 0025): a per-STEM table whose conditioning is EXACTLY the
# subset the runtime live_flux_cond(s, feats) builds — the 4 flux drivers + the per-cell boundary tail,
# DELIBERATELY excluding the 6 patch-state aggregates + n_prev (src/components/slow.jl::live_flux_cond).
# This order IS the copula feature-order contract. Targets = FIT's 4 LIVE sampled trait primaries (beta_2
# is compile-time dead in this build, so it is NOT an axis; ADR 0025). Trained on SURVIVING stems only
# (isdead==0): the emulator's mortality is trait-blind, so the community distribution = the establishment
# distribution, which must therefore be FIT's SURVIVOR marginal.
# ADR 0037 — OPT-IN EXTENDED conditioning (env `COPULA_ENV_COLS`, comma-separated `cell_year_feats` columns,
# DEFAULT EMPTY so this builder's output stays byte-identical). Appended AFTER the boundary tail, so the
# existing 8 columns keep their positions and only the tail grows.
#
# WHY: the boundary tail is `eco_diag_gdd_5`, `tas_cold_month`, `soil_depth`, `co2` — one temperature axis and
# one soil axis, and NO moisture or precipitation climatology — while FIT's establishment gates are
# temperature AND moisture. Measured on `t8` (scripts/diagnose_copula_cond_ceiling.py): adding the wider
# climate descriptors lifts attainable per-cell trait skill by +0.011 SLA / +0.025 Wooddens / +0.042 D95max,
# and on Wooddens an environment-only predictor BEATS the eight production columns (0.910 vs 0.893).
#
# LOAD-BEARING (ADR 0023, and it fails SILENTLY): the runtime must build the SAME tail in the SAME order via
# `src/components/slow.jl::live_flux_cond_env`. The `.rcop`'s `cond_cols` line is the contract between them.
#
# THE TAIL'S TIME BASIS IS A SECOND, INDEPENDENT KNOB — `ENV_WINDOW` (ADR 0108, see `_env_source`). Unset ⇒
# per-CELL time means (the pre-0108 behaviour, matching the DEFAULT static boundary). `ENV_WINDOW=W` ⇒ the
# per-(Cell,Year) trailing-W-year tables, i.e. the ADR-0026 treatment the boundary pair already gets. The two
# bases produce tables with IDENTICAL `ncond` and IDENTICAL `cond_cols` and require DIFFERENT runtime
# policies (`live_flux_cond_env` vs `live_flux_cond_env_series`), so the manifest's `env_basis` line — not the
# width, which matches either way — is what tells a consumer which one it is holding.
COPULA_ENV_COLS = [c.strip() for c in os.environ.get("COPULA_ENV_COLS", "").split(",") if c.strip()]
COPULA_COND_COLS = HEAD_COLS[:4] + BOUNDARY_COLS + COPULA_ENV_COLS
COPULA_AXES = ["SLA", "Wooddens", "D95max", "minwscal"]

# DIAGNOSTIC-ONLY per-stem axes (opt-in, env STRUCT_AXES): the stand-STRUCTURE validation targets — per-stem
# aboveground biomass and height — so the global emulator's BIOMASS and SIZE distributions are validated
# per-cell out-of-sample exactly like the traits (same conditioning, same K-fold-BY-CELL split). Both are
# already columns of the 29-col `ind` table in the runtime's own units: `agb` is per-m² (×nind baked in by the
# C writer, CLAUDE.md §3), so a per-patch ROW SUM is the per-m² stand total; `Height` is metres.
# WHY DIAGNOSTIC ONLY: they must never reach the serialized production `.rcop`. Line M PINS that artifact and
# `src/components/slow.jl::make_recruit_to_pools` maps the 4 PRODUCTION axes onto carbon pools (ADR 0025, a
# frozen cross-line contract) — a 5th/6th axis there would silently redefine that mapping.
# WHY APPENDED: `eval_slow_copula.jl` seeds each axis's RNG/forest from the axis INDEX, so appending after
# the production axes leaves their predictions BIT-IDENTICAL (guardrail 4). Never interleave or reorder.
STRUCT_AXES_DEFAULT = ["agb", "Height"]

#: PER-PFT Lambert-Beer light-extinction coefficient (`par/pft_lpjmlfit.js`: `K_LAMBERT_BEER_BL` 0.59
#: broadleaf ids {0,2,3,5} / `K_LAMBERT_BEER_NL` 0.45 needleleaf ids {1,4,6}; Zhang et al. 2014), keyed by
#: the 0-based `Type` = pftpar index. The C reads it PER PFT (`fpc_tree.c:28`
#: `getpftpar(pft, lightextcoeff)`), so one global k would bias every needleleaf stem's inverted crown area.
K_LIGHTEXT = {0: 0.59, 1: 0.45, 2: 0.59, 3: 0.59, 4: 0.45, 5: 0.59, 6: 0.45}


def patch_stand_lai_expr() -> pl.Expr:
    """Per-stem contribution to the PER-PATCH stand LAI, from the emitted `LAI` / `fpc_ind` / `Type`.

    THE CANONICAL DEFINITION (ADR 0035) — `scripts/diagnose_patch_lai_reconstruction.py` imports THIS, so
    the training column and its validation can never drift apart (the ADR-0031 lesson: two independent
    copies of one definition is exactly what caused the tree-PFT truncation).

    The `slow-drf-pipeline` skill used to record "per-patch LAI is NOT reconstructable from ind (no
    leaf_c/nind)". True literally, false in effect — `LAI` (the within-crown individual LAI) and `fpc_ind`
    between them carry the crown area:

        fpc_ind = crownarea * nind * (1 - exp(-k_pft * LAI))     fpc_tree.c:28
        nind    = 1 / param.patcharea                            new_tree.c:209 (individual = true)
        LAI     = leaf_c * sla / crownarea                       lai_tree.c:18
      => leaf_c * sla / patcharea = LAI * fpc_ind / (1 - exp(-k_pft * LAI))

    and summing that over a patch's stems gives `sum(leaf_c*sla)/patcharea` = the stand LAI the runtime
    forms as `sum(leaf_c*sla*nind)` (slow.jl::flux_feature_vector). `patcharea` cancels — it is never used.

    Guarded at LAI<=0: a leafless stem has leaf_c==0 so its true contribution is 0, while the
    `1 - exp(-k*LAI)` denominator goes to 0 there (0/0).
    """
    k = pl.col("Type").replace_strict(K_LIGHTEXT, return_dtype=pl.Float64)
    return (
        pl.when(pl.col("LAI") > 0.0)
        .then(pl.col("LAI") * pl.col("fpc_ind") / (1.0 - (-k * pl.col("LAI")).exp()))
        .otherwise(0.0)
    )


def _boundary_source(scenario):
    """The boundary join source + its keys, honoring the opt-in TRANSIENT boundary (ADR 0026).

    Default (env `BOUNDARY_WINDOW` unset): the per-CELL climatological MEAN of [gdd5, tas_cold_month,
    soil_depth] — time-constant, joined on ["Cell"] — i.e. byte-identical to the pre-0026 static boundary.

    ⚠ THE STATIC BRANCH IS SCENARIO-BLIND: it reads `tables/cell_year_feats.parquet`, which is the
    2000-2019 HISTORIC climatology, for BOTH scenarios. So a default-boundary `SCENARIO=ssp370` table
    conditions 2020-2100 rows on a frozen PRESENT-DAY establishment gate while its flux and state columns are
    genuinely transient. That is intended only for the per-scenario diagnostic artifacts; the multi-regime
    production path is `BOUNDARY_WINDOW=20` (ADR 0026), which is exactly why `run_pooled_slow_*.sh` require it.
    Do not read a default-boundary ssp370 artifact as a transient-boundary model.

    `BOUNDARY_WINDOW=W`: the TRANSIENT boundary — per-(Cell,Year) `gdd5`/`tas_cold_month` from the
    trailing-W-year table `cell_year_boundary_<scenario>_wW.parquet` (build_transient_boundary.py), joined on
    ["Cell","Year"], plus the STATIC per-cell `soil_depth` (soil is not time-varying). The boundary COLUMN
    order/names are unchanged — only the values become year-specific — so the `flux_feature_vector` /
    `live_flux_cond` feature-order contract (ADR 0023/0025) is preserved. co2 is appended by the caller
    (constant 369, ADR 0004). Returns (frame, join_keys)."""
    w = os.environ.get("BOUNDARY_WINDOW", "").strip()
    if not w:
        cyf = (pl.scan_parquet(CELL_YEAR_FEATS)
               .select(["Cell", "eco_diag_gdd_5", "tas_cold_month", "soil_depth"])
               .group_by("Cell").mean().collect())
        return cyf, ["Cell"]
    path = TRANSIENT_BOUNDARY.format(scenario=scenario, w=int(w))
    if not os.path.exists(path):
        raise SystemExit(f"FATAL: BOUNDARY_WINDOW={w} but transient boundary table missing: {path} "
                         f"(run: SCENARIO={scenario} WINDOW={w} python3 scripts/build_transient_boundary.py)")
    soil = (pl.scan_parquet(CELL_YEAR_FEATS).select(["Cell", "soil_depth"]).group_by("Cell").mean().collect())
    tb = (pl.read_parquet(path).select(["Cell", "Year", "eco_diag_gdd_5", "tas_cold_month"])
          .join(soil, on="Cell", how="left"))
    print(f"== TRANSIENT boundary (ADR 0026) W={w}: {path} ({tb.height} cell-years)")
    return tb, ["Cell", "Year"]


def _env_source(scenario):
    """The COPULA_ENV_COLS tail source + its join keys, honoring the opt-in TRANSIENT env (ADR 0108).

    Default (env `ENV_WINDOW` unset): the per-CELL time MEAN over `cell_year_feats.parquet` — time-constant
    and scenario-blind, joined on ["Cell"], i.e. byte-identical to the pre-0108 ADR-0037 tail. The mean is
    taken AFTER an explicit `cast(Float64)` because 4 of the 6 columns are stored `Float32` and polars
    accumulates a `Float32` mean in `Float32` (CLAUDE.md §4) — dropping the cast lands ~3.4e-7 relative away
    from the value the shipped artifacts were conditioned on.

    `ENV_WINDOW=W`: the TRANSIENT tail — per-(Cell,Year) trailing-W-year moisture descriptors from
    `cell_year_env_<scenario>_wW.parquet`, joined on ["Cell","Year"], exactly the ADR-0026 treatment the
    boundary pair already gets via `_boundary_source`. Column names and ORDER are unchanged; only the values
    become year- and scenario-specific.

    WHY IT EXISTS. Under the default tail every one of the six moisture columns is a frozen present-day
    constant, so a 2100 ssp370 stem is conditioned on the 2000-2019 climatology of its own cell, and the SLOW
    moisture climate FIT's establishment gates key on cannot reach the sampled marginal at all.
    ⚠ That does NOT mean the emulator has no trait response — the frozen tail is 6 of 14 columns, and
    `water_stress`/`soilmoist` (per-cell-year) plus the transient boundary pair are the other channel.
    Measured on the shipped `_t8` generation (scripts/diagnose_moisture_arm_response.py, 52 020 cells, OOS),
    the per-cell scenario response already tracks the C truth's with slope +0.85 (SLA) / +0.35 (Wooddens) /
    +0.16 (D95max) / +0.69 (minwscal). So this knob opens the frozen channel and is MEASURED against those
    slopes; it does not move a response off zero. The transient tables carry a real signal: global mean
    VPD +20.4 %, PET +4.9 %, humidity +19.9 % from 2019 to 2100.

    LOAD-BEARING, and it fails SILENTLY (ADR 0023): a table built with `ENV_WINDOW` must be consumed by a
    runtime that advances the env tail per YEAR — `src/components/slow.jl::live_flux_cond_env_series` — not
    by `live_flux_cond_env(env)`, which closes over one constant vector. The widths are IDENTICAL, so the
    construction-time width probe cannot catch the mismatch; only the manifest's `env_basis` line can.
    Returns (frame, join_keys)."""
    w = os.environ.get("ENV_WINDOW", "").strip()
    if not w:
        # NO year filter — the SAME basis as the static boundary this tail is appended to.
        # `cell_year_feats` is a HISTORIC climatology table (Year 2000-2019 only) and `_boundary_source`
        # reads it whole for every scenario. A `Year >= FIRSTYEAR[scenario]` filter here was a no-op for
        # `historic` but selected ZERO rows for `ssp370`, whose FIRSTYEAR is 2020 — making an ssp370
        # env-conditioned build die downstream with a message that blamed a coverage hole.
        have = pl.scan_parquet(CELL_YEAR_FEATS).collect_schema().names()
        missing = [c for c in COPULA_ENV_COLS if c not in have]
        if missing:
            raise SystemExit(f"FATAL: COPULA_ENV_COLS not in cell_year_feats: {missing}")
        envt = (pl.scan_parquet(CELL_YEAR_FEATS)
                .select(["Cell"] + COPULA_ENV_COLS)
                .group_by("Cell")
                .agg([pl.col(c).cast(pl.Float64).mean().alias(c) for c in COPULA_ENV_COLS])
                .collect())
        if envt.height == 0:
            raise SystemExit(
                f"FATAL: env aggregation over {CELL_YEAR_FEATS} produced ZERO cells — an EMPTY SOURCE, "
                f"not a coverage hole."
            )
        print(f"== STATIC env tail (ADR 0037): per-cell means over {CELL_YEAR_FEATS} ({envt.height} cells)")
        return envt, ["Cell"], "static_cell_mean"
    path = TRANSIENT_ENV.format(scenario=scenario, w=int(w))
    if not os.path.exists(path):
        raise SystemExit(f"FATAL: ENV_WINDOW={w} but transient env table missing: {path} (run: "
                         f"export MOISTURE=1; SCENARIO={scenario} WINDOW={w} "
                         f"python3 scripts/build_transient_boundary.py)")
    have = pl.scan_parquet(path).collect_schema().names()
    missing = [c for c in COPULA_ENV_COLS if c not in have]
    if missing:
        raise SystemExit(f"FATAL: COPULA_ENV_COLS not in {path}: {missing}")
    envt = (pl.read_parquet(path)
            .select(["Cell", "Year"] + COPULA_ENV_COLS)
            .with_columns([pl.col(c).cast(pl.Float64) for c in COPULA_ENV_COLS]))
    # A duplicated (Cell,Year) here would MULTIPLY conditioning rows in the join below and be invisible to a
    # `dropped = h_pre - h_post` guard (it goes negative). The builder already learned this on the streamed
    # aggregate (ADR 0036 §5b); assert it on every joined table, not only the one that produced it.
    if envt.select(["Cell", "Year"]).n_unique() != envt.height:
        raise SystemExit(f"FATAL: {path} has duplicate (Cell,Year) keys ({envt.height} rows, "
                         f"{envt.select(['Cell', 'Year']).n_unique()} distinct) — the join would duplicate rows.")
    yr = (int(envt['Year'].min()), int(envt['Year'].max()))
    print(f"== TRANSIENT env tail (ADR 0108) W={w}: {path} ({envt.height} cell-years, "
          f"{envt['Cell'].n_unique()} cells, Year {yr[0]}-{yr[1]})")
    return envt, ["Cell", "Year"], f"transient_w{int(w)}"


def _struct_axes_from_env() -> list[str]:
    """The requested DIAGNOSTIC struct axes, from env `STRUCT_AXES` (default OFF ⇒ byte-identical output).

    unset / empty  -> []                      (no Y_ files, no manifest lines — today's behaviour exactly)
    "1"/"yes"/"all"-> STRUCT_AXES_DEFAULT     (["agb", "Height"])
    otherwise      -> a comma list of `ind` column names, in the order given (appended in that order).

    Every name is VALIDATED against the frozen 29-col `ind_data.IND_COLUMNS` and rejected if it duplicates a
    production axis (that would write a second Y_<axis>.f64 over the trait one) or repeats within the list.
    Unknown/duplicate names FAIL LOUD rather than silently yielding a truncated or mislabelled table — the
    ADR-0031 lesson (a silently wrong column list cost months of artifacts).
    """
    raw = os.environ.get("STRUCT_AXES", "").strip()
    if not raw:
        return []
    if raw.lower() in ("1", "yes", "all"):
        axes = list(STRUCT_AXES_DEFAULT)
    else:
        axes = [a.strip() for a in raw.split(",") if a.strip()]
    known = set(ind_data.IND_COLUMNS)
    for i, ax in enumerate(axes):
        if ax not in known:
            raise SystemExit(f"FATAL: STRUCT_AXES={raw!r} names {ax!r}, which is not a column of the 29-col "
                             f"ind table (ind_data.IND_COLUMNS = {sorted(known)}).")
        if ax in COPULA_AXES:
            raise SystemExit(f"FATAL: STRUCT_AXES={raw!r} names {ax!r}, which is already a PRODUCTION copula "
                             f"axis ({COPULA_AXES}) — it would overwrite that axis's Y_{ax}.f64.")
        if ax in axes[:i]:
            raise SystemExit(f"FATAL: STRUCT_AXES={raw!r} repeats {ax!r}; each axis writes one Y_<axis>.f64.")
    print(f"== STRUCT axes (DIAGNOSTIC ONLY, never in the .rcop): {axes}")
    return axes


def _write_copula_table(agg, scenario, seed, cells, out_dir, firstyear) -> int:
    """MODE=copula (ADR 0025): per-STEM trait targets + the runtime-consistent flux+boundary conditioning.

    `agg` carries the per-(Cell,Patch,Year) flux drivers with the soilmoist coverage gate applied. Here:
    (1) attach the boundary tail via `_boundary_source` (static per-cell mean by default; per-(Cell,Year)
        TRANSIENT under `BOUNDARY_WINDOW`, ADR 0026);
    (2) scan the SURVIVING tree stems (`isdead==0`) for the trait axes — one row per living stem, the
        distribution to reproduce (mortality is trait-blind ⇒ community dist == establishment dist);
    (3) broadcast the conditioning onto each stem via an inner join.
    Conditioning column order == COPULA_COND_COLS == the runtime `live_flux_cond(s, feats)`. Writes Xc.f64
    (n×ncond row-major), one Y_<axis>.f64 per COPULA_AXES, cells.i64, manifest_copula.txt.

    Under the opt-in `STRUCT_AXES` (default OFF) the same per-stem rows also yield one Y_<axis>.f64 per
    DIAGNOSTIC struct axis, selected from the SAME stem scan and APPENDED after the production axes, plus the
    `nstruct`/`struct_axes` manifest lines. Everything else — Xc, cells.i64, the existing manifest lines, the
    STEM_CAP subsample (it operates on the whole `tbl`) — is unchanged, so the default output stays
    byte-identical and the production axes' downstream predictions stay bit-identical.
    """
    struct_axes = _struct_axes_from_env()
    cyf, bkeys = _boundary_source(scenario)
    cond = (agg.select(["Cell", "Patch", "Year"] + HEAD_COLS[:4])
            .join(cyf, on=bkeys, how="left").with_columns(pl.lit(CO2_CONST).alias("co2")))
    env_basis = "none"
    if COPULA_ENV_COLS:
        # The tail source: per-CELL time means (default) or per-(Cell,Year) TRANSIENT under ENV_WINDOW
        # (ADR 0108). INNER-joined and then asserted non-null: a silent null here would become a NaN in Xc,
        # and `is_not_null` does NOT catch NaN in polars (CLAUDE.md §4), so check both.
        envt, ekeys, env_basis = _env_source(scenario)
        bad = {c: int(envt[c].is_null().sum() + envt[c].is_nan().sum()) for c in COPULA_ENV_COLS}
        assert not any(bad.values()), f"null/NaN in the COPULA_ENV_COLS tail source: {bad}"
        h_pre = cond.height
        cells_pre = set(cond["Cell"].unique().to_list())
        cond = cond.join(envt, on=ekeys, how="inner")
        h_post = cond.height
        cells_lost = cells_pre - set(cond["Cell"].unique().to_list())
        assert h_post >= 0.98 * h_pre and not cells_lost, (
            f"COPULA_ENV_COLS join (on {ekeys}) dropped {h_pre - h_post} of {h_pre} conditioning rows "
            f"({100 * (1 - h_post / max(h_pre, 1)):.2f}%) and lost {len(cells_lost)} cells entirely "
            f"(e.g. {sorted(cells_lost)[:10]}) — a coverage hole, not a rounding loss"
        )
        print(f"== COPULA_ENV_COLS: appended {len(COPULA_ENV_COLS)} env column(s) {COPULA_ENV_COLS} "
              f"on basis '{env_basis}' (join keys {ekeys}) -> ncond={len(COPULA_COND_COLS)}")

    stem_filt = pl.col("Type").is_in(TREE_TYPES) & (pl.col("isdead") == 0)
    if cells:
        stem_filt = stem_filt & pl.col("Cell").is_in(cells)
    stems = (pl.scan_parquet(IND[scenario].format(seed=seed)).filter(stem_filt)
             .select(["Cell", "Patch", "Year"] + COPULA_AXES + struct_axes).collect(engine="streaming"))
    h0 = stems.height
    tbl = stems.join(cond, on=["Cell", "Patch", "Year"], how="inner").sort(["Cell", "Patch", "Year"])
    dropped = h0 - tbl.height
    drop_frac = dropped / max(h0, 1)
    print(f"== copula: {h0} surviving stems, {tbl.height} after conditioning-join "
          f"({dropped} dropped, {drop_frac:.4f})")
    if drop_frac > 0.02:  # same anti-silent-truncation guard as the count path
        raise SystemExit(f"FATAL: copula conditioning-join dropped {drop_frac:.3f} of stems "
                         f"(soilmoist coverage hole). scenario={scenario}.")
    # STEM_CAP (opt-in, default 0 = keep all → byte-identical): per-CELL subsample to at most STEM_CAP stems.
    # A cell's trait MARGINAL (+ its per-cell KS) is fully estimated by a few hundred stems, so capping keeps
    # the distribution while making the POOLED multi-regime copula (~730M stems across scenarios) tractable
    # (ADR 0026). Deterministic: a per-row hash of (Cell,Patch,Year) + row index, seeded by SEED, gives a
    # stable pseudo-random rank within each cell; keep the lowest STEM_CAP. Applied AFTER the coverage gate so
    # the drop_frac guard still sees the true join coverage.
    # ⚠ IT IS A CLUSTER SUBSAMPLE, NOT A PER-STEM ONE (corrected 2026-07-29). The hash is of
    # (Cell,Patch,Year), so every stem in one patch-year gets the SAME hash, and the `+ int_range` tiebreak
    # spans only 0..n while the hashes span the full u64 — so the rank orders whole PATCH-YEAR groups and the
    # cap keeps entire patch-years (plus one partial group at the boundary). For a trait marginal that is
    # acceptable (traits are drawn per PFT at establishment and mortality is trait-blind, so patch-years within
    # a cell are exchangeable), but it means (a) the effective sample size is patch-years, not stems, so
    # per-cell statistics from a capped table are noisier than the stem count suggests, and (b) any statistic
    # that must be reconciled with a per-patch-year quantity from the COUNT table (e.g. the stand-biomass
    # composite in plot_slow_emulator_validation.py) is on a DIFFERENT row universe. Never describe a capped
    # per-cell mean as an unbiased per-stem mean.
    cap = int(os.environ.get("STEM_CAP", "0"))
    if cap > 0:
        h_before = tbl.height
        tbl = (tbl.with_columns(
                   (pl.struct(["Cell", "Patch", "Year"]).hash(seed=seed) + pl.int_range(pl.len(), dtype=pl.UInt64))
                   .rank("ordinal").over("Cell").alias("_rk"))
               .filter(pl.col("_rk") <= cap).drop("_rk").sort(["Cell", "Patch", "Year"]))
        print(f"== STEM_CAP={cap}: {h_before} -> {tbl.height} stems "
              f"({tbl['Cell'].n_unique()} cells, median {tbl.height / max(tbl['Cell'].n_unique(), 1):.0f} stems/cell)")
    n = tbl.height
    if n == 0:
        raise SystemExit("FATAL: 0 copula stems after conditioning-join.")

    Xc = tbl.select(COPULA_COND_COLS).to_numpy().astype("<f8", copy=False)  # C-contiguous row-major n×ncond
    assert not np.isnan(Xc).any() and np.isfinite(Xc).all(), "non-finite in copula Xc"
    Xc.tofile(os.path.join(out_dir, "Xc.f64"))
    for ax in COPULA_AXES:
        col = tbl[ax].to_numpy().astype("<f8", copy=False)
        assert np.isfinite(col).all(), f"non-finite in axis {ax}"
        col.tofile(os.path.join(out_dir, f"Y_{ax}.f64"))
    # DIAGNOSTIC struct axes, same Y_<axis>.f64 layout and the same Xc row alignment, written AFTER the
    # production axes (the append order the manifest's struct_axes line records).
    for ax in struct_axes:
        col = tbl[ax].to_numpy().astype("<f8", copy=False)
        assert np.isfinite(col).all(), f"non-finite in struct axis {ax}"
        col.tofile(os.path.join(out_dir, f"Y_{ax}.f64"))
    tbl["Cell"].to_numpy().astype("<i8", copy=False).tofile(os.path.join(out_dir, "cells.i64"))
    # PER-ROW Year, aligned to Xc's rows exactly like cells.i64 (ADR 0108). Emitted UNCONDITIONALLY: without
    # it a per-(Cell,Year) quantity cannot be attached to an already-built table at all, and the Year is NOT
    # recoverable from Xc — a per-cell-year feature triple collides across two years in ~140 of 1.35M
    # historic cell-years (measured), so an inversion is ambiguous where it matters least visibly. Every
    # downstream consumer is key-driven, so the extra file + manifest line are inert to them.
    tbl["Year"].to_numpy().astype("<i8", copy=False).tofile(os.path.join(out_dir, "years.i64"))

    with open(os.path.join(out_dir, "manifest_copula.txt"), "w") as f:
        f.write(f"n\t{n}\n")
        f.write(f"ncond\t{len(COPULA_COND_COLS)}\n")
        f.write(f"naxes\t{len(COPULA_AXES)}\n")
        f.write("cond_cols\t" + " ".join(COPULA_COND_COLS) + "\n")
        f.write("axes\t" + " ".join(COPULA_AXES) + "\n")
        # The DIAGNOSTIC tail, emitted ONLY when requested — absent nstruct/struct_axes ⇔ no struct axes, so
        # every pre-existing table dir keeps parsing unchanged and `naxes`/`axes` keep meaning the 4
        # PRODUCTION axes. Consumers must default to zero/empty.
        if struct_axes:
            f.write(f"nstruct\t{len(struct_axes)}\n")
            f.write("struct_axes\t" + " ".join(struct_axes) + "\n")
        f.write(f"scenario\t{scenario}\n")
        f.write("years_tag\tyears.i64\n")
        # THE ENV-TAIL BASIS, in the artifact (ADR 0108). A static-tail and a transient-tail table have the
        # SAME ncond and the SAME cond_cols, so nothing else distinguishes them — and the runtime policies
        # they require (`live_flux_cond_env` vs `live_flux_cond_env_series`) are NOT interchangeable while
        # the construction-time width probe passes for both. This line is the only contract that can say so.
        f.write(f"env_basis\t{env_basis}\n")
        # Record the cap IN the artifact: a capped and an uncapped table are NOT interchangeable (the cap is a
        # patch-year cluster subsample), and a consumer previously could not tell them apart at all.
        f.write(f"stem_cap\t{cap}\n")
        f.write(f"ncells\t{tbl['Cell'].n_unique()}\n")
        f.write(f"firstyear\t{firstyear}\n")
        # fallback conditioning row x = column MEAN (a climatological center for the .rcop fallback field).
        xmean = [float(tbl[c].mean()) for c in COPULA_COND_COLS]
        f.write("x\t" + " ".join(repr(v) for v in xmean) + "\n")
        if cells and len(cells) == 1:
            f.write(f"cells\t{','.join(str(c) for c in cells)}\n")

    struct_note = f" + {len(struct_axes)} struct axes {struct_axes}" if struct_axes else ""
    print(f"== wrote copula table Xc {Xc.shape} + {len(COPULA_AXES)} axes{struct_note} "
          f"({tbl['Cell'].n_unique()} cells) to {out_dir}")
    for j, c in enumerate(COPULA_COND_COLS):
        print(f"   cond {c:16s} min={Xc[:, j].min():12.4g} max={Xc[:, j].max():12.4g} mean={Xc[:, j].mean():12.4g}")
    for ax in COPULA_AXES:
        col = tbl[ax].to_numpy()
        print(f"   axis {ax:10s} min={col.min():12.4g} max={col.max():12.4g} mean={col.mean():12.4g} std={col.std():12.4g}")
    for ax in struct_axes:
        col = tbl[ax].to_numpy()
        print(f"   struct-axis {ax:10s} min={col.min():12.4g} max={col.max():12.4g} "
              f"mean={col.mean():12.4g} std={col.std():12.4g}")
    return 0


def main() -> int:
    seed = int(os.environ.get("SEED", "1"))
    scenario = os.environ.get("SCENARIO", "historic")
    if scenario not in IND:
        raise SystemExit(f"SCENARIO must be one of {list(IND)} (got {scenario!r})")
    cells = [int(c) for c in os.environ.get("CELLS", "").split(",") if c.strip()] or None
    mode = os.environ.get("MODE", "count")
    if mode not in ("count", "copula"):
        raise SystemExit(f"MODE must be 'count' or 'copula' (got {mode!r})")
    default_out = f"{BASE}/slow_runtime_{scenario}" + (f"_seed{seed}" if seed != 1 else "")
    out_dir = os.environ.get("OUT", default_out)
    os.makedirs(out_dir, exist_ok=True)
    firstyear = FIRSTYEAR[scenario]

    # --- streaming aggregate straight from the LazyFrame (projection+predicate pushdown) ---
    filt = pl.col("Type").is_in(TREE_TYPES) & (pl.col("isdead") == 0)
    if cells:
        filt = filt & pl.col("Cell").is_in(cells)
    agg = (
        pl.scan_parquet(IND[scenario].format(seed=seed)).filter(filt)
        .group_by(["Cell", "Patch", "Year"]).agg(
            pl.len().alias("n_living"),
            pl.col("npp").sum().alias("bm_inc_cell"),
            # APPLIED npp = non-stagnating stems only (npp>0 & Height>0), mirroring the runtime applied_cell
            # (fast.jl:353-369: a cohort with bm_net<=0 i.e. bm_ind<=0, or height<=0, contributes 0). This is
            # the growth_eff numerator; bm_inc_cell (total) stays the head[0] flux. Approximation of the
            # per-cohort bm_net rule — exact parity is not reconstructable from the 29-col ind output.
            pl.col("npp").filter((pl.col("npp") > 0) & (pl.col("Height") > 0)).sum().alias("_applied_npp"),
            (pl.col("Height") * pl.col("fpc_ind")).sum().alias("_hfpc"),
            pl.col("fpc_ind").sum().alias("_fpc_sum"),
            pl.col("Height").max().alias("hmax"),
            pl.col("agb").sum().alias("agb"),
            pl.col("wscal_mean").mean().alias("_wscal_mean"),
            ((pl.col("Age") - 1).mean()).cast(pl.Float64).alias("age_mean"),
            # PER-PATCH stand LAI, reconstructed in-row (ADR 0035) — same patch, same >5 m stem population
            # as every other aggregate here. Replaces the joined cell-mean C LAI_STAND.
            patch_stand_lai_expr().sum().alias("lai"),
        )
        .collect(engine="streaming")
    )
    print(f"== scenario={scenario} seed={seed} cells={'ALL' if not cells else cells}: "
          f"{agg.height} (Cell,Patch,Year) groups")

    agg = agg.with_columns(
        (1.0 - pl.col("_wscal_mean")).alias("water_stress"),
        (pl.col("_hfpc") / pl.max_horizontal(pl.col("_fpc_sum"), pl.lit(EPS))).alias("hmean"),
        pl.min_horizontal(pl.col("_fpc_sum"), pl.lit(1.0)).alias("fpc"),
    )

    # --- REAL feature join (soilmoist); inner + height-assert = the anti-NaN guard ---
    # `lai` is NO LONGER joined (ADR 0035) — it is reconstructed per-patch in the aggregate above, so the
    # only remaining external feature table is the root-zone year-end soilmoist. SOIL_TBL_PATH overrides the
    # scenario default (subset verification, seed/scenario variants).
    sm = pl.read_parquet(os.environ.get("SOIL_TBL_PATH", SOIL_TBL[scenario])).select(["Cell", "Year", "soilmoist"])
    h0 = agg.height
    cells_before = set(agg["Cell"].unique().to_list())
    agg = agg.join(sm, on=["Cell", "Year"], how="inner")
    dropped = h0 - agg.height
    drop_frac = dropped / max(h0, 1)
    cells_lost = cells_before - set(agg["Cell"].unique().to_list())
    print(f"== after soilmoist inner-join: {agg.height} rows ({dropped} dropped, {drop_frac:.4f}); "
          f"{len(cells_lost)} cells fully lost")
    # COVERAGE GATE (the anti-silent-drop guard): soilmoist should cover every tree (Cell,Year). A large
    # drop or an entirely-lost cell = a coverage hole in the feature table (e.g. an incomplete daily run) —
    # fail loud rather than silently train on a biome-truncated global set.
    if drop_frac > 0.02 or cells_lost:
        raise SystemExit(
            f"FATAL: feature-join coverage hole — {dropped} rows ({drop_frac:.3f}) dropped, "
            f"{len(cells_lost)} cells fully lost (e.g. {sorted(cells_lost)[:10]}). "
            f"Check cell_year_soilmoist_ye completeness for scenario={scenario}.")
    # growth_eff — MATCH THE RUNTIME's zero-leaf-area guard (fast.jl:369):
    #     growth_eff = leaf_area > 0 ? applied_cell / leaf_area : zero(T)
    # The C oracle guards it the same way (`if(leafarea_real > 1e-6) … else mort_npp = 1`,
    # mortality_tree_ind.c:95-99). This USED to be `applied_npp / max(lai, EPS)`, which turns a joined
    # `LAI_STAND == 0` into `applied_npp * 1e6` — a train/inference shift on a primary mortality driver
    # (ADR 0023). Measured by scripts/diagnose_lai0_growth_eff.py: it never fired on a seed1 table (0 of
    # 23.9M tree groups) but a seed2 `ind` joined against that seed1 lai table hit 21 501 groups /
    # 204 867 stems and max 1.19e9 — a CROSS-SEED join artifact (one lai table existed, seed1-derived).
    # ADR 0035 makes that class STRUCTURALLY IMPOSSIBLE: `lai` is now reconstructed from the same `ind`
    # rows being aggregated, so it cannot come from another trajectory, and `lai == 0` for a group with
    # positive npp cannot occur (a stem with npp>0 and Height>5 m has leaf carbon). The guard + the
    # GROWTH_EFF_MAX assertion stay as the standing alarm, not because a known path can still trip them.
    agg = agg.with_columns(
        pl.when(pl.col("lai") > 0.0)
        .then(pl.col("_applied_npp").fill_null(0.0) / pl.col("lai"))
        .otherwise(0.0)
        .alias("growth_eff")
    )
    ge_max = float(agg["growth_eff"].max())
    n_lai0 = int(agg.filter(pl.col("lai") <= 0.0).height)
    print(f"== growth_eff: max={ge_max:.6g} mean={float(agg['growth_eff'].mean()):.6g}; "
          f"{n_lai0} rows with lai<=0 forced to 0 ({n_lai0 / max(agg.height, 1):.5f})")
    # A sane-magnitude assertion, because the coverage guards structurally CANNOT catch this: the feature
    # tables are complete, so a zero lai is PRESENT, not missing (drop_frac/cells_lost both stay clean).
    # Observed maxima are ~3-4e4; 1e6 is the EPS-class blow-up floor, so this fails loud with wide margin.
    if ge_max > GROWTH_EFF_MAX:
        raise SystemExit(
            f"FATAL: growth_eff max {ge_max:.6g} exceeds GROWTH_EFF_MAX={GROWTH_EFF_MAX:.6g} — a tiny-lai "
            f"divisor blow-up (conditioning on it is a live train/inference hazard). {n_lai0} rows had "
            f"lai<=0 — since ADR 0035 that should be unreachable (lai is reconstructed in-row), so a hit here "
            f"means the reconstruction or the stem filter changed.")

    # MODE=copula forks here: `agg` already carries the 4 flux drivers (with the soilmoist coverage gate
    # applied); the copula path needs those + the per-cell boundary, broadcast onto per-STEM trait targets.
    if mode == "copula":
        return _write_copula_table(agg, scenario, seed, cells, out_dir, firstyear)

    # --- KEY-SET INVARIANT (added 2026-07-29; this class of corruption was SILENT and shipped) ---
    # `collect(engine="streaming")` on the group_by above is not deterministic in the KEY SET it emits at
    # global scale, not merely in float summation order as the module docstring used to say. Two runs of the
    # ssp370 build over the SAME `ind` parquet produced 99 023 397 and 99 028 310 rows: 141 cells differed,
    # 4 913 rows were missing net, and 12 cells came out with EXTRA rows. Nothing caught it — the two coverage
    # gates only watch the FEATURE joins, and `dropped = h0 - height` goes negative on duplication so
    # `drop_frac > 0.02` can never fire. A duplicated key is then AMPLIFIED by the AR self-join below (a key
    # present twice on both sides yields four rows), and a missing key silently removes two training rows.
    # So: assert the key set, and take the AR lag with a window shift instead of a 100M x 100M self-join, which
    # removes the amplification path entirely. Equivalent to the old inner join whenever keys are unique —
    # verified by rebuilding the historic table and comparing it byte-for-byte.
    nkeys = agg.select(["Cell", "Patch", "Year"]).n_unique()
    if nkeys != agg.height:
        raise SystemExit(
            f"FATAL: the streaming aggregate emitted {agg.height - nkeys} DUPLICATE (Cell,Patch,Year) keys "
            f"({agg.height} rows, {nkeys} distinct). This is a polars streaming-group_by determinism failure, "
            f"not a data property — the ind table has one row per stem per patch-year. Re-run; if it recurs, "
            f"drop engine='streaming' for the aggregate or partition the scan by cell block.")

    # --- AR state: previous-year n_living for the SAME (Cell,Patch) ---
    agg = agg.sort(["Cell", "Patch", "Year"])
    tbl = (agg.with_columns(
               pl.col("n_living").shift(1).over(["Cell", "Patch"]).alias("n_prev"),
               pl.col("Year").shift(1).over(["Cell", "Patch"]).alias("_prev_year"))
           .filter(pl.col("_prev_year") + 1 == pl.col("Year"))   # drops the first year per (Cell,Patch),
           .drop("_prev_year"))                                  # and any gap in a (Cell,Patch) year run

    # --- boundary: per-CELL climatological mean (static, default) OR per-(Cell,Year) TRANSIENT (ADR 0026) ---
    cyf, bkeys = _boundary_source(scenario)
    tbl = (tbl.join(cyf, on=bkeys, how="left").with_columns(pl.lit(CO2_CONST).alias("co2")))
    tbl = tbl.sort(["Cell", "Patch", "Year"])  # MUST sort AFTER all joins → deterministic X row order
    n = tbl.height
    if n == 0:
        raise SystemExit("FATAL: 0 training rows after joins (check feature-table coverage / cells).")
    print(f"== {n} training rows (with AR state); {nkeys} distinct (Cell,Patch,Year) keys in the aggregate")
    if tbl.select(["Cell", "Patch", "Year"]).n_unique() != n:
        raise SystemExit("FATAL: duplicate (Cell,Patch,Year) rows AFTER the AR/boundary joins — a boundary "
                         "table with a non-unique key would do this; check tables/cell_year_*.parquet.")

    # --- X / y ---
    colnames = HEAD_COLS + BOUNDARY_COLS
    X = tbl.select(colnames).to_numpy().astype("<f8", copy=False)  # C-contiguous row-major n×15 (no-op copy on x86 LE)
    y = tbl["n_living"].to_numpy().astype("<f8", copy=False)
    assert not np.isnan(X).any(), "NaN in X (join coverage hole slipped through)"
    assert np.isfinite(X).all(), "non-finite in X"

    # --- per-cell seed sidecar (n_init/age0/boundary) with a MIN_YEARS floor ---
    cell_meta = (tbl.group_by("Cell").agg(
        pl.col("n_living").median().alias("n_init"),
        pl.col("age_mean").median().alias("age0"),
        pl.col("eco_diag_gdd_5").first(),
        pl.col("tas_cold_month").first(),
        pl.col("soil_depth").first(),
        pl.col("co2").first(),
        pl.len().alias("n_rows"),
    ).sort("Cell"))
    weak = cell_meta.filter(pl.col("n_rows") < MIN_YEARS).height
    if weak:
        print(f"== NOTE: {weak} cells have < {MIN_YEARS} rows (their n_init/age0 medians are less robust)")
    cell_meta.write_parquet(os.path.join(out_dir, "cell_meta.parquet"))

    X.tofile(os.path.join(out_dir, "X.f64"))
    y.tofile(os.path.join(out_dir, "y.f64"))
    # per-row Cell id (aligned to X rows, same Cell,Patch,Year sort) → enables a rigorous held-out-BY-CELL
    # generalization eval in train_slow_drf.jl (DEVELOPMENT_PLAN §5: hold out CELLS, not rows).
    tbl["Cell"].to_numpy().astype("<i8", copy=False).tofile(os.path.join(out_dir, "cells.i64"))
    # PER-ROW Year, aligned to X's rows (ADR 0108) — same rationale as the copula path: it makes any
    # per-(Cell,Year) quantity attachable to a frozen table, and the Year is not recoverable from X.
    tbl["Year"].to_numpy().astype("<i8", copy=False).tofile(os.path.join(out_dir, "years.i64"))
    p = len(colnames)
    with open(os.path.join(out_dir, "manifest.txt"), "w") as f:
        f.write(f"n\t{n}\n")
        f.write(f"p\t{p}\n")
        f.write(f"nhead\t{len(HEAD_COLS)}\n")
        f.write(f"nboundary\t{len(BOUNDARY_COLS)}\n")
        f.write("colnames\t" + " ".join(colnames) + "\n")
        f.write("target\tn_living\n")
        f.write(f"scenario\t{scenario}\n")
        f.write(f"ncells\t{tbl['Cell'].n_unique()}\n")
        f.write(f"firstyear\t{firstyear}\n")
        f.write("years_tag\tyears.i64\n")
        f.write("cell_meta\tcell_meta.parquet\n")
        # single-cell demo: ALSO emit the scalar boundary/n_init/age0 so train_slow_drf.jl (unchanged)
        # still produces the committed Hainich demo meta (slow-drf-pipeline step 2).
        if cells and len(cells) == 1:
            bvals = [float(cell_meta[c][0]) for c in ["eco_diag_gdd_5", "tas_cold_month", "soil_depth"]] + [CO2_CONST]
            f.write("boundary\t" + " ".join(repr(v) for v in bvals) + "\n")
            f.write(f"n_init\t{float(cell_meta['n_init'][0])}\n")
            f.write(f"age0\t{float(cell_meta['age0'][0])}\n")
            f.write(f"cells\t{','.join(str(c) for c in cells)}\n")

    print(f"== wrote X {X.shape}, y ({n},), cell_meta ({cell_meta.height} cells), manifest to {out_dir}")
    print(f"== target n_living: min={int(y.min())} max={int(y.max())} median={np.median(y):.1f} mean={y.mean():.2f}")
    for j, c in enumerate(colnames):
        print(f"     {c:16s} min={X[:, j].min():12.4g} max={X[:, j].max():12.4g} mean={X[:, j].mean():12.4g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
