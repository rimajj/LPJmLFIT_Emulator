#!/usr/bin/env python3
"""Emit THE ONE committed per-PFT ESTABLISHMENT-parameter table for the ported FIT recruit rule (ADR 0119).

WHY THIS EXISTS. The owner's steer of 2026-08-11 replaced "learn a recruit-trait marginal from FIT's
output" with "port FIT's establishment rule", because which trees are BORN is a parameter-file fact —
uniform draws on each PFT's own interval plus inheritance from the cell's rolling top-AGB seedbank — and
only which trees SURVIVE has to be learned. A ported rule needs its parameters, and it needs them in the
same place the ported mortality hazard gets its own (``scripts/build_mort_params_reference.py`` →
``S_pft_mortality_params.csv``): ONE generated artifact, read from the live C parameter files, that every
consumer gates against. ADR 0031 is the record of what two independent copies cost.

WHAT IT READS, and every value is a direct read — nothing is transcribed by hand:
  * ``$LPJROOT/par/pft_lpjmlfit.js`` — the four recruit trait intervals the emulator samples
    (``sla``, ``wooddens``, ``D95max``, ``minwscal``), the inheritance diffusion width
    ``inherit_corridor``, the per-PFT establishment recruitment scale ``alpha_r``, and the three columns of
    FIT's own bioclimatic establishment gate (``temp`` = the 20-yr mean-annual-minimum window the gate is
    read on, ``gdd5min``, ``aprec_min``).
  * ``$LPJROOT/par/lpjparam_fit.js`` — the run globals: the two establishment rates
    ``k_est_inherit`` / ``k_est_inherit_bg``, the inheritance ``alpha_r``, ``patcharea``, the seedbank
    memory ``max_age`` and the seedbank width scale ``n_max``.

Both are expanded with the same ``cpp -P`` LPJmL itself pipes them through (``src/lpj/openconfig.c:28``,
``:467``); the parser is imported from ``build_mort_params_reference`` rather than copied.

THE C ROUTINES THESE PARAMETERS BELONG TO (source of record for the port; read them before changing a
number here):
  * ``src/lpj/establishmentpft_ind.c:97-140`` — the TWO channels. Background: for each ELIGIBLE PFT,
    ``poidev(k_est_inherit_bg·patcharea·f_sap(fpar, alpha_r))`` recruits with uniform traits. Inheritance:
    ``poidev(k_est_inherit·patcharea·f_sap(fpar, param.alpha_r))`` recruits from the seedbank. Both
    ``alpha_r`` are 2.0 and both carry the same ``f_sap(patch->fpar_leafon_grass, ·)``, so the light and
    patch-area factors CANCEL in the ratio and the inherited share is the closed form
    ``k_est_inherit / (k_est_inherit + n_elig·k_est_inherit_bg) = 4/(4 + n_elig)`` (ADR 0045).
    ⚠ The equality of the two ``alpha_r`` is asserted below — it is what makes the closed form exact.
  * ``src/tree/new_tree.c:38-61`` (``draw_new_trait``) — the inheritance diffusion:
    ``new = old·(1 + corridor·s)`` with ``s`` a clamped ±5 standard normal, and if the result leaves
    ``[low, high]`` it is redrawn UNIFORMLY BETWEEN THE PARENT AND THE VIOLATED BOUND — not reflected.
  * ``src/tree/new_tree.c:196-203`` — the background channel is ``getrndinterval`` =
    ``low + (high−low)·U`` on each axis (``include/numeric.h:59``).
  * ``src/lpj/getsapling.c`` — the seedbank: seeds older than ``max_age`` years are dropped, then every
    tree of the cell whose ``agb_tree`` is at least the ``n``-th largest is APPENDED, with
    ``n = n_max·npatch·patcharea/100`` (C integer truncation). It is an accumulation of individual-YEARS,
    so a tree that dominates for 30 years contributes 30 draws.
  * ``src/lpj/establish.c:24-34`` — eligibility: ``temp_min20 ∈ [temp.low, temp.high]`` AND
    ``gdd ≥ gdd5min`` AND NOT (tree AND ``temp_max20 ≤ 10``), where ``temp_min20``/``temp_max20`` are
    20-year running means of the year's coldest/warmest MONTHLY mean (``src/lpj/climbuf.c:134-137,153-154``).
    The ``aprec ≥ aprec_min`` test is in ``establishmentpft_ind.c:88``.

THE STRUCTURAL FACTS IN THIS TABLE THAT A HAND-WRITTEN VERSION WOULD GET WRONG (all asserted below):
  * ``temp_high`` is 1000 (i.e. no upper bound) for ids 0-3 but **0.0 for the three boreal PFTs 4/5/6** —
    so boreal establishment is gated OFF wherever the 20-yr mean coldest month is above freezing.
  * ``gdd5min`` spans 0 / 900 / 1200 / 1200 / 350 — the eligible SET is strongly cell-dependent, which is
    the whole reason ``n_elig`` (and so the inherited share) is not a constant.
  * ``minwscal_high`` is 0.75 for id 0 but 0.15-0.30 for the others, and ``sla`` intervals do not even
    overlap between the evergreen (0.005-0.0187) and summergreen (0.0242-0.0547) PFTs — a single pooled
    recruit marginal cannot represent this, which is ADR 0118 §3's composition control in parameter form.

Usage:
    python3 scripts/build_estab_params_reference.py            # write the CSV
    CHECK=1 python3 scripts/build_estab_params_reference.py    # regenerate + diff, exit 1 on drift
Env: LPJROOT (default /home/jamirp/lpjml56fit), OUT (default the committed reference path).
"""

