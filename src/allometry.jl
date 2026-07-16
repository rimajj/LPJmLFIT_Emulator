# ── Shared allometry / diagnostics library (differentiable pure functions) ──────────────────────
# This module is DELIBERATELY neither "F physics" nor "S ML" (ADR 0014): it is the shared,
# differentiable geometry that maps a tree's carbon pools + individual density to the structural
# diagnostics (height, crown area, LAI, FPC, …) that the S→F / S→E interface needs and that S also
# uses. Kept as a standalone submodule so both sides call ONE implementation.
#
# REDONE from the LPJmL-FIT C source (crops have nothing usable here) — see
# `docs/decisions/0015-reuse-map.md`. This is the **FIT fork**, so:
#   • height is the pipe-model / leaf-area:sapwood-area (La:Sa) relation — NOT `allom2·D^allom3`;
#   • crown area / stem diameter use the **Jucker et al. (2022)** allometry — NOT Reinicke's rule
#     (`reinickerp` is #define'd but UNUSED in the fork).
# Every function is a pure diagnostic (no state mutation) so it is trivially AD-friendly. The one
# non-pure C operation — the sapwood→heartwood transfer at the height cap — is a *state update* and
# lives in F/S, not here (see [`height_capped`]).
#
# Source citations are to `/home/jamirp/lpjml56fit` (v5.6.004), verified this session.

"""
    Allometry

Differentiable tree allometry / diagnostics (LPJmL-FIT fork). Pure functions mapping carbon pools
`(C_leaf, C_sapwood)` and individual density `N` to structure `(height, stem diameter, crown area,
LAI, FPC, FPAR)`, plus smooth surrogates for the two capped operations. Constants live in
[`TreeAllometry`](@ref); the FIT numeric values (Jucker 2022 crown/height, `k_latosa` pipe model,
Beer–Lambert light extinction) are the module defaults.

All quantities SI-ish per the C source: carbon `gC`, `SLA` `m²/gC`, wood density `gC/m³`, height
`m`, crown area `m²`, `N` individuals `m⁻²`, LAI/FPC/FPAR dimensionless.
"""
module Allometry

using ..SmoothOps: smoothmin        # the shared C∞ soft-min (low-level surrogate lib)

export TreeAllometry, tree_height, height_capped, stem_diameter, crown_area, crown_area_smooth,
    bole_height, bark_thickness, lai, fpc, fpar

"""
    TreeAllometry{T}

Allometry constants for one tree PFT (LPJmL-FIT, `par/pft_lpjmlfit.js`). Defaults are the
**angiosperm** (broadleaf) values; [`gymnosperm`](@ref TreeAllometry) swaps in the needleleaf set.

| field | default (angio) | unit | meaning | LPJmL source |
|---|---|---|---|---|
| `k_latosa` | 4000 | – | leaf-area:sapwood-area ratio (pipe model) | `pft_lpjmlfit.js:84` |
| `sla` | 0.01986 | m²/gC | specific leaf area | `:143` |
| `wooddens` | 2e5 | gC/m³ | wood (carbon) density | `include/tree.h:83` |
| `allom1` | 117.44 | m² | Jucker22 crown-area coefficient | `:31` |
| `allom2` | 28.7490 | – | Jucker22 height coefficient (`H = allom2·D^allom3`) | `:34` |
| `allom3` | 0.5633 | – | Jucker22 height exponent | `:37` |
| `kpr` | 1.2922 | – | crown-area exponent | `:41` |
| `crownarea_max` | 225 | m² | crown-area cap | `:40` |
| `height_max` | 100 | m | maximum tree height | `:50` |
| `crownlength` | 0.3334 | – | crown fraction of height | `:236` |
| `k_beer` | 0.59 | – | Beer–Lambert light-extinction coefficient (broadleaf) | `:43` |
| `barkthick_par1` | 0.0301 | cm/cm | bark-thickness slope (stem cm) | `:237` |
| `barkthick_par2` | 0.0281 | cm | bark-thickness intercept | `:238` |

References: Jucker et al. (2022) *Glob. Change Biol.*; Sitch et al. (2003) LPJ (pipe model,
Beer–Lambert). Same-physics port target of the LPJmL-FIT C `allometry_tree.c`/`lai_tree.c`/
`fpc_tree.c`.
"""
Base.@kwdef struct TreeAllometry{T <: Real}
    k_latosa::T = 4.0e3
    sla::T = 0.01986
    wooddens::T = 2.0e5
    allom1::T = 117.44
    allom2::T = 28.749
    allom3::T = 0.5633
    kpr::T = 1.2922
    crownarea_max::T = 225.0
    height_max::T = 100.0
    crownlength::T = 0.3334
    k_beer::T = 0.59
    barkthick_par1::T = 0.0301
    barkthick_par2::T = 0.0281
