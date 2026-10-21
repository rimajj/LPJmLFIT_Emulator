# 0348 — Learned daily model: soil texture as an input, and how many networks the ensemble needs (pre-registration)

* **Status:** pre-registered 2026-10-21, before any training. Results: §4, added after the runs.
* **Owner instruction (2026-10-21):** *"do the model fixes first and train on the wvaialbeldata to see how they help.
  we produce more full grid trainig data only when we are sure whic model verisn we want to emulate"* — and *"store
  the daly data in teh refomrt folder, not in open"*.
* **Follows:** STATE.md to-dos of 2026-10-21 (items 1 and 3: soil texture is not a daily-network input; the
  ensemble size was chosen for cost and never tuned), ADR 0335/0336 (arm D = the deployment daily model, and the
  run-to-run noise of one five-member ensemble), ADR 0322 (a single network's NPP level wanders by several %).
* **Storage (owner, 2026-10-21):** the daily arrays and runs moved from `/p/projects/open/Jamir/esm_land_emulator_data/f2`
  to **`/p/projects/reformit/Jamir/esm_land_emulator_data/f2`** (rsync + checksum dry-run = 0 differences, job
  2638455); the old path is a symbolic link, so every older record and script still resolves.
* **Code:** `scripts/f2_train.py --soil-texture` (new, off by default ⇒ every earlier run unchanged);
  `scripts/build_soil_texture_reference.py` → `config/soil_texture_by_code.csv`;
  `scripts/f2_chain_arm.py --after` (new); `scripts/f2_ensemble_sizes.py` (new).

## 1. Arm T — soil texture as four per-cell inputs

**What the network sees today about the soil:** only the top-metre capacity `cap` (= Σ_{l<3} whc_nat·dz, mm, yearly)
and the stores. `cap` carries how much water the top metre holds (field capacity minus wilting point), not how fast
water enters or moves through it. In the original the infiltration / percolation step uses the soil type's saturated
conductivity `Ks` and suction `Sf` (`par/soil_20m.js`). Runoff (5.2× a second run) and ET (3.1×) are the worst daily
fluxes on the release (ADR 0340 §4.2), and runoff error is the negative of the ET error (ADR 0326 §4).

**The change (one variable):** arm D's exact recipe (3 × 256 network, NPP = GPP − respiration head, humidity input
dropped, 40 M samples, all 14 climate legs, deep store draining over 365 days, five members) **plus** four per-cell
columns appended after every other input: sand fraction, clay fraction, ln Ks (mm/h), ln Sf (mm) of the cell's soil
type. Values are read from the panel binary snapshot's `par/soil_20m.js` with `cpp -P`, and the input soil code is
mapped onto it by the run's own `soilmap` (code k = the k-th name, looked up in `soilpar` by name; `soilpar` also has
an unmapped "clay (light)" row). The panel's 1 050 cells carry 11 of the 13 codes (none of codes 2, 10). Silt is
`1 − sand − clay` and is left out as redundant.

**Runs.** Members `T_3x256_seed0..4` → ensemble `TE_5seed`; replicate `T2_3x256_seed5..9` → `T2E_5seed`. Controls:
`DE_5seed` (arm D, seeds 0–4, existing) and a new arm-D replicate `D2_3x256_seed5..9` → `D2E_5seed`. Two pairs with
different seeds (TE vs DE, T2E vs D2E), because one ensemble's run-to-run noise is ±9–20 % per leg (ADR 0336 §6).

**Venue:** free runs of all 14 legs, the 238 held-out cells with GPP ≥ 50 (ADR 0325 yardstick,
`f2_relative_score.py`), compared with `f2_relscore_compare.py <scores> REF CAND`. ⚠ Arm D trains on every climate
leg, so this is **out of sample by place only** — which is the axis a soil property can help.

**Pre-registered verdict (both pairs must agree):**

* **Primary (adopt):** median over legs of CAND / REF typical (30-yr p50, early and late pooled) **runoff ≤ 0.90 and
  ET ≤ 0.95**.
* **Must not get worse:** median GPP and NPP ratio ≤ 1.05; no flux's worst leg > 1.25; no leg's drift more than
  0.08 above REF's (drift noise ±0.05–0.08, ADR 0336 §6).
* **Null reading:** primary fails in either pair ⇒ at the panel's soil types texture carries nothing the capacity
  input does not; close the item (no larger arm).
* **Expectation:** runoff 0.85–0.95, ET 0.93–1.00, carbon unchanged within ±3 %. Modest, because `cap` already
  encodes the texture's water-holding part and there are only 11 types.
* **If adopted:** the package (`landemu`) gets the same four columns — `Setup` already carries `soil_code`.

## 2. Arm N — ensemble size 1 / 3 / 5 / 10

No new training beyond the arm-D replicate of §1. Ensembles of arm-D members (each a free-run + score job,
`--deep-tau 365`):

| size | replicate a | replicate b |
|---|---|---|
| 1 | `DE_1seed` (seed 0) | `D2E_1seed` (seed 5) |
| 3 | `DE_3seed` (seeds 0–2) | `D2E_3seed` (seeds 5–7) |
| 5 | `DE_5seed` (existing) | `D2E_5seed` (§1) |
| 10 | `DE_10seed` (seeds 0–9) | — |

The one-core cost per cell-year of each ensemble is measured inside the same job (`bench_speed`).

**Pre-registered decision.** Reference = `DE_5seed` for the a-replicates and `D2E_5seed` for the b-replicates.

* **Smaller deployment ensemble:** the smallest size whose BOTH replicates have median ratio ≤ 1.05 on every flux
  (GPP, NPP, ET, runoff) becomes the deployment size.
