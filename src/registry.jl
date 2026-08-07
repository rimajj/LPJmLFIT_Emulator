# Component/flux registry — the SOURCE OF TRUTH for the code-derived data-flow diagrams
# (ENGINEERING_STANDARDS §5). `scripts/gen_diagrams.jl` reads THIS and emits Mermaid; CI fails if the
# committed diagram is stale (`git diff --exit-code`). Curated diagrams mirror this by hand; if this
# changes, the derived diagram changes and acts as a diff alarm to update the curated one.

"A model component (node in the data-flow graph)."
Base.@kwdef struct Component
    id::Symbol           # :S, :F, :E, :ATM
    name::String
    kind::Symbol         # :ml, :physics, :hybrid, :external
    timescale::Symbol    # :annual, :daily, :subdaily
    description::String
end

"""
A directed flux/handoff (edge). `payload` names the interface struct; `conserved` flags the hard constraint.

`payload_type` names the `src/interface.jl` struct this edge actually carries (`:SToF`, `:FToE`, …), or
`nothing` for an edge with no single struct. It is what makes the FULL data-flow diagram
(`docs/src/generated/dataflow_full.mmd`) *code-derived*: the field list drawn on the edge comes from
`fieldnames(payload_type)`, so adding a field to an interface struct changes the diagram and the
staleness gate (`diagram_registry_tests.jl`) fails until the committed copy is regenerated. The
free-text `payload` string above is the legacy hand-written label used by the two older diagrams; it is
deliberately NOT reformatted, so those stay byte-identical (guardrail 4).
"""
Base.@kwdef struct Flux
    from::Symbol
    to::Symbol
    payload::String
    timescale::Symbol
    conserved::Bool
    payload_type::Union{Nothing, Symbol} = nothing
end

"The components S / F / E (+ the atmosphere ATM). Mirrors DESIGN.md §0 table."
const COMPONENTS = [
    Component(
        id = :S, name = "Slow distribution emulator", kind = :ml, timescale = :annual,
        description = "p(traits,size | drivers,state) + count N; allocates delivered NPP (flux-then-integrate)"
    ),
    Component(
        id = :F, name = "Fast physical core (LPJmL-FIT)", kind = :physics, timescale = :daily,
        description = "photosynthesis→GPP→NPP, water balance, snow, soil thermal; conserving"
    ),
    Component(
        id = :E, name = "Energy-balance + skin-T closure", kind = :hybrid, timescale = :subdaily,
        description = "solve T_skin; close Rn=LE+H+G (H residual); self-contained SEB (ADR 0017)"
    ),
    Component(
        id = :ATM, name = "Atmosphere (ESM)", kind = :external, timescale = :subdaily,
        description = "SpeedyWeather.jl / FLUXNET forcing; NEE diagnostic-only (no carbon cycle)"
    ),
]

"The interface contract as edges (DESIGN.md §8). Kept in sync with `src/interface.jl` payload types."
const FLUXES = [
    Flux(from = :S, to = :F, payload = "SToF (LAI,height,z0,rootdepth,Vcmax,FPC,albedo)", timescale = :annual, conserved = false, payload_type = :SToF),
    Flux(from = :S, to = :E, payload = "SToE (albedo,z0,canopy structure)", timescale = :annual, conserved = false, payload_type = :SToE),
    Flux(from = :F, to = :S, payload = "FToS (bm_inc, stresses, soil moisture)", timescale = :annual, conserved = true, payload_type = :FToS),
    Flux(from = :F, to = :E, payload = "FToE (LE=λ·ET; GPP,NPP,Rh,firec,flux_estabc; G)", timescale = :daily, conserved = true, payload_type = :FToE),
    Flux(from = :E, to = :F, payload = "EToF (T_skin, G(T_skin), g_a)", timescale = :daily, conserved = false, payload_type = :EToF),
    Flux(from = :E, to = :ATM, payload = "EToATM (LE,H,G,T_skin,NBP_atm,z0)", timescale = :subdaily, conserved = true, payload_type = :EToATM),
    Flux(from = :ATM, to = :F, payload = "AtmForcing (SW,LW,Tair,qair,wind,psurf,precip,CO₂)", timescale = :subdaily, conserved = false, payload_type = :AtmForcing),
    Flux(from = :ATM, to = :E, payload = "AtmForcing (+wind,psurf — NEW)", timescale = :subdaily, conserved = false, payload_type = :AtmForcing),
]

