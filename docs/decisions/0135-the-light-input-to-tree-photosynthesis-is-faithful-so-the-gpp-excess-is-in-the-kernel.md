# ADR 0135 — Scoping the photosynthesis half: the light INPUT to F_diff's tree photosynthesis is faithful to the live C, so the GPP excess is in the kernel — and the one candidate that looked decisive was a commented-out C branch

* **Status:** accepted
* **Date:** 2026-08-13
* **Line:** M (multi-cell coupled S+F+E; rung 3 of `EXECUTION_PLAN.md`)
* **Supersedes:** nothing. **Narrows:** ADR 0130 §6 (locates its +10.1 % GPP excess in the kernel, not the light input). **Corrects:** a source comment in `src/fdiff.jl` that justified the layered-light port with a wrong number.
* **Basis:** the LIVE lines of `/home/jamirp/lpjml56fit/src/lpj/getfpar.c` etc.; the global historic seed1 `ind` parquet at the five biome cells, 2010–2019, survivors (`Type<=6 & D95max>0`); and the committed C reference `test/testitems/references/M_fdiff_oracle_biomes_annual.csv`.
* **Related:** ADR 0129, 0130, 0131, 0133 (the assimilate split and the demand gate); ADR 0126 (per-PFT parameters); ADR 0060 (the two FPCs); ADR 0134 (the method this reuses).

---

## 1. Context — the item this discharges

Line M's handoff has carried, for two sessions:

> **"The photosynthesis half of the assimilate is the head of the F queue and still unscoped."** At Hainich
> F over-grows by 57 % with 77 % of that on the assimilate (ADR 0127 §4); ADR 0130 split the assimilate
> ≈43–47 % photosynthesis / ≈57–53 % respiration. The respiration half has two priced leads landed
> (per-PFT `respcoeff`, ADR 0125; the demand gate at 17.5 %, ADR 0131/0133); **nothing aims at the
> photosynthesis half.** ADR 0130's **+10.1 % GPP excess at Hainich** is the concrete target.

This ADR is the scoping step, not a fix. It asks one question — **is the excess in the light INPUT or in the
kernel?** — because the kernel is homogeneous of degree 1 in `apar` except for the SLA Vcmax cap, so the light
input is the largest single lever on tree GPP that is not the kernel itself, and because "the tall trees hog
the light" is the most plausible-sounding suspect on the list.

## 2. Decision

**The light input is FAITHFUL. Close it as a suspect and record the audit, so the photosynthesis work aims at
the kernel and its non-light inputs.** Ship the audit as a committed 2-second diagnostic
(`scripts/diagnose_layered_light_basis.py`), no source change, no flag, no default.

## 3. ⚠ THE FINDING THAT NEARLY WENT THE OTHER WAY — a `grep`/`sed` read landed inside a commented-out C branch

The first pass of this audit produced what looked like a first-order defect, and it was wrong. It is recorded
first because the *method* matters more than the (retracted) number.

`getfpar.c` builds each stem's leaf-area density `atoh` for the vertical layer integration. Read via a `sed`
line range and via `grep`, the expression that surfaces is

```c
atoh = lai_tree(pft)/(tree->height-tree->boleht);     /* lai_tree = leaf_c*sla/CROWNAREA  */
lai_leafon_layer[p] = atoh*frac*VSTEP;                /* ... and NO *nind                 */
```

i.e. a **per-crown** leaf-area density summed across individuals. Against F's **per-patch**
`min(leaf_c·sla/cd, 40)·nind` that is a per-stem ratio of exactly `crownarea·nind = crownarea/patcharea`,
measured at a **median 0.016–0.098** across the five cells — a 5–37× optical-thickness gap that makes the C's
tree canopy fully opaque (absorbed fraction **1.000** in all five cells) against F's 0.40–0.97. That is a
dramatic finding, it was internally consistent, and it is **an artefact of reading a comment**.

Read verbatim in context, `getfpar.c:108-124` is:

```c
/* original FIT code   */
  atoh=tree->ind.leaf.carbon*pft->sla/(tree->height-tree->boleht);
    if(atoh>40)
       atoh=40;
    lai_leafon_layer[p]=atoh*frac*VSTEP *pft->nind;
/* test: use LAI for atoh calc
     atoh=(tree->ind.leaf.carbon*pft->sla/tree->crownarea)/(...);            ... */
/* test: like in GUESS3.0
     atoh=lai_tree(pft)/(tree->height-tree->boleht);
     lai_leafon_layer[p]=atoh*frac*VSTEP;                                     */
```

**The live line is per-PATCH, carries `*pft->nind`, and caps `atoh` at 40 BEFORE the `*nind`.** F's
`_patch_fpars_soa` is `min(leafc·sla/cd, 40)·nind` — the same expression, the same cap, in the same order.
The two per-crown forms are both inside `/* test: ... */` blocks.

**The generalisable rule** (CLAUDE.md §3; appended to the `residual-diagnosis` skill): guardrail 5 and the
`individual=true` dead-path rule say *confirm the C path actually executes*. **A commented-out block is a dead
path that no config check and no `grep` will flag** — it looks exactly like live code in every tool output
except a verbatim read of the surrounding lines. Before scoring a port against a C expression, `awk`/`sed` the
**enclosing** lines and look for the comment delimiters. This file contains three candidate expressions for one
quantity, two of them dead, and they differ in precisely the factor under audit.

## 4. The audit — every factor in the C's tree APAR, against F

`water_stressed.c:204` is `apar = par·(1−albedo_leaf)·alphaa(pft)·fpar(pft)`, and in `individual:true` mode
`fpar(pft)` resolves through the function pointer at `fscanpft_tree.c:142` to **`fpar_tree_ind`** — i.e.
`pft->fpar*(1−pft->snowcover)`, the layered share from `getfpar.c`. (**Not** `fpar_tree`, the crown-cover form
`phen·fpc·(1−snowcover)`; that is the non-individual-mode function and is dead here — a second live/dead pair
in the same chain.)

| factor | C (live) | F_diff | verdict |
|---|---|---|---|
| `par` | `dayseconds·swdown/2` (`petpar3.c:74`) | `0.5·dayseconds·swdown` | **match** |
| `albedo_leaf` | per-PFT `par->albedo_leaf` | per-stem `ind.albedo_leaf`, from the C's own table | **match** |
| `alphaa` | `pft->par->alphaa` (N off ⇒ the PFT constant; `alphaa_tree.c`) | per-stem `ind.alphaa` | **match** |
| light model | vertical layered Beer–Lambert, `getfpar.c` | `_patch_fpars_soa` | **match** (§3) |
| leaf-area density | `min(leaf_c·sla/(h−bole), 40)·nind` | identical, same cap order | **match** (§3) |
| `k_lambert` | **0.5**, a global (`par/lpjparam_fit.js`), not a PFT parameter | `k_lambert = 0.5` | **match** |
| `VSTEP` / crown geometry | 2.0 m; `bole = (1−crownlength)·h`, `crownlength` 0.3334 for all 7 PFTs | 2.0 m; same | **match** |
| SLA Vcmax cap | `issla = config->individual` ⇒ **ON**, per stem's own `sla` | `issla = true`, `PhotoParams.sla` read **per stem** from the C's output | **match** |
| **phen placement** | phen is **inside** the extinction (`:126`, `:158`) ⇒ `pft->fpar` | leaf-on share × phen afterwards (`fdiff.jl:1923`) | **DIFFERS** — §5 |
| **snowcover** | `·(1−pft->snowcover)` (`fpar_tree_ind.c:20`) | absent | **DIFFERS** — §6 |

### 4b. The port's basis, checked against the C's own output rather than against the source

Reading the source is how §3 went wrong once, so the basis is also scored against a quantity the C **emits**.
The layer loop telescopes (`Σ_layers atoh·frac·VSTEP = atoh·crowndepth`), so the port's patch leaf-area index
has a closed form readable straight from the `ind` table — `crownarea·nind = fpc_ind/(1−exp(−k_pft·LAI))`
(`fpc_tree.c:28`) — and can be compared against the run's own `LAI_STAND` output:

