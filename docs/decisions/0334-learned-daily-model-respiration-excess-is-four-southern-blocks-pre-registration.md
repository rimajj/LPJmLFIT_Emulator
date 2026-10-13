# 0334 — Learned daily model: the "constant respiration excess" is four southern blocks (measurement + two arms pre-registered)

* **Status:** Measurement 2026-10-13; arms L and V pre-registered the same day, before any training. Results in §4
  (2026-10-13): both falsifiers fired.
* **Follows:** ADR 0333 (warm-climate coverage; it named a "constant 1.5–2.7 % plant-respiration excess on every leg"
  as the next target) and the STATE handoff, which proposed (a) an annual-NPP-sum loss term against it and (b) a
  larger sample budget. Tools: `scripts/f2_carbon_split.py --blocks=` (new filter),
  `scripts/f2_season_residual.py` (new), `scripts/f2_train.py --season-phase local` (new, default unchanged).

## 1. Measurement: the excess is a place effect, not a training bias

Run `WE_5seed` (arm W, ADR 0333), plant respiration = GPP − NPP, emulator ÷ original summed over cells with GPP ≥ 50:

| cells | ctl_obs free / one-step | UKESM ssp370 free / one-step | MPI ssp585 free / one-step |
|---|---|---|---|
| training cells (730) | 1.008 / 1.004 | 0.997 / 0.998 | 1.002 / 1.003 |
| held-out, all (240) | 1.024 / 1.019 | 1.017 / 1.023 | 1.024 / 1.031 |
| held-out, blocks 0, 1, 2, 4 (40) | **1.097 / 1.095** | **1.073 / 1.089** | **1.095 / 1.113** |
| held-out, the other 200 | 1.011 / 1.005 | 1.007 / 1.011 | 1.011 / 1.015 |

1. **Training cells show no excess** (≤ 0.8 %, on all 15 legs) and the one-step run (each day from the original's own
   state) shows it as much as the free run. So it is not an annual-sum bias of the loss and not accumulated store
   error ⇒ **proposal (a) of the handoff, an annual-NPP-sum loss term, would act on cells that are already right; it
   is dropped.**
2. **Four of the five southernmost panel blocks (33–47° S) carry ~80 % of the net excess** (per-block shares on
   observed weather +0.21 / +0.20 / +0.20 / +0.17). The split of ADR 0320 §4 holds out "the lowest non-biome block of
   each stratum", and the blocks are ordered by latitude, so it removed four of the five blocks south of 33° S; only
   block 3 trains there. In those 40 cells the median per-cell NPP error is −7 to −11 % with 72–84 % of cells low;
   in the other 200 held-out cells it is −1.4 … +0.8 % with 44–58 % low — **no bias.**
3. **What the four blocks are** (2020–49, observed weather): mostly grass-dominated (dominant cover = grass band),
   6–16 °C mean temperature, 380–1 390 mm rain. Distance to the nearest training cell in standardised climate +
   stand space: blocks 0 / 1 **1.37 / 1.10**, blocks 2 / 4 0.68 / 0.92, against a training-block leave-one-out median
   0.64 (90th percentile 1.14) ⇒ blocks 0 and 1 are at or beyond the edge of what training covers; 2 and 4 are not.
4. **Season** (`f2_season_residual.py WE_5seed`, one-step, member 1, observed weather, gC/m² per cell-year per
   month): respiration is too high in **every** month in all four blocks (+1 to +12, no sign change), so the
   respiration excess is a level offset. But GPP in blocks 2 and 4 has a seasonal pattern — too high in June–July
   (+18 to +25) and too low in September (−16 / −26) — which a calendar input that is not hemisphere-aware would
   produce. The network's day-of-year input is the absolute calendar (sin, cos of 1 January = day 1) for every cell;
   south of the equator the season is shifted by half a year, which the original itself handles explicitly (its annual
   resets fall on day 14 north, day 195 south, `include/climate.h:20-21`).

⇒ The "constant excess on every leg" of ADR 0333 is a generalisation error to a few southern places, not a
property of the network on cells like those it trained on. The deployment model trains on all 1 050 panel cells,
but a global run has 54 020, so generalisation to places is what matters.

## 2. The arms (each one change against arm W; legs, network, ensemble, deep drainage exactly as arm W)

* **Arm L** (`L_3x256_seed0..4`, ensemble `LE_5seed`): `--season-phase local` — south of the equator the two
  day-of-year inputs are multiplied by −1 (= shifted by half a year), so they measure the local season.
  Default unchanged (`calendar`), so every earlier run reproduces.
* **Arm V** (`V_3x256_seed0..4`, ensemble `VE_5seed`): `--nsamp 80000000` (arm W: 40 M). The handoff's proposal (b):
  arm U's early-window losses (ADR 0333 §6) suggested 40 M is thin over 12–13 legs.

## 3. Pre-registered numbers (free runs, ADR 0325 yardstick; scorers `f2_carbon_split.py`, `f2_relative_score.py`)

**Arm L.**
* **Primary:** the four southern blocks' plant-respiration excess (ratio − 1, summed over all 81 years as in §1), arm W
  0.097 / 0.073 / 0.095 on observed weather / UKESM / MPI ssp585, **at most half of arm W's on at least two of the
  three legs**; and the July minus September GPP swing of blocks 2 and 4 (one-step, member 1, observed
  weather; arm W 40.9 and 46.4 gC/m² per cell-year) at least halved in both.
* **Must not get worse:** the other 200 held-out cells' respiration ratio within 1.000 ± 0.015 on all three legs
  (arm W 1.007–1.011); UKESM GPP / NPP drift ≤ 1.20 / 1.30 (arm W 1.15 / 1.25); typical-cell GPP / NPP / ET error on
  both test legs ≤ 1.1 × arm W's.
