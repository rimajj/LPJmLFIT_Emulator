### Added

- **The SpeedyWeather ↔ Terrarium online-coupling harness runs on this cluster (P4).** Terrarium 0.1.3 +
  SpeedyWeather 0.21.1 now install alongside the emulator, and the upstream coupled model has been **verified
  running on a compute node** (6 simulated hours, `vegetation = nothing`, 4608/4608 cells finite, Float32
  held, T_skin −16.7…25.0 °C) — the control run against which our own physics will be judged.
  `[VERIFIED]` **SpeedyWeather ships `SpeedyWeatherTerrariumExt`**, giving
  `SpeedyWeather.LandModel(::SpectralGrid, ::Terrarium.AbstractModel)`, so Terrarium is the *supported*
  land-model socket and we write no atmosphere↔land plumbing. New `docs/p4_online_coupling_design.md` is the
  design of record (every API claim read from the installed packages), new `scripts/online_coupling/` holds
  the harness, and the new **`online-coupling-env`** skill captures the four traps that each cost a failed
  job: Julia **1.10.0 cannot precompile this stack** (`KeyError: "KernelAbstractions"`; 1.10.10 does it in
  81 s), `SpeedyWeather.EarthOrography` **downloads an artifact inside `initialize!`** so assets must be
  warmed on the login node, **Terrarium state is °C not Kelvin**, and `Pkg.status()` throws
  `KeyError: "Dates"`. The design's central finding: Terrarium steps at Δt = 300 s while F is daily and S
  annual, so rate processes couple directly but stateful ones need a piecewise-constant tendency — which
  ForwardEuler integrates to exactly the daily total, preserving conservation by construction. **No
  LPJmL-FIT physics is in the coupled loop yet**; the `FDiffPhotosynthesis` spike is specified in §4.