# ═════════════════════════════════════════════════════════════════════════════════════════════════════
# FULL DATA-FLOW GRAPH — every dataset, not just the runtime S↔F↔E seam.
#
# `COMPONENTS`/`FLUXES` above describe the *runtime coupling seam only*. The owner also needs to see
# where the data COMES FROM: what LPJmL-FIT itself is driven by, what each component reads at run time,
# and which of the C model's outputs become the emulator's training data versus its validation oracle.
# That is the graph below; `scripts/gen_diagrams.jl` renders it to
# `docs/src/generated/dataflow_full.mmd` and `docs/src/explanation/dataflow.md` embeds it.
#
# WHY IT CANNOT GO STALE (three independent gates in `test/testitems/diagram_registry_tests.jl`):
#   1. staleness  — the committed .mmd is regenerated and compared byte-for-byte.
#   2. reflection — every runtime edge's field list is `fieldnames(payload_type)`, so a change to an
#                   `src/interface.jl` struct changes the diagram.
#   3. provenance — every `path_key` here must resolve to a real key in `config/paths.yaml`, so a
#                   renamed/removed input cannot leave a phantom box on the diagram.
# ═════════════════════════════════════════════════════════════════════════════════════════════════════

"""
A node in the full data-flow graph: a dataset, a model, a derived table, or a learned artifact.

`stage` groups nodes into the rendered subgraphs (see `STAGES`); `kind` picks the visual style;
`detail` is the honest contents line (variables, columns, caveats). `path_key` is a dotted key into
`config/paths.yaml` (`""` when the node is not a file on disk) and is gate-checked — see `DATA_NODES`.
"""
Base.@kwdef struct DataNode
    id::Symbol
    label::String
    kind::Symbol         # :dataset :model :table :artifact :ml :physics :hybrid :external
    stage::Symbol        # a key of STAGES
    detail::String
    path_key::String = ""
end

"""
A directed edge of the full data-flow graph.

If `payload_type` is set, the rendered label is DERIVED from `fieldnames` of that `src/interface.jl`
struct rather than from `label` — that is gate 2 above. Otherwise `label` is used verbatim.
`style` selects the arrow: `:solid` (data moves), `:thick` (a conserved handoff), `:dashed`
(offline/validation path — not part of a coupled run).
"""
Base.@kwdef struct DataEdge
    from::Symbol
    to::Symbol
    label::String = ""
    payload_type::Union{Nothing, Symbol} = nothing
    timescale::Symbol = :none
    style::Symbol = :solid
end

"""
The rendered subgraph groups of the full data-flow graph, in draw order: `stage => title`.

Ordered so the diagram reads left→right as *provenance → training → runtime*: the raw inputs LPJmL-FIT
consumes, the C model, its outputs, the derived tables, the learned artifacts, then the coupled
emulator and the atmosphere it talks to.
"""
const STAGES = [
    :input => "Input data — what drives LPJmL-FIT",
    :input_extra => "Extra forcing — the energy balance only (LPJmL-FIT ignores these)",
    :lpjml => "LPJmL-FIT (the C reference model / oracle)",
    :truth => "LPJmL-FIT output = ground truth",
    :derived => "Derived tables (training + per-cell provisioning)",
    :artifact => "Learned artifacts (versioned, pinned)",
    :runtime => "The hybrid emulator at run time",
    :obs => "Independent observations",
]

