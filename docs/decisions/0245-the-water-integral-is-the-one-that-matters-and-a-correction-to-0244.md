# ADR 0245 — The WATER integral is the one that matters at 10 of 12 cells (and a correction to ADR 0244's per-cell claim)

* **Status:** proposed (§0 is a correction and is final; §§1–4 are the PRE-REGISTRATION of the water
  measurement and are committed before any number exists)
* **Date:** 2026-08-17
* **Line:** S (Component-S science)
* **Supersedes / amends:** **NARROWS ADR 0244 §2's per-cell justification** (§0 below). ADR 0244's
  defects, its fix, its exact null and its default flip all stand unchanged.
* **Answers:** line S STATE §C — the water half of ADR 0243's 22 % shortfall.

## 0. CORRECTION to ADR 0244 §2 — the per-cell comparison was on the wrong basis, and it overstated the temperature term

ADR 0244 §2 justified fixing the temperature integral partly by asserting it is *"the **dominant** of the
two integrals at the cold cells"*, quoting **"FIT's own mean `temp_stress` 24.1 days/yr at c52059 … against
water integrals of 0.34/0.01/1.89"**. **Both halves of that sentence are wrong, in two independent ways.**

1. **The water numbers were not means.** They came from a quick scan that took the FIRST stem of each
   (year, PFT) group. That is correct for `temp_stress`, which ADR 0244 §3 verified is *constant* within
   (year, patch, PFT) — it is a per-PFT day count — but `water_stress` is **per-stem** and varies inside
   every group, so the same scan yields an arbitrary representative, not a mean. The stem-weighted mean
   `water_stress` at those cells is **0.414 (c52059) / 0.035 (c57087) / 2.361 (c44048)**, and at
   `semiarid_sahel` **1.270**, not the sampled values quoted.
2. **The two raw integrals are not commensurable anyway.** `temp_stress` is an integer day count entering
   `mort_temp = min(1, 5.0·temp_stress/365)`; `water_stress` is an unbounded VPD-weighted sum entering
   `mort_water` through a different factor. Comparing 24.1 against 0.34 compares two different units and
   licenses no conclusion at all. **ADR 0243 §5.1 already had the commensurable statistic** — each
   integral's cost in *nominated mortality flux* — and ADR 0244 should have used it per cell instead of
   inventing a second, worse comparison.

**THE BASIS-CORRECT TABLE** (ssp370 leg, `REC` rosters, from ADR 0243's own scorer output
`hazard_inputs_predict.csv`; `1 − Φ` is the fraction of FIT's nominated mortality flux lost by zeroing
that integral, and `S_wt` is FIT's own water+temp share of hazard mass):

| cell | `1 − Φ(zeroW)` | `1 − Φ(zeroT)` | `S_wt` | larger term |
|---|---|---|---|---|
| 12235 | 0.0000 | 0.0000 | 0.0001 | neither (inert) |
| 57087 | 0.0163 | **0.0879** | 0.1513 | **temperature** |
| 12045 | 0.0263 | 0.0000 | 0.0354 | water |
| 22990 | 0.0275 | 0.0000 | 0.1757 | water |
| 18371 | 0.0312 | 0.0000 | 0.3340 | water |
| 22732 | 0.0434 | 0.0179 | 0.1210 | water |
| 42757 | 0.0440 | 0.0006 | 0.0501 | water |
| 32628 | 0.0544 | 0.0224 | 0.1163 | water |
| 42490 | 0.0691 | 0.0038 | 0.0939 | water |
| 42973 | 0.0951 | 0.0284 | 0.1554 | water |
| 52059 | **0.1329** | **0.1308** | 0.3400 | a TIE |
| 44048 | **0.4288** | 0.1070 | 0.6851 | water |

**What is corrected:** temperature is the larger term at **exactly one of twelve cells** (c57087) and ties
at c52059 — *not* "dominant at the cold cells". ADR 0244 named c52059 as its example, where the two are
equal to within 1.6 %. Water is the larger term at ten of twelve, and at c44048 zeroing it alone costs
**43 % of FIT's nominated flux**.

**What is NOT corrected, and stands entirely:** both defects ADR 0244 found are real and independent of
this basis error — the temperature accumulator was gated on water state it never reads, and the reset day
was a calendar year instead of the C's fixed day (verified **4 334/4 334 integer-exact**, a calendar year
wrong in 431 groups). The fix is exact, cost-free and worth having on its own terms: pooled over all cells
the temperature integral is **5.6–7.9 %** of the flux (ADR 0243 §5.1), it is now supplied exactly, and it
is the only half that *can* be. ADR 0244's default flip stands.

