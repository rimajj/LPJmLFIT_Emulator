# Calibrate FourBandLongwave's clear-sky gas absorptivities against a correlated-k reference (stand-alone, no emulator).
# Columns: snapshots of a spun-up PrimitiveWetModel (prescribed SST; env LW=fourband for a four-band host, else grey).
# Reference: NumericalRadiation's ClearSkyEcCKDRadiation (ecCKD, H2O + CO2 + O3, CO2 from env CO2PPM, default 370 ppm,
# ~ the 1985-2014 mean) on the same columns. Fitted: window, CO2 and the two water vapour absorptivities and the
# black-band fraction of FourBandLongwave, by Nelder-Mead in log space, minimising over all columns (area-weighted)
#   Σ_k Δσ_k (ΔH_k / 0.25 K/day)² + (ΔOLR / 5 W/m²)² + (ΔLW↓ / 5 W/m²)²      (clear sky, cloud cover 0)
#   julia --project=<env> calibrate_fourband_vs_ecckd.jl [spinup_days=90] [snapshots=6] [days_between=5] [iterations=300]
using SpeedyWeather, NumericalRadiation, Dates, Printf

const SPINUP = parse(Int, get(ARGS, 1, "90"))
const NSNAP = parse(Int, get(ARGS, 2, "6"))
const DAYS = parse(Int, get(ARGS, 3, "5"))
const NITER = parse(Int, get(ARGS, 4, "300"))
const CO2 = parse(Float64, get(ENV, "CO2PPM", "370")) * 1.0e-6

sg = SpectralGrid(NF = Float64, truncation = 32, nlayers = 8)
kw = (; ocean = SeasonalOceanClimatology(sg))
get(ENV, "LW", "") == "fourband" && (kw = (; kw..., radiation = Radiation(sg; longwave = FourBandLongwave(sg))))
host = PrimitiveWetModel(sg; kw...)
sim = initialize!(host; time = DateTime(2015, 1, 1))
run!(sim, period = Day(SPINUP))
hv = sim.variables

m4 = PrimitiveWetModel(sg; radiation = Radiation(sg; longwave = FourBandLongwave(sg)), ocean = SeasonalOceanClimatology(sg))
mc = PrimitiveWetModel(sg; radiation = ClearSkyEcCKDRadiation(sg; mole_fractions = (; co2 = CO2)), ocean = SeasonalOceanClimatology(sg))
v4, vc = initialize!(m4).variables, initialize!(mc).variables

const FIELDS = (
    v -> v.grid.temperature, v -> v.grid.humidity, v -> v.dynamics.geopotential,
    v -> v.parameterizations.surface_pressure, v -> v.prognostic.ocean.sea_surface_temperature,
    v -> v.prognostic.land.soil_temperature,
)
snapshot(v) = map(f -> copy(f(v)), FIELDS)
restore!(v, s) = foreach((f, x) -> f(v) .= x, FIELDS, s)

_, lats = SpeedyWeather.RingGrids.get_londlatds(sg.grid)
Ω = SpeedyWeather.RingGrids.get_solid_angles(typeof(sg.grid), sg.grid.nlat_half)
w = zeros(length(lats))
for (j, ring) in enumerate(SpeedyWeather.RingGrids.eachring(sg.grid))
    w[ring] .= Ω[j]
end
w ./= sum(w)
nlayers, npoints = sg.nlayers, sg.npoints
g, cₚ = host.planet.gravity, host.atmosphere.heat_capacity
coord = host.geometry.vertical_coordinates
Δσ = host.geometry.σ_levels_thick

# reference fluxes per snapshot
snaps, ref = [], []
for s in 1:NSNAP
    s > 1 && run!(sim, period = Day(DAYS))
    st = snapshot(hv)
    push!(snaps, st)
    restore!(vc, st)
    SpeedyWeather.reset_variables!(vc)
    SpeedyWeather.global_parameterizations!(vc, mc)
    p = vc.parameterizations
    H = zeros(npoints, nlayers)
    for ij in 1:npoints
        SpeedyWeather.parameterization!(ij, vc, mc.radiation, mc)
        up, down, pₛ = p.ecckd.longwave_up[ij, :], p.ecckd.longwave_down[ij, :], p.surface_pressure[ij]
        for k in 1:nlayers
            Δp = SpeedyWeather.pressure_thickness(k, pₛ, coord)
            H[ij, k] = (up[k + 1] - up[k] + down[k] - down[k + 1]) * g / (cₚ * Δp) * 86400
        end
    end
    push!(ref, (olr = copy(p.outgoing_longwave.data), down = copy(p.surface_longwave_down.data), H = H))
