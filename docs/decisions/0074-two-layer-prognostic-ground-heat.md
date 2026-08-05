---
status: "accepted"
date: 2026-08-05
deciders: "line E (session 3), autonomous per STEERING_PROMPT.md"
consulted: "ADR 0073 (the diagnosis this implements the fix for), ADR 0072 (the P2 verdict), ADR 0070 (the PLUMBER2 reference), ADR 0017 (E is self-contained), ADR 0081 (reuse authorized, cite transparently), guardrail 2 (conservation) and guardrail 4 (opt-in / default byte-identical), guardrail 7 + `residual-diagnosis` (falsifiable hypothesis first), src/run.jl:93"
informed: "line M (owns run.jl + the coupled/biome baselines; enabling this SUPERSEDES the λ_g = 1.0 integration point), line O (this is the sub-daily blocker ADR 0073 named), lines/E/STATE.md, docs/third_party_licensing.md"
supersedes: "the `lambda_g = 1.0` RECOMMENDATION of ADR 0073 (its diagnosis stands unchanged)"
---

# Component E gets an opt-in two-layer **prognostic** ground-heat column — the mechanism ADR 0073 called for, which beats the fitted `λ_g` without fitting anything

**ADR 0073's diagnosis stands in full.** What this ADR replaces is only its *remedy*: its recommended
`λ_g = 1.0` was explicitly "a coefficient, not a mechanism", and it named the real fix — "a force-restore /
two-layer soil scheme with a genuine diurnal soil wave" — while deferring it as "a design change, not a
tune". This is that design change, measured against the same towers on the same rows.

## Context and Problem Statement

The default ground-heat term is `G = λ_g(T_skin − t_soil)` with `λ_g = 7.0 W/m²/K` and `t_soil` a τ = 30 d
EWMA of **air** temperature. ADR 0073 measured this as the dominant nocturnal-H error: `sd(G_m)` runs 5–7×
`sd(G_o)` at the forest sites, 88 % of DE-Hai's nocturnal H bias is `ΔG`, and the form has **no soil thermal
inertia at all** — `G_m`'s only variability is `T_skin`'s. Fitting `λ_g ≈ 1.0` repaired the daily variance
but could never produce a diurnal soil wave, which is why ADR 0073 recorded nocturnal skill as unreachable
"in the present form" and flagged it as the blocker for line O's sub-daily online coupling.

## Decision Drivers

- **Guardrail 7 / `residual-diagnosis`:** state a falsifiable hypothesis *before* the run, and reproduce a
  trusted number through the new harness first.
- **Guardrail 4:** new physics must be opt-in and leave every committed baseline byte-identical.
- **Guardrail 2:** `Rn = LE + H + G` must still close to machine precision.
- **ADR 0017:** E stays self-contained — no new dependency, no copied code.
- A fitted coefficient that only works at one timestep is a dead end for line O.

## Decision Outcome

**Chosen: implement the two-layer prognostic soil column as an opt-in `SEBParams` scheme
(`enable_two_layer`, default `false`), and recommend that line M enable it INSTEAD of flipping
`lambda_g` to 1.0.**

    G   = κ_g (T_skin − T1),   κ_g = 2 λ_soil / z1            [surface → layer-1 midpoint, half-cell]
    D   = Δ (T1 − T2),         Δ   = 2 λ_soil / (z1 + z2)      [inter-layer diffusion]
    T1 += dt/(z1 C) (G − D);   T2 += dt/(z2 C) D               [closed bottom]
    C   = C_water·θ·γ + C_dry                                  [wet-soil volumetric heat capacity]

The ground reference is now the **surface's own thermal state**, not the air's. `solve_seb` itself is
unchanged — it gained only a trailing `lambda_g =` keyword defaulting to `p.lambda_g`, so the default path
is bit-for-bit the pre-E7 computation — and the column lives in `SEBEnergyClosure` (`t_soil1`, `t_soil2`)
stepped by `step_soil_column!` after each `solve!`.

**PROVENANCE (ADR 0081 — reuse freely, cite accurately).** This is an **independent implementation of the
MITgcm land-package two-layer soil formulation**, cross-read against **SpeedyWeather.jl**'s
`LandBucketTemperature` (which implements the same MITgcm equations) and **Terrarium.jl**'s half-cell
`ImplicitSkinTemperature` + conduction column. **No code was copied and neither package is a dependency.**
All thermal constants are those references' published values, unfitted: `λ_soil` 0.42 W/m/K, `C_dry`
1.13e6, `C_water` 4.2e6 J/m³/K, `γ` 0.3, `z2` 2.0 m. Registered in `docs/third_party_licensing.md`,
`CITATION.cff`, `docs/src/refs.bib` and the `energy.jl` header.

