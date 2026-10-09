# LINE X — project direction & exploration (branch `line/X`, worktree `wt-X`)

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/X/JOURNAL.md` (append-only). Decisions: tier-1 block
> **0310–0329**, opened by **ADR 0310**. **Next free number: 0318.**
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

---

## What this line is (created 2026-08-19 on owner instruction)

Owner, verbatim: *"you are also nto the correct person to discuss this with. relocate our whole discussion to
a new line that is responisble for these project lever decisions and exploring new ideas."*

**Line X is where project-level direction is explored and where new ideas are worked out before anybody
builds them.** It exists because the four component lines (S, M, E, O) are each mid-ladder on a specific
subsystem, so a question like *"should the whole architecture be different?"* has no owner: whichever line is
asked either has to act on it (wrong — it is not their call) or drop it (worse). Line X can hold an open
question, measure it, and leave it open.

### Scope — what line X DOES

* **Explore directions that deviate from the current architecture** — the hybrid, the ladder, the component
  split. Adversarially, with measurements, against the existing records.
* **Own the owner conversations about direction**, and record what the owner actually said, verbatim, next to
  every open exploration.
* **Price alternatives honestly** — including pricing the *incumbent* fairly, which is where exploration work
  usually cheats (see the traps below).
* **Write the exploration up as an ADR from block 0310–0329**, marked `exploratory` unless the owner promotes
  it.
* **Read anything. Measure anything read-only.**

### Scope — what line X does NOT do

* ⚠ **It does not implement.** No `src/**`, no `ext/**`, no flags, no artifacts. A finding that survives
  becomes a *proposal*; the owner decides; the owning line builds it.
* ⚠ **It does not write into another line's `STATE.md`, `MEMORY.md`, or `EXECUTION_PLAN.md`.** Line X's whole
  value is that it can hold an idea without pushing it at anyone. **Propagation is an owner decision.** This
  is not a style preference — it is the instruction that created the line:
  *"no! stop! dont write anythign of this to other lines!!!"*
* **It does not merge another line's work or act as the integrator.** (Except in the ordinary sense that
  whoever holds the `flock` is the integrator for that moment — §9.)
* **It does not re-litigate closed owner decisions.** Standing closures: **CO2** (the emulator does not see
  CO2 and must not respond to it — ADR 0004/0107; never propose a CO2 feature or list its absence as a
  defect), **licensing/reuse** (ADR 0080/0081 — reuse is authorised, cite transparently, never raise it
  again), **the spin-up saving is not the goal** (ADR 0094), and **the acceptance criterion** (ADR 0106 —
  line X may *propose* an amendment, explicitly and with both patch counts stated, but never adopt one as a
  premise).

### Owned paths

| path | note |
|---|---|
| `lines/X/**` | exclusive |
| `docs/decisions/0310-0329` | exclusive (tier-1 block; tier-2 would be 0330–0349) |
| `changelog.d/X-*.md` | new fragments only — **never** edit `CHANGELOG.md` from a line |
| `docs/notes/exploration_*.md` | exclusive — long-form exploration notes that are not decisions |
| `scripts/explore_*.py` / `scripts/explore_*.jl` | exclusive — read-only probes. ⚠ Derive the repo root from the script (`os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` / `@__DIR__`), never a hard-coded absolute path, or you write into the integrator worktree (§9 trap 6). |

**Everything else is read-only to line X**, including all of `src/**`, `test/**`, `python/**`, every other
line's `lines/*/STATE.md`, `MEMORY.md`, and `EXECUTION_PLAN.md`.

### The four traps this line is most likely to fall into

These are not hypothetical — every one of them was committed in line X's own opening exploration (ADR 0310)
and caught only by adversarial review.

1. ⚠ **Rigging the comparison against the incumbent.** ADR 0310's speed case claimed "210× faster than the C"
   by measuring against a 25-patch configuration that the same repo had already shown nobody needs for the
   quantity being priced. **Price the incumbent at the configuration it would actually be run at.**
2. ⚠ **Reporting a skill number with no null.** A one-step forest-state operator scored 0.9824 — against a
   persistence null of **0.9622**. A per-cell response model scored 0.748 — against a **pure lat/lon
   geographic address at 0.654**. **Derive what each null must return and write it down BEFORE the run**
   (ADR 0184's rule). A missing null is the single most common way an exploration reports a discovery.
3. ⚠ **Substituting a convenient basis for the owner's.** ADR 0310 nearly concluded that the response bar
   needs 0.12 % level accuracy, from an area-weighted **global aggregate** that appears in **no** acceptance
   criterion; on the owner's **per-cell** basis the number is 1.86 %, fifteen times looser. **State the basis
   in the same sentence as the number.**
4. ⚠ **Letting a measurement go stale.** ADR 0310's first draft reasoned from records that stopped ~30 ADRs
   before the present day, and two of its "blocking data gaps" were refutable with one `ls`. **Check the
   newest ADR number and the newest STATE files before concluding anything is unmeasured or impossible.**

---

## NEXT — start here

### 0🎯 2026-10-10 (ADR 0316 §11) — BEST ARM NOW A7rH: biomass per tree 1.26× a second run; TREE COUNT IS THE BINDING GAP

Sparse cells (< 5 trees per patch, ~20 % of cells) carried most of the error: A7r's tree-count ratio 3.1–3.5 there vs
1.15–1.36 at 5–20, while the mean of three runs is 0.82 everywhere. Cause found in part: squared error on the ABSOLUTE
residual. `explore_panel_a7.py logt` (A7rL: log-ratio target, jobs 2456437–41) + `logt_mix` (A7rH = log target on biomass
per tree only, job 2456487). **A7rH** (`both` set, ssp370): pass 0.207 (A7r 0.193), biomass per tree **1.26 / 1.26**
(was 1.42 / 1.71), tree count unchanged 1.35 / 2.08, totals 1.9 % / 4.2 %. The log target on tree count helps sparse cells
(3.45 → 2.04) but hurts the 10–20 class and biases the stem total 4 % low.
**NEXT, in order:**
1. **Tree count, one variable:** a count-aware loss (LightGBM `poisson`/`tweedie` objective, anchor as `init_score` offset
   in log space) vs A7r on the same `both` set; pre-register in the header (expect: < 2 class ≤ 2.5, 10–20 class not worse
   by > 0.05, stems total within 2 %). Score with `logt`-style mode + `PRED_SET=… PRED_ARMS=…`.
2. Port A7rH to the global venue (`explore_glob_a7r.py`, then `explore_glob_tolerance.py`) — does the biomass gain
   (1.96 there) reproduce on 5 809 cells?
3. UKESM (warmest model) still fails the bar: the extrapolation measurement of ADR 0317 §8 item 5 is still open.
4. Owner questions (10 %/20 %, 5 % totals, unseen cells) unchanged.

### 0📈 2026-10-10 (ADR 0316 §10) — THE MORE-DATA PREDICTION HELD, AND IT IS NOT ENOUGH — read first

Scored the chained test (5 seeds, `xpanel/eval/a7_more_mean.csv`; second-run measure via
`PRED_SET=<base|mod|run|both> python scripts/explore_tolerance_measure.py`, ~1 min each, login node OK).
**Pass rate:** `both` (9 models, 5 runs) − `base` (4 models, 3 runs) = **+0.033** on ssp370 (0.161 → 0.193), bar on 12 of
13 ⇒ the prediction **HELD**. The gain is the climate models (`mod` +0.023), not the runs (`run` +0.005). Still failing:
UKESM ssp370 (0.134 vs 0.151) and UKESM ssp585 (0.073 vs 0.143) — the warmest model, outside every training model.
**Second-run measure (ssp370, median over 5 held-out models):** tree count 1.39 → **1.35** (bad cells 2.23 → 2.08),
biomass per tree 1.64 → **1.42** (1.77 → 1.71). Target ≤ 1.1–1.2. The panel already uses all ten ISIMIP3b models.
⇒ **More climate models are necessary, not sufficient; the arm must improve.** More runs per cell: not worth producing.
**NEXT, in order:**
1. **The arm, not the data.** Where does A7r's per-cell tree-count / biomass-per-tree error come from on the panel `both`
   set? Split by the truth's density class (the global venue's miss sat in sparse cells, ADR 0317 §8 item 2) and by how far
   the leg's climate lies outside the training legs per cell (ADR 0317 §8 item 5's open question — same measurement, now
   on both venues). Score on `explore_tolerance_measure.py` / `explore_glob_tolerance.py`. Measure first, then one
   one-variable treatment (e.g. a sparse-cell target transform or a log-count target), pre-registered.
2. Owner questions still open: 10 % vs 20 % (ADR 0317 §7 reserved), the 5 % area-total line, and ADR 0316 §8/§4
   (cells never run by the original). Do not propagate the threshold without the owner.
3. Global all-cell runs under more climate models: NOT recommended yet on this evidence (pass rate yes, second-run
   measure no). Re-raise only with an arm whose ratio moves with data.

### 0🎯 2026-10-09 (ADR 0317) — THE TARGET CHANGED: "as close as a second run of the original" — read with ADR 0316 below

Owner, verbatim: *"of course. the goal is to be as close as a secodn run of the orignal model. it is even fine if it s worse.
find a good measure ... I would be happy if the emolator is not more than 10% worse thatn a second model run of the
orignal"* · then *"but maybe the threshold should be even 20%?? what do you think?"*
**Done:** measure defined + measured (`scripts/explore_tolerance_measure.py`, ~1 min, login node OK): per quantity, the
emulator's per-cell error vs an unseen run divided by a second run's, at the median cell and the 90th centile, levels and
response, all cells + per region; plus area totals ≤ 5 % and no drift (proposed). Harness passed (second run 0.95–1.03,
mean of 3 runs 0.82 as derived). **A7r: traits 0.66–0.94 (better than a second run); tree count 1.43 / 2.23, biomass per
tree 1.63 / 1.76 — FAILS, and barely beats the lookup null (1.52 / 1.66).** Recommended 10 % on all cells, 20 % per region.
**NEXT:**
1. Owner's answer on 10 % vs 20 % (and on the 5 % totals line, which is line X's own proposal). Record it as ADR 0317 §7.
   Propagation to `~/.claude/CLAUDE.md` / MEMORY / the plan only if the owner says so.
2. Score every new result on BOTH the old screens and this measure. **Global venue DONE (ADR 0317 §8,
   `scripts/explore_glob_tolerance.py`, ~5 min on SLURM):** harness 0.96–1.04, mean-of-5 oracle 0.78–0.82; **A7r tree
   count 1.44 / 3.62, biomass per tree 1.96 / 2.75 — worse than the lookup null on biomass (1.84) and on bad-cell tree
   count (2.34)**; biomass total 8 % off; failure concentrated in sparse cells (tree count 6.4 at < 2 trees/patch);
   5th training run moves ≤ 0.02. "Global is easier than the panel" FALSIFIED.
   The "anchor too low" hypothesis is REFUTED on disk (anchor is 11 % HIGH on biomass per tree; ssp370 = more, smaller
   trees). **Next (measure, don't fix):** how far ssp370's climate lies outside the training scenarios' range per cell,
   and whether the A7r miss tracks it; then a sparse-cell treatment. Score on `explore_glob_tolerance.py`.
3. The binding gap is now per-cell tree count and biomass per tree under a held-out climate model. When ADR 0316's
   more-data test lands (item 1 below), read it on this measure too: does more data move ρ on those two quantities?

### 0🧪 2026-10-09 (ADR 0316) — PANEL VENUE + MORE DATA RUNNING — this block wins over everything below

Owner, verbatim: *"continue. the goal stays the same. do everything you need to do to reach it. including producing more
data if that is mandatory and we have solid results that support the assumption that more data gives the breakthroug."*
**Read ADR 0316 first.** Done: panel venue on line S's Track-D runs (`scripts/explore_panel_prep.py`, data
`…/esm_land_emulator_data/xpanel/`); direct map with cells held out fails; in the DEPLOYMENT setting (cells seen, run +
climate model held out) the anchored direct map **A7r** passes the bar on 11/13 held-out-model cases (`explore_panel_a7.py
seen`, 5 seeds, `LGB_SEED`), global GS370 on the bar 0.140 ± 0.004 (`explore_glob_a7r.py`). Data curves all rising ⇒
**more data submitted** (`scripts/explore_panel_runs.py`): 5 new climate models × 3 scen for m1–m4 + new members m5/m6
(spin-up + everything). Jobs: forcing 2451723 (done, gate PASS); runs 2451916/18/20/22/24/26 (spread over free cores: the one-node
pin waited ~3 days and matters only for row-by-row reproduction of an existing run), collectors 2451917/19/21/23/25/27 → tables `…/esm_land_emulator_data/xpanel_runs/m<k>/<leg>/` (`status`:
`python scripts/explore_panel_runs.py status`). Also resubmitted line S's two dead panel legs (m3 MPI ssp585 run 2451928 →
collector 2451929; m4 UKESM ssp585 2451930 → 2451931; all 105 blocks re-run, spread over nodes; these write into line S's
trackD tables with unchanged tooling).
**NEXT, in order:**
1. ✅ DONE 2026-10-10 (ADR 0316 §10, prediction HELD; see the 📈 block). Was: The prediction test is CHAINED (already extended code: `explore_panel_prep.py` reads `xpanel_runs`, `explore_panel_a7.py
   more`): statistics 2452216 → `more` seeds 1–5 (2452217–21, logs `logs/X-pan-more-s*.out`, outputs
   `xpanel/eval/a7_more_s<k>.csv`). Aggregate the 5 seeds per (set, held-out model, scenario) and read ADR 0316 §7's
   PREDICTION (`both` vs `base` on ssp370: ≥ +0.02, bar on ≥ 12/13; falsifier < +0.01); `mod`/`run` split the gain.
   If a job died: `python scripts/explore_panel_runs.py status`, rerun the missing collector, then the chain. Do NOT
   re-tune before scoring it. Write the result as ADR 0316 §10 (or 0317 if it changes direction).
2. Panel LSTM: DONE, parked (ADR 0316 §9: stable for 3 of 5 held-out models, runaway for 2; levels below the direct map).
3. Global venue: A7r with 5 training runs (2,3,4,6,7) clears DP-G1 (a) by 0.003 — marginal (ADR 0316 §5).
4. Owner decision raised (ADR 0316 §8): which reading of the acceptance tolerance — a second run of the original passes only
   17–21 % of cells under the current reading. Also: whether cells the original was never run on must be emulated (§4).
5. If the prediction holds: price global (all-cell) runs under more climate models (disk is the cost; trees > 5 m only).

### 0🌍 OWNER INSTRUCTION 2026-10-08 (ADR 0313): TRAIN ON BILLING'S GLOBAL RUNS, NOT GERMANY — this block wins over everything below

Owner, verbatim: *"if you find suitable global runs, use them for training the emulators instead of the germany runs"* ·
*"the emulator needs to work with every model version"* · *"cancel the germany runs if you think we have better data now"*.
**Done 2026-10-08:** found M. Billing's standard-trait (family r1) global LPJmL-FIT runs, audited them, cancelled the
18 pending Germany humidity re-run jobs (D2; none had started), converting 38 per-tree tables (array job 2445643,
`logs/X-glob-conv.2445643_*.out`; the first passed `conversion_ok`). Full inventory + exclusions: **ADR 0313**.
**Data:** `/p/projects/open/Jamir/esm_land_emulator_data/billing_global/ind/<gcm>/<scen>/s<m>/<window>/cb=NN/` (+ `ind_dev/`, `_gates.csv`):
GFDL-ESM4 × {historical h1985 (1985–2014), ssp126/245/370 w2071 (2071–2100)} × members 2,3,4,6,7,8 (Feb-2026 build),
9,10 (May-2026); GSWP3-W5E5 obsclim h1990 (1990–2019) × members 1,2,3,5,6,7 (Oct-2026 builds). 67 420 cells, 25 patches.
⚠ Cells are in `grid.bin` order (Hainich = 28008), not orderA. ⚠ No per-tree table 2015–2070 (gridded only, in each
run's `output_transient/`). ⚠ Expected gate "fails": `census` (bare-land cells, verified) and `unique` (raw ID key).
**Done 2026-10-08 (night, ADR 0314/0315):** all 38 tables converted (the six Oct-build reanalysis tables have a
30-column layout — converted natively, `ind_layout` in the registry); climate inputs built and verified end to end
(`…/billing_global/climate/cell_year/<gcm>_<scen>.parquet`, Germany feature names; printed per-tree `mort_temp`
reproduced 100 % on all 38 tables); registry + folds + splits at `…/billing_global/registry/`; **DP-G1 pre-registered**
in ADR 0315 before any arm is scored. ⚠ The Oct builds use `MORT_TEMP_FACTOR` 4.0 and a 14 °C tropical cold limit (Feb/May:
5.0, 12.5) — different model, by design part of the GV split. ⚠ getvpd.c's `1013.25` is NOT a unit slip (ADR 0314 §2).
**Done (late night):** scorer `scripts/explore_glob_eval.py` + baselines (ceiling 0.173 conjunctive pass; lookup 0.100 ⇒
DP-G1 (a) tightened to "above the best null"); arm A7 `scripts/explore_glob_a7.py`: A7s 0.131, response slope 0.63,
biomass per tree +12.4 % ⇒ fails (b). Scores: `…/billing_global/eval/scores_GS370.csv`; ADR 0315 §7–8.
**Done 2026-10-08/09 (night): GV measured (ADR 0315 §10, `scripts/explore_glob_gv.py`, `eval/scores_GV.csv`).** Feb → May build
is inert (Feb-mean vs May 0.28 = vs Feb 8 0.28; A7s transfers with no loss). The Oct builds are four different models
(biomass per tree 1.47 / 1.22 / 1.04 / 1.11 × Feb on identical forcing within the family); Feb-trained A7 passes 0.3 %
of Oct cells vs 16 % Oct-to-Oct — useless there.
**Running: arm A2g, the cell-level LSTM with a GAP-CROSSING rollout loss** (`scripts/explore_glob_lstm.py`; trains on
members 2,3,4,6 × hist+ssp126/245, free-runs 2015→2100 and is penalised only where truth exists). Yearly stats built
(`…/billing_global/yearly/`, 32 files). Smoke passed (beats 2014 persistence on held-out blocks after 100 steps;
~7e-6 core-s per cell-year). Train array **2445840** (lstm/lstmCB × 5 folds, `logs/X-glob-a2tr.2445840_*.out`) →
score **2445841** (`afterok`; `eval/scores_A2g.csv`, log `logs/X-glob-a2sc.2445841_*.out`). Pre-registered expectations
+ gates in the script header. If the score job is missing: a training task failed (check `JOB DONE exit=`).
**Owner correction 2026-10-09, verbatim:** *"dude. of course an eulator trained on one model verison cant be used for
another. it only works for one model verision. but for any model version"* ⇒ "every model version" = **the METHOD
retrained per build**, not transfer (ADR 0315 §11). Tested (`scripts/explore_glob_pv.py`, `eval/scores_PV.csv`): A7/A7s
retrained on one run of each build reach the same skill on Feb, May, Oct-1/6/7/8 (absolute numbers equal to ~0.01;
the pre-registered ratio test was badly posed — §11.1). Per-version inputs to fix: `tstress_pft0` threshold per build,
no per-tree column the Oct layout lacks.
**NEXT, in order:**
1. **A2g DONE, clean (ADR 0315 §15, 2026-10-09).** The input fill is now causal (forward only, training AND prediction;
   `explore_glob_lstm.py --fill causal`, default). Clean retrain (tag `_causal`, `eval/scores_A2g_causal.csv`): pass
   0.119, trees 0.996, biomass per tree 1.068, tree-count response slope **0.85** (twin 0.59), free run from 1985 at 2014
   0.986 / 0.990 ⇒ DP-G1 fails on (a) only, as before. ⚠ §14.1's "clean slope 0.65" was a train/inference mismatch (the
   leak-trained model fed an input it never saw; 22 % of colonising stems vs 95 % after the retrain) — the leak was
   worth ≈ 0.01, superseded. Calendar test on the clean models (`clock_*_causal.csv`): scenario-contrast stems slope
   0.47 (was 0.30), still just under the 0.5 rule; total overshoots +19 %. Germany LSTM: 0 cells exposed (§15.4).
   Per-build retrains clean (§15.5): Feb pass 0.103 / slope 0.83, May 0.097 / 0.77 — §13's reading stands.
   **Rule from now on:** every recurrent arm uses `fill_causal`; price a leak with a retrain, never a re-prediction.
2. Then the other recursive arms (A3, A4, A6) on this venue, same harness, each with its climate-blind twin.
   ⚠ **All three sit on the Germany per-tree stepper (TAB) — the PORT is IN PROGRESS (2026-10-09, ADR 0315 §16).**
   Map + blockers: `docs/notes/exploration_glob_tab_port.md`. Data root (Germany format, Feb members 2,3,4,6,7,8, dev
   cells renumbered 0..6419): `…/billing_global/xde`, built by `scripts/explore_glob_tabroot.py` (gates pass).
   **Every stage needs these exported** (sbatch forwards the env): `XDE_ROOT=…/billing_global/xde XDE_GRASS_TYPES=7,8,9
   XDE_RECR_TYPES=0,1,2,3,4,5,6 XDE_TRAIT_BUILD=feb2026 XDE_LAST_SIM_YEAR=2100`.
   DONE + gated: SH2 params/allometry, SH3 transitions (24 member-windows; identity gates all pass), SH4 patches,
   SH5 starts (s8 1985/2014, s7 2014; NOTE `sh_init submit` ignores `--start` — use `build --start` via
   sbatch_python), A1 samples. Scorer `scripts/explore_glob_tabeval.py`; harness (frozen stepper) reproduces §7's
   persist_2014 row EXACTLY (`eval/scores_TAB_frozen.csv`).
   DONE too: SH13 heads, A1 recruits, all 20 TAB heads (one grass model per grass type), stepper prep.
   **First free run SCORED (ADR 0315 §16.1): plain TAB FAILS badly** — GS370 pass 0.022 (below carrying 2014 forward,
   0.057), trees 1.17, biomass per tree **0.505**; its climate-blind twin 0.026 / 0.90 / 0.90. Two failures: a slow
   growth deficit in both (−23..−29 % biomass per tree by 2014 from 1985) and a CLIMATE-driven halving only in the arm
   (on ssp126 too ⇒ not extrapolation). 0.17 core-s per cell-year.
   **Attribution DONE (§16.3):** the growth-efficiency climate booster carries 60 % of the GS370 biomass collapse; the
   growth-amount booster 0 %, survival 0 %, and the recruit booster was SUPPRESSING recruits (off ⇒ +8 % stems). The
   sign head is calibrated on true stands (held-out, within 0.4–0.6 points); the excess bad years appear only in the
   free run (drift compounds). **A4 DONE — fails DP-G1 (a), (b) (§16.5–16.7):** scalar calibration on member 2 /
   ssp245 / fold 1 (`scripts/explore_glob_a4.py` cal|split|twin|pick|confirm; stepper gained `kappa_gsign`/`kappa_gmag`,
   default 1). No scalar reaches (b): best κ_g = 0 → biomass per tree 0.596 (twin there 0.743); offset −0.5 → 0.587,
   transfers to GS370 within 0.03 (0.614 / 1.174, pass 0.024). Growth-efficiency channel = 38 % of the climate gap on
   the calibration basis (magnitude 27 %, how-often 13 %). The twin itself is 26 % short (trees never mature).
   **NEXT for the per-tree route (decide, don't drift):** it is the weakest arm on this venue (pass ≤ 0.035 vs A7s 0.131,
   A2g 0.119, 2014-persistence 0.057). A3 needs the original's response on the arm's own states — no C re-run harness
   here; A6 needs B7 + four single-grass modules. Recommended to the owner: park A3/A4/A6 on TAB; the open per-tree
   question worth one probe is the twin's slow growth deficit (a multi-step / rollout loss on the growth heads, as A2g's
   gap-crossing loss did for the LSTM) — only if the owner wants the per-tree route kept alive.
3. **Integration point (not done — line X does not edit the plan):** `EXECUTION_PLAN.md` DP-A1 → DP-G1; X ↔ S overlap.
4. Germany tables + scorer stay a secondary venue; do not resubmit D2 without the owner.


### 0⛳ PLAN REVISION 2 — `EXECUTION_PLAN.md` CHANGED 2026-10-08 (owner instruction; ADR 0096): parallel method arms on one yardstick, data first

Owner, verbatim: *"based on the findings of this project so far and the findings in the review, update this
projects plan. the goal stays the same, upate the plan on how to get there if necessary. try all promising
methods"*. The goal (ADR 0094/0106/0107) is unchanged. The 2026-08-07 error-attribution ladder is **no longer the
order of work** — its findings stand (plan §11) and so does its rule *one variable per arm*. Read
`EXECUTION_PLAN.md` §1–§9 and `docs/review_comparison.md` (the literature comparison) before planning.
**Where anything further down this NEXT block conflicts with this block, this block wins.**

**Line X's assignment** (consistent with the owner's Germany-first milestone of 2026-10-01; line X's own charter
still holds: it does not write into other lines' state):
* **Germany round 1 of arms A2–A7 on one scorer** (`scripts/explore_de_sh_eval.py`, extended with the plan §4
  statistics: within-training-period free run, speed, conservation): **A2** add a rollout loss + 4 → 8 → 16-yr
  curriculum to the LSTM, then a per-tree output stage; **A3** one dataset-aggregation round on TAB (retrain on its
  own free-run states, targets from the original via the C re-run driver); **A4** free-run calibration / signed
  zero-sum loss on TAB; **A5** finish the set model's scoring; **A6** your current margin/NPP route; **A7** re-score a
  direct non-recursive window map as the benchmark. A8 only if a slot is free.
* **D2** — the Germany 2071–2100 re-run with the humidity setting corrected (`restart_2070_nv.lpj` exists for every
  leg; ~900 core-h per leg) — **only after the owner says yes**.
* **C3** — equilibrium initialiser: `vegemu`'s map (read-only) + the functional restart test.
* **Do NOT start:** the global transfer of an arm before it passes DP-A1.
* **Integration points:** X ↔ S (shared Track-Y statistics, D0 cell list).

**Bound by (plan §4, §8, §10):** every score carries its nulls (persistence, lookup, climate-blind twin,
frozen-climate control, other-member ceiling) and its free-run beside any one-step number; decision-point
thresholds may be tightened before a run, never loosened; no CO2.

---

### 📥 INBOUND (integrator/line S, 2026-10-08, ADR 0246) — the Germany 2045-2100 re-run you asked the owner about is APPROVED and RUNNING

Owner, 2026-10-08: *"yes, produce all data that you need"*. Built and submitted on **line S's** branch because
this worktree had a live session (nothing of yours was touched). **What you get:** all 12 members re-run
2045-2100 in ONE run from production `restart_2044_nv.lpj` with the production 2045-2070 config (humidity on) +
lastyear 2100; the production 2071-2100 config's `fix_climate` block acts only after 2100, so the humidity key was
the only defect. Each member used its production build (read from its logs; the ssp245 Feb-2026 build is row-gated
against production w2015 rows first, and its four members are submitted only on PASS — `logs/S-D2gate-eval.*.out`
on line S's worktree). **Tables, in YOUR converter's layout** (`explore_de_convert.py` unchanged, paths redirected by
`scripts/trackd_convert_germany.py`): `/p/projects/open/Jamir/esm_land_emulator_data/trackD/germany_rh/ind/<GCM>/<scen>/s<seed>/w2045/cb=NN/`.
Two differences from your production tables: trees <= 5 m are included (`Height > 5` gives the production format)
and 2045-2070 now has a tree table. Query progress, don't assume it: `squeue -u $USER | grep S-D2`. The re-run's
2045-2070 gridded outputs vs production's tell whether production was reproduced (node types) — line S checks it.
Also available soon for the global transfer: the panel campaign (105 blocks, 4 members, 15 real-climate legs + 2
controls) under `.../trackD/panel/` — skill `trackd-data`.

### 00✦ 🔨 OWNER INSTRUCTION 2026-09-30: BUILD the data-driven emulator, Germany first (supersedes "line X does not implement" FOR THIS BUILD ONLY)

Owner, verbatim: *"ok go on and build the emulator. you can also do it for germany only now, for testing. for germany we have runs with
more pathces and several different ssp scenarios and two differnt models in /p/projects/waldspektrum/data/LPJmlFit/productionruns_Jamir"*
(the real path is `/p/projects/waldspektrum/data/LPJmLFIT/productionruns_jamir`), and *"be aware that the trasnioent run is only until
2100, after that the climate is recycled, so no warmin response is tehre"*. Ultracode (multi-agent) switched on by the owner the same turn.
**Milestone (owner, 2026-10-01, verbatim): *"the next milestone is to make a "germany emulator" work with the germany data. once that
works we can then use the method for the global emulator"*** — so build the METHOD so it transfers: nothing Germany-specific baked in
(cell counts, patch count, PFT set, file paths all parameters).
**Owner, 2026-10-01, verbatim: *"I want you to try out all the most promising designs in parallel. is LSTM also an option?"*** ⇒ the
round-1 design panel now has FOUR architects (per-tree boosted heads · structured = learned growth + the original's own death/recruit
rules · recurrent LSTM/GRU memory for the invisible state · patch-level neural set model with multi-step training), and the judge
plans SHARED infrastructure + one parallel build TRACK per promising design, all scored by the same scorer.
**Round 1 DONE (2026-10-01, `wf_89265fa2-f32`):** all 40 tables converted + gated; climate features; transition anatomy (verified);
scorer + nulls; 4-architect panel → judge plan = shared SH0–SH13 + tracks A-TAB / B-STRUCT / C-RECUR / D-NSET; critic amendments.
Everything in `/p/tmp/jamirp/X_de/_reports/` (`round1_all.json`, `round2_args.json` = the build plan).
⚠ **[VERIFIED] HUMIDITY CONFIG DEFECT IN THE GERMANY PRODUCTION RUNS:** `"relative_humidity": true` is missing from every
`lpjml_2100_*` and `lpjml_3100_*` segment config (present in Historical/2044/2070/3070); `fscanconfig.c:255` defaults it FALSE, so
2071–2100 and 3071–3100 read relative humidity as specific humidity ⇒ VPD 0 ⇒ **water-stress mortality exactly 0** (living trees with
mort_water>0: 5.1 % in 2015, 0.0 in 2071/2085/2100, MPI ssp370 s1 dev cells; same ACCESS ssp126). Told the owner; rerun = owner decision.
Emulator carries `rh_on` as an input; primary response statistic = between-scenario contrast at w2071 (cancels it).
Also: all ssp245 segments ran the Feb-2026 binary, everything else Dec-2025.
🛑 **OWNER DECISION 2026-10-01 (verbatim): *"double check if the runs after 2070 were really corrupted with the wrong settings. if its
true, lets only use the earlier data that is correct, for now."*** Double-checked three ways and TRUE: configs (key in 12/12 2044,
12/12 2070, 12/12 3070, 4/4 Historical; 0/12 2100, 0/12 3100), run logs (2071–2100/3071–3100 list "humid", all others "rhumid"),
data (mort_water>0 share exactly 0.0 in 2071 and 2100 in all 24 ssp runs vs 0.02–5.1 % in 2015, 0.08–9.4 % in 2044;
`/p/tmp/jamirp/X_de/_jobs/check_rh_effect.py`, log X-de-rhcheck.2371045). ⇒ **the build uses 1985–2044 only**; w2071/w3071 excluded
everywhere; primary response = ssp370−ssp126 contrast in 2015–2044; the correct 2045–2070 segment's gridded outputs become optional
cell-aggregate checks to 2070. A rerun of 2071–2100 (and beyond) is the owner's call.
**Round 2 — the multi-agent workflow `wf_d4262351-d9d` DIED (~14:17, 2026-10-01) after SH0, SH1, SH2, SH12, SH14 (+ verifiers
of SH2, SH14); a workflow cannot be resumed from another session. 2026-10-02 the build continued BY HAND + background Agent
helpers (no Workflow call: ultracode was not re-confirmed this session).** State per item (status `_status/<id>.md`):
* DONE 2026-10-02 (dev cellset = 907 cells): **SH3** transition table `shared/trans/dev/` (882 M rows, ALL gates pass) ·
  **SH4** patch + recruit tables (4/6 gates; the 2 misses are pre-registered bands contradicting their own source
  measurement — release x3.17-3.31 = round 1's 0.29->0.92-1.06; re-entry is episodic 0-2.15 %/yr) · **SH5** initial
  states 1985/2014/2044 (20/20 pass) · **SH6** engine `scripts/explore_de_engine.py` — conformance (i) REPLAY == truth
  EXACTLY through the scorer (239 448 cell + 13 728 block rows, incl. the c2015 contrast); (ii)-(iv) rerun after two fixes
  (bank row order made runs non-deterministic; frozen test's expectation wrong for interpolated quantiles).
* **SH8** rules ceiling `explore_de_sh_oracle.py` run (runs/oracle1/), scoring + yearly death series submitted.
  ⚠ FINDING: per-patch fire identification from one patch-year is biased ~9x (clipping keeps the positive Bernoulli
  noise); pooled per cell-year the rule deaths are +3.5-3.9 % of truth. Told the SH13 helper.
* **SH7** LOOKUP `explore_de_sh_lookup.py` bank + one-step gate submitted. **SH9** `explore_de_sh_eval.py` (score / dynamics
  / table -> shared/eval/comparison.csv) written.
* All three helpers FINISHED 2026-10-02 (committed): SH13 patch heads (3/4 gates; fire yearly r 0.821 vs a 0.9 gate whose
  noise ceiling is ~0.89), TAB A1-A5 (one-step held-out: G-sign log-loss 0.110-0.144 vs persistence 0.25-0.30; scenario
  sign gate 76 % on ACCESS; full chain death rate 3.39 vs 3.44 %; 543 CPU-us per tree-step ≈ 1.1 core-s per 250-patch
  cell-year; FOUR boosters hit their round cap — retrain open), STRUCT B1-B3 (G R2 0.93-0.96 vs persistence 0.67-0.77;
  water-stress amount fails; ~3 core-s per 250-patch cell-year). Everything one-step / teacher-forced.
* **NEXT ACTIONS, in order:** (1) the TAB rollout stepper (A6) and the STRUCT stepper (B5) on the engine — the API of each
  is in its report (`_reports/r2_A*.json`, `docs/notes/exploration_de_struct.md`); (2) free runs on ACCESS s1 1985->2044
  ssp126/245/370 + their climate-blind twins, scored with explore_de_sh_eval.py exactly like the lookup; (3) the
  free-run calibration steps (A7 / B5) ONLY on training members; (4) speed: both learned designs are 10-25x slower than
  the lookup — shrink/distill before any full-Germany run.
* **2026-10-02 (later session): A6 + B5 DONE — first free runs of both learned designs, scored** (helpers, committed
  bfe39d76 / 1c96dfda; reports `_reports/r2_A6.json`, `r2_B5.json`; table `shared/eval/comparison.csv`, column
  pass_cal_xg). ACCESS s1, 907 dev cells, 1985 start, legs forked 2014, to 2044. **Fold-5 (185 held-out places), cell
  panel pass:** h1985 — lookup 0.83 · TAB A-L 0.62 · A-S 0.68 · A-k0 0.45 · STRUCT 0.00 · ceiling 0.91.
  w2015 (ssp126/245/370) — lookup 0.08/0.11/0.07 · A-L 0.37/0.37/0.34 · A-S 0.43/0.46/0.36 · A-k0 0.35/0.41/0.37 ·
  STRUCT 0/0/0 · ceiling 0.91-0.92. Block scale: every arm 0 in w2015; the block contrast gate's own ceiling is 0.09
  on 11 fold-5 blocks => no power there; the per-cell contrast has none either (blind twins pass 0.99).
  READING: (a) TAB beats the lookup ~4x in 2015-2044, but its climate-blind twin does almost as well => the gain is
  not a climate response; climate does set the TIMING of deaths (yearly death corr A-L 0.51-0.56 vs A-k0 0.03).
  (b) rule death (A-S) >= learned death (A-L) in every window. (c) TAB stems drift to 1.21x truth by 2044 in every arm:
  deaths are right (3.52 vs 3.47 %/yr) but recruits are ~11 % too many (3.56 vs 3.20 % of stems/yr). STRUCT recruits
  are too many as well (3.67 vs 3.20) — BOTH use the SH13 recruit-count head => suspect a shared cause first.
  (d) STRUCT: free-run biomass ~2x truth by w2015 (median agb 162 vs 83) despite G R2 0.93-0.96 one-step; no
  acceptance => beech 0.81 vs 0.93, boreal NE 5 % vs 0.9 %. Cost (core-s/cell-yr, 250 patches, excl. daily->annual
  climate): lookup 0.12 · TAB 1.17-1.30 · STRUCT 2.86 · original ~12.
* **2026-10-02 (third session): the recruit excess is DIAGNOSED — it is the STAND, not the recruit head** [VERIFIED,
  ACCESS s1 ssp370 leg, 200 dev cells = chunks 0-1 of the TAB run; `scripts/explore_de_recruit_drift.py` ->
  `shared/eval/recruit_drift_ssp370.csv`, `scripts/explore_de_recruit_attrib.py` -> `shared/eval/recruit_attrib_tabAL.csv`].
  (a) NOT threshold flicker: TAB re-entries 0.0002-0.0015/patch-yr; entry height/age match truth (5.07 m, ~12 yr).
  (b) The original SELF-THINS (stems/patch 9.17 -> 7.19 from 1996 to 2036, agb/stem 497 -> 899, cover 0.42 -> 0.48,
  recruits 0.31 -> 0.21-0.24/patch-yr); TAB never matures (agb/stem ~500 flat, cover 0.44-0.46, recruits 0.34-0.37).
  (c) Biomass budget: death losses per patch are the SAME as truth (110-190/yr); the gap is GROWTH of big trees
  (>= 15 m: median dln agb 0.022-0.026 vs 0.026-0.030 from decade 2 on; summed survivor rate 2.9-3.6 % vs 3.1-3.8 %).
  (d) Input-swap attribution, recruit head on the original's stand with free-run inputs swapped in (gate: rebuilt
  inputs == stored SH13 features on the original, 0 mismatches, needs the SLA+Wooddens key): original 0.237 (obs
  0.249) · full free-run stand 0.353 (realised free run 0.33-0.40) · **cover only (sum_fpc + patch_lai) 0.343 = ~90 %**
  · everything except cover 0.223 · cell stem density alone 0.228 (NEGATIVE: crowding, no cell-level feedback) ·
  patch stem count alone 0.258 (a weak positive loop, ~10-25 % in context — watch it).
  ⇒ the head responds honestly to a canopy that is too open; the canopy is too open because big-tree growth is too
  slow in free run. ⚠ **Do NOT fix this with A7's recruit-count log offset** — that would hide the growth error behind
  a compensating recruit error (the ADR 0126 "two wrong parameters of opposite sign" trap).
  STRUCT is a different failure: recruits/patch are about right, but its trees DROP BELOW 5 m at 15x the original's
  rate (exit 0.03-0.04 vs 0.002/patch-yr) and stems/patch fall too fast (8.25 -> 6.04) while agb/stem overshoots.
  **NEXT, in order:** (1) TAB: find why big trees grow slower in free run than one-step — compare the growth head's
  inputs (its AR residual state e_dagb, G, c, the canopy features) free-run vs truth for >= 15 m stems, same swap
  method (`explore_de_recruit_attrib.py` is the template: rebuild from roster, gate against stored, swap groups);
  (2) A7 free-run calibration of TAB on TRAINING members only, with the recruit offset FROZEN at 0 until (1) is
  understood; (3) STRUCT: why its trees shrink below 5 m (height-from-agb closure?) + B4 acceptance + the
  growth-memory calibration; (4) cross-fit for all-52-block scoring (critic gap 1) so block-scale gates get power.
  Engine `submit` hard-codes the priority QOS (64-cpu user cap) — helpers ran its `run` command from their own
  standard/short arrays.
* **2026-10-02 (fourth session): the slow big-tree growth is mostly GRASS + the cell stem count, not the tree**
  [VERIFIED, ACCESS s1 Historical+ssp370, chunks 0-1 = 200 dev cells]. (a) One step ahead on the original's own
  held-out states the growth chain is only 0.000-0.0024/yr low for >= 15 m stems (median; pre-registered bar 0.004)
  — but its negative-growth-year probability is too high for big trees (0.11 vs 0.05 in the 1980s, 0.27 vs 0.22 in
  the 2040s) [`scripts/explore_de_growth_onestep.py` -> `shared/eval/growth_onestep_GCM.csv`]. (b) Instrumented
  re-run `scripts/explore_de_tab_probe.py:TabALProbe` (gate: its rosters == the analysed tabAL run, 120/120 files;
  dumped inputs reproduce the stepper's growth mean to 7e-9) + same-tree pairing with the original (2.01 M
  tree-years >= 15 m, climate columns identical) [`scripts/explore_de_growth_attrib.py` ->
  `shared/eval/growth_attrib_tabAL{,_shift}.csv`]. Median dln agb, 2010s: original realised 0.0285; chain on the
  original's inputs 0.0271 (one-step bias 0.0014); chain on the free run's inputs 0.0242 (input shift 0.0029);
  free run realised 0.0242 (sampling adds nothing). Swap one group in: GRASS -0.0026, CELL stem density -0.0023,
  own lagged G -0.0019; patch stand +0.0015 and previous growth +0.0015 push the other way (non-additive).
  **The grass under big trees is the striking drift:** original grass cover there falls to ~0 (median 0.0007 in the
  2010s, mean 0.18 -> 0.08), the free run's RISES (median 0.09, mean 0.19 -> 0.26). The A3 grass heads are a
  deterministic mean regression of next-year grass iterated forward — that cannot reproduce a bounded variable
  collapsing to 0. ⚠ This also qualifies the recruit attribution above: it held grass at the ORIGINAL's values.
  **CONFIRMED by counterfactual:** `TabALGrassOracle` (the same run, same random numbers, only the next-year grass
  replayed from the original's patch table) -> `shared/eval/recruit_drift_ssp370_grassreplay.csv`. Share of the
  free-run-vs-original gap it closes, 2026-2035 mean: stems/patch 57 % (9.84 -> 8.39 vs 7.31), recruits 79 %
  (0.355 -> 0.239 vs 0.207), agb/stem 54 %, stand agb 67 %, >= 15 m growth 61 % (0.0224 -> 0.0249 vs 0.0265),
  cover 85 %, deaths/patch 77 %. ⇒ **the free-run grass model is the largest single cause of the TAB drift**;
  what remains (>= 15 m growth still 0.0016-0.0026/yr low) is the one-step bias (~0.0014) + the cell stem-density
  shortcut + the model's own lagged G. Oracle = an upper bound on what a better grass model can give, not an arm.
  **NEXT, in order (supersedes the third session's list):** (1) a grass model that can collapse to 0: replace the
  A3 deterministic mean heads with a distributional one (P(grass = 0 | state) + magnitude + a residual draw, as the
  G sampler does), and test it in a GRASS-ONLY free run (trees replayed from the original, grass free) against the
  original's grass under big trees AND patch-wide before coupling it back; (2) `cell_stems_per_patch` in the tree
  heads is a cross-cell proxy, not a mechanism — retrain the G/growth heads without it and price the one-step loss;
  (3) the big-tree negative-G over-prediction (one-step); (4) only then A7 calibration, recruit offset still frozen
  at 0; (5) STRUCT shrink-below-5 m and the cross-fit for block scoring stay as listed above. All on 200 cells of
  one GCM/scenario so far — rerun the counterfactual on all 10 chunks before quoting it as general.
* **2026-10-02 (fifth session): a grass model that can collapse — it fixes most of the 2030s drift, but distorts
  the 1990s-2000s path** [VERIFIED, ACCESS s1; `scripts/explore_de_grass2.py` (model + grass-only replay),
  `scripts/explore_de_tab_g2.py:TabALG2` (TAB with it); pre-registration + results `_status/G2.md`; models
  `tab/models/DEV-A/grass2_*`; tables `shared/eval/grass2_replay_ACCESS-CM2_s1_ssp370*.csv|json`,
  `shared/eval/recruit_drift_ssp370_g2.csv`; runs `runs/_tabg2_{ar,m}`]. (a) Grass in the original is ONE number per
  patch: agb = 23.673 x LAI exactly; cover = 1-exp(-0.5 LAI) unless total cover is capped (~1/3 of patch-years);
  bimodal (30 % < 1e-3) and persistent in log space (corr 0.988). New model = next-year log LAI (two-stage boosted,
  residual draws), cover/biomass by that closure. (b) Grass-only free run on the original's own trees (907 cells,
  1985->2043): the OLD heads drift on their own (falsifier did not fire: grass under >= 15 m stems median 0.054 vs
  0.000, P(grass < 1e-3) 0.016 vs 0.484 in 2026-35); the new one passes every pre-registered gate in 1995-2004 and in
  2026-35 misses only the under-big-tree mean (0.090 vs 0.068). Its remaining error is the MEAN response to tree
  cover, too weak (too much grass in closed patches, too little in open ones). (c) Coupled TAB + new grass, 200 cells:
  2026-35 it closes 84-103 % of the stems / recruits / biomass-per-stem / stand-biomass gap and 55 % of the
  big-tree growth gap — better than the grass-replay counterfactual, which is therefore NOT an upper bound (it pasted
  the original's grass onto a different tree roster). ⚠ BUT 1991-2010 is wrong the other way: stems 5-8 % low,
  recruits ~15 % low, biomass per stem 9-11 % high — the stand matures too early and reaches the right 2030s state by
  a different path. Treat the 2030s agreement as partly compensating until the early path is fixed.
  **NEXT, in order (supersedes the fourth session's list):** (1) the early-maturation undershoot: input-swap
  attribution (template `explore_de_recruit_attrib.py`) on 1991-2010 for TAB+G2 vs the original — is it the open-patch
  grass deficit, or the recruit head's response to it? (2) the grass mean's weak cover response: candidate features
  (lagged grass change, the stepper's own sub-5 m trees' cover, which the original's grass also sees) — and ⚠ TUNE on a
  dev set that is NOT the test: use the training GCM's held-out place fold (MPI s1, fold 5) for the grass-only
  replay, keep ACCESS as the untouched test; (3) the remaining big-tree growth gap (~0.002/yr in the 2030s) = one-step
  bias + the cell stem-density shortcut: retrain the G/growth heads without `cell_stems_per_patch`; (4) then A7
  calibration, recruit offset still frozen at 0; (5) rerun on all 10 chunks + seed 2 + MPI before quoting anything
  as general; (6) STRUCT shrink-below-5 m and the cross-fit for block scoring stay as listed above.
* **2026-10-02 (sixth session): the early recruit shortfall is the grass COVER RULE erasing a hidden-sapling
  signal** [VERIFIED, ACCESS s1, 907 dev cells; `scripts/explore_de_recruit_grass.py` -> `shared/eval/recruit_grass_
  ACCESS-CM2_s1_ssp370{,_bins}.csv`; `scripts/explore_de_recruit_hidden.py` -> `recruit_hidden_ACCESS-CM2_s1.csv`;
  `scripts/explore_de_hidden_persist.py` (log only); pre-registration + results `_status/RG.md`]. (a) Coupled fact:
  the 1986 roster is identical across TAB arms, yet 1987 recruits are grass2 0.335 / grass replay 0.381 / old A3 0.406
  / truth 0.368 per patch => the grass alone. (b) Recruit head on the ORIGINAL's trees (gates exact: 0.0), grass
  swapped: grass2 one step ahead -0.066 / -0.107 / -0.111 / -0.092 relative in 1985-89 / 90-94 / 95-99 / 2000-04
  (-0.10..-0.16 on the coupled 200 cells), shrinking to 0 by 2015 and +0.06..+0.10 after 2025; the grass-only free run
  gives the same within 0.01 => one-step error, no accumulation. (c) Keeping the original's own grass LAI/biomass and
  replacing ONLY grass cover by grass2's closure of that LAI reproduces it in full (-0.108; no cap at all -0.533).
  (d) Why: where total cover is capped (35 % of patch-years) the original's grass cover = 1 - tree cover - the patch's
  OWN cover of unprinted < 5 m trees, and those are next year's recruits. In the truth, at matched tree cover, recruits
  rise 3-4x across quartiles of that implied hidden cover h (tree cover 0.4-0.5: 0.13 -> 0.51 per patch-yr); the head
  learned it; grass2 uses a per-bin median, which flattens and inverts it. h drains when recruits appear (mean change
  +0.006 / -0.006 / -0.020 / -0.041 for 0 / 1 / 2 / 3+ recruits) but is noisy year to year (corr 0.12); capped status
  persists (0.94). ⇒ **the sub-5 m layer is a real hidden state, the old grass heads leaked it in through grass cover,
  and any grass model with a closure removes it.** The 2030s "agreement" of TAB+grass2 is then partly a compensating
  error (late positive bias of the same channel).
  **NEXT, in order (supersedes the fifth session's list):** (1) DESIGN, then test in replay: give the emulator an
  explicit hidden-sapling cover per patch (grows each year, drained by recruits, bounded above by 1 - grass pot cover
  - tree cover where uncapped, observed where capped), let the recruit head read IT instead of grass cover, and keep
  grass2 for grass. Retrain the recruit head with h (and without grass fpc) on training members; score one-step
  first, then the recruit-only replay on the original's trees, then coupled. ⚠ Do not "fix" it by putting the
  original's grass-cover noise back into grass2 — that re-hides the state. (2) Then the remaining fifth-session items:
  the grass mean's weak tree-cover response (may be the same cap channel: check closed-patch grass vs h first), the
  `cell_stems_per_patch` retrain, A7 with the recruit offset frozen at 0, all-10-chunks + seed 2 + MPI, STRUCT
  shrink-below-5 m, cross-fit for block scoring. Still one GCM, one seed.
* **2026-10-03 (seventh session): the hidden < 5 m layer is worth carrying, and carrying it exposes a grass error
  that a compensation had been hiding** [VERIFIED, ACCESS s1 unless stated; pre-registrations + results
  `_status/HR.md`, `_status/HS.md`; scripts `explore_de_recruit_nofpc.py`, `explore_de_hidden_cover.py`,
  `explore_de_tab_g2.py:TabALG2HS`, `explore_de_grass_diag_truth.py`]. C fact: after establishment, if total
  cover > 1 every grass fpc is divided so grass = 1 - ALL tree cover (`establishmentpft_ind.c:197-204`;
  `reduce_grass.c` touches fpc only). (a) Recruit head WITHOUT grass cover: 5.2 % worse deviance (13 % of what it
  explains over a constant), +4.3..+5.4 % on every ACCESS leg; grass2 then biases it only +-0.01 after 1990 (+0.054
  in 1986-89). Adding the TRUTH's last-year hidden cover back closes 70-73 % of that gap on every member; the
  emulator's own recruit history closes 0.2-1.8 % => the signal persists, so an explicit state is worth building.
  (b) Why it persists despite a lag-1 corr of 0.12: TOTAL tree cover (printed + hidden) is nearly conserved year to
  year; cover just moves between the labels as trees cross 5 m (next-year h is 76 % "minus the printed-cover
  change"). (c) HS = two-part model of next year's cap (P(cap) + log bite, residual draws), carrying the patch's own
  previous grass cover. One step ahead on the original's trees: head bias -0.021..+0.012 in every window, 85-89 %
  of the closure's lost information recovered, P(cap) within 0.001. A direct-h parametrisation: 91 %, but -0.031
  in 1990-94 (fails the bar). (d) Grass-only free run FAILS (-6..-9 % early, +5..+11 % late) but is the wrong test:
  it drives the carried state with the original's recruits. (e) COUPLED TAB + HS, 200 cells: early recruit deficit
  fixed (1996-2005 -6 % vs -15 %) but +15..+27 % too many recruits from 2006 on and stems +14..+16 % by the 2030s
  (bars FAIL). (f) Diagnosis (re-run of 100 cells with a grass log; reruns reproduce the scored rosters exactly):
  HS's hidden cover runs ~15-25 % high after 2010, but the bigger cause is in BOTH coupled arms: grass leaf area
  does not decline as in the original (truth 3.08 -> 1.13-1.35, emulator 2.7 -> 1.8-2.1), so 0.34-0.42 of patches
  stay capped vs 0.18-0.24 and grass cover is +60-80 %. ⇒ the current arm's near-right late recruitment is a
  COMPENSATION (too much grass + the median closure); HS reads the same wrong grass more faithfully.
  **NEXT, in order (supersedes the sixth session's list):** (1) input-swap attribution of grass2's next-year LAI
  on the coupled emulator state vs the original's (template `explore_de_recruit_attrib.py`; candidates stand
  biomass, stem counts, loss history, recruits) — the grass-only replay on the original's trees is already +27 %
  on these cells in the 2020s, coupled +75 %, so check both the grass model's own response to tree cover (fifth
  session's finding) and what the emulator's trees feed it; (2) only then re-score TAB + HS coupled (bars in
  `_status/HS.md`); keep the HS bite parametrisation; (3) the HS hidden cover's own ~15-25 % late excess; (4) the
  tree heads ALSO read grass8_fpc_y (G / growth / death), so the same hidden-layer channel enters tree growth —
  price it after (1); (5) then the fifth/sixth-session items (`cell_stems_per_patch` retrain, A7 with recruit offset
  frozen at 0, all 10 chunks + seed 2 + MPI, STRUCT shrink-below-5 m, cross-fit). Still one GCM, one seed, 200 cells.
* **2026-10-05 (eighth session): the coupled grass excess on ACCESS is a CLIMATE-MODEL TRANSFER failure of the grass
  model, not the emulator's trees; on MPI weather the carried hidden-cover design works** [VERIFIED; pre-registrations
  + results `_status/GA.md`, `_status/HS.md` (last two sections); scripts `explore_de_grass_attrib.py` (grass-only
  replay along either tree history, GATED to reproduce the coupled run's own grass log exactly: the engine's random
  stream is keyed on (arm, rep, gcm, stream, year, cell, patch), so any coupled run's grass state can be rebuilt from
  its rosters — no re-run needed), `explore_de_grass_onestep.py`, `explore_de_grass_climrange.py`;
  `explore_de_recruit_drift.py` now takes `--gcm/--seed`]. (a) ACCESS s1, 200 cells: grass2 on the ORIGINAL's trees
  already carries ~87 % of the coupled LAI excess after 2016; the emulator's trees ~13 % (falsifier fired). Group swaps
  were uninterpretable (patches are different stands after 1985) and are not used. (b) Under a closed canopy grass2 is
  ~right one step ahead in LAI but biased -0.11/yr in log space after 2006 on ACCESS, flat across stand biomass, loss
  history and hidden cover: it is weather — a few warm bad years (2008, 2012, 2035, 2041 = -1.04) crash grass in the
  original more than predicted, and a near-zero grass state ratchets. (c) Same check, MPI s2 (training weather, new
  trees): +0.007/yr, 5-step within 4 %; MPI s1 ssp245 (weather years never seen): +0.020/yr, but yearly error x3
  (sd 0.14 vs 0.05 — part of the weather response is memorised years); ACCESS -0.129/yr, sd 0.24. ACCESS's bad years
  are mostly INSIDE the training weather range (only 2035, 2041 partly outside). (d) COUPLED on MPI s2: grass within
  13 % of truth every decade; carried hidden cover (g2hs) vs closure (g2ar): 1991-2010 recruits -6.7 % vs -12.3 %
  (bar +-5 %: narrowly FAILS), stems -2.1 % vs -4.1 %; 2026-35 stems -0.4 %, recruits +5.5 %, biomass/stem +5.4 %
  (PASS); NO late over-recruitment (max +6 %) => the ACCESS +15..+27 % was the ACCESS grass. ⚠ MPI s2 shares the
  training GCM's weather: this is "new trees, familiar weather", not a transfer test.
  **NEXT, in order (supersedes the seventh session's list):** (1) the tree-side early maturation that remains in BOTH
  arms on MPI s2 (biomass/stem +8..+17 % in 1996-2025, deaths -7..-14 % in 2006-2025) — same input-swap method on the
  growth and death heads (templates `explore_de_growth_attrib.py`, `explore_de_tab_probe.py`), on MPI s2 so the GCM
  transfer cannot contaminate it; it plausibly carries the residual recruit deficit. (2) The cross-GCM weather
  transfer of grass2 (and check the TREE heads for the same: they are MPI-trained too): does the original respond to
  the same weather anomaly more strongly in ACCESS than in MPI (=> a missing input: absolute temperature level,
  daily extremes) or is it a booster limitation (=> fewer / smoother weather inputs, monotone constraints)? Tune only
  on MPI held-out weather (ssp245) — ACCESS stays the untouched test. (3) adopt g2hs (bite) as the TAB grass-cover
  default once (1) is understood; (4) then the older items: `cell_stems_per_patch` retrain, A7 with the recruit
  offset frozen at 0, all 10 chunks + seed 2, STRUCT shrink-below-5 m, cross-fit for block scoring.
* **2026-10-05/06 (ninth session): the tree-side early maturation is NOT a small-tree growth bias after 2000; it is
  an early G-state drift + a big-tree hazard deficit** [VERIFIED; `_status/TS.md` has every number + pre-registrations].
  (a) One-step on the original's states (`explore_de_tree_onestep.py` -> `shared/eval/tree_onestep_*.csv`): growth
  heads +0.0016/+0.0022 per yr high for < 10 m stems in 1985-94 only, death rate 0.98-1.02, dead-tree size right.
  (b) Same-tree input-swap attribution on the instrumented coupled run (`explore_de_tab_probe2.py`, job 2407363;
  `explore_de_tree_attrib.py`, job 2420297 -> `shared/eval/tree_attrib_g2hs_mpi2{,_shift}.csv`; all three gates
  pass): on trees living in both runs (0.33 of the free run) the < 15 m growth gap is +0.0016 in 1985-94, carried by
  the tree's own last-year G (G_y free median 34.3 vs 30.7; "only G_y" 144 %, "all except G_y" closes 88 %) — GRASS
  carries none of it (the pre-registered prediction FAILED); ~0 after 1995 with large offsetting input shifts. No
  hazard deficit for small trees; >= 15 m hazard 0.88 of truth in 1995-2004 and 0.87 in 2035-44, no single carrier.
  (c) Cohort x size decomposition (`explore_de_recruit_drift.py` now splits < 15 m survivors INITIAL/ENTRANT x
  height bin; `shared/eval/recruit_drift_ssp370_g2_mpi2_coh.csv`, `smallgrowth_cohort_decomp_g2_mpi2.csv`): the
  composition term is <= 0.0001 everywhere; the MEAN small-tree growth gap is +0.0014/+0.0035/+0.0013 in 1986-2000
  (within initial trees) and |<= 0.0022|, sign-changing after; the persistent +0.002..+0.003 quoted earlier is a
  MEDIAN artefact: the free run's small-tree growth is less right-skewed (too few very fast years).
  (d) Sapling re-runs of the original (every tree printed; private Dec-2025 binary + LPJ_IND_ALL_HEIGHTS; owner
  instruction 2026-10-05 above in the ninth-session record of git history): campaign = cells 0-2239 in 7 blocks of
  320 on 64 tasks for MPI s1 {Historical, ssp126, ssp370}, MPI s2 {Historical, ssp370}, ACCESS s1 {Historical,
  ssp370}. ⚠ **[VERIFIED] a re-run spread over nodes of different processor types does NOT reproduce production**
  (23/23 single-type runs pass the row-by-row gate, 21/23 mixed fail, 3/3 out-of-sample predictions right; CLAUDE.md
  §3). 16 runs PASS and are in `/p/tmp/jamirp/X_de/ind_all/<gcm>/<scen>/s<seed>/<win>/c<a>-<b>.parquet` (29 cols +
  `in_prod`); the other 26 were resubmitted with `--nodes 1` 2026-10-06 (`_jobs/crerun_rerun1node_jobs.txt`; moved
  from priority to standard because priority caps 64 cpus PER USER). Collection is CHAINED to start after all of them (job 2420688, afterany); if it is gone, check `logs/X-crr-collect.2420688_*.out` and each run dir's `gate.json`, else rerun: `sbatch --cpus-per-task=32
  --time=04:00:00 _jobs/crerun_collect.jcf` (idempotent; gates every year; deletes the CSV only on PASS; now reads
  only the newest log). Earlier fixes: the Historical config generator cut at an `#else` inside a comment (fixed).
  **NEXT, in order (supersedes the eighth session's list):** (1) the G sampler's early drift — why the free run's
  G_y runs 12 % above truth in 1985-94 when the one-step G draw is unbiased later (check the first years: the
  initial-state G_y vs the sampled one, and the residual pool by size); (2) the >= 15 m hazard deficit on shared
  trees (0.87-0.88 in two windows) — joint inputs, try a two-group swap of LAGGED_OWN + stand; (3) the narrow
  small-tree growth distribution (residual draw / AR sigma — compare the free run's per-tree growth quantiles with
  truth's); (4) once the re-runs are collected: use the < 5 m trees to replace the hidden-cover proxy with the
  real sapling layer (the seventh-session design question); (5) the eighth-session items (cross-GCM grass weather
  transfer, g2hs as default, cell_stems_per_patch retrain, A7, all 10 chunks + seed 2, STRUCT, cross-fit).
* **2026-10-06 (tenth session): the early growth-efficiency drift is the SAMPLER'S SHAPE, half one step ahead and half
  amplified by feeding it its own draws** [VERIFIED, MPI s2, 200 dev cells; `_status/TS.md` last two sections;
  `scripts/explore_de_gdrift.py` -> `shared/eval/gdrift_g2hs_mpi2_*.csv`, `scripts/explore_de_gpit.py` ->
  `shared/eval/gpit_mpi2*`]. (a) Start is exact (466 979 paired trees, G identical in 1985). (b) < 15 m median next-year
  G, 1985-94, model/truth - 1: one step ahead on the original's inputs +6.2 %, G-only chain on the original +13.0 %,
  the free run +14.7 % — the means only +1.8 / +3.4 / +6.6 %, q25 LOW => a shape error, not a level error; other drifted
  inputs add little (swap: G_y alone 96 %). (c) Exact PIT of the original's next-year G under the sampler: share below
  the sampler's median 0.543 in 1985-94, drifting to 0.47-0.50 after 2015; by previous-G decile 0.46..0.67..0.29 —
  the LOCATION of the conditional distribution bends wrongly with the previous G (spread is about right everywhere);
  plus a year-common shock (sd 0.06 of that share, range 0.36-0.66) that the climate inputs do not carry even though
  this member shares the training member's weather years; beech carries the excess, ids 1/2/4 go the other way.
  Sapling re-runs: 24 of 49 blocks collected and gated (`ind_all/`); **the other 25 were CANCELLED at 07:00 on
  2026-10-06 by the owner's own account while still pending** (not by this line) — resubmission is the owner's call
  (`_jobs/crerun_rerun1node_jobs.txt` lists them; collector `scripts/explore_de_crerun_collect.py` now skips never-run
  blocks instead of crashing).
  **NEXT, in order (supersedes the ninth session's list):** (1) a distributional magnitude model for G: LightGBM
  quantile heads for log|G| (~9 levels, Type-aware, previous G and weather as inputs) replacing the pooled residual,
  trained on training members only; gate = PIT share < 0.5 within 0.50 +- 0.02 in every previous-G decile one step
  ahead on MPI s2, then the G-only chain (`explore_de_gdrift.py` S3) within +-3 % in median AND mean, only then coupled;
  measure how much of the year shock it removes before chasing that; (2) the >= 15 m hazard deficit on shared trees;
  (3) the narrow small-tree growth distribution (likely the same shape defect one level down — re-check after (1));
  (4) sapling layer from the collected re-runs (ask the owner about the 25 cancelled blocks); (5) the eighth-session
  items (cross-GCM grass weather transfer, g2hs as default, cell_stems_per_patch retrain, A7, all 10 chunks + seed 2,
  STRUCT, cross-fit).
* **2026-10-06 (eleventh + twelfth sessions): a quantile model of next-year G fixes the sampler's shape; the chain gate
  still fails by ~1 point; coupled run submitted** [VERIFIED, MPI s2 one step / G-only chain, 200 dev cells;
  everything in `_status/TS.md` from "a DISTRIBUTIONAL G-magnitude model" on]. `scripts/explore_de_gquant.py`: 11
  LightGBM quantile heads per sign (models `tab/models/DEV-A/gquant/`), arms gq (as fitted) / gqc (validation-fold
  conformal offsets) / gqs (+ Platt-recalibrated sign head, `sign_platt.json`); stepper class `TabALG2HSGQ` (+ `Probe`);
  scorers `explore_de_gpit.py` / `explore_de_gdrift.py --sampler gq|gqc|gqs`. (a) Calibration by previous-G decile:
  0.29-0.67 (old) -> 0.465-0.530 (gqs); gate +-0.02 FAILS in 1-3 deciles. Sharpness: pinball -30..-40 % in every group
  (PASS). Year shock sd ~1/3 smaller. (b) FOUND: the sign head was badly under-confident (predicted 3.3 % -> observed
  0.7 % negative G) with the errors cancelling in the mean, which is why every earlier check called the sign right;
  Platt a = 1.47 fixes it to 0.93-1.08 per bin. (c) G-only chain, < 15 m median / mean: old +13.9 / +3.4 % ->
  gqs -3.7 / -2.6 % (1985-94), gate +-3 % FAILS narrowly; loop gain 2.1-2.5 in every arm => needs one-step error
  within ~1.3 %. (d) Cost 13x the old magnitude head (1 820 vs 140 us/tree single thread) — fidelity test only.
  (e) COUPLED gqs run despite the failed gates (deviation pre-registered; job 2425236, `runs/_probe2_g2hsgqs_mpi2`
  + dump; scored `shared/eval/recruit_drift_ssp370_gqs_mpi2.csv`, `gpaired_gqs_vs_g2hs_mpi2.csv`): early small-tree G
  drift 1985-94 +16.4 % -> -2.7 % (median), biomass/stem excess 1996-2025 +7.6..+13.4 % -> +2.3..+5.0 %, stems within
  1 % to 2025 (was -4.9 %), recruit deficit halved; the ninth session's attribution holds. Remaining: (i) small-tree G
  now drifts LOW from 1995 (-9.0 % median, -5.4 % mean in 1995-2004); (ii) 2016-25 deaths -7.7 % (separate big-tree
  hazard item); (iii) 2036-44 stems +4.1 %, stand biomass +5.3 %. Cost 4.7-5.0 core-s/cell-year incl. the dump
  (old 1.28): no longer cheaper than the original's ~12 by a margin worth having until shrunk.
  (the (e) NEXT list that stood here is merged into the thirteenth-session list below.)
* **2026-10-06 (thirteenth session): the other three designs, and three failed attempts to make the quantile G
  model cheap** [all pre-registered in `_status/` before running; reports in `_reports/`]. Owner, verbatim: *"work on
  the other emulator methods while this is running"*.
  (a) **Quick LSTM (C0)**, `scripts/explore_de_rec_lstmstats.py`, `_status/C0.md`, `recurrent/lstmstats/`: a cell-level
  2x64 LSTM over yearly cell statistics + climate, trained on MPI s1 only, 5-fold block cross-fit. Held-out places,
  held-out GCM (ACCESS): from the 2014 truth 0.97-0.98 of fold-5 cells pass (persistence 0.33-0.48, other-seed
  ceiling 0.92-0.93); from 1985, 2015-44 cells 0.79-0.91 (lookup 0.06-0.10, TAB 0.34-0.46, STRUCT 0). Emits no trees and
  has no sampling noise (not equal footing). Climate: beats its frozen-climate twin by 0.04-0.16 from 1985, not from
  2014; collapses on resampled historical weather (partly warming-as-clock); the ssp370-ssp126 block contrast FAILS
  for every arm (0.31 vs 0.46 for "no difference"; the two scenarios differ by +0.015 K here). Cost ~2.4e-6 core-s.
  The window aggregation was changed (log-space mixture) after the first scores, because the truth replay failed;
  it applies to every arm, old scores kept.
  (b) **Neural set model (SH11 + D1 + D2)**, `scripts/explore_de_sh_tensors.py`, `explore_de_nset_{model,train,stepper}.py`,
  tensors `shared/tensors/dev/` (98 GB, 5 members), `nset/`, `_status/SH11.md`, `D.md`: tensors round-trip exactly;
  unit checks pass; stage 1 on one H100 (~1 h per arm, still improving). Stage-2 gate PASSES on paper but has no power
  (one-step death Brier beats the rule hazard by 0.001 %; the +-50 % stems test is passed by a frozen roster too).
  30-yr free run from 2014: stems 0.87 x truth (19 % of cells within +-10 %; ACCESS fold 5 0.91, 67 %); deaths right
  incl. 2018; recruits ~30 % short after year 1 — replaying the original's grass removes it (the same grass-closure
  defect TAB had). Poor transfer of the continuous heads to ACCESS. Stage 2 NOT started.
  (c) **STRUCT diagnosis (SD)**, `scripts/explore_de_struct_*.py`, `_status/SD.md`, `struct/accept/`: on ACCESS s1, 200
  cells. "Biomass 2x" was the per-cell MEDIAN tree (stand biomass right to ~4 %); the real failure is a stem deficit of
  trees < 10 m, caused by the recruit kernel with no acceptance step (wrong type mix / trait tails enter at 5 m, bad
  years 2-6x, drop below 5 m or die). Fix arm `acc` = no-shrink height rule + a B4-lite acceptance classifier trained
  on MPI s1 ssp370 only: closes 106 % of the 2026-35 stem gap (7.37 vs 7.31, base 6.21), 33 % of the median-tree gap;
  size SHAPE still wrong (too many 10-20 m trees), recruits/deaths ~20 % low. Also: two same-seed runs of one
  stepper DIFFER (262 of 425 427 rows in 1986, <= 0.01 stems/patch); the helper blamed the PatchHeads entry-table
  group_by — made ordered anyway, but NOT confirmed (old split identical in 5 repeats and at 1-16 threads on the
  login node) => the source of run-to-run noise is OPEN; "same random streams" comparisons carry it.
  (d) **Coupled gqs** (scored twice, independently; both in `_status/TS.md`): P1/P2/P4 pass, P3 fails; small-tree G
  now -9 % median in 1995-2004; cost 4.7-5.0 core-s/cell-year. **Cheaper G model: three attempts, all FAIL** (TS.md
  SYNTHESIS): truncation/fewer levels best 1.007-1.009 x pinball at 0.70 x cost; residual start `rq` 1.12-1.23 x at
  0.26-0.30 x (confounded: 5x fewer rows); distillation `dq` 1.29-1.41 x and coverage off by 0.19. gq's raw quantiles
  cross in 51-65 % of held-out rows. Code: stages shrink / r* / d* in `scripts/explore_de_gquant.py`.
  (e) ⚠ **ALL of the owner's SLURM jobs were cancelled at 18:42:34** (incl. ~30 `globN-*` jobs from another project) —
  not by this session or its helpers. The coupled `rqs` run (pre-registered in TS.md, `_jobs/probe2_g2hsrqs_mpi2.jcf`
  + `score_g2hsrqs_mpi2.jcf`, env GQ_TAG=_res) died with it at year 2001; NOT resubmitted pending the owner.
  **NEXT, in order:** (1) if the owner agrees, resubmit the coupled `rqs` run: does the coupled model need gq's last
  12-23 % of pinball? (pass => rq is the working G model at ~1/3 the cost); (2) if it fails: ONE network with 22
  monotone outputs, pinball loss, all rows (the neural-set GPU tooling exists); (3) the second-decade LOW small-tree G
  drift (1995-2004 -9 % median): magnitude loop vs the sign head's G_y-shaped error; (4) the >= 15 m hazard deficit
  (2016-25 deaths -7.7 %) and the late biomass excess; (5) GRASS is now the shared failure of three designs (TAB fixed by
  grass2; NSET recruits -30 %; STRUCT frozen grass): port grass2 into NSET, then NSET stage 2; (6) STRUCT: the size
  shape with acceptance on, acceptance without no-shrink, other members, fold-5 scoring; (7) the LSTM's response: the
  block contrast has no power in 2015-44 — it needs a longer clean window (a 2045-2070 ind table or a rerun of the
  humidity-defective 2071-2100 segments: owner's call); (8) sapling layer (25 cancelled blocks: owner's call); (9) the
  eighth-session items (cross-GCM grass weather transfer, g2hs as default, cell_stems_per_patch retrain, A7, all 10
  chunks + seed 2, cross-fit). Still mostly one GCM, one seed, 200 cells.
* **2026-10-06 (fourteenth session): the 2016-25 death deficit is the original's CERTAIN-KILL PULSES, under-amplified**
  [VERIFIED, MPI s2 ssp370 leg, 200 dev cells; every number + pre-registration in `_status/TS.md` from "WHERE the
  2016-25 death deficit sits" to "RESULT the emulator's own certain kills"].
  (a) Owner said "continue" => resubmitted the coupled `rqs` run on `standard` (the owner's own `globN` jobs fill
  `priority`): job 2427029, both chunks clean, **2.0-2.1 core-s per cell-year** (gqs 4.7-5.0, old 1.2-1.3; dump on).
  (b) `explore_de_death_decomp.py`: gqs 2016-25 deaths -7.9 % = rate term, 80 % of it trees of 5-10 m; the ">= 15 m
  hazard" label was WRONG (pre-registered D1 failed, falsifier fired). `explore_de_death_pulse.py`: the deficit sits in
  the original's PULSE years (2019, 2025, 2031, 2010, 2015, 2020, 2026); pulses are diffuse, not patch clearings/fire.
  (c) `explore_de_death_terms.py` + C source (`mortality_tree_ind.c:129-143`): the `ind` column `mort` = min(1, sum of
  the four hazards), then SET TO 1 by two certain-kill rules (5 consecutive negative-growth years; leaf carbon below a
  sapling's). Certain kills carry **101 %** of the pulse rise (< 10 m: 0.0355 pulse vs 0.0113 quiet; Bernoulli deaths
  flat at 0.019); the four hazards are nearly flat. **The emulator's certain kills (counter c1 >= 5) track the
  original's year to year (r 0.89) but each pulse is ~1/3 too small (2019 0.036 vs 0.056) and quiet years run slightly
  high; its non-certain death is right. Its negative-growth share has NO pulse signal (0.143 vs 0.146).**
  ⇒ the pulse is synchrony of bad-growth years across trees, which the per-tree G-sign draw lacks (the same
  year-common shock the tenth session found in the G magnitude).
  **PENDING on `standard` (estimated starts 2026-10-07 10:37-13:37, owner's jobs fill `priority`):**
  2427030 = rqs scorer (pre-registered R1-R3 in TS.md), 2427035 = 1995-2004 swap attribution of the low small-tree G
  drift (W0/W1/H1/H2), 2427045 = one-step death on the original's states (E1/E2 + truth vs sampled negative-G and
  counter >= 5 shares per year — the direct test of the synchrony reading).
  **NEXT, in order:** (1) read the three jobs against TS.md and record verdicts; (2) if 2427045 shows the sampled
  negative-G share lacks truth's year swings while tf (true G, true counter) reproduces the pulses: design a
  YEAR-SHARED latent for the G sign (and magnitude) draw — e.g. a per-cell-year common uniform mixed into each tree's
  sign draw, its strength fitted on training members from the between-year variance of the negative-G share given the
  climate inputs; pre-register: pulse-year certain kills within +-15 % and quiet-year over-kill removed; (3) by the
  rqs verdict: pass => rq is the working G model; fail => the single monotone network; (4)-(9) as in the thirteenth
  session's list (grass into NSET, STRUCT size shape, LSTM response window, sapling layer, eighth-session items).
* **2026-10-06 (fifteenth session): the pulses are STREAK CONTINUATION, and the sign head is mis-calibrated by
  counter** [VERIFIED, MPI s2 Historical+ssp370, 200 dev cells; everything + pre-registrations in `_status/TS.md` from
  "WHICH certain-kill rule makes the pulses" on]. (a) Correction of the fourteenth session: the counter IS recoverable
  (trans `c_y`/`c_y1`), so the two certain-kill rules are separable: the 5-bad-years COUNTER rule carries 100 % of the
  pulse rise, the sapling-leaf-carbon rule fires on 0 trees (`explore_de_certain_rule.py`). (b) Truth's same-year
  negative-growth share does NOT pulse (0.146 vs 0.147) => the planned "year-shared latent in the G-sign draw" is
  WRONG and was not built. What pulses is the c = 4 pool a year earlier (0.041 vs 0.015). (c) `explore_de_streak.py`:
  the coupled gqs run STARTS streaks right (0.065 vs 0.061, yearly corr 0.94, same sd) but CONTINUES them too rarely
  after year 1 (p1 0.56 vs 0.63; chain to 5 = 0.32 vs 0.39), most in the high-continuation cohorts that make the
  2019/2025/2031/2038 pulses. (d) One step on the original's states (job 2427208): deaths and certain kills are RIGHT
  (pulse 0.0555 vs 0.0552); continuation P(G<0 | c_y = 1) 0.579 vs 0.630 while starts run high (0.067 vs 0.062) — the
  errors cancel in the all-tree share, which is why every earlier sign check passed. Same pattern in the training OOF.
  (e) Fix arm **gqsc** = Platt per counter c_y = 0..4 (`explore_de_gquant.py signc`, `sign_platt_c.json`; OOF
  log-loss 0.1027 -> 0.1016); sampler option `sign_cal="c"`. Pre-registered C2 (one step) / C3 (coupled) in TS.md.
  (f) rqs (cheap residual quantile model) coupled: R2 FAILS (biomass/stem +5.8 / +9.7 / +8.6 % in 1996-2025, bar
  +-6 %), R3 passes => not the working model; R1 from job 2427211. (g) Queue: 32-core 2-3 h jobs were not being
  scheduled on `standard` while 8-16-core ones start at once — submit at <= 16 cores.
  **RESULTS later the same session (all in TS.md):** C2 one step PASSES on means (c1 0.561 vs truth 0.574 all trees;
  < 10 m 0.621 vs 0.630, was 0.579), but C3 coupled FAILS: pulse-year certain kills < 10 m -24.7 % (gqs -26.3 %),
  2016-25 deaths -6.9 % (gqs -7.7 %); quiet years, biomass/stem and stems 2026-35 still pass. Reason (one step on the
  original's states): the corrected head is right on AVERAGE but its year-to-year continuation is COMPRESSED (slope
  0.78, corr 0.84) — low in exactly the pulse cohorts' second years (2016 0.78 vs 0.85, 2022 0.77 vs 0.88). A
  per-counter weather scale (gqsc2) does not move it (OOF slope 0.851 -> 0.861; falsifier fired). rqs: R1 PASS
  (+3.7 / +1.4 %), R2 FAIL, R3 PASS => not the working model. 1995-2004 small-tree undershoot (swap job): 53 % of the
  median gap is the G magnitude's own autoregressive loop (H1 pass), no single stand/grass input carries the rest.
  **NEXT, in order:** (1) explain truth's yearly streak continuation (the breadth of the start year is a candidate:
  2026 p1 0.10 after the huge 2025 start cohort vs 2016 0.84 after 2015), then RETRAIN a continuation sign head for
  c_y >= 1 with the inputs that carry it; pre-register on the one-step yearly slope (>= 0.90 on MPI s2) + the four
  pulse-cohort second years, then the C3 bars coupled; (2) keep gqsc as the sign calibration meanwhile (it is not
  worse anywhere and fixes the counter means); (3) the cheap G model: single monotone network (rq failed R2, but its
  second-decade undershoot is smaller — compare loop gains); (4)-(8) as in the thirteenth session's list (grass into
  NSET, STRUCT size shape, LSTM response window, sapling layer, eighth-session items).
* **2026-10-06/07 (sixteenth session): the sign head's year-to-year skill was MEMORISED WEATHER YEARS; on unseen
  years it is corr ~0.78 and no stopping rule or streak term raises it** [VERIFIED; every number + pre-registration in
  `_status/TS.md` from "WHAT CARRIES truth's yearly streak continuation" on; `scripts/explore_de_contin.py`,
  `scripts/explore_de_gsign_yb.py`; tables `shared/eval/contin_*.json|csv`, `death_onestep_{gqsk,gqsy}_*.csv`,
  `death_onestep_gqsc_{acc1,mpi1_245}.csv`]. (a) The continuation residual follows the weather of the streak's START
  year (dry/bright start -> recovery); cell-year streak breadth carries nothing (B1 +0.007). (b) A streak x weather
  booster lifted the yearly c_y = 1 slope 0.851 -> 0.965 under a cross-fit by CELL — but under a cross-fit by YEAR it
  stops at 1-54 rounds and scores 0.833: every cell of a member-year shares Germany's weather, so a cell cross-fit
  leaks the year. Low-capacity variants fail too. Its coupled run was cancelled. (c) One step on weather years never
  trained on, the SHIPPED sign head's yearly corr (starts / all-tree negative share / c_y = 1) is 0.98 / 0.98 / 0.90
  on MPI s2 (shares MPI s1's weather years) -> 0.78 / 0.78 / 0.69 on MPI s1 ssp245 (same GCM, unseen years) ->
  0.57 / 0.63 / 0.60 on ACCESS (0.51 / 0.43 / 0.49 in its 2015-44). Means stay right. (d) Mechanism of the
  memorisation: every two-stage head early-stops its weather booster on held-out CELLS of the SAME years. Refitting
  gsign's B1 with YEAR-held-out stopping (arm gqsy) stops at median 43 rounds instead of 400 and removes the
  memorised skill (MPI s2 0.98 -> 0.90) but barely raises unseen-year skill (ssp245 0.775 -> 0.790, ACCESS 0.627 ->
  0.621) and damps the swings further => not adopted; the limit is the transferable INFORMATION in the annual
  weather anomalies, not the stop. ⚠ Consequence: every yearly-timing number scored on MPI s2 (incl. the C3 pulse
  deficit, -25 %) was on trained weather years; the pulse deficit on unseen years is unmeasured and likely larger.
  **NEXT, in order:** (1) MEASURE on unseen weather: rerun the coupled gqsc arm on MPI s1 ssp245 (same GCM, unseen
  years; `_jobs/probe2_g2hsgqsc_mpi2.jcf` with --seed 1 --legs ssp245 + the scorer) and on ACCESS s1, and score the
  pulses / deaths / stems there — that is the honest baseline every later fix must be scored against; (2) the
  information ceiling: a YEAR-level cross-validated regression of the member-year negative-growth share (and c_y = 1
  continuation) on (a) the current annual anomalies and (b) richer seasonal/monthly drought + temperature features
  from the daily forcing (the C decides growth from daily water/temperature) — if (b) beats (a) out of year, rebuild
  the weather inputs of all heads; (3) more weather years: a held-out-SCENARIO split (train Hist + ssp126 + ssp370 of
  BOTH GCMs' seed 1, test ssp245 of both) doubles the training weather years — costs the held-out-GCM test, decide
  after (2); (4) adopt year-held-out early stopping for every weather booster anyway (it removes the inflation of
  in-year scores; scores must then be on unseen years); (5)-(9) as before (cheap G model, grass into NSET, STRUCT size
  shape, LSTM response window, sapling layer, eighth-session items). gqsc stays the sign calibration.
* **2026-10-07 (seventeenth session): honest baseline on unseen weather, and WHERE the year-to-year bad-growth swing
  lives** [VERIFIED; every number + pre-registration in `_status/TS.md` from "the HONEST BASELINE" on; scripts
  `explore_de_{unseen_score,gsign_info,monthly_oracle,negG_npp,phenlatch,bmdelta,nppmodel}.py`; tables
  `shared/eval/{unseen_score,gsign_info_*,monthly_oracle_*,negG_npp_yearly,phenlatch_*,bmdelta_yearly,nppmodel_yearly}`].
  (a) HONEST BASELINE, coupled gqsc, 200 cells, pulse years = each member's own 8 truth-highest < 10 m certain-kill
  years 2016-44: MPI s2 (seen weather) pulse -19 % / quiet +3 % / timing corr 0.93; MPI s1 ssp245 (unseen yrs) -25 % /
  +14 % / 0.79, stand bars still pass (biomass/stem +2.5..+4.7 %, stems +2.8 %), deaths 16-25 -6 %; ACCESS s1 ssp370
  -32 % / +30 % / 0.51 AND the stand drifts (stems +11..+14 %, biomass/stem -13 % by 2016-25, deaths +8.6 %).
  (b) The original's yearly bad-growth swing is ~100 % WEATHER: its two seeds on identical weather agree at corr
  0.996-0.9999 (Germany yearly) and 0.94-0.98 per cell-year. Ceiling ~1, emulator ~0.78.
  (c) Reduced-form cell regressions, out-of-year: annual weather 0.86, + monthly anomalies 0.92 (MPI unseen); ACCESS
  futures 0.51-0.79 -> 0.69-0.89. Doubling weather years (both GCMs) adds 0.01 on a seen GCM. The original's OWN
  monthly NPP / soil water / phenology as oracle features add <= 0.02. The whole-leaf-drop latch reconstructed from
  daily forcing (gated vs the C's monthly phenology: means to 1e-4) is constant for beech (one drop every year).
  (d) MECHANISM: negative growth = the tree's NPP below its loss (turnover + reproduction + excess + debt); holding
  last year's loss and taking this year's NPP reproduces the yearly share at 0.83-0.97, the reverse ~0. So the swing
  is a THRESHOLD CROSSING of individual trees' NPP — a tail event the cell means blur.
  PROPOSAL (not built): replace the G-sign head by a smooth per-tree NPP model + a pool-based loss model, sign by the
  C's own threshold. First test I8 (`explore_de_nppmodel.py`): implied yearly share corr 0.835 / slope 0.86 on MPI
  unseen years (sign head 0.775 / 0.64), 0.69-0.74 on ACCESS ssp245/370 (sign head ~0.43), 0.37 on ACCESS ssp126; mean
  biased high by ~0.03; bars (0.88 / 0.75) missed, falsifier not fired => promising, not yet good enough.
  **NEXT, in order:** (1) improve the NPP route before building it in: a loss model for L_y1 (pools + fractions of
  gain) instead of last year's loss, a size/light-dependent residual spread, then re-run I8's test; if it clears the
  bars, build the NPP + loss G model as a TAB stepper option and score it coupled on BOTH unseen members against (a); (2) ACCESS's stand drift after ~2006 is a second, separate failure — attribute
  it (grass transfer across GCMs was the eighth session's suspect) before blaming the sign head; (3)-(8) as in the
  sixteenth session's list (cheap G model, grass into NSET, STRUCT size shape, LSTM response window, sapling layer,
  eighth-session items). Score everything weather-driven on MPI s1 ssp245 + ACCESS s1, never only on MPI s2.
* **2026-10-07 (eighteenth session): the bad-growth LOSS side is solved, the limit is the weather -> tree margin map; the
  ACCESS stand drift is half grass, half tree heads** [VERIFIED; every number + pre-registration in `_status/TS.md` from
  "I9 NPP route + LOSS model" on; `scripts/explore_de_nppmodel2.py` (fit W|L|M|MN, score, shared; models
  `tab/models/DEV-A/npp2/`), `scripts/explore_de_access_drift.py` (steppers GrassLAIOracle / GrassFullOracle); tables
  `shared/eval/nppmodel2_{yearly,shared}.csv`, `recruit_drift_ssp370_{grl,grf}_acc1.csv`].
  (a) I9: a per-tree LOSS model (log loss change | true NPP change, R2 0.79) reproduces the yearly negative-growth share
  at 0.90-0.99 with the mean right to 0.004 when given the TRUE NPP => the loss side is solved. With PREDICTED NPP it is
  WORSE than I8 (falsifier fired): I8's last-year-loss basis over-swung and its NPP under-swung — a compensation. Best
  model: the MARGIN log(gain_y1/L_y1) directly (arm Mh, per-tree spread): yearly corr 0.874 MPI s1 ssp245 / 0.798 ACCESS
  Hist / 0.583 / 0.750 / 0.718 ACCESS ssp126/245/370 (shipped sign head one step: 0.775 / ~0.43-0.51), mean +0.005..+0.016;
  null without weather anomalies 0.25 / 0.15 / -0.01 / 0.03 on futures. (b) I10: 24-33 % of its residual is shared by a
  cell-year, but the simulated swings already have the right size (0.8-1.1 x truth) — the low slopes are timing error,
  not damping; my premise was wrong. (c) ACCESS drift: replaying the original's grass LEAF AREA (cover still from the
  emulator's hidden-cover model) closes 71 / 59 / 54 % of the recruit / stem / biomass-per-stem gaps; replaying cover too
  closes LESS (41 / 34 / 30 %) and adds an early recruit excess. Big-tree growth -6..-9 % from 1996 and small-tree growth
  -9..-17 % after 2030 are untouched => the tree heads' own cross-GCM transfer is the other half.
  **NEXT, in order:** (1) build the margin model Mh as the G-SIGN replacement in the TAB stepper (sign = margin < 0 drawn
  from mu + s z, cell-year shared part rho ~0.3 optional; G magnitude stays gqsc's quantile heads conditioned on sign)
  and score it coupled on MPI s1 ssp245 + ACCESS s1 against the honest baseline (U-M / U-A rows in TS.md); pre-register
  pulse / quiet / timing-corr bars first; (2) the grass2 LEAF-AREA weather transfer across GCMs (half the ACCESS drift):
  is it a missing input (absolute temperature level, daily extremes) or booster extrapolation? tune on MPI held-out
  weather only, ACCESS stays the test; (3) the tree growth heads' ACCESS transfer: one-step growth on ACCESS states by
  size class, 1996-2010 big trees first; (4) more weather information for the margin (it is now the limit everywhere):
  per-tree daily/monthly drivers, cost-checked; (5)-(9) as in the sixteenth session's list (cheap G model, grass into
  NSET, STRUCT size shape, LSTM response window, sapling layer, eighth-session items).
* **2026-10-07 (nineteenth + twentieth sessions): the margin sign fixes cross-model TIMING but misallocates bad years
  to big trees; the ACCESS big-tree deficit is the G MAGNITUDE's compressed year swings** [VERIFIED; every number +
  pre-registration in `_status/TS.md` from "Pre-registration I11" on; scripts `explore_de_nppmodel2.py fit MS |
  score_ms | score_ms_size`, `explore_de_tab_margin.py:TabALG2HSGQMProbe` (arm gqm), `explore_de_bigtree_resp.py
  [--gq]`; tables `shared/eval/{nppmodel2_ms_yearly,nppmodel2_ms_size,bigtree_resp_yearly,bigtree_resp_gq_yearly,
  unseen_score}.csv`, `recruit_drift_*_gqm_*`, `streak_gqm_*`]. (a) I11: the stepper-feasible margin model MS (no
  per-tree npp / transpiration / water stress) is within -0.05..+0.04 of Mh one step; falsifier not fired. (b) TG +
  BT + BT3: given the TRUE next-year G the dagb growth head is exact on every member (|error| <= 0.0006/yr); the ACCESS
  big-tree deficit is the DRAWN G's MAGNITUDE (true sign closes 0-18 %, true |G| most of it): on unseen weather the
  yearly mean drawn G swings too little (yearly error sd 0.20-0.33, corr -0.45 with the true G), netting ~-3 % of
  growth/yr on ACCESS ssp126 / ssp370 and ~0 on ssp245 / MPI ssp245. TG's "monotone ssp370 decline" was the OLD
  sampler's. (c) CM coupled (arm gqm, 200 cells): timing corr U-M 0.785 -> 0.798, U-A 0.505 -> **0.838**; pulses
  U-M -35 % (worse), U-A -28.5 %, quiet U-A +30 -> +13 %; but the stand regresses: agb/stem U-M -10 / -13 % (2006-25),
  U-A -19 / -25 %, stems +9..+19 %, recruits +8..+27 % — CM1-CM3 FAIL, falsifier not fired. Cost 5.2-5.6 core-s.
  (d) MZ: MS over-predicts bad-growth years for >= 10 m trees ONE STEP ahead by +0.013..+0.025 (13-24 % relative) on
  every test member; < 10 m +0.002..+0.010 => model calibration, not free-run feedback.
  **NEXT, in order:** (1) size-wise recalibration of MS (scale on s or Platt on -mu/s per height class, maybe per
  counter c_y), fitted ONLY on training-member out-of-fold rows (the fit stage's year-grouped folds; save OOF if not
  saved); pre-register one-step by size (>= 10 m and < 10 m within +-0.005 on all five test members) and keep the
  yearly corr; then rerun CM coupled (same jobs, `_jobs/probe2_g2hsgqm_*.jcf` + scorers, new XDE_RUNS dir) — the timing
  gain on ACCESS is worth keeping if the stand holds; (2) the G magnitude's compressed year swings: derive the
  magnitude from the margin too (|G| = (gain_y1 / la)(1 - e^-m)), or add the margin as a magnitude input; (3) the
  grass2 leaf-area weather transfer across GCMs (half the ACCESS drift, eighteenth session); (4)-(8) as in the
  sixteenth session's list. ⚠ `explore_de_unseen_score.py` OVERWRITES `unseen_score.csv` with only the rows passed —
  pass every row you want kept (now: mpi2, um, ua, um_gqm, ua_gqm).
* **2026-10-07 (twenty-first session): the margin model's big-tree excess is NOT a calibration error; the margin
  carries the G magnitude's year swing only if productivity per leaf area is known** [VERIFIED; every number +
  pre-registration in `_status/TS.md` from "Pre-registration K" on; `scripts/explore_de_nppmodel2.py oof | calib |
  score_calib | zstats` (arm "MS+c" = MS + per-height probit, `npp2/MS.{oof.parquet,calib.json}`),
  `scripts/explore_de_gmargin.py`; tables `shared/eval/nppmodel2_ms_{calib_size,calib_yearly,zstats}.csv`,
  `gmargin_yearly.csv`]. (a) K: on the TRAINING members out of year the >= 10 m bad-year share is right (+0.003), so a
  size-wise probit fitted there removes only ~1/3 of the test excess (MPI ssp245 +0.013 -> +0.008, ACCESS +0.015..+0.025
  -> +0.012..+0.019); falsifier fired, coupled gqmc NOT run (job files ready: `_jobs/probe2_g2hsgqmc_*.jcf`,
  `score_g2hsgqmc_*.jcf`). (b) KZ: two parts. A tail-shape part for big trees present everywhere (the calibration's
  third), and a MEMBER-TRANSFER mean bias: on ACCESS futures the tall trees do better than predicted by +0.17..+0.38
  spread units (mu too low, growing with height), plus a too-narrow spread on ssp370 (z sd 1.2-1.3). Same family as the
  eighteenth session's tree-head cross-GCM transfer. All-tree bad-year share is +0.006..+0.015 too high on every test
  member (OOF ~0). (c) GM: G_y1 = (NPP per leaf area) x (1 - e^-margin) exactly (1.5e-13). With the TRUE productivity
  the drawn margin tracks the 15-25 m yearly G at corr 0.83-0.94 (gqsc's reference 0.74-0.80 on ACCESS); with LAST
  year's productivity only 0.74-0.83 (level with gqsc); both 4-12 % LOW in mean (the excess above). GM1/GM2 miss,
  falsifier not fired.
  **NEXT, in order:** (1) the margin model's cross-member transfer: why does mu run low for tall trees on the other
  climate model's weather? Check whether the weather inputs for big-tree rows leave the training range (the
  `explore_de_grass_climrange.py` logic), and refit MS with the GCM-common inputs only (anomalies relative to each
  member's own 1985-2014 climatology — check how `gi.features` defines them first); score with `score_calib`/`zstats`
  on the five test members; (2) a productivity-per-leaf-area model r_y1 (weather + state, stepper-feasible) — GM showed
  it is what the margin route for the magnitude needs; score it with `explore_de_gmargin.py` as a third arm against
  RM / PM; (3) then the coupled gqm / gqmc runs only once (1) moves the >= 10 m excess under +0.008; (4) the grass2
  leaf-area transfer across GCMs (eighteenth session); (5)-(9) as in the sixteenth session's list.
* **2026-10-07 (twenty-second session): the margin model's tall-tree bias on the other climate model is a GCM-SPECIFIC
  weather -> growth mapping; that model's own historical run removes about half of it** [VERIFIED; every number +
  pre-registration in `_status/TS.md` from "Pre-registration T" on; `scripts/explore_de_mstransfer.py` (level swap) and
  `... anom` (by warming bin), arm `MSx` in `explore_de_nppmodel2.py` (`TRAIN_X`: MS + ACCESS Historical s1; `zstats MSx`);
  tables `shared/eval/mstransfer_{zstats,levels,yearly,anom}.csv`, `nppmodel2_ms_zstats_MSx.csv`]. (a) T: every weather
  ANOMALY input is already GCM-common; replacing ACCESS's 15 climatology levels + 2 absolute temperatures by MPI's for the
  same cell closes only 5-8 % of the futures' 15-25 m shift (28 % on ACCESS Hist) — falsifier fired. (b) T3: at equal
  warming (+0.5..+1.5 K) ACCESS is shifted (+0.05..+0.67) where MPI ssp245 is not (-0.01..+0.06), and on rows with every
  anomaly inside the training range the shift is still +0.14..+0.43 => GCM-specific response, not only extrapolation
  (though ACCESS's faster-rising 20-yr means leave the range on 25-48 % of big-tree rows). (c) T4: MSx (+ ACCESS Hist in
  training) halves it: 15-25 m +0.17..+0.38 -> +0.09..+0.25, >= 10 m bad-year excess +0.023..+0.025 -> +0.013..+0.016
  (MPI ssp245 +0.013 -> +0.010); ssp245 worst, not the warmest. Prediction failed, falsifier not fired.
  **NEXT, in order:** (1) the realistic multi-GCM setting: arm MSb trained on BOTH GCMs' Historical/ssp126/ssp370 (s1),
  tested on the bracketed held-out scenario ssp245 of both GCMs (+ s2 members if loadable) — add it to `TRAIN_X`, give
  `zstats`/`score_calib` a test-member list; pre-register >= 10 m excess <= +0.010 and 15-25 m r/s <= +0.10 on both, and
  the yearly corr kept; if it passes, rerun the coupled gqm runs with it (`_jobs/probe2_g2hsgqm_*.jcf` + scorers, new
  XDE_RUNS dir); (2) the productivity-per-leaf-area model r_y1 (twenty-first session's item 2), scored as a third arm
  in `explore_de_gmargin.py`; (3) the grass2 leaf-area transfer across GCMs (eighteenth session) — same family as (a)-(c),
  so test the "train on both GCMs' history" fix there first; (4)-(8) as in the sixteenth session's list.
* NOT started: tracks C (full roster recurrent, C1-C6) and D stage 2; calibrations; full-cellset (9065) builds
  (trans dev = 108 GB, tensors dev 98 GB for 5 members -> check /p/tmp quota first).
**The build stays inside line X's owned paths** (`scripts/explore_de_*.py`, `/p/tmp/jamirp/X_de/`, `docs/notes/exploration_de_*.md`):
it is a standalone prototype, no `src/**` edits, nothing propagated to other lines.

**The Germany data [VERIFIED 2026-09-30]:** 2 GCMs (MPI-ESM1-2-HR, ACCESS-CM2) x {Historical, ssp126, ssp245, ssp370} x 2 independent
spin-up seeds, 9067 cells (~8 km), **npatch 250**, all 16 runs log a clean termination. `ind` tables: Historical 1985-2014; each ssp
2015-2044 / 2071-2100 / 3071-3100 (**no table for 2045-2070**; **3071-3100 is recycled shuffled 2071-2100 climate = equilibrium test
only, never a response window**). ⚠ MPI ssp370 seed2 `ind_3100.csv` is 10 GB vs ~120 GB siblings — suspect truncated. Fire is ON.
Daily forcing `/p/projects/waldspektrum/data/FirEUrisk/<GCM>/{TMean,tpr,HRMean,SWR,LWR,windspeed}_<GCM>_<leg>_germany.clm` (v3 float32).
The original costs ~12 core-s per cell-year at 250 patches (2048 tasks x 3556 s / (65 yr x 9067 cells)).
**Why this data matters:** the same cell sees six different futures (2 GCMs x 3 scenarios) — the design that can break the
"warming vs character of the place" confound ADR 0311 found, and ssp245 is a bracketed held-out scenario.

**Round 1 workflow `wf_89265fa2-f32`** (conversion of all 40 tables to parquet, climate features, transition anatomy + verifier,
scorer + null scores, 3-architect design panel + judge, critic). Resume: `Workflow({scriptPath:
"~/.claude/projects/-p-projects-open-Jamir-esm-land-emulator-lines-X/a19083d6-0024-4d05-8614-5e108626a023/workflows/scripts/de-emulator-germany-foundation-wf_89265fa2-f32.js",
resumeFromRunId: "wf_89265fa2-f32"})`. ⚠ The first launch died with the session at ~14:50 (no agent finished); the
cluster jobs survived. Resumed 14:57 with a durability note: the full conversion is SLURM array **2363349** (submitted directly, not by an
agent; ~4 min/file, idempotent: `scripts/explore_de_convert.py submit|collect`), every agent keeps `/p/tmp/jamirp/X_de/_status/<label>.md`
and writes its report to `/p/tmp/jamirp/X_de/_reports/<label>.json`. **If the session dies again, read those two folders first.**
First measured facts: raw key (Cell,Patch,Type,ID) has 2 779 duplicates / 569 M tree rows (0 with SLA+Wooddens added); MPI ssp370 s2
w3071 confirmed truncated. Round 2 = build + train + free-running rollouts + held-out scoring, from the judge's work items.


### 0✦ 💬 NEW OWNER QUESTION, ANSWERED — where does the ORIGINAL model's time go? (owner, 2026-09-02; **ADR 0312**)

Owner, verbatim: *"find out which parts of the original model consume most computational time (e.g.
photosysntesis or other processes). we can use this as basis for explorign soltutions where only these
processes are learned."* **Measured at five biome sites on the unmodified binary — no rebuild, so the oracle's
reference basis is untouched.** Three things to carry forward:

1. ⚠ **The pre-registered falsifier for that strategy FIRED at all five sites.** The largest single process
   (the per-tree daily assimilation/conductance kernel) is **36–46 %** of runtime, so making it entirely
   **free** buys only **1.57–1.84×** — against a requirement of **≈15–25×**. ⇒ *"learn only the expensive
   process"* works **only as a portfolio covering ≥ 90 % of the daily loop**, which is close to a
   whole-daily-core replacement, not a surgical one. **And every ceiling assumes the replacement is FREE; at
   20 % of the replaced cost, 1.84× becomes 1.56×. Never quote a ceiling as a speed-up.**
2. ⛳ **The annual demography — the whole block the learned slow component replaces — is 0.44–1.06 % of the
   original model's runtime.** The correct reading is **not** "we learned the cheap part": it is that the
   demography's speed value was never its own cost but that **it removes the patch tax** (cost is linear in
   patch count, this configuration runs 25, and a component predicting the ensemble expectation converts a
   ~25× multiplier into 1 — a bigger lever than every process combined). The reason nobody sets the patch
   count to 1 is **fidelity, not speed**.
3. **Two targets worth pricing, different in kind.** A quarter of the entire model (**21–27 %**) is
   `exp`/`pow`/`log` ⇒ an **engineering** target, no learning, no fidelity risk, ceiling 1.28–1.37×. And the
   **λ root-find** is the best-posed *learning* target in the model — smooth, deterministic, scalar output,
   no state, unlimited training data, sitting on the largest share (33.3 % inclusive) — but the gross flux is
   **non-monotone** in its iteration count, so its convergence cannot be assumed.

**The cheapest missing number in ADR 0312: re-measure the patch-count slope on this binary.** It is cited from
ADR 0093, not reproduced, and my own blocks disagree with its published value by a factor ~1.4–2.

### 0b✦ 💬 THE OPEN CONVERSATION, ROUND 2 IS MEASURED AND HALF-FINISHED (owner, 2026-08-19 → 2026-09-02; **ADR 0311**)

**Still an owner conversation, not a work item. Still nothing raised with S/M/E/O, nothing in `MEMORY.md` or
`EXECUTION_PLAN.md`, nothing implemented.** Owner's words this round: *"continue the exploration of the
feasibility of a **more** data driven emulator"* — **more**, not necessarily **purely**, and nobody has yet
priced the middle of that spectrum.

**⚠ READ `ADR 0311` BEFORE ANYTHING ELSE. It overturns ADR 0310's headline verdict.** Three
things you must not carry forward from ADR 0310 as stated:

1. **"ZERO positive evidence exists for the warming response" is NO LONGER TRUE.** A direct
   20-yr-climatology → 20-yr-window-state map beats a coordinates-only null under **spatially blocked** folds
   by **+0.162…+0.715** on the clean 20-vs-20-yr response, and climate *subsumes* the address rather than
   proxying it. Its verifier attacked with three independent address nulls and the margin came out
   **2–6× larger**. ADR 0310's kill of this claim was a hash-fold artifact on a drift-contaminated target.
2. **"The geographic-address null was never run" is FALSE** — it was built, pre-registered, published and
   committed sixteen days earlier (ADR 0038/0040/0042, plus `blocked_cv_folds_probe.jl`,
   `build_slow_spatial_controls.py`, `diagnose_slow_address_prereg.py`). **Reuse it; do not rebuild it.**
3. **"Single-draw R² cannot discriminate arms" is overstated** — the exact Bernoulli floor is ~28 % of the
   residual variance, not all of it.

**The four things that now matter most:**

* ⛳ **The identification limit is the deepest result and it bounds every cross-sectional design.** Within one
  emissions scenario a cell's warming increment is **76.4 %** predictable from its own baseline climate, so
  "response to warming" and "sensitivity of this place" are **not separately identified**. Consistently:
  knowing the future climate adds nothing over knowing today's on 5 of 6 targets, and a **counterfactual with
  warming scaled to zero still reproduces 76–110 %** of the predicted per-cell change. ⇒ **the third forcing
  leg is the only way to break it**, and the literature says only a **bracketed** design has precedent
  (historic + ssp370 bracket ssp126 at 0.227×).
* ⛳ **The per-tree hidden state is exactly recoverable and propagable — but UNVERIFIED** (its adversarial
  verifier died to a usage limit; `scripts/explore_verify_b1.py` exists and was never run to completion).
  **Finishing that verification is the single cheapest high-value action available.**
* ⚠ **Per tree, climate adds nothing beyond the stand** (+0.0030, below the pre-registered 0.005; within noise
  under blocking) ⇒ a free-running rollout's response can only come from state it generates itself.
* ⚠ **The map is 7.2 % of cells on the owner's conjunctive basis and LOSES to persistence on the future state**
  (7.35 % vs 12.96 %), and space-for-time transfer is **sign-wrong** in the 3.7 % of genuinely extrapolating
  cells.

### 1✦ THE UNFINISHED HALF — resume the campaign from cache (no new design needed)

Three measurements, the spectrum synthesis and the completeness critic **did not run** (usage limit, then
server overload). Everything that did run **replays from cache**:

```
Workflow({scriptPath: '~/.claude/projects/-p-projects-open-Jamir-esm-land-emulator-lines-X/
  71d6fd2b-2837-45c1-9b0b-0e3e1b72c572/workflows/scripts/
  data-driven-emulator-feasibility-round2-wf_5ba7e1aa-b45.js',
  resumeFromRunId: 'wf_5ba7e1aa-b45'})
```
Restore `ITEMS` (currently `.slice(0, 3)`) and set `RUN_SYNTH = true`. What is queued in it:
**B4** the ssp126 bracketed held-out leg (⚠ gate its Aug-12-vs-Feb-5 build provenance FIRST; it is raw CSV
only, 186 GB/seed, and is in **no** shared table) · **B5** whether a fixed-size stand summary suffices for the
daily fluxes · **B6** the closed density-feedback rollout with a stochastic binomial-survival/Poisson-birth
head · **the synthesis that prices the WHOLE SPECTRUM** from the shipping hybrid to the pure learned model,
which is what the owner's word *"more"* actually asks for · the completeness critic.
⚠ **Add the persistence null to the pre-registration TEMPLATE, not only to the brief's prose** — ADR 0310
§2(ii) made it a STANDING RULE and the very next campaign violated it anyway (see ADR 0311 §8).

### 2✦ WHAT IS ON DISK ALREADY — look before building (all read-only, no model run needed)

`/p/tmp/jamirp/X_explore/`: `prep_paired_stems.parquet` (21 785 911 × 40, year-paired per-stem on the
**corrected** identity key) · `prep_patch_year_stand.parquet` (2 553 172 × 43) ·
`prep_cell_window_state.parquet` (334 212 × 26, **both seeds** ⇒ a per-cell two-seed noise floor for the
20-yr state with no model run) · `prep_cell_window_clim.parquet` (202 260 × 37, incl. unit-sphere x/y/z) ·
`prep_cell_year_census.parquet` (11 029 804 × 9) · `prep_suspect_cell_blocks.csv` (**the exclusion list — join
it, or you will measure five damaged blocks**) · the `b3_*`, `vb2_*`, `vb3_*` result sets.
Probes: `scripts/explore_{prep_tables,hidden_counter,perstem_ladder,direct_window_map}.py` and
`scripts/explore_verify_b{1,2,3}.py`. Literature: `docs/notes/exploration_data_driven_literature.md`.

### 3✦ THREE CORRECTIONS OWED TO OTHER LINES — RAISED IN ADR 0311 §6, DELIBERATELY NOT PROPAGATED

**Propagation is the owner's call, not this line's.** (a) **ADR 0125's per-stem identity key is WRONG** — it is
`(Cell, Patch, PFT, ID)`; the tree number comes from a **per-PFT** counter, the documented key fails the
identity gates on every leg, and the corrected one gives 0 violations of 20.4 M pairs on three checks.
(b) `bm_inc_counter` **is** recoverable from the annual `ind` output, and it **is** populated into the output
struct at `fwriteoutput_ind.c:167` with only its print line commented out at `:96`. (c) The heat/cold stress
day count is **exactly** invertible as `round(mort_temp × 365/5)`. Plus: the two roster seeds were **never
re-verified as a valid ADR-0041 pair**, which is an open gate on every number in ADR 0311.

**Do NOT redo** ADR 0310's six investigations or ADR 0311's three measurements. Transcripts:
`…/subagents/workflows/wf_1392bef9-337/journal.jsonl` (round 1) and `…/wf_5ba7e1aa-b45/journal.jsonl`
(round 2 — one `{"type":"result"}` line per agent; the `/tmp` task-output files have since been cleared, so the
journal is the only copy).

---

### 0a✦ 💬 ROUND 1 — the record that opened this line (**ADR 0310**; superseded in part by 0311 above)

**This is an owner conversation in progress, not a work item.** Answer questions, measure, deepen it.
**Do not implement, do not raise it with line S/M/E/O, do not write it into `MEMORY.md` or
`EXECUTION_PLAN.md`.** Promotion is the owner's call. Both governing instructions are quoted verbatim in
ADR 0310's Status box — read them first.

**What the owner asked:** drop the hybrid — learn `(forest state, climate) → next forest state` directly and
roll it out, plus a second head for the daily fluxes an atmosphere needs. *"Do you think this is learnable /
achievable?"* Offline first; the hope is that it captures **the warming response**, not just the steady state.

**The answer delivered — it is SIX problems, not one, and lumping them is why it looks either obviously right
or obviously refuted:**

| part | verdict |
|---|---|
| daily **water + carbon** fluxes | data exist (~1 TB, both scenarios); **learnability untested** |
| daily **energy** fluxes | ⛔ **impossible from this model, permanently** — of 421 outputs only monthly albedo + soil temperature are energy-adjacent |
| one-year-ahead step, teacher-forced | **already built, and 96 % of its skill is the persistence null** (0.9622 of 0.9824) |
| free-running century rollout | stable — but **every reason given for the stability was a tree-ensemble artifact**, and rollout training has never been tried here |
| **the warming response** | ⛔ **not demonstrated, and ZERO positive evidence exists** — the one claim died to a geographic-address null (lat/lon alone 0.654 of the 0.748) |
| speed | ✅ **≈0.0032 core-s/cell-year at fp64**, fits the strict convention with 4× margin |

**The four things that matter if the owner picks this up** (all measured; full detail in ADR 0310 §5):

1. **The strongest objection is specific, and it just became TESTABLE.** Every tree carries a private
   consecutive-bad-years counter; it is trait-correlated (+19 % wood density across its range), 11.69 % of
   stems carry **44.8 % of all mortality**, and summarising it away **reverses the selection sign in 4 of 7
   tree types** (ADR 0093 §4.4 — which is owner-approved and says the density family is *dead*). ⛳ **NEW: that
   counter IS dumped per stem in the rung-2 roster files** (§7.3), so the refutation can be measured instead
   of believed. **This is the highest-information thing available.**
2. **The architecture nobody priced: a permutation-equivariant set/graph network over the per-stem roster.**
   Still purely learned (no ported equations) but it **keeps the individuals** ⇒ **2.55e9 paired per-stem
   labels** instead of 1.2e8 cell-year rows; it is the only candidate that survives (1); and it pays no patch
   tax. ADR 0086 §5d's "learned annual operator = 1.3–1.5× only" **does not apply** to it (that costing
   assumed the daily soil loop stays).
