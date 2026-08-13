# ADR 0134 — The uniform leaf-recycle suspect is REFUTED at `boreal_siberia`, and relocated to the two cells whose leaf longevity actually exceeds the C's own clamp

- **Status:** accepted
- **Date:** 2026-08-13
- **Line:** M (multi-cell coupled S+F+E; ADR block 0120–0139)
- **Supersedes:** nothing. **Narrows:** ADR 0132 §8 item 5 / ADR 0133's "what to do next" item 1, which
  named `AllocParams.is_deciduous` as the concrete `boreal_siberia` allocation suspect.
- **Related:** ADR 0126 (per-PFT parameters; §5's one-variable-arm rule), ADR 0127 (the additive growth
  identity), ADR 0130/0131/0133 (the assimilate channel), ADR 0047 (read a `.js` value with `cpp -P`,
  and the duplicate-key trap), ADR 0110 (the `ind` table as a per-stem oracle), ADR 0117 (the
  variability audit must be the first panel).

## Context

The previous two handoffs carried this as line M's next action, stated as a concrete, cheap, per-PFT
defect of the same shape as the parameter work already landed in ADR 0126:

> `AllocParams.is_deciduous` is `true` for **every** tree in F, while the C gates the summergreen
> full-leaf recycle (`leaf/1.05`) on `tree->isphen` (`turnover_tree.c:100`) — so F runs a summergreen
> leaf recycle for the boreal/temperate **evergreen** PFTs.

The premise is that the C's gate discriminates by PFT **phenology type**, so a per-PFT `is_deciduous`
would fix an evergreen-dominated cell. This record establishes that the premise is wrong in three
independent ways, that the conclusion is *mechanically impossible* at the cell it was aimed at, and
that the real gap sits at two different cells — one of which is the worst-scoring cell on the board.

No code behaviour changes here. What changes is where the next F-side work points, plus two corrected
claims and one new durable fact about the C.

## Decision

**1. The C's phenology-TYPE switch is dead code in this configuration.** `lpjmlfit.js:53` sets
`"new_phenology": true`, so `daily_natural.c:123-124` dispatches to `phenology_gsi`, never to
`leaf_phenology` → `phenology_tree`. The entire `SUMMERGREEN` / `RAINGREEN` / `EVERGREEN` switch in
`src/tree/phenology_tree.c` — the only place the `phenology` PFT key selects a leaf-turnover behaviour
— **never executes**. This is CLAUDE.md §3's individual-mode dead-path rule (guardrail 5) firing on a
suspect that had already been written into two handoffs.

**2. Even if it did execute, it could not discriminate: all seven tree PFTs are declared
`"phenology": "summergreen"`.** Read with `cpp -P` from the live `par/pft_lpjmlfit.js` (`:190, 320,
450, 580, 710, 840, 970`), including id 0, the *tropical broadleaved evergreen*, whose `//"raingreen"`
alternative is commented out. The PFT **names** are evergreen; the parameter is not. So a per-PFT
`is_deciduous` derived from that key would have been a uniform `true` — i.e. exactly today's code.

**3. What the C actually does is a RUNTIME LATCH, `tree->isphen`, and it is phenology-type-blind.**
The live daily path is `turnover_daily_tree.c:42-76`, which branches on `config->individual` **first**;
its own source comment states the intent — *"LPJmL-FIT turnover (now every PFT can shed leaves (due to
dryness, heat, cold etc.)"*. Every tree PFT can therefore take either branch, and which one it takes
is a function of its own leaf-display trajectory, not of its identity:

| branch | condition | annual leaf turnover |
|---|---|---|
| **latched** | `isphen` TRUE at the annual call (`turnover_tree.c:100`) | `turn.leaf = leaf_c / 1.05` (sheds 95.24 %) |
| **drip** | else | the daily accumulation, `leaf_c · turnover_leaf / NDAYYEAR` per day (`:63-65`) |

`isphen` latches TRUE when `phen < 0.25 && aphen > aphen_min && !isphen` (`:47`), un-latches when
`phen > 0.25 && isphen && aphen > aphen_min` (`:44`), and is reset FALSE on the coldest day
(`phenology_gsi.c:88-97`; day 14 N / 195 S). While latched, **no daily drip accumulates at all** — the
`else if(!tree->isphen)` at `:63` is skipped.

