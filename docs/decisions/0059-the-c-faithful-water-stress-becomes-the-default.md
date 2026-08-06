# ADR 0059 — the C-faithful leaf-on water scalar becomes the DEFAULT, and it is a one-cell change worth 3.5× of the Sahel's carbon

* **Status:** Accepted
* **Date:** 2026-08-06
* **Line:** M (multi-cell coupled S+F+E) · ADR block 0050–0069 (tier 1)
* **Decides:** `WaterParams.wscal_leafon` defaults to **`true`** (`src/fdiff.jl:236`). Guardrail 4 is now
  served by the **opt-out** — `wscal_leafon = false` reproduces the pre-ADR-0051 expression exactly, and
  both arms are exercised on every run by `wscal_leafon_tests.jl`. `biome_coupled_tests.jl` item 2's pinned
  LE/GPP are regenerated for the new defaults (a deliberate baseline move, its own commit).
* **Closes:** the flip line S GO'd explicitly (`lines/M/STATE.md`, 2026-08-05): *"it is yours to land,
  unilaterally, and S's side is ALREADY IN"* — `slow_production_drf_tests.jl:168` now admits exactly the
  two admissible states, so no synchronised two-sided commit is needed.
* **Related:** ADR 0051 (measured the defect and shipped the flag opt-in), ADR 0052 (the dry-cell root-zone
  bias — the same cell), ADR 0053 (every published F-vs-C comparison already ran `wscal_leafon = true`),
  ADR 0075 (line E's parallel default flip, same guardrail-4 corollary), CLAUDE.md §6 guardrail 4 **and its
  corollary**, which names this exact failure: *"an opt-in flag whose default is known wrong is a defect on
  a timer — `wscal_leafon` … sat off for weeks with each line recording the flip as the other's to
  schedule."*
* **Evidence:** CI-faithful suites **1718279** (flip only: 111 234 pass / **3 fail**, all three expected)
  and **1718316** (with the regenerated pins). Pins re-measured by `scripts/biome_ensemble_pin_probe.jl`,
  job **1718307**. C-side reference: `test/testitems/references/M_fdiff_oracle_biomes.csv`.

## 1. What the flag is (one paragraph, because the name hides it)

The C's `wscal` is a **potential, phenology-independent** index — *if this canopy were at full leaf cover,
could the soil meet the evaporative demand?* — and it equals **1 (unstressed)** on a no-demand day
(`water_stressed.c:130-138`, ADR 0051). F_diff's original expression was the **realized** supply/demand
ratio, which carries `phen` **squared** and collapses to **0 (maximal stress)** as leaf display vanishes.
So every leaf-off day was scored as fully water-stressed. That number is consumed **twice**: as Component
S's `water_stress` conditioning feature, and as the F-core's water-stress-modulated leaf:root allocation
driver `lmtorm` (`fdiff.jl:2082`).

## 2. The measurement: four cells do not move, one moves by 3.5×

Full CI-faithful suite with **only the default flipped** (job 1718279): **3 failures out of 111 237**, and
all three are exactly the assertions that must move — the opt-in guarantee in `wscal_leafon_tests.jl:26`,
and `semiarid_sahel`'s two pinned signatures. Nothing else in the tree moves at all.

| cell | LE before → after | GPP before → after | GPP vs the C's tree GPP |
|---|---|---|---|
| boreal_siberia | 23.943 → 23.973 | 1.007 → 1.019 (+1.2 %) | 0.90× → 0.91× (C 1.117) |
| temperate_hainich | 40.453 → 40.468 | 3.445 → 3.449 (+0.1 %) | 1.12× → 1.12× (C 3.067) |
| mediterranean_iberia | 46.623 → 46.625 | 5.056 → 5.057 (0.0 %) | 1.86× → 1.86× (C 2.723) |
| **semiarid_sahel** | **33.179 → 35.205 (+6.1 %)** | **0.386 → 1.367 (+254 %)** | **0.26× → 0.90×** (C 1.513) |
| tropical_amazon | 116.105 → 116.062 | 6.925 → 6.940 (+0.2 %) | 1.00× → 1.01× (C 6.897) |

**Why one cell.** The defect's size is the number of leaf-off (or near-leaf-off) days, because those are
the days the two expressions disagree most. The Sahel has the most, so its annual mean `wscal` was pinned
near zero, which crushed `lmtorm`, which starved the leaf pool, which starved GPP. It is the cell with the
**largest** correction available and it was carrying a **3.9× GPP deficit** against the C. That deficit is
now 10 %.

**The honest cost, stated because it is in the same cell.** The Sahel's ET goes 1.17 → 1.24 mm/day against
a C ET of 0.983 — i.e. from 1.19× to **1.26×** the C's — so the flip trades a large carbon gain for a
~6 % worse ET overshoot. That overshoot is ADR 0053's open item (a), unchanged in kind: F carries **no**
grass transpiration while the C's ET does, so the tree-only bias is larger still. This ADR does not close
it and does not claim to.

## 3. The reason this matters more than "more faithful"

**Until today this CI gate pinned a configuration that no published F-vs-C comparison ever ran.** Every
oracle probe on this line (`biome_fdiff_oracle_probe.jl`, `biome_slow_oracle_probe.jl`,
`biome_resilience_probe.jl`) passes `wscal_leafon = true` **explicitly** and says so in its header — that
is where ADR 0053/0054/0055's numbers come from. The *default* arm, which is what the gate and any casual
`FDiffFastCore(...)` call ran, was the arm nobody scored. A default and a measurement basis that disagree
is the train/inference-shift hazard in its cheapest form, and it survived because both were individually
documented.

Line S's endorsement is on the conditioning side and is independent of the allocation effect above:
Hainich's annual `water_stress` goes **0.3050 → 0.0034** against a C truth of 0.0014 and a trained band of
`[0, 0.04315]`, so the flip **closes S's last out-of-band conditioning column**.

## 4. What did NOT move, and why that is the interesting part

Not a single F_diff-vs-C numerical-regression baseline, canopy-rollout reference, conservation gate,
gradient check, resilience fixture or rollout-stability assertion moved. The change is confined to the
water-stress path's two consumers, and in four of five climates the annual-mean `wscal` was already near 1
under both expressions — the two definitions agree wherever the canopy is in leaf. **A flag can be
"physics-wide" in the source and still be a one-cell change in effect; measure which cells before
scheduling the regeneration.** Both previous items on this line (ADR 0057's CI cost, ADR 0058's baseline
sweep) failed the same way, in the same direction: the assumed blast radius was much larger than the
measured one.

## 5. Consequences

* The package default now equals the basis every published M-line F-vs-C number was measured on. Probes
  that pass `wscal_leafon = true` explicitly are unchanged and stay explicit (a control that silently
  tracks a default stops being a control — ADR 0075 §4).
* Any coupled number quoted from now on is **package defaults**: C-faithful `wscal` + two-layer ground heat
  (ADR 0075) + the 25-patch ensemble (ADR 0057). `run_coupled_biomes.jl` prints all three.
* **`semiarid_sahel`'s symptom list changes.** ADR 0056 §4 counted four independent symptoms in that cell;
  one of them — the GPP level — is now largely explained and fixed. The remaining three (ADR 0052's
  too-dry root zone, ADR 0053's `fpc` moving opposite the C, M4's τ = 602 yr non-recovery) are untouched,
  and line S's ADR 0105 separately **inverts** the sign of that cell's coupled count error (48 % *under*-
  dense, not over). Re-read that cell's whole file before quoting any of it.
* Opt-out arms remain available and are exercised: `wscal_leafon_tests.jl` runs both expressions and pins
  the default explicitly, so the next default move cannot be silent.
