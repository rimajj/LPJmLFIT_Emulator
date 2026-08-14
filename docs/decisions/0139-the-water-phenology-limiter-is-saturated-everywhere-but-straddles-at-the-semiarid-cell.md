# ADR 0139 — The GSI water limiter is SATURATED at every biome cell, so its two v1 simplifications are inert — except at the semi-arid cell, where F's inflection puts the filter on the OPPOSITE side of the threshold from the C's

* **Status:** accepted
* **Date:** 2026-08-14
* **Line:** M (multi-cell coupled S+F+E), rung 3
* **Supersedes / amends:** amends the framing of item (c) in `lines/M/STATE.md` §0-NEWEST step 1 and
  §0-PREV-23 step 2 — both of which are hereby narrowed. Amends the magnitude claim in
  `FDiff.pft_phenparams`' docstring.
* **Related:** ADR 0047 (a par-file interval `"median"` is a global default, not a central value) ·
  ADR 0134 (the same shape on leaf longevity: par file 2.0 yr, realised median 0.286) ·
  ADR 0135 / 0136 / 0137 (the four faithful terms that make `GPP_F/GPP_C` a lower bound) ·
  ADR 0138 (the sibling shortlist item, closed on a magnitude two orders below its incidence) ·
  ADR 0126 §5 (Sahel's assimilate ratio moves +1.01 on phenology alone) · ADR 0110 (the `ind` table
  already emits the per-stem answer) · ADR 0051 (`wscal_mean` is a POTENTIAL index, = 1 on a
  no-demand day)

## Context

Item (c) was the last remaining entry on line M's photosynthesis shortlist — the compensating error
that makes F's tree GPP sit above the C's while four independent faithfulness fixes each move F's
absorbed light or solved state DOWN. It was scoped into two concrete sub-items, neither measured:

* **(c1)** the C's water-limiter inflection is `pft->minwscal·100`, a **sampled per-stem trait**
  (`phenology_gsi.c:64-66`, the live `config->individual` branch); F's `PhenParams.wscal_base` is a
  per-PFT constant, and `per_pft_phenology` gives every stem of a PFT one shared trajectory.
* **(c2)** the C forces the water filter fully open while `soil->temp[0] < 10`
  (`phenology_gsi.c:67`); `rollout_daily_canopy` passes **air** temperature into that slot
  (`fdiff.jl:2220`). Soil was assumed to lag air substantially, putting the gate on the wrong spring
  and autumn days — the exact partial-leaf regime ADR 0136 localised the GPP error to.

Both were to be priced with `residual-diagnosis` §17 (weight the affected days by the assimilation
at stake, not by their count) **before** any arm was built. This ADR is that pricing. No code
changed; no flag was added.

## The parameter algebra, which settles most of it before any data is opened

`residual-diagnosis` §17 steps 1–2 say to establish the scaling and look for redundancy first. The
water filter's slope is per **percentage** point while the trait is a **fraction**, so the sigmoid
exponent is `sl·100·(w − m)` with `sl` = 5.0–5.24 for all seven tree PFTs ⇒ ≈ 524 per unit of water
availability. The 10–90 % transition width is therefore

    Δw = 2·ln(9) / (100·sl) ≈ 0.0084        (0.84 percentage points of water availability)

**The water limiter is very nearly a hard step at `w = m`.** So the inflection's *value* is inert as
a value: what matters is only which side of it the realised `w` falls on, and a per-stem wiring
change can buy something only where stems of one (cell, PFT) **straddle** the threshold. This
reframes both sub-items from "how big is the parameter error?" to "is the filter saturated?".

## Measurements

