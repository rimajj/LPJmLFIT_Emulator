# ADR 0127 — The `keep` gap is NOT an allocation defect: F's surplus above-ground growth, decomposed exactly into three carbon channels

- **Status:** accepted
- **Date:** 2026-08-12
- **Line:** M (multi-cell coupled S+F+E) · ADR block 0120–0139
- **Consumes:** ADR 0125 (rung 3: the paired per-stem growth error and the `bmi`/`keep` split it
  introduced), ADR 0126 (per-cohort PFT parameters; §6.4 promoted the `keep` gap to the binding F-side
  item), ADR 0060 (never substitute a reference basis silently; emit both columns), ADR 0111 §9 (keep
  exactly ONE definition of a ratio statistic, and guard its denominator)
- **Supersedes:** nothing. **Narrows ADR 0125 §7 and ADR 0126 §6.4** — the item they named as "the
  binding F-side gap" is a ratio-form of an error they had already attributed elsewhere at 4 of 5 cells.
- **Also corrects:** ADR 0125 §PART 7's published `keep_F` at `semiarid_sahel` (see §3).

## 1. Context — the residual, and why it was believed to be allocation

ADR 0125 split F's paired per-stem growth error into *how much assimilate comes in* (`bmi_F/C`) and *how
much of it ends up as standing above-ground biomass* (`keep = ΣΔagb / bmi`). At the two cells where the
input was already right, the retention was not:

| cell | `bmi_F/C` | `keep_F` | `keep_C` | `keep_F/C` |
|---|---|---|---|---|
| boreal_siberia | 1.05 | 0.465 | 0.251 | **1.85** |
| temperate_hainich | 1.24 | 0.549 | 0.368 | **1.49** |

ADR 0126 wired the C's own per-PFT parameters and the overshoot survived (Σ`dagb` F/C 1.45–1.48 at those
two cells), so §6.4 concluded it is not a parameter and named it *"the binding F-side item"*, with the
allocation/turnover suspects listed in order: the summergreen full-leaf recycle, the `reprod_cost` path,
and whether F's `agb` reconstruction and the C's `agb` column are the same pool set.

**The third suspect turned out to be the whole question, and the answer changes the attribution.**

## 2. The reference basis, read off the C source rather than the column names

Both sides carry columns called `agb` and `vegc` and they are **not** the same pool sets:

| | expression | source |
|---|---|---|
| C `agb` | `(leaf + heartwood + sapwood − debt + excess)·nind − turn_litt.leaf` | `agb_tree.c:25`, `tree.h:259` |
| C `vegc` | `(leaf + root + heartwood + sapwood + `**`sapwood_bg`**` + `**`heartwood_bg`**` − debt + excess)·nind − turn_litt.leaf − turn_litt.root + fruit` | `veg_sum_tree.c:25`, `tree.h:257` |
| F `agb_ind` | `leaf_c + sapwood_c + heartwood_c` | `fdiff.jl:2277` |
| F `vegc_ind` | `leaf_c + sapwood_c + heartwood_c + root_c` | `fdiff.jl:2282` |

⇒ the C's below-ground bucket `vegc − agb` holds **root + below-ground sapwood + below-ground
heartwood**; F's holds **root only**. `Treephys2` (`tree.h`) carries the two below-ground wood pools that
F does not have, and `allocation_tree.c:163-209 / :268-277` **deducts their annual demand from
`bm_inc_ind` before the leaf/root/sapwood split**. F's `grow_individual` carries `sapwood_bg_c` through
unchanged (`fdiff.jl:2460-2467`, the deferred `docs/notes/sapwood_bg_design.md` §5.4 step) and its
`sap_inc = bm_net − leaf_inc − root_inc` is a **residual**, so any undeducted demand lands in
**above-ground** sapwood, which is in `agb_ind`.

Harness: `scripts/biome_sapwood_bg_probe.jl` — a **second, independent reader** of the same fixtures as
`biome_canopy_growth_probe.jl`, gated on reproducing all 20 of ADR 0125 §PART 7's published numbers
(`bmi_F`, `bmi_C`, `keep_F`, `keep_C` × 5 cells) to the printed digit before anything new is read. **It
does**, and the reconstruction residual `recon` is 0.00 at every cell, so the published `keep_C` was a
clean C-side quantity. Log of record `logs/M-sapbg3.1765720.out` (4 arms × 5 cells × 10 yr × 25 patches,
~9 min); committed table `test/testitems/references/M_growth_channel_decomposition.csv`.

## 3. First finding — two definitions of `keep` exist, and one of the published numbers is not a fraction

`carbon_panel` forms `keep` as the **mean of the per-year ratios**; the natural absolute form is the
**ratio of the year means**. On four cells they agree to ≤3 %. At `semiarid_sahel` they do not:

