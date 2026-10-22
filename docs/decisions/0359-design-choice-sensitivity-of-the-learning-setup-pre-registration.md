# 0359 — Why these networks and these trees? Design-choice sensitivity of the learning set-up (pre-registration)

* **Status:** pre-registered 2026-10-21, before any arm of this record ran.
* **Owner instruction (2026-10-21):** "all decisions for learning architecture, number of neural networks or gradient
  trees etc. must be justified. why this number / architecture? if that needs extra experiments, do them!"
* **Evidence that already exists** (not re-run): daily network 2×64 vs 3×256 (ADR 0321), ensemble size 1/3/5/10 with
  replicates (ADR 0322/0348), sample count 40/46.7/80/160 M (ADR 0322/0334/0336), humidity input (ADR 0327), deep-store
  time constant (ADR 0326), NPP head form (ADR 0324/0332), soil texture input (ADR 0348); forest map: the anchor, the
  non-recursive form (ADR 0315/0316/0330/0352), log vs Poisson/Tweedie targets (ADR 0316), lat/lon/soil code
  (ADR 0343/0349), cover mode (ADR 0339), training rows every year with extra inputs (ADR 0351), the departure model's
  inputs (ADR 0354–0356).
* **Not yet justified, tested here:** every LightGBM setting of the map and of the departure model, the climate-window
  and anomaly-window lengths, the training-row step with the release inputs, the start-state and climate-offset
  inputs; the daily networks' width and depth beyond one pair, activation, epochs, learning rate, batch size and the
  trailing-window inputs.
* **Code:** `scripts/explore_panel_yearly_drift.py` (`--lgb --rounds --dep-lgb --dep-rounds --clim-window --z-window
  --drop-feats --train-step`), `scripts/f2_train.py` (`--act`, window inputs droppable by name), driver
  `scripts/run_design_sensitivity.sh`, summary `scripts/summarise_design_sensitivity.py`.

## 1. Forest map (the level), one setting at a time around the release (`fix`, leak-free)

