"""The `python` CI gate on the ONE per-PFT mortality-parameter table (ADR 0047).

``scripts/build_slow_flux_table.py::PFT_PARAMS`` and ``src/trait_mortality.jl``'s
``PFT_MORT_PARAMS`` are two consumers of the same physical constants, and the source of record for
both is the committed
``test/testitems/references/S_pft_mortality_params.csv``, generated from
``$LPJROOT/par/pft_lpjmlfit.js`` by ``scripts/build_mort_params_reference.py``. The Julia side is
gated by ``test/testitems/slow_trait_mortality_tests.jl``.

This file is what makes the PYTHON side's gate run in CI. It has to live here rather than in
``scripts/`` because the ``python`` workflow watches ``python/**`` only — ``scripts/*.py`` is
neither linted nor tested by any gate (CLAUDE.md §5), so an import-time assert inside the builder
fires only when somebody runs the builder. ADR 0031 is the record of what an unchecked second copy
of a constant costs: a stale ``TREE_TYPES`` hid 32.5 % of survivor tree stems, and 16.7 % of
tree-bearing cells, for months.

The builder is loaded BY PATH (it is a script, not part of the installed package) and is
import-safe: its module level defines constants and functions only.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_BUILDER = _REPO / "scripts" / "build_slow_flux_table.py"
_REFERENCE = _REPO / "test" / "testitems" / "references" / "S_pft_mortality_params.csv"


def _load_builder():
    """Import ``scripts/build_slow_flux_table.py`` by path, skipping if its deps are absent."""
    if not _BUILDER.exists():  # pragma: no cover - the script is committed
        pytest.skip(f"{_BUILDER} not present")
    pytest.importorskip("polars")
    pytest.importorskip("numpy")
    spec = importlib.util.spec_from_file_location("_build_slow_flux_table", _BUILDER)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_reference_is_committed_and_well_formed():
    assert _REFERENCE.exists(), (
        f"{_REFERENCE} is missing — regenerate with "
        "`python3 scripts/build_mort_params_reference.py` (ADR 0047)."
    )
    lines = [
        ln
        for ln in _REFERENCE.read_text().splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    hdr = [c.strip() for c in lines[0].split(",")]
    assert hdr[0] == "pft_id"
    rows = [[c.strip() for c in ln.split(",")] for ln in lines[1:]]
    assert len(rows) == 7, "ids 0-6 are the complete FIT tree set (ADR 0031)"
    assert all(len(r) == len(hdr) for r in rows), "a PFT name must not contain a comma"
    assert sorted(int(r[0]) for r in rows) == list(range(7))
    # the columns the hazard needs must all be present, so a silently-shortened reference fails here
    for key in (
        "wdmort_1",
        "wdmort_2",
        "mort_water_factor",
        "mort_water_res",
        "mort_temp_factor",
        "longevity",
        "temp_low",
        "temp_high",
        "aphen_min",
        "lai_sapl",
        "allom1",
        "allom2",
        "allom3",
        "kpr",
        "k_latosa",
        "wood_sapl",
        "k_mort",
        "kmort_2",
        "kmortbg_lnf",
        "kmortbg_q",
        "bm_inc_counter_max",
        "ndayyear",
    ):
        assert key in hdr, f"reference is missing column {key!r}"


def test_pft_params_match_the_generated_c_reference():
    """The builder's own gate, run under CI. Also asserts it is not a no-op."""
    mod = _load_builder()
    n = mod.gate_pft_params_against_reference()
    assert n == 7


def test_gate_actually_fails_on_a_perturbed_value():
    """A gate that cannot fail is not a gate — perturb one value and require the assert to fire.

    This is the ADR-0032 lesson in miniature: the previous "predicted targets are inside the
    training band" check could never fail, so it hid a 2-order-of-magnitude basis shift for 5 days.
    """
    mod = _load_builder()
    original = mod.PFT_PARAMS[3]["wdmort_1"]
    try:
        mod.PFT_PARAMS[3]["wdmort_1"] = original + 0.001
        with pytest.raises(AssertionError, match="wdmort_1"):
            mod.gate_pft_params_against_reference()
    finally:
        mod.PFT_PARAMS[3]["wdmort_1"] = original
    assert mod.gate_pft_params_against_reference() == 7


def test_the_three_rows_a_beech_default_used_to_get_wrong():
    """ADR 0031's measured defect: a temperate/ANGIO default was applied to every PFT."""
    mod = _load_builder()
    p = mod.PFT_PARAMS
    assert p[5]["longevity"] == 125.0  # NOT TREE_LONGEVITY 400 — a 3.2x age-mortality error
    assert p[5]["mort_water_factor"] == 20.0  # NOT beech's 5
    assert p[1]["mort_water_res"] == 0.25  # XERIC, not ANGIO 0.75
    assert p[2]["mort_water_res"] == 0.25
    assert p[0]["wdmort_1"] == -2.458  # tropical, not temperate -2.465
    assert p[3]["wdmort_1"] == -2.465
    assert all(p[i]["verified"] for i in range(7))
