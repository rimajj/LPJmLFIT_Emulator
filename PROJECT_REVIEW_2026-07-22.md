# Project Review & Orders — LPJmL-FIT Hybrid Emulator (2026-07-22)

Owner-facing analysis. Companion to `STEERING_PROMPT.md` (the paste-able coding-agent prompt).
This doc holds the *reasoning*; the prompt holds the *directives*.

---

## 1. Verdict

The engineering is genuinely strong; the *project thesis is only half-built*, and the working
process has become expensive to run. The fast physics (F) and the new energy balance (E) are real,
C-validated, differentiable, and conserving. But **the scientific novelty — the slow ML distribution
emulator S — is not in the coupled model.** The "coupled emulator that runs" is F+E with F growing a
deterministic canopy; `src/components/slow.jl` is a 26-line interface whose `step!` throws
`"not implemented yet"`. Everything is also proven on **one cell (Hainich)** only. So the two headline
claims of the project — *emulate the demography with ML* and *get the speed-up from doing so* — are
currently unrealized. That is the number-one thing to fix.

Separately, the agent's memory/handoff discipline has degraded into ~570 KB of overlapping narrative
logs that cost ~60k tokens just to onboard, and there is no persistent environment runbook, so each
session re-discovers the same test/package/HPC friction. Both are cheap to fix and will pay for
themselves within one session.

---

## 2. Where the project actually is (corrected)

The pasted "§4 CURRENT STATUS" (≈19 commits, F/E skeletons, spike just commissioned) is ~23 sessions
stale. Real state at session 27 (~90 commits, clean tree, main-only):

- **Phase 0–1 done.** Global 186 GB daily dataset regenerated; **water + carbon closure both PASSED**
  (water proven by the `-DSAFE` per-cell balance abort over all cells × 20 yr).
- **Phase 2 (S offline) gate met** at baseline tier — LightGBM + copula ("DirectEmulator"), 6000 cells.
  In-distribution KS 0.023 vs 0.0049 floor; **warm+dry OOD fails (KS ~32× floor)** — the documented
  equilibrium-ML failure the hybrid exists to fix.
- **Phase 3 (F_diff) far past skeleton** — multi-layer soil, multi-PFT canopy, prognostic structure via
  a differentiable `allocation_tree.c` port, self-computed NPP calibrated, NN λ/Vcmax hooks with
  verified Enzyme/Zygote gradients, grass faithful to ±10–15%, `sapwood_bg` added.
- **Phase 4 (E) landed, self-contained** — energy closes to 1.4e-14 W/m², AD-friendly; coupled Hainich
  decade emergently reproduces the 2018 drought (Bowen 0.89 vs ~0.15–0.29). ADR 0017 dropped the
  Terrarium runtime dependency (this is what your new steer reopens — see §5).

Not done: **S in the loop; E validated against FLUXNET/PLUMBER2; multi-cell; online SpeedyWeather
coupling; wind/psurf forcing.** These are the whole remaining project.

---

## 3. Strategic gaps in the emulator (ranked)

1. **The novelty isn't coupled, and there's an unresolved architectural fork.** F_diff already
   reimplemented allocation + growth (`grow_individual`, `rollout_canopy_years`) — which the boundary
   rule assigns to **S**. So when S is wired in, *who owns tree growth?* Until this is decided the
   "hybrid" is a slogan, not an architecture. My recommendation is in §4.
2. **The speed-up — the entire reason to build a hybrid — is unmeasured and unrealized**, because the
   running model executes the full deterministic demography S was meant to replace.
3. **Everything is single-cell.** F-validation, E, the coupled run: all Hainich. The only multi-cell
   asset (offline S) is the piece not coupled. Generalization is completely untested.
4. **E has no observational validation yet** — LE/H/T_skin are invented quantities validated only
   out-of-model, and that validation hasn't happened. "ESM-ready" is architecturally true, empirically
   unproven, and `g_a` is neutral-only.
5. **Coupled stability is asserted from one 10-yr Hainich run.** That is not evidence for multi-cell,
   long-horizon, or *online* stability — and the field's sharpest lesson (Brenowitz 2020) is that
   offline skill can anti-correlate with coupled stability.
6. **Constant-CO₂ / no-N ceiling** blocks the highest-value scientific question (future carbon / CO₂
   fertilization). This is the subject of the deferred "(c)" discussion and the nitrogen track (P6).

---

## 4. The architectural fork — recommended resolution

Two investments overlap: S (ML demography, non-differentiable, offline) and F_diff's differentiable
deterministic allocation/growth. Don't discard either. Recommended split, to be ratified in a new ADR:

- **F_diff owns the conserving, differentiable *carbon* growth of the representative individuals**
  (flux-then-integrate: it already grows pools from delivered NPP, differentiably — keep it; it is what
  makes online physics training possible).
