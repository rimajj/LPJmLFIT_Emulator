# ADR 0110 — the "structurally impossible" water-supply verdict was reached on GRASS and does not apply to TREES; per-tree roots + per-tree water are an order-INDEPENDENT faithful port, and they are what unblocks drought response

- **Status:** accepted (line S, 2026-08-06)
- **Supersedes:** nothing. **Narrows the scope** of `docs/water_supply_perpft_design.md`'s DEFER
  recommendation (and §26.4 CORRECTION #2 of `docs/phase3_fdiff_cbinary_validation.md`) from "per-individual
  water supply" to "the *order-dependent* residue cap alone". **Reopens** the channel ADR 0049 §3 closed.
- **Context:** ADR 0106 (the owner's acceptance criterion — all 54 020 tree-bearing cells, both scenarios,
  *and the response between them*, "especially under climate change"), ADR 0025 (the recruit copula ships four
  axes; `D95max` + `minwscal` are sampled + validated only, "until F_diff gains per-tree consumers"), ADR 0049
  (trait mortality wired in with `mort_water` and `mort_temp` set to **zero**), ADR 0050 (`rootdist` is the
  fpc-weighted community mean, option B2), ADR 0051/0059 (the C-faithful leaf-on `wscal`, now the default),
  ADR 0046 (the warming trait shift is **51.3 % within-PFT selection**), ADR 0108 §1 (the method rule:
  **measure the baseline before arguing from code structure that a channel is closed**), **ADR 0109 (the
  conditioning arm's verdict — see §0 below)**.

## 0. Why now: conditioning has been tried, and it does not reach this axis

ADR 0109 closed out the moisture-conditioning arm across three estimator arms on 52 074 cells. Its bottom
line for the rooting-depth trait is that **`D95max` is the largest measured trait-side gap against ADR 0106
on ALL THREE arms** (28–33 % of cells within 10 %), and that even the best arm for it reaches a
historic→ssp370 response slope of only **+0.172** where 1.0 would be faithful. The transient tail was the
best of the three on this axis and still **did not flip**.

That is the completion of a search. The rooting-depth trait has now been pushed on the *statistical* side —
richer conditioning, a better estimator, a transient moisture climate — and it remains the worst axis on both
level and response. The remaining explanation is the one this ADR acts on: **the trait has no physical
consumer.** No conditioning change can make a predicted quantity matter downstream when nothing downstream
reads it.

## 1. The defect

Component S samples a per-tree rooting depth (`D95max`) and a per-tree drought tolerance (`minwscal`),
validates both globally, and then **drops both**. `make_recruit_to_pools`
(`src/components/slow.jl:410-432`) writes only `SLA` → `TreePools.sla` and `Wooddens` →
`TreePools.wooddens`; the drawn `D95max`/`minwscal` are live elements of the `traits` vector with no
destination field. `_merge_pair!` (`:494-502`) would destroy them anyway — it copies traits from the
dominant parent.

On the F side there is no per-tree rooting field at all. The 23-layer profile lives on the **single shared**
`SoilColumn.rootdist` (`src/fdiff.jl:823`) and collapses to **one scalar** at `src/fdiff.jl:1540-1546`
*before* the per-individual loop opens, so `supply_i = ind.emax·wr·phi` (`:1625`) varies only by phenology and
a PFT-constant `emax`. The one rooting number the interface carries, `SToF.rootdepth`, is a cumulative-sum
read-back of that **static shared input** (`src/run.jl:62-69`) — not a population property — and nothing reads
it (`step!`, `src/components/fast.jl:174-260`, never dereferences `bc`).

Consequence: **two trees differing only in rooting depth are identical in the water balance.** Drought
response — the acceptance criterion's binding clause — cannot be represented.

## 2. Why the standing DEFER does not cover this

`docs/water_supply_perpft_design.md` (status *SCOPED, RECOMMENDATION = DEFER*) was scoped to **one grass
residual** (2018 European drought, grass F/C 1.87). Its three findings are correct **for that problem**:

1. the mechanism is the competitive per-layer cap `aet_cor`;
2. `-DPERMUTE` re-randomizes the depletion order **daily**, so a faithful port is non-deterministic and
   non-differentiable — "structurally impossible" on the AD path (§4.1);
3. **rooting depth is not the mechanism**, because grass shares beech's `beta_root=0.8` and
   `EMAX_ANGIO = EMAX_GRASS = 10.0` (§4.2).

Finding 3 is a statement about **grass versus the average tree**. It has been read as a statement about
per-individual rooting in general. It is not, and for trees the degeneracy it rests on does not exist:

| fact | source |
|---|---|
| `beta_root` is set **per individual** from that individual's own `D95max`; `"isD95max": true`, so the per-PFT `beta_root` draws are dead code | `src/tree/new_tree.c:229-230`, `lpjmlfit.js:44` |
| `D95max` interval **within one tree PFT**: `{low 51, high 300…1800}` **cm** | `par/pft_lpjmlfit.js:131,261,391,521,651,781,911` |
| `getrootdist` is called per individual, every day, and renormalizes to the deepest layer *that individual* reaches | `src/lpj/getrootdist.c:27-47` |
| the profile is **also** size-driven — `rootdepth = getrootdepth(height, k_root, logistic)`, and `k_root` is drawn per individual | `src/tree/allocation_tree.c:152`, `src/tree/getrootdepth.c:34-35` |
| resulting top-20 cm root share, shallowest vs deepest recruit | **≈69 % vs ≈4 %** (~17×) |
| the competing group is **6–12 individuals per patch**, each its own `Pft` object | `getnpft`, measured from `test/testitems/references/M_cells.csv` |

`emax` is not fully degenerate between trees either: `EMAX_ANGIO = 10.0` vs `EMAX_GYMNO = 12.9`
(`par/pft_lpjmlfit.js:116-118`).

## 3. ★ THE DECISIVE FINDING — the randomness does not touch the part we need

A line-by-line read of `water_stressed.c` against `daily_natural.c` separates the C's quantities cleanly.
`soil.w[]` is **frozen for the whole permuted loop** (it is written once per patch-day *after* it, in
`waterbalance.c:117-138`), and `aet_layer[]` is the only order-carrying state:

| quantity | order-dependent? | why |
|---|---|---|
| per-individual `wr`, `supply` (`:108`), `demand`, `supply_pft`, `demand_pft` | **NO** | read only the frozen `soil.w[]` and the pre-loop `gp_stand` |
| **per-individual `pft->wscal`, `wscal_mean`** (`:130-140`) | **NO** | a function of `wr` alone; it reads the **uncorrected** supply, *before* the cap |
| cap (i) — "no individual may take more than its own FPC share of a layer" (`:159-161`) | **NO** | depends only on this individual and the frozen `soil.w[]`; **fires routinely** in summer once `w[0] ≲ 0.4` |
| cap (ii) — "take only what earlier individuals left" (`:162-166`), and hence `aet_cor`, the rewritten `supply` (`:177`), `gc`, GPP | **YES** | via the running `aet_layer[]` |

So the chain **per-tree roots → per-tree `wr` → per-tree `wscal` → per-tree drought stress → drought
mortality is entirely order-independent and can be ported EXACTLY.** The design study treated `aet_cor` as
one blocked object; it is **two caps**, and the one that fires routinely is order-free. The randomness is
confined to realized *uptake* in the stressed regime — real, but separable and second-order.

(Noted in passing, not chased: `water_stressed.c:272` has an operator-precedence error and `:273` is a
guaranteed no-op, both in `AET_LAYER`/`pft->atransp` **diagnostics** only; `aet_layer[]` itself is correct.)

## 4. ★ MEASURED — the Phase-0 kill/proceed check (`scripts/diagnose_per_tree_water_access.py`)

Per ADR 0108's method rule, the premise was **measured before any `src/` edit**, and measured on the C's own
per-individual output rather than simulated: the `ind` table emits `wscal_mean`, `minwscal`, `D95max`,
`beta_root`, `D95`, `mort_water` and `mort_temp` **per stem**, so no port of `getrootdist` is needed for the
diagnostic. Criterion pre-registered in the script before the run. Historic, seed1, live tree stems
(`Type ≤ 6`, `D95max > 0`, `isdead == 0`):

| cell | mean `wscal_mean` | across-tree p5–p95 span | within-(PFT×age) corr `beta_root`~`wscal` (dry yrs) | drought share of total hazard | `D95max` of drought-hit stems vs mean |
|---|---|---|---|---|---|
| boreal_siberia | 0.691 | 0.051 | 0.063 | **0.147** | **−15 %** |
| temperate_hainich | 0.999 | 0.005 | 0.267 | 0.039 | **−57 %** |
| mediterranean_iberia | 0.914 | **0.193** | 0.267 | 0.069 | −3 % |
| semiarid_sahel | 0.640 | **0.162** | **0.829** | 0.000 | n/a |
| tropical_amazon | 0.999 | 0.009 | 0.227 | 0.006 | (0.5 % of stems, n too small) |

**Pre-registered verdict: PASS** (median within/between spread ratio 1.11 > 1; median dry/wet spread
amplification 2.22 > 1; median drought hazard share 0.039 > 0.01).

Read honestly, the three sub-tests are not equally strong:

- **The spread-ratio test is marginal and FAILS at two cells** (Hainich 0.82, boreal 0.64; passes at Sahel
  1.97, Amazon 1.82, Iberia 1.11). It is the weakest of the three — at Hainich and Amazon both numerator and
  denominator are tiny because those cells are essentially never water-limited on this index.
- **The dry/wet amplification is decisive**: Hainich 112×, Amazon 104×, Iberia 2.2× — trees are
  interchangeable in wet years (across-tree sd 6e-5 at Hainich) and diverge sharply in dry ones (7e-3).
  Boreal and Sahel are the exceptions (0.88, 1.14) — both are *chronically* water- or cold-limited rather
  than episodically, so their spread is large in every year.
- **The trait signal is strongest exactly where water is scarce**: in the Sahel a tree's own root-profile
  parameter explains ~69 % of the within-PFT, within-age-band variance in its own water status.
- **The selection differential is correctly signed and large**: drought-killed stems at Hainich root **57 %
  shallower** than the population mean (boreal −15 %, Iberia −3 %). This is the age–trait gradient mechanism
  of ADR 0046 acting through the hazard ADR 0049 zeroed.

**Warming response of the drought channel** (historic → ssp370, the acceptance-criterion clause): the
drought share of total hazard rises **×3.95** (Amazon), **×1.47** (Iberia), **×1.32** (Hainich), ×0.97
(boreal); the fraction of stems carrying drought hazard rises in 4 of 5 cells. **This is a warming-response
channel our emulator currently hard-zeroes.**

**The Sahel zero is explained by the trait, not by a defect.** `waterstress_tree` gates on
`wscal < mort_water_res − minwscal`. Sahel stems are all `Type 0` with mean `minwscal` **0.655**, so their
threshold is `0.75 − 0.655 = 0.095` against a mean `wscal` of 0.641 — the gate essentially never fires; they
are **drought-tolerant by trait**. Hainich beech sits at `minwscal` 0.122 ⇒ threshold 0.63, boreal at 0.125
with `mort_water_res` 0.65 ⇒ threshold 0.525 and 15.9 % of stems hit. The per-tree threshold spans **5×
between these cells and varies within them** — and it is the second trait we predict and discard. So the
rooting channel acts through **growth** in the Sahel and through **death** in the boreal; both need per-tree
water.

⚠ Every spread above is a **LOWER bound**: `wscal_mean` is a *potential* leaf-on index averaged over all 365
days and equals 1 on a no-demand day (ADR 0051), whereas `waterstress_tree` gates on the **daily** value.
Basis: **5 of 54 020** cells (ADR 0106).

## 5. Decision

**Build per-individual water state, in three separately-gated steps. Do not build the order-dependent cap.**

1. **Carry the traits.** `TreePools` gains `d95max` and `minwscal` (backwards-compatible constructor,
   `src/fdiff.jl:1942-1945`); `make_recruit_to_pools` looks them up **by name** as it already does for the two
   live axes (absent ⇒ today's behaviour); `_merge_pair!` carries them.
2. **Per-tree roots and per-tree water.** Build each tree's profile once a year in `individual_from_pools`
   (traits immutable after establishment, size annual ⇒ a daily-loop constant, no gradient cost); move the
   `wr` computation inside the individual loop; distribute withdrawal down each tree's own profile in
   `_transpire_total`; port **cap (i)**, which is order-free; make `_wscal_leafon` per-tree.
3. **Un-zero the two hazards** (ADR 0049 §3) by porting `waterstress_tree.c`'s gated daily integral on its own
   basis, using the per-tree `wscal` from (2) and the per-tree `minwscal` from (1).

**Out of scope: cap (ii).** For the record, so it is not re-derived as impossible: the C's answer *is* the
average over daily-random orders, the competing group is only 6–12 individuals, and the expectation over
uniformly random arrival orders is a deterministic, symmetric, piecewise-linear (hence smoothable) function
of the claims. The honest framing is **"reproduce the average rather than any one draw"**, not "impossible" —
and an order-average is arguably the *right* target for an emulator of a model whose own two runs differ by up
to 29 % (ADR 0106). Not started here.

## 6. Guardrail 4 and the pre-registered flip criteria

All three steps ship **opt-in, default byte-identical**. Per guardrail 4's corollary (an opt-in flag whose
default is known wrong is a defect on a timer — `wscal_leafon`, `trait_mortality` and `anchor` all sat off for
weeks), the flip conditions are registered **here, now**:

- **Step 2 → default** when, at the five biome cells against the C oracle: (a) the per-tree `wscal`
  distribution's within-cell-year spread matches the C's within the seed1-vs-seed2 noise floor on ≥3 of 5
  cells, (b) the water-closure gate stays green, and (c) no committed baseline moves that is not listed in the
  flip commit.
- **Step 3 → default** when, in addition: (d) the drought-hit selection differential on `D95max` is correctly
  signed at Hainich and boreal (the two cells where the C's is resolvable), and (e) the historic→ssp370
  **response** in per-cell trait medians improves on the rooting-depth axis without degrading the other three.
  If (d) holds and (e) does not, **say so and keep it opt-in** — do not flip on the level result alone
  (ADR 0104's error).

## 7. Consequences

- Two predicted-and-validated trait axes gain consumers, four years of `D95max` scoring stops being decorative,
  and the axis that is currently **worst on both level (28 % of cells within 10 %) and response (slope 0.16)**
  gains a physical channel.
- The S→M contract is touched, but **not** where the design note said: the per-tree carrier is `TreePools`,
  which already carries two traits. `SToF.rootdepth` becomes a real population statistic; nothing reads it.
- **This is an integration point.** `src/fdiff.jl`, `src/components/fast.jl`, `src/run.jl`,
  `src/interface.jl` are line M's; `src/components/slow.jl` is S's. Recorded in both STATE files.
- ADR 0049 §3's stated blocker ("recovering `mort_water`/`mort_temp` requires a per-PFT daily accumulator in
  F") is **not withdrawn** — it is exactly what step 2 builds.
