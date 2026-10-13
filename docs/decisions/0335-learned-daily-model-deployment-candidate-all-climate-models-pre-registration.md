# 0335 — Learned daily model: deployment candidate trained on all five climate models (pre-registration)

* **Status:** Pre-registered 2026-10-13, before training. Result appended below.
* **Follows:** ADR 0334 §4 (arms L and V both null; the remaining respiration excess is generalisation to places, not
  a calendar input or the sample budget), STATE item 2 ("once arms L / V settle, train on all five climate models").
  Tool change: `scripts/f2_train.py --test-legs none` (no climate model held out; the default is unchanged).

## 1. The arm

**Arm D** (`D_3x256_seed0..4`, ensemble `DE_5seed`): exactly arm W (ADR 0333: 3 × 256 network, `--npp-head ra`,
humidity input dropped, 40 M samples, deep drainage 365 d, 5-member ensemble, calendar season input), with the two
legs held out so far added to training — **all 14 legs**: observed weather plus MPI-ESM1-2-HR ssp126/370/585,
GFDL-ESM4, MRI-ESM2-0 and IPSL-CM6A-LR ssp126/370/585, UKESM1-0-LL ssp370. The cell split is unchanged (730 train,
80 validation, 240 held-out cells in held-out blocks), so **the only out-of-sample check left is by cell (place)**:
every score below is on the 240 held-out cells, on climates the network has now seen. A number from this arm must
never be quoted as skill on an unseen climate model; ADR 0333's arms W/U remain the evidence for that.

## 2. Pre-registered numbers (free runs, held-out cells, ADR 0325 yardstick, `f2_relative_score.py WE_5seed DE_5seed`)

* **Primary (adopt as the deployment model):** on the two newly included legs (UKESM ssp370, MPI ssp585), the typical
  (30-yr p50) NPP error early (2021–50) is at most arm W's (3.16 / 3.37), and UKESM GPP / NPP drift ≤ 1.15 / 1.25
  (arm W's values, i.e. not worse).
* **Must not get worse:** on the 12 legs shared with arm W, the median over legs of the typical GPP, NPP and ET error
  (early and late) ≤ 1.05 × arm W's; no single leg's value > 1.15 × arm W's.
* **Failure reading:** if the primary fails, adding a climate model to training does not help the cells it does not
  cover ⇒ the deployment model is still arm D (more training data cannot be the wrong default), but say that the
  held-out-climate numbers of arm W are the honest error estimate for it.
* **Expectation:** primary passes with small gains (NPP error on the two legs 5–15 % lower, UKESM NPP drift
  ~1.10–1.20); shared legs unchanged within ±5 %; the southern-block respiration excess (ADR 0334) unchanged, since it
  is about places, not climates.

## 3. Result

(to be appended)
