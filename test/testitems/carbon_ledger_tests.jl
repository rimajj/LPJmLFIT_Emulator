# P1 Step 2 (docs/p1_s_in_loop_design.md §4) — the flux-then-integrate carbon LEDGER that makes the S↔F
# demographic handoff conserve. When S changes the population (establishment / mortality / K-cap merge),
# every carbon movement is routed as an accounted flux through a `CarbonLedger`, so total carbon
# (vegetation + litter) is created/destroyed ONLY by the external influxes (applied NPP + establishment).
# This gate exercises each demographic operation on a small tree+grass population — INCLUDING a cohort
# with a SEEDED below-ground `sapwood_bg_c` pool — and asserts:
#   • internal moves (mortality, merge) leave total carbon (C_veg + litter) invariant to machine precision;
#   • external influxes (growth-applied NPP, establishment) raise total carbon by exactly the influx;
#   • `handoff_carbon_residual` closes to ≤ 1e-6·scale after a full mixed year.
# The load-bearing subtlety: mortality carbon MUST be routed on `vegc_full_ind` (incl. sapwood_bg_c) — on
# `vegc_ind` it would silently leak the seeded pool. The test asserts the leak's magnitude to document it.

@testitem "Carbon ledger — S↔F demographic handoff conserves (establish/kill/merge, seeded sapwood_bg)" tags = [:conservation, :coupling, :scientific] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using Test

    TP = FDiff.TreePools{Float64}
    vfull = FDiff.vegc_full_ind
    pop_vegc(pools) = sum(vfull(p) * p.nind for p in pools)   # total vegetation C, gC/m²

    # population: two beech trees (cohort 1 carries a SEEDED sapwood_bg pool) + one grass cohort
    #            (leaf, sap,  heart,  root, sapwood_bg, height, crown, nind,  sla,  wd, is_grass)
    t1 = TP(3000.0, 8000.0, 15000.0, 2000.0, 250.0, 20.0, 30.0, 0.05, 0.02, 2.0e5, false)
    t2 = TP(2200.0, 5000.0, 9000.0, 1500.0, 0.0, 16.0, 22.0, 0.08, 0.02, 2.0e5, false)
    g1 = FDiff.grass_treepools(120.0, 300.0, 0.0422)          # grass: leaf=agb, root=vegc-agb, no woody pools
    pools = FDiff.TreePools{Float64}[t1, t2, g1]

    led = CarbonLedger()
    @test led isa CarbonLedger{Float64}
    @test led.litter_total == 0.0

    # seeded pool is real and NOT in vegc_ind — routing mortality on vegc_ind would leak exactly this:
    @test vfull(t1) - FDiff.vegc_ind(t1) ≈ 250.0
    @test vfull(t2) == FDiff.vegc_ind(t2)                     # unseeded ⇒ equal

    ctot(pools, led) = pop_vegc(pools) + led.litter_total     # total ecosystem carbon (veg + litter)
    cveg0 = pop_vegc(pools)
    scale = max(cveg0, 1.0)

    # ── OP 1 — GROWTH (external influx): F integrates NPP into pools + sheds turnover litter ──
    c_before = ctot(pools, led)
    applied_bm = 900.0                                        # gC/m² integrated into pools this year
    litterfall = 260.0                                        # gC/m² turnover litterfall
    # F grew cohort 1 by Δvegc_full·nind1 = applied_bm − litterfall (leaf pool bumped)
    Δper_ind = (applied_bm - litterfall) / pools[1].nind
    pools[1] = TP(
        pools[1].leaf_c + Δper_ind, pools[1].sapwood_c, pools[1].heartwood_c, pools[1].root_c,
        pools[1].sapwood_bg_c, pools[1].height, pools[1].crownarea, pools[1].nind, pools[1].sla, pools[1].wooddens, false,
    )
    record_growth!(led, applied_bm, 0.0)
    record_litter!(led, litterfall)
    @test ctot(pools, led) - c_before ≈ applied_bm rtol = 1.0e-12   # total C rises by exactly the applied NPP

    # ── OP 2 — MORTALITY (internal veg→litter): kill Δnind from the SEEDED cohort ──
    c_before = ctot(pools, led)
    dn = 0.02
    moved = vfull(pools[1]) * dn                              # routed on vegc_full ⇒ includes sapwood_bg
    record_litter!(led, moved)
    pools[1] = TP(
        pools[1].leaf_c, pools[1].sapwood_c, pools[1].heartwood_c, pools[1].root_c, pools[1].sapwood_bg_c,
        pools[1].height, pools[1].crownarea, pools[1].nind - dn, pools[1].sla, pools[1].wooddens, false,
    )
    @test ctot(pools, led) ≈ c_before rtol = 1.0e-12          # INTERNAL move ⇒ total C invariant
    # had we routed on vegc_ind, we'd have moved `moved − sapwood_bg·dn` and leaked this much:
    @test (vfull(pools[1]) - FDiff.vegc_ind(pools[1])) * 1.0 > 0.0

    # ── OP 3 — ESTABLISHMENT (external influx): append an age-0 sapling cohort ──
    c_before = ctot(pools, led)
    sap = FDiff.grass_treepools(2.37, 5.33, 0.0422)           # a fixed-carbon grass sapling (nind = 1 per-area)
    push!(pools, sap)
    estab_c = vfull(sap) * sap.nind
    record_estab!(led, estab_c)
    @test ctot(pools, led) - c_before ≈ estab_c rtol = 1.0e-12   # total C rises by exactly flux_estabc

    # ── OP 4 — K-CAP MERGE (internal): merge the two tree cohorts, mass-conserving ──
    c_before = ctot(pools, led)
    a, b = pools[1], pools[2]
    n = a.nind + b.nind
    wsum(fa, fb) = (fa * a.nind + fb * b.nind) / n            # per-individual mass-weighted pools
    merged = TP(
        wsum(a.leaf_c, b.leaf_c), wsum(a.sapwood_c, b.sapwood_c), wsum(a.heartwood_c, b.heartwood_c),
        wsum(a.root_c, b.root_c), wsum(a.sapwood_bg_c, b.sapwood_bg_c),
        wsum(a.height, b.height), wsum(a.crownarea, b.crownarea), n, a.sla, a.wooddens, false,
    )
    pools = FDiff.TreePools{Float64}[merged, pools[3], pools[4]]
    @test ctot(pools, led) ≈ c_before rtol = 1.0e-12          # mass-weighted merge ⇒ total C invariant

    # ── FULL-YEAR CLOSURE: Δ(C_veg) + litter_year == applied_bm + estab (to 1e-6·scale) ──
    cveg_end = pop_vegc(pools)
    resid = handoff_carbon_residual(led; c_veg_delta = cveg_end - cveg0)
    @test abs(resid) ≤ 1.0e-6 * scale
    @test led.litter_year ≈ litterfall + moved rtol = 1.0e-12
    @test led.applied_bm_year == applied_bm
    @test led.estab_year ≈ estab_c

    # reset_year! zeros the tallies, keeps the running litter_total
    lt = led.litter_total
    reset_year!(led)
    @test led.litter_year == 0.0 && led.applied_bm_year == 0.0 && led.estab_year == 0.0
    @test led.litter_total == lt
end
