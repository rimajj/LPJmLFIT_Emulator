---
status: "accepted"
date: 2026-07-28
deciders: "line O (agent, full autonomy per STEERING_PROMPT.md P5)"
consulted: "STEERING_PROMPT.md P5; ADR 0006 §Consequences, ADR 0014, ADR 0015 §Consequences, ADR 0017 §Decision-Drivers-1; MEMORY.md §4 reuse-posture TODO; DESIGN.md §3.4; README.md §License; CITATION.cff; the upstream LICENSE/NOTICE files themselves"
informed: "line S, line M, line E, the integrator; ADR 0017 (annotated, not superseded); ADR 0015 (one claim corrected)"
supersedes: "—"
---

# Licensing basis: AGPL-3.0-or-later outbound; consume EUPL/MIT works as *library dependencies*, never vendored

## Context and Problem Statement

`STEERING_PROMPT.md` **P5** requires "a good-faith EUPL↔AGPL↔MIT licensing basis in the ADR" so that P4
(online coupling to Terrarium.jl / SpeedyWeather.jl) can proceed; it states explicitly that a formal legal
review "remains an owner or external action but is **not a blocker for research use**". The question has been
open since **ADR 0006** flagged it, was cited as the first of three drivers for **ADR 0017** (component E
reimplemented rather than reused), was deferred again by **ADR 0015** ("not triggered by research-use
porting"), and has sat in `MEMORY.md` as *"the EUPL↔AGPL↔MIT licensing read is still unresolved and ADR
0017's premise rests on it"*.

Auditing it this session turned up three facts that change the framing from "a future formality" to
"an open item with one live compliance gap":

1. **This repository has no `LICENSE` file — and it is public.** `git log --all -- LICENSE` returns nothing
   (it never existed); `Project.toml` has no `license` field; `CITATION.cff`'s `license:` is commented out
   ("TBD by owner"); `README.md` §License says "To be set by the owner." The GitHub API reports
   `private: false`, `visibility: "public"`, `license: null` **[VERIFIED 2026-07-28]** — so
   `docs/make.jl`'s comment that "the repo is PRIVATE" is stale. An unlicensed public repository is
   *all rights reserved*: it grants no reuse or citation rights at all, which defeats its purpose, **and**
   it distributes derivative material of AGPL-3.0 code without the notices AGPL-3.0 §4/§5 require.
2. **Terrarium.jl ships a `NOTICE` that extends EUPL Article 5 to *any* licence for library use.** This is
   the single most decision-relevant fact in the whole audit and it had not been read before.
3. **The trainer extension describes itself as a "port" of CC-BY-NC code.** `ext/FDiffTrainingExt.jl`
   (3 places) and `src/LPJmLFITEmulator.jl:120` call it "the finished port of NeuralCrop.jl's
   `train_loop_rollout!` scaffold" — in the same sentence as "no code copied". NonCommercial and AGPL-3.0
   are mutually undistributable, so an inaccurate provenance claim is itself the exposure.

So: what licence does this work carry outbound, what may it consume and how, and what is actually still
owed to the owner?

## Decision Drivers

- **The outbound licence is not a free choice.** F_diff, `src/allometry.jl`, `src/state.jl` and the
  Component-S physics are functional reimplementations produced by *reading* LPJmL-FIT's AGPL-3.0 C source
  under guardrail 5 ("adversarially re-derive ported physics against the C source"), and their headers say
  "Ported per ADR 0015 from …". `patches/lpjmlfit_daily_grass_gpp.patch` goes further: it contains
  **verbatim context lines** from AGPL-3.0 `include/conf.h` and `par/outputvars.js`. The conservative — and
  the only defensible — reading is that this repo is a derivative work of AGPL-3.0 software.
- **P4 needs Terrarium and SpeedyWeather, both EUPL-1.2.** Whatever we pick must permit that combination.
- **The mechanism is already constrained by ADR 0014**: runtime `[deps]` stays EMPTY, so any coupling
  package arrives as `[weakdeps]` + a package extension. This is not only an engineering choice — it is
  also the *lowest-exposure* licensing posture available, because it means we distribute none of their code.
- **Compute nodes have no GitHub egress** (`CLAUDE.md` §1), so upstream licences cannot be checked from a
  job; they must be captured in-repo once and kept current.
- **Auditability over cleverness.** ENGINEERING_STANDARDS makes ADRs the audit trail for agent-written code.
  A licensing position a non-lawyer owner can hand to a lawyer unchanged is worth more than a maximally
  permissive one that needs re-litigating.
- **Cheap to reverse.** If a formal review later disagrees, the fix should be a licence-header change and a
  `Project.toml` edit — never "rewrite the physics core".

## Considered Options

- **A. AGPL-3.0-or-later outbound; consume EUPL/MIT works strictly as *library dependencies* (`[weakdeps]`
  + extension), never vendored; CC-BY-NC and unlicensed works are *method-only* references.**
- **B. EUPL-1.2 outbound** (match Terrarium/SpeedyWeather directly).
- **C. MIT / permissive outbound.**
- **D. Status quo — leave the repo unlicensed** and rely on "research use".
- **E. Vendor the upstream code we need** (copy Terrarium's SEB, NeuralCrop's trainer) instead of depending.

## Decision Outcome

Chosen option: **A**, because it is the only option that satisfies LPJmL-FIT's copyleft **and** is a licence
the EUPL itself names as compatible — the other four each fail on a hard constraint.

### 1. Outbound: **AGPL-3.0-or-later**

Two independent obligations converge on exactly one licence family:

- **Upstream (LPJmL-FIT, AGPL-3.0).** A derivative work of AGPL-3.0 software must be conveyed under
  AGPL-3.0 (§5c). This alone eliminates B, C and D.
- **Downstream (Terrarium / SpeedyWeather, EUPL-1.2).** EUPL-1.2's **Compatibility clause** (Art. 5,
  quoted verbatim from `Terrarium.jl/LICENSE`) reads:

  > If the Licensee Distributes or Communicates Derivative Works or copies thereof based upon **both the
  > Work and another work licensed under a Compatible Licence**, this Distribution or Communication can be
  > done under the terms of this Compatible Licence. […] Should the Licensee's obligations under the
  > Compatible Licence conflict with his/her obligations under this Licence, the obligations of the
  > Compatible Licence shall prevail.

  The EUPL-1.2 **Appendix** lists *"GNU Affero General Public License (AGPL) v. 3"* as a Compatible Licence.
  Our situation instantiates the clause literally: a work based upon **both** an EUPL Work
  (Terrarium/SpeedyWeather) **and** another work under a Compatible Licence (AGPL-3.0 LPJmL-FIT) may be
  distributed under AGPL-3.0, and AGPL-3.0's obligations then prevail.

