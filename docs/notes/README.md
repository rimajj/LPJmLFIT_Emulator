# Engineering notes

Long-form working documents: design specifications, phase validation write-ups and data specifications.
**Not part of the published documentation website** — they are not built, link-checked or deployed, and
they trigger no CI gate.

They are *not* scratch files either. Source files and tests cite them by name and section number — for
example `docs/notes/phase3_fdiff_cbinary_validation.md` is referenced from `src/fdiff.jl` and about ten
test files, and its section numbers appear in committed baseline headers. Treat a section reference as
durable: renumbering a section in one of these breaks a pointer somewhere in the code.

| Note | What it covers |
|---|---|
| `phase1_p3b_water_closure.md` | The daily water balance and how its closure is verified |
| `phase2_slow_emulator.md` | The first slow-emulator prototype |
| `phase3_fdiff_spike.md` | The differentiable fast core's initial design; also the API summary for its submodules, which the strict docs build deliberately does not render |
| `phase3_fdiff_cbinary_validation.md` | The long-running validation of the fast core against the original C model, section by section. The most-cited note in the repo |
| `p1_s_in_loop_design.md` | Putting the slow emulator inside the coupled loop |
| `p4_online_coupling_design.md` | Coupling online to an atmosphere model |
| `slow_flux_conditioning_data_spec.md` | The data specification for what the slow emulator is conditioned on |
| `online_transient_boundary_climbuf.md` | The running climate buffer that keeps the slow emulator's bioclimate current during a coupled run |
| `sapwood_bg_design.md` | Below-ground sapwood in the growth path |
| `water_supply_perpft_design.md` | A per-plant-type water supply scheme (designed, deliberately not built — see the note itself for why) |

## Where else to look

- **Published documentation** → `docs/src/` (built site). Start at `docs/src/index.md`.
- **Decisions**, with rationale and alternatives → `docs/decisions/`.
- **What is in `docs/` generally** → `docs/README.md`.

These notes moved here from the top level of `docs/` on 2026-08-06. Append-only history
(`CHANGELOG.md`, `JOURNAL.md`, `docs/archive/**`) and the immutable decision records still show the old
`docs/<name>.md` paths, correctly describing where the files were when those entries were written.