end

const NAMES = (:absorptivity_window, :absorptivity_co2, :absorptivity_water_vapor_weak, :absorptivity_water_vapor_strong, :black_band_fraction)
fourband(θ) = (lw = FourBandLongwave(sg; NamedTuple{NAMES}(Tuple(θ))...); SpeedyWeather.initialize!(lw, m4); lw)

function evaluate(θ; report = false)
    lw = fourband(θ)
    p = v4.parameterizations
    dTdt = SpeedyWeather.get_tendency_step(v4.tendencies.grid.temperature, m4.time_stepping, m4.radiation)
    cost = 0.0
    stats = zeros(3 + nlayers, 2)        # rows: OLR, LW down, global H per layer; cols: model, ref
    for (st, r) in zip(snaps, ref)
        restore!(v4, st)
        SpeedyWeather.reset_variables!(v4)
        SpeedyWeather.global_parameterizations!(v4, m4)
        for ij in 1:npoints
            p.cloud_cover[ij] = 0
            p.cloud_top[ij] = nlayers + 1
            p.polar_night_cooling[ij] = 0
            dTdt[ij, :] .= 0
            SpeedyWeather.parameterization!(ij, v4, lw, m4)
            c = ((p.outgoing_longwave[ij] - r.olr[ij]) / 5)^2 + ((p.surface_longwave_down[ij] - r.down[ij]) / 5)^2
            for k in 1:nlayers
                H = dTdt[ij, k] * 86400
                c += Δσ[k] * ((H - r.H[ij, k]) / 0.25)^2
                stats[3 + k, 1] += w[ij] * H / NSNAP
                stats[3 + k, 2] += w[ij] * r.H[ij, k] / NSNAP
            end
            stats[1, :] .+= w[ij] .* (p.outgoing_longwave[ij], r.olr[ij]) ./ NSNAP
            stats[2, :] .+= w[ij] .* (p.surface_longwave_down[ij], r.down[ij]) ./ NSNAP
            cost += w[ij] * c / NSNAP
        end
    end
    if report
        @printf("  OLR %.1f (ref %.1f) W/m², LW down %.1f (ref %.1f) W/m²\n", stats[1, :]..., stats[2, :]...)
        for k in 1:nlayers
            @printf("  σ %.3f  heating %6.2f (ref %6.2f) K/day\n", host.geometry.σ_levels_full[k], stats[3 + k, :]...)
        end
    end
    return cost
end

# Nelder-Mead in log space
function nelder_mead(f, x0; step = 0.3, iters = 300)
    n = length(x0)
    X = [copy(x0)]
    for i in 1:n
        x = copy(x0); x[i] += step; push!(X, x)
    end
    F = f.(X)
    for it in 1:iters
        o = sortperm(F); X, F = X[o], F[o]
        xc = sum(X[1:n]) / n
        xr = xc + (xc - X[end]); fr = f(xr)
        if fr < F[1]
            xe = xc + 2(xc - X[end]); fe = f(xe)
            X[end], F[end] = fe < fr ? (xe, fe) : (xr, fr)
        elseif fr < F[n]
            X[end], F[end] = xr, fr
        else
            xk = xc + 0.5(X[end] - xc); fk = f(xk)
            if fk < F[end]
                X[end], F[end] = xk, fk
            else
                for i in 2:(n + 1)
                    X[i] = X[1] + 0.5(X[i] - X[1]); F[i] = f(X[i])
                end
            end
        end
        it % 25 == 0 && (@printf("  iteration %3d  cost %.4f  θ = %s\n", it, minimum(F), round.(exp.(X[argmin(F)]), sigdigits = 4)); flush(stdout))
    end
    return X[argmin(F)], minimum(F)
end

θ0 = [0.3, 6.0, 0.7, 50.0, 0.05]          # speedy.f90
println("\nFourBandLongwave clear sky vs ecCKD (CO2 $(CO2 * 1.0e6) ppm), $NSNAP snapshots, host LW = $(get(ENV, "LW", "grey"))")
println("speedy.f90 parameters: cost ", round(evaluate(θ0; report = true), digits = 4))
flush(stdout)
x, c = nelder_mead(x -> evaluate(exp.(x)), log.(θ0); iters = NITER)
println("calibrated: cost ", round(c, digits = 4), "  ", join(("$n = $(round(v, sigdigits = 4))" for (n, v) in zip(NAMES, exp.(x))), ", "))
evaluate(exp.(x); report = true)
flush(stdout)