**AGPL-3.0 is therefore forced, not preferred.** Note the asymmetry that makes B impossible: EUPL-1.2 has a
compatibility clause and AGPL-3.0 does not, so EUPL→AGPL is sanctioned while AGPL→EUPL is not. The direction
we need is the one that works. And note why C fails twice: MIT does not satisfy AGPL-3.0's copyleft, and MIT
is **not** in the EUPL Appendix, so Art. 5 could not rescue it either.

Accepted consequences of AGPL-3.0: complete corresponding source on conveyance (satisfied by the public
repo), retained notices, stated modifications, and **§13 remote-network-interaction** — if the coupled model
is ever offered as a network service, source must be offered to its users. That last point is a design
constraint on the P7/O6 ESM-packaging milestone, recorded here rather than rediscovered there.

### 2. The three tiers: **READ**, **DEPEND**, **VENDOR** are different acts with different rules

Conflating them is what kept this question open, so they are separated permanently.

**Tier 1 — READ** (study a reference implementation, then write our own). Copyright protects *expression*,
not ideas, algorithms or methods (EU Software Directive 2009/24/EC Art. 1(2); CJEU C-406/10 *SAS Institute v
World Programming*: functionality, programming languages and data-file formats are not protected). Reading a
public repository and reimplementing what it *does* is permitted for every reference we hold. A literal
line-by-line translation is **not** mere reading — it is a derivative work. Per source:

| Reference | Licence | What is permitted here |
|---|---|---|
| LPJmL-FIT C source | AGPL-3.0 | Literal porting **is** permitted — AGPL-3.0 outbound absorbs it. This is the premise of F_diff, not a problem. |
| LPJmL-hybrid-photosynthesis | MIT | Anything, with the MIT notice retained. Permissive → copyleft is one-way and fine. |
| Terrarium.jl / SpeedyWeather.jl | EUPL-1.2 | Literal porting *would* be permitted into AGPL-3.0 via Art. 5, but is **disallowed by default** (see Tier 3) — we don't need it. |
| NeuralCrop.jl | **CC BY-NC 4.0** | **Method only — never a line of code.** See §3. |
| LPJ_resilience | **no licence** (`license: null`, public — [VERIFIED 2026-07-28]) | **Method only, from the paper** (Bathiany et al. 2024, GCB 30(12):e17613). No licence = all rights reserved = no permission to copy, modify or redistribute, regardless of public visibility. The resilience *metrics* are published equations and are ours to implement. |

