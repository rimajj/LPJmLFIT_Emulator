# LINE X — project direction & exploration (branch `line/X`, worktree `wt-X`)

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/X/JOURNAL.md` (append-only). Decisions: tier-1 block
> **0310–0329**, opened by **ADR 0310**. **Next free number: 0313.**
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
* NOT started: SH11 neural tensors (deferred until a neural track starts), tracks C/D, steppers A6/B5,
  calibrations, full-cellset (9065) builds (trans dev = 108 GB -> full ~1 TB: check /p/tmp quota first).
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
