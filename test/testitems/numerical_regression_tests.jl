# Gate 3 — Numerical regression (ENGINEERING_STANDARDS §2 item 3; ADR 0014 step 6).
# Committed baselines catch silent numerical drift after refactors. F_diff pins its annual totals on
# a FIXED deterministic scenario against `references/fdiff_annual_totals.txt`.
#
# NB on "reproduce the F1 (C-binary) daily outputs": a full quantitative match to the LPJmL-FIT C
# binary needs the binary's EXACT forcing (real petpar radiation), soil parameters, and per-PFT
# constants — a scale-up item (see docs/phase3_fdiff_spike.md). This spike's regression gate pins
# F_diff against ITSELF (drift alarm) and validates physical closure/plausibility; the C-binary
# cross-check is documented as the next validation step, with the 186 GB daily dataset as the target.
@testitem "Numerical regression — softmax closed form" tags = [:regression] begin
    using LPJmLFITEmulator
    using Test

    @test softmax_partition([0.0, 0.0, 0.0]) ≈ fill(1 / 3, 3)
    # softmax(log.(w)) == w ./ sum(w): logits = log([1,2,3]) ⟹ fractions = [1,2,3]/6 exactly.
    @test softmax_partition(log.([1.0, 2.0, 3.0])) ≈ [1.0, 2.0, 3.0] ./ 6
end

@testitem "Numerical regression — F_diff annual totals baseline" tags = [:regression, :fdiff] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using Test

    # FIXED deterministic scenario — MUST match references/fdiff_annual_totals.txt.
    str = Structure{Float64}(lai = 4.0, fpc = 0.8, albedo = 0.15, phen = 1.0, whc = 200.0, k_beer = 0.5)
    forc = [
        DailyForcing{Float64}(
                swdown = 150 + 120 * sin(2π * (d - 80) / 365), lwnet = -40.0,
                temp = 15 + 12 * sin(2π * (d - 110) / 365), precip = d % 3 == 0 ? 6.0 : 0.5,
                daylength = 12 + 4 * sin(2π * (d - 80) / 365), co2 = 380.0
            ) for d in 1:365
    ]
    (_, tot) = rollout(FDiffParams{Float64}(), FDiffState{Float64}(w = 0.6), str, forc)

    # ── committed baseline (drift alarm) ────────────────────────────────────────────────────────
    ref = Dict{String, Float64}()
    for ln in eachline(joinpath(@__DIR__, "references", "fdiff_annual_totals.txt"))
        (isempty(ln) || startswith(strip(ln), "#")) && continue
        k, v = split(ln)
        ref[k] = parse(Float64, v)
    end
    @test tot.npp ≈ ref["npp"] rtol = 1.0e-5
    @test tot.gpp ≈ ref["gpp"] rtol = 1.0e-5
    @test tot.transp ≈ ref["transp"] rtol = 1.0e-5
    @test tot.evap ≈ ref["evap"] rtol = 1.0e-5
    @test tot.runoff ≈ ref["runoff"] rtol = 1.0e-5
    @test tot.precip ≈ ref["precip"] rtol = 1.0e-12

    # ── physical validity (not just drift) ──────────────────────────────────────────────────────
    @test all(isfinite, (tot.npp, tot.gpp, tot.transp, tot.evap, tot.runoff))
    @test 0.1 < tot.npp / tot.gpp < 0.6            # NPP is a plausible fraction of GPP
    @test tot.transp ≥ 0 && tot.evap ≥ 0
    # annual water balance: precip − (ET + runoff) = Δstorage (soil + snow), which is BOUNDED by the
    # storage capacity — it is not zero (the soil fills over the year). Per-day EXACT closure incl.
    # Δstorage is asserted in fdiff_physics_tests.jl; here we bound the annual storage change.
    @test abs(tot.precip - (tot.transp + tot.evap + tot.runoff)) < str.whc + 100.0
end
