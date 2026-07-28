### Changed

- **The licensing question is CLOSED; reuse is authorized; citation is the requirement
  ([ADR 0081](docs/decisions/0081-owner-closes-licensing-reuse-authorized.md)).** The owner is a member of
  **both** upstream groups — the **LPJmL-FIT** group and **TUM-PIK-ESM**, which hosts SpeedyWeather.jl,
  Terrarium.jl and LPJmL-hybrid-photosynthesis — the fact missing from every prior analysis. So those models
  are reused freely, with no licence analysis, licence decision or upstream re-audit needed, including for P4
  online coupling. `LICENSE` is no longer a blocker or a tracked TODO. **The one standing obligation is
  transparent citation** across four surfaces kept in agreement: the register (now
  `docs/third_party_licensing.md` — *reuse + citation*, reframed from a licence gate), `CITATION.cff`,
  `docs/src/refs.bib`, and the header of every source file with derived content — stated *accurately*, neither
  overstated nor omitted. The `dependency-license-gate` skill is replaced by **`reuse-citation`**, and the
  licensing sections of `CLAUDE.md`, `MEMORY.md` and `lines/O/STATE.md` collapse to "closed, cite, move on" so
  no future session relitigates it. ADR 0080 is retained for its verified upstream register and its
  depend-don't-vendor hygiene, with only its §4 owner-action checklist superseded. **Not reopened, and not
  licence caveats:** NeuralCrop.jl stays method-only (CC-BY-NC, a different author outside both groups) and
  runtime `[deps]` stays empty (ADR 0014 — a *technical* constraint from the GitHub-egress-free compute nodes,
  so Terrarium/SpeedyWeather still enter as `[weakdeps]` + an extension).
