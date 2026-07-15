# Aqua.jl quality gate (ENGINEERING_STANDARDS §2). Catches the bug classes agents introduce:
# method ambiguities, undefined exports, unbound type params, stale/missing deps, type piracy.
@testitem "Aqua" tags=[:quality, :aqua] begin
    using Aqua, LPJmLFITEmulator
    Aqua.test_all(LPJmLFITEmulator)
end
