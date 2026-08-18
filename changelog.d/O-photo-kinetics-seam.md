### Added

- **A hoistable seam for the temperature-only photosynthesis kinetics — landed bit-identical and
  deliberately INERT ([ADR 0087](docs/decisions/0087-the-photosynthesis-kinetics-seam-is-landed-and-inert.md)).**
  `FDiff.photo_kinetics(p, temp) -> (fac_kin, gammastar)` lifts the Michaelis–Menten kinetics
  (`photosynthesis.c:66-70`) out of the `photosynthesis` body, and a new `kin` keyword argument lets a
  caller looping at one temperature pass them in; the default recomputes them, so **all 9 existing call
  sites are bit-identical and no flag guards the change**. `ko`/`kc`/`tau` depend on `temp` alone, yet the λ
  solve re-evaluates them on each of its ~78 kernel calls per individual-day — the 26.5 % of runtime
  [ADR 0084](docs/decisions/0084-the-speed-gate-exists-and-the-38x-is-reproduced-and-worse.md)'s profile
  attributes to `^(::Float64,::Float64)`. ⚠ **This is worth 0 % on its own and no speed-up is claimed:**
  those 78 calls originate inside `solve_lambda`, which line M owns, so realising the expected ≈1.36× needs
  two lines in M's file. Landing O's half inert was the agreed split. Gated by
  `test/testitems/o_photo_kinetics_seam_tests.jl`, which asserts bitwise equality (`===`, never `≈`) over a
  3 240-call sweep across both photosynthetic pathways, the SLA-capped Vcmax branch, the learned-Vcmax
  `vm_scale` hook and Float32, and pins `photo_kinetics` against a frozen copy of the pre-refactor
  arithmetic.

### Changed

- **The claim "Float32 readiness is gated" is corrected: the interface types are Float32-clean, the
  photosynthesis kernel's arithmetic is not** (ADR 0087 §5, found by the seam's own gate). Measured — the
  exponent literal `0.1` is a `Float64`, so `(temp − 25) * 0.1` promotes and `Float32 ^ Float64 → Float64`
  carries double precision through every downstream quantity: `photo_kinetics` returns
  `Tuple{Float64,Float64}` for `PhotoParams{Float32}`, **`temp_stress` promotes identically with no
  involvement from the seam at all**, and `photosynthesis` consequently returns all four values as
  `Float64` for a fully-Float32 call. The four existing "(SpeedyWeather-coupling type)" testitems and
  `@test c.npp isa Float32` all still pass, because the **output structs** are Float32-parameterised and
  convert on assignment — they never gated the arithmetic. Consequence for the online work: a coupled run
  at single precision would silently compute its hottest kernel in double precision, so any expectation of
  Float32 speed or memory there is unfounded. **Not fixed here on purpose** — making the literals
  type-generic would move numbers, so it needs its own opt-in and its own re-measure rather than riding
  along on a bit-identical refactor. The behaviour is pinned by the new testitem instead, so a future
  single-precision change fails loudly and lands the reader on the reasoning.

### Fixed

- **Two defects in the ADR record, both from the 2026-08-17 patch-ensemble session: a duplicate decision
  number and a title that asserted a mechanism its own section kills.** The patch-scaling ADR was committed
  as `0085`, which the online `plant_available_water` clamping decision (2026-08-14) already held and was
  already indexed, and it was never added to `docs/decisions/README.md` at all; it is renumbered to
  **[0086](docs/decisions/0086-lpjmlfit-cost-is-999-percent-patch-ensemble-and-the-patch-count-is-a-pure-variance-knob.md)**
  (the incumbent keeps `0085` — it is older, indexed, and cited from four skills and a committed scorer) and
  both rows are now in the index. Its title also read *"the patches are COUPLED through a shared gene
  pool"*, which its own §5a measures and **kills** at Hainich and at the Amazon; retitled to what it
  actually concludes — the patch count is a pure **variance** knob, with no patch-count bias. A reader who
  stopped at the title carried away the opposite of the result. No measurement, number or decision changed;
  the correction is recorded in a box at the top of the file, and the references that meant the patch
  ensemble (`lines/O/STATE.md`, the `speed-gate` skill's trap 0) now point at 0086.
