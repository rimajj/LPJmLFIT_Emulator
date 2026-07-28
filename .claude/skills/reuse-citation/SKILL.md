---
name: reuse-citation
description: Cite a reused model/repo correctly across this repo's four citation surfaces (the docs/third_party_licensing.md register, CITATION.cff, docs/src/refs.bib, and the source-file header), and state provenance ACCURATELY — "ported from X" must mean ported, while an independent implementation of a published method must say so. Also holds the mechanics for finding a Julia package's real upstream repo from this cluster (the General registry is a tarball; RingGrids/SpeedyWeatherInternals both resolve to the SpeedyWeather monorepo). Use whenever reusing or newly depending on Terrarium.jl / SpeedyWeather.jl / LPJmL-FIT / LPJmL-hybrid-photosynthesis, adding a weakdep, porting equations from a reference repo, or writing a source header that names an upstream. LICENSING IS CLOSED (ADR 0081 — the owner is a member of both the LPJmL-FIT and TUM-PIK-ESM groups): reuse those models freely and do NOT raise licence questions or re-audit upstream licences.
---

# reuse-citation — reuse freely, cite transparently

**Licensing is CLOSED — [ADR 0081](../../../docs/decisions/0081-owner-closes-licensing-reuse-authorized.md)**
(owner decision, 2026-07-28). The owner is a member of **both** the **LPJmL-FIT** group and **TUM-PIK-ESM**
(which hosts SpeedyWeather.jl, Terrarium.jl, LPJmL-hybrid-photosynthesis). **Reuse those models freely. Do not
raise licensing, ask for a licence decision, or re-audit upstream licences** — it is settled, and re-opening it
wastes a session.

**The one standing obligation is transparent citation.** That is what this skill is for.

## The four surfaces — all four, saying the same thing

| Surface | What to add |
|---|---|
| [`docs/third_party_licensing.md`](../../../docs/third_party_licensing.md) | a register row: what the work is · what we reuse from it · where it is used |
| `CITATION.cff` → `references:` | the citable entry (`type: software` or `article`) |
| `docs/src/refs.bib` | the BibTeX entry — then cite it inline in the docs as `[key](@cite)` |
| the **source-file header** | in *every* file with derived content: name the upstream and say what came from it |

Miss one and they drift out of agreement, which is the actual failure mode here.

## State provenance accurately — this is the part that goes wrong

- **"Ported from X"** must mean the expression came from X.
- An **independent implementation of a published method** must say that, and cite the method's paper — not the
  codebase that also happens to implement it.
- Comparative notes are good practice and should stay, e.g. *"θ = 0.7 (C source); NeuralCrop's 0.9 is
  crop-specific"*.

Worked example (ADR 0080 §3): the TBPTT trainer's header claimed it was *"the finished port of NeuralCrop.jl's
`train_loop_rollout!` scaffold"* while the same sentence said "no code copied". Diffing the two showed **no
shared expression** — the only overlap was `Zygote.withgradient` → finite-loss guard → `Optimisers.update`
inside a windowed day loop, i.e. those libraries' public API plus TBPTT itself (Williams & Peng 1990). The code
was fine; the *wording* was the defect. When in doubt, read both and compare before writing the header.

## Two works that are method-only, no code (facts, not licence caveats to relitigate)

- **NeuralCrop.jl** — CC-BY-NC, a different author outside both groups, so the owner's memberships don't cover
  it. Cite arXiv:2512.20177; implement from the paper.
- **LPJ_resilience** — no licence upstream. Implement the published metrics (Bathiany et al. 2024, GCB
  30(12):e17613).

## Finding a Julia package's real upstream (fiddly on this cluster)

A package name is not a repo. The General registry here is a **tarball**, and its paths have **no `./` prefix**:

```bash
mkdir -p /tmp/regx
tar xzf ~/.julia/registries/General.tar.gz -C /tmp/regx <FirstLetter>/<Package>/Package.toml
grep repo /tmp/regx/<FirstLetter>/<Package>/Package.toml
```

**Expect monorepos:** `RingGrids` and `SpeedyWeatherInternals` both resolve to
`SpeedyWeather/SpeedyWeather.jl.git`, so both are cited as SpeedyWeather.jl. Guessing a `RingGrids.jl` repo
gets a 404 that proves nothing. If the package is newer than the registry snapshot, fetch
`https://raw.githubusercontent.com/JuliaRegistries/General/master/<L>/<Pkg>/Package.toml`.

GitHub HTTPS is blocked from the cluster (`CLAUDE.md` §1) — fetch upstream files harness-side (WebFetch), not
with `curl`. A local clone under `/p/tmp/jamirp/esm_reference_repos/` is authoritative for the commit we
actually read, so **pin the commit** in the register (Terrarium is v0.1.x with an unstable API).

## New dependency mechanics

Runtime `[deps]` stays **EMPTY** (ADR 0014) ⇒ a new package is `[weakdeps]` + a package extension, and
`Project.toml` is **integrator-owned**, so request it. This is a **technical** constraint — the HPC compute
nodes have no GitHub egress and the physics core is deliberately dependency-free — not a licensing one.

Copying third-party source *into* the tree still deserves a short ADR, for **maintenance** reasons (a vendored
copy drifts from upstream silently). Name the file, the upstream commit, and the header added.
