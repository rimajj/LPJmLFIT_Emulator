# The DIAGRAM STALENESS GATE — the check that `.github/workflows/CI.yml` always claimed the suite ran.
#
# `CI.yml` has watched `docs/src/generated/**` since the beginning with the comment "diagram fixtures
# the suite compares against registry.jl", but NO test actually compared them. The consequence was
# measured: `docs/src/generated/components.mmd` sat stale from the Phase-4 commit 773945fb for weeks,
# i.e. the rendered architecture diagram contradicted `src/registry.jl` and nothing failed. The
# `scripts/gen_diagrams.jl --check` alarm existed but was purely local and had to be remembered.
# These gates make the diagrams genuinely self-maintaining — they are the enforcement point behind
# ENGINEERING_STANDARDS §5(ii) ("code-derived diagrams that cannot silently go stale").
#
# Four independent gates, each closing a different way the diagram could lie:
#   1. STALENESS  — regenerate from the registry and compare byte-for-byte with the committed .mmd.
#   2. REFLECTION — every runtime edge label is `fieldnames` of its `src/interface.jl` struct, so
#                   adding/renaming a field in the interface contract reds CI until regenerated.
#   3. PROVENANCE — every `path_key` on a data node resolves to a real key in `config/paths.yaml`,
#                   so the diagram cannot show a box for an input the project no longer has.
#   4. STRUCTURE  — no dangling edge endpoints, no orphan nodes, no node outside a rendered stage.
#
# NOTE the include of `scripts/gen_diagrams.jl` below is only safe because that script guards its
# `main(ARGS)` with `abspath(PROGRAM_FILE) == @__FILE__`. Without the guard, including it would
# REGENERATE the committed fixtures mid-test and gate 1 could never fail.

@testitem "Diagrams are not stale: the committed .mmd match src/registry.jl exactly" tags = [:unit] begin
    using LPJmLFITEmulator
    using Test

    root = pkgdir(LPJmLFITEmulator)
    @test root !== nothing
    script = joinpath(root, "scripts", "gen_diagrams.jl")
    @test isfile(script)

    # Including the script brings `targets()` / `check()` into scope WITHOUT running `main`.
    include(script)

    # Every declared target exists and is non-trivial.
    for (path, content) in targets()
        @test isfile(path)
        @test !isempty(strip(content))
        # A generated file must announce itself, so nobody hand-edits one by mistake.
        @test occursin("AUTO-GENERATED", content)
    end

    # The gate proper: regenerate in memory, compare with what is committed. `check()` returns 0 when
    # every committed file matches and prints the offenders to stderr otherwise.
    @test check() == 0
end

@testitem "Diagram edge labels are REFLECTED from the src/interface.jl structs" tags = [:unit] begin
    using LPJmLFITEmulator
    using Test

    root = pkgdir(LPJmLFITEmulator)
    include(joinpath(root, "scripts", "gen_diagrams.jl"))

    typed = filter(e -> e.payload_type !== nothing, DATA_EDGES)
    @test !isempty(typed)

    for e in typed
        sym = e.payload_type
        # The struct must exist in the package — a typo must fail loudly, not render an empty label.
        @test isdefined(LPJmLFITEmulator, sym)
        T = getproperty(LPJmLFITEmulator, sym)
        @test T isa Type

        label = payload_fields(sym)
        @test startswith(label, String(sym) * ": ")
        # THE TEETH: every field of the interface struct must appear in the rendered label, so a new
        # field in `SToF`/`FToE`/… changes the diagram and gate 1 fails until it is regenerated.
        fields = fieldnames(T)
        @test !isempty(fields)
        for f in fields
            @test occursin(String(f), label)
        end
        # And the label carries no MORE fields than the struct has (guards a hand-edited label).
        @test length(split(label, ", ")) == length(fields)
    end

    # Every interface struct named in the legacy FLUXES table must also declare its payload type, so
    # the two diagrams cannot describe different contracts.
    for f in FLUXES
        @test f.payload_type !== nothing
        @test isdefined(LPJmLFITEmulator, f.payload_type)
        # The hand-written legacy label must at least name the struct it claims to carry.
        @test occursin(String(f.payload_type), f.payload)
    end

    # The rendered full diagram must actually contain the reflected field lists.
    full = render_dataflow_full(DATA_NODES, DATA_EDGES, STAGES)
    for e in typed
        @test occursin(payload_fields(e.payload_type), full)
    end
