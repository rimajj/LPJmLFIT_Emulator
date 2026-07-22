# Component E — surface-energy-balance + skin-temperature closure (Phase 4; ADR 0017). The Phase-4 gate
# (DEVELOPMENT_PLAN §6): energy CLOSES (Rn = LE + H + G to machine precision, by construction — H is the
# residual) and LE/H/T_skin are physically plausible. LE is fixed by F (water-limited); E solves ONE
# skin temperature and partitions the available energy. These gates exercise the self-contained solver
# `solve_seb` + the `SEBEnergyClosure` `solve!` handoff (no Terrarium dependency; DEVELOPMENT_PLAN §2.4).

@testitem "Component E — energy closes by construction (Rn = LE + H + G)" tags = [:energy, :scientific] begin
    using LPJmLFITEmulator
    using Test

    p = SEBParams{Float64}()
    # A broad grid of day/night, cold/hot, calm/windy, forest/grass, wet/dry-demand conditions.
    for swdown in (0.0, 150.0, 500.0, 900.0),
            lwdown in (220.0, 320.0, 400.0),
            tair in (263.15, 283.15, 298.15, 308.15),
            wind in (0.2, 2.0, 8.0),
            (z0, height) in ((0.05, 0.5), (0.5, 5.0), (2.5, 25.0)),
            le in (0.0, 50.0, 250.0, 800.0),
            albedo in (0.12, 0.25)

        t_soil = tair - 3.0
        (Ts, Rn, H, G, le_out, ga, capped) =
            solve_seb(p, swdown, lwdown, tair, 1.0e5, wind, albedo, z0, height, le, t_soil)

        # 1) closure to machine precision — the HARD Phase-4 gate
        @test isapprox(Rn, le_out + H + G; atol = 1.0e-6, rtol = 0)
        # 2) everything finite
        @test all(isfinite, (Ts, Rn, H, G, le_out, ga))
        # 3) latent heat is non-negative and, uncapped (the default), passes through unchanged from F
        @test le_out ≥ -1.0e-9
        @test !capped
        @test isapprox(le_out, le; atol = 1.0e-9)
        # 4) H is the aerodynamic residual: H = ρ c_p g_a (T_skin − Tair). With the stability correction
        #    on, g_a and T_skin are solved by a Picard-coupled Newton, so this identity holds to the
        #    SOLVE tolerance (relative ~1e-8), not machine precision — unlike the closure above, which is
        #    exact by construction (H := Rn − LE − G). Use a convergence-appropriate relative tolerance.
        ρ = 1.0e5 / (p.R_d * tair)
        H_aero = ρ * p.c_p * ga * (Ts - tair)
        @test isapprox(H, H_aero; atol = 1.0e-4, rtol = 1.0e-6)
    end
end

@testitem "Component E — demand cap (opt-in) pins LE to available energy" tags = [:energy, :scientific] begin
    using LPJmLFITEmulator
    using Test

    # Cap OFF by default: F's water-limited LE passes through, H is the pure residual (may be negative
    # when Rn − G < 0). Cap ON (opt-in): in a demand-limited DAY (LE > Rn − G > 0), LE is pinned to the
    # available energy and H → 0; closure still exact. (v1 keeps it off — the unused-water return to F
    # is not wired, so capping would drop water; this gate proves the mechanism is correct when enabled.)
    p_off = SEBParams{Float64}()
    p_on = SEBParams{Float64}(enable_cap = true)
    # a hot dry afternoon where the evaporative demand exceeds available energy
    args = (900.0, 380.0, 305.15, 1.0e5, 2.0, 0.15, 2.5, 25.0, 700.0, 304.0)
    (_, Rn0, H0, G0, le0, _, cap0) = solve_seb(p_off, args...)
    @test !cap0
    @test isapprox(le0, 700.0)                                 # uncapped: F's LE passes through
    @test isapprox(Rn0, le0 + H0 + G0; atol = 1.0e-6)          # closes with H possibly < 0

    (_, Rn1, H1, G1, le1, _, cap1) = solve_seb(p_on, args...)
    @test cap1
    @test isapprox(le1, Rn1 - G1; atol = 1.0e-6)               # LE pinned to available energy
    @test isapprox(H1, 0.0; atol = 1.0e-6)                     # sensible heat → 0
    @test isapprox(Rn1, le1 + H1 + G1; atol = 1.0e-6)          # still closes exactly
    @test le1 < le0                                            # capped below F's demand
end

