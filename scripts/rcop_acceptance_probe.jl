# Acceptance probe for a PRODUCTION recruit-trait copula artifact (`.rcop` + its `_meta.txt`) — ADR 0038.
#
# WHY THIS EXISTS. `scripts/train_slow_copula.jl` already self-checks a round trip in the process that
# built the artifact, with the forests still in memory. That proves serialization is self-consistent; it
# does NOT prove the artifact is usable by a LATER process, which is the thing that actually ships. Three
# failure modes live in that gap, and all three are silent:
#
#   1. The `.rcop` carries `ncond`, but NOT `qrf`. The QRF (Meinshausen) leaf weighting is recorded only in
#      the sidecar `_meta.txt` (`qrf_weighting`), so a runtime that loads the artifact and forgets to pass
#      `qrf = true` samples a DIFFERENT conditional distribution than the one the ADR-0030 gate scored, and
#      every draw still lands in range. This probe reproduces the meta's golden pairs under BOTH settings
#      and reports whether they differ — i.e. whether `qrf_weighting` is load-bearing for THIS artifact.
#   2. The conditioning WIDTH contract. A 14-column artifact must be queried through
#      `live_flux_cond_env(env)`, an 8-column one through `live_flux_cond`. Passing the wrong-width row was
#      an out-of-bounds heap read (`_leaf` reads `x[f]` under `@inbounds`) that returned a plausible
#      in-range trait; there are guards now, and this probe exercises them from the OUTSIDE.
#   3. Load cost. `DRF.load_copula` slurps the whole file and `split`s it into tokens (`src/drf.jl`), so a
#      ~0.5 GB text artifact has a real, measurable startup cost that a coupled run pays per process. The
#      "~12 s at 42 MB/s" figure quoted in an earlier handoff was an ESTIMATE, never measured — this
#      prints the measured number so nobody has to guess again.
#
# Usage (SLURM; see CLAUDE.md §2 — this parses ~0.5 GB and is not a login-node job):
#   RCOP=/p/tmp/jamirp/emulator_global/recruit_copula_global_historic_t9.rcop \
#     scripts/sbatch_julia.sh S-rcop-accept --project=. scripts/rcop_acceptance_probe.jl
#
# Env: RCOP (required, path to the .rcop; the sidecar is inferred as <stem>_meta.txt)
#      NDRAW (2000) how many draws for the distribution summary
#      BOUNDARY_N (4) width of the boundary tail `live_flux_cond` contributes, for the env-width arithmetic
#
# Named `*_probe.jl` DELIBERATELY: ReTestItems scans the whole repo for `*_test(s).jl` and rejects any that
# is not pure `@testitem`, so a diagnostic script must never take that name (CLAUDE.md §2).

using LPJmLFITEmulator
using LPJmLFITEmulator.DRF

const RCOP = get(ENV, "RCOP", "")
const NDRAW = parse(Int, get(ENV, "NDRAW", "2000"))
const BOUNDARY_N = parse(Int, get(ENV, "BOUNDARY_N", "4"))

isempty(RCOP) && error("set RCOP=<path to the .rcop>")
isfile(RCOP) || error("no such .rcop: $RCOP")

const META = replace(RCOP, r"\.rcop$" => "_meta.txt")

function read_meta(path)
    d = Dict{String, String}()
    golden = Tuple{Int, Vector{Float64}}[]
    isfile(path) || return d, golden
    for line in eachline(path)
        startswith(line, "#") && continue
        parts = split(line, '\t')
        if length(parts) == 3 && parts[1] == "golden"
            push!(golden, (parse(Int, parts[2]), parse.(Float64, split(strip(parts[3])))))
        elseif length(parts) == 2
            d[parts[1]] = parts[2]
        end
    end
    return d, golden
end

nfail = 0
function check(label, ok, detail = "")
    global nfail
    ok || (nfail += 1)
    println("   ", ok ? "PASS" : "FAIL", "  ", label, isempty(detail) ? "" : "  — $detail")
    return ok
end

println("="^100)
println("RCOP ACCEPTANCE PROBE — $(basename(RCOP))")
println("="^100)
println("   artifact : $RCOP")
println("   bytes    : $(filesize(RCOP)) ($(round(filesize(RCOP) / 2^20, digits = 1)) MiB)")
println("   meta     : $META $(isfile(META) ? "" : "(ABSENT)")")

