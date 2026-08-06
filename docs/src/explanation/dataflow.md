# The full data flow — every dataset, end to end

```@meta
CurrentModule = LPJmLFITEmulator
```

This page answers three questions in one picture: **what data goes into the original model
(LPJmL-FIT)**, **what data goes into each of the three components** of the emulator, and **what the
components hand to each other**.

It is generated from the code, not drawn by hand. If someone changes what a component reads or
produces, this diagram changes with it, and the test suite refuses to pass until the picture and the
code agree again — see [How it stays true](@ref dataflow-governance) at the bottom.

!!! tip "How to read it"
    - **Solid arrows** move data during an actual simulation.
    - **Thick arrows** are the handoffs where a quantity must be *conserved* — nothing may be created
      or lost in the exchange (carbon, water, energy).
    - **Dashed arrows** never happen during a simulation. They are the offline work: *training* the
      emulator on the original model's output, and *scoring* it against the original model or against
      real-world measurements.
    - Left to right, the picture is a history: raw input data → the original model → its output →
      tables built from that output → the two learned pieces → the running emulator.

## The diagram

```@eval
using Markdown
f = joinpath("..", "generated", "dataflow_full.mmd")
isfile(f) ? Markdown.parse("```mermaid\n" * read(f, String) * "\n```") :
    Markdown.parse("*Generated diagram `docs/src/generated/dataflow_full.mmd` pending — run `julia --project=. scripts/gen_diagrams.jl`.*")
```

It is a large diagram on purpose — it is the *complete* inventory. For the small,
four-box version of just the component coupling, see [Diagrams](../diagrams.md) and
[The three-component architecture](@ref).

## What goes into the original model

LPJmL-FIT is the model this project is learning to imitate, and it is also the source of all training
data. Eight things drive it:

| Input | What it is | Worth knowing |
|---|---|---|
| Grid | 67 420 half-degree land cells; 54 020 of them grow trees | The cell numbering is a specific ordering; two different files on the cluster disagree about it, so they are not interchangeable |
| Soil texture class | One byte per cell, keyed into a soil parameter table | |
| Soil depth | A global soil-depth dataset | **It is read and then thrown away.** The code overwrites every cell with 20 m, so this input has no effect at all |
| Historical climate | Daily air temperature, precipitation, incoming shortwave, net longwave, humidity, 1901–2019 | Observation-based |
| Warming climate | The same five variables from a climate model under a strong-warming scenario, 2015–2100 | This is the out-of-sample test: the emulator must get the *response* to warming right, not just today's world |
| CO₂ concentration | One annual number | **Deliberately frozen** from 2020 onward, and the emulator never sees it at all — see below |
| Parameter files | Plant and soil parameters | Read through the C preprocessor, so the effective value of a parameter is not always what a line in the file appears to say |
| Spin-up state | The state after a 1000-year warm-up, plus each cell's random-number seeds | Every production run continues from here rather than starting from bare ground |

!!! note "Why there is no CO₂ arrow into the emulator"
    The emulator responds to **climate**, not to CO₂ — and that is faithfulness, not a gap. The
    warming scenario's climate already carries the effect of rising CO₂. The original model is run
    with CO₂ held constant on purpose, because with its nitrogen limitation switched off its own
    response to rising CO₂ grows without bound and inflates vegetation carbon. An emulator that
    reproduced that behaviour would be reproducing a known error.

Two further inputs — **wind speed** and **surface pressure** — sit in their own box, because
LPJmL-FIT has no such inputs at all. Only the energy component needs them, and they were sourced
separately from the same observational climate product family.

## What comes out of the original model, and what it is used for

The original model's output plays **two completely different roles**, and the diagram separates them
deliberately:

- **Training data** — the annual tree table (one row per tree per year) becomes, after several
  processing steps, the table the two learned pieces are fitted on.
- **Answer key** — the same outputs, and the daily fields, are what the emulator is *scored*
  against. Both roles are dashed arrows, because neither happens while the emulator runs.

One honest caveat the diagram records: the annual tree table only contains stems **taller than 5 m**,
and writes numbers to six significant digits. Every per-cell statistic derived from it inherits both
limits.

## What goes into each component

Three of the boxes on the right are the emulator itself.

**S — the slow emulator** (annual; the learned part). It decides how many trees there are and what
they are like. It reads:

- the two learned artifacts, pinned to a specific version: a forest model for counts and sizes, and a
  copula for the traits of newly established trees;
- per-cell starting values — an initial tree count, a mean age, and a row of local bioclimate;
- from the fast core each year, the carbon increment it must allocate plus the year's water and
  temperature stresses and the soil moisture state.

Internally, S is conditioned on a fixed-order feature row — four flux drivers from the fast core, six
summaries of this year's stand, last year's tree count, and the bioclimate tail. That order is
load-bearing: it must be *identical* between training and running, or the model is being asked a
different question than it was taught. The function that builds it is
[`flux_feature_vector`](@ref).