- **S owns the *distribution and demography*** that F's representative-individual growth cannot produce:
  the count N, establishment, mortality, and the trait×size *spread* across the population, conditioned
  on climate + state + the delivered `bm_inc`. This is S's genuine novelty and is exactly what the
  offline emulator already predicts.
- Each year: S sets population membership + trait distribution; F_diff advances each representative
  individual's carbon; the flux-then-integrate reconciliation conserves at the handoff.

This preserves both code investments, keeps the gradient path intact for online training, and puts S's
distributional contribution back at the center. The alternative (S regenerates the whole distribution
and F_diff's allocation is retired) throws away the differentiable growth needed for P4 and should be
rejected unless S-only proves strictly better on the distributional panel.

---

## 5. Reuse posture — reconciling your steer with ADR 0017

Your directive ("reuse Terrarium and the other GitHub sources where helpful") is right, and it should
*invert the agent's current default*, which has drifted toward reimplementation (ADR 0014 fast core,
0017 energy). Some of that was well-justified (F must be differentiable and the C is AGPL/Fortran-like
C, not reusable Julia; FIT trees don't exist in any reuse source). Some was driven by an **unverified
licensing assumption** (EUPL↔AGPL) that has been deferred for the entire project. Honest synthesis:

- **Keep the offline core able to run dependency-light** (good for HPC/testing) — but stop treating
  "self-contained" as a virtue in itself.
- **Reuse Terrarium as the coupling substrate for the online path.** Implement S/F/E as Terrarium
  `Abstract*` processes and couple to SpeedyWeather via the existing `SpeedyWeatherTerrariumExt`
  external-land interface. This is literally what Terrarium is for and is the lowest-risk route to the
  "run online" half of the goal. E can *also* borrow Terrarium's SEB/skin-temp as a cross-check on the
  self-contained solver.
- **Reuse LPJmL-hybrid-photosynthesis's differentiable-λ pattern** (already done) and **NeuralCrop's
  two-stage pretrain→fine-tune recipe + rollout machinery** — subject to NeuralCrop's CC-BY-NC license
  (a real blocker for shipped code; contact the author, or reuse methodology not code).
- **Resolve the deferred licensing read now** (EUPL-1.2 ↔ AGPL-3.0 ↔ MIT). ADR 0017's core premise
  rests on it. New ADR: "reuse Terrarium for coupling; offline core stays dependency-light; here is the
  written licensing basis." Reverse the burden of proof: **reuse is the default; reimplementation must
  be justified in an ADR.**

---

## 6. How the agent has worked — retrospective

**Genuinely excellent, keep it:** the `[VERIFIED]/[DECISION]/[TODO]/[ASSUMPTION]` tagging; ADRs for
every decision; conservation/gradient/rollout/resilience CI gates; validating F_diff against the C
binary as an oracle (kernel-isolation drive); adversarial line-by-line re-derivation of ported physics;
the "no committed baseline moved / opt-in default-byte-identical" discipline. This is better than most
research code and is why the physics is trustworthy. Do not let the reforms below erode it.

**Failure modes, costing real time:**

1. **Documentation bloat.** MEMORY 125 KB, JOURNAL 202 KB, HANDOFF 159 KB, CHANGELOG 86 KB — four
   overlapping narrative logs, ~570 KB total. MEMORY.md has stopped being "durable current state" and
   become a session-by-session journal (its §6 is a giant run-on of 20+ session entries). The HANDOFF
   "takeover prompt" has grown to 1,675 lines — a takeover prompt should be readable in minutes.
   Onboarding now costs ~60k tokens before any work starts.
2. **No persistent runbook.** There is no `CLAUDE.md`/`AGENTS.md`. Every session re-derives the same
   environment facts — `module purge` + json-c 0.13.1 for the C binary, `pip --break-system-packages`,
   `uv sync --frozen`, delete `test/Manifest.toml` before `Pkg.test()`, Enzyme ≤0.13.188, the Julia
   1.10-lts vs 1.11 Enzyme guard, the "eval"-filename classifier gotcha. These are scattered through
   MEMORY prose instead of living in one runbook + skills.
3. **Diagnosis thrashing.** The grass-overshoot investigation ran ~10 sessions (17–26) with
   "RE-DIAGNOSIS #2/#3", "REFUTED", "RULED OUT", and finally "it was a **reference-basis artifact**" —
   i.e. many sessions were spent chasing a gap that came from comparing against the wrong reference. The
   ~20 `scripts/grass_*` probes are the fingerprint. Lesson: **establish the correct validation/reference
   basis and a falsifiable hypothesis *before* chasing a residual**, and time-box sub-investigations.
4. **Reimplementation bias** over reuse (see §5).

---

## 7. Working-practice reforms (do first, session 1)

- **Create `CLAUDE.md`** at repo root: the environment runbook + workflow + the gotcha list, so no
  session re-derives them. (Spec in the steering prompt.)
- **Consolidate & cap the docs.** MEMORY.md = *current durable state only* (frozen decisions as an
  index → ADRs; verified facts; open TODOs; phase status) with a hard cap (~400 lines / ≤15k tokens).
  Session narrative moves to an append-only JOURNAL. Retire the ever-growing HANDOFF in favor of a
  short (<150-line) `00_START_HERE` pointer + the capped MEMORY. Run the **`consolidate-memory` skill**
  now and every ~5 sessions.
- **Write project skills** for the repeated mechanical tasks (see §8). This is the direct fix for "the
  agent keeps struggling with test envs and packages."
- **Housekeeping:** delete the 946 MB `core-*` dump; confirm `.cov` files stay gitignored.

Target outcome: a fresh agent is productive after reading `CLAUDE.md` + `00_START_HERE` + capped
MEMORY — under ~15k tokens, not 60k.

---

## 8. Skills to create (project-specific)

1. **`julia-test`** — run the suite correctly: delete `test/Manifest.toml` first; `Pkg.test()` vs
   `--project=test`; the testitems layout; Runic format gate; JET/Aqua; Enzyme ≤0.13.188 + the
   1.10-lts-vs-1.11 guard; how to regenerate ReferenceTests baselines.
2. **`lpjmlfit-cbinary`** — run the C oracle: `module purge` + exact module set (json-c 0.13.1, not
   0.17); restart from `restart_1999.lpj`; positional `startgrid/endgrid`; enable daily output
   (config-only); the SLURM templates (`run_daily_subset.sh`).
3. **`fdiff-validate`** — the C-oracle cross-check pattern: kernel-isolation drive (FAPAR/PET crutch),
   Hainich cell 42490 harness, the extract→validate→baseline loop (subsumes the many `extract_fdiff_*`
   / `validate_fdiff_*` scripts).
4. **`python-env`** — `uv sync --frozen`; `pip install --break-system-packages`; the ruff-format gate;
   the "eval"-filename classifier workaround.
5. **`residual-diagnosis`** — the discipline missing during the grass saga: state the reference basis
   and a falsifiable hypothesis first; confirm the comparison basis is correct before probing; time-box.
6. **`repo-commit`** — main-only workflow; pre-push checklist against the 5 CI gates (CI/format/docs/
   python/TagBot); signed vs unverified note.

(These must be created *by the coding agent in its own environment* — skills can't be authored from this
session. The steering prompt instructs it to do so.)

---

## 9. Orders — prioritized, with acceptance gates

**P0 — Working-practice reset (session 1, before feature work).** CLAUDE.md; doc consolidation + caps;
create the 6 skills; housekeeping. *Gate:* onboarding < 15k tokens; skills exist; `consolidate-memory`
run.

**P1 — Put S in the loop (the novelty).** Implement `AbstractSlowEmulator` concretely (port the Python
LightGBM+copula to Julia, or call it, per an ADR); wire into `run_coupled_cell`; resolve the growth
fork per §4; conserve carbon at the handoff (flux-then-integrate). *Gate:* S+F+E runs on Hainich;
carbon conserved to ~1e-6; coupled distribution matches offline S on the panel; **speed-up measured vs
the deterministic-F baseline.**

**P2 — Validate E against observations (parallel to P1).** Source FLUXNET/PLUMBER2 DE-Hai + `sfcwind`/
`ps` forcing; validate LE/H/T_skin; add a stability correction to `g_a`. *Gate:* LE/H/T_skin within
published PLUMBER2 error bands at ≥1 site; closure holds; diurnal cycle plausible.

**P3 — Multi-cell generalization.** Run coupled S+F+E on the biome-stratified 6000-cell set; held-out
cell **and** scenario eval; the LPJ_resilience battery (esp. the shuffle test + climate-dependent ACF).
*Gate:* per-cell error vs the seed1-vs-seed2 noise floor; resilience metrics preserved.

**P4 — Online coupling with SpeedyWeather (via Terrarium/NumericalEarth).** Implement S/F/E as Terrarium
`Abstract*` processes; couple through the external-land interface; rollout curriculum + noise injection;
multi-year free run; OOD warming at constant CO₂. *Gate:* stable coupled multi-year run — no drift, no
AC-gap/oscillation — conserving; gradients flow for online training.

**P5 — Reuse + licensing reconciliation (enables P4, start early).** New ADR reconciling self-contained
offline core vs Terrarium coupling substrate; document a good-faith EUPL↔AGPL↔MIT basis and proceed;
reverse the default to reuse-first.

**P6 — Nitrogen limitation (research track; lowest priority, after P1–P4).** Prototype a learned
differentiable N-downregulation closure on Vcmax/photosynthesis trained vs N-fertilization + FLUXNET, to
lift the constant-CO₂ ceiling — the path to "better than LPJmL-FIT." Alternative: scope porting a process
N cycle. The agent chooses the approach and records it in an ADR.

Dependencies: P0 first; P1 ∥ P2 ∥ P5; P3 after P1; P4 after P3 + P5. P6 last.