end

"""
    gymnosperm(TreeAllometry{T}) -> TreeAllometry{T}

The needleleaf (gymnosperm) constant set (`par/pft_lpjmlfit.js` `_GYMNO` values + `K_LAMBERT_BEER_NL`).
"""
gymnosperm(::Type{TreeAllometry{T}}) where {T} = TreeAllometry{T}(;
    allom1 = 101.34, allom2 = 31.4093, allom3 = 0.665, kpr = 1.4163, k_beer = 0.45
)

# The crown-area / height caps use the shared C∞ soft-min `smoothmin` from `SmoothOps` (deviation
# `≤ log(2)/β` from the exact `min`); see [`crown_area_smooth`](@ref) and [`height_capped`](@ref).

# ── height (pipe model / La:Sa) — allometry_tree.c:39-41 ─────────────────────────────────────────
"""
    tree_height(p::TreeAllometry, c_sapwood, c_leaf) -> H

Tree height from the leaf-area:sapwood-area (pipe-model) relation
`H = k_latosa · C_sap / (C_leaf · SLA · ρ_wood)` (`allometry_tree.c:39-41`). Returns `0` when either
carbon pool is non-positive (the C guard; the physical limiting case *zero leaf carbon ⇒ H = 0*).
The guard is a real branch — the live branch is only taken for `C_leaf > 0`, so the `1/C_leaf`
singularity is never differentiated at an operating point.
"""
function tree_height(p::TreeAllometry, c_sapwood, c_leaf)
    T = promote_type(typeof(float(c_sapwood)), typeof(float(c_leaf)), typeof(p.k_latosa))
    (c_sapwood <= 0 || c_leaf <= 0) && return zero(T)
    return p.k_latosa * c_sapwood / (c_leaf * p.sla * p.wooddens)
end

"""
    height_capped(p::TreeAllometry, H; smooth=false, β=1.0) -> H_capped

Apply the `height_max` cap (`allometry_tree.c:44`). `smooth=false` is the exact `min(H, height_max)`;
`smooth=true` uses [`smoothmin`](@ref) for a differentiable cap near the ceiling.

**NB — the C source also moves carbon** `sapwood → heartwood` when the cap binds
(`allometry_tree.c:47-50`); that is a *state update*, not a diagnostic, so it is intentionally NOT
here — it belongs to the F/S carbon bookkeeping and must stay out of the pure-diagnostic AD path.
"""
height_capped(p::TreeAllometry, H; smooth::Bool = false, β = one(H)) =
    smooth ? smoothmin(H, p.height_max, β) : min(H, p.height_max)

# ── stem diameter — allometry_tree.c:55 (inverse Jucker H = allom2·D^allom3) ──────────────────────
"""
    stem_diameter(p::TreeAllometry, H) -> D

Stem diameter `D = (H / allom2)^(1/allom3)` (inverse of the Jucker 2022 height relation,
`allometry_tree.c:55`), units `m`. Smooth for `H > 0`; `H = 0 ⇒ D = 0`.
"""
stem_diameter(p::TreeAllometry, H) = H <= 0 ? zero(float(H)) : (H / p.allom2)^(inv(p.allom3))

# ── crown area (Jucker 2022, capped) — allometry_tree.c:53,57 ─────────────────────────────────────
"""
    crown_area(p::TreeAllometry, H) -> CA

Crown area `CA = min( allom1·(H/allom2)^(kpr/allom3), crownarea_max )` (Jucker 2022,
`allometry_tree.c:53,57`), units `m²`. Equivalent to `allom1·D^kpr` with `D` from
[`stem_diameter`](@ref). The `min` cap is a kink; see [`crown_area_smooth`](@ref) for the AD
surrogate. `H = 0 ⇒ CA = 0`.
"""
function crown_area(p::TreeAllometry, H)
    H <= 0 && return zero(float(H))
    allometry = p.allom1 * (H / p.allom2)^(p.kpr / p.allom3)
    return min(allometry, p.crownarea_max)
