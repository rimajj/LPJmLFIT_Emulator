# Phase 3 spike — the differentiable fast core (`F_diff`), one-cell de-risking

**Status: FEASIBLE — gate met.** Enzyme reverse-mode **and** ForwardDiff both differentiate the full
365-day `F_diff` daily-biophysics rollout end-to-end, matching finite differences to ~1e-11 relative
error, with no NaN/Inf gradients. This retires the central risk of the differentiable-fast-core
decision (ADR 0014): reverse-mode AD through the *entire physics* — including the λ (ci:ca) solve and
the autoregressive soil-water coupling — works, which the reference repos do **not** demonstrate
(they detach the physics and only adjoint the λ residual / backprop the NN closures).

This report is the deliverable of the spike step 8: what was built, the headline result, the
non-smoothness issues actually hit, fidelity vs the LPJmL-FIT C oracle, and an effort estimate to
cover all of F. See ADR [0014](decisions/0014-differentiable-fast-core-first.md) (decision) and
[0015](decisions/0015-reuse-map.md) (reuse map + citations).

---

## 1. What was built

| Piece | File | Role |
|---|---|---|
| Shared allometry / diagnostics | `src/allometry.jl` | pure, differentiable tree geometry (pipe-model height, Jucker 2022 crown/stem, LAI, Beer–Lambert FPC). Neither "F physics" nor "S ML" — used by the S→F/S→E interface AND S. |
| Smooth-surrogate library | `src/fdiff_smoothops.jl` | C∞ replacements for the non-differentiable ops (softplus, smoothmin/max, smooth-clamp, sqrt-floor), each with a stated deviation bound. |
| Differentiable fast core | `src/fdiff.jl` | daily continuous biophysics with the SAME equations: C3/C4 Haxeltine & Prentice photosynthesis, the λ supply/demand solve, Priestley–Taylor PET/ET, soil-water bucket + degree-day snow, Lloyd–Taylor maintenance + growth respiration; a pure `daily_step` and a 365-day `rollout`. |
| Gates | `test/testitems/{allometry,smoothops,fdiff_physics,gradient_correctness,numerical_regression}_tests.jl` | unit values/limits/monotonicity; surrogate deviation bounds; water closure + boundedness + limiting cases + determinism + Float32; **AD-vs-FD gradient battery**; regression baseline. |

**Scope (deliberately narrow, per the spike brief):** one cell, one representative tree individual;
the continuous prognostic state is soil water + snow; canopy STRUCTURE (LAI, FPC, height) is a fixed
S→F boundary condition (S owns the discrete demography — ADR 0014). The runtime `src/` is
**dependency-free** (pure Base Julia); AD is a test/train-time tool, so Enzyme/ForwardDiff/
FiniteDifferences live in `test/Project.toml`.

Physical plausibility of the fixed regression scenario (temperate forest, seasonal forcing):
annual NPP ≈ 869, GPP ≈ 2960 gC/m²/yr (NPP/GPP ≈ 0.29), ET ≈ 685 mm/yr vs precip 848 — all sensible.
Per-day water closure `precip = ET + runoff + Δ(soil+snow)` holds to ~1e-12 mm by construction.

## 2. Headline result — gradient correctness through the rollout

`d(annual NPP)/dx` for four different differentiated variables, AD vs central finite differences
(`central_fdm(5,1)`), through the daily rollout including the λ Newton solve:

| variable `x` | ∂NPP/∂x (FiniteDiff) | ForwardDiff relerr | Enzyme reverse relerr |
|---|---|---|---|
| CO₂ (forcing) | 3.2222 | 4.2e-11 | 4.2e-11 |
| emax (water param) | 42.846 | 1.8e-12 | — |
| α_c3 (photosynthesis param) | 15006 | 1.7e-12 | — |
| initial soil water w₀ (dry scenario, state coupling) | non-zero | matches | matches |

Both AD modes agree with finite differences to round-off. The dry-scenario `w₀` gradient is
genuinely non-zero — the **autoregressive soil-water state coupling is really differentiated**, not
just the within-day physics. (In a wet scenario the soil saturates and `w₀`'s gradient is
correctly 0 — the state forgets its initial condition.)

## 3. The crux: differentiating the λ (ci:ca) solve

λ is defined implicitly by `g(λ) = fac·(1−λ) − adtmm(λ) = 0` (Eqn 18, Haxeltine & Prentice 1996).
The reference (`LPJmL-hybrid-photosynthesis`) differentiates this with the **implicit-function-theorem
adjoint** (`SteadyStateAdjoint(autojacvec=EnzymeVJP())` over a non-AD Newton) — never through the
bisection iterations.

