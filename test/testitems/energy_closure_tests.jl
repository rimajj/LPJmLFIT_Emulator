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

# ══════════════════════════════════════════════════════════════════════════════════════════════════════
# P2 (milestone E4) — the OBSERVATIONAL gate, frozen as a regression test.
#
# The full validation runs over 534k tower half-hours at 4 PLUMBER2 sites
# (`scripts/build_e_seb_validation_table.py` → `scripts/validate_e_seb_vs_plumber2.jl`, ADR 0072). This
# testitem re-runs the SAME Experiment-A comparison — the closure driven by a tower's own forcing AND its
# own measured LE, so nothing of F's ET enters — on two committed 3-hourly one-year extracts, and asserts
# the skill bounds the full run established. Its job is to catch a REGRESSION in the observational skill,
# not to re-derive the verdict, so the bounds are deliberately looser than the measured values (quoted in
# each comment) rather than tight fits.
#
# The fixtures are sampled EVERY 12th DAY OF YEAR at every 3rd hour, i.e. stratified across the whole record.
# A single-year fixture was tried first and was wrong: it landed inside DE-Hai's 2010-2012 window where
# PLUMBER2's `le_cor` is ≈0 garbage (the uncorrected `le` is all-NaN there), which fed the closure LE ≈ 0 and
# reported an H bias of +39.8 instead of +4.5 W/m². That failure is what surfaced the trap — see
# `lines/E/STATE.md` gotchas and `scripts/build_e_seb_validation_table.py`.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════
@testitem "Component E — P2 observational gate vs PLUMBER2 towers (E4 Experiment A)" tags = [:energy, :validation] begin
    using LPJmLFITEmulator
    using Test

    "Read a committed e4_seb_drive fixture into column vectors (NaN for blanks)."
    function read_fixture(path)
        lines = readlines(path)
        cols = String.(split(strip(lines[1]), ','))
        data = [Float64[] for _ in cols]
        for line in lines[2:end]
            isempty(strip(line)) && continue
            f = split(line, ',')
            length(f) == length(cols) || continue
            for (j, x) in enumerate(f)
                v = tryparse(Float64, x)
                push!(data[j], v === nothing ? NaN : v)
            end
        end
        return Dict(cols[j] => data[j] for j in eachindex(cols))
    end

    refdir = joinpath(@__DIR__, "references")

    # (site, canopy height m, measurement height m) — geometry read from the PLUMBER2 NetCDF, not assumed.
    # z_ref MUST be the tower's measurement height: `g_a` is evaluated at that level, and the 10 m default
    # would score the closure at a height the forcing was never measured at.
    for (site, h_can, z_ref) in (("DE-Hai", 33.0, 43.5), ("AU-ASM", 6.5, 11.6))
        tbl = read_fixture(joinpath(refdir, "e4_seb_drive_$site.csv"))
        n = length(tbl["tair"])
        @test n > 1500                                     # 2400 / 1680 rows: every 12th day, every 3rd hour
        p = SEBParams{Float64}(; z_ref = z_ref)
        z0m = 0.1 * h_can

        h_mod = similar(tbl["tair"])
        ts_mod = similar(tbl["tair"])
        rn_mod = similar(tbl["tair"])
        for i in 1:n
            (Ts, Rn, H, _G, _le, _ga, _c) = solve_seb(
                p, tbl["swdown"][i], tbl["lwdown"][i], tbl["tair"][i], tbl["psurf"][i], tbl["wind"][i],
                tbl["albedo"][i], z0m, h_can, tbl["le_in"][i], tbl["t_soil"][i],
            )
            h_mod[i] = H; ts_mod[i] = Ts; rn_mod[i] = Rn
        end
        @test all(isfinite, h_mod) && all(isfinite, ts_mod) && all(isfinite, rn_mod)

        mean_(v) = sum(v) / length(v)
        function r2(model, obs)
            ok = findall(i -> isfinite(model[i]) && isfinite(obs[i]), eachindex(model))
            m, o = model[ok], obs[ok]
            ō = mean_(o)
            return 1 - sum(abs2, m .- o) / sum(abs2, o .- ō)
        end

        # ---- H: the residual, and PLUMBER2's hardest flux -------------------------------------------
        okh = findall(i -> isfinite(tbl["h_obs"][i]), 1:n)
        bias_h = mean_(h_mod[okh] .- tbl["h_obs"][okh])
        # Measured on these fixtures: +4.5 (DE-Hai) / −6.4 (AU-ASM) W/m², both far inside PLUMBER2's own
        # ±40.9 W/m² daytime uncertainty at DE-Hai. Bound at ±20 ⇒ a real drift trips it, sampling noise does not.
        @test abs(bias_h) < 20.0
        # Measured on these fixtures: 0.667 (DE-Hai) / 0.910 (AU-ASM); full-record half-hourly is 0.60 / 0.90.
        # NB this 3-hourly R² is inflated by the diurnal cycle — the daily-mean R² is the honest skill number
        # (ADR 0072). Here it serves only as a regression tripwire.
        @test r2(h_mod, tbl["h_obs"]) > 0.5

        # ---- Rn: the radiation path under the tower's OWN albedo — the strongest result --------------
        if haskey(tbl, "rn_obs") && any(isfinite, tbl["rn_obs"])
            @test r2(rn_mod, tbl["rn_obs"]) > 0.95        # measured 0.988 (DE-Hai) / 0.996 (AU-ASM)
            okr = findall(i -> isfinite(tbl["rn_obs"][i]), 1:n)
            @test abs(mean_(rn_mod[okr] .- tbl["rn_obs"][okr])) < 20.0   # measured +1.6 / +7.7 W/m²
        end

        # ---- T_skin: only observable where the file carries LWup (OzFlux) ---------------------------
        if any(isfinite, tbl["t_skin_obs"])
            @test r2(ts_mod, tbl["t_skin_obs"]) > 0.85     # measured 0.935 on the fixture (0.941 full record)
            okt = findall(i -> isfinite(tbl["t_skin_obs"][i]), 1:n)
            dts = ts_mod[okt] .- tbl["t_skin_obs"][okt]
            @test abs(mean_(dts)) < 3.0                    # measured −1.22 K
            @test sqrt(mean_(abs2.(dts))) < 5.0            # measured 2.73 K RMSE
            # The KNOWN failure mode (ADR 0072): the closure runs too COLD at night. Pinned as an
            # inequality on the sign, so a future fix that removes it will trip this and force the update.
            night = findall(i -> tbl["swdown"][i] <= 50.0 && isfinite(tbl["t_skin_obs"][i]), 1:n)
            @test mean_(ts_mod[night] .- tbl["tair"][night]) <
                mean_(tbl["t_skin_obs"][night] .- tbl["tair"][night])
        end

        # ---- inside PLUMBER2's own uncertainty band (FLUXNET2015 sites only) ------------------------
        if haskey(tbl, "h_uc") && any(isfinite, tbl["h_uc"])
            okb = findall(i -> isfinite(tbl["h_obs"][i]) && isfinite(tbl["h_uc"][i]), 1:n)
            inside = count(i -> abs(h_mod[i] - tbl["h_obs"][i]) <= tbl["h_uc"][i], okb)
            @test inside / length(okb) > 0.45              # measured 59.8% on the fixture; 76.3% of daily means
        end
    end
