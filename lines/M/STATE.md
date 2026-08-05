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

**M1, M2, M3 ALL DONE. M3's F side closed 2026-07-30 (ADR 0053); its S SIDE CLOSED 2026-08-05 (ADR 0054).
The P3 gate has a number and a mechanism on both sides. The next milestone is M4 (item 2 below) — but read
item 1 first, because M3 produced one finding that outranks it.**

✅ **ADR 0054 IS MERGED AND VERIFIED ON BOTH SIDES — nothing about it is outstanding.** Branch CI on the work
sha `12bf126b` was green on every required gate (`format`, `test (1)`, `test (lts)`, + non-required
`test (macOS, lts)`; `python` also ran green), and **`main`'s OWN post-merge run on `2755d091` is green on
all of them too**. The follow-up docs/skill commits merged as `3be1db87` (only `format` triggers on that
diff — one `.jl` file, nothing under `src/`/`test/` — and it is green). Local suite before pushing:
**110,045 pass / 0 fail / 4 broken**, 106 items (job 1701261).
**`test (pre)` is red and was diagnosed, not waved away:** it dies at LOAD time with
`MethodError: no method matching setindex!(::Base.ScopedValues.ScopedValue{Bool}, ::Bool)` — a
Julia-prerelease API removal breaking a dependency before any testitem runs. Byte-identical to the failure
line S diagnosed on `1b44cebb`, it is the documented allowed-to-fail churn (CLAUDE.md §5), and `test (1)`
passing on 1.12 is the evidence it is not ours.

**The `wscal_leafon` question is SETTLED as option (b), and stays settled until line S moves.**
`lines/S/STATE.md` still reads "Not S's to chase: `water_stress` is line M's F core, leave it pinned", and S
is mid-flight on Phase 3A/S2. So: **default stays `false`; pass `wscal_leafon = true` EXPLICITLY in every
coupled run and label every number with it.** Flipping the default makes S's
`slow_production_drf_tests.jl:168` assertion (`Set(["water_stress"])`) fail and moves every coupled
baseline. M's recommendation to flip still stands; it is S's to schedule.

**Artifact pin: still `_t8`.** Re-checked 2026-08-05 — a `recruit_copula_global_historic_t9.rcop` (508 MB,
2026-07-31) exists on `/p/tmp` but there is **no `_t9` `.drf`**, so it is a half-published pair and adopting
it is exactly ADR 0023's trap. Line S's own `lines/S/STATE.md` also says t9's env-conditioned copula is
**deliberately NOT promoted to production** (its six env columns have within-cell sd exactly 0, so they
cannot encode a warming response). Do not re-pin without both halves AND S saying it is production.

### 1. THE FINDING TO ACT ON — the count recursion is unanchored (integration point → line S)

ADR 0054's attribution arm: in the **training table** `n_prev` is the C's OWN previous `n_living`
(`build_slow_runtime_table.py:572`), never a prediction, so a free-running coupled rollout is off that basis
by construction and **compounds a one-step count bias at 2.6–4.9 %/yr into a ×1.26–1.53 recursion
contribution over nine steps** (the rest of the +36–81 % total 2019 excess is the year-1 level offset —
do not quote the total as "the recursion").
Teacher-forcing `s.n_prev` back onto the C truth each year removes **59–72 % of the total coupled count error in all five
cells** and flattens the drift (boreal 1.12→1.74 becomes a flat 1.12–1.17); the per-year model on F's own
canopy features is then within **0.2–3.9 noise floors**.

Any fix touches `src/components/slow.jl` = **line S's exclusive path** (ADR 0029), so raise it with S rather
than editing. `scripts/biome_slow_oracle_probe.jl`'s `run_cell(k; teacher = true)` arm is the ready-made
before/after test — it is a driver-level write to a public mutable field, so it needs nothing from S to run.
This compounds without bound, so it matters **more than any remaining F-side item** for a multi-decadal or
online run.

**✅ RAISED with line S on 2026-08-05** — as item **H** in `lines/S/STATE.md`'s `DO THIS NEXT` list, with the
numbers, the ready-made arm, and one concrete hook: ADR 0100's wrong-signed warming response was measured on
**free-running** 81-year rollouts, so re-running that 2×2 with the teacher-forced arm separates recursion
from the recruit channel at zero training cost. Nothing further is owed from this line until S replies —
**do not implement it here.** If S declines or defers, the honest framing for any coupled multi-decadal
result M publishes is that the count level carries an unbounded recursion term; quote the teacher-forced
number alongside the free one.

