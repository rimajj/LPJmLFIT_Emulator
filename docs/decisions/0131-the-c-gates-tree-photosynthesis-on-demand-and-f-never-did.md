# ADR 0131 — The C gates TREE photosynthesis on canopy demand and F_diff never did; porting the gate rescues the Sahel's negative carbon balance on its own and removes 9–28 % of the assimilate error at three of five cells

* **Status:** accepted
* **Date:** 2026-08-12
* **Line:** M (multi-cell coupled S+F+E; rung 3 of `EXECUTION_PLAN.md`)
* **Supersedes:** nothing. **Narrows:** `docs/notes/sapwood_bg_design.md` §1/§6 and
  `docs/notes/phase3_fdiff_cbinary_validation.md` §13 (both of which predicted the WRONG SIGN for this
  fix), and ADR 0125 §PART 7's attribution of `semiarid_sahel`'s negative arm-A carbon balance.
* **Basis:** rung 3 — the C's own roster restarted every year, 25-patch ensemble, year-matched, five biome
  cells, historic 2010–2019. Identical to ADR 0125/0127/0129/0130, and the probe's PART 1 basis gate
  against ADR 0125's published panel **PASSes** in this run (`logs/M-treegate.1767691.out`).

---

## 1. Context — the respiration channel was put at the head of the queue and this is its cheapest lead

ADR 0130 closed ADR 0129's bracket at **≈43–47 % photosynthesis / ≈57–53 % respiration** and its handoff
put the respiration channel first. Of the respiration leads on record, exactly one is a **pure
faithfulness defect with no missing state behind it** — every other candidate (`sapwood_bg`, the
below-ground heartwood pool) needs a carbon pool F_diff does not carry:

> `src/lpj/water_stressed.c:196` runs photosynthesis only `if(gpd>1e-5 && isphoto(data.tstress))`, and
> `:83` has **already zeroed `*rd`** on entry, while the `else` at `:260` sets `agd=0`. So on a gated day
> the C's PFT contributes **neither gross assimilation nor leaf respiration**.

Two facts make this a TREE issue and not the grass issue it was recorded as:

1. **The gate is not grass-specific.** It is per-`Pft`, and this configuration runs `individual:true`, so
   **every tree is its own `Pft` entry** and the C applies the gate per individual tree. F_diff's existing
   `WaterParams.grass_demand_gate` (docs §26) is `ind.is_grass`-gated, so the tree path has run **ungated
   since it was written** — the "`rd` is not conductance-gated on rare water-stress-collapse days" v1
   simplification of `phase3_fdiff_cbinary_validation.md` §13.
