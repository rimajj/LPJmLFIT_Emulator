# O3a — a REAL, spatially varying soil texture for the online (Terrarium) soil, plus the guard that
# makes the degenerate case fail loudly.  `include(...)` this from a coupling script.
#
# WHY (ADR 0082 §4; skill `online-coupling-env` trap 6; [VERIFIED 2026-07-28, job 1622830]):
# Terrarium's default `ConstantSoilHorizon` carries `SoilTexture(NF)` = `sand = 1, clay = 0`.
# `SoilHydraulicsSURFEX` then gives
#     wilting_point  = 37.13e-3 * sqrt(clay*100)   -> 0
#     field_capacity = 89.0e-3  * (clay*100)^0.35  -> 0
# so `plant_available_water = clamp((θw − wp)/(fc − wp), 0, 1) ≡ 1` wherever θw > 0.  It does not
# error: it silently reports "fully unstressed everywhere", deleting the drought response and
# feeding Terrarium's own `soil_moisture_limiting_factor` → photosynthesis chain.  No online run
# on the default soil may be used to judge vegetation.
#
# THE FIX HERE
#   1. `lpjml_texture_fields(grid, csv)` — nearest-neighbour-maps the LPJmL-FIT ground-truth soil
#      texture (built by `build_soil_texture_field.py`) onto the ring grid's land columns and
#      returns Oceananigans `Field`s ready to hand to `PrescribedSoilHorizon`.
#   2. `prescribed_texture_soil(NF; ...)` — a single-horizon `SoilStratigraphy` whose texture is
#      those prescribed fields, with SURFEX porosity (texture-consistent with SURFEX hydraulics).
#   3. `assert_nondegenerate_soil(...)` — THE GUARD.  Rejects any texture whose SURFEX
#      `field_capacity <= wilting_point`, and reports the PAW denominator's spread.
#
# The horizon is named `:soil`, so its inputs live at `state.namespaces.soil.{sand,silt,clay}_fraction`
# and are supplied through `fields = (soil = (...),)`.  That routing matters in the COUPLED path:
# `SpeedyWeatherTerrariumExt` builds its `ModelIntegrator` with an EMPTY `InputSources(NF)`, so an
# `InputSource`-based prescription (what the upstream `soil_heat_global_soilgrids.jl` example uses)
# is silently DROPPED under SpeedyWeather.  Only `fields` is forwarded (via `TerrariumLand.fields`
# → `Terrarium.initialize(...; fields)` → `StateVariables`, which does
# `ns_fields = get(fields, varname(ns), (;))` per namespace).

using Terrarium
using DelimitedFiles
import RingGrids

const TEXTURE_CSV_DEFAULT = "/p/tmp/jamirp/esm_online_coupling/lpjml_soil_texture_orderA.csv"

# The LPJmL source grid is a regular half-degree lat/lon grid; binning it makes the
# nearest-neighbour search a small local scan instead of 4608 × 67420 distance evaluations.
const SRC_RES = 0.5
const SRC_NLON = 720
const SRC_NLAT = 360

# Global-median LPJmL soil type ("loam", 23 340 of 67 420 cells) — used only where no LPJmL land
# cell is anywhere near a ring-grid column (open ocean under a RockyPlanetMask).  Non-degenerate
# by construction (clay = 0.18), and reported so it is never silently assumed to be data.
const FALLBACK_TEXTURE = (sand = 0.43, silt = 0.39, clay = 0.18)

"""
    read_lpjml_texture(csv) -> (lon, lat, sand, silt, clay)

Read the LPJmL-FIT ground-truth soil texture table written by `build_soil_texture_field.py`.
"""
function read_lpjml_texture(csv::AbstractString = TEXTURE_CSV_DEFAULT)
    isfile(csv) || error("texture table $csv not found — run scripts/online_coupling/build_soil_texture_field.py first")
    raw, hdr = readdlm(csv, ',', header = true)
    cols = Dict(strip(String(h)) => i for (i, h) in enumerate(vec(hdr)))
    for c in ("lon", "lat", "sand", "silt", "clay")
        haskey(cols, c) && continue
        error("texture table $csv has no `$c` column (header = $(vec(hdr)))")
    end
    get_f(c) = Float64.(raw[:, cols[c]])
    return get_f("lon"), get_f("lat"), get_f("sand"), get_f("silt"), get_f("clay")
end

# bin index of a coordinate on the half-degree source grid
@inline src_ix(lon) = clamp(round(Int, (mod(lon + 180, 360)) / SRC_RES + 0.5), 1, SRC_NLON)
@inline src_iy(lat) = clamp(round(Int, (lat + 90) / SRC_RES + 0.5), 1, SRC_NLAT)