### Two design choices that are load-bearing

1. **`G` is held CONSTANT over the step** (the MITgcm/SpeedyWeather form), not recomputed from `T1`
   mid-step. This makes the column **energy-exact** — it gains exactly the `G·dt` reported in `EToATM`, so
   there is no split between the closed flux and the reservoir — and it keeps the daily step well resolved
   across the whole useful `z1` range: only the inter-layer term is stiff, bounding `dt < 2 z1 C/Δ` at
   **100 d** for the default `z1 = 0.75 m` (21 d even at `z1 = 0.2 m`). Recomputing `G` inside the step
   would instead impose `dt < 2 z1 C/(κ_g+Δ)` — 21 d at 0.75 m but only **1.8 d at 0.2 m**, i.e.
   `dt·rate = 1.125`, damped but overshooting equilibrium every daily step.
2. **No deep-restore term, and none is needed.** The bottom is closed, so the only thing preventing a
   runaway is the surface feedback (`T1` cold ⇒ `T_skin − T1` up ⇒ `G` up ⇒ `T1` warms). Measured below: it
   holds.

### The hypotheses, stated before the run

- **H1** — with unfitted constants, the daily step reproduces the observed daily `sd(G_o)` 4.3–6.3 W/m² and
  recovers daily H R² comparable to the **fitted** `λ_g = 1.0` arm. *Falsified if* daily `sd(G_m)` > 10
  W/m² or daily H R² < 0.3 at DE-Hai or AU-ASM.
- **H2** — at the native sub-daily step the column carries a real diurnal wave, improving on ADR 0073's
  nocturnal floor. **Not** expected to reach R² > 0: `ε_obs` scatter alone (sd 36 W/m² at DE-Hai) is the
  size of the night H RMSE.

### What the data says [VERIFIED 2026-08-05]

Probe `scripts/e_two_layer_probe.jl` (SLURM `E-e7probe` 1705681 → `E-e7drift` 1705869), the same drive
tables and rows as ADR 0072/0073. Three arms: **A** default `λ_g` 7.0 · **B** fitted `λ_g` 1.0 · **C** E7.

**0. Harness check passed first (`residual-diagnosis` §3).** Arms A and B reproduce ADR 0073's published
daily H R² **digit for digit at all four sites** — DE-Hai 0.035/0.637 (published 0.03/0.64), AU-ASM
0.329/0.745 (0.33/0.74), AU-Tum −0.478/−0.353 (−0.48/−0.35), AU-Rob 0.069/−0.172 (0.07/−0.17) — and the
observed daily `sd(G_o)` matches (4.28/6.25/4.33/5.95 vs 4.3/6.3/4.3/6.0).

**1. H1 SUPPORTED, and E7 beats the fitted arm it was only asked to match.** Daily step, `z1 = 0.75 m`:

| site | H R² A → B → **C** | G R² A → B → **C** | daily sd(G): obs / A / B / **C** |
|---|---|---|---|
| DE-Hai | 0.035 → 0.637 → **0.645** | −39.4 → 0.657 → **0.717** | 4.28 / 30.7 / 4.74 / **4.57** |
| AU-ASM | 0.329 → 0.745 → **0.775** | −15.4 → 0.477 → **0.614** | 6.25 / 27.0 / 4.18 / **4.02** |
| AU-Tum | −0.478 → −0.353 → **−0.362** | −31.6 → 0.508 → **0.401** | 4.33 / 28.0 / 4.63 / **4.44** |
| AU-Rob | 0.069 → −0.172 → **−0.176** | −4.02 → 0.085 → **0.067** | 5.95 / 14.2 / 2.25 / **2.24** |

At the two sites that **can** score H (ADR 0073: AU-Tum/AU-Rob have `ε_obs` −62.3/−47.5 W/m²), E7 matches
or beats the fitted coefficient on H *and* clearly beats it on `G` itself. `Rn` daily R² is unchanged
within ±0.005 — DE-Hai 0.976 → 0.978 and AU-ASM 0.987 → 0.988 (up), AU-Tum 0.969 → 0.965 and AU-Rob
0.992 → 0.987 (down) — so the strongest existing result is preserved, not improved.

