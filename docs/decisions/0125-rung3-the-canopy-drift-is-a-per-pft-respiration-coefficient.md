# ADR 0125 — Rung 3: F's canopy error is a PER-YEAR growth bias with OPPOSITE SIGNS by biome, and one per-PFT respiration coefficient carries the tropical half of it

- **Status:** accepted
- **Date:** 2026-08-12
- **Line:** M (multi-cell coupled S+F+E) — `EXECUTION_PLAN.md` **rung 3**, "F alone, on the C's own canopy"
- **Related:** ADR 0041 (a subset re-run is not a replica of the global run) · ADR 0052 (F's dry-cell
  root zone) · ADR 0053 (the five-biome F-vs-C oracle) · ADR 0060 (the C's two FPC outputs; the t=0
  reconstruction gate) · ADR 0093/0094 (the ladder, and speed as goal #2) · ADR 0106 (the acceptance
  criterion) · ADR 0111 §9 (band a ratio, guard its denominator) · ADR 0124 (an exactness gate is only
  as wide as the states it ran on)
- **Supersedes nothing. Withdraws nothing.** It narrows one open item (`lines/M/STATE.md` item 4(d)) and
  corrects the year alignment and the reference basis that item was measured on.

## 1. Context — what rung 3 had to answer, and why nothing could

The rung-3 exit gate is *"the decadal canopy drift is quantified and either fixed or bounded"*. The drift
on the table: over 2010–2019 F's crown cover moves **+65 %** (boreal), **+27 %** (Hainich), **−13 %**
(Sahel) where the C's own moves −11 / −3 / +25 % (ADR 0053, corrected by ADR 0060).

Every measurement of it was a **decadal aggregate**, and a decadal aggregate cannot separate

* **(i)** a per-year growth bias that compounds, from
* **(ii)** something the free-running loop manufactures out of its own accumulated state,

which need completely different fixes. Worse, the free-running arm has **no mortality** (`slow = nothing`),
so ADR 0060 had already recorded that it *cannot convict F's growth on its own*.

## 2. The enabling fact: `(Cell, Patch, ID)` is a STABLE CROSS-YEAR INDIVIDUAL IDENTITY

`[VERIFIED 2026-08-12]` The annual `ind` output's `ID` column follows one tree through time. Over the five
biome cells, 2009–2019, 13 152 tree stem-years:

* `Age` increments by **exactly 1** on every one of 10 323 year-pairs — no exceptions;
* `SLA` and `Wooddens` are **bit-identical** across each pair, which is the independent check (traits are
  immutable after `new_tree`, ADR 0046, so a shuffled identity would break it);
* no stem emitted with `isdead == 1` is ever seen again;
* **no living stem disappears** except **8 stem-years of 13 152** (0.06 %), all within **0.4 m** of the
  writer's 5 m emission threshold — they dipped back under it and stopped being written (one is emitted
  again two years later). The gate is on the vanished stems' **height**, not their count.

So the year-y roster is exactly {year-(y−1) survivors, grown} + the stems that newly crossed 5 m. That is
what makes an F-vs-C comparison **paired per stem** rather than aggregate, and it had never been used.

Builder + gate: `scripts/build_biome_stem_growth_reference.py`; committed summary
`test/testitems/references/M_stem_growth_reference.csv`.

## 3. Two reference-basis corrections, both measured

**(a) The year alignment was off by one, and the correct one is now measured rather than argued.** The
`ind` row for year y is written at the END of year y, so the stand entering year y is the year-(y−1)
roster. The existing kernel probe starts from roster(2010) and drives it with **2010** forcing — the
weather that stand has already lived through. Scored on the paired per-stem annual increment (median
|relative error|, alignment A = roster(y−1)+forcing(y) vs B = roster(y)+forcing(y)):

| cell | A `dagb` | B `dagb` | A `dheight` | B `dheight` |
|---|---|---|---|---|
| boreal_siberia | **1.468** | 1.629 | **8.088** | 8.145 |
| temperate_hainich | **1.107** | 1.140 | **0.988** | 1.000 |
| mediterranean_iberia | **3.570** | 5.454 | **3.935** | 4.493 |
| semiarid_sahel | 1.000 | 1.000 | 1.000 | 1.000 |
| tropical_amazon | 1.000 | 1.000 | 1.000 | 1.000 |