# great-circle separation in degrees (only used to rank a handful of local candidates)
function angsep_deg(lon1, lat1, lon2, lat2)
    φ1, φ2 = deg2rad(lat1), deg2rad(lat2)
    Δλ = deg2rad(mod(lon2 - lon1 + 180, 360) - 180)
    c = sin(φ1) * sin(φ2) + cos(φ1) * cos(φ2) * cos(Δλ)
    return rad2deg(acos(clamp(c, -1, 1)))
end

"""
    column_lonlats(grid) -> (lond, latd)

Longitude/latitude in DEGREES of each land column of a `ColumnRingGrid`, in the same order as the
first axis of `interior(field)` — i.e. the ring-grid points selected by `grid.mask`.
"""
function column_lonlats(grid)
    lon_rad, lat_rad = RingGrids.get_lonlats(grid.rings)
    mask = Array(grid.mask.data)
    sel = vec(mask) .!= 0
    return rad2deg.(Array(lon_rad)[sel]), rad2deg.(Array(lat_rad)[sel])
end

"""
    map_texture_to_columns(grid; csv, max_land_dist_deg, max_search_boxes)

Nearest-neighbour-map the LPJmL texture onto the land columns of `grid`.

Returns `(sand, silt, clay, dist_deg, is_land)` as plain `Vector`s over columns, where `dist_deg`
is the angular separation to the LPJmL cell used and `is_land` marks columns whose nearest LPJmL
land cell is within `max_land_dist_deg` (the rest got `FALLBACK_TEXTURE`).  `is_land` is what the
O3b `soilmoist` comparison must restrict to — the LPJmL reference distribution is over land only.
"""
function map_texture_to_columns(
        grid;
        csv::AbstractString = TEXTURE_CSV_DEFAULT,
        max_land_dist_deg::Real = 2.5,
        max_search_boxes::Int = 60,
    )
    slon, slat, ssand, ssilt, sclay = read_lpjml_texture(csv)

    # bin the source cells; the half-degree grid has at most one source cell per box
    binned = zeros(Int32, SRC_NLON, SRC_NLAT)
    @inbounds for n in eachindex(slon)
        binned[src_ix(slon[n]), src_iy(slat[n])] = Int32(n)
    end

    clon, clat = column_lonlats(grid)
    ncol = length(clon)
    sand = fill(FALLBACK_TEXTURE.sand, ncol)
    silt = fill(FALLBACK_TEXTURE.silt, ncol)
    clay = fill(FALLBACK_TEXTURE.clay, ncol)
    dist = fill(Inf, ncol)

    @inbounds for c in 1:ncol
        ix0, iy0 = src_ix(clon[c]), src_iy(clat[c])
        best, bestd = 0, Inf
        r, r_found = 0, -1
        while r <= max_search_boxes
            # scan the square ring at radius r; longitude wraps, latitude clamps
            for dy in -r:r, dx in -r:r
                (max(abs(dx), abs(dy)) == r) || continue      # ring only, interior already scanned
                iy = iy0 + dy
                (1 <= iy <= SRC_NLAT) || continue
                ix = mod1(ix0 + dx, SRC_NLON)
                n = binned[ix, iy]
                n == 0 && continue
                d = angsep_deg(clon[c], clat[c], slon[n], slat[n])
                if d < bestd
                    best, bestd = Int(n), d
                end
            end
            # Keep scanning two rings past the first hit: a diagonal hit at radius r can be
            # farther in great-circle terms than an axis hit at r+1, and near the poles a 0.5°
            # longitude step shrinks so later rings can be closer still. Two extra rings makes
            # this exact away from the poles and negligibly approximate at them — the target grid
            # is ~4° here, so a marginally suboptimal neighbour cannot matter.
            r_found < 0 && best != 0 && (r_found = r)
            r_found >= 0 && r >= r_found + 2 && break
            r += 1
        end
        best == 0 && continue
        dist[c] = bestd
        if bestd <= max_land_dist_deg
            sand[c], silt[c], clay[c] = ssand[best], ssilt[best], sclay[best]
        end
    end

    is_land = dist .<= max_land_dist_deg
    nfar = count(!, is_land)
    @info "texture mapped onto $ncol columns: $(count(is_land)) within $(max_land_dist_deg)° of an " *
        "LPJmL land cell, $nfar fell back to loam(clay=$(FALLBACK_TEXTURE.clay))"
    if any(is_land)
        d = sort(dist[is_land])
        @info "  match distance over land columns (deg): min=$(round(d[1]; digits = 3)) " *
            "median=$(round(d[cld(end, 2)]; digits = 3)) max=$(round(d[end]; digits = 3))"
    end
    return sand, silt, clay, dist, is_land
end

