# Gate — PROGNOSTIC below-ground wood (ADR 0132; the deferred `docs/notes/sapwood_bg_design.md` §5.4 step,
# amended by ADR 0127 §6). `sapwood_bg` was seeded and static: it paid maintenance respiration but never
# grew, so the C's below-ground wood SINK — the carbon `allocation_tree.c:268-277` deducts from the
# assimilate before the leaf/root/sapwood split — landed in F's ABOVE-ground sapwood instead, which is
# exactly the pool `agb_ind` reports. This step makes the pool prognostic, and it needs the SECOND pool
# `heartwood_bg_c`: `turnover_tree.c:124-130` moves `sapwood_bg·turnover.sapwood` into it every year, and a
# one-field port would have to destroy that carbon (a leak, and conservation is a CI gate — guardrail 2)
# or charge it maintenance respiration the C does not charge.
#
# What this gate locks in, all against the committed Hainich 2010 structure (no HPC dependency):
#  (a) `bg_growth=false` is byte-identical, and so is `bg_growth=true` on an UNSEEDED roster (the C's own
#      `allocation_tree.c:206` gate grows nothing while the pool is 0) — guardrail 4, twice over;
#  (b) the PINNING identity: after growth `sapwood_bg_c` equals the C_LATERAL demand at this year's
#      post-turnover sapwood, and `heartwood_bg_c` gained exactly `turnover_sapwood ·` the pool it started
#      the year with;
#  (c) CONSERVATION: the port only REDISTRIBUTES — total `vegc_full_ind` is identical between the on and
#      off arms, so the carbon the below-ground bucket gains is exactly the carbon the rest of the tree
#      did not get. This is the assertion that makes the second pool non-optional;
#  (d) the CLOSED FORM `D = c·leaf_c·sla·wooddens/k_latosa` for a pipe-model-consistent stem (`c` a pure
#      soil-geometry constant), from which the annual sink is `∝ (leaf_y − (1−r)·leaf_{y−1})`;
#  (e) the SEED RULE that follows from (d) and is the whole reason the sink can read as zero: seeding at
#      the bare demand makes the pool and the demand shrink in lockstep and the top-up is EXACTLY 0;
#      `FDiff.sapwood_bg_seed`'s `(1−r)·D` is what a stem in the C actually holds and charges the honest
#      steady-state sink instead.
@testitem "sapwood_bg growth — the C_LATERAL sink is prognostic, conserving, and paid on leaf growth" tags = [:validation, :fdiff, :conservation] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.Allometry
    using Test
    import LPJmLFITEmulator.FDiff: TreePools, grow_individual, tebs_allocparams, reconstruct_sapwood_bg,
        sapwood_bg_seed, vegc_full_ind, vegc_ind, agb_ind

    refdir = joinpath(@__DIR__, "references")
    function readsoil(path)
        dz = Float64[]; rd = Float64[]
        for ln in eachline(path)
            s = strip(ln)
            (isempty(s) || startswith(s, "#")) && continue
            v = parse.(Float64, split(s))
            push!(dz, v[2]); push!(rd, v[4])
        end
        return (dz, rd)
    end
    (soildepth, rootdist) = readsoil(joinpath(refdir, "hainich_soilcolumn.txt"))
    @test length(soildepth) == length(rootdist) > 0

    alloc = tebs_allocparams()
    allom = Allometry.TreeAllometry{Float64}()
    r_sap = alloc.turnover_sapwood                      # 0.04 = 1/25 yr

    mk(sbg, hbg; leaf = 3000.0, sap = 40000.0, h = 25.0) = TreePools{Float64}(
        leaf, sap, 120000.0, 3000.0, sbg, hbg, h, 20.0, 0.02, 0.0198, 2.0e5, 0.0, 0.0, false,
    )
    gi(t, bm; on = false) = grow_individual(
        alloc, allom, t, bm, 0.9;
        bg_growth = on, bg_rootdist = (on ? rootdist : Float64[]), bg_soildepth = (on ? soildepth : Float64[]),
    )

    # ── (a) guardrail 4: default off is byte-identical, and ON is a no-op on an unseeded pool ──────────
    t_unseeded = mk(0.0, 0.0)
    base = grow_individual(alloc, allom, t_unseeded, 900.0, 0.9)          # the pre-ADR-0132 call, verbatim
    @test gi(t_unseeded, 900.0; on = false) == base
    @test gi(t_unseeded, 900.0; on = true) == base                        # allocation_tree.c:206 gate
    # a grass row is untouched by either (no woody sapwood)
    grass = TreePools{Float64}(50.0, 0.0, 0.0, 50.0, 0.0, 1.0, 1.0, 100.0, 0.03, 0.0, true)
    @test grass.sapwood_bg_c == 0.0 && grass.heartwood_bg_c == 0.0

    # ── (d) the closed form: the demand is PROPORTIONAL TO LEAF CARBON for a pipe-consistent stem ──────
    #     D = c·S/H  and the pipe model gives S/H = leaf·sla·wooddens/k_latosa.
    (sla, wd) = (0.0198, 2.0e5)
    cgeom = reconstruct_sapwood_bg(40000.0, 25.0, wd, rootdist, soildepth) * 25.0 / 40000.0
    @test cgeom > 0
    for leaf in (1500.0, 3000.0, 6000.0)
        sapw = 40000.0
        hpipe = allom.k_latosa * sapw / (leaf * sla * wd)                  # pipe-model height for this leaf
        @test reconstruct_sapwood_bg(sapw, hpipe, wd, rootdist, soildepth) ≈
            cgeom * leaf * sla * wd / allom.k_latosa rtol = 1.0e-12
    end

    # ── (e) THE SEED RULE — the finding this gate exists to pin down ───────────────────────────────────
    #  seeding at the bare demand D: post-turnover pool (1−r)·D vs a demand recomputed on the same
    #  shrunken sapwood, also (1−r)·D ⇒ the top-up is EXACTLY zero and the sink vanishes.
    dmd0 = reconstruct_sapwood_bg(40000.0, 25.0, wd, rootdist, soildepth)
    naive = gi(mk(dmd0, 0.0), 5.0e4; on = true)
    @test naive.sapwood_bg_c + naive.heartwood_bg_c ≈ dmd0 rtol = 1.0e-14 # bucket unchanged: no top-up at all
    @test naive.sapwood_bg_c ≈ (1 - r_sap) * dmd0 rtol = 1.0e-12
    #  seeding at what a stem in the C actually HOLDS, (1−r)·D, charges the honest steady-state sink.
    seed = sapwood_bg_seed(alloc, 40000.0, 25.0, wd, rootdist, soildepth)
    @test seed ≈ (1 - r_sap) * dmd0 rtol = 1.0e-14
    fair = gi(mk(seed, 0.0), 5.0e4; on = true)
    @test fair.sapwood_bg_c + fair.heartwood_bg_c > seed                  # the sink is real
    @test fair.sapwood_bg_c + fair.heartwood_bg_c - seed ≈ (1 - r_sap) * r_sap * dmd0 rtol = 1.0e-10

    # ── (b) the PINNING identity + the below-ground turnover, on an ample assimilate ───────────────────
    t0 = mk(seed, 0.0)
    on = gi(t0, 5.0e4; on = true)
    sm_post = 40000.0 * (1 - r_sap)                                        # turnover_tree runs before allocation
    @test on.sapwood_bg_c ≈ reconstruct_sapwood_bg(sm_post, 25.0, wd, rootdist, soildepth) rtol = 1.0e-12
    @test on.heartwood_bg_c ≈ r_sap * seed rtol = 1.0e-12                  # turnover_tree.c:126,135
    #  the sink pool only ever accumulates — it never respires and never leaves the plant
    on2 = gi(on, 5.0e4; on = true)
    @test on2.heartwood_bg_c > on.heartwood_bg_c

    # ── (c) CONSERVATION: the port redistributes, it does not create or destroy ────────────────────────
    off = gi(t0, 5.0e4; on = false)
    @test vegc_full_ind(on) ≈ vegc_full_ind(off) rtol = 1.0e-12            # identical TOTAL vegetation carbon
    @test vegc_ind(on) < vegc_ind(off)                                     # …but less of it above ground + roots
    moved = (on.sapwood_bg_c + on.heartwood_bg_c) - (off.sapwood_bg_c + off.heartwood_bg_c)
    @test moved ≈ vegc_ind(off) - vegc_ind(on) rtol = 1.0e-10              # exactly the carbon withheld
    @test agb_ind(on) < agb_ind(off)                                       # the channel ADR 0127 measured
    #  `vegc_ind` deliberately EXCLUDES both below-ground WOOD pools (it already carries the fine root);
    #  `vegc_full_ind` is the C's own `vegc` pool set (`veg_sum_tree.c:25`).
    @test vegc_full_ind(on) - vegc_ind(on) ≈ on.sapwood_bg_c + on.heartwood_bg_c rtol = 1.0e-12

    # ── the whole committed Hainich roster: conserving everywhere, and the sink is not negligible ──────
    lines = readlines(joinpath(refdir, "hainich_individuals_2010.csv"))
    i0 = findfirst(l -> !startswith(strip(l), "#") && !isempty(strip(l)), lines)
    hdr = split(strip(lines[i0]), ',')
    rows = [split(strip(l), ',') for l in lines[(i0 + 1):end] if !isempty(strip(l))]
    cols(k) = [parse(Float64, r[findfirst(==(k), hdr)]) for r in rows]
    (lc, sc, rc, ht) = (cols("leaf_c"), cols("sapwood_c"), cols("root_c"), cols("height"))
    (ca, nd, sl, wdc) = (cols("crownarea"), cols("nind"), cols("sla"), cols("wooddens"))
    hc = max.(cols("agb") ./ nd .- lc .- sc, 0.0)
    typ = Int.(cols("type"))
    npatch = 25

    pool_m2 = 0.0; sink_m2 = 0.0; ntree = 0; nfired = 0
    for i in eachindex(lc)
        typ[i] <= 6 || continue
        ntree += 1
        s0 = sapwood_bg_seed(alloc, sc[i], ht[i], wdc[i], rootdist, soildepth)
        tr = TreePools{Float64}(lc[i], sc[i], hc[i], rc[i], s0, 0.0, ht[i], ca[i], nd[i], sl[i], wdc[i], 0.0, 0.0, false)
        bm = 400.0 * ca[i]
        a = gi(tr, bm; on = false)
        b = gi(tr, bm; on = true)
        @test vegc_full_ind(b) ≈ vegc_full_ind(a) rtol = 1.0e-10           # conserving on every real stem
        buck = b.sapwood_bg_c + b.heartwood_bg_c
        @test buck >= s0 - 1.0e-9                                          # the bucket never shrinks
        buck > s0 + 1.0e-9 && (nfired += 1)
        pool_m2 += s0 * nd[i]; sink_m2 += (buck - s0) * nd[i]
    end
    @test ntree == 272
    @test pool_m2 / npatch ≈ 510.1 atol = 0.2                              # = (1−r)·the 531.4 gC/m² of §8
    @test 0.6 * ntree < nfired < ntree                                     # most stems top up; some are C-limited
    @test sink_m2 / npatch > 1.0                                           # a real, non-trivial annual sink
end
