#!/usr/bin/env python3
"""Emit THE ONE committed per-PFT mortality-parameter table for the ported FIT hazard (ADR 0047).

Component S is about to grow a trait-dependent mortality operator (ADR 0046: FIT's wood-density
warming shift is 51.3 % WITHIN-PFT selection, so the hazard is the lever). That operator's parameters
are needed in THREE places at once — the Julia runtime (``src/trait_mortality.jl``), the Python
training-table builder (``scripts/build_slow_flux_table.py::PFT_PARAMS``), and any diagnosis script —
and ADR 0031 is the record of what happens when the same physical constants live in two independent
copies: a stale ``TREE_TYPES = [1,2,3,4,5]`` silently dropped 32.5 % of survivor tree stems for months.

So the values live in exactly ONE committed artifact, ``test/testitems/references/
S_pft_mortality_params.csv``, generated HERE from the live C parameter file, and both consumers GATE
against it (a Julia testitem and a Python assert). Nothing hardcodes a third copy.

HOW IT READS THE C (this is the whole point — it is not a transcription).
LPJmL parses its own ``.js`` parameter files by piping them through the C preprocessor
(``src/lpj/openconfig.c:28`` ``#define cpp_cmd "cpp"``, invoked at ``:467`` via ``popen``), so the
authoritative macro expansion is reproducible exactly: run plain ``cpp -P`` over
``$LPJROOT/par/pft_lpjmlfit.js``, strip the trailing commas LPJmL's own lenient parser tolerates, wrap
the resulting ``"pftpar": [...]`` fragment in braces, and ``json.loads`` it. Every value below is then a
direct read of the array element at the 0-based index that IS the ``ind`` output's ``Type`` column
(CLAUDE.md §3). No macro is re-typed by hand, so a future edit to ``WD_mort1_temp`` (or to id 5's
``"age"`` override) propagates on the next regeneration instead of silently disagreeing.

⚠ Read against ``par/pft_lpjmlfit.js``, NOT ``par/pft.js`` — the latter is present but unloaded and its
``WD_mort*``/``TREE_LONGEVITY`` macros differ (-1.9/0.4 vs -2.458/0.129; longevity 800 vs 400).

The three naming traps this file resolves, each `[VERIFIED]` against the C source:
  * ``longevity`` is the JSON key ``"age"`` (``fscanpft_tree.c`` binds it to ``treepar->longevity``),
    NOT the leaf key ``"longevity"`` = {mean, interc, slope, sigma}. id 5 overrides it to 125, not 400.
  * ``temp_low``/``temp_high`` are the ``"temp_stressed"`` interval consumed by ``tempstress_tree.c:29``,
    NOT the establishment gate ``"temp"``.
  * ``mort_max`` in the parameter file is DEAD: ``mortality_tree_ind.c:87`` reads it and ``:92``
    overwrites it unconditionally with ``10^(wdmort_1 + wdmort_2/(wooddens/1e6))``. It is emitted as
    ``mort_max_dead`` so the record shows the value exists and is unused; nothing may consume it.

Usage:
    python3 scripts/build_mort_params_reference.py            # write the CSV
    CHECK=1 python3 scripts/build_mort_params_reference.py    # regenerate + diff, exit 1 on drift
Env: LPJROOT (default /home/jamirp/lpjml56fit), OUT (default the committed reference path).
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "python" / "src"))
from lpjmlfit_emulator import data as ind_data  # noqa: E402  (the ONE TREE_TYPES, ADR 0031)

LPJROOT = Path(os.environ.get("LPJROOT", "/home/jamirp/lpjml56fit"))
OUT = Path(os.environ.get("OUT", _REPO / "test" / "testitems" / "references" / "S_pft_mortality_params.csv"))

# ── C constants that are #defines in the SOURCE, not in any parameter file ─────────────────────────
# mortality_tree_ind.c:23 KMORT_2 · :25 KMORTBG_LNF · :28 KMORTBG_Q · :22 BM_INC_COUNTER_MAX
# waterstress_tree.c / tempstress_tree.c divide the accumulated stress by NDAYYEAR (conf.h, 365).
C_SOURCE_CONSTANTS = {
    "kmort_2": 0.2,
    "kmortbg_lnf": -math.log(0.001),
    "kmortbg_q": 2.0,
    "bm_inc_counter_max": 5.0,
    "ndayyear": 365.0,
}

#: column order of the emitted CSV — per-PFT parameters, then the globals repeated on every row (so the
#: gate on either side is a plain per-row comparison and a global cannot drift unnoticed).
PFT_COLS = [
    "pft_id", "name",
    # the wood-density → mort_max map (mortality_tree_ind.c:92)
    "wdmort_1", "wdmort_2",
    # the other three additive hazards
    "mort_water_factor", "mort_water_res", "mort_temp_factor",
    "longevity", "temp_low", "temp_high",
    # the stress accumulation gate (waterstress_tree.c:31)
    "aphen_min",
    # leaf_carbon_sapl (mortality_tree_ind.c:63-65) + stemdiam (:139)
    "lai_sapl", "allom1", "allom2", "allom3", "kpr", "k_latosa", "wood_sapl",
    # trait intervals the hazard is evaluated over (diagnostics / test ranges)
    "wooddens_low", "wooddens_median", "wooddens_high",
    "sla_low", "sla_median", "sla_high",
    # DEAD — read at :87, overwritten at :92. Recorded, never consumed.
    "mort_max_dead",
]
GLOBAL_COLS = ["k_mort", "kmort_2", "kmortbg_lnf", "kmortbg_q", "bm_inc_counter_max", "ndayyear"]
COLS = PFT_COLS + GLOBAL_COLS


#: DUPLICATE keys observed in the C parameter file, with the value that actually takes effect. LPJmL
#: reads every parameter through json-c's hash lookup (``json_object_object_get_ex``, e.g.
#: ``src/tools/fscanreal.c``), and json-c's tokener inserts each pair with ``json_object_object_add``,
#: which REPLACES an existing key — so the LAST occurrence wins, which is also what ``json.loads``
#: does. That agreement is the only reason this parse is faithful, so the duplicates are enumerated
#: rather than tolerated: an unexpected one means a key silently overrides another and must be read
#: deliberately, not absorbed.
#:   pftpar[6] "boreal needleleaved summergreen tree" (larch) declares aphen_min AND aphen_max twice —
#:   the macro defaults at par/pft_lpjmlfit.js:1001-1002 (APHEN_MIN 60 / APHEN_MAX 245) followed at
#:   :1003-1004 by a deliberate override pair (10 / 200). So the EFFECTIVE larch values are 10 and 200:
#:   larch starts accumulating water stress (waterstress_tree.c:31 `pft->aphen > aphen_min`) SIX TIMES
#:   earlier in the season than every other tree PFT. Not previously recorded anywhere, and invisible
#:   in the file unless you notice the key appears twice.
KNOWN_DUPLICATE_KEYS = {("pftpar", 6, "aphen_min"): 10.0, ("pftpar", 6, "aphen_max"): 200.0}


def _dup_hook(known: set):
    """``object_pairs_hook`` that records every duplicated key it sees (last-wins, as json-c does)."""
    def hook(pairs):
        seen = set()
        for k, _v in pairs:
            if k in seen:
                known.add(k)
            seen.add(k)
        return dict(pairs)
    return hook


def cpp_json(path: Path) -> tuple[dict, set]:
    """Expand a LPJmL ``.js`` parameter file exactly as LPJmL does, and parse it.

    ``cpp -P`` is the same preprocessor invocation ``openconfig.c`` pipes the file through; the file is
    a brace/bracket FRAGMENT (top-level ``"key": value,`` pairs), so it is wrapped in braces, and its
    trailing commas — which LPJmL's own parser tolerates but ``json`` does not — are removed.

    Returns ``(parsed, duplicated_key_names)``; see :data:`KNOWN_DUPLICATE_KEYS`.
    """
    proc = subprocess.run(
        ["cpp", "-P", str(path)], capture_output=True, text=True, check=True,
        stdin=subprocess.DEVNULL,
    )
    body = proc.stdout.strip().rstrip(",")
    body = re.sub(r",(\s*[}\]])", r"\1", body)
    dups: set = set()
    return json.loads("{" + body + "}", object_pairs_hook=_dup_hook(dups)), dups


def build_rows() -> list[dict]:
    parsed, dups = cpp_json(LPJROOT / "par" / "pft_lpjmlfit.js")
    pft = parsed["pftpar"]
    expected_dups = {k[2] for k in KNOWN_DUPLICATE_KEYS}
    assert dups == expected_dups, (
        f"duplicate keys in par/pft_lpjmlfit.js changed: got {sorted(dups)}, expected "
        f"{sorted(expected_dups)}. json-c takes the LAST occurrence, so a new duplicate SILENTLY "
        f"overrides a parameter — read it deliberately and update KNOWN_DUPLICATE_KEYS."
    )
    for (_scope, i, key), val in KNOWN_DUPLICATE_KEYS.items():
        assert float(pft[i][key]) == val, (
            f"pftpar[{i}][{key!r}] = {pft[i][key]} but the recorded last-wins value is {val}"
        )
    # lpjparam_fit.js nests everything under a top-level "param" object (the C's global `param` struct)
    prm, prm_dups = cpp_json(LPJROOT / "par" / "lpjparam_fit.js")
    assert not prm_dups, f"unexpected duplicate keys in par/lpjparam_fit.js: {sorted(prm_dups)}"
    k_mort = float(prm["param"]["k_mort"])

    tree_ids = sorted(ind_data.TREE_TYPES)
    rows = []
    for i in tree_ids:
        p = pft[i]
        assert p["type"] == "tree", (
            f"pftpar[{i}] is a {p['type']!r} ({p['name']!r}), not a tree — TREE_TYPES and "
            f"par/pft_lpjmlfit.js have drifted apart (ADR 0031)."
        )
        row = {
            "pft_id": i,
            "name": p["name"],
            "wdmort_1": float(p["wdmort_1"]),
            "wdmort_2": float(p["wdmort_2"]),
            "mort_water_factor": float(p["mort_water_factor"]),
            "mort_water_res": float(p["mort_water_res"]),
            "mort_temp_factor": float(p["mort_temp_factor"]),
            "longevity": float(p["age"]),          # the JSON key "age", NOT "longevity"
            "temp_low": float(p["temp_stressed"]["low"]),
            "temp_high": float(p["temp_stressed"]["high"]),
            "aphen_min": float(p["aphen_min"]),
            "lai_sapl": float(p["lai_sapl"]),
            "allom1": float(p["allom1"]),
            "allom2": float(p["allom2"]),
            "allom3": float(p["allom3"]),
            "kpr": float(p["kpr"]),
            "k_latosa": float(p["k_latosa"]),
            "wood_sapl": float(p["wood_sapl"]),
            "wooddens_low": float(p["wooddens"]["low"]),
            "wooddens_median": float(p["wooddens"]["median"]),
            "wooddens_high": float(p["wooddens"]["high"]),
            "sla_low": float(p["sla"]["low"]),
            "sla_median": float(p["sla"]["median"]),
            "sla_high": float(p["sla"]["high"]),
            "mort_max_dead": float(p["mort_max"]),
            "k_mort": k_mort,
            **C_SOURCE_CONSTANTS,
        }
        rows.append(row)

    # ── self-checks: the parse's own cross-validation against independently-recorded facts ──────────
    by_id = {r["pft_id"]: r for r in rows}
    assert set(by_id) == set(tree_ids), "row set must be exactly TREE_TYPES"
    # CLAUDE.md §3's [VERIFIED] table — the values a past session read by hand. A mismatch means either
    # the C changed or this parse is wrong; both must stop the build, not be papered over.
    expect = {  # id: (wdmort_1, wdmort_2, mort_water_factor, mort_water_res, longevity, temp_low)
        0: (-2.458, 0.129, 10.0, 0.75, 400.0, 12.5),
        1: (-2.625, 0.236, 5.0, 0.25, 400.0, -15.0),
        2: (-2.625, 0.236, 10.0, 0.25, 400.0, -10.0),
        3: (-2.465, 0.148, 5.0, 0.75, 400.0, -20.0),
        4: (-2.430, 0.143, 7.5, 0.65, 400.0, -45.0),
        5: (-2.430, 0.143, 20.0, 0.75, 125.0, -45.0),
        6: (-2.430, 0.143, 5.0, 0.65, 400.0, -70.0),
    }
    for i, exp in expect.items():
        if i not in by_id:
            continue
        got = (
            by_id[i]["wdmort_1"], by_id[i]["wdmort_2"], by_id[i]["mort_water_factor"],
            by_id[i]["mort_water_res"], by_id[i]["longevity"], by_id[i]["temp_low"],
        )
        assert all(abs(a - b) < 1e-12 for a, b in zip(got, exp)), (
            f"pft {i}: parsed {got} != the CLAUDE.md §3 [VERIFIED] row {exp} — the C parameter file "
            f"changed, or this parse binds a key to the wrong pftpar entry. Investigate; do not widen."
        )
    assert abs(k_mort - 0.01) < 1e-12, f"k_mort = {k_mort}, expected 0.01 (par/lpjparam_fit.js)"
    assert all(r["temp_high"] == 54.0 for r in rows), "every tree PFT's temp_stressed.high is 54.0"
    # id 5 is the row a temperate-default fallback used to get wrong in TWO ways at once
    if 5 in by_id:
        assert by_id[5]["longevity"] == 125.0 and by_id[5]["mort_water_factor"] == 20.0, (
            "id 5 (boreal broadleaved summergreen) must carry longevity 125 and mort_water_factor 20"
        )
    return rows


def render(rows: list[dict]) -> str:
    buf = io.StringIO()
    buf.write(
        "# S_pft_mortality_params.csv — THE ONE per-PFT mortality-parameter table for the ported\n"
        "# LPJmL-FIT tree mortality hazard (ADR 0047). GENERATED — do not hand-edit.\n"
        "#   regenerate: python3 scripts/build_mort_params_reference.py\n"
        "#   verify:     CHECK=1 python3 scripts/build_mort_params_reference.py\n"
        "# Source of record: $LPJROOT/par/pft_lpjmlfit.js + par/lpjparam_fit.js, expanded with the same\n"
        "# `cpp -P` LPJmL itself pipes them through (src/lpj/openconfig.c:28,467). `pft_id` IS the `ind`\n"
        "# output's `Type` column (0-based pftpar index; ids 0-6 are the complete tree set, ADR 0031).\n"
        "# `longevity` is the JSON key \"age\" (NOT the leaf \"longevity\"); `temp_low`/`temp_high` are\n"
        "# \"temp_stressed\" (NOT the establishment gate \"temp\"). `mort_max_dead` is the parameter-file\n"
        "# `mort_max`, read at mortality_tree_ind.c:87 and OVERWRITTEN at :92 — recorded, never consumed.\n"
        "# The trailing six columns are per-run GLOBALS, repeated on every row so neither consumer can\n"
        "# drift on them silently: k_mort from par/lpjparam_fit.js, the rest #defines in the C source.\n"
        "# Two quirks of the C file, both faithful and both surprising:\n"
        "#   * id 6 (larch) declares `aphen_min`/`aphen_max` TWICE — the macro defaults (60/245) then a\n"
        "#     deliberate override pair (10/200). json-c's last-wins lookup makes 10/200 EFFECTIVE, so\n"
        "#     larch accumulates water stress six times earlier in the season than the other six PFTs.\n"
        "#   * `sla_median` is a single global default (0.01986) and lies OUTSIDE [low, high] for ids\n"
        "#     1, 2, 3 and 5. Recruit traits are drawn on [low, high] (ADR 0045), so do not treat\n"
        "#     `sla_median` as a central value of the interval.\n"
    )
    w = csv.DictWriter(buf, fieldnames=COLS, lineterminator="\n")
    w.writeheader()
    for r in sorted(rows, key=lambda r: r["pft_id"]):
        out = {}
        for c in COLS:
            x = r[c]
            out[c] = x if isinstance(x, str) else (repr(x) if isinstance(x, float) else x)
        w.writerow(out)
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
            print(f"CHECK: {OUT} is up to date ({len(rows)} tree PFTs).")
            return 0
        print(f"CHECK: DRIFT — {OUT} differs from a fresh read of the C parameter files.", file=sys.stderr)
        import difflib
        sys.stderr.writelines(
            difflib.unified_diff(old.splitlines(True), text.splitlines(True), "committed", "regenerated")
        )
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print(f"wrote {OUT}  ({len(rows)} tree PFTs, {len(COLS)} columns)")
    for r in sorted(rows, key=lambda r: r["pft_id"]):
        print(
            f"  id {r['pft_id']}  wdmort=({r['wdmort_1']:+.3f}, {r['wdmort_2']:.3f})  "
            f"mwf={r['mort_water_factor']:<5g} mwr={r['mort_water_res']:<5g} "
            f"L={r['longevity']:<6g} tstress=[{r['temp_low']:g}, {r['temp_high']:g}]  {r['name']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
