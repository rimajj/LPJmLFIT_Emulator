# Reuse + citation register

**The licensing question is CLOSED** — [ADR 0081](decisions/0081-owner-closes-licensing-reuse-authorized.md)
(owner decision, 2026-07-28). The owner is a member of **both** the **LPJmL-FIT** group and **TUM-PIK-ESM**,
which hosts SpeedyWeather.jl, Terrarium.jl and LPJmL-hybrid-photosynthesis, so **reuse those models freely**.
Do not raise licensing, ask for a licence decision, or re-audit upstream licences. The reasoning and the
verified upstream facts are preserved once and for all in [ADR 0080](decisions/0080-licensing-basis.md).

**The one standing obligation is TRANSPARENT CITATION.** This file is the register that makes it checkable.

## The four citation surfaces — keep them in agreement

Every reused model appears in **all four**, saying the same thing:

| Surface | What goes there |
|---|---|
| **This register** | one row per reused work: what it is, what we take from it, where it is used |
| **`CITATION.cff`** `references:` | the citable software/paper entry |
| **`docs/src/refs.bib`** | the BibTeX entry, cited inline in the docs as `[key](@cite)` |
| **Source-file header** | in *every* file with derived content — name the upstream and what came from it |

**State provenance accurately** — neither overstated nor omitted. "Ported from X" must mean ported; an
independent implementation of a published method must say so. ADR 0080 §3 is the worked example: a trainer
described as "the finished port of NeuralCrop.jl's `train_loop_rollout!`" turned out, on direct comparison, to
share no expression with it at all, and the wording was the defect.

## Register

| Work | What it is | What we reuse | Cited in |
|---|---|---|---|
| **LPJmL-FIT v5.6.004** (`/home/jamirp/lpjml56fit`, © 2007–2025 PIK) | The model this component is derived from; the C binary is our numerical-regression **oracle** and daily data generator | The physics: photosynthesis→GPP→NPP, the λ solve, PET/ET, soil water/snow, respiration, allometry, mortality, establishment. Parameter values are the C-source values | `src/{fdiff,allometry,state,climbuf}.jl`, `src/components/{fast,slow}.jl` headers · `CITATION.cff` · `refs.bib` |
| **Terrarium.jl** (NumericalEarth / TUM-PIK-ESM) @ `4f42508`, v0.1.3 | Differentiable land-surface substrate; the **P4 coupling substrate** | Its `Abstract*` process interfaces and the `speedy_{dry,wet}_land.jl` coupling pattern — S/F/E sit *behind* its interfaces | (P4, pending) `ext/` header · `CITATION.cff` · `refs.bib` |
| **SpeedyWeather.jl** (incl. `RingGrids`, `SpeedyWeatherInternals` — same monorepo) | The atmosphere for the **online** coupled run | `SpectralGrid` / `RingGrids` / `LandModel` wiring; `PrescribedLand{Heat,Humidity}Flux` for H/LE injection | (P4, pending) `ext/` header · `CITATION.cff` · `refs.bib` |
| **LPJmL-hybrid-photosynthesis** (TUM-PIK-ESM, Philipp Hess) | Differentiable LPJmL photosynthesis | The differentiable λ (ci:ca) root-find pattern and the C3/C4 coupled kernel (ADR 0015) | `src/fdiff.jl` header · `CITATION.cff` · `refs.bib` |
| **NeuralCrop.jl** (Yunan Lin, arXiv:2512.20177) | Differentiable Julia LPJmL for **crops** | ⚠️ **METHOD ONLY — no code.** CC-BY-NC, a different author outside both groups, so the owner's memberships do not cover it. Cite the paper; implement from it | `src/fdiff.jl`, `ext/FDiffTrainingExt.jl` headers (as prior art) · `CITATION.cff` · `refs.bib` |
| **LPJ_resilience** (TUM-PIK-ESM; Bathiany et al. 2024, GCB 30(12):e17613) | Resilience-indicator battery for LPJmL | ⚠️ **Method from the paper** (no licence upstream). The AC-vs-climate / recovery-rate / shuffle-test metrics | (resilience battery, pending — line M) · `refs.bib` |
| **json-c 0.13.1** | JSON library the C binary links against | A reconstructed `json_object_iterator.h` compat shim (the cluster's 0.13.1 headers are truncated) | `patches/json_object_iterator.h.shim` header (MIT notice reproduced) |

Terrarium's own dependency tree (Oceananigans, Thermodynamics.jl, FreezeCurves.jl, …) arrives transitively via
`Pkg` when the extension is activated; we ship none of it and cite Terrarium as the unit.

## Copying source into this tree still deserves an ADR

Not a licensing rule — a **maintenance** one. A vendored copy silently drifts from upstream and nobody
notices. So if you copy third-party source into the repo (rather than depending on the package or
reimplementing the method), write a short ADR naming the file, the upstream commit, and the header added.
Current vendored artifacts, both fine:

- `patches/lpjmlfit_daily_grass_gpp.patch` — our `D_GRASS_GPP`/`D_GRASS_NPP` addition, as a diff against
  LPJmL-FIT `include/conf.h` + `par/outputvars.js`.
- `patches/json_object_iterator.h.shim` — verbatim json-c declarations, MIT notice reproduced in the header.

## Adding a new reused work

1. If it is from **LPJmL-FIT or TUM-PIK-ESM** → just use it. Add the row here, then the other three surfaces.
2. If it is from **anywhere else** → check for a NonCommercial / no-derivatives term or a missing licence,
   because those two cases mean **method-only, no code** (NeuralCrop.jl and LPJ_resilience are the precedents).
   That is the whole check; nothing more elaborate is wanted.
3. Runtime `[deps]` stays **empty** (ADR 0014) — a new package is `[weakdeps]` + an extension, requested from
   the integrator. This is technical (compute nodes have no GitHub egress), not legal.
4. Finding the real upstream repo of a Julia package is fiddly on this cluster — the `reuse-citation` skill
   has the mechanics (the General registry is a tarball; `RingGrids` and `SpeedyWeatherInternals` both resolve
   to the SpeedyWeather monorepo).
