# ADR 0056 — the level anchor does NOT get the default: it fires perfectly, closes a bigger level error than Hainich showed, and closes a feedback loop that is UNSTABLE in one cell

* **Status:** Accepted
* **Date:** 2026-08-06
* **Line:** M (multi-cell coupled S+F+E) · ADR block 0050–0069 (tier 1)
* **Answers:** **ADR 0103 §6**, line S's pre-registered criterion for flipping `FluxDrivenSlowEmulator`'s
  `anchor` default from `0` to `0.1`, and the ▶ ACTION block S wrote into `lines/M/STATE.md`. ADR 0103 asked
  for a measurement and asked explicitly that a failure be reported as the finding rather than tuned away.
  **This is that failure.**
* **Decides:** **(1)** the criterion **FAILS on clauses (i) and (ii)** — do **not** flip the default;
  `anchor` stays opt-in and `0`. **(2)** The failure is **not** a defect in the anchor: it fires exactly as
  designed in all five cells and closes a level error that is **larger** than the single-cell evidence
  showed. **(3)** The reason clause (i) fails is structural and was predicted by ADR 0103's own
  Consequences — the anchor pins the *roster* to the DRF's target, and the drift lives in the *target*,
  which F's canopy features drive. **(4)** The reason clause (ii) fails is a **new** finding: anchoring
  closes a `density → fpc → target → density` feedback loop that is **stable in four cells and runaway in
  `semiarid_sahel`**. **(5)** `anchor = 0.1` specifically is the worst available choice at line M's 10-year
  horizon — near-zero benefit on the drifters, non-zero cost on the Sahel.