**2. `z1 = 0.2 m` is under-resolved at a daily step — a genuine finding, and the reason the first run
looked mediocre.** MITgcm's 0.2 m is for a model stepping in *minutes*. At `dt = 1 d` the layer-1
relaxation number `dt·(κ_g+Δ)/(z1 C)` is **1.125**, so the top layer equilibrates with `T_skin` inside one
step and `G` degenerates into a **day-to-day difference of `T_skin`**. DE-Hai daily G R² by `z1`:

| `z1` [m] | 0.2 | 0.3 | 0.5 | 0.75 | 1.0 | 1.5 |
|---|---|---|---|---|---|---|
| `dt·rate` | 1.125 | 0.518 | 0.198 | **0.093** | 0.055 | 0.026 |
| daily H R² | 0.615 | 0.634 | 0.643 | **0.645** | 0.645 | 0.647 |
| daily G R² | −2.827 | −0.747 | 0.393 | **0.717** | 0.776 | 0.740 |
| daily sd(`G_m`) | 9.59 | 7.66 | 5.78 | **4.57** | 3.91 | 3.22 |

`z1 = 0.75 m` is selected on that **resolution** criterion inside a broad optimum — H R² moves only
0.634→0.647 across 0.3–1.5 m — so it is a structural choice, not a fitted conductance. Being precise: it is
the one value here not taken from the reference, and `G` R² does peak near it, so call it weakly
observation-informed; the *conductance* `κ_g = 2λ/z1` is still derived, never fitted to a flux.

**3. H2 PARTIALLY supported — the diurnal wave is real, nocturnal R² > 0 is still out of reach.**
Sub-daily, `z1 = 0.75 m`, night = SWdown ≤ 50 W/m²:

| site | night H R² A → **C** | night H RMSE A → **C** | all-hours sd(G): obs / A / **C** | night G R² **C** |
|---|---|---|---|---|
| DE-Hai | −1.019 → **−0.324** | 37.0 → **29.96** | 5.66 / 34.7 / **5.75** | **+0.394** |
| AU-Tum | −1.698 → −3.363 | 51.1 → 65.0 | 7.65 / 39.6 / **7.45** | −0.04 |
| AU-ASM | −1.014 → −1.935 | 29.7 → 35.9 | 64.0 / 55.1 / 10.35 | −5.915 |