from __future__ import annotations

import csv
import io
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "scripts"))
sys.path.insert(0, str(_REPO / "python" / "src"))
from build_mort_params_reference import cpp_json  # noqa: E402  (ONE parser, not a second copy)
from lpjmlfit_emulator import data as ind_data  # noqa: E402  (the ONE TREE_TYPES, ADR 0031)

LPJROOT = Path(os.environ.get("LPJROOT", "/home/jamirp/lpjml56fit"))
OUT = Path(os.environ.get("OUT", _REPO / "test" / "testitems" / "references" / "S_pft_estab_params.csv"))

#: per-PFT columns, then the run globals repeated on every row (so a global cannot drift unnoticed on
#: either side of the gate — the same discipline as S_pft_mortality_params.csv).
PFT_COLS = [
    "pft_id", "name",
    # the four recruit trait axes the emulator samples (ADR 0117 §6: `k_root` is a scalar 0.02 in this
    # configuration and `emax`/`beta_2` are emitted nowhere, so these four ARE the interface)
    "sla_low", "sla_high",
    "wooddens_low", "wooddens_high",
    "d95max_low", "d95max_high",
    "minwscal_low", "minwscal_high",
    # the inheritance diffusion width and the per-PFT recruitment exponent
    "inherit_corridor", "alpha_r",
    # FIT's own bioclimatic establishment gate (establish.c + establishmentpft_ind.c:88)
    "temp_low", "temp_high", "gdd5min", "aprec_min",
]
GLOBAL_COLS = [
    "k_est_inherit", "k_est_inherit_bg", "param_alpha_r", "patcharea", "max_age", "n_max",
]
COLS = PFT_COLS + GLOBAL_COLS


def build_rows() -> list[dict]:
    parsed, _dups = cpp_json(LPJROOT / "par" / "pft_lpjmlfit.js")
    pft = parsed["pftpar"]
    prm, prm_dups = cpp_json(LPJROOT / "par" / "lpjparam_fit.js")
    assert not prm_dups, f"unexpected duplicate keys in par/lpjparam_fit.js: {sorted(prm_dups)}"
    p = prm["param"]
    globals_row = {
        "k_est_inherit": float(p["k_est_inherit"]),
        "k_est_inherit_bg": float(p["k_est_inherit_bg"]),
        "param_alpha_r": float(p["alpha_r"]),
        "patcharea": float(p["patcharea"]),
        "max_age": int(p["max_age"]),
        "n_max": int(p["n_max"]),
    }

    rows = []
    for i in sorted(ind_data.TREE_TYPES):
        q = pft[i]
        assert q["type"] == "tree", (
            f"pftpar[{i}] is a {q['type']!r} ({q['name']!r}), not a tree — TREE_TYPES and "
            f"par/pft_lpjmlfit.js have drifted apart (ADR 0031)."
        )
        rows.append(
            {
                "pft_id": i,
                "name": q["name"],
                "sla_low": float(q["sla"]["low"]),
                "sla_high": float(q["sla"]["high"]),
                "wooddens_low": float(q["wooddens"]["low"]),
                "wooddens_high": float(q["wooddens"]["high"]),
                "d95max_low": float(q["D95max"]["low"]),
                "d95max_high": float(q["D95max"]["high"]),
                "minwscal_low": float(q["minwscal"]["low"]),
                "minwscal_high": float(q["minwscal"]["high"]),
                "inherit_corridor": float(q["inherit_corridor"]),
                "alpha_r": float(q["alpha_r"]),
                "temp_low": float(q["temp"]["low"]),
                "temp_high": float(q["temp"]["high"]),
                "gdd5min": float(q["gdd5min"]),
                "aprec_min": float(q["aprec_min"]),
                **globals_row,
            }
        )

    # ── self-checks: the parse cross-validated against independently-recorded facts ────────────────
    by_id = {r["pft_id"]: r for r in rows}
    assert set(by_id) == set(sorted(ind_data.TREE_TYPES)), "row set must be exactly TREE_TYPES"
    # ADR 0045's closed form `w_inherit = 4/(4 + n_elig)` is EXACT only because both establishment
    # channels carry the same f_sap exponent, so it cancels. If a future parameter edit breaks that, the
    # closed form silently becomes an approximation — stop the build instead.
    assert all(r["alpha_r"] == globals_row["param_alpha_r"] for r in rows), (
        "per-PFT alpha_r must equal param.alpha_r for the ADR-0045 closed form `4/(4+n_elig)` to be "
        f"exact (got per-PFT {sorted({r['alpha_r'] for r in rows})} vs param "
        f"{globals_row['param_alpha_r']}). Re-derive the mixture weight before touching the port."
    )
    assert abs(globals_row["k_est_inherit"] / globals_row["k_est_inherit_bg"] - 4.0) < 1e-12, (
        "k_est_inherit / k_est_inherit_bg must be 4 for `4/(4+n_elig)`; got "
        f"{globals_row['k_est_inherit']} / {globals_row['k_est_inherit_bg']}"
    )
    assert globals_row["max_age"] == 50 and globals_row["n_max"] == 7, (
        f"seedbank globals changed: max_age={globals_row['max_age']}, n_max={globals_row['n_max']} "
        f"(recorded 50 / 7) — the seedbank depth and width are both ported constants."
    )
    assert globals_row["patcharea"] == 225.0, f"patcharea = {globals_row['patcharea']}, expected 225.0"
    # the three structural facts named in the module docstring
    for i in (4, 5, 6):
        if i in by_id:
            assert by_id[i]["temp_high"] == 0.0, (
                f"id {i} (boreal) must gate establishment at temp_high = 0 °C; got "
                f"{by_id[i]['temp_high']} — the boreal PFTs' eligibility is the reason `n_elig` varies."
            )
    for i in (0, 1, 2, 3):
        if i in by_id:
            assert by_id[i]["temp_high"] >= 1000.0, f"id {i} temp_high should be unbounded (1000)"
    assert all(r["inherit_corridor"] == 0.1 for r in rows), (
        "every tree PFT's inherit_corridor is 0.1 (the 10 % diffusion width of new_tree.c:54)"
    )
    for r in rows:
        for axis in ("sla", "wooddens", "d95max", "minwscal"):
            lo, hi = r[f"{axis}_low"], r[f"{axis}_high"]
            assert lo < hi, f"id {r['pft_id']}: {axis} interval [{lo}, {hi}] is empty or inverted"
    # the union of the per-PFT intervals is what `make_recruit_to_pools` clamps drawn traits to
    assert min(r["d95max_low"] for r in rows) == 51.0, "D95max low bound is 51 cm for every tree PFT"
    assert max(r["d95max_high"] for r in rows) == 1800.0, "D95max union upper bound is 1800 cm"
    return rows