| arm | change | arm | change |
|---|---|---|---|
| L15 / L63 | 15 / 63 leaves (31) | W10 / W20 / W50 | climate window 10 / 20 / 50 years (30) |
| R200 / R800 | 200 / 800 rounds (400) | S2 / S8 | training rows every 2nd / 8th year (4th) |
| LR025 / LR10 | learning rate 0.025 / 0.1 (0.05) | NOS0 | without the run's own 2000–2019 levels and their offset |
| F10 | no row / column subsampling (0.8) | NODC | without the climate offset from the anchor runs |
| MD100 | min 100 rows per leaf (20) | NOANC | without the anchors as inputs (still the target's reference) |

Scored as every structure arm: 15 held-out cases, `final_structure_score.py` (dense / sparse, typical and worst-tenth
ratio to a second run, area totals) and the drift stage. Departure model (on `dep`): DL15 / DL63 leaves, DR200 / DR800
rounds, DZ15 / DZ20 anomaly window 15 / 20 years (30).

**Reading (pre-registered):** an alternative is **better** if dense tree count AND dense biomass per tree improve by
≥ 2 % (median ratio to the release over 15 cases ≤ 0.98) with no quantity and group worse by > 2 %; **worse** if any
of those two is > 2 % worse; otherwise **equivalent**. If an alternative is better, it replaces the release setting and
the release is rebuilt (a new record); if none is, the release setting is justified as "no tested alternative does
better" with the measured curve. Settings that are equivalent but cheaper are reported (rounds, leaves).

## 2. Daily networks: a screen on single networks, then full ensembles for the contenders

**Screen:** one network per arm and seed (3 seeds: 0, 1, 2), trained exactly as the release members (`D` arm:
14 legs, 40 M samples, NPP as GPP − Ra, humidity dropped), `--train-only`; measure = the final validation loss
(80 cells never trained on, all eight targets standardised) and its per-target parts. Arms: BASE (3×256, SiLU, 10
epochs, peak learning rate 3e-3, batch 16 384), H128 / H512 (width), L2 / L4 (depth), RELU / GELU / TANH, E5 / E20
(epochs), LR1 / LR10 (peak learning rate 1e-3 / 1e-2), B4K / B64K (batch), NOWIN (no trailing windows), NOPWIN (no
precipitation windows), NOTWIN (no temperature / radiation windows).

**Stage 2 (full test):** an arm whose 3-seed mean validation loss is below BASE's by more than 2 % AND by more than two
pooled seed standard deviations is trained as a five-network ensemble and free-run (`f2_chain_arm.py`), scored with
`f2_relative_score.py` against `DE_5seed` and `D2E_5seed` (two baseline replicates, ADR 0336), and adopted if it
beats BOTH by ≥ 5 % (median over legs) on at least two of GPP, ET, NPP, runoff with none worse by > 5 %, at a cost
the T31 allowance still covers (ADR 0348 §2). NOWIN goes to stage 2 regardless if its loss is > 10 % worse (to show
what the windows carry in free runs) — reported, not adopted.

## 3. Expectations (written before running)

* Map: equivalent for leaves 15–63, rounds 200–800, learning rate, subsampling, min leaf size (gradient boosting is
  flat near its defaults); W10 worse (noisier window), W50 slightly worse late (lags the climate); S2 equivalent, S8
  slightly worse; NOS0 clearly worse early (ADR 0315: start state +0.09), NODC and NOANC worse.
* Departure model: all equivalent; DZ15 possibly better for tree count (closer to the event).
* Daily: H128 2–5 % worse, H512 within ±2 %, L2 worse, L4 equivalent; RELU / GELU / TANH within ±3 %; E5 worse, E20
  slightly better on loss (risk of overfit on free runs); LR1 worse, LR10 unstable; batch within ±3 %; NOWIN > 10 %
  worse (the deep-water memory), NOPWIN worse, NOTWIN slightly worse. Most likely no arm reaches stage 2 except NOWIN.

## 4. Results — forest map and departure model (2026-10-22; all 22 arms finished)

Median over the 15 held-out cases of (arm's ratio to a second run) / (release's), from
`python scripts/summarise_design_sensitivity.py map`; < 1 is better than the release. Drift = late (2081–2100) over
early (2021–2040) dense ratio; release 1.22 (tree count) / 1.41 (biomass per tree).

| arm | dense count | dense biomass/tree | dense count worst 10 % | sparse count | dense trait medians | verdict |
|---|---|---|---|---|---|---|
| L15 | 1.010 | 1.028 | 1.031 | 1.067 | 1.018 | worse |
| **L63** | **0.969** | **0.982** | 0.970 | 0.925 | 0.986 | equivalent (every one of 12 quantity/group pairs ≤ 1.004) |
| R200 | 1.010 | 1.030 | 1.019 | 1.047 | 1.013 | worse |
| R800 | 0.986 | 0.981 | 0.988 | 0.937 | 0.986 | equivalent |
| LR025 | 1.006 | 1.026 | 1.024 | 1.030 | 1.013 | worse |
| LR10 | 0.982 | 0.988 | 0.976 | 0.923 | 0.993 | equivalent |
| F10 | 0.985 | 0.995 | 0.998 | 0.985 | 1.006 | equivalent |
| MD100 | 0.975 | 1.003 | 0.999 | 0.995 | 1.001 | equivalent |
| W10 | 0.988 | 1.017 | 0.981 | 0.874 | 1.005 | equivalent |
| W20 | 0.991 | 1.002 | 0.985 | 0.966 | 1.005 | equivalent |
| W50 | 0.999 | 1.036 | 1.039 | 1.008 | 1.004 | worse |
| S2 | 0.980 | 1.003 | 0.996 | 0.974 | 1.007 | equivalent |
| S8 | 1.000 | 0.997 | 0.989 | 1.009 | 1.003 | equivalent (half the training rows) |
| NOS0 | 1.005 | 1.011 | 0.996 | 0.973 | **1.294** | equivalent by the rule — but dense trait medians 1.13–1.41 (rooting depth worst, 1.73 in the worst tenth) |
| NODC | 1.012 | 1.112 | 1.036 | 1.136 | 1.026 | worse; late biomass drift 1.56 |
| NOANC | 1.003 | 1.021 | 1.016 | 1.012 | 1.014 | worse |
| DL15 | 1.016 | 0.999 | 1.026 | 0.995 | — | equivalent; die-off capture 0.16 (release 0.18) |
| DL63 | 0.969 | 1.004 | 0.988 | 1.007 | — | equivalent; capture 0.20 |
| DR200 | 1.015 | 1.006 | 0.993 | 1.014 | — | equivalent; capture 0.15 |
| DR800 | 0.974 | 0.998 | 0.993 | 0.982 | — | equivalent; capture 0.21 |
| DZ15 | 1.006 | 0.992 | 1.000 | 0.990 | — | equivalent; capture 0.18 |
| DZ20 | 0.995 | 0.993 | 0.997 | 0.982 | — | equivalent; capture 0.18 |

**Reading.** No alternative is *better* under §1's rule, so **no release setting changes and the release is not
rebuilt**. Each release setting is justified as "no tested alternative does better", and the release sits on a
plateau: fewer leaves, fewer rounds and a lower learning rate are each worse by 2–3 % on dense biomass per tree; more
leaves, more rounds and a higher rate are each 1–3 % better on dense tree count but miss the biomass-per-tree bar
(closest: L63, 0.982 against 0.98, better on every quantity). The 30-year climate window is justified against 50
(worse) and is equivalent to 10/20 (10 is better for sparse tree count, worse for dense biomass per tree). Training
rows every 8th year are equivalent at half the rows. Every input group is needed: the climate offset from the anchors
(NODC) costs 11 % on dense biomass per tree and 14 % on sparse tree count; the anchors as inputs cost 2 %; the start
state does not affect tree count or biomass but **carries the trait medians** (+13 to +41 %) — the two-quantity verdict
calls NOS0 equivalent, which understates it. Departure model: all six equivalent; more capacity (DL63, DR800) raises die-off
capture 0.18 → 0.20–0.21, far from the 0.30 bar of ADR 0354.
Expectations of §3 that held: plateau near the defaults, W50 worse, S8 not worse, NODC/NOANC worse. That did not:
W10 not worse; NOS0 not worse on counts (only on traits); L15/R200/LR025 worse rather than equivalent.

**Follow-up worth a pre-registration, not run:** a combined capacity arm (63 leaves + 800 rounds) — the three
capacity arms point the same way and L63 misses the bar by 0.002.

## 5. Daily screen (2026-10-22; 17 arms × 3 seeds) and the stage-2 selection

Validation loss over 3 seeds, ratio to BASE (0.05373): L4 0.957 · B4K 0.960 · E20 0.973 · H512 0.976 · GELU 1.010 ·
RELU 1.017 · TANH 1.027 · H128 1.062 · LR1 1.100 · E5 1.105 · L2 1.118 · NOTWIN 1.146 · B64K 1.288 · NOPWIN 1.570 ·
NOWIN 1.890 · LR10 2.195 (one seed diverged: sd 0.085).

**Deviation, recorded before any stage-2 result exists.** §2's "two pooled seed standard deviations" was implemented
in `summarise_design_sensitivity.py` as the RMS of every arm's seed sd. LR10's sd is a diverged training, not seed
noise, and inflates the pooled value to 0.0207 = 39 % of BASE's loss, which no arm could ever clear (the rule would be
void by construction). Pooled over the 16 arms that trained stably it is **0.00078**. On that basis **L4 (−4.3 %, 3.0
sd) and B4K (−4.0 %, 2.8 sd) qualify; E20 (−2.7 %, 1.9 sd) and H512 (−2.4 %, 1.7 sd) do not.** NOWIN is > 10 % worse
and goes to stage 2 for reporting only. Ensembles `DCL4E_5seed`, `DCB4KE_5seed`, `DCNOWINE_5seed` (members seeds 0–4,
`f2_chain_arm.py`, release flags + the arm's flag), scored by the chained job `logs/f2-dc-stage2-score.jcf`
→ `logs/f2-dc-stage2-relscore.md` against `DE_5seed` and `D2E_5seed` with §2's adoption rule unchanged.

## 6. Stage 2 results (2026-10-22; three five-network ensembles, free runs on all 14 legs)

Scored by `logs/f2-dc-stage2-score.jcf` (job 2661168) → `logs/f2-dc-stage2-relscore.md` +
`logs/f2-dc-stage2-score.2661168.out`. Each entry: median over the 14 legs × 2 windows of (arm's typical 30-yr error /
baseline's), against both baseline replicates (`f2_relscore_compare.py`). §2's rule: adopt if ≤ 0.95 against BOTH on
≥ 2 of GPP / NPP / ET / runoff, none > 1.05, cost within the T31-class allowance (0.0135 core-s per cell-year, whole
emulator).

| arm | vs | GPP | NPP | ET | runoff | daily cost (core-s / cell-year) | verdict |
|---|---|---|---|---|---|---|---|
| L4 (4 × 256) | DE_5seed | **0.938** | **0.940** | 0.993 | **0.904** | 8.98e-3 (base 6.40e-3) | |
| L4 (4 × 256) | D2E_5seed | **0.917** | **0.869** | **0.943** | **0.835** | | **ADOPTED** (3 of 4 vs both) |
| B4K (batch 4 096) | DE_5seed | 0.991 | 0.983 | 0.960 | 1.125 | 6.41e-3 | |
| B4K (batch 4 096) | D2E_5seed | 0.939 | 0.915 | 0.951 | 1.030 | | not adopted (runoff 12.5 % worse vs DE; ≤ 0.95 on only GPP/NPP vs D2E) |
| NOWIN (no trailing windows) | DE_5seed | 1.608 | 1.218 | 1.507 | 1.468 | 6.44e-3 | report only |
| NOWIN | D2E_5seed | 1.531 | 1.168 | 1.507 | 1.269 | | |

* **L4:** the gain is broad, not a few legs: of the 112 leg × window × flux ratios, 84 are < 1 against `DE_5seed` and 103 against `D2E_5seed`. Its worst
  single ratios are late-century GPP on IPSL-CM6A-LR ssp370 / ssp585 against `DE_5seed` (1.19 / 1.18), but 0.92 / 1.01
  against `D2E_5seed` — i.e. within the two baseline replicates' own disagreement (DE's IPSL ssp370 late GPP error is
  1.37, D2E's 1.78 a second run's). Drift (late / early error) within ±0.07 of `DE_5seed`'s on every leg and flux (largest moves
  0.98 → 0.91 UKESM ET, 0.81 → 0.76 GFDL ssp126 ET, 0.94 → 0.99 IPSL ssp370 NPP); the five above 1.05 were already
  above it (IPSL ssp126 GPP/NPP 1.10/1.11 → 1.08/1.08, UKESM GPP/NPP 1.13/1.17 → 1.12/1.18, IPSL ssp585 GPP 1.07 → 1.06). Cost +2.6e-3 core-s per cell-year (40 % more for the daily part);
  the whole emulator measured 9.8e-3 (v2 7.0e-3; ADR 0362 §4), within 0.0135.