end

"""
    crown_area_smooth(p::TreeAllometry, H; β=0.1) -> CA

[`crown_area`](@ref) with the `crownarea_max` cap replaced by [`smoothmin`](@ref) (deviation
`≤ log(2)/β` m²). Use where the cap must be differentiable; default `β=0.1` keeps the surrogate
within `≈6.9 m²` of the exact cap (only matters for the largest crowns, `CA ≳ 200 m²`).
"""
function crown_area_smooth(p::TreeAllometry, H; β = 0.1)
    H <= 0 && return zero(float(H))
    allometry = p.allom1 * (H / p.allom2)^(p.kpr / p.allom3)
    return smoothmin(allometry, p.crownarea_max, β)
end

# ── bole height — allometry_tree.c:52 ────────────────────────────────────────────────────────────
"""
    bole_height(p::TreeAllometry, H) -> boleht

Bole (branch-free trunk) height `boleht = (1 − crownlength)·H` (`allometry_tree.c:52`).
"""
bole_height(p::TreeAllometry, H) = (one(p.crownlength) - p.crownlength) * H

# ── bark thickness [cm] — allometry_tree.c:56 (fire diagnostic) ──────────────────────────────────
"""
    bark_thickness(p::TreeAllometry, D) -> bt

Bark thickness `bt = barkthick_par1·(D·100) + barkthick_par2` (`allometry_tree.c:56`), units `cm`.
**Unit flag:** `D·100` converts the stem diameter from `m` to `cm` before the bark coefficients.
"""
bark_thickness(p::TreeAllometry, D) = p.barkthick_par1 * (D * 100) + p.barkthick_par2

# ── LAI — lai_tree.c:22-23 ───────────────────────────────────────────────────────────────────────
"""
    lai(p::TreeAllometry, c_leaf, crownarea) -> LAI

Leaf area index `LAI = C_leaf·SLA / CA` (`lai_tree.c:22-23`), dimensionless. Returns `0` when either
argument is non-positive — the required limiting case *zero leaf carbon ⇒ LAI = 0*.
"""
function lai(p::TreeAllometry, c_leaf, crownarea)
    T = promote_type(typeof(float(c_leaf)), typeof(float(crownarea)), typeof(p.sla))
    (c_leaf <= 0 || crownarea <= 0) && return zero(T)
    return c_leaf * p.sla / crownarea
end

# ── FPC (Beer–Lambert) — fpc_tree.c:28-29 ────────────────────────────────────────────────────────
"""
    fpc(p::TreeAllometry, crownarea, nind, LAI) -> FPC

Foliar projective cover `FPC = CA·N·(1 − exp(−k·LAI))` (Beer–Lambert, `fpc_tree.c:28-29`), where
`k = k_beer`, `N` = individuals m⁻². The `(1 − exp)` term is smooth; the only guard is
`crownarea > 0 ⇒ 0`. Saturates to `CA·N` as `LAI → ∞`. (The non-negative FPC *increment*
`max(0, FPC − FPC_old)` of `fpc_tree.c:30` is a bookkeeping step for F/S, not this diagnostic.)
"""
function fpc(p::TreeAllometry, crownarea, nind, LAI)
    T = promote_type(typeof(float(crownarea)), typeof(float(nind)), typeof(float(LAI)), typeof(p.k_beer))
    crownarea <= 0 && return zero(T)
    return crownarea * nind * (one(T) - exp(-p.k_beer * LAI))
end

# ── FPAR — fpar_tree.c:20 ────────────────────────────────────────────────────────────────────────
"""
    fpar(FPC, phen, snowcover) -> FPAR

Fraction of absorbed PAR `FPAR = phen·FPC·(1 − snowcover)` (`fpar_tree.c:20`), with phenology
`phen ∈ [0,1]` and `snowcover ∈ [0,1]`.
"""
fpar(FPC, phen, snowcover) = phen * FPC * (one(snowcover) - snowcover)

end # module Allometry