**4. THE FINDING — the two branches are the SAME NUMBER wherever leaf longevity ≤ 1.05 yr, and that
covers the cell the suspect was aimed at.** In individual mode the drip rate is
`turnover_leaf = 1.0 / max(pft->longevity, 1.05)` (`turnover_daily_tree.c:38`). The `max` **clamps the
drip rate at 0.9524/yr, which is exactly the latched branch's rate.** So for any stem whose leaf
longevity is at or below 1.05 yr, the latch is a no-op: both branches shed 95.24 % of the leaf pool and
F's unconditional recycle is *exactly correct*, however often the latch fires.

Measured per stem from the C's own `ind` table (`scripts/diagnose_leaf_turnover_regime.py`, historic
seed1, `Type <= 6 & D95max > 0`, 23 375 tree stem-years over the five coupled cells), as the leaf
fraction **retained** into allocation:

| cell | dominant PFTs | frac. stems with `Longevity > 1.05` | stem-weighted `excess_shed` | verdict |
|---|---|---|---|---|
| `boreal_siberia` | id 6 larch 82 %, id 5 18 % | **0.000 / 0.000** (id 4: 1.000, but 42 of 5 342) | **0.0031** | **CANNOT BIND** |
| `semiarid_sahel` | id 0, 100 % | **0.008** | **0.0018** | **CANNOT BIND** |
| `temperate_hainich` | id 3 beech 96 % | 0.013 (beech) | 0.0142 | marginal |
| `tropical_amazon` | id 0, 100 % | **0.671** | **0.1240** | **CAN BIND** |
| `mediterranean_iberia` | id 1 45 %, id 2 53 % | **0.905 / 0.853** | **0.2475** | **CAN BIND** |

`excess_shed` = the leaf fraction F sheds that the C would have **kept** in a non-latched year. At
`boreal_siberia` it is **0.3 %** of the leaf pool — and it is 0.3 % rather than 0 only because of 42
stem-years of id 4 out of 5 342. **The suspect is refuted at its own target cell, and refuted
mechanically rather than statistically: no simulation and no latch-incidence measurement can revive
it, because the two branches evaluate to the same number there.**