end

# =====================================================================================================
# E6 / ADR 0073 — the STRUCTURE of the nocturnal-H error: which parameter is actually the lever.
#
# `H` is the EXACT residual `Rn − LE − G`, so its error can only come from `ΔRn`, `ΔG`, or the reference's
# own non-closure. `g_a` is in NONE of those terms — it acts only by moving `T_skin`. That is why ADR 0072
# item 6's "the stability form is the limitation, raise `stab_amp`" reading was wrong (its monotone sweep
# was bias cancellation), and the PLUMBER2 decomposition then measured why: the closure's nocturnal `g_a`
# is within **0.7 %** of DE-Hai's measured-`u*` value (ratio 0.82–1.70 across the four sites), while
# sd(`G_model`) is **5–7×** sd(`G_observed`) at the forest sites and the towers imply `λ_g ≈ 1.0`, not 7.0.
#
# These assertions pin the LEVER RANKING synthetically (no fixture needed) so a future session cannot
# quietly re-open the refuted hypothesis. The comparison is deliberately made over each parameter's
# OBSERVATIONALLY-IMPLIED uncertainty — `g_a` across the measured 0.8×–1.7× band vs `λ_g` across the
# implied 1.0 against the 7.0 default — because a 100× `g_a` bracket is not a real uncertainty and
# comparing raw sensitivities on unequal ranges would prove nothing. Per-site evidence: ADR 0073.
# =====================================================================================================
@testitem "Component E — nocturnal H is a ground-heat lever, not an aerodynamic one (ADR 0073)" tags = [:energy, :scientific] begin
    using LPJmLFITEmulator
    using Test

    # A representative clear, calm night at DE-Hai's real geometry: 33 m canopy, forcing measured at
    # 43.5 m (the tower's height — `SEBParams`' 10 m default would put z−d inside the roughness layer and
    # inflate `g_a` ~15×, which is exactly the `z_ref` trap ADR 0072's pipeline documents).
    Z = 43.5
    night(lg, u) = solve_seb(
        SEBParams{Float64}(z_ref = Z, enable_stability = false, lambda_g = lg),
        0.0, 300.0, 278.0, 1.0e5, u, 0.15, 3.3, 33.0, 10.0, 281.0,
    )

    # --- the identity the whole diagnosis rests on: H really IS Rn − LE − G --------------------------
    (_Ts, Rn0, H0, G0, le0, _ga0, _c0) = night(7.0, 2.0)
    @test isapprox(H0, Rn0 - le0 - G0; atol = 1.0e-9)

    # --- lever 1: g_a across the band the towers' measured u* actually permits (0.8×…1.7×) -----------
    # With stability off, g_a ∝ wind exactly, so scaling wind is an exact g_a multiplier applied through
    # the real solver — the same trick `scripts/e_nocturnal_h_decomp.jl` uses against the towers.
    ga_span = abs(night(7.0, 2.0 * 1.7)[3] - night(7.0, 2.0 * 0.8)[3])

    # --- lever 2: lambda_g across the observation-implied 1.0 vs the 7.0 default ---------------------
    lg_span = abs(night(7.0, 2.0)[3] - night(1.0, 2.0)[3])

    @test lg_span > 3 * ga_span     # measured ≈ 7.0× on this state (18.5 vs 2.6 W/m²)

    # --- the mechanism: the 7.0 default makes G swing several-fold harder than the towers show --------
    G_default = night(7.0, 2.0)[4]
    G_implied = night(1.0, 2.0)[4]
    @test G_default < 0                              # night: heat leaves the ground toward the surface
    @test abs(G_default) > 4 * abs(G_implied)        # measured ≈ 6.4× (cf. sd(G_m)/sd(G_o) = 5–7× at the towers)

    # --- and the closure stays EXACT at every lambda_g (guardrail 2: no conservation regression) ------
    for lg in (0.5, 1.0, 7.0, 14.0)
        (_T, Rn, H, G, le, _g, _cp) = night(lg, 2.0)
        @test isapprox(Rn, le + H + G; atol = 1.0e-9)
    end