"""
Every node of the full data-flow graph.

The `path_key` of each `:input`/`:truth` node is asserted to exist in `config/paths.yaml` by
`test/testitems/diagram_registry_tests.jl`, so this list cannot describe an input the project no
longer has. Contents lines record the traps that matter scientifically — that the soil-depth input is
read and then discarded, that CO₂ is deliberately frozen and invisible to the emulator, that the
annual tree table only carries stems above 5 m.
"""
const DATA_NODES = [
    # ── Input data consumed by the C model ───────────────────────────────────────────────────────
    DataNode(
        id = :GRID, label = "Grid (orderA)", kind = :dataset, stage = :input,
        detail = "67 420 cells at 0.5°, 54 020 tree-bearing; .clm v3 float32",
        path_key = "lpjml.inputs.coord"
    ),
    DataNode(
        id = :SOILCODE, label = "Soil code", kind = :dataset, stage = :input,
        detail = "1 byte per cell, keys the texture class into par/soil_20m.js",
        path_key = "lpjml.inputs.soil"
    ),
    DataNode(
        id = :SOILDEPTH, label = "Soil depth (Pelletier)", kind = :dataset, stage = :input,
        detail = "READ THEN DISCARDED — newgrid.c:282 forces every cell to 20 m",
        path_key = "lpjml.inputs.soildepth"
    ),
    DataNode(
        id = :CLIM_HIST, label = "Historical climate (obsclim GSWP3-W5E5)", kind = :dataset, stage = :input,
        detail = "daily noleap 1901-2019: tas, pr, rsds, lwnet (net LW), huss",
        path_key = "lpjml.inputs.historical"
    ),
    DataNode(
        id = :CLIM_SSP, label = "Warming climate (MPI-ESM1-2-HR ssp370)", kind = :dataset, stage = :input,
        detail = "daily 2015-2100, same 5 variables; MIXED .clm versions (huss v3, rest v2 int16 x0.1)",
        path_key = "lpjml.inputs.ssp370"
    ),
    DataNode(
        id = :CO2, label = "CO₂ concentration (annual)", kind = :dataset, stage = :input,
        detail = "HELD CONSTANT from 2020 on purpose (ADR 0004); the emulator never sees it (ADR 0107)",
        path_key = "lpjml.inputs.historical.co2"
    ),
    DataNode(
        id = :PARAMS, label = "Parameter files (.js)", kind = :dataset, stage = :input,
        detail = "lpjmlfit.js, param_lpjmlfit.js, par/pft_lpjmlfit.js, par/soil_20m.js; read via cpp",
        path_key = "lpjml.run_config"
    ),
    DataNode(
        id = :RESTART, label = "Spin-up-end restart", kind = :dataset, stage = :input,
        detail = "restart_1999.lpj — 1000-yr spin-up state; also carries the per-cell RNG seeds",
        path_key = "lpjml.restart_historical_spinup_end"
    ),
    # ── The C model ──────────────────────────────────────────────────────────────────────────────
    # ⚠ The patch count is a RUN SETTING, not a property of the model — the current training runs use
    # 25 and a planned regeneration uses 500. Never state a bare number here as if it were fixed.
    DataNode(
        id = :LPJML, label = "LPJmL-FIT v5.6.004", kind = :model, stage = :lpjml,
        detail = "individual=true, carbon-only, stochastic gap model (-DPERMUTE); N replicate patches per cell (25 in the current training runs)",
        path_key = "lpjml.binary"
    ),
    # ── Its outputs = the ground truth ───────────────────────────────────────────────────────────
    DataNode(
        id = :IND, label = "Tree table 'ind' (annual)", kind = :dataset, stage = :truth,
        detail = "29 columns per individual; ONLY stems taller than 5 m; 6 significant digits",
        path_key = "lpjml.ind_csv_historical_seed1"
    ),
    DataNode(
        id = :GFLUX, label = "globalflux (annual)", kind = :dataset, stage = :truth,
        detail = "cell carbon + water budget terms — the closure check",
        path_key = "lpjml.globalflux_csv_historical_seed1"
    ),
    DataNode(
        id = :DAILY, label = "Daily fields (NetCDF)", kind = :dataset, stage = :truth,
        detail = "NPP/GPP, vegc, whc_nat, rootmoist, LAI_STAND, per-PFT daily grass GPP/NPP",
        path_key = "lpjml.daily_output_run_root"
    ),
    # ── Derived tables ───────────────────────────────────────────────────────────────────────────
    DataNode(
        id = :IND_PQ, label = "ind parquet (per seed)", kind = :table, stage = :derived,
        detail = "frozen 29-column schema, both random seeds = the run-to-run noise floor",
        path_key = "data.prior_derived"
    ),
    DataNode(
        id = :CELLFEAT, label = "Cell/year features", kind = :table, stage = :derived,
        detail = "49 climate/soil/ecology boundary columns per cell and year",
        path_key = "data.slow_table"
    ),
    DataNode(
        id = :SLOWTAB, label = "Runtime-consistent training table", kind = :table, stage = :derived,
        detail = "one row per cell-year in the SAME order as flux_feature_vector (ADR 0023)",
        path_key = "data.slow_table"
    ),
    DataNode(
        id = :CELLPROV, label = "Per-cell provisioning", kind = :table, stage = :derived,
        detail = "soil column (whcs, root distribution), starting tree roster, n_init, age0",
        path_key = "data.fast_validation"
    ),
    # ── Learned artifacts ────────────────────────────────────────────────────────────────────────
    DataNode(
        id = :DRFART, label = "Count/size forest (.drf)", kind = :artifact, stage = :artifact,
        detail = "zero-dependency quantile regression forest — how many trees, how big",
        path_key = "artifacts.models"
    ),
    DataNode(
        id = :RCOPART, label = "Recruit-trait copula (.rcop)", kind = :artifact, stage = :artifact,
        detail = "Gaussian copula over the 4 live trait axes — which trees establish",
        path_key = "artifacts.models"
    ),
    # ── Extra forcing the C model never used ─────────────────────────────────────────────────────
    # Deliberately its OWN stage, not `:input`: putting it in the box headed "what drives LPJmL-FIT"
    # would assert the opposite of the truth — the C model has no wind or surface-pressure input at all.
    DataNode(
        id = :WINDPS, label = "Wind + surface pressure", kind = :dataset, stage = :input_extra,
        detail = "NEW inputs LPJmL-FIT ignores; needed by the energy balance (ADR 0071)",
        path_key = "lpjml.energy_extra_inputs.obsclim_dir"
    ),
    # ── Runtime components (same ids as COMPONENTS, so all diagrams agree) ───────────────────────
    DataNode(
        id = :S, label = "S — slow emulator", kind = :ml, stage = :runtime,
        detail = "annual: how many trees, of which traits and sizes; allocates the carbon F delivered",
    ),
    DataNode(
        id = :F, label = "F — fast physical core", kind = :physics, stage = :runtime,
        detail = "daily: photosynthesis, water balance, snow, soil heat; differentiable, conserving",
    ),
    DataNode(
        id = :E, label = "E — energy balance + skin temperature", kind = :hybrid, stage = :runtime,
        detail = "sub-daily: solves the surface temperature and closes net radiation = LE + H + G",
    ),
    DataNode(
        id = :ATM, label = "Atmosphere", kind = :external, stage = :runtime,
        detail = "offline: tower or reanalysis forcing; online: SpeedyWeather.jl",
    ),
    # ── Independent observations ─────────────────────────────────────────────────────────────────
    DataNode(
        id = :OBS, label = "Flux towers (PLUMBER2)", kind = :dataset, stage = :obs,
        detail = "9 sites, half-hourly: observed LE, H, net radiation, surface temperature",
        path_key = "data.energy_reference"
    ),
]

