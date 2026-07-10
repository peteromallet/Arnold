"""Forbidden authoring terms — the single source of truth.

These terms describe authoring patterns that must NOT appear in generator
scripts under ``scripts/`` (and other scanned surfaces). The boundary test
``tests/docs/test_m5_generated_scans.py`` enforces them by substring scan, and
the AST import-scanners in ``scripts/`` (e.g.
``generate_native_representation_evidence.py``) source their detection set from
``FORBIDDEN_MEGAPLAN_IMPORT_PREFIXES`` here.

Why this module exists
----------------------
Before this module, the forbidden-terms list lived as independent copies in the
boundary test and in scanners under ``scripts/``. A scanner that hardcodes the
literal it is built to detect trips the substring test *on itself* — a false
positive that cannot be resolved without weakening the test or the baseline.
Centralising the terms lets scanners reference the constant instead of
re-authoring the literal, so the literal never re-enters a scanned ``scripts/``
file. See ``test_forbidden_terms_single_source``.

Boundary note
-------------
This module is pure string *data* — it contains no ``import megaplan`` /
``from megaplan`` and honours the ``arnold/conformance/`` purity contract (see
``arnold/conformance/__init__.py``). Sibling modules such as
``deleted_surfaces.py`` already carry megaplan path strings as data.
"""

from __future__ import annotations

# Authoring patterns forbidden in generator scripts. Kept as a tuple so callers
# iterate in a stable order; defined in exactly one place (see
# test_forbidden_terms_single_source).
FORBIDDEN_AUTHORING_TERMS = (
    "PipelineBuilder",
    "Stage(",
    "Edge(",
    "@stage",
    "@step",
    "run_pipeline",
    "from arnold.pipeline",
    "import arnold.pipeline",
    "arnold.pipelines.megaplan",
)

# Legacy CLI command fragments forbidden in generator scripts.
FORBIDDEN_COMMAND_TERMS = (
    "arnold pipelines describe",
    "arnold pipelines check",
    "arnold pipelines doctor",
    "arnold pipelines new",
    "arnold pipeline ",
)

# The subset of ``FORBIDDEN_AUTHORING_TERMS`` that are import-path prefixes.
# AST scanners that walk for illegal imports source their detection set from
# here instead of hardcoding the literal, so the literal never re-enters a
# scanned ``scripts/`` file (which would trip the substring test on the scanner
# itself). ``test_forbidden_terms_single_source`` asserts every entry here is a
# member of ``FORBIDDEN_AUTHORING_TERMS`` so the two cannot drift.
FORBIDDEN_MEGAPLAN_IMPORT_PREFIXES = (
    "arnold.pipelines.megaplan",
)