@testitem "Component E — physical plausibility (day heating, night cooling, bounds)" tags = [:energy, :scientific] begin
    using LPJmLFITEmulator
    using Test

    p = SEBParams{Float64}()

    # Midday, moderate LE: skin temperature above air, positive Rn, positive sensible heat.
    (Ts_day, Rn_day, H_day, _, _, _, _) =
        solve_seb(p, 700.0, 350.0, 298.15, 1.0e5, 3.0, 0.15, 2.5, 25.0, 250.0, 296.15)
    @test Rn_day > 0
    @test Ts_day > 298.15                     # daytime surface warmer than air
    @test H_day > 0                            # sensible heat leaves the surface
    @test abs(Ts_day - 298.15) < 15.0          # skin stays near air (well-coupled forest)

    # Clear calm night, no shortwave: radiative cooling ⇒ skin BELOW air, negative Rn, downward H.
    (Ts_night, Rn_night, H_night, _, _, _, _) =
        solve_seb(p, 0.0, 300.0, 288.15, 1.0e5, 1.0, 0.15, 2.5, 25.0, 5.0, 289.15)
    @test Rn_night < 0
    @test Ts_night < 288.15                    # nighttime surface cooler than air
    @test H_night < 0                          # sensible heat toward the surface

    # Short smooth vegetation (grass) couples less to the air than a rough forest ⇒ larger day-time
    # skin–air difference at identical forcing (a real, well-known effect).
    (Ts_grass, _, _, _, _, ga_grass, _) =
        solve_seb(p, 700.0, 350.0, 298.15, 1.0e5, 3.0, 0.2, 0.05, 0.5, 250.0, 296.15)
    (Ts_forest, _, _, _, _, ga_forest, _) =
        solve_seb(p, 700.0, 350.0, 298.15, 1.0e5, 3.0, 0.2, 2.5, 25.0, 250.0, 296.15)
    @test ga_forest > ga_grass                 # rougher canopy is better coupled
    @test (Ts_grass - 298.15) > (Ts_forest - 298.15)
end

@testitem "Component E — aerodynamic conductance monotonicity + bounds" tags = [:energy, :unit] begin
    using LPJmLFITEmulator
    using Test

    p = SEBParams{Float64}()
    # g_a increases with wind speed, at fixed roughness/height.
    gas = [aerodynamic_conductance(p, u, 0.5, 5.0) for u in (0.5, 1.0, 2.0, 4.0, 8.0)]
    @test issorted(gas)
    @test all(g -> p.ga_min ≤ g ≤ p.ga_max, gas)
    # g_a increases with roughness (rougher surface, stronger turbulent exchange), at fixed wind.
    gz = [aerodynamic_conductance(p, 3.0, z0, 10.0 * z0 / 0.1) for z0 in (0.02, 0.1, 0.5, 2.5)]
    @test issorted(gz)
    # never divides-by-zero or goes non-finite even for a tall canopy at low reference height
    @test isfinite(aerodynamic_conductance(p, 3.0, 5.0, 40.0))
    @test aerodynamic_conductance(p, 0.0, 0.5, 5.0) ≥ p.ga_min   # wind floor
end

@testitem "Component E — solve! handoff (EToATM/EToF, NBP, feedback)" tags = [:energy, :unit] begin
    using LPJmLFITEmulator
    using Test

    clo = SEBEnergyClosure(; t_soil0 = 283.15)
    st = SharedState()
    ff = FToE(le = 250.0, gpp = 8.0, npp = 4.0, rh = 1.5, firec = 0.2, flux_estabc = 0.1, ground_heat = 0.0)
    bc = SToE(albedo = 0.15, z0 = 2.5, lai = 4.0, height = 25.0)
    forc = AtmForcing(
        swdown = 700.0, lwdown = 350.0, tair = 298.15, qair = 0.008,
        wind = 3.0, psurf = 1.0e5, precip = 0.0, co2 = 400.0
    )

    atm, tof = solve!(clo, st, ff, bc, forc)
    @test atm isa EToATM && tof isa EToF
    # E→ATM carries the closed partition + the diagnostic NBP_atm = Rh + firec − NPP − estab
    @test isapprox(atm.nbp_atm, nbp_atm(rh = 1.5, firec = 0.2, npp = 4.0, flux_estabc = 0.1); atol = 1.0e-12)
    @test atm.z0 == 2.5
    # E→F feedback is self-consistent: same skin temperature + ground heat handed back to F
    @test tof.t_skin == atm.t_skin
    @test tof.ground_heat == atm.g
    @test tof.g_a > 0
    # deep-soil temperature EWMA has advanced one step from its 283.15 K seed TOWARD the air temp (298.15)
    @test clo.initialized
    @test 283.15 < clo.t_soil < 298.15
    @test isapprox(clo.t_soil, (29 / 30) * 283.15 + (1 / 30) * 298.15; atol = 1.0e-9)
end

