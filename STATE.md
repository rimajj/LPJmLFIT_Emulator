# STATE — the single current state and handoff (one development stream, ADR 0319)

> The `## NEXT — start here` block is what the SessionStart hook replays. **Refresh it before a session ends.**
> Narrative → `JOURNAL.md` (append). Durable cross-cutting facts → `MEMORY.md`. Decisions → next free ADR number
> (**0369**). History of the retired parallel lines: `lines/{S,M,E,O,X}/STATE.md` + `JOURNAL.md` (read-only).

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

**2026-10-23 — owner "n1": soil texture in the daily model + mortality re-score (ADR 0367): neither adopted.**
* Package `landemu` now accepts an optional soil-texture table in `daily.npz` (texture-free releases unchanged, gated
  bit for bit). `scripts/build_release_daily_swap.py` copies a release with only its daily networks replaced → built
  `v2tex`, `fold_<g>_v3tex` (5 models) with ADR 0348's texture networks; all gates pass.
* **Complete emulator (emulated stand), two seed pairs:** NPP error 0.884 / 0.844 of the release's (all 28 leg-windows
  better in both — the whole gain survives, unlike ADR 0362), ET 0.96/0.97, runoff 0.97/0.91, cost unchanged. Fails
  the pre-registered rule: hottest leg (IPSL ssp585, late) gets worse in both pairs — ET drift +0.10 in pair b (limit
  0.08), GPP 1.13/1.15 — and pair a's GPP median sits on the 1.05 limit. Release stays `v4`.
* **Mortality `BCET`** (165 emulator run-legs, 5 fits): capture 0.433 vs `BCE` 0.430, 30-yr rate 1.517 vs 1.517, anomaly
  correlation +0.002. Texture fixes each cell's NPP LEVEL; the die-off inputs are anomalies, where a level cancels.