**5. It is relocated to `mediterranean_iberia` (24.8 % of the leaf pool) and `tropical_amazon`
(12.4 %)** — which are, respectively, the cell whose assimilate ratio is 2.7–3.1× (excluded from ADR
0131/0133's headline mean for exactly that reason) and the cell whose tree carbon balance F still gets
**negative** (ADR 0125/0131). Both are ~100 % evergreen-*named* PFTs with genuinely long leaves. This
is a real, localised, quantified gap that nothing on the F queue currently aims at.

**6. ⚠ NEW DURABLE FACT — leaf longevity is a PER-INDIVIDUAL trait drawn from the stem's own SLA, and
it is NOT the per-PFT residence time F carries.** `new_tree.c:215` (inside the `config->individual`
branch) sets

```c
pft->longevity = corr_corridor(pft->sla, pft->par->longevity.interc,
                               pft->par->longevity.slope, pft->par->longevity.sigma, seed);
```

which is why `par/pft_lpjmlfit.js` declares `longevity` as `{mean, interc, slope, sigma}` rather than a
scalar. It is emitted per stem as the `ind` column **`Longevity`**, and it is genuinely sampled: 116–668
distinct values per (cell, PFT), spreads 1.12–6.80×, with the leaf-economics corridor visible as
`r(SLA, Longevity)` = **−0.66 to −0.98** within (cell, PFT) at 12 of 13 groups (the 13th is 42 stems).

Two traps follow, both live:

- **`longevity.mean` is NOT the realized central value.** The par file says 2.0 yr for all six
  non-tropical trees; the realized median at `boreal_siberia` is **0.286** (id 6) and **0.305** (id 5)
  — 7× lower — because the corridor maps the realized SLA distribution, not the `mean` field. Same
  shape as ADR 0047's finding that an interval's `"median"` can lie outside `[low, high]`.
- **F's `AllocParams.turnover_leaf` is a different quantity and would be wrong if ever wired in.** It
  carries the per-PFT `turnover.leaf` residence (1, 2 or 4 yr; ADR 0126), which the C **does not
  consult for trees in individual mode**. Substituting it into the drip branch would retain 0.75 where
  the truth is 0.4389 (`boreal_siberia` id 4) and 0.50 where the truth is 0.1717 (`tropical_amazon`).
  The `F_wrong_par` column of the probe prints this side by side so the substitution can never be
  silent (ADR 0060's rule). **There is no active defect today** — F's tree path never reads
  `turnover_leaf`, because `is_deciduous` is always `true` — so this is a latent trap, recorded before
  it is stepped in.

**7. Two claims are corrected in place, in the same commit as this record.** Both stated the right
conclusion for a reason that does not hold:

- `src/fdiff.jl`'s `pft_allocparams` docstring said *"Every tree PFT in this configuration is
  `summergreen` under `new_phenology`, so `is_deciduous` stays `true` for all"*. The `summergreen`
  declaration is real (item 2) but it is **not** what makes the default safe, because the key is never
  read (item 1). The load-bearing reason is item 4's clamp.
- `scripts/build_pft_fdiff_params_reference.py` asserted `phenology == "summergreen"` for ids 0–6 with
  the message *"a tree PFT is no longer summergreen — `AllocParams.is_deciduous` becomes per-PFT"*.
  That assertion guards an **inert** key: it can only fail on an edit that changes nothing, and it
  would stay green through the edit that *does* matter. Replaced with an assertion on the quantity the
  C actually consumes — the per-PFT `longevity.mean` and the `1.05` clamp — plus a comment naming this
  record. This is `residual-diagnosis` §3e ("ask whether that assertion CAN fail") on our own gate.

## Consequences

- **`boreal_siberia`'s allocation gap is still open, and its remaining named suspect is now the
  `reprod_cost` path.** ADR 0132 §5 already retired the below-ground wood port as its answer (it
  closed 97 % of a bar its own measurement said was 89 % something else); this record retires the leaf
  recycle. Do not re-propose either at that cell.
- **What would close the relocated gap, and what is deliberately NOT claimed here.** The 0.2475 /
  0.1240 figures are an **upper bound**: they are what F over-sheds *in a year the latch does not
  fire*, and the latch's incidence at those two cells is **not measured**. Per
  `residual-diagnosis` ADR 0105's rule, this record therefore publishes **no recommended default and
  no parameter**. The measurement that would close it is a latch-incidence probe:
  `per_pft_phenology(pft_ids, forcings; water_avails = <the rollout's own lag-1 wscal>)` reproduces the
  daily leaf-display trajectory F already runs, so the latch is a pure post-process on it — report the
  fraction of (patch, year) with `isphen` TRUE at day 365, per cell × PFT, with the activation count
  printed next to it (`residual-diagnosis` trap 3: a zero count bounds nothing).
- **If the incidence is high at those cells the gap shrinks toward zero and this becomes a closed
  question; if it is low, the fix is a state machine, not a parameter** — an opt-in `isphen` latch on
  F's own `phen`, with the drip branch reading each stem's **`Longevity`** (a new per-stem field, from
  the `ind` column) and *not* `AllocParams.turnover_leaf`. Note the per-PFT `aphen_min` trap: larch
  (id 6) declares `aphen_min` **twice** in `par/pft_lpjmlfit.js` (`:1001-1004`, the macro default 60
  then an override **10**), and json-c's last-wins means larch's effective threshold is 10 (ADR 0047).
- **The `Longevity` column is a fifth measurable recruit-trait axis, which is line S's interest.** It
  is sampled, SLA-coupled, and emitted per stem. ADR 0117 §5 recorded the recruit interface as complete
  on four axes with `k_root` proven an identity; `Longevity` is neither a constant nor currently
  consumed by F, so it is not a defect — but it is a real axis, and if the leaf-turnover branch above
  is ever built, it becomes a quantity the slow emulator would have to carry for recruits. Raised in
  `lines/S/STATE.md` as information, not as a request.
- **Method lesson, for the skill.** A suspect can be refuted by an **algebraic identity in the
  reference** rather than by a measurement of the model: the `max(longevity, 1.05)` clamp makes two
  branches coincide over most of the realized parameter range, so the branch that "is missing" was
  never distinguishable. Before building an operator to reproduce a reference's *branch*, evaluate both
  of the reference's branches on the reference's own realized inputs and check they actually differ —
  it cost one parquet scan here and it retired an item that had survived two handoffs.

## Artifacts

- `scripts/diagnose_leaf_turnover_regime.py` — the three-panel audit (variability first per ADR 0117;
  retained-fraction with the decisive `frac_gt` column and a per-cell CANNOT BIND / CAN BIND verdict;
  the SLA corridor). Seconds to run; reads the committed cell registry and the global `ind` parquet.
- Corrected: `src/fdiff.jl` (`pft_allocparams` docstring),
  `scripts/build_pft_fdiff_params_reference.py` (the inert assertion).
