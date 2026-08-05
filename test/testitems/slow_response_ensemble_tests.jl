# The Phase-3A response SEED ENSEMBLE fixture (ADR 0101) — `S_response_seed_ensemble.csv`.
#
# WHY THIS TEST EXISTS. ADR 0101's whole argument is arithmetic over this file: it is what says ADR 0100's
# `+1.40× FIT` response contribution does not survive replication, that the LEVEL effect does, and that the
# baseline defect tracks the artifact's CELL SCOPE rather than its training scenario. The 32 rows are the only
# committed record of 32 SLURM jobs whose logs live in a gitignored `logs/` — so if this fixture is
# regenerated wrongly, an ADR-quoted number moves with nothing failing. The gates below are the fixture's
# MEANING:
#
#   • the double-difference IDENTITY holds per row (interaction ≡ Δ_ssp − Δ_hist ≡ R_arm − R_ctl), which is
#     what makes each row an internally consistent 2×2 rather than four unrelated numbers;
#   • every row satisfies both PRECONDITIONS (ADR 0048 merge dormancy; ADR 0101 hard kills and count-override
#     both zero) — a fixture row that violated one may not be averaged, so none may be present;
#   • the three artifacts' ensemble statistics reproduce the numbers ADR 0101 quotes: the LEVEL effect is
#     significant everywhere, the operator's RESPONSE contribution is not on either global artifact, and
#     `R_ctl`'s sign REVERSES between the single-cell demo pair and the global historic-only pair;
#   • the seed sd of the double difference is the size of the effect — the fact that motivates the whole
#     ensemble protocol, so it is asserted rather than left as prose.
#
# It reads only the committed CSV: no artifact, no /p/tmp, no rollout.