end

# ══════════════════════════════════════════════════════════════════════════════════════════════════════
# E7 / ADR 0074 — the OPT-IN two-layer PROGNOSTIC ground-heat column.
#
# ADR 0073 attributed the nocturnal-H failure to the ground-heat term's TIMESCALE and named the fix a
# "force-restore / two-layer soil scheme" — a design change, not a tune. `enable_two_layer` is that
# scheme: `G = κ_g(T_skin − T1)` with `κ_g = 2λ_soil/z1`, and the two soil temperatures integrated
# forward under the MITgcm land-package update. These gates pin the four properties that must hold no
# matter what the observational scoring says, the first of which is guardrail 4:
#
#   1  DEFAULT BYTE-IDENTICAL — disabled (the default), nothing about the old path moves.
#   2  CLOSURE STILL EXACT (guardrail 2) with the scheme enabled, over a broad state grid.
#   3  ENERGY-EXACT COLUMN — the column's heat uptake equals the REPORTED `G`·dt exactly. This is the
#      property that made the flux-forced form the right one; a within-step recomputation of `G` would
#      break it (and would also be unstable at the daily step).
#   4  STABLE + SELF-EQUILIBRATING — with a closed bottom and no restoring term, the only thing stopping
#      a runaway is the surface feedback (T1 cold ⇒ G up ⇒ T1 warms). Assert it actually holds.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════
@testitem "Component E — two-layer ground heat is ON by default; `false` restores the pre-E7 kernel (ADR 0075)" tags = [:energy, :unit] begin
    using LPJmLFITEmulator
    using Test

    # ADR 0075 flipped this default, after ADR 0074 measured the scheme against four towers and ADR 0058
    # measured it inside the coupled loop. Guardrail 4 is therefore served by the OPT-OUT below rather
    # than by the default: `enable_two_layer = false` must still reproduce the pre-E7 closure exactly, so
    # every published pre-E7 number stays reproducible from the shipped package.
    p = SEBParams{Float64}()
    @test p.enable_two_layer

    # The `lambda_g` kwarg on the kernel defaults to `p.lambda_g`, so the pre-E7 call is bit-for-bit the
    # same computation. NB `solve_seb` never reads `enable_two_layer` — the scheme lives entirely in
    # `solve!`, which is why every STATELESS caller (the P2 tower gate above included) is unaffected by
    # this flip by construction, not by tolerance.
    args = (700.0, 350.0, 298.15, 1.0e5, 3.0, 0.15, 2.5, 25.0, 250.0, 295.15)
    @test solve_seb(p, args...) === solve_seb(p, args...; lambda_g = p.lambda_g)

    ff = FToE(le = 250.0, gpp = 0.0, npp = 0.0, rh = 0.0, firec = 0.0, flux_estabc = 0.0, ground_heat = 0.0)
    bc = SToE(albedo = 0.15, z0 = 2.5, lai = 4.0, height = 25.0)
    forc = AtmForcing(
        swdown = 700.0, lwdown = 350.0, tair = 298.15, qair = 0.008,
        wind = 3.0, psurf = 1.0e5, precip = 0.0, co2 = 400.0
    )

    # --- the OPT-OUT still is the pre-E7 closure: soil layers untouched, G driven by the air EWMA -----
    p0 = SEBParams{Float64}(enable_two_layer = false)
    clo0 = SEBEnergyClosure{Float64}(; params = p0, t_soil0 = 283.15)
    st0 = SharedState()
    for _ in 1:10
        solve!(clo0, st0, ff, bc, forc)
    end
    @test clo0.t_soil1 == 283.15 && clo0.t_soil2 == 283.15   # seeded, never integrated
    @test clo0.t_soil > 283.15                                # the EWMA is what moved
    (atm0, _tof0) = solve!(clo0, st0, ff, bc, forc)
    @test isapprox(atm0.g, p0.lambda_g * (atm0.t_skin - clo0.t_soil); atol = 1.0e-9)

    # --- and the DEFAULT is now the prognostic column -------------------------------------------------
    clo = SEBEnergyClosure(; t_soil0 = 283.15)
    st1 = SharedState()
    for _ in 1:10
        solve!(clo, st1, ff, bc, forc)
    end
    @test clo.t_soil1 != 283.15 && clo.t_soil2 != 283.15      # the column actually integrated
    @test clo.t_soil > 283.15                                 # the air EWMA is still advanced (still state)
    # G is the half-cell conductance against the PROGNOSTIC top layer, diagnosed from its PRE-step value.
    t1_pre = clo.t_soil1
    (atm, _tof) = solve!(clo, st1, ff, bc, forc)
    kappa_g = 2 * p.lambda_soil / p.z_soil1
    @test isapprox(atm.g, kappa_g * (atm.t_skin - t1_pre); atol = 1.0e-9)
    # ...and the two schemes really do differ on identical forcing — this is what ADR 0075 moved.
    @test !isapprox(atm.g, atm0.g; rtol = 1.0e-3)
