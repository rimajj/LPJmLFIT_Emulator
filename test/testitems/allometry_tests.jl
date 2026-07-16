# Unit tests — shared allometry / diagnostics library (ENGINEERING_STANDARDS §2 base layer + ADR 0014
# step 3). Deterministic, independently checkable: closed-form values, the required limiting cases
# (zero leaf carbon ⇒ LAI/FPC 0), monotonicity, and the Beer–Lambert saturation. Ported from the
# LPJmL-FIT C source (allometry_tree.c / lai_tree.c / fpc_tree.c).
@testitem "Allometry — values, limits, monotonicity" tags = [:allometry, :unit] begin
    using LPJmLFITEmulator.Allometry
    using Test

    p = TreeAllometry{Float64}()   # angiosperm FIT defaults

    # ── height (pipe model) vs hand-computed closed form ────────────────────────────────────────
    # H = k_latosa·C_sap / (C_leaf·SLA·ρ_wood) = 4000·5000 / (1000·0.01986·2e5)
    csap, cleaf = 5000.0, 1000.0
    H_expected = 4000.0 * csap / (cleaf * 0.01986 * 2.0e5)
    H = tree_height(p, csap, cleaf)
    @test H ≈ H_expected
    @test H ≈ 5.0352 atol = 1.0e-3          # numeric anchor (m)

    # ── stem diameter = (H/allom2)^(1/allom3); crown area = allom1·(H/allom2)^(kpr/allom3) ──────
    D = stem_diameter(p, H)
    @test D ≈ (H / 28.749)^(1 / 0.5633)
    CA = crown_area(p, H)
    @test CA ≈ 117.44 * (H / 28.749)^(1.2922 / 0.5633)
    # equivalent Reinicke-form CA = allom1·D^kpr (Jucker consistency)
    @test CA ≈ 117.44 * D^1.2922 rtol = 1.0e-10

    # ── LAI = C_leaf·SLA / CA ───────────────────────────────────────────────────────────────────
    L = lai(p, cleaf, CA)
    @test L ≈ cleaf * 0.01986 / CA

    # ── FPC (Beer–Lambert) = CA·N·(1 − exp(−k·LAI)) ─────────────────────────────────────────────
    N = 0.1
    FP = fpc(p, CA, N, L)
    @test FP ≈ CA * N * (1 - exp(-0.59 * L))

    # ── limiting cases (task-required) ──────────────────────────────────────────────────────────
    @test tree_height(p, 0.0, cleaf) == 0.0      # zero sapwood ⇒ H = 0
    @test tree_height(p, csap, 0.0) == 0.0       # zero leaf    ⇒ H = 0
    @test stem_diameter(p, 0.0) == 0.0
    @test crown_area(p, 0.0) == 0.0
    @test lai(p, 0.0, CA) == 0.0                 # zero leaf carbon ⇒ LAI 0
    @test fpc(p, 0.0, N, L) == 0.0               # zero crown area ⇒ FPC 0

    # ── crown-area cap at crownarea_max = 225 m² ────────────────────────────────────────────────
    @test crown_area(p, 90.0) ≤ 225.0 + 1.0e-9   # a tall tree hits the cap
    @test crown_area(p, 90.0) ≈ 225.0 atol = 1.0e-6

    # ── monotonicity: height ↑ with sapwood; LAI ↓ with crown area; FPC ↑ with LAI ─────────────
    @test tree_height(p, 6000.0, cleaf) > tree_height(p, 4000.0, cleaf)
    @test lai(p, cleaf, 2.0) > lai(p, cleaf, 4.0)
    @test fpc(p, CA, N, 2.0) > fpc(p, CA, N, 1.0)

    # ── Beer–Lambert saturation: FPC → CA·N as LAI → ∞ ─────────────────────────────────────────
    @test fpc(p, CA, N, 1000.0) ≈ CA * N rtol = 1.0e-6

    # ── FPAR = phen·FPC·(1 − snowcover) ─────────────────────────────────────────────────────────
    @test fpar(FP, 0.5, 0.2) ≈ 0.5 * FP * 0.8
    @test fpar(FP, 0.0, 0.0) == 0.0              # no phenology ⇒ no absorbed PAR
end

# Type stability / Float32 support (ENGINEERING_STANDARDS §2 item 9): the pure allometry functions
# infer concretely and preserve element type.
@testitem "Allometry — type stability" tags = [:allometry, :types] begin
    using LPJmLFITEmulator.Allometry
    using Test

    for T in (Float64, Float32)
        p = TreeAllometry{T}()
        H = @inferred tree_height(p, T(5000), T(1000))
        @test H isa T
        CA = @inferred crown_area(p, H)
        @test CA isa T
        L = @inferred lai(p, T(1000), CA)
        @test L isa T
        @test (@inferred fpc(p, CA, T(0.1), L)) isa T
    end
end
