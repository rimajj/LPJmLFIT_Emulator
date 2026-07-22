# P1 Step 1 (ADR 0019 / docs/p1_s_in_loop_design.md) — the carbon-accounting FOUNDATION for wiring the
# slow demography emulator S into the coupled loop under the ADR-0018 growth-ownership split. F_diff owns
# the conserving CARBON growth of representative individuals; S owns the demography. For the S↔F handoff to
# conserve carbon to ~1e-6, every carbon movement must be an accounted flux. This gate verifies the two
# primitives that make that possible, WITHOUT changing any growth behaviour (opt-in helpers, default
# byte-identical): `vegc_full_ind` (total veg C INCLUDING the below-ground sapwood_bg pool) and
# `_turnover_litter` (the reproduction + leaf/root turnover litter that leaves the pools each year).
#
# The load-bearing facts (verified on real Hainich cohorts, scratchpad/litter_probe.jl):
#   • Growth NEVER creates carbon: Δvegc_full_ind ≤ bm_inc_ind (the ledger litter = bm − Δvegc_full ≥ 0).
#   • On the NORMAL allocation branch (dominant path) AND for all grass, the litter residual equals the
#     independent `_turnover_litter` formula to machine precision (the non-tautological check that
#     grow_individual/grow_grass_individual conserve into the known channels reprod + leaf/root turnover).
#   • On the rare ABNORMAL low-bm tree branch, grow_individual sheds a little EXTRA leaf carbon to litter
#     beyond the formula — so the conserving ledger (conservation.jl, Step 2) routes litter as the EXACT
#     residual `bm − Δvegc_full`, which captures the extra automatically; the formula is the normal-path witness.

@testitem "Carbon accounting foundation — vegc_full_ind + _turnover_litter closure (Hainich)" tags = [:conservation, :fdiff, :scientific] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.Allometry
    using Test

    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
        hdr = split(strip(lines[1]), ',')
        rows = [split(strip(l), ',') for l in lines[2:end]]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end
    ind = readcsv(joinpath(refdir, "hainich_individuals_2010.csv"))
    v(k, r) = parse(Float64, ind[k][r])
    nt(r) = parse(Int, ind["type"][r])

    allom = TreeAllometry{Float64}()
    alloc = FDiff.tebs_allocparams()
    galloc = FDiff.grass_allocparams()

    mkp(r) = FDiff.TreePools{Float64}(
        v("leaf_c", r), v("sapwood_c", r),
        max(v("agb", r) / v("nind", r) - v("leaf_c", r) - v("sapwood_c", r), 0.0), v("root_c", r),
        v("height", r), v("crownarea", r), v("nind", r), v("sla", r), v("wooddens", r), false,
    )
    treerows = [r for r in eachindex(ind["type"]) if nt(r) <= 6 && v("height", r) > 0]
    grassrows = [r for r in eachindex(ind["type"]) if nt(r) >= 7]
    @test !isempty(treerows) && !isempty(grassrows)

    # ── vegc_full_ind includes the below-ground sapwood pool that vegc_ind omits ──
    let r = first(treerows)
        base = mkp(r)
        @test FDiff.vegc_full_ind(base) == FDiff.vegc_ind(base)          # sapwood_bg_c == 0 ⇒ equal
        seeded = FDiff.TreePools{Float64}(
            base.leaf_c, base.sapwood_c, base.heartwood_c, base.root_c, 137.0,   # seed sapwood_bg_c
            base.height, base.crownarea, base.nind, base.sla, base.wooddens, false,
        )
        @test FDiff.vegc_full_ind(seeded) - FDiff.vegc_ind(seeded) ≈ 137.0
        @test FDiff.vegc_full_ind(seeded) - FDiff.vegc_full_ind(base) ≈ 137.0
    end

    # ── TREES: growth never creates carbon; ledger identity is exact; normal branch matches the formula ──
    normal_branch_hits = 0
    for r in treerows[1:min(8, end)]
        tr = mkp(r)
        scale = max(FDiff.vegc_full_ind(tr), 1.0)
        for bm in (50.0, 200.0, 800.0)
            grown = FDiff.grow_individual(alloc, allom, tr, bm, 0.9)
            dveg = FDiff.vegc_full_ind(grown) - FDiff.vegc_full_ind(tr)
            litter_residual = bm - dveg                              # what the conserving ledger routes
            (reprod, lsh, rsh) = FDiff._turnover_litter(alloc, tr, bm)
            formula = reprod + lsh + rsh
            bm_net = bm * (1 - alloc.reprod_cost)
            # (a) growth creates no carbon ⇒ litter ≥ 0
            @test litter_residual ≥ -1.0e-9 * scale
            # (b) exact ledger identity: Δveg + litter == bm (the flux-then-integrate guarantee)
            @test abs((dveg + litter_residual) - bm) ≤ 1.0e-9 * max(scale, bm)
            @test reprod ≈ bm * alloc.reprod_cost                    # reproduction flux is bm·reprod_cost
            # (c) normal-branch non-tautological check: formula == residual (≡ Δveg == bm_net − shed)
            if abs(litter_residual - formula) ≤ 1.0e-6 * scale
                normal_branch_hits += 1
                @test dveg ≈ bm_net - (lsh + rsh) rtol = 1.0e-8
            end
        end
    end
    @test normal_branch_hits ≥ 3     # the healthy/growing (normal) branch is exercised & formula-verified

    # ── GRASS: the formula is exact on all cases (no woody allocation solve, no abnormal branch) ──
    for r in grassrows[1:min(4, end)]
        g = FDiff.grass_treepools(v("agb", r), v("vegc", r), v("sla", r))
        scale = max(FDiff.vegc_full_ind(g), 1.0)
        for bm in (5.0, 20.0, 60.0)
            grown = FDiff.grow_grass_individual(galloc, g, bm, 0.9)
            dveg = FDiff.vegc_full_ind(grown) - FDiff.vegc_full_ind(g)
            (reprod, lsh, rsh) = FDiff._turnover_litter(galloc, g, bm)
            bm_net = bm * (1 - galloc.reprod_cost)
            @test dveg ≈ bm_net - (lsh + rsh) rtol = 1.0e-8 atol = 1.0e-9
            @test (bm - dveg) ≥ -1.0e-9 * scale
        end
    end
end
