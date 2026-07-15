"""pytest bootstrap for the S-emulator prototype.

Ensures ``src/`` is importable when running against the reused conda env without an
editable install (redundant with ``[tool.pytest.ini_options] pythonpath`` in
pyproject.toml, kept for robustness across invocation styles), and registers a
deterministic Hypothesis profile (fixed-seed discipline, seed 42) when Hypothesis
is available. Hypothesis is optional: if it is not installed, property tests skip.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

try:  # deterministic Hypothesis config; skipped cleanly if not installed
    from hypothesis import HealthCheck, settings

    settings.register_profile(
        "ci",
        settings(
            deadline=None,
            derandomize=True,
            max_examples=100,
            suppress_health_check=[HealthCheck.too_slow],
        ),
    )
    settings.load_profile("ci")
except ImportError:  # pragma: no cover - env without hypothesis
    pass
