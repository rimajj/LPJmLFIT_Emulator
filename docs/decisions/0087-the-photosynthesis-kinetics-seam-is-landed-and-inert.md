# ADR 0087 — The photosynthesis kinetics seam is landed, bit-identical, and INERT: worth 0 % until line M hoists it

* **Status:** accepted
* **Date:** 2026-08-18
* **Line:** O (online coupling) · ADR block 0080–0089
* **Implements:** the **(d) SPLIT** agreed between lines M and O against [ADR 0084](0084-the-speed-gate-exists-and-the-38x-is-reproduced-and-worse.md) §5
  — M keeps `solve_lambda`, O takes the kinetics. Both halves of the exchange are recorded verbatim at the
  top of `lines/O/STATE.md` and `lines/M/STATE.md`.
* **Does not supersede anything.** No measurement in this repo moves, because nothing this ADR lands
  changes a single output value.

---

## 1. What was landed

Two edits to `src/fdiff.jl`, both inside `photosynthesis`, plus one new test file:

1. **`FDiff.photo_kinetics(p::PhotoParams, temp) -> (fac_kin, gammastar)`** — the temperature-dependent
   Michaelis–Menten kinetics (`photosynthesis.c:66-70`), lifted verbatim out of the kernel body: operand
   for operand, in the same order, with the same `one(temp)` type promotion.
2. **A `kin` keyword argument on `photosynthesis`,** defaulting to `photo_kinetics(p, temp)`. A caller that
   evaluates the kernel repeatedly at ONE temperature can hoist the call out of its loop and pass the
   result; a caller that does nothing gets exactly today's behaviour.
3. **`test/testitems/o_photo_kinetics_seam_tests.jl`** — the equivalence gate (§3).

## 2. Why the seam exists, and what it is worth

`ko`, `kc` and `tau` — hence the only two quantities the kernel actually consumes downstream, `fac_kin`
and `gammastar` — depend on **`temp` alone**. Not on λ, not on `apar`, not on `vm`, not on the individual.
ADR 0084's profile nevertheless attributes **26.5 %** of total emulator runtime to the
`^(::Float64,::Float64)` those three `q10^` calls dominate, because the λ solve re-evaluates them on each
of its **~78 kernel calls per individual-day**.

**So the payoff is not computing them once — it is not computing them 78 times.** Those 78 calls all
originate in the `g(λ)` residual closure **inside `solve_lambda`**, which is line M's under
`CLAUDE.md` §9 Gap 1. Hence:

| | |
|---|---|
| O's half (this ADR) | factor the arithmetic out + open the `kin` seam. **Bit-identical at all 9 call sites. Worth 0 %.** |
| M's half (2 lines, M's file) | hoist `kin = photo_kinetics(p.photo, temp)` above the closure, pass `; kin = kin` into it. **This is the part that turns 78 evaluations into 1.** |
| expected together | **≈1.36×** on arm F (`1/(1−0.265)`), zero fidelity risk — the same arithmetic, evaluated once |

⚠ **Stated plainly because the temptation to round it up is the whole risk here: line O has not measured a
speed-up and does not claim one.** Loop-invariant code motion needs the loop, and the loop is M's. The
1.36× is arithmetic O put to M, not a benchmark O ran. Anyone reading this ADR as "the hoist landed, so
the emulator got 1.36× faster" has it wrong — the correct status is **landed and inert, on purpose.**

## 3. The equivalence argument, and why it is bitwise

The claim "zero fidelity risk" rests on exactly one premise: **a caller passing a hoisted `kin` gets
bitwise the same four return values as the default path.** That premise is the new testitem, not a
narrative:

* **`===`, never `≈`.** On `Float64`/`Float32`, `===` is bit comparison (`0.0 === -0.0` is `false`). A
  tolerance would defeat the purpose — bit-identity is precisely what lets M's hoist ship with no flag.
* **The sweep is 3 240 kernel calls** over both photosynthetic pathways, six temperatures spanning −15 to
  40 °C, three daylengths, five λ across the solver bracket `[0.02, 0.85]`, three `apar` including 0, and
  all three call shapes the code uses: the Vcmax pass (`comp_vm = true`), the λ-residual pass
  (`comp_vm = false` at the Vcmax the first pass produced — the call the hoist is *for*), and the
  learned-Vcmax hook (`vm_scale`). The count is asserted, so a silently-empty sweep fails.
* **The SLA-capped Vcmax branch is included** (`issla = true`), because that cap reads `temp` too and is
  the branch LPJmL-FIT's `individual:true` mode actually runs.
* **Float32 params are included** — the SpeedyWeather-coupling type. The seam is bit-identical there
  too, and the gate also pins what the kernel actually returns for them, which is not what anyone
  would guess: see §5.
* **A frozen local copy of the pre-refactor arithmetic** is asserted against `photo_kinetics`. This is the
  part that keeps paying: a future edit to the kinetics fails *here*, with the operand printed, instead of
  surfacing as a moved ReferenceTests baseline three files away.

