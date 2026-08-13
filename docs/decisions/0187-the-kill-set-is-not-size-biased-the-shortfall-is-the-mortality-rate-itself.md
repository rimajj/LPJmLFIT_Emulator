# 0187 — The emulator picks the RIGHT KIND of trees to kill: its kill set is not size-biased, and the shortfall is the mortality RATE itself — 3.5× too few discretionary deaths, 58 % of FIT's mass flux

* **Status:** accepted
* **Date:** 2026-08-13
* **Line:** S · ADR block 0170–0189 (tier 3)
* **Answers:** **ADR 0186 §B** — the size-resolved "who dies" comparison it promoted to the primary next
  action. The question is answered and the hypothesis it named is **REFUTED**.
* **Narrows:** **ADR 0186's headline framing** ("the emulator kills the right NUMBER of trees and the
  WRONG trees"). The first half stands. The second half is now measured and is **wrong**: the trees it
  kills are, in size and mass, the trees FIT kills. What is wrong is *how many* of the biomass-bearing
  ones die. **ADR 0186's numbers are all untouched** — count −2.9 %, agb +90.6 %, per-stem mass
  +63…+246 % — this ADR explains them by a different mechanism than the one 0186 pointed at.
* **Does NOT disturb:** ADR 0183 (the hazard is exact as a function), ADR 0185 §7.1 (the limit is the
  stand the map is conditioned on), ADR 0186 §§2–7 (the anchor's algebra and unreachability).
* **Evidence:** `scripts/diagnose_rung2_kill_selectivity.py`, SLURM job **1779616** (~9 min, 24 GB of
  `predict`-matrix dumps, 12 cells × 2 legs). Log `logs/S-killsel.1779616.out`; per-leg CSV
  `/p/tmp/jamirp/S_rung2/kill_selectivity_predict.csv`. No new model run.

## 1. The question, and why it needed a new statistic

ADR 0186 left the investigation here: the count statistic is *satisfied* (−2.9 % stems) while the stand
is wrong (+90.6 % agb, +57 % mean age), so a count statistic provably cannot see the failure and the
remaining question is **which individual trees die**. The hypothesis it named: the arms spare large/old
stems FIT would have killed, which then compound for decades.

Two things had to be got right before that could be measured.

**(a) The kill set had to be found.** ADR 0186 §B planned to read the harness's `rsp_r*_y*_p*.txt` kill
lists and flagged "check they still exist". **They do not** — the `_apply` dirs now hold only
`audit_r0000.txt`, `s_arm_log.txt` and `harness.ready`. They are not needed: under ADR 0123 the rung-2
binary **defers** its demographic kills to the end of the growth loop, so the `mort`-phase roster still
carries every killed stem, flagged `isdead = 1`, on a roster identical in length to `grow` (17 121
records at both phases, 940 flagged, in the development leg). The kill set *and* each killed stem's own
size at the moment of decision are in that one phase.

**(b) The comparison basis.** The arms' stands and FIT's have diverged by construction (ADR 0184/0185:
+89…+312 % agb), so a killed-size histogram is not like-for-like — it would mostly re-measure the
published stand difference. Every statistic here is therefore formed **inside an arm's own stand** and
only then compared. The blessed one is the kill set's **mass selectivity**:

    kill_frac_n = stems killed / stems present        kill_frac_m = agb killed / agb present
    LAMBDA      = kill_frac_m / kill_frac_n

LAMBDA = 1 means the killed stems carry exactly their population share of biomass; < 1 means the
operator spares mass; > 1 means it removes mass preferentially. The hypothesis predicts
LAMBDA_arm < LAMBDA_FIT.

## 2. The verdict — REFUTED, on a validated scorer

ssp370 leg, median over the five FIT-GAIN cells, seeds averaged, discretionary population (§3),
stratified by patch-year (§4):

| arm | LAMBDA | LAMBDA_REC − LAMBDA | pre-registered band |
|---|---|---|---|
| **REC = FIT** | **0.900** | — | the target |
| S0h | 0.996 | **−0.096** | inside REFUTE (< 0.10) |
| S1 | 0.926 | **−0.026** | inside REFUTE (< 0.10) |
| S0 (uniform) | 0.994 | — | the derived self-test, = 1.00 |

Both operator arms land inside the pre-registered refute band, so the pre-registered branch fires:
**the arms' mass selectivity matches FIT's.** If anything the sign is the *opposite* of the hypothesis —
both arms remove slightly MORE mass per stem killed than FIT does.

Two independent corroborations in the same run:

* **Selection differentials** (standardized, level-free, robust to the stand divergence) are near zero
  for everybody: FIT **−0.066** on height, **−0.080** on age; S1 **+0.019** / **+0.010**; S0h **+0.015**
  / **+0.069**. Neither FIT's mortality nor the emulator's is strongly size-selective at these cells.
  ⚠ Note this also narrows a natural reading of ADR 0046: FIT's *age–wooddens gradient* is steep, but
  its one-year mortality is only weakly size-selecting — the gradient is built over centuries out of a
  weak per-year differential, so "FIT strongly kills big trees" is not a thing to reproduce.
* **The size-conditional rate profile has FIT's SHAPE at a lower LEVEL.** P(die | height quintile of
  FIT's own stand), ssp370, FIT-gain cells:

  | arm | Q1 | Q2 | Q3 | Q4 | Q5 |
  |---|---|---|---|---|---|
  | REC = FIT | 0.0231 | 0.0221 | 0.0175 | 0.0188 | 0.0198 |
  | S1 | 0.0075 | 0.0048 | 0.0038 | 0.0044 | 0.0069 |
  | S0h | 0.0073 | 0.0046 | 0.0044 | 0.0042 | 0.0065 |
  | ratio FIT/S1 | 3.1× | 4.6× | 4.6× | 4.3× | 2.9× |

  Both are flat-to-faintly-U-shaped; the arms sit **2.9–4.6× below FIT in every bin**. A size-selectivity
  defect would tilt the profile. This one shifts it.

## 3. What IS wrong: the rate, not the choice

The same table read as a level rather than a shape. On the discretionary population, ssp370, FIT-gain
median: FIT kills **2.1 %** of stems per year, S1 **0.6 %**, S0h **0.5 %** — a **3.5–4.2× shortfall**.
And on TOTAL mortality (every `isdead` stem — what actually moves biomass), the annual mass-removal
fraction is

    FIT 0.03063     S1 0.01781     S0h 0.01811     S0 0.00806     NP 0.00102

so **the emulator's mortality removes 58 % of the biomass FIT's removes each year**, uniformly across
sizes. Compounded over the 81-year leg, `(1 − m_arm)^81 / (1 − m_FIT)^81` gives **2.90×** for S1 and
**2.83×** for S0h — which **exceeds** the observed +90 % agb excess (1.90×). So the reachability clause
passes: this channel is not merely real, it is *more than sufficient* to produce the departure ADR 0186
measured, and no other mechanism needs to be invoked to explain the biomass level.

**How this is consistent with ADR 0186's "the count is on target".** The two are the same fact seen
through populations that weigh biomass differently. FIT's kill set is dominated by **certain** deaths
(`mort_prob ≥ 1` — starving stems: `bm_inc_counter ≥ 5`, `leaf_c` below a sapling's), and the arms
honour those by construction, so the *stem count* largely takes care of itself. But certain deaths are
suppressed stems carrying almost no mass. Biomass turnover is carried by the **discretionary** channel,
and that is where the arms run 3.5–4× short. A count target can therefore be satisfied while the
mortality *mass flux* is 42 % short — which is precisely why ADR 0186's count statistic could not see
this, and why the answer was never going to be found on the count axis.

⚠ **So the operative sentence changes.** Not "the emulator kills the right number of trees and the wrong
trees" but: **the emulator kills the right number of trees, of the right kinds, and far too few of the
ones that carry biomass.** The lever is the discretionary mortality rate. This is NOT a re-opening of
the count channel ADR 0186 closed (§8.8): that closure is about the *emitted stand count*, which is on
FIT's number; this is about the rate of discretionary deaths within it, a different quantity that no
published rung-2 statistic had measured.

## 4. Two basis errors the pre-registered self-test caught — both in the STATISTIC, neither in an arm

This is the methodological content of the ADR, and it is why the S0 self-test was pre-registered at all.
S0 is *uniform* thinning — `f[i] = ρ` for every tree, killed iff `rand() > f[i]`
(`rung2_s_demography_harness.jl:529-530`), a draw independent of size — so **LAMBDA_S0 = 1.00 is
derivable a priori**. That derived value is a hard gate on the scorer, and it failed twice.

**(a) The `isdead` set is not the operator's kill set.** First run: LAMBDA_S0 = **0.287**. The
`mort`-phase flag is the arm's nomination **union the C's own non-negotiable kills** (negative pools /
`isneg_tree`, bioclimatic `survive()`, `cut_year`), which the C applies whatever the arm answers. Those
are dying stems carrying almost no mass, so they drag LAMBDA down — and their share of the kill set is
**wildly arm-dependent**, measured off the audit logs over the 12 cells' ssp370 legs:

    NP 100.0 %      S0 45.8 %      S0h 7.9 %      S1 8.7 %        (forced / total kills)

A statistic whose contamination runs from 8 % to 100 % across the arms being compared cannot rank them.
Fix: restrict to the stems the operator had discretion over, **`mort_prob < 1`**, applied identically to
every arm including REC. The check that it works is NP, which nominates nothing: its discretionary kill
count came out **14 of 12 393**, i.e. zero to rounding.

**(b) The pooled estimator is not 1.00 for a uniform operator.** Second run, still off:
LAMBDA_S0 = **1.19**. Pooled over a leg,

    LAMBDA_pooled = <(1−ρ)>_mass-weighted / <(1−ρ)>_count-weighted   over patch-years,

which equals 1 only if the thinning ratio is uncorrelated with per-stem mass **across** patch-years —
and it is not, because the patches thinned hardest are the dense, old, heavy ones. The operator draws
**once per patch-year**, so the patch-year is the stratum at which the null is exact. The blessed
statistic is therefore the kill-weighted mean over patch-years of
`mean(mass | killed) / mean(mass | present)`. `lam_pooled` is still printed beside it (ADR 0185's rule:
the alternative basis stays on screen rather than being quietly replaced) — and it is visibly different,
S1 1.08 pooled vs 0.93 stratified on the blessed row.

With both fixed the self-test lands at **0.994, i.e. 0.14 σ from its derived 1.000** (per-leg SE 0.174
over 15 S0 legs ⇒ pooled SE 0.045). That is what licenses reading the verdict.

⚠ **And one honest caveat about that tolerance.** `S0_SELFTEST_TOL = 0.15` was pre-registered *without*
deriving the statistic's sampling distribution, which at a single cell is ≈ 0.09 — so at one cell the
tolerance was about 1.7 σ, too tight to be a clean gate, and the single-cell smoke test's 1.19 was
~2 σ, not a defect. The scorer now prints the SE and the σ-departure beside the pass/fail so the
tolerance is interpretable; **the tolerance itself was not moved.** The general clause for the next
pre-registration: *derive the blessed statistic's sampling SE before choosing its tolerance*, or a
noise-limited self-test will read as a defect (and, worse, a real defect will read as noise).

## 5. Decision

1. **The size/mass-selectivity hypothesis is REFUTED and is closed.** Do not re-open "the emulator
   spares big trees" — it is measured at 12 cells, both legs, on a scorer validated by a derived-a-priori
   self-test at 0.14 σ, and it is refuted on three independent statistics (LAMBDA, selection
   differentials, the size-conditional rate profile).
2. **The next question is the DISCRETIONARY MORTALITY RATE**, whose shortfall is 3.5–4.2× and whose
   compounded biomass consequence (2.83–2.90×) already exceeds the observed +90 %. Because the shortfall
   is uniform across size, this is a question about the *magnitude* the operator is asked for, not about
   its ordering — and ADR 0183 established the hazard is exact as a function, so **the live suspects are
   its INPUTS and the thinning ratio ρ that converts a count target into a kill quota.** Specifically:
   ρ is `clamp(target/n_prev, 0.7, 1.3)` and it is formed against the **emitted** (>5 m) count while the
   thinning acts on the **whole** roster — the same emitted-vs-whole mismatch ADR 0186 §2 found in the
   anchor's algebra. That is the first thing to measure, and it is measurable from the arm logs alone.
3. **Do not read this as a defect in the count target.** ADR 0186 §8.8's closure of the *emitted stand
   count* stands. This is a different quantity.
4. **Guardrail 4 is untouched** — nothing was flipped, no default moved, no baseline regenerated.

## 6. What this does NOT establish

* **It does not indict, or clear, the F fast core.** In a rung-2 arm the C grows the stand (skill trap 5);
  the Julia core never runs. The 58 %-of-FIT mass flux is a statement about the substituted mortality
  only.
* **It is 12 cells, not 54 020, and the FIT-gain subset is 5.** The acceptance criterion (CLAUDE.md,
  owner 2026-08-06) is all tree-bearing cells, both scenarios; this is a diagnostic on the discriminating
  subset. **The binding constraint on enlarging it is still the `ERROR043 duplicate roster key` interface
  fault** (line M's `rung2_apply.c`), unchanged from ADR 0186's §D.
* **6 legs are excluded**, all the known `--max-idle` timeouts (`c12045 S1 s2/s3`, `c12235 S0h s1`,
  `c22732 S0h s1/s2`, `c52059 S1 s2`). 234 of 234 audit-bearing legs passed the provenance
  cross-check; the other 24 scored legs are the REC legs, which have no harness and so no audit log —
  stated in the panel rather than hidden.
* **`agb` here is the dumped above-ground pool sum**, `(leaf + sapwood + heartwood − debt) · nind`, not
  the C's `agb_tree.c` quantity (ADR 0127): `excess` and `turn_litt.leaf` are not dumped. They enter
  LAMBDA's numerator and denominator alike, so a level offset in them cancels; the *level* numbers in §3
  carry that small unquantified offset.
* **No climate-sensitivity claim.** Per ADR 0182/0184, a difference of leg means is not a response
  without a drift control, and FIT's own drift is 12.5× the leg signal. Nothing here is a warming
  response number.