@testitem "Component E — Monin–Obukhov stability correction (night suppresses, day enhances g_a)" tags = [:energy, :scientific] begin
    using LPJmLFITEmulator
    using Test

    p_on = SEBParams{Float64}()                          # stability ON (default)
    p_off = SEBParams{Float64}(enable_stability = false) # neutral

    # closure stays EXACT with stability on, over a broad grid
    for sw in (0.0, 300.0, 700.0), lw in (250.0, 350.0), ta in (270.0, 290.0, 305.0),
            u in (0.5, 3.0, 8.0), le in (0.0, 100.0, 400.0)

        (Ts, Rn, H, G, le_out, ga, _) = solve_seb(p_on, sw, lw, ta, 1.0e5, u, 0.15, 1.0, 15.0, le, ta - 4.0)
        @test isapprox(Rn, le_out + H + G; atol = 1.0e-6)                  # closure EXACT by construction
        ρ = 1.0e5 / (p_on.R_d * ta)
        @test isapprox(H, ρ * p_on.c_p * ga * (Ts - ta); atol = 1.0e-4, rtol = 1.0e-6)   # converged identity
        @test all(isfinite, (Ts, Rn, H, G, le_out, ga))
    end

    # NIGHT (clear, calm): surface cools below air ⇒ STABLE ⇒ g_a suppressed ⇒ skin cools MORE than neutral
    (Tn_off, _, _, _, _, ga_n_off, _) = solve_seb(p_off, 0.0, 300.0, 288.15, 1.0e5, 1.0, 0.15, 1.0, 15.0, 5.0, 289.0)
    (Tn_on, _, _, _, _, ga_n_on, _) = solve_seb(p_on, 0.0, 300.0, 288.15, 1.0e5, 1.0, 0.15, 1.0, 15.0, 5.0, 289.0)
    @test ga_n_on < ga_n_off                              # stable stratification suppresses exchange
    @test Tn_on < Tn_off                                  # ⇒ stronger nocturnal cooling

    # DAY (hot, sunny, dry): surface heats above air ⇒ UNSTABLE ⇒ g_a enhanced ⇒ hot surface ventilated
    (Td_off, _, _, _, _, ga_d_off, _) = solve_seb(p_off, 800.0, 380.0, 300.0, 1.0e5, 1.5, 0.15, 1.0, 15.0, 60.0, 299.0)
    (Td_on, _, _, _, _, ga_d_on, _) = solve_seb(p_on, 800.0, 380.0, 300.0, 1.0e5, 1.5, 0.15, 1.0, 15.0, 60.0, 299.0)
    @test ga_d_on > ga_d_off                              # unstable convection enhances exchange
    @test Td_on < Td_off                                  # ⇒ hot surface closer to air

    # the stability factor is bounded (Fs ∈ [1−amp, 1+amp]) ⇒ g_a stays within amp× of neutral
    for Ri_case in ((0.0, 300.0, 288.15, 1.0, 5.0), (0.0, 250.0, 260.0, 0.3, 2.0), (900.0, 400.0, 310.0, 1.0, 100.0))
        sw, lw, ta, u, le = Ri_case
        (_, _, _, _, _, ga, _) = solve_seb(p_on, sw, lw, ta, 1.0e5, u, 0.15, 1.0, 15.0, le, ta - 3.0)
        ga_neu = aerodynamic_conductance(p_on, u, 1.0, 15.0)
        @test (1 - p_on.stab_amp) * ga_neu - 1.0e-9 ≤ ga ≤ (1 + p_on.stab_amp) * ga_neu + 1.0e-9
    end
end

@testitem "Component E — AD-friendly (ForwardDiff vs FiniteDifferences) + Float32" tags = [:energy, :unit] begin
    using LPJmLFITEmulator
    using Test
    using ForwardDiff, FiniteDifferences

    p = SEBParams{Float64}()
    # skin temperature as a function of downward shortwave — a fixed-graph Newton solve is AD-safe.
    f_sw(sw) = solve_seb(p, sw, 350.0, 298.15, 1.0e5, 3.0, 0.15, 2.5, 25.0, 200.0, 295.15)[1]
    g_ad = ForwardDiff.derivative(f_sw, 600.0)
    g_fd = central_fdm(5, 1)(f_sw, 600.0)
    @test isapprox(g_ad, g_fd; rtol = 1.0e-6)
    @test g_ad > 0                                   # more shortwave ⇒ warmer skin

    # gradient of the (residual) sensible heat w.r.t. wind, ForwardDiff vs FD
    f_u(u) = solve_seb(p, 700.0, 350.0, 298.15, 1.0e5, u, 0.15, 2.5, 25.0, 200.0, 295.15)[3]
    @test isapprox(ForwardDiff.derivative(f_u, 3.0), central_fdm(5, 1)(f_u, 3.0); rtol = 1.0e-5)

    # Float32 path stays finite and still closes the balance
    p32 = SEBParams{Float32}()
    (Ts, Rn, H, G, le_out, ga, _) =
        solve_seb(p32, 700.0f0, 350.0f0, 298.15f0, 1.0f5, 3.0f0, 0.15f0, 2.5f0, 25.0f0, 250.0f0, 295.15f0)
    @test all(isfinite, (Ts, Rn, H, G, le_out, ga))
    @test isapprox(Rn, le_out + H + G; atol = 1.0f-1)   # Float32 closure (looser tol)
    @test Ts isa Float32
end