"""
Every edge of the full data-flow graph.

Three kinds of arrow, and the distinction is the point of the diagram: `:solid`/`:thick` edges move
data inside a coupled run (`:thick` = a conserved handoff), while `:dashed` edges are the OFFLINE
paths — training the emulator on the C model's output, and scoring it against the C model or against
observations. A dashed edge never runs during a coupled simulation.
"""
const DATA_EDGES = [
    # inputs → C model
    DataEdge(from = :GRID, to = :LPJML, label = "cell coordinates"),
    DataEdge(from = :SOILCODE, to = :LPJML, label = "texture class"),
    DataEdge(from = :SOILDEPTH, to = :LPJML, label = "ignored in this config"),
    DataEdge(from = :CLIM_HIST, to = :LPJML, label = "5 daily variables", timescale = :daily),
    DataEdge(from = :CLIM_SSP, to = :LPJML, label = "5 daily variables", timescale = :daily),
    DataEdge(from = :CO2, to = :LPJML, label = "annual, frozen after 2019", timescale = :annual),
    DataEdge(from = :PARAMS, to = :LPJML, label = "PFT + soil parameters"),
    DataEdge(from = :RESTART, to = :LPJML, label = "initial state + RNG seeds"),
    # C model → its outputs
    DataEdge(from = :LPJML, to = :IND, label = "one row per tree per year", timescale = :annual),
    DataEdge(from = :LPJML, to = :GFLUX, label = "budget terms", timescale = :annual),
    DataEdge(from = :LPJML, to = :DAILY, label = "daily fields", timescale = :daily),
    # outputs → derived tables (offline)
    DataEdge(from = :IND, to = :IND_PQ, label = "convert + index", style = :dashed),
    DataEdge(from = :IND_PQ, to = :SLOWTAB, label = "targets: counts, sizes, traits", style = :dashed),
    DataEdge(from = :CELLFEAT, to = :SLOWTAB, label = "bioclimatic boundary tail", style = :dashed),
    DataEdge(from = :DAILY, to = :SLOWTAB, label = "soil moisture + stand LAI features", style = :dashed),
    DataEdge(from = :CLIM_HIST, to = :CELLFEAT, label = "climate summaries", style = :dashed),
    DataEdge(from = :CLIM_SSP, to = :CELLFEAT, label = "climate summaries", style = :dashed),
    DataEdge(from = :DAILY, to = :CELLPROV, label = "soil water capacity per layer", style = :dashed),
    DataEdge(from = :IND_PQ, to = :CELLPROV, label = "starting roster + mean age", style = :dashed),
    # training → artifacts (offline)
    DataEdge(from = :SLOWTAB, to = :DRFART, label = "fit forest", style = :dashed),
    DataEdge(from = :SLOWTAB, to = :RCOPART, label = "fit copula", style = :dashed),
    # artifacts + provisioning → runtime
    DataEdge(from = :DRFART, to = :S, label = "pinned artifact"),
    DataEdge(from = :RCOPART, to = :S, label = "pinned artifact"),
    DataEdge(from = :CELLPROV, to = :S, label = "n_init, age0, boundary row"),
    DataEdge(from = :CELLPROV, to = :F, label = "soil column + starting canopy"),
    DataEdge(from = :WINDPS, to = :E, label = "wind, surface pressure", timescale = :daily),
    # the runtime seam — labels DERIVED from the interface structs (gate 2)
    DataEdge(from = :S, to = :F, payload_type = :SToF, timescale = :annual),
    DataEdge(from = :S, to = :E, payload_type = :SToE, timescale = :annual),
    DataEdge(from = :F, to = :S, payload_type = :FToS, timescale = :annual, style = :thick),
    DataEdge(from = :F, to = :E, payload_type = :FToE, timescale = :daily, style = :thick),
    DataEdge(from = :E, to = :F, payload_type = :EToF, timescale = :daily),
    DataEdge(from = :E, to = :ATM, payload_type = :EToATM, timescale = :subdaily, style = :thick),
    DataEdge(from = :ATM, to = :F, payload_type = :AtmForcing, timescale = :subdaily),
    DataEdge(from = :ATM, to = :E, payload_type = :AtmForcing, timescale = :subdaily),
    # validation (offline)
    DataEdge(from = :IND_PQ, to = :S, label = "score trees + traits", style = :dashed),
    DataEdge(from = :DAILY, to = :F, label = "score daily fluxes (oracle)", style = :dashed),
    DataEdge(from = :GFLUX, to = :F, label = "score carbon + water closure", style = :dashed),
    DataEdge(from = :OBS, to = :E, label = "score LE, H, surface temperature", style = :dashed),
]
