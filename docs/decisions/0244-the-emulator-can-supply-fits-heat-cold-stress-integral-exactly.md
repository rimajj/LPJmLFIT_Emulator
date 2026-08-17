# ADR 0244 — The emulator can supply FIT's heat/cold-stress integral EXACTLY, and two defects were stopping it

* **Status:** accepted
* **Date:** 2026-08-17
* **Line:** S (Component-S science)
* **Supersedes / amends:** amends ADR 0110 §5 step 3 (the accumulator it built has two faithfulness
  defects, both fixed here) and retires ADR 0049 §3's blocker for the TEMPERATURE half.
* **Answers:** the owner's steer of 2026-08-17, verbatim: *"well then change that, right? make it hand
  over the right inputs!!!"* — after ADR 0243 measured that the coupled loop hands the ported mortality
  hazard zeros for both stress integrals and thereby loses 22 % of FIT's mortality flux.

## 1. The instruction, and what it turned out to require

ADR 0243 established that the rate-mortality operator — which reproduces FIT's stem count and biomass to
~4 % when fed FIT's own inputs (ADR 0242) — delivers only **Φ = 0.78** of the needed mortality flux on the
inputs the coupled emulator passes today, because `slow.jl:865` hands `water_stress = temp_stress = 0`
unless `WaterParams.trait_drought_mortality` is on. The owner's answer was to fix it, not to measure it
further.

**Switching the flag on would NOT have fixed it.** Reading the path against the C first (guardrail 5)
found two defects, either of which alone would have handed the hazard a *wrong* non-zero integral — which
is worse than a zero, because ADR 0242's `H0` showed that at FIT's full flux mis-directed kills annihilate
the stand while every count-side diagnostic still looks fine.

## 2. The two defects

**(1) The temperature integral was gated on per-tree WATER state it does not need.**
`_accumulate_stress!` opened with

```julia
ws = fl.wscal_ind
ws === nothing && return nothing      # needs per_tree_roots
```

but `tree/tempstress_tree.c:29` is

```c
if((temp < treepar->temp_stressed.low) || (temp > treepar->temp_stressed.high))
    tree->temp_stress += 1;
```

— the day's **air temperature** against that PFT's own `temp_stressed` interval, and nothing else. It needs
no `wscal`, no roots, no soil water. So with `per_tree_roots` off (the shipped default) `mort_temp` was
identically zero *even with `trait_drought_mortality` on* — ADR 0243's failing case, reachable with the
flag set. And this is the **dominant** of the two integrals at the cold cells: FIT's own mean
`temp_stress` is **24.1 days/yr at boreal c52059**, 13.3 at c57087 and 12.0 at c44048, where its
`water_stress` is 0.34/0.01/1.89 — while at the dry cells the ordering reverses (c18371: water 21.1,
temperature 0.0). The two integrals bind at **different cells**, so neither is the small one.

**(2) Both integrals were reset on the wrong day — a whole-hemisphere error in the south.**
`tempstress_tree.c:31-33`, `waterstress_tree.c:40-42` and `phenology_gsi.c:87-90` all do the same thing,
**after** the day's increment:

```c
if ((lat >= 0.0 && day == COLDEST_DAY_NHEMISPHERE) ||     /* 14  */
    (lat <  0.0 && day == COLDEST_DAY_SHEMISPHERE))       /* 195 */
    tree->temp_stress = 0.0;                              /* include/climate.h:20-21 */
```