**Next (owner to choose):** (q1) measure capture with a PERFECT stand-level NPP (the original's stand NPP fed as `BCE`'s
inputs; ~1 h, no emulator runs) — decides whether any daily model can reach the 0.5 bar on this route; (q2) if yes,
aim the daily model at the yearly NPP anomaly (score it by the anomaly correlation, now 0.63) instead of its 30-yr
error; (q3) ship texture anyway for its NPP gain, accepting the hot-leg drift (owner's call); (n2)/(n3) of the block
below still open.
Note: other jobs under the account (`emu-clu-*`, `xtf-*`) were running at the same time — not this session's.

**2026-10-23 (morning) — owner: transformer experiments, SEPARATE, NOTHING INTO THE PAPER (ADR 0368).** Owner also:
*"for now we should only judge how well the emulator reproduces the clustered runs it was trained on"* (held-out cells
of those runs, training-cell fit beside it) and *"produce more data if you need it, just dont do full grid runs"*.
* **New data:** 24 seed-3 legs (rising CO2) of the clustered nitrogen-on runs for the 8 climate models that had none
  (all 30 terminated cleanly) + their f2 arrays (`clu_emu_f2.py build --seed 3`, done) ⇒ a second run exists for all
  10 climate models × 3 scenarios.
* **Exp 1 (daily memory), `scripts/xtf_daily.py`, data `esm_land_emulator_data/xtf/daily/`:** arms B (NC_s0–4 as
  is), TC (transformer, no memory), TW (transformer over the past 364 days of raw weather), 3 seeds each. Jobs:
  packed 4-GPU `xtf-dtrain` 2672360 → `xtf-drunT` 2672362; `xtf-drunB` 2672361; score `xtf-d-score` 2672365
  (`score.md`-style table in the log, decision printed); one-core cost `xtf-d-bench` 2672368. Per-GPU logs
  `logs/xtf-<tag>.gpu<i>.<jobid>.out`.
* **Exp 2 (set transformer for tree deaths), `scripts/xtf_tree_pairs.py` + `xtf_tree_models.py`, data
  `xtf/trees/` + `xtf/treemort/`:** tables array 2672319 (60 legs) → P0 2672330, P1 2672331 (CPU), ST ×3 packed
  2672363 → score 2672364. Two corrections found before any fit (ADR 0368 §2a): no whole-patch losses (my check's
  2101 artefact); the merged model's `mort` already includes fire ⇒ oracle = min(1, mort).
* GPU gotcha: `gpushort` allows 2 running jobs per user ⇒ pack (one job, 4 GPUs, one process each; `pack()` in the
  shell history of this session = the `logs/xtf-*.jcf` files are the template).
**RESULTS (ADR 0368 §7):** exp 1 — weather memory HELPS: the transformer over the past year cuts the daily errors
20–30 % vs the no-memory transformer and the deployed network (held-out cells × held-out models, single-year GPP 1.01 /
NPP 1.31 / ET 1.18 / runoff 6.95 × a second run, vs B 1.30 / 1.82 / 1.71 / 8.28), no drift; but it costs 0.45 core-s
per cell-year (350× B, slower than the original) ⇒ not a candidate. Exp 2 — per-tree neural net beats LightGBM (skill
0.44 → 0.50), seeing the patch adds +0.03 (0.53); die-off capture 0.24; + the year's carbon from the emulator 0.27,
from the original 0.35, the tree's own NPP 0.46, ceiling 0.70 ⇒ the lever is the daily NPP + a per-tree carbon state.
**Next (owner to choose):** (x1) carry the weather memory cheaply in the deployed daily network (more or learned
running means / a small recurrent state; new record) and re-score NPP + die-off capture with it; (x2) the per-tree
leaf-carbon / bad-year state (the parked "c2" candidate); (x3) stop here.

**2026-10-22 (night) — owner "do both" (m1 + p1): emulated NPP into the per-tree mortality model (ADR 0366, NOT
adopted); population outputs written into the paper.**
* **(m1)** Weather arrays for the 17 legs without them (`build_emulator_forcing.py`, f2/forc_leg/), v2 start files for
  runs m5/m6 (`run_emulator_npp.py setups`; fields m5/m6 never wrote = the m1–m4 mean), fold releases
  `fold_{ipsl-cm6a-lr,mpi-esm1-2-hr,mri-esm2-0,ukesm1-0-ll}_v3` (same build as fold_gfdl-esm4_v3), 165 emulator
  run-legs (35.5 core-h) → `xpanel/eval/treemort/enpp/enpp.parquet`. Every gate bit-exact. Arm `BCE` (virtual trees):
  die-off capture **0.43** (BC 0.36, bound with the original's NPP 0.74; clean cells 0.44 → 0.54), outright-kill capture
  0.45 → 0.61, 30-yr death rate 1.52 (bar 1.2) ⇒ not adopted; no mortality output. Emulated vs original NPP anomaly
  r = 0.60–0.66. Reading: the route works; its limit is the emulated NPP's accuracy; no arm reaches the 30-yr level.
* **(p1)** Paper Sect. 4.5 (population method), 6.4 + Fig. `fig_population`, abstract/table/limitations/conclusions,
  die-off section corrected to ADR 0364 and given the mortality results incl. ADR 0366. 33 pp., builds clean.
**Next (owner to choose):** (n1) improve the daily model's NPP (the lever for mortality: soil texture as input
gave NPP −13…−16 %, ADR 0348, not in the release) and re-score `BCE` with it; (n2) accept no mortality output;
(n3) the 30-yr death-rate level (1.5× everywhere) needs its own diagnosis — which hazard is off late in the century.

**2026-10-22 (late evening) — owner "do a-c, all of it": tree population SHIPPED (release v4 / fold v5, ADR 0365);
per-tree mortality NOT adopted (ADR 0364); evenness fixed (ADR 0363 §12).**
* **(a) Release `v4`** = v2 + 79 population models (9-level distributions of height, biomass per tree, the four traits,
  ACTUAL rooting depth, age; 7 type shares) + virtual trees + diversity indices on request
  (`LandEmulator.start(setup, PopSetup)`, outputs `pop_*`). Additive: v2 files byte-identical, all 20 existing outputs
  identical with the population on, v2 with the new code == v4 without it. Cost +7 % (7.67e-3 vs 7.14e-3 core-s per
  cell-year); virtual trees + indices 6.7e-3 each time. `fold_gfdl-esm4_v5` reproduces the scored pipeline from daily
  weather except Age (its LightGBM fit is not reproducible run to run — two refits differ as much) and the known
  larch/hot-day artefact; functional richness's 99th pct 0.058 (limit 0.05).
* **(c)** Computed biomass per tree (allometry, ~1 % per tree in the original) 0.95 vs learned 0.86 ⇒ learned ships
  (5 % inconsistency documented). Evenness bias = repeated donor trees; no-repeat draw ⇒ evenness 3.32 → 1.82 (no
  bias left), richness 1.28 → 1.06.
* **(b)** Per-tree model (leaf carbon vs sapling threshold + bad-years counter + hazard, applied to virtual trees):
  yearly rate 0.97 ✓, totals 15/15 ✓, 30-yr rate 1.51 ✗ (bar 1.2), die-off capture 0.36 ✗ (bar 0.5; cell map 0.28).
  With the run's own NPP 0.74 ⇒ the carbon signal is the lever. Not shipped; no mortality output.
* **Corrections found:** the `ind` `mort` column already holds the hard kills (ADR 0363's "excess deaths" = fire /
  isneg / luck); tree identity = (Cell, Patch, Type, ID) + SLA; for trees ≥ 5 m outside die-offs most hard kills are
  the bad-years counter (ADR 0357 mixed heights). In CLAUDE.md.
**Next (owner to choose):** (m1) mortality with the emulator's OWN NPP (build forcing for the 5 newer climate models
+ setups for runs m5/m6, run the full emulator on 135 training run-legs ~25 core-h, retrain the per-tree model; bound
0.74); (m2) accept no mortality output for now; (p1) make the population outputs part of the paper (Sect. 4/5:
distributions + indices, with the "second-run bar has little power" caveat); open threads below.

