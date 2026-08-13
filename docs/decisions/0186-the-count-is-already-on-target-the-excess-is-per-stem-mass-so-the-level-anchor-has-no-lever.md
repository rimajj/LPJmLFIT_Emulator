# 0186 — The count is already on target: the arms' excess is PER-STEM MASS, so ADR 0103's level anchor has no lever and its pre-registered criterion is unreachable

* **Status:** accepted
* **Date:** 2026-08-13
* **Line:** S · ADR block 0170–0189 (tier 3)
* **Narrows:** **ADR 0185 §7.2 and §7.5** — the named next action ("wire ADR 0103's `anchor` into the
  rung-2 path") and the criterion pre-registered for it. **ADR 0185 §7.1's verdict is untouched and is
  in fact sharpened**: the limit is still the stand the map is conditioned on; this ADR identifies *which
  coordinate* of that stand is displaced, and therefore which instrument can move it.
* **Does NOT disturb:** ADR 0103 itself (see §6 — this says nothing against the anchor in the coupled
  path, where the departure it was measured on genuinely *is* a count-level departure), ADR 0183, ADR 0184.
* **Evidence:** `scripts/diagnose_rung2_anchor_preflight.py`, run over the `predict` matrix already on
  disk. No new model run, no SLURM job: ~7 s on the login node. Output kept at
  `/p/tmp/jamirp/S_rung2_maptarget/anchor_preflight.txt`.

## 1. What was asked, and what was done instead of doing it

ADR 0185 §7.2 named the next work as wiring ADR 0103's level anchor into the rung-2 harness, and §7.5
pre-registered its pass criterion: the same 12-cell `predict` matrix must move `ASK_gain` over the
learned arms to ≥ 4 **while** the stand-level departure in `agb` at the FIT-gain cells falls below
**+40 %**, scored together.

Before wiring anything, two things were derived that the ADR did not state: **what the anchor reduces
to in this harness**, and **whether the departure it would act on is a count departure at all**. Both
are answerable from the arm logs already written. The second answer is no, and it makes the criterion
unreachable — so the 264-job matrix was **not** submitted.

## 2. The algebra — the anchor does NOT carry over from `slow.jl` unchanged

`reconcile_demography!` forms `r = target/n_prev`, `D_want = target/patch_area`, and
`ρ = r^(1−a)·(D_want/D)^a` with `D = Σ nind` over the **whole** roster, because the coupled path feeds
that same whole roster to `flux_feature_vector`.

**This harness does not.** `pools_of`'s docstring makes the feature row and the count target the >5 m
**emitted** population (`fwriteoutput_ind.c:84`) while the thinning acts on every tree. So the
population `target` lives on is the emitted one, `D` must be `n_emit/patch_area`, and `patch_area`
**cancels**:

    ρ_eff = (target/n_prev)^(1−a) · (target/n_emit)^a        then clamp(·, 0.7, 1.3)

Two consequences, both **measured** rather than asserted:

1. **In `roster` mode the anchor is IDENTICALLY INERT.** There `n_prev := n_emit` by definition, so both
   factors are the same number and `ρ_eff = ρ` for every `a`. Verified over **916 484 roster-mode rows:
   bit-identical, max |n_prev − n_emit| = 0**. ⇒ every published `roster` number is untouched by this
   question, and the anchor was unmeasurable in rung 2 before ADR 0185 opened the `predict` axis — a
   mechanical reason it sat unreachable, not an oversight.
2. **`a` interpolates the ρ conversion between the two modes but NOT the feature row.** `n_prev` is also
   feature 3, and the anchor does not touch it, so `target` keeps its free-running recursion at every
   `a`. `a = 1` is therefore *not* a return to `roster` mode, and ADR 0184's tether stays off.

## 3. The finding: the count is on target for the whole leg; the mass is not

On the **imported** basis (see §7) — patch-mean at the terminal year, seeds averaged, median over the
five FIT-gain cells, behind the scorer's own coverage gate. `dN` is the count departure vs FIT, `dAGB`
the above-ground-biomass departure, `dTGT` where the anchor would drive the count, and `dPER` the
per-stem mass departure from `(1+dAGB) = (1+dN)(1+dPER)`:

| arm | leg | dN | dAGB | dPER | dTGT | hmean | hmax | age_mean |
|---|---|---|---|---|---|---|---|---|
| `NP`  | ssp370 | **+4.9 %**  | +311.6 % | +245.6 % | −30.2 % | +38.3 % | +44.6 % | +160.1 % |
| `S0`  | ssp370 | **+10.2 %** | +136.7 % | +126.5 % | −19.6 % | +21.6 % | +19.4 % | +94.7 % |
| `S0h` | ssp370 | **−13.6 %** | +89.0 %  | +63.5 %  | −13.7 % | +16.2 % | +14.2 % | +53.5 % |
| `S1`  | ssp370 | **−2.9 %**  | +90.6 %  | +99.4 %  | −3.1 %  | +12.5 % | +17.8 % | +57.2 % |

The `dN`/`dAGB` columns reproduce ADR 0185 §5's table **exactly**, which is the check that the basis is
the criterion's own. (The product identity is exact per cell; the columns are medians taken
independently, so they do not multiply exactly at the summary level — read `dPER` as the median of the
per-cell per-stem departures, not as `dAGB` divided by `dN`.)

