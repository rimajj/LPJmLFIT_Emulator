# Conservation by construction

> *Explanation. The functions named here are real and tested — see [`softmax_partition`](@ref),
> [`flux_then_integrate`](@ref), [`carbon_budget_residual`](@ref), [`water_budget_residual`](@ref),
> [`nbp_atm`](@ref), [`latent_heat`](@ref). Frozen rules: `DESIGN.md` §8; `00_START_HERE.md` §3.*

The single most important design principle is that **coupling variables are conserved and derived,
not co-predicted**. A neural network that independently emits carbon pools, water fluxes, and energy
fluxes will not conserve anything; small per-flux errors accumulate into drift and, under coupling,
instability. We instead make conservation a property of the *architecture*, so it holds for any
model output [Beucler2021, Harder2024](@cite).

## Prefer partitions over residuals

The safest hard constraint is to **partition a conserved input**: emit real-valued logits, map them
through a softmax to fractions that sum to one, and multiply the conserved total by them
[Kraft2022, Harder2024](@cite). Mass is split, never created or destroyed. [`softmax_partition`](@ref)
does exactly this (numerically stabilised by subtracting the max):

```math
f_k = \frac{e^{z_k}}{\sum_j e^{z_j}}, \qquad \sum_k f_k = 1, \qquad f_k \ge 0.
```

Beucler et al. [Beucler2021](@cite) also warn of **residual-field bias**: whichever variable is
forced to absorb the residual carries a localised error spike. Hence the rule *prefer fraction /
partition forms over a privileged residual variable* — with exactly one documented exception (energy,
below).

## Flux-then-integrate: advance the state, don't regenerate it

For storage states (soil water, carbon pools) and for the tree population, we predict **increments**
and integrate them, MC-LSTM style [Hoedt2021](@cite): `new_state = state + increments`, clamped to
non-negativity. [`flux_then_integrate`](@ref) is the primitive. Because every increment is an
accounted flux, carbon is conserved by construction.

This is why **S advances the existing population rather than regenerating it** (`DESIGN.md` §6): S
predicts, per surviving individual (or size×trait class), a growth increment whose across-population
sum equals the allocated NPP,

```math
\sum_i \Delta C_i = f_\text{alloc}\, \cdot\, \texttt{bm\_inc},
```

with allocation/turnover/mortality-fraction as softmax partitions of the delivered
[`FToS`](@ref)`.bm_inc`. Mortality moves an individual's carbon to litter/soil; establishment adds
saplings debited from the establishment flux; fire removes carbon to the atmosphere. The new
population is the old one *advanced*, so the drawn distribution carries the right carbon — a bare
softmax over a *variable* count `N` would not guarantee that.

## The carbon budget must include fire and establishment

Fire (GlobFIRM) is **on** in this configuration, and there is establishment. So the ecosystem carbon
closure is **not** the fire-free `NEE = Rh − NPP` (which will leak carbon and fail to close), but

```math
\Delta C = \text{NPP} - R_h - \texttt{firec} + \texttt{flux\_estabc}.
```

[`carbon_budget_residual`](@ref) computes `ΔC − (NPP − Rh − firec + flux_estabc)`; the conservation
test asserts `|residual| ≤ tol`. The atmosphere-facing net flux the land hands the ESM is

```math
\text{NBP}_\text{atm} = R_h + \texttt{firec} - \text{NPP} - \texttt{flux\_estabc},
```

computed by [`nbp_atm`](@ref). All four terms (`Rh`, `firec`, `NPP`, `flux_estabc`) must reach E for
this to be formed, which is why [`FToE`](@ref) carries them (`flux_estabc` on an annual channel, the
rest daily). Because the training targets are a *self-consistent numerical model* whose budgets
close, enforcing hard carbon (and water) conservation is safe here — unlike observation-trained
hydrology, where strict closure can hurt when the *observed* budget does not close [Frame2023](@cite).

## The water budget

Water closes as

```math
P = \text{ET} + \text{runoff} + \text{drainage} + \Delta S_{\text{soil}+\text{snow}+\text{interception}},
```

checked by [`water_budget_residual`](@ref) against LPJmL's own internal `balanceW` term set. (This
requires the daily runoff/drainage/storage outputs from the Phase-1 daily re-run; the carbon budget,
by contrast, can be verified *now* on the existing annual `globalflux` data — `DESIGN.md` §3.2.)

## Latent heat is derived: `LE = λ·ET`

Latent heat is never predicted independently. It is *derived* from evapotranspiration,
[`latent_heat`](@ref):

```math
\text{LE} = \lambda\, \text{ET},
```

using the latent heat of **vaporization** ([`LAMBDA_VAPORIZATION`](@ref) ``= 2.50\times10^6`` J/kg)
for liquid ET and of **sublimation** ([`LAMBDA_SUBLIMATION`](@ref) ``= 2.83\times10^6`` J/kg) for the
snow/ice component — a ≈13 % difference that must not be conflated.

## The one documented residual: sensible heat H

The energy budget is the single place we *assert* a budget rather than inherit it, and the single
place a privileged residual is used deliberately. LPJmL's ET is **water-limited** — `LE` is set by
water availability, not free to choose — so we cannot also softmax-partition available energy into
`LE / H / G`. Instead `LE` is given and **H closes the balance as the residual**:

```math
H = R_n(T_\text{skin}) - G(T_\text{skin}) - \text{LE}.
```

This is the deliberate exception to "no privileged residual". PLUMBER2 finds sensible heat the
worst-modelled turbulent flux across ~170 sites [Abramowitz2024](@cite), so **H is validated hardest
against FLUXNET/PLUMBER2**, and only a *bounded* ML correction to `g_a`/`T_skin` inside the closed
balance is permitted — the physics owns closure; the network never breaks `Rn = LE + H + G`. Follow
the MC-LSTM lesson: only close a budget you can actually account for [Hoedt2021](@cite).

See the [limitations](limitations.md) page for the honest caveats this entails.