Harnesses, both sub-second-to-seconds and needing no simulation:
`scripts/diagnose_phenology_water_inflection.py` (a parquet scan of the C's own per-stem output) and
`scripts/run_soiltemp_gate_cells.sh` + `scripts/diagnose_phenology_soiltemp_gate.py` (five
single-cell C re-runs adding the daily `soiltemp1` output, ~seconds each, all five carrying
`lpjml successfully terminated`).

### 1. F's pinned inflection is the par-file interval `"median"` — and for three of seven tree PFTs that value lies ABOVE the interval's own `high`

`pft_phenparams`' docstring calls its `wscal_base` "minwscal_med·100". Measured against
`par/pft_lpjmlfit.js`, all seven values are exactly `100 ×` the par file's
`"minwscal": {"low", "median", "high"}` **`"median"`** field — and that field is the ADR-0047 trap:

| id | par `low` | par `"median"` | par `high` | F's `wscal_base` | realised median ×100 (cell) | F − realised |
|---|---|---|---|---|---|---|
| 3 beech | 0.10 | **0.2096** | 0.15 | 20.96 | 11.88 (Hainich) | **+9.08** |
| 5 BoBS | 0.10 | **0.25** | 0.15 | 25.00 | 12.47 (boreal) | **+12.53** |
| 6 larch | 0.05 | **0.35** | 0.15 | 35.00 | 13.31 (boreal) | **+21.69** |
| 4 BoNE | 0.05 | 0.25 | 0.30 | 25.00 | 7.10 (boreal) | +17.90 |
| 1 TeNE | 0.025 | 0.10 | 0.20 | 10.00 | 18.80 (Iberia) | −8.80 |
| 2 TeBE | 0.025 | 0.10 | 0.20 | 10.00 | 13.67 (Iberia) | −3.67 |
| 0 TrBE | 0.05 | 0.60 | 0.75 | 60.00 | 66.92 (Sahel) | −6.92 |

For **ids 3, 5 and 6 the declared `"median"` exceeds the declared `high`** — larch's by more than
2× — so it is not a possible central value of the trait the C samples, and the realised medians
(13.31 inside [5, 15]; 11.88 inside [10, 15]) confirm the interval is what is sampled. The pattern
reproduces on the ssp370 leg to within ~1 pp at every group, so it is a parameter defect, not a leg
artefact.

### 2. …and it does not matter at four of five cells, because the filter is SATURATED

Evaluated at each group's own realised water availability, F's inflection and the realised-median
inflection give the **same** filter value to four decimal places at 12 of 13 (cell, PFT) groups —
all saturated fully OPEN. With a 0.0084-wide transition band and `w − m` typically 0.5–0.9, both
arms sit far out on the same plateau. **A parameter error of 21.7 percentage points is inert
because the function it parameterises is saturated there.**

### 3. ★ THE EXCEPTION, AND IT IS A BINARY DIFFERENCE: at `semiarid_sahel` the two inflections land on OPPOSITE sides

| leg | realised `w` | F's inflection | C's realised median | F's filter | C's filter |
|---|---|---|---|---|---|
| historic | 0.6364 | 0.60 | 0.6692 | **1.0000** (open) | **0.0000** (closed) |
| ssp370 | 0.6619 | 0.60 | 0.6649 | **1.0000** (open) | **0.1805** |

The realised water availability falls **between** the two thresholds. So at the semi-arid cell F's
water phenology is unlimited where the C's is shut — not a few per cent of leaf display, the whole
of it. This is the one group where the trait's own spread (q10–q90 = 54.75–74.70) also straddles,
i.e. where the per-stem wiring of item (c1) is a real mechanism rather than a refinement.

Two things make the direction robust. (a) `wscal_mean` **overstates** `w` (it is exactly 1 on a
no-demand day, ADR 0051), so the realised growing-season `w` is *lower*, pushing the C's filter
further closed and widening the straddle. (b) The result does not depend on which F arm is scored:
without `pft_ids` every stem runs beech's `wscal_base` = 20.96 (ADR 0126 §5), which is even further
open. **F's filter is open at Sahel on both arms.**

⚠ The direction is the same as the shortlist needs: F over-displays leaf ⇒ over-absorbs ⇒
over-assimilates, at the cell where ADR 0126 measured phenology alone worth **+1.01** on the annual
assimilate ratio. But this is an inflection **straddle**, not a magnitude — see "What is not
measured".

### 4. Item (c2)'s premise is REFUTED at four of five cells: layer-1 soil temperature does not lag air

| cell | mean(soil − air) °C | sd | best lag (d) | % days soil<10 | % days air<10 |
|---|---|---|---|---|---|
| boreal_siberia | **+4.40** | 10.83 | 1 | 87.9 | 77.4 |
| temperate_hainich | −0.04 | 2.27 | **0** | 54.1 | 53.0 |
| mediterranean_iberia | −0.13 | 1.56 | **0** | 28.6 | 30.8 |
| semiarid_sahel | −0.02 | 0.69 | **0** | 0.0 | 0.0 |
| tropical_amazon | +0.03 | 0.56 | **0** | 0.0 | 0.0 |

The gate variable tracks air temperature essentially instantaneously at four cells. Only
`boreal_siberia` differs, and **not by a lag**: it is a +4.4 °C mean offset with a large seasonal
swing (sd 10.8) — snow insulation raising winter soil temperature and thermal damping lowering the
summer peak — which is why soil is below 10 °C *more* often (87.9 %) than air despite being warmer
on average. "Soil lags air substantially" was an assumption, and it is wrong here.

### 5. And where it is live, the day count is not the magnitude

Gate-verdict flips, weighted by the quantity the gate acts on (absorbed light, ∝ `swdown`), then by
the low-pass response at the median flip run (`wscal_tau` spans 0.01–0.8 across tree PFTs, a
100-day vs a 1-day time constant):

| cell | % days flipped | % light spring-type | % light autumn-type | net | low-pass resp | bound |
|---|---|---|---|---|---|---|
| boreal_siberia | 10.49 | 18.720 | 0.000 | **+18.72** | 0.896 | **16.78 %** |
| temperate_hainich | 4.63 | 3.818 | 1.393 | +2.42 | 0.097 | 0.235 % |
| mediterranean_iberia | 4.77 | 0.757 | 2.295 | **−1.54** | 0.061 | 0.093 % |
| semiarid_sahel | 0.00 | 0 | 0 | 0 | — | 0 |
| tropical_amazon | 0.00 | 0 | 0 | 0 | — | 0 |

**The sign is not one-signed** — Iberia's net is negative (F absorbs MORE) while boreal's and
Hainich's are positive (F absorbs LESS), because the two flip directions push leaf display opposite
ways and their light weights differ per cell. The prediction that spring-type dominates was
recorded in the harness before the run (ADR 0131's rule) and holds at 2 of 3 live cells; **it fails
at Iberia**, where autumn-type carries 3× the light.

⚠ **The 16.78 % at boreal is an UPPER BOUND with dampener 2 unclosed**, and §2 above says that
dampener probably annihilates it: the gate only matters to the extent the water filter would have
been *closed* on a flipped day, and boreal's filter is saturated OPEN (`w` ≈ 0.68–0.70 against
`m` ≈ 0.12–0.13, i.e. σ = 1.0000). If the filter is open either way, forcing it open changes
nothing. **This is not established** — see below.

## Decision

1. **Item (c1) is NARROWED, not closed, and it is a PARAMETER defect before it is a wiring one.**
   The per-stem wiring the handoff scoped is inert at 12 of 13 measured (cell, PFT) groups. What is
   *not* inert is F's pinned per-PFT constant being the par file's non-central `"median"`. Fixing
   that is a one-line-per-PFT change to a table, needs no new input, and is strictly more faithful.
   It is **not landed here** — the realised median is cell-dependent for id 0 (66.92 Sahel vs 56.03
   Amazon), so a single global per-PFT constant cannot be right everywhere, which is an argument for
   the per-stem wiring **at id 0 specifically**. Landing either is the next session's decision, with
   the Sahel straddle as its pre-registered target.
2. **Item (c2) is CLOSED as scoped, with no port and deliberately NO opt-in flag.** Its stated
   premise (a substantial soil-vs-air lag) is refuted at four of five cells; at the fifth the
   mechanism is a snow/damping offset, and its own light-weighted bound is credible only if the
   water filter is closed there, which §2 measures it is not. Guardrail 4's corollary cuts against
   shipping a flag whose measured ceiling is conditional on a regime the cells do not visit — the
   same disposition as ADR 0138. The `fdiff.jl:2220` comment now records the measurement instead of
   leaving the substitution unremarked.
3. **The `pft_phenparams` docstring is corrected.** It claimed its `wscal_base` values are realised
   medians; they are par-file interval `"median"` fields, three of which exceed their own `high`.
   Leaving that uncorrected is how a stale measurement becomes an assumption
   (`residual-diagnosis` §18 item 3).
4. **Neither sub-item is the compensating error.** The shortlist item (c) does not close the ~3 %
   decadal residual: (c2) cannot bind, and (c1) binds at exactly one cell, in the direction that
   would make F's over-production *larger*, not smaller. Item (c) is therefore struck as "the"
   candidate. The Sahel straddle is promoted to a per-cell defect in its own right.

## What is NOT measured — recorded rather than implied

* **Dampener 2 is unclosed.** Every (c2) magnitude above assumes the water filter would be fully
  closed on a flipped day. Closing it needs the realised **daily** water availability from F's own
  rollout; the `ind` table carries only the annual mean of a potential index. The saturation
  argument in §2 is on that annual-mean basis, and a daily minimum can dip into a 0.0084-wide band
  that an annual mean cannot see. **This is the single measurement that would overturn item (c2)'s
  closure**, and it is the named next action.
* **The Sahel straddle's magnitude in GPP.** §3 establishes the filter values differ by ~1.0; it
  does **not** convert that into assimilation, which requires the coupled arm. Publishing a
  recommended fix from a straddle would be the ADR-0105 error.
* **`phen` is a product of four filters**, and a day when `tmin` or `light` is already ~0 cannot be
  moved by the water filter. Not corrected for; it biases every (c2) number DOWN.
* The `soiltemp1` output is the stand's **patch-mean** while the gate is evaluated per patch, so a
  day on which patches straddle 10 °C is averaged. Narrow band, but it is a patch-mean gate.
* A cool cell dominated by PFT id 0 would put a much higher inflection (0.60) into a wetter regime;
  none of the five cells samples that population. Scope statement, not an open item.

## Consequences

* Two committed, lint-clean harnesses that answer this class of question with no simulation, and a
  reusable driver for **any** daily C output (`run_soiltemp_gate_cells.sh` inserts one output entry
  and re-validates the config, the ADR-0130 pattern).
* `residual-diagnosis` gains §20: **a saturated function makes its own parameters inert — check for
  saturation before pricing a parameter error**, together with the straddle test that finds the one
  place it is not inert.
* `CLAUDE.md` §3 records that F's water-limiter inflections are par-file interval `"median"` fields
  and that three of them exceed their own `high`, so no future session re-derives it.
* ⚠ **ADR 0139 exhausts line M's tier-2 block (0120–0139).** M's next ADR is **0190**, the start of
  its pre-allocated tier-3 block (0190–0209) — allocated 2026-08-11 precisely so this needs no
  negotiation.
