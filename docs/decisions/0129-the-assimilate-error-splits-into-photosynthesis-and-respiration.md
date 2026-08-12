# ADR 0129 — F's assimilate error at the prototype cell is BOTH photosynthesis and respiration, and the sub-5 m stems the C's daily GPP contains make the split a BRACKET (38–78 % photosynthesis), not a number

- **Status:** accepted
- **Date:** 2026-08-12
- **Line:** M (multi-cell coupled S+F+E) · ADR block 0120–0139
- **Consumes:** ADR 0127 (the three-channel decomposition and this harness), ADR 0125 (the paired
  per-stem arm and the `respcoeff` defect), ADR 0126 (the per-PFT parameters), ADR 0053 (the five basis
  checks — grass, ensemble, year-matching, the lying `units` attribute), ADR 0060 (the >5 m emission cut
  and the never-substitute-silently rule), ADR 0174 §5.3 / `residual-diagnosis` §3e (check a statistic's
  own noise floor before reading a null)
- **Supersedes:** nothing outright. **Narrows** `docs/notes/phase3_fdiff_cbinary_validation.md` §11's
  *"the remaining standalone NPP overshoot is inherited from the standalone GPP, **not** a respiration
  miscalibration"* and `docs/notes/sapwood_bg_design.md` §13's implicit converse. Both were right about a
  channel and wrong to exclude the other.

## 1. Context — the head of the F queue was one number wearing two defects

ADR 0127 decomposed F's surplus above-ground growth into three exactly-additive carbon channels and found
that at the temperate prototype (`temperate_hainich`) **77 % of it is the assimilate error** `bmi_F − bmi_C`
— i.e. the item two earlier decision records had called an *allocation* defect is, at that cell, almost
entirely a *flux* defect. That made `bmi_F/C` = 1.20–1.28 the head of the F queue.

But `bm_inc` is a **net** flux, and two completely different defects produce the same number. Two leads
were on record, each attributing the whole error to a different half and neither measured on the current
basis:

- `docs/notes/sapwood_bg_design.md` §13/§8: F's tree CUE 0.512 vs the C's 0.46 ⇒ **respiration**.
- `docs/notes/phase3_fdiff_cbinary_validation.md` §11: a +17 % GSI-phenology level in standalone GPP ⇒
  **photosynthesis**, with respiration explicitly exonerated (F's total Ra matched the C's to 0.5 % in the
  kernel-isolation configuration).

Both were measured pre-ADR-0125: one year, a standalone canopy, no per-stem pairing, no ensemble.

## 2. The decomposition — an exact identity, no model in it

    bmi = GPP · CUE,   CUE ≡ NPP/GPP = 1 − Ra/GPP
    ⇒  ln(bmi_F/bmi_C) = ln(GPP_F/GPP_C) + ln(CUE_F/CUE_C)      (exactly additive)

