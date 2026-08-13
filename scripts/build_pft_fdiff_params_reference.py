#!/usr/bin/env python3
"""Emit THE ONE committed per-PFT table of the parameters F_diff applies PER INDIVIDUAL (ADR 0126).

WHY THIS EXISTS. `FDiffFastCore` gave every tree in every cell **beech's** parameters
(``fast.jl``'s ``pft_ids`` default ``t.is_grass ? 8 : 3``). ADR 0125 measured what that costs: the
maintenance-respiration coefficient ``respcoeff`` is **0.2** for the tropical broadleaved evergreen
tree (id 0) and **1.2** for all six temperate/boreal trees, so at the two hot biome cells — 100 %
id 0 by sapwood — F over-respired every stem by 6× and its annual carbon balance went NEGATIVE
(−223 gC/m²/yr against a truth of +1073). It is not the only one: the Beer-Lambert extinction
``lightextcoeff`` is 0.45 for the three needleleaved trees and 0.59 for the four broadleaved ones,
the photosynthesis optimum ``temp_photos`` is 15/25 °C for the three boreal trees and 20/30 °C for
the other four, and leaf/root residence is 1, 2 or 4 years depending on the PFT.

So the values live in exactly ONE committed artifact, ``test/testitems/references/
M_pft_fdiff_params.csv``, generated HERE from the live C parameter file, and the Julia lookups
(``FDiff.pft_respparams`` / ``pft_tempstressparams`` / ``pft_canopy_traits`` / ``pft_allocparams`` /
``pft_allometry``) GATE against it in a testitem. Nothing hardcodes a second copy — ADR 0031 is the
record of what a second copy costs (a stale ``TREE_TYPES`` silently dropped 32.5 % of tree stems for
months), and ``scripts/build_mort_params_reference.py`` is the same pattern for the mortality half.

HOW IT READS THE C. Not by transcription: LPJmL parses its own ``.js`` parameter files by piping them
through the C preprocessor (``src/lpj/openconfig.c:28`` ``#define cpp_cmd "cpp"``), so the
authoritative macro expansion is reproduced by running plain ``cpp -P`` over
``$LPJROOT/par/pft_lpjmlfit.js`` and parsing the result — the ``cpp_json`` helper is IMPORTED from
``build_mort_params_reference.py`` rather than copied, including its duplicate-key audit (json-c takes
the LAST occurrence of a repeated key, so a new duplicate silently overrides a parameter).

THE UNIT CONVENTIONS, both of which are a trap:
  * ``turnover.{leaf,sapwood,root}`` in the C is a **residence time in years**; F's ``AllocParams``
    stores a **rate per year**. Both are emitted (``*_yr`` and ``*_rate``) and the builder asserts
    ``rate == 1/yr``, so the Julia gate compares like with like and the inversion is recorded once.
  * ``temp_photos``/``temp_co2`` are the photosynthesis optimum and the CO2-assimilation limits
    (``temp_stress.c:38-40``), NOT the ``temp_stressed`` mortality interval and NOT the ``temp``
    establishment gate — three different keys with confusable names (CLAUDE.md §3).

Rows are the ten NATURAL PFTs (0-6 trees, 7-9 grasses) in the 0-based ``pftpar`` scan order that IS
the ``ind`` output's ``Type`` column. The grasses carry every daily-physics key but none of the tree
allometry ones (no ``allom1``/``kpr``/``crownarea_max``/…), which are emitted as empty fields.

Usage:
    python3 scripts/build_pft_fdiff_params_reference.py            # write the CSV
    CHECK=1 python3 scripts/build_pft_fdiff_params_reference.py    # regenerate + diff, exit 1 on drift
Env: LPJROOT (default /home/jamirp/lpjml56fit), OUT (default the committed reference path).
"""

from __future__ import annotations

import csv
import io
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_mort_params_reference import cpp_json  # noqa: E402  (the ONE cpp -P reader, ADR 0047)

LPJROOT = Path(os.environ.get("LPJROOT", "/home/jamirp/lpjml56fit"))
OUT = Path(os.environ.get("OUT", _REPO / "test" / "testitems" / "references" / "M_pft_fdiff_params.csv"))