The spike instead uses a **fixed-iteration damped Newton with a FIXED computational graph** (no
data-dependent branch or convergence `break`; `g'` by a central finite difference in λ, which only
drives the primal solve). Because the graph is identical for every parameter value and the residual
is smooth-a.e. and monotone on the bracket, the total derivative through the unrolled Newton equals
the implicit-function result at convergence — and, decisively, it is **dependency-free and both
ForwardDiff and Enzyme differentiate it cleanly** (verified above). The `SteadyStateAdjoint` path
(which also avoids the reference's noted solver-path memory blow-up on large grids) is retained as
the **scale-up** option; it is not needed to prove feasibility.

## 4. Non-smoothness issues actually hit (and how handled)

The genuinely instructive part of the spike — what blocked AD in practice:

1. **`ForwardDiff.Dual <: Real` but NOT `<: AbstractFloat`.** The initial structs were parameterized
   `{T <: AbstractFloat}`, which *rejected* Dual numbers — ForwardDiff errored immediately. Fix:
   relax the F_diff/allometry structs to `{T <: Real}`. (The Phase-0 `SharedState` keeps
   `AbstractFloat` — it is not on the AD path.)
2. **Mixed-type AD (only one input is `Dual`).** Forcing all four argument structs to share one type
   parameter blocked differentiating w.r.t. a single input (only that struct becomes `Dual`). Fix: a
   promoted working type `T = promote_type(_wt(p), _wt(st), _wt(str), _wt(f))` and `convert`-coerce
   the returned state/flux fields to `T` (state fields that don't depend on the active variable —
   e.g. snow when differentiating CO₂ — would otherwise stay `Float64` and break type-uniformity).
3. **`@kwdef` + parametric defaults = unbound `T`.** `FDiffParams`'s `@kwdef` defaults referenced
   `PhotoParams{T}()`; the auto-generated zero-arg `FDiffParams()` evaluated them with `T` unbound —
   a latent bug JET caught (5 reports). Fix: explicit constructors (`FDiffParams{T}(;…)` +
   `FDiffParams(;…)≡{Float64}`), exactly as `state.jl` does for `SharedState`.
4. **Smooth-surrogate floors are not exactly zero.** `smooth_clamp(0,0,15,β)` returns `log(2)/β`, not
   0; likewise `softplus(0,β)`. So "no light ⇒ eeq = 0" is really "eeq ≈ 0.14 mm/day" (the clamp
   floor) and "no leaf ⇒ GPP = 0" is "GPP ≈ 0.014 gC" (the softplus floor). Both are physically
   negligible and *bounded and tested* (`SmoothOps` deviation ≤ `log(2)/β`); the limiting-case tests
   assert the floors, not exact zero.
5. **The supply/demand conductance regime switch** (`gc = gp_pot` vs the water-limited back-solve) is
   the one C0/C1 discontinuity that mattered physically. Handled by a smooth cap
   `gc = smoothmin(gc_water, gp_pot)` with a softplus-guarded denominator (so `gc_water → +∞`, not a
   NaN, when not water-limited, where `smoothmin` then selects `gp_pot`). Continuous at `supply=demand`.
6. **sqrt-at-0**: the σ term and the co-limitation discriminant. The co-limitation discriminant
   `(je+jc)²−4θ·je·jc ≥ (je−jc)² ≥ 0` is positive by construction (θ<1), so it needs only a round-off
   floor; the σ term uses an ε-floored sqrt.

Two physics corrections the spike also surfaced (not AD-related but caught by the plausibility/
closure checks): woody **maintenance respiration** must use tissue-specific C:N (a leaf-like N:C
over-respires the large sapwood pool → wildly negative NPP); and **runoff must be the non-negative
overflow drainage** with ET supply-capped, not a budget residual (which could go negative).

## 5. Fidelity vs the LPJmL-FIT C oracle ("same physics")

Same equations and **LPJmL-FIT C-source constants** (θ=0.7, ALPHAM=1.391, GM=3.26, α_PT=1.32,
α_c3=0.08, …; NeuralCrop's *crop* values θ=0.9/ALPHAM=1.485 are NOT used). 273.15 K everywhere (the
hybrid repo's 272.15 helper is a bug — a unit test guards this). FIT allometry is **pipe-model height
+ Jucker 2022 crown** (NOT stock `allom2·D^allom3` / Reinicke). Two distinct Priestley–Taylor
coefficients (soil evap vs transpirative demand).

**Documented spike simplifications (scale-up items, NOT physics errors):**
- single-bucket soil water + degree-day snow (vs LPJmL's 23-layer soil water + enthalpy thermal +
  permafrost);
- daylength supplied as forcing (vs the full `petpar` radiation/declination — avoids the polar-day/
  night `acos` branches for the spike);
- smooth surrogates for the non-smooth ops (bounded deviations, tested);
- fixed-graph Newton for λ (vs `SteadyStateAdjoint`).

**Numerical-regression gate today** pins `F_diff` against ITSELF (`references/fdiff_annual_totals.txt`
— a drift alarm). A full quantitative match to the C binary needs the binary's exact forcing, soil
params, and per-PFT constants; that is the next validation step, with the 186 GB daily dataset
(`/p/tmp/jamirp/esm_land_daily/daily_2000_2019_global_c0_67419_seed1/output`) as the target.

## 6. Reuse outcome

- **LPJmL-hybrid-photosynthesis (MIT):** photosynthesis kernel + λ residual + the differentiable-solve
  *pattern* ported cleanly. Its `SteadyStateAdjoint` recipe is the scale-up option, not needed for the spike.
- **NeuralCrop.jl (CC-BY-NC):** PET/ET/respiration equations and the daily-rollout idiom ported
  cleanly. Its public **training driver is a non-turnkey scaffold** (loss/daily-driver/loop have
  inconsistent signatures and reference undefined variables `ps_frozen`/`dailyWeather`; AD backend is
  Zygote, Enzyme is declared-but-unused) — the physics kernels port, the training loop must be
  finished. This is a concrete effort input for Phase 6.
- **LPJmL-FIT C source (AGPL):** allometry + authoritative constants redone. Crops contribute nothing.

## 7. Effort estimate to cover all of F

Rough engineering estimate (one experienced dev), building on this spike's foundation:

| Work item | Est. |
|---|---|
| Multi-layer soil water (LPJmL infil/perc/drainage, `NSOILLAYER`) + rootdist extraction | 1–2 wk |
| 23-layer enthalpy soil-thermal + permafrost (REDO from C, or reuse Terrarium.jl differentiable thermal) | 2–3 wk |
| Full `petpar` radiation/daylength (smoothed polar-day/night branches) | 3–5 d |
| Multi-PFT + representative-individual set (C3/C4, angio/gymno) driven by S | 1–2 wk |
| Quantitative C-binary validation on the prototype cell (exact forcing/params) + ReferenceTests trajectory baselines | 1–2 wk |
| `SteadyStateAdjoint`/`ImplicitDifferentiation` λ-solve for scale (memory) + gradient re-verification | 3–5 d |
| Learned-closure NN hooks (λ/Vcmax via Lux) + finish NeuralCrop's TBPTT training loop | 2–3 wk |
| GPU (KernelAbstractions) + batching over cells | 1–2 wk |
| `SharedState` wiring + S↔F flux-then-integrate coupling on the prototype | 1 wk |
| **Total** | **≈ 2.5–4 months** |

The spike shows none of these are blocked by the AD toolchain: Enzyme reverse-mode works through the
physics rollout today. The remaining work is physics coverage and validation, not a differentiability
unknown.

## 8. Reproducing the gate

```
# runtime is dependency-free; the AD gate uses test/Project.toml (Enzyme/ForwardDiff/FiniteDifferences)
JULIA_DEPOT_PATH=$HOME/.julia julia --project=. -e 'import Pkg; Pkg.test()'
```
Gates of interest: `Gradient correctness — F_diff rollout: AD vs FiniteDifferences`,
`F_diff — water closure by construction`, `Numerical regression — F_diff annual totals baseline`,
`SmoothOps — deviation bounds`, `Allometry — values, limits, monotonicity`.

## Bibliography (research-use reuse; ADR 0015)
- Haxeltine, A. & Prentice, I.C. (1996). BIOME3. *Global Biogeochem. Cycles* 10(4), 693–709.
- Sitch, S. et al. (2003). LPJ DGVM. *Glob. Change Biol.* 9, 161–185.
- Jucker, T. et al. (2022). Tallo allometry. *Glob. Change Biol.*
- LPJmL-hybrid-photosynthesis — github.com/TUM-PIK-ESM/LPJmL-hybrid-photosynthesis (MIT).
- Lin, Y. et al. NeuralCrop.jl — arXiv:2512.20177; github.com/yunan-l/NeuralCrop.jl (CC-BY-NC).
- Terrarium.jl — github.com/NumericalEarth/Terrarium.jl (EUPL-1.2).
- LPJmL-FIT C source — `/home/jamirp/lpjml56fit` (v5.6.004, AGPL-3.0).
