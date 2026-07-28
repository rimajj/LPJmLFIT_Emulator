---
status: "accepted"
date: 2026-07-28
deciders: "line E (session 2), autonomous per STEERING_PROMPT.md"
consulted: "ADR 0072 (the P2 verdict this supersedes), ADR 0070 (the PLUMBER2 reference), ADR 0017 (the self-contained SEB), guardrail 4 (opt-in / default byte-identical) and guardrail 7 + the `residual-diagnosis` skill (state the reference basis and a falsifiable hypothesis first), src/run.jl:93 (`couple_day!` calls `solve!` ONCE PER DAY)"
informed: "line M (owns `run.jl` and the coupled/biome baselines; `lambda_g` is now a live integration point), line O (the online SpeedyWeather coupling is the sub-daily use case this ADR bounds), lines/E/STATE.md, MEMORY.md, the `plumber2-reference` skill"
---

# Component E's nocturnal-H failure is a ground-heat **timescale** error, not an aerodynamic one — and `λ_g = 7.0` is ~7× too large for the daily step the model actually runs at

**Supersedes [ADR 0072](0072-e4-p2-observational-verdict.md) items 4 and 6.** Its measured verdict (items 1,
2, 3, 5, 7 — Rn VERIFIED, T_skin VERIFIED where observable, H verified in the mean only, half-hourly R²
inflated by the diurnal cycle, AU-Rob suspect) **stands unchanged**; ADR 0072 itself asked to be superseded
"when the nocturnal diagnosis lands". This is that diagnosis, and it **refutes** the cause 0072 proposed.

## Context and Problem Statement

ADR 0072 found nocturnal `H` wrong at every one of four PLUMBER2 sites (R² −1.0…−5.6) and named the failure
"the closure runs too COLD at night … too little nocturnal turbulent + ground coupling" (item 4). Item 6
inferred from a monotone `stab_amp` sweep that the **bounded-tanh stability form** was the limitation and
recommended a stability-form change before any retune. The line-E handoff ranked the candidates
accordingly: (1) the stability form / `g_a`, (2) the ground-heat term, (3) emissivity.

That ranking was never tested. This ADR tests it.

## Decision Drivers

- **`H` is not predicted — it is the exact residual** `H_m = Rn_m − LE − G_m` (LE prescribed from the tower
  in Experiment A). Anything said about "what H is sensitive to" must respect that.
- **Guardrail 7 / `residual-diagnosis`:** state the reference basis and a falsifiable hypothesis, and
  reproduce a trusted number through the new harness, before interpreting any residual.
- **Guardrail 4:** no default may move as a side effect of a diagnosis.

## Decision Outcome

**Chosen: attribute the nocturnal-H failure by exact algebraic decomposition rather than by parameter
sweep, and accept its verdict — the dominant model-side term is the ground-heat flux `G`, whose default
conductance `λ_g = 7.0 W/m²/K` is a *diurnal-amplitude* value applied to a *daily-mean* gradient.**

Because the model closes exactly, and writing the tower's own non-closure as
`ε_obs ≡ Rn_o − LE − H_o − G_o`, the H error obeys **identically** (algebra, not a hypothesis):

    ΔH  =  ΔRn  −  ΔG  +  ε_obs   =   ΔRn  −  (G_m − G_res),   G_res ≡ Rn_o − LE − H_o

**`g_a` appears in none of these terms.** It can act only indirectly, by moving the solved `T_skin` and
hence `Rn_m` and `G_m`. That is why a `stab_amp` sweep looked informative and was not.

Probe: `scripts/e_nocturnal_h_decomp.jl` (SLURM `E-e6decomp` 1622483 → `E-e6decomp4` 1622494), the same
497 936 tower steps and the same drive tables as ADR 0072. Harness check passed first: model self-closure
`max|H_m − (Rn_m − LE − G_m)| = 0.0` exactly, the identity closes to `≤ 2.3e-13 W/m²`, and the night-H
numbers reproduce ADR 0072's per-site values digit for digit.

### What the data says [VERIFIED 2026-07-28]

**1. The stability / `g_a` hypothesis is REFUTED — three independent ways.**

| site | modelled night `g_a` | measured-`u*` night `g_a` | ratio | night H RMSE default → with measured `g_a` |
|---|---|---|---|---|
| DE-Hai | 0.05724 | 0.05685 | **0.993** | 37.0 → **38.2** |
| AU-ASM | 0.01914 | 0.01564 | 0.817 | 29.7 → **30.8** |
| AU-Tum | 0.02365 | 0.04029 | 1.704 | 51.1 → **65.5** |
| AU-Rob | 0.04464 | 0.02222 | 0.498 | 75.5 → **80.2** |

- The closure's nocturnal `g_a` is **within 0.7 % of the tower's measured value at DE-Hai** and within a
  factor 2 everywhere. The bounded-tanh surrogate at `stab_amp = 0.75` is not the problem.
