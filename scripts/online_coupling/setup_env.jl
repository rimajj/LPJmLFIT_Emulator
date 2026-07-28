# Warm the shared ~/.julia depot with Terrarium + SpeedyWeather for the online-coupling work (line O).
# Run on the LOGIN node (it has pkg-server access; compute nodes do not reach GitHub).
#
# NOTE: do NOT call Pkg.status() here — on this Julia/Pkg it throws `KeyError: key "Dates" not found`
# from print_status when the project has a dev'd package carrying [weakdeps] (our LPJmLFITEmulator).
# It is a display-only bug, but it aborts the script before precompile.
import Pkg
Pkg.activate(@__DIR__)
Pkg.precompile()
println("=== PRECOMPILE DONE ===")
using Terrarium, SpeedyWeather, RingGrids, LPJmLFITEmulator
println("Terrarium : ", pkgversion(Terrarium))
println("Speedy    : ", pkgversion(SpeedyWeather))
println("RingGrids : ", pkgversion(RingGrids))
println("Emulator  : ", pkgversion(LPJmLFITEmulator))
println("=== IMPORT OK ===")

# Does SpeedyWeather know how to wrap a Terrarium.LandModel? (the adapter question)
ms = methods(SpeedyWeather.LandModel)
println("\n=== SpeedyWeather.LandModel methods (", length(ms), ") ===")
for m in ms
    println("  ", m.sig)
end
println("\n=== Terrarium abstract vegetation subtypes ===")
using InteractiveUtils: subtypes
for T in subtypes(Terrarium.AbstractVegetation)
    println("  ", T)
end