meta, golden = read_meta(META)

# ---- [1/5] LOAD, timed in a FRESH process (the number a coupled run actually pays) -------------------
println("\n== [1/5] load =======================================================================")
t0 = time_ns()
cop, forests, x, axes, cond_cols = DRF.load_copula(RCOP)
dt = (time_ns() - t0) / 1.0e9
mbs = (filesize(RCOP) / 2^20) / dt
println("   loaded in $(round(dt, digits = 2)) s  =  $(round(mbs, digits = 1)) MiB/s   [MEASURED, not estimated]")
ncond = length(cond_cols)
println("   axes     : $(axes)")
println("   ncond    : $ncond")
println("   cond_cols: $(join(cond_cols, " "))")
println("   forests  : $(join(("$(a)=$(length(f.trees))t/nfeat$(f.nfeat)" for (a, f) in zip(axes, forests)), "  "))")

# ---- [2/5] the HEADER contract ------------------------------------------------------------------------
println("\n== [2/5] header contract vs the sidecar meta =========================================")
check(
    "every axis forest's nfeat == ncond", all(f.nfeat == ncond for f in forests),
    "nfeat = $(join((f.nfeat for f in forests), ","))  ncond = $ncond"
)
check("fallback row x has ncond entries", length(x) == ncond, "length(x) = $(length(x))")
check("x is all finite", all(isfinite, x))
if haskey(meta, "ncond")
    check(
        "meta ncond agrees with the .rcop", parse(Int, meta["ncond"]) == ncond,
        "meta $(meta["ncond"]) vs rcop $ncond"
    )
end
if haskey(meta, "cond_cols")
    check("meta cond_cols agrees with the .rcop", split(strip(meta["cond_cols"])) == cond_cols)
end
if haskey(meta, "axes")
    check("meta axes agrees with the .rcop", split(strip(meta["axes"])) == axes)
end
qrf_meta = haskey(meta, "qrf_weighting") ? meta["qrf_weighting"] == "1" : nothing
println(
    "   meta qrf_weighting: ", qrf_meta === nothing ? "ABSENT (pre-ADR-0037 artifact ⇒ treat as 0)" :
        (qrf_meta ? "1 (QRF leaf weighting)" : "0 (equal-weight)")
)

# ---- [3/5] GOLDEN pairs — and whether `qrf` is load-bearing for this artifact -------------------------
println("\n== [3/5] golden (seed, x) -> draw pairs, under BOTH qrf settings =====================")
if isempty(golden)
    println("   (no golden rows in the meta — skipped)")
else
    qrf_use = qrf_meta === true
    # Single-assignment via a comprehension, NOT a counter mutated inside the loop: at top level a `for`
    # body is SOFT scope, so `ndiff += 1` there binds a NEW local and the outer name is never assigned
    # (`UndefVarError` at the read below — this script hit exactly that on its first run). Same family as
    # the JET boxed-capture rule in CLAUDE.md §2: prefer a single assignment over a reassigned local.
    flipped = [
        begin
                got_declared = DRF.sample_copula!(DRF.Xoshiro256pp(s), cop, forests, x; qrf = qrf_use)
                got_other = DRF.sample_copula!(DRF.Xoshiro256pp(s), cop, forests, x; qrf = !qrf_use)
                # The meta prints draws with `string(v)` (full Float64 round-trip) ⇒ this must be EXACT.
                check(
                    "golden seed $s reproduces at qrf=$(qrf_use)", got_declared == want,
                    got_declared == want ? "" : "got $(got_declared) want $(want)"
                )
                got_other != want
            end for (s, want) in golden
    ]
    ndiff = count(flipped)
    # If flipping qrf changes the draws, then `qrf_weighting` is a LOAD-BEARING part of the contract that
    # lives ONLY in the sidecar — a runtime that loses the sidecar silently samples the wrong distribution.
    if ndiff == length(golden)
        println("   NOTE: flipping qrf changes ALL $(ndiff) golden draws ⇒ `qrf_weighting` is LOAD-BEARING")
        println("         and it is NOT stored in the .rcop, only in the sidecar meta. A runtime that")
        println("         constructs RecruitCopula without qrf=$(qrf_use) samples a DIFFERENT conditional")
        println("         distribution than the ADR-0030 gate scored, and every draw stays in range.")
    elseif ndiff == 0
        println("   NOTE: flipping qrf changes NO golden draw at the fallback row — not evidence that qrf")
        println("         is irrelevant in general (leaf weighting can be degenerate at this one row).")
    end