**No flag.** Guardrail 4 asks for opt-in, default byte-identical; a bit-identical refactor is already
byte-identical by construction, and M's reply said so explicitly — *"I will not ask for a flag on a hoist
that is provably bit-identical; a flag nobody would ever switch off is maintenance cost"* (M's own
ADR 0138 reasoning). Guardrail 4's corollary — an opt-in flag whose default is known wrong is a defect on
a timer — is the reason not to invent one here.

## 4. Consequences

* **For line M:** the seam is in `main`; the two-line hoist inside `solve_lambda` is unblocked and needs
  nothing further from O. The equivalence testitem already gates the property M's hoist depends on, so M
  does not need to re-derive it.
* **For the speed record:** the emulator's cost is **unchanged** — still 1.2329 core-s per cell-year at
  cell 42490, npatch 25, one core (ADR 0084), and still to be read with ADR 0086's patch-count warning
  attached, because that verdict is at 25 patches and production is ~500.
* **Gates:** the diff touches `src/**`, so it runs `CI` (4 Julia jobs) and `format` on the branch and
  `docs` on `main` having never run on the branch. All three were run locally first — Runic 1.7.0 (the CI
  version) clean, the docs built with linkcheck off, and the mermaid render checked in the built HTML
  rather than inferred from a green build (ADR 0091's amendment).

## 5. ⭐ AN UNRELATED FINDING THE GATE PRODUCED: the photosynthesis kernel computes in Float64 even when it is parameterised Float32 — and that is the *only* P4 preparation this repo has in code

This was not sought. The seam's Float32 assertion failed, and the reason is a property of the kernel that
predates the seam entirely. Measured (`PhotoParams{Float32}`, Float32 forcing throughout):

| expression | type |
|---|---|
| `p.q10ko` | `Float32` |
| `temp - 25` | `Float32` |
| **`(temp - 25) * 0.1`** | **`Float64`** ← the literal `0.1` is a Float64 |
| `p.q10ko ^ that` | `Float64` |
| `photo_kinetics(p, 18.0f0)` | `Tuple{Float64, Float64}` |
| **`temp_stress(TempStressParams{Float32}(), …)`** | **`Float64`** — *this seam is not involved at all* |
| `photosynthesis(...)` → `(agd, rd, vm, adtmm)` | **all four `Float64`** |

**The promotion is not in the seam and not specific to the kinetics.** `temp_stress` promotes identically
with no involvement from anything landed here, so this is the kernel's Float64 literals in general. The
proof that the seam is innocent is already in the gate: the frozen pre-refactor copy returns the *same
Float64 bits*, and `===` is type-sensitive, so a type change would have failed that comparison rather than
the separate purity assertion.

**Why this matters, and it is line O's own problem.** `lines/O/STATE.md` records *"Float32 readiness is
already gated — 4 testitems assert Float32 type-stability explicitly labelled '(SpeedyWeather-coupling
type)'; that is the only P4 preparation that exists in code today."* Those four gates, and
`fdiff_physics_tests.jl`'s `@test c.npp isa Float32`, are all satisfied — because the **output structs**
are Float32-parameterised and convert on assignment. **They do not gate the arithmetic**, and the
arithmetic is double precision. So:

* **O3c** — the photosynthesis spike behind `Terrarium.AbstractPhotosynthesis{NF}` — would run its kernel
  in Float64 at `NF = Float32`, silently. Any expectation that the online configuration gets Float32 speed
  or memory in the hot kernel is currently **unfounded**.
* The claim to make from here on is *"the interface types are Float32-clean; the kernel arithmetic is
  not"*, not *"Float32 readiness is gated"*.

**Not fixed here, deliberately, and this is the guardrail-4 reasoning rather than a fence excuse.** Making
the literals type-generic would make a Float32 run compute in single precision, which **moves numbers** —
it is a numerical change needing its own opt-in, its own re-measure and its own baseline discussion, not a
tidy-up to ride along on a bit-identical refactor. It is also in `src/fdiff.jl` beyond the one function O
was handed. **Pinned instead:** the gate asserts the Float64 promotion *as measured*, so a future
single-precision change fails this test and lands the reader on this section — which is the desired
behaviour, not an obstacle.

⚠ And the method note worth keeping: **the failing assertion was mine and the finding is real.** The
correct response to a red assertion in a refactor's own gate is to establish which of the two it is —
"the refactor broke something" or "the assertion claimed something the code never did" — before touching
either. Here the whole rest of the suite (279 076 assertions, every ReferenceTests baseline, the
numerical-regression baseline) was green and only the new purity claim failed, which localises it
immediately.

## 6. What this ADR does NOT do

* It does not touch `solve_lambda`, the λ bracket, `nlambda`, or the `lambda_vm_gp` /
  `gp_stand_leafon_basis` flags parked inside the solve (ADR 0136) — that whole region stays M's, which
  was M's substantive reason for keeping it: an optimiser who flattened the solver would silently retire a
  faithfulness control.
* It does not settle ADR 0084 §3's finding that **GPP is non-monotone in `nlambda`**, i.e. that 25
  iterations are not evidence of convergence. That is in M's queue, with M's correction adopted:
  convergence is a statement about **λ**, not about GPP.
* It changes no physics, no parameter, and no baseline.
