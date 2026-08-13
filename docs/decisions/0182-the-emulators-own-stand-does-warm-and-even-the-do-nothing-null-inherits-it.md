# ADR 0182 — The emulator's own stand DOES warm, in FIT's own direction — and even the do-nothing null inherits it

- **Status:** accepted
- **Date:** 2026-08-13
- **Line:** S
- **Supersedes / amends:** amends the line-S handoff's branch B.3 wording (see §6); closes the action
  pre-registered in ADR 0181 §7.3
- **Scripts:** `scripts/diagnose_rung2_stand_warming.py` (new)
- **Artifacts:** `logs/S-standwarm.1773336.out` · `/p/tmp/jamirp/S_rung2_standwarm/stand_warming_per_cell.csv`
  · per-dump caches under `/p/tmp/jamirp/S_rung2_standwarm/cache/`

## 1. The question, and why it was the one worth asking next

ADR 0181 established that the learned count model is a **stand diagnostic**: handed LPJmL-FIT's own stand
it delivers 0.292 of FIT's area-weighted warming response, and the STAND columns carry essentially all of
it (slope 0.994) while the direct climate channel gives 0.016 and the flux channel 0.037. A map driven by
the stand can only produce a warming count if the stand it is handed warms. FIT's own stand shifts ~0.30 of
a cell's own within-leg sd per feature between the legs (ADR 0181 PANEL 1, 51 432 cells). **Whether each
rung-2 arm's OWN stand does the same had never been measured** — and ADR 0181 §7.3 pre-registered the
reading in both directions before the run.

No new run was needed: the rung-2 roster dumps carry full per-tree state at the `grow` rendezvous for every
arm × cell × scenario × seed.

## 2. Basis

| | |
|---|---|
| source | `/p/tmp/jamirp/S_rung2/S_r2s_<scen>_c<cell>_<arm>_roster_s<seed>_dump/roster_rank0000.txt`, 510 dumps, ~38 GB of text |
| phase | **`grow` only** — after this year's turnover/allocation/hazard, before anyone leaves the roster. That is the exact analogue of the runtime feature point (`slow.jl` builds `flux_feature_vector` from the GROWN pools, before `reconcile_demography!` removes anybody). |
| features | the six stand features of `flux_feature_vector` (its columns 5-10), per (year, patch), with the runtime's own formulas — `hmean` fpc-weighted, `agb` = `FDiff.agb_ind`·nind, `lai` = Σ`leaf_c`·`sla`·`nind`, `fpc` capped at 1, `age_mean` nind-weighted |
| shift `z` | per (cell, arm, seed) per feature, `[mean(ssp370 leg) − mean(historic leg)] / sqrt(0.5·(var_hist + var_ssp))` — byte-for-byte ADR 0181 PANEL 1's basis |
| reference | **the `REC` arm at the SAME cells** = FIT's own roster through the pure-observation path, through this same parser. Not PANEL 1's global median (51 432 cells vs 12; ADR 0124). |
| coverage | historic 2000-2019 and ssp370 2020-2100, 25 patches each, both legs complete or the (cell, arm, seed) is excluded and named. **92 of 510 legs excluded**, all accounted for by the two known interface faults (the `ERROR043` duplicate-roster-key deaths and cell 22732's hang) ⇒ 12 scoreable cells, 11 for `S1`. |
| seeds | across-seed mean `z`; the across-seed spread of `‖z‖` is 0.11-0.17, i.e. small against the effects below |

**Basis check passed before anything was read:** `REC`'s median per-feature `|z|` is 0.21-0.37 (median
`‖z‖` 0.809), reproducing ADR 0181 PANEL 1's ~0.30 on 12 cells instead of 51 432. Liveness (ADR 0179's
mandatory first panel): all six features vary in every leg of every arm, zero degenerate cases.

## 3. The result — the FAIL branch is decisively excluded

Pre-registered: PASS if `RATIO` = median `‖z_arm‖/‖z_REC‖` ≥ 0.70 **and** `COSINE` = median direction
agreement ≥ 0.50; FAIL if `RATIO` ≤ 0.30.

| arm | cells | RATIO | COSINE | `‖z‖` arm | `‖z‖` REC | verdict |
|---|---|---|---|---|---|---|
| `S0` (shipped uniform thinning) | 12 | 1.426 | 0.876 | 1.485 | 0.809 | **PASS** |
| `S0h` (decomposition control) | 12 | 1.652 | 0.758 | 1.962 | 0.809 | **PASS** |
| `S1` (trait ordering) | 11 | 1.634 | 0.907 | 1.863 | 0.734 | **PASS** |
| `NP` (persistence null) | 12 | 3.741 | 0.483 | 2.983 | 0.809 | PARTIAL |

**The emulator's stand is not frozen. It moves at least as much as FIT's and in FIT's own direction.** So
the second branch of ADR 0181 §7.3 — "the emulator's stand does not warm, and no S-side retrain can recover
it" — is excluded, and the first branch stands: **the stand carries the signal and the count map still
loses it.** Its size remains ADR 0181 §4's 0.292 of FIT's response, i.e. 2.4× short.

