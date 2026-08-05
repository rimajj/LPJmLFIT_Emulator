# ADR 0055 — M4, the resilience battery: the documented AC-vs-climate gradient is not in this model, and the memory that IS there is internal

- **Status:** accepted (2026-08-05)
- **Line:** M (multi-cell coupled S+F+E, P3) — ADR block 0050–0069
- **Builds on:** ADR 0050 (per-cell inputs), ADR 0051 (`wscal_leafon`), ADR 0052 (F's soil-water residuals),
  ADR 0053 (the F-side oracle and its four reference bases), ADR 0054 (the S-side oracle; the unanchored
  count recursion). **Supersedes nothing.** Corrects one claim in `DEVELOPMENT_PLAN` §5 (see §2).
- **Code change:** none in `src/` — every committed baseline is byte-identical. Two new measurement scripts,
  six new committed reference tables, and the four `@test_skip` stubs of Gate 4 / Gate 11 replaced by real
  tests. `wscal_leafon` stays `false` by default and the artifact pin stays `_t8`.

## Context

M4 is the last of `ENGINEERING_STANDARDS` §2's gates that was still a stub: three `@test_skip false` in
`resilience_battery_tests.jl` (item 11) and one in `rollout_stability_tests.jl` (item 4). The battery exists
because offline RMSE — and even M3's year-matched levels — say nothing about **dynamics**. An emulator can
hit every annual value and still have the wrong memory timescale, the wrong recovery rate, or a memory that
is not its own. `DEVELOPMENT_PLAN` §5 lists four metrics: lag-autocorrelation-vs-climate, variance-vs-climate,
recovery rate from a pool perturbation, and the shuffle test (S0 vs S1).

Two things make M4 different from a normal "fill the stub" task.

**First, the acceptance criterion was a quotation, not a measurement.** The plan asks the emulator to
reproduce "the ~0.2-in-wet → ~0.75-in-dry gradient". That number comes from the literature; nobody had
measured it on *this* run, *this* window and *this* population. Gating on a borrowed number is how a gate
ends up testing something that is not true of the system it guards, so the reference was measured first.

**Second, ADR 0054 poisons the naive shuffle test.** The shuffle test asks whether the emulator's memory is
genuinely internal or merely inherited from autocorrelated climate — and `DEVELOPMENT_PLAN` §5 already flags
that "an AR emulator can cheat this". ADR 0054 established that the coupled count *is* an unanchored AR
recursion. An unanchored AR recursion manufactures autocorrelation and slow recovery by itself, so a shuffle
test with no control would pass loudly and mean nothing.

**Method reimplemented from Bathiany et al. 2024 (doi:10.1111/gcb.17613).** `LPJ_resilience` carries no
licence, so none of its code is copied.

**Phase bookkeeping, settled:** `DEVELOPMENT_PLAN` §6 schedules the battery in Phase 6, `MEMORY.md` and
`STEERING_PROMPT.md` put it in P3, and the stubs said "Phase-6 scaffold". It is Phase-6 *work* pulled forward
into P3 / line M, because everything it needs exists now and because ADR 0054's recursion is exactly the
failure mode it detects. There is no scaffold left.

## 1. The reference: three method choices, each of which changes the answer

`scripts/extract_resilience_reference.py` measures the C's own memory from `ind_hist_seed{1,2}_all.parquet`,
2000–2019 (the **full extent** of the historic table — checked, not assumed), on ADR 0053/0054's four bases
(tree-only `Type <= 6`; per-**patch** series, because each of a cell's ~25 patches is an independent
realization and the coupled driver runs ONE patch; year-matched; the writer's >5 m population). Output:
**52 544 (seed1) / 52 551 (seed2) cells**, ~1.35 M patch-series each; **52 224** are present in both
seeds and carry the binned gradient below.

Three choices are load-bearing and are applied identically on the emulator side:

**(a) Detrend first.** 2000–2019 is transient (rising CO₂, warming) and a pure linear ramp has lag-1 AC ≈ 1
with no memory at all. Undetrended, the AC of these series is 0.59–0.71; detrended, 0.45–0.54. The whole
apparent "high memory" of the raw series is trend.

**(b) n = 20 is short and the estimator is biased low** by ≈ (1+3φ)/n ≈ 0.16 at φ = 0.75 — comparable to the
entire gradient it is supposed to resolve. `ac1_debias` inverts it (Marriott–Pope/Kendall
φ̂ = (r₁ + 1/n)/(1 − 3/n)); the **gates use the uncorrected `ac1_detr`**, because both sides are measured on
the same 20 points with the same estimator so the bias cancels in the comparison.

**(c) An empty patch is a zero, not a gap.** A patch with no living >5 m tree in year *y* emits no rows, so a
naive `group_by` silently drops it — shortening the series and breaking the lag structure, and doing so
preferentially in exactly the dry cells the gradient is about. Missing `(Cell, Patch, Year)` are filled with 0.

An independent-extractor check ran for free: this script's per-year patch-ensemble means agree with
`M_slow_oracle_counts.csv` (ADR 0054, a different script and a different scan) on **all 100 overlapping
cell-years to 1e-6**. It is asserted in the extractor, not merely noted.

## 2. THE FINDING — the AC gradient is not there; the VARIANCE gradient is

Binned by P/PET decile over the 52 224 cells present in both seeds (bin 1 = driest, 5 222–5 223 each):

| bin | P/PET | `n` AC detr | floor | `n` AC raw | `n` AC debias | r₂/r₁ | `n` CV |
|---|---|---|---|---|---|---|---|
| 1 (driest) | 0.092 | **0.452** | 0.062 | 0.586 | 0.590 | 0.395 | **1.149** |
| 2 | 0.233 | 0.482 | 0.046 | 0.617 | 0.625 | 0.310 | 0.700 |
| 3 | 0.392 | 0.525 | 0.043 | 0.675 | 0.677 | 0.373 | 0.365 |
| 4 | 0.547 | 0.537 | 0.043 | 0.703 | 0.691 | 0.396 | 0.212 |
| 5 | 0.686 | **0.541** | 0.042 | 0.713 | 0.695 | 0.406 | 0.171 |
| 6 | 0.813 | 0.531 | 0.044 | 0.713 | 0.684 | 0.398 | 0.150 |
| 7 | 0.944 | 0.523 | 0.044 | 0.709 | 0.674 | 0.392 | 0.143 |
| 8 | 1.110 | 0.522 | 0.044 | 0.705 | 0.673 | 0.389 | 0.152 |
| 9 | 1.348 | 0.521 | 0.044 | 0.703 | 0.672 | 0.386 | 0.140 |
| 10 (wettest) | 1.767 | 0.522 | 0.044 | 0.710 | 0.673 | 0.386 | **0.143** |

**Lag-1 autocorrelation is flat at 0.45–0.54 across the entire aridity range, and the driest decile is the
LOWEST, not the highest.** The `agb` series behave the same way (0.448 → 0.514). The documented
~0.2-wet → ~0.75-dry gradient is not present in this run on this basis, in either direction and in neither
the detrended nor the raw series. The seed1-vs-seed2 floor is 0.042–0.062, so the flatness is a result and
not sampling noise.

**What IS strongly climate-graded is the variance:** the coefficient of variation runs 1.149 (driest) →
0.143 (wettest), an **8×** gradient, monotone over the dry half. `DEVELOPMENT_PLAN` §5's second bullet
("variance/SD vs climate") is the metric that carries the climate signal here; its first bullet is not.

### 2a. Two diagnostics that rule out the obvious explanation

A per-patch count holds only ~4–11 stems, so the obvious objection is attenuation: lag-1 AC of
signal-plus-white-noise is φ·s²/(s²+q), and dry cells are noisier (CV 8×), so a real gradient could be
flattened by unequal noise. Two checks say it is not:

1. **`r₂/r₁` is the noise-immune estimate.** Additive white noise scales *every* ACF lag by the same factor,
   so r₂/r₁ = φ regardless of q. If the series were badly attenuated this ratio would sit well **above** r₁.
   Measured, it sits at 0.31–0.41 — **below** r₁ everywhere, and just as flat.
2. **The between-patch spread is not year-to-year noise.** `(between-patch variance / P)` over `(the
   year-to-year variance of the patch MEAN)` is **1.18–12.6** in the bin means: the patch-to-patch spread is
   one to two orders larger than what the patch mean actually varies by from year to year. It is a
   *persistent* patch-level offset (patch *i* is denser than patch *j* decade after decade) that cancels in
   the mean, not sampling noise. A variance-based attenuation correction therefore does not apply here, and
   it is deliberately **not** emitted: it would divide by a negative denominator in most cells and report a
   silently self-selected subsample of the rest. That correction was written, measured, and discarded.

Independent corroboration: the `cellmean` basis (average the 25 patches first — ~1/25 of any shot noise)
gives 0.470 → 0.534, equally flat.

### 2b. The honest caveat

**20 years is the full extent of the historic `ind` table, and linear detrending is a high-pass filter.**
Memory with a timescale ≳ n/2 ≈ 10 yr is removed *with* the trend and cannot be distinguished from it on
this window. The implied restoring timescale here is τ = −1/ln(0.52) ≈ **1.5–2.5 yr**, which is short. So
the correct statement is *"not resolvable on this window and basis"*, not *"the literature is wrong"*: a
decadal wet-to-dry memory gradient could exist and be invisible to this measurement. Resolving it would need
a longer transient than this dataset has.

## 3. Decision

1. **The M4 acceptance criterion is the MEASURED reference, not the quoted gradient.** `DEVELOPMENT_PLAN` §5
   is annotated in place with a pointer here so the quote is not re-adopted by a future session.
2. **Both sides of every comparison use the identical estimator** (`detrend` → biased ACF → optional
   debias), reimplemented in Julia in `scripts/biome_resilience_probe.jl` and pinned in CI against synthetic
   series with analytically known answers.
3. **The gate yardstick is the C's own between-patch SD of AC** (0.118–0.242), because the coupled driver
   produces a single 20-year patch trajectory and that is the spread such an estimate samples from.
4. **The shuffle test ships with a memory-removal control** (§5), because ADR 0054's recursion makes the
   uncontrolled version uninformative.

## 4. The emulator side: the memory is the right SIZE, and it is INTERNAL

`scripts/biome_resilience_probe.jl` runs a **3×2 design** (forcing ordered / year-shuffled × demography
free / `n_prev`-pinned / absent) plus ADR 0054's teacher-forced `anchor` arm, over an ensemble of **one
member per patch** of the year-2000 canopy (25 members, 24 at the Sahel) so the emulator ensemble matches
the C's patch ensemble one-to-one. Pinned `_t8`, `wscal_leafon = true`, the five cells IN-SAMPLE.

**(a) There is no AC gap.** The deployed arm (`free0`) is **0.1–0.6 between-patch SDs** from the C on every
cell and both variables — mean 0.32, max 0.6:

| cell | `n`: E / C (miss, in C's between-patch SDs) | `agb`: E / C (miss, in SDs) |
|---|---|---|
| `boreal_siberia` | 0.672 / 0.568 (0.6) | 0.511 / 0.569 (0.4) |
| `temperate_hainich` | 0.537 / 0.514 (0.1) | 0.657 / 0.551 (0.5) |
| `mediterranean_iberia` | 0.476 / 0.456 (0.1) | 0.347 / 0.442 (0.4) |
| `semiarid_sahel` | 0.628 / 0.568 (0.4) | 0.638 / 0.557 (0.4) |
| `tropical_amazon` | 0.481 / 0.501 (0.1) | 0.554 / 0.521 (0.2) |

This is the first coupled result on this line that is *inside* the noise floor everywhere — M3's counts were
4.5–13.9 floors out on three cells. The two are consistent: ADR 0054's error is in the count **level**, and
a lag-1 autocorrelation of a **detrended** series is blind to a level and to a monotone drift. Both
statements are true of the same runs.

**(b) `anchor0` — ADR 0054's attribution arm — makes the AC WORSE in two cells** (`mediterranean_iberia` `n`
0.165 vs a C of 0.456 = 1.2 SDs; `tropical_amazon` `n` **0.066** vs 0.501 = **2.3 SDs**, the single worst
number in the table). Teacher-forcing `n_prev` onto an externally measured series removes the emulator's own
memory and does not replace it with equivalent memory. So the anchor is a **diagnostic, not a fix to
deploy** — a point that matters for the open integration point with line S, which was raised on the strength
of the level improvement alone.

## 5. The shuffle test, decomposed — and two things it reveals

| cell · var | `free0` | `free1` (shuffled) | `pin1` | `fonly1` | inherited | recursion | C |
|---|---|---|---|---|---|---|---|
| boreal `n` | 0.672 | 0.637 | 0.635 | — | +0.036 | +0.002 | 0.568 |
| boreal `agb` | 0.511 | 0.600 | 0.704 | 0.599 | −0.089 | −0.104 | 0.569 |
| Hainich `n` | 0.537 | 0.464 | 0.446 | — | +0.073 | +0.018 | 0.514 |
| Hainich `agb` | 0.657 | 0.580 | 0.715 | 0.691 | +0.077 | −0.135 | 0.551 |
| medit. `n` | 0.476 | 0.460 | 0.391 | — | +0.017 | +0.068 | 0.456 |
| medit. `agb` | 0.347 | 0.493 | 0.498 | 0.454 | −0.146 | −0.005 | 0.442 |
| Sahel `n` | 0.628 | 0.633 | 0.695 | — | −0.006 | −0.062 | 0.568 |
| Sahel `agb` | 0.638 | 0.653 | 0.698 | 0.488 | −0.015 | −0.044 | 0.557 |
| Amazon `n` | 0.481 | 0.514 | 0.518 | — | −0.033 | −0.003 | 0.501 |
| Amazon `agb` | 0.554 | 0.552 | 0.656 | 0.611 | +0.001 | −0.104 | 0.521 |

**PASS, and by a wide margin: the memory is internal.** Destroying the climate's own year-to-year sequencing
leaves the state's autocorrelation at **0.460–0.653**, and `inherited` is at most **0.146** in either
direction — almost none of it was taken from the forcing to begin with.

**And it is not the AR recursion.** `pin1` (the DRF's explicit count-space AR feature carrying nothing from
year to year) stays at **0.391–0.704**, and `|recursion|` is ≤ **0.135**. `fonly1` — no demography at all —
already sits at **0.454–0.691**. So the memory lives in **F's carbon pools**, not in Component S's
recursion. This is the finding that makes the shuffle test non-vacuous here, and it is *not* what ADR 0054
would have led one to expect: **the unanchored recursion drives the count LEVEL drift, and contributes
essentially nothing to the memory timescale.** Two different failure modes, one of which is absent.

⚠ `pin` is not a total memory-removal control and must not be reported as one: the density update stays
recursive (the ratio `target/n_prev` is applied to the standing roster), so what survives in `pin1` is
memory reaching the count model through F's canopy features — which is exactly the term being isolated.

## 6. Recovery rate and long-horizon stability — two open findings

`slow` live, 100 years of **cycled** 20-year forcing, every tree carbon pool halved at year 21:

| cell | τ_rec (yr) | r² of the log-linear fit | drift (last20/first20) | min/init | max/init | osc |
|---|---|---|---|---|---|---|
| `boreal_siberia` | 54.1 | 0.727 | 5.15 | 1.000 | 12.45 | 0.061 |
| `temperate_hainich` | 52.3 | 0.649 | 3.14 | 0.826 | 3.80 | 0.092 |
| `mediterranean_iberia` | 47.0 | 0.687 | 2.87 | 1.000 | 7.77 | 0.500 |
| `semiarid_sahel` | **601.7** | **0.377** | 4.65 | 0.296 | 2.30 | 0.296 |
| `tropical_amazon` | 50.4 | 0.601 | 1.39 | 1.000 | 1.91 | 0.143 |

**PASS on the failure mode this gate exists for:** no spurious limit cycle anywhere (`osc` 0.06–0.50, at or
below the white-noise value of 0.5, nowhere near the → 1 of a two-year flip-flop), nothing non-finite, and
carbon still closes at the S↔F handoff (≤ 2.1e-11) after a century.

**Open finding 1 — the semi-arid cell does not recover.** Four cells relax with an e-folding time of
47–54 yr at r² 0.60–0.73; `semiarid_sahel` sits at τ 602 yr with r² 0.377, i.e. it neither recovers on a
century nor relaxes as a single exponential. That is the same cell ADR 0052 identified as running too dry,
and the same one whose F-only recovery in CI closes to only 0.92× of the initial departure in 19 years.

**Open finding 2 — there is no steady state under cyclic forcing.** With the forcing exactly periodic,
AGB still grows **1.39–5.15×** over the century (`max/init` up to 12.45 at the boreal cell). A model at
equilibrium under a periodic forcing would sit at drift ≈ 1. The gate bounds this drift; it does **not**
bless it, and the test says so. It is consistent with ADR 0053's free-running canopy drift measured over
ten years, now seen over a hundred.

**Open finding 3 — an autocorrelation is not a recovery rate.** The AR(1) timescale implied by the AC,
τ = −1/ln(r₁), is **1.2–2.9 yr**; the measured pool-perturbation recovery is **~50 yr** — a **≈20× gap**.
They are different quantities (fast year-to-year fluctuation vs slow biomass regrowth), so
`DEVELOPMENT_PLAN` §5's reading of the AC as "the autoregressive memory timescale" holds only for the
fluctuation, never for the restoring rate. Both are now measured and both are gated, separately.

## 7. Consequences

- **M4 is done and P3's gate list has no stubs left.** Gate 4 and Gate 11 compute the estimator and the
  mechanism every CI run and pin the cluster-measured science as fixtures.
- **`DEVELOPMENT_PLAN` §5 bullet 1 is annotated in place** and bullet 2 (variance/SD vs climate) is the
  acceptance criterion that survives. Do not re-adopt the quoted AC gradient without re-measuring.
- **The line-S integration point (ADR 0054, `n_prev`) gains a caveat, not a retraction:** anchoring fixes
  the level and *costs* AC fidelity in two cells. Whatever S lands should be scored on both.
- **Three open findings above are line-M work, not blockers on M4:** the Sahel's non-recovery, the absent
  steady state under cyclic forcing, and (from §2b) the fact that a 20-year window cannot resolve
  decadal memory even in the C.
- **Not attempted:** the ramp/hysteresis experiments `DEVELOPMENT_PLAN` §5 makes conditional on LPJmL-FIT
  proving multistable. Nothing here shows multistability, so the condition is unmet.
