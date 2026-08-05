# ADR 0101 — the response arm is a SEED ENSEMBLE, not a run: ADR 0100's response contribution does not survive replication, and its baseline defect was CELL SCOPE, not scenario coverage

* **Status:** Accepted
* **Date:** 2026-08-05
* **Line:** S (Component-S science) · ADR block 0100–0119 (tier 2)
* **Supersedes, in part:** **ADR 0100 §1, §2 and §5**. Its *protocol* decisions (the 2×2 on real
  two-scenario forcing, the window mean, the raised `k_cap`, the byte-identical `MODE=stage2`) all stand and
  are used unchanged here. Its three *conclusions* do not: the operator's response contribution, the claim
  that the emulator's baseline warming response is wrong-signed, and the attribution of that to the
  artifact's training scenario. ADR 0100 is immutable — this ADR is the correction, not an edit.
* **Decides:** **(1)** a Phase-3A response number is a **seed ensemble** with a stated `n`, mean, SEM and
  95 % CI — a single-seed read is one draw and may not be quoted; **(2)** a response measurement is
  interpretable only when **hard kills = 0 and count-override (shortfall) years = 0**, alongside ADR 0048's
  merge dormancy; **(3)** the artifact pair is part of the measurement and must be named with every number;
  **(4)** the deployment-relevant answer is recorded as it came out — the operator's contribution to the
  warming response is **not distinguishable from zero** — and Phase 3A's Stage-3 claim is withdrawn rather
  than restated on the artifact that happened to show it.
