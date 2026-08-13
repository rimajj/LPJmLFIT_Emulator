---
name: rung2-dump-analysis
description: Read and score the rung-2 roster dumps — the per-tree state LPJmL-FIT writes at the demography rendezvous when the emulator substitutes its mortality (line S, ADR 0175). Use whenever a question about the rung-2 arms can be answered from state already on disk instead of a new LPJmL run: an arm's own stand features (hmean/hmax/agb/lai/fpc/age_mean), its per-stem hazards or certain-kill set, its trait/age distributions, a historic-vs-ssp370 leg comparison, or FIT's own values as the like-for-like reference. Names the dump layout `/p/tmp/jamirp/S_rung2/S_r2s_<scen>_c<cell>_<arm>_roster_s<seed>_dump/roster_rank0000.txt`, the arms REC/NP/S0/S0h/S1, the four phases pre/grow/mort/post and why `grow` is almost always the right one, the `#H`-header-to-field OFFSET that silently mis-reads two same-typed columns, the coverage gate that 92 of 510 legs fail, and the existing scorers scripts/diagnose_rung2_stand_warming.py, scripts/diagnose_rung2_ported_certain_set.jl, scripts/diagnose_rung2_response.py, scripts/diagnose_rung2_armc.py. ALSO the rule that in a rung-2 arm the C GROWS THE STAND, so any stand-derived statistic is inherited by every arm including the do-nothing null and cannot rank arms.
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
3. **⚠ IN A RUNG-2 ARM THE C GROWS THE STAND.** The emulator only decides who dies. So any stand-derived
   statistic is **inherited by every arm, including `NP`** — ADR 0182 measured the do-nothing null tracking
   FIT's stand-shift direction at 0.910, as well as `S1`. Such a statistic can clear or convict a
   hypothesis; it cannot rank arms. Score `NP` on the same statistic and print its number in the same table.
   For the same reason a rung-2 result can never indict the Julia **fast core**, which never runs here.
4. **`age` at `grow` is POST-increment** (the C's hazard used `age − 1`; ADR 0031's off-by-one). Subtract 1
   when feeding a ported equation; a constant offset cancels in a difference-of-means-over-sd statistic but
   not in a level.
5. **Empty patches emit no `T` record** but are a real all-zero stand row at runtime — enumerate patch-years
   from the `P grow` records, not from the trees.
6. `leaf_c`/`sapwood_c`/`heartwood_c` are `tree->ind.*.carbon`, i.e. **per individual** — multiply by `nind`
   exactly where the runtime does.

## Existing scorers — extend one before writing a new one

| script | what it does |
|---|---|
| `scripts/diagnose_rung2_stand_warming.py` | the six stand features per (year, patch) from `grow`, leg shifts in per-cell sd units vs `REC`, liveness panel, drift control. **Caches one `.npz` per dump under `/p/tmp/jamirp/S_rung2_standwarm/cache/`, keyed by size+mtime — reuse that cache rather than re-reading 38 GB.** |
| `scripts/diagnose_rung2_ported_certain_set.jl` | per-stem ported hazard vs FIT's own `mort_prob`, certain-set recall/precision, and a zeroed-stress arm that evaluates the hazard as the COUPLED loop runs it |
| `scripts/diagnose_rung2_response.py` | the per-cell count response by arm/scenario/seed |
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