3. **The head should be STOCHASTIC, and the target the ensemble distribution.** Rectification (86.7 % of a
   decline reproduced vs 96.2 % of a rise) is the *definitional* failure of a self-fed conditional-mean
   regressor. A **binomial-survival + Poisson-birth** head is conservative by construction and structurally
   forbids the measured 799.5-stem blow-up. Precedent: GraphCast → GenCast.
4. **Single-draw R² cannot discriminate arms.** Deeper history buys **0.00024** of variance; the ~2.4 %
   surviving lag-1 is the C's own Bernoulli noise ⇒ the ceiling is a **variance** ceiling. Any experiment
   guarded on an R² floor is mis-designed. (This also **narrows** "the state is not Markov" to the trait-axis
   selection covariance — it is *not* true of count predictability.)

**Three measured facts sitting unpropagated in ADR 0310 §7** — real, and deliberately NOT in `MEMORY.md`:
**ssp126 both seeds completed 2026-08-18** (591 GB, correct seed protocol; warms **0.227×** of ssp370 on a
common baseline; pattern correlation only **0.19–0.22**; **15–26 % of cells COOL** ⇒ useless per cell,
excellent as a held-out test that a memorised warming pattern must fail; ⚠ built with an Aug-12 binary vs
Feb-5 for the other legs, so gate the provenance) · **a 1000-step global vegetation-carbon trajectory exists
for both seeds** (`vegc_spinup_1999.nc`) · **the bad-years counter + all four hazards are in the rung-2
dumps.**

