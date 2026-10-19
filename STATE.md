# STATE — the single current state and handoff (one development stream, ADR 0319)

> The `## NEXT — start here` block is what the SessionStart hook replays. **Refresh it before a session ends.**
> Narrative → `JOURNAL.md` (append). Durable cross-cutting facts → `MEMORY.md`. Decisions → next free ADR number
> (**0348**). History of the retired parallel lines: `lines/{S,M,E,O,X}/STATE.md` + `JOURNAL.md` (read-only).

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
| energy closure, online coupling | **the learned emulator is two-way coupled to SpeedyWeather 0.23 (ADR 0345, 2026-10-16):** daily weather in, daily ET back as the land moisture flux, T31, 10-yr runs; offline replay identical, water closes; land ET +47 %, land rain +16 %; SpeedyWeather's own land is ~7 °C colder than the emulator's training climate. **ADR 0346:** the cold is SpeedyWeather's atmosphere (GFDL-ESM4 = W5E5 observations at these cells; not mountains, not the slab ocean; its latitude-only grey longwave + a cold lowest air layer); **albedo (emulator tree/grass cover + snow) and roughness channels added**, replay identical, < 0.1 °C effect. No runoff routing; energy closure of ADR 0073–0085 not used |

## NEXT — start here

**2026-10-19 — POEM: the overheating "fix" was a no-op; cause still open (ADR 0347 §8).** The corrected 10-yr runs
died at year 4.8 (project disk quota full) and, up to there, were identical to the first coupled runs: stock LPJmL in
POEM already sets `cell->dedt = 0` every step, so `LANDEMU_DEDT=zero|lpj` are the same model (runs deleted). The
single-hour > 80 °C overheating (from year 1, ~6 per million cell-hours, 0 in shadow) is real and unexplained; §5's
monthly climate and speed numbers stand. Shadow re-gate on the final binary: identical (1 050 / 1 050).
Disk (owner decisions 2026-10-19): **all merged LPJmL-FIT run data moved to `/p/projects/reformit/Jamir/`** (same
folder names; the emulator's nitrogen-on runs and grids are now `/p/projects/reformit/Jamir/lpjml-fit-clustered/...`,
scripts `clu_emu*.py/.sh` repointed); superseded runs trimmed to configs/logs/totals (2.9 TB); core dumps deleted;
`billing_global` is NOT a copy of Billing's data (converted tables, 8 of them now the only copy — keep), only its
leftovers removed; `xde` and the 720 GB re-convertible tables kept for now. `/p/projects/open/Jamir` ≈ 2.4 TB.
The open quota is visible with `df -h /p/projects/open` (fileset view), not `mmlsquota`.
**Next (owner to choose):** find the overheating cause from the existing records (emulator ET vs LPJmL's own ET at
the overheated cells/hours, `landemu_record.npz`, no new run — the suggested first step); or the earlier options below.