### 2. M4 — the resilience battery (the next MILESTONE proper)

4 stubs still `@test_skip`: (a) lag-1 autocorrelation vs climate (the documented ~0.2-wet → ~0.75-dry
gradient), (b) recovery/restoring rate from a pool perturbation, (c) the **shuffle test** (S0 vs S1 — proves
the memory is internal, not inherited from autocorrelated climate; an AR emulator can cheat this, so it is
mandatory), (d) the long-horizon AC-gap / oscillation check in `rollout_stability_tests.jl`.
**Reimplement from Bathiany et al. 2024 (doi:10.1111/gcb.17613) — LPJ_resilience has NO licence, so its code
must not be copied.** Also resolve the live inconsistency: MEMORY/STEERING place this in P3, the test
comments say "Phase 6". ⚠ Item 1 above is directly relevant: an unanchored AR recursion will *itself* produce
autocorrelation and slow recovery, so measure the resilience battery with the teacher-forced arm alongside
the free arm or (c) will not be able to tell internal memory from recursion memory.

### 3. F-side follow-ons, in value order (all reference bases now established)

ADR 0053's verdict, so you do not re-measure it: **seasonal phase is excellent in all 5 biomes** (monthly
r 0.870–0.999 GPP, 0.858–0.999 ET). The level verdict DECOMPOSES per cell, and three of the five 10-yr
means are actively misleading — read the year-matched ratio series' SHAPE:

| cell | year-matched GPP ratio 2010→2019 | diagnosis |
|---|---|---|
| `tropical_amazon` | flat ≈ 0.97 | **F is right**, within 3 % |
| `temperate_hainich` | flat, +12 % → +25 % | a genuine FLUX-LEVEL bias — the one clean one |
| `boreal_siberia` | 0.80 → **1.70** monotone | DRIFT: unbounded canopy growth (FPC +64.5 %) |
| `semiarid_sahel` | 1.10 → **0.59** monotone | DRIFT: canopy dieback (FPC −13.5 %) |
| `mediterranean_iberia` | noisy 1.09–1.72 | excessive interannual volatility |

a. **ET is 11–35 % HIGH while F carries NO grass transpiration** ⇒ the tree-only bias is larger still. This
   is the best-scoped candidate for ADR 0052's too-dry root zone and it is the **demand** side, which ADR
   0052 never considered (it guessed `_infiltrate` / the absent `w_fw`). Cheapest high-value F diagnosis
   left; `residual-diagnosis` first.
b. **Attribute Hainich's flat +12 %** with the kernel-isolation drive (`fdiff-validate`): drive F with the
   C run's own daily FAPAR so a GPP gap cannot come from the canopy. `d_fapar` is already in all 5 runs.
c. **The Sahel decline IS ADR 0052's dry-cell bias seen end-to-end** (canopy starts correct, dies back) —
   one mechanism, two points in the chain. Fixing (a) may fix this; measure before assuming.
d. **F under-predicts tree FPC in all 5 cells (0.31–0.72×)** *despite* starting from a patch 1.12–1.72×
   denser than the ensemble — the most robust structural finding in the set, and unattributed.

### 4. Deliberately NOT done — move the production driver to the patch ensemble

