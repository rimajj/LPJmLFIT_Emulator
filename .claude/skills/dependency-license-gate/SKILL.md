---
name: dependency-license-gate
description: Verify a third-party work's LICENCE before depending on it, reading it, or copying from it — the mandatory gate from ADR 0080 for this AGPL-3.0-or-later repo. Covers how to resolve a Julia package to its real upstream repo from the General registry TARBALL, how to read a LICENSE when GitHub HTTPS is blocked from the cluster, why you must also look for a NOTICE (Terrarium's is what unblocked P4), and the AGPL-compatibility decision table (EUPL-1.2 ✅ via the Appendix / CC-BY-NC ❌ / unlicensed ❌ / LGPL-2.1-only depend-only). Use whenever adding a dep or weakdep, requesting one from the integrator, cloning or reading a new reference repo, porting/copying code from one, or answering "can we use X here?" — and whenever tempted to state a package's licence from memory (SpeedyWeather.jl is EUPL-1.2, NOT MIT).
---

# dependency-license-gate — check the licence before you take the dependency

**The rule (ADR 0080):** this repo's outbound licence is **AGPL-3.0-or-later** (forced — LPJmL-FIT's
copyleft *and* the EUPL-1.2 Appendix both point there). Three tiers, never conflated:

| Tier | Act | Rule |
|---|---|---|
| **READ** | Study, then write our own | OK for every reference. Methods aren't copyrightable; a line-by-line translation is not "reading". |
| **DEPEND** | `[weakdeps]` + extension | The P4 mechanism. Runtime `[deps]` stays EMPTY (ADR 0014). `Project.toml` is **integrator-only** — request it. |
| **VENDOR** | Copy source into our tree | **Not permitted by default — needs its own ADR.** |

**The register + the full checklist live in [`docs/third_party_licensing.md`](../../../docs/third_party_licensing.md).**
Run it, then add your row there. This skill exists because steps 1–3 are non-obvious *on this cluster*.

## 1. Resolve the package to its real upstream

A Julia package name is not a repo. On this cluster the General registry is a **tarball**, and its paths have
**no `./` prefix** (`tar xzf ... ./S/Foo/...` fails):

```bash
mkdir -p /tmp/regx
tar xzf ~/.julia/registries/General.tar.gz -C /tmp/regx <FirstLetter>/<Package>/Package.toml
grep repo /tmp/regx/<FirstLetter>/<Package>/Package.toml
```

**Expect monorepos.** `RingGrids` and `SpeedyWeatherInternals` both resolve to
`SpeedyWeather/SpeedyWeather.jl.git` — subpackages sharing one LICENSE. Guessing `RingGrids.jl` gets a 404
that proves nothing. If the package is newer than the registry snapshot, fetch
`https://raw.githubusercontent.com/JuliaRegistries/General/master/<L>/<Pkg>/Package.toml` instead.

## 2. Read the licence from upstream — never from memory

GitHub HTTPS is **blocked from the cluster** (`CLAUDE.md` §1), so use the harness (WebFetch), not `curl`:

- `https://raw.githubusercontent.com/<org>/<repo>/main/LICENSE` (try `master` on 404)
- `https://api.github.com/repos/<org>/<repo>` → `license.spdx_id`, and `private`

⚠️ The API's `license` is `null` both for **unlicensed** repos and for licences it **can't classify** — if
null, fetch the file before concluding anything. Also check the *local clone* first when one exists under
`/p/tmp/jamirp/esm_reference_repos/` — that's authoritative for the commit we actually read.

**Do not state a licence from memory.** SpeedyWeather.jl is **EUPL-1.2, not MIT** — the plausible-sounding
wrong answer that a whole ADR would have rested on.

## 3. Look for a `NOTICE` too — it changes the licence's reach

The file everyone skips, and the one that decided P4: Terrarium.jl's `NOTICE` extends **EUPL Article 5 to
*any* licence** for "derivative works produced by the normal use of the Work as a library" — i.e. a linking
exception that removes copyleft reach for the DEPEND tier. SpeedyWeather.jl has **no** `NOTICE` (404). A 404
is a finding: record it.

## 4. Walk the transitive tree

Read the upstream `Project.toml`'s `[deps]` and repeat 1–2 for anything unfamiliar — this is how
FreezeCurves.jl's **LGPL-2.1** (a Terrarium dep) surfaced.

## 5. Decide against AGPL-3.0-or-later outbound

| Inbound | Verdict |
|---|---|
| MIT / BSD / Apache-2.0 | ✅ retain the notice |
| **EUPL-1.2** | ✅ — AGPL-3.0 **is** in the EUPL Appendix, so Art. 5's compatibility clause covers it |
| GPL-3 / AGPL-3 / LGPL-3 / MPL-2 | ✅ |
| **CC BY-NC / any NonCommercial or ND term** | ❌ **STOP** — AGPL §7 forbids added restrictions ⇒ undistributable. Method-only (NeuralCrop.jl). |
| **No licence at all** | ❌ **STOP** — all rights reserved, public visibility is irrelevant. Method-only, from the paper (LPJ_resilience). |
| LGPL-2.1-only | ⚠️ depend, never vendor |

## 6. Record it

Add the row to `docs/third_party_licensing.md` (licence, tier, **how verified**, obligation), the attribution
to `CITATION.cff`, and — if code or constants derive from it — the source-file header.

**State provenance accurately.** Calling an independent implementation a "**port**" of a CC-BY-NC work is
itself the legal exposure, even when no code was copied (ADR 0080 §3 — resolved by diffing the two
implementations and rewording). If you write "ported from X", be sure it was.
