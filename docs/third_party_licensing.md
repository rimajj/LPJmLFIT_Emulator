# Third-party licensing register

The operational companion to **[ADR 0080](decisions/0080-licensing-basis.md)** (the licensing basis). ADR 0080
holds the *reasoning* and is immutable; this file holds the *inventory* and is kept current.

Two things live here:

1. **The register** — every inbound work, its licence, how that licence was verified, which of the three
   tiers we use it at, and the obligation it puts on us.
2. **The gate** — the checklist to run *before* taking a new dependency or reading a new reference. ADR 0080
   makes it mandatory. The `dependency-license-gate` skill drives it.

**Outbound licence of this repository: AGPL-3.0-or-later** — forced by LPJmL-FIT's AGPL-3.0 copyleft and by
EUPL-1.2 Art. 5's Appendix (ADR 0080 §1). ⚠️ **The `LICENSE` file has not been filed yet** and the repo is
public; that is the named owner action in ADR 0080 §4.

## The three tiers (ADR 0080 §2)

| Tier | Act | Rule |
|---|---|---|
| **READ** | Study a reference implementation, then write our own | Permitted for every work below. Copyright covers *expression*, not methods (EU Directive 2009/24/EC Art. 1(2); CJEU C-406/10). A literal line-by-line translation is **not** reading. |
| **DEPEND** | `[weakdeps]` + a package extension; no upstream bytes in our tree | The P4 mechanism. Runtime `[deps]` stays EMPTY (ADR 0014). Adding an entry to `Project.toml` is an **integrator** action. |
| **VENDOR** | Copy upstream source into our tree | **Not permitted by default.** Needs its own ADR naming the file, the upstream commit, the licence header added, and an entry in §Vendored below. |

## Register

All licences verified **2026-07-28** unless noted. "How verified" matters because compute nodes have no
GitHub egress — the check must be re-runnable from the login node or the harness, never from a job.

| Work | Licence | Tier used | How verified | Obligation on us |
|---|---|---|---|---|
| **LPJmL-FIT v5.6.004** (`/home/jamirp/lpjml56fit`) | **AGPL-3.0-or-later** (© 2007–2025 PIK) | READ (literal porting permitted) + VENDOR (one patch) | local `LICENSE` (GNU AGPL v3) + `AUTHORS`; **the version scope is in `COPYRIGHT`** — "either version 3 …, or (at your option) any later version" — *not* in `LICENSE`, and the source headers say only "Version 3" | Outbound must be AGPL-3.0-or-later; retain notices; state modifications; provide source; §13 network clause |
| **Terrarium.jl** (NumericalEarth) @ `4f42508` | **EUPL-1.2** + a `NOTICE` extending Art. 5 to **any licence** for normal library use | DEPEND (planned, P4) | local `LICENSE` + `NOTICE`; GitHub API `spdx_id: EUPL-1.2` | Keep notices intact; attribute. The `NOTICE` removes copyleft reach for library use — **read it before relying on Art. 5 alone** |
| **SpeedyWeather.jl** | **EUPL-1.2**, **no `NOTICE`** | DEPEND (planned, P4) | raw `LICENSE` on `main`; `NOTICE` → HTTP 404 | Plain EUPL-1.2. Covered by Art. 5 because our outbound (AGPL-3.0) is an Appendix Compatible Licence |
| ↳ **RingGrids**, **SpeedyWeatherInternals** | EUPL-1.2 (same monorepo) | DEPEND (transitive) | General-registry `repo` field → `SpeedyWeather/SpeedyWeather.jl.git` for both | As SpeedyWeather.jl |
| **LPJmL-hybrid-photosynthesis** (TUM-PIK-ESM) | **MIT** (© 2022 Philipp Hess) | READ (done — differentiable λ, C3/C4 kernel; ADR 0015) | local `LICENSE` | Retain the MIT notice where code/constants derive from it (source headers + `CITATION.cff`) |
| **NeuralCrop.jl** (Yunan Lin) @ `dff3fc8` | **CC BY-NC 4.0** | **READ — method only, never a line of code** | local `LICENSE` | NonCommercial is irreconcilable with AGPL-3.0 §7 (ADR 0080 §3). Cite the paper (arXiv:2512.20177); copy nothing |
| **LPJ_resilience** (TUM-PIK-ESM) | **none** — all rights reserved | **READ — from the paper only** | GitHub API `license: null`, `private: false` | No permission to copy/modify/redistribute. Implement the published metrics (Bathiany et al. 2024, GCB 30(12):e17613) |
| **json-c 0.13.1** | **MIT** (© 2009–2012 Eric Haszlakiewicz; © 2004–2005 Metaparadigm Pte Ltd) | VENDOR (one header shim) | raw `COPYING` | MIT copyright + permission notice must accompany the shim — now reproduced in it, see §Vendored |
| Oceananigans (Terrarium dep) | MIT (© CliMA) | DEPEND (transitive) | raw `LICENSE` | Notice only; never distributed by us |
| Thermodynamics.jl (Terrarium dep) | Apache-2.0 | DEPEND (transitive) | raw `LICENSE` | Notice + `NOTICE`-file handling only if ever vendored |
| FreezeCurves.jl (Terrarium dep) | **LGPL-2.1** | DEPEND (transitive) | raw `LICENSE` | The one node whose strict-2.1-only reading is GPL-3-incompatible. Non-issue while we never distribute it; **re-check first if the vendoring posture changes** |

