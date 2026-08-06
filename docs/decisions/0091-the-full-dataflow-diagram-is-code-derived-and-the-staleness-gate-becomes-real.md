# ADR 0091 — the full data-flow diagram is code-derived, and the staleness gate stops being imaginary

* **Status:** Accepted
* **Date:** 2026-08-06
* **Line:** cross-cutting / integrator (block 0090–0099)
* **Owner request:** yes (2026-08-06): *"make a full data flow diagram as part of the documentation and
  that gets updated when the code changes. the diagram should show the data that goes into lpjmlfit, the
  data that goes into each of the components and the data that is exchanged between the components."*
  Plus, in the same message, a cleanup of `docs/`.
* **Amends:** ADR 0090 §the `CI` path table (the `docs/src/generated/**` row's justification is now true)
* **Related:** ADR 0008 (documentation-only), ADR 0029 (`registry.jl` is shared/additive-only),
  ENGINEERING_STANDARDS §5 (curated vs derived diagrams)

## Context

Two independent problems, and the owner's request exposed both at once.

**1. There was no full data-flow diagram.** `src/registry.jl` described the *runtime coupling seam only*
— four nodes (S, F, E, atmosphere) and eight handoffs. Nothing anywhere drew the inputs LPJmL-FIT is
driven by, the provenance chain from its outputs to the two learned artifacts, or what each component
reads at run time. ENGINEERING_STANDARDS §5(ii) had explicitly called for "the input-drivers → model →
output-fluxes data flow" since Phase 0; it was never built.

**2. The staleness gate was fictional.** `.github/workflows/CI.yml` has watched `docs/src/generated/**`
from the beginning, annotated *"diagram fixtures the suite compares against registry.jl"*, and ADR 0090
repeated that justification in its path table. **No test compared them.** `scripts/gen_diagrams.jl
--check` existed but was a local command someone had to remember to run. The consequence is measured, not
hypothetical: `docs/src/generated/components.mmd` was stale from the Phase-4 commit `773945fb` for
**weeks** — the rendered architecture diagram contradicted `src/registry.jl` and nothing failed. This was
already written down in the `julia-test` skill as *"NO CI job runs this check … don't assume CI will catch
it"*, i.e. the gap was known and carried rather than closed.

A diagram that the owner is expected to trust, and that no gate defends, is worse than no diagram: it
looks authoritative and drifts silently.

## Decision

**1. Add a full data-flow graph to the registry, and generate the diagram from it.**
`src/registry.jl` gains `DataNode`, `DataEdge`, `STAGES`, `DATA_NODES`, `DATA_EDGES` — purely additive, so
`COMPONENTS`/`FLUXES` and both existing generated diagrams stay **byte-identical** (guardrail 4).
`scripts/gen_diagrams.jl` gains a third target, `docs/src/generated/dataflow_full.mmd`, grouped into
subgraphs that read left-to-right as *provenance → training → runtime*. Offline paths (training and
validation) are **dashed**, so a coupled run is visually distinguishable from the pipeline that built it.

**2. Component-to-component edge labels are REFLECTED from the interface structs, not hand-written.**
`Flux`/`DataEdge` gain `payload_type::Union{Nothing,Symbol}` naming the `src/interface.jl` struct the edge
carries; the rendered label is `fieldnames(T)`. This is what makes "updated when the code changes"
mechanical rather than aspirational — adding a field to `SToF` changes the diagram. The legacy free-text
`Flux.payload` strings are deliberately left alone (they are what keeps the two older diagrams
byte-identical), and a gate asserts each one at least names the struct it claims to carry.

**3. Four gates in `test/testitems/diagram_registry_tests.jl`, so the gate runs under `CI` for real.**

| Gate | What it stops |
|---|---|
| Staleness | Regenerates and compares byte-for-byte with the committed `.mmd`. This is the check `CI.yml` always claimed. |
| Reflection | Every typed edge's label equals its struct's `fieldnames`, with the field **count** asserted too (so a hand-edited label cannot pass). |
| Provenance | Every `DataNode.path_key` must resolve in `config/paths.yaml`, so a renamed or deleted input cannot leave a phantom box on the diagram. Parsed by a ~20-line Base indentation reader — runtime `[deps]` stays empty (ADR 0014). |
| Structure | No dangling edge endpoint, no orphan node, no node in an unrendered stage, no empty stage, unique ids. |

`scripts/gen_diagrams.jl`'s `main(ARGS)` is now guarded by `abspath(PROGRAM_FILE) == @__FILE__` so the
test can include it without regenerating the fixtures mid-run — an unguarded include would destroy the
very signal gate 1 detects.

**4. Reorganise `docs/`.** The engineering notes and the LaTeX report moved out of the top level:

| From | To |
|---|---|
| `docs/<10 loose notes>.md` | `docs/notes/` (+ a `README.md` index) |
| `docs/component_s_public_report.{tex,pdf}` | `docs/report/` |
| `docs/figs/**` | `docs/report/figs/` (keeps `\graphicspath{{figs/}}` valid — **no `.tex` edit**) |
| — | new `docs/README.md` explaining what each subdirectory is and which CI gate it triggers |

The untracked `docs/viewing_built_docs.md` was deleted: it duplicated
`docs/src/howto/build_docs.md`, whose one genuinely new tip (serving over HTTP) was folded into that
published page instead.

## Consequences

* **The owner gets a diagram that cannot lie**, on a new page `docs/src/explanation/dataflow.md`, written
  in plain language with the honest caveats visible on the boxes themselves — that the soil-depth input is
  read and discarded, that CO₂ is frozen deliberately and the emulator never sees it, that the annual tree
  table omits stems under 5 m.
* **The `CI.yml` comment and ADR 0090's path table are now accurate.** They were describing an intended
  gate as an existing one; anyone reasoning from them was reasoning from a false premise.
* **A change to the interface contract now has a documentation cost that CI enforces.** Adding a field to
  `SToF` reds the suite until `scripts/gen_diagrams.jl` is rerun. That is the intended friction.
* **`git log --follow` is needed** to trace the moved notes across the rename.
* **Old paths survive in append-only history on purpose.** `CHANGELOG.md`, `JOURNAL.md`,
  `docs/archive/**`, the `changelog.d/*` fragments and the **immutable numbered decision records** were
  left untouched — they correctly describe where files were when written. `docs/README.md` and
  `docs/notes/README.md` both record the move and date so an old path is still resolvable. The mechanical
  rewrite was applied only to live files (source, tests, scripts, the page tree, skills, plan/state docs).
* **Comment-only edits landed in three committed reference fixtures** (`hainich_canopy_baseline_2010.txt`,
  `hainich_fdiff_baseline_2010.txt`, `hainich_slow_oracle_counts.csv`) to keep their note pointers
  resolvable. **No baseline moved:** each reader skips `#` lines, so not one compared value changed.
* **Cross-line note:** the path rewrite touched comment lines in files owned by lines S, M and E
  (`slow.jl`, `drf.jl`, `climbuf.jl`, `fdiff.jl`, `fast.jl`, `energy.jl`) and in three skills. A
  directory rename cannot be done by any single line, so it is integrator work by construction; it is
  comment-only, and merging promptly keeps the conflict window small.

## Alternatives rejected

* **Hand-draw the full diagram** as a curated `.mmd`. Rejected: it is exactly the artifact the owner asked
  to keep current, and a hand-drawn one drifts — which is how `components.mmd` went wrong for weeks.
* **Parse the LPJmL-FIT `.js` config directly** to derive the input list (ENGINEERING_STANDARDS §5's
  original suggestion). Rejected for CI: those files live on the cluster at `/home/jamirp/lpjml56fit`,
  which GitHub Actions cannot see, so the gate could never run. The registry names `config/paths.yaml`
  keys instead, and gate 3 checks them — in-repo, so it runs everywhere.
* **Generate the diagram live in the docs build** (staleness then impossible, per §5). Rejected as the
  *only* mechanism: the `docs` gate does not run on line branches at all, so drift would surface only on
  `main`. The committed-fixture-plus-test approach runs under `CI` on every branch. Both are in fact
  active — the page embeds the committed `.mmd` and the suite regenerates it.
* **Leave the loose notes in place** and only document the layout. Rejected: the owner's read of `docs/`
  as disorganised was correct, and a `README` explaining a mess is not a fix.
* **Delete the loose notes as leftovers**, which is what the owner's message wondered about. Rejected on
  evidence: every one is live, referenced by name from source and tests —
  `phase3_fdiff_cbinary_validation.md` alone has 31 inbound references including `src/fdiff.jl` and about
  ten test files. They were **misfiled, not obsolete**.

---

## Amendment — 2026-08-06, same day (the diagrams were never actually RENDERING)

Recorded as a labelled amendment rather than a superseding record because it lands the same day, before
any other work depended on this ADR, and it corrects a mechanism this ADR asserted rather than a decision
it made. The decision (code-derived diagram + four gates) is unchanged.

**The owner opened the built docs and the diagram was raw text in a grey code box.** Not only the new one
— the *pre-existing* `Diagrams` page too. These diagrams had never rendered.

**Cause.** Every page embedded its diagram with

```
​```@eval
Markdown.parse("```mermaid\n" * read(f, String) * "\n```")
​```
```

DocumenterMermaid converts a mermaid fence with an **expander**:
`Selectors.matcher(::Type{MermaidExpander}, node, page, doc) = Documenter.iscode(node, "mermaid")` at
expansion order 7.9, matching nodes of the **parsed source AST**. An `@eval` block produces its output
*during that same expansion pass* — after the matcher already walked that node — so the returned fence is
never turned into a `MermaidBlock` and falls through to Documenter's ordinary code-block rendering.

**Why nothing caught it.** Mermaid draws client-side, so the strict docs build never validates a diagram;
it only checks that the block *ran*. The build was green with zero diagrams rendered. Measured on the
built site: **0** occurrences of `class="mermaid"`, while DocumenterMermaid's `mermaid.esm.min.mjs` loader
was injected on every page — the renderer was present and idle. This ADR's own "Alternatives rejected"
section said generating live in the docs build was *also* active; that was wrong, and it was wrong in the
direction that mattered.

**Fix.** The fence is now **literal markdown in the page source**, inside
`<!-- BEGIN MERMAID <name> … -->` / `<!-- END MERMAID <name> -->` markers that `scripts/gen_diagrams.jl`
rewrites from the `.mmd` sources. The two pages (`docs/src/diagrams.md`,
`docs/src/explanation/dataflow.md`) are now `targets()` alongside the three `.mmd`, so gate 1 (staleness)
covers the embedded fences too and page-vs-source drift stays impossible. All five previously-dead
diagrams on `diagrams.md` are fixed by the same change.

**Verified:** the rebuilt site has **5** `class="mermaid"` elements on `diagrams.html` and **1** on
`explanation/dataflow.html`, with **0** code-block-wrapped `flowchart` occurrences; strict docs build
exit 0; `--check` idempotent; Runic clean.

**The transferable lesson, and the reason this is worth a record:** *a green docs build is not evidence
that a diagram renders.* The only check that distinguishes them inspects the built HTML —
`grep -c 'class="mermaid"' docs/build/<page>.html` — and it is now written into the `julia-test` skill next
to the regeneration commands. Two further consequences: the CDN dependency means a machine without
outbound internet shows a blank area even when the markup is correct, and an `@eval`-embedded fence must
never be reintroduced as a "simplification" (the generator carries a comment saying so).
