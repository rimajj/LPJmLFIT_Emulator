### Added

- **The nocturnal-H diagnosis for Component E (line E, milestone E6; ADR 0073 — supersedes ADR 0072 items 4
  and 6).** `scripts/e_nocturnal_h_decomp.jl` attributes the H error by **exact algebra** rather than by
  parameter sweep. Because `H` is the exact residual `Rn_m − LE − G_m`, its error obeys identically
  `ΔH = ΔRn − ΔG + ε_obs`, where `ε_obs = Rn_o − LE − H_o − G_o` is the **tower's own non-closure** — an error
  no closing model can remove. `g_a` appears in none of the three terms. The probe reports, per site: a harness
  check (model self-closure `= 0.0` exactly; the identity closes to `≤ 2.3e-13`; ADR 0072's night numbers
  reproduced digit for digit), the decomposition night/day/all, `G` scored against **both** the measured plate
  `Qg` and the budget-implied sink `G_res = Rn_o − LE − H_o`, **night-only** `Rn` (never reported before), a
  100× `g_a` bracket, the tower's measured-`u*` `g_a` substituted into the real solver, the model's **native
  daily step**, the observation-implied `λ_g`, and a `λ_g` sensitivity table.
- `scripts/build_e_seb_validation_table.py` now also emits **`ustar`** (u\* ≤ 0 masked — a documented OzFlux
  artifact). Row counts are unchanged at all four sites, so ADR 0072's basis is untouched.
- A synthetic CI testitem pinning the **lever ranking** (`test/testitems/energy_closure_tests.jl` — *"nocturnal
  H is a ground-heat lever, not an aerodynamic one"*), so the refuted hypothesis cannot quietly re-open.

### Verdict (same 497 936 tower steps, 4 sites — full numbers in ADR 0073)

- **The stability / `g_a` hypothesis is REFUTED, three independent ways.** The closure's nocturnal `g_a` is
  within **0.7 %** of DE-Hai's measured-`u*` value (0.05724 vs 0.05685 m/s) and within a factor 2 at every
  site; substituting the measurement makes nocturnal H **worse at all four sites**; and a **100× `g_a`
  bracket cannot reach positive nocturnal R²** anywhere (best −0.06). ADR 0072's monotone `stab_amp` sweep was
  a **bias-cancellation artifact** — suppressing `g_a` offsets the ground-heat error without fixing it.
- **The mechanism is the ground-heat term's timescale.** `G = λ_g(T_skin − t_soil)` with `λ_g = 7.0` and a
  τ = 30 d EWMA reference has no diurnal soil inertia and no canopy decoupling: sd(`G_model`) is **5–7×**
  sd(`G_observed`) at the closed-canopy forest sites (34.7 vs 5.7 W/m² at DE-Hai), G night R² −3.4…−51.1, and
  **88 % of DE-Hai's +14.04 W/m² nocturnal H bias is `ΔG`**.
- **`λ_g ≈ 1.0`, not 7.0, at the daily step the coupled model actually runs** (`run.jl:93` calls `solve!` once
  per day). Three independent lines agree: the observation-implied `λ_g` is **0.83–1.10** at all four sites at
  the daily step; `λ_g ≈ 1.0` reproduces the observed daily sd(`G_o`) of 4.3–6.3 W/m²; and daily H skill
  improves at 3 of 4 sites — **DE-Hai R² 0.03 → 0.64** (RMSE 38.1 → 23.4), **AU-ASM 0.33 → 0.74** (31.8 → 19.6).
  A broad optimum (0.5 and 1.0 score alike), degrading only the already-suspect AU-Rob.
- **Part of the residual is UNCLOSABLE.** Mean nocturnal `ε_obs`: DE-Hai **−0.32** (the tower closes — the
  trustworthy site), AU-ASM −12.0, AU-Rob −47.5, AU-Tum **−62.3** W/m². At the daily step `ε_obs` accounts for
  essentially the entire mean H bias at three sites, while DE-Hai's daily H bias is **+0.87 W/m²**. AU-Tum and
  AU-Rob **cannot** honestly score a closing model's nocturnal H; they remain valid for `T_skin`.
- **Nocturnal *skill* (R² > 0) is not recoverable by any parameter value in the present form** — that needs a
  force-restore / two-layer soil scheme with a real diurnal wave plus canopy heat storage. This bounds line O:
  the online sub-daily coupling inherits an R² < 0 nocturnal H until that lands.
- **No default changed and no physics changed** (guardrail 4). `lambda_g` is already a `SEBParams` field, so
  `SEBEnergyClosure(params = SEBParams(lambda_g = 1.0))` works today with zero code change. Flipping the
  default moves every coupled/biome baseline ⇒ **`lambda_g` is now the live E→M integration point, and
  `stab_amp` is withdrawn as one.**
