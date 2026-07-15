---
status: "accepted"
date: 2026-07-15
deciders: "Jamir Priesner (owner)"
consulted: "ENGINEERING_STANDARDS.md §4/§6"
informed: "the whole docs stack"
---

# Documentation-only (Documenter.jl as single source of truth); no AI code-wiki

## Context and Problem Statement

The owner does not write the code and must be able to understand and control everything. Should the
project add an AI code-wiki (DeepWiki / OpenDeepWiki / Google Code Wiki) as a browsable explorer, or
rely solely on hand-/agent-authored documentation kept honest by CI? See ENGINEERING_STANDARDS §6.

## Decision Drivers

- **Control** stays with the owner; no third-party code upload.
- **No hallucination** in the source of truth (AI wikis can invent build systems, integrations,
  pipeline diagrams).
- Operational simplicity; no extra ops surface.

## Considered Options

- **Documenter.jl only** — the single source of truth, kept honest by CI (doctests, executed
  examples, code-derived diagrams, source links, ADRs).
- **Documenter + an AI code-wiki** as a browsable explorer alongside it.
- **AI code-wiki only.**

## Decision Outcome

Chosen: **Documenter.jl only, no AI code-wiki (for now)**. Keeps everything in the owner's control,
uploads no code to a third party, and removes hallucination risk from the source of truth. The cost is
that the owner **browses/searches the Documenter site** rather than chatting with an AI over the repo —
accepted. This obliges the Documenter docs to be genuinely complete and self-standing (strong
Explanation + Reference, the GMD model description, curated + code-derived diagrams, code links on
every symbol).

### Consequences

- Good: no third-party code upload; no hallucinated source of truth; minimal ops.
- Good: forces investment in complete, self-standing docs (Diátaxis) — the actual deliverable here.
- Bad: no conversational "ask the repo" layer; the owner navigates the site manually.

## More Information

**Deferred with zero rework:** an AI wiki may later be added *as an explorer only, never the source of
truth* — free private-repo options are DeepWiki (uploads code to Cognition's cloud → needs IP sign-off)
or self-hosted OpenDeepWiki with a local LLM. If ever adopted, the rule is: read Documenter as truth;
use the wiki only to explore and click through to verified code links (ENGINEERING_STANDARDS §6).
