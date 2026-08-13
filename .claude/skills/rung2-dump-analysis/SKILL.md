---
name: rung2-dump-analysis
description: Read and score the rung-2 roster dumps — the per-tree state LPJmL-FIT writes at the demography rendezvous when the emulator substitutes its mortality (line S, ADR 0175). Use whenever a question about the rung-2 arms can be answered from state already on disk instead of a new LPJmL run: an arm's own stand features (hmean/hmax/agb/lai/fpc/age_mean), its per-stem hazards or certain-kill set, its trait/age distributions, a historic-vs-ssp370 leg comparison, or FIT's own values as the like-for-like reference. Names the dump layout `/p/tmp/jamirp/S_rung2/S_r2s_<scen>_c<cell>_<arm>_roster_s<seed>_dump/roster_rank0000.txt`, the arms REC/NP/S0/S0h/S1, the four phases pre/grow/mort/post and why `grow` is almost always the right one, the `#H`-header-to-field OFFSET that silently mis-reads two same-typed columns, the coverage gate that 92 of 510 legs fail, and the existing scorers scripts/diagnose_rung2_stand_warming.py, scripts/diagnose_rung2_ported_certain_set.jl, scripts/diagnose_rung2_response.py, scripts/diagnose_rung2_armc.py. ALSO the rule that in a rung-2 arm the C GROWS THE STAND, so any stand-derived statistic is inherited by every arm including the do-nothing null and cannot rank arms. ALSO — CHECK `<apply>/s_arm_log.txt` FIRST: beside every arm's dump the harness logged its own count `target`, `rho`, `n_kill`, the four flux drivers and BOTH stand feature bases per patch-year in ~170 kB, so most stand questions need no dump scan at all (only REC lacks one; supply it with scripts/diagnose_rung2_map_on_rec_stand.jl). ALSO the `--n-prev` mode check that decides whether a response statistic exists: all 767 dumps are `roster`, where the model is handed the LIVE stem count and returns one within ±5 % of it in ~85 % of patch-years, so `target` and the stand's own count are the SAME quantity, any ASK-vs-GOT comparison is degenerate, and a persistence null passes a sign-agreement basis check at 12/12 cells by construction (ADR 0184) — test it with median |target/n_emit − 1| > 0.10, never with |rho − 1|, which is near 1 in both modes. ALSO the `predict` matrix now on disk (264 jobs, 258 done, tags `_predict_s<seed>`, ADR 0185) and the three rules it paid for: the mode knob must reach the OFFLINE REC replay too or the reference sits on a tethered axis while the arms run free; gate an added recursion on the first year it cannot change (600/600 rows bit-identical) rather than on an aggregate; and run the python scorers with the conda py311 interpreter, because /usr/bin/python3 dies on zip(strict=True) two thirds down the output and a partial run looks complete.
---

# rung2-dump-analysis — answer a rung-2 question from the dumps instead of a new run

The rung-2 harness leaves **full per-tree state on disk for every arm × cell × scenario × seed**. Two
sessions in a row have found a decisive answer in it with a parser and no model run (ADR 0182, ADR 0183).
**Before scheduling any LPJmL run for a rung-2 question, check whether the dumps already carry it.**

## What is on disk

```
/p/tmp/jamirp/S_rung2/S_r2s_<scenario>_c<cell>_<arm>_roster_s<seed>_dump/roster_rank0000.txt
        scenario : historic (2000-2019) | ssp370 (2020-2100) | ssp370frz
        arm      : REC | NP | S0 | S0h | S1          seed : 1-5 (S0/S0h/S1), 1 (NP/REC)
```
~71 GB total, ~38 GB for the non-`frz` arms. One cell per dump, 25 patches, plain text.

Three record types, each with its own `#H` header line: **`P`** = per patch-year (incl. `rootzone_w`, the
`soilmoist` driver — v6 hook only), **`T`** = per TREE (52 columns: full pools, traits, all five `mort_*`,
`bm_delta`, `leafarea_real`, `bm_inc_counter`, `isdead`), **`G`** = per grass PFT. `T` is trees only
(`istree(pft)` in the writer), so no grass filter is needed.

