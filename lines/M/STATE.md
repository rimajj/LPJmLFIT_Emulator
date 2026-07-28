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

## 📌 The PINNED Component-S artifact (M2 step 1 — frozen S→M contract, ADR 0023)

**Pinned pair** (`/p/tmp/jamirp/emulator_global/`, line S's, read-only to this line):

| Artifact | sha256 | bytes | mtime |
|---|---|---|---|
| `drf_forest_global_pooled_w20.drf` | `652a13278ff04511b78ab36ce3da178b7b879faa464e0b529a44fc79c2708c8c` | 51771375 | 2026-07-27 14:45 |
| `recruit_copula_global_pooled_w20.rcop` | `50322b4154c52a951720ad1681f35afd1ffacc794f279465b9fd029ceb122f2f` | 129322844 | 2026-07-27 16:56 |

**Contract VERIFIED against the runtime order (2026-07-28), not assumed:**
- DRF `_meta.txt`: `nfeat 15`, `nhead 11`, `target n_living`, `ntrees 150`, pooled over 53,993 cells;
  `colnames` = `bm_inc_cell growth_eff water_stress soilmoist hmean hmax agb lai fpc age_mean n_prev` +
  boundary tail `eco_diag_gdd_5 tas_cold_month soil_depth co2` — **identical** to
  `slow.jl::flux_feature_vector` (11 head + 4 boundary).
- Copula `_meta.txt`: `naxes 4` (`SLA Wooddens D95max minwscal`), `ncond 8`, `cond_cols` =
  the 4 flux drivers + the same boundary tail — **identical** to `slow.jl::live_flux_cond`
  (`vcat(feats[1:4], s.boundary)`).
- So the per-cell boundary vector this line must build is exactly
  `[eco_diag_gdd_5, tas_cold_month, soil_depth, co2]` — precisely the columns `cell_meta.parquet` carries.

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

**REJECTED at the time of writing — `*_t7` (superseded by the update above):** `drf_forest_global_pooled_w20_t7.drf` and
`drf_forest_global_historic_t7.drf` appeared **today** (58,587 cells) and line S was still mid-production when
this was written (job 1622131 `gcopula_historic_t7` RUNNING) — **there is no matching `_t7` `.rcop`**. Adopting
a half-published retrain is exactly the "never adopt a re-trained artifact silently" trap (ADR 0023). Moving to
`_t7` is an **integration point with line S** once S publishes a complete, versioned pair.

**Consequence for the M2 gate:** these artifacts live on `/p/tmp` (DVC, not git), so a CI test cannot load
them — CI runs on GitHub runners with no cluster. Split it: the **committed** demo artifact
(`test/testitems/references/drf_forest_hainich.drf`) drives the CI conservation/determinism/byte-identity gate
(closure is artifact-independent), and the pinned global pair drives the cluster-only per-cell science (M3).

### ⛔ …but the pinned `pooled_w20` CANNOT SERVE ALL FIVE CELLS — the pin must move to `_t7`

Found 2026-07-28 by `scripts/extract_cell_slow_init.py`'s completeness gate, *not* by inspection. Cell
coverage of every `cell_meta.parquet` on `/p/tmp/jamirp/emulator_global/`:

| table | ncells | biome cells present |
|---|---|---|
| `slow_count_historic_w20/` (pinned pool) | 44,328 | **3/5** — no `semiarid_sahel`, no `tropical_amazon` |
| `slow_count_ssp370_w20/` (pinned pool) | 53,566 | **4/5** — no `semiarid_sahel` |
| `slow_runtime_historic/` | 44,328 | 3/5 |
| `slow_runtime_ssp370/` | 53,566 | 4/5 |
| **`slow_count_historic_w20_t7/`** | 53,699 | **5/5** |
| **`slow_runtime_historic_t7/`** | 53,699 | **5/5** |
| **`slow_count_ssp370_w20_t7/`** | 58,495 | **5/5** |

**`semiarid_sahel` (18371) is in NEITHER table the pinned `pooled_w20` artifact was trained on** — that DRF
has never seen the cell, so there is no honest `n_init`/`age0` for it at this version. Only the `_t7` family
covers all five. **So M2's real step 1 is an integration point with line S: adopt the `_t7` pair once S
publishes a COMPLETE one.** As of this writing `drf_forest_global_pooled_w20_t7.drf` and
`drf_forest_global_historic_t7.drf` exist (2026-07-28 15:00/15:09) but **no `_t7` `.rcop`** does — S's job
1622131 `gcopula_historic_t7` was still RUNNING. Do not adopt a half-published retrain (ADR 0023).
`STATE.md`'s pin table above stays authoritative until that swap is made deliberately.

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

**M1 is DONE (2026-07-28, ADR 0050).** Every biome cell now runs its OWN soil column, canopy, forcing and
latitude; both extractors are committed and gated (the soil-column extractor reproduces the committed
`hainich_soilcolumn.txt` **byte-identically**). To add a cell, use the **`provision-coupled-cell`** skill —
do not re-derive the procedure.

**M2 — wire the flux-driven Component S into the multi-cell driver.** The next blocker: the driver still runs
`slow=nothing`, so the coupled evidence for S is offline-only (line S), not coupled.

**Step 1 (pin an artifact) is DONE-but-CONDITIONAL, and step 2's tool is written and proven. Start at step 0.**

0. **RESOLVE THE PIN — the one thing blocking the rest (integration point with line S).** Check whether S has
   published a **complete** `_t7` pair: `ls /p/tmp/jamirp/emulator_global/*t7*` and look for a
   `recruit_copula_global_*_t7.rcop` beside the two `_t7` `.drf`s. Why it matters: the currently pinned
   `pooled_w20` pair **was never trained on `semiarid_sahel`** (see the ⛔ subsection above), so it cannot
   serve all five cells; every `_t7` table covers 5/5.
   - **If a complete `_t7` pair exists:** verify its `*_meta.txt` `colnames`/`cond_cols` tails against
     `flux_feature_vector`/`live_flux_cond` (the extractor's `META_TXT=` does this for you), record the new
     paths + sha256s in the pin table above, and note the swap in BOTH `lines/M/STATE.md` and `lines/S/STATE.md`
     — ADR 0023 makes adopting a re-trained artifact a deliberate, two-sided act, never silent.
   - **If not:** either wait, or proceed on `pooled_w20` for the **four** cells it covers and run the M2 gate
     with `slow` enabled on those four and `slow=nothing` at Sahel — but say "4 of 5 cells" everywhere, and do
     NOT paper over Sahel by borrowing another version's `n_init`/`age0` (they are version-coupled; the numbers
     are in *Two verified facts* above).
1. ~~**Pin a versioned S artifact**~~ — done, contracts verified (see the pin table). Conditional on step 0.
2. **Per-cell S initial state — the tool EXISTS and is proven: `scripts/extract_cell_slow_init.py`.** It reads
   a `cell_meta.parquet`, re-checks the artifact's trained boundary order against the runtime order, and merges
   `n_init, age0, eco_diag_gdd_5, tas_cold_month, soil_depth, co2` into `references/M_cells.csv`. Run it once
   the pin is resolved:
   ```bash
   SC=/p/tmp/jamirp/emulator_global
   META=$SC/slow_runtime_historic_t7/cell_meta.parquet META_TXT=$SC/drf_forest_global_historic_t7_meta.txt \
     /home/jamirp/.conda/envs/py311_new/bin/python scripts/extract_cell_slow_init.py
   ```
   **The fixture is deliberately NOT committed yet** — emitting it from `_t7` while the pin says `pooled_w20`
   would silently adopt the unpinned retrain. Verified working: `_t7` → 5/5 cells; the pinned `pooled_w20`
   tables → correct ABORT. (STATE.md's old claim that `slow_runtime_historic` holds "all five biome cells" was
   **wrong** — it holds 3/5. That error is what the gate caught.)
3. **Per-cell `ClimBuf`** through the `climbuf=` kwarg `src/run.jl` already owns — **now REQUIRED, not
   optional**, if the pin is a POOLED artifact: the boundary's two climate columns differ by up to 1513 GDD /
   8.84 °C between historic and ssp370, so one baked row is a single-climate snapshot (see *Two verified facts*).
4. *Gate:* carbon ≤1e-6·C_scale **and** energy ≤1e-6 W/m² in **every** cell, deterministic under seed, and
   **`slow=nothing` still byte-identical** (guardrail 4). Add it as a third test item in
   `test/testitems/biome_coupled_tests.jl` beside the two that are there now. Template to copy:
   `test/testitems/slow_production_drf_tests.jl` already does exactly this for one cell (loads the committed
   `drf_forest_hainich.drf` + its meta's `boundary`/`n_init`/`age0`, asserts fixed-N reference vs S-driven
   mechanism, conservation, energy, determinism). **The CI gate must use the COMMITTED demo forest**, not the
   pinned `/p/tmp` artifact — CI has no cluster. A useful structural property: a DRF prediction is a mean over
   leaf values, so it cannot leave the training target range — the `0.5 ≤ target ≤ 40` band assertion therefore
   still holds per-cell even where the Hainich-trained forest is extrapolating.
5. **Carry the M1 review debt (below): test item 2 still passes verbatim if all five cells revert to Hainich's
   inputs.** Pin a per-cell OUTPUT signature (each cell's mean LE/GPP in a band) while you are editing that
   file — numbers are in `lines/M/JOURNAL.md` (job 1617060).

**Cheap win available while doing M2:** the four new single-cell C runs
`/p/tmp/jamirp/esm_land_daily/daily_2000_2019_M_biome_val_c{52059,33335,18371,12045}_seed1` also carry
`a_lai_stand` / `a_fpc_stand` / `d_gpp` / `d_transp` / `d_swc` / `d_fapar` — i.e. a **per-cell F_diff-vs-C
oracle for four new biomes**, the raw material for M3's per-cell validation with no new HPC run.

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
- **From S — SECOND INTEGRATION POINT, not yet actioned (line S milestone S1c, ADR 0032):** the committed
  `test/testitems/references/drf_forest_hainich.drf` is trained on the RETIRED PROXY features
  (`soilmoist` 0.7, `lai` 21.2) while `recruit_copula_hainich.rcop` beside it is on the REAL ones (0.85, 3.07)
  — one emulator, two conditioning bases, a live ADR-0023 shift masked by the DRF's OOD leaf-clamping. S will
  regenerate BOTH together; that **moves the drift thresholds** in `slow_production_drf_tests.jl` and
  `slow_oracle_tests.jl`, so land it jointly and re-measure rather than widening the alarms.
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
- **M2** **Wire the flux-driven S into the multi-cell driver**: the global pooled `.drf`/`.rcop` (pinned
  version), a per-cell `ClimBuf`, and per-cell `n_init`/`age0`/boundary from `cell_meta.parquet`.
  *Gate:* carbon ≤1e-6·C_scale **and** energy ≤1e-6 W/m² in **every** cell, deterministic under seed,
  `slow=nothing` still byte-identical. *(NEXT, above)*
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

## M1 review debt — carry into M2 (from the 2026-07-28 adversarial review)

A 4-lens adversarial review of the M1 commits raised 16 candidate findings; the judge/verification phase
died on a session limit, so treat these as **unverified candidates, not confirmed defects**. The ones that
survived my own inspection were fixed in `b106cdae`'s follow-up (gate now also unit-checks the
`getrootdist` port that `beta_mean` uses; `WHC_SRC != percell` aborts unless `ALLOW_UNGATED_WHC=1`; the
`nstep`/window is asserted; `find_whc_run`'s glob is pinned to the historical window; subset `CELLS=` runs
MERGE the registry instead of truncating it; the test pins per-cell provenance and the FAPAR band).
**Still open:**

1. **Test item 2 has no provenance sensitivity.** It is the only test that feeds the per-cell inputs to the
   model, and it passes VERBATIM when all five cells revert to Hainich's soil + canopy (measured) — its 12
   assertions are closure + finiteness + qualitative orderings. Item 1's new pins catch a *fixture* swap but
   not a *driver-level* fallback (e.g. an M2 edit hoisting `soil`/`pools` out of the per-cell loop, or a
   per-cell S artifact silently resolving to Hainich's). **Fix while doing M2:** pin a per-cell OUTPUT
   signature — each cell's mean LE / GPP within a band — so the model actually has to have consumed that
   cell's inputs. Numbers to use are in `lines/M/JOURNAL.md` (job 1617060).
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