**2026-10-22 (evening) — whole-tree-population emulation scored (ADR 0363 §9–11).** Owner: "the emulator runs finished".
* **Distributions** (9 quantile levels, one model each, `AQ`): every variable passes in dense cells — height 0.86,
  biomass/tree 0.85, the four traits 0.60–0.80, actual rooting depth 0.76, age 0.87 of a second run's error. Caveat:
  the anchor alone already scores 0.83–1.01, so this bar has little power.
* **Rooting depth:** learned (0.78) beats computing it from `D95max` + emulated height (1.09) ⇒ learned ships.
* **Virtual trees / diversity indices** (donor = the run's own 2019 roster): all barred indices pass (richness 1.28,
  dispersion 0.71, Rao's Q 0.72, CWMs/CWVs ≤ 0.81); **functional evenness 3.3× (a 4 % bias, 0.79 vs 0.82), undiagnosed**.
* **Mortality:** with weather (`BMW`) yearly rate and totals pass; 30-year rate 1.32 (bar 1.2) and die-off capture
  0.28 / 0.43 (bar 0.5) fail. Oracle with the original's own NPP (`BMN`): death-rate capture 0.59 but excess
  (hard-kill) capture unchanged at 0.42 ⇒ per the pre-registered reading, the cohort leaf-carbon model `BC` is next.
* **Owner question (compute vs learn related quantities):** biomass per tree is a power law of height, wood density
  and SLA to 0.6–1.9 % per tree ⇒ candidate: compute it per virtual tree instead of learning it (§11). Not tested.
* Nothing added to the release package yet. Outputs: `xpanel/eval/popmap/` (score_popmap.csv).
**Next (owner to choose):** (a) package the passing parts (distributions, learned rooting depth, virtual trees +
indices) as new outputs of the release (additive); (b) pre-register + build `BC`; (c) compare computed vs learned
biomass per tree (and the evenness bias); (d) open threads below.

**2026-10-22 (afternoon) — daily-network design check finished; four-layer networks NOT shipped (owner, ADR 0362).**
Owner: "all emulator runs finished", then "ok lets do it that way" (stay on v2).
* Stage 2 (networks fed the original's stand): 4 × 256 passed ADR 0359's rule (GPP −6…−8 %, NPP −6…−13 %, runoff
  −10…−17 %, ET −1…−6 %); batch 4 096 failed; no trailing windows 1.2–1.6× worse.
* Built anyway: `release/v3` + `fold_gfdl-esm4_v4` (`--daily-members DCL4_3x256_seed`), gated, fold reproduces
  `PD_L4_fx`. In the complete emulator (emulated stand) the gain is mostly gone (NPP −6 %, runoff −3 %, GPP/ET
  unchanged) at 9.8e-3 vs 7.0e-3 core-s per cell-year ⇒ **current releases stay `v2` / `fold_gfdl-esm4_v3`**.
  Re-open if the carbon cycle is coupled or the emulated stand improves.
* Paper Sect. 4.6 daily paragraph + Table `tab:choices_daily` done; the ADR 0359 campaign is fully written up.
**Next:** the design-choice work is closed. Open threads: SpeedyWeather coupling (t1–t3 above, s2/s3 below).

**2026-10-22 (midday) — SpeedyWeather: emulator coupling PAUSED (owner), every finding reported upstream.** Owner: *"I do
not want to do any coupling with the emulator as long as the climate model does not work correctly yet. All solutions
and valuable tests for the speedyweather developers should be reported as issues."* ⇒ the coupled follow-ups (t1)–(t3)
in the block below are **off** until the owner says the atmosphere is good enough; stand-alone SpeedyWeather work is
allowed. Filed as rimajj: #1342 (four-band longwave, source in the issue), #1343 (near-surface air in inversions + 2 m
diagnostic), #1344 (no clear-sky Rayleigh scattering), #1345 (clear-sky OLR at L8 vs L32; slab drift); follow-up comments
on #1333 (stage table of the open PRs) and #1339 (three more convection tests). Texts in `patches/speedyweather/`.
Nothing upstream has replied yet. **Next there:** watch the six threads; answer questions; open PRs only when a
maintainer asks (no fork exists yet). Still open on the atmosphere: high-latitude lower troposphere warm (+3–8 K in
winter at 650–890 hPa), slab drift +0.35 K/yr, cloud/clear-sky split. Terrarium default-setting traps (sand soil,
NoFlow hydrology, VPD = 0 assertion) are NOT reported — they belong to Terrarium's repository; ask the owner.

**2026-10-22 (morning) — the coupled emulator now runs on the fixed SpeedyWeather atmosphere; the 2 m air feed was
NOT adopted (ADR 0360).** Owner: "continue" (s1 below). `run_speedy_landemu.jl` + `PROJ=/p/tmp/jamirp/speedy_landemu_fix_env`
with `LW=fourband T0=speedy CONVKW="ascent_substeps=10,entrainment_mse=1"` (skill online-coupling-env). 10-yr runs,
prescribed SST: coupled land +1.4 K vs W5E5 (stock −7.7 K); `AIR=2m` fixes the high-latitude winter (+14.7 → +4.3 K) but
makes the tropics 2.1 K too cold — the emulator's evaporation cools the ground to the air temperature, so the formula's
stable branch pulls the 2 m value down; the formula has no displacement height for the emulator's forest roughness.
Also: coupled precipitation +182 mm/yr too wet; vegetation carbon still −2.8 % in 10 yr; 225 core-s per simulated year.
**Next there, if pursued:** (t1) separate the two causes with one run `AIR=2m ROUGH=speedy` (~40 min); (t2) a 2 m
formula with a displacement height, applied only at night-time stable steps (pre-register); (t3) why the coupled
fixed atmosphere rains 180 mm/yr too much and why vegetation carbon falls (NPP 64–70 vs 81–84 PgC/yr stock);
(s2)/(s3) below unchanged.

**2026-10-22 (night, 2) — design-choice campaign (ADR 0359): forest map DONE, daily stage 2 RUNNING.** Owner: "all
emulator runs are done".
* **Forest map + departure model (22 arms):** no alternative beats the release ⇒ no setting changes, no rebuild. Plateau:
  fewer leaves/trees/lower rate 2.6–3.0 % worse on dense biomass per tree; more capacity 1.4–3.1 % better on dense tree
  count but misses the biomass bar (L63 0.982 vs 0.98, every quantity ≤ 1.004). Every input group needed (no climate
  offset: biomass +11 %, sparse count +14 %; no start state: trait medians +13–41 %). Departure settings all equivalent.
  Results in ADR 0359 §4; paper Sect. 4.6 map paragraph + Table `tab:choices_map` written, PDF rebuilt.
* **Daily screen:** L4 0.957, B4K 0.960 of BASE loss; E20/H512 −2.4…−2.7 % but under two seed sds. **Deviation recorded
  before results (ADR 0359 §5):** pooled seed sd excludes the diverged LR10 (0.0207 → 0.00078; summariser fixed).
* **Stage 2 queued (gpu):** `DCL4E_5seed` (2661152), `DCB4KE_5seed` (2661159), `DCNOWINE_5seed` (2661165, report only);
  chained scorer 2661168 (`afterany`) → `logs/f2-dc-stage2-relscore.md` + compare blocks in its .out.
* **Combined forest-map capacity arm (ADR 0361): NOT ADOPTED.** 63 leaves + 800 rounds: dense count 0.970, biomass/tree
  0.952 of the release, but a sparse trait pair at 1.022 and drift +0.04 (the gain is ~4 % early, ~1 % late; with the
  departure model 0.986 / 0.961). Paper table row + sentence added. Release keeps 31 / 400.
**Next:** read the scorer output; adopt L4 / B4K only if it beats BOTH `DE_5seed` and `D2E_5seed` by ≥ 5 % on ≥ 2 of
GPP/ET/NPP/runoff, none worse > 5 %, cost within T31 (release 6.4e-3 core-s per cell-year; L4 adds a layer). Then write
ADR 0359 §6, replace the paper's "[Daily networks: to be completed …]" marker (one paragraph + screen table), rebuild
(`scripts/paper/make_all.sh` or latexmk). If adopted: rebuild the release (new ADR). Optional, needs pre-registration:
combined map capacity arm (63 leaves + 800 rounds).

**2026-10-22 (late night) — SpeedyWeather side track: convection reported upstream (#1339), clouds measured, winter
split.** Owner: "yes, do all that" (clouds, high-latitude winter, upstream report). Branch coldfix-E 6ae14204 (patch
refreshed). JOURNAL 2026-10-22 (night) has every number.
* **Convection:** most of the warm parcel was the layer in which it saturates (ascended moist from its bottom); fixed on
  the branch (sub-steps rise dry to the saturating sub-step). New base E3ent50 = `ascent_substeps=10, entrainment_mse=1`
  (default entrainment depth): tropical 308/431/555 hPa −1.8/+0.1/+0.6 K prescribed, +1.8/+2.7/+2.1 K slab. Reported
  upstream with a stand-alone parcel check: SpeedyWeather #1339.
* **Clouds:** vs CERES the clouds reflect ~33 W/m² too much and the clear sky ~20 too little (no Rayleigh in
  SpeedyWeather; new opt-in `rayleigh_fraction`). Clear-sky OLR ~12 W/m² low in every arm, NOT the longwave code (8 vs
  32 layers costs 6–9 W/m²; the four-band code at L8 ≈ ecCKD at L32) ⇒ the budget cannot close through clouds. No cloud
  setting passed the pre-registered rule (R5 = Rayleigh 0.5 + albedos ×0.75 fixes the split but worsens budget and land
  sunshine). Defaults unchanged. R5 on the free ocean (5 yr) confirms it: ~1 K warmer than the base by year 5, net
  TOA +3.5 vs +2.2 W/m², tropical upper troposphere back to +3–4 K. All side-track runs are scored; none pending.
* **High-latitude winter:** of the +13 K coldest-month bias, two thirds is the definition (SpeedyWeather reports the
  lowermost layer as near-surface air in an inversion); a diagnostic 2 m air temperature (reproducer) gives +3.5 K vs
  GFDL-ESM4, land annual +1.1 K. Stronger stable mixing fails. Remaining: a warm high-latitude lower troposphere.
**Next there, if pursued:** (s1) feed the emulator a 2 m air temperature in `run_speedy_landemu.jl` (same formula as
`air_2m` in the reproducer) — the biggest gain for the coupling; (s2) the slab drift (+0.35 K/yr): it needs either more
vertical layers (L16, cost ×2) or an explicit clear-sky OLR compensation; (s3) wait for #1339's reply before a PR.

**2026-10-22 (night) — departure model SHIPPED (release v2 / fold v3, ADR 0358), paper REWRITTEN, design-choice
campaign RUNNING (ADR 0359).** Owner: "c1" (ship), remember c2/c3 as future candidates (memory
`dieoff-future-candidates`), rewrite the paper without the earlier hybrid design, without citing the unpublished review,
performance only (no pass/fail; memory `paper-no-pass-fail`), and justify every architecture / size choice with
experiments.
* **Release:** `release/v2` (deployment) and `release/fold_gfdl-esm4_v3` (`build_emulator_release.py --departure dep`);
  gate (4) z-scores 3.7e-11; `--check` reproduces `preds_gfdl-esm4_statedep_fx` (tree count median 2.3e-4); 7.0e-3
  core-s per cell-year. Shipping trade-off: dense tree count 1.26 → 1.22×, die-off share 3 → 18 %, but dense stem total
  −0.2 → −2.6 %, sparse biomass per tree 1.47 → 1.55×.
* **Paper** (`docs/paper/main.tex`, 29 pp., builds clean): new literature introduction; Sect. 4.6 "Choice of
  architecture and settings" holds the already-measured evidence and a **[To be completed]** marker for ADR 0359.
* **ADR 0359 campaign (73 jobs):** `scripts/run_design_sensitivity.sh` (map arms moved to `priority` at 16 cpus;
  daily screen on `gpu`). Read with `python scripts/summarise_design_sensitivity.py [daily|map]`; then apply ADR 0359's
  reading, run stage-2 ensembles if any daily arm qualifies (`f2_chain_arm.py`), rebuild the release if a map setting
  is better, write ADR 0359's results, fill Sect. 4.6 of the paper, rebuild the PDF (`scripts/paper/make_all.sh`).
  First result: without the precipitation windows the daily validation loss rises ~55 %.

**2026-10-21 (late night, 4) — what kills the trees in a drought die-off: the leaf-carbon threshold (ADR 0357).**
Owner: "continue as recommended" (b5).
* Leaf carbon per tree rebuilt exactly from the tree table: 95–98 % of hard-killed trees had less leaf carbon than a
  sapling (median 0.58 of it in the die-off year), 0 % of chance deaths ⇒ the original's "ghost tree" rule, not the
  five-bad-years counter. (The check's self-test flagged 10–14 % of survivors below the line — all of them the year's
  new saplings sitting exactly at it; 2 of 33.6 M older trees.)
* Last year's share of trees close to the threshold does NOT predict die-off years (AUC ~0.5) ⇒ the planned
  vulnerability arm was not run. Best single yearly signal is the original's own NPP crash (AUC 0.90); the bucket the
  emulator already computes gets 0.88.
* Reading: a die-off is a per-tree threshold crossed by a one-year carbon crash; stand-level inputs top out near what
  the departure model already has (a quarter of the drop). More needs a per-tree/cohort leaf-carbon quantity in the
  emulator.
**Next (owner to choose):** (c1) close the die-off line and ship the departure model for its general gain — `dep`
(20 of 22, everything else passes) or `depv` (20 of 22, die-off share 25 %, sparse biomass per tree +4.9 %); (c2) a
cohort sub-model that tracks the trees' leaf carbon against their threshold and moves it with the emulated yearly NPP
(a real new component; pre-register before building); (c3) the emulated NPP anomaly as departure input (expected small:
0.90 vs 0.88; needs the daily networks run on the 27 training legs); or (d)/(e) further below.

**2026-10-21 (late night, 3) — forest map: runs of bad years as vulnerability input (ADR 0356), not adopted; and
what the die-offs actually are.** Owner: "continue with b3".
* In the original, a dry year's tree-count drop does NOT deepen when it follows other bad years (−0.4 % in every bin,
  tail flat too) ⇒ arm `depv` (weather runs of bad years) ≈ `depw` (capture 0.25, gap 3.47×, 20 of 22, sparse biomass
  per tree 4.9 % worse than `fix`); `depvs` (+ the forest's own history) worse, and its start cut grows (1.14).
* **Post-hoc findings (ADR 0356 §7):** even the driest years (z < −2) cause a ≥ 15 % drop in only 7 % of dense
  cell-years; **not fire** (deaths in die-off years equal the trees' own death probability, 0.342 vs 0.343; the live
  fire path is per tree, `fire_tree_ind`); die-off years are mostly **hard kills** — 23 % of trees vs 11 % normally,
  with the hazards below 1: leaf carbon below a sapling's ("ghost tree fix") or 5 bad years in a row. The flat
  run-length result points to the leaf-carbon threshold, a one-year per-tree trigger — not measured yet.
**Next (owner to choose):** (b5) confirm which hard kill (rebuild each dying tree's leaf carbon from the tree table vs
its sapling threshold, no new run) and, if it is the leaf threshold, give the departure model the share of trees
close to it (needs a within-stand leaf-carbon statistic the emulator does not carry yet); (b2) ship `dep` (20 of 22,
capture 0.18) or `depv` (20 of 22, capture 0.25, but sparse biomass per tree +4.9 %) for the general gain; (d)/(e)
below.

**2026-10-21 (late night, 2) — forest map: a daily soil-water stress input for the departure model (ADR 0355), not
adopted.** Owner: "continue with b1". A forcing-only daily top-metre bucket (`scripts/build_panel_bucket_stress.py`,
data `xpanel/climate_bucket/`; evaporation rate 3 mm/day chosen on observed weather only) gives six yearly stress
statistics on the original's own stress window; arm `depw` = ADR 0354's `dep` + these.
* Die-off capture **0.18 → 0.25**, aftermath gap **3.75× → 3.50×** (best of every arm; bars 0.30 / 2.0×). Drift,
  late level, start-cut test pass. But sparse biomass per tree 2.5 % worse than `fix` (bar 2 %) and the sparse
  tree-count criterion drops to 10 of 15 cases (needs 12) although its median is the best yet (2.71) ⇒ 19 of 22.
* The bucket's daily soil water tracks the original's at 0.69, but its VPD-weighted stress integral follows the
  original's year to year at only 0.30 (pre-registered: read as a crude index). What singles out die-off years best is
  the bucket's actual/potential evaporation (AUC 0.87 vs the yearly water balance's 0.81).
* Still open from ADR 0354: the recovery after a start cut overshoots (+50 % of the cut above the uncut run in 2050).
**Next (owner to choose):** (b3) the stand's own vulnerability as departure input (consecutive bad years — the
original's counter multiplies every hazard and kills at 5); (b4) the emulator's own learned daily soil water instead
of the bucket (needs its daily networks run on the 27 training legs); (b2) ship `dep` (20 of 22) for its general
gain; or (d)/(e) from the blocks below.

**2026-10-21 (late night) — forest map: a weather-driven departure model for drought die-offs (ADR 0354), not
adopted on its target, but a general gain.** Owner: "continue with the emulator" ⇒ option (b) of the block below.
The leak-free map stays the level; a second small model per quantity learns the forest's year-to-year departure from
that level (tree count, biomass per tree) from this and last year's weather anomaly, run forward year by year
(`explore_panel_yearly_drift.py fit --state dep`; null `depnw` without weather).
* Drop capture of the original's drought die-offs **0.03 → 0.18** (bar 0.30; the null stays 0.03), 10-year aftermath
  gap **4.5× → 3.75×** a second run's (bar 2.0×). The year's 25 annual climate statistics explain about a quarter of a
  die-off the original's other runs reproduce at 94 %.
* Everything else passes: **20 of 22 criteria** (from 18; + dense tree count worst 10 %, + sparse tree count typical),
  nothing lost, drift 1.20 / 1.41 (unchanged), late tree-count level ×0.97. After a 30 % start cut the recovery
  overshoots (+40–47 % of the cut above the uncut run in 2040–2060, fading).
**Next (owner to choose):** (b1) a daily-resolved stress input for the departure model (the year's water-stress
integral on the original's own calendar — the record's pre-registered next candidate); (b2) ship `dep` for its general
gain (two numbers per cell carried year to year) — or `fx10`, smaller (19 of 22); (d)/(e) from the block below.

**2026-10-21 (night) — SpeedyWeather cold-bias side track: the warm, moist tropical upper troposphere was the
convection scheme, now fixed (opt-in); the remaining errors are clouds and high-latitude winter.** Owner: "continue
the speedy wheater fix". Reference built from GFDL-ESM4 1985–2014 profiles (`build_speedy_profile_reference.py`,
reproducer env `PROFREF`). Two defects in SpeedyWeather's Betts–Miller convection found with
`speedy_convection_diag.jl`: one coarse step per layer for the rising parcel (too warm aloft) and mixing that never
lets dry outside air cool the parcel. Both are new default-off options on branch coldfix-E (684c181c,
`patches/speedyweather/`): `BettsMillerConvection(ascent_substeps = 10, entrainment_mse = true)` + `σ_entrainment = 0`.
With them the tropical 300–550 hPa profile is within 1.5 K of GFDL-ESM4 (was +4…+9 K) and column water vapour right
(40.5 vs 40.3) on both ocean modes; tropical ocean evaporation 88 → 126 W/m². NOT fixed: free-ocean drift (+0.2 K/yr
at year 5, TOA +1.9 W/m²), land rain −300 mm/yr on the slab, high-latitude land winters +15 K, too-reflective clouds
(reflected SW 113, OLR 226 W/m²). Lowering the convection's target humidity: dries, does not cool — not adopted.
JOURNAL 2026-10-21 (night). **Next there, if pursued:** clouds (DiagnosticClouds cover/top and their SW/LW
optical properties, scored on reflected SW + OLR + cloud cover vs GFDL-ESM4 `clt`), then the high-latitude winter
inversion; upstream: report the two convection defects (search the SpeedyWeather issues first).