**2026-10-16 (evening) — COUPLED TO POEM 1.2: the emulator runs inside POEM's LPJmL (ADR 0347).** Build
`/p/projects/open/Jamir/poem_landemu/POEM-1.2_20261013_6-layers_landemu` (patches `patches/poem/`, skill `poem-landemu`);
switch `LANDEMU` (unset = stock, `shadow` = record only, `1` = coupled: emulator ET → next day's land moisture flux +
LPJmL's latent heat, emulator runoff → rivers). Same 0.5° grid as the emulator (58 436 cells). Gates: stock / off /
shadow identical to stock (1 050 variables), replay identical, water closes, LPJmL's water check 0 errors. 10-yr
preindustrial runs (1851–60): **POEM is not cold** (+0.04 °C vs GFDL-ESM4 1850–79, −0.5 °C vs W5E5 1985–2014; 15 % too
dry). Coupled with sun-shaped hours: land +0.1 °C, evap +5 %, rain +2 %. Flat hours: nights −2.2 °C, convective rain
−30 %, land −1.1 °C (the hour shape matters). Vegetation carbon −4 %/decade even one-way (emulator memory starts in
1985–2014 GFDL climate). **Not faster than POEM-with-LPJmL** (LPJmL still runs; emulator 2–3 %; the whole land is 28 %
of POEM's time ⇒ ≤ ~1.3× even if replaced). Defect: zeroing LPJmL's evaporation derivative let ~6 per million
cell-hours overheat past 80 °C → fixed (`LANDEMU_DEDT=lpj`); ~~corrected 10-yr runs `poem_coupled_{sun,flat}_dedtlpj_10y`
(jobs 2527979/80)~~ → done 2026-10-19, see above (`score_poem_landemu.py replay <dir>`, then the scorer with
`poem_shadow_10y`) **and append ADR 0347 §8; check `grep -c "soiltemp too large"` is 0.** Shadow re-gate on the final
binary: `gate_shadow2_1m` (job 2527981) vs `gate_stock_1m` with `poem/compare_poem_runs.py`.
**Next (owner to choose):** spin the emulator up on POEM's own climate (shadow mode) before coupling; more channels
(albedo/roughness/surface temperature, i.e. drop LPJmL's vegetation); a speed arm that skips LPJmL's daily vegetation;
a second POEM member for internal variability.

**2026-10-16 (later) — the cold bias explained, two more coupled channels (ADR 0346).** `run_speedy_landemu.jl`
now takes `ALBEDO=emulator` (land albedo from the emulator's tree cover, grass cover, snow), `ROUGH=emulator` (land
roughness from its cover) and `OCEAN=prescribed`; every run records the climate diagnostics that
`scripts/online_coupling/diagnose_speedy_climate.py` scores against W5E5 observations / GFDL-ESM4 at the same cells.
Findings (7 × 10-yr runs): GFDL-ESM4 equals the observations (17.12 vs 17.11 °C); SpeedyWeather's land air is 6.6 °C
too cold (8.8 °C in summer) — not mountains (+0.4 °C), not the slab ocean (it drifts warm; observed SST → −8.2 °C);
+8–15 W/m² sun but −18–28 W/m² net longwave (latitude-only grey longwave), top soil 9 K warmer than the air above it.
The new channels: replay identical, water closes, land temperature −0.06…+0.08 °C (inside one run's yearly spread).
ADR 0345's offline totals were over the whole 0.5° grid, not the 1 197 cells — its ×1.08/×1.32/×0.94 are void.
**Next (owner to choose):** bias-corrected weather for the emulator (observed climatology + SpeedyWeather anomaly);
a longwave-scheme / optical-depth arm to prove the radiation attribution (tunes the atmosphere); runoff routing;
all 0.5° cells per column; T63.

**2026-10-16 — COUPLED: the learned emulator runs inside SpeedyWeather, day by day (ADR 0345).** Package:
`begin_year` / `step_day` / `end_year` (`step_year` = their loop, bit-identical). Coupler
`scripts/online_coupling/run_speedy_landemu.jl` (+ `landemu_coupler.py`, `score_speedy_landemu.py`,
`sbatch_speedy_landemu.sh`; env `/p/tmp/jamirp/esm_online_coupling_sw023` with PythonCall; skill
`online-coupling-env`): SpeedyWeather 0.23 T31 L8, each land column = nearest 0.5° cell of the global nitrogen-off
emulator (1 197 of 1 363), start 2015 from the global run's end-of-2014 state; daily mean weather in, the day's ET
out as the next day's land moisture flux (`DIURNAL=flat|sun`). 10-yr runs (coupled flat, coupled sun, control):
offline replay identical; water closes to the leap days (+0.082 %); land ET 409 → 601 mm/yr, land rain 716 → 828,
land temperature unchanged (10.50 vs 10.55 °C); emulator 8.8 s per simulated year = 7 % of the run.
⚠ SpeedyWeather's land is 6.7 °C colder and 10 % drier than GFDL-ESM4 1985–2014 (control run, not the coupling); the
emulator reads it as climate change (vegetation carbon −6 % at year 10 and falling, NPP ×1.32, soil evaporation ×1.9,
runoff ×0.57 vs the same cells offline). Data `esm_land_emulator_data/coupled/`.
**Next (owner to choose):** anomaly coupling (observed climatology + SpeedyWeather's anomaly) so the bias does not
act as climate change; more coupled channels (albedo / roughness from leaf area and cover, runoff to rivers, snow);
all 0.5° cells per column (~54× the emulator time ≈ 4× the atmosphere); a T63 run; the nitrogen-on CO2 release
(needs setups beyond 674 cells).

**2026-10-15 (night) — DEPLOYED: the nitrogen-on emulator with a CO2 input (ADR 0344).** The package takes
`step_year(..., co2=ppm)`; releases `release/non_v1` (deployment: all 10 climate models, all 674 cells) and
`release/non_fold_v1` (validated set-up; reproduces the scored maps bit-identically and the daily fluxes to 1e-7 on
a held-out climate model). 7.3e-3 core-s per cell-year ≈ 115–130× fewer than the original on the same cells.
Build/run: `scripts/build_emulator_release_non.py`, `scripts/run_emulator_non.py` (skill `emulator-release`).
Limits: setups for the 674 representative cells only; capacity fixed at 2019; not coupled.
**Next (owner to choose):** coupling to SpeedyWeather via `step_year` (goal #3); a full-grid nitrogen-on training
run (removes the unseen-cell limit, ADR 0343, and gives setups for every cell); the damping of the largest losses.

**2026-10-15 (evening) — why the emulated stand responds too evenly on unseen cells (ADR 0343): sample size.**
On cells it trained on, the stand map follows the original's leaf-area / tree-cover response nearly as well under
an unseen climate model as a seen one; on the 20 % held-out cells its error is 1.82× / 2.20× a second run's.
Four one-change arms (larger leaves, no coordinates, the cell's own historical sensitivity, its own 1990–2019
trend) all null (±5 %). Learning curve 135 → 269 → 539 training cells: error falls ~6–12 % per doubling, so
the clustered design (674 regions) is the limit; a full-grid training set (as ADR 0341) never meets an unseen
cell. Scripts: `clu_emu_maps.py` arms `m2_*`, `summarize_clu_arms.py`.
**Next (owner to choose):** repeat the warming-response proof with training on many more cells (full-grid
nitrogen-on run, or the distributed 1-patch clustering); the damping of the largest warming losses (ADR 0342 §8);
or deploy (CO2 input in the `landemu` package does not exist yet).

**2026-10-15 — warming-response proof on clustered nitrogen-on runs: DONE, not passed as pre-registered (ADR 0342
§7–8).** Original = merged LPJmL-FIT nitrogen on, transient CO2, 674 cells × 25 patches; 10 climate models × 3 SSPs
+ CO2-fixed twins; held out MPI-ESM1-2-HR + IPSL-CM6A-LR and 20 % of cells; seed 3 = second run (skill
`response-proof-clustered`). Findings: warm-trained maps get 0.79–0.98 of the original's vegetation-carbon change
(second run 0.61–0.89), ssp126-only maps 0.37–0.43 (Billing failure reproduced); per cell as close as a second run.
Daily model with the original's stand: GPP change ±4 %, slope 0.92–0.99. Misses: emulated leaf area / cover respond
too uniformly across cells (slope 0.73–0.83 vs 0.89–0.96) → GPP slope 0.66–0.79; warming-only (CO2-fixed) IPSL
vegetation-carbon LOSS 0.72 of the original's even with CO2-fixed twins in training (arm `main2`; was 0.57–0.67).
The slope ≥ 0.8 criterion is failed by the original's own second run (regression dilution) — fix the criterion.
**Next (owner to choose):** stand map per-cell response; the damping of the largest losses; or deploy (CO2 input in
the `landemu` package does not exist yet).

**Earlier on 2026-10-15: the emulator now runs GLOBALLY (ADR 0341).** Retrained (structure + stand maps) on Billing's Oct-2026
GFDL-ESM4 r1_1 runs, anchored on each cell's own 1985–2014 state, leave-one-scenario-out; run on all 64 240 land cells
(1985–2014 + three futures to 2100, 7.65e-3 core-s per cell-year); benchmarked with the lpjml-fit ILAMB + lpjmlstats
tools on the full grid (`scripts/glob_emu.py`, `scripts/glob_emu_bench.sh`; data `esm_land_emulator_data/global_emu/`).
Headlines: ILAMB within ±0.03 of the original on all 27 datasets; historical GPP total right but the CO2-driven trend
missing; transpiration −8.5 % / runoff +5.8 % (daily model not retrained — the runs write no daily output); unseen
futures beat "1985–2014 state carried forward" everywhere; ssp370 misses two thirds of the vegetation-carbon loss.
Open from it: (a) Billing's next runs need the outputs listed in ADR 0341 / the owner message of 2026-10-15
(yearly `ind`, `lai_stand` every year, `whc_nat`, daily fluxes, a second member) — then retrain the daily model on
them; (b) top-metre capacity could be recomputed from texture + `soilc_layer` instead of another run's `whc_nat`.
⚠ The futures' `output_transient` 2071–2100 is NOT a second run (identical on ~92 % of cells).

**Release v1 is done (ADR 0340).** What remains is a choice among its §5 misses — ask the owner which, do not start
another open-ended arm:
1. **Coupling to SpeedyWeather** (goal #3; nothing exists in the package). The package's `step_year` is the call an
   ESM would make; the coupler needs daily ET/runoff/snow back to the atmosphere and the energy closure (ADR
   0073–0085), and forcing per land column.
2. ~~A global release~~ — done with a historical-state anchor (ADR 0341); the per-year anchor of release v1 remains
   panel-only.
3. **Daily NPP / ET / runoff and the climate response** (ADR 0340 §4.2): the stand's plant-type cover carries most of
   the added error (ADR 0338); two loss re-weightings did nothing (ADR 0339).
4. **Speed:** a GPU or batched numpy daily step; the daily model is 97 % of the cost.
Owner questions still open: the relaxed numbers (ADR 0318 §2), the daily numbers (ADR 0325 §3; runoff is a residual),
dense cells defined by the anchor (ADR 0329 — the fair reading) rather than the held-out run, removal of `wt-*`.
⚠ Known: panel forcing is 0.1 °C-quantised and the training table counted exactly-30.0 °C days as hot (float32 scale);
the package does not (ADR 0340 §3) — harmless for continuous forcing.
