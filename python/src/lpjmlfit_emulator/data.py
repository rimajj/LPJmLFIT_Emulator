"""Data validation for the frozen LPJmL-FIT ``ind`` (individual-tree) table.

Schema source: DESIGN.md §3.1 (writer ``src/lpj/fwriteoutput_ind.c:28-57``). The
CSV/TXT ground-truth data has exactly 29 columns in a fixed order (header names as
written by the model, e.g. ``index`` -> ``ID``, ``id`` -> ``Type``,
``mort_prob`` -> ``mort``). One row per living individual per year (natural stands
only; grass PFTs Type 8 written with tree fields zeroed).

This module is a lightweight SCHEMA gate (Engineering Standards §2, test class 6
"Data validation"). Range / units / NaN / shape checks are added to the loader as
it grows.
"""

from __future__ import annotations

from collections.abc import Iterable

#: Frozen 29-column ``ind`` schema, in on-disk order (DESIGN.md §3.1).
IND_COLUMNS: tuple[str, ...] = (
    "Year",
    "ID",
    "Type",
    "Height",
    "Age",
    "agb",
    "vegc",
    "transp",
    "npp",
    "gpp",
    "wscal_mean",
    "SLA",
    "Longevity",
    "Wooddens",
    "LAI",
    "fpc_ind",
    "minwscal",
    "D95",
    "D95max",
    "beta_root",
    "k_root",
    "mort_npp",
    "mort_age",
    "mort_water",
    "mort_temp",
    "mort",
    "isdead",
    "Patch",
    "Cell",
)

assert len(IND_COLUMNS) == 29, "ind schema must have exactly 29 columns"

__all__ = ["IND_COLUMNS", "ind_columns", "validate_ind_schema"]


def ind_columns() -> list[str]:
    """Return the frozen ``ind`` column names as a fresh list."""
    return list(IND_COLUMNS)


def _columns_of(obj) -> list[str]:
    """Extract column names from a pandas/polars DataFrame or a sequence of names."""
    cols = getattr(obj, "columns", None)
    if cols is not None:  # pandas Index or polars list of names
        return [str(c) for c in list(cols)]
    if isinstance(obj, (str, bytes)):
        raise TypeError(
            "validate_ind_schema expects a pandas/polars DataFrame or a sequence "
            "of column names, not a bare string"
        )
    if isinstance(obj, Iterable):
        return [str(c) for c in obj]
    raise TypeError(
        "validate_ind_schema expects a pandas/polars DataFrame or a sequence of "
        f"column names, got {type(obj).__name__}"
    )


def validate_ind_schema(df, *, ordered: bool = True) -> bool:
    """Validate that ``df`` matches the frozen 29-column ``ind`` schema.

    Accepts a pandas DataFrame, a polars DataFrame, or any sequence of column names.
    Raises ValueError on any missing or extra column, on duplicate columns, and
    (when ``ordered`` is True, the default) on a column-ORDER mismatch. Returns
    True on success.
    """
    got = _columns_of(df)
    expected = list(IND_COLUMNS)
    expected_set = set(expected)
    got_set = set(got)

    missing = [c for c in expected if c not in got_set]
    extra = [c for c in got if c not in expected_set]
    if missing or extra:
        raise ValueError(
            f"ind schema mismatch: missing={missing}, extra={extra} "
            f"(expected {len(expected)} columns, got {len(got)})"
        )
    if len(got) != len(expected):  # same name set but a duplicate present
        raise ValueError(
            f"ind schema has duplicate columns: got {len(got)} names for {len(expected_set)} unique"
        )
    if ordered and got != expected:
        raise ValueError(
            f"ind schema column ORDER mismatch:\n  got     : {got}\n  expected: {expected}"
        )
    return True
