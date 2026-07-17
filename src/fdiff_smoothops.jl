# ── Smooth surrogates for the non-differentiable ops in the LPJmL-FIT daily biophysics ──────────
# Every kink the C core relies on (min/max caps, clamps, sqrt-at-0, the supply/demand regime switch,
# the tstress temperature cutoffs, the rain/snow split) is replaced here by a C∞ surrogate so
# reverse-/forward-mode AD has a well-defined gradient everywhere. **Each surrogate is an
# APPROXIMATION** — its deviation from the exact op is bounded and documented, and the bound is a
# CI test (ENGINEERING_STANDARDS §2; ADR 0014 step 5). NeuralCrop.jl already ships several of these
# (sigmoid Rd gate, C4 phipi, logistic soil-moisture) — we adopt the same idiom, cite it, and make
# the sharpness β explicit so callers trade smoothness against fidelity knowingly.

"""
    SmoothOps

C∞ surrogates for the non-smooth ops in F_diff, each with a stated deviation bound from the exact
operation. Sharpness parameters (`β`) default to values that keep the deviation negligible at the
model's operating scales; a larger `β` is a closer approximation with a stiffer gradient.
"""
module SmoothOps

export sigmoid, stable_sigmoid, softplus, smoothmax0, smoothmin, smoothmax, smooth_clamp, sqrt_floor, softabs

"Logistic sigmoid `1/(1+e^{-x})`. Smooth everywhere; the building block for regime gates."
sigmoid(x) = inv(one(x) + exp(-x))

"""
    stable_sigmoid(x, xcap=30) -> y

Logistic sigmoid with the argument clamped to `[-xcap, xcap]` before `exp`. Prevents `exp(-x)`
overflow (→ `Inf` → `NaN` gradient) for the steep GSI phenology limiters (e.g. the light slope
`58`, whose argument reaches ≈±2300). The clamp only bites deep in a saturated tail where the true
sigmoid derivative is `< e^{-30} ≈ 1e-13`, so the deviation from the exact sigmoid is negligible and
the forward/backward passes stay finite. Mirrors the C GSI's own `if(-sl·(x-base) < 200)` overflow
guard (`phenology_gsi.c:57`), which likewise relaxes toward the saturated value.
"""
stable_sigmoid(x, xcap = 30) = sigmoid(clamp(x, -xcap, xcap))

"""
    softplus(x, β=one(x)) -> y

Smooth `max(x, 0)`: `softplus(x,β) = log1p(exp(β·x))/β`. **Deviation:** `0 ≤ softplus(x,β) − max(x,0)
≤ log(2)/β`, maximal at `x=0`. Overflow-guarded for large `β·x` (falls back to the identity branch,
which is exact there). Used for the `max(0, …)` flux floors.
"""
function softplus(x, β = one(x))
    z = β * x
    # for large z, log1p(exp(z)) ≈ z to within machine eps ⇒ return x (avoids Inf)
    return z > 30 ? x : log1p(exp(z)) / β
end

"""
    smoothmax0(x, β) -> y

Alias for [`softplus`](@ref) — a smooth `max(x, 0)` (relu). Same `log(2)/β` deviation bound.
"""
smoothmax0(x, β) = softplus(x, β)

"""
    smoothmin(a, b, β) -> m

Log-sum-exp soft minimum, `m = -log(exp(-β·a)+exp(-β·b))/β`. **Deviation:** `0 ≤ min(a,b) − m ≤
log(2)/β`. Stabilised by factoring out `min(a,b)`; handles `±Inf` arguments (an `+Inf` argument drops
out, so `smoothmin(+Inf, b, β) → b`). Used for the crown-area / height / conductance caps.
"""
function smoothmin(a, b, β)
    m = min(a, b)
    return m - log(exp(-β * (a - m)) + exp(-β * (b - m))) / β
end

"""
    smoothmax(a, b, β) -> m

Log-sum-exp soft maximum, `m = log(exp(β·a)+exp(β·b))/β`. **Deviation:** `0 ≤ m − max(a,b) ≤
log(2)/β`. Stabilised by factoring out `max(a,b)`.
"""
function smoothmax(a, b, β)
    m = max(a, b)
    return m + log(exp(β * (a - m)) + exp(β * (b - m))) / β
end

"""
    smooth_clamp(x, lo, hi, β) -> y

Smooth clamp to `[lo, hi]` via `smoothmax(lo, smoothmin(x, hi, β), β)`. Deviation `≤ 2·log(2)/β`.
Used for the `eeq ∈ [0, 15]` cap and the soil-water fraction `w ∈ [0, 1]`.
"""
smooth_clamp(x, lo, hi, β) = smoothmax(lo, smoothmin(x, hi, β), β)

"""
    sqrt_floor(x, ε) -> y

Differentiable `sqrt(max(x, 0))`: `sqrt(softplus(x, β)+ε)`-style is overkill; we use `sqrt(x + ε)`
after ensuring `x ≥ 0` at the physical operating point, or `sqrt(√-guard)`. Here: `sqrt(x + ε)` for
`x` known `≥ −ε`; for the co-limitation discriminant `x ≥ (je−jc)² ≥ 0` analytically, so `ε` only
guards round-off. **Deviation:** `|sqrt(x+ε) − sqrt(max(x,0))| ≤ √ε` for `x ≥ 0`. Default `ε=1e-9`.
"""
sqrt_floor(x, ε = 1.0e-9) = sqrt(x + ε)

"""
    softabs(x, ε) -> y

Smooth `|x|` via `sqrt(x² + ε)`. Deviation `≤ √ε`. (Not on the current F_diff path; provided for the
water-stress accumulator port.)
"""
softabs(x, ε = 1.0e-9) = sqrt(x * x + ε)

end # module SmoothOps
