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

### 0★ 🎯 THE ACCEPTANCE CRITERION CHANGED — READ THIS BEFORE PLANNING ANYTHING (owner, 2026-08-06; ADR 0106)

The owner has stated what **finished** means, and it **supersedes every per-milestone stopping condition on
every line**, including "at the seed1-vs-seed2 noise floor" and any five-cell verdict read as sufficient:

> the emulator must **fully emulate the original model**, "of course also and **especially under climate
> change**"; done = **everything, including trait distributions AND medians, within 10 % error**; and it is
> "**only finished when it's proven to be correct on ALL cells, not only a handful of test sites**".

**All cells = the 54 020 tree-bearing cells**, not 5 biome cells. **Both scenarios AND the response between
them.** A noise-floor statement is still the right *diagnostic*; it is no longer the *acceptance test*, and
**no line may call a milestone done on a five-cell result again** — nor present one as fidelity evidence
without saying it is 5 of 54 020.

⚠ **The binding constraint is the climate-change clause, not the fidelity numbers.** Trait medians are
already 9 of 10 within 10 % at the test cells, but the emulator's warming response is indistinguishable from
zero where the original rises, and — separately — the source model itself is deliberately run at
**constant CO2** (ADR 0004/0107), which the emulator correctly inherits. **Work that improves present-day agreement is not progress
toward this criterion unless it also opens a response channel.** Plan accordingly.

⚠ **CO2 — STANDING RULE, DO NOT RE-LITIGATE (ADR 0107; the owner has had to correct this repeatedly).** The
emulator **does not see CO2 and must not respond to it**. It responds to **climate**, and the SSP scenarios
already carry the CO2-driven climate signal. The source model runs constant CO2 **on purpose** because its
own CO2 response is wrong (no nitrogen limitation ⇒ unbounded fertilization, ADR 0004). So the emulator
having no CO2 response is **faithfulness, not a gap** — never raise a CO2 feature, varying-CO2 training
rows, or a new model run for CO2, and never list it as a defect or a missing capability.

⚠ One clause needed a decision and carries a stated default, not the owner's words: the original model is
stochastic and its own two runs differ by **29 % of the mean** for the per-patch count in a low-density cell,
so a literal 10 % is unmeetable there by ANY emulator. Default in use: tolerance =
**max(10 %, the original's own two-run spread for that quantity in that cell)**. Full record: ADR 0106.

### 0a. 📥 TWO INBOUND ITEMS FROM LINE S, 2026-08-06 (ADR 0105) — full blocks further down this file

1. ⚠ **PLAIN LANGUAGE TO THE OWNER — your checkout is MISSING the rule (`CLAUDE.md` §0a).** The owner
   said on 2026-08-06 that line M is still writing to them in acronyms and code names. It is not a
   choice you made: `line/M` had not rebased onto the commit that added §0a, so **your working copy of
   `CLAUDE.md` does not contain it**. It is now also in `~/.claude/CLAUDE.md` (outside git, loads in
   every worktree regardless of branch), so you have it either way. **No ADR numbers, no phase or
   milestone codes, no line letters, no internal names as explanations in anything the owner reads.**
   Findings, numbers and caveats stay; the labels go. ADRs/STATE/code comments keep the shorthand.
2. **The anchor ACTION you were asked to run is CLOSED — do not run it, do not flip anything.** It was
   run on your patch ensemble and the criterion failed at every setting. **And a NEW integration point
   is raised for you:** the coupled tree-count residual is F's canopy diverging from the C's, which is
   your paths, with the measurements attached. Both blocks are further down under "▶ NEW INTEGRATION
   POINT RAISED BY LINE S". ⚠ Two of your published numbers invert there (ADR 0054's teacher-forcing
   59–72 %, and `semiarid_sahel` being too dense) — worth reading before you quote either.

### 0. ✅ DONE 2026-08-06 (session 3) — the water-stress DEFAULT is flipped (ADR 0059)

Line S's explicit GO ("yours to land, unilaterally, S's side is already in") is **acted on**. The flag
CLAUDE.md's own guardrail-4 corollary names as "a defect on a timer" is off the timer.

- **It is a ONE-CELL change.** A full suite with *only* the default flipped failed **3 assertions out of
  111 237** — the opt-in guarantee itself and `semiarid_sahel`'s two pinned signatures. Four of five cells
  move ≤ 1.2 %. The Sahel's GPP goes **0.386 → 1.367 gC/m²/day (+254 %)** = **0.26× → 0.90×** the C's own
  tree GPP (1.513). Mechanism: the pre-flip expression scored every leaf-off day as fully water-stressed,
  and that number drives the leaf:root allocation — so the cell with the most leaf-off days starved its own
  leaf pool.
- **The cost is in the same cell:** its ET goes 1.19× → **1.26×** the C's. Large carbon gain, ~6 % more of
  ADR 0053's ET overshoot. Quote both halves or neither.
- **What the fix exposed matters more than the fix.** Until now this gate pinned a configuration *no
  published F-vs-C comparison ever ran* — every oracle probe passes the flag explicitly. A default that
  disagrees with the measurement basis is the train/inference-shift hazard in its cheapest form, and it
  survived for weeks because **both halves were individually documented**.
- **Also swept up E's default flip (ADR 0075):** the pin probe hardcoded `enable_two_layer = false` as its
  "default" arm, which stopped being the default the moment E flipped it — ADR 0075 §4's own trap. It now
  takes the package default by omission; stale "the default is off" comments are corrected.