**The stand is not over-numerous. It is over-massive per stem.** `S1` carries **fewer** stems than FIT
and nearly **twice** the biomass; the corroborating height and age departures move in the same
direction, so the decomposition is physical and not an artefact of the arithmetic.

**And the count channel was never open.** Median over the FIT-gain cells of the per-year departure,
ssp370 leg:

| arm | stat | 2020 | 2030 | 2040 | 2050 | 2060 | 2070 | 2080 | 2090 | 2100 |
|---|---|---|---|---|---|---|---|---|---|---|
| `S1`  | dN   | +0 % | +4 % | +1 % | −0 % | +0 % | −7 % | +5 % | −2 % | −3 % |
| `S1`  | dAGB | +0 % | +18 % | +27 % | +29 % | +50 % | +42 % | +56 % | +71 % | **+91 %** |
| `S0h` | dN   | +0 % | +6 % | −1 % | +8 % | +7 % | +7 % | −3 % | −10 % | −14 % |
| `S0h` | dAGB | +0 % | +20 % | +18 % | +23 % | +47 % | +56 % | +87 % | +97 % | **+89 %** |

This kills the one alternative that would have rescued the anchor — *"the count departure was large
early and an anchor acting throughout would have stopped the mass accumulating"*. For the two arms that
carry the interface fix and the trait ordering, the count sits within a few per cent of FIT's **for all
81 years** while the biomass diverges monotonically. `S0` and `NP` do open a mid-leg count gap
(+26…+39 % around 2050), so for those two the statement is weaker — and they are the arms without the
trait operator.

## 4. Why the pre-registered criterion is unreachable

The anchor's only lever is to place the live count on the map's `target`. Grant it the **most generous
bound available**: assume it lands the count exactly on `target` and that biomass follows the count
proportionally (it will not — the anchor cannot touch per-stem mass at all). The surviving departure is
`(1+dAGB)/(1+dTGT) − 1`:

| arm | leg | surviving dAGB | criterion (< +40 %) |
|---|---|---|---|
| `S0h` | ssp370 | **+75.6 %** | NO |
| `S1`  | ssp370 | **+117.2 %** | NO |
| `S0`  | ssp370 | **+194.5 %** | NO |
| `NP`  | ssp370 | **+415.1 %** | NO |

Every learned arm misses by **2–5×**, and for `S1` the bound is **worse than the unanchored +90.6 %** —
because `dTGT` is *negative* while `dAGB` is strongly positive, so pushing the count further down raises
the per-stem excess. ⇒ **ADR 0185 §7.5's criterion cannot be met by wiring the anchor**, and the
conjunction it demanded ("`ASK_gain` ≥ 4 *and* departure < +40 %") could only have failed on its second
half after 264 jobs.

A second, independent reason not to run it naively: on the **historic** leg the count departure IS real
(+10.7 % to +44.0 %) and the anchor's bound *does* clear +40 % there (+20.8 % to +40.4 %). An
instrument that corrects the baseline leg and not the future leg **manufactures a response**, because
the blessed statistic is a difference of leg means. That is ADR 0185 §9's own gotcha, arriving from the
other direction.

## 5. Decision

1. **Do NOT wire ADR 0103's `anchor` into the rung-2 harness, and do not run the anchored matrix.** The
   departure it acts on is closed for the arms that matter, and its best case misses the pre-registered
   criterion by 2–5×. ADR 0185 §7.2's named next action is **withdrawn on measured grounds**.
2. **ADR 0185's conditioning-limited verdict STANDS and is sharpened.** The limit is the stand the map
   is conditioned on — and the displaced coordinate is **per-stem mass, height and age**, not count.