"""
    texture_fields(grid, sand, silt, clay) -> NamedTuple

Wrap per-column texture vectors as XY `Field`s on `grid`, normalized so each cell's fractions sum
to unity (the `SoilTexture` constructor asserts this).
"""
function texture_fields(grid, sand::AbstractVector, silt::AbstractVector, clay::AbstractVector)
    NF = eltype(grid)
    tot = sand .+ silt .+ clay
    all(t -> t > 0, tot) || error("texture fractions sum to zero in $(count(<=(0), tot)) columns")
    out = map((sand, silt, clay)) do v
        f = Field(grid, XY())
        interior(f)[:, 1, 1] .= NF.(v ./ tot)
        f
    end
    return (sand_fraction = out[1], silt_fraction = out[2], clay_fraction = out[3])
end

"""
    assert_nondegenerate_soil(hydraulics, sand, silt, clay; label)

THE GUARD (O3a step 2).  Rejects any soil configuration in which the plant-available-water
denominator `field_capacity − wilting_point` is not strictly positive — the silent degeneracy of
trap 6.  Also reports the spread of that denominator, so "it ran" is never mistaken for "it has
water stress".
"""
function assert_nondegenerate_soil(
        hydraulics,
        sand::AbstractVector,
        silt::AbstractVector,
        clay::AbstractVector;
        label::AbstractString = "soil",
        min_denominator::Real = 1.0e-4,
    )
    n = length(clay)
    fc = similar(clay, Float64)
    wp = similar(clay, Float64)
    for i in 1:n
        tex = SoilTexture(Float64; sand = sand[i], silt = silt[i], clay = clay[i])
        fc[i] = Terrarium.field_capacity(hydraulics, tex)
        wp[i] = Terrarium.wilting_point(hydraulics, tex)
    end
    denom = fc .- wp
    bad = findall(<=(min_denominator), denom)
    if !isempty(bad)
        i = bad[1]
        error(
            "DEGENERATE SOIL in `$label`: $(length(bad))/$n columns have " *
                "field_capacity - wilting_point <= $min_denominator " *
                "(e.g. column $i: clay=$(clay[i]) fc=$(fc[i]) wp=$(wp[i])). " *
                "plant_available_water would collapse to a constant and silently delete water stress " *
                "(online-coupling-env trap 6, ADR 0082 §4)."
        )
    end
    d = sort(denom)
    @info "GUARD ok [$label]: field_capacity − wilting_point over $n columns — " *
        "min=$(round(d[1]; digits = 4)) median=$(round(d[cld(end, 2)]; digits = 4)) max=$(round(d[end]; digits = 4))"
    return (; fc, wp, denom)
end

"""
    prescribed_texture_soil(grid; csv, porosity, hydrology, kwargs...)

Build the online soil: a single `PrescribedSoilHorizon` named `:soil` spanning the whole column,
with SURFEX porosity (`0.49 − 0.11·sand`, texture-consistent with SURFEX hydraulics) and the
LPJmL-FIT texture mapped onto `grid`.  Runs `assert_nondegenerate_soil` before returning.

Returns `(soil, fields, is_land, texture)` where `fields = (soil = (sand_fraction = …, …),)` is
what must be passed as `fields =` to `SpeedyWeather.LandModel` (or `Terrarium.initialize`).
"""
function prescribed_texture_soil(
        grid;
        csv::AbstractString = TEXTURE_CSV_DEFAULT,
        max_land_dist_deg::Real = 2.5,
        # a finite thickness rather than the library default `Inf`: with one horizon the depth
        # selection is unconditional either way, and `z -= Inf` inside `with_soil_horizon` is
        # avoided. 1000 m is far below anything the exponential spacing reaches.
        default_thickness::Real = 1000,
        # `NoFlow` is Terrarium's default and makes the soil water COMPLETELY IMMOBILE: the state
        # stays at whatever `SoilInitializer`'s `SaturationWaterTable` wrote (vadose zone 0.75,
        # saturated below 5 m), forever, identically in every column — even though the
        # SpeedyWeather adapter faithfully pushes `rainfall`/`snowfall` into the Terrarium inputs.
        # Any soil-moisture distribution measured under `NoFlow` is the INITIALIZER, not a model
        # result. `RichardsEq()` is required for the ADR 0082 §4 `soilmoist` comparison.
        vertical_flow = Terrarium.RichardsEq(),
    )
    NF = eltype(grid)
    porosity = SoilPorositySURFEX(NF)
    horizon = PrescribedSoilHorizon(NF, :soil; porosity, default_thickness = NF(default_thickness))
    strat = SoilStratigraphy(NF, horizon)
    hydrology = SoilHydrology(NF; vertical_flow)                   # hydraulics default = SURFEX
    soil = SoilEnergyWaterCarbon(NF; strat, hydrology)

    sand, silt, clay, _dist, is_land = map_texture_to_columns(grid; csv, max_land_dist_deg)
    assert_nondegenerate_soil(
        hydrology.hydraulic_properties, sand, silt, clay;
        label = "PrescribedSoilHorizon(:soil) from LPJmL texture",
    )
    fields = (soil = texture_fields(grid, sand, silt, clay),)
    return soil, fields, is_land, (; sand, silt, clay)
end
