# The rung-2 θ=1 mortality identity gate, as a CI test (line M, ADR 0122).
#
# `src/trait_mortality.jl` has no call site anywhere in the package (guardrail 4 — it ships inert), so
# until now nothing scored it against the LPJmL-FIT C binary on real per-individual state; the existing
# `slow_trait_mortality_tests.jl` gates its PARAMETER table, not its arithmetic. It is about to become
# load-bearing: line S returned it as the rung-2 demography interface (ADR 0117, option (c) — a
# per-individual survival factor `f_i = (1 − mort_i)^θ`), and ADR 0049 item 2 records that θ = 1 recovers
# FIT exactly. So the port reproducing the C's own `mort_prob` is an IDENTITY, not an approximation, and
# a regression in it would silently corrupt every later trait-selection number.
#
# The fixture is the C's own answer, not a stored output of this code: `references/M_rung2_hazard_identity.csv`
# is a PFT-stratified subsample of the rung-2 observation dump (cell 42490, 25 patches, 2000–2019),
# carrying the eleven inputs `mortality_tree_ind` used and the five numbers it produced. It exists because
# the dump itself is 20 MB on `/p/tmp` and is not in git. The full-population run — all 9 951
# tree-patch-years, max relative error 1.6e-15 — is `scripts/diagnose_rung2_hazard_identity.jl`; this item
# is the cheap always-on version of it.
#
# ⚠ `age_pre` is the PRE-increment age. `annual_tree.c:46` does `tree->age++` AFTER `mortality_tree_ind`,
# so the age that produced a row's `mort_age` is one LESS than the `ind` output's `Age` (CLAUDE.md §3).
# ⚠ `bm_inc_counter` is the UPDATED counter. `mortality_tree_ind.c:71-81` advances it from the sign of
# `bm_delta` and then uses the new value; the dump's `pre` phase carries the previous one, and passing that
# instead is what inverts the wood-density selection sign (ADR 0122 §4). The fixture stores the updated one.
@testitem "rung-2 θ=1 hazard identity vs the LPJmL-FIT C oracle" tags = [:slow, :reference] begin
    using LPJmLFITEmulator.TraitMortality

    path = joinpath(@__DIR__, "references", "M_rung2_hazard_identity.csv")
    @test isfile(path)

    lines = filter(l -> !isempty(l) && !startswith(l, "#"), readlines(path))
    header = split(lines[1], ",")
    col = Dict(n => i for (i, n) in enumerate(header))
    rows = [split(l, ",") for l in lines[2:end]]
    @test length(rows) > 300

    fl(row, n) = parse(Float64, row[col[n]])
    it(row, n) = parse(Int, row[col[n]])

    # every component, the capped sum, and both hard kills — the decomposition is kept deliberately
    # (ADR 0046 §3: the trait dependence enters through `npp` in a direction that can OPPOSE the
    # `mort_max` factor, so a harness that only checks the total cannot localise a port error).
    worst = 0.0
    n_hard = 0
    pfts = Set{Int}()
    for row in rows
        p = pft_mort_params(it(row, "pft_id"))
        push!(pfts, it(row, "pft_id"))
        wd = fl(row, "wooddens")
        sla = fl(row, "sla")
        cnt = it(row, "bm_inc_counter")
        h = mortality_hazard(
            p; wooddens = wd, sla = sla, age = it(row, "age_pre"),
            bm_delta = fl(row, "bm_delta"), leafarea = fl(row, "leafarea_real"),
            leaf_c = fl(row, "leaf_c"), water_stress = fl(row, "water_stress"),
            temp_stress = fl(row, "temp_stress"), bm_inc_counter = cnt
        )
        h.hard_kill === :none || (n_hard += 1)
        for (got, want) in (
                (h.npp, fl(row, "c_mort_npp")),
                (h.age, fl(row, "c_mort_age")),
                (h.water, fl(row, "c_mort_water")),
                (h.temp, fl(row, "c_mort_temp")),
                (h.total, fl(row, "c_mort_prob")),
            )
            rel = abs(got - want) / max(abs(want), 1.0e-300)
            want == 0.0 ? (@test got == 0.0) : (@test rel < 1.0e-12)
            want != 0.0 && rel > worst && (worst = rel)
        end
        # leafarea_real is the C's own `ind.leaf.carbon*sla`; a mismatch means the fixture's two
        # columns came from different phases, which would make the whole comparison meaningless
        @test fl(row, "leaf_c") * sla ≈ fl(row, "leafarea_real") rtol = 1.0e-15
    end
    # the identity holds to double round-off, not to a loose tolerance
    @test worst < 1.0e-13
    # coverage: the fixture must exercise more than beech, and must contain hard kills — the two
    # branches (`bm_inc_counter >= 5`, leaf carbon below a sapling's) are 3.7 % of the population and
    # are where a port error would hide
    @test length(pfts) >= 5
    @test n_hard > 0
end