#: the ten natural PFTs; ids >= 10 are crops (`landuse:"no"` ⇒ never simulated, never emitted).
NATURAL_IDS = tuple(range(10))

#: duplicate keys the C file is KNOWN to carry, with the value that actually takes effect (last wins).
#: Identical to `build_mort_params_reference.KNOWN_DUPLICATE_KEYS`; asserted here too so this script
#: fails loudly rather than silently reading a newly-shadowed parameter.
EXPECTED_DUPLICATE_KEYS = {"aphen_min", "aphen_max"}

#: The C's individual-mode leaf-recycle divisor (`turnover_tree.c:102`,
#: `turnover_daily_tree.c:52`) and F's `AllocParams.deciduous_leaf_div`. It is ALSO the clamp in the
#: non-latched branch's rate `1/max(pft->longevity, 1.05)` (`turnover_daily_tree.c:38`), which is
#: what makes F's uniform `is_deciduous = true` faithful for every stem whose leaf longevity is at
#: or below it (ADR 0134).
DECIDUOUS_LEAF_DIV = 1.05

COLS = [
    "pft_id", "name", "type", "path", "leaftype", "phenology",
    # ── autotrophic respiration (npp_tree.c:51; F: RespParams) ──
    "respcoeff", "cn_leaf", "cn_sapwood", "cn_root",
    # ── the daily canopy constants F holds PER INDIVIDUAL (F: Individual + WaterParams.gmin) ──
    "gmin", "emax", "intc", "alphaa",
    "albedo_leaf", "albedo_stem", "albedo_litter", "snowcanopyfrac", "lightextcoeff",
    # ── photosynthesis temperature limits (temp_stress.c:38-40; F: TempStressParams) ──
    "temp_photos_low", "temp_photos_high", "temp_co2_low", "temp_co2_high", "b",
    # ── annual allocation/turnover (turnover_tree.c, allocation_tree.c; F: AllocParams) ──
    "turnover_leaf_yr", "turnover_sapwood_yr", "turnover_root_yr",
    "turnover_leaf_rate", "turnover_sapwood_rate", "turnover_root_rate",
    "lmro_ratio", "lmro_offset", "reprod_cost",
    # ── tree allometry (allometry_tree.c; F: Allometry.TreeAllometry). Blank for grass. ──
    "allom1", "allom2", "allom3", "allom4", "kpr", "k_latosa",
    "crownarea_max", "crownlength", "height_max", "wood_sapl",
]

#: keys read straight off the pftpar entry with no renaming
_SCALARS = [
    "respcoeff", "gmin", "emax", "intc", "alphaa",
    "albedo_leaf", "albedo_stem", "albedo_litter", "snowcanopyfrac", "lightextcoeff", "b",
    "lmro_ratio", "lmro_offset", "reprod_cost",
]
#: tree-only keys (absent from every grass entry)
_TREE_ONLY = [
    "allom1", "allom2", "allom3", "allom4", "kpr", "k_latosa",
    "crownarea_max", "crownlength", "height_max", "wood_sapl",
]