@testitem "Response seed-ensemble fixture (ADR 0101): identity, preconditions, and the withdrawn claim" tags = [:scientific] begin
    using Test
    # `Statistics` is NOT a test dep (runtime `[deps]` is empty by ADR 0014 and `test/Project.toml` is
    # integrator-owned by §9 Gap 3), so the two moments are computed here — they are three lines.
    _mean(v) = sum(v) / length(v)
    _std(v) = sqrt(sum(abs2, v .- _mean(v)) / (length(v) - 1))

    refdir = joinpath(@__DIR__, "references")
    lines = [
        l for l in readlines(joinpath(refdir, "S_response_seed_ensemble.csv"))
            if !isempty(strip(l)) && !startswith(strip(l), "#")
    ]
    hdr = split(strip(lines[1]), ',')
    rows = [split(strip(l), ',') for l in lines[2:end]]
    col(c) = [r[findfirst(==(c), hdr)] for r in rows]
    fcol(c) = parse.(Float64, col(c))
    icol(c) = parse.(Int, col(c))

    FIT = 2432.9        # ADR 0046 §1 — the per-cell median wooddens shift historic → ssp370

    for c in (
            "log", "drf", "seed", "n_init", "age0", "score_window", "wd_ctl_hist", "wd_arm_hist",
            "d_hist", "wd_ctl_ssp", "wd_arm_ssp", "d_ssp", "R_ctl", "R_arm", "interaction",
            "hard_kills", "shortfall_years", "n_merge",
        )
        @test c in hdr
    end
    @test length(rows) == 32

    # ── (a) the 2×2 identity, per row. Both forms must hold, on the corners as stored. ──────────────────────
    dh, ds = fcol("d_hist"), fcol("d_ssp")
    rc, ra, it = fcol("R_ctl"), fcol("R_arm"), fcol("interaction")
    ch, ah = fcol("wd_ctl_hist"), fcol("wd_arm_hist")
    cs, as_ = fcol("wd_ctl_ssp"), fcol("wd_arm_ssp")
    # Two DIFFERENT tolerances, and the difference is the point. `R_ctl`/`R_arm`/`interaction` are DERIVED by
    # the summarizer from the stored corners, so those identities must close to float eps — a loose tolerance
    # there would hide a genuine derivation bug. `d_hist`/`d_ssp` are the probe's own printed Δ column, and
    # every corner is printed to 2 decimals, so an identity mixing the two carries a rounding budget of
    # 3 × 0.005 = 0.015 (and 0.03 where two such Δ's are combined). Measured: 0.010 for both.
    @test maximum(abs.(rc .- (cs .- ch))) < 1.0e-9
    @test maximum(abs.(ra .- (as_ .- ah))) < 1.0e-9
    @test maximum(abs.(it .- (ds .- dh))) < 1.0e-9
    @test maximum(abs.(dh .- (ah .- ch))) < 2.0e-2
    @test maximum(abs.(ds .- (as_ .- cs))) < 2.0e-2
    @test maximum(abs.(it .- (ra .- rc))) < 4.0e-2

    # ── (b) both preconditions, every row. A violating row may not be averaged (ADR 0048/0101 §2). ─────────
    @test all(==(0), icol("hard_kills"))
    @test all(==(0), icol("shortfall_years"))
    @test all(==(0), icol("n_merge"))
    # the initial condition is held COMMON across the whole ensemble, or the seeds are not replicates
    @test all(≈(11.0), fcol("n_init"))
    @test all(≈(43.5556; atol = 1.0e-3), fcol("age0"))
    @test all(==(20), icol("score_window"))

    # ── (c) the three artifacts, and the statistics ADR 0101 quotes ────────────────────────────────────────
    drf = col("drf")
    demo = findall(contains("hainich"), drf)                 # the committed single-cell DEMO pair
    ghist = findall(contains("global_historic"), drf)        # global, historic-only
    gpool = findall(contains("pooled_w20"), drf)             # global, pooled — the pair line M pins
    @test length(demo) == 8
    @test length(ghist) == 12
    @test length(gpool) == 12
    @test length(demo) + length(ghist) + length(gpool) == 32
    # seeds within an artifact are distinct — a duplicated seed would fake independent replication
    for idx in (demo, ghist, gpool)
        @test length(unique(icol("seed")[idx])) == length(idx)
    end

    "mean, sem and the half-width of a two-sided 95 % CI (t with n−1 df, table for the n used here)."
    function stats(v)
        n = length(v)
        m = _mean(v)
        sem = _std(v) / sqrt(n)
        t975 = n == 8 ? 2.365 : n == 12 ? 2.201 : 1.96
        return m, sem, t975 * sem
    end

    # the LEVEL effect (ADR 0049's claim) is large and significant on EVERY artifact
    for idx in (demo, ghist, gpool)
        m, sem, _ = stats(dh[idx])
        @test m > 5000.0                       # gC/m³ — 2× the FIT shift at least
        @test m / sem > 8.0                    # measured 10.4–23.5
    end

    # the operator's RESPONSE contribution: NOT distinguishable from zero on either GLOBAL artifact, and both
    # CIs exclude ADR 0100's +1.40× — this pair of assertions IS the withdrawal of the Stage-3 claim
    for idx in (ghist, gpool)
        m, _, h = stats(it[idx] ./ FIT)
        @test m - h < 0.0 < m + h              # CI straddles zero
        @test m + h < 1.4                      # and excludes ADR 0100's headline (+1.40× FIT)
    end
    # on ADR 0100's own artifact the mean is large but the CI still straddles zero (it was never significant)
    let (m, _, h) = stats(it[demo] ./ FIT)
        @test m > 1.0
        @test m - h < 0.0
    end

    # `R_ctl`'s SIGN REVERSES between the single-cell demo pair and the global historic-only pair — the
    # correction to ADR 0100 §2, and the reason a response number must name its artifact
    let (md, _, hd) = stats(rc[demo] ./ FIT), (mg, _, hg) = stats(rc[ghist] ./ FIT)
        @test md + hd < 0.0                    # demo: significantly NEGATIVE (wrong sign vs FIT)
        @test mg - hg > 0.0                    # global historic: significantly POSITIVE (FIT's sign)
    end

    # ── (d) the fact that motivates the protocol: the seed sd is the size of the effect ────────────────────
    for idx in (demo, ghist, gpool)
        @test _std(it[idx] ./ FIT) > 0.6        # measured 0.673–1.741 ×FIT
    end
    # ⇒ a single seed cannot resolve the measured contribution: the |mean| is below its own sd on both globals
    for idx in (ghist, gpool)
        @test abs(_mean(it[idx] ./ FIT)) < _std(it[idx] ./ FIT)
    end
end
