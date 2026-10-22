# 0361 — Forest map with more capacity (63 leaves + 800 rounds): pre-registration

* **Status:** pre-registered 2026-10-22, before the arm ran.
* **Owner (2026-10-22):** "yes, do that if you think it is promising" — the follow-up named in ADR 0359 §4.
* **Why promising:** in ADR 0359 the three single-setting capacity arms all point the same way. L63 (dense tree count
  0.969, dense biomass per tree 0.982, all 12 quantity/group pairs ≤ 1.004), R800 (0.986 / 0.981), LR10 (0.982 /
  0.988). L63 missed the "better" bar by 0.002 on biomass per tree. More leaves and more rounds are partly
  complementary (tree shape vs number of corrections), so the combination may clear it. Overfitting is the risk:
  4× the model size at a fixed learning rate of 0.05.

## Arms

| arm | fit arguments | compared with |
|---|---|---|
| `L63R800` (level map alone) | `--lgb num_leaves=63 --rounds 800` | `_fx` (the release's map settings, no departure model) |
| `L63R800` departure (the shipped configuration) | the same + `--state dep` | `_statedep_fx` (release v2) |

Both via `scripts/run_design_sensitivity.sh capacity` (driver extended), summarised by
`scripts/summarise_design_sensitivity.py map` (arm added to both lists).

## Reading (fixed before running)

1. **Better (level map)**, exactly ADR 0359 §1: dense tree count AND dense biomass per tree median ratio ≤ 0.98 over the
   15 held-out cases, and no quantity/group (median or worst tenth) worse than 1.02.
2. **Shipped configuration not harmed:** with the departure model, no quantity/group worse than 1.02 against
   `_statedep_fx`; die-off capture ≥ 0.16 (release 0.18); dense drift late/early not above the release's by more
   than 0.03 (1.20 tree count, 1.41 biomass per tree).
3. **Cost:** the map is evaluated once per cell-year; after a rebuild, the one-core end-to-end time
   (`run_emulator.py`) must stay within the T31-class allowance of 0.0135 core-s per cell-year (release 7.0e-3).
4. **Adopt** only if 1, 2 and 3 all hold: rebuild `release/v3` + the fold release with its gates and `--check`, a new
   decision record. Otherwise the release's 31 leaves / 400 rounds stand, and this result is added to the paper's
   Table `tab:choices_map` as one more row either way.

## Expectation (written before running)

Dense tree count ~0.96, dense biomass per tree ~0.975–0.985 — i.e. close to the bar on the second quantity; the
sparse groups gain most (L63 0.925, R800 0.937). Probability of clearing all of 1–3: roughly one in three.

## Result (2026-10-22; jobs 2661366 18 min, 2661367 38 min)

Median over 15 held-out cases of arm / release (ratio to a second run), worst tenth in brackets:

| | dense count | dense biomass/tree | dense trait medians | sparse count | sparse biomass/tree | worst pair | drift count / biomass (release) | die-off capture |
|---|---|---|---|---|---|---|---|---|
| level map | **0.970** (0.968) | **0.952** (0.968) | 0.979–0.984 | 0.901 (0.893) | 0.945 (0.985) | **1.022** (sparse SLA, worst tenth) | 1.242 / 1.411 (1.219 / 1.407) | — |
| with departure model | 0.986 (0.971) | 0.961 (0.982) | 0.979–0.984 | 0.932 (0.930) | 1.004 (0.967) | **1.022** (same) | **1.243 / 1.444** (1.201 / 1.412) | 0.184 (0.183) |

**Against the pre-registered reading:** (1) better — dense count and biomass ≤ 0.98 ✓, but one pair at 1.022 > 1.02 ✗;
(2) shipped configuration — the same 1.022 ✗, capture ✓, drift +0.042 (count) and +0.032 (biomass) > 0.03 ✗;
(3) cost not measured (no rebuild). ⇒ **NOT ADOPTED; the release keeps 31 leaves / 400 rounds.**

**What the drift failure actually is (post hoc, does not change the verdict):** the bigger map's error is LOWER than the
release's in every period — dense tree count 0.962 / 0.982 / 0.987 (2021–40 / 2051–70 / 2081–2100), biomass per tree
0.956 / 0.978 / 0.972 (level map; with the departure model 0.963 / 0.982 / 0.991 and 0.957 / 0.977 / 0.977). The
late/early ratio rises because the gain is largest at the start and fades to ~1 % by the end of the century. So the
extra capacity mostly fits the present-day better — the period that is already the best — and buys little where the
emulator is weakest (late-century, under the strongest climate change). That is a substantive reason not to adopt it
beyond the letter of the rule. Read as: the release sits on a plateau; four times the model size gives 1–4 %.