`readcanopy` in `run_coupled_biomes.jl` / `wscal_leafon_probe.jl` picks the **modal** patch, which is
1.12–1.72× denser in FPC than the 25-patch ensemble mean the C's outputs report. `biome_fdiff_oracle_probe.jl`
already has the correct `readcanopy_patches` + `run_cell` ensemble driver to lift across. **This will move
`biome_coupled_tests.jl` item 2's pinned per-cell LE and GPP (±2 %/±3 %)** ⇒ a deliberate baseline
regeneration under guardrail 4, in its own change with its own commit. Do it before any global coupled run.

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
- **From S — NEW OPEN INTEGRATION POINT raised 2026-08-04 (line S Phase 3A, ADR 0047): your drivers must
  pass `fc.pft_ids`.** `FDiffFastCore` defaults it to `pft_ids = is_grass ? 8 : 3`, i.e. **every tree in
  every cell runs as beech (`Type 3`)**. That is already wrong for the coupled biome set — Amazon and Sahel
  are `Type 0` — and it becomes load-bearing when S wires in the ported per-individual mortality hazard
  (`src/trait_mortality.jl`, landed offline with no call site), because that operator's parameters are
  **genuinely per-PFT**: ids 1/2 are XERIC (`mort_water_res` 0.25, not 0.75), id 5's `longevity` is 125
  (not 400) and its `mort_water_factor` 20 (not 5), and ids 0/1/2/4/5/6 all carry non-temperate `wdmort`
  pairs. Running the tropics on beech wood-density mortality would reproduce the ADR-0031 defect class
  inside the fix, so `pft_mort_params(id)` **errors** on an unknown id rather than defaulting — a coupled
  call site that does not pass real ids will therefore FAIL LOUDLY, not run wrong.
  **Nothing is asked of you yet:** the operator has no call site, so nothing in `run.jl`/`interface.jl`
  changes today and no struct changes are needed (`fc.pft_ids` already exists at `fast.jl:94` and
  `slow.jl` maintains it). What is asked is that when the per-cell drivers are next touched, the real
  `Type` per cohort is threaded through from `M_individuals_*` instead of taking the default. Until then
  line S passes ids itself in its own harnesses. No ADR-0023 contract break: the
  `FluxDrivenSlowEmulator` kwargs, `flux_feature_vector` order, `live_flux_cond` and the `.drf`/`.rcop`
  format are all unchanged.
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
- **From S — ✅ ACKNOWLEDGED 2026-08-05, a STANDING REQUIREMENT on any future M driver (S's item D,
  ADR 0049).** `fc.pft_ids` is a **correctness** requirement for `trait_mortality = true`: the ported hazard
  errors on a non-tree id, but a *wrong-but-valid* id passes **silently**, and `FDiffFastCore` defaults every
  tree to **beech** (`fast.jl:147`) — so a driver that leaves the default would run the tropical and boreal
  PFTs on temperate wood-density mortality, which is the ADR-0031 defect class exactly. **No M driver enables
  `trait_mortality` today** (it is opt-in, default `false`, and neither `run_coupled_biomes.jl` nor
  `biome_slow_oracle_probe.jl` sets it), so nothing is currently wrong — but the first M driver that turns it
  on **must pass real per-cohort `pft_ids`**. The per-cell PFT ids are already in
  `references/M_individuals_<name>_2010.csv` (the `type` column, 0-based `pftpar` index, `Type <= 6`), so
  there is no new extraction to do. Recorded here rather than only in S's file so it cannot be missed.
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
- **From E — SUPERSEDED 2026-08-05 by the FOURTH integration point below (ADR 0074).** E7 measured a
  two-layer prognostic ground-heat column that **beats** `lambda_g = 1.0` on every scoreable metric, so
  `enable_two_layer = true` is now E's recommendation and `lambda_g = 1.0` is only the smaller fallback. The
  original text is kept because the fallback is still valid and its evidence still stands:
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
- **From E — FOURTH OPEN INTEGRATION POINT raised 2026-08-05 (line E milestone E7, ADR 0074). This is the
  one to act on; it REPLACES the `lambda_g = 1.0` request above.** E now recommends
  **`SEBParams.enable_two_layer = true`** (default `false`, so nothing has moved and every baseline is
  byte-identical today). It swaps the single conductance against a 30-day EWMA of *air* temperature for a
  prognostic two-layer soil column (`G = κ_g(T_skin − T1)`, `κ_g = 2λ_soil/z1`, MITgcm land-package update);
  `lambda_g` becomes inert when it is on. **Why this instead of `λ_g = 1.0`:** measured on the same 497k
  tower steps (harness reproduces ADR 0073 digit for digit), at the two sites whose towers can score H —
  daily H R² **0.645** vs 0.637 (DE-Hai) and **0.775** vs 0.745 (AU-ASM), and on `G` itself **0.717** vs
  0.657 and **0.614** vs 0.477. So it wins on H, wins clearly on G, and unlike a fitted coefficient it
  carries a real diurnal soil wave (sub-daily DE-Hai sd(G) 5.75 vs observed 5.66, night G R² **+0.394**),
  which is what line O needs. `Rn` is preserved within ±0.005. No secular drift over a 16-year record
  (−0.059 K/yr), so it is safe for your decadal coupled runs.
  **What lands on your side:** it moves every coupled and 5-biome baseline (it is the ground-heat term), so
  it is your call and must land with the baselines in one change, and ADR 0072's night-cold **sign**
  assertion in `energy_closure_tests.jl` is re-pinned at that moment. Measure first with
  `SEBEnergyClosure(params = SEBParams(enable_two_layer = true))` — it works today.
  **Costs to quote when you land it:** sub-daily `T_skin` degrades at AU-Tum/AU-Rob; one global
  `z_soil1` (default 0.75 m) suits closed canopies but under-resolves sparse/desert surfaces. **A related
  request:** `theta_soil` is a constant 0.5 because `FToE` (yours) carries no soil moisture — wiring F's
  root-zone wetness into the soil heat capacity is the natural follow-up, same shape as the E3 ask.
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
  **Plus, 2026-07-30 (ADR 0053):** `daily_2000_2019_M_grass_val_c{52059,33335,18371,12045}_seed1` — the same
  four cells re-run with the custom per-PFT daily **grass** GPP/NPP (`conf.h` ids 419/420), which is what
  makes `gpp_tree = d_gpp − d_grass_gpp` possible. Hainich's equivalent is the pre-existing
  `daily_2000_2019_grassgpp_c42490_seed1`. ~9 s per cell to regenerate
  (`CELL=<c> RUNTAG=M_grass_val SUBMIT=yes bash scripts/run_fdiff_grass_gpp_cell.sh`).
