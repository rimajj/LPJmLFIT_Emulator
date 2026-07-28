---
status: "accepted"
date: 2026-07-28
deciders: "line E (session 1), autonomous per STEERING_PROMPT.md"
consulted: "DEVELOPMENT_PLAN.md §7 (P2 gate), DESIGN.md §energy reference, lines/E/STATE.md (E1/E4), ADR 0017 (self-contained SEB)"
informed: "line M (E→M contract consumer), MEMORY.md, config/paths.yaml"
---

# PLUMBER2 v1-0 is Component E's observational reference — and T_skin can only come from its OzFlux subset

## Context and Problem Statement

Component E (`src/components/energy.jl`, ADR 0017) closes `Rn = LE + H + G` to 1.4e-14 W/m² and orders the
Bowen ratio correctly across five biomes, but every one of its outputs is still `[ASSUMPTION]`: *physically
plausible but invented quantities validated only out-of-model*. Line E exists to convert LE / H / T_skin into
`[VERIFIED]` against observations (milestones E1 → E4, the P2 gate). Which observational product, which sites,
and — the question that only surfaces once the files are open — is the model's `T_skin` observable at all?

## Decision Drivers

- The reference must carry **all of** LE, H, Rn *and* the forcing E consumes (`SWdown, LWdown, Tair, Qair,
  Wind, Psurf, Precip`) at **sub-daily** resolution: the diurnal cycle is part of the E4 gate, and E is the
  component that needs the two forcings the LPJmL-FIT run never had (wind, psurf — milestone E2).
- It must be **acquirable by an autonomous session on this cluster**: no interactive registration, no token,
  and GitHub HTTPS is blocked from PIK.
- It must ship **per-sample QC flags and an uncertainty estimate**, because the P2 gate is stated as "within
  PLUMBER2 error bands" and `DEVELOPMENT_PLAN` §7 flags H (the residual) as the hardest flux to get right.
- The site set must line up with the five biome slots the coupled test already asserts an ordering over
  (`test/testitems/biome_coupled_tests.jl`), so observations can anchor that test rather than sit beside it.

## Considered Options

- **PLUMBER2 v1-0** (Ukkola et al. 2022, ESSD 14, 449; doi:10.25914/5fdb0902607e1) — the ~170-site
  quality-controlled, energy-flux-complete FLUXNET2015 / LaThuile / OzFlux subset built for land-model
  benchmarking, served from NCI THREDDS.
- **FLUXNET2015 Tier-1 directly** from fluxdata.org.
- **A local cluster copy** — `/p/projects/lpjml/reference_data/fluxnet` (found; a different LPJmL group's
  staging tree, undocumented provenance and processing).
- **ICOS / Warm Winter 2020** for DE-Hai specifically.

## Decision Outcome

Chosen option: **PLUMBER2 v1-0, nine sites, staged by `scripts/fetch_plumber2_sites.py`** and summarized by
`scripts/validate_e_plumber2_load.py`.

