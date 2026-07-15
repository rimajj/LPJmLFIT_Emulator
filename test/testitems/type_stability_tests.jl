# Gate 9 — Type stability & shapes (ENGINEERING_STANDARDS §2, item 9).
# The conservation kernels are inference-stable (`@inferred`); SharedState constructs for both
# Float32 and Float64. (The full @test_opt / JET battery across batch sizes lands with the
# components; the package-wide JET pass lives in `test/jet.jl`.)
@testitem "Type stability" tags=[:types] begin
    using LPJmLFITEmulator
    using Test

    # Positional kernels: return type matches the compiler's inference.
    @test @inferred(softmax_partition([1.0, 2.0, 3.0])) isa Vector{Float64}
    @test @inferred(softmax_partition(Float32[1, 2, 3])) isa Vector{Float32}
    @test @inferred(latent_heat(1.0)) isa Float64
    @test @inferred(latent_heat(2.5)) isa Float64
    @test @inferred(flux_then_integrate([1.0, 2.0], [0.5, -3.0])) isa Vector{Float64}

    # Keyword-only helpers: wrap in a nullary closure (robust `@inferred` on kwargs).
    carbres() = carbon_budget_residual(; npp = 1.0, rh = 0.5, firec = 0.1, flux_estabc = 0.2, dC = 0.6)
    watres()  = water_budget_residual(; prec = 1.0, et = 0.4, runoff = 0.3, drainage = 0.2, dstorage = 0.1)
    @test @inferred(carbres()) isa Float64
    @test @inferred(watres()) isa Float64

    # Both float precisions construct with the frozen shapes.
    s64 = SharedState{Float64}()
    s32 = SharedState{Float32}()
    @test s64 isa SharedState{Float64}
    @test s32 isa SharedState{Float32}
    @test eltype(s32.w) === Float32
    @test eltype(s64.enth) === Float64
end