- **Committed F-vs-C oracle tables (ADR 0053):** `test/testitems/references/M_fdiff_oracle_biomes.csv`
  (monthly climatology) + `M_fdiff_oracle_biomes_annual.csv` (per-year, for year-matched scoring) +
  `M_fdiff_oracle_meta.json`. Built by `scripts/extract_biome_fdiff_oracle.py`; the F side is
  `scripts/biome_fdiff_oracle_probe.jl` (25-patch ensemble, `wscal_leafon=true`).
- **Committed S-vs-C oracle tables (ADR 0054, 2026-08-05):** `M_slow_oracle_counts.csv` (per-patch living-tree
  ensemble per cell-year, both seeds) + `M_slow_oracle_traits.csv` (6 axes × per-year community marginals,
  both seeds) + `M_slow_oracle_meta.json` (incl. the precomputed noise floors). Built by
  `scripts/extract_biome_slow_oracle.py` from the `ind_hist_seed{1,2}_all.parquet` tables; the coupled side is
  `scripts/biome_slow_oracle_probe.jl` (pinned `_t8` `.drf`+`.rcop`, `wscal_leafon=true`, a free arm and an
  `n_prev`-teacher-forced arm). A CI `@testitem` in `biome_coupled_tests.jl` guards the fixture's BASIS only —
  the skill measurement needs the 180 MB `/p/tmp` pin, which CI has no cluster for.