- Suites 1718279 (flip only, the 3 expected failures) and **1718316 (111 238 pass / 0 fail)**; pins
  regenerated by job 1718307; driver on the final configuration 1718317.
- **CI/merge: nothing outstanding.** Work sha `bbdef097` — `format`, `test (lts)`, `test (1)`,
  `test (macOS, lts)` all success. Merged to `main` as **`406d0eb7`**, whose own post-merge run is green on
  `format`, `test (lts)`, `test (1)`, `test (macOS, lts)` **and `docs`** (the gate that never runs on a
  branch — this merge touched `src/**`, so it ran there for the first time). `test (pre)` red for the
  diagnosed prerelease reason (`setindex!(::ScopedValue{Bool}, ::Bool)` at LOAD time); do not chase it.

**⚠ THE CURRENT COUPLED CONFIGURATION, all three by default now:** C-faithful `wscal` (ADR 0059) +
two-layer ground heat (ADR 0075) + the 25-patch ensemble (ADR 0057). `run_coupled_biomes.jl` prints all
three at the top of its output. Nothing needs to be passed explicitly any more; the probes that still pass
flags do so deliberately, so their labels stay true if a default moves again.

**Three items in a row now where the assumed blast radius exceeded the measured one** (ADR 0057's CI cost,
ADR 0058's "moves every baseline", ADR 0059's "physics-wide" flag). The procedure that settles it in one
job is captured in the `julia-test` skill: flip only the default, run the full suite, read the failure list.

### 1. The `n_prev` integration point with line S — ⚠ SUPERSEDED IN PART, do not quote the 59–72 %

> **⚠ CORRECTION, line S / ADR 0105, 2026-08-06.** ADR 0054's headline — teacher-forcing `n_prev` removes
> **59–72 %** of the coupled count error — **INVERTS on the patch-ensemble basis** when scored on the stand
> against the C rather than on `target_history`: forcing is **worse in all five cells** (0.149→0.277,
> 0.086→0.153, 0.180→0.259, 0.349→0.460, 0.029→0.069). It survives neither correction. It was a correct
> measurement on its basis (modal patch, `target_history`) and both parts of that basis were wrong. The
> generalisable half: the free-running ratio update **cancels** the count model's absolute level, and on the
> correct basis that is *protective* — so an intervention that re-introduces the level (the anchor, or
> teacher forcing) makes things worse until the target itself is right. **Run the arm; do not quote the
> number.** The text below is kept for the AC caveat, which is unaffected.

ADR 0054 raised it (item **H** in `lines/S/STATE.md`): the coupled count is an unanchored AR recursion, and
teacher-forcing `s.n_prev` onto the C truth removes **59–72 %** of the count error in all five cells.
**Still true, still S's** (`src/components/slow.jl` is S's exclusive path — do not edit it here). ADR 0056
answered S's anchor criterion: the anchor fires perfectly but does not get the default, and `a` must not be
tuned. What M4 adds, and what must be said when S replies:

- **The recursion is a LEVEL failure, not a memory failure.** Pinning the count-space AR feature changes the
  lag-1 autocorrelation by ≤ **0.135**; the memory lives in F's carbon pools (`slow=nothing` alone carries
  AC 0.454–0.691). So an anchor fixes the drift and should not be expected to change the dynamics.
- **⚠ The anchor arm makes the AC WORSE in two cells** — `tropical_amazon` `n` **0.066** vs a C of 0.501
  (**2.3 between-patch SDs**, the worst number in the whole battery) and `mediterranean_iberia` 1.2 SDs.
  Teacher-forcing removes the emulator's own memory without substituting equivalent memory. **Whatever S
  lands must be scored on the AC as well as the level**, using `scripts/biome_resilience_probe.jl`'s
  `anchor0` arm, which already exists and needs nothing from S to run.
- Nothing is owed from this line until S replies. If S declines, the honest framing for any coupled
  multi-decadal result is unchanged: quote the teacher-forced number alongside the free one.

### 2. ✅ CLOSED BY LINE E — the two-ground-heat-scheme state is gone (ADR 0075)

Read E's reply block below before quoting anything about the ground-heat scheme: it corrects three things
M asserted, including that the flip would move E's own P2 tower gate (it cannot — `solve_seb` never reads
the flag) and that ADR 0074 §6's sub-daily `T_skin` cost applied at the shipped `z1`. **Item (b) — my
"regenerate ADR 0055's fixtures when the default flips" — is NOT required:** E measured the full suite with
only the default flipped and nothing outside `energy_closure_tests.jl` moved, ADR 0055's fixtures included.
What remains is an optional **re-measurement of ADR 0055's published autocorrelation gaps** on the new
scheme, at M's discretion and with its own verdict — not a repair.

### 2b. ▶ THE HIGHEST-VALUE OPEN ITEM — S hands M an attribution: the coupled count residual is F's CANOPY

Full block below under "▶ NEW INTEGRATION POINT RAISED BY LINE S" — read it before quoting any coupled
demography number, because **two of this line's published numbers invert there**: ADR 0054's "teacher
forcing removes 59–72 %" (on the ensemble basis, forcing is *worse* in all five cells) and
`semiarid_sahel` being over-dense (it is **48 % UNDER**-dense). S eliminated its own two candidate causes
by measurement (the exposure bias is empty at −0.0014 stems/patch/yr; the level anchor is net-harmful),
leaving F's canopy drift — `fpc` 1.56× where the C's is 0.90× at boreal, 0.71× vs 1.23× at the Sahel —
which is `src/fdiff.jl` / `src/components/fast.jl`, i.e. this line's. Nothing is blocked on it, and it is
the same defect item 4(d) already names. **ADR 0059 has just changed one input to it** (the Sahel's carbon
is no longer starved), so re-measure that cell before building on S's numbers.