**Do NOT redo** the six investigations or their refutations. Transcript:
`~/.claude/projects/-p-projects-open-Jamir-wt-O/d1fedf05-84e7-49aa-8351-cc3c0206c27b/subagents/workflows/wf_1392bef9-337/journal.jsonl`
(one `{"type":"result"}` line per agent), replayable from cache with
`Workflow({scriptPath: '…/pure-data-driven-emulator-feasibility-wf_1392bef9-337.js', resumeFromRunId: 'wf_1392bef9-337'})`.
⚠ **ADR 0310 §10 lists five OPEN disagreements between an investigator and its reviewer — quote neither side
of any of them as fact**, in particular whether the measured −0.226 response inversion bounds a closed
rollout from below or from above (it changes the prior on the whole question).

**Housekeeping owed on this line's first working session:** none — the line was bootstrapped complete
(charter, block, worktree, hook entry, index rows). Just refresh this block before you end.

---

## Milestones

**X1 — the purely-data-driven direction (OPEN, owner conversation).** ADR 0310. Status: explored, adversarially
reviewed, no decision. Awaiting the owner.

**X2 — round 2: is a MORE data-driven emulator feasible? (OPEN, owner conversation, HALF-MEASURED).** ADR 0311
+ `docs/notes/exploration_data_driven_literature.md`. Status: three of six planned measurements done, two of
them adversarially verified (both `NARROWED`, neither refuted), one unverified. **What would have to be true to
promote it:** (a) the warming-response signal that survives blocked folds must also survive a **bracketed
held-out forcing leg** — the only design with published precedent — because within one scenario the forcing is
**76.4 %** predictable from the baseline climate and so is not separately identified; (b) the per-tree
hidden-state propagation result must survive its **unrun** adversarial verifier; (c) the per-cell conjunctive
pass rate must move from **7.2 %** toward the acceptance criterion, on a reference at acceptance-grade patch
count, not at 25; and (d) somebody must price the **middle** of the spectrum, which is what the owner's word
*"more"* asks about and which no record yet covers.