* **Falsifier:** southern excess falls by less than 0.02 on all three legs **and** the two GPP swings fall by less
  than a quarter ⇒ the calendar input is not the cause; what remains is coverage (places unlike any training cell),
  which only more training places can fix — record it and go to the deployment model.
* **Expectation:** partial — the GPP swings of blocks 2 / 4 shrink by about half, blocks 0 / 1 (edge of coverage)
  barely move; the southern respiration excess drops to ~0.05–0.07, i.e. the primary fails on respiration.

**Arm V.**
* **Primary:** typical-cell NPP error, early window (2021–50), on UKESM and MPI ssp585 ≤ 0.9 × arm W's
  (arm W 3.16 and 3.37 ⇒ ≤ 2.84 and ≤ 3.03).
* **Must not get worse:** UKESM GPP / NPP drift ≤ 1.20 / 1.30; GPP / ET typical errors ≤ 1.05 × arm W's.
* **Falsifier:** both NPP numbers within ±5 % of arm W's ⇒ the sample budget is not the limit at 12 legs; keep 40 M.
* **Expectation: null.** ADR 0322 found more rows from the same cells did not help, and arm W's members end with a
  training loss (0.043) well under the loss on validation blocks it never trained on (0.055): the limit is places, not rows.

## 4. Result (2026-10-13; jobs 2476675–86 all completed; season job 2480784)

Scored with `f2_relative_score.py WE_5seed LE_5seed VE_5seed`, `f2_carbon_split.py … --blocks=0,1,2,4` and
`--blocks=-0,1,2,4`, `f2_season_residual.py LE_5seed`. The carbon split reports two 20-year windows (2021–40,
2081–2100); their mean reproduces arm W's 81-year figures of §1 to within 0.003, so it is used for both arms below.

**Arm L (hemisphere-aware season input): falsifier fires — the calendar input is not the cause.**

| | arm W | arm L | required |
|---|---|---|---|
| southern respiration excess, observed weather / UKESM / MPI ssp585 | 0.095 / 0.074 / 0.096 | 0.091 / 0.063 / 0.089 | ≤ half on 2 of 3 |
| July − September GPP swing, block 2 / block 4 (gC/m² per cell-yr) | 40.9 / 46.4 | **44.6 / 49.8** | ≤ half |
| other 200 held-out cells, respiration ratio (both windows, 3 legs) | 0.993–1.014 | 0.993–1.011 | 1.000 ± 0.015 ✓ |
| UKESM GPP / NPP drift | 1.15 / 1.25 | 1.18 / 1.24 | ≤ 1.20 / 1.30 ✓ |
| typical GPP error early/late, UKESM | 1.96 / 2.10 | **2.22 / 2.32** (1.13× / 1.10×) | ≤ 1.1× ✗ |
| typical GPP error early/late, MPI ssp585 | 2.08 / 1.87 | 2.06 / **2.23** (0.99× / 1.19×) | ≤ 1.1× ✗ |
| typical NPP error early, UKESM / MPI ssp585 | 3.16 / 3.37 | 2.82 / 2.91 | — |

The respiration excess fell by 0.004–0.011 (< 0.02 on all three legs) and both GPP swings *grew* by 7–9 %, so both
halves of the falsifier hold. The June–July GPP excess of blocks 2 and 4 (33–36° S) persists when the network is
told the local season ⇒ it is not a mis-phased calendar; most likely these places' own seasonality (winter-rain
climates) is unlike anything in training — coverage. One side effect is real and recorded: the southern blocks'
median per-cell NPP error moved from −7 … −11 % to −1 … −5 % (fraction of cells low 0.72–0.84 → 0.53–0.82), but
the typical GPP error on the two test climates got worse by more than the allowed 10 %. **Not adopted; the default
(`calendar`) stays.**

**Arm V (80 M samples instead of 40 M): falsifier fires — the sample budget is not the limit.**

| | arm W | arm V | required |
|---|---|---|---|
| typical NPP error early, UKESM / MPI ssp585 | 3.16 / 3.37 | 3.02 / 3.25 (−4.4 % / −3.6 %) | ≤ 2.84 / ≤ 3.03 ✗ |
| UKESM GPP / NPP drift | 1.15 / 1.25 | 1.16 / 1.27 | ≤ 1.20 / 1.30 ✓ |
| typical GPP error early, UKESM / MPI ssp585 | 1.96 / 2.08 | 1.91 / 2.18 (1.05×) | ≤ 1.05× (borderline) |
| typical ET error early, UKESM / MPI ssp585 | 1.92 / 2.00 | 1.91 / **2.14** (1.07×) | ≤ 1.05× ✗ |
| southern respiration excess (3 legs) | 0.095 / 0.074 / 0.096 | **0.134 / 0.100 / 0.124** | — |

Both NPP numbers are within ±5 % of arm W's, as expected. More rows made the southern excess worse, not better,
consistent with "the limit is places, not rows". **Keep 40 M.**

**Consequence.** Both of the handoff's remaining levers on the respiration excess are now measured null. What
remains is generalisation to places unlike the training cells, which only more training places can fix. Per §3,
go to the deployment model (all five climate models in training); a larger or differently placed cell panel is the
lever if the excess must be reduced further.

## Amendment 2026-10-13 (ADR 0336)

Arms L and V each had early-stopped members. Re-scored with repaired ensembles (ADR 0336 §4): both nulls stand
(southern excess 0.099 / 0.071 / 0.096, GPP swing 42.6 / 47.6; arm V NPP within 4 % of arm W).
