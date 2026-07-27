---
status: "accepted"
date: 2026-07-27
deciders: "engineering agent (standing autonomous delegation, STEERING_PROMPT); owner-confirmed long-term strategy (component-s-copula-handoff); reversible by the owner or a superseding ADR"
consulted: "ADR 0002 (emulate distributions), ADR 0004 (constant-CO2 regime), ADR 0020 (S conditioned on fluxes + a SLOW bioclimatic boundary + AR state), ADR 0023 (runtime-consistent training table), ADR 0025 (recruit-trait copula, same boundary conditioning); the LPJmL-FIT 20-yr Climbuf establishment memory; python/src/lpjmlfit_emulator/features.py::eco_diagnostics (climclusterpy); the orderA daily .clm climate forcing for historic + ssp370; src/components/slow.jl::{flux_feature_vector,live_flux_cond,reconcile_demography!}; scripts/build_slow_runtime_table.py"
informed: "scripts/build_slow_runtime_table.py (transient boundary + scenario pooling); a new transient-boundary data-gen script (trailing-window eco_diagnostics); src/components/slow.jl (opt-in per-year boundary series); scripts/train_slow_{drf,copula}.jl + eval_slow_{drf,copula}.jl (pooled + hold-out-by-scenario); the slow-drf-pipeline + emulator-validation-figures skills; MEMORY.md; JOURNAL.md; CHANGELOG.md"
---

# Component S is ONE pooled multi-regime emulator with a TRANSIENT (time-varying) bioclimatic boundary; scenarios/climate-models are pooled training data; CO₂ stays constant

> **Status note.** `accepted` 2026-07-27 under the standing autonomous delegation, implementing the
> owner-confirmed long-term strategy (`~/.claude/plans/component-s-copula-handoff.md` §"LONG-TERM STRATEGY"):
> **ONE** emulator that reproduces LPJmL-FIT across CLIMATE regimes AND its TRANSIENT behaviour — not one
> model per scenario. Refines ADR 0020 (the slow bioclimatic boundary goes from climatological-**static** to
> trailing-**transient**) and ADR 0023/0025 (the transient boundary flows through the same runtime-consistent
> training table + copula conditioning). Keeps ADR 0004 (CO₂ constant). Default remains OFF — committed
> baselines + the AD trainer stay byte-identical until the transient boundary is deliberately enabled.
> Reversible by a superseding ADR.

## Context and Problem Statement

Component S (ADR 0020) is conditioned on F's delivered fluxes + AR state + a **slow bioclimatic boundary**
that the fluxes do *not* carry — coldest-month temperature (`tas_cold_month`), growing-degree-days
(`eco_diag_gdd_5`), soil depth, and CO₂ (held constant, ADR 0004). These govern establishment and which
PFTs can be present. The recruit-trait copula (ADR 0025) conditions the trait marginals on the same boundary
(`live_flux_cond`). The owner's stated goal for S is to reproduce LPJmL-FIT **across climate regimes and over
its transient**, and to interpolate to **unseen** regimes and climate models — one environment-conditioned
emulator, not a family of per-scenario fits.

Two structural facts (established empirically this session against the live tables) block that goal:

1. **The boundary is TIME-CONSTANT — by construction, at the feature source.** `eco_diag_gdd_5` and
   `tas_cold_month` are **static per-cell climatological normals**: for Hainich (cell 42490) they are
   *identical every one of the 20 historic years* (`gdd_5 = 1863.70`, `tas_cold_month = 0.2184`). They are
   produced by `features.py::eco_diagnostics` over a **fixed** climatological window and broadcast across
   years; `build_slow_runtime_table.py` then *additionally* means them over years (`group_by(Cell).mean()`);
   and the runtime bakes `s.boundary` **once** at construction and re-appends it unchanged every year
   (`slow.jl` `FluxDrivenSlowEmulator.boundary`, read by `flux_feature_vector`/`live_flux_cond`). So **year 5
   and year 95 of a transient get the identical establishment gate.** A cell that warms until it crosses a
   `gdd5`/`tas_cold_month` PFT-presence threshold cannot have that shift represented. This is the defining
   limitation for **transient** fidelity — and LPJmL-FIT's own establishment gate is *not* static: it is a
   ~20-yr `Climbuf` running memory.

2. **The models are PER-SCENARIO, and the SSP boundary is not even populated.** The count DRF and the copula
   are trained separately per scenario (`drf_forest_global_{historic,ssp370}.drf`, `slow_copula_historic`).
   Worse, in the SSP feature table (`tables_ssp_sn/cell_year_feats.parquet`, 2015–2100) **every eco_diag /
   tas_* column is all-zero** — they were never computed — so the current SSP pipeline falls back to the
   **historic** climatological boundary. That is a future run of an 80-year warming trajectory driven by a
   **frozen present-day establishment gate**: the exact failure this ADR removes. SSP370 (MPI-ESM1-2-HR,
   strong warming over 2015–2100) is precisely where the transient signal is largest and where the boundary
   is most wrong.