**The arms:** `REC` = pure observation, i.e. **LPJmL-FIT's own roster** and the like-for-like reference for
anything; `NP` = persistence null (ρ = 1, learns nothing); `S0` = shipped uniform thinning; `S0h` = S0 +
honouring certain kills (the decomposition control); `S1` = + the trait hazard's ordering. `ssp370frz`
freezes only the 4 boundary columns fed to the emulator — it is **not** a frozen-climate control for the
stand, because the C still runs transient forcing.

## ⚠ CHECK `<apply>/s_arm_log.txt` BEFORE YOU SCAN A SINGLE DUMP

Beside every emulator arm's `_dump` there is an `_apply` directory, and in it the harness's own runtime log:

```
/p/tmp/jamirp/S_rung2/S_r2s_<scen>_c<cell>_<arm>_roster_s<seed>_apply/s_arm_log.txt
#H L year patch n_tree n_emit n_prev target rho theta shortfall n_kill n_recruit
       bm_inc growth_eff water_stress soilmoist  hmean_rt hmax_rt agb_rt lai_rt fpc_rt age_rt
       hmean_c hmax_c agb_c lai_c fpc_c age_c
```

One line per patch-year, ~170 kB per leg instead of 11–47 MB, and it carries **the map's own prediction
(`target`), the thinning ratio it implied (`rho`), the kills it made, all four flux drivers and BOTH stand
feature bases** (`_rt` = the RUNTIME row the DRF was actually fed; `_c` = the C's `ind`-aggregate training
basis — the gap between them is a real train/inference shift, ADR 0060). Two sessions read 38 GB of dumps
for stand features this file already had. **Only `REC` has no log** (pure observation ⇒ no harness starts);
supply it offline with `scripts/diagnose_rung2_map_on_rec_stand.jl`.

⚠ **AND CHECK WHICH `--n-prev` MODE THE RUNS USED — it decides whether your statistic exists at all.**
All 767 dumps written before 2026-08-13 are `roster`, where `n_prev` is the LIVE stand count; measured, `target` then lies within
±5 % of it in 84–87 % of patch-years and `target/n_emit` = 1.00 ± 2.3 % (ADR 0184). So in `roster` mode
**the map's target and the stand's own count are the same quantity**, any comparison between them is
degenerate, and a persistence null (`target = n_prev`) reproduces FIT's count direction at 12/12 cells *by
construction* — it will pass a sign-agreement basis check that looks like skill. `predict` mode (the shipped
coupled path, `n_prev[patch] = target`) decouples them to ±24 %. **Do not use |ρ−1| to test for this**: ρ is
a year-on-year ratio of two smooth tree-ensemble outputs and sits near 1 in *both* modes. Use
median |`target`/`n_emit` − 1|, and require > 0.10 before reading any response statistic.

**Both scorers now take `NPREV` (default `roster`) and there is a `predict` matrix on disk** — 264 jobs,
258 completed, tags `S_r2s_<scen>_c<cell>_<arm>_predict_s<seed>` (ADR 0185). Measured separability on the
ssp370 leg: `REC` 0.132 · `NP` 0.347 · `S0` 0.244 · `S0h`/`S1` 0.18, against 0.018–0.031 for every `roster`
arm and leg. Three things to carry over:

* ⚠ **THE MODE KNOB MUST REACH EVERY SCRIPT IN THE CHAIN, INCLUDING THE REFERENCE ARM'S.** `REC` has no
  runtime log, so its `target` column is replayed offline by `diagnose_rung2_map_on_rec_stand.jl`. Leaving
  that replay in `roster` while the arms are in `predict` puts **the reference on a tethered axis and the
  arms on a free one** — invisible in every output, and it would have inflated `REC`'s score back toward
  the null's. Set `NPREV` on both, and check each script names its mode in its own header line.
* **Gate an added recursion on the year it CANNOT change, not on an aggregate.** In `predict` mode a
  patch's first year seeds `n_prev` from `n_emit`, so it must reproduce the `roster` replay bit-for-bit
  while later years must not: measured **600/600 first-year rows identical, 78.3 % of 29 700 later rows
  differing**. One aggregate agreement number cannot tell "wired in" from "the seed moved too".