**Tier 2 — DEPEND** (`[weakdeps]` + a package extension; no upstream bytes in our tree). **This is the P4
mechanism.** We ship only our own code, which *calls* their public API; the user's `Pkg` fetches Terrarium
and SpeedyWeather from the General registry under their own licences. Two independent arguments make this
clean, and we do not need to pick between them:

- **Terrarium settles it outright.** Its `NOTICE` states: *"Licensed under the EUPL, with extension of
  article 5 (compatibility clause) to **any licence** for (i) distributing derivative works that have been
  produced by the **normal use of the Work as a library**, (ii) distributing derivative works managed by the
  NumericalEarth development organization."* Calling Terrarium's `Abstract*` interfaces from a package
  extension is precisely normal use as a library. Clause (ii) does not apply to us; clause (i) does.
- **SpeedyWeather has no `NOTICE`** (verified: HTTP 404), so plain EUPL-1.2 governs — and the Art. 5 route
  in §1 already covers it, because our outbound licence is an Appendix Compatible Licence.

Worth recording honestly: **EUPL-1.2 deliberately declines to say whether a dependency creates a derivative
work.** Art. 1 defines Derivative Works and then adds *"This Licence does not define the extent of
modification or dependence on the Original Work required in order to classify a work as a Derivative Work;
this extent is determined by copyright law applicable in the country mentioned in Article 15"* — Art. 15
being the law of the EU Member State where the Licensor has its seat (Terrarium's licensors are at PIK
Potsdam ⇒ German law; SpeedyWeather's are mixed, with Belgian law as the EUPL's fallback for non-EU
licensors). **Our position does not depend on resolving that question**, because AGPL-3.0 outbound is
compliant under either reading — which is the main reason to prefer it over a permissive licence, where the
answer would matter a great deal.

Obligations we accept in Tier 2 regardless: keep all copyright/licence notices intact (Art. 5 attribution
right), make source available (a public repo does this), and state modifications.

**Tier 3 — VENDOR** (copy third-party source into our tree). **Not permitted by default.** Vendoring
triggers the full copyleft, attribution and notice-reproduction obligations *and* maintenance drift, and it
is the act ADR 0006/0017 correctly called blocked. Any future vendoring needs **its own ADR** naming the
file, the upstream commit, the licence header added, and its entry in
[`docs/third_party_licensing.md`](../third_party_licensing.md). Two vendored artifacts already exist and are
inventoried there with their obligations:

- `patches/lpjmlfit_daily_grass_gpp.patch` — a unified diff carrying verbatim context lines from AGPL-3.0
  LPJmL-FIT. Fine under AGPL-3.0 outbound; needs the notice, which §4 provides.
- `patches/json_object_iterator.h.shim` — self-described as "verbatim declarations from json-c's public
  `json_object_iterator.h`". json-c is **MIT** (© 2009–2012 Eric Haszlakiewicz; © 2004–2005 Metaparadigm
  Pte Ltd). The file documented its provenance in a comment but **carried no MIT copyright + permission
  notice**, which MIT requires; that notice is now reproduced in it (§4).

### 3. NeuralCrop.jl: method-only, and one provenance claim corrected

CC BY-NC 4.0 is a **NonCommercial use restriction**. AGPL-3.0 §7 forbids imposing further restrictions on
conveyed work, so a work that is genuinely a derivative of *both* LPJmL-FIT and NeuralCrop.jl **cannot be
lawfully distributed at all** — not under AGPL, not under CC-BY-NC. Attribution does not cure this; only
absence of copied expression does. (CC licences are also not designed for software: no patent grant, no
source-provision terms, and "NonCommercial" is undefined enough to be a hazard for a publicly funded
institute.) Hence: **NeuralCrop.jl is a method reference, cited, never a code source.**

Because the repo is public and the trainer *described itself* as a "port", that claim was checked rather
than assumed. **[VERIFIED 2026-07-28** — direct comparison of
`NeuralCrop.jl/src/training/training_loop.jl::train_loop_rollout!` (170 lines, clone `dff3fc8`) against
`ext/FDiffTrainingExt.jl::train_fdiff_rollout!`**]**:

- **Shared:** `Zygote.withgradient` → non-finite-loss skip guard → `Optimisers.update` inside a windowed day
  loop, and `best_ps = deepcopy(ps)`. That is the documented public-API idiom of Zygote/Optimisers plus
  truncated backprop through time itself — a technique long predating both codebases (BPTT: Werbos 1990;
  truncated BPTT: Williams & Peng, *Neural Computation* 2(4):490–501, 1990) — i.e. unprotectable method,
  not expression.