| cell | stems/patch | plai (the port's basis) | the C's own `LAI_STAND` | ratio |
|---|---|---|---|---|
| `boreal_siberia` | 11.5 | 1.415 | 1.611 | **0.878** |
| `temperate_hainich` | 9.9 | 2.811 | 3.236 | **0.869** |
| `mediterranean_iberia` | 8.3 | 1.476 | 1.504 | **0.981** |
| `semiarid_sahel` | 13.3 | 1.146 | 1.264 | **0.907** |
| `tropical_amazon` | 4.9 | 3.394 | 5.912 | **0.574** ⚠ |

The port lands **just below** `LAI_STAND` at four cells, which is the direction the basis predicts: the `ind`
writer emits only stems above 5 m, so both the leaf area **and** the grass are missing from the sum. The
retracted per-crown basis would give **4.8–37×** these numbers. ⇒ the port's basis is confirmed by the C's own
output, not only by the source.

⚠ **`tropical_amazon` at 0.574 is flagged, not smoothed.** That cell has the fewest emitted stems per patch
(4.9) and by far the largest sub-5 m share of stem count (ADR 0130: 0.659 above the cut), so more of its leaf
area is below the writer's cut. It is consistent with the cut, but it is **not evidence** the way the other
four are, and the script prints `CHECK` rather than `OK` for it.

## 5. The one live difference that is priceable — phen placement, and it is an UPPER BOUND

The C weights the extinction profile by phenology **inside** the integral: `plai_layer += lai_leafon·phen`
(`:126`) and shares each layer's uptake by the phen-weighted numerator (`:158`), producing `pft->fpar`
directly. F computes the **leaf-on** share (`_patch_fpars_soa` takes no phen argument) and multiplies after:
`fpar_i = ind.fpar·phen`. These agree only at `phen ≡ 1`. For a patch with leaf-on layered `plai` and a
uniform phenological state `φ`, the two absorbed fractions are

    C:  1 − exp(−k·plai·φ)          F:  φ·(1 − exp(−k·plai))

so by concavity **F under-absorbs on every partial-leaf day**, by a pure function of `plai`:

| cell | plai | absorbed at φ=1 | max gap | at φ | as a fraction of F's own absorption |
|---|---|---|---|---|---|
| `boreal_siberia` | 1.415 | 0.507 | 0.0445 | 0.47 | **0.187** |
| `temperate_hainich` | 2.811 | 0.755 | 0.1291 | 0.44 | **0.389** |
| `mediterranean_iberia` | 1.476 | 0.522 | 0.0478 | 0.47 | **0.195** |
| `semiarid_sahel` | 1.146 | 0.436 | 0.0311 | 0.47 | **0.150** |
| `tropical_amazon` | 3.394 | 0.817 | 0.1667 | 0.43 | **0.475** |

⚠ **These are per-DAY upper bounds, not annual effects, and no default or parameter may be published from
them** (ADR 0105). They bind only where `0 < phen < 1`, and the WEIGHT of such days in annual GPP is **not
measured here** — `phen` is not an `ind` column. A second, unpriced part of the same difference: when
individuals' phen differ, the C lets a leafless stem stop shading the stems below it while F keeps it in the
leaf-on profile.

## 6. The difference that is not priceable from existing artifacts — snowcover

`fpar_tree_ind` returns `pft->fpar*(1−pft->snowcover)`; F's tree APAR has no such factor (`snowcanopyfrac` is
carried on `Individual` and consumed by the albedo path only). `snowcover` is not an `ind` column, so this
needs a C re-run or an F-side reconstruction. **Listed, not measured** — and it, too, makes F absorb *more*,
i.e. it is the one live difference whose sign could contribute to the excess, at the cells and seasons where a
green canopy coincides with snow. Under GSI phenology all seven tree PFTs shed in winter (ADR 0134), so the
overlap window is narrow; that is a reason to price it, not a reason to assume it is zero.

## 7. ⇒ What this means for the photosynthesis half (the point of the exercise)

**Both live differences make F absorb LESS PAR than the C, while F's tree GPP is measured ABOVE the C's**
(Hainich 1.074× on the shipped default, ADR 0133). So:

