# FourBandLongwave: a port of speedy.f90's longwave; the default grey longwave puts clear-sky OLR ~28 W/m² too high and cools the wrong layers

(SpeedyWeather/SpeedyWeather.jl#1342, filed 2026-10-22 as rimajj)

**Summary.** The wet model's default longwave, `OneBandLongwave` with `FriersonLongwaveTransmissivity`, has a prescribed optical depth that depends only on latitude and σ. It does not see the model's water vapour, CO₂ or clouds. Measured against a correct radiation code (ecCKD, via the NumericalRadiation extension) on identical model columns, it gets the clear-sky OLR 28 W/m² too high and puts the cooling in the wrong layers. We ported speedy.f90's four-band longwave (window, CO₂, weak and strong water-vapour bands, cloud absorption from `DiagnosticClouds`) as a new `FourBandLongwave`. On the same columns it matches ecCKD within 3.5 W/m² of OLR. In the model it gave the first free-ocean (slab) climate in our tests that does not keep cooling. It is on a branch, with a test against speedy.f90 reference fluxes, and we can open a PR.

Context: the cold-bias work in #1333. Setup as there: default `PrimitiveWetModel`, T31 L8, Float32, 40-min step. The base is `main` d6e3286d + #1332 + #1284 + #1283 + #1262 (+ the `variables(::TwoBandShortwave)` line from #1279). `FourBandLongwave` needs #1262's `DiagnosticClouds` cloud cover and cloud top. Single realisations.

## 1. Clear-sky longwave on identical columns (no model feedback)

After a 90-day spin-up of the four-band model, each column's clear-sky longwave is recomputed by the three schemes on the same state. CO₂ is 400 ppm for ecCKD. Global means:

| | four-band | grey (Frierson, default) | ecCKD |
|---|---|---|---|
| OLR [W/m²] | 252.5 | **276.5** | 249.0 |
| LW down at the surface [W/m²] | 285.7 | **365.6** | 315.0 |
| cooling σ 0.31 [K/day] | −1.65 | −0.49 | −1.72 |
| cooling σ 0.56 [K/day] | −1.24 | −3.51 | −1.59 |
| cooling σ 0.69 [K/day] | −1.22 | −4.44 | −1.35 |
| cooling σ 0.94 [K/day] | −1.55 | −3.06 | −2.17 |

Tropics (|lat| < 15): OLR 265.7 / 300.7 / 263.1. Poleward of 60°: 198.8 / 229.1 / 194.3. The grey scheme cools the lower and middle troposphere 2–3× too strongly and the upper troposphere too weakly. Its surface downward longwave is 50 W/m² too high. The four-band scheme's surface downward longwave is ~30 W/m² too low, and the rest is close to ecCKD.

One caveat: on the columns of a grey-longwave spin-up (warmer and moister at σ 0.19), the four-band scheme cools σ 0.19 by 4.95 K/day against ecCKD's 2.77. On its own columns the two agree there (−1.00 vs −0.94).

## 2. In the model (3 years prescribed SST, years 2–3; 5 years slab, year 5)

| | grey (base above) | four-band |
|---|---|---|
| prescribed SST: TOA net [W/m²] | −48.9 | +4.6 |
| prescribed SST: OLR / reflected SW [W/m²] | 269.5 / 120.6 | 222.2 / 114.5 |
| prescribed SST: ice-free ocean air − SST, tropics [K] | −3.7 | +0.1 |
| slab: global near-surface air [°C] | 3.2, still cooling | 18.3, steady |
| slab: TOA net, year 5 [W/m²] | −5.3 | +0.8 |

So the four-band scheme removes the cold bias, but with `main`'s convection it overshoots to warm: land +3.7 K vs W5E5, and the tropical upper troposphere 4–9 K warmer than GFDL-ESM4. The upper-tropospheric part is the convection's parcel ascent (#1339), which the grey scheme's cold bias had hidden. With the #1339 options on top (`ascent_substeps = 10, entrainment_mse = true`), the four-band slab run is at 17.1 °C global, with the tropical 300–550 hPa temperature within 3 K of GFDL-ESM4. A remaining drift of +0.35 K/yr is a separate issue (#1345).

Other things we tried, none adopted:
- `AnalyticBandLongwave` (NumericalRadiation) as the model's longwave: the slab freezes (−0.7 °C global after 5 years).
- Calibrating the five four-band gas absorptivities against ecCKD by Nelder-Mead on model columns. Column cost 42 → 11, but in the model the slab then runs away warm (+7–9 W/m² in year 5). So speedy.f90's own values stay the defaults.

## Proposed change

A new `FourBandLongwave <: AbstractLongwave` (one file, ~265 lines), not the default. It follows speedy.f90's `longwave_radiation.f90` and the longwave transmissivities in `shortwave_radiation.f90` (Molteni 2003):
- **Bands:** four bands with the temperature-dependent band fractions `fband(T)` (evaluated at the continuous temperature rather than tabulated), plus speedy.f90's "black" band.
- **Clouds:** absorption from `DiagnosticClouds`' cover and top.
- **Other speedy.f90 terms:** the gradient correction within tropospheric layers, stratospheric emission and polar-night cooling.
- **Any number of layers:** generalised the same way #1262 does for the clouds (`σ_tropopause`, `σ_boundary_layer`). For speedy.f90's 8 levels it is exactly speedy.f90.

Column energy closes to 1e-4 W/m². The test compares four columns against speedy.f90 reference fluxes at `rtol = 1e-10`.

Usage: `Radiation(spectral_grid; shortwave = TwoBandShortwave(spectral_grid), longwave = FourBandLongwave(spectral_grid))`.

<details><summary>four_band_longwave.jl</summary>

```julia
export FourBandLongwave

"""Four-band longwave radiation following Fortran SPEEDY (speedy.f90, `longwave_radiation.f90` and the
longwave transmissivities in `shortwave_radiation.f90`, Molteni 2003). Bands: 1 the infrared "window",
2 the CO₂ band, 3 a weak and 4 a strong water vapour band. Transmissivities depend on the layer's mass,
its specific humidity and on the diagnosed cloud cover and cloud top (`DiagnosticClouds` of the shortwave
scheme): clouds below their top absorb in the window band (`absorptivity_cloud_thick`), and all cloudy
layers absorb at least `absorptivity_cloud_thin` × cloud cover in the water vapour bands. Each band carries
the temperature-dependent fraction `fband(T)` of the blackbody emission; the remaining fraction
`epslw` is a "black" band exchanged only between the surface and the lowermost layer, and emitted
from the stratosphere directly to space. Tropospheric layers add a correction for the temperature
gradient within the layer to their downward (+) and upward (−) emission.

The layers of Fortran SPEEDY's 8 levels are generalized to any number of layers as in `DiagnosticClouds`:
the stratosphere is the layers above `σ_tropopause` (no gradient correction, no water vapour bands in the
uppermost layer, stratospheric emission to space), the free troposphere between `σ_tropopause` and
`σ_boundary_layer` can hold clouds, the layers below are cloud-free. For SPEEDY's 8 σ levels this is
exactly SPEEDY. Differences: `fband` is evaluated at the continuous temperature (SPEEDY tabulates
it on integer K), and the surface emissivity can differ over ocean and land (both default to SPEEDY's 0.98).
Fields are $(TYPEDFIELDS)"""
@parameterized @kwdef struct FourBandLongwave{NF, RI} <: AbstractLongwave
    "[OPTION] Absorptivity of air in the window band, per 10⁵ Pa (SPEEDY ablwin) [1]"
    @param absorptivity_window::NF = 0.3 (bounds = Nonnegative,)

    "[OPTION] Absorptivity of air in the CO₂ band, per 10⁵ Pa (SPEEDY ablco2) [1]"
    @param absorptivity_co2::NF = 6 (bounds = Nonnegative,)

    "[OPTION] Absorptivity of water vapour in the weak band, per 10⁵ Pa and g/kg (SPEEDY ablwv1) [1]"
    @param absorptivity_water_vapor_weak::NF = 0.7 (bounds = Nonnegative,)

    "[OPTION] Absorptivity of water vapour in the strong band, per 10⁵ Pa and g/kg (SPEEDY ablwv2) [1]"
    @param absorptivity_water_vapor_strong::NF = 50 (bounds = Nonnegative,)

    "[OPTION] Absorptivity of thick clouds (below cloud top) in the window band, per 10⁵ Pa (SPEEDY ablcl1) [1]"
    @param absorptivity_cloud_thick::NF = 12 (bounds = Nonnegative,)

    "[OPTION] Absorptivity of thin upper clouds in the window and water vapour bands, per 10⁵ Pa (SPEEDY ablcl2) [1]"
    @param absorptivity_cloud_thin::NF = 0.6 (bounds = Nonnegative,)

    "[OPTION] Fraction of the blackbody spectrum in the black band, exchanged between surface and lowermost layer, emitted by the stratosphere to space (SPEEDY epslw) [1]"
    @param black_band_fraction::NF = 0.05 (bounds = 0 .. 1,)

    "[OPTION] Surface emissivity over ocean (SPEEDY emisfc) [1]"
    @param emissivity_ocean::NF = 0.98 (bounds = 0 .. 1,)

    "[OPTION] Surface emissivity over land (SPEEDY emisfc) [1]"
    @param emissivity_land::NF = 0.98 (bounds = 0 .. 1,)

    "[OPTION] Polar night cooling of the uppermost layer where the daily mean insolation is below this, SPEEDY fs0 [W/m²]"
    @param polar_night_insolation::NF = 6 (bounds = Nonnegative,)

    "[OPTION] Reference pressure for the absorptivities [Pa]"
    reference_pressure::NF = 100_000

    "[OPTION] Stratosphere above (σ < σ_tropopause) [1]"
    σ_tropopause::NF = 0.14

    "[OPTION] Clouds only above the boundary layer (σ ≤ σ_boundary_layer) [1]"
    σ_boundary_layer::NF = 0.9

    "[DERIVED] Lowermost stratospheric layer, set in `initialize!`"
    stratosphere_bottom::RI = Ref(0)

    "[DERIVED] Lowermost layer that can hold clouds, set in `initialize!`"
    cloud_base::RI = Ref(0)
end

Adapt.@adapt_structure FourBandLongwave
FourBandLongwave(SG::SpectralGrid; kwargs...) = FourBandLongwave{SG.NF, Base.RefValue{Int}}(; kwargs...)

function variables(::FourBandLongwave)
    return (
        variables(UniformCooling{Float32}())...,     # the standard longwave diagnostics
        ParameterizationVariable(:polar_night_cooling, Grid2D(), desc = "Polar night cooling of the uppermost layer", units = "W/m^2"),
        ScratchVariable(:longwave_transmissivity, Grid4D(n = 4), desc = "Longwave transmissivity per layer and band", units = "1", namespace = :grid),
        ScratchVariable(:longwave_emission, GridXYZ(), desc = "Layer blackbody emission", units = "W/m^2", namespace = :grid),
        ScratchVariable(:longwave_gradient, GridXYZ(), desc = "Layer emission gradient correction", units = "W/m^2", namespace = :grid),
        ScratchVariable(:longwave_absorbed, GridXYZ(), desc = "Longwave flux absorbed per layer", units = "W/m^2", namespace = :grid),
    )
end

function initialize!(lw::FourBandLongwave, model::PrimitiveEquation)
    coord = Adapt.adapt(Array, model.geometry.vertical_coordinates)     # on CPU
    nlayers = get_nlayers(coord)
    stratosphere_bottom = 0
    cloud_base = 0
    for k in 1:(nlayers - 1)
        σ = sigma(k, coord)
        stratosphere_bottom = σ < lw.σ_tropopause ? k : stratosphere_bottom
        cloud_base = σ <= lw.σ_boundary_layer ? k : cloud_base
    end
    lw.stratosphere_bottom[] = stratosphere_bottom
    lw.cloud_base[] = max(cloud_base, stratosphere_bottom)
    return nothing
end

"""$(TYPEDSIGNATURES)
Energy fraction of the blackbody emission at temperature `T` [K] in `band` 1 to 4 (SPEEDY `radset`),
summing to `1 - ϵ` with ϵ the fraction of the black band."""
@inline function longwave_band_fraction(T, band::Integer, ϵ)
    NF = typeof(ϵ)
    T = clamp(T, NF(200), NF(320))
    f2 = (NF(0.148) - NF(3.0e-6) * (T - 247)^2) * (1 - ϵ)
    f3 = (NF(0.356) - NF(5.2e-6) * (T - 282)^2) * (1 - ϵ)
    f4 = (NF(0.314) + NF(1.0e-5) * (T - 315)^2) * (1 - ϵ)
    f1 = (1 - ϵ) - (f2 + f3 + f4)
    return band == 1 ? f1 : band == 2 ? f2 : band == 3 ? f3 : f4
end

# polar night cooling from the daily mean insolation (SPEEDY stratz), once per time step
function parameterization!(vars::Variables, lw::FourBandLongwave, model::PrimitiveEquation)
    field = vars.parameterizations.polar_night_cooling
    NF = eltype(field)
    δ = solar_declination(NF, model.solar_zenith, vars.prognostic.clock.orbit_time)
    S₀ = convert(NF, model.planet.solar_constant)
    launch!(
        architecture(field), LinearWorkOrder, size(field), polar_night_cooling_kernel!,
        field, δ, S₀, lw.polar_night_insolation, model.geometry.sinlat, field.grid.whichring
    )
    return nothing
end

@kernel inbounds = true function polar_night_cooling_kernel!(field, δ, S₀, insolation_min, sinlat, whichring)
    ij = @index(Global, Linear)
    sinϕ = sinlat[whichring[ij]]
    cosϕ = sqrt(max(0, 1 - sinϕ^2))
    tanϕ_tanδ = cosϕ > 0 ? sinϕ / cosϕ * tan(δ) : sign(sinϕ * δ) * one(δ)
    h₀ = acos(clamp(-tanϕ_tanδ, -1, 1))        # half day length (hour angle at sunset)
    daily_mean_insolation = S₀ / π * (h₀ * sinϕ * sin(δ) + cosϕ * cos(δ) * sin(h₀))
    field[ij] = max(insolation_min - daily_mean_insolation, 0)
end

@propagate_inbounds function parameterization!(ij, vars, lw::FourBandLongwave, model)
    T = get_prognostic_step(vars.grid.temperature, model.time_stepping, lw)
    q = get_prognostic_step(vars.grid.humidity, model.time_stepping, lw)
    dTdt = get_tendency_step(vars.tendencies.grid.temperature, model.time_stepping, lw)
    NF = eltype(T)
    nlayers = size(T, 2)
    coord = model.geometry.vertical_coordinates
    pₛ = vars.parameterizations.surface_pressure[ij]
    σSB = model.atmosphere.stefan_boltzmann
    cₚ = model.atmosphere.heat_capacity
    ϵ = lw.black_band_fraction
    p₀ = lw.reference_pressure
    ks, kb = lw.stratosphere_bottom[], lw.cloud_base[]

    t = vars.scratch.grid.longwave_transmissivity     # [ij, k, band]
    B = vars.scratch.grid.longwave_emission
    G = vars.scratch.grid.longwave_gradient
    A = vars.scratch.grid.longwave_absorbed

    # clouds from the shortwave scheme's DiagnosticClouds (none if not diagnosed)
    params = vars.parameterizations
    cloud_cover = haskey(params, :cloud_cover) ? params.cloud_cover[ij] : zero(NF)
    cloud_top = haskey(params, :cloud_cover) ? unsafe_trunc(Int, params.cloud_top[ij]) : nlayers + 1
    a_thin = cloud_cover * lw.absorptivity_cloud_thin

    # 1. Transmissivities, SPEEDY shortwave_radiation.f90 section 5.1
    for k in 1:nlayers
        Δp = pressure_thickness(k, pₛ, coord) / p₀
        qₖ = 1000 * max(q[ij, k], 0)                       # [g/kg]
        a_win = lw.absorptivity_window
        a_wv1 = lw.absorptivity_water_vapor_weak * qₖ
        a_wv2 = lw.absorptivity_water_vapor_strong * qₖ
        if ks < k <= kb                                    # free troposphere, cloudy
            a_win += k < cloud_top ? a_thin : lw.absorptivity_cloud_thick * cloud_cover
            a_wv1 = max(a_wv1, a_thin)
            a_wv2 = max(a_wv2, a_thin)
        end
        t[ij, k, 1] = exp(-Δp * a_win)
        t[ij, k, 2] = exp(-Δp * lw.absorptivity_co2)
        t[ij, k, 3] = k == 1 ? one(NF) : exp(-Δp * a_wv1)  # no water vapour bands in the uppermost layer
        t[ij, k, 4] = k == 1 ? one(NF) : exp(-Δp * a_wv2)
    end

    # 2. Blackbody emission, half-level temperatures linear in log p (SPEEDY st4a)
    T_above = T[ij, 1]                                     # isothermal above the uppermost layer
    for k in 1:nlayers
        T_below = if k < nlayers
            lnp, lnp₊ = log(pressure(k, pₛ, coord)), log(pressure(k + 1, pₛ, coord))
            w = (log(pressure_below(k, pₛ, coord)) - lnp) / (lnp₊ - lnp)
            T[ij, k] + w * (T[ij, k + 1] - T[ij, k])
        else
            T[ij, k]
        end
        if k <= ks                                         # stratosphere: mean temperature, no gradient
            Tₘ = T[ij, k] / 2 + (T_above + T_below) / 4
            B[ij, k] = σSB * Tₘ^4
            G[ij, k] = zero(NF)
        else                                               # troposphere: gradient correction
            ΔT = k < nlayers ? max(T_below - T_above, 0) / 2 : max(T[ij, k] - T_above, 0)
            T³ = σSB * T[ij, k]^3
            B[ij, k] = T³ * T[ij, k]
            G[ij, k] = 4 * T³ * ΔT
        end
        A[ij, k] = zero(NF)
        T_above = T_below
    end

    # 3. Downward beam, per band, starting with no flux from space
    land_fraction = model.land_sea_mask.land_fraction[ij]
    ϵ_surf = (1 - land_fraction) * lw.emissivity_ocean + land_fraction * lw.emissivity_land
    D = ntuple(band -> longwave_downward_band!(A, ij, t, B, G, T, band, nlayers, ϵ), Val(4))
    D_surface = sum(D)                                     # flux per band reaching the surface
    black = ϵ * ϵ_surf * B[ij, nlayers]                    # black band from the lowermost layer
    A[ij, nlayers] -= black
    D_absorbed = ϵ_surf * D_surface + black
    params.surface_longwave_down[ij] = D_absorbed

    # 4. Upward beam: surface emission + reflection
    sst = get_prognostic_step(vars.prognostic.ocean.sea_surface_temperature, time_stepper(model.time_stepping, :ocean), lw)
    soil_temperature = get_prognostic_step(vars.prognostic.land.soil_temperature, time_stepper(model.time_stepping, :land), lw)
    U_ocean = lw.emissivity_ocean * σSB * sst[ij]^4
    U_land = lw.emissivity_land * σSB * soil_temperature[ij, 1]^4
    params.ocean.surface_longwave_up[ij] = U_ocean
    params.land.surface_longwave_up[ij] = U_land
    U = (1 - land_fraction) * U_ocean + land_fraction * U_land
    params.surface_longwave_up[ij] = U
    Tₛ = sqrt(sqrt(U / (ϵ_surf * σSB)))                    # effective surface temperature for the band fractions
    A[ij, nlayers] += ϵ * U                                # black band into the lowermost layer

    OLR = zero(NF)
    for band in 1:4
        flux = longwave_band_fraction(Tₛ, band, ϵ) * U + (1 - ϵ_surf) * D[band]
        for k in nlayers:-1:1
            tₖ = t[ij, k, band]
            brad = longwave_band_fraction(T[ij, k], band, ϵ) * (B[ij, k] - (1 - tₖ) * G[ij, k])
            A[ij, k] += flux
            flux = tₖ * flux + (1 - tₖ) * brad
            A[ij, k] -= flux
        end
        OLR += flux
    end

    # 5. Stratospheric emission to space (black band, by layer mass) and polar night cooling (SPEEDY stratc)
    Δp_strat = ks > 0 ? pressure_below(ks, pₛ, coord) - pressure_above(1, pₛ, coord) : one(NF)
    for k in 1:ks
        E = ϵ * (pₛ / p₀) * pressure_thickness(k, pₛ, coord) / Δp_strat * B[ij, k]
        k == 1 && (E += params.polar_night_cooling[ij] * pₛ / p₀)
        A[ij, k] -= E
        OLR += E
    end
    params.outgoing_longwave[ij] = OLR

    # 6. Absorbed fluxes into temperature tendencies
    for k in 1:nlayers
        dTdt[ij, k] += flux_to_tendency(A[ij, k] / cₚ, pₛ, k, model)
    end
    return nothing
end

"""$(TYPEDSIGNATURES)
Downward beam of longwave `band` through all layers from the top (no flux from space), accumulating
the absorbed flux into `A`, returns the flux reaching the surface."""
@propagate_inbounds function longwave_downward_band!(A, ij, t, B, G, T, band, nlayers, ϵ)
    flux = zero(eltype(A))
    for k in 1:nlayers
        tₖ = t[ij, k, band]
        brad = longwave_band_fraction(T[ij, k], band, ϵ) * (B[ij, k] + (1 - tₖ) * G[ij, k])
        A[ij, k] += flux
        flux = tₖ * flux + (1 - tₖ) * brad
        A[ij, k] -= flux
    end
    return flux
end
```
</details>

Happy to open a PR with the test and docs. Making it the default is your call, given its interaction with the convection (#1339).