* **Related:** ADR 0103 (the anchor + the criterion this answers), ADR 0102 (mechanism (A), the exposure
  bias this confirms is untouched), ADR 0054 (M's original drift finding + the teacher-forced arm),
  ADR 0053 (the F-side canopy drift this attributes to), ADR 0052 (the dry-cell bias — the Sahel again),
  CLAUDE.md §6 guardrails 4 and 6
* **Evidence:** `scripts/biome_slow_oracle_probe.jl`, jobs **1716489** (the criterion) and **1716493** (the
  criterion reproduced identically, plus the mechanism report §4). Five biome cells, historic 2010–2019,
  `wscal_leafon = true` passed explicitly, pinned `_t8` artifact pair, scored against the C's `ind` truth in
  seed1-vs-seed2 noise floors. Four arms: free · `n_prev`-teacher-forced · `anchor = 0.5` · `anchor = 0.1`.

## 1. The thresholds were fixed before the run

ADR 0103 §6's clauses are qualitative ("each should flatten", "stay there"). They were made falsifiable
**in the script, before submitting it** (`residual-diagnosis` — a threshold you wrote is a hypothesis too):

* **(i)** drift factor `d = (E/C)₂₀₁₉ / (E/C)₂₀₁₀`; PASS iff `|ln d|` falls ≥ 50 % vs free **and** the
  anchored `|ln d| < 0.20`. Both clauses: a large relative cut off a large drift is still a drifting model.
* **(ii)** PASS iff the anchored gate metric is ≤ 2.0 noise floors **and** ≤ 1.5× the free arm's.
* **(iii)** carbon closes at ≤ 1e-6·C_scale (the standing Gate-2 tolerance, unchanged).

Scored on `a = 0.5`, which ADR 0103 §3b's non-monotone convergence curve selects for a 10-year horizon;
`a = 0.1` was run beside it because that is the value the flip would actually install.

## 2. The verdict

| cell | role | `d` free | `d` a=0.5 | `d` a=0.1 | `\|ln d\|` drop | gate a=0.5 | clause |
|---|---|---|---|---|---|---|---|
| `boreal_siberia` | drift | 1.561 | 1.460 | 1.541 | 15 % | 9.88 fl | **FAIL** |
| `temperate_hainich` | drift | 1.298 | 1.201 | 1.210 | 30 % | 3.15 fl | **FAIL** |
| `mediterranean_iberia` | drift | 1.842 | 1.245 | 1.815 | 64 % | 5.77 fl | **FAIL** |
| `semiarid_sahel` | floor | 0.795 | **0.277** | 0.543 | −461 % | 3.69 fl | **FAIL** |
| `tropical_amazon` | floor | 1.030 | 1.016 | 1.098 | 46 % | 0.61 fl | PASS |

**(i) FAIL** — the drift is not removed. `mediterranean_iberia` is the only near miss: it clears the ≥ 50 %
clause at 64 % and misses the second at `|ln 1.245| = 0.219` against a 0.20 bar. Boreal and Hainich fail
outright. **(ii) FAIL** — the Sahel goes from 1.4 to 3.7 floors. **(iii) PASSES** in every cell and every
arm, by six orders of magnitude (worst `resid / 1e-6·C_scale` = 1.0e-9).

## 3. The anchor is not what failed — it fires perfectly, and the level error is BIGGER than Hainich showed

The mechanism check (ADR 0048's failure mode: an operator that never runs returns a clean null that reads
as a pass). Stand density × `patch_area` ÷ the DRF's own target, 2019 — `1.00` means the stand sits exactly
where its own count model says it should:

| cell | free | `a = 0.5` | `a = 0.1` |
|---|---|---|---|
| `boreal_siberia` | 1.459 | **1.001** | 1.158 |
| `temperate_hainich` | 1.486 | **1.001** | 1.166 |
| `mediterranean_iberia` | 1.665 | **1.001** | 1.218 |
| `semiarid_sahel` | 1.635 | **1.001** | 1.210 |
| `tropical_amazon` | **2.214** | **1.002** | 1.361 |

Two things worth more than the criterion itself:

* **ADR 0103 §2's 41 % over-density is a Hainich number, and Hainich is the mild case.** Across biomes the
  free-running stand sits **46 %–121 %** denser than its own count model's absolute prediction, worst in
  `tropical_amazon` at **2.21×**. A level error that no gate in this project can see is *more* than twice
  the size the single-cell evidence implied. That finding survives this ADR's negative verdict intact.
* **`a = 0.5` closes it to 1.001 in all five cells; `a = 0.1` reaches only 1.16–1.36 in ten years.** This
  confirms ADR 0103 §3b's partial-effect caveat at five cells and transient forcing, not one cell and
  constant forcing. **`anchor = 0.1` at a 10-year horizon is the worst of both worlds** — it leaves most of
  the level error standing (`mediterranean_iberia` 13.6 floors vs 13.9 free — statistically nothing) while
  still costing the Sahel (1.9 floors vs 1.4).

## 4. WHY (i) fails: the drift is in the target, and the anchor cannot reach the target

The anchor pins the **roster** to `target / patch_area`. It cannot pin the **target**, which the DRF
re-predicts each year from F's canopy features. Those features are themselves drifting away from the C's
(ADR 0053's F-side finding, re-measured here as the 2019/2010 ratio of each quantity to its own 2010 value):

| cell | F `fpc` | C `fpc` | F `lai` | C `lai` | F `agb` |
|---|---|---|---|---|---|
| `boreal_siberia` | 1.56 | 0.90 | 1.86 | 0.92 | 2.17 |
| `mediterranean_iberia` | 0.98 | 0.67 | 0.60 | 0.63 | 1.52 |
| `semiarid_sahel` | 0.71 | **1.23** | 0.71 | 1.37 | 0.95 |

**This is exactly what ADR 0103 said it would be**: *"This does not close ADR 0102's mechanism (A). The
exposure bias is untouched: the anchor makes the stand track the DRF's prediction, so a biased prediction is
now followed faithfully rather than compounded."* Clause (i) asked the anchor to fix a drift that ADR 0103
had already stated it does not fix. **The criterion was mis-specified, not the anchor** — and that is worth
saying plainly, because the alternative reading (the anchor underperformed) is wrong and would send S
chasing a healthy mechanism.

## 5. WHY (ii) fails: anchoring closes a feedback loop, and in the Sahel that loop runs away — a NEW finding

Free-running, `ρ = target/n_prev` transmits only the *relative* year-on-year change in the target, so a
level error in the canopy features cannot feed back on itself. Anchoring ties density to the target's
*absolute* level and thereby closes the loop `density → fpc/lai/agb → target → density`. Two competing
readings were pre-stated and the per-year shape separates them:

* **H1 feedback** — the anchored arm's own `fpc` falls faster than the free arm's, monotonically.
* **H2 initial-canopy artefact** — the driver starts from the **modal** patch, so the anchor's first act is
  a one-time thinning; `fpc` steps down early and then **flattens or recovers**.

`fpc`, per year, free vs `a = 0.5`:

| cell | arm | 2010 | 2012 | 2014 | 2016 | 2018 | 2019 |
|---|---|---|---|---|---|---|---|
| `tropical_amazon` | free | 0.817 | 0.734 | 0.722 | 0.714 | 0.662 | 0.661 |
| | a=0.5 | 0.817 | **0.351** | 0.346 | 0.389 | 0.432 | **0.446** |
| `temperate_hainich` | free | 0.610 | 0.665 | 0.709 | 0.735 | 0.765 | 0.776 |
| | a=0.5 | 0.610 | 0.557 | **0.530** | 0.563 | 0.608 | **0.630** |
| `semiarid_sahel` | free | 0.281 | 0.244 | 0.229 | 0.217 | 0.203 | 0.201 |
| | a=0.5 | 0.281 | 0.181 | 0.119 | 0.084 | 0.057 | **0.057** |

**Four cells are H2 and benign.** `tropical_amazon` is the textbook case — a single step at 2012 (its level
error was the largest, 2.21×) followed by **monotone recovery** 0.351 → 0.446, with the target essentially
unmoved (4.010 → 3.860) and the gate metric unchanged (0.5 → 0.6 floors). Hainich is the same shape with a
trough at 2014 and a recovery to 0.630, and its gate metric **improves** (4.5 → 3.2 floors), as does
`mediterranean_iberia`'s (13.9 → 5.8).

**`semiarid_sahel` is H1, unambiguously.** `fpc` falls monotonically 0.281 → 0.057 with **no trough and no
recovery**, flatlining at a floor of 0.057, and the count target follows it down in lockstep **13.5 → 4.46**
(E/C 1.19 → 0.33). The free arm's `fpc` over the same decade falls only 0.281 → 0.201. The anchor drives
that canopy down **3.5× harder than free-running**, and the DRF, fed the collapsed canopy, keeps lowering
the target that the anchor then enforces. That is the loop, running away.

**This is the Sahel's fourth independent symptom, in the same cell.** ADR 0052's dry-cell root-zone bias;
ADR 0053's F `fpc` moving *opposite* to the C's (0.71 vs 1.23); M4's non-recovery from a pool perturbation
(τ 602 yr vs 47–54 yr elsewhere); and now the only cell where closing the S↔F level loop is unstable. The
handoff already recorded three and asked whether one fix addresses all of them. **This ADR does not claim
they share a cause** — it records that the count is now four, in one cell, and that the Sahel is where the
next F-side diagnosis should be aimed.

## Consequences

* **The default stays `anchor = 0`.** No baseline moves, no artifact is re-pinned, nothing in `slow.jl` is
  touched by this ADR — it is a measurement and a verdict. Line M's coupled runs continue to quote the
  free-running number with the teacher-forced number beside it (ADR 0054's framing, unchanged).
* **What line S should take from this, stated so it is not misread:** the anchor is a **healthy mechanism
  that does what it claims**, and its target error is bigger than the Hainich evidence showed. The blocker
  is not `a`. Tuning `a` is explicitly *not* the response ADR 0103 §6 asked for, and it would not help:
  `a = 0.5` already lands the level at 1.001, so there is no setting that both closes the level and avoids
  the Sahel loop. **The productive next step is ADR 0102 mechanism (A)** — the retrain without the fed-back
  count — because a target that no longer drifts is what both clause (i) and the Sahel loop need.
* **A stability question now exists that did not before.** Anchoring converts the count update from an
  open-loop relative recursion into a closed loop through F's canopy. Four of five cells damp it; one does
  not. **Any future default-on anchor needs a stability criterion, not just a skill criterion** — and the
  cheapest form is the one used here: run the anchored arm beside the free one and read the per-year `fpc`
  shape for a monotone collapse.
* **`anchor = 0.1` should not be the recommended value for a decade-scale coupled run** even when the
  anchor is eventually enabled. At that horizon it delivers 15–46 % of the level correction and none of the
  drift benefit. If M enables the anchor after mechanism (A) lands, `a = 0.5` is the horizon-correct
  setting, per ADR 0103 §3b and confirmed here.
* **The criterion did its job.** It was pre-registered, it failed, and the failure produced two findings
  (the 2.21× Amazon level error and the Sahel loop) that a pass would have hidden. Clause (i) being
  mis-specified against ADR 0103's own Consequences section is itself worth carrying forward: **a
  pre-registered criterion should be checked against what the mechanism claims to do**, not only against
  what one wants it to do.
* **Guardrail 6.** Five cells, one decade, historic forcing, one artifact pair, one seed. The Sahel loop is
  a single-cell instability observed once; it is reproducible (jobs 1716489 and 1716493 agree exactly) but
  it has not been separated from that cell's other three pathologies.
