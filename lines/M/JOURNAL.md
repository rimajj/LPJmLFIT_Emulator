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
