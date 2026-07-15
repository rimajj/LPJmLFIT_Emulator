# docs/make.jl — build the Documenter.jl site (the SINGLE SOURCE OF TRUTH).
#
# The docs are strict by design (ENGINEERING_STANDARDS.md §0/§4): `warnonly=false`, so a build
# fails if a docstring is missing (`checkdocs=:exports`), a doctest output drifts (`doctest=true`),
# an `@example`/`@eval`/derived diagram no longer runs, or a cross-reference breaks. That loud
# failure is what gives the (non-coding) owner control over agent-written code.
#
# Local build:   julia --project=docs docs/make.jl        (see docs/src/howto/build_docs.md)
# CI/deploy:     .github/workflows/docs.yml via julia-docdeploy@v1.

using Documenter
using DocumenterCitations
using DocumenterMermaid
using LPJmLFITEmulator

# Make `using LPJmLFITEmulator` implicit in every doctest so jldoctest blocks stay terse.
DocMeta.setdocmeta!(
    LPJmLFITEmulator,
    :DocTestSetup,
    :(using LPJmLFITEmulator);
    recursive = true,
)

# BibTeX bibliography — every model equation cites the paper it came from via `[key](@cite)`.
# The canonical `@bibliography` block lives at the end of model/model_description.md.
bib = CitationBibliography(
    joinpath(@__DIR__, "src", "refs.bib");
    style = :authoryear,
)

makedocs(;
    sitename = "LPJmL-FIT Hybrid Land Component",
    authors = "Jamir Priesner",
    modules = [LPJmLFITEmulator],
    # Explicit GitHub remote so source links resolve to the exact lines even though the HPC git
    # remote uses an SSH host alias (git@github-esm:…) that auto-detection cannot parse.
    repo = Documenter.Remotes.GitHub("rimajj", "LPJmLFIT_Emulator"),
    checkdocs = :exports,   # every exported symbol must be documented
    doctest = true,         # execute all jldoctest blocks; fail on output mismatch
    warnonly = false,       # STRICT — no silent doc↔code drift
    plugins = [bib],
    format = Documenter.HTML(;
        prettyurls = get(ENV, "CI", "false") == "true",
        canonical = "https://rimajj.github.io/LPJmLFIT_Emulator",
        edit_link = "main",
        mathengine = Documenter.KaTeX(),
        assets = String[],
        size_threshold = 1_000_000,       # generous — the @autodocs API page is the largest
        size_threshold_warn = 600_000,
    ),
    # Information architecture = Diátaxis (explanation / how-to / reference / tutorials); for the
    # owner, Explanation + Model description + Reference matter most (ENGINEERING_STANDARDS.md §4/§6).
    pages = [
        "Home" => "index.md",
        "Explanation" => [
            "The three-component architecture" => "explanation/architecture.md",
            "Conservation by construction" => "explanation/conservation.md",
            "Why a hybrid?" => "explanation/hybrid_rationale.md",
            "Limitations & honest scope" => "explanation/limitations.md",
        ],
        "Model description (GMD-style)" => [
            "Model description" => "model/model_description.md",
            "Model card — component S" => "model/model_card.md",
            "Datasheets" => [
                "Historical (obsclim)" => "model/datasheets/historical_obsclim.md",
                "SSP370 (OOD)" => "model/datasheets/ssp370.md",
            ],
        ],
        "Diagrams" => "diagrams.md",
        "How-to guides" => [
            "Run LPJmL-FIT & generate data" => "howto/run_lpjml.md",
            "Reproduce a result" => "howto/reproduce.md",
            "Build the documentation" => "howto/build_docs.md",
        ],
        "Tutorials" => "tutorials/index.md",
        "Reference" => [
            "API" => "reference/api.md",
            "Glossary" => "reference/glossary.md",
        ],
    ],
)

# Deploy to GitHub Pages (docs.yml). Preview builds are pushed for every PR.
deploydocs(;
    repo = "github.com/rimajj/LPJmLFIT_Emulator.git",
    devbranch = "main",
    push_preview = true,
)
