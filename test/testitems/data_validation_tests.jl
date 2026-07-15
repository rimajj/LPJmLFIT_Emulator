# Gate 6 — Data validation (ENGINEERING_STANDARDS §2, item 6).
# `checkdims` enforces the frozen SharedState array shapes (the schema/shape gate). Well-formed
# states pass; malformed states are rejected with DimensionMismatch.
@testitem "Data validation" tags=[:validation] begin
    using LPJmLFITEmulator
    using Test

    # Well-formed state passes (returns true).
    good = SharedState{Float64}()
    @test LPJmLFITEmulator.checkdims(good) === true

    # Malformed: wrong-length enthalpy vector (must be NHEATGRIDP) ⟹ DimensionMismatch.
    bad_enth = SharedState{Float64}(; enth = zeros(Float64, NHEATGRIDP - 1))
    @test_throws DimensionMismatch LPJmLFITEmulator.checkdims(bad_enth)

    # Malformed: wrong-length soil-water vector (must be NSOILLAYER) ⟹ DimensionMismatch.
    bad_w = SharedState{Float64}(; w = zeros(Float64, NSOILLAYER + 3))
    @test_throws DimensionMismatch LPJmLFITEmulator.checkdims(bad_w)

    # Shapes hold for both supported float precisions.
    @test LPJmLFITEmulator.checkdims(SharedState{Float32}()) === true
end
