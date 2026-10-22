# SpeedyWeather cold-bias work (2026-10-21)

Diffs against SpeedyWeather.jl `main` d6e3286d (CHANGELOG.md excluded). Apply in a clean checkout with
`git apply <file>`. The working branches live in worktrees of `/p/tmp/jamirp/speedy_main_src` (scratch).

| file | branch | contents, in order |
|---|---|---|
| `coldfix-E_vs_main-d6e3286d.diff` | `coldfix-E` | upstream PR #1332 (implicit-solver reference temperature reinitialized) + #1284 (balanced initial state, initial snow) + #1283 (surface Richardson number with the surface temperature, working vertical diffusion) + #1262 (TwoBandShortwave following speedy.f90, DiagnosticClouds bug fixes) + the #1279 glue fix (TwoBandShortwave allocates cloud variables) + **new `FourBandLongwave`** (port of speedy.f90's longwave, water vapour and cloud absorption) + **new opt-in `SurfaceCondition(actual_lapse_rate = true)`** (speedy.f90's surface air temperature) + the NumericalRadiation-extension fix for #1262 + **new opt-in `BettsMillerConvection(ascent_substeps = N, entrainment_mse = true)`** (sub-stepped moist parcel ascent; entrainment by mixing moist static energy, parcel kept saturated; JOURNAL 2026-10-21 night) |
| `coldfix-all_vs_main-d6e3286d.diff` | `coldfix-all` | the same, plus the provisional cold-bias tuning commits of #1279 (b267f018, 54736e2c, 2dcefb0f, 45af26cf: shortwave absorptivities, ozone, ocean roughness, Frierson fₗ = 0.25, ByrneOGormanLongwaveTransmissivity) |

Upstream report of the convection defects: SpeedyWeather #1339 (text: `upstream_issue_1339_convection.md`).

**Upstream reports (everything of value from this branch, owner instruction 2026-10-22):** #1333 (cold near-surface air;
follow-up comment with the stage-by-stage table of the open PRs), #1339 (convection; follow-up comment with three more
tests), #1342 (`FourBandLongwave`, full source in the issue), #1343 (near-surface air temperature in inversions,
`SurfaceCondition(actual_lapse_rate)` + a 2 m diagnostic), #1344 (no clear-sky scattering, `rayleigh_fraction`), #1345
(clear-sky OLR 6–9 W/m² lower at 8 than at 32 layers; slab drift). Texts as filed: `upstream_issue_*.md`,
`upstream_comment_*.md`. Clear-sky backscatter option: `TwoBandShortwaveRadiativeTransfer(rayleigh_fraction = ...)`, coldfix-E ≥ 6ae14204.

Measure with `scripts/online_coupling/speedy_cold_bias_repro.jl` (submit: `sbatch_speedy_cold_repro.sh`; env
`LW=fourband`, `T0=speedy`, `LWKW=` / `CLOUDKW=` parameter lists, `LANDREF=` the observed land table from
`build_speedy_land_reference.py`, `PROFREF=` the GFDL-ESM4 profile table from `build_speedy_profile_reference.py`,
`CONVKW=` convection parameters; convection internals: `speedy_convection_diag.jl`), tabulate with `summarize_speedy_cold_runs.py`. Results: JOURNAL 2026-10-21.
