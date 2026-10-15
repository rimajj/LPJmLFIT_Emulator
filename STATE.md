# STATE — the single current state and handoff (one development stream, ADR 0319)

> The `## NEXT — start here` block is what the SessionStart hook replays. **Refresh it before a session ends.**
> Narrative → `JOURNAL.md` (append). Durable cross-cutting facts → `MEMORY.md`. Decisions → next free ADR number
> (**0341**). History of the retired parallel lines: `lines/{S,M,E,O,X}/STATE.md` + `JOURNAL.md` (read-only).

## The goal (owner, 2026-10-10, ADR 0318)

> "AS before the goal is to have a full LPJmL_FIT emulator that emulates everything happening in the mode orders of
> magnitude faster thatn lpjmlfit and does not drift away in transient runs"

* **Everything** = forest structure (tree counts, biomass, trait distributions) **and** the daily carbon/water exchange.
  ⚠ The re-implemented daily physics in `src/fdiff.jl` is **4.62× slower** than the original (ADR 0084) — it is not a
  fast path; the daily exchange must be **learned** too (owner: *"We also want to simulate teh fast physcs
  structure!!!"*).
* **Yardstick everywhere = error relative to a second run of the original** (ADR 0317), never a flat ±X %; the daily
  fluxes need not be as close as a second run (owner 2026-10-11, ADR 0325). **Drift = the gap to the original growing
  over time**, not the values changing (owner: *"as long as we are no in equilibirum of course teh values drift"*).
* **Pass standard (relaxed, owner 2026-10-10):** *"as long as the dense ells are fine and the sparse cells dont drift
  away completely we should go on."* Proposed numbers: ADR 0318 §2, scorer `scripts/explore_relaxed_standard.py`.
* **Orders of magnitude faster** than the original, measured end to end at the patch count the original is run at.
* **No drift** in transient (year-by-year) runs.
* Standing closures: no CO2 response (ADR 0004/0107); reuse is authorised, cite (ADR 0081).

## Where things stand (2026-10-15) — RELEASE v1 EXISTS (ADR 0340)

**The whole emulator is one package**, `python/src/lpjmlfit_emulator/landemu` (`LandEmulator`; numpy + LightGBM only):
daily weather in → daily GPP/NPP/interception/transpiration/evaporation/runoff/snow/soil water + yearly tree count,
biomass per tree, four trait medians, leaf area, vegetation carbon, cover of 10 plant types out. Releases under
`/p/projects/open/Jamir/esm_land_emulator_data/release/` (`v1` = deployment; `fold_gfdl-esm4_v1` = proves package ==
scored pipeline). Guide `docs/emulator_release.md`. Verdict (ADR 0340 §4): structure on the panel 21/22 relaxed
criteria (dense tree count one case short); all 57 726 global cells under an unseen scenario fails tree count /
biomass per tree / sparse stems (traits pass); daily GPP + totals pass, NPP 3.9×, ET 3.1×, runoff 5.2×, responses
1.8–2.5× a second run; no structure drift after the start state fades (×1.05); 7.6e-3 core-s per cell-year = 35× /
~900× cheaper than the original at 25 / 500 patches; setups only for the 1 050 panel cells; NOT coupled to an ESM.
The table below is the per-part history up to 2026-10-14.

| part | state |
|---|---|
| forest structure, 30-year windows | best setup = per-cell anchor + gradient-boosted climate shift, log target on biomass per tree (ADR 0316 §11–13). On the 1 050-cell panel, held-out climate model: passes the relaxed standard except dense typical-cell tree count (1.23× a second run) / biomass per tree (1.18×) on the case count and the sparse stem total (19.5 %). Dense stem total "low in 14–15/15 cases" is a selection effect, not a bias (ADR 0329: with dense cells defined before the run the total is −3.7 … +1.5 %, median 0.0 %); the real limit is that the learned shift explains only 27–49 % of how cells differ in their response to an unseen climate model. **Year by year (ADR 0330):** run each year from the trailing 30-yr climate, its error starts below a second run's (it knows the run's 2000–2019 state) and settles at about a second run's by the 2050s (biomass per tree ~1.0×, tree count ~1.1×), with a slow tree-count creep after that grows with warming; the pre-registered late/early drift rule fails as written (tree count 8/15, biomass per tree 2/15). **Cost 7.8e-5 core-s per cell-year** (the daily half is 6.4e-3, so the whole is ~6.5e-3 ≈ 41× less than the original at 25 patches, ~1 000× at 500; a sum of parts). Not yet on the global venue |
| daily carbon/water exchange, learned | **exists (phase A, offline; phase B — fed the emulated stand — measured, ADR 0331: +10–40 % error; with the deployment model arm D on all 13 climate-model legs, ADR 0337: the full learned emulator's daily fluxes are GPP 2.0–2.9×, ET 2.1–3.9×, NPP 3.3–4.6×, runoff 3.9–7.7× a second run, totals ≤ 2.5 %, the stand adds a median 13 % (GPP) to 35 % (ET); falsifier fired on two IPSL legs ⇒ the stand map is now the lever).** **End-to-end timing (ADR 0337 §5): 6.55e-3 core-s per cell-year on one core for structure + stand + daily model in one loop (daily model 97 %), 41× less than the original at 25 patches, ≈ 1 000× at 500 (the original measured at one cell).** One small network + closed snow / top-metre / deep water stores, trained on the panel runs of the original (ADR 0320–0328; skill `daily-model`). Best setup: five-seed ensemble, NPP = GPP − respiration, no humidity input (the original's daily exchange never reads it, ADR 0327), deep store draining into runoff (ADR 0326). **On the second-run yardstick:** GPP / ET typical error 2–3× a second run ✓, NPP 2.7–3.5× (3× proposed) ✗, runoff 3.9–5.5× ✗ (the ET error carried through — runoff is a small residual of rain minus ET); area totals ≤ 1.8 % ✓; deep store stable ✓; no drift on the MPI climates ✓; **under the unseen climate model the GPP / NPP gap still grows 1.29× / 1.35× over the century ✗** (removing humidity was a null). Cost 6.4e-3 core-s per cell-year. The stand still comes from the original (flatters the score). **More climate models in training (ADR 0328, 2026-10-12): fails, falsifier fired** — levels improve 10–20 %, the gap still grows on UKESM / IPSL, NPP totals now 3–5 % off (plant respiration 1.5–3 % too high everywhere). A structured carbon head (ADR 0332) was much worse (daily GPP fit 2.3× worse) — closed. **Warm-climate coverage (ADR 0333, corrected by ADR 0336):** the effect is small — with IPSL in training UKESM's GPP/NPP gap growth 1.19/1.27 → 1.15/1.25 (the first reading, 1.30/1.41, came from early-stopped members); swapped roles IPSL ssp585 1.13/1.20 → 1.06/1.14. Run-to-run noise (ADR 0336 §6): the UKESM effect is within it, the IPSL GPP effect beyond it. ⇒ still train on every climate model (no measured cost on GPP). **The "constant respiration excess" is four places (ADR 0334):** none on training cells (≤ 0.8 %) or on 200 of 240 held-out cells; ~80 % of it is four held-out blocks at 33–47° S (NPP −7 … −11 %), two at the edge of what training covers. Arms L (hemisphere-aware season input) and V (80 M samples) **both null** (ADR 0334 §4) ⇒ it is coverage of places. Deployment candidate (all 14 legs, arm D, ADR 0335): not passed — UKESM drift 1.25 → 1.17 but early ET 16–28 % worse on three legs; **11 members in 7 ensembles had stopped mid-schedule (ADR 0336); repaired:** the L/V nulls stand, **arm D is the deployment model** (UKESM drift 1.25 → 1.17, early ET ×1.16–1.28 on three legs). **Run-to-run noise of one ensemble: ±9–20 % per leg in typical error, 0.05–0.08 in drift** (ADR 0336 §6) — most earlier arm margins are inside it |
| re-implemented daily physics (F_diff) | C-validated at 5 biome cells with known residuals (ADR 0125–0139); 4.62× slower than the original. Parked as the fidelity oracle/reference, not the runtime path |
| energy closure, online coupling | built for Hainich / harness level (ADR 0073–0085); not on the critical path until both halves above exist |