- Substituting the observation-derived `g_a = 1/(U/u*² + ln(z0m/z0h)/(k·u*))` — which embeds the *real*
  stability — makes nocturnal H **worse at all four sites**. (It *improves* night `T_skin` at AU-Tum,
  RMSE 3.32 → 2.47 K, R² 0.64 → 0.80, and at AU-Rob — it is the better `g_a`; H still degrades, because H
  is the residual.)
- Bracketing `g_a` over a **100-fold** range (×0.1…×10, applied exactly through the real solver by scaling
  wind with stability off) **cannot produce a positive nocturnal R² at any site**. The best achievable is
  −0.06 (AU-ASM), −0.35 (AU-Tum), −0.46 (DE-Hai), −2.14 (AU-Rob). `g_a` can move the nocturnal *bias*; it
  cannot create nocturnal *skill*.

ADR 0072's monotone `stab_amp` sweep was a **bias-cancellation artifact**: suppressing `g_a` warms/cools
the skin in the direction that happens to offset the ground-heat error, which reduces RMSE without fixing
anything. Item 6's recommendation ("raise `stab_amp`, the form is the limitation") is withdrawn.

**2. The ground-heat term is the model-side mechanism.** `G = λ_g(T_skin − t_soil)` with `λ_g = 7.0` and a
τ = 30 d EWMA reference has no diurnal soil thermal inertia and no canopy decoupling, so `G_m`'s only
variability is `T_skin`'s:

| site | sd(`G_m`) sub-daily | sd(`G_o`) | sd(`G_m`) **daily** | sd(`G_o`) **daily** | G night R² |
|---|---|---|---|---|---|
| DE-Hai | 34.7 | **5.7** | 30.7 | **4.3** | −41.9 |
| AU-Tum | 39.6 | **7.7** | 28.0 | **4.3** | −51.1 |
| AU-Rob | 33.9 | 19.1 | 14.2 | 6.0 | −5.4 |
| AU-ASM | 55.1 | 64.0 | 27.0 | 6.3 | −3.4 |

The modelled ground heat flux swings **5–7× too hard at the closed-canopy forest sites**, and 4–6× too hard
at *every* site once aggregated to the daily step. At DE-Hai — the one site whose tower closes at night
(`ε_obs = −0.32 W/m²`) — **88 % of the +14.04 W/m² nocturnal H bias is `ΔG` (−12.41)**, with `ΔRn` +1.95.

**3. `λ_g = 7.0` is right for a sparse surface sub-daily and ~7× too large for the daily step.**
Least-squares `λ_g` implied by the observations, fitted on `(T_skin_m − t_soil)`:

| site | vs measured `G_o`, sub-daily | vs budget `G_res`, sub-daily | vs `G_o`, **DAILY STEP** |
|---|---|---|---|
| AU-ASM (sparse, 6.5 m canopy) | 6.03 | 5.99 | **1.03** |
| DE-Hai (DBF, 33 m) | 0.94 | 1.27 | **0.83** |
| AU-Tum (EBF, 40 m) | 0.90 | 9.67 | **0.86** |
| AU-Rob (EBF, 44 m) | 1.46 | 19.92 | **1.10** |

The two target populations **agree only where the tower closes** (DE-Hai `ε_obs` −0.32, AU-ASM −12.0) and
diverge by an order of magnitude where it does not (AU-Tum −62.3, AU-Rob −47.5) — the `residual-diagnosis`
§3b signal, here used to decide *which sites can constrain `λ_g` at all*. **DE-Hai and AU-ASM can; AU-Tum
and AU-Rob cannot.** At the daily step all four collapse to **0.83–1.10 W/m²/K**, and `λ_g ≈ 1.0`
independently reproduces the observed daily sd(`G_o`) of 4.3–6.3 W/m² (sd(`G_m`) = 4.2–4.7). Three
independent lines, one number.

**4. `couple_day!` calls `solve!` once per day (`src/run.jl:93`) — so this is the operational number.**
Solving the closure on daily-mean forcing, as the coupled model actually does:

| site | daily H @ `λ_g`=7 (default) | daily H @ `λ_g`=1 | daily H @ `λ_g`=0.5 |
|---|---|---|---|
| DE-Hai | 38.1 RMSE, R² **0.03** | 23.4, R² **0.64** | 22.8, R² **0.65** |
| AU-ASM | 31.8, R² 0.33 | 19.6, R² **0.74** | 19.5, R² **0.75** |
| AU-Tum | 49.2, R² −0.48 | 47.1, R² −0.35 | 47.3, R² −0.37 |
| AU-Rob | 38.6, R² 0.07 | 43.3, R² −0.17 | 43.9, R² −0.20 |

A **broad** optimum (0.5 and 1.0 score alike ⇒ not a knife-edge fit), improving 3 of 4 sites and degrading
only AU-Rob — already ruled a suspect site by ADR 0072 item 7, and the site whose two `λ_g` targets
disagree 1.46 vs 19.92.

