"""Tests for ``lpjmlfit_emulator.data`` schema validation (pytest + Hypothesis).

pandas and polars are both present in the reused env; each is guarded with
``importorskip`` anyway. Hypothesis is OPTIONAL and its property tests skip
gracefully when absent. Fixed seed 42.
"""

from __future__ import annotations

import pytest

from lpjmlfit_emulator.data import IND_COLUMNS, ind_columns, validate_ind_schema

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