- So: **F+E generalize across biomes with per-cell vegetation, and since M2/M3 the coupled S runs all five
  cells and is scored against the C truth.** The global (all-cell) evidence for S is still offline (line S).
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
- **M3** **Coupled multi-cell validation vs the C truth. This is the P3 gate.**
  - **F-side: DONE 2026-07-30 (ADR 0053).** Per-cell tree GPP / ET / FPC / stand LAI vs the C oracle for all
    five biomes, on bases fixed by construction rather than caveated (grass removed exactly via the id-419
    output; the C's own 25-patch ensemble; year-matched levels). Verdict: seasonal phase excellent everywhere
    (monthly r 0.870–0.999), level decomposes per cell into one genuine flux bias (Hainich +12 %), two pure
    drifts (boreal, Sahel), one volatility case (mediterranean) and one clean pass (Amazon 0.97).
  - **S-side: DONE 2026-08-05 (ADR 0054). M3 is CLOSED.** Per-cell demography + trait distributions against
    the annual `ind` parquet (both seeds, historic 2010–2019), on the same four bases: tree-only via the
    imported `TREE_TYPES`; the C's **25-patch ensemble mean** (S's count target is per-(Cell,Patch,Year) and
    the driver runs ONE patch — a per-cell total is ~25× off); year-matched; the writer's >5 m population.
    Population cross-checked EXACTLY against a second extractor (2010 per-cell totals == `M_cells.csv`'s
    `n_trees`, 122/282/214/272/276) and that equality is now a CI assertion.
    *Counts (mean |E−C| in seed1-vs-seed2 floors, free-running):* Amazon **0.5**, Sahel **1.4** — at the
    floor; Hainich **4.5**, boreal **11.1**, mediterranean **13.9** — and those three drift MONOTONELY
    (1.05→1.36, 1.12→1.74, 0.98→1.81), so their 10-yr means (1.2–1.4) hide the mechanism.
    *Attribution:* teacher-forcing `n_prev` onto its trained basis removes **59–72 %** of the error in every
    cell and flattens the drift ⇒ **0.2–3.9 floors**. The deployed error is an unanchored AR recursion
    compounding a ~5 %/yr one-step bias, NOT the count model's conditional skill (NEXT item 1).
    *Traits:* 9 of 10 cell-axis medians within **2.0 floors** (only SLA/Wooddens reach `TreePools`); two
    named exceptions — Sahel SLA 7.9 floors = a 4.6 % error on a 0.0002 floor (denominator artefact), and
    boreal SLA a correct median with a wrong distribution WIDTH (nqrmse 1.31 vs ≤0.43 elsewhere).
    *Carbon* closes 4.3e-13 – 3.4e-12 throughout. Cells are **IN-SAMPLE** for `_t8` (S's held-out-cell OOS
    R² 0.9824 is the out-of-sample statement) — which makes a miss here a real miss, not extrapolation.
    Artifacts: `scripts/extract_biome_slow_oracle.py` → `references/M_slow_oracle_{counts,traits}.csv` +
    `M_slow_oracle_meta.json` (committed); `scripts/biome_slow_oracle_probe.jl` (cluster-only, ~180 MB pin).
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
- **`[VERIFIED 2026-07-30]` F_diff has NO soil ice, and that IS the cause of the boreal water-stress
  residual ADR 0051 left open (now ADR 0052).** The C's root-zone plant-available fraction at
  `boreal_siberia` (52059) is **exactly 0.000 for Nov–Apr** — every drop in the top metre is ice — while
  F_diff's sits flat at **0.67–0.91 all year**, so `emax·wr` beats the leaf-on demand every day and the
  leaf-on `wscal` is pinned at **1.000 in all twelve months**. Measured by
  `scripts/boreal_soilice_diagnosis.py` (C side, from `d_rootmoist.nc` + `whc_nat.nc`) and
  `scripts/boreal_soilice_probe.jl` (F side, `root_zone_soilmoist`). It is not a bad `wscal` — it is the
  right `wscal` of a soil column that cannot freeze.
- **`[VERIFIED 2026-07-30]` SECOND, DISTINCT residual: F_diff's root-zone water runs too DRY in dry cells**
  (ADR 0052). Same seasonal shape as the C, systematically lower: Sahel Jan **0.361 vs 0.533**, Jul 0.564
  vs 0.770; mediterranean Jul 0.239 vs 0.369. That — not the `wscal` definition — is what remains of those
  two cells' ADR-0051 gap (Sahel 36.5× the noise floor, mediterranean 7.5×), and it points the **opposite**
  way from boreal: F_diff **over**-stresses where it runs too dry. Higher-value than soil ice for a global
  run (semi-arid cells vastly outnumber permafrost ones). Candidate terms: the `_infiltrate` cascade (no
  surface/infiltration-excess runoff — a documented v2 item), `_soil_evap`, and the absent free-water
  (`w_fw`) reservoir.
- **The C's `rootmoist` + `whc_nat` are a per-cell, per-day reference for the emulator's root-zone water
  ANYWHERE on the global grid, with no new HPC run** (`d_rootmoist.nc` is in the global daily output).
  `w_C = rootmoist / Σ_{l<3} whc_nat[l]·soildepth[l]`, `soildepth = 200,300,500` mm. This is the cheapest
  check on F_diff's soil water balance — measure any soil-water residual against it FIRST. `swc` is NOT
  invertible to `w` (ADR 0035); `rootmoist` is the only output carrying it.
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
