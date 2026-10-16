# Copied from /p/tmp/jamirp/esm_online_coupling_sw023 (SpeedyWeather 0.23.0 env). Run on ONE core via sbatch, priority QOS.
# Single-core speed of SpeedyWeather (PrimitiveWetModel, default land/ocean/physics, no output).
using SpeedyWeather, Dates
println("SpeedyWeather ", pkgversion(SpeedyWeather), "  threads=", Threads.nthreads()); flush(stdout)
for (trunc, nl) in ((31, 8), (63, 8))
    sg = SpectralGrid(trunc = trunc, nlayers = nl)
    model = PrimitiveWetModel(sg)
    sim = initialize!(model)
    run!(sim, period = Day(2))                     # compile + warm-up
    ndays = trunc == 31 ? 120 : 45
    t = @elapsed run!(sim, period = Day(ndays))
    s_per_year = t / ndays * 365
    mask = model.land_sea_mask.land_fraction
    nland = count(>(0.5), mask)
    npts = length(mask)
    println(
        "T$trunc L$nl: points=$npts land=$nland  wall=$(round(t, digits = 1)) s for $ndays d  ",
        "=> $(round(s_per_year, digits = 1)) core-s per simulated year, SYPD=$(round(86400 / s_per_year, digits = 0)), ",
        "core-s per land-column-year=$(round(s_per_year / nland, sigdigits = 3))"
    )
    flush(stdout)
end
