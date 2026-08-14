### Added

- **A reproducible end-to-end speed harness** for the coupled emulator and for the LPJmL-FIT C binary on
  the same cells and years (line O, rung 5-pre; ADR 0084): `scripts/bench_speed_gate.jl` (Julia — three
  arms S+F+E / F+E / F, single-threaded, per-cell-year, per-patch-year and per-cohort-year, machine-readable
  `logs/bench_speed_gate.csv`), `scripts/bench_speed_gate_c.sh` (C — parameterised cell block, two run
  lengths differenced so every per-run start-up cost cancels, `lpjcheck` pre-flight, completion-line gate),
  and `scripts/profile_fdiff_hotspots.jl` (read-only attribution: sampling profile, an `nlambda` sweep, and
  leaf-kernel microbenchmarks).

### Measured (ADR 0084)

- **Cell 42490 (Hainich), npatch 25, 1 core**: LPJmL-FIT C **0.2666** core-s per cell-year (marginal rate;
  0.2884 over the 21-cell block 42480–42500); emulator **1.1169** at F+E and **1.2329** at full coupled
  S+F+E ⇒ **4.62× slower than the model it replaces**. ADR 0093's 3.8× is reproduced (its F+E arm to
  +1.9 % across 403 commits) — the increase comes from putting Component S in the loop, which its harness
  never did, and from taking the C's marginal rather than naive rate.
- Component S costs 5.0–22.1 % of the coupled run across the five biome cells (9.4 % at Hainich); the
  energy closure E costs 0.9 %; the fast core is **99 %**.
- **82.7 % of the emulator's runtime is the λ solve.** `solve_lambda` takes its Newton derivative by
  central finite difference, so each of 25 iterations costs three `photosynthesis` evaluations — 78–79
  calls per individual per day against the C's ≤ 30. Sweeping `nlambda` (a parameter, no source change)
  gives **4.10× at nlambda=3 for −0.03 % on GPP**. A separate **26.5 %** of runtime is three
  temperature-only `q10^` power calls recomputed on every one of those calls.

### Verdict

- GPP is **non-monotone in `nlambda`** (±2.1 % over {1,2,3,6,12,25}), so 25 iterations are **not** evidence
  of convergence. Mechanism not verified; raised to line M as a fast-core physics question alongside the
  hand-over request for `solve_lambda`.

### Notes

- The T63/T31 allowances in `EXECUTION_PLAN.md` §0 (0.030 / 0.0135 core-s per cell-year) are a
  **convention** — 10 % of a measured SpeedyWeather coupled cost — not an owner requirement. Against a
  CMIP-class 1° atmosphere nothing binds. From the corrected 1.2329, T63-class needs 41× and T31-class 91×.
- Integration points raised: `solve_lambda` hand-over to **line M** (`lines/M/STATE.md`, six-part
  pre-registered equivalence criterion), and a **required speed CI gate** to the integrator
  (`MEMORY.md` §3; a runner cannot host the 180 MB `_t8` artifacts or reproduce cluster timings, so the
  gate must threshold a ratio measured inside its own job, on arm F).
