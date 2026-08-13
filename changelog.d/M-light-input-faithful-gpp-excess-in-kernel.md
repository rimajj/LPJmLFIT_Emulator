### Added

- **Scoping the photosynthesis half of the assimilate error: the light INPUT to the fast core's tree
  photosynthesis is faithful to the live C, so the GPP excess is in the kernel
  ([ADR 0135](docs/decisions/0135-the-light-input-to-tree-photosynthesis-is-faithful-so-the-gpp-excess-is-in-the-kernel.md)).**
  New 2-second, simulation-free audit `scripts/diagnose_layered_light_basis.py` checks every factor of
  `apar = par·(1−albedo_leaf)·alphaa·fpar` against the LIVE lines of LPJmL-FIT: `par` (`petpar3.c:74`),
  `alphaa`, `albedo_leaf`, the vertical layered Beer–Lambert light model (`getfpar.c`), its leaf-area
  density and `atoh>40` cap, `k_lambert`=0.5, `VSTEP`, crown geometry, and the SLA Vcmax cap (per stem,
  `issla = config->individual` ⇒ ON) — **all match**. The port's basis is additionally scored against a
  quantity the C *emits* rather than against its source: patch LAI reproduces the run's own `LAI_STAND` at
  **0.878 / 0.869 / 0.981 / 0.907** at boreal / Hainich / mediterranean / Sahel, below 1 by exactly the `ind`
  writer's 5 m cut (`tropical_amazon` 0.574 is printed as `CHECK`, not smoothed). **Two live differences
  remain and both make the fast core absorb LESS PAR than the C, while its tree GPP is measured 1.074× ABOVE
  the C's — so neither explains the excess and the kernel-side error is larger than the measured ratio:**
  phenology is applied after the layered share instead of inside the extinction (per-DAY upper bound 15.0 %,
  38.9 %, 19.5 %, 15.0 %, 47.5 % of the core's own absorption at `phen≈0.45`; the annual weight of such days
  is **not** measured, and no default or parameter may be published from a bound), and there is no
  `(1−snowcover)` factor at all (not priceable from the `ind` table — listed, not measured). ⚠ **A first pass
  of this audit produced a 5–37× optical-thickness "defect" that does not exist:** `getfpar.c:108-124` holds
  three expressions for one quantity and both `grep` and a `sed` range land inside its `/* test: */` comment
  blocks. Recorded as a durable trap in `CLAUDE.md` §3 and as `residual-diagnosis` §10 — a commented-out
  branch is a dead path that no config check and no `grep` output distinguishes from live code. The only
  source change is a corrected comment in `src/fdiff.jl`, which had justified the layered-light port with
  ≈0.83 as "the true layered fraction" when 0.83 is the emulator's own absorption and the C output named
  beside it (`d_fapar`) is built from a different variable and cannot validate it. No behaviour change, no
  flag, no default. Remaining shortlist for the photosynthesis half, with the C line that scopes each: the λ
  solve's Vcmax basis, the `tstress<1e-2` hard zeroing, and the phenology trajectory itself.
