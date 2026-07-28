# JOURNAL — LINE M (multi-cell coupled S+F+E (P3))

> **Append-only, newest at the bottom.** Narrative for THIS LINE only: what you did, the commands, the
> results, dead ends. Durable state goes to `lines/M/STATE.md` (and its `## NEXT` block — refresh it before
> your session ends); cross-cutting durable facts go to `MEMORY.md`; the story of one change goes to a
> `changelog.d/M-<slug>.md` fragment. Pre-split history for the whole project: the root `JOURNAL.md`.
>
> Entry template:
> ```
> ## YYYY-MM-DD — <short title>  [milestone M<n>]
> - **Goal:**
> - **Did:**
> - **Result / evidence:** (numbers, job ids, gate outcomes)
> - **Decisions:** (ADR NNNN if any)
> - **Next:** (mirror into STATE.md's NEXT block)
> ```

## 2026-07-28 — line created (ADR 0028/0029)
- **Goal:** stand up line M as an independent work line so it can run concurrently with the other lines.
- **Did:** created by the Phase-0 setup session on `main`: branch `line/M` + worktree `wt-M`,
  `lines/M/{STATE.md,JOURNAL.md}`, ADR block assigned, ownership recorded in ADR 0029.
- **Result / evidence:** see the root `JOURNAL.md` Phase-0 entry for the setup evidence.
- **Decisions:** ADR 0028 (branch+worktree per line, supersedes 0013), ADR 0029 (the split + ownership).
- **Next:** the `## NEXT — start here` block in `lines/M/STATE.md`.

## 2026-07-28 — M1: per-cell input provisioning (soil column + canopy + registry)  [milestone M1]
- **Goal:** unblock M1 — give every biome cell its OWN inputs instead of Hainich's soil column and Hainich's
  canopy. The named starting point was the piece with no script at all: a per-cell soil-column extractor,
  gated on reproducing the committed `hainich_soilcolumn.txt`.
