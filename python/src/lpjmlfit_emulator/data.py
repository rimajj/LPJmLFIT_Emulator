"""Data validation for the frozen LPJmL-FIT ``ind`` (individual-tree) table.

Schema source: DESIGN.md §3.1 (writer ``src/lpj/fwriteoutput_ind.c:28-57``). The
CSV/TXT ground-truth data has exactly 29 columns in a fixed order (header names as
written by the model, e.g. ``index`` -> ``ID``, ``id`` -> ``Type``,
``mort_prob`` -> ``mort``). One row per living individual per year (natural stands
only; grass PFTs Type 8 written with tree fields zeroed).

This module is a lightweight SCHEMA gate (Engineering Standards §2, test class 6
"Data validation"). Range / units / NaN / shape checks are added to the loader as
it grows.

Provenance: the frozen 29-column schema is from DESIGN.md §3.1; the column-group
constants and ``build_patch_summaries`` were ported once on 2026-07-16 from the
frozen sibling emulator module ``data_prep.py`` (newest sibling source mtime
2026-07-14). This repository is the single source of truth for component S; the
sibling is frozen (ADR 0012) — port once, do not sync. The sibling's parquet/path
pipeline glue (``living_trees_lf``, ``build_transitions``, ``build_splits``,
``tree_level_training``, ``build_tree_step``, ``build_recruit_tables``) is
deliberately NOT ported — those are run-specific data-prep scripts, not library API.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # import only for type checkers; runtime imports are lazy (see below)
    import pandas as pd

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

#: PFT type codes (``Type`` column). Grass PFTs are written with tree fields zeroed;
#: tree PFTs carry the full trait/size record (config ``variables``; DESIGN.md §3.1).
TREE_TYPES: tuple[int, ...] = (1, 2, 3, 4, 5)
GRASS_TYPE: int = 8

#: Size/diagnostic pools re-derived by allometric fan-out (heavy right-skew → log1p).
DIAG_VARS: tuple[str, ...] = ("agb", "vegc", "npp", "LAI", "fpc_ind", "D95")
#: Traits ~fixed at establishment (quasi-stationary); modelled jointly per PFT.
TRAIT_VARS: tuple[str, ...] = ("SLA", "Wooddens", "beta_root")

#: Default per-(Cell,Patch,Year) summary statistics for :func:`build_patch_summaries`.
DEFAULT_SUMMARY_STATS: tuple[str, ...] = ("mean", "sd", "q25", "q50", "q75")

__all__ = [
    "IND_COLUMNS",
    "TREE_TYPES",
    "GRASS_TYPE",
    "DIAG_VARS",
    "TRAIT_VARS",
    "DEFAULT_SUMMARY_STATS",
    "ind_columns",
    "validate_ind_schema",
    "load_ind",
    "build_patch_summaries",
]


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


def load_ind(path, *, validate: bool = True, ordered: bool = True) -> pd.DataFrame:
    """Load an ``ind`` (individual-tree) table from CSV/TXT or Parquet into pandas.

    The reader is chosen from the file suffix (``.parquet``/``.pq`` → Parquet, else
    delimited text). When ``validate`` is True (the default), the loaded frame is
    checked against the frozen 29-column schema via :func:`validate_ind_schema`
    (``ordered`` forwarded), raising ``ValueError`` on any mismatch.
    """
    import pandas as pd  # lazy: keep the schema gate importable without pandas installed

    p = str(path)
    if p.lower().endswith((".parquet", ".pq")):
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    if validate:
        validate_ind_schema(df, ordered=ordered)
    return df


def build_patch_summaries(
    living,
    *,
    summary_vars: Iterable[str] = TRAIT_VARS + DIAG_VARS,
    stats: Iterable[str] = DEFAULT_SUMMARY_STATS,
    tree_types: Iterable[int] = TREE_TYPES,
    keys: Iterable[str] = ("Cell", "Patch", "Year"),
):
    """Per-``(Cell, Patch, Year)`` summary of a living-tree table (polars in, polars out).

    Ported (generalized, I/O-free) from the sibling ``data_prep.build_patch_summaries`` +
    ``_stat_exprs`` + ``_type_fraction_exprs``: for each key group it emits ``n_trees``,
    then for every ``summary_vars`` variable the requested ``stats`` (``mean``; ``sd`` with
    nulls filled to 0; and ``q<pct>`` quantiles, e.g. ``q25`` → 0.25), plus the per-PFT
    fractions ``frac_type<t>`` for each ``t`` in ``tree_types``. Faithful to the sibling's
    expression logic; the sibling's parquet write and grass left-join are the caller's job.

    ``living`` may be a polars DataFrame/LazyFrame or a pandas DataFrame (converted).
    """
    import polars as pl  # lazy: heavy dep, only needed for this aggregation

    if isinstance(living, pl.LazyFrame):
        lf = living
    elif isinstance(living, pl.DataFrame):
        lf = living.lazy()
    else:  # pandas or anything polars can wrap
        lf = (
            pl.from_pandas(living).lazy()
            if hasattr(living, "columns")
            else pl.DataFrame(living).lazy()
        )

    keys = list(keys)
    exprs = [pl.len().alias("n_trees")]
    for v in summary_vars:
        for s in stats:
            if s == "mean":
                exprs.append(pl.col(v).mean().alias(f"{v}_mean"))
            elif s == "sd":
                exprs.append(pl.col(v).std().fill_null(0.0).alias(f"{v}_sd"))
            elif s.startswith("q"):
                q = int(s[1:]) / 100.0
                exprs.append(pl.col(v).quantile(q).alias(f"{v}_{s}"))
            else:
                raise ValueError(f"unknown summary stat {s!r} (expected mean/sd/q<pct>)")
    exprs += [(pl.col("Type") == t).mean().alias(f"frac_type{t}") for t in tree_types]
    return lf.group_by(keys).agg(exprs).sort(keys).collect()
