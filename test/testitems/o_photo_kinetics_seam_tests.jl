# The temperature-only photosynthesis kinetics seam (`FDiff.photo_kinetics` + the `kin` kwarg on
# `FDiff.photosynthesis`) — line O's half of the split agreed with line M (ADR 0084 §5, ADR 0087).
#
# WHY THE SEAM EXISTS. `ko`/`kc`/`tau` — hence the two derived quantities the kernel actually consumes,
# `fac_kin` and `gammastar` — depend on `temp` ALONE: not on λ, not on `apar`, not on `vm`, not on the
# individual. The λ solve (`solve_lambda`) nevertheless re-evaluates them inside its residual closure on
# each of its ~78 kernel calls per individual-day, and the profile attributes 26.5 % of total runtime to
# the `^(::Float64,::Float64)` those three `q10^` calls dominate. Hoisting them is loop-invariant code
# motion: the SAME arithmetic, evaluated once instead of ~78 times.
#
# WHAT THIS FILE PINS, AND WHY IT IS THE WHOLE EQUIVALENCE ARGUMENT. The payoff is claimed with no
# fidelity risk on exactly one premise: that a caller passing a hoisted `kin` gets BITWISE the same four
# return values as the default path. That premise is what these assertions are. They use `===`, which on
# `Float64`/`Float32` is bit comparison (`0.0 === -0.0` is `false`), never `≈` — a tolerance here would
# defeat the purpose, because "bit-identical" is the property M's two-line hoist inside `solve_lambda`
# relies on and the reason no opt-in flag guards it (ADR 0138's reasoning: a flag nobody would ever
# switch off is maintenance cost).
#
# The first testitem freezes the pre-refactor arithmetic as a local copy, so a future edit to
# `photo_kinetics` that changes a value — rather than the seam — fails here with the operand printed,
# instead of surfacing as a moved ReferenceTests baseline three files away.
@testitem "photo_kinetics — bit-reproduces the pre-refactor inline kinetics" tags = [:validation, :fdiff, :structure] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff: PhotoParams, photo_kinetics
    using Test

    # The arithmetic as it stood inline in `photosynthesis` before the seam was factored out
    # (`photosynthesis.c:66-70`), operand for operand and in the same order.
    function kinetics_frozen(p::PhotoParams, temp)
        ko = p.ko25 * p.q10ko^((temp - 25) * 0.1)
        kc = p.kc25 * p.q10kc^((temp - 25) * 0.1)
        fac_kin = kc * (one(temp) + p.po2 / ko)
        tau = p.tau25 * p.q10tau^((temp - 25) * 0.1)
        gammastar = p.po2 / (2 * tau)
        return (fac_kin, gammastar)
    end

    for T in (Float64, Float32)
        p = PhotoParams{T}()
        # spans the physical range plus both tails the smooth gates run in
        for temp in T.(-40.0:2.5:55.0)
            got = photo_kinetics(p, temp)
            want = kinetics_frozen(p, temp)
            # `===` compares TYPE as well as bits, so each of these is simultaneously the bit-identity
            # check and the proof that the seam did not change the promotion behaviour pinned below.
            @test got[1] === want[1]
            @test got[2] === want[2]
        end
    end

    # ⚠ MEASURED, NOT ASSUMED, AND IT IS A PRE-EXISTING PROPERTY OF THE KERNEL — NOT OF THIS SEAM.
    # The kinetics COMPUTE IN Float64 EVEN FOR `PhotoParams{Float32}`: the exponent literal `0.1` is a
    # Float64, so `(temp - 25) * 0.1` promotes and `Float32 ^ Float64 -> Float64` carries it through every
    # downstream quantity. The frozen copy above — the arithmetic exactly as it stood BEFORE the seam —
    # returns the same Float64 bits (that is what the `===` above proves, since `===` is type-sensitive),
    # so the seam neither introduced nor removed this.
    #
    # It is pinned rather than asserted away because it bears on P4: `temp_stress` promotes the same way
    # with no involvement from this seam at all, and `photosynthesis` consequently returns all four values
    # as Float64 for a fully-Float32 call. The four existing "(SpeedyWeather-coupling type)" testitems gate
    # the Float32-ness of the OUTPUT STRUCTS, which convert on assignment — they do not gate the arithmetic.
    # If someone makes this kernel genuinely single-precision, THIS TEST SHOULD FAIL: that change moves
    # numbers and needs its own opt-in and its own re-measure (guardrail 4). See ADR 0087 §5.
    @test eltype(photo_kinetics(PhotoParams{Float64}(), 18.0)) === Float64
    @test eltype(photo_kinetics(PhotoParams{Float32}(), 18.0f0)) === Float64      # NOT Float32 — see above

    # `gammastar` (the CO2 compensation point) rises with temperature and `fac_kin` with it — a live
    # sanity check, so a seam that returned two constants could not pass on the identity alone.
    p = PhotoParams{Float64}()
    ks = [photo_kinetics(p, t) for t in (0.0, 15.0, 25.0, 40.0)]
    @test issorted(getindex.(ks, 2))
    @test issorted(getindex.(ks, 1))
    @test all(k -> k[1] > 0 && k[2] > 0, ks)