**5. A large part of the remaining nocturnal residual is UNCLOSABLE.** `ε_obs` is the tower's own failure
to close, and a model that closes exactly must differ from `H_o` by exactly that amount. Night means:
DE-Hai **−0.32** (closes — the trustworthy site), AU-ASM −12.0, AU-Rob −47.5, AU-Tum **−62.3** W/m². At the
daily step `ε_obs` accounts for essentially the *entire* mean H bias at three sites (AU-Tum −37.95 of
−33.95; AU-Rob −19.18 of −17.93; AU-ASM −12.62 of −23.44), while DE-Hai's daily H bias is **+0.87 W/m²**.
Even with a perfect `λ_g`, nocturnal R² stays < 0 everywhere: `ε_obs` scatter alone (sd 36 W/m² at DE-Hai)
is the same order as the night H RMSE.

### Consequences

- **No default changed, no physics changed** (guardrail 4). `lambda_g` is already a `SEBParams` field, so
  the improvement is **available today** as `SEBEnergyClosure(params = SEBParams(lambda_g = 1.0))` with
  zero code change — which is exactly why this ADR does not need to touch `src/components/energy.jl`.
- **`lambda_g` is now the live E→M integration point, and `stab_amp` is withdrawn as one.** Flipping
  `lambda_g` 7.0 → 1.0 moves every coupled and 5-biome baseline (it is the ground-heat term), so it is M's
  call and must land with the baselines together. E's recommendation, with the evidence above: **1.0**.
- **ADR 0072's night-cold-bias sign assertion in `test/testitems/energy_closure_tests.jl` still passes**,
  because no default moved. It should be re-pinned only when M flips `lambda_g`.
- **Good:** the failure is now attributed to a *form* and a *timescale*, not to a coefficient — and the two
  things a future session would otherwise have burned sessions on (retuning `stab_amp`, forcing `g_a` from
  `u*`) are both **measured and refuted**, not merely deprioritized.
- **Bad:** nocturnal *skill* (R² > 0) is not recoverable by any parameter value in the present form. Real
  sub-daily fidelity needs a force-restore / two-layer soil scheme with a genuine diurnal soil wave, plus a
  canopy heat-storage term — a design change, not a tune. **This bounds line O**: the online SpeedyWeather
  coupling is the sub-daily use case, and it inherits an R² < 0 nocturnal H until that lands.
- **Bad:** AU-Tum and AU-Rob cannot honestly score a closing model's nocturnal H at all (`ε_obs` −62 / −47
  W/m²). Quote DE-Hai (and AU-ASM) for H; AU-Tum/AU-Rob remain valid for `T_skin`, which does not depend on
  the tower closing.
- **Neutral:** the `Rn` night-only skill, never reported before, is materially worse than the headline
  all-hours number (R² 0.42–0.83 at night vs 0.97–0.996 by day; bias +1.95…+11.9). Second-order against
  `ΔG`, but it is not zero and it is now on the record.

## Pros and Cons of the Options

### Exact algebraic decomposition (chosen)

- Good, because it is *complete*: the H error has exactly three possible sources and all three are measured,
  so no mechanism can hide.
- Good, because it is falsifiable and cheap — the drive tables already carried `g_obs`/`rn_obs`; the whole
  diagnosis needed one new column (`ustar`) and no new observations.
- Bad, because it depends on the tower's `Qg` and `Rn`, which is why `ε_obs` had to be carried as a term in
  its own right rather than assumed zero.

### Continue the `stab_amp` / stability-form sweep (ADR 0072 item 6's recommendation)

- Good, because the sweep was already built and monotone.
- Bad, because it optimizes a bias cancellation. Measured here: the modelled `g_a` is already within 0.7 %
  of the measurement at DE-Hai, and no `g_a` in a 100× bracket yields positive nocturnal R².

### Force-restore / two-layer soil heat scheme now

- Good, because it is the physically correct fix and the only route to sub-daily nocturnal skill.
- Bad, because it is a design change to a frozen E→M contract, and it is not needed for the **daily** step
  the coupled model runs at, where `λ_g ≈ 1.0` already recovers R² 0.64–0.75. Sequence it with line O's
  sub-daily need.

## More Information

- Report: `<energy_reference>/derived/seb_validation/e6_nocturnal_h_decomp.txt` (per site: the harness
  check, the decomposition, G vs both target populations, night-only Rn, the 100× `g_a` bracket, the
  measured-`u*` substitution, the native daily step, the implied `λ_g`, and the `λ_g` sensitivity).
- Probe: `scripts/e_nocturnal_h_decomp.jl`. Drive tables: `scripts/build_e_seb_validation_table.py`
  (now also emits `ustar`; row counts unchanged, so ADR 0072's basis is untouched).
- Procedure captured in the `plumber2-reference` skill (§"Diagnosing a residual in H").
