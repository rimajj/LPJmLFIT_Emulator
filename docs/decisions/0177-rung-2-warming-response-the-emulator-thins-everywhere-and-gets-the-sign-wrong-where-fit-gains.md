# 0177 — rung-2 warming response over the scenario pair at 12 cells: the learned demography thins almost everywhere, so it matches FIT's SIGN wherever FIT thins and gets it WRONG at 4 of 5 cells where FIT gains stems — and on that sign test it is indistinguishable from doing nothing

* Status: accepted
* Date: 2026-08-12
* Line: S (tier-3 block 0170–0189)
* Supersedes: nothing. **Delivers the first item of ADR 0176's handoff** (the response over the scenario
  pair) and the standing owner steer's actual deliverable. Extends ADR 0176 from one cell / one scenario to
  12 cells / both scenarios.
* Scope, mandatory with every number: **12 cells of 54 020**, both legs of the scenario pair, establishment
  deferred to the C in every arm (so every number is a MORTALITY result), `n_living` = terminal-year
  patch-ensemble mean of stems above the `ind` writer's 5 m cut. ⚠ **§5 is not optional reading: the
  headline is NOT yet a clean climate response**, because the two legs differ in length.

---

## 1. What was run

15 cells were selected by a pre-registered rule that keys only on PRESENT-DAY climate
(`scripts/select_rung2_response_cells.py` → the committed `test/testitems/references/S_rung2_response_cells.csv`):
trained in both scenarios in the pooled production forest, mean `n_living` ≥ 5 in each, 10 equal-count
growing-degree-day strata, plus the five canonical biome cells for continuity. They span gdd5 **519 → 9043**
and cold-month **−32 → +27 °C**.

Per cell and per scenario: `ARM=REC` (the per-cell, per-scenario recorded baseline — ADR 0041 forbids
scoring a single-cell re-run against the global truth), `NP` (persistence null, 1 seed — it never reaches
`rand`), and `S0` / `S0h` / `S1` at 5 seeds. **510 runs**, `bin/lpjml_rung2_v6`, 1 task each.

Legs: historic **2000–2019** from `restart_1999.lpj`; ssp370 **2020–2100** from `restart_2019.lpj`. Each leg
is independently initialised from FIT's own state, so the cross-leg difference partly cancels each arm's
level bias. The count model is the **pooled two-scenario** artifact `drf_forest_global_pooled_w20_t8.drf` —
one model across both legs, or part of the measured "response" would be a model swap.

## 2. Three defects were fixed on the way in; two would each have invalidated the measurement

1. **The harness conditioned every year on a FROZEN PRESENT-DAY CLIMATE.** It read its 4-column bioclimatic
   tail ONCE from the five-cell registry `M_cells.csv`, whose value is the per-cell 2000–2019 climatology.
   On an 81-year ssp370 leg that shows the count model present-day climate throughout, so the two legs
   differ only through the roster and **any measured response is driven to ~0 by construction** — an
   unfalsifiable experiment, not a null result. The shipped runtime never had the defect
   (`FluxDrivenSlowEmulator.boundary_series`, ADR 0026), and the pooled forest was *trained* under exactly
   that per-(Cell,Year) treatment, so this was also a train/inference split (ADR 0023). Fixed by
   `scripts/build_rung2_boundary_series.py` + `--boundary-csv`; unset, the static tail is kept, so ADR
   0176's arms still reproduce byte-for-byte.
2. **`scripts/run_daily_subset.sh` could not generate a runnable ssp370 config at all** — its CO2 path named
   a file removed when `climclusterpy_package/` was reorganised on 2026-07-27/28. Repointed to the recovered
   copy (md5 `ed5699b9c92d4d25857889f644b153db`, 5212 B, verified).
3. **The baseline and the arms had drifted onto different binaries.** `run_rung2_replay_arm.sh`'s
   `MODE=record` hardcodes `bin/lpjml`, which line M rebuilt on 2026-08-12 21:12 for the ADR-0130 `ind`
   switches, while the arms run `bin/lpjml_rung2_v6`. `ARM=REC` now lives in `run_rung2_s_arm.sh`, pinned to
   the same `$BIN` as the arms by construction.

## 3. THE RESULT — the sign, which is the part that matters

`response = terminal(ssp370) − terminal(historic)`; `truth` is the same for `REC`. FIT's own response is
**not one-signed**: it thins at 7 of the 12 cells and **gains** stems at 5.

| | cells where FIT THINS (7) | cells where FIT GAINS (5) |
|---|---|---|
| `NP` (persistence null) | 7 / 7 sign correct | **1 / 5** |
| `S0` (shipped uniform) | 7 / 7 | **1 / 5** |
| `S0h` (interface control) | 7 / 7 | **1 / 5** |
| `S1` (trait ordering) | 6 / 6 (cell 22732 lost, §6) | **2 / 5** |

**The learned demography thins almost everywhere.** Where FIT thins it agrees in sign; where FIT gains
stems it keeps thinning. And **the persistence null reproduces the arms' sign pattern exactly** — 8/12
for `NP`, `S0` and `S0h` alike. So on the direction of the warming response, the shipped count model is
**indistinguishable from doing nothing**, at every cell in this set.

