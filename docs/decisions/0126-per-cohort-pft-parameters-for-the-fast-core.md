# ADR 0126 — Per-cohort PFT parameters for the fast core: the tropical failure is fixed, the temperate over-growth gets WORSE, and the pre-registered criterion FAILS

- **Status:** accepted
- **Date:** 2026-08-12
- **Line:** M (multi-cell coupled S+F+E) · ADR block 0120–0139
- **Consumes:** ADR 0125 (rung 3: the per-year growth error and its pre-registered fix criterion),
  ADR 0047/0049 (the per-PFT mortality half of the same table, and S's standing `fc.pft_ids`
  requirement), ADR 0031 (one copy of a physical constant), ADR 0060 (never substitute a reference basis
  silently), ADR 0110 (why per-individual data travels beside `Individual`, not inside it)
- **Supersedes:** nothing. **Does not supersede ADR 0125** — it answers the question ADR 0125 §7.3 posed.

## 1. Context

`FDiffFastCore` gave **every tree in every cell the temperate-beech parameter set**
(`fast.jl`'s `pft_ids` default `t.is_grass ? 8 : 3`, and one `params`/`alloc`/`allom` per core). ADR 0125
measured the cost at the five biome cells and promoted the gap to the head of the F-side queue: the
maintenance-respiration coefficient `respcoeff` is **0.2** for the tropical broadleaved evergreen tree
(id 0) and **1.2** for all six temperate/boreal trees, so at the two hot cells — 100 % id 0 by sapwood —
F over-respired every stem sixfold and its annual carbon balance went **negative** (−223 gC/m²/yr at the
Amazon against a truth of +1073) while its GPP was within a few per cent. The same wiring is also line S's
standing prerequisite for flipping `trait_mortality` (ADR 0049), whose hazard parameters are per-PFT.

ADR 0125 §7.3 pre-registered the pass criterion **before** the arm was run, and it is quoted verbatim in
the probe so it cannot be re-read after the fact:

> pass = with per-cohort `pft_ids` wired through `FDiffFastCore`, `bmi_F/C` lands in **[0.8, 1.25]** at all
> five cells and the paired Σ`dagb` F/C moves toward 1 at all five, with **no** committed baseline moving
> while the feature is off.

## 2. What was built

Five per-PFT lookups in `src/fdiff.jl` — `pft_respparams`, `pft_tempstressparams`, `pft_allocparams`,
`pft_allometry`, `pft_canopy_traits` — plus the per-individual bundle `PFTPhys` (`resp`, `alloc`, `allom`,
`tstress`, `gmin`) and `pft_phys(ids)`. Nine parameters are genuinely per-PFT across the seven tree PFTs:

| parameter | spread over the tree PFTs | F's single shipped value |
|---|---|---|
| `respcoeff` | **0.2** (id 0) / 1.2 (ids 1–6) | 1.2 (beech) |
| `lightextcoeff` (`k_beer`) | **0.45** needleleaved (1, 4, 6) / 0.59 broadleaved | 0.59 |
| `temp_photos` low/high | **15/25 °C** boreal (4, 5, 6) / 20/30 elsewhere | 20/30 |
| `temp_co2` low/high | **2/55** (id 0), −4/42 (1, 2), −4/38 (3–6) | −4/38 |
| `gmin` | **0.3 – 1.6** | 1.0 |
| `turnover` leaf/root | 1 yr (2, 3, 5, 6) / **2 yr** (0) / **4 yr** (1, 4) | 1 yr |
| `turnover` sapwood | 25 yr / **30 yr** (id 0) | 25 yr |
| `allom1/2/3`, `kpr` | angiosperm / **gymnosperm** (1, 4, 6) | angiosperm |
| `intc` | 0.02 / **0.06** boreal | 0.02 |

The consuming path takes them as an optional per-individual vector, exactly as ADR 0110's `rootdists` does
and for the same two reasons (a heap field on `Individual` aborts the Enzyme reverse pass, and a
back-compatible constructor default could not be byte-identical because the shipped `respcoeff` is 1.2
while `RespParams()`'s own default is 1.0): `daily_step_canopy(...; pftphys=)`,
`individuals_from_pools(...; pftphys=)`, `individual_from_pools(...; k_beer=, tstress=)`,
`_treepools_fpc(...; k_beer=)`, `_patch_fpars(...; kbeers=)`, and
`FDiffFastCore(...; per_pft_params=true)` (or an explicit `Vector{PFTPhys}`, which is how the
single-variable arms of §5 are built).

**The numbers live in exactly one place.** `test/testitems/references/M_pft_fdiff_params.csv` is generated
from the live `par/pft_lpjmlfit.js` by `scripts/build_pft_fdiff_params_reference.py` using `cpp -P` — the
same preprocessor LPJmL pipes its own parameter files through (`openconfig.c:28`) — reusing the `cpp_json`
reader of `scripts/build_mort_params_reference.py` rather than copying it, duplicate-key audit included.
A testitem compares the Julia literals to that table value by value, so a drifting C parameter reds the
gate instead of silently disagreeing (ADR 0031).

**Guardrail 4 holds by construction and is asserted, not asserted-about.** `pft_respparams(3)`,
`pft_tempstressparams(3)`, `pft_allocparams(3)` and `pft_allometry(3)` **equal** F's shipped beech sets
exactly, and `pft_allocparams(8) == grass_allocparams()`; the feature is off by default; and a beech-only
stand run for a full simulated year is **bit-for-bit identical** with the channel on
(`test/testitems/per_pft_params_tests.jl`). The full suite is green with **no committed baseline moving**
(274 934 pass / 0 fail, 133 items, job 1762535 on the final code).

## 3. The result — the tropical half is fixed completely, and two cells get WORSE

Arm **P** = per-cohort parameters, the C's own `Type` per stem; arm **A** = the shipped single beech set
(the published rung-3 arm). Same rosters, same forcing, `slow = nothing`, 25-patch ensemble, alignment A,
historic 2010–2019. `bmi` = the annual assimilate handed to allocation (gC/m²/yr); `bmi_C` is the C's own
Σ per-stem NPP over the very same stems and is identical in both arms.

| cell | `bmi_A` | `bmi_P` | `bmi_C` | A/C | **P/C** | Σ`dagb` A/C | **Σ`dagb` P/C** |
|---|---|---|---|---|---|---|---|
| boreal_siberia | 198.0 | 240.8 | 188.8 | 1.049 | **1.275** | 1.616 | **2.260** |
| temperate_hainich | 606.0 | 606.7 | 489.0 | 1.239 | 1.241 | 1.855 | 1.865 |
| mediterranean_iberia | 644.2 | 721.8 | 236.2 | 2.727 | **3.056** | 3.997 | **5.103** |
| semiarid_sahel | **−83.8** | **207.3** | 183.2 | −0.457 | **1.132** | 0.038 | **1.483** |
| tropical_amazon | **−223.2** | **1198.8** | 1072.5 | −0.208 | **1.118** | −0.071 | **1.452** |

* **The two hot cells are fixed.** The Amazon's annual carbon balance goes from −223 to **+1199** against a
  truth of **+1073** (1.118×) and its paired per-stem growth from **−0.07 to 1.45**; the Sahel from −0.457
  to **1.132** — better than ADR 0125's single-scalar `respcoeff` arm managed there (0.399). ⚠ §5 shows
  the extra improvement is the **phenology**, not the other parameters: id 0's own `gmin` of 1.6 makes the
  Sahel *worse* on its own (0.400), so do not read the cohort set as uniformly helping even where the total
  lands well.
* **Hainich does not move** (1.239 → 1.241): it is 99.4 % beech by sapwood, so P ≡ A there **by
  construction**. That is this arm's own control that the change touches only what it should — it is not
  evidence that the change does nothing.
* **boreal_siberia and mediterranean_iberia get worse**: `bmi` 1.049 → **1.275** and 2.727 → **3.056**, and
  the paired growth ratio 1.62 → **2.26** and 4.00 → **5.10**.

**So the pre-registered criterion FAILS on both of its measured clauses** (in band at 3 of 5 cells, not 5;
moved toward 1 at 2 of 5, not 5). The third clause — no committed baseline moving with the feature off —
passes. Per the standing rule for a pre-registered criterion, **the failure is the finding**; nothing was
tuned to make it pass and the criterion was not rewritten.

## 4. Why the failure does NOT argue for reverting

1. **These are the C's own parameters.** Arm P is strictly more faithful than beech-for-everyone: every
   value is a `cpp -P` read of the parameter file LPJmL itself parses. "Beech for every tree in the
   tropics" is not a defensible alternative, and the two hot cells were not marginally wrong under it —
   they were **losing biomass** where the C gained it.
2. **The criterion asked one fix to close errors ADR 0125 had already attributed elsewhere.** ADR 0125 §5
   records that at boreal/Hainich the assimilate input was already right (1.05 / 1.24) while `keep` — the
   fraction retained as standing biomass — was **1.85 / 1.49**, and that mediterranean_iberia has an
   independent GPP defect (F's GPP is 1.3–1.5× the C's there). A criterion of "in band at all five cells"
   therefore required this change to also fix the allocation gap and the mediterranean GPP gap. It was
   over-scoped when it was written, and that is visible only now.
3. **Boreal's previous agreement was partly coincidental.** Its `bmi_A/C` of 1.049 was produced with the
   *wrong* photosynthesis optimum (20/30 °C instead of 15/25) and the *wrong* extinction (0.59 instead of
   0.45) — two errors of opposite sign in a cold cell. Making both faithful reveals a real +27 % assimilate
   bias that was previously hidden. **A cell that scores well under wrong parameters is not evidence of a
   correct model**, and this is the second time in this repo that fixing a basis exposed a compensating
   pair (ADR 0060 was the first).

## 5. Which parameter did what — the single-variable arms

Arm P moves nine parameters at once, which cannot say which one moved a cell (and the owner's standing
preference is one variable per experiment). Each arm below takes exactly **one** per-PFT field from the
stem's own PFT and beech's for everything else, built by passing an explicit `Vector{PFTPhys}`.

⚠ **The first arm is a BASELINE, not a null, and finding that out corrected this whole section.** Passing
real `pft_ids` also switches on the per-PFT **GSI phenology** — a `FDiffFastCore` kwarg that has existed
since long before ADR 0126 and that arm A **does not pass**, so all of arm A's trees run *beech's*
phenology filters. Every per-PFT arm therefore carries the phenology change as well, and a first version of
this table (job 1762534) attributed its effect to whichever parameter happened to be in the column. The
`phen` arm isolates it (bundle and templates all beech, real ids only); **every other column must be
differenced against `phen`, not against `A`.** A column equal to `phen` means that parameter is already
beech's at that cell — the arm's own control.

`bmi_F/C` (the annual assimilate; 1.000 is the target):

| cell | A | **phen** | resp | tstress | kbeer | gmin | alloc | allom | traits | P (all) |
|---|---|---|---|---|---|---|---|---|---|---|
| boreal_siberia | 1.049 | **1.026** | 1.026 | **1.124** | **1.004** | **1.191** | 1.026 | 1.026 | 1.026 | 1.275 |
| temperate_hainich | 1.239 | 1.240 | 1.240 | 1.241 | 1.240 | 1.240 | 1.240 | 1.240 | 1.240 | 1.241 |
| mediterranean_iberia | 2.727 | **3.110** | 3.110 | 3.109 | 3.115 | **3.047** | 3.110 | 3.110 | 3.110 | 3.056 |
| semiarid_sahel | −0.457 | **0.557** | **1.290** | 0.557 | 0.557 | **0.400** | 0.557 | 0.557 | 0.550 | 1.132 |
| tropical_amazon | −0.208 | −0.204 | **1.128** | −0.207 | −0.204 | −0.212 | −0.204 | −0.204 | −0.204 | 1.118 |

Σ`dagb` F/C (the paired per-stem growth, year-median):

| cell | A | **phen** | resp | tstress | kbeer | gmin | alloc | allom | traits | P (all) |
|---|---|---|---|---|---|---|---|---|---|---|
| boreal_siberia | 1.616 | **1.566** | 1.566 | **1.878** | **1.507** | **2.038** | 1.573 | 1.506 | 1.566 | 2.260 |
| temperate_hainich | 1.855 | 1.858 | 1.858 | 1.859 | 1.858 | 1.858 | 1.864 | 1.857 | 1.858 | 1.865 |
| mediterranean_iberia | 3.997 | **4.820** | 4.820 | 4.819 | 4.810 | **4.775** | **5.180** | 4.791 | 4.820 | 5.103 |
| semiarid_sahel | 0.038 | **0.670** | **1.558** | 0.668 | 0.670 | **0.541** | **0.759** | 0.670 | 0.658 | 1.483 |
| tropical_amazon | −0.071 | −0.069 | **1.030** | −0.070 | −0.069 | −0.063 | **−0.030** | −0.069 | −0.069 | 1.452 |

What this says, cell by cell:

* **`respcoeff` IS the tropical fix, alone.** At the Amazon it takes `bmi` from −0.208 to **1.128** and the
  paired growth from −0.071 to **1.030** by itself; no other field moves that cell at all (every other
  column is within 0.005 of `phen`). ADR 0125's attribution is confirmed on the code path, not just as a
  substituted scalar.
* **The Sahel needs BOTH, and they are roughly additive.** Phenology alone fixes the sign (−0.457 →
  **0.557**), `respcoeff` alone reaches **1.290**, and together they land at 1.132. So the Sahel's remaining
  shortfall in ADR 0125's single-scalar arm (0.399) was partly a *phenology* gap, not the dry-cell root zone
  of ADR 0052 — which narrows that item rather than confirming it.
* **The boreal cell is `temp_photos` and `gmin`, and they push the same way.** The 15/25 °C optimum takes
  it 1.026 → **1.124** and the low larch conductance `gmin` 0.3 takes it 1.026 → **1.191**; both raise the
  assimilate at a cold cell. Meanwhile the correct needleleaf extinction alone gives **1.004** — the best
  single number in the whole table. Three faithful parameters, two of which make the total worse.
* **The Mediterranean cell is not the parameters at all — it is the PHENOLOGY.** `phen` alone accounts for
  2.727 → **3.110**, and every one-field arm sits on top of that within 0.07. Since ADR 0125 already
  measured an independent 1.3–1.5× GPP bias there, this cell has a defect that no per-PFT parameter
  touches.
* **Hainich is flat in every column** (1.239–1.241) — the control, and it also confirms the arms are wired
  as intended.
* ⚠ The arms do **not** sum to P (the daily canopy is nonlinear; `alloc`/`allom` act through the next
  year's pools), and `alloc` moves Σ`dagb` while barely moving `bmi` — exactly as expected for a turnover
  parameter, and a useful check that the two statistics are measuring different things.

**A finding that is not about ADR 0126 at all, and matters more widely: arm A — the published rung-3 arm,
and every earlier five-cell F number in this repo — ran beech's GSI phenology for larch, for the tropical
evergreen and for every other PFT.** Switching to each PFT's own filters, with no other change, moves the
Sahel by **+1.01** in `bmi_F/C` and the Mediterranean by **+0.38**. `pft_ids` was always available; nothing
had to be built to close it. Any five-cell F number that predates this table should be assumed to be on
beech phenology.

## 6. Decision

1. **Land the wiring, opt-in and default byte-identical.** It is the faithful reading of the C, it is line
   S's prerequisite for `trait_mortality` (ADR 0049), and it is the only way the tropical belt — the whole
   id-0 domain, not just two cells — can have a non-negative carbon balance.
2. **Do NOT flip the default.** The criterion that would have authorised a default flip failed, and two of
   five cells move away from the truth. `per_pft_params` stays `false` until the two defects §4.2 names are
   closed. **Pre-registered flip criterion** (guardrail 4's corollary — stated here, before the next arm):
   flip the default to `per_pft_params = true` when arm P reaches `bmi_P/C ∈ [0.8, 1.25]` **and**
   Σ`dagb` P/C ∈ [0.8, 1.25] at **all five** cells, on line M's own probe, with the beech-only
   byte-identity item still green. Until then every per-PFT number must be reported as an opt-in arm.
3. **Pass real `pft_ids` in every arm from now on, independently of `per_pft_params`.** §5's `phen` column
   is a pre-existing gap, not part of this feature, and it is free to close. Every future five-cell F
   number should be on per-PFT phenology, and any earlier one should be read as beech-phenology.
4. **The next F-side item is the one ADR 0125 §7 already named, and it is now the binding one:** the
   allocation/turnover `keep` gap. Arm P made it worse everywhere it acted (Σ`dagb` overshoots 1.45–1.48
   even at the two cells whose assimilate is now right), which localises the remaining error to allocation
   rather than to the carbon input at three of five cells. §5 adds two narrower targets beside it: the
   boreal cell's `temp_photos`/`gmin` pair and the Mediterranean cell's phenology-plus-GPP defect.
5. **F-side only, enforced rather than documented.** `run_coupled_cell` **errors** when a per-PFT core is
   passed together with a slow emulator: S's `reconcile_demography!` rebuilds the roster with the core's
   single shared allometry, so such a run would use each cohort's own physics daily and then recompute
   `fpc` with beech's `k_beer` annually — a mixed basis, the class of error ADR 0060 cost a published
   verdict to. The bundles are indexed by roster position, so both growth entry points also assert
   `length(pft_phys) == length(pools)` and name the fix in the message.
6. **Raise the S-side wiring as an integration point** (`lines/S/STATE.md`, 2026-08-12). S owns
   `src/components/slow.jl`; M may not edit it. The change S needs is small — thread `fc.pft_phys` into the
   three `_patch_fpars`/`individuals_from_pools`/`_treepools_fpc` call sites and rebuild the bundles
   whenever the roster changes — and it unblocks both the coupled per-PFT arm and `trait_mortality`.

## 7. Consequences

* ADR 0125 §7.3's criterion is **closed as FAILED**, not left open. Any future statement that the per-PFT
  parameters "fixed rung 3" is wrong: they fixed the tropical half and worsened the temperate/boreal half.
* ADR 0125 §5's reading of the Sahel — "the sign is fixed and the 2.5× shortfall left is ADR 0052's dry-cell
  root zone" — is **narrowed**: §5 here shows about a third of that shortfall was the beech-phenology gap.
  Do not attribute the Sahel's residual to the root zone without re-measuring on per-PFT phenology.
* Two committed artifacts are added: `test/testitems/references/M_pft_fdiff_params.csv` (generated) and
  `test/testitems/per_pft_params_tests.jl`. No existing baseline changed.
* `scripts/biome_canopy_growth_probe.jl` gains arm P and the seven single-variable arms (PART 9/9b/9c). Its
  crown cover for the per-PFT arms is computed with **each stem's own `k_beer`** — the basis the C's own
  `fpc_ind` is on — while arms A/B/R2 keep the shared 0.59 so their published numbers reproduce unchanged;
  both are printed, never substituted (ADR 0060).
* A general rule worth carrying: **a per-PFT parameter table is not a tidy-up, and a model that scores well
  with the wrong one is not thereby validated.** Fixing two compensating parameter errors in the same cell
  can move a good-looking number in the wrong direction, and that is information, not a regression.

## 8. Scope that rides with every number here

Five cells of 54 020; one scenario (historic 2010–2019); seed1 only; `slow = nothing` (no mortality, no
establishment on F's side — which is why the paired per-stem framing is used); the 25-patch ensemble;
`wscal_leafon = true`; year alignment A. **No climate-change response is measured** — the acceptance
criterion's binding clause (ADR 0106) is untouched by this ADR. The `keep`/Σ`dagb` statistics use
above-ground biomass only, because the `ind` table's per-stem pools are the only ones the C emits per
individual. Grass is out of the probe entirely (its roster rows are filtered at `Type <= 6`), so the grass
per-PFT values in the table are committed and gated but **not** exercised by any measurement here.

## 9. Reproduce

```bash
# the committed per-PFT table, from the live C parameter file
python3 scripts/build_pft_fdiff_params_reference.py            # CHECK=1 to verify instead of write
# the arms (SLURM, ~12 min: A, B, R2, P, the 8 single-variable/baseline arms, FREE)
TIME=02:00:00 scripts/sbatch_julia.sh M-rung3h --project=. scripts/biome_canopy_growth_probe.jl
# the gates
scripts/run_tests_slurm.sh M-perpft
```

Logs of record: **`logs/M-rung3h.1762579.out`** (all thirteen arms, including §5's attribution table with
the `phen` baseline) and **`logs/M-perpft2.1762535.out`** (the suite on the final code: 274 934 pass / 0
fail, 133 items, 7m20s). Job 1762501 is arm P before the single-variable arms existed; job 1762534 is the
first attribution run, whose table was CONFOUNDED by the phenology (see §5) and is superseded by 1762579;
job 1762478 is the suite before the roster-length assertion was added.