- **Different:** everything else. NeuralCrop takes 19 positional arguments plus 4 keywords and interleaves
  `jld2` climate-chunk loading, per-cell batching, `ps_frozen`, device dispatch, a learning-rate schedule, a
  validation split, `ProgressMeter` and checkpointing. Ours takes 6 positional arguments plus keywords, has
  none of that, and adds the actual TBPTT state carry (`_advance_state` — a detached end-state recomputed
  with the updated `ps`) that NeuralCrop does **not** do, since it keeps mutable state structs live across
  its day loop. No shared identifiers beyond third-party API names; no shared expression.

⇒ **The code is an independent implementation of a standard technique. The wording was wrong.** "The
finished port of NeuralCrop.jl's `train_loop_rollout!` scaffold" is replaced with an accurate statement of
provenance (same idiom, independently implemented, NeuralCrop cited as prior art). This is a comment-only
change: behaviour and every committed baseline are byte-identical (guardrail 4).

### 4. What is still owed — a named owner action, not an open question

The analysis above is complete and this ADR is the good-faith basis P5 asked for. The two attribution
defects it uncovered are **fixed in the same commit as this ADR** (comment-only, behaviour and every
committed baseline byte-identical — guardrail 4):

- ✅ `patches/json_object_iterator.h.shim` now carries json-c's MIT copyright + permission notice.
- ✅ The "port of NeuralCrop.jl" wording is corrected in `ext/FDiffTrainingExt.jl` (3 places),
  `src/LPJmLFITEmulator.jl`, and the `src/fdiff.jl` header. Comparative citations that are simply good
  practice ("NeuralCrop's 0.9 is crop-specific", "petpar.c / NeuralCrop radiation.jl") are retained.

What remains is the **licensing act itself**, which only the copyright holder can perform (Jamir Priesner,
and any PIK institutional claim). Recommended, in one commit:

1. Add `LICENSE` = **AGPL-3.0-or-later** (verbatim GNU text) at the repo root.
2. Set `license = "AGPL-3.0-or-later"` in `Project.toml` *(integrator-owned)*.
3. Uncomment `CITATION.cff`'s `license:` with the same SPDX identifier.
4. Replace `README.md` §License ("To be set by the owner") with the licence statement plus a pointer to
   `docs/third_party_licensing.md`.
5. Optionally obtain the formal review — explicitly **not** a blocker (P5).

Until (1) lands, the repo is public and unlicensed. If the owner prefers to defer the licence, the correct
interim mitigation is to **make the repository private again**, which suspends the distribution that
triggers the obligations. Either action closes the gap; doing neither does not.

### Consequences

- Good: **P4 is unblocked.** Taking Terrarium and SpeedyWeather as `[weakdeps]` + a package extension has a
  written, auditable basis — Terrarium's `NOTICE` for one, EUPL Art. 5 + the AGPL-3.0 Appendix entry for both.
- Good: the choice is **forced by the upstream licences**, so it survives a lawyer's review largely intact;
  and if it does not, the remedy is a header change, not a rewrite.
- Good: `MEMORY.md`'s standing licensing TODO becomes a **named owner action** with a 7-item checklist
  instead of an unresolved research question, and ADR 0015's *"NOT triggered by research-use porting"* is
  corrected — AGPL obligations attach on **distribution**, which a public repo already performs, not on
  commercialization.
- Good: a real compliance gap and two attribution defects were found and are now tracked rather than latent.
- Bad: **AGPL-3.0 is strongly copyleft.** Any third party embedding this component in a closed ESM cannot;
  §13 additionally reaches network services. This is inherited from LPJmL-FIT and is not ours to relax — but
  it does mean "can industry use this?" has the answer "only under AGPL-3.0", which the owner should know.
- Bad: the CC-BY-NC constraint makes NeuralCrop.jl permanently a *reading* source. Any future reuse of its
  neural-ODE allocation must be reimplemented from the paper, at real cost — or the author's permission
  obtained (a cheap, high-value ask: relicensing to MIT/Apache-2.0 would remove the constraint outright).
- Bad: FreezeCurves.jl (**LGPL-2.1**, a transitive dependency of Terrarium) is the one node in the tree whose
  strict-2.1-only reading would be GPL-3-incompatible. It is a non-issue *because we never distribute it*
  and LGPL permits library use — but it is the item to re-check if the vendoring posture ever changes.