def build_rows() -> list[dict]:
    parsed, dups = cpp_json(LPJROOT / "par" / "pft_lpjmlfit.js")
    assert dups == EXPECTED_DUPLICATE_KEYS, (
        f"duplicate keys in par/pft_lpjmlfit.js changed: got {sorted(dups)}, expected "
        f"{sorted(EXPECTED_DUPLICATE_KEYS)}. json-c takes the LAST occurrence, so a new duplicate "
        f"SILENTLY overrides a parameter — read it deliberately before regenerating this table."
    )
    pft = parsed["pftpar"]
    rows = []
    for i in NATURAL_IDS:
        p = pft[i]
        assert p["type"] in ("tree", "grass"), f"pftpar[{i}] is a {p['type']!r}, not natural vegetation"
        is_tree = p["type"] == "tree"
        turn = p["turnover"]
        row = {
            "pft_id": i,
            "name": p["name"],
            "type": p["type"],
            "path": p["path"],
            "leaftype": p.get("leaftype", ""),
            "phenology": p["phenology"],
            "cn_leaf": float(p["cn_ratio"]["leaf"]),
            # grass has no woody pool ⇒ no sapwood C:N (and F zeroes a grass individual's `c_sapwood`)
            "cn_sapwood": float(p["cn_ratio"]["sapwood"]) if "sapwood" in p["cn_ratio"] else "",
            "cn_root": float(p["cn_ratio"]["root"]),
            "temp_photos_low": float(p["temp_photos"]["low"]),
            "temp_photos_high": float(p["temp_photos"]["high"]),
            "temp_co2_low": float(p["temp_co2"]["low"]),
            "temp_co2_high": float(p["temp_co2"]["high"]),
        }
        for k in _SCALARS:
            row[k] = float(p[k])
        for k in _TREE_ONLY:
            row[k] = float(p[k]) if is_tree else ""
        # residence time (yr, as the C stores it) → rate (1/yr, as F stores it). Grass has no sapwood.
        for pool in ("leaf", "sapwood", "root"):
            yr = float(turn[pool]) if pool in turn else ""
            row[f"turnover_{pool}_yr"] = yr
            row[f"turnover_{pool}_rate"] = (1.0 / yr) if yr != "" else ""
            if yr != "":
                assert yr > 0, f"pftpar[{i}] turnover.{pool} = {yr} is not a positive residence time"
        rows.append(row)

    # ── self-checks: the facts this table is built to carry, asserted against the parse ─────────────
    by_id = {r["pft_id"]: r for r in rows}
    # ADR 0125 §5: the 6x respiration spread that motivated the whole change.
    assert by_id[0]["respcoeff"] == 0.2, by_id[0]["respcoeff"]
    assert all(by_id[i]["respcoeff"] == 1.2 for i in range(1, 7)), "trees 1-6 are no longer all 1.2"
    # the needleleaved/broadleaved Beer-Lambert split (CLAUDE.md §3: K_LAMBERT_BEER_NL/_BL)
    for i in range(7):
        expect = 0.45 if by_id[i]["leaftype"] == "needleleaved" else 0.59
        assert by_id[i]["lightextcoeff"] == expect, (i, by_id[i]["lightextcoeff"])
    # beech (id 3) is the set F ships as its default (`tebs_params`/`tebs_allocparams`) — if any of
    # these moved, the "id 3 == today's defaults, byte-identical" property of the Julia lookups breaks.
    b = by_id[3]
    for key, val in (
        ("respcoeff", 1.2), ("cn_sapwood", 330.0), ("cn_root", 30.0), ("gmin", 1.0), ("emax", 10.0),
        ("temp_photos_low", 20.0), ("temp_photos_high", 30.0), ("temp_co2_low", -4.0),
        ("temp_co2_high", 38.0), ("lightextcoeff", 0.59), ("alphaa", 0.55), ("albedo_leaf", 0.15),
        ("intc", 0.02), ("albedo_stem", 0.04), ("albedo_litter", 0.1), ("snowcanopyfrac", 0.4),
        ("turnover_sapwood_rate", 0.04), ("turnover_root_rate", 1.0), ("allom1", 117.44),
        ("allom2", 28.749), ("allom3", 0.5633), ("kpr", 1.2922), ("crownarea_max", 225.0),
    ):
        assert b[key] == val, f"beech (id 3) {key} = {b[key]!r}, F's shipped default assumes {val!r}"
    # F's `AllocParams.is_deciduous = true` is uniform and needs no per-PFT branch. ⚠ The assertion
    # that used to live here checked `phenology == "summergreen"` for ids 0-6. It was INERT (ADR
    # 0134): under `new_phenology:true` the `phenology` key is never read for leaf turnover
    # (`daily_natural.c:123` dispatches to `phenology_gsi`, so `phenology_tree.c`'s switch is dead
    # code), and all seven trees declare `summergreen` anyway — so it could only fail on an edit
    # that changes nothing, while staying green through the edit that matters.
    #
    # What actually makes the uniform default safe is the CLAMP in the C's own non-latched branch:
    # `turnover_daily_tree.c:38` drips at `1/max(pft->longevity, 1.05)`, capped at the latched
    # branch's own 0.9524/yr, so the two branches COINCIDE for any stem whose leaf longevity is at
    # or below 1.05 yr. Assert the clamp constant and the per-PFT `longevity.mean` that positions
    # the corridor, i.e. the quantities a real change would move. (`longevity` is per-INDIVIDUAL,
    # drawn from the stem's own SLA at `new_tree.c:215`; the `mean` is only the corridor's centre.)
    # Read straight off the parse; deliberately NOT added as a CSV column, because moving the
    # committed 43-column reference is an integration point and this is a self-check, not a datum.
    for i in range(7):
        lg = pft[i]["longevity"]
        assert isinstance(lg, dict) and {"mean", "interc", "slope", "sigma"} <= set(lg), (
            f"tree PFT {i} `longevity` is {lg!r}, not the {{mean,interc,slope,sigma}} corridor "
            "form — "
            "if it became a scalar the C stopped sampling leaf longevity per individual "
            "(new_tree.c:215) and ADR 0134's whole argument needs re-deriving"
        )
        lm = float(lg["mean"])
        assert lm > DECIDUOUS_LEAF_DIV, (
            f"tree PFT {i} `longevity.mean` = {lm!r} is at or below the "
            f"{DECIDUOUS_LEAF_DIV} clamp; "
            "the leaf-longevity corridor has moved and ADR 0134's per-cell CANNOT BIND / CAN BIND "
            "verdicts must be re-measured (scripts/diagnose_leaf_turnover_regime.py)"
        )
    return rows


