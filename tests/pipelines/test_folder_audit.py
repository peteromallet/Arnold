"""Retired folder-audit pipeline compatibility suite.

The pipeline was archived in d47a4ce05. Current first-class native pipeline
coverage lives in the active pipeline contract suites.
"""

import pytest


@pytest.mark.skip(reason="folder-audit pipeline was archived; current native targets remain covered")
def test_folder_audit_pipeline_retired() -> None:
    pass
