"""M8 acceptance regression: route-bypass prevention (T12).

Covers one motivating failure class: unknown ``StepInvocation`` adapter
kinds must fail closed during validation, preventing a pipeline from
bypassing the registered adapter surface.

The test uses only the neutral :func:`arnold.workflow.validator.validate`
and :class:`arnold.execution.step_invocation.StepInvocation` — no
evidence-pack runtime fixtures or imports from
``arnold.pipelines.evidence_pack``.

Diagnostic path
---------------
- ``validate_invocation_requirements`` inspects ``Stage.invocation.kind``.
- The ``StepInvocationAdapterRegistry`` starts with only ``"model"``
  registered (via a ``_ModelAdapterPlaceholder``).
- Any other kind — ``"tool"``, ``"human"``, ``"state"``, or arbitrary
  custom kinds — fails to resolve and produces an
  ``invocation.unknown_adapter`` diagnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from arnold.execution.step_invocation import StepInvocation
from arnold.pipeline.types import Edge, Pipeline, Stage
from arnold.workflow.validator import (
    UNKNOWN_ADAPTER_CODE,
    validate,
    validate_invocation_requirements,
)


# ---------------------------------------------------------------------------
# Minimal stub step for validation-only pipelines
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _StubStep:
    """A step that must never be dispatched by the validator (static only)."""

    name: str = "stub"
    kind: str = "stub"

    def run(self, ctx: Any) -> Any:
        raise RuntimeError("static validator must not dispatch")


def _pipeline(stages: dict[str, Stage], *, entry: str = "start") -> Pipeline:
    """Build a minimal Pipeline from a dict of Stage objects."""
    return Pipeline(entry=entry, stages=stages)


# ---------------------------------------------------------------------------
# Route-bypass: unknown adapter kinds are rejected
# ---------------------------------------------------------------------------


class TestRouteBypassPrevention:
    """Unknown StepInvocation adapter kinds are rejected during validation.

    This is the M8 gate for route-bypass: a pipeline that tries to use an
    unregistered adapter kind (e.g. ``"tool"``) must fail validation before
    any executor can dispatch it.
    """

    def test_tool_kind_rejected(self) -> None:
        """'tool' adapter kind is rejected (not registered)."""
        stage = Stage(
            name="start",
            step=_StubStep(name="start"),
            invocation=StepInvocation(kind="tool"),
            edges=(Edge(label="halt", target="halt"),),
        )
        diag = validate(_pipeline({"start": stage}))
        assert not diag.ok
        codes = {issue.code for issue in diag.issues}
        assert UNKNOWN_ADAPTER_CODE in codes, (
            f"Expected {UNKNOWN_ADAPTER_CODE} for 'tool' kind; "
            f"got codes: {codes}"
        )

    def test_human_kind_rejected(self) -> None:
        """'human' adapter kind is rejected (not registered)."""
        stage = Stage(
            name="start",
            step=_StubStep(name="start"),
            invocation=StepInvocation(kind="human"),
            edges=(Edge(label="halt", target="halt"),),
        )
        diag = validate(_pipeline({"start": stage}))
        assert not diag.ok
        codes = {issue.code for issue in diag.issues}
        assert UNKNOWN_ADAPTER_CODE in codes

    def test_state_kind_rejected(self) -> None:
        """'state' adapter kind is rejected (not registered)."""
        stage = Stage(
            name="start",
            step=_StubStep(name="start"),
            invocation=StepInvocation(kind="state"),
            edges=(Edge(label="halt", target="halt"),),
        )
        diag = validate(_pipeline({"start": stage}))
        assert not diag.ok
        codes = {issue.code for issue in diag.issues}
        assert UNKNOWN_ADAPTER_CODE in codes

    def test_arbitrary_custom_kind_rejected(self) -> None:
        """Any arbitrary unregistered kind is rejected."""
        stage = Stage(
            name="start",
            step=_StubStep(name="start"),
            invocation=StepInvocation(kind="custom-bypass-attempt"),
            edges=(Edge(label="halt", target="halt"),),
        )
        diag = validate(_pipeline({"start": stage}))
        assert not diag.ok
        codes = {issue.code for issue in diag.issues}
        assert UNKNOWN_ADAPTER_CODE in codes

    def test_model_kind_accepted(self) -> None:
        """The 'model' adapter kind is registered and passes validation."""
        stage = Stage(
            name="start",
            step=_StubStep(name="start"),
            invocation=StepInvocation(kind="model"),
            edges=(Edge(label="halt", target="halt"),),
        )
        diag = validate(_pipeline({"start": stage}))
        # model kind is registered — should not report unknown_adapter
        codes = {issue.code for issue in diag.issues}
        assert UNKNOWN_ADAPTER_CODE not in codes, (
            f"'model' kind should be registered; got codes: {codes}"
        )

    def test_no_invocation_passes_validation(self) -> None:
        """A stage with no invocation (None) passes validation cleanly."""
        stage = Stage(
            name="start",
            step=_StubStep(name="start"),
            invocation=None,
            edges=(Edge(label="halt", target="halt"),),
        )
        diag = validate(_pipeline({"start": stage}))
        codes = {issue.code for issue in diag.issues}
        assert UNKNOWN_ADAPTER_CODE not in codes

    def test_diagnostic_includes_invocation_kind_and_registered_kinds(self) -> None:
        """The unknown-adapter diagnostic carries the offending kind and
        the list of registered kinds in its details."""
        stage = Stage(
            name="scan",
            step=_StubStep(name="scan"),
            invocation=StepInvocation(kind="unregistered-scanner"),
            edges=(Edge(label="halt", target="halt"),),
        )
        diag = validate(_pipeline({"scan": stage}, entry="scan"))
        assert not diag.ok

        unknown_issues = [
            issue for issue in diag.issues
            if issue.code == UNKNOWN_ADAPTER_CODE
        ]
        assert len(unknown_issues) == 1
        issue = unknown_issues[0]
        assert issue.stage == "scan"
        assert issue.details["invocation_kind"] == "unregistered-scanner"
        assert "model" in issue.details["registered_kinds"]

    def test_validate_invocation_requirements_direct(self) -> None:
        """validate_invocation_requirements can be called directly and
        returns the expected structured diagnostics."""
        stage = Stage(
            name="direct-test",
            step=_StubStep(name="direct-test"),
            invocation=StepInvocation(kind="direct-bypass"),
            edges=(Edge(label="halt", target="halt"),),
        )
        diag = validate_invocation_requirements(
            _pipeline({"direct-test": stage}, entry="direct-test")
        )
        assert not diag.ok
        codes = {issue.code for issue in diag.issues}
        assert UNKNOWN_ADAPTER_CODE in codes


# ---------------------------------------------------------------------------
# Route-bypass: multiple stages with unknown adapters
# ---------------------------------------------------------------------------


class TestRouteBypassMultipleStages:
    """Multiple stages with unknown adapters are all reported."""

    def test_two_unknown_adapters_both_reported(self) -> None:
        """Two stages each with an unknown adapter → both reported."""
        stages = {
            "ingest": Stage(
                name="ingest",
                step=_StubStep(name="ingest"),
                invocation=StepInvocation(kind="tool"),
                edges=(Edge(label="next", target="validate"),),
            ),
            "validate": Stage(
                name="validate",
                step=_StubStep(name="validate"),
                invocation=StepInvocation(kind="human"),
                edges=(Edge(label="halt", target="halt"),),
            ),
        }
        diag = validate(_pipeline(stages, entry="ingest"))
        unknown_issues = [
            issue for issue in diag.issues
            if issue.code == UNKNOWN_ADAPTER_CODE
        ]
        assert len(unknown_issues) == 2, (
            f"Expected 2 unknown-adapter issues, got {len(unknown_issues)}: "
            f"{[(i.stage, i.details.get('invocation_kind')) for i in unknown_issues]}"
        )
        reported_stages = {issue.stage for issue in unknown_issues}
        assert reported_stages == {"ingest", "validate"}

    def test_mixed_known_and_unknown(self) -> None:
        """A pipeline with one known ('model') and one unknown ('tool')
        adapter reports only the unknown one."""
        stages = {
            "first": Stage(
                name="first",
                step=_StubStep(name="first"),
                invocation=StepInvocation(kind="model"),
                edges=(Edge(label="next", target="second"),),
            ),
            "second": Stage(
                name="second",
                step=_StubStep(name="second"),
                invocation=StepInvocation(kind="tool"),
                edges=(Edge(label="halt", target="halt"),),
            ),
        }
        diag = validate(_pipeline(stages, entry="first"))
        unknown_issues = [
            issue for issue in diag.issues
            if issue.code == UNKNOWN_ADAPTER_CODE
        ]
        assert len(unknown_issues) == 1
        assert unknown_issues[0].stage == "second"
        assert unknown_issues[0].details["invocation_kind"] == "tool"


# ---------------------------------------------------------------------------
# Boundary: no evidence-pack imports
# ---------------------------------------------------------------------------


class TestRouteBypassNoEvidencePackImports:
    """Route-bypass tests must not depend on evidence-pack runtime fixtures.

    This class mechanically verifies that the test module does not import
    from ``arnold.pipelines.evidence_pack``.
    """

    def test_no_evidence_pack_imports_in_this_module(self) -> None:
        """This test module does not import from evidence_pack."""
        import ast
        import inspect

        source = inspect.getsource(inspect.getmodule(self.test_no_evidence_pack_imports_in_this_module))
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "evidence_pack" in module:
                    assert False, (
                        f"evidence_pack import found in route-bypass test: {module}"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if "evidence_pack" in alias.name:
                        assert False, (
                            f"evidence_pack import found in route-bypass test: {alias.name}"
                        )
