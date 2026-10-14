# 0338 — Which stand input carries the emulated stand's added error: one input at a time (pre-registration)

* **Status:** decided 2026-10-14. Result in §4.
* **Depends on:** ADR 0337 (arm D fed the emulated stand: the stand adds a median 13 % (GPP) to 35 % (ET) to the
  daily fluxes' typical error; falsifier fired on two IPSL legs ⇒ the next lever is the stand map), ADR 0331 (the stand
  map; its own errors: leaf area 1.37×, vegetation carbon 1.24×, tree cover 1.55×, grass cover 1.27× a second run on
  dense cells; 1.58 / 1.67 / 1.74 / 1.98× on all cells).
* **Scripts:** `scripts/explore_panel_stand_map.py arrays --only <quantities>` (new: take only these stand quantities
  from the map, the rest from the original), `scripts/f2_train.py --ensemble D_3x256_seed0..4 --stand-dir`,
  `scripts/f2_relative_score.py`, `scripts/f2_relscore_compare.py`.

## 1. Why

To improve the stand map for the daily model, it must be known which of its three input groups the daily model's
added error comes from. The daily model reads 12 stand numbers per cell-year: leaf area, vegetation carbon, and cover
of each of the 10 plant types.

## 2. Design (one variable per arm; everything else as ADR 0337)

Arm D, the 13 climate-model legs, held-out cells, free runs, the stand of run k from the map fitted with run k and the
leg's climate model unseen. Three arms, each taking ONE group from the stand map and the other two from the original:

| arm | from the stand map | from the original |
|---|---|---|
| `PD_L` | leaf area | vegetation carbon, cover |
| `PD_V` | vegetation carbon | leaf area, cover |
| `PD_C` | cover of the 10 plant types | leaf area, vegetation carbon |

References: `PD_A` (all from the original) and `PD_B` (all from the map), ADR 0337. **Harness:** the `--only` path with
all twelve quantities must reproduce `stand_emul`'s arrays exactly (checked on the arrays before the runs).

**Statistic:** per leg × flux × window, the share of the full increment carried by arm X:
`s_X = (X ÷ A − 1) / (B ÷ A − 1)` on the typical-cell error, computed only where `B ÷ A − 1 ≥ 0.10` (a smaller
denominator makes the share meaningless); the median share per flux over those values, and the median of
`s_L + s_V + s_C` (1 = the three effects add up; below 1 = they reinforce each other; above 1 = they partly cancel).
Same five networks in every arm, so ensemble-to-ensemble noise does not enter (ADR 0337 §2).

## 3. Expectations and decision rule (written before the runs)

* **ET:** cover carries most of the increment, `s_C` median ≥ 0.5. Reason: cover is the stand map's worst input
  (1.55–1.98× a second run) and decides how water splits between interception, transpiration and soil evaporation.
* **GPP and NPP:** leaf area carries most, `s_L` median ≥ 0.5 (light capture).
* **Vegetation carbon:** `s_V` median ≤ 0.2 for every flux (the original's daily exchange reads leaf area and cover,
  and vegetation carbon only through them).
* **Additivity:** median `s_L + s_V + s_C` within 0.7–1.3.
* **Decision rule:** the group with the largest median share for ET is the stand-map target to improve first (e.g.
  cover as its own learned quantity with a relative target, or per-type cover constrained to sum to the total); if no
  group reaches 0.5 for ET, the stand map is improved as a whole. **Falsifier:** `s_V` ≥ 0.3 for any flux ⇒ the daily
  model uses vegetation carbon as a stand-in for something the other inputs do not carry, and that input needs a check
  before any stand-map work.

## 4. Result (2026-10-14)

Jobs 2483470–72 (PD_L, PD_V, PD_C) completed; scored with `scripts/f2_relative_score.py PD_A PD_B PD_L PD_V PD_C` then
`scripts/f2_stand_attribution.py` (ctl_obs excluded, `B/A − 1 ≥ 0.10` rows only):

| flux | n kept | median `s_L` | median `s_V` | median `s_C` | median sum |
|---|---|---|---|---|---|
| gpp | 15 | 0.34 | 0.16 | 0.70 | 1.18 |
| npp | 16 | 0.10 | 0.12 | 0.89 | 1.13 |
| et | 25 | 0.20 | 0.08 | 0.87 | 1.27 |
| runoff | 19 | 0.45 | 0.13 | 0.57 | 1.04 |

Pooled over all kept (leg, flux, window) rows: median `s_L + s_V + s_C` = 1.19 (n = 75; within the 0.7–1.3 additivity
band, so the three groups are close to additive with a slight partly-cancelling tilt).

**Against the pre-registered expectations:**

* **ET — confirmed.** `s_C` median 0.87 ≥ 0.5: cover carries almost all of ET's added error, as expected.
* **GPP and NPP — NOT confirmed, in fact reversed.** The guess was `s_L` ≥ 0.5 (leaf area, light capture). Measured
  `s_L` is 0.34 (GPP) and 0.10 (NPP) — small — while `s_C` (cover) is 0.70 (GPP) and 0.89 (NPP), the largest share for
  every flux, not only ET. Cover decides more than light capture in this daily model; a plausible reason is that per-type
  cover also gates how the stand's area is split for interception/evaporation/transpiration partitioning that then
  feeds back into carbon uptake, but that is not established here — a hypothesis for later, not a finding.
* **Vegetation carbon — confirmed.** `s_V` median is 0.08–0.16 across all four fluxes, under the 0.2 ceiling.
* **Additivity — confirmed.** Pooled median sum 1.19, inside 0.7–1.3.
* **Falsifier — not fired on the pre-registered (median) reading:** the largest median `s_V` over the four fluxes is
  0.16 (gpp), well under 0.3. Caveat: individual (leg, window) values of `s_V` range up to 0.60 (npp) and 0.56 (gpp) —
  the median is what was pre-registered as the test statistic, and it clears the falsifier comfortably, but a few
  individual legs show a larger vegetation-carbon contribution than the median suggests.

**Decision:** cover (the per-type plant cover) is the stand-map target to improve first — it carries the largest
median share of the added error on every flux (GPP, NPP, ET, runoff), not only ET as hypothesized. Leaf area is a
secondary contributor (largest for runoff, 0.45); vegetation carbon is a minor pass-through everywhere, as expected.
Next: improve the cover component of the stand map (e.g., learn it as its own target with a relative error measure,
or constrain the ten per-type covers to sum to the stand total) before revisiting leaf area or vegetation carbon.