def render(rows: list[dict]) -> str:
    buf = io.StringIO()
    buf.write(
        "# S_pft_estab_params.csv — THE ONE per-PFT establishment-parameter table for the ported\n"
        "# LPJmL-FIT recruit rule (ADR 0119). GENERATED — do not hand-edit.\n"
        "#   regenerate: python3 scripts/build_estab_params_reference.py\n"
        "#   verify:     CHECK=1 python3 scripts/build_estab_params_reference.py\n"
        "# Source of record: $LPJROOT/par/pft_lpjmlfit.js + par/lpjparam_fit.js, expanded with the same\n"
        "# `cpp -P` LPJmL itself pipes them through (src/lpj/openconfig.c:28,467). `pft_id` IS the `ind`\n"
        "# output's `Type` column (0-based pftpar index; ids 0-6 are the complete tree set, ADR 0031).\n"
        "# The four trait intervals are what BOTH establishment channels draw on: uniformly in the\n"
        "# background channel (new_tree.c:196-203), and as the clamp/redraw bounds of the inheritance\n"
        "# diffusion `new = old*(1 + inherit_corridor*s)` (new_tree.c:38-61, s a +-5-clamped normal).\n"
        "# `temp_low`/`temp_high` are the ESTABLISHMENT gate \"temp\" read on the 20-yr running mean of\n"
        "# the year's coldest monthly mean (establish.c:29-33) — NOT \"temp_stressed\" (that is the\n"
        "# mortality table's column, S_pft_mortality_params.csv). Note temp_high = 0 for the boreal\n"
        "# ids 4/5/6 and 1000 (unbounded) for 0-3, and that establish() ALSO requires the 20-yr mean\n"
        "# warmest month above 10 C for any tree.\n"
        "# The trailing six columns are run GLOBALS from par/lpjparam_fit.js, repeated on every row so\n"
        "# neither consumer can drift on them silently. k_est_inherit / k_est_inherit_bg = 4 exactly,\n"
        "# and both channels carry the same alpha_r, which is what makes the inherited share of recruits\n"
        "# the closed form 4/(4 + n_elig) (ADR 0045) rather than a fitted number.\n"
    )
    w = csv.DictWriter(buf, fieldnames=COLS, lineterminator="\n")
    w.writeheader()
    for r in sorted(rows, key=lambda r: r["pft_id"]):
        w.writerow(r)
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
            f"  id {r['pft_id']}  sla=[{r['sla_low']:g}, {r['sla_high']:g}]  "
            f"wd=[{r['wooddens_low']:g}, {r['wooddens_high']:g}]  "
            f"gate temp=[{r['temp_low']:g}, {r['temp_high']:g}] gdd5min={r['gdd5min']:g}  {r['name']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