end

@testitem "photosynthesis — a hoisted `kin` is BITWISE the default path" tags = [:validation, :fdiff, :structure] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams, photo_kinetics, photosynthesis,
        temp_stress
    using Test

    # Both photosynthetic pathways, and the SLA-capped Vcmax branch that LPJmL-FIT's `individual:true`
    # mode actually runs (`issla = true`), since the cap reads `temp` too.
    paramsets = [
        PhotoParams{Float64}(; path = :c3),
        PhotoParams{Float64}(; path = :c4),
        PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.01986),
        PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.03),
    ]
    tsp = TempStressParams{Float64}()
    co2_Pa = 40.0

    n = 0
    for p in paramsets, temp in (-15.0, 0.0, 7.5, 20.0, 27.5, 40.0), dl in (4.0, 12.0, 20.0)
        ts = temp_stress(tsp, temp, dl)
        kin = photo_kinetics(p, temp)           # hoisted ONCE per temperature, as `solve_lambda` will
        for λ in (0.02, 0.2, 0.4, 0.7, 0.85), apar in (0.0, 1.0e4, 2.0e6)
            # (a) the Vcmax pass (`comp_vm = true`, the C's `gp_sum` call)
            a = photosynthesis(p, λ, ts, co2_Pa, temp, apar, dl; comp_vm = true)
            b = photosynthesis(p, λ, ts, co2_Pa, temp, apar, dl; comp_vm = true, kin = kin)
            @test all(a .=== b)
            # (b) the λ-residual pass (`comp_vm = false`) at the Vcmax the first pass produced — this is
            #     the call the hoist is FOR, reached ~78 times per individual-day through `g(λ)`.
            vm = a[3]
            c = photosynthesis(p, λ, ts, co2_Pa, temp, apar, dl; comp_vm = false, vm = vm)
            d = photosynthesis(p, λ, ts, co2_Pa, temp, apar, dl; comp_vm = false, vm = vm, kin = kin)
            @test all(c .=== d)
            # (c) the learned-Vcmax hook must not interact with the seam either (FluxHooks, `vm_scale`)
            e = photosynthesis(p, λ, ts, co2_Pa, temp, apar, dl; comp_vm = true, vm_scale = 1.37)
            f = photosynthesis(p, λ, ts, co2_Pa, temp, apar, dl; comp_vm = true, vm_scale = 1.37, kin = kin)
            @test all(e .=== f)
            n += 3
        end
    end
    @test n == length(paramsets) * 6 * 3 * 5 * 3 * 3      # the sweep really ran, all of it

    # Float32 params (the SpeedyWeather-coupling type): the seam must be bit-identical here too — and note
    # what the kernel actually returns. `temp_stress` is already Float64 for Float32 inputs WITHOUT this
    # seam being involved, and all four returns follow, so a Float32-parameterised call computes in double
    # precision throughout. Pinned, with the reasoning, in the first testitem and in ADR 0087 §5.
    p32 = PhotoParams{Float32}(; issla = true, sla = 0.01986f0)
    ts32 = temp_stress(TempStressParams{Float32}(), 18.0f0, 13.0f0)
    a32 = photosynthesis(p32, 0.7f0, ts32, 40.0f0, 18.0f0, 1.0f6, 13.0f0; comp_vm = true)
    b32 = photosynthesis(
        p32, 0.7f0, ts32, 40.0f0, 18.0f0, 1.0f6, 13.0f0;
        comp_vm = true, kin = photo_kinetics(p32, 18.0f0)
    )
    @test all(a32 .=== b32)                      # the seam: bit-identical, types included
    @test all(x -> x isa Float64, a32)           # NOT Float32 — the kernel's own promotion, pre-existing
end
