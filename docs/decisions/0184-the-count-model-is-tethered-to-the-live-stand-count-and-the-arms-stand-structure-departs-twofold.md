# ADR 0184 — the rung-2 count model is TETHERED to the live stand count, so the warming-response question is unanswerable as run; and the arms' stand STRUCTURE departs by 2×

* **Status:** accepted
* **Date:** 2026-08-13
* **Line:** S
* **Supersedes:** nothing. **Narrows:** ADR 0177 §3–4, ADR 0182 §3. **Explains:** ADR 0180 §4 and ADR 0181 §7.4 as one mechanism.
* **Scripts:** `scripts/diagnose_rung2_map_on_rec_stand.jl` (new), `scripts/diagnose_rung2_map_target_response.py` (new), `scripts/rung2_s_demography_harness.jl` (made includable)

---

## 1. The pre-registered action, and why it needed no model run

Line S's handoff (STATE §B) fixed the next action before this session: three measured numbers did not fit
together, and the gap between them was where the warming response was being lost.

| ADR | what it said |
|---|---|
| 0181 | handed FIT's OWN stand, the count model turns a warming stand into a warming count at slope 0.994 |
| 0182 | each arm's OWN stand does warm, aligned with FIT's (cosine 0.97–0.99 where FIT's stand moves) |
| 0177 | yet the arms' realised count response is indistinguishable from a do-nothing null ON DIRECTION |

The instruction was to run the map on each arm's **own** stand and score the resulting count response, with
a two-branch pre-registered reading (the map's own attenuation vs the arm's stand mobility).

**It needed no new run, and less work than the handoff assumed.** `rung2_s_demography_harness.jl` already
records `target` — `DRF.predict` on that arm's own stand — at **every** rendezvous, in
`<apply>/s_arm_log.txt`. Four of the five arms were therefore already measured. Only `REC` (FIT's own
roster) had no log, because `REC` is the pure-observation path and no harness starts; that one column was
supplied by replaying the `REC` dumps through the same shipped functions.

Two quantities, per cell and per arm, differing by exactly one thing — the substitution operator:

```
ASK(arm, cell) = response of the count the MAP ASKED FOR   (`target`)
GOT(arm, cell) = response of the count the STAND REACHED   (`n_emit`, the grown roster)
```

## 2. The reader is gated bit-identically, which is what licenses the reference

`diagnose_rung2_map_on_rec_stand.jl` does **not** re-derive the feature row: it `include`s the harness and
reaches its `Tree`/`pools_of`/`flux_drivers`/`n_emitted`, which reach the shipped
`EM.flux_feature_vector` + `DRF.predict` (ADR 0023 — a copy would make the copy the thing measured). The
harness's `exit(main(ARGS))` was wrapped in the repo's existing `PROGRAM_FILE` guard to allow this.

**The gate:** in year 2000 no arm has yet killed anything, so the offline reader's row must equal the live
rendezvous reader's. It does, to the last printed digit — `target = 6.819800183403388`, `n_emit`,
`bm_inc`, `growth_eff`, `water_stress` and `soilmoist` all identical at cell 12045 patches 0–2. A
`grow`-phase vs `mort`-phase cross-check of FIT's own count response agrees in sign at **12/12** cells.
Coverage gate: **145 of 480 legs excluded** (the known `ERROR043` duplicate-key fault and the cell-22732
hang), leaving the same **12 scoreable cells** as ADR 0182, with ADR 0177's split — FIT thins at 7, gains at
5 ({12045, 22990, 32628, 42973, 44048}).

---

## 3. THE HEADLINE — the map's output is pinned to the count it is handed

Every one of the **767** rung-2 dumps was run `--n-prev=roster`, which hands the count model the live
stand's own current stem count as feature 11. Measured over all patch-years:

| arm · leg | median ρ | median \|ρ−1\| | frac ρ ∈ [0.95, 1.05] | p05 – p95 |
|---|---|---|---|---|
| `REC` historic | 1.0034 | 0.0232 | **84.3 %** | 0.950 – 1.068 |
| `REC` ssp370 | 1.0045 | 0.0211 | **83.5 %** | 0.951 – 1.080 |
| `S1` historic | 0.9906 | 0.0271 | **87.3 %** | 0.942 – 1.050 |
| `S1` ssp370 | 0.9955 | 0.0307 | **84.6 %** | 0.933 – 1.063 |

`ρ = target / n_prev` is the whole demographic decision. **In ~85 % of patch-years the model asks for a
count within ±5 % of the one it was just given**, and its median per-year authority is a **2–3 % nudge**.
The [0.7, 1.3] clamp is almost never the binding constraint (ρ ≤ 0.70 in 0.0–1.5 % of patch-years, ρ ≥ 1.30
in 0.0–0.8 %) — **the tether, not the clamp, is what limits the arm.**

## 4. Consequence 1 — the ASK/GOT decomposition is degenerate, and "the operator is faithful" is an artifact

`ASK ≈ GOT` at essentially every cell and every arm (`S1`: +0.490/+0.460, −8.523/−8.584, −4.177/−4.184,
−16.175/−16.296, +3.283/+3.576 …; median |GOT/ASK| ≈ 1.02–1.10). Read naively that says the operator
transmits the map's ask faithfully and the loss is elsewhere. **That reading is wrong.** ASK and GOT are
both within a few per cent of the same live count *by construction of the tether*, so their agreement
carries no information about the operator at all. The decomposition the handoff asked for is not
identifiable on this data.

## 5. Consequence 2 — the basis check is passed by the persistence null, so THERE IS NO VERDICT

The pre-registered basis check was `ASK_gain(REC) ≥ 4` of 5, and it passed at **5/5** — with `REC` also
scoring 7/7 on the thin cells, **12/12** overall, and a pooled ASK slope of **1.058**. That looks like the
map reproducing FIT cell for cell.

**It has no power.** The null "`target = n_prev`", which learns nothing, returns FIT's own count and
therefore scores 12/12 *by construction*. The blessed statistic cannot distinguish the model from that
null, so none of these numbers may be quoted as skill.

| arm | ASK gain | GOT gain | ASK thin | GOT thin | ASK all | GOT all | ASK slope (I²) | GOT slope (I²) |
|---|---|---|---|---|---|---|---|---|
| `REC` | **5/5** | 5/5 | 7/7 | 7/7 | 12/12 | 12/12 | 1.058 (100 %) | 1.062 (100 %) |
| `NP` | 1/5 | 1/5 | 7/7 | 7/7 | 8/12 | 8/12 | 2.148 (100 %) | 2.533 (100 %) |
| `S0` | 2/5 | 2/5 | 6/7 | 7/7 | 8/12 | 9/12 | 1.343 (92.7 %) | 1.474 (92.7 %) |
| `S0h` | 2/5 | 2/5 | 7/7 | 7/7 | 9/12 | 9/12 | 0.499 (99.6 %) | 1.500 (99.1 %) |
| `S1` | 2/5 | 2/5 | 6/7 | 6/7 | 8/12 | 8/12 | 1.371 (98.5 %) | 1.469 (98.5 %) |

The verdict expression fired `CONDITIONING-LIMITED` (`max ASK_gain(arms) = 2 ≤ 2`). **That branch is
overridden here and recorded as NO VERDICT**, because its premise — that ASK and GOT are separable — is
false under §3–4. This is line S's own standing gotcha ("a pre-registered threshold is not a pre-registered
verdict") firing on a probe that was written *with* that gotcha in its header. The threshold was right; the
model of the experiment behind it was wrong. **Slopes are reported and are not a summary** (I² 92.7–100 %,
ADR 0177 §4).

## 6. It reconciles ADR 0177, ADR 0180 and ADR 0181 §7.4 as ONE mechanism

* **ADR 0180** — de-leaking `n_prev` buys 2.85× on the climate channel. Of course: the leak is the tether.
* **ADR 0181 §7.4** — flipping `roster_n_prev` is *negative* on the aggregate (0.707 → 0.292). Also of
  course: removing the tether makes the model expressive but exposes its absolute-level calibration.
  ⇒ **with the live count the model is accurate but MUTE; without it, expressive but mis-levelled.** Those
  are not two findings, and neither is evidence about the warming response.
* **ADR 0177's null-on-direction then follows with no statement about the learned map at all.** The arms'
  counts track their own stands because the map is pinned to those stands; the map contributes ±3 %/yr.
  ADR 0177 §3's "indistinguishable from doing nothing" is **narrowed**: on this configuration the model is
  *structurally* incapable of doing much, so the result was never a measurement of what it learned.

⚠ **The handoff's own anchor was also wrong on basis grounds.** It pre-registered "≈ 0.292". `roster` is a
real stand count, i.e. ADR 0181's **CTRL** (leaked) arm at **0.707**, not its de-leaked ABL at 0.292. Both
are moot here: 0.707/0.292 are area-weighted aggregates over 51 767 one-step-forced cells and this axis is
12 free-running ones.

---

## 7. SECOND, INDEPENDENT FINDING — the stand's SIZE STRUCTURE departs by 2×, and no count statistic sees it

`roster` mode re-anchors the *count* to the C every year. **Nothing anchors the stand's size/age
structure.** Median over cells of (arm − `REC`)/|`REC`| at each leg's terminal year:

| arm · leg | n_emit | hmean | hmax | agb | lai | fpc | age_mean |
|---|---|---|---|---|---|---|---|
| `S1` historic | +12.6 % | +7.8 % | +5.9 % | **+38.4 %** | +23.4 % | +25.5 % | +22.7 % |
| `S1` ssp370 | **−14.6 %** | +16.4 % | +23.8 % | **+106.1 %** | +19.1 % | +22.3 % | **+72.5 %** |
| `S0h` ssp370 | −14.3 % | +20.2 % | +18.8 % | +99.1 % | +20.7 % | +26.5 % | +84.1 % |
| `S0` ssp370 | −0.4 % | +12.6 % | +13.4 % | +41.5 % | +8.3 % | +7.8 % | +31.1 % |
| `NP` ssp370 | +4.9 % | +38.3 % | +44.6 % | **+311.6 %** | +25.2 % | +67.5 % | +160.1 % |

(FIT-gain cells; the FIT-thin cells are the same shape — `S1` ssp370 −14.9 % stems, **+98.8 %** agb,
+47.6 % age.) By 2100 the arms hold **~15 % fewer stems but twice the above-ground biomass and 47–84 %
higher mean age**: a stand thinned into fewer, larger, older trees. The departure **grows monotonically**
(`S1` agb +38 % → +106 % between the legs), and even the do-nothing null departs — worst of all, because
sparing everyone overgrows the stand.

**This is where a real conditioning defect lives, and it is invisible to every count-based statistic on
this line so far.** ADR 0182 measured the stand *shift* (a z-score) and found it aligned with FIT's; that
remains true and is **narrowed** here — a correctly-directed shift on top of a 2× displaced level is not
the same conditioning, because the map is a nonlinear function of the level and is being evaluated where
FIT's stands never go. Same shape as ADR 0127's `keep`-ratio trap: a right ratio over a wrong level.

## 8. Controls

* **Drift (ADR 0182's declared control).** Within the historic leg, where FIT and the arm see the same
  forcing, `REC`'s own count drifts **−2.44 stems/decade** while the leg-to-leg "warming rate" is
  **+0.19/decade** — the drift is **12.5× the signal**, and it is largest for FIT itself (as in ADR 0182).
  ⇒ **no number here is a climate sensitivity** (ADR 0177 §5 reconfirmed). What the numbers *are* is a
  comparison of arms against FIT on one identical, drift-contaminated axis, which is legitimate for the
  attribution question and for nothing else.
* **Frozen boundary (`ssp370frz`).** The direct-boundary share of the ASK is small and not sign-consistent
  (`NP` +0.160, `S0` −1.577, `S0h` −0.167, `S1` −0.071), consistent with ADR 0179's flat climate channel.
  It freezes only the 4 columns the emulator sees, so it is not a frozen-climate control for the stand
  (ADR 0181 §6).

## 9. What this does NOT say

* It does **not** say the count model has no warming response. It says this configuration cannot measure
  one. ADR 0181's 0.292 on a de-leaked global table stands and is the live estimate.
* It does **not** indict the Julia fast core, which never runs in a rung-2 arm (the C grows the stand).
* It does **not** indict the ported hazard: ADR 0183's exactness is a statement about a function given its
  inputs and is untouched.
* `S0h`'s ASK slope of 0.499 against a GOT slope of 1.500 is the one place ASK and GOT visibly separate.
  With I² 99 %+ and one seed surviving the gate at several cells, **it is not interpreted here.**

---

## 10. Decision

1. **No verdict is recorded on the operator-vs-conditioning question.** The axis is degenerate (§4–5).
2. **`roster` mode is recorded as unsuitable for any response claim.** It remains correct for what ADR 0175
   introduced it for — matching the training basis for a *one-step* fidelity measurement — and every
   published rung-2 number stays on that footing. Any future response arm must run `--n-prev=predict`, the
   shipped coupled path, in which `n_prev[patch] = target` is the model's own free-running recursion and ρ
   is a genuine prediction rather than a nudge to a given answer.
3. **A `predict`-mode smoke matrix was run this session and it SUCCEEDS** (12 jobs: cells 12045 + 42757,
   arms `REC`/`NP`/`S1`, both legs, 1 seed; all 12 completed). `predict` mode had **never been run** in this
   harness — all 767 prior dumps are `roster` — so it was smoked before committing to the full matrix. The
   run tag encodes `NPREV` (`S_r2s_<scen>_c<cell>_<arm>_predict_s<seed>`), so nothing was overwritten.

   **§10.4 below was pre-registered on the wrong statistic, and the smoke caught it.** The criterion was
   "median |ρ−1| > 0.10". Measured, `S1` ssp370: **0.0237 (`roster`) → 0.0366 (`predict`)** — it does not
   reach 0.10, and on that reading the experiment would have been abandoned. **But |ρ−1| is the wrong
   metric.** ρ is the *year-on-year* ratio `target/n_prev`, and in `predict` mode `n_prev` is the model's own
   previous target, so ρ is a ratio of two DRF outputs on barely-changed inputs — it is near 1 in **both**
   modes because a tree ensemble's output is smooth, not because the model lacks authority. What separability
   needs is that the map's count *state* decouples from the *live stand*, i.e. `target/n_emit`:

   | arm · leg | median `target/n_emit` | median \|·−1\| | frac ∈ [0.95, 1.05] | p05 – p95 |
   |---|---|---|---|---|
   | `S1` `roster` ssp370 | 0.9979 | **0.0234** | 92.1 % | 0.956 – 1.048 |
   | `S1` `predict` ssp370 | 1.0149 | **0.2406** | 23.2 % | 0.679 – 1.710 |
   | `S1` `predict` ssp370, 2081–2100 | 1.0039 | **0.2767** | — | 0.674 – 1.858 |

   ⇒ in `roster` mode the map's target **is** the live count (±2.3 %), which is §4's degeneracy stated as a
   number; in `predict` mode it decouples by **±24 %** (±28 % late century, up to 1.86× at p95). **ASK and
   GOT are separable in `predict` mode and not in `roster` mode**, so the loop-closure question is
   answerable there. The full matrix is warranted and was submitted.
4. **Pre-registered reading for the full `predict` matrix, fixed here before its results are read.**
   * **Report the separability metric FIRST** — median |`target`/`n_emit` − 1| per arm and leg. It must
     exceed **0.10** or that arm's sign counts are uninterpretable for exactly the reason in §5. (Do **not**
     use |ρ−1|; see §10.3.)
   * Then, on the blessed statistic (sign agreement on the FIT-gain cells for `ASK` and `GOT`, with `NP`
     scored in the same process and `REC` as the reference):
     - `ASK_gain(S1) ≥ 4` with `GOT_gain(S1) ≤ 2` ⇒ **operator-limited**: given real authority the map asks
       for FIT's gain and the thin-only operator cannot deliver it.
     - `ASK_gain(S1) ≤ 2` ⇒ **mis-levelled, not mute**: given authority it still asks wrongly, which points
       at the absolute-level calibration ADR 0103's anchor addresses — and which rung 2 does not apply at
       all, because the harness calls `flux_feature_vector` directly and never constructs a
       `FluxDrivenSlowEmulator`, so `anchor` is structurally absent from every arm.
   * State explicitly, every time, that `REC`'s 12/12 is the persistence null's value and not skill.
5. **The structural departure of §7 is the standing open defect** and is not conditional on any of the
   above: it is measured, it grows with time, it afflicts every arm including the null, and no count
   statistic detects it. The next structural step is a size-resolved comparison of who dies (the arm's
   mortality size/age distribution vs FIT's), not another count score.

## 11. Gotchas paid for here

* ⚠ **A PROBE CAN CARRY THE RIGHT WARNING IN ITS HEADER AND STILL BE BUILT ON A DEGENERATE AXIS.** This
  script's header names the null-power trap and its verdict reads only the blessed variables — and the
  blessed variable was still one the null passes. **Before blessing a statistic, construct the null's value
  for it explicitly and write that number down beside the threshold.** Not "score the null too" (ADR 0181
  did that) — *derive what the null must return*. Here `target = n_prev` gives 12/12 on paper, which would
  have voided the basis check before a single job ran.
* ⚠ **CHECK THE MODE A HARNESS WAS ACTUALLY RUN IN, NOT ONLY WHAT IT SUPPORTS.** `--n-prev` has two values;
  one is documented in the runner as "the shipped coupled path" and has **never been used**. Three ADRs
  (0177, 0180, 0182) were written on the other one without that being stated. `grep` the run script for the
  defaulted knobs and record their values in the ADR.
* ⚠ **A "FAITHFUL TRANSMISSION" RESULT IS SUSPICIOUS WHEN THE TWO SIDES SHARE AN INPUT.** ASK ≈ GOT to a few
  per cent looked like a clean operator result; it was the tether. Ask what pins the two quantities together
  before reading their agreement as a property of the thing between them.
* ⚠ **A LEVEL DEPARTURE HIDES BEHIND A CORRECT SHIFT.** ADR 0182's cosine 0.97–0.99 and this ADR's +106 %
  agb are both true. A z-scored shift is invariant to the level it sits on, so **report the level beside
  every shift** — the same discipline ADR 0127 imposed on the `keep` ratio and ADR 0182 §7 on per-feature
  ratios.
* **The arm logs are a first-class dataset.** Two sessions read 38 GB of dumps to get stand features that
  `s_arm_log.txt` already carried per patch-year, alongside `target`, `rho`, `n_kill` and both feature
  bases. **Check `<apply>/s_arm_log.txt` before scanning a dump** (folded into the
  `rung2-dump-analysis` skill).