1. **Neither explains the excess.** The photosynthesis suspect that would have been most expensive to fix — a
   light-competition rewrite — is closed by a 2-second parquet scan and a verbatim source read.
2. **The kernel-side error is LARGER than the measured ratio**, because the light input is biased the other
   way. How much larger is not quantified: GPP is concave in `apar` through the SLA Vcmax cap, so the apar
   bound does not transfer linearly to GPP.
3. **Since the light input is faithful, `GPP_F/GPP_C` on a matched roster IS the kernel error** — which makes
   ADR 0130's +10.1 % (now 1.074× after the gate) a clean target rather than a composite one.

**The remaining shortlist for the photosynthesis half**, in the order the evidence supports:

* **(a) The λ solve's Vcmax.** The C's bisection residual (`water_stressed.c`, `data.compvm=FALSE`) uses
  `pft->vmax` as left by **`gp_sum`** — computed at `LAMBDA_OPT` from a **crown-cover** apar
  (`par·pft->fpc·alphaa·(1−albedo)·(1−snowcover)`, no `phen`) — whereas F recomputes `vm` at the **actual
  layered, phen-scaled** apar before its solve (`fdiff.jl:1927`). The C then recomputes `vm` at the actual
  apar in its final call, so only the **solved λ** differs, not the final Vcmax. Cheap to test: an F arm that
  feeds the pass-1 (`apar_gp`) Vcmax into the pass-2 λ solve.
* **(b) `temp_stress` and the `isphoto`/`tstress<1e-2` hard zeroing**, which F replaces with a smooth linear
  `tstress` factor. ADR 0131 argued this half of the C's gate needs no branch; that argument is about
  *smoothness*, not about the *threshold*, and the threshold has never been scored.
* **(c) The phen trajectory itself.** ADR 0130 §6 refuted the *upper* bracket end and with it "GSI phenology
  is the single cause", but +10.1 % against a documented +17 % phenology GPP level does not exclude phenology
  as **part** of it — and §5 above shows F's phen enters the light differently as well.

**Do not re-open**: the layered-light model, the leaf-area density basis, `k_lambert`, `par`, `alphaa`,
`albedo_leaf`, or the per-stem SLA Vcmax cap. Each is checked in §4 with the C line that settles it.

## 8. Consequences

* **A wrong number in a source comment is corrected.** `src/fdiff.jl`'s multi-individual design comment says
  the canopy *"absorbs the true layered fraction (≈0.83 leafon)"*. 0.83 is F's own leaf-on absorption at
  Hainich, not a C reference — the C's is the same number, because the port is faithful, so the sentence
  asserts a validation that was never run. Reworded to say what is actually true and to point at this ADR.
  (`residual-diagnosis`: a comment asserting consistency with a reference is a test you have not run.)
* **No behaviour change, no flag, no default.** `scripts/*.py` is not linted by CI and this diff touches no
  gate-watched path except `src/fdiff.jl` comments, which do trigger `CI`/`format`/`docs`.
* **The `ind`-table closed forms in §4b are reusable**: `crownarea·nind = fpc_ind/(1−exp(−k_pft·LAI))` turns
  any per-patch canopy-geometry question into a parquet scan (ADR 0110's rule, one more instance).

## 9. Alternatives rejected

* **Go straight to an F arm for the phen placement.** Rejected for now: it is wrong-signed for the excess, so
  it cannot be the scoping answer, and ADR 0105 forbids publishing a value from a bound. It belongs behind
  whichever of §7's shortlist turns out to carry the excess.
* **Score the light input against the C's `FAPAR`/`d_fapar` output.** Rejected: `albedo_tree.c:75` builds
  `pft->fapar` from **`pft->fpc`** and the albedos, so it is the crown-cover quantity (ADR 0060's `a_fpc`
  family), not the layered `pft->fpar` under audit — the same same-name-different-quantity trap. `LAI_STAND`
  is the output that constrains the basis, which is why §4b uses it.
* **Trust the §3 source read and open a light-model milestone.** That was one commit away and would have been
  a rewrite of a faithful component, justified by a comment block.