The three cells where every arm including the null gets the sign wrong are **22990, 32628 and 42973**
(FIT +0.60, +0.88, +0.60 stems; arms −1.5 to −7.5). The two the arms get right are 12045 and 44048 —
and 44048 is the cell with by far the largest true gain (+5.24).

## 4. Magnitude, and why the pooled slope may NOT be quoted as a summary

Weighted through-origin slope of response on truth across cells, with Cochran's Q on the per-cell ratios:

| arm | slope | per-cell ratio mean (n) | Q (df) | I² |
|---|---|---|---|---|
| `NP` | 2.559 | 2.904 (12) | 1.7e11 (11) | 100.0 % |
| `S0` | 1.481 ± 0.093 | 1.216 (7) | 88.5 (6) | 93.2 % |
| `S0h` | 1.333 | 1.350 (7) | 460.5 (6) | 98.7 % |
| `S1` | 1.441 ± 0.050 | 3.351 (7) | 699.4 (6) | 99.1 % |

Two readings, and the second cancels most of the first:

* **The arms beat the null on magnitude.** `NP` over-responds by 2.56×, the arms by 1.33–1.48×. That is a
  real difference and it is the one thing the learned model demonstrably buys here.
* **`I² is 93–99 % for every arm`, so there is no common effect for the slope to estimate.** The per-cell
  ratios run from −7.5 to +15.5. The pooled slope is an artifact of averaging heterogeneous cells and
  **must not be quoted as "the emulator's warming response is 1.4× too strong"** (ADR 0174 §3d — this is
  exactly the cancellation that ADR warned about, now measured). **The per-cell table is the result.**

Five cells have `|truth|` below one seed standard deviation and are reported as unresolved rather than
dropped; they are excluded from the ratio column only, never from the sign test or the slope.

## 5. ⚠ THIS IS NOT YET A CLEAN CLIMATE RESPONSE — the legs have different lengths

The historic leg is 20 years and the ssp370 leg is 81. So `terminal(ssp) − terminal(hist)` is the climate
response **plus 61 extra years of free-running drift**, and an arm with zero climate sensitivity still posts
a large "response" on that definition. **`NP` is the direct evidence**: it kills nobody, yet it thins at
almost every cell and posts the largest slope of all (2.56). That is drift, not sensitivity.

⇒ **No number in §4 may be quoted as a climate sensitivity.** The §3 SIGN result is more robust — a
pure-drift artifact would not preferentially align with FIT's own thinning cells — but even it is
contaminated, since "thin everywhere" agrees with "FIT thinned" for free.

The control that separates them is **written, tested and one command**:
`BOUNDARY=frozen SCEN=ssp370 bash scripts/run_rung2_response_matrix.sh` reruns the ssp370 leg with the
climate held at present day — same restart, same seeds, same leg length, only the climate channel frozen.
Then `transient − frozen` is the climate response with drift differenced out and `frozen − historic` is the
drift. **That is the next action and it is the number the owner asked for.** It did not fit in this session.

## 6. Two limits of the substitution interface, both in the C hook (line M's `rung2_apply.c`)

* **`ERROR043: rung2 apply: duplicate roster key (pft P, tree N)` killed 82 of 510 runs.** The guard is
  `rung2_apply_note` → `find_verdict`, gated on `rung2_defer_mortality()` = **either** env var
  (`rung2_apply.c:118`), so **it fires in the pure OBSERVATION path too** — several `ARM=REC` baselines died
  of it. It is **cell-specific, not leg-length-specific** (20-year historic runs hit it as well). Cells
  **23318 and 33335 lost their baseline in both scenarios**, and **46336** lost its ssp370 baseline; all
  three are excluded, leaving the 12 scored cells. ADR 0176 never saw it because it ran the one cell that
  does not collide. `fread_tree.c:64-66` **does** restore `index` and advance the per-PFT counter past it,
  so both "uninitialised memory" and "the counter restarts at 0" are ruled out — **the mechanism is open**.
* **Cell 22732's `S0h`/`S1` ssp370 arms hang at the rendezvous, reproducibly, at low concurrency as well as
  high** — the harness serves ~755 of 2025 patch-years, logs one malformed request (`year -1`, survived only
  because the boundary lookup clamps), then idles out while the C waits on its apply timeout.

**Nothing contaminated survived into §3–4**: every dump is gated on the run's own
`lpjml successfully terminated` line AND on the expected terminal year, and every exclusion is printed with
its reason. A hung or crashed run is dropped, never scored at an early year.

## 7. Consequences

1. **The response deliverable is not met.** The count model does not reproduce FIT's warming response: it
   thins everywhere, and its direction is that of a model that learned nothing. Reporting a magnitude ratio
   without §3 and §5 would overstate it badly.
2. **Run the frozen-climate control before any further modelling work** (§5). Until then, the attribution
   between "no climate sensitivity" and "sensitivity swamped by drift" is open, and ADR 0175 §3's falsifier
   for `roster_n_prev` is still untested.
3. **`trait_mortality`'s flip criterion is untouched.** `S1 − S0h` is not resolved here on the response
   (S1's advantage is within the per-cell heterogeneity), so ADR 0176 §4's certain-set criterion remains the
   gate. It needs no new run — the dumps are on disk.
4. **Raise the duplicate-key guard with line M** as an integration point: the key `(pft_id, treeidx)` is not
   unique in all cells, and it currently fails the observation path too.
