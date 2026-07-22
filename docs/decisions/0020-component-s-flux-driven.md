---
status: "accepted"
date: 2026-07-22
deciders: "Jamir Priesner (owner) — decision authority delegated to the engineering agent"
consulted: "ADR 0002 (emulate distributions), ADR 0003 (flux-then-integrate carbon), ADR 0005 (DRF baseline + escalation), ADR 0018 (growth-ownership split), ADR 0019 (port inference / wrap machinery); DEVELOPMENT_PLAN §2.2/§2.5/§3/§5; docs/p1_s_in_loop_design.md; src/interface.jl (FToS); /home/jamirp/lpjml56fit/src/tree/mortality_tree_ind.c, waterstress_tree.c, tempstress_tree.c; python/src/lpjmlfit_emulator/baseline.py (DirectEmulator)"
informed: "P1 (put S in the coupled loop); the extended Phase-1 data task; the offline S retrain; the OOD benchmark gate; MEMORY.md; JOURNAL.md"
---

# Component S is flux-driven (flux-then-integrate), not climate-equilibrium

> **Status note.** `accepted` 2026-07-22, under the owner's standing delegation of decision authority to
> the engineering agent ("decide, record each decision in an ADR, and proceed"). This is the **governing
> spec for how S is conditioned and trained** — reversible only by a superseding ADR. It refines ADR 0002/
> 0003/0018 and **overrides one consequence of ADR 0019** (the "P1 ships climate-only trained weights /
> FToS-conditioning gap deferred out of P1 scope" clause); see *Relationship to prior ADRs* below.

## Context and Problem Statement

The inherited offline S is the Python `DirectEmulator` (LightGBM + a hand-rolled Gaussian copula + Poisson/
NB count). It maps **climate + soil directly to the trait/size distribution**, **non-recursively** — a
climate→equilibrium-distribution regression. On the in-distribution panel it meets the P2 gate (KS 0.023 vs
a 0.0049 noise floor), but on the **warm+dry out-of-distribution holdout it misses by ~32× the floor**
(MEMORY.md §Status, phase 2). That failure is not an S-escalation trigger (ADR 0005) — it is the **defining
failure mode of the equilibrium-ML design**: a pure climate→state map has no physical intermediary, so
outside the training climate envelope it extrapolates a mapping that was only ever fit inside it.

The whole point of the phased **hybrid** (ADR 0001) is that the physical core **F/F_diff turns climate into
fluxes** — a conserving, differentiable, physically-constrained transformation that *does* extrapolate — and
**S only maps fluxes + state → demography**. If we wire the climate-only `DirectEmulator` into the coupled
loop as-is, we import the exact OOD failure the hybrid exists to remove, and we double-count: F already
consumed the climate to produce the fluxes, and S would consume the raw climate again.

ADR 0018 fixed *who owns what* (S owns distribution + demography; F_diff owns representative-individual
carbon growth). ADR 0019 fixed *how S runs* (port inference to Julia; wrap the machinery). **Neither fixed
what S is conditioned on, nor what it is trained against** — ADR 0019 explicitly deferred that as a
"documented FToS-conditioning gap" and shipped climate-only trained weights for P1. This ADR closes that
question: S must be **flux-driven**, and the flux-conditioned training/evaluation is a first-class P1
deliverable, not a post-P1 nicety.

## Decision Drivers

- **Kill the equilibrium-ML OOD failure at its root.** The failure comes from re-feeding raw this-year
  climate as a *primary* driver. Remove that path; let F's fluxes carry the climate signal.
- **No double-counting.** A quantity that F already transformed (temperature, precip, radiation, VPD →
  fluxes) must not re-enter S as raw climate. S consumes F's *output*, not F's *input*.
- **Conservation by construction (ADR 0003/0018).** `bm_inc` is simultaneously an S **input feature** and
  the S **conservation budget**: S advances the existing population by softmax-bounded increments summing to
  the delivered `bm_inc` (flux-then-integrate) — it does **not** regenerate a fresh distribution.
- **Extremes and timing, not just means, drive demography.** LPJmL-FIT mortality/establishment respond to
  water-stress accumulation, counts of heat/cold-stress days, and growing-season vs end-of-year soil
  moisture (`mortality_tree_ind.c`, `waterstress_tree.c`, `tempstress_tree.c`). Annual means alone discard
  the signal the C model actually uses.
- **Keep the slow bioclimatic boundary that fluxes do *not* carry.** Establishment and PFT *presence* are
  governed by coldest-month temperature and growing-degree-days and by the 20-yr `Climbuf` memory — these
  are legitimately *not* encoded in this-year fluxes, so they stay as inputs (the one climate channel kept,
  and only because it is slow/boundary, not this-year weather).
- **Train/runtime consistency.** S must be trained on the *same kind of signal* it will be conditioned on at
  runtime — fluxes — and the offline-true-flux vs coupled-F_diff-flux mismatch must be removed by online
  fine-tuning (the P4 rollout), not left as an unquantified bias.
- **Falsifiability.** The change must have a single, pre-registered success test: the flux-driven S must
  close the warm+dry OOD gap the climate-only baseline fails.

## Considered Options

- **Option A — keep climate-equilibrium S (the inherited `DirectEmulator`), wire it in as-is.** Rejected:
  it *is* the OOD failure mode; it double-counts climate; it is non-recursive (ADR-0018-rejected
  "regenerate each year"). Retained only as the **benchmark** (below).
- **Option B — flux-driven, flux-then-integrate S (chosen).** Condition S on F's delivered fluxes + AR
  state + the slow bioclimatic boundary; drop this-year raw climate as a primary driver; advance the
  existing population by conserved increments; train offline on LPJmL-FIT's true fluxes, fine-tune online
  against F_diff's delivered fluxes.
- **Option C — hybrid conditioning (fluxes *and* raw this-year climate).** Rejected: re-admits the
  double-count and the OOD-extrapolation path through the raw-climate features; the flux channel is
  supposed to *be* the climate signal, physically transformed. If a controlled ablation ever shows a
  flux-only S underperforms a flux+climate S *on OOD* (not in-distribution), revisit — but the default is
  flux-only precisely because in-distribution gains from raw climate are the trap.

## Decision Outcome

Chosen: **Option B — S is flux-driven (flux-then-integrate), not climate-equilibrium.**

### 1. S conditioning inputs (annual step) — the contract

**(a) Primary dynamic drivers — annual *statistics* of the daily F outputs (not just means):** because
mortality and establishment respond to extremes, timing, and stress-day counts, S is conditioned on
*distributional summaries* of what F actually delivered over the year:

- delivered NPP increment **`bm_inc`** (per representative individual and PFT; also the conservation budget);
- **water stress** — the annual accumulated tree `water_stress` (definition below) plus within-year
  statistics (peak, timing, count of stress days) built from daily `transp`/`swc`/VPD;
- **temperature / heat stress** — the annual `temp_stress` count of heat/cold-stress days plus its timing;
- **growth efficiency** — `bm_delta / leafarea_real` (definition below), the greff mortality driver;
- **end-of-year and growing-season soil moisture** — from daily `swc`, not the annual mean alone.

**(b) Autoregressive state (S is recursive):** the **previous-year trait×size distribution summary** —
moments and quantiles of height, stem diameter, crown area, wood density, SLA, leaf longevity, and the
carbon pools — plus count `N`. Year *t* is conditioned on year *t−1*'s population, not regenerated from
climate.

**(c) Slow / boundary inputs that F's fluxes do NOT encode:** the **20-yr `Climbuf`** climate memory;
**coldest-month temperature** and **growing-degree-days (gdd5)** (they govern establishment and which PFTs
can be present); **CO₂** (held constant, ADR 0004); **soil texture and depth**; and **stand age /
time-since-disturbance**.

### 2. Explicitly dropped: this-year raw climate as a primary driver

This-year raw **temperature, precipitation, radiation, and VPD are removed** as primary S drivers. F has
already transformed them into the fluxes of (1a); re-feeding them double-counts and re-opens the
equilibrium-mapping OOD failure. **Only the slow bioclimatic memory of (1c) is kept**, and only because it
governs establishment and PFT presence — signals the fluxes genuinely do not carry.

### 3. Conservation — `bm_inc` is both feature and budget (flux-then-integrate)

S allocates **exactly** `bm_inc` across the population as softmax-bounded increments on the **existing**
individuals — it advances the population, it does not regenerate a distribution (ADR 0003/0018). Mortality
moves carbon to litter and soil; establishment draws carbon from `flux_estabc`; fire removes `firec`. The
ecosystem closure `ΔC = NPP − Rh − firec + flux_estabc` holds by construction (ADR 0003,
`carbon_budget_residual`). Under the ADR 0018 split the *differentiable* carbon allocation is F_diff's;
S sets the demographic/distributional envelope those increments are applied within.

### 4. The climate-only `DirectEmulator` is kept ONLY as a benchmark

It is not wired into the coupled loop. The offline evaluation **must** compare the new flux-driven S against
it on the warm+dry OOD holdout. The flux-driven S is *expected to close that gap*. **This comparison is the
falsifiable success test for this change** and must be reported explicitly (see the gate below).

### 5. Train/runtime consistency (teacher forcing → online fine-tune)

- **Offline:** train S on LPJmL-FIT's **TRUE** fluxes (teacher forcing) — the extended Phase-1 data (below)
  supplies `bm_inc` + the four mortality drivers + soil-moisture state aligned to the annual `ind`
  distribution.
- **Online (P4 rollout):** fine-tune S against F_diff's **ACTUAL delivered** fluxes to remove the mismatch
  between LPJmL's true fluxes and F_diff's approximate ones. This is the same TBPTT/online-rollout path
  ADR 0016 / P4 already own; S being flux-driven is what makes that fine-tuning well-posed (train and
  runtime condition on the same channel).

### 6. Data task (extends Phase 1) — F + mortality-driver outputs

From the LPJmL-FIT training runs, write out or reconstruct, **per cell, per year, aligned to the annual
`ind` distribution**, the F variables S needs. Buildable spec of record:
**`docs/slow_flux_conditioning_data_spec.md`**. The four mortality drivers and two accumulated stress states
are **confirmed against the C source** (`[VERIFIED]` against `mortality_tree_ind.c`, `waterstress_tree.c`,
`tempstress_tree.c`):

- **`bm_delta = pft->bm_inc.carbon / pft->nind − turnover_ind`** (per-individual net biomass increment);
  `leafarea_real = tree->ind.leaf.carbon · pft->sla`; **growth efficiency = `bm_delta / leafarea_real`**.
- **`mort_npp` (growth-efficiency mortality)** `= mort_max / (1 + 0.2·exp(k_mort·bm_delta/leafarea_real)) ·
  (1 + bm_inc_counter)`, capped at 1; `mort_max = 10^(wdmort_1 + wdmort_2/(wooddens/1e6))` (wood-density
  dependent); if `leafarea_real ≤ 1e-6` then `mort_npp = 1`. `bm_inc_counter` increments each year
  `bm_delta < 0`, resets on `bm_delta ≥ 0`; `counter ≥ 5` ⇒ immediate death.
- **`mort_age` (background/age mortality)** `= min(1, −log(0.001)·(2+1)/longevity · (age/longevity)^2)`.
- **`mort_water`** `= (mort_water_factor · water_stress / 365) · (1 + bm_inc_counter)`, capped at 1, where
  **`water_stress`** accumulates daily (reset at the coldest day) as `phen · (VPD_kPa) · ((mort_water_res −
  minwscal) − wscal)` only when leaves are unfolded, `soil.temp[0] > 10 °C`, and `wscal` is below threshold.
- **`mort_temp`** `= (mort_temp_factor · temp_stress / 365)`, capped at 1, where **`temp_stress`** is the
  annual **count of stress days** (`+1` each day `temp < temp_stressed.low` or `> temp_stressed.high`,
  reset at the coldest day).

`tree->mort_npp/mort_age/mort_water/mort_temp/mort_prob` and the states `tree->water_stress`/`temp_stress`/
`bm_inc_counter` are already computed per individual and are in the restart image, so the task is to **emit
them in the annual `ind` output** and/or **reconstruct** `water_stress`/`temp_stress` from the daily set
(`transp`, `swc`, `gpp`, `npp` are already in the 186 GB daily data). Confirm each variable's exact
definition against `mortality_tree_ind.c` and the F→S interface contract (`src/interface.jl` `FToS`) before
training.

### Consequences

- **Good:** removes the equilibrium-ML OOD failure at its source; no double-counting of climate; train and
  runtime condition on the same (flux) channel; conservation is unchanged (same flux-then-integrate
  primitives). The FToS-conditioning gap ADR 0019 deferred is now a first-class, gated deliverable.
- **Good:** the F→S interface (`FToS`) already carries `bm_inc`, `water_stress`, `temp_stress`,
  `growth_eff`, `soilmoist` — the *rate channel* Tier-0 `DemographicSlowEmulator` already uses is
  flux-driven; this ADR governs how the **Tier-1 ML weights are trained** (flux-conditioned, not
  climate-only), and requires extending `FToS`/the training table to carry within-year *statistics*
  (extremes, timing, stress-day counts), not just means.
- **Bad/risk:** the extended Phase-1 data must be generated/reconstructed before the flux-conditioned
  retrain — a C-binary run + reconstruction task (spec'd, gated). Until it lands, coupled S runs on the
  Tier-0 physical-rate channel + climate-only Tier-1 weights (honestly labelled), and the OOD benchmark
  cannot yet be reported.
- **Bad/risk:** `FToS` must grow from 5 scalar fields to carry annual *statistics*; this is an interface
  change — must stay **opt-in, default byte-identical** (guardrail 4) behind the existing
  `run_coupled_cell(...; slow=)` path until the flux-conditioned weights exist.
- **Neutral:** ADR 0018's ownership split and ADR 0019's port/wrap decisions are untouched; only the
  conditioning/training contract and ADR 0019's "climate-only in P1" clause change.

## Relationship to prior ADRs

- **Refines ADR 0002/0003** — S emulates the distribution by *advancing* the population under the delivered
  `bm_inc` (flux-then-integrate), which 0003 already required; 0020 makes the *conditioning* match (fluxes,
  not climate).
- **Consistent with ADR 0018** — S owns demography/distribution conditioned on delivered `bm_inc` + the
  mortality drivers; F_diff owns the differentiable carbon growth. 0020 specifies the *feature set* S is
  conditioned on; it does not move the ownership boundary.
- **Consistent with ADR 0019's core decisions** — port inference to Julia; wrap the machinery (reuse
  ResidualRegressor + copula + count model) in a recursive demography-only adapter. **Overrides ADR 0019's
  consequence** that "P1 ships climate-only trained weights (FToS-conditioned retrain out of P1 scope)": the
  flux-conditioned training and the OOD benchmark are now the P1 success test. Open-risk #2 of
  `docs/p1_s_in_loop_design.md` is closed by this ADR (updated there).
- **Uses ADR 0004** — CO₂ held constant; it stays an input only as a fixed slow driver.
- **Uses ADR 0005** — the climate-only `DirectEmulator` remains the benchmark; escalation of S's method is
  unaffected (the OOD failure was never an escalation trigger).

## More Information

- **Falsifiable success test (S gate):** on the warm+dry OOD holdout, the flux-driven S's distributional
  panel error (per-axis KS / quantile-RMSE on the S-owned axes) must be **materially below** the climate-only
  `DirectEmulator`'s ~32×-floor miss, at matched in-distribution error. Report both side by side; the
  flux-driven S closing the gap is the pass condition. If it does not close the gap, this decision is
  falsified and must be revisited (Option C ablation, or a diagnosis of which flux statistic is missing).
- **Data spec:** `docs/slow_flux_conditioning_data_spec.md` (extended Phase-1 outputs, C-source definitions,
  reconstruction, alignment).
- **Plan:** DEVELOPMENT_PLAN §2.2 (S inputs), §2.5 (F→S row), §3 (data generation), §5 (OOD benchmark),
  §6 (P1/P2 gates).
- ADRs are immutable once accepted — supersede rather than edit.
</content>
</invoke>
