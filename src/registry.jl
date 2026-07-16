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

"A directed flux/handoff (edge). `payload` names the interface struct; `conserved` flags the hard constraint."
Base.@kwdef struct Flux
    from::Symbol
    to::Symbol
    payload::String
    timescale::Symbol
    conserved::Bool
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
        description = "solve T_skin; partition A=Rn−G into LE,H,G (H residual); reuse Terrarium.jl"
    ),
    Component(
        id = :ATM, name = "Atmosphere (ESM)", kind = :external, timescale = :subdaily,
        description = "SpeedyWeather.jl / FLUXNET forcing; NEE diagnostic-only (no carbon cycle)"
    ),
]

"The interface contract as edges (DESIGN.md §8). Kept in sync with `src/interface.jl` payload types."
const FLUXES = [
    Flux(from = :S, to = :F, payload = "SToF (LAI,height,z0,rootdepth,Vcmax,FPC,albedo)", timescale = :annual, conserved = false),
    Flux(from = :S, to = :E, payload = "SToE (albedo,z0,canopy structure)", timescale = :annual, conserved = false),
    Flux(from = :F, to = :S, payload = "FToS (bm_inc, stresses, soil moisture)", timescale = :annual, conserved = true),
    Flux(from = :F, to = :E, payload = "FToE (LE=λ·ET; GPP,NPP,Rh,firec,flux_estabc; G)", timescale = :daily, conserved = true),
    Flux(from = :E, to = :F, payload = "EToF (T_skin, G(T_skin), g_a)", timescale = :daily, conserved = false),
    Flux(from = :E, to = :ATM, payload = "EToATM (LE,H,G,T_skin,NBP_atm,z0)", timescale = :subdaily, conserved = true),
    Flux(from = :ATM, to = :F, payload = "AtmForcing (SW,LW,Tair,qair,wind,psurf,precip,CO₂)", timescale = :subdaily, conserved = false),
    Flux(from = :ATM, to = :E, payload = "AtmForcing (+wind,psurf — NEW)", timescale = :subdaily, conserved = false),
]
