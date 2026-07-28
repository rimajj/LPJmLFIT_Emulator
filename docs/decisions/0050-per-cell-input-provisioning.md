---
status: "accepted"
date: 2026-07-28
deciders: "line M (session 1)"
consulted: "LPJmL-FIT 5.6.004 C source (soilpar_output.c, pedotransfer.c, fscansoilpar.c, getrootdist.c, getbetaroot.c, new_tree.c, fwriteoutput_ind.c, newgrid.c); the committed test/testitems/references/hainich_soilcolumn.txt and its uncommitted generator JSON; ADR 0029 (path ownership + shared references); guardrails 3/4/5 (C binary is the oracle, opt-in default byte-identical, adversarially re-derive ported physics)"
informed: "lines/M/STATE.md, CLAUDE.md §7 source map, the fdiff-validate skill"
---

# Per-cell input provisioning for the multi-cell coupled driver: the `whc_nat` time-mean soil column and the community-mean `getrootdist` root profile

## Context and Problem Statement

`run_coupled_cell` has always been N-cell-agnostic — it takes a per-cell `FDiffFastCore` plus a latitude.
What blocked genuine multi-cell running (milestone M1, the gate on everything else in line M) was
**inputs**: the five biome cells in `test/testitems/biome_coupled_tests.jl` all reused **Hainich's** soil
column and **Hainich's** canopy. That was deliberate — it isolated the climate effect — but it means the
existing multi-cell evidence covers F+E under five climates, not five *ecosystems*.

The soil column in particular had **no generating script at all**. `references/hainich_soilcolumn.txt`
(23 rows of `layer soildepth_mm whcs_mm rootdist`) was produced ad hoc in an earlier session; the only
surviving generator artifact is an uncommitted scratch JSON. So provisioning a second cell required first
reconstructing how the first one was built, and then deciding what the per-cell quantities *are* — because
two of the three columns are not simply "a number stored somewhere for this cell".

Specifically: LPJmL-FIT's plant-available water per layer (`whc`) is **not a static soil property** (it is
recomputed twice a day from the evolving soil-carbon profile), and the root profile is a **property of the
vegetation**, i.e. of a whole distribution of individuals with different traits. Each therefore needs a
stated reduction, not a lookup.

## Decision Drivers

- **The C binary is the oracle (guardrail 3).** Where the C emits the quantity, read it rather than porting
  a pedotransfer function.
- **A falsifiable correctness gate before trusting any new cell (guardrail 7).** Re-deriving the ONE cell we
  already have must reproduce it, or the extractor is unproven.
- **`references/` is shared and its baselines are load-bearing (ADR 0029, guardrail 4).**
  `hainich_soilcolumn.txt` feeds sixteen test files and several committed ReferenceTests baselines, so
  regenerating it is an integration point, not a line action.
- **One rule for every cell.** A per-cell input set where one cell is special cannot support M3's
  per-cell error-vs-noise-floor scoring.
- **Silent physical wrongness is the real risk.** F_diff's water supply scales *linearly* with
  `sum(rootdist)` (`src/fdiff.jl:846,928`) and `stand_structure_tof`'s D95 loop (`src/run.jl:65`) never
  terminates if the profile sums below 0.95, while a zero `whcs[l]` produces a `NaN` that propagates into
  `SharedState.w`. None of this is validated by the constructor.

## Considered Options

**Per-layer plant-available water (`whcs_mm`)**

- **A1. Read the C's own `WHC_NAT` output and multiply by the layer thickness**, reducing its time axis by a
  mean over all monthly steps.
- **A2. Port the Saxton–Rawls pedotransfer** (`pedotransfer.c`) from the soil code + soil-carbon profile.
- **A3. Use a single time slice of `WHC_NAT`** (e.g. the first month, or the reference year).

**Root profile (`rootdist`)**

- **B1. One community-scalar D95 → `beta = 0.05**(1/D95_cm)`**, the unnormalized Jackson difference profile
  (what the committed Hainich column did).
