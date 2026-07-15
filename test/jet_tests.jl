# JET.jl static analysis gate (ENGINEERING_STANDARDS §2). Flags type instabilities and latent
# errors across the package's own modules. `target_defined_modules=true` scopes analysis to code
# defined in LPJmLFITEmulator (not its dependencies).
@testitem "JET" tags=[:quality, :jet] begin
    using JET, LPJmLFITEmulator
    JET.test_package(LPJmLFITEmulator; target_defined_modules=true)
end
