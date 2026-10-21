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
