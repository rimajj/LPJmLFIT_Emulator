"""Tests for ``lpjmlfit_emulator.data`` schema validation (pytest + Hypothesis).

pandas and polars are both present in the reused env; each is guarded with
``importorskip`` anyway. Hypothesis is OPTIONAL and its property tests skip
gracefully when absent. Fixed seed 42.
"""

from __future__ import annotations

import pytest

from lpjmlfit_emulator.data import (
    DIAG_VARS,
    IND_COLUMNS,
    TRAIT_VARS,
    TREE_TYPES,
    build_patch_summaries,
    ind_columns,
    load_ind,
    validate_ind_schema,
)

SEED = 42

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    HAS_HYPOTHESIS = True
except ImportError:  # pragma: no cover - exercised only when hypothesis is absent
    HAS_HYPOTHESIS = False

    def given(*_a, **_k):
        def deco(fn):
            return fn

        return deco

    def settings(*_a, **_k):
        def deco(fn):
            return fn

        return deco

    class _Dummy:
        def __getattr__(self, _name):
            return lambda *a, **k: self

    class _NoStrategies:
        def __getattr__(self, _name):
            return lambda *a, **k: _Dummy()

    st = _NoStrategies()


requires_hypothesis = pytest.mark.skipif(
    not HAS_HYPOTHESIS, reason="hypothesis not installed in this env"
)


def _row_dict():
    """One-row column->list mapping covering the full schema."""
    return {c: [0] for c in IND_COLUMNS}


# --------------------------------------------------------------------------
# Plain unit tests (always run)
# --------------------------------------------------------------------------
def test_schema_has_29_unique_columns():
    assert len(IND_COLUMNS) == 29
    assert len(set(IND_COLUMNS)) == 29
    assert ind_columns() == list(IND_COLUMNS)


def test_accepts_column_list():
    assert validate_ind_schema(list(IND_COLUMNS)) is True


def test_accepts_pandas():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame(_row_dict())
    assert validate_ind_schema(df) is True


def test_accepts_polars():
    pl = pytest.importorskip("polars")
    df = pl.DataFrame(_row_dict())
    assert validate_ind_schema(df) is True


def test_rejects_missing_column():
    cols = list(IND_COLUMNS)[:-1]  # drop "Cell"
    with pytest.raises(ValueError, match="missing"):
        validate_ind_schema(cols)


def test_rejects_extra_column():
    cols = list(IND_COLUMNS) + ["bogus_extra"]
    with pytest.raises(ValueError, match="extra"):
        validate_ind_schema(cols)


def test_rejects_wrong_order():
    cols = list(IND_COLUMNS)
    cols[0], cols[1] = cols[1], cols[0]
    with pytest.raises(ValueError, match="ORDER"):
        validate_ind_schema(cols)


def test_order_not_checked_when_unordered():
    cols = list(IND_COLUMNS)
    cols[0], cols[1] = cols[1], cols[0]
    assert validate_ind_schema(cols, ordered=False) is True


def test_rejects_bare_string():
    with pytest.raises(TypeError):
        validate_ind_schema("Year,ID,Type")


# --------------------------------------------------------------------------
# load_ind (CSV/Parquet loader with schema validation)
# --------------------------------------------------------------------------
def test_load_ind_csv_valid(tmp_path):
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame([[0] * len(IND_COLUMNS)], columns=list(IND_COLUMNS))
    p = tmp_path / "ind.csv"
    df.to_csv(p, index=False)
    out = load_ind(p)  # validate=True by default
    assert list(out.columns) == list(IND_COLUMNS)
    assert len(out) == 1


def test_load_ind_csv_bad_schema_raises(tmp_path):
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame([[1, 2, 3]], columns=["a", "b", "c"])
    p = tmp_path / "bad.csv"
    df.to_csv(p, index=False)
    with pytest.raises(ValueError):
        load_ind(p)
    # validation can be skipped
    assert list(load_ind(p, validate=False).columns) == ["a", "b", "c"]


# --------------------------------------------------------------------------
# build_patch_summaries (generalized, I/O-free)
# --------------------------------------------------------------------------
def test_build_patch_summaries_shape_and_columns():
    pd = pytest.importorskip("pandas")
    pytest.importorskip("polars")
    rng = __import__("numpy").random.default_rng(SEED)
    n = 300
    living = pd.DataFrame(
        {
            "Cell": rng.integers(0, 3, n),
            "Patch": rng.integers(0, 2, n),
            "Year": rng.integers(2000, 2003, n),
            "Type": rng.choice(TREE_TYPES, n),
            **{v: rng.uniform(0.1, 1.0, n) for v in TRAIT_VARS},
            **{v: rng.uniform(0.0, 50.0, n) for v in DIAG_VARS},
        }
    )
    summ = build_patch_summaries(living)
    # keys present, plus n_trees, the requested stats, and per-PFT fractions
    for key in ("Cell", "Patch", "Year", "n_trees"):
        assert key in summ.columns
    assert "agb_q50" in summ.columns and "SLA_mean" in summ.columns and "agb_sd" in summ.columns
    for t in TREE_TYPES:
        assert f"frac_type{t}" in summ.columns
    # one summary row per (Cell,Patch,Year) group and n_trees sums back to the input count
    import polars as pl

    assert summ.height == living[["Cell", "Patch", "Year"]].drop_duplicates().shape[0]
    assert int(summ.select(pl.col("n_trees").sum()).item()) == n


# --------------------------------------------------------------------------
# Hypothesis property tests (skipped if hypothesis absent)
# --------------------------------------------------------------------------
@requires_hypothesis
@settings(deadline=None, derandomize=True, max_examples=50)
@given(st.integers(min_value=0, max_value=len(IND_COLUMNS) - 1))
def test_prop_any_single_missing_column_rejected(drop_idx):
    cols = list(IND_COLUMNS)
    del cols[drop_idx]
    with pytest.raises(ValueError):
        validate_ind_schema(cols)


@requires_hypothesis
@settings(deadline=None, derandomize=True, max_examples=50)
@given(st.text(min_size=1, max_size=12).filter(lambda s: s not in set(IND_COLUMNS)))
def test_prop_any_extra_column_rejected(extra):
    cols = list(IND_COLUMNS) + [extra]
    with pytest.raises(ValueError):
        validate_ind_schema(cols)