**F — the fast physical core** (daily; kept from the original model, made differentiable). It reads
the atmospheric forcing, the canopy structure S derived for it, the surface temperature from the
energy component, and its per-cell soil column.

### Inside F: individual trees, not one average tree

"Reused from LPJmL-FIT" invites a fair question: the original model computes the daily biophysics for
**each individual tree separately** and then adds them up — does ours?

**Yes, for the parts the original does per individual.** The fast core carries the patch's real set of
individuals — a distribution of tree sizes and plant types plus grass — and loops over them. Concretely:

- **Light competition is per individual, and it is vertical.** Tall dominant trees absorb sunlight
  first; suppressed trees below them receive only what is transmitted. Each individual photosynthesises
  on the light *it* actually intercepts.
- **Photosynthesis, respiration and the carbon increment are per individual.** Each tree ends the year
  with its own carbon gain, which is what the slow emulator then allocates.
- **Water demand is stand-level — in the original too.** The original computes one mean canopy
  conductance shared across the whole stand, and each individual transpires the smaller of its own
  water supply and that shared demand, weighted by its share of ground cover. Ours copies that exactly.
  Making this "more per-individual" would be *less* faithful, not more.
- **The soil column is shared** by all individuals in a patch, with total withdrawal capped at each
  layer's available water — again as in the original.

This distinction is not cosmetic. An earlier version of the fast core used a **single representative
tree**, and it was wrong in two directions at once: about 42 % too little photosynthesis and about 45 %
too much transpiration. Both errors came from collapsing the individuals — one over-lit average tree
saturates its own photosynthetic capacity, and it transpires at full-light demand without being scaled
by its ground cover. Moving to the real set of individuals closed both gaps.

!!! warning "Honest simplifications in the current version"
    - Canopy structure is held at its year-end values through the year, with a daily leaf-out factor
      applied — it does not grow continuously within the year.
    - **Trees under 5 m are missing**, because the original model's tree table does not write them out.
    - Each individual uses the cell's shared root-depth profile rather than its own.
    - Rainfall interception by the canopy is not yet included.

    There is a further dimension above the individual: the original runs **25 independent patches per
    cell** and averages them. Whether the emulator is driven from one representative patch or from the
    whole ensemble measurably changes the levels it reports, so the two are not interchangeable — the
    ensemble is the correct basis, and any single-patch number is biased dense by construction.

**E — the energy balance** (sub-daily; a closure the original model does not have). It reads the
atmospheric forcing *including wind and pressure*, the canopy structure from S, and the latent and
ground heat from F. It solves for one surface temperature and closes the energy budget, with sensible
heat as the residual.

## What the components exchange

These are the labelled arrows between S, F and E. **The field lists in the diagram are read directly
out of the code** — they are the actual fields of the interface structures in `src/interface.jl`, not
a hand-written summary that could drift.

| Handoff | Carries | Conserved? |
|---|---|---|
| S → F | canopy structure: leaf area, height, roughness, rooting depth, photosynthetic capacity, cover, albedo | no — boundary conditions, not fluxes |
| S → E | albedo, roughness, leaf area, height | no |
| F → S | the annual carbon increment, plus water/temperature stress, growth efficiency, soil moisture | **yes** — S must allocate exactly the carbon F delivered |
| F → E | latent heat, and the four carbon terms E needs | **yes** |
| E → F | the one surface temperature, the matching ground heat, aerodynamic conductance | no |
| E → atmosphere | latent, sensible and ground heat, surface temperature, net land–atmosphere carbon flux, roughness | **yes** |

The rule behind the direction of these arrows: S sends **structure**, F sends **the carbon budget**,
and E owns **the one surface temperature** so that radiation, evaporation and heating all refer to the
same surface.

## [How it stays true](@id dataflow-governance)

The diagram is written by `scripts/gen_diagrams.jl` from [`DATA_NODES`](@ref), [`DATA_EDGES`](@ref)
and [`STAGES`](@ref) in `src/registry.jl`. Four checks in the test suite
(`test/testitems/diagram_registry_tests.jl`) stop it drifting out of agreement with the code:

1. **Staleness.** The diagram is regenerated and compared with the committed copy. Any difference
   fails the build.
2. **Reflection.** The field list on every component-to-component arrow is taken from the interface
   structure itself. Add, rename or remove a field and the diagram changes — and check 1 then fails
   until it is regenerated.
3. **Provenance.** Every input box must name a real entry in `config/paths.yaml`. A dataset that is
   renamed or dropped cannot leave a box on the diagram describing something that no longer exists.
4. **Structure.** No arrow may point at a box that does not exist, no box may be left unconnected, and
   no box may fall outside a drawn group — all three would silently omit information.

To regenerate after changing the model:

```
julia --project=. scripts/gen_diagrams.jl            # rewrite the diagram
julia --project=. scripts/gen_diagrams.jl --check    # just report whether it is stale
```

This closes a real gap. The continuous-integration configuration had claimed for months that the test
suite compared these diagrams against the registry, but no test did — and one of the diagrams had in
fact been silently wrong for weeks. Now the claim is true.
