### Added

- **A LEVEL ANCHOR for the coupled stand — opt-in, default-off, and it closes a 41 % over-density nothing
  in this project could see ([ADR 0103](docs/decisions/0103-the-level-anchor-ships-the-conversion-was-a-constant.md)).**
  `FluxDrivenSlowEmulator(...; anchor = a, patch_area = 225.0)`. ADR 0102 measured that the coupled stand has
  no level anchor — it is advanced by a pure ratio, `D_T = D_0·Πρ_t`, so the count DRF's *absolute* skill
  never reaches it — and then **deferred the fix on a false premise** (see below). It is now built:
  - **Mechanism.** A **geometric** blend of the AR ratio and the ratio that lands the stand on the DRF's
    absolute target: `ρ_eff = (target/n_prev)^(1−a)·(D_want/D)^a` with `D_want = target/patch_area`, clamped
    by `max_mort`/`max_estab` exactly as before. Geometric rather than arithmetic keeps the update
    multiplicative and strictly positive, so the carbon routing is untouched and `a` is a **relaxation rate**
    (time constant ≈ `1/a` years) rather than a mixing weight.
  - **`anchor = 0` does not evaluate the branch** ⇒ every committed baseline, ReferenceTest and AD gate is
    byte-identical. This is the ADR-0049 opt-in pattern reused unchanged, and it is *measured*, not asserted:
    the new testitem compares the full density trajectory with `==`, not `isapprox`.
  - **Measured** (job 1707102, Hainich, 150 yr, the same 4× initial-density sweep as ADR 0102 §3):

    | `anchor` | retention | terminal spread | stand ÷ its own count target |
    |---|---|---|---|
    | 0.00 | 1.0364 | 4.207× | **1.409** |
    | 0.10 | **0.0513** | 1.074× | **1.000** |
    | 0.25 | 0.0491 | 1.071× | 1.000 |
    | 0.50 | 0.0513 | 1.074× | 1.000 |
    | 1.00 | 0.0762 | 1.111× | 1.000 |

    The initialisation is forgotten (retention ÷20) **and** a previously invisible level error is closed: the
    unanchored stand settles **1.409× denser than its own count model's absolute prediction**. Every existing
    gate — the ADR-0030 per-cell trait gate, the count R², the trained-band check — reads ratios,
    distributions or correlations, so **none of them can see an absolute-level error**.
  - **Recommendation for line M: `anchor = 0.1`** — 0.1–0.5 are equivalent and `a = 1` is measurably *worse*
    (retention 0.076), because a hard anchor overwrites the stand's own dynamics each year so a perturbation
    is re-imposed through the clamp and the recruit branch instead of relaxing away. This is the measured
    value the owner's standing pre-authorisation of M's baseline regeneration was waiting on.
  - **`patch_area` travels with the ARTIFACT, not the cell.** 225 m² is `param.patcharea` of the training
    runs — a global constant in this configuration, so no `cell_meta.parquet` column — but stock LPJmL-FIT
    uses **100.0**, so an artifact built from a different `patcharea` run must pass its own value or the
    anchor pulls the stand to a level wrong by the ratio of the two areas. Inert when `anchor == 0`.
- `test/testitems/slow_level_anchor_tests.jl` — pins byte-identity at `a = 0` (with `==`), that `a > 0`
  actually anchors (so the test cannot pass on a no-op — the ADR-0048 never-fired-null failure mode), that
  retention drops, that `patch_area` is load-bearing when on and inert when off, carbon closure, determinism,
  and the `[0,1]` kwarg validation in both directions.

### Fixed

- **ADR 0102 §4's central claim was wrong, and the correction matters more than the fix.** It stated the
  anchor "requires the count↔density conversion at the S↔F seam — an `interface.jl` addition, which is line
  M's", and on that basis deferred a one-file change into a cross-line integration point. **The conversion is
  a documented constant:** `par/lpjparam_fit.js:17` sets `"patcharea": 225.0` m² (15×15) and
  `src/tree/new_tree.c:209` gives every individual `nind = 1/patcharea`. **The project owner caught it.**
  Verified rather than taken on trust, per CLAUDE.md §3: `cpp -P` over the *live* config yields exactly one
  `"patcharea"` (225.0, no duplicate-key override — the trap that makes larch's `aphen_min` 10 instead of
  60), and the committed fixture agrees end-to-end (`sum(nind) × 225 = 17.000`, every individual at `1/225`).
  Two transferable lessons:
  - **"X cancels" is a statement about an expression, not about X.** CLAUDE.md's own sentence — "with
    `nind = 1/patcharea` the patcharea cancels" — is true of the ADR-0035 per-patch LAI derivation and was
    read as a general property of the quantity. The follow-up question, *cancels against what?*, was never
    asked.
  - **Before routing work to another line, confirm the thing you need is actually theirs.** ADR 0029 stops
    lines editing each other's files; it does not make a constant from a third repository into another line's
    property. Deferring a one-file change to a negotiation is a real cost.
