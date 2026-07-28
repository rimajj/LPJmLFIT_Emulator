# LINE E — Component E vs observations (branch `line/E`, worktree `wt-E`) — P2

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/E/JOURNAL.md` (append-only). Decisions: ADR block **0070–0079**.
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## NEXT — start here

**E1 — source the observational reference (this line is data-bounded; unblock that first).**
Component E's LE / H / T_skin are currently `[ASSUMPTION]`-tagged: *"physically plausible but invented
quantities validated only out-of-model"*. The whole line exists to convert that into `[VERIFIED]`.

1. Acquire **PLUMBER2** (preferred — the ~170-site quality-controlled FLUXNET subset, Ukkola et al. 2022 ESSD
   14 449) or **FLUXNET2015 Tier-1** for **DE-Hai** (= Hainich, the prototype cell), plus 2–3 sites spanning
   the other prototype biomes. Format: NetCDF `*_Flux.nc` + `*_Met.nc`, half-hourly.
2. Land it under the path `config/paths.yaml` already reserves and fill in the TODO:
   `data.energy_reference: ${data.root}/fluxnet_plumber2   # TODO: external FLUXNET/PLUMBER2 site data`.
3. Write a loader + a first sanity report (site-mean LE/H/Rn, data coverage, gap-fill flags).

The variable/unit schema is **already frozen** in `DESIGN.md` §(energy reference): `LE [W/m²], H [W/m²],
Ts/T_skin [K], Rn [W/m²]` plus the forcing E needs — `SWdown, LWdown [W/m²], Tair [K], qair [kg/kg],
wind [m/s], psurf [Pa], precip`. Aggregate to daily mean **and retain the sub-daily cycle** (the diurnal test).

*Gate:* DE-Hai half-hourly LE/H/Rn/Ts loaded, unit-checked, and summarized; `paths.yaml` no longer a TODO.
If acquisition needs a registration/download the agent cannot perform, record exactly what is needed in
`lines/E/JOURNAL.md` + this NEXT block and proceed to **E2** (which is fully self-contained).

## Scope + ownership (ADR 0029)

**You own (exclusive):**
- `src/components/energy.jl`, `test/testitems/energy_closure_tests.jl`
- the energy / `sfcwind` / `ps` keys in `config/paths.yaml`
- new `scripts/` for the remap + the PLUMBER2 validation (name them clearly, e.g. `remap_*`, `validate_e_*`)
- `lines/E/*`, `changelog.d/E-*.md`, ADRs 0070–0079

**Do NOT touch:** `src/components/slow.jl`, `src/drf.jl`, `src/climbuf.jl` (line S) · `src/run.jl`,
`src/interface.jl` (line M owns the coupling seam — request changes through M) · `ext/` (line O) ·
`Project.toml` (integrator; a NetCDF reader belongs in the **Python/script** env or a weakdep, never runtime
`[deps]` — ADR 0014).
Shared, additive-only: `src/LPJmLFITEmulator.jl` (inside `# ── line E ──`), `CLAUDE.md`, `MEMORY.md`.

**SLURM tag prefix:** `E-` · other lines' `/p/tmp` artifacts are **read-only**.

## The contract you must not silently break (E → M)

Line M runs your closure inside the coupled loop: the `SEBEnergyClosure(...)` constructor + the `solve!`
signature are **frozen**. New physics is **opt-in, default byte-identical** (guardrail 4) — the coupled/biome
baselines and `energy_closure_tests.jl` must not move until a change is deliberately enabled, and flipping a
default is an integration point with M.

## Status (2026-07-28)

- `SEBEnergyClosure` (self-contained, ADR 0017 — no Terrarium runtime dep) closes `Rn = LE + H + G` to
  **1.4e-14 W/m²** (13,824 cases; ForwardDiff-vs-FD; Float32 clean), H as the residual.
- Monin–Obukhov `g_a` stability correction is **ON by default**; the aerodynamic identity checks to ~3e-11.
- Emergent behaviour is climate-correct: Bowen ordering across 5 biomes (tropical ~0.10 → semi-arid
  H-dominated), and the coupled Hainich decade reproduces the **2018 drought** (summer Bowen 0.89 vs ~0.2).
- **Not done:** no observational validation, and two forcings E needs are not model-ready.
- Honest scope currently recorded: wind is held **constant** and psurf is effectively fixed (the LPJmL run
  never used them — `photosynthesis.c` hard-codes `p=1e5`), and LE uses the **vaporization** λ for all ET
  (no snow-sublimation split).

## Milestones

- **E1** Source PLUMBER2 / FLUXNET2015 for DE-Hai + biome sites; fill `paths.yaml`. *(NEXT, above)*
- **E2** **The named blocker — cross-grid remap for `sfcwind` + `ps`.** The raw GCM / GSWP3-W5E5 `.clm` are a
  **different, int16, re-ordered grid** from the model-grid `_test.clm`: **raw cell 42490 ≠ Hainich**. Write a
  lat/lon remap onto the orderA grid (sources per `config/paths.yaml`: `ssp370_raw_gcm` MPI-ESM1-2-HR NetCDFs
  incl. `sfcwind`, and GSWP3-W5E5 obsclim). *Gate:* remapped wind/psurf at Hainich matches an independent
  lat/lon lookup, and a round-trip on a known cell reproduces the model-grid `_test.clm` value for a variable
  present in both.
- **E3** **Sublimation-λ split** — use `LAMBDA_SUBLIMATION` when the flux leaves snow/ice rather than
  vaporization for everything (`conservation.jl` already exports both constants). Opt-in, default
  byte-identical.
- **E4** **Validate LE / H / T_skin within PLUMBER2 error bands** at ≥1 site, plus the diurnal cycle, with real
  wind + psurf from E2. Per `DEVELOPMENT_PLAN` §7: **H is the residual and PLUMBER2 flags it as the hardest
  flux to get right — validate it hardest.** *This is the P2 gate.* Then flip `MEMORY.md`'s `[ASSUMPTION]` to
  `[VERIFIED]` with the site + bands quoted.
- **E5** Feed the real wind/psurf back to line M as an integration point (the coupled runs currently use
  constants), and record the improvement.

## Line-local gotchas

- **Parse the `.clm` header, never assume the layout** — v3 (`LPJCLIM`, 7 ints + 3 floats + datatype,
  HDR=51, float32) vs v2 (no datatype field, HDR=43, **int16 with `scalar 0.1` ⇒ °C×10**). Reuse
  `scripts/build_transient_boundary.py::open_clm`; that function already handles both.
- `AtmForcing.tair` is **Kelvin**; F converts with `tair − 273.15`. PLUMBER2 `Tair` is also K — check, don't assume.
- `swc` output from the C run is **fractional** saturation, not mm (`swe`/`rootmoist` are mm).
- The 5-biome test tolerates LE ≥ −2 W/m² (a bounded smooth-min undershoot in the fully water-depleted corner,
  not a sign bug) — don't "fix" that by changing the physics without reading the comment.
- Any long job → SLURM (`scripts/sbatch_python.sh` / `sbatch_julia.sh`); the login node is hook-blocked.
