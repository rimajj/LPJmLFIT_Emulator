# 0355 — Yearly forest map: a daily soil-water stress input for the departure model (pre-registration)

* **Status:** pre-registered 2026-10-21, before the bucket is built or any fit of this record.
* **Owner instruction (2026-10-21):** "continue with b1" = ADR 0354 §4's next candidate, a daily-resolved stress
  input for the departure model.
* **Follows:** ADR 0354 (weather-driven departure model `dep`: drought die-off capture 0.03 → 0.18, aftermath gap
  4.5× → 3.75× a second run's; 20 of 22 criteria; the 25 YEARLY climate statistics explain about a quarter of a
  die-off that the original's other runs reproduce at 94 %).
* **Code:** `scripts/build_panel_bucket_stress.py` (new: stages `calib`, `build`, `check`, `events`);
  `scripts/explore_panel_yearly_drift.py fit --state depw` (new arm).

## 1. What the original's drought mortality reads (C source, live in this configuration)

* Water term (`waterstress_tree.c:31-36`, `mortality_tree_ind.c:120`): `water_stress += phen · VPD/1000 ·
  ((mort_water_res − minwscal) − wscal)` on every day with `aphen > aphen_min`, layer-1 soil temperature > 10 °C and
  `wscal < mort_water_res − minwscal`; reset on day 14 (north) / 195 (south) after the increment;
  `mort_water = mort_water_factor · water_stress / 365 · (1 + bm_inc_counter)`.
* `wscal = min(1, emax · wr / (eeq · ALPHAM / (1 + GM · ALPHAM / gp_stand_leafon)))` (`water_stressed.c:133`),
  `wr` = root-weighted relative soil water, `emax` 10 (broadleaved) / 12.9 (needleleaved) mm/day.
* Growth-efficiency term: a drought cuts growth, `bm_inc_counter` counts consecutive bad years and multiplies every
  hazard; at 5 the tree dies.
So the day-by-day ingredient missing from the yearly statistics is the soil water and its supply/demand ratio over
the season. The emulator cannot see the original's soil water at run time (its own daily model does produce one,
but it does not exist for the nine training climate models' legs here — the original's daily output exists only for
the five held-out models, ADR 0328). The stress input is therefore computed **from the daily weather alone**, which
also makes it available inside an Earth-system model.

## 2. The bucket and its six yearly statistics

Per cell, daily, from the daily weather (`tas`, `pr`, `rsds`, `lwnet`, `huss`; observed 1996–2019 in front of each
leg, started full on 1996-01-01):
* snow: precipitation falls as snow below 0 °C; melt = min(snow, 3 mm/°C/day · max(T, 0));
* top-metre store `W` with capacity `C` = the cell's top-metre water capacity at the end of 2019 (Σ_{l<3} whc·dz, the
  f2 arrays' `cap`, mean over runs m1–m4 — what the deployed emulator already fixes, ADR 0344);
* PET = `pet_pt` (the yearly statistics' Priestley–Taylor, `explore_glob_climate.py`), `eeq = PET / 1.32`;
* evaporation = min(`E_b` · W/C, PET); `W ← min(C, max(0, W + rain + melt − evaporation))`, overflow lost;
* `wscal = min(1, 10 · (W/C) / (1.391 · eeq))` (the C's form at full conductance, broadleaved `emax`; 1 when
  `eeq = 0`); VPD as the yearly statistics (`getvpd`).
Yearly statistics, over the C's accumulator window (days 15–365 north / 196–365 south) on days with T > 10 °C (the
soil-temperature gate, air temperature as proxy as in the yearly statistics):
`bk_s50` = Σ VPD · max(0, 0.5 − wscal), `bk_s30` = the same at 0.3 (kPa·day), `bk_wscal` = mean wscal (1 if no
day), `bk_dry` = days with wscal < 0.5; over the calendar year: `bk_wmin30` = minimum 30-day running mean of W/C,
`bk_aetpet` = Σ evaporation / Σ PET.
* **The one free parameter `E_b`** (mm/day) is chosen from {2, 3, 5, 8} on the observed-weather leg `ctl_obs` only
  (run m1): the value with the highest median over cells of the daily correlation between W/C and the original's own
  top-metre soil water (`rootmoist / cap`). No held-out-model data enters the choice.

## 3. Checks before any fit (reported; they decide how the result is read, not whether it runs)

* **C1 bucket vs the original's soil water** (`check`, the 13 held-out-model legs with daily output, run m1): median
  over cells of (a) the daily correlation of W/C with the original's, (b) the year-to-year correlation of `bk_s50`
  computed from the bucket vs from the original's own soil water (same formula), (c) the same for `bk_wscal`.
  Expectation: (a) 0.6–0.85, (b) 0.4–0.7, (c) 0.5–0.8.
* **C2 does it single out the die-off years** (`events`, ADR 0350's shared tree-count events of the unseen run):
  median z-anomaly of each statistic in the event year (against the cell's 30 years before), beside the yearly water
  balance's −1.20 SD; and how well each separates event years from the same cells' other years (AUC).
  Expectation: `bk_s50` z ≥ +1.5 and AUC above `cwb_ann`'s.
If C1(b) < 0.3 the bucket does not follow the original's seasonal stress and the arm's result is read as a test of
a crude index only.

## 4. The arm `depw`

= ADR 0354's `dep` + the six statistics, each as this year's raw value, last year's raw value, and both as z-scores
against the 30 years before (as `dep`'s weather anomalies) — 24 columns. Everything else as `dep` (same level map,
same departure target, same rows, same run-time forward loop). Compared with `fix` (the bars) and with `dep`.

## 5. Pre-registered verdict (bars as ADR 0354 §4, against `fix`)

* **Adopt `depw`** if: drop capture ≥ 0.30 AND aftermath gap ≤ 2.0× a second run's AND must-not-worsen (median ratio
  to `fix` ≤ 1.02 on every quantity and group, no criterion `fix` passes lost) AND drift ≤ `fix` + 0.05 (1.269 /
  1.457) and late level ≤ 1.05 × `fix` AND the 30 % start cut fades (max ≤ 1.1, late ≤ 0.5).
* Reported against `dep`: capture, gap, criteria. **The daily input is a gain** if capture rises ≥ 0.05 over `dep`'s
  0.183 with no criterion lost against `dep`.
* If it is not a gain: the yearly weather already carries what a forcing-only bucket can add; the remaining
  candidates are the stand's own vulnerability (consecutive bad years, the growth-efficiency counter) or the
  original's stochasticity at 25 patches — owner's call.

## 6. Expectations (written before running)

* `E_b`: 3 or 5 mm/day.
* `depw`: capture 0.22–0.35 (above `dep`, probably short of 0.30), gap 3.2–3.7×, criteria 20 of 22 as `dep`, drift
  unchanged. My best guess is "a gain, not adopted". I am not confident: ADR 0350 found the event years already
  extreme in the yearly water balance (−1.2 SD), so the daily timing may add less than hoped.