- Neutral: `docs/make.jl`'s stale "the repo is PRIVATE" comment and its now-possibly-unneeded
  `linkcheck_ignore` for self-links are an **integrator** item (the `docs` gate does not run on line
  branches, so a line cannot verify a change to it).

## Pros and Cons of the Options

### A. AGPL-3.0-or-later + depend-not-vendor *(chosen)*

- Good: the only licence satisfying both LPJmL-FIT's copyleft and EUPL Art. 5 compatibility.
- Good: valid whether or not a library dependency is deemed a derivative work — the ambiguity stops mattering.
- Good: aligns with the mechanism ADR 0014 already mandates (empty runtime `[deps]`, extensions).
- Bad: copyleft limits downstream commercial/closed adoption; §13 reaches network services.

### B. EUPL-1.2 outbound

- Good: identical to Terrarium/SpeedyWeather; would make any future vendoring of *their* code trivial.
- Bad: **not available.** AGPL-3.0 has no compatibility clause, so a derivative of LPJmL-FIT cannot be
  relicensed EUPL. Only viable if the FIT derivation were deemed non-derivative — which this project
  deliberately does not assume (guardrail 5 says the opposite).

### C. MIT / permissive outbound

- Good: maximum downstream reuse; simplest for an ESM host to adopt.
- Bad: fails AGPL-3.0's copyleft, and MIT is not an EUPL Appendix Compatible Licence, so Art. 5 offers no
  rescue. Would also make the unresolved "is a dependency a derivative work?" question load-bearing.

### D. Status quo (no `LICENSE`)

- Good: nothing to do.
- Bad: strictly worse than any choice. All-rights-reserved grants no reuse or citation rights — defeating the
  repo's purpose — *while* distributing AGPL-derived material without AGPL's §4/§5 notices. It is the only
  option that is simultaneously non-compliant and useless.

### E. Vendor upstream code

- Good: no dependency-resolution or offline-compute-node concerns.
- Bad: triggers full copyleft/attribution obligations plus maintenance drift; already rejected for
  component E by ADR 0017; and for NeuralCrop it is not merely inadvisable but undistributable (§3).

## More Information

- **Relation to ADR 0017 — annotated, *not* superseded.** ADR 0017's driver 1 ("embedding Terrarium code
  across repos needs a written legal read … a *hard* blocker") is **correct and retained for the VENDOR
  tier**, which is what "embedding" means. What this ADR establishes is that it never applied to the
  DEPEND tier, so calling the blocker "hard" generalized one tier to all three. **ADR 0017's outcome stands
  unchanged** on its two independent drivers — the empty-runtime-`[deps]` / offline-compute-node constraint,
  and Terrarium's v0.1.x instability. Component E stays self-contained; this line couples *through*
  Terrarium without embedding it.
- **Relation to ADR 0015.** Its reuse map and attributions stand. One claim is corrected: AGPL/CC-BY-NC
  obligations are triggered by **distribution**, not by commercial use, and distribution is already
  happening.
- **The operational register** — every inbound work, its licence, how it was verified, and the obligation it
  carries — is [`docs/third_party_licensing.md`](../third_party_licensing.md), together with the
  **before-you-take-a-dependency checklist** this ADR makes mandatory. The `dependency-license-gate` skill
  runs it (checking a Julia package's licence from this cluster is non-obvious: GitHub HTTPS is blocked on
  the cluster, subpackages such as `RingGrids` resolve to a monorepo, and the General registry is a tarball).
- **Verified inbound licences** (all 2026-07-28): LPJmL-FIT v5.6.004 AGPL-3.0 (local `LICENSE`);
  Terrarium.jl EUPL-1.2 + Art.-5-extension `NOTICE` (local files; GitHub API `spdx_id: EUPL-1.2`);
  SpeedyWeather.jl EUPL-1.2, no `NOTICE`, and `RingGrids` + `SpeedyWeatherInternals` are subpackages of the
  same monorepo (General-registry `repo` field) so they share it; LPJmL-hybrid-photosynthesis MIT;
  NeuralCrop.jl CC BY-NC 4.0; LPJ_resilience unlicensed; Oceananigans MIT; Thermodynamics.jl Apache-2.0;
  FreezeCurves.jl LGPL-2.1; json-c MIT.
- **Revisit when:** the owner files `LICENSE` (record it and close §4); a formal legal review returns; a
  vendoring request arrives (needs its own ADR); NeuralCrop.jl relicenses; SpeedyWeather adds a `NOTICE`;
  or the repo's visibility changes.
- **Not legal advice.** This is an engineering good-faith analysis by a non-lawyer, written to be handed to
  a lawyer unchanged. It binds the project's *practice*, not the owner or PIK.