## NEXT — start here

**Release v1 is done (ADR 0340).** What remains is a choice among its §5 misses — ask the owner which, do not start
another open-ended arm:
1. **Coupling to SpeedyWeather** (goal #3; nothing exists in the package). The package's `step_year` is the call an
   ESM would make; the coupler needs daily ET/runoff/snow back to the atmosphere and the energy closure (ADR
   0073–0085), and forcing per land column.
2. **A global release:** the anchors need the original's yearly 2020–2100 output on every cell; Billing's runs store
   per-tree output only for 1985–2014 / 2071–2100. Either run the original yearly on all cells, or design an anchor
   from those windows (and an anchor rule past 2100). Global all-cells structure score (window map, unseen
   scenario): ADR 0340 §4.1, `scripts/explore_glob_allcells.py`, outputs `billing_global/eval/allcells/`.
3. **Daily NPP / ET / runoff and the climate response** (ADR 0340 §4.2): the stand's plant-type cover carries most of
   the added error (ADR 0338); two loss re-weightings did nothing (ADR 0339).
4. **Speed:** a GPU or batched numpy daily step; the daily model is 97 % of the cost.
Owner questions still open: the relaxed numbers (ADR 0318 §2), the daily numbers (ADR 0325 §3; runoff is a residual),
dense cells defined by the anchor (ADR 0329 — the fair reading) rather than the held-out run, removal of `wt-*`.
⚠ Known: panel forcing is 0.1 °C-quantised and the training table counted exactly-30.0 °C days as hot (float32 scale);
the package does not (ADR 0340 §3) — harmless for continuous forcing.