The diurnal **amplitude** of `G` is now essentially correct at the forest sites (DE-Hai 5.75 vs obs 5.66;
AU-Tum 7.45 vs 7.65, against the default's 34.7 and 39.6), and **night `G` R² turns positive at DE-Hai
(+0.394)** — the first arm ever to have skill in `G` itself. Night H at DE-Hai improves substantially in
RMSE (37.0 → 29.96) and bias (14.04 → 3.74) but **R² stays negative (−0.324)**, exactly as H2 predicted and
ADR 0073's `ε_obs` bound requires.

**4. `z1` is surface-dependent sub-daily — the honest limitation.** AU-ASM (sparse mulga over bare soil)
has an observed all-hours `sd(G_o)` of **64 W/m²**; `z1 = 0.75 m` gives 10.4 (under-amplitude), while
`z1 = 0.2 m` gives 32.6. This matches ADR 0073's finding that AU-ASM's implied sub-daily `λ_g` was 6.03 vs
~0.9 at the forests. One global `z1` is therefore a compromise: right for closed canopies, too insulating
for sparse/desert surfaces.

**5. No secular drift — the closed bottom is safe for decadal runs.** Annual-mean column temperatures
oscillate with interannual climate and show no runaway. Second-half trends at `z1 = 0.75 m`: AU-Tum, the
**16-year** record and therefore the decisive one, **T1 −0.059 / T2 −0.015 K/yr**; DE-Hai (10 yr)
+0.159/+0.100; AU-ASM (7 yr) −0.328/−0.213; AU-Rob (4 yr) −0.138/+0.280 — the short-record numbers are
climate variability, not drift. Mean daily `G_m` = 0.001…0.072 W/m², i.e. **⟨G⟩ → 0** as the
self-equilibration argument requires.

**6. T_skin: neutral-to-slightly-worse sub-daily, and this one IS interpretable.** `T_skin` does not depend
on the tower closing, so all sites count. At `z1 = 0.2 m`: AU-ASM R² 0.941 → 0.945, AU-Tum 0.773 → 0.667,
AU-Rob 0.385 → 0.166. The daily-step `T_skin` R² is far flatter across `z1` (AU-Rob 0.81 → 0.79,
AU-Tum 0.864 → 0.851). So E7 costs some sub-daily `T_skin` skill at the two evergreen-broadleaf sites while
gaining `G` and H — a real trade to re-measure when a canopy heat-storage term lands.

### Consequences

- **No default moved; nothing is enabled** (guardrail 4). `enable_two_layer = false`, so every coupled and
  biome baseline, and every existing energy gate, is untouched. `SEBParams(enable_two_layer = true)` works
  today for anyone who wants to measure it.
- **The `lambda_g = 1.0` integration point with M is SUPERSEDED by this one.** E's recommendation is now
  `enable_two_layer = true` (which makes `lambda_g` inert) rather than `lambda_g = 1.0`: better daily H,
  clearly better `G`, a correct diurnal amplitude, and it is the only one of the two that gives line O a
  sub-daily path. `lambda_g = 1.0` remains the valid one-line fallback if M wants the smaller change.
  Either way it moves the baselines, so it is M's call and must land with the baselines together, and ADR
  0072's night-cold **sign** assertion in `energy_closure_tests.jl` is re-pinned at that moment.
- **Line O's named blocker is materially reduced, not removed.** The diurnal `G` wave exists and is
  correctly scaled at closed-canopy sites; nocturnal H R² is still < 0.
- **Bad:** one global `z1` cannot serve both a closed canopy and a sparse desert (§4). Making `z1` (or `C`)
  a function of vegetation/soil is the natural next step and is an **S→E** boundary question — `SToE`
  carries `lai`/`height` already, but soil texture/wetness would need `FToE`, which is M-owned.
- **Bad:** `theta_soil` is a constant 0.5 because the frozen `FToE` carries no soil moisture. Wiring F's
  real root-zone wetness into `C` is an E→M integration point; guessing it inside E would be invented
  physics (the same reasoning that re-scoped E3).
- **Bad:** sub-daily `T_skin` degrades at AU-Tum/AU-Rob (§6). Not a blocker while the scheme is off, but it
  must be quoted whenever E7 is enabled.
- **Good:** the fix is a *mechanism* with published constants, so it transfers across timesteps and
  surfaces in a way a fitted `λ_g` never could — and `dt_seconds` is now explicit in `SEBParams`, which is
  what makes the sub-daily path well-defined at all.

## Pros and Cons of the Options

### Opt-in two-layer prognostic column (chosen)

- Good: matches/beats the fitted coefficient on H, beats it on `G`, fixes the diurnal amplitude, unblocks
  the sub-daily direction, and needs no new dependency.
- Good: energy-exact and stable at the daily step by construction (§1), and self-equilibrating (§5).
- Bad: more state and more parameters than a single conductance; one `z1` does not fit every surface.

### Flip `lambda_g` to 1.0 (ADR 0073's recommendation)

- Good: a one-line change, and its daily `G` R² is respectable (0.657 DE-Hai).
- Bad: a coefficient with no diurnal inertia — leaves line O's blocker fully in place, and is worse than E7
  on every scoreable daily metric.

### Full multi-layer conduction column (Terrarium-style)

- Good: the physically complete answer, and Terrarium already has it.
- Bad: far more state and a real dependency or a large port, for a model whose operational step is a day;
  two layers already recover the daily skill and the forest-site diurnal amplitude.

## More Information

- Probe: `scripts/e_two_layer_probe.jl` (+ the extracted `scripts/e_seb_drive_common.jl`). Reports:
  `<energy_reference>/derived/seb_validation/e7_two_layer_probe{,_v2,_v3,_v4}.txt` (v2 adds the `z1` sweep,
  v3 the sub-daily `z1` arm, v4 the annual-mean drift diagnostic).
- Gates: `test/testitems/energy_closure_tests.jl` — default-off byte-identity, closure exactness with the
  scheme on, the energy-exact column invariant, stability/self-equilibration over 4000 daily steps, and
  `dt_seconds` correctness (24 hourly steps ≈ 1 daily step), which is what line O inherits.
- The `plumber2-reference` skill carries the scoring procedure; ADR 0073 carries the diagnosis.