The daily climate forcing needed to fix this exists on the orderA grid for both scenarios (ssp370:
`{tas,pr,rsds,huss,lwnet}_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm`; the equivalent historic forcing), so a
**transient** boundary is buildable — it is a data-generation task, not a data-availability blocker.

## Decision Drivers

- **Transient fidelity.** Reproducing FIT's transient requires the establishment gate to *track the changing
  slow climate*, mirroring FIT's ~20-yr `Climbuf` memory. A frozen boundary cannot.
- **Generalization to unseen regimes / climate models.** One model conditioned on ENVIRONMENT (climate +
  soil), pooled across scenarios (and later climate models), interpolates; N per-scenario fits do not.
- **Keep CO₂ constant (ADR 0004).** N-limitation-free FIT gives runaway vegc under rising CO₂; the ground
  truth is constant-CO₂. The SSP regime signal must enter via **climate** (→ gdd5 / tas_cold_month / the flux
  drivers) + soil, never via CO₂. CO₂ is not a feature.
- **No double-counting; keep ADR 0020's physical split.** The boundary stays the *slow* bioclimate the fluxes
  don't carry — it is made time-varying, not replaced by this-year weather (which the flux channel already
  carries). The slow memory (a trailing window), not this-year values, is the faithful form.
- **Train/runtime consistency (ADR 0020 §5, ADR 0023).** The transient boundary must be *identical* in the
  training table and at runtime, or S is conditioned at inference on a channel it wasn't trained on.
- **Guardrail 4 (opt-in, default byte-identical).** The change must leave every committed baseline and the AD
  trainer unchanged until deliberately enabled.

## Considered Options

- **A — status quo: time-constant boundary, one model per scenario.** Rejected: cannot represent the
  transient; cannot generalize to unseen regimes; per-scenario artifacts are not the goal.
- **B — transient trailing-climatology boundary + ONE pooled multi-regime model (chosen).** Recompute
  `gdd5`/`tas_cold_month` on a trailing W-yr window per (cell, year); pool scenarios (+ later climate models)
  into one environment-conditioned training table; CO₂ constant; train one copula + one count DRF; evaluate
  by held-out scenario in addition to K-fold-by-cell.
- **C — fully per-year (this-year) boundary, no trailing window.** Rejected as the boundary form: FIT's
  establishment gate is a *slow* memory (Climbuf ~20 yr), not this-year weather; a raw this-year boundary
  re-injects the high-frequency climate signal the flux channel already carries (the ADR 0020 double-count
  concern) and is noisier year-to-year. The **trailing window** is both transient *and* the faithful slow
  memory. (The window width W is the knob; W→1 recovers this option, W→∞ recovers the static boundary.)
- **D — proxy the transient with the per-year trailing raw-climate features already in the table
  (`temp_r10`, `prec_r10`).** Rejected as the *primary* mechanism: `temp_r10` is a raw-temperature trailing
  mean, not the establishment-gating bioclimate (`gdd5` = degree-day integral above 5 °C; `tas_cold_month` =
  coldest-month gate) that FIT uses to decide PFT presence. Keep `gdd5`/`tas_cold_month` as the boundary and
  recompute them on a trailing window — faithful *and* transient. `temp_r10`/`prec_r10` are retained only as
  a possible ablation/augmentation, not a replacement for the recomputed bioclimate.

## Decision Outcome

Chosen: **Option B.** The contract:

### 1. The boundary becomes TIME-VARYING — a trailing-climatology of the establishment-gating bioclimate

For each `(cell, year)`:
`boundary(cell, year) = [ gdd5_W(cell, year), tas_cold_month_W(cell, year), soil_depth(cell), 369 ]`
where `gdd5_W` / `tas_cold_month_W` are the `eco_diagnostics` bioclimate computed over a **trailing
W-year window ending at that year** (W ≈ 20–30, matching FIT's `Climbuf`; the exact W is a documented,
tuned hyperparameter — W→∞ recovers today's static boundary, so the static case is a nested special case and
a natural ablation). `soil_depth` stays static per cell; CO₂ stays 369 (ADR 0004). This **refines ADR
0020**'s "slow bioclimatic boundary" from climatological-*static* to trailing-*transient*; every other ADR
0020 conditioning choice (flux-then-integrate, drop this-year raw climate, AR state) is unchanged.

### 2. Data: recompute the bioclimate on trailing windows from the daily .clm forcing, for BOTH scenarios

The SSP eco_diag columns are unpopulated; the historic ones are climatological-static. A new data-gen step
computes `gdd5_W`/`tas_cold_month_W` per `(cell, year)` from the orderA daily `.clm` forcing
(`tas`/`pr`/`rsds`/`huss`) for historic and ssp370, producing a per-`(cell, year)` **transient-boundary
table** that replaces the static eco join. Early years have shorter windows (shrink to the available climate,
or backfill from the spin-up forcing) — a documented edge, not a blocker.