2. **Only ONE half of the C's gate was missing.** F has no `isphoto(tstress)` branch, but it does not need
   one: `tstress` multiplies `c1`/`c1o` **linearly** in `photosynthesis`, so `vm`, and hence `rd = b·vm`,
   goes to 0 smoothly as `tstress` does. The `gpd > 1e-5` half has no such surrogate. ⇒ the gate fires on
   **DROUGHT-collapse days** (supply ≪ demand drives `canopy_conductance`'s `gc → 0`), **not** on leaf-off
   days, which is the opposite of where a reader of §13's "rare" would look.

On a gated day F therefore pays `rd = b·vm` — set from `apar`, so **not** collapsed with the demand —
against a suppressed `agd` plus the shared `βflux` softplus GPP floor.

## 2. Decision

**Port the gate to trees as `WaterParams.tree_demand_gate`, opt-in, default `false` ⇒ byte-identical, and
PRICE it on all five cells before proposing any default flip.** One expression in
`daily_step_canopy`; the pre-existing grass gate becomes the `ind.is_grass` branch of the same ternary.

## 3. The pre-registered prediction, and how it failed

Written into `scripts/biome_sapwood_bg_probe.jl` PART 6 **before the arm ran**, so the sign cannot be read
after the fact:

| # | prediction | outcome |
|---|---|---|
| (i) | the gate LOWERS F's GPP and RAISES F's NPP ⇒ photosynthesis channel toward the C, respiration channel away | **half right.** GPP falls everywhere (0.00–4.3 %), but NPP falls at 3 of 5 cells and rises at 2 |
| (ii) | the net effect on `bmi` (every published ADR 0125/0127 number) is therefore **WORSE** | **REFUTED at 3 of 5 cells, and spectacularly at one** |
| (iii) | ~nil at `temperate_hainich`, largest at `semiarid_sahel` / `mediterranean_iberia` | **wrong about the mediterranean** — its GPP effect is 0.01 % and the largest GPP effect is at `boreal_siberia` |

The mechanism behind the sign error is exact and worth carrying: with `A ≡ gpp − rd` and
`npp = A − rmaint − rgrowth(A − rmaint)`, gating scales `A` by `g ∈ (0,1]`, so **a gated day raises `npp`
only where its ungated `A` was NEGATIVE** and lowers it otherwise. §13's "biases NPP low on those days"
silently assumed every gated day is one of the pathological ones. It is not: at Hainich the gated days are
carbon-POSITIVE (NPP falls 1.84 %), at the mediterranean they are carbon-NEGATIVE (NPP rises 1.15 %).

## 4. The measurement (arm A → Ag, hard step; `bmi F/C` is ADR 0125/0127's published statistic)

| cell | GPP off → on | d% | NPP off → on | d% | `bmi F/C` off → on |
|---|---|---|---|---|---|
| `boreal_siberia` | 363.1 → 347.6 | −4.26 | 198.0 → 179.5 | −9.34 | 1.049 → **0.951** |
| `temperate_hainich` | 1220.0 → 1207.4 | −1.03 | 606.0 → 594.8 | −1.84 | 1.239 → **1.217** |
| `mediterranean_iberia` | 1423.2 → 1421.5 | −0.12 | 644.2 → 651.6 | +1.15 | 2.727 → 2.758 |
| `semiarid_sahel` | 517.5 → 515.7 | −0.35 | **−83.8 → +34.6** | −141.2 | **−0.457 → +0.189** |
| `tropical_amazon` | 2583.3 → 2583.3 | −0.00 | −223.2 → −223.1 | −0.07 | −0.208 → −0.208 |

Fluxes are gC/m²/yr, F's own tree-only annual ensemble means; the C side is arm-independent, so every `d%`
is the gate with nothing else moving.

**On the shipping parameter configuration (arm P → Pg, per-cohort PFT parameters + the C's own `pft_ids`):**

| cell | `bmi F/C` off → on | |
|---|---|---|
| `boreal_siberia` | 1.275 → **1.200** | better |
| `temperate_hainich` | 1.241 → **1.219** | better |
| `mediterranean_iberia` | 3.056 → 3.104 | worse |
| `semiarid_sahel` | 1.132 → **1.095** | better |
| `tropical_amazon` | 1.118 → 1.118 | unchanged |

Over the four cells whose growth error is inside an order of magnitude (i.e. excluding
`mediterranean_iberia`, whose 2.7–3.1× error dominates any mean), mean `|bmi_F/bmi_C − 1|` falls
**0.1915 → 0.1580, a 17.5 % reduction**, from one C-faithful expression and no new parameter.

## 5. The headline finding: the Sahel's negative arm-A carbon balance was the ungated `rd`, not the parameters

At `semiarid_sahel` on arm A the gate flips F's annual tree carbon balance from **−83.8 to +34.6
gC/m²/yr** — a sign change, from a stand that loses biomass to one that gains it — while moving GPP by
0.35 %. **This is the entire arm-A negativity at that cell**, and it narrows ADR 0125 §PART 7: that record
grouped the Sahel with the Amazon as cells whose negative assimilate is the per-PFT `respcoeff` defect
(0.2 tropical vs the 1.2 F carries for every tree). The two cells are **not** the same defect:

* `tropical_amazon` −223.2 → −223.1 under the gate (0.07 %), and arm P fixes it (+1198.8). **Parameters.**
* `semiarid_sahel` −83.8 → +34.6 under the gate alone, **with beech parameters everywhere**. Arm P also
  fixes it (+207.3), so that cell has **two independent sufficient causes** and ADR 0125's attribution was
  one of two, stated as the one.

⚠ A sign change is not a fidelity claim: `bmi F/C` at the Sahel is +0.189 after the gate, i.e. F still
produces **19 % of the C's assimilate** there. The gate fixes the *sign*, not the *level*.

## 6. The sharpness control, and why it matters for the differentiable path

`βgpd_gate` is shared with the grass gate, and `_with_grass_gate` pins it to the C's hard step `1e8`
whenever the grass gate is switched on — which `FDiffFastCore` does by default. Arm **Ags** runs the same
gate at the **soft, AD-usable `2e4`** (free of grass side-effects in this harness: its roster is
`type <= 6`, so no grass individual ever enters the daily loop).

| cell | NPP d%, hard `1e8` | NPP d%, soft `2e4` |
|---|---|---|
| `boreal_siberia` | −9.34 | −7.72 |
| `temperate_hainich` | −1.84 | −1.69 |
| `mediterranean_iberia` | +1.15 | +1.15 |
| `semiarid_sahel` | −141.24 | −141.24 |
| `tropical_amazon` | −0.07 | −0.07 |

⇒ **the smooth sigmoid is not doing the work.** Three cells are identical to the printed digit, Hainich
differs by 0.15 pp and boreal — the cell with the largest effect — by 1.6 pp. So the gate is available on
the Enzyme/`rollout_canopy_years_gpp` path at a gradient-friendly sharpness without becoming a different
operator, which is not true of most hard-branch ports (cf. the REFUTED §25 grass hard-floor lever).

## 7. What this does NOT show

* **It is not the photosynthesis channel.** The GPP effect is ≤ 4.3 % at every cell and ≤ 1.1 % at four of
  five, so ADR 0130's +10.1 % GPP excess at Hainich is untouched by it.
* **It is not measured at `mediterranean_iberia` in a usable way.** That cell's own growth error is 2.7–3.1×
  and the gate moves it the wrong way; ADR 0127 §6 already excludes it from arm scoring for the same reason.
* **The INCIDENCE is not measured — only the effect.** Counting gated tree-days needs an accumulator inside
  `daily_step_canopy`, i.e. a struct on the Enzyme path, which ADR 0110 makes a SIGABRT risk. The probe says
  so in its own output rather than leaving the omission implicit.
* **Five cells, historic window.** Nothing here may be quoted against ADR 0106's all-54 020-cell criterion,
  and the warming window is unrun.

## 8. Guardrail 4 — the evidence, and the PRE-REGISTERED FLIP CRITERION

**Default byte-identical, evidenced twice:**

* the CI-faithful suite on this diff with the flag defaulting off: **274 934 pass / 0 fail**, 133 test items
  (job 1767694, `src/` change only) and **275 028 pass / 0 fail**, 134 items with the new gate included
  (job 1767974) — no committed baseline moved either time. Docs built locally (job 1768287, exit 0, the five
  mermaid fences still render), because `src/**` changed and the `docs` gate never runs on a line branch;
* the regenerated `test/testitems/references/M_growth_channel_decomposition.csv` differs from its previous
  version in **exactly three comment lines** (the new arms' legend); **every pre-existing data row is
  byte-identical**, verified by diff against the four original arms' rows.

New gate: `test/testitems/tree_demand_gate_tests.jl` pins the mechanism, not the verdict — the flag is off
by default, the off-path reproduces a bare `tebs_params()` rollout **bit-for-bit**, a grass individual in a
fixed-structure daily rollout is **byte-identical** when only the tree flag flips (the gate multiplies only
tree GPP and tree `rd`, both formed after the gate-free `gp_stand`, transpiration and per-layer withdrawal),
the trees are not, and stand GPP is monotone under the gate.

**Guardrail 4's corollary is binding here — this default is now KNOWN UNFAITHFUL, so the flip criterion is
pre-registered rather than left to a future session's judgement.** Flip
`WaterParams.tree_demand_gate` to `true` (leaving `βgpd_gate` at `2e4`, licensed by §6) when **all three**
hold:

1. the `sapwood_bg` **growth** port (ADR 0127 §5/§6) has landed, because it acts on the **same CUE channel**
   and `sapwood_bg_design.md` §6 records that the two partially cancel — flipping this default first would
   silently re-price that port's pass criterion;
2. on arm Pg, mean `|bmi_F/bmi_C − 1|` over the four readable cells (excluding `mediterranean_iberia`) does
   not increase against the then-current arm P;
3. the full suite's failure list is enumerated and every moved assertion is a deliberate baseline move
   (the `julia-test` skill's default-flip procedure).

Owner: line M. Recorded as an ACTION in `lines/M/STATE.md`, not as a note.

## 9. Method note, for the `residual-diagnosis` skill

Two things generalise beyond this fix:

* **A written prediction that fails is worth more than one that succeeds, but only if it was written down
  first.** Prediction (ii) came from two independent design notes that both had the sign wrong, and it propagated into a third; the failure localised the error to one unstated assumption (that every
  gated day is carbon-negative), which is a sharper result than the arm's own numbers.
* **"Rare" is a claim about incidence and needs a mechanism before it is believed.** §13 called these "rare
  water-stress-collapse days" and the phrase survived unchallenged into two later notes. The mechanism says
  they are *drought* days — so "rare" is a statement about the CELL, not about the model, and at a semiarid
  cell it was false enough to be the whole sign of the carbon balance.

## 10. Files

* `src/fdiff.jl` — `WaterParams.tree_demand_gate` + the one-expression change in `daily_step_canopy`; the
  `_with_grass_gate` comment amended (turning the grass gate on re-pins the SHARED `βgpd_gate` and thereby
  sharpens the tree gate too).
* `scripts/biome_sapwood_bg_probe.jl` — arms `Ag` / `Ags` / `Pg` + PART 6; `arm`/`run_one_year!` gained
  `params` and `grass_gate` kwargs (defaults unchanged ⇒ arms A/Abg/P/Pbg byte-identical).
* `test/testitems/tree_demand_gate_tests.jl` — new.
* `test/testitems/references/M_growth_channel_decomposition.csv` — three arms appended, pre-existing rows
  byte-identical.
* Logs of record: `logs/M-treegate.1767691.out` (the measurement, PART 1 gate PASS),
  `logs/M-treegate-suite.1767694.out` (guardrail 4).