end

# ADR 0072's night-cold failure mode, RESTATED under the ADR 0075 default rather than deleted.
#
# The P2 tower gate above pins that sign on `solve_seb`, which is scheme-independent, so the flip cannot
# move it — but the *coupled* path can, and it does. Measured on the four PLUMBER2 towers
# (`e7_two_layer_probe_v6.txt`, sub-daily, `z1 = 0.75 m`), nocturnal `T_skin` bias, pre-E7 arm → default:
# AU-ASM −0.95 → −3.17 K, AU-Tum −1.99 → −3.67 K, AU-Rob −1.09 → −2.03 K. So the sign is unchanged and the
# magnitude GROWS: pinning the surface's night-time reference to its own cooling top soil layer, instead of
# to a 30-day mean of air temperature, removes a warm bias that was partly masking it. ADR 0074 §3/§6 and
# ADR 0073 both name the missing term as canopy heat storage; this asserts the direction so that whoever
# lands it trips this test and must update it with a measurement.
# NB a `"""docstring"""` here (rather than `#`) makes this a `Core.@doc` expression and ReTestItems REJECTS
# the whole file with "Test files must only include `@testitem` and `@testsetup` calls".
@testitem "Component E — the ADR 0072 night-cold sign survives the default flip, and deepens (ADR 0075)" tags = [:energy, :scientific] begin
    using LPJmLFITEmulator
    using Test

    # A synthetic repeating diurnal cycle at a SUB-DAILY step — "night" only exists sub-daily, and the
    # towers above are scored the same way. 30 days is many multiples of the top layer's ~1 d timescale.
    dt = 1800.0
    steps_per_day = round(Int, 86400 / dt)
    tair_of(h) = 288.15 + 6.0 * sinpi((h - 9.0) / 12.0)
    sw_of(h) = max(0.0, 800.0 * sinpi((h - 6.0) / 12.0))

    "Mean nocturnal (T_skin − Tair) over the last 10 days of a 30-day rollout, in K."
    function night_dt(two_layer)
        p = SEBParams{Float64}(enable_two_layer = two_layer, dt_seconds = dt)
        clo = SEBEnergyClosure{Float64}(; params = p, t_soil0 = 288.15)
        st = SharedState()
        ff = FToE(le = 40.0, gpp = 0.0, npp = 0.0, rh = 0.0, firec = 0.0, flux_estabc = 0.0, ground_heat = 0.0)
        bc = SToE(albedo = 0.15, z0 = 2.5, lai = 4.0, height = 25.0)
        acc = 0.0
        cnt = 0
        for day in 1:30, k in 0:(steps_per_day - 1)
            h = 24.0 * k / steps_per_day
            (sw, ta) = (sw_of(h), tair_of(h))
            forc = AtmForcing(
                swdown = sw, lwdown = 320.0, tair = ta, qair = 0.008,
                wind = 1.0, psurf = 1.0e5, precip = 0.0, co2 = 400.0
            )
            (atm, _tof) = solve!(clo, st, ff, bc, forc)
            if day > 20 && sw <= 50.0                     # nocturnal, after the column has spun up
                acc += atm.t_skin - ta
                cnt += 1
            end
        end
        return acc / cnt
    end

    # Measured on this synthetic cycle: −1.474 K (pre-E7) → −2.496 K (default), n = 250 nocturnal steps —
    # the same direction and a comparable deepening to the three towers quoted above.
    d_pre = night_dt(false)          # the pre-E7 closure
    d_new = night_dt(true)           # the ADR 0075 default
    @test d_pre < 0.0                # ADR 0072: the closure runs too cold at night...
    @test d_new < 0.0                # ...and the flip does not repair that
    @test d_new < d_pre              # ...it DEEPENS it, as measured at all three T_skin towers