3. **The next work on this line is the size-resolved "who dies" comparison** — the arm's mortality
   distribution over stem size and age against FIT's own, at the same cells. ADR 0185 §B recorded this
   as "secondary"; this ADR promotes it to the primary question, on the measurement in §3 rather than
   on preference. It is the thing a count statistic provably cannot see, and §3 is the proof: the count
   statistic is *satisfied* while the stand is wrong.
4. **This is NOT an operator-quality verdict either way.** Hitting the right count while holding the
   wrong size distribution is consistent with a mis-ordered kill rule *and* with a kill rule that is
   fine but never given enough deaths to allocate (`ESTAB_C` always defers, so no arm can add stems).
   §3 says where to look; it does not say what is wrong there. ADR 0185 §6's "the operator-limited
   hypothesis is untested, not refuted" survives intact.
5. **No flag is flipped, no committed artifact regenerated, no `src/**` file touched.**

## 6. ⚠ What this does NOT say — scope the negative result

**This is not a finding against ADR 0103's anchor.** In the coupled path the anchor was measured against
a departure that genuinely *is* a count-level departure: an unanchored stand settling **1.409× denser**
than its own count model's absolute prediction, with no restoring force, at Hainich under constant
forcing (ADR 0103 §2). Nothing here touches that measurement, and `anchor` remains the right instrument
for it. The finding is narrower and entirely about the rung-2 setting: **there, the C grows the stand
and the count is already on the map's number, so the same instrument has nothing to pull.** ADR 0103's
own flip criterion (§6, line M's five-cell biome arm) is unaffected and still unrun.

## 7. Reproduce

```bash
export ROOT=/p/tmp/jamirp/S_rung2 NPREV=predict \
       RECCSV=/p/tmp/jamirp/S_rung2_maptarget/map_on_rec_stand_predict.csv
/home/jamirp/.conda/envs/py311_new/bin/python scripts/diagnose_rung2_anchor_preflight.py
```

~7 s, six panels, no SLURM. **Panels (4)–(6) IMPORT `diagnose_rung2_map_target_response.py` and reuse
its `Leg`, `read_arm_log`, `read_rec_csv`, `median` and coverage gate rather than re-deriving them** —
see §8.

## 8. Gotchas paid for here

* ⚠ **A CRITERION IS WRITTEN AGAINST A DEFINITION, SO A PANEL THAT SPEAKS TO IT MUST IMPORT THAT
  DEFINITION, NOT RE-IMPLEMENT IT.** The first version of panel (4) used a 20-year terminal window, a
  mean over cells, and a mean of per-patch ratios. Every one of those is defensible in isolation, and
  together they put `S1`'s ssp370 count departure at **+37 %** where the criterion's own basis (single
  terminal year, patch-mean, median over cells) gives **−2.9 %** — a different **sign**, on the same
  data, for the quantity the whole decision turns on. Mean-of-ratios is the dominant term: per-patch
  counts here are 4–11 stems, so patches where FIT holds one or two stems dominate an unweighted mean of
  ratios. The rewrite imports the scorer's own `Leg` and now reproduces ADR 0185 §5's table exactly,
  which is the check that the basis is right. **Reproducing the published table is the gate; do it
  before adding a column to it.**
* ⚠ **DERIVE WHAT AN INSTRUMENT'S LEVER IS BEFORE BUILDING THE EXPERIMENT AROUND IT.** The anchor's
  lever is the count. One table of count-vs-mass departures — free, from logs already written — retired
  a 264-job matrix and a pre-registered criterion. The pre-registration in ADR 0185 §7.5 was sound
  practice and still gated the *reading*; what it did not do is check that the **instrument could reach
  the gated quantity at all**. Add that check to the pre-registration: *state the mechanism by which the
  proposed change moves the blessed statistic, and measure that mechanism's current size first.*
* ⚠ **KILL THE RESCUE HYPOTHESIS EXPLICITLY, AND IN TIME.** "The gap was large earlier and closed" would
  have inverted this verdict, and a terminal-year table cannot see it. The per-year trajectory in §3 is
  four lines of extra code and is the difference between a finding and an assumption.
* **`patch_area` cancelling is a property of an EXPRESSION, not of the quantity** — ADR 0103's own
  transferable lesson, arriving here with the sign reversed. There it did *not* cancel where a past
  session assumed it did; here it *does* cancel, because this harness's `D` and `target` are on the same
  emitted population. Both times the question that settles it is *cancels against what?*