**2026-10-21 (late) — SpeedyWeather cold-bias side track: retuning its longwave to a reference radiation code makes it WORSE** (TOA imbalance +6 → +10/+15 W/m², slab ocean runs away +1.6–2.4 K/yr); the four-band longwave was already close to the reference on clear sky. Remaining error is the model atmosphere (tropical upper troposphere too moist and too warm) + clouds. JOURNAL 2026-10-21 (late). Next there, if pursued: humidity/convection, not radiation.

**2026-10-21 (night) — the leak-free restatement is done (ADR 0353), and the two daily-network arms are closed
(ADR 0348 §4).** Owner: "continue in the recommended way" ⇒ option (a) below.
* **Restated (leak-free; quote these, not ADR 0340 §4.1–4.3):** structure **18 of 22** criteria (was 21): dense tree
  count 1.26× and biomass per tree 1.18× a second run (both now fail the 1.2 limit), dense worst-10 % tree count 1.47
  (10/15 ✗), sparse tree count 3.00 (7/15 ✗); drift mid → late ×1.06 / ×1.05 (pre-registered rule 1.22 / 1.41, fails);
  stand map leaf area 1.45×, vegetation carbon 1.31× (+5–6 %); plant-type cover untouched (the leaked run never had
  it); **the whole emulator's daily fluxes within 1 % of before** (`PD_B_fx`: GPP 2.36, NPP 3.94, ET 3.09, runoff 5.22;
  ET typical 5 → 4 of 13 legs). Validated fold release is now **`release/fold_gfdl-esm4_v2`** (check equals v1's).
  `release/v1` (deployment) unchanged. Paper text + figure scripts updated (`docs/paper/README.md` notes it).
* **Soil texture into the daily networks: not adopted** (ET 0.99 in both seed pairs, bar 0.95; runoff 0.95 / 0.89).
  Unexpected: NPP 13–16 % better in both pairs with GPP unchanged — a follow-up needs its own pre-registration.
* **Ensemble size: five stays.** Three networks lose 10–11 % on ET/runoff in one replicate; ten gain 2–13 % on water
  and NPP at twice the cost (1.28e-2 core-s per cell-year, at the T31 allowance) but fail GPP ≤ 1.00 against one of
  the two five-network ensembles.
**Next (owner to choose):** (b) a die-off model of the one-year tree-count change from the year's drought anomaly +
the stand (the forest map's biggest known miss, ADR 0352 §6.3); (c) ship `fx10` (recent-climate inputs, small gain:
dense tree count ×0.98, 19 of 22); (d) the NPP gain from soil texture as a pre-registered NPP arm; (e) a ten-network
ensemble for deployment if the cost is acceptable.

**2026-10-21 (evening) — the forest map fed its own last-year state: does NOT follow die-offs; and a training leak
found and fixed (ADR 0352).** Owner said "yes try it" to the recursive map.
* **Leak:** the yearly structure map's (and the stand map's) training rows held run m5 on the HELD-OUT climate model's
  legs (m5 is a training run and the test-side harness; 7.9 % of rows). Fixed in `explore_panel_yearly_drift.py` and
  `explore_panel_stand_map.build_rows`; new prediction files end `_fx`. Size on the structure map: errors +7–12 %
  (dense tree count 1.16 → 1.26, biomass per tree 1.07 → 1.18 a second run's), relaxed standard 21 → **18 of 22**,
  drift 1.17/1.32 → 1.22/1.41. The deployment release `v1` is unaffected (no test legs), but **ADR 0330 / 0340's
  held-out-model structure numbers, the stand map and the fold release must be restated** — not done yet.
* **Recursive arms:** `lag` (true last-year state) remembers a start error for ~10–20 yr but reproduces only 19 % of
  a drought drop → aftermath gap 3.98× (unchanged), errors +24–30 %, drift 1.55/1.86 (fails). `lagd` (trained on
  its own free-run lags) learns to ignore the state (start error gone by 2025) → gap 3.77×, errors +2–10 %. Neither
  adopted. The bottleneck is the drought year's drop itself, not the memory.
* `fx10` (recent-climate inputs, leak-free) is a small consistent gain (dense tree count ×0.98, sparse ×0.93,
  19 of 22) — ship-or-not is open.
* Rerun / score any variant: `scripts/score_yearly_map_variant.sh <suffix> [fit args]`.
**Next (owner to choose):** (a) restate the release's structure accuracy and re-score the stand map + fold release
leak-free (recommended first: it corrects published numbers); (b) a die-off model of the one-year change
`n(y)/n(y−1)` from the year's drought anomaly + the stand; (c) ship `fx10`.

**2026-10-21 (afternoon) — model fixes on the available data (owner: *"do the model fixes first … we produce more
full grid training data only when we are sure which model version we want to emulate"*; daily data now in
`/p/projects/reformit/Jamir/esm_land_emulator_data/f2`, old path a link).** Status of the four to-dos below:
* **Soil texture into the daily network (ADR 0348 arm T) — RUNNING.** 15 members trained (all 10 epochs). One-day
  validation loss −7.5 % in both seed pairs (runoff −20…−24 %, deep −12 %, transpiration/GPP/NPP −4…−6 %, snow change
  +11 % of a tiny value). The verdict is the free-run score: ensembles `TE_5seed`, `T2E_5seed`, `D2E_5seed` (jobs
  2638473/79/85, gpu queue). When done: `python scripts/f2_relative_score.py DE_5seed TE_5seed D2E_5seed T2E_5seed >
  $SCRATCH/s.md`, then `python scripts/f2_relscore_compare.py $SCRATCH/s.md DE_5seed TE_5seed` and the same for
  `D2E_5seed T2E_5seed`; adopt if BOTH pairs give runoff ≤ 0.90 and ET ≤ 0.95 (median over legs), GPP/NPP ≤ 1.05,
  worst leg ≤ 1.25, drift ≤ +0.08 (ADR 0348 §1). If adopted: the package `landemu` needs the four columns
  (`Setup.soil_code` exists).
* **Ensemble size (ADR 0348 §4.2): FIVE STAYS** — one net 10–28 % worse; three passes in one replicate only (ET/runoff +10 % in the other); ten is 6–13 % better on ET/runoff but GPP +1.8 % vs one reference and doubles the daily cost (whole emulator ~1.4e-2 core-s, just over the T31 allowance). Was: (jobs
  2638488–92); rule in ADR 0348 §2 (read each run's one-core timing from its summary.md).
* **Soil code in the forest map (ADR 0349): NULL, closed** (±2 %).
* **Drought die-offs (ADR 0350/0351): the forest map MISSES them; climate inputs do not fix it.** 94 % of the
  original's big one-year tree-count drops are drought years shared by its other runs; the map captures 3 % of the
  drop (14 % with recent-climate inputs) and is 3.8–4.4× a second run's error in the 10 years after. A fix needs the
  forest's own state as input (recursive map) — **ask the owner** before starting it.

**2026-10-21 — to-dos from the owner's questions on the paper draft (items 1–4 now being worked, see above).** Paper wording to-dos are in
`docs/paper/README.md` ("Owner's questions, 2026-10-21"). Emulator to-dos, each a one-variable arm, pre-registered:
1. **Soil texture is not a daily-network input** — only the top-metre capacity (`cap`, mm). Texture sets how fast water
   moves (infiltration, percolation), which `cap` does not carry; runoff (5.2× a second run) and top-metre water are
   the worst daily variables. Arm: add texture (sand/silt/clay or saturated conductivity from the soil code via the
   live soil par file) to the daily inputs; score runoff, ET, top-metre water as ADR 0325. Never tested so far.
2. **Soil code enters the yearly maps as a plain number** (no `categorical_feature` in `explore_panel_yearly_drift.py`
   / `explore_panel_stand_map.py` / the release), so LightGBM splits on code ranges with no physical meaning. Arm:
   categorical, or replace by physical soil properties. Expect a small effect (dropping lat/lon/soil changed < 5 %,
   ADR 0343).
3. **Ensemble size is not tuned** — five members were chosen for cost (ADR 0322: a single net's NPP level wanders by
   several % with the seed). Measure 1/3/5/10 members: score vs cost (the daily nets are 97 % of run time).
4. **Legacy of single extreme years** — the forest maps are non-recursive, so a die-off after one extreme drought
   cannot carry into later years except via 1/30 of the climate window. Diagnostic first: score the years after the
   original's largest one-year drops; if missed, try lagged-extreme climate features (e.g. worst year of the last
   5), not recursion.
5. Unseen cells stay a sample-size problem (ADR 0343) → full-grid training, already in the options below.

**2026-10-21 — the emulator paper is drafted and fact-checked (`docs/paper/`, README there).** Model-description
manuscript of release v1 (25 pages, 11 figures, rebuild `scripts/paper/make_all.sh`); every number traced to a record,
an independent fact-check applied in full (`docs/paper/FACTCHECK.md`). Open: the owner's read, author list, Zenodo
DOI, journal formatting. ESM coupling deliberately not in it (owner, 2026-10-20).

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