| cell | `keepF` mean-of-ratios (published) | `keepF` ratio-of-means | ratio |
|---|---|---|---|
| semiarid_sahel | **+0.350** | **−0.059** | **−5.885** |
| mediterranean_iberia (C side) | 0.269 | 0.335 | 0.802 |

Arm A's assimilate at the Sahel **changes sign between years** (its 10-year mean is −83.8 gC/m²/yr), and a
mean of per-year ratios with a sign-changing denominator is not a retained fraction of anything. ADR 0125's
published `keep_F = 0.350` for that cell should be read as **undefined**, not as "F retains 35 %". This is
ADR 0111 §9's denominator rule in its exact predicted form. Both columns are now printed side by side in
the probe and both are in the committed table (ADR 0060's rule); nothing is substituted silently.

## 4. The decision — score the ABSOLUTE carbon identity, not the ratio

On each side, with no model in it,

    Δagb  =  assimilate  −  loss  −  Δbelow

(`loss` = everything that left the plant: the reproduction reserve, leaf and fine-root litter, and on the
C side the carbon-debt payback). Differencing the two sides gives an **exact, additive** attribution of
F's surplus above-ground growth into three named channels:

    Δagb_F − Δagb_C  =  (bmi_F − bmi_C)  −  (loss_F − loss_C)  −  (Δbel_F − Δbel_C)
                     =    t_input        +    t_loss           +    t_nosink

Measured (arm A = the ADR 0125/0126 basis; gC/m²/yr, 2010–2019 means, five biome cells):

| cell | `dagb_C` | **surplus** | `t_input` | `t_loss` | `t_nosink` |
|---|---|---|---|---|---|
| boreal_siberia | 49.0 | **+43.5** | +9.2 (21 %) | +14.4 (33 %) | **+19.9 (46 %)** |
| temperate_hainich | 181.1 | **+152.7** | **+117.0 (77 %)** | +4.7 (3 %) | +30.9 (20 %) |
| mediterranean_iberia | 79.2 | **+320.5** | **+408.0 (127 %)** | −100.7 (−31 %) | +13.2 (4 %) |
| semiarid_sahel | 90.6 | −85.6 | −267.0 | +159.9 | +21.5 |
| tropical_amazon | 372.0 | −402.4 | −1295.8 | +755.9 | +137.5 |

(The two hot cells' arm-A columns are dominated by the ADR 0125 `respcoeff` defect — their assimilate is
negative — and are reported for completeness, not read.)

**At `temperate_hainich` — the prototype, 99.4 % beech, every parameter already faithful — 77 % of F's
surplus above-ground growth is the ASSIMILATE error and 3 % is allocation/turnover.** At
`mediterranean_iberia` the assimilate channel is 127 % of the surplus and the loss channel *over*-corrects
by 31 %. Only at `boreal_siberia`, where the assimilate is nearly right (+4.9 %), do the allocation and
sink channels bind.

**Why the ratio misled.** F's litter fluxes are **pool-driven** (a summergreen sheds its leaf pool and its
fine-root pool each year regardless of that year's NPP) while its assimilate is not. So a too-large
`bm_inc` mechanically raises the retained *fraction* even with a perfectly faithful allocation — and the
absolute losses confirm it: at Hainich `loss_F` = 262.1 against `loss_C` = 266.8 gC/m²/yr, i.e. **F's
turnover + reproduction flux is right to 1.8 %** while its `keep` ratio is 49 % high.

⇒ **the item ADR 0125 §7 / ADR 0126 §6.4 named "the binding F-side gap" is, at 4 of 5 cells, a ratio-form
of the assimilate error those same ADRs had already attributed elsewhere.** It is retired as an
independent defect. The F-side queue re-points to the assimilate (`bmi_F/C`), which at Hainich is +24 %
with no parameter excuse left.

## 5. The one genuinely new channel — the below-ground wood sink, measured and priced

`t_nosink` is real and it is the C's below-ground wood. The C's below-ground **wood** (sapwood_bg +
heartwood_bg together) grows by exactly the year's C_LATERAL top-up: `turnover_tree.c:124-130` moves
`sapwood_bg·turnover.sapwood` into `heartwood_bg`, which is *internal to the bucket*, and
`allocation_tree.c:268-277` tops `sapwood_bg` back up from `bm_inc`. Reconstructing that demand per stem
with the already-ported `FDiff.reconstruct_sapwood_bg`:

| cell | pool (gC/m²) | % of above-ground biomass | demand increment `dD` | measured `bel_C` | `dD/bel_C` |
|---|---|---|---|---|---|
| boreal_siberia | 256.4 | 29.8 | 2.25 | 20.44 | **0.11** |
| temperate_hainich | 564.8 | 12.2 | 49.25 | 41.05 | **1.20** |
| mediterranean_iberia | 540.0 | 27.0 | 135.08 | 34.40 | 3.93 |

**At Hainich the C_LATERAL demand reproduces the C's whole measured below-ground sink to 20 %**, in the
direction expected (F over-grows, so a demand computed at F's own growth over-states it). At the boreal
cell it explains **11 %** — that cell's below-ground sink is mostly something else (fine-root growth in a
stand that is not at steady state), so the port is **not** the boreal answer. At the mediterranean cell
the demand overshoots 3.9× because F grows 2.7× too fast there; that column measures F's growth error, not
the sink.

**The maintenance half is already landed and is measured here at no `src/` cost.** Seeding the pool
(`docs/notes/sapwood_bg_design.md` §8.1) switches on its respiration through `individual_from_pools`:
it costs **2.4 / 3.6 / 6.3 %** of the assimilate at boreal / Hainich / mediterranean and removes
**9 / 12 / 9 %** of the surplus. The most faithful configuration that exists today — per-cohort PFT
parameters + the seed — leaves the surplus at **+71.9 / +134.9 / +378.3 / +42.3 / +127.9** gC/m²/yr
against C increments of 49.0 / 181.1 / 79.2 / 90.6 / 372.0.

## 6. ⚠ A CORRECTION TO THE DESIGN NOTE: the port needs TWO pools, not one, or it leaks carbon

`docs/notes/sapwood_bg_design.md` §5.4 specifies the deferred step as *"grow the pool"* from the C_LATERAL
demand. That is not implementable in the single `TreePools.sapwood_bg_c` field, and the reason was not in
the note:

* the C's `sapwood_bg` is **pinned to the demand** after every allocation (`ind.sapwood_bg += tinc` where
  `tinc = D − sapwood_bg_post_turnover`), so it is a state variable, not a stock;
