# LINE M — multi-cell coupled S+F+E (branch `line/M`, worktree `wt-M`) — P3

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/M/JOURNAL.md` (append-only). Decisions: ADR block **0050–0069**.
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## ✅ RESOLVED — the JET 0.12.0 blocker (pinned on `main` in `47c6407a`, 2026-07-28)

JET **0.12.0** removed the `target_defined_modules` configuration that `test/jet_tests.jl:6` passes, so
`JET.test_package` died with `JETConfigError` and `test (1)` (Julia 1.12) errored **repo-wide** on a fresh
resolve — `test/Project.toml` had no `JET` `[compat]` entry. Confirmed repo-wide, not line-M: identical
failure on line/M `693322fa` (job 90278705919, a docs+tests-only diff) **and** line/O `11ef8d89`
(job 90275445875); `test (lts)` stayed green because JET 0.11+ needs Julia ≥1.12 so 1.10 resolves 0.9.20.

Fixed with `JET = "0.9, 0.11"` in `test/Project.toml` `[compat]`. **Landed directly on `main`** rather than on
this branch, because that file is integrator-owned (ADR 0029) and the breakage blocked all four lines from
merging; both pinned versions were already in the shared depot, so the compute-node warm needs no new tarball.
**[TODO, not this line]** lift the pin by migrating `jet_tests.jl` to JET 0.12's replacement scoping API.

## 📌 The PINNED Component-S artifact — **`_t8`**, adopted 2026-07-30 (frozen S→M contract, ADR 0023)

**Pinned pair** (`/p/tmp/jamirp/emulator_global/`, line S's, read-only to this line):

| Artifact | sha256 | bytes | mtime |
|---|---|---|---|
| `drf_forest_global_pooled_w20_t8.drf` | `b8e59a4ab1d59f2fab5c31757947e870a960c85f22d71a2f31ca292778e5b483` | 51554735 | 2026-07-29 15:14 |
| `recruit_copula_global_pooled_w20_t8.rcop` | `016f51117c6af79fe2de5e1c25e4714584f8bf319212225b9af3ffb0ea7dc444` | 129031922 | 2026-07-29 22:49 |

Per-cell seed + boundary taken from **`slow_runtime_historic_t8/cell_meta.parquet`**
(sha256 `d208ca0797161b86130e8d1d9693a3dcc1c7408946887031e0374db96b88012e`, 53,699 cells) — provenance
recorded in `references/M_slow_init_meta.json`.

**Why `_t8` and not `_t7`/`pooled_w20`:** `_t8` re-derives the same population (ADR 0031's complete seven
tree PFTs) on the **ADR-0035 feature bases** (`soilmoist` = root-zone year-end plant-available fraction,
`lai` = the per-patch reconstruction). `_t7`'s OOS numbers stay valid as *offline* measurements, but a
COUPLED run on `_t7` inherits the retired bases — exactly what M3 must avoid. The original `pooled_w20`
pin was never trained on `semiarid_sahel` at all.

**VERIFIED INDEPENDENTLY (2026-07-30), not taken from S's handoff note:**
- `DRF.load_forest` → 1.46 s, `nfeat = 15`, 150 trees. Meta `colnames` = the 11 head features + boundary
  tail `eco_diag_gdd_5 tas_cold_month soil_depth co2` — **identical** to `slow.jl::flux_feature_vector`.
- `DRF.load_copula` → 3.0 s, `axis_names = [SLA, Wooddens, D95max, minwscal]`, and **`nfeat = 8` on every
  axis forest**. That last number is the one that actually proves ADR 0036's new diagnostic axes
  (`agb`, `Height`) are **absent** from the `.rcop` — the meta only *claims* 4 axes. `cond_cols` is
  **identical** to `live_flux_cond` = `vcat(feats[1:4], s.boundary)`.
- Coverage read out of the parquet directly: both `_t8` tables cover **5/5** biome cells
  (historic 53,699 · ssp370 58,496).
- **Bit-identity cross-check:** `M_cells.csv`'s `temperate_hainich` row (`n_init` 11.0, `age0`
  43.55555555555556, boundary `1863.695068359375 0.21838709712028503 1.5173755884170532 369.0`) is
  **exactly** the committed `drf_forest_hainich_meta.txt`'s own baked values. Same quantity, same
  upstream, independently derived ⇒ the extractor pulls the right columns in the right ORDER. Asserted
  as an equality in `biome_coupled_tests.jl` (which is why the fixture is emitted at `repr`/`%.17g` —
  `%.6f` truncated that gdd5 to 1863.695068, and these values feed DRF split thresholds).

So the per-cell boundary vector this line builds is exactly
`[eco_diag_gdd_5, tas_cold_month, soil_depth, co2]` — the columns `cell_meta.parquet` carries.

**Nothing about the FEATURE CONTRACT changed** across `pooled_w20` → `_t7` → `_t8`: same 15 count
features in the same order, same 8 `live_flux_cond` cond cols, same 4 axes. These are basis + population
+ version bumps, not ADR-0023 breaks.

> **✅ UPDATE from line S, 2026-07-28 15:46 — the POOLED `_t7` pair is now COMPLETE and verified.** Your
> rejection below was correct at the time and is now satisfied. Both halves exist and **both deserialize**
> (checked, not just built):
> - `drf_forest_global_pooled_w20_t7.drf` — loads in 1.5 s, 150 trees, `nfeat = 15` (11 head + 4 boundary).
> - `recruit_copula_global_pooled_w20_t7.rcop` (128 MB) — loads in 2.9 s, axes
>   `[SLA, Wooddens, D95max, minwscal]`, **8 cond cols in exactly the `live_flux_cond` order**
>   (`bm_inc_cell growth_eff water_stress soilmoist eco_diag_gdd_5 tas_cold_month soil_depth co2`), 4 marginal
>   forests, latent corr intact. Meta reports 58 766 cells.
>
> Pooled K-fold-by-cell OOS trait fidelity on this pair (nqrmse): **SLA 0.005 · Wooddens 0.016 · D95max 0.012 ·
> minwscal 0.004**. The count side is in `lines/S/STATE.md` §Status (every metric within ≈0.003 R² of `tree5`).
> Built by `VERSION=t7 scripts/run_pooled_slow_copula.sh` (job 1622337) + `run_pooled_slow_training.sh` (1622134).
>
> **Two things to carry into the swap:** (1) `n_init`/`age0` are version-coupled, exactly as you documented —
> take them from the `_t7` `cell_meta.parquet`, never mixed with the old pin. (2) The `historic`-only `_t7`
> `.rcop` (job 1622131) was still running at handoff; if you want the historic-only pair rather than the pooled
> one, check `logs/gcopula_historic_t7.*` for `JOB DONE` first. Nothing about the **feature contract** changed —
> only the training population (ADR 0031), so this is not an ADR-0023 break.

> **✅ UPDATE from line S, 2026-07-30 — the `_t8` GENERATION supersedes `_t7`. Re-pin deliberately.**
> `_t7` is intact and readable; nothing was mutated. `_t8` is the same population (ADR 0031's complete seven
> tree PFTs) re-derived on the **ADR-0035 feature bases** — `soilmoist` = root-zone year-end plant-available
> fraction of WHC, `lai` = the per-patch reconstruction. **`_t7`'s OOS numbers stay valid as OFFLINE
> measurements, but a COUPLED run on `_t7` inherits the retired bases**, which is exactly what M3 needs to
> avoid. Both halves LOAD-VERIFIED (deserialized, not just built):
> - `drf_forest_global_pooled_w20_t8.drf` — 1.4 s, 150 trees, `nfeat = 15` (11 head + 4 boundary).
> - `recruit_copula_global_pooled_w20_t8.rcop` (129 MB) — 3.0 s, axes `[SLA, Wooddens, D95max, minwscal]`,
>   **8 cond cols in exactly the `live_flux_cond` order**, 4 marginal forests, latent corr intact.
> - Tables: `slow_count_pooled_w20_t8/` (121 495 658 rows / 58 588 cells) + `slow_copula_pooled_w20_t8/`.
>
> Pooled K-fold-by-cell OOS: count **R² 0.9824 / RMSE 0.697** (held-out-CELL test R² 0.9824; hold-out-by-
> SCENARIO 0.982 / 0.9818, so the unseen-regime gap stays flat); trait `nqrmse` **SLA 0.004 · Wooddens 0.021 ·
> D95max 0.008 · minwscal 0.004**. Per-scenario `_t8` pairs also exist (`historic`, `ssp370`) if you want one.
>
> **Nothing about the FEATURE CONTRACT changed** — same 15 count features in the same order, same 8
> `live_flux_cond` cond cols, same 4 axes. So this is not an ADR-0023 break: it is a basis + version bump.
>
> **Three things to carry into the swap:**
> 1. `n_init`/`age0` are version-coupled — take them from the **`_t8`** `cell_meta.parquet`, never mixed with
>    a `_t7` or older pin. All five biome cells are covered (the `_t8` historic table has 53 699 cells, the
>    ssp370 one 58 496, same as `_t7`).
> 2. The **copula table now carries two extra DIAGNOSTIC axes** (`agb`, `Height` — ADR 0036) for validating the
>    emulator's biomass/size distributions. They are **NOT in the `.rcop`**: it declares exactly the 4
>    production axes, verified by deserializing it. `make_recruit_to_pools` is untouched. Nothing for M to do.
> 3. A `polars` streaming-determinism defect was found and fixed while building this generation (CLAUDE.md §4,
>    ADR 0036 §5b). **The pooled artifacts you pin were never affected** — the pooled table's row count is
>    exactly `22 467 348 + 99 028 310`, the correct ssp370 row set. Only the per-scenario static ssp370 table
>    was hit, and it has been rebuilt. If you build any table of your own with a streamed `group_by` over the
>    `ind` parquets, assert your own key set: the usual `drop_frac` guard cannot detect duplication.

**REJECTED at the time of writing — `*_t7` (superseded by the update above):** `drf_forest_global_pooled_w20_t7.drf` and
`drf_forest_global_historic_t7.drf` appeared **today** (58,587 cells) and line S was still mid-production when
this was written (job 1622131 `gcopula_historic_t7` RUNNING) — **there is no matching `_t7` `.rcop`**. Adopting
a half-published retrain is exactly the "never adopt a re-trained artifact silently" trap (ADR 0023). Moving to
`_t7` is an **integration point with line S** once S publishes a complete, versioned pair.

**Consequence for the M2 gate:** these artifacts live on `/p/tmp` (DVC, not git), so a CI test cannot load
them — CI runs on GitHub runners with no cluster. Split it: the **committed** demo artifact
(`test/testitems/references/drf_forest_hainich.drf`) drives the CI conservation/determinism/byte-identity gate
(closure is artifact-independent), and the pinned global pair drives the cluster-only per-cell science (M3).

### ✅ RESOLVED — the cell-coverage blocker (was: `pooled_w20` could not serve all five cells)

Found 2026-07-28 by `scripts/extract_cell_slow_init.py`'s completeness gate, *not* by inspection, and
**fixed 2026-07-30 by re-pinning to `_t8`**. Cell coverage of the `cell_meta.parquet` tables:

| table | ncells | biome cells present |
|---|---|---|
| `slow_count_historic_w20/`, `slow_runtime_historic/` (the OLD pin's pool) | 44,328 | **3/5** — no `semiarid_sahel`, no `tropical_amazon` |
| `slow_count_ssp370_w20/`, `slow_runtime_ssp370/` (the OLD pin's pool) | 53,566 | **4/5** — no `semiarid_sahel` |
| `slow_*_historic_*_t7/`, **`slow_runtime_historic_t8/`** | 53,699 | **5/5** |
| `slow_count_ssp370_w20_t7/`, **`slow_runtime_ssp370_t8/`** | 58,495 / 58,496 | **5/5** |

`semiarid_sahel` (18371) was in NEITHER table the original `pooled_w20` artifact was trained on, so that
DRF had never seen the cell and there was no honest `n_init`/`age0` for it at that version. The lesson to
keep: **read coverage out of the parquet yourself** — a meta's stated cell count and a sibling line's
handoff note are both one level removed from the thing you actually need.

### Two verified facts that constrain how per-cell S state may be sourced

1. **`n_init`/`age0` are version-COUPLED — never mix them across artifact versions.** They are the per-cell
   **median over the training years** of the count target `n_living` and of `age_mean`
   (`build_slow_runtime_table.py:320-332`, `MIN_YEARS=3`), i.e. statistics *of the training window*, not
   properties of the cell. Measured on the 44,328 cells shared by `slow_runtime_historic` and its `_t7`
   retrain: `n_init` differs for **15,665** cells (max |Δ| **24** individuals), `age0` for **22,542**
   (max |Δ| **85** years). Corollary: they are also **not** derivable from the committed single-year
   `M_individuals_<name>_2010.csv` canopy — different statistic — so that shortcut is closed.
2. **The 4 boundary columns are invariant across VERSIONS but not across SCENARIOS.** Same-scenario,
   different training version (`slow_runtime_historic` vs `_t7`): byte-identical for all 44,328 shared cells.
   Different scenario (`slow_count_historic_w20` vs `slow_count_ssp370_w20`): `eco_diag_gdd_5` differs by up
   to **1513** GDD and `tas_cold_month` by **8.84 °C** on 43,901 shared cells — physically correct, they are
   *climate* diagnostics of different climates. **Therefore a POOLED artifact has two boundary rows per cell,
   and a single baked `boundary` is a historic-climate snapshot.** That promotes M2 step 3 (per-cell
   `ClimBuf`, or a baked `boundary_series`) from optional to **required** for the pooled pin — it is the only
   way the boundary tracks the year (ADR 0026/0027). `run.jl` already owns the `climbuf=` kwarg and enforces
   that a `ClimBuf` and a baked `boundary_series` are mutually exclusive.

## NEXT — start here

**M1, M2 DONE. The M3 BLOCKER is now DIAGNOSED AND FIXED (2026-07-30, ADR 0051)** — the `water_stress`
runtime↔training shift that the last two handoffs said must be settled *before* M3 draws per-cell
conclusions. It was a **quantity** mismatch, not an aggregation one: the C's `wscal` is a POTENTIAL leaf-on
index, F_diff's was the realized supply/demand ratio. Landed opt-in (`WaterParams.wscal_leafon`, default
`false` ⇒ every baseline byte-identical); Hainich's `water_stress` goes 0.3050 → 0.0034 against a C truth
of 0.0014. Full write-up: ADR 0051; the two-sided default flip and the boreal caveat are in "the contracts
you consume" and "Line-local gotchas" above. **Read those two before running M3.**

**M3 — coupled multi-cell validation vs the C truth. The P3 gate, and now unblocked.** Everything it needs
is on disk; no new HPC run is required. In priority order:

1. **DECIDE THE `wscal_leafon` QUESTION FIRST — it changes every number M3 will report.** Options: (a) raise
   the two-sided integration with line S and flip the default (M's recommendation — it is the C's actual
   expression, and it is better in 4 of 5 cells, one to within the noise floor); or (b) run M3 with
   `wscal_leafon=true` passed explicitly while the default stays off, and say so in every result. **Do not
   run M3 on the default `false` and report it as fidelity** — the Sahel loses 36 % of its trees to the
   shift. If you take (a): flip `WaterParams.wscal_leafon` to `true`, have S change
   `slow_production_drf_tests.jl:168` to `Set(String[])` in the same integration, and re-measure/regenerate
   every coupled baseline in that one change (guardrail 4 — deliberate, not incidental).
2. **Then score per-cell demography + trait distributions** against the annual `ind` parquet and the
   **seed1-vs-seed2 noise floor** — reuse `scripts/noise_floor_vs_emulator.py` (line S's, read-only), and
   `scripts/wscal_c_truth_diagnosis.py` is this line's worked example of the pattern (derive the C column
   exactly as the training table forms it, report error in units of the floor). Report held-out **cells and
   scenarios** separately. Use the PINNED `_t8` pair (`drf_forest_global_pooled_w20_t8.drf` +
   `recruit_copula_global_pooled_w20_t8.rcop`); wire the copula with
   `RecruitCopula{Float64}(cop, af, x, make_recruit_to_pools(axes), live_flux_cond)` — pattern in
   `test/testitems/slow_oracle_traits_tests.jl:89`. SLURM only (~180 MB, ~4.5 s just to deserialize);
   `scripts/wscal_leafon_probe.jl` is a ready 5-cell coupled driver to copy.
   **Caveat to carry:** the CI gate deliberately uses the committed Hainich demo forest (CI has no cluster),
   so it proves conservation/determinism, NOT per-cell count skill.
3. **The cheap win, STILL unclaimed:** the four single-cell C runs
   `/p/tmp/jamirp/esm_land_daily/daily_2000_2019_M_biome_val_c{52059,33335,18371,12045}_seed1` carry
   `a_lai_stand` / `a_fpc_stand` / `d_gpp` / `d_transp` / `d_swc` / `d_fapar` — a per-cell **F_diff-vs-C**
   oracle for four new biomes, i.e. M3's F-side evidence with no new HPC run. Use the `fdiff-validate` skill.
   **Do cell 52059 first and include `rootmoist`:** it doubles as the falsifiable test of the boreal
   soil-ice hypothesis (gotcha list above), which is the one part of ADR 0051 left open.

**Then M4 (resilience battery)** — 4 stubs still `@test_skip`; reimplement from Bathiany et al. 2024
(doi:10.1111/gcb.17613), never from LPJ_resilience (no licence).

**Small, still open:** `GATE=no` in `extract_cell_soilcolumn.py` leaves no trace in the emitted artifacts;
consider stamping the gate verdict into the header + meta. Also: `daily_step`/`daily_step_ml`
(`fdiff.jl:662,850`) still use the realized-ratio `wscal` — harmless (their `wscal` feeds no conditioning
feature) but a second definition in the tree; unify when convenient (ADR 0051 §Consequences).

## Scope + ownership (ADR 0029)

**You own (exclusive):**
- **`src/run.jl`, `src/interface.jl`** — the coupling seam. Other lines request changes here through you.
- `scripts/{run_coupled_biomes.jl,extract_biome_forcing.py}` + the new per-cell extractors
- `test/testitems/{biome_coupled,coupled_run,resilience_battery,rollout_stability}_tests.jl`
- `lines/M/*`, `changelog.d/M-*.md`, ADRs 0050–0069

**Do NOT touch:** `src/components/slow.jl`, `src/drf.jl`, `src/climbuf.jl` (line S) ·
`src/components/energy.jl` (line E) · `ext/` (line O) · `Project.toml` (integrator).
Shared, additive-only: `src/LPJmLFITEmulator.jl` (inside `# ── line M ──`), `CLAUDE.md`, `MEMORY.md`.

**SLURM tag prefix:** `M-` · other lines' `/p/tmp` artifacts are **read-only**.

## The contracts you consume (frozen — do not edit the other side)

- **From S:** `FluxDrivenSlowEmulator(fc, forest; boundary=, boundary_series=, n_init=, age0=, k_cap=,
  recruit_copula=, seed=)`, the `flux_feature_vector` order, `live_flux_cond`, the `.drf`/`.rcop` format, the
  `cell_meta.parquet` schema. **Pin a specific versioned artifact path** in your driver; if S needs to change
  the feature contract it is an integration point (both sides land together) — never adopt a re-trained
  artifact silently, because train/inference consistency is load-bearing (ADR 0023).
- **From S — OPEN INTEGRATION POINT raised 2026-07-28 (line S milestone S1b, ADR 0031):** Component S's
  training population was widened from `TREE_TYPES = [1,2,3,4,5]` to FIT's COMPLETE tree set `[0..6]` — the old
  list silently dropped the tropical broadleaved evergreen (id 0) + the boreal larch (id 6) = **32.5 % of
  survivor tree stems** and made **16.7 % of tree-bearing cells** (the tropical belt + Siberian larch)
  invisible. **The feature contract is UNCHANGED** (`flux_feature_vector` / `live_flux_cond` order, the
  `.drf`/`.rcop` format, the `cell_meta.parquet` schema) — only the training *population*, so this is not an
  ADR-0023 break and needs no runtime change. What DOES change for you:
  - **New versioned artifacts, `t7`** (the orchestrators now take `VERSION=<tag>`; the pre-0031 files are
    untouched): `drf_forest_global_pooled_w20_t7.drf` (+ meta) is BUILT and validated; the pooled
    `recruit_copula_global_pooled_w20_t7.rcop` follows. **Re-pin deliberately** — do not adopt silently.
  - **`cell_meta.parquet` gains ~4 600 cells** (pooled 53 993 → **58 587**), i.e. previously-invisible tropical
    and larch cells now have `n_init`/`age0`/boundary. Your multi-cell driver's coverage grows accordingly;
    check any hard-coded cell list or expected-count assertion.
  - Count skill is essentially unchanged (every metric within ≈0.003 R²; see `lines/S/STATE.md` §Status), so
    expect no coupled-behaviour surprise from the count side — but the *set of runnable cells* is larger.
- **From S — ✅ DONE 2026-07-28, S1c landed (ADR 0032 closed → ADR 0034). Two things here concern you.**
  The committed `test/testitems/references/drf_forest_hainich.drf` + `_meta.txt` were regenerated off the
  retired proxy features onto the real basis; `recruit_copula_hainich.rcop`, its meta and both
  `hainich_slow_oracle_*.csv` are **byte-identical**, so only the count `.drf` moved. Re-measured Hainich
  thresholds all IMPROVED (Gate-3 Height `nqrmse` 0.3895 → **0.2998**, median ratio 1.25 → 1.13, count ratio
  0.67 → **1.28**) and the alarm was **tightened** 0.45 → 0.40. **If your M2 CI gate was designed against the
  old fixture, re-read it** — the artifact meta now also carries `y_min`/`y_max`/`feat_min`/`feat_max`, and
  `FluxDrivenSlowEmulator` gained a diagnostic-only `feature_history` field (no numerical change; every
  committed baseline byte-identical). Global `_t7` artifacts are untouched — your pin is unaffected.
- **From S — NEW INTEGRATION POINT raised 2026-07-28 (ADR 0034 §1, cause 1 of 3): the F core's
  `water_stress` at Hainich is ~330× the C oracle's.** With the runtime feature rows now recorded, the
  coupled loop feeds the count DRF `water_stress` **0.323–0.331** every year, while the C-derived training
  rows for the same cell/years span **[0, 0.0432]** (Hainich is essentially unstressed in the C). Same
  definition on both sides (`1 − wscal_mean`, `fast.jl`), and F_diff's own soil column is *near saturation*
  for part of the year — so a 1/3 water stress is internally odd, not just a basis difference. `src/fdiff.jl`
  / `src/components/fast.jl` are **yours** (ADR 0029), so S cannot chase this; it wants an F-vs-C oracle
  diagnosis (`fdiff-validate`). It is the single largest of the three remaining runtime↔training conditioning
  shifts (6.6× the trained band width) and it will bias any *coupled* global S run, so it matters before M3.
  The other two causes (`soilmoist` temporal aggregation, `lai`/`fpc` spatial aggregation) are S's, as
  milestone S1d.
  **↳ UPDATE 2026-07-28: S1d is DONE (ADR 0035) and `water_stress` is now the ONLY pinned out-of-band
  column** — the CI assertion in `slow_production_drf_tests.jl` is literally `Set(["water_stress"])`. So
  this integration point is no longer one of three; it is the last one, and it is yours. Nothing about the
  finding changed (runtime 0.323–0.331 vs trained [0, 0.0432], 6.6× band width).
  **↳ ✅ DIAGNOSED + FIXED 2026-07-30 by line M — ADR 0051. It was a QUANTITY mismatch, not aggregation.**
  ADR 0034 §1's "same definition on both sides" was wrong: the C's `pft->wscal`
  (`water_stressed.c:130-140`) is a **POTENTIAL leaf-on** index (no `phen`, `gp_stand_leafon` normalized by
  the plain `Σfpc`, no `(1−wet)`, and `= 1` on a no-demand day), while F_diff computed the **realized**
  supply/demand ratio (`phen` SQUARED in the numerator, degenerating to 0 as leaf display vanishes).
  Landed as **opt-in `WaterParams.wscal_leafon`, default `false`** ⇒ all baselines byte-identical.
  **⚠️ FLIPPING THE DEFAULT IS A TWO-SIDED INTEGRATION POINT — line M will not do it unilaterally.**
  It makes S's pinned set empty (`slow_production_drf_tests.jl:168` asserts exactly
  `Set(["water_stress"])` ⇒ must become `Set(String[])`), and it moves every coupled baseline because
  `wscal_mean` also drives the leaf:root allocation `lmtorm` (`allocation_tree.c:233` — the C uses the same
  accumulator, so this was never *only* a feature-basis bug). **Line M recommends the flip;** S should say
  when it wants to land both sides together. Measured effect (C truth derived per cell/year by
  `scripts/wscal_c_truth_diagnosis.py`, scored against the seed1-vs-seed2 noise floor):
  Hainich `water_stress` 0.3050 → **0.0034** vs a C truth of 0.0014 (**152×** error reduction, inside the
  trained band); `tropical_amazon` **inside the noise floor** (0.4×); `semiarid_sahel` 6.7× better;
  `mediterranean_iberia` 2.1×. **`boreal_siberia` is NOT closed** — see the gotcha list below.
- **From S — S1d landed 2026-07-28 (ADR 0035). Three things concern you.**
  1. **Both committed Hainich demo artifacts moved** (`drf_forest_hainich.drf` + meta AND
     `recruit_copula_hainich.rcop` + meta, regenerated together from one table build); the two
     `hainich_slow_oracle_*.csv` are unchanged. Re-read any M2 gate pinned to the old fixtures. Re-measured:
     Gate-3 Height `nqrmse` 0.2998 → 0.2990, count ratio 1.2808 → **1.1597**, DIRECT copula draws SLA
     0.1274 → **0.0391** / Wooddens 0.0346 → **0.0273** (both bounds tightened, none widened).
  2. **`flux_feature_vector` gained a 6th positional argument, the fast core's `SoilColumn`**
     (`flux_feature_vector(s, grow, pools, state, allom, soil)`). It is exported but had no caller outside
     `slow.jl`, so nothing of yours should break. The FROZEN contract is untouched: feature-column ORDER,
     `live_flux_cond`, the `.drf`/`.rcop` format and the `FluxDrivenSlowEmulator` kwargs are all unchanged.
  3. **NEW, SMALL, YOURS: `fast.jl:302` builds `FToS.soilmoist` on the retired basis.** It still computes
     `sum(state.w)/length(state.w)` (an unweighted mean over all 23 layers), while `interface.jl:37`
     documents that field as "root-zone soil moisture state, fraction of WHC" and S now computes exactly
     that (`LPJmLFITEmulator.root_zone_soilmoist(state, fc.soil)` — the top-1 m, `whcs`-weighted mean, which
     is what the C's `rootmoist` output measures). Nothing consumes the field numerically (only
     `coupling_tests.jl:96`'s `0 ≤ x ≤ 1` bound), so this is cosmetic *today* — but it is a second
     definition of a named quantity living in the codebase, which is the exact hazard ADR 0035 exists to
     remove. One-line fix in your file; S made all three of its own call sites use the shared helper.
  **Global consequence for M3:** the `_t7` global tables are on the retired `soilmoist`/`lai` bases, so a
  COUPLED global run inherits the shift. They need a versioned re-derivation (`t8`) and a deliberate re-pin
  by you before M3 — `_t7` is never mutated in place. The published `_t7` OOS numbers stay valid as
  *offline* measurements (table vs table). SSP370 additionally needs its own
  `cell_year_soilmoist_ye_ssp.parquet` first (the historic one exists).
- **From E:** the `SEBEnergyClosure(...)` constructor + `solve!` signature.
- **From E — OPEN INTEGRATION POINT raised 2026-07-28 (line E milestone E5, ADR 0071):** real daily
  **wind + surface pressure** now exist for the 5 orderA biome cells —
  `test/testitems/references/wind_psurf_<biome>.csv` (`year,doy,wind,psurf`, 2010–2019 × 365 d, obsclim
  GSWP3-W5E5, mapping proven by a `tas` round-trip). The coupled driver still builds `AtmForcing` with a
  CONSTANT wind and a fixed psurf, and `src/run.jl` is **yours** — so wiring these in is an M-side change
  E cannot make. Expect the coupled Hainich/biome baselines to MOVE when it lands (deliberate, not a
  regression): Bowen and the 2018-drought numbers are wind-sensitive. Land it with E (see
  `lines/E/STATE.md` E5).
- **From E — SECOND OPEN INTEGRATION POINT raised 2026-07-28 (line E milestone E3):** the
  **sublimation-λ split** cannot be done inside `energy.jl`. `src/components/fast.jl:236` forms
  `le = et/86400 · LAMBDA_VAPORIZATION` from `et = transp + evap + interc` — one λ for everything, and
  that ET sum has no snow/ice component to split; `FToE` carries no snow mass or snow fraction, so E
  cannot see which part of `le` left snow. Both files are **yours** (F core + the seam). Doing it right
  needs F to partition ET into a snow/ice part and either a new `FToE` field or the λ choice applied next
  to the partition (`conservation.jl::latent_heat(et; sublimation)` already exists for it). Opt-in,
  default byte-identical (guardrail 4). E will not attempt it alone — guessing a snow fraction inside E
  would be invented physics.
- **From E — THIRD OPEN INTEGRATION POINT raised 2026-07-28 (line E milestone E6, ADR 0073):** E recommends
  **`SEBParams.lambda_g = 1.0` (currently 7.0)**. This is E's own file, but flipping a *default* moves every
  coupled and 5-biome baseline (it is the ground-heat term), so it must land with the baselines in one change
  — your call, your re-measure. **The evidence** (497 936 PLUMBER2 tower steps, 4 sites): `H` is the exact
  residual `Rn − LE − G`, so `ΔH = ΔRn − ΔG + ε_obs` identically; the modelled ground heat swings **5–7×**
  harder than observed at the forest sites, and **88 %** of DE-Hai's nocturnal H bias is the `G` error.
  `couple_day!` calls `solve!` **once per day** (`run.jl:93`), and at that step three independent lines give
  `λ_g ≈ 1.0`: the observation-implied fit is 0.83–1.10 at all four sites, `λ_g ≈ 1.0` reproduces the observed
  daily sd(`G_obs`) of 4.3–6.3 W/m² (the 7.0 default gives 14–31), and **daily H R² goes 0.03 → 0.64 (DE-Hai)
  and 0.33 → 0.74 (AU-ASM)** — a broad optimum (0.5 ≈ 1.0), degrading only the already-suspect AU-Rob.
  Expect `T_skin` swings to widen slightly (λ_g is in the Newton denominator), so re-check the
  `|T_skin − Tair| < 25/30 K` gates; `ρ·c_p·g_a` dominates that denominator, so the effect should be small.
  Nothing is needed from you until you choose to land it — **no default was changed** and
  `SEBEnergyClosure(params = SEBParams(lambda_g = 1.0))` already works today if you want to measure first.
  **Also: do NOT act on ADR 0072's `stab_amp` suggestion — ADR 0073 refutes it** (the closure's nocturnal
  `g_a` is within 0.7 % of DE-Hai's measured-`u*` value; that sweep was bias cancellation).
- `src/climbuf.jl` (`ClimBuf`, line S) is consumed via the `climbuf=` kwarg you already own in `run.jl`.

## Status (2026-07-28)

- `run_coupled_cell` runs the full S+F+E daily loop for **one** cell; carbon conserves at the S↔F handoff to
  ~1e-12 gC, energy closes to ~1e-14 W/m², and the opt-in `climbuf=` refreshes S's transient boundary.
- `test/testitems/biome_coupled_tests.jl` drives **5 biome cells** (boreal/temperate/mediterranean/semi-arid/
  tropical) with real GSWP3-W5E5 forcing — energy closes in every climate and the Bowen ordering is
  climate-correct — and since **M1 (ADR 0050)** each cell runs its **own soil column + own canopy + own
  latitude** (`references/M_soilcolumn_<name>.txt`, `M_individuals_<name>_2010.csv`, `M_cells.csv`), no longer a
  common Hainich patch. Still **`slow=nothing`**.
- **M1 evidence:** soil-column extractor gate = byte-identical reproduction of the committed
  `hainich_soilcolumn.txt` (`max|Δwhcs| 3.7e-5 mm`); emergent top-1 m root fraction 99.3 % (Sahel) → 53.2 %
  (Amazon), effective D95 72 → 690 cm; vegetation+soil effect vs the legacy common canopy = **+10.8 W/m² LE**
  (Amazon), **−7.6** (Sahel), mediterranean Bowen **1.27 → 0.65**; energy still closes ≤2.8e-14 W/m² everywhere.
  Suite 106,987 pass / 0 fail / 4 broken.
- **New oracle data this line owns (read-only to others):**
  `/p/tmp/jamirp/esm_land_daily/daily_2000_2019_M_biome_val_c{52059,33335,18371,12045}_seed1` — single-cell
  daily re-runs of the four non-Hainich biome cells with `d_fapar` + `a_lai_stand` + `a_fpc_stand` +
  per-cell `whc_nat`. Water-closure checked (multi-year fractional imbalance ≤3.5 %).
- So: **F+E generalize across biomes with per-cell vegetation; the coupled S does not run multi-cell yet.** The
  global evidence for S is offline (line S), not coupled.
- Resilience battery is scaffold only: 3 `@test_skip false` in `resilience_battery_tests.jl` + 1 in
  `rollout_stability_tests.jl` (the `lag1_autocorr` estimator itself is real and tested).

## Milestones

- **M1** Per-cell input provisioning. **DONE 2026-07-28** (ADR 0050; skill `provision-coupled-cell`).
- **M2** Wire the flux-driven S into the multi-cell driver. **DONE 2026-07-30.** All five cells build their
  own `FluxDrivenSlowEmulator` (own `n_init`/`age0`/boundary from `M_cells.csv`, extracted by
  `scripts/extract_cell_slow_init.py` from the pinned `_t8` `cell_meta.parquet`) plus their own `ClimBuf`.
  *Gate (third item in `biome_coupled_tests.jl`, all five cells):* carbon at the S↔F handoff ≤1e-6·C_scale
  AND <1e-6 · energy <1e-6 W/m² · deterministic under seed · a fixed-N control proving F alone cannot move
  tree N · the `ClimBuf` drives only the two climate axes and its recomputed gdd5 orders the cells the same
  way their baked C-derived gdd5 does. Suite 107,192 pass / 0 fail / 4 broken (job 1643130).
- **M3** **Coupled multi-cell validation vs the C truth** — per-cell demography + trait distributions against
  the annual `ind` parquet, scored against the seed1-vs-seed2 noise floor (reuse
  `scripts/noise_floor_vs_emulator.py`, line S's script — read-only). **This is the P3 gate.** Report per-cell
  error vs floor, and held-out **cells and scenarios**.
- **M4** **Resilience battery** — fill the 4 stubs: (a) lag-1 autocorrelation vs climate (the documented
  ~0.2-wet → ~0.75-dry gradient), (b) recovery/restoring rate from a pool-perturbation experiment,
  (c) the **shuffle test** (S0 vs S1 — proves the memory is genuinely internal, not inherited from
  autocorrelated climate; an AR emulator can cheat this, so it is mandatory), (d) the long-horizon AC-gap /
  oscillation check in `rollout_stability_tests.jl`. **Reimplement from Bathiany et al. 2024
  (doi:10.1111/gcb.17613) — LPJ_resilience has NO license, so its code must not be copied.** Also resolve the
  live inconsistency: MEMORY/STEERING place this in P3, the test comments say "Phase 6".
- **M5** Biome-calibrated PFT params + spin-up (today every biome runs beech ANGIO params from
  `par/pft_lpjmlfit.js`).
- **M6** Provide the coupled multi-cell harness line O needs for O5 (online multi-cell).

## Line-local gotchas

- **Hainich is `42490` in the global orderA grid** — `28008` is Sonoran desert there (it is Hainich only in the
  repo's `-DSINGLESITE` grid). Every per-cell extractor must use the orderA index.
- `.clm` readers must **parse the header** (v3 float32 HDR=51 vs v2 int16 HDR=43 with `scalar 0.1` ⇒ °C×10) —
  never assume float32/HDR=51. Reuse `scripts/build_transient_boundary.py::open_clm`.
- Committed fixtures under `test/testitems/references/` are **shared** — new ones take an `M`-ish/cell-specific
  name; **regenerating an existing baseline is an integration point** (guardrail 4: opt-in, default
  byte-identical).
- The 5-biome test uses a bounded negative-LE tolerance (`@test all(≥(-2.0), out.le)`) for the smooth-min
  undershoot in the fully-depleted Sahel corner — keep that reasoning if you touch the assertions.
- **Per-cell inputs come from the cell's OWN single-cell C run, not the global one** (ADR 0050): `whc_nat`
  differs between the 512-task global run and a single-cell re-run by up to 1.6e-4 relative in layer 0 under
  `-DPERMUTE`, which is 40× the fixture print resolution. `WHC_SRC=percell` is the default for that reason.
- **A `rootdist` that does not sum to 1 is silently physical**, not an error: F_diff's water supply scales
  linearly with `sum(rootdist)` (`src/fdiff.jl:846,928`) and `stand_structure_tof`'s D95 loop
  (`src/run.jl:65`) never terminates below 0.95. `hainich_soilcolumn` validates none of this — the extractor
  and `biome_coupled_tests.jl` do.
- **Never hard-code the repo root in a script** — it writes into the integrator worktree from here
  (CLAUDE.md §9 item 6). Derive it from `__file__` / `@__FILE__`.
- **`[ASSUMPTION]` F_diff has NO soil-ice / permafrost representation, and that is the leading (UNVERIFIED)
  explanation for the one cell ADR 0051 does not close.** The C says `boreal_siberia` (52059) *is* water
  stressed (`water_stress` 0.3146); the realized ratio over-stressed it (0.664) and the C-faithful
  expression **under**-stresses it to exactly 0.000 — the `min(…,1)` cap binds on **100 %** of days, so
  F_diff's `emax·wr` exceeds the leaf-on demand every day. The C's `wr` is over **plant-available** water
  and the C's soil carries ice (`ice_depth`/`ice_fw`, `getrootdist(…, config->permafrost)`), so a frozen
  profile has little available water; F_diff's `wr` never collapses. **Verified:** the absence of any ice
  state in `src/fdiff.jl`/`src/state.jl`. **Not verified:** that this is the cause. Falsifiable test —
  compare F_diff's root-zone `w` against the C's `rootmoist` for cell 52059 over winter/spring (that
  single-cell run exists: `daily_2000_2019_M_biome_val_c52059_seed1`); if F_diff's stays high while the C's
  collapses, confirmed. Note `swc` is NOT invertible to `w` (ADR 0035) — use `rootmoist`.
- **A "conditioning shift" and "extrapolation out of the trained band" are different failure modes, and the
  global band cannot tell them apart.** Against the **global pooled `_t8`** band (`water_stress ∈
  [0, 0.9618]`) the shifted runtime values were *inside* range; only the **Hainich demo artifact's** band
  ([0, 0.04315]) exposed them. A global coupled run was therefore evaluating the DRF at a perfectly valid
  point in feature space belonging to a **much drier cell** — which cost the Sahel 36 % of its trees. When
  checking a per-cell conditioning feature, score it against **that cell's own C truth**, never against the
  global band (`residual-diagnosis` §3e).

## M1 review debt — carry into M2 (from the 2026-07-28 adversarial review)

A 4-lens adversarial review of the M1 commits raised 16 candidate findings; the judge/verification phase
died on a session limit, so treat these as **unverified candidates, not confirmed defects**. The ones that
survived my own inspection were fixed in `b106cdae`'s follow-up (gate now also unit-checks the
`getrootdist` port that `beta_mean` uses; `WHC_SRC != percell` aborts unless `ALLOW_UNGATED_WHC=1`; the
`nstep`/window is asserted; `find_whc_run`'s glob is pinned to the historical window; subset `CELLS=` runs
MERGE the registry instead of truncating it; the test pins per-cell provenance and the FAPAR band).
**Still open:**

1. ~~**Test item 2 has no provenance sensitivity.**~~ **CLOSED 2026-07-30.** It passed VERBATIM when all
   five cells reverted to Hainich's soil + canopy, because its assertions were closure + finiteness +
   qualitative orderings. Item 2 now pins each cell's OWN mean LE and GPP (±2 % / ±3 %, against a
   24.9…119.3 W/m² between-cell spread) and asserts the five signatures are mutually distinguishable at
   those tolerances — so a driver-level fallback (an edit hoisting `soil`/`pools` out of the per-cell loop,
   or a per-cell artifact silently resolving to Hainich's) is now detected where the orderings could not
   see it.
2. **`GATE=no` leaves no trace in the emitted artifacts.** It now warns on stderr, but the files and
   `M_soilcolumn_meta.json` are still structurally indistinguishable from gated output. Consider stamping the
   gate verdict into the header + meta.
3. **`CLAUDE.md` §9 contradicts itself on `MEMORY.md`**: the "where things are written" table says
   cross-cutting `[VERIFIED]` facts go to `MEMORY.md` (shared, additive) while the ownership table lists
   `MEMORY.md` as **integrator only**. This line appended to it (commit `e9da4d0c`) on the former reading.
   Integrator's call to reconcile — flagging, not fixing, since `CLAUDE.md` §9 is shared.

## Observed, NOT ours to fix (raise with the owner/integrator)

- `scripts/gen_diagrams.jl --check` reports `docs/src/generated/components.mmd` **STALE** — pre-existing,
  unrelated to any line-M change: the committed diagram still says component E will "reuse Terrarium.jl",
  while `src/registry.jl` now says "self-contained SEB (ADR 0017)". One line. It is **not** a CI gate (`docs`
  CI runs doctests + `makedocs`, never the diagram alarm), so nothing is red. The text belongs to component E,
  so regenerating it is line E's or the integrator's call — line M left it untouched deliberately.