Runtime `[deps]` is currently **empty** (ADR 0014); the only declared `[weakdeps]` are Enzyme, Lux,
Optimisers and Zygote — all MIT, train/test-time only, and not distributed by us.

## Vendored artifacts (Tier 3 — the complete inventory)

| File | Upstream | Licence | Status |
|---|---|---|---|
| `patches/lpjmlfit_daily_grass_gpp.patch` | LPJmL-FIT `include/conf.h`, `par/outputvars.js` | AGPL-3.0 | Contains **verbatim context lines** from AGPL source. Compliant once the repo's `LICENSE` is AGPL-3.0-or-later (ADR 0080 §4.1) |
| `patches/json_object_iterator.h.shim` | json-c `json_object_iterator.h` | MIT | ✅ Compliant. Contains verbatim declarations, and now reproduces json-c's MIT copyright + permission notice in its header (was missing; fixed with ADR 0080) |

Nothing else in the tree is vendored: `git ls-files | grep -iE '\.(c|h|js|patch)$'` returns only
`patches/`, and no `.md` under `docs/` quotes C source in a fenced block.

## The gate — before taking a dependency or reading a new reference

Run this **before** writing code against a new package or reference repo, and record the outcome as a row
above. Steps 1–3 are the non-obvious part on this cluster.

1. **Find the real upstream.** A Julia package name is not a repo. Resolve it from the General registry —
   which is a *tarball* on this cluster, and its paths have no `./` prefix:
   ```bash
   mkdir -p /tmp/regx
   tar xzf ~/.julia/registries/General.tar.gz -C /tmp/regx <FirstLetter>/<Package>/Package.toml
   grep repo /tmp/regx/<FirstLetter>/<Package>/Package.toml
   ```
   Expect surprises: `RingGrids` and `SpeedyWeatherInternals` both resolve to
   `SpeedyWeather/SpeedyWeather.jl.git` — **subpackages of one monorepo**, sharing its licence. Checking a
   `RingGrids.jl` repo that does not exist returns 404 and proves nothing.
2. **Read the licence from upstream, don't recall it.** GitHub HTTPS is blocked from the cluster
   (`CLAUDE.md` §1), so fetch it harness-side rather than with `curl`:
   `https://raw.githubusercontent.com/<org>/<repo>/<main|master>/LICENSE`, or the GitHub API
   (`https://api.github.com/repos/<org>/<repo>` → `license.spdx_id`, plus `private`). The API's `license`
   field is `null` both for unlicensed repos **and** for licences it cannot classify — if it is null, fetch
   the file. Try `master` when `main` 404s.
3. **Always look for a `NOTICE` too.** It can *change* the licence's reach in either direction, and it is the
   file people skip. Terrarium's `NOTICE` is what unblocked P4; SpeedyWeather has none. A 404 is a finding —
   record it.
4. **Check the transitive tree** for copyleft or NonCommercial nodes: read the upstream `Project.toml`'s
   `[deps]` and repeat steps 1–2 for anything unfamiliar. (This is how FreezeCurves' LGPL-2.1 surfaced.)
5. **Classify the tier** and apply ADR 0080 §2. If the answer is VENDOR, stop and write an ADR.
6. **Check compatibility against AGPL-3.0-or-later outbound**, in this order:
   - MIT / BSD / Apache-2.0 → inbound-compatible, retain the notice. ✅
   - EUPL-1.2 → compatible **because AGPL-3.0 is in the EUPL Appendix** (Art. 5). ✅
   - GPL-3 / AGPL-3 / LGPL-3 / MPL-2 → compatible. ✅
   - **CC BY-NC, CC ND, or any NonCommercial/no-derivatives term → STOP.** AGPL-3.0 §7 forbids added
     restrictions; a combined work is undistributable. Method-only. ❌
   - **No licence at all → STOP.** All rights reserved. Method-only, from the paper. ❌
   - LGPL-2.1-only → fine to depend on, **never** vendor. ⚠️
7. **Record the row** in the register above with the verification method, and add the attribution to
   `CITATION.cff` (and the source-file header, if code or constants derive from it — ADR 0015).

## Attribution surfaces

Attribution is carried in four places and all four must agree: the **source-file header** of any file with
derived content, **`CITATION.cff`** `references:`, the **docs bibliography** (`docs/src/refs.bib`, cited
inline as `[key](@cite)`), and this register. A provenance claim that overstates what was copied is itself a
risk — see ADR 0080 §3, where "the finished port of NeuralCrop.jl's `train_loop_rollout!`" was corrected to
an accurate description after a direct comparison showed no shared expression.