So the value the annual mortality call reads is the accumulation over days **`reset+1 … 365`**, not a
calendar-year total. `FDiffFastCore` reset all three accumulators with `bm_inc_acc` at the **end of the
calendar year** (`fast.jl:463`, and the same in `slow.jl`'s S-in-the-loop path), i.e. it would hand the
hazard days `1 … 365`. In the north the extra days 1–14 are the coldest of the year — the days most likely
to fall below `temp_low`. In the **south** the two windows differ by half a year.

⚠ The C's own comment says *"set to zero by start of vegetation period"* while its code says a fixed
calendar day. **The code is the authority** (guardrail 5), and the measurement below settles it: a
phenological reading would not have reproduced the dumps.

## 3. The measurement — an EXACT null, and it passes at every group

`scripts/diagnose_stress_integral_window.py`, SLURM job 1815335, **no model run**: the C's own daily air
temperature (the `.clm` the run itself read, header-driven per ADR 0100's mixed-version trap) plus the
committed `temp_stressed` intervals, against the C's own dumped `temp_stress` from the rung-2 `REC`
`predict` rosters. Nulls written in the script header before it ran (ADR 0243 §4.1's discipline):

| window | definition | pooled result over **4 334 (cell, year, PFT) groups**, 12 cells × 2 legs |
|---|---|---|
| **C** | reset at day 14 N / 195 S, after the increment | **4 334 / 4 334 exact — 0 mismatching** |
| **F** | the calendar year (`fast.jl`'s convention) | 3 903 / 4 334 exact, **431 groups wrong**, max **14 days** |

Mean stressed days: truth **4.479** · window C **4.479** · window F **5.245** ⇒ **F over-counts the
stressed-day total by +17.1 %** pooled, and the exact-match rate at the three cold cells is only
**0.647 / 0.692 / 0.672**. The structural pre-check passed too: `temp_stress` is constant within
(year, patch, PFT) at every group and patch-invariant, which is what a per-PFT day count must be — and it
is simultaneously the guard that the dump column offset is right (dump-skill trap 1).

⇒ **The emulator can supply this integral EXACTLY: same forcing, same interval, same window, no new
physics, no per-tree water state, no measurable cost.** ADR 0049 §3's blocker ("recovering
`mort_water`/`mort_temp` requires a per-PFT daily accumulator in F") is retired for the temperature half —
the accumulator exists, and this is what it has to do.

## 4. The fix

`src/components/fast.jl` — the water gate narrowed to the water branch, and the C's fixed-day reset added
(`_COLDEST_DAY_NH = 14`, `_COLDEST_DAY_SH = 195`, applied after the increment, clearing
`water_stress_acc`, `temp_stress_acc` and `aphen_acc` exactly as the C clears its three). The
year-boundary `fill!` in `fast.jl`/`slow.jl` is **kept deliberately**: with the coldest-day reset in place
it is equivalent for the only reader (`_trait_hazards!` runs at year end, by which point both conventions
hold exactly the C's window), and a fresh zero at Jan 1 keeps a rollout that starts mid-stream
well-defined. `slow.jl`'s comment claiming the year boundary is "the one reset point it has" is corrected.

**Guardrail 4 holds by construction, not by measurement:** `_accumulate_stress!` returns before touching
anything unless `trait_drought_mortality` is on, and the three accumulators are then all-zero, so every
existing configuration is byte-identical. The new testitem asserts that first.

**New gate — `test/testitems/stress_integral_window_tests.jl`.** The flag had **no test and no probe at
all**, which is how two defects survived in shipped code; that is the root cause and it is now closed.
Four assertions, all encoding the C's semantics rather than fitted numbers: default-off inertness; the
temperature integral accumulating with `wscal_ind === nothing` while water stays zero; and the surviving
window being `365 − 14` in the north, `365 − 195` in the south and `365 − 14` at the equator (the C's
`lat >= 0.0` branch). Measured directly before committing: 351 / 170 / 351 / `aphen` 351 / water 0.

⚠ **`fast.jl` is line M's file** (CLAUDE.md §9). This edit is made on line S under the owner's standing
steer of 2026-08-12 (*"why do you switch important mechanisms off?? This has nothing to do with other
lines… has to work in line S"*) and today's follow-up, and it is disclosed rather than quiet: it is
provably inert for every configuration line M runs, the request that preceded it is already an inbound in
`lines/M/STATE.md`, and that inbound is updated to say the fix has landed and what it changed.

## 5. The default flip — pre-registered HERE, before the flip suite runs

Per guardrail 4's corollary (an opt-in flag whose default is known wrong is a defect on a timer —
`wscal_leafon`, `trait_mortality` and `anchor` each sat off for weeks) and the `julia-test` skill's
default-flip procedure:

**What is flipped:** `WaterParams.trait_drought_mortality` `false → true`. **What is NOT:**
`per_tree_roots` stays `false`.

**Why that pair is the right increment.** With `per_tree_roots` off there is no per-tree `wscal`, so after
§4 the flip hands the hazard an **exact** `temp_stress` and an unchanged **zero** `water_stress`. It is
strictly a recovery of the half that is exactly computable, and it cannot introduce an approximation. The
water half needs `per_tree_roots`, whose runtime cost is unmeasured — and speed is goal #2 — and whose own
flip criteria (ADR 0110 §6 (a)–(c)) have never been measured. Flipping both at once would confound an
exact fix with an unmeasured one.

**The criterion, met before the flip is made:** window C exact at **4 334 / 4 334** groups (§3). That is a
stronger condition than ADR 0110 §6's step-3 clauses (d)/(e), which are about the *water* axis's response
and remain open.

**The expected blast radius, stated before the suite runs.** Any arm that runs the coupled loop with
`trait_mortality` on now sees a non-zero `mort_temp` where it saw zero, so per-stem hazards move at cold
cells and pinned assertions may move with them. Prediction: the failure list is confined to arms that
(i) enable `trait_mortality` **and** (ii) run a cell cold enough for `temp_stress > 0`. A failure outside
that set means the change is not what this ADR says it is, and is to be diagnosed, not re-pinned. Any
moved pin is listed in the flip commit with its old and new value read out of the failing run's own log.

## 5a. The flip result — green, and the green is NOT the evidence

| run | code under test | result |
|---|---|---|
| job 1815346 | §4's fix, default still `false` | **275 634 pass / 0 fail**, 138 items, 7m33s |
| job 1815424 | + the default flipped to `true` | **275 634 pass / 0 fail**, 138 items, 7m20s |

**The flip moved ZERO of 275 634 assertions**, and the pre-registered blast radius in §5 was therefore
not merely met but empty. ⚠ **That is a fact about the test suite, not about the flip, and it must not be
reported as if the suite had confirmed anything.** Beech's `temp_stressed` band is **[−20, 54] °C** — the
widest interval in the parameter table — and no test arm's forcing leaves it, so `temp_stress` is 0 in
every arm the suite runs and the suite **cannot witness this flip**. It was predicted before the run for
exactly that reason.

**What IS the evidence, then:** (a) the 4 334 / 4 334 integer-exact reproduction of the C's own emitted
`temp_stress` in §3, and (b) the new testitem's −30 °C arms, which are the only place in the repo where the
mechanism is actually exercised. And what makes the *default* gated rather than incidental is the
assertion added with the flip — `WaterParams{Float64}().trait_drought_mortality` — plus its companion
`!per_tree_roots`, so a silent revert of either half is loud. Verified live in the built package:
`trait_drought_mortality = true`, `per_tree_roots = false`, `wscal_leafon = true`.

**Where the flip does bite** is the field, not the fixtures: at the 12 rung-2 cells FIT's own mean
`temp_stress` runs **0 → 24.1 days/yr**, with three cells at 12–24. Those are cells the emulator runs.

⚠ **A green suite after a default flip is the case that most needs the honest reading**, and it is the
mirror of ADR 0242 §7's lesson: there a pre-registered clause failed on a sound result, here a
pre-registered clause passed vacuously. Both are only interpretable because the reading was fixed first.
Recorded in the `julia-test` skill's default-flip procedure as the fifth outcome class: **vacuous — the
suite has no arm in the regime the flag acts on**, which is itself a coverage finding.

## 6. What is NOT fixed, and what comes next

* **The water half is still zero by default.** It needs `per_tree_roots = true`, and ADR 0243's bracket for
  it is unchanged and unmeasured: **0.78 (zeros) ≤ F's own integrals ≤ 1.00 (the C's own)**. Next step:
  score F's own per-individual `water_stress_acc` against the C's dumped `water_stress` at the same cells,
  and F's per-tree `wscal` against the C's, plus the runtime cost of `per_tree_roots` on the speed gate.
* **`soil_temp` remains an air-temperature proxy** in the water increment (`water_stress_increment`'s own
  documented substitution; the C uses `soil->temp[0] > 10`). Direction stated in that docstring:
  over-counts shoulder-season stress days. Retires when E's ground-heat column is wired through.
* **`tree->isphen`** is reset by the C on the same coldest day (`phenology_gsi.c:90`). F's leaf-recycle
  latch is uniform `is_deciduous` and ADR 0134 measured that as faithful, so nothing is owed — but the
  coldest day is now a named constant in `fast.jl` if that item is ever re-opened.
* This ADR does **not** touch ADR 0242's ceiling caveat, and it does not by itself close ADR 0243's
  22 % shortfall: it closes the temperature part of it exactly and leaves the water part measured-and-open.
