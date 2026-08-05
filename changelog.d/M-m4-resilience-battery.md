### Added

- **The M4 RESILIENCE BATTERY (line M, milestone M4; ADR 0055).** `ENGINEERING_STANDARDS` §2's last stubbed
  gates — three `@test_skip false` in `resilience_battery_tests.jl` (item 11) and one in
  `rollout_stability_tests.jl` (item 4) — are replaced by real tests, and the metrics behind them are
  measured rather than quoted. Method reimplemented from Bathiany et al. 2024 (doi:10.1111/gcb.17613);
  `LPJ_resilience` has no licence, so none of its code is copied.
  - `scripts/extract_resilience_reference.py` — the C's own memory from the annual `ind` parquet,
    **52 544 / 52 551 cells (seed1/seed2) × 2000–2019** — the full extent of the historic table, 52 224
    cells present in both seeds — on ADR 0053/0054's four bases. Emits `references/M_resilience_reference_{cells,gradient,series}.csv` + `_meta.json`. Its
    per-year patch-ensemble means are asserted equal to `M_slow_oracle_counts.csv`'s on all 100 overlapping
    cell-years — a different script, a different scan, the same population.
  - `scripts/biome_resilience_probe.jl` — the coupled side: a **3×2 shuffle design** (forcing
    ordered/year-shuffled × demography free/`n_prev`-pinned/absent) plus ADR 0054's teacher-forced anchor
    arm, over a **one-member-per-patch ensemble** of the year-2000 canopy, then a 100-year cycled rollout
    carrying a pool-perturbation recovery experiment. Emits `references/M_resilience_battery.csv`,
    `_shuffle.csv`, `_longrun.csv`.
  - `scripts/extract_biome_forcing.py` gains `FIRSTYEAR`/`LASTYEAR` (default unchanged; the widened
    2000–2019 window reproduces the committed 2010–2019 fixture **byte-identically** on all five cells).
  - CI computes what CI honestly can — the estimator against synthetic AR(1)/ramp series with known
    answers, and a real `slow = nothing` F+E rollout that is perturbed, shuffled and run 60 years — and
    gates the cluster-measured numbers as fixtures. No `src/` change; every committed baseline is
    byte-identical.

### Changed

- `DEVELOPMENT_PLAN` §5's first resilience bullet is annotated in place: its `~0.2-in-wet → ~0.75-in-dry`
  lag-1 autocorrelation gradient is **not reproduced** on this run (see the verdict below), so it cannot be
  used as an acceptance criterion as written. The second bullet (variance/SD vs climate) is the replacement.
- The live P3-vs-Phase-6 inconsistency for this gate is settled: it is Phase-6 *work* pulled forward into
  P3 / line M, because everything it needs exists now. The "Phase-6 scaffold" comments are gone.

### Verdict (full numbers in ADR 0055)

- **The documented AC-vs-climate gradient is not in this model on this basis.** Detrended lag-1
  autocorrelation of the per-patch living tree count is **flat at 0.452–0.541 across all ten P/PET
  deciles**, and the driest decile is the **lowest**, not the highest; `agb` behaves the same
  (0.448–0.544). The seed1-vs-seed2 floor is 0.042–0.062, so the flatness is a result, not noise. Two
  diagnostics rule out shot-noise attenuation as the explanation: the noise-immune `r₂/r₁` sits *below*
  `r₁` everywhere (0.31–0.41) rather than above it, and the between-patch spread is 1.18–12.6× larger than
  the year-to-year variance of the patch mean, i.e. a persistent patch offset rather than sampling noise —
  which is also why the obvious variance-based attenuation correction was written, measured, and discarded.
- **The variance gradient is real and large:** CV 1.149 (driest) → 0.143 (wettest), 8×, monotone over the
  dry half.
- **Carried caveat:** 20 years is all the historic `ind` table has, and linear detrending is a high-pass
  filter, so memory with a timescale ≳ 10 yr is removed with the trend. The honest statement is "not
  resolvable on this window and basis", not "the literature is wrong".
- **The coupled emulator has NO AC gap.** The deployed arm sits **0.1–0.6 between-patch SDs** from the C on
  every cell and both variables (mean 0.32) — the first coupled result on this line inside the noise floor
  everywhere. Consistent with ADR 0054, whose error is in the count **level**: a detrended lag-1
  autocorrelation is blind to a level and to a monotone drift.
- **The shuffle test PASSES and the memory is F's carbon pools, not S's recursion.** Destroying the
  climate's year-to-year sequencing leaves AC at **0.460–0.653** (inherited ≤ 0.146 either way), pinning
  the count-space AR feature leaves **0.391–0.704**, and `slow = nothing` already carries **0.454–0.691**.
  `|free1 − pin1| ≤ 0.135`: **ADR 0054's unanchored recursion drives the count level drift and contributes
  essentially nothing to the memory timescale** — two different failure modes, one of them absent.
- **ADR 0054's teacher-forced anchor arm makes the AC WORSE in two cells** (Amazon `n` 0.066 vs a C of
  0.501 = 2.3 SDs; mediterranean 1.2 SDs). It is a diagnostic, not a fix to deploy — a caveat on the open
  line-S integration point, which was raised on the level improvement alone.
- **No limit cycle** over 100 cycled years (`osc` 0.06–0.50, at or below white noise), nothing non-finite,
  carbon closing at ≤ 2.1e-11 throughout. **Three open findings recorded rather than smoothed over:**
  `semiarid_sahel` does not recover from the pool perturbation (τ 602 yr, r² 0.38, vs 47–54 yr / 0.60–0.73
  elsewhere); there is **no steady state under cyclic forcing** (AGB drifts 1.39–5.15× over the century);
  and the AC-implied timescale (1.2–2.9 yr) is **~20× shorter** than the measured recovery time (~50 yr),
  so an autocorrelation must not be read as a restoring rate.
