# ADR 0090 — CI runs only when the changed paths can change its verdict

* **Status:** Accepted
* **Date:** 2026-08-04
* **Line:** cross-cutting / integrator · **opens the new integrator ADR block 0090–0099**
* **Owner decision:** yes — raised by the repo owner (2026-08-04): *"why do you run CI when changing
  something in the report? In general, CI is run too often which is a computational waste and a waste of
  time. Rethink the CI strategy."*
* **Amends:** ADR 0013 §CI (the 5-gate list), ADR 0028/0029 §the merge ritual (what "green" means)
* **Related:** ADR 0008 (documentation-only changes), ADR 0028 (parallel session lines)

## Context

Every workflow triggered on **every push** to `main` or `line/**`, with no path filters. The Julia matrix
(`test (lts)`, `test (1)`, `test (pre)`, `test (macOS, lts)`) is four jobs at roughly ten minutes each, and
it ran identically whether the commit changed `src/fdiff.jl` or a sentence in a LaTeX report.

That is not a hypothetical inefficiency. On 2026-08-04 four consecutive commits — a rewritten
`docs/component_s_public_report.tex`, a `.claude/skills/**` update, a `lines/S/STATE.md` handoff refresh,
and a table-caption edit — each triggered the full matrix plus `format` and `python`. None of them touched a
single `.jl` file, `python/`, or anything the Documenter build reads. That is on the order of **an hour of
runner time and four merge-ritual waits** spent confirming that prose cannot break Julia tests.

The waste compounds under ADR 0028: four parallel lines, each pushing several times per session, each
waiting for a green verdict before merging. The documented ritual ("green on THAT sha? integrate") made the
wait mandatory, so the cost was in wall-clock time to the human as well as in compute.

## Decision

**Each gate declares the paths that can change its verdict, and runs only when one of them changed.**

| Gate | Runs when these change | Rationale |
|---|---|---|
| `CI` (Julia, 4 jobs) | `src/**`, `ext/**`, `test/**`, `Project.toml`, `docs/src/generated/**`, own workflow | The only inputs to the test suite. `docs/src/generated/**` is included because the suite compares those diagram fixtures against `registry.jl`. |
| `format` (Runic) | `**/*.jl`, own workflow | Runic formats Julia and nothing else. |
| `python` (ruff + pytest) | `python/**`, own workflow | Every step runs with `working-directory: python`, so `ruff check .` / `pytest` only ever see that subtree. `scripts/*.py` is **not** linted by this gate (and carries ~162 pre-existing findings under the repo-root config, which is why it must not be added casually). |
| `docs` (Documenter) | `docs/src/**`, `docs/make.jl`, `docs/Project.toml`, `src/**`, `Project.toml`, own workflow | Docstrings come from `src/**`. Deliberately excluded: `docs/component_s_public_report.{tex,pdf}`, `docs/figs/**`, `docs/decisions/**` — all live under `docs/` but are **not** in the Documenter page tree, and `make.jl`'s linkcheck ignores the GitHub self-links that point at the ADRs. |
| `TagBot` | unchanged (release-triggered) | Not a push gate. |

**Every workflow additionally gains `workflow_dispatch`.** That is the escape hatch and it is what makes the
filters safe: any gate can be forced from the Actions tab or `gh workflow run` when you want it regardless of
the paths touched.

## The load-bearing consequence: a skipped gate reports NOTHING

This is the part that will break a future session if it is not internalised.

A path-filtered workflow that does not trigger does not produce a "skipped" status — **it produces no
check-run at all**. Querying `/commits/<sha>/check-runs` returns fewer entries, and a poll loop written as
*"wait until `test (lts)` is `completed`"* **waits forever**.

So the merge ritual's "green on THAT sha" becomes:

> **A gate is satisfied if it passed, or if it never ran because no path it watches changed.**
> Never wait for a check that cannot appear; never merge on a gate that ran and *failed*.

Concretely, the poll must treat *absent* and *success* alike, and must decide which of the two it is from the
diff rather than from the API. The practical rule, in order:

1. `git diff --name-only origin/main...HEAD` — what did this branch actually touch?
2. Map that against the table above to get the set of gates that *should* exist.
3. Require exactly those to be green. Absent gates outside that set are correct, not pending.

`test (pre)` remains `continue-on-error` and allowed to fail (Julia-prerelease churn); that is unchanged.

## Consequences

* **A prose/docs/skill/ADR/handoff-only commit now triggers no gate at all** and can be merged as soon as it
  is pushed. That is the intended outcome, and it is safe precisely because those paths are inputs to no gate.
* **Cost falls by roughly the share of commits that are documentation** — historically a large fraction of
  this repo's commits, given the §8 capture discipline and the per-line STATE/JOURNAL protocol.
* **A tag push is now also path-filtered**, including `docs`. A release tag therefore may not redeploy the
  versioned documentation. Accepted: the tag's tree is identical to a `main` commit that already deployed, so
  the site is current; if a versioned deploy is ever wanted, run `docs` via `workflow_dispatch`. Recorded
  here so it is a known trade rather than a surprise.
* **The risk being accepted** is a path that influences a gate but is not listed. The mitigation is that the
  filters are deliberately *generous* on the cheap gates (`format` watches `**/*.jl` anywhere, not just
  `src/`) and that the expensive gate lists the whole of `src/`, `ext/`, `test/` rather than trying to be
  clever about which file affects which test. If a gate is ever seen to disagree between a line branch and
  `main`, suspect a missing path entry first and widen the filter.
* **`.github/workflows/**` remains integrator-owned** (CLAUDE.md §9 Gap 3). This ADR was landed on the
  owner's explicit instruction, which supersedes the line-ownership convention for this change only.
* **ADR numbering:** the cross-cutting block 0001–0029 is exhausted and lines hold 0030–0089, so this ADR
  opens **0090–0099 for integrator/cross-cutting decisions**. Recorded in CLAUDE.md §9 and the ADR index.

## What was explicitly NOT done

* **No reduction of the Julia matrix.** `test (lts)` and `test (1)` are both required and both catch real
  regressions the other does not (they resolve different dependency sets, and JET 0.11 only runs on 1.12).
  The waste was running them on irrelevant commits, not running them at all.
* **No `paths-ignore` formulation.** An allow-list (`paths`) fails safe in the direction that matters: a new
  top-level directory is not silently assumed to be irrelevant to every gate. A deny-list would have to be
  updated every time a new kind of file appears.
* **`scripts/**` was not added to any gate.** It is not currently linted or tested by CI at all; adding it
  is a separate decision with its own cost (the ~162 pre-existing ruff findings would have to be cleared
  first), and pretending otherwise here would have quietly turned a cost-reduction ADR into a red `main`.