*(Future explorations append here. One subsection each: the question, what the owner said, what was measured,
what would have to be true to promote it.)*

---

## Line X gotchas

- **A cross-fit by CELL leaks the YEAR whenever the target responds to weather shared by every cell (2026-10-06,
  sixteenth session).** Germany's cells share each year's weather, so a booster cross-fitted by cell can recognise a
  member-year from other cells and memorise its outcome (continuation slope 0.85 -> 0.97 by cell, 0.83 by year). The
  seed-2 members share the seed-1 members' weather years, so MPI s2 cannot rule it out either. Hold out YEARS (or a
  scenario / GCM with its own weather years) for anything weather-driven; early-stop on held-out years too.

* **The SessionStart hook is generic over `line/*`** — it reads `lines/<letter>/STATE.md` and needs no
  per-line code. Only the integrator-worktree hint list names worktrees explicitly, and `wt-X` was added
  there when the line was created.
* **Read `EXECUTION_PLAN.md` before proposing a direction change** — it is the owner-approved order of work
  and it is **integrator-owned**. A line raises a change to it; it never edits it.
* **`scripts/*.py` is not linted by CI.** Lint any probe yourself with the repo's real rule set:
  `ruff check --select E,F,I,UP,B --line-length 100 scripts/explore_<x>.py`. `B905` (a `zip()` without
  `strict=`, which silently truncates) and `B023` (a closure over a loop variable) catch real defects in
  exactly the paired-array comparisons an exploration does constantly.
* **Path-filtered CI (ADR 0090):** a line-X commit is normally prose + `scripts/*.py` only, which triggers
  **no gate at all** — so there is no verdict to wait for and the merge can proceed as soon as it is pushed.
  Decide the expected set from `git diff --name-only origin/main...HEAD` against CLAUDE.md §5's table.