* **B4K** helped on the screen's loss (−4.0 %) but not in free runs: runoff is worse against one replicate — the
  screen's validation loss is a one-step (teacher-forced) measure and does not see the bucket's accumulation.
* **NOWIN** (report only): without the trailing weather windows the free-run errors are 1.2–1.6× the release's —
  the windows carry the slow soil-water memory the bucket alone cannot.
* Expectation check (§3): L4 was expected "equivalent" and came out 6–17 % better in free runs; NOWIN > 10 % worse as
  expected; B4K "within ±3 %" — true for loss direction but runoff moved more.

**Consequence:** by §2's rule L4 is adopted: ensemble `DCL4_3x256_seed0–4` (trained exactly as `D_3x256_seed0–4`
with `--layers 4`; the tag's "3x256" is the inherited prefix, not the depth). Releases `v3` (deployment) and
`fold_gfdl-esm4_v4` were built (ADR 0362). **Post-hoc check, not part of §2's rule:** in the complete emulator (networks
fed the emulated stand) the gain shrinks to NPP −6 %, runoff −3 %, GPP / ET unchanged, at +31–40 % one-core cost
(ADR 0362 §3–4); whether v3 becomes the current release is left to the owner there. Status: accepted (the campaign);
the release choice is ADR 0362's.