The deciding fact is access: **[VERIFIED 2026-07-28]** the NCI THREDDS `ks32` collection serves PLUMBER2 v1-0
**anonymously over plain HTTPS and is reachable from the PIK login node** — no registration, no token. That
makes the reference reproducible from a script instead of a manual download, which FLUXNET2015 (login-walled)
and the local copy (unknown provenance) are not. PLUMBER2 additionally ships exactly what the gate needs:
per-sample QC flags, energy-balance-corrected fluxes (`Qle_cor`/`Qh_cor`) *and* their joint uncertainties
(`Qle_cor_uc`/`Qh_cor_uc` — the E4 error band), `Ustar` (an independent handle on E's aerodynamic conductance),
`Qg`, and Copernicus/MODIS LAI.

The site set pairs each biome slot of `biome_coupled_tests.jl` with a tower, and pairs it **twice** where
T_skin matters:

| biome slot | site | IGBP | record | T_skin? |
|---|---|---|---|---|
| `temperate_hainich` | **DE-Hai** (Hainich — the prototype cell, orderA 42490) | DBF | 2000–2012, 30 min | no |
| `temperate_hainich` | AU-Tum (Tumbarumba) | EBF | 2002–2017, 60 min | **yes** |
| `boreal_siberia` | FI-Hyy (Hyytiälä) | ENF | 1996–2014, 30 min | no |
| `mediterranean_iberia` | FR-Pue (Puéchabon) | EBF | 2000–2014, 30 min | no |
| `semiarid_sahel` | US-SRM (Santa Rita Mesquite) | WSA | 2004–2014, 30 min | no |
| `semiarid_sahel` | AU-How (Howard Springs) | WSA | 2003–2017, 30 min | **yes** (suspect — see below) |
| `semiarid_sahel` | AU-ASM (Alice Springs Mulga) | ENF | 2011–2017, 30 min | **yes** |
| `tropical_amazon` | GF-Guy (Guyaflux) | EBF | 2004–2014, 30 min | no |
| `tropical_amazon` | AU-Rob (Robson Creek) | EBF | 2014–2017, 30 min | **yes** |

### The T_skin finding (the reason this ADR exists rather than a journal note)

**[VERIFIED 2026-07-28] PLUMBER2's FLUXNET2015- and LaThuile-sourced files contain no upwelling longwave**
(`SWup` yes, `LWup` no), and no surface/skin temperature at all. **T_skin is therefore not observable at
DE-Hai from this dataset.** The OzFlux-sourced files *do* carry `LWup`, from which T_skin follows by inverting
the closure's own longwave term at its own emissivity (`SEBParams.emissivity = 0.97`):

```
T_skin = [ (LWup − (1−ε)·LWdown) / (ε·σ) ]^(1/4)
```

so that `Rn_lw = ε·LWdown − ε·σ·T_skin⁴` reproduces the measured `LWdown − LWup` by construction
(`src/components/energy.jl:131,156`). The ε = 1 brightness temperature differs by only +0.2…+0.5 K across the
four sites, so the emissivity assumption is not the limiting uncertainty.

Consequently **the E4 gate is split**: LE / H / Rn / Bowen / closure are validated at DE-Hai (the prototype
cell) and the biome set; **T_skin is validated at the OzFlux sites only**, biome-analogously rather than at
Hainich. Three of the four are physically consistent on first look (daytime `T_skin − Tair` = +1.11 K AU-Tum,
+4.70 K AU-ASM, +0.65 K AU-Rob); **AU-How is an outlier at −1.85 K daytime** and must be diagnosed before it
is used for T_skin. There is **no boreal OzFlux site**, so boreal T_skin stays unsourced under this decision.

### Consequences

- Good, because the reference is **script-reproducible** (`manifest.json` records URL + `sha256` + byte size
  per file), so a future session re-stages it without re-deriving where it came from.
- Good, because the dataset's own uncertainty (`*_cor_uc`) supplies the E4 acceptance band instead of a band
  invented here — daytime mean LE ±50.1 / H ±56.6 W/m² at DE-Hai (±48.3/±68.9 FI-Hyy, ±40.7/±70.4 FR-Pue,
  ±24.2/±59.3 US-SRM; H's band is the wider at every site, exactly as `DEVELOPMENT_PLAN` §7 warns) — and
  because `Ustar` gives an independent check on the Monin–Obukhov `g_a` that E currently only self-verifies
  to ~3e-11. Caveat: `*_cor_uc` exists **only on the FLUXNET2015-sourced files**, so the OzFlux (T_skin) sites
  need a band from another source.
- Good, because the first-look numbers already anchor the coupled test's biome ordering with observations —
  daytime Σ H/Σ LE rises monotonically GF-Guy 0.30 < AU-Rob 0.52 ≈ AU-How 0.54 < AU-Tum 0.80 < DE-Hai 0.96 <
  FI-Hyy 1.23 < FR-Pue 1.70 < US-SRM 3.31 < AU-ASM 4.57, i.e. tropical → temperate → mediterranean →
  semi-arid, exactly the order `biome_coupled_tests.jl` asserts.
- Bad, because **T_skin at Hainich is out of reach** here; closing that needs a separate source (ICOS
  `LW_OUT` for DE-Hai, or satellite LST) — deferred, recorded as an open E-line item.
- Bad, because tower fetch is only ~76.9 % (DE-Hai), 55.6 % (FR-Pue) and 39.1 % (FI-Hyy) jointly-valid in
  Rn/LE/H/G, so per-site sample sizes differ by 2.5× and every skill score must report its n.
- Bad, because PLUMBER2 uses a **real (leap) calendar** while the model forcing is noleap-365, and PLUMBER2's
  time axis is **local standard time** (verified: mean-diurnal `SWdown` peaks at 11.0–12.5 h at all nine
  sites, i.e. near local solar noon) — both are pairing hazards for E4, and both are documented in the loader.
- Neutral: the eight non-prototype sites are **biome analogues, not the model cells**. Any statement made from
  them is a biome-level statement, never "Hainich" (guardrail 6).

## Pros and Cons of the Options

### PLUMBER2 v1-0

- Good, because anonymous HTTPS from the login node, gap-filled forcing, QC flags, uncertainties, corrected
  fluxes, `Qg`, `Ustar`, LAI, and a published reference paper + DOI.
- Good, because it is *the* benchmark other land models are scored on, so E's numbers land in a comparable
  frame.
- Bad, because no `LWup` / surface temperature outside the OzFlux subset (the finding above).

### FLUXNET2015 Tier-1 direct

- Good, because it is the upstream source and has the widest site coverage.
- Bad, because acquisition is login-walled — an autonomous session cannot complete it — and the raw product
  needs the gap-filling / unit-standardization work that PLUMBER2 has already done and published.

### Local `/p/projects/lpjml/reference_data/fluxnet`

- Good, because it is on-cluster and needs no egress.
- Bad, because provenance and processing are undocumented and it belongs to another group's project tree; a
  physics claim resting on it is not reproducible from this repo.

### ICOS / Warm Winter 2020 for DE-Hai

- Good, because it plausibly carries `LW_OUT` at DE-Hai — the one gap PLUMBER2 leaves.
- Bad, because it is single-site and a different processing chain; better used later as a **targeted
  supplement** for T_skin at Hainich than as the line's reference product.

## More Information

- Staged at `config/paths.yaml` `data.energy_reference` = `/p/tmp/jamirp/esm_land_emulator_data/fluxnet_plumber2`
  (raw `Flux/` + `Met/`, `manifest.json`, and `derived/` = `halfhourly_/daily_/diurnal_<site>.parquet` +
  `plumber2_sanity_report.txt` + `site_summary.csv`). 300 MB total; DVC/git-untracked scratch by design.
- Reproduce: `scripts/fetch_plumber2_sites.py` then `scripts/validate_e_plumber2_load.py` (procedure captured
  in the `plumber2-reference` skill).
- Loader trap worth knowing: every PLUMBER2 variable declares `_FillValue = -9999` and netCDF4 hands back a
  **masked** array — `np.asarray()` silently drops the mask and the fill leaks in as data (DE-Hai mean LE came
  out at −2283 W/m² before the fix). Use `np.ma.filled(..., np.nan)`.
- Validated by: milestone **E4** (LE/H/T_skin within the dataset's error bands at ≥1 site + the diurnal
  cycle), which flips the `[ASSUMPTION]` in `MEMORY.md` to `[VERIFIED]` with site and bands quoted.
- Revisit if: PLUMBER2 v2 ships, a boreal `LWup` source appears, or the T_skin-at-Hainich gap is closed from
  ICOS — then supersede rather than edit.