## 4. Two things that stop this being a credit to the emulator

**(a) Split the cells by how much FIT's own stand moves, and the picture is much sharper.** On the 6 cells
where FIT's shift is large the arms track it almost exactly; where FIT barely moves, they move anyway, in
unrelated directions:

| arm | FIT moves a lot (`‖z_REC‖` med 2.23) | | FIT barely moves (med 0.54) | |
|---|---|---|---|---|
| | RATIO | COSINE | RATIO | COSINE |
| `S0` | 1.362 | **0.985** | 1.833 | 0.590 |
| `S0h` | 1.429 | **0.969** | 3.092 | 0.505 |
| `S1` | 1.601 | **0.988** | 2.560 | 0.644 |
| `NP` | 1.814 | **0.910** | 4.681 | 0.272 |

**(b) `NP` — the persistence null, which learns nothing — tracks FIT's stand direction at 0.910 in exactly
those cells.** In a rung-2 arm the **C grows the stand**; the emulator only decides who dies. So the
warming shift in the stand is *inherited from the C's physics*, and every arm inherits it, including the one
that does nothing. ⇒ **this statistic has no power to discriminate between arms.** It can clear or convict
the hypothesis "the stand handed to the map does not warm"; it cannot credit the emulator with the shift.
Read the PASS that way and no other.

**The declared drift control says the same thing from the other side.** The headline `z` is a difference of
leg means, which a monotonically drifting stand produces with no response to the forcing at all (ADR 0178
measured 94-100 % of the arms' apparent count response as drift). Computing the same statistic between the
two halves of the HISTORIC leg — same forcing, no warming excursion — gives a per-decade drift rate of 3.0-3.6
× the arms' warming rate, and **5.39× for `REC`**: FIT is not drift-free either, and on absolute magnitudes
the arms' within-historic decadal movement (0.86 for `REC`, 1.04-1.34 for the arms) stands in about the same
1.5× proportion as their leg shift. ⇒ **the arms' RATIO > 1 is stand MOBILITY, not a stronger warming
response.** Do not quote "the arms warm 1.6× more than FIT".

## 5. Decisions

1. **[DECISION] The "the stand does not warm" hypothesis is closed. Do not re-investigate it.** The stand
   handed to the count map carries FIT's warming direction at cosine 0.97-0.99 wherever FIT's own stand
   moves substantially.
2. **[DECISION] Do not quote the stand-shift statistic as evidence for or against any arm.** `NP` passes its
   direction test as well as `S1` does. In rung 2 the stand is the C's.
3. **[DECISION] The next measurement is the one that closes the loop, and it needs no new run:** run the map
   on **each arm's OWN stand** (these same dumps carry every feature) and score the resulting count
   response. ADR 0181 measured the map on FIT's stand → 0.292; ADR 0177 measured the arms' actual count →
   indistinguishable from a do-nothing null on direction. Those two numbers are not yet reconciled, and the
   gap between them is either the map's attenuation compounding with per-cell direction error, or the extra
   stand mobility of §4(b) diluting the response. **Pre-registered reading:** map-on-arm-stand response
   ≈ 0.292 ⇒ the loss is the map's attenuation and a calibration/target-parameterisation change is the work;
   map-on-arm-stand response ≪ 0.292 ⇒ the arm's own stand mobility is destroying the signal and the
   demography operator is the work.

## 6. The handoff wording this corrects

The line-S handoff's branch B.3 read: *"arm shift ≪ FIT's ⇒ the emulator's stand does not warm ⇒ the defect
is upstream in the fast core and no S-side retrain can recover it."* **The "fast core" attribution is not
reachable from a rung-2 arm**, because the Julia fast core never runs there — the C grows the stand. Had the
FAIL branch fired, it would have indicted the emulator's *demography* destroying a signal the C's physics did
put in. That branch did not fire, so nothing rests on it; the wording is corrected so it is not inherited.

## 7. Gotchas paid for here

- **A per-feature RATIO explodes wherever the reference shift is near zero** (`age_mean` read 26.5 at the
  first smoke cell because `REC`'s own `age_mean` shift there is −0.028). Report the arm's own signed shift
  beside the reference's; keep ratios for the vector norm, where the denominator is bounded away from 0.
- **A difference of leg means is not a response until a drift control says so.** Declare the control with
  the thresholds, before the run, and read the reference's own drift rate too — `REC`'s is the largest of
  all five arms, which would have been very easy to present as an arm defect.
- **Parse the dump's `#H` header for column positions, and remember the name-to-field offset:** the header
  is `#H T phase lon lat …` while the record is `T grow <lon> …`, so name *n* is field *n+1*. Getting it
  wrong fails loudly here (`int('51.25')`) but would fail silently for two columns of the same type.