end

# ---- [4/5] the RUNTIME path: build the conditioning row the way the coupled loop does -----------------
println("\n== [4/5] runtime conditioning row (live_flux_cond / live_flux_cond_env) =============")
nenv = ncond - 4 - BOUNDARY_N
println("   arithmetic: ncond $ncond = 4 flux + $BOUNDARY_N boundary + $nenv env")
check("the env width is non-negative", nenv >= 0, "nenv = $nenv")
# Reuse the artifact's own fallback row as a physically-plausible cell: split it the way the two policies
# do, so the row this probe builds is exactly the row the artifact was trained to be queried with.
feats = vcat(x[1:4], zeros(7))          # live_flux_cond reads feats[1:4]; [5:11] are deliberately excluded
boundary = x[5:(4 + BOUNDARY_N)]
s_stub = (boundary = boundary,)
if nenv == 0
    row = live_flux_cond(s_stub, feats)
    println("   policy   : live_flux_cond")
else
    env = x[(5 + BOUNDARY_N):ncond]
    row = live_flux_cond_env(env)(s_stub, feats)
    println("   policy   : live_flux_cond_env(env) with length(env) = $(length(env))")
end
check("the runtime row has exactly ncond entries", length(row) == ncond, "length(row) = $(length(row))")
check("the runtime row reproduces the fallback row x", row == x)

# The guard must FIRE on a wrong-width row rather than returning a plausible trait (it was an
# out-of-bounds @inbounds heap read before ADR 0038).
for bad_len in filter(l -> l >= 1 && l != ncond, (ncond - 1, ncond + 1, 4))
    bad = collect(x[1:min(bad_len, ncond)])
    while length(bad) < bad_len
        push!(bad, 0.0)
    end
    threw = false
    try
        DRF.sample_copula!(DRF.Xoshiro256pp(1), cop, forests, bad)
    catch
        threw = true
    end
    check("a $(bad_len)-column row is REJECTED (ncond = $ncond)", threw)
end

# ---- [5/5] distribution summary at the fallback row --------------------------------------------------
println("\n== [5/5] draw distribution at the fallback row x ($(NDRAW) draws) ===================")
qrf_use = qrf_meta === true
draws = [DRF.sample_copula!(DRF.Xoshiro256pp(10_000 + s), cop, forests, x; qrf = qrf_use) for s in 1:NDRAW]
println("   axis          mean         sd          min          max   nonfinite")
for (a, ax) in enumerate(axes)
    v = [d[a] for d in draws]
    μ = sum(v) / length(v)
    sd = sqrt(max(sum((vi - μ)^2 for vi in v) / length(v), 0.0))
    nnf = count(!isfinite, v)
    println(
        "   $(rpad(ax, 10)) $(rpad(round(μ, sigdigits = 5), 12)) $(rpad(round(sd, sigdigits = 4), 11)) " *
            "$(rpad(round(minimum(v), sigdigits = 5), 12)) $(rpad(round(maximum(v), sigdigits = 5), 12)) $nnf"
    )
    check("$ax draws are all finite", nnf == 0)
end
println("   NOTE: the mean here is the CONDITIONAL mean at the average conditioning row, which for a")
println("         skewed/multi-biome axis is NOT the global marginal mean. On the global tables minwscal")
println("         reads ~0.13 against a ~0.24 training mean in EVERY generation (t7/t8/t9, historic +")
println("         ssp370 + pooled) while single-cell Hainich agrees to 1 % — that is the biome mixture,")
println("         not a defect. Do not open a residual investigation on it.")

println("\n" * "="^100)
println(
    nfail == 0 ? "ACCEPTANCE: PASS — $(basename(RCOP)) is loadable and contract-consistent" :
        "ACCEPTANCE: $nfail CHECK(S) FAILED for $(basename(RCOP))"
)
println("="^100)
exit(nfail == 0 ? 0 : 1)
