---
name: skill-creator
description: How to author or update a skill in THIS repo (.claude/skills/) so a future session reuses a procedure instead of re-deriving it — the capture triggers, the SKILL.md frontmatter, the trigger-rich description that makes a skill auto-activate, and the "point at a helper script, don't inline it" rule. Use whenever you wrote a rerunnable script, did the same multi-step thing twice, found a non-obvious fix, or re-derived something a prior session knew — i.e. whenever you are about to capture a reusable procedure.
---

# skill-creator — capture a procedure as a skill

This repo lives or dies on **not re-deriving**. When you learn a repeatable *procedure*, it belongs in a
skill so the next session runs it instead of rebuilding it. Creating skills is part of the job, not a
favor to a future session — and historically agents here **under-create** them, so bias toward doing it.

## When to make (or update) a skill — the triggers

Stop and capture the moment ANY of these fires:

- You wrote a script you (or a future session) would plausibly run again.
- You did the same multi-step thing twice this session, or can imagine a third time.
- You hit a non-obvious error and found the fix.
- **You re-derived something a prior session already figured out** — the strongest signal; last capture failed, capture it now.

**Route check first (don't reach for a skill by reflex):** a *procedure/how-to* → skill (here). An
*environment fact/gotcha* → `CLAUDE.md`. A *decision* → an ADR. *Current state* → `MEMORY.md`. *Narrative*
→ `JOURNAL.md`. Only procedures come here.

**Prefer updating an existing skill over creating a new one.** Check the six current skills
(`fdiff-validate`, `julia-test`, `lpjmlfit-cbinary`, `python-env`, `residual-diagnosis`, `repo-commit`)
first — a new gotcha or a parameterized variant usually belongs inside one of them, not in a new skill.
Example: single-cell forcing+restart extraction is `fdiff-validate` **parameterized by cell index**, not
a new skill each time.

## How to author one (5 minutes — do it minimally in the moment)

1. `mkdir -p .claude/skills/<kebab-name>` and write `.claude/skills/<kebab-name>/SKILL.md`.
2. **Frontmatter is two fields — `name` and `description`.** Skills are auto-discovered; nothing else to
   register.
   ```markdown
   ---
   name: <kebab-name>              # matches the directory
   description: <see below — this is the load-bearing field>
   ---
   # <name> — <one-line what it does>
   ```
3. **The description is what makes the skill trigger.** It is the ONLY part loaded into every session's
   skill list, so the model decides whether to invoke the skill from this text alone. Write it in the
   third person, pack it with the concrete triggers a future session will be doing ("Use whenever
   running/validating/committing…"), and name the artifacts involved (scripts, files, cell 42490, the
   gate). A vague description = a skill that never fires. Compare the existing six for calibration.
4. **Point at the helper script; don't inline it.** If you wrote `scripts/foo.jl`, the skill says *when*
   and *how* to run it and lists its gotchas — it does not paste the code. Keep the body lean; a 10-line
   SKILL.md that points at a real script beats a perfect essay that never gets written.
5. **Do NOT name a script `*_test.jl`/`*_tests.jl`** — ReTestItems scans the whole repo and fails
   collection on any such file that isn't a pure `@testitem`. Use `*_probe.jl` / `*_diagnosis.jl` (see
   CLAUDE.md §2).

## Bundle it into the same commit

A skill captured "later" is captured never. When the work that taught you the procedure gets committed,
the new/updated skill goes in the **same commit** (see the capture gate in CLAUDE.md §8 and the
`repo-commit` skill). Note it in the commit body ("+ skill: <name>").

## Sharpen a description that isn't triggering

If a skill exists but sessions still re-derive its task, the description is too weak — rewrite it with the
exact verbs and artifact names of the task, not a summary of the skill's internals.