* **Related:** ADR 0100 (the protocol this uses and the conclusions this corrects), ADR 0049 (the LEVEL
  claim — **confirmed and strengthened here**), ADR 0048 (merge dormancy; the measurement protocol),
  ADR 0046 §1/§3 (the target: FIT's +2432.9 gC/m³ per-cell shift, within-PFT within-age selection),
  ADR 0034 (the trained-band excursion diagnostic — **correct as a measurement, mis-read as a cause**),
  ADR 0031 (the `t7`/`t8` complete-tree-PFT artifact generations), ADR 0026 (the transient boundary),
  ADR 0023/0029 (artifact pinning and the S→M contract), ADR 0044 (the global response gate — **nothing here
  may be quoted against it**)
* **Evidence:** `scripts/trait_mortality_arm_probe.jl` (now with a `SEED` / `DRF_ART` / `RCOP_ART` /
  `N_INIT` / `AGE0` / `BOUNDARY` knob), `scripts/run_response_seed_ensemble.sh`,
  `scripts/summarize_response_seed_ensemble.py`; committed fixture
  `test/testitems/references/S_response_seed_ensemble.csv` (32 per-seed rows, three artifacts).
  Jobs: `1701183`/`1701192` (pooled, seed 1 — the ACTION-A run and its re-run on the final script,
  identical to the digit), `1701190` (global historic), `1701191` (global ssp370), `1701193`/`1701194`
  (window-40 sensitivity), `1701195`/`1701198`/`1701199`/`1701200` (the initial-condition decomposition),
  `1701207–1701219` (pooled 12-seed ensemble), `1701220–1701227` (demo 8-seed ensemble),
  `1701249–1701260` (global-historic 12-seed ensemble). Hainich cell 42490 only (guardrail 6).

## Context

ADR 0100 measured the trait-mortality operator's contribution to the *warming response* as a 2×2 double
difference and reported **+3 400.6 gC/m³ = +1.40× the FIT shift, right sign**, with the finding that the
emulator's *baseline* response is wrong-signed (`R_ctl` = −5 945.8 = −2.44× FIT). It attributed that baseline
defect to the demo `.rcop` being fit on the **historic scenario alone** — `soilmoist` runs 0.658 trained-band
widths below anything that copula saw, a 16× larger excursion than the historic arm — and handed forward a
**falsifiable prediction**: re-run the 2×2 against the global `pooled_w20` artifacts, which are fit on
historic *and* ssp370, and `|R_ctl|` should shrink or flip.

Everything below was produced by running that prediction and then asking the two questions it does not
answer on its own: *is one seed a measurement?* and *if the pooled artifact fixes it, is the scenario what
did the fixing?*

## Decision

### 1. A response number is an ensemble; the seed is a nuisance parameter with the size of the signal

The 2×2 differences four **small-sample stochastic** rollouts — ~17 initial cohorts at Hainich plus a few
tens of copula-drawn recruits over 81 years. `SEED` was hard-coded to `1` through ADR 0100. Exposing it and
replicating gives a seed **standard deviation of 0.67–1.74× FIT on the double difference** — the same size as
the effect being measured. So:

* **no single-seed response number may be quoted**, including ADR 0100's; report mean ± SEM with `n` and a
  95 % CI, from `summarize_response_seed_ensemble.py`, which refuses to average a run that violated a
  precondition;
* **a common seed across the four corners does NOT pair them.** All four corners run `seed = SEED`, yet the
  noise does not cancel: `sd(Δ_ssp) = 2 419` and `sd(interaction) = 2 452` gC/m³ are the same number. The
  rosters diverge after year 1 (ADR 0048 §2's feedback), so the four seed streams are consumed differently
  and the differencing buys no variance reduction. Replication is the only lever;
* **measured power:** at sd ≈ 1.0× FIT, ~8 seeds resolve a 1×-FIT effect at 80 % power; the +0.26× actually
  measured needs **~115**. 12 is the practical default — enough to *exclude* 1×, not to *confirm* 0.26×.

### 2. Hard kills and count-override years are a precondition, not a diagnostic

ADR 0048 established that a response is only interpretable with the k-cap merge dormant. A second silent
failure mode is now measured, and it is larger. Changing only the per-cell count seed `n_init` from 11.0 to
7.0 on the pooled artifact fires **6 hard kills and one year in which the hazard OVERRODE the DRF's count
target** (max relative shortfall 0.144) — and the operator's contribution swings from **+0.756× to −3.714×
FIT**. When the hazard overrides the count, the operator stops being a redistribution of a DRF-set count and
the double difference measures a different object. ⇒ **hard kills = 0 and shortfall years = 0 are required**,
and the summarizer excludes violating runs from every statistic rather than averaging them in.

### 3. The artifact pair is part of the measurement

`DRF_ART`/`RCOP_ART` are now knobs, and every response number carries the pair, the per-cell `n_init`/`age0`
and the boundary row it was produced with. The probe prints all of them in its header. Two hard-coded messages
that asserted the *demo* artifact's properties as if they were the harness's were also removed: "not inert ⇒
out-of-band extrapolation" (false for an artifact trained on a varying boundary — it mis-reported the good
artifact as the broken one) and "the two boundary rows report `Inf`" (true only for a zero-width band).

### 4. Report the deployment answer, not the artifact that showed the effect

Three artifacts were ensembled. The one line M pins is `drf_forest_global_pooled_w20_t8` + its `.rcop`
(`M_slow_init_meta.json`). Its answer is the one recorded as Phase 3A's, and it is a null.

## What the ensembles say

Hainich only, 81 yr per corner, `K_CAP=400`, `SCORE_WINDOW=20`, real two-scenario forcing (+2.45 K /
+709 gdd5), `n_init=11.0`/`age0=43.556` throughout, **0 merges / 0 hard kills / 0 shortfall years in all 32
runs**, carbon closing at 0.6–1.8e-11 everywhere. `×FIT` = ÷ 2432.9 (ADR 0046 §1).

| artifact | n | operator's LEVEL effect, historic (gC/m³) | t | `R_ctl` ×FIT [95 % CI] | `R_arm` ×FIT [95 % CI] | **operator's contribution to the RESPONSE** ×FIT [95 % CI] | t |
|---|---|---|---|---|---|---|---|
| demo Hainich single-cell (**ADR 0100's basis**) | 8 | +8 959 ± 862 | 10.4 | **−1.234** [−2.058, −0.411] | +0.121 [−1.071, +1.313] | +1.356 [−0.100, +2.812] | 2.20 |
| global **historic-only** `t8` | 12 | +6 718 ± 286 | 23.5 | **+0.417** [+0.050, +0.784] | **+0.465** [+0.236, +0.695] | +0.048 [−0.380, +0.476] | 0.25 |
| global **pooled_w20** `t8` (**line M's pin**) | 12 | +7 041 ± 334 | 21.1 | −0.000 [−0.809, +0.808] | +0.263 [−0.211, +0.736] | **+0.263** [−0.377, +0.903] | 0.90 |

### 1. ADR 0049's LEVEL claim is confirmed and strengthened

The operator raises community wood density by **+6 718 ± 286 / +7 041 ± 334 / +8 959 ± 862 gC/m³** on the
three artifacts, `t` = 10.4–23.5. That is 2.76×/2.89×/3.68× the FIT shift as a *level*, consistent with
ADR 0049's constant-forcing 3.25×, and it is the one number in this family that replication makes *stronger*
rather than weaker. **The level effect is a measurement.**

### 2. The operator's contribution to the warming RESPONSE does not survive replication

On **both** global artifacts it is indistinguishable from zero: +0.048 [−0.380, +0.476] and
+0.263 [−0.377, +0.903]. Both CIs **exclude ADR 0100's +1.40×**. On ADR 0100's own demo artifact the 8-seed
mean is +1.356 — so **its +1.398 was a fair draw, not an outlier** — but even there the CI [−0.100, +2.812]
straddles zero. The effect was never significant on any artifact; the single-seed read overstated its
precision by ~6×.

**Phase 3A's Stage-3 claim is therefore withdrawn.** The correct statement is: *the ported hazard produces a
large, robust, correctly-signed change in the LEVEL of community wood density, and no detectable change in
its warming RESPONSE at one cell over 81 years.* ADR 0100's §1 reading — "the operator selects harder in a warmer
climate" (Δ 2.54× → 3.94×) — survives *as a direction* on its own artifact's ensemble (Δ +8 959 → +12 257) but
not as a significant one, and it does **not** reproduce on either global artifact, where the level effect is
essentially climate-independent: **+6 718 → +6 835** and **+7 041 → +7 680**.

### 3. ADR 0100's headline FINDING is a single-cell-artifact artefact, and on a global artifact the sign REVERSES

`R_ctl` is **significantly negative on the demo artifact** (−1.234 [−2.058, −0.411]) — so ADR 0100 §2 was
real *for its artifact*. On the global historic-only artifact it is **significantly POSITIVE**
(+0.417 [+0.050, +0.784]) — FIT's own sign. On the pooled artifact it is **exactly zero** (−0.000 ± 0.367).

So *"the emulator's baseline warming response has the wrong sign and is larger than the operator's
contribution"* — the finding ADR 0100 said reframes the line — **is not a property of the emulator.** It is a
property of a single-cell demo *test fixture*. The recruit channel's real defect on the deployment artifact is
milder and different: **no warming response where FIT has +1×**, rather than a wrong-signed one.

### 4. The attribution was wrong: CELL SCOPE, not scenario coverage

ADR 0100's predicted fix was retraining on the pooled historic+ssp370 table. Decomposing it with two
ensembles that each hold one factor fixed:

| contrast | what it isolates | ΔR_ctl ×FIT | t |
|---|---|---|---|
| demo → global **historic** (scenario held at historic) | **cell scope** | **+1.651 ± 0.386** [+0.840, +2.462] | **+4.28** |
| global historic → global **pooled** (scope held global) | **scenario coverage** | −0.417 ± 0.403 [−1.253, +0.419] | −1.03 |

**Cell scope is the lever; scenario coverage is not** — and if anything pooling the ssp370 rows in moves
`R_ctl` slightly the wrong way. The mechanism is visible in the metadata: the `soilmoist` trained band is
**[0.791, 1.000] (width 0.209)** for the demo artifact, **[0.000, 1.002] (width 1.002)** for the
historic-only global — **4.79× wider** — and **[0.001, 1.002] (width 1.001)** for the pooled one, i.e.
adding the entire ssp370 scenario widens it by **−0.04 %**. Every runtime feature reads **0.0 excursion in
both scenarios** on both global artifacts, `soilmoist` down to 0.557 included.

**The transferable lesson, and it is the important one.** ADR 0100 §5's excursion measurement was *correct* —
`soilmoist` really was 0.658 band widths out, really was 16× worse under ssp370 — and its causal inference was
still wrong. A scenario-asymmetric excursion does **not** imply the training scenario is the fix: widening the
band by *any* means fixes it, and here cross-**cell** pooling widens it 4.79× while cross-**scenario** pooling
widens it not at all. ⇒ **an excursion diagnostic localises a channel; it does not identify which axis of the
training design to change.** Test the candidate levers separately, holding the others fixed.

### 5. The pooled artifact has NO well-defined per-cell initial condition, and line M's pin resolves it silently

The pooled artifact's meta names `cell_meta cell_meta.parquet`, and **that file does not exist** — neither in
`slow_count_pooled_w20_t8/` nor beside the `.drf`. Its two sub-tables disagree at Hainich:

| source | `n_init` | `age0` | boundary `gdd5` / `tcm` |
|---|---|---|---|
| `slow_count_historic_w20_t8` (a training input) | 11.0 | 43.556 | 1 698.0 / 0.047 |
| `slow_count_ssp370_w20_t8` (the other training input) | **7.0** | **46.0** | 1 947.7 / 0.865 |
| `slow_runtime_historic_t8` (**what M's pin actually reads**) | 11.0 | 43.556 | **1 863.7 / 0.218** |

Both seeds are legitimate, and the choice **swings the operator's contribution by 4.5× FIT** (+0.756× at
11.0/43.556 → −3.714× at 7.0/43.556 → −4.080× at 7.0/46.0). Decomposed: **`n_init` is the fragile seed**
(it is what fires the hard kills of §2); `age0` 43.556 → 46.0 fires none, yet still moves the contribution
from +0.756× to +0.017× — *a 44× change with every diagnostic clean*. Two consequences, both S→M:

* **`M_slow_init_meta.json` takes `n_init`/`age0` from `slow_runtime_historic_t8`** — the well-behaved branch,
  so nothing is broken today, but the substitution is a **choice with a 4.5×-FIT consequence that is recorded
  nowhere**. `extract_cell_slow_init.py`'s own contract ("read them from the cell_meta of the SAME artifact
  version the driver pins") is **unsatisfiable** for a pooled artifact and was met by silent substitution.
* **the boundary row is on a basis the pinned artifact was never trained on.** M reads gdd5 = 1 863.7 from
  `slow_runtime_historic_t8` (the *climatological* table), while the pooled artifact was trained on the
  w20 transient tables whose historic value for this cell is **1 698.0** — a 165.7 gdd5 gap, 23 % of the
  +709 warming signal — and on that artifact the boundary channel is worth **3 165 gC/m³ = 1.30× FIT** on
  ensemble average (§6).

### 6. The boundary channel is LIVE on every global artifact — ADR 0100 §4's null was a fixture property

Measured as `max |Δwd|` between a transient and a static boundary on the same forcing, over the ensembles:

| artifact | boundary liveness, gC/m³ (mean [range]) | ×FIT |
|---|---|---|
| demo Hainich single-cell | **0.0 [0.0, 0.0] — exactly zero in all 8 seeds** | 0.00 |
| global historic-only | 1 105.3 [288.6, 2 040.4] | 0.45 |
| global pooled_w20 (line M's pin) | **3 164.5 [829.9, 6 677.2]** | **1.30** |

ADR 0100 §4's inertness is real, is *exact*, and is a property of the **per-cell demo fixture only** — the
8-seed all-zero result is a harder confirmation of it than the single run ADR 0100 had. Every global artifact
can express a boundary-mediated response, and the pooled one does so at **1.30× the FIT shift on average**.
That is what makes §5's boundary-basis mismatch worth fixing rather than noting: M's pin feeds a 1.30×-FIT
channel a boundary row from a table the pinned artifact was never trained on.

### 7. Robustness of what is claimed here

* **The `SEED` knob defaults to ADR 0100's behaviour, verified.** `SEED=1` on the demo pair returns
  `R_ctl` **−5 945.79**, `R_arm` **−2 545.21**, interaction **+3 400.58** — ADR 0100's primary to the digit.
  So the ensemble is a superset of that measurement, not a different harness, and the disagreement with
  ADR 0100 is entirely about replication and attribution, never about reproducibility.
* **Scoring window.** `SCORE_WINDOW` 20 → 40 at seed 1: global historic +0.220× → +0.292×, pooled
  +0.756× → +0.950×. Both well inside the seed spread; the window is not what moved the answer.
* **The seed-1 pooled run reproduces to the digit** after the script edits (`R_ctl` −1.94, `R_arm` +1 836.09,
  interaction +1 838.02 in both job 1701183 and 1701192) — guardrail 4 by measurement.
* **Hard-kill fragility is artifact-specific.** The broken seed pair (7.0/46.0) on the global historic
  artifact fires 4 hard kills yet still returns +0.233× — close to its own +0.048 ± 0.194 ensemble. The
  pooled artifact is the fragile one.

## Consequences

* **Phase 3A Stage 3's response claim is WITHDRAWN.** `+1.40× FIT` must not be quoted, in the report, an
  abstract, or a handoff. The defensible Phase-3A claims are ADR 0049's **level** change (now +6 718 ± 286
  gC/m³, `t` = 23.5 on the deployment artifact) and ADR 0049 §4's **age structure**. Two numbers in
  `docs/component_s_public_report.tex` inherited from ADR 0100 need the same treatment as the two already
  known to be wrong there.
* **The recruit channel remains the next lever, but the target changed.** Not "fix a wrong-signed response"
  (that was the fixture) but "the deployment artifact's recruit channel has **no** warming response where FIT
  has +1×". That is a **conditioning-set** question — milestone **S2** — since the band excursions are now
  all zero and the training scenario is excluded. Phase 3A cannot deliver it.
* **Every future response arm runs as an ensemble.** `run_response_seed_ensemble.sh` +
  `summarize_response_seed_ensemble.py` are the entry points; the summarizer enforces the ADR-0048/0101
  preconditions and refuses to mix artifacts or initial conditions in one ensemble.
* **A single-cell 81-yr harness cannot resolve a FIT-magnitude warming response, and that is now quantified**
  (~115 seeds for the measured effect). FIT's own +2432.9 is a 25-patch ensemble mean over 67 420 cells. So
  the **ADR-0044 global gate is the right instrument** for any response claim, and this harness is a
  mechanism check — which is what ADR 0049/0100 said, now for a measured reason rather than a cautious one.
* **S→M integration point #2 (new, unraised):** the pooled artifact's missing `cell_meta.parquet`, the
  undocumented `n_init`/`age0` substitution, and the boundary-basis mismatch in `M_slow_init_meta.json`.
  Nothing is broken in M's current pin — it happens to read the well-behaved branch — but the artifact ships
  an undefined per-cell initial condition whose two candidate resolutions differ by 4.5× FIT. Either ship a
  pooled `cell_meta.parquet` or record the substitution and its consequence in the pin's provenance.
  (Integration point #1, `fc.pft_ids`, is unchanged and still unraised.)
* **Unchanged:** `trait_mortality` stays **opt-in, default-off**; runtime `[deps]` stays empty; no committed
  baseline moved; `MODE=stage2` is untouched and remains the ADR-0049 regression.

## Alternatives rejected

* **Report the pooled seed-1 result (+0.756× FIT) as Phase 3A's answer.** It is a real run and it is the
  deployment artifact — but it is one draw from a distribution with sd 1.008, and reporting it would repeat
  exactly the error this ADR exists to correct.
* **Keep ADR 0100's +1.40× and add a caveat.** Its own artifact's CI straddles zero and both global CIs
  exclude it. A caveat would leave a withdrawn number quotable.
* **Blame the seed spread on `n_init`/`age0` and pick the "right" seed.** The 12-seed ensembles hold both
  fixed at 11.0/43.556, and the spread is still ±1.0× FIT. The initial condition is a *second*, independent
  problem (§5), not an explanation of the first.
* **Retrain a pooled artifact with a proper `cell_meta` before concluding.** Days of compute to change an
  initial condition that §5 shows is not what makes the response null — the two global artifacts disagree on
  `n_init`'s consequence but agree on the null. Recorded as an integration point instead.
* **Run ~115 seeds to settle +0.263× ourselves.** The measured effect is ≤ +0.90× FIT at one cell with two
  known confounds travelling with it (data source, +65.9 ppm CO₂). The ADR-0044 global gate answers the same
  question on 67 420 cells; spending ~10× this ADR's compute to put a CI on a single-cell number that may not
  be quoted against that gate is the wrong buy.