- **Did:**
  - **Recon (5 parallel readers)** over the C source, the Julia `SoilColumn` contract, the python-script
    conventions, D95 provenance, and the live NetCDF/parquet data. Findings that changed the design:
    `whc_nat` is the patch-mean whc **fraction** and is **time-varying + `-DPERMUTE`-nondeterministic**; layer
    thicknesses are a C global (`newgrid.c:282` throws the per-cell Pelletier depth away); `beta_root` — not
    `D95` — is the C's actual root-profile parameter; `hainich_soilcolumn.txt`'s `D95=115 cm` is hand-rounded
    with no committed derivation (the generator survives only as an uncommitted scratch JSON).
  - **Generated new oracle data:** single-cell daily re-runs of the four non-Hainich biome cells
    (`run_fdiff_validation_cell.sh RUNTAG=M_biome_val`, jobs 1615264/66/68/71 — each ~9 s), adding
    `d_fapar` + `a_lai_stand` + `a_fpc_stand` + a single-cell `whc_nat.nc` per cell. Water-closure checked.
  - **Wrote `scripts/extract_cell_soilcolumn.py`** (whcs from `whc_nat`×thickness, float32 240-month mean;
    rootdist = fpc-weighted mean of per-individual `getrootdist.c` profiles with the rooted depth recovered by
    inverting the emitted `D95`) and **`scripts/extract_cell_individuals.py`** (N-cell generalization of
    `extract_fdiff_individuals.py`, importing its physics rather than copying it, validated per cell against
    that cell's own C FAPAR).
  - **Removed the hard-coded cell lists:** `extract_biome_forcing.py` now holds THE registry (`cells_from_env`)
    that both new extractors import, and `references/M_cells.csv` carries cell/lat/lon from `grid.nc`.
  - **Rewrote** `scripts/run_coupled_biomes.jl` (runs per-cell AND legacy common-Hainich, so the
    vegetation+soil effect is separable) and `test/testitems/biome_coupled_tests.jl` (two test items; adds the
    "inputs are pairwise distinct" regression guard).
  - **Fixed a cross-line footgun:** `extract_biome_forcing.py`, `extract_fdiff_validation_inputs.py` and
    `validate_fdiff_structure.jl` bound the repo root to the hard-coded integrator path, so running them from a
    line worktree wrote fixtures into `$INT`'s working tree. Now derived from `__file__` / `@__FILE__`.
- **Result / evidence:**
  - **GATE PASS** — re-extracting cell 42490 (`d95_scalar`, `D95=115`, single-cell whc source) reproduces all
    23 printed rows of `hainich_soilcolumn.txt` **byte-identically**; `max|Δwhcs| = 3.7e-5 mm`,
    `max|Δrootdist| = 4.3e-7`, `Δsoildepth = 0`.
  - Individuals extractor reproduces the committed Hainich numbers exactly (`cell_fapar_leafon` 0.8339690,
    297/272/25). Per-cell reconstructed/C-peak FAPAR ratio 1.28–1.64 (Hainich 1.60) — the known leaf-on basis
    overshoot, consistent across all five cells, so no cell is anomalous.
  - Emergent rooting gradient (top-1 m root fraction / effective D95): Sahel 99.3 % / 72 cm · boreal 88.6 % /
    160 cm · Hainich 87.8 % / 178 cm · mediterranean 61.5 % / 376 cm · Amazon 53.2 % / 690 cm.
  - Coupled 10-yr run (job 1617060): energy closes 0–2.8e-14 W/m² in every cell. Vegetation+soil effect vs the
    legacy common canopy: Amazon **+10.8 W/m² LE**, Sahel **−7.6**, mediterranean Bowen **1.27 → 0.65**,
    Sahel GPP 347 → 110.
  - **Suite 106,987 pass / 0 fail / 4 broken** (job 1617065, 5m42s) — +69 assertions over the 106,918 baseline.
    Runic clean over `src test ext scripts`.
- **Decisions:** **ADR 0050** — per-cell input provisioning: `whc_nat` time-mean soil column + community-mean
  `getrootdist` root profile, gated on the committed Hainich column. `hainich_soilcolumn.txt` and
  `hainich_individuals_2010.csv` deliberately NOT regenerated (guardrail 4 / ADR 0029).
- **Dead ends / traps paid for:** a gate against the **global** `whc_nat.nc` cannot pass (1.6e-4 relative in
  layer 0); a float64 time mean changes 5 of 23 printed values; the unnormalized single-scalar-β profile does
  not sum to 1 for deep-rooted communities (0.99999999 for the boreal cell) — which is silently physical, since
  F_diff's water supply scales linearly with `sum(rootdist)`.
- **Next:** M2 — wire the flux-driven S into the multi-cell driver (see STATE.md's NEXT block).

### Addendum — independent cross-check of the per-cell chain (2026-07-28)
The Hainich gate proves the *derivation*, but it cannot catch a **mis-mapped cell** (a wrong `grid.nc`
`cellid` lookup or the wrong per-cell run would still reproduce Hainich). Falsifiable second check, from the
soil codes in `soil_code_test.soil.bin`: three biome cells share **soil code 7 (loam)** — boreal Siberia
(52059), mediterranean Iberia (33335), tropical Amazon (12045) — on three different continents. Since the
deep layers carry ~no organic matter, Saxton–Rawls gives `whc = f(sand, clay)` only, so their DEEP-layer
`whc` must be identical.
- layers 10/15/21: `0.15127945 / 0.15124385 / 0.15124735` — spread **3.6e-5** (2.4e-4 relative).
- layer 22: spread **1.3e-5**.
- and they must differ from the other soil types, which they do: code 4 (clay loam, Hainich) **0.17421**,
  code 9 (sandy loam, Sahel) **0.11545**. Ordering sandy loam < loam < clay loam is pedotransfer-correct.
- meanwhile the **top** layer legitimately differs *within* code 7 — 0.2099 (boreal) / 0.1977 (Amazon) /
  0.1676 (Iberia) — the organic-matter term, highest where soil carbon is highest (cold boreal), lowest in
  dry Iberia. So the chain reproduces both the invariant and the variable part for the right reasons.
Conclusion: the `cellid` mapping, the per-cell run selection and the layer indexing are all independently
confirmed — not just the arithmetic.

### Addendum 2 — adversarial review of M1 and the hardening it forced (2026-07-28)
Ran a 4-lens adversarial review (physics faithfulness vs the C / does-the-gate-prove-anything /
would-the-tests-catch-a-regression / protocol+reproducibility) over the four M1 commits. 16 candidate
findings; the judge phase died on a session limit, so they are **unverified candidates** — but several
survived my own inspection and were real. What they found and what I changed:
- **★ The gate certified a path no emitted file takes.** It ran `ROOTDIST=d95_scalar` (the legacy form) while
  every emitted column uses `beta_mean`, so the entire `getrootdist.c` port + D95 inversion + fpc weighting
  was covered by *nothing*. Added `gate_getrootdist()`: the port now matches an independent closed-form
  evaluation of the C algorithm to **0.00e+00** for a case rooted exactly into layer 3, plus invariants
  (sum==1 to 1e-12, layer 22 == 0, non-negative) over the real committed β range 0.943–0.9991.
- **★ ADR 0050 contained a factual error.** I wrote that the permafrost root redistribution could not be
  ported because "no output carries that thaw state". Wrong: `MAXTHAW_DEPTH` is a declared annual output
  (`par/outputvars.js:201`); our runs merely never requested it. Corrected in the ADR + script header, and the
  boreal column's deviation is now stated concretely (the C would return exactly 0 below layer 4 for
  `mean_maxthaw ≈ 2 m`; ours carries 8.4e-4 there).
- **★ The `[VERIFIED]` inversion claim was overstated.** `dR/dD95 = β^D95/(β^D95−0.05)` diverges at the
  asymptote, and `D95`/`beta_root` reach the parquet via `%g` (6 sig digits), so a measured
  1.8/13.2/1.4/2.8/14.8 % of living trees per cell (**35.3 % of the fpc weight at Hainich**) hit `arg ≤ 0` and
  fall back to `R = ∞`. Quantified in the ADR; `k_root` (ind col 20) noted as the principled fix.
- `WHC_SRC=global` printed GATE PASS then emitted uncertified whc → now aborts unless `ALLOW_UNGATED_WHC=1`.
- `find_whc_run`'s glob matched short debug re-runs, which sort FIRST in ASCII order and would silently swap
  both the whc source and the averaging period → pinned to the historical window + `nstep` asserted.
- A subset `CELLS=` run (the documented way to re-extract one cell) truncated `M_cells.csv` from 5 rows to 1
  → both scripts now MERGE by name. Verified: a `CELLS="boreal_siberia:52059"` run leaves all 5 rows.
- Test item 1's orderings were permutation-insensitive: an adversarial sweep of all 120 permutations of the
  five committed columns found **4** that satisfy every assertion (identity, boreal↔sahel, med↔amazon, and
  the 4-cycle) → added per-cell provenance PINS (top-1 m whcs, total whcs, top-1 m root fraction), row-wise
  name→(cell,lat,lon) instead of an order-blind Set, the FAPAR-ratio band, and `rd[end] == 0`. Tightened the
  `sum(rootdist)` tolerance 2e-5 → 2e-6 (max committed deviation is 1e-6).
- Re-verified after all of it: the 11 committed artifacts still reproduce **byte-identically** (0/11 differ).
**Left open** (in STATE.md "M1 review debt"): item 2 still has no provenance sensitivity — it passes with
all-Hainich inputs, so a driver-level fallback in M2 would not be caught; `GATE=no` leaves no trace in the
artifacts; and `CLAUDE.md` §9 contradicts itself on whether `MEMORY.md` is shared-additive or integrator-only.

### Addendum 3 — merge blocked by a JET 0.12.0 dependency bump (2026-07-28)
After the hardening, `line/M` sha `693322fa` came back with `test (1)` (Julia 1.12) **red** while
`test (lts)`, `format`, `python` and `test (macOS, lts)` were green. The diff touched only python scripts,
`biome_coupled_tests.jl` and docs — no `src/` — so this is the "CI red with the test tree unchanged ⇒ suspect
a dep bump" pattern (CLAUDE.md §5). Diagnosis from the job log:
`JETConfigError: Given unexpected configuration: `target_defined_modules = true``, with the log's package path
showing **JET v0.12.0**. `test/Project.toml` has no `JET` entry in `[compat]`, and CI resolves fresh, so 1.12
picked up the brand-new 0.12.0, which removed the option `test/jet_tests.jl:6` passes.
Evidence it is not mine: `b106cdae` was green on `test (1)` with JET 0.11.6; `main`'s last run (`c470711e`) is
still green only because it predates the release. **The next push to `main` or to any line goes red the same
way.** The one-line fix (`JET = "0.9, 0.11"` beside the Enzyme pin) lives in `test/Project.toml` `[compat]`,
which ADR 0029 makes **integrator-only**, so line M did not apply it — recorded as the top-line blocker in
`lines/M/STATE.md` and as an integrator TODO in `MEMORY.md`. M1 itself is complete: local suite
**107039 pass / 0 fail / 4 broken** on Julia 1.10 (job 1621984), Runic clean, docs build green, the 11
committed artifacts byte-reproducible.

---

## 2026-07-28 — session: unblock CI repo-wide, then open M2 (artifact pin + the coverage gap)

**1. The JET 0.12.0 blocker: diagnosed as repo-wide, fixed on `main`.** Last session left M1 complete and
green except `test (1)`, red from a fresh JET **0.12.0** resolve that removed the `target_defined_modules`
config `test/jet_tests.jl:6` passes. Confirmed from the job logs that it was *not* a line-M defect: the
identical `JETConfigError` appears on line/M `693322fa` (job 90278705919, a docs+tests-only diff) **and**
line/O `11ef8d89` (job 90275445875), while `test (lts)` stayed green because JET 0.11+ needs Julia ≥1.12 so
1.10 caps at 0.9.20. `test/Project.toml` `[compat]` is integrator-owned (ADR 0029) and the breakage blocked
all four lines from merging, so I landed the one-line pin `JET = "0.9, 0.11"` directly on `main` (`47c6407a`)
rather than on this branch. **Verified: `main` 47c6407a `test (1)` = success.** Both pinned versions were
already in the shared depot, so the compute-node warm needed no new tarball. `test (pre)` remains red for the
known unrelated prerelease churn.

**2. Suite green after rebasing onto the pin:** 107,039 pass / 0 fail / 4 broken, 86/86 items, 5m41s
(`M-suite-jetpin`, job 1622318). Also fixed the `julia-test` skill, whose "run the suite" recipe still said
`cd /p/projects/open/Jamir/esm_land_emulator` — now the *integrator* worktree, so following it from a line
session would have submitted a suite testing `main` instead of the branch under test.

**3. M2 step 1 — pinned the S artifact, contracts VERIFIED not assumed.** Chose
`drf_forest_global_pooled_w20.drf` + `recruit_copula_global_pooled_w20.rcop` (sha256s in STATE.md): the DRF
meta's `colnames` (nfeat 15 = 11 head + 4 boundary) matches `flux_feature_vector` exactly, and the copula
meta's `cond_cols` (ncond 8) matches `live_flux_cond` = `vcat(feats[1:4], s.boundary)`. That fixes the
per-cell boundary vector as `[eco_diag_gdd_5, tas_cold_month, soil_depth, co2]`. Deliberately did **not**
adopt the `_t7` retrain that appeared today — S was still producing it (job 1622131) and there is no `_t7`
`.rcop`.

**4. Then the gate I wrote found that the pin cannot serve all five cells.** `scripts/extract_cell_slow_init.py`
folds the per-cell S seed + boundary out of `cell_meta.parquet` into the committed `M_cells.csv`, and aborts if
a requested cell is missing. Running it against the pinned artifact's own tables:
**`semiarid_sahel` (18371) is in NEITHER `slow_count_historic_w20` NOR `slow_count_ssp370_w20`** — the pinned
DRF never saw the cell. Only the `_t7` family covers 5/5. STATE.md's inherited claim that
`slow_runtime_historic` contains "all five biome cells" was simply **wrong** (it holds 3/5) — that is the value
of gating rather than trusting a handoff note.

**5. Two measurements that constrain how per-cell S state may ever be sourced.**
- `n_init`/`age0` are the per-cell **median over training years** of `n_living` / `age_mean`
  (`build_slow_runtime_table.py:320-332`), i.e. statistics of the *training window*. Across the 44,328 cells
  shared by `slow_runtime_historic` and its `_t7` retrain, `n_init` differs for 15,665 cells (max |Δ| 24) and
  `age0` for 22,542 (max |Δ| 85 years). So they are version-coupled, and — usefully — **not** derivable from
  the committed single-year canopy, which closes a shortcut I had started to design.
- The 4 boundary columns are byte-identical across *versions* of the same scenario, but differ across
  *scenarios* by up to **1513 GDD** and **8.84 °C** (43,901 shared cells) — they are climate diagnostics of
  different climates. Hence a POOLED artifact has two boundary rows per cell, which promotes the per-cell
  `ClimBuf` (M2 step 3) from optional to required. The invariance check inside the extractor is what surfaced
  this: it refused the cross-scenario borrow instead of silently averaging two climates.

**Deliberately left undone:** `M_cells.csv` is NOT yet extended. Emitting it from `_t7` while the pin says
`pooled_w20` would silently adopt the unpinned retrain — precisely ADR 0023's trap. Resolving the pin is
step 0 of the next session and is an integration point with line S.