### 3. Both the training table AND the runtime use the same per-(cell, year) boundary

- **Training table** (`build_slow_runtime_table.py`, count + copula modes): stop meaning the boundary over
  years; join the transient boundary per `(cell, year)`. The conditioning column order is unchanged
  (`gdd5, tas_cold_month, soil_depth, co2`) — only its *values* become year-specific — so the
  `flux_feature_vector` / `live_flux_cond` feature-order contract (ADR 0023/0025) is preserved.
- **Runtime** (`src/components/slow.jl`): `FluxDrivenSlowEmulator` gains an **opt-in** per-year boundary
  series indexed by `s.year`. When set, `reconcile_demography!` updates `s.boundary` from the series each
  year *before* building `feats` (so both the count DRF and the copula's `live_flux_cond` see the transient
  boundary). Default = **no series** ⇒ `s.boundary` constant ⇒ committed baselines + gates byte-identical
  (guardrail 4). The offline/validation driver bakes the per-`(cell, year)` series from the transient-boundary
  table into a sidecar the coupled driver reads (as it already does for the static boundary/`n_init`/`age0`).
- **Online coupling** (SpeedyWeather): the faithful mechanism is a **self-maintained trailing climate buffer**
  (a Climbuf) fed by the climate F sees, from which S computes `gdd5_W`/`tas_cold_month_W` each year. This is
  a later coupling change; the pre-baked per-year series is the offline path and the immediate deliverable.

### 4. ONE pooled multi-regime model

Union historic + SSP370 (and later additional SSPs / climate models) into ONE training table; condition on
climate + soil (the flux drivers + the transient boundary); CO₂ constant; train ONE copula + ONE count DRF.
The per-scenario artifacts (`drf_forest_global_{historic,ssp370}`, `slow_copula_historic`) are demoted to
**evaluation slices**, not deliverables.

### 5. Evaluation adds HOLD-OUT-BY-SCENARIO / BY-CLIMATE-MODEL

In addition to K-fold-by-cell OOS (ADR 0025), evaluate by **held-out regime**: train on N−1 scenarios /
climate models, test the held-out one. This is the honest *unseen-regime* proof. **Falsifiable success
test:** on the held-out scenario's transient tail (its late, most-warmed years), the pooled +
transient-boundary model must reproduce the FIT trait/count distributions **materially better** than a
static-boundary per-scenario model. If it does not, the transient boundary is falsified for that regime and
this decision must be revisited (window W, or Option D augmentation).

### 6. Keep ADR 0004 — CO₂ stays constant (369)

CO₂ is **not** a varying feature and is not added as one. The regime signal enters only through climate
(→ gdd5 / tas_cold_month / flux drivers) + soil, which do vary.

### Consequences

- **Good.** Transient fidelity (the establishment gate tracks the warming); generalization to unseen
  regimes / climate models via one environment-conditioned model; train/runtime consistency preserved; the
  CO₂ constraint preserved; conservation unaffected (the boundary is a conditioning feature only, not a
  carbon quantity — `vegc_full_ind` is boundary-independent); default byte-identical.
- **Bad / risk.** (i) A **data-gen prerequisite** — trailing-window `eco_diagnostics` from the `.clm` forcing
  for both scenarios (a large SLURM job); until it lands, the pooled + transient model cannot be
  trained/evaluated, and coupled runs stay on the static boundary (honestly labelled). (ii) Early-year
  trailing windows are short (documented backfill/shrink). (iii) The window W is a hyperparameter — a poor W
  under- or over-smooths the transient; sweep it (the static boundary W→∞ is the baseline). (iv) The online
  Climbuf mechanism is deferred; offline uses the pre-baked series. (v) Pooling scenarios with very different
  year counts (historic 20 vs ssp370 86) can bias the pooled fit toward the longer regime — weight or
  subsample as needed, and report the mix.
- **Guardrail.** Opt-in per-year boundary series, default OFF; no change to the feature *order* contract, to
  `fit_forest`/`predict`, or to the copula serialization; committed baselines + the AD trainer byte-identical
  until deliberately enabled.

## Relationship to prior ADRs

- **Refines ADR 0020** — the "slow bioclimatic boundary" becomes trailing-transient instead of
  climatological-static, and S is trained as ONE pooled multi-regime model with a hold-out-by-scenario eval.
  Every other ADR 0020 conditioning choice is unchanged. **Supersedes ADR 0020's implicit time-constant
  boundary.**
- **Refines ADR 0023 / 0025** — the transient boundary flows through the *same* runtime-consistent training
  table and the *same* `live_flux_cond` copula conditioning; the feature-order contract is preserved (values
  become year-specific, order does not change).
- **Keeps ADR 0004** — CO₂ held constant; the SSP signal is climate + soil only. Not superseded.
- **Uses ADR 0002/0003** — S still emulates the distribution by advancing the population under the delivered
  `bm_inc` (flux-then-integrate); conservation is untouched.

ADRs are immutable once accepted — supersede rather than edit.