A wins wherever the test has power (the two 1.000 rows are F's increment being ≈ 0 — §5 — so they cannot
discriminate). Everything below uses A.

**(b) The committed C structural oracle is a DIFFERENT RUN from the one F is initialised from, and at one
cell a different realisation.** `M_fdiff_oracle_biomes_annual.csv` comes from the per-cell **single-cell**
daily re-runs; F's canopy and Component S's counts come from the **global** run's `ind` table. ADR 0041
says those need not agree. Measured on daily GPP, 2010–2019
(`scripts/diagnose_oracle_run_divergence.py`), with the shared restart year as the control (r = 1.00000 in
all five):

| cell | r over 2010–2019 | level ratio |
|---|---|---|
| boreal_siberia | 0.99991 | 1.000 |
| temperate_hainich | 0.99932 | 0.989 |
| mediterranean_iberia | 0.99889 | 1.002 |
| semiarid_sahel | 0.99937 | 1.004 |
| **tropical_amazon** | **0.97027** | **0.933** |

Four of five track closely enough to serve as each other's oracle; **the Amazon does not** — a level miss
there against `a_fpc` is not evidence about F.

**And `a_fpc` includes stems below 5 m while F's stand cannot** — a fraction that is **time-varying**
(boreal 0.712 → 0.806 over the decade), so it contaminates the DRIFT, not only the level. Both problems
vanish by scoring against `fpc_live`/`fpc_all`, formed from the very stems F is handed. `a_fpc` is still
printed beside them (ADR 0060's rule: never substitute a basis silently).

The reconstruction itself is **not** the problem: F's crown cover at t = 0 over the C's own crown-cover sum
for exactly those stems is **0.995–1.038 in every cell and every year** (PART 1).

## 4. The result — the per-year growth error, and it has OPPOSITE SIGNS by biome

Paired, alignment A, 25-patch ensemble, `slow = nothing`, `wscal_leafon = true`. Σ per-stem annual
above-ground biomass increment, F over C, and the stand multipliers on the same individuals:

| cell | Σ`dagb` F/C (year median) | F stand ×/yr | C stand ×/yr |
|---|---|---|---|
| boreal_siberia | **1.62** | 1.073–1.128 | 1.017–1.089 |
| temperate_hainich | **1.86** | 1.058–1.091 | 1.031–1.050 |
| mediterranean_iberia | **4.00** | 1.05–1.26 | 0.99–1.10 |
| semiarid_sahel | **0.038** | 1.001–1.035 | 1.063–1.117 |
| tropical_amazon | **−0.071** | 0.997–0.999 | 1.021–1.029 |

F grows **1.6–4×** too fast in the cold/temperate/mediterranean cells and **does not grow at all** in the
two hot ones — at the Amazon its stems **lose** biomass while the C's gain. This is stable in every one of
the ten years, in the same direction, at every cell. It is far larger than the decadal canopy drift the
gate was written about (§6).

## 5. Where the error enters — and one per-PFT parameter carries the tropical half

The C emits each stem's own annual NPP, so "how much assimilate arrives" and "how much of it is kept as
standing biomass" can be separated with no new run. `bmi` = the annual assimilate handed to allocation
(F: `FToS.bm_inc`; C: Σ per-stem `npp` over the same stems, gC/m²/yr); `keep` = ΣΔAGB / that assimilate:

| cell | `bmi_F` | `bmi_C` | F/C | `keep_F` | `keep_C` | keep F/C |
|---|---|---|---|---|---|---|
| boreal_siberia | 198.0 | 188.8 | **1.05** | 0.465 | 0.251 | **1.85** |
| temperate_hainich | 606.0 | 489.0 | **1.24** | 0.549 | 0.368 | **1.49** |
| mediterranean_iberia | 644.2 | 236.2 | **2.73** | 0.602 | 0.269 | **2.24** |
| semiarid_sahel | **−83.8** | 183.2 | **−0.46** | 0.350 | 0.493 | 0.71 |
| tropical_amazon | **−223.2** | 1072.5 | **−0.21** | 0.143 | 0.347 | 0.41 |

**F's annual carbon balance is NEGATIVE at the two hot cells** — its autotrophic respiration eats the whole
year's assimilate — while its **GPP is within a few per cent of the C's** there (Amazon 6.76–7.31 vs the
C's 6.54–7.47 gC/m²/day). So the tropical failure is respiration, not photosynthesis.

**The cause is a per-PFT parameter F does not carry.** Read from the live `par/pft_lpjmlfit.js` with
`cpp -P` (CLAUDE.md §3): `respcoeff` is **0.2** for the tropical broadleaved evergreen tree (id 0) and
**1.2** for all six temperate/boreal trees — a **6× spread**. F holds ONE scalar for every tree in every
cell: `RespParams.respcoeff` defaults to 1.0 and the ACTIVE calibrated set sets it to **1.2**
(`fdiff.jl:1287`, `tebs_params`) — beech's value. Both Sahel and Amazon are **100 % id 0 by sapwood**, so
F over-respires every stem there by 6×.

Arm **R2** substitutes the cell's own sapwood-weighted coefficient and changes nothing else:

| cell | respcoeff used | `bmi_F` | `bmi_F` (R2) | `bmi_C` | F/C | **R2/C** | Σ`dagb` R2/C |
|---|---|---|---|---|---|---|---|
| boreal_siberia | 1.2 | 198.0 | 198.0 | 188.8 | 1.049 | 1.049 | 1.616 |
| temperate_hainich | 1.2 | 606.0 | 606.0 | 489.0 | 1.239 | 1.239 | 1.855 |
| mediterranean_iberia | 1.2 | 644.2 | 644.2 | 236.2 | 2.727 | 2.727 | 3.997 |
| semiarid_sahel | **0.2** | −83.8 | **73.1** | 183.2 | −0.457 | **0.399** | 0.216 |
| tropical_amazon | **0.2** | −223.2 | **1205.8** | 1072.5 | −0.208 | **1.124** | **1.023** |

At the **Amazon** one parameter takes the annual carbon balance from **−223 to +1206** against a truth of
**+1073**, and the paired per-stem growth ratio from **−0.07 to 1.02**. At the **Sahel** it fixes the sign
and most of the magnitude (−0.46 → 0.40) and leaves a real 2.5× shortfall, consistent with ADR 0052's
dry-cell root-zone bias being a second, independent defect in that cell. The three temperate/boreal cells
are **unmoved by construction** (1.2 → 1.2) — which is the arm's own control that it changes exactly one
thing.

**The other half of the error is NOT respiration.** At boreal/Hainich the assimilate input is right
(1.05 / 1.24) while `keep` is **1.85 / 1.49** — F retains far too much of each year's carbon as standing
above-ground biomass. That is allocation/turnover, it is untouched by R2, and it is the open item §7 hands
on. At mediterranean_iberia **both** halves are wrong (input 2.73, keep 2.24), and its F GPP is also
~1.3–1.5× the C's.

## 6. ⚠ THE DECADAL DRIFT UNDERSTATES THE PER-YEAR ERROR — the canopy saturates

| cell | REINIT compounded | C growth-only | FREE 2019/2010 | C `fpc_live` 2019/2010 |
|---|---|---|---|---|
| boreal_siberia | **20.40** | 1.32 | 1.667 | 1.008 |
| temperate_hainich | 1.71 | 1.29 | 1.292 | 0.902 |
| mediterranean_iberia | **14.32** | 1.14 | 0.991 | 0.776 |
| semiarid_sahel | 0.63 | 1.78 | 0.870 | 1.432 |
| tropical_amazon | 0.61 | 1.19 | 1.043 | 0.908 |

The free-running arm reproduces the previously published drift (+67 % boreal, +29 % Hainich, −13 % Sahel),
which is the harness's own basis check. But compounding F's *per-year* crown growth gives **20×** at boreal
against a free-running **1.67×**. The free arm is smaller because **F's canopy saturates** — crown area is
capped, cover is bounded, and light competition closes the stand — not because it is closer to right.

**Consequence, and it generalises:** *a bounded state variable's drift is a LOWER BOUND on the rate error
that drives it.* Quoting "+27 % over a decade" as the size of F's growth problem understates it by roughly
an order of magnitude at the boreal cell. Score the **rate**, not the accumulated stock, whenever the stock
has a ceiling.

## 7. Decision

1. **Rung 3's gate is met by QUANTIFICATION, not by a fix.** The drift is quantified per year, per stem,
   per cell, on a self-consistent basis, and decomposed into assimilate-in and biomass-kept. Nothing in
   `src/` changes in this ADR (guardrail 4); R2 is a diagnostic arm.
2. **The per-PFT parameter gap is now a measured defect, not a tidy-up.** `FDiffFastCore` gives every tree
   beech's parameters (`fast.jl:147`). This was already a standing requirement for `trait_mortality`
   (ADR 0049, `lines/M/STATE.md` item 3 / M5) on the grounds that the mortality parameters are per-PFT;
   it now also carries a **6× respiration error at every tropical cell**, which is 100 % of the stems at
   two of the five biome cells and the whole tropical belt globally. It is promoted to the head of the
   F-side queue.
3. **PRE-REGISTERED PASS CRITERION for the per-PFT-parameter change** (guardrail 4's corollary — a flip
   criterion written before the arm): pass = with per-cohort `pft_ids` wired through `FDiffFastCore`,
   `bmi_F/C` lands in **[0.8, 1.25]** at all five cells and the paired Σ`dagb` F/C moves toward 1 at all
   five, with **no** committed baseline moving while the feature is off. Decide from that arm alone.
4. **Do not quote the decadal canopy drift as the size of F's growth error** (§6), and do not read a
   year-matched structural comparison at `tropical_amazon` against `a_fpc` as an F error (§3b).

## 8. Consequences

* `lines/M/STATE.md` item 4(d) ("F's growth, start with the Sahel") is **narrowed and re-pointed**: the
  Sahel's shortfall is now known to be *two* defects, one of which (respiration) is fixed by the per-PFT
  parameters and one of which (ADR 0052's root zone) is not. Start with the parameters, then re-measure.
* Item 4(a) (ET 11–35 % high) and 4(c) are untouched by this and remain open.
* The `keep` gap (1.5–2.2× at the temperate/boreal cells) is a **new**, named F-side item with a
  measurement attached: allocation/turnover, not photosynthesis and not respiration.
* Two committed artifacts gain columns, both **purely additive and verified row-by-row**:
  `M_individuals_<cell>_2010.csv` gain `id`,`age` (every pre-existing value byte-identical), and
  `M_stem_growth_reference.csv` is new.
* `scripts/extract_cell_individuals.py` had a **latent registry-eating bug**, found while doing this and
  fixed here: it rewrote `M_cells.csv` from its own ten-column header and dropped every row whose field
  count differed, so a re-run would have silently deleted the six columns
  `extract_cell_slow_init.py` appends — the pinned Component-S per-cell seed (`n_init`, `age0`, the
  four-column boundary). The merge now preserves columns and comment lines it does not own, and a re-run
  over the live registry is byte-identical.

## 9. Reproduce

```bash
# 1. the C side: per-stem targets + the committed accounting (one parquet scan, ~30 s)
/home/jamirp/.conda/envs/py311_new/bin/python scripts/build_biome_stem_growth_reference.py
# 2. the per-year rosters F restarts from (2009-2019 x 5 cells, ~10 s each)
for y in $(seq 2009 2019); do YEAR=$y OUT=/p/tmp/jamirp/M_canopy_drift/individuals \
  /home/jamirp/.conda/envs/py311_new/bin/python scripts/extract_cell_individuals.py; done
# 3. the basis check on the oracle runs
/home/jamirp/.conda/envs/py311_new/bin/python scripts/diagnose_oracle_run_divergence.py
# 4. the probe (SLURM; ~2.5 min)
TIME=02:00:00 scripts/sbatch_julia.sh M-rung3 --project=. scripts/biome_canopy_growth_probe.jl
```

Log of record: **`logs/M-rung3e.1761716.out`** — the run of the *committed* (Runic-formatted) script; it is
byte-identical to `logs/M-rung3d.1761700.out` apart from the job tag, which is the check that reformatting
moved nothing. Jobs 1761459 / 1761663 / 1761689 / 1761700 / 1761716, all exit 0, ~2.5 min each.

## 10. Scope that rides with every number here

**Five cells of 54 020**, one scenario (historic 2010–2019), seed1 only, `slow = nothing` (so no mortality
and no tree establishment on F's side — which is exactly why the paired per-stem framing was needed), the
25-patch ensemble, `wscal_leafon = true`, and F carrying beech's parameters for every tree (which is the
defect §5 identifies, not a controlled condition). **No climate-change response is measured.** The `keep`
statistic uses above-ground biomass only, because the `ind` table's per-stem `vegc`/`agb` are the only
pools the C emits per individual.