⚠ **The method lesson, which is the reason this correction exists at all.** ADR 0243 §4.1 derived a
commensurable statistic and ADR 0244 then justified its own §2 with an ad-hoc `awk` scan instead of
reusing it — the same shape as dump-skill trap 5c ("a criterion is written against a definition; import
that definition, do not re-implement it"), one level down: **when a published scorer already emits the
comparable quantity per unit, quote THAT and never form a second comparison by hand.** The tell was
available for free and was not checked: a quantity that is *constant within a group* (`temp_stress`) and
one that *varies within it* (`water_stress`) cannot be summarised by the same one-line scan.

## 1. What is pre-registered here

ADR 0243 bracketed the water half and refused to guess at it:

```
Φ = 0.78 (both integrals zero)   ≤   F's OWN integrals   ≤   1.00 (the C's own = ADR 0242's ceiling)
```

ADR 0244 closed the temperature end exactly. **The water end is what remains of ADR 0243's 22 %
shortfall, and §0's table says it is the larger half at 10 of 12 cells.** It cannot be answered from a
dump, because F's `water_stress` is F's own value: it needs F to run. Two measurements, both required
before any further default moves, and **neither may be reported without the other**.

## 2. Measurement A — FIDELITY: does F's own water integral reproduce the C's?

**Basis.** The rung-2 `REC` dumps are simultaneously the initial condition and the truth, which removes
the fixture-mismatch that would otherwise wreck the pairing (the committed biome fixtures come from the
ground-truth run, the dumps from the rung-2 `predict` runs — different rosters). Verified prerequisites,
all measured before writing this: the `T pre` and `T grow` rosters of a year hold **the same stem set**
(16 293 = 16 293 at `semiarid_sahel` historic); `water_stress` is **identical at `pre`, `grow` and `mort`**
(mean 1.270, max 265.365 at c18371 ssp370 — the annual routine does not touch it); and `post` carries the
recruits (52 036 vs 47 611 rows), so **`post` of year y−1 minus its `isdead` stems is exactly the roster
year y's daily loop runs on** (deferred kills, ADR 0123 / trap 5g).

**Cells.** The four cells that are BOTH biome cells (so F-side soil column and forcing exist) and rung-2
cells (so the C's per-stem `water_stress` exists): **`tropical_amazon` 12045 · `semiarid_sahel` 18371 ·
`temperate_hainich` 42490 · `boreal_siberia` 52059.** `mediterranean_iberia` 33335 is a biome cell but not
a rung-2 cell and is out of scope — say so rather than quietly scoring four and calling it five. The set
covers the water-dominated case (18371) and the tie case (52059); ⚠ it does **not** contain c44048 or
c57087, the two most extreme cells in §0's table, so the answer will be a four-cell answer.

**The arm.** `FDiffFastCore` with `per_tree_roots = true`, `wscal_leafon = true`,
`trait_drought_mortality = true`, **`pft_ids` passed explicitly** (ADR 0126 §5 — without it every stem
runs beech's phenology, which moved a Sahel statistic by +1.01), initialised from the C's own `post(y−1)`
roster and driven with the cell's own daily forcing for year y.

**The statistics and their DERIVED nulls, written before the run:**

1. **`Φ_F`** — the same nomination-flux ratio ADR 0243 blessed, with F's integrals in place of zeros, on
   ADR 0243's basis so the three numbers are directly comparable. Nulls: **0.78** (the zeros arm, i.e. no
   information gained) and **1.00** (the C's own). **PASS at `Φ_F ≥ 0.867`**, the bound ADR 0243 §4.1
   derived from ADR 0187's measured flux→biomass mapping. A value at 0.78 means F's water status carries
   nothing; between is a partial recovery and must be reported as such.
2. **Per-stem agreement** of `water_stress_acc` against the C's `water_stress`: median ratio and the share
   of stems within a factor 2, plus the **zero-agreement** rate (the C's integral is 0 for most stems, so
   a scorer that only reports a mean ratio would be dominated by the tail — report the joint-zero,
   F-zero-C-nonzero and F-nonzero-C-zero counts separately).
3. **A DERIVED sanity bound, free:** F's integral is a sum of non-negative daily terms gated by
   `wscal < mort_water_res − minwscal`, so **a stem whose F-side `wscal` never drops below its own
   threshold must return exactly 0** — and any stem where F returns 0 while the C does not is a *gate*
   disagreement, not a magnitude one. Splitting the residual that way is the difference between "F's water
   is wrong" and "F's phenology or soil-temperature gate is wrong".
4. ⚠ **The confound that must be priced, not assumed away:** `water_stress_increment` takes
   `soil_temp` and F passes **air temperature** (the C uses `soil->temp[0] > 10`). Its documented direction
   is an **over**-count of shoulder-season days ⇒ **if `Φ_F` overshoots, that proxy is a candidate cause
   and must be excluded before concluding F's water status is too dry.** The cheap discriminator is
   already known to exist: CLAUDE.md §3 records that layer-1 soil temperature does not lag air at four of
   five cells (|mean(soil−air)| ≤ 0.13 °C) but is **+4.40 °C offset at `boreal_siberia`** — so a
   `boreal_siberia`-only discrepancy is attributable to it and a four-cell one is not.

**The trap that would silently void the whole run**, restated because it is one line of code:
`wscal_ind` is allocated only under `per_tree_roots && wscal_leafon` (`fdiff.jl:2092`) and the water branch
is skipped on `nothing`. **Assert a non-zero `water_stress_acc` before reading any number.**

## 3. Measurement B — COST: what does `per_tree_roots` do to the speed gate?

Speed is goal #2 and **`per_tree_roots` has never been timed**. It rebuilds a root profile per individual
per year and moves the `wr` computation inside the individual loop. Via the `speed-gate` skill
(`scripts/bench_speed_gate.jl`), on/off arms on the same cells and years, reported as **core-seconds per
cell-year** with the per-individual normalisation the skill requires.

**No pass/fail threshold is pre-registered here, deliberately**, because none is derivable: the emulator is
already **3.8× slower per cell-year than the C it replaces** (CLAUDE.md), so the honest output is a priced
trade — "the water integral costs X % of runtime and buys `Φ` from 0.78 to Y" — handed to the owner with
both numbers, not a unilateral flip. What IS pre-registered: **the cost is reported in the same document
as the fidelity gain, and a fidelity pass does not by itself authorise the default.**

## 4. What this ADR will decide

* **`Φ_F ≥ 0.867` and the cost acceptable** ⇒ recommend `per_tree_roots = true` as a default — **line M's
  call**, with both numbers attached (the inbound already exists in `lines/M/STATE.md`).
* **`Φ_F` near 0.78** ⇒ F's per-tree water status carries no usable drought signal; the finding is an
  F-fidelity one (M-owned file, S-specified change) and the rate operator's remaining shortfall is
  attributed, not closed.
* **In between** ⇒ report the partial recovery and the residual split from §2.3 (gate vs magnitude), and do
  not flip.

## 5. Result

*(to be written after the runs — nothing above this line is edited once a number has been seen)*