Measured on the rung-3 basis: the C's own roster restarted every year, the 25-patch ensemble,
year-matched, `slow = nothing`. F's annual tree GPP is the canopy's own `gpp_acc` read **before**
`annual_step!` (which zeroes it); the harness asserts `npp_acc == bm_inc` on every cell-year (0 violations)
so that `cue = bm_inc/gpp` is the same object on both sides. Harness:
`scripts/biome_sapwood_bg_probe.jl` PART 5/5b/5c; fixture
`test/testitems/references/M_growth_channel_decomposition.csv`, six columns appended (the pre-existing 21
columns are **byte-identical** across all 20 arm-cell rows — verified, ADR 0060's additive rule).

## 3. The result, arm A (the published basis), historic 2010–2019

| cell | GPP_F | GPP_C | F/C | NPP_F | NPP_C | F/C | CUE_F | CUE_C | F/C | `gt5m` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| boreal_siberia | 363.1 | 410.4 | 0.885 | 198.0 | 190.4 | 1.039 | 0.545 | 0.463 | 1.179 | 0.76 |
| **temperate_hainich** | **1220.0** | **1125.7** | **1.084** | **606.0** | **489.9** | **1.237** | **0.496** | **0.435** | **1.140** | **0.92** |
| mediterranean_iberia | 1423.2 | 996.2 | 1.429 | 644.2 | 238.3 | 2.704 | 0.443 | 0.232 | 1.915 | 0.93 |
| semiarid_sahel | 517.5 | 555.7 | 0.931 | −83.8 | 187.8 | −0.446 | −0.163 | 0.337 | −0.485 | 0.78 |
| tropical_amazon | 2583.3 | 2518.6 | 1.026 | −223.2 | 1073.2 | −0.208 | −0.086 | 0.426 | −0.203 | 1.09 |

gC/m²/yr. The two hot cells' arm-A assimilate is negative (the ADR 0125 `respcoeff` defect), so their log
split is **undefined** and is printed as `undef`, not as a number (ADR 0127's sign-changing-denominator
guard, same failure mode).

Arm **Pbg** (per-cohort PFT parameters + the seeded below-ground pool — the most faithful configuration
that exists today) has all five cells positive: Hainich GPP 1.085 / CUE 1.099, boreal 1.027 / 1.210, Sahel
0.906 / 1.209, Amazon 1.022 / 1.041, mediterranean 1.571 / 1.832.

**At Hainich both channels are live.** As measured: GPP **+8.4 %**, CUE **+14.0 %** ⇒ **38 %** of the
assimilate error is photosynthesis and 62 % is respiration (arm Pbg: 46 / 54).

## 4. ⚠ The sub-5 m stems make it a BRACKET, and that is the finding

The `ind` writer emits only stems above 5 m (`fwriteoutput_ind.c:84`), so **F's stand is missing the
sub-5 m trees the C's daily GPP includes, while the C's per-stem NPP is missing them too.** Writing `s`
for their share of the C's tree GPP, `GPP_F/GPP_C` is biased **down** by `(1 − s)` and `CUE_F/CUE_C`
**up** by exactly the same factor — so their **product, the `bmi` ratio, is unaffected** and every prior
`bmi` number stands, but the split between them is not determined. At Hainich `gt5m` (the crown-cover form
of `1 − s`) runs 0.963 → 0.892 over the decade:

| assumption | GPP_F/GPP_C | CUE_F/CUE_C | photosynthesis share |
|---|---:|---:|---:|
| `s = 0` — the sub-5 m stems carry no flux | 1.084 | 1.140 | **38 %** |
| `s` = 2 % (suppressed, ~¼ of understory light) | 1.106 | 1.117 | 47 % |
| `s` = their crown share (`1 − s = gt5m` = 0.919) | **1.180** | **1.048** | **78 %** |

The bracket **straddles the verdict**, so it cannot be left as a footnote.

⚠ **A bookkeeping note that must travel with these numbers:** `CUE_F`/`CUE_C` are means of the per-year
ratios while `bmi_F/bmi_C` is a ratio of the year means, so the product reads **1.236** against the
published **1.239** — agreeing to 0.2 %, not exactly. That is ADR 0127's own mean-of-ratios vs
ratio-of-means distinction, in its harmless form; do not quote the split as an exact factorisation of the
published ratio.

**The discriminator, and why it does not close it.** `gt5m` moves from year to year while F's population
is fixed by construction, so regressing `ln(GPP_F/GPP_C)` on `ln(gt5m)` across years must give slope ≈ +1
if the sub-5 m stems carry their crown share, and ≈ 0 if they carry nothing. Raw, Hainich looks like a
textbook confirmation: **slope 0.83, r 0.890**, and dividing `gt5m` out removes **98.5 %** of the decadal
drift (−0.0777 → −0.0012). But **both series are near-monotone in time**, so that fit cannot separate
"tracks `gt5m`" from "tracks anything else that drifts over the decade". Detrended, it collapses to slope
**0.22, r 0.166**.

**That collapse is NOT evidence against the mechanism — the test has no power, and the probe now measures
that rather than asserting it.** Detrending leaves `gt5m` a residual spread of **0.0102** in log against
the GPP ratio's **0.0134** of weather-year flux error, giving **SE(slope) = 3.63**. A test whose standard
error is 3.6 cannot separate slope 0 from slope 1. (boreal 41.8, mediterranean 5.3 — same verdict; the two
cells with real power, Amazon 0.19 and Sahel 0.83, are unreadable for other reasons: the Amazon's two C
runs differ by 6.7 % (ADR 0125) and the Sahel's raw slope is negative.)

## 5. Decision

1. **Report the Hainich split as a bracket — 38–78 % photosynthesis, 62–22 % respiration — and never as a
   point estimate.** Both leads on record are live; neither may be credited with the whole error and
   neither may be dismissed. In particular `phase3_fdiff_cbinary_validation.md` §11's exoneration of
   respiration does not survive: the CUE channel is at minimum **+4.9 %** and at maximum **+14.0 %**.
2. **Do not read the split at `boreal_siberia`, `semiarid_sahel` or `mediterranean_iberia` at all**
   (`gt5m` 0.76 / 0.78 / 0.93 with no identifying power, and the mediterranean's own growth error is
   2.9×). The Amazon's is readable in arm Pbg only with its 6.7 % two-run caveat attached.
3. **Re-price the two queued CUE-side items against the bracket before scheduling them.** The
   `sapwood_bg` port and the `rd` gate act on the CUE channel only, and `sapwood_bg_design.md` §7 prices
   them at closing ~40–50 % of the CUE gap ⇒ **between ~2 % and ~7 % of the assimilate error** at Hainich.
   That is materially weaker than the queue implied and does not on its own justify the two-struct-field
   Enzyme-path change ADR 0127 §5/§6 scopes. It remains justified by its own `t_nosink` criterion (which
   is an allocation channel, not this one) — the two cases must not be added together.
4. **The bracket closes with a C-side change, not another emulator arm.** Removing the writer's
   `height > height_min` cut (`fwriteoutput_ind.c:84`) under an env gate gives F the C's full stand *and*
   per-stem NPP for the sub-5 m trees, making both `GPP_F/GPP_C` and `CUE_C` like-for-like in one step.
   The `patches/lpjmlfit_rung2_hook_v5.patch` machinery is the pattern (opt-in, inert unless an env var is
   set, gated by `scripts/diagnose_cbinary_rebuild_equality.py`). Scope: one writer condition, a rebuild,
   a ~9 s single-cell re-run. Until then the bracket is the honest statement.

## 6. Consequences

- **The head of the F queue is now two items, not one**, and the larger of them is unidentified. A fix
  aimed at either channel must be scored on **both** columns of PART 5, or it will move the total for the
  wrong reason.
- **One suggestive corroboration, reported as such and not as proof:** the upper end of the bracket
  (GPP **+18.0 %**) is within a percentage point of the independently documented **+17 %** GSI-phenology
  GPP level in `phase3_fdiff_cbinary_validation.md` §11 — two different bases, five years apart in the
  repo's history. If the writer-cut change lands and confirms the upper end, that note's mechanism is the
  named suspect and the phenology is where to look first.
- **Nothing in `src/` changed and no committed baseline moved.** The fixture gained six columns; its 21
  pre-existing columns are byte-identical and the probe's own PART 1 gate against ADR 0125's published
  panel still PASSes.
- **The ssp370 window cannot carry this split yet**: the C's daily GPP exists only for the historic
  window (the single-cell re-runs, and the global daily dataset is 2000–2019). On a scenario run PART 5's
  C columns print `nan` by design. ADR 0128's climate-dependence result is unaffected — it is on `bmi`,
  which the sub-5 m issue does not touch.

## 7. Method notes worth reusing (captured in `residual-diagnosis` and `fdiff-validate`)

- **A ratio of two quantities measured on different populations is fine as a PRODUCT and undetermined as a
  SPLIT.** The population mismatch cancelled exactly in `bmi_F/bmi_C` and landed entirely on the
  decomposition of it. Before decomposing a validated ratio, check whether the *factors* are on the same
  population even when the *product* is.
- **A null from an underpowered test is not a null.** The detrended slope collapsed to 0.22 and the
  temptation was to report "the sub-5 m correction is refuted". Computing the test's own SE (3.63) took
  four lines and one 4-minute job and converted a wrong conclusion into a correctly-bounded one.
- **Two monotone decadal series will fit each other.** Any regression over a 10-year window here needs the
  detrended companion printed beside it, and the detrended companion needs its SE printed beside *it*.