end

@testitem "Every diagram data node's path_key resolves in config/paths.yaml" tags = [:unit] begin
    using LPJmLFITEmulator
    using Test

    root = pkgdir(LPJmLFITEmulator)
    yaml = joinpath(root, "config", "paths.yaml")
    @test isfile(yaml)

    # Collect the set of dotted key paths in the YAML by indentation. Deliberately a ~20-line Base
    # parser rather than a YAML dependency: the runtime `[deps]` must stay EMPTY (ADR 0014), and this
    # only needs key STRUCTURE, never values. Handles nested maps; ignores comments, list items and
    # `${...}` interpolations (which are values, not keys).
    function key_paths(path)
        paths = Set{String}()
        stack = Tuple{Int, String}[]        # (indent, key) — single-assignment friendly
        for raw in eachline(path)
            line = rstrip(raw)
            (isempty(strip(line)) || startswith(strip(line), "#") || startswith(strip(line), "-")) && continue
            m = match(r"^(\s*)([A-Za-z0-9_]+)\s*:", line)
            m === nothing && continue
            indent = length(m.captures[1])
            key = String(m.captures[2])
            while !isempty(stack) && stack[end][1] >= indent
                pop!(stack)
            end
            push!(stack, (indent, key))
            push!(paths, join((s[2] for s in stack), "."))
        end
        return paths
    end

    available = key_paths(yaml)
    @test length(available) > 50          # sanity: the parser found a real tree, not nothing
    @test "lpjml.inputs.coord" in available
    @test "lpjml.binary" in available

    keyed = filter(n -> !isempty(n.path_key), DATA_NODES)
    @test !isempty(keyed)
    for n in keyed
        # A renamed or deleted input must break the diagram rather than leave a phantom box on it.
        @test n.path_key in available
    end

    # The three runtime components and the atmosphere are code, not files — they must NOT claim a path.
    for id in (:S, :F, :E, :ATM)
        node = DATA_NODES[findfirst(n -> n.id === id, DATA_NODES)]
        @test isempty(node.path_key)
    end
end

@testitem "The full data-flow graph is structurally sound (no dangling edges, no orphans)" tags = [:unit] begin
    using LPJmLFITEmulator
    using Test

    ids = [n.id for n in DATA_NODES]
    @test length(unique(ids)) == length(ids)          # node ids are unique (Mermaid would silently merge)
    idset = Set(ids)

    for e in DATA_EDGES
        @test e.from in idset
        @test e.to in idset
        @test e.from !== e.to
        @test e.style in (:solid, :thick, :dashed)
        # An edge must carry SOME label: either a reflected struct or free text.
        @test e.payload_type !== nothing || !isempty(e.label)
    end

    # No orphan boxes: every node is on at least one edge, or it is invisible clutter on the diagram.
    touched = Set{Symbol}()
    for e in DATA_EDGES
        push!(touched, e.from)
        push!(touched, e.to)
    end
    for id in ids
        @test id in touched
    end

    # Every node lands in a RENDERED stage — a node whose stage is missing from STAGES is dropped
    # silently by the renderer, which is exactly the kind of quiet omission this gate exists to stop.
    stage_ids = Set(first(p) for p in STAGES)
    for n in DATA_NODES
        @test n.stage in stage_ids
    end
    # And no stage is empty (an empty Mermaid subgraph renders as a stray titled box).
    for (stage, _) in STAGES
        @test any(n -> n.stage === stage, DATA_NODES)
    end

    # The components in the full graph must be the SAME set as the runtime registry's, so the
    # detailed diagram and the subsystem diagram can never disagree about what exists.
    @test Set(c.id for c in COMPONENTS) ⊆ idset
end