* ⚠ **A gate met on one leg and missed on another is a DERIVATION problem.** The `predict` historic leg
  reaches only 0.079–0.099. Keying on ssp370 is defensible because the blessed statistic is a *difference
  of leg means*, so a tethered BASELINE leg deletes the term `ASK_hist − GOT_hist` from the ASK-vs-GOT
  contrast rather than collapsing it (degeneracy needs BOTH legs tethered) — but that reading was chosen
  after seeing the numbers, so the scorer prints the strict per-leg alternative (NO VERDICT) every run.
  Do the algebra of what your statistic needs from each leg *before* picking.

⚠ **RUN THE PYTHON SCORERS WITH `/home/jamirp/.conda/envs/py311_new/bin/python`, NOT `/usr/bin/python3`.**
The system python is too old for `zip(..., strict=True)` and dies `TypeError: zip() takes no keyword
arguments` **two thirds of the way down the output** — after the separability gate and the per-cell table
have already printed convincingly. A partial run that dies below the fold looks like a complete one.

## The four phases, and which one you want

`patches/lpjmlfit_rung2_hook_v5.patch` writes at four points in `annual_natural`:

| phase | state | use it for |
|---|---|---|
| `pre` | before turnover/allocation/mortality | almost never — `mort_*`/`bm_delta`/`leafarea_real` are **uninitialised garbage** here and at a recruit's establishment year |
| **`grow`** | after this year's turnover/allocation/**hazard**, before anyone is removed — the rendezvous | **the default choice.** It is the exact analogue of the runtime feature point (`slow.jl` builds `flux_feature_vector` from the GROWN pools, before `reconcile_demography!` removes anybody), AND it carries this year's hazard: verified that for a stem present at both, all five `mort_*` are bit-identical at `grow` and at `mort` |
| `mort` | after the demographic hazards, before fire | when you need the post-hazard roster specifically. Note it is missing the stems this year's hazard killed — which is why a certain-set comparison uses `grow` |
| `post` | after mortality AND establishment | recruits |

## The traps

1. **⚠ THE HEADER-TO-FIELD OFFSET.** The header is `#H T phase lon lat …` while a record is
   `T grow <lon> …`, so **name *n* lives at field *n+1*** (field 0 is the `T` tag). Getting it wrong fails
   loudly on a string column (`int('51.25')`) and **silently between two columns of the same type**. Parse
   the `#H` line for positions — never hardcode offsets; the writer's column set has grown across hook
   versions (v3 → v5 → v6).
2. **⚠ THE COVERAGE GATE IS NOT OPTIONAL — 92 of 510 legs are incomplete.** Two known interface faults
   (`ERROR043 duplicate roster key` killed 82 runs; cell 22732 hangs) truncate dumps *mid-leg*, and a
   truncated dump looks exactly like a short one. Require every year of the leg present with all 25 patches,
   **exclude and NAME the failures**, and expect ~12 scoreable cells, not 15. A statistic that needs only
   per-stem rows (a hazard comparison) can still use a truncated dump — say which kind yours is.
3. **⚠ `ERROR043` IS TWO DIFFERENT FAULTS — READ THE MESSAGE, NOT THE CODE.**
   * `rung2 apply: duplicate roster key (pft P, tree N)` — the C-side interface fault (line M's
     `rung2_apply.c:118`, gated on *either* env var so it fires in the pure OBSERVATION path too). Killed 82
     of 510 `roster` runs; cells 23318/33335 lose both baselines, 46336 its ssp370 one. Mechanism OPEN.
   * `rung2 apply: no answer for year <Y> patch <P> after 600 s` — a **harness-side idle timeout**, not an
     interface fault. The harness exits *cleanly* on its `--max-idle` (default 300 s) while the C is still
     running — its log ends `harness: served <N> patch-years` with N short of the leg — and the C then waits
     600 s and dies. Cost 6 of 264 `predict` runs, all late ssp370 (2071–2094). Fix by raising `--max-idle`
     in `scripts/run_rung2_s_arm.sh` above the C's own 600 s wait.
4. **⚠ THE RUN LOG GLOB IS `lpjml.*.out`, NOT `lpjml_*.out`.** The wrong one matches nothing, so a
   completion-line count over a healthy matrix reports **0** and looks like total failure. Same family as
   CLAUDE.md §3's "a 0-byte log is a provenance FATAL, never a physics verdict" — confirm the glob matches
   *something* before reading a zero as a result.