* **Larger:** 10 is adopted only if `DE_10seed` against BOTH five-member ensembles has median ≤ 0.95 on NPP or
  runoff and ≤ 1.00 on every flux.
* Otherwise five stays.
* **Expectation:** 1 member clearly worse (1.1–1.3 on NPP, ADR 0322); 3 within ~5 % of 5 (borderline); 10 gains
  ≤ 5 %. Cost scales roughly with the member count (the daily networks are 97 % of the emulator's time).

## 3. Not in this record

Soil code as a category in the yearly forest maps, and memory of single extreme years (STATE to-dos 2 and 4), are
separate records. More full-grid training data is deferred by the owner until the model version to emulate is
settled.

## 4. Results

### 4.1 Arm T — soil texture (2026-10-21; ensembles `TE_5seed`, `T2E_5seed`, `D2E_5seed`; score job 2643623,
`logs/f2-armT-relscore.md`; every member ran 10 of 10 epochs)

Median over the 14 legs × 2 windows of CAND / REF typical-cell error (30-yr means; < 1 = texture helps):

| | GPP | NPP | ET | runoff | worst leg (flux) | drift rise > 0.08 |
|---|---|---|---|---|---|---|
| pair a `TE_5seed` / `DE_5seed` | **1.056 ✗** | 0.868 | 0.988 ✗ | 0.949 ✗ | **1.335 ✗** (GPP, IPSL ssp585 late) | none (max +0.07, NPP) |
| pair b `T2E_5seed` / `D2E_5seed` | 1.009 | 0.841 | 0.988 ✗ | 0.886 ✓ | 1.180 (GPP, IPSL ssp126 early) | **1 ✗** (ET IPSL ssp585 0.90 → 1.00) |
| pre-registered | ≤ 1.05 | ≤ 1.05 | ≤ 0.95 | ≤ 0.90 | ≤ 1.25 | none |

**Verdict: NOT adopted (null reading).** The primary (runoff ≤ 0.90 AND ET ≤ 0.95) fails in both pairs on ET
(0.988 in each) and in pair a on runoff too; pair a also fails must-not-worsen on GPP and on its worst leg. Against
the expectation (runoff 0.85–0.95 ✓ on the edge, ET 0.93–1.00 ✓, carbon within ±3 % ✗): **NPP is 13–16 % better in
both pairs** — consistent over legs (pair b: every one of 28 leg-windows below 0.94; pair a: 24 of 28 below 1) and
larger than one ensemble's run-to-run noise at the median (±9 % per leg at the 90th percentile, ADR 0336 §6) — while
GPP is unchanged or worse, so the gain is in the respiration side of the NPP head, not in production. That was not
predicted and is not an adoption criterion here; following it up would need its own pre-registration (owner's call).
As pre-registered, the water item is closed: at the panel's 11 soil types texture adds nothing for ET that the
top-metre capacity does not already carry.

### 4.2 Arm N — ensemble size (2026-10-21; jobs 2638485, 2638488–92; every member 10 of 10 epochs; scored with
`f2_relative_score.py` + `f2_relscore_compare.py`, free runs, 14 legs, 238 held-out cells)

Median over legs × windows of size-n / five-member typical-cell error (< 1 = better), and the one-core cost of the
daily half (`bench_speed`, same job):

| ensemble | GPP | NPP | ET | runoff | worst (flux, leg) | core-s per cell-year |
|---|---|---|---|---|---|---|
| 1 net, seed 0 / `DE_5seed` | 1.276 | 1.173 | 1.169 | 1.228 | 1.723 (GPP, IPSL ssp370 late) | 1.32e-3 |
| 1 net, seed 5 / `D2E_5seed` | 1.125 | 1.013 | 1.283 | 1.100 | 1.591 (ET, UKESM ssp370 late) | 1.32e-3 |
| 3 nets, seeds 0–2 / `DE_5seed` | 1.004 | 1.015 | **1.114** | **1.101** | 1.280 (runoff, GFDL ssp370 early) | 3.85e-3 |
| 3 nets, seeds 5–7 / `D2E_5seed` | 0.951 | 1.040 | 1.022 | 1.040 | 1.271 (ET, IPSL ssp585 late) | 3.88e-3 |
| 5 nets (reference) | 1 | 1 | 1 | 1 | — | 6.40e-3 |
| 10 nets, seeds 0–9 / `DE_5seed` | **1.018** | 1.000 | 0.938 | 0.942 | 1.109 (GPP, IPSL ssp370 late) | 1.28e-2 |
| 10 nets, seeds 0–9 / `D2E_5seed` | 0.979 | 0.928 | 0.913 | 0.869 | 1.046 (GPP, MPI ssp126 early) | 1.28e-2 |

**Verdict (pre-registered §2): five stays.** Smaller: one network fails in both replicates (10–28 % worse); three
passes in replicate b (≤ 1.04) but not in replicate a (ET 1.114, runoff 1.101) — both were required. Larger: ten
improves ET by 6–9 % and runoff by 6–13 % against both five-member ensembles, NPP 0–7 %, but GPP is 1.8 % worse
against `DE_5seed` (whose five members it contains), failing "≤ 1.00 on every flux". The cost is linear in the
member count (1.3e-3 per network); ten would put the whole emulator at ~1.4e-2 core-s per cell-year, just above the
T31-class allowance of 0.0135 (`EXECUTION_PLAN.md` §0) — a speed cost for a gain mostly in ET / runoff.
**Reading:** the five-member choice of ADR 0322 was close to the knee; the replicate-to-replicate spread at three
members (ET 1.11 vs 1.02) is itself the run-to-run noise ADR 0336 §6 warned about.