def render(rows: list[dict]) -> str:
    buf = io.StringIO()
    buf.write(
        "# M_pft_fdiff_params.csv — the per-PFT parameters F_diff applies PER INDIVIDUAL, read from the\n"
        "# live par/pft_lpjmlfit.js with `cpp -P` (the same preprocessor LPJmL pipes its own parameter\n"
        "# files through). Rows are the ten natural PFTs in the 0-based `pftpar` scan order that IS the\n"
        "# `ind` output's `Type` column; ids 0-6 are trees, 7-9 grasses (tree allometry columns blank).\n"
        "# `turnover_*_yr` is the C's residence time; `turnover_*_rate` = 1/yr is what F's AllocParams\n"
        "# stores. GENERATED — do not edit by hand: scripts/build_pft_fdiff_params_reference.py\n"
        "# (CHECK=1 to verify against the C). ADR 0126; the mortality half is S_pft_mortality_params.csv.\n"
    )
    w = csv.DictWriter(buf, fieldnames=COLS, lineterminator="\n")
    w.writeheader()
    for r in sorted(rows, key=lambda r: r["pft_id"]):
        w.writerow({c: (r[c] if isinstance(r[c], (str, int)) else repr(r[c])) for c in COLS})
    return buf.getvalue()


def main() -> int:
    rows = build_rows()
    text = render(rows)
    if os.environ.get("CHECK"):
        if not OUT.exists():
            print(f"CHECK: {OUT} does not exist — run without CHECK=1 first.", file=sys.stderr)
            return 1
        old = OUT.read_text()
        if old == text:
            print(f"CHECK: {OUT} is up to date ({len(rows)} natural PFTs).")
            return 0
        print(f"CHECK: DRIFT — {OUT} differs from a fresh read of the C parameter file.", file=sys.stderr)
        import difflib
        sys.stderr.writelines(
            difflib.unified_diff(old.splitlines(True), text.splitlines(True), "committed", "regenerated")
        )
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print(f"wrote {OUT}  ({len(rows)} natural PFTs, {len(COLS)} columns)")
    for r in sorted(rows, key=lambda r: r["pft_id"]):
        print(
            f"  id {r['pft_id']}  respcoeff={r['respcoeff']:<4g} k_beer={r['lightextcoeff']:<5g} "
            f"t_photos=[{r['temp_photos_low']:g}, {r['temp_photos_high']:g}]  "
            f"gmin={r['gmin']:<4g} turnover(leaf/sap/root yr)="
            f"{r['turnover_leaf_yr']}/{r['turnover_sapwood_yr'] or '-'}/{r['turnover_root_yr']}  {r['name']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