* `turnover_tree.c:124-130` moves `sapwood_bg·turnover.sapwood` into a **second** pool, `heartwood_bg`,
  which only ever accumulates and never respires.

So a one-field port must either (a) apply the turnover and **destroy** `r·sapwood_bg` per year (≈22 gC/m²/yr
at Hainich — a carbon leak, and guardrail 2 makes conservation a CI gate), or (b) not apply it and charge
maintenance respiration on the below-ground **heartwood** as well, which the C does not. **Neither is
acceptable.** `TreePools` needs `heartwood_bg_c` alongside `sapwood_bg_c`, and `vegc_ind` must then gain
both (today `sapwood_bg_c` is deliberately outside the conserved ledger *because* the pool is static).
That is the struct + AD-path churn the design note budgets at 2–3 sessions, and it is **not** landed here.

**PRE-REGISTERED PASS CRITERION for that port** (written before the arm exists, ADR 0104's rule): with
`sapwood_bg` seeded *and* prognostic, the paired surplus `Δagb_F − Δagb_C` must fall by **at least
`t_nosink`** at `boreal_siberia` and `temperate_hainich` (i.e. ≥19.9 and ≥30.9 gC/m²/yr) **without** any
committed baseline moving while the feature is off, and the tree CUE must stay inside `[0.42, 0.56]`.
Decide on those two cells only — the mediterranean cell's demand is contaminated by its own 2.7× growth
error and the two hot cells' arm-A assimilate is negative.

## 7. Scope — what this is NOT

* **Five cells of 54 020**, one scenario, ten years. This is a mechanism result, not fidelity evidence
  (ADR 0106).
* The decomposition is **exact** but its third channel compares **different pool sets by construction**
  (the C's below-ground bucket vs F's fine roots). That asymmetry is the finding; it is stated with every
  number and it is why §5 prices the sink from the model side as well as measuring it from the C's.
* `dD` uses the **cell-mean** root profile (F's seed convention) while the C uses each individual's own
  `beta_root` (ADR 0110), so a deep-rooted stem's demand is under-stated.
* Nothing in `src/` changed. Guardrail 4 is not at issue.
* The two hot cells are unreadable in arm A and only partly readable in arm P; no claim is made from them.

## 8. Consequences

1. **`keep_F/keep_C` is retired as a headline statistic.** Report the absolute three-channel
   decomposition. The committed table is `test/testitems/references/M_growth_channel_decomposition.csv`.
2. **ADR 0125's `keep_F` for `semiarid_sahel` (0.350) is withdrawn** as undefined; the ratio-of-means is
   −0.059 and the honest statement is that arm A's assimilate changes sign there.
3. **The F-side queue re-points to the assimilate error**, which is ADR 0126 §6.2's own flip criterion —
   at Hainich +24 % with all parameters faithful and 99.4 % beech, i.e. a pure F-physics defect at the
   prototype cell.
4. **`boreal_siberia` is now the one cell where allocation/turnover genuinely binds** (`t_loss` 33 % of a
   surplus that is 1.89× the C's own increment) and where the below-ground sink is NOT the explanation
   (`dD/bel_C` = 0.11). It is the right cell for the next allocation probe, and the wrong one for the port.
5. **`docs/notes/sapwood_bg_design.md` §5.4 is amended** with §6 above.