5. **⚠ IN A RUNG-2 ARM THE C GROWS THE STAND.** The emulator only decides who dies. So any stand-derived
   statistic is **inherited by every arm, including `NP`** — ADR 0182 measured the do-nothing null tracking
   FIT's stand-shift direction at 0.910, as well as `S1`. Such a statistic can clear or convict a
   hypothesis; it cannot rank arms. Score `NP` on the same statistic and print its number in the same table.
   For the same reason a rung-2 result can never indict the Julia **fast core**, which never runs here.
6. **`age` at `grow` is POST-increment** (the C's hazard used `age − 1`; ADR 0031's off-by-one). Subtract 1
   when feeding a ported equation; a constant offset cancels in a difference-of-means-over-sd statistic but
   not in a level.
7. **Empty patches emit no `T` record** but are a real all-zero stand row at runtime — enumerate patch-years
   from the `P grow` records, not from the trees.
8. `leaf_c`/`sapwood_c`/`heartwood_c` are `tree->ind.*.carbon`, i.e. **per individual** — multiply by `nind`
   exactly where the runtime does.

## Existing scorers — extend one before writing a new one

| script | what it does |
|---|---|
| `scripts/diagnose_rung2_stand_warming.py` | the six stand features per (year, patch) from `grow`, leg shifts in per-cell sd units vs `REC`, liveness panel, drift control. **Caches one `.npz` per dump under `/p/tmp/jamirp/S_rung2_standwarm/cache/`, keyed by size+mtime — reuse that cache rather than re-reading 38 GB.** |
| `scripts/diagnose_rung2_ported_certain_set.jl` | per-stem ported hazard vs FIT's own `mort_prob`, certain-set recall/precision, and a zeroed-stress arm that evaluates the hazard as the COUPLED loop runs it |
| `scripts/diagnose_rung2_response.py` | the per-cell count response by arm/scenario/seed |
| `scripts/diagnose_rung2_map_on_rec_stand.jl` | the count model run over **FIT's OWN** roster, i.e. the `target` column `REC` has no log for. `include`s the harness for `Tree`/`pools_of`/`flux_drivers` so the row reaches the SHIPPED `flux_feature_vector` + `DRF.predict` (ADR 0023); ~15 s for all 30 REC dumps. **Its gate is the pattern to copy: at year 2000 no arm has killed anything yet, so its row must equal the live `s_arm_log.txt` to the last digit — verified bit-identical.** |
| `scripts/diagnose_rung2_map_target_response.py` | ASK (the count the map asked for) vs GOT (the count the stand reached) vs FIT, per cell and arm, off the arm logs; the ρ/tether panel, the stand-LEVEL departure table, the drift and frozen-boundary controls (ADR 0184). Takes `NPREV`; prints the pre-registered SEPARABILITY GATE before any response statistic and suppresses the verdict for a tethered arm (ADR 0185). |
| `scripts/diagnose_rung2_armc.py` | age–wooddens gradients and selection differentials (shared with line M's arm C; **each arm family has its own recorded baseline and they are NOT interchangeable**) |
| `scripts/rung2_s_demography_harness.jl` | **the row assembly.** It reaches `flux_feature_vector` and `DRF.predict` as private names off the package rather than copying them — do the same, or the copy becomes the thing being measured (ADR 0023). |

**Reach ported physics as the shipped name** (`LPJmLFITEmulator.TraitMortality.mortality_hazard`,
`flux_feature_vector`) and feed it only dumped columns. That is what makes an agreement result meaningful:
ADR 0183's 5e-18 match over 1 568 744 stem-years would have proved nothing had the scorer re-derived any
input. And **check what a harness actually feeds its own test before building on it** — ADR 0176 §4's whole
blocker rested on `Tree.mort` being FIT's hazard when its own declaration comment says it is the port.

## Mechanics

Both scorers run off the login node only for a smoke test on a symlink dir of 2-4 dumps; the full scan goes
to SLURM (`scripts/sbatch_python.sh S-<tag>` / `scripts/sbatch_julia.sh S-<tag> --project=.`). **`export`
every env knob** — the wrappers forward only a fixed list of names. Python: lint with the repo's real rule
set, `ruff check --select E,F,I,UP,B --line-length 100` (CI does not lint `scripts/*.py`, so nobody else
will). Julia: the repo-wide Runic `format` gate DOES cover `scripts/**` — run the check from the
`julia-test` skill before pushing.