- **B2. The fpc-weighted mean over the cell's living trees of each individual's own profile, ported from
  `getrootdist.c`** (Jackson renormalized over the depth that individual's roots reach).
- **B3. Port `getrootdist.c` exactly, including the permafrost `mean_maxthaw` redistribution.**

## Decision Outcome

**A1 + B2**, implemented in `scripts/extract_cell_soilcolumn.py` (+ `scripts/extract_cell_individuals.py`
for the canopy and `M_cells.csv` for the cell/lat registry), gated on exact reproduction of the committed
Hainich column.

### What is emitted, and from what

| Column | Source | Reduction |
|---|---|---|
| `soildepth_mm` | `depth_bnds` of the run's own `whc_nat.nc` | none — **cell-invariant** in the C (`fscansoilpar.c:36-39` reads `soildepth[NSOILLAYER]` once from `par/soil_20m.js`: 200,300,500,1000×19,3000 mm). Asserted against that array, not assumed. |
| `whcs_mm` | `WHC_NAT` × thickness | **mean over all monthly steps, accumulated in float32** |
| `rootdist` | the annual `ind` table's per-individual `beta_root` + `D95` | **fpc-weighted mean of per-individual `getrootdist.c` profiles** |

`whcs = whc * soildepth` is the C's own definition (`include/soil.h:222`), and `WHC_NAT` is the
patch-ensemble mean `whc` **fraction** (`soilpar_output.c:42`:
`WHC_NAT[l] += patch->soil.whc[l]/stand->npatch`), so A1 is not an approximation of the C — it *is* the C,
with only the time reduction added.

### The correctness gate

Re-extracting cell 42490 in the legacy `d95_scalar` mode with `D95_CM=115` reproduces all 23 printed data
rows of `hainich_soilcolumn.txt` **byte-identically** (`max|Δwhcs| = 3.7e-5 mm`, `max|Δrootdist| = 4.3e-7`,
both below the `%.4f`/`%.6f` print resolution). Three findings were load-bearing to get there, and each is
now recorded in the script header:

1. **The fixture came from the SINGLE-CELL run** `daily_2000_2019_fdiff_val_c42490_seed1`, not the 512-task
   global run. Under `-DPERMUTE` the two diverge by up to 1.6e-4 relative in layer 0 (whc depends on the
   stochastic patch soil-carbon ensemble), which is 40× the print resolution — a gate against the global
   file cannot pass.
2. **The time mean must accumulate in float32** (the on-disk dtype). Promoting to float64 first changes 5 of
   the 23 printed values.
3. **`D95 = 115 cm` is hand-rounded with no derivation.** No statistic of the `ind` table equals it (tree
   mean 116.63 cm in 2010, 114.24 cm over all years, 115.30 cm via mean `beta_root`), so the gate passes it
   explicitly rather than pretending to re-derive it.

### Why B2 over B1

`beta_root` **is** the C's root-profile parameter: `new_tree.c:230` sets
`beta_root = getbetaroot(2000 cm, D95max)` and `getrootdist.c` consumes it. The emitted `D95` column is a
*diagnostic* — the rooting-depth-limited realized 95 % depth (`fwriteoutput_ind.c:104`) — and
`D95 ≠ log(0.05)/log(beta_root)` for 86.6 % of Hainich trees, so B1 conditions the profile on the wrong
variable and then collapses a whole trait distribution to one scalar.

The rooted depth that `getrootdist` needs is not in the frozen 29-column schema, but it is recoverable by
inverting the emitted `D95`:
`R_cm = ln(1 − (1 − beta**D95)/0.95) / ln beta = min(rootdepth/10, soildepth·100)`.
[VERIFIED on all five biome cells: wherever the inversion is well-conditioned, `R ≥ D95` for every
individual and `R ≤ 2000 cm` (one Amazon individual at 2027 cm, within `getbetaroot`'s own
`EPSILON = 1e-4`).]

**It is NOT exact everywhere, and this bounds the derivation's fidelity.** Since
`arg = 1 − (1 − beta**D95)/0.95 = (beta**D95 − 0.05)/0.95`, we have
`dR/dD95 = beta**D95 / (beta**D95 − 0.05)`, which diverges as `D95` approaches its unlimited-depth
asymptote `ln 0.05 / ln beta`. The `ind` table prints `D95` and `beta_root` through `%g` (6 significant
digits, `printind`), so for individuals sitting at that asymptote the rounded values give `arg ≤ 0` and the
inversion degenerates. Those individuals are assigned `R = ∞` — i.e. "roots reach the whole 20 m column",
the correct limit but an over-deep approximation for any whose true `R` was merely large. Measured share
per cell (2010, living trees / share of the fpc weight the profile is averaged with):
boreal 1.8 % / 6.8 % · Hainich 13.2 % / **35.3 %** · mediterranean 1.4 % / 4.3 % · Sahel 2.8 % / 10.2 % ·
Amazon 14.8 % / 20.2 %. So at Hainich a third of the weight comes from individuals whose rooted depth is
only bounded below, biasing that cell's profile deeper. `[TODO]` the `ind` table also carries `k_root`
(column 20), from which `rootdepth` may be derivable directly and unconditionally — the principled fix, and
the first thing to try if a per-cell water-supply residual appears.

B2 also removes a class of silent error: renormalizing over the rooted depth makes every individual's
profile sum to 1, so the community mean does too — whereas B1's unnormalized form leaks the tail below the
column bottom (up to 1.4e-8 for a deep community, and it is *not* checked anywhere downstream).

**What B2 buys scientifically:** the rooting gradient becomes emergent rather than assumed —
top-1 m root fraction 99.3 % (semi-arid Sahel) → 88.6 % (boreal) → 87.8 % (Hainich) → 61.5 %
(mediterranean) → 53.2 % (tropical Amazon), with effective D95 from 72 cm to 690 cm, straight out of FIT's
own trait distributions.

### Consequences

- Good, because the soil column now has a committed, gated generator instead of an unreproducible fixture.
- Good, because every cell follows one rule, which is what M3's per-cell scoring needs.
- Good, because `hainich_soilcolumn.txt` is untouched: no committed baseline moves, and the F_diff
  validation chain stays byte-identical (guardrail 4).
- Good, because the coupled biome driver can now report the **vegetation+soil** contribution separately from
  the climate contribution (it runs both configurations): +10.8 W/m² LE in the Amazon and −7.6 W/m² in the
  Sahel, with the mediterranean Bowen ratio falling 1.27 → 0.65.
- Bad, because Hainich's *emitted* per-cell `rootdist` differs from the committed legacy column
  (top-1 m 87.8 % vs 93 %), so the biome test's Hainich cell is not bit-identical to its pre-M1 self. Its
  `whcs` column **is** identical, and its assertions are qualitative (closure + Bowen ordering), so no
  baseline moves. Accepted deliberately: one rule for all cells beats continuity for one cell.
- Bad, because the time-mean reduction of `whc_nat` hides a real (if small) drift: layer 0 varies by
  3.3e-4 in fraction (≈ 0.07 mm) over 2000–2019 as topsoil carbon changes. Accepted — `SoilColumn` is a
  static boundary by construction.
- Bad, because **B3 is not done and `"permafrost": true` is live in this config** (`lpjmlfit.js:62` and every
  run config), so the boreal cell's emitted profile is knowably *not* the C's. `getrootdist.c:59-75`
  redistributes all roots below `min(soildepth·1000, soil.mean_maxthaw)` into the last thawed layer; with a
  boreal `mean_maxthaw` of order 2 m the C would return **exactly 0** for every layer from 5 down, whereas
  `M_soilcolumn_boreal_siberia.txt` carries 8.4e-4 / 1.6e-4 / 4e-6 / 1e-6 there. The mass is tiny, but the
  boreal column is the one place where "faithful port" is an overstatement.
  **Correcting the first version of this ADR:** it claimed "no output carries that thaw state" — that is
  **wrong**. `MAXTHAW_DEPTH` is a declared annual output (`par/outputvars.js:201`, "maximum thawing depth",
  mm); our runs simply never requested it, and a re-run can. What is genuinely unavailable is the *running
  mean* `soil.mean_maxthaw` that `getrootdist` actually reads, which would have to be approximated from the
  annual series. So B3 is a bounded follow-up, not a blocked one: add `maxthaw_depth` to the per-cell
  `run_fdiff_validation_cell.sh` output list and redistribute. `[TODO]` — do it if the boreal cell is ever
  implicated in a residual, or before any boreal permafrost claim.
  The sediment branch of the same loop IS dead here, because `newgrid.c:282` overwrites every cell's
  Pelletier soil depth with a flat 20 m.

## More Information

- **Scripts:** `scripts/extract_cell_soilcolumn.py` (gate: `EMIT=no`), `scripts/extract_cell_individuals.py`,
  `scripts/extract_biome_forcing.py` (now the canonical N-cell registry via `cells_from_env`).
- **Fixtures:** `references/M_soilcolumn_<name>.txt`, `references/M_individuals_<name>_2010.csv`,
  `references/M_cells.csv`, plus the `M_*_meta.json` provenance files.
- **Oracle data generated for this ADR:** single-cell daily re-runs of the four non-Hainich biome cells
  (`scripts/run_fdiff_validation_cell.sh CELL=<idx> RUNTAG=M_biome_val`), which add `d_fapar` /
  `a_lai_stand` / `a_fpc_stand` so each reconstructed canopy is checked against **its own** cell's C FAPAR.
- **Revisit when** a cell needs a scenario other than historical seed1 (the SSP370 global run has its own
  `whc_nat.nc` with 972 monthly steps), when M2 pins the S artifact (a per-cell `ClimBuf` and
  `n_init`/`age0` come from `cell_meta.parquet`, not from here), or if the permafrost root redistribution
  (B3) is implicated in a boreal residual.