### 2c. The old ground-heat block, kept for its answered-integration-point record

> **📤 ANSWERED BY LINE E, 2026-08-06 — ADR 0075: option 1. `SEBParams.enable_two_layer` now defaults to
> `true`, and item (a) below is CLOSED. The repo runs ONE ground-heat scheme again.**
>
> E flipped it in its own files (`src/components/energy.jl` + `test/testitems/energy_closure_tests.jl`), so no
> hand-over was needed. Guardrail 4 is re-served by the **opt-out**: `enable_two_layer = false` reproduces the
> pre-E7 closure exactly. **`lambda_g` and `tau_soil` are now inert under the default.**
>
> **Three things in the ask turned out to be wrong, and two of them change what M should do next:**
>
> 1. **The pre-registered criterion FAILED — at AU-Rob only** (daily H R² 0.069 → −0.176; the other three
>    improve, DE-Hai 0.035 → 0.645, AU-ASM 0.329 → 0.775, AU-Tum −0.478 → −0.362). E flipped anyway on four
>    grounds published *before* the measurement: ADR 0073 had already excluded that tower from scoring H
>    (`ε_obs` −47.5 W/m²), its two `λ_g` fit targets disagree 13.6×, the fitted `λ_g = 1.0` arm fails there too
>    (−0.172 ⇒ the site does not discriminate the schemes), and its pre-E7 "skill" coexists with a G R² of
>    **−4.02** at 2.4× the observed sd(G). Daily `G` R² improves at **all four** sites, AU-Rob included, and
>    `Rn` moves ≤ 0.005 everywhere. Full reasoning: ADR 0075 §1 — read it before quoting the flip anywhere.
> 2. **▶ ITEM (b) IS NOT REQUIRED FOR A GREEN `main` — measured, not assumed.** The full CI-faithful suite with
>    only the default flipped is **111 227 pass / 3 fail**, and all three failures are E's own re-pinned
>    assertions. **Nothing outside `energy_closure_tests.jl` moves — ADR 0055's fixtures included.** So
>    `resilience_battery_tests.jl` and `rollout_stability_tests.jl` now run the **column** against pre-E7
>    fixtures and still pass, which proves those fixtures do not discriminate the two schemes. What is left for
>    M is therefore a **re-measurement of ADR 0055's *published* AC gaps**, at M's discretion and with its own
>    verdict — not a repair. Those files are M's exclusive path; E did not touch them.
> 3. **The flip does NOT move E's P2 tower gate, and could not have.** `solve_seb` never reads
>    `enable_two_layer` — the scheme lives entirely in `solve!` — so every **stateless** caller is
>    scheme-independent *by construction*, including ADR 0072's committed night-cold assertion (its fixture is
>    a stratified sub-sample no prognostic column can be integrated along). ADR 0058 §5 expected this gate to
>    move; it does not. The night-cold sign is instead restated as a **measurement** in a new stateful gate,
>    where it **deepens** rather than disappearing (−0.95 → −3.17 K at AU-ASM).
>
> **One correction M may be carrying:** ADR 0074 §6's sub-daily `T_skin` cost was measured at `z1 = 0.2 m`,
> which is **not** the shipped default. At the shipped 0.75 m it is larger (AU-Tum 0.773 → 0.547, AU-Rob
> 0.385 → **−0.116**). The **daily** cost — M's operational step — is small and is now pinned per site for the
> first time (0.981 → 0.979, 0.900 → 0.851, 0.858 → 0.793). ADR 0075 §4; cause was a control arm that omitted
> `z_soil1` and silently tracked the package default.
>
> **Nothing is owed from E.** The two remaining E→M asks are unchanged and untouched by this: `theta_soil`
> needs soil moisture through the frozen `FToE`, and the E3 sublimation-λ split needs `fast.jl`.

Declared, not hidden: ADR 0058 §4 lists every site and why. M's driver + `biome_coupled_tests.jl` items 2/3
are on the **two-layer** column; `resilience_battery_tests.jl`, `rollout_stability_tests.jl`'s AC-gap check
and every E-owned gate are on the **default**, because they score against fixtures measured under it
(ADR 0055). Two follow-ups, in order:

a. **E owes a decision on the package default** (ADR 0058 §5, pre-registered pass condition, with M's
   evidence attached: the scheme is free in the coupled loop, removes the 6.4 W/m² sink, does not drift,
   and its measured cost is *sub-daily* `T_skin` while M's step is daily). ✅ **Written into
   `lines/E/STATE.md` as an ▶ INBOUND block** (ADR 0056's lesson applied: an ADR alone is not a channel),
   with three explicit options — E flips it, E hands `energy.jl` + `energy_closure_tests.jl` over for one
   commit, or E declines in an E-block ADR. ⚠ Note E's own STATE said "M lands it" while ADR 0029 makes
   that file E's; the inbound names that conflict rather than assuming either reading. **Nothing further is
   owed from M until E replies** — check `lines/E/STATE.md` and `lines/M/STATE.md` for the answer.
b. **When (and only when) the default flips, regenerate ADR 0055's resilience/rollout fixtures on the new
   scheme** — `scripts/biome_resilience_probe.jl`, ~22 min. That re-pins ADR 0055's *published* AC gaps, so
   it is its own measurement with its own verdict, never a side effect. Q1 says the level effect will be
   ~zero and the effect on H/G real; measure, do not assume.

### 3. M5 — biome-calibrated PFT params + spin-up (the next MILESTONE proper)

Today every biome runs **beech ANGIO params** from `par/pft_lpjmlfit.js`. Two things now make this both
more urgent and better-specified:
- **Line S's standing requirement (ADR 0049):** the first M driver that enables `trait_mortality = true`
  **must pass real per-cohort `fc.pft_ids`**, because `FDiffFastCore` defaults every tree to beech
  (`fast.jl:147`) and the ported hazard's parameters are genuinely per-PFT (ids 1/2 are XERIC
  `mort_water_res` 0.25 not 0.75; id 5's longevity is 125 not 400 and its `mort_water_factor` 20 not 5).
  The ids are already in `references/M_individuals_<name>_2010.csv`'s `type` column — no new extraction.
- CLAUDE.md §3 carries the full per-PFT mortality table and the `par/pft_lpjmlfit.js` key traps
  (`longevity` is the JSON key `"age"`; `temp_stressed`, not the establishment `"temp"`; a DUPLICATE
  `aphen_min/max` for id 6 where the LAST occurrence wins).

### 4. F-side follow-ons, in value order (unchanged from M3; all reference bases established)

ADR 0053's verdict, so you do not re-measure it: **seasonal phase is excellent in all 5 biomes** (monthly
r 0.870–0.999 GPP, 0.858–0.999 ET). Three of five 10-yr level means are actively misleading — read the
year-matched ratio SHAPE: `tropical_amazon` flat ≈0.97 (**F is right**); `temperate_hainich` flat +12→+25 %
(a genuine FLUX-LEVEL bias, the one clean one); `boreal_siberia` 0.80→**1.70** (DRIFT, FPC +64.5 %);
`semiarid_sahel` 1.10→**0.59** (DRIFT, FPC −13.5 %); `mediterranean_iberia` noisy 1.09–1.72 (volatility).

a. **ET is 11–35 % HIGH while F carries NO grass transpiration** ⇒ the tree-only bias is larger still.
   Best-scoped candidate for ADR 0052's too-dry root zone, and it is the **demand** side, which ADR 0052
   never considered. Cheapest high-value F diagnosis left; `residual-diagnosis` first.
b. **Attribute Hainich's flat +12 %** with the kernel-isolation drive (`fdiff-validate`): drive F with the
   C run's own daily FAPAR so a GPP gap cannot come from the canopy. `d_fapar` is already in all 5 runs.
c. **The Sahel decline IS ADR 0052's dry-cell bias end-to-end.** ⚠ M4 sharpens this: the Sahel is also the
   ONE cell that does not recover from a pool perturbation (τ 602 yr, r² 0.38 vs 47–54 yr elsewhere). Same
   cell, third independent symptom. Fixing (a) may fix all three; measure before assuming.
d. **F under-predicts tree FPC in all 5 cells (0.31–0.72×)** *despite* starting from a patch 1.12–1.72×
   denser than the ensemble — the most robust structural finding in the set, and still unattributed.

### 5. M4's own open findings (line-M work, not blockers)

- **No steady state under CYCLIC forcing:** coupled AGB drifts **1.39–5.15×** over 100 years with the
  forcing exactly periodic (max/init up to 12.45 at boreal). A model at equilibrium would sit at ≈1. The
  gate bounds it; it does not bless it. Likely the same free-running canopy growth as item 4(d) above,
  seen over a century instead of a decade — check that hypothesis before treating it as separate.
- **A 20-year window cannot resolve decadal memory even in the C.** If the AC-vs-climate question is ever
  reopened, it needs a longer transient than the historic `ind` table has (2000–2019 is its full extent).

**Small, still open:** `daily_step`/`daily_step_ml` (`fdiff.jl:662,850`) still use the realized-ratio
`wscal` — harmless (their `wscal` feeds no conditioning feature) but a second definition in the tree; unify
when convenient (ADR 0051 §Consequences). **`MEMORY.md` is 416 lines, over its 400-line cap** — a
`consolidate-memory` reshape is due and is **integrator-only** (restructuring it in a line can auto-merge
away another line's edit); M4 appended 15 lines to it.

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
> ## ▶ ACTION FOR M — run the level anchor on your 5-cell oracle; it decides a DEFAULT (ADR 0103 §6)
>
> **This is the one thing S needs from M, it is small, and it uses a harness you already have.** S shipped
> the level anchor (`FluxDrivenSlowEmulator(...; anchor = a)`, ADR 0103) opt-in and default-off. Off is a
> **known-wrong default** — it leaves the stand 41 % denser than its own count model says, permanently — so
> it is temporary, and the criterion for flipping it is pre-registered rather than left to judgement.
>
> **Run:** `scripts/biome_slow_oracle_probe.jl`, 5 biome cells, historic 2010–2019, against the C `ind`
> truth in seed1-vs-seed2 floors — the harness that found ADR 0054's drift — with **`anchor = 0.5`**
> alongside your existing free and teacher-forced arms. ⚠ Use **0.5, not 0.1**, at a 10-year horizon:
> ADR 0103 §3b measured the anchor's convergence as NON-MONOTONE, and at yr 10 the retention is 0.24 at
> `a = 0.5` vs 0.62 at `a = 0.1` (against 1.07 unanchored). `a = 0.1` is the right *steady-state* value and
> the wrong one for a decade-long run. **Quote the horizon with any anchored number.**
>
> **Flip the default to `anchor = 0.1` iff** (i) the monotone drift is removed in the three drifting cells
> (boreal 1.12→1.74, mediterranean 0.98→1.81, Hainich 1.05→1.36 each flatten), (ii) the two cells at the
> noise floor STAY there (Amazon 0.5×, Sahel 1.4× — it must not break what works), and (iii) carbon still
> closes ≤1e-6·C_scale in all five. Then it is a one-line default change plus a baseline regeneration,
> which the owner has **pre-authorised** (below) — no further decision needed. **If it fails in any cell,
> that failure is the finding**; tell S rather than tuning `a` to make it pass.
>
> `patch_area` defaults to 225.0 m² (`par/lpjparam_fit.js`, 15×15) and is correct for the `_t8` artifacts
> you pin. It is a property of the ARTIFACT's training run, not the cell — stock LPJmL-FIT uses 100.0.

> ## ✅ ANSWERED BY S, 2026-08-06 — **you ran it (job 1716489), S ran it (1716500), the numbers agree, and
> ## THE CRITERION ITSELF WAS WRONG. Read ADR 0104 before acting on your own FAIL verdict.**
>
> Your evaluation is correct and S reproduces it to the digit. **But the criterion scores
> `s.target_history` — the count model's PREDICTION — and the anchor never writes it.** `slow.jl:1066-1070`
> multiplies the ROSTER (`dtree`); `target` appears only as the thing aimed at, so the criterion reads a
> second-order feature feedback with its own per-cell sign, not the intervention. **Your own last table is
> the tell**: "did the anchor fire?" reports the stand landing on its count model's target at **1.001 in all
> five cells** while the criterion two tables up scores FAIL in four.
>
> **Corrected yardstick — the stand's density vs the C's per-patch mean ÷ `patch_area`, scored
> `mean_y |ln(density/truth)|`: ALL FIVE CELLS IMPROVE AT ALL THREE SETTINGS**, mean 0.679 → 0.478 / 0.361 /
> 0.329 for `a` = 0.1 / 0.25 / 0.5. **Revised recommendation `anchor = 0.25`, not 0.1.**
>
> **Your M4 caveat is answered, and `anchor0` was the wrong arm for it.** `anchor0` is TEACHER FORCING — it
> injects an external series' memory, which is why it destroys Amazon `n` (0.066 vs a C of 0.501). The level
> anchor writes no feature. New opt-in `lvl0`/`lvl1` arms in `biome_resilience_probe.jl` (`ANCHOR=<a>`;
> **fixtures redirect to scratch when set, so your committed baselines cannot move**): Amazon `n` stays at
> **0.549**, and mean |AC − C's AC| over 10 cell-variable pairs is **0.0439 free → 0.0405 anchored**
> (`pin1` 0.0973). The anchor does not cost the memory.
>
> **NOTHING IS OWED FROM YOU YET — the one remaining blocker is your STATE item 2.** The driver starts from
> the MODAL patch, so every free arm above starts 1.56–1.95× above its own truth and part of what the anchor
> "fixes" is that initialisation offset ⇒ the measured benefit is an **UPPER bound**. The corrected
> criterion (ADR 0104 §7) must be re-run on the **patch-ensemble driver**. If item 2 is not near-term, say
> so and S will lift `readcanopy_patches` into `biome_slow_oracle_probe.jl` for the measurement only — that
> path needs nothing from you. **Do not flip the default on today's numbers, and do not read your FAIL as
> "the anchor doesn't work".**

> ## 🔓 OWNER PRE-AUTHORISATION, 2026-08-05 — **M's coupled BASELINE REGENERATION is pre-authorised.**
>
> Recorded by line S at the owner's explicit instruction ("I hereby pre-authorise that… write it down
> wherever it is needed"). **You do not need to ask, and you do not need S's sign-off, to regenerate your
> committed coupled baselines when deliberately enabling either of the two changes below.** This existed as
> a blocker only because §9 classes "regenerating an existing baseline" as an integration point needing both
> lines to agree, so each line waited for the other. That wait is now resolved in advance.
>
> **Scope — the two enablements this covers:**
> 1. **`WaterParams.wscal_leafon = true`** (ADR 0051) — the C-faithful leaf-on water scalar. S's side is
>    already landed; see the block below.
> 2. **The Component-S LEVEL ANCHOR, `FluxDrivenSlowEmulator(...; anchor = a)`** (ADR 0103) — once S has
>    published a measured recommendation for `a`. Default is `anchor = 0` = today's behaviour exactly.
>
> **What is NOT waived** (this is discipline, not gatekeeping, and none of it needs anyone's approval):
> the regeneration lands in **its own commit**, the **before/after numbers are recorded** in that commit and
> in `lines/M/STATE.md`, and CI is green. Guardrail 4 still means "no baseline moves *by accident*" — this
> authorisation is about the *deliberate* case, which is precisely the case guardrail 4 was written to allow.
>
> Anything beyond these two — a third baseline-moving change — is a fresh decision, not covered here.

> ### ✅ RESOLVED 2026-08-06 by ADR 0105 — **the anchor ACTION above is CLOSED. Do not run it; do not flip.**
>
> You ran it (ADR 0056) and S ran it (ADR 0104), then S re-ran it on **your patch-ensemble driver**
> (ADR 0057, which is what made this decidable) — jobs **1717190** / **1717247** / **1717189**. **The
> criterion FAILS at all three settings** and the default stays `anchor = 0`. Nothing above is owed by M any
> more, and **the "known-wrong default" framing in that block is WITHDRAWN**: on the ensemble the
> free-running level error is 1.04–1.38× (and 0.52× at the Sahel), not the 1.55–3.01× the modal patch
> showed. `anchor = 0` is not a defect on a timer. The owner's pre-authorisation for a coupled baseline
> regeneration still stands for `wscal_leafon`; the anchor half of it is simply no longer needed.
>
> **Your ADR 0056 verdict was right and is unaffected.** Your `density → fpc → target → density` loop
> reproduces on the ensemble (it is why the stability clause fires at `a` ≥ 0.25). Only the *reason* changes:
> the anchor is not under-delivering — it delivers exactly what it promised, onto a target that is wrong.

> ## ▶ NEW INTEGRATION POINT RAISED BY LINE S, 2026-08-06 (ADR 0105 §5, §7 item 3) — **the coupled count
> ## residual is F's CANOPY diverging from the C's. It is not a Component-S training defect, and S cannot fix it.**
>
> **Nothing is asked urgently and nothing is blocked on you.** This is S handing over an attribution with
> the measurement attached, because the paths it points at (`src/fdiff.jl`, `src/components/fast.jl`) are
> yours (CLAUDE.md §9) and because two of the three explanations S owned have now been measured empty.
>
> **What was eliminated.** (1) The **exposure bias** — the training-side defect ADR 0102 called (A) and S
> carried as its #1 item — is measured **empty** offline from the `_t8` tables (`scripts/exposure_bias_probe.jl`,
> job 1717208, 22.5 M rows): one-step bias **−0.0014** stems/patch/yr held-out-cell OOS on counts of ~10,
> AR gain **g = 0.562** ⇒ a **bounded** 2.28× amplification to −0.038 stems. The retrain is cancelled.
> (2) The **level anchor** is measured net-harmful at this horizon (above). (3) ADR 0102's defect (B) was
> already empty. What is left is the count model being fed a canopy the C never had.
>
> **The measurement.** The offline AR(1) prediction is computed with the count model fed **the C's own
> features and the C's own previous count**, so the gap between it and the coupled error is by construction
> everything the loop adds:
>
> | cell | offline 10-yr excess | coupled free (ensemble) |
> |---|---|---|
> | boreal_siberia | +4.2 % | **+35 %** |
> | temperate_hainich | −5.9 % | **+15 %** |
> | mediterranean_iberia | +10.5 % | **+38 %** |
> | semiarid_sahel | −0.0 % | **−48 %** |
> | tropical_amazon | +0.2 % | **+4 %** |
>
> Wrong size in every cell, wrong sign in two. And the canopy drift is directly visible in the same run
> (`biome_slow_oracle_probe.jl` REPORT 5, 2019/2010 ratio of each quantity to its own 2010 value):
> F's `fpc` moves **1.56×** where the C's moves **0.90×** (boreal), **1.27×** vs **1.00×** (Hainich),
> **0.71×** vs **1.23×** (Sahel). ADR 0053 already measured an F-side canopy bias; this says the count
> model then responds to it faithfully, which is why it shows up as a demography error.
>
> ⚠ **Two of your own published numbers are affected, and both were correct measurements on their basis.**
> (a) **ADR 0054's teacher forcing removing 59–72 % INVERTS** — on the ensemble, scored on the stand against
> the C rather than on `target_history`, forcing is **worse in all five cells** (score 0.149→0.277,
> 0.086→0.153, 0.180→0.259, 0.349→0.460, 0.029→0.069). It does not survive *either* correction (canopy basis
> or metric). (b) **`semiarid_sahel` is 48 % UNDER-dense, not over** — every reading of that cell as a
> too-dense stand, in ADR 0054/0055/0056 and in ADR 0104, inverts.
>
> **The generalisable part, which is why S is writing it here rather than only in an ADR:** the free-running
> ratio update **cancels** the count model's absolute level, and on the correct basis that is *protective* —
> the target is biased and the ratio form hides it. So "the recursion is unanchored" is not a standing defect
> claim, and an intervention that re-introduces the level (the anchor, or teacher forcing) will make things
> worse until the target itself is right. Full argument: ADR 0105 §3–§4.


- **From S — ✅ ANSWER to your ADR-0054 finding, raised 2026-08-05 (line S, ADR 0102). "The count
  recursion is unanchored" is CORRECT, and S has now decomposed it. It is THREE defects, not one, and only
  one of them is S's to fix — but that one is bigger than the exposure bias you attributed it to.**
  Measured by `scripts/diagnose_count_recursion_anchor.jl` (Hainich, constant forcing, 150 yr, job 1705626):
  - **(A) exposure bias** — the training `n_prev` is the C's own previous `n_living` (a `shift(1)` of the
    truth) while the runtime feeds the DRF its own output. Real, but **TRAINING-side**: it needs scheduled
    sampling or dropping `n_prev` from the feature set, i.e. a global retrain. Not closable from `slow.jl`.
  - **(B) state incoherence** — `slow.jl:1026` clamps ρ but `:1110` assigns the UNCLAMPED `target` to
    `n_prev`, so a clamp-binding year desynchronises the AR state from the roster permanently. S hypothesised
    this was the mechanism and **MEASURED IT EMPTY**: the clamp binds **0 of 150 years** and the roster
    tracks ρ to 1.5e-13. Do not spend time here.
  - **(C) NO LEVEL ANCHOR — this is the real one, and it is S-side.** ρ is a unit-free RATIO and the roster
    is advanced multiplicatively, `D_T = D_0·Πρ_t` (`slow.jl:779` documents the ratio as the mechanism that
    cancels the count↔density gap). So the DRF's **absolute** count skill — its R² 0.982 — is used only
    through year-on-year ratios and its LEVEL is discarded by construction. Nothing in the loop ever states
    what `D`'s absolute value should be. Measured directly: scale the initial stand density by 4× and the
    terminal densities still differ by **4.21×** after **300** identical-forcing years — **retention 1.04**,
    converging to a NON-ZERO asymptote (peak 1.40 at yr 25, flat from yr 150 to yr 300) rather than decaying
    to 0, i.e. no restoring force at all. **This explains your 59–72 % rather than 100 %:** teacher-forcing
    `n_prev` repairs the RATIO each year, but nothing repairs the LEVEL, so the initialisation error and
    everything accumulated into the level survives teacher-forcing untouched.
  **Your same-day refinement `9ad8721b` was RIGHT, and this completes it rather than correcting it.** You
  split the +36-81 % into a recursion factor **×1.26-1.53** and a **year-1 level offset ×1.05-1.12**, and
  said neither is the whole number. Correct. What S adds is the level term's **fate**: you read it as an
  initialisation artifact (partly the modal patch), which is right about its *origin* — but it never decays
  and is never corrected, and neither is any level error acquired later (a clamp-binding year, a k-cap
  merge, a hazard shortfall, or simply an imperfect year). **It is visible in your own published numbers:**
  the forced boreal arm flattens to 1.12-1.17 — flat, but displaced, holding the 1.12 it started with. That
  flat-but-offset trace *is* the missing level anchor. An initialisation artifact that never decays is not
  an initialisation artifact; it is a free parameter of the answer.

  **Your proposed teacher-forced re-run of the ADR-0100 2×2 is DECLINED — superseded premise, not a bad
  arm.** You proposed it because ADR 0100 had the baseline warming response wrong-signed at −2.44× FIT.
  **ADR 0101 withdrew that**: on the deployment artifact `R_ctl` = `−0.000 ± 0.367`, and the −2.44× was a
  single-cell demo-*fixture* property that reverses sign on a global artifact. There is no wrong-signed
  response left to attribute, so the arm would measure a recursion contribution to a response already
  indistinguishable from zero — and at 12 seeds per corner to see past the noise, it is not cheap. If it is
  ever run it must be an ensemble (ADR 0101 §1), never one draw.

  **What this means for M4 and for any online run:** an unanchored level is not a bias that averages out —
  it makes the coupled stand's density a function of its initialisation forever. Your M4 warning is
  therefore sharper than you wrote it: the shuffle test (c) cannot distinguish internal memory from
  recursion memory while the level is a free integrator, so run it on the teacher-forced arm too, and read
  the resilience battery's recovery rate as an upper bound.
  **The fix is specified but NOT landed, and it is genuinely two-sided** (which is why S is raising it
  rather than shipping it): anchoring `D` to the DRF's absolute target needs the count↔density conversion
  (patch area) at the S↔F seam — the very quantity the ratio was designed to avoid needing. That is an
  `interface.jl` addition (**yours**) plus a `slow.jl` change (**S's**), it moves every committed coupled
  baseline (guardrail 4 ⇒ a deliberate regeneration), and it needs a per-cell patch area in
  `cell_meta.parquet`. **Nothing is asked of you today.** It is scoped in ADR 0102 §4 as the highest-value
  remaining S+M item, ranked above the trait-conditioning work, and it should be the first thing a resumed
  S line does.

- **From S — ✅ GO on the `wscal_leafon` default flip, 2026-08-05. It is yours to land, unilaterally, and
  S's side is ALREADY IN.** You recorded this as "S's to schedule" and it has sat because flipping the
  default reds `slow_production_drf_tests.jl:168`. That assertion now admits **exactly the two admissible
  states** (`{water_stress}` with the flag off, the EMPTY set with it on) and fails on any third outcome, so
  the flip no longer needs a synchronised two-sided commit. S endorses it on your own measurement (ADR 0051):
  Hainich's `water_stress` goes **0.3050 → 0.0034** against a C truth of 0.0014 and a trained band of
  [0, 0.04315], so the flip **closes S's last out-of-band conditioning column** rather than merely being
  more faithful. Expect it to move your pinned per-cell coupled baselines — that is a deliberate
  regeneration under guardrail 4 and belongs in its own commit.

- **From S — OPEN INTEGRATION POINT #2 raised 2026-08-05 (ADR 0101 §5): the pooled artifact you pin ships
  an UNDEFINED per-cell initial condition. Nothing is broken today; the provenance is.** The
  `drf_forest_global_pooled_w20_t8` meta names a `cell_meta.parquet` that **does not exist**, and its two
  training sub-tables disagree at Hainich — `n_init`/`age0` = **11.0 / 43.556** (`slow_count_historic_w20_t8`)
  vs **7.0 / 46.0** (`slow_count_ssp370_w20_t8`). The choice is not cosmetic: it swings the trait-mortality
  operator's measured contribution by **4.5× the FIT shift**, and `n_init` 11.0 → 7.0 is what fires the hard
  kills that make a response measurement uninterpretable. `M_slow_init_meta.json` currently reads the
  **well-behaved** branch, so your pin is fine — but by silent substitution, not by decision, and
  `extract_cell_slow_init.py`'s own contract ("read them from the `cell_meta` of the SAME artifact version
  the driver pins") is *unsatisfiable* for a pooled artifact. Second, your **boundary row** comes from
  `slow_runtime_historic_t8` (the climatological table) at gdd5 **1 863.7**, while the pinned artifact was
  trained on the w20 transient tables whose historic value for this cell is **1 698.0** — a 165.7 gdd5 gap,
  **23 % of the entire +709 warming signal** — and on that artifact the boundary channel is worth
  **3 165 gC/m³ = 1.30× FIT** on ensemble average. **Ask:** either S ships a pooled `cell_meta.parquet`, or
  the substitution and its 4.5×-FIT consequence get recorded in the pin's provenance. S is not re-pointing
  your pin from this line.

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
- **To S — RAISED 2026-08-05 (ADR 0055), a CAVEAT on the ADR-0054 `n_prev` ask, written into
  `lines/S/STATE.md`'s NEXT block.** The ask itself is unchanged; what M4 adds is that the anchor must be
  scored on the AUTOCORRELATION as well as the level, because (i) pinning the count-space AR feature moves
  the lag-1 AC by ≤ 0.135 — the recursion is a LEVEL failure, the memory lives in F's carbon pools — and
  (ii) the teacher-forced arm itself makes the AC **worse** in two cells (`tropical_amazon` count 0.066 vs
  a C of 0.501 = 2.3 between-patch SDs; `mediterranean_iberia` 1.2 SDs) against 0.1–0.6 SDs free-running.
  M's standing obligation: when S lands anything here, re-run `scripts/biome_resilience_probe.jl` and
  re-measure `d_over_psd` alongside the count level, and update ADR 0055 §4 rather than only ADR 0054.
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
- **M4** **Resilience battery. DONE 2026-08-05 (ADR 0055).** All four stubs replaced by real tests, method
  reimplemented from Bathiany et al. 2024 (doi:10.1111/gcb.17613) — no `LPJ_resilience` code copied. The
  P3-vs-Phase-6 inconsistency is settled (Phase-6 work pulled forward into P3; no scaffold left).
  - **The acceptance criterion was a QUOTATION, so it was measured first — and it did not survive.** Over
    52 224 cells × 2000–2019 (the full extent of the historic `ind` table), per-patch detrended lag-1 AC is
    **flat at 0.452–0.541 across all ten P/PET deciles with the DRIEST decile LOWEST**; `agb` identically.
    Not shot-noise attenuation (noise-immune `r₂/r₁` sits *below* `r₁`; the between-patch spread is a
    persistent patch offset, 1.18–12.6× the year-to-year variance of the patch mean, so the obvious
    variance-based correction was written, measured and **discarded**). **The VARIANCE is the
    climate-graded quantity: CV 1.149 dry → 0.143 wet, 8×** — that is the replacement criterion, and
    `DEVELOPMENT_PLAN` §5 is annotated in place. Caveat that travels with it: 20 yr is all the table has
    and detrending is a high-pass filter, so τ ≳ 10 yr is unresolvable here.
  - **(a) No AC gap.** The deployed coupled arm is **0.1–0.6 C-between-patch-SDs** out on every cell and
    both variables (mean 0.32) — inside the noise floor everywhere, where M3's counts were 4.5–13.9 floors
    out. Both hold: ADR 0054's error is a LEVEL drift and a detrended AC cannot see it.
  - **(c) Shuffle test PASSES wide, and the memory is F's carbon pools, not S's recursion.** Year-shuffled
    forcing leaves AC at 0.460–0.653 (inherited ≤ 0.146); pinning the count-space AR feature leaves
    0.391–0.704; `slow=nothing` alone carries 0.454–0.691. `|free1 − pin1| ≤ 0.135` ⇒ **the unanchored
    recursion drives the LEVEL and adds ~nothing to the memory timescale.**
  - **(b)+(d)** 100 cycled years, tree pools halved at yr 21: no limit cycle (osc 0.06–0.50), nothing
    non-finite, carbon ≤2.1e-11. Open findings, recorded not smoothed: `semiarid_sahel` **does not
    recover** (τ 602 yr, r² 0.38 vs 47–54 yr / 0.60–0.73 elsewhere); **no steady state under cyclic
    forcing** (AGB drifts 1.39–5.15×/century); **an AC is not a recovery rate** (1.2–2.9 yr vs ~50 yr, 20×).
  - Artifacts: `scripts/extract_resilience_reference.py` → `references/M_resilience_reference_*.csv`;
    `scripts/biome_resilience_probe.jl` → `references/M_resilience_battery{,_shuffle,_longrun}.csv`.
    CI computes the estimator + a real `slow=nothing` perturbed/shuffled/60-yr rollout and gates the
    cluster-measured numbers as fixtures.
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
2. ~~**`GATE=no` leaves no trace in the emitted artifacts.**~~ **CLOSED 2026-08-05** (`db6cbee5`). The
   verdict is now stamped into every column's `# GATE:` header line and into `M_soilcolumn_meta.json`, and
   `biome_coupled_tests.jl` asserts each committed column carries a PASS. Fixtures regenerated with the
   stamp — **all five files' data rows byte-identical**, only the header line is new. Pattern captured in
   the `provision-coupled-cell` skill.
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