end

@testitem "Component E — two-layer column: closure exact, energy-exact, stable (ADR 0074)" tags = [:energy, :scientific] begin
    using LPJmLFITEmulator
    using Test

    p2 = SEBParams{Float64}(enable_two_layer = true)
    c_vol = p2.c_water * p2.theta_soil * p2.field_capacity + p2.c_dry_soil
    kappa_g = 2 * p2.lambda_soil / p2.z_soil1
    h1 = p2.z_soil1 * c_vol
    h2 = p2.z_soil2 * c_vol

    # --- 2. closure stays EXACT with the scheme on, over a broad state grid --------------------------
    for sw in (0.0, 300.0, 900.0), ta in (263.15, 288.15, 308.15), u in (0.2, 3.0, 8.0), le in (0.0, 250.0)
        clo = SEBEnergyClosure{Float64}(; params = p2, t_soil0 = ta)
        st = SharedState()
        ff = FToE(le = le, gpp = 0.0, npp = 0.0, rh = 0.0, firec = 0.0, flux_estabc = 0.0, ground_heat = 0.0)
        bc = SToE(albedo = 0.15, z0 = 1.0, lai = 4.0, height = 15.0)
        forc = AtmForcing(
            swdown = sw, lwdown = 330.0, tair = ta, qair = 0.008,
            wind = u, psurf = 1.0e5, precip = 0.0, co2 = 400.0
        )
        # `G` is diagnosed from the START-of-step `T1`; `solve!` then advances the column, so the
        # comparison must use the PRE-step value. (Reading `clo.t_soil1` afterwards is off by exactly
        # `κ_g·ΔT1` — the mistake this line originally made.)
        t1_pre = clo.t_soil1
        (atm, tof) = solve!(clo, st, ff, bc, forc)
        # Rn recomputed INDEPENDENTLY from the radiation law at the solved skin temperature, so this is a
        # real closure test rather than a restatement of `H := Rn − LE − G`.
        Rn = (1 - bc.albedo) * sw + p2.emissivity * 330.0 - p2.emissivity * p2.sigma * atm.t_skin^4
        @test isapprox(Rn, atm.le + atm.h + atm.g; atol = 1.0e-6)
        @test all(isfinite, (atm.t_skin, atm.h, atm.g, atm.le, tof.g_a, clo.t_soil1, clo.t_soil2))
        # G is now the HALF-CELL conductance against the PROGNOSTIC top layer, not the EWMA
        @test isapprox(atm.g, kappa_g * (atm.t_skin - t1_pre); atol = 1.0e-6)
        @test clo.t_soil1 != t1_pre                       # ...and the column actually integrated
    end

    # --- 3. energy-exact: the column gains exactly the REPORTED G·dt ---------------------------------
    clo = SEBEnergyClosure{Float64}(; params = p2, t_soil0 = 288.15)
    st = SharedState()
    ff = FToE(le = 120.0, gpp = 0.0, npp = 0.0, rh = 0.0, firec = 0.0, flux_estabc = 0.0, ground_heat = 0.0)
    bc = SToE(albedo = 0.15, z0 = 1.0, lai = 4.0, height = 15.0)
    forc = AtmForcing(
        swdown = 400.0, lwdown = 340.0, tair = 290.15, qair = 0.008,
        wind = 2.0, psurf = 1.0e5, precip = 0.0, co2 = 400.0
    )
    solve!(clo, st, ff, bc, forc)                   # warm-up: the first call also seeds the layers
    (t1_0, t2_0) = (clo.t_soil1, clo.t_soil2)
    (atm, _) = solve!(clo, st, ff, bc, forc)
    uptake = h1 * (clo.t_soil1 - t1_0) + h2 * (clo.t_soil2 - t2_0)
    @test isapprox(uptake, atm.g * p2.dt_seconds; rtol = 1.0e-12)

    # --- 4. stable + self-equilibrating under constant forcing --------------------------------------
    # A closed bottom has no restoring term. Run 4000 daily steps: the column must converge (not
    # oscillate, not run away), and at equilibrium the ground-heat flux must vanish — ⟨G⟩ → 0 is the
    # condition that makes the scheme usable without a deep-restore knob.
    g_hist = Float64[]
    for k in 1:4000
        (a, _) = solve!(clo, st, ff, bc, forc)
        k > 3990 && push!(g_hist, a.g)
    end
    @test all(isfinite, (clo.t_soil1, clo.t_soil2))
    @test abs(sum(g_hist) / length(g_hist)) < 0.5              # W/m² — equilibrated
    @test abs(clo.t_soil1 - clo.t_soil2) < 1.0                 # the two layers have joined up
    @test 200.0 < clo.t_soil1 < 400.0                          # no runaway

    # --- dt_seconds is really the step length: 24 hourly steps ≈ 1 daily step -----------------------
    # This is what line O's sub-daily coupling depends on, so it gets its own assertion.
    mk(dt) = SEBEnergyClosure{Float64}(;
        params = SEBParams{Float64}(enable_two_layer = true, dt_seconds = dt), t_soil0 = 288.15,
    )
    c_day = mk(86400.0)
    c_hr = mk(3600.0)
    solve!(c_day, st, ff, bc, forc)
    for _ in 1:24
        solve!(c_hr, st, ff, bc, forc)
    end
    # same elapsed time ⇒ same column state to within the operator-splitting difference
    @test isapprox(c_day.t_soil1, c_hr.t_soil1; atol = 0.05)
    @test isapprox(c_day.t_soil2, c_hr.t_soil2; atol = 0.05)
end
