"""Durable-subject classification and static omission lint.

This module implements the durability classification engine: it
determines whether a :class:`SourceDeclaration` should be classified
as *durable* (requiring a completion obligation) or *pure* (no formal
completion obligation required), and provides static lint rules for
detecting omission errors.

The classification is driven by six :data:`DURABLE_REQUIRED_INDICATORS`
that collectively identify when a subject must be treated as durable.
Static omission lint rules cross-reference the disposition rule IDs from
:file:`docs/arnold/workflow-execution-mode-dispositions.yaml` to detect
misclassifications.

.. caution::
   This package is **experimental and non-authoritative** — see
   :mod:`arnold.workflow.completion` for the full disclaimer.
"""

from __future__ import annotations

from typing import Any

from arnold.workflow.completion.spec import SubjectKind
from arnold.workflow.completion.source_declaration import SourceDeclaration

# ---------------------------------------------------------------------------
# Durable required indicators
# ---------------------------------------------------------------------------

#: Indicator — The subject is an ``@workflow`` function.
DURABLE_REQUIRED_INDICATOR_WORKFLOW = "is_workflow"

#: Indicator — The subject is an ``@step`` function.
DURABLE_REQUIRED_INDICATOR_STEP = "is_step"

#: Indicator — The subject is a dynamic task (e.g. ``dynamic_task``, ``fan_out``).
DURABLE_REQUIRED_INDICATOR_DYNAMIC_TASK = "is_dynamic_task"

#: Indicator — The subject is a registered effect adapter.
DURABLE_REQUIRED_INDICATOR_EFFECT = "is_effect"

#: Indicator — The subject is a human boundary (review gate, approval step).
DURABLE_REQUIRED_INDICATOR_HUMAN_BOUNDARY = "is_human_boundary"

#: Indicator — The subject was explicitly declared durable by the author.
DURABLE_REQUIRED_INDICATOR_DECLARED_DURABLE = "declared_durable"


#: The six conditions that together determine when a subject must be
#: classified as durable.  Each entry is a tuple of
#: ``(indicator_key, human_label)``.
#:
#: The presence of any one indicator is sufficient to classify a subject
#: as durable (with the exception of pure helpers, which are classified
#: by :func:`is_pure_helper` and bypass the durable classification).
DURABLE_REQUIRED_INDICATORS: tuple[tuple[str, str], ...] = (
    (DURABLE_REQUIRED_INDICATOR_WORKFLOW, "Subject is a @workflow function"),
    (DURABLE_REQUIRED_INDICATOR_STEP, "Subject is a @step function"),
    (DURABLE_REQUIRED_INDICATOR_DYNAMIC_TASK, "Subject is a dynamic task"),
    (DURABLE_REQUIRED_INDICATOR_EFFECT, "Subject is a registered effect adapter"),
    (
        DURABLE_REQUIRED_INDICATOR_HUMAN_BOUNDARY,
        "Subject is a human boundary (review gate, approval step)",
    ),
    (DURABLE_REQUIRED_INDICATOR_DECLARED_DURABLE, "Subject explicitly declared durable"),
)

#: All members of the sole completion-subject taxonomy are durable.  A pure
#: helper is represented by ``SourceDeclaration.kind is None``, not by a
#: sixth taxonomy member.
_INHERENTLY_DURABLE_KINDS: frozenset[SubjectKind] = frozenset(SubjectKind)


def classify_subject(
    source: SourceDeclaration,
    declared_durable_override: bool | None = None,
) -> SubjectKind | None:
    """Return the durable subject kind, or ``None`` for a pure helper.

    A subject is classified as durable if its :class:`SubjectKind` is one
    of the inherently durable kinds (workflow, step, dynamic_task, effect,
    human_boundary) **or** if it was explicitly declared durable by the
    author.

    A declaration without a subject kind is a pure helper and receives no
    completion contract.  A durable declaration is returned as its single
    :class:`SubjectKind` member.  The override is retained only to support
    callers deciding whether to trust the authored durability annotation;
    it cannot invent a sixth "pure" subject kind.

    Parameters
    ----------
    source:
        The :class:`SourceDeclaration` to classify.
    declared_durable_override:
        If provided, overrides the ``declared_durable`` field on the
        source declaration.  ``None`` means use the field's own value.

    Returns
    -------
    SubjectKind | None
        The durable kind, or ``None`` when the declaration is a pure helper.
    """
    if source.kind is None:
        if declared_durable_override:
            raise ValueError(
                "A pure helper cannot be made durable without a SubjectKind"
            )
        return None
    return source.kind


def is_pure_helper(source: SourceDeclaration) -> bool:
    """Return ``True`` if *source* describes a pure helper (not durable).

    A pure helper has no :class:`SubjectKind`.  Pure helpers do not require
    formal completion obligations and must not enter a shadow inventory.

    This is the inverse of :func:`classify_subject` when the author has
    not declared durability.

    Parameters
    ----------
    source:
        The :class:`SourceDeclaration` to check.

    Returns
    -------
    bool
        ``True`` if the subject is a pure helper.
    """
    return classify_subject(source) is None


# ---------------------------------------------------------------------------
# Static omission lint rules
# ---------------------------------------------------------------------------


class LintViolation:
    """A single omission lint violation.

    Attributes
    ----------
    rule_id:
        The disposition rule ID from
        :file:`docs/arnold/workflow-execution-mode-dispositions.yaml`
        that was violated.
    source_id:
        The ``source_id`` of the :class:`SourceDeclaration` that
        triggered the violation.
    message:
        Human-readable description of the violation.
    """

    def __init__(
        self,
        rule_id: str,
        source_id: str,
        message: str,
    ) -> None:
        self.rule_id = rule_id
        self.source_id = source_id
        self.message = message

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LintViolation):
            return NotImplemented
        return (
            self.rule_id == other.rule_id
            and self.source_id == other.source_id
            and self.message == other.message
        )

    def __hash__(self) -> int:
        return hash((self.rule_id, self.source_id, self.message))

    def __repr__(self) -> str:
        return (
            f"LintViolation(rule_id={self.rule_id!r}, "
            f"source_id={self.source_id!r}, message={self.message!r})"
        )


def _lint_workflow_declared_as_helper(
    source: SourceDeclaration,
) -> list[LintViolation]:
    """Detect workflow subjects that are misclassified as pure helpers.

    Cross-references :attr:`SubjectKind.WORKFLOW` against
    ``workflow-execution-mode-dispositions.yaml`` rule
    ``step_invokes_workflow_or_decorated_step`` (DISP-1).
    """
    violations: list[LintViolation] = []
    if source.kind == SubjectKind.WORKFLOW and is_pure_helper(source):
        violations.append(LintViolation(
            rule_id="DISP-1/step_invokes_workflow_or_decorated_step",
            source_id=source.source_id,
            message=(
                f"Subject {source.canonical_name!r} is declared "
                f"as WORKFLOW but would be classified as a pure helper. "
                f"Workflows must be classified as durable. "
                f"See DISP-1: step_invokes_workflow_or_decorated_step."
            ),
        ))
    return violations


def _lint_step_declared_as_helper(
    source: SourceDeclaration,
) -> list[LintViolation]:
    """Detect step subjects that are misclassified as pure helpers.

    Cross-references :attr:`SubjectKind.STEP` against
    ``workflow-execution-mode-dispositions.yaml`` rule
    ``step_invokes_workflow_or_decorated_step`` (DISP-1).
    """
    violations: list[LintViolation] = []
    if source.kind == SubjectKind.STEP and is_pure_helper(source):
        violations.append(LintViolation(
            rule_id="DISP-1/step_invokes_workflow_or_decorated_step",
            source_id=source.source_id,
            message=(
                f"Subject {source.canonical_name!r} is declared "
                f"as STEP but would be classified as a pure helper. "
                f"Steps must be classified as durable. "
                f"See DISP-1: step_invokes_workflow_or_decorated_step."
            ),
        ))
    return violations


def _lint_effect_declared_as_helper(
    source: SourceDeclaration,
) -> list[LintViolation]:
    """Detect effect subjects that are misclassified as pure helpers.

    Cross-references :attr:`SubjectKind.EFFECT` against
    ``workflow-execution-mode-dispositions.yaml`` rule
    ``hidden_effect_or_nondeterminism_in_helper`` (DISP-1).
    """
    violations: list[LintViolation] = []
    if source.kind == SubjectKind.EFFECT and is_pure_helper(source):
        violations.append(LintViolation(
            rule_id="DISP-1/hidden_effect_or_nondeterminism_in_helper",
            source_id=source.source_id,
            message=(
                f"Subject {source.canonical_name!r} is declared "
                f"as EFFECT but would be classified as a pure helper. "
                f"Effect adapters must be classified as durable. "
                f"See DISP-1: hidden_effect_or_nondeterminism_in_helper."
            ),
        ))
    return violations


def _lint_helper_calls_subworkflow(
    source: SourceDeclaration,
    helper_call_graph: dict[str, list[str]] | None = None,
) -> list[LintViolation]:
    """Detect pure helpers that call workflows or decorated steps.

    A helper that calls a workflow or decorated step is a
    :class:`SubjectKind` violation — the helper should be reclassified
    as appropriate.

    Cross-references ``workflow-execution-mode-dispositions.yaml`` rule
    ``step_invokes_workflow_or_decorated_step`` (DISP-1).

    Parameters
    ----------
    source:
        The source declaration to check.
    helper_call_graph:
        Optional mapping of helper canonical names to the list of
        callee canonical names they invoke.  If not provided, the
        rule is a no-op (no call-graph analysis available).
    """
    violations: list[LintViolation] = []
    if not is_pure_helper(source) or helper_call_graph is None:
        return violations
    callees = helper_call_graph.get(source.canonical_name, [])
    if not callees:
        return violations
    violations.append(LintViolation(
        rule_id="DISP-1/step_invokes_workflow_or_decorated_step",
        source_id=source.source_id,
        message=(
            f"Pure helper {source.canonical_name!r} calls "
            f"{callees!r} which includes workflow or decorated step "
            f"targets.  Helpers must not invoke durable subjects. "
            f"See DISP-1: step_invokes_workflow_or_decorated_step."
        ),
    ))
    return violations


def _lint_helper_mutates_state(
    source: SourceDeclaration,
    mutates_state: bool = False,
) -> list[LintViolation]:
    """Detect pure helpers that mutate shared state.

    Pure helpers must not mutate shared state, as this introduces
    nondeterminism that breaks authoring-preview guarantees.

    Cross-references ``workflow-execution-mode-dispositions.yaml`` rule
    ``hidden_effect_or_nondeterminism_in_helper`` (DISP-1).
    """
    violations: list[LintViolation] = []
    if not is_pure_helper(source) or not mutates_state:
        return violations
    violations.append(LintViolation(
        rule_id="DISP-1/hidden_effect_or_nondeterminism_in_helper",
        source_id=source.source_id,
        message=(
            f"Pure helper {source.canonical_name!r} mutates shared "
            f"state, which introduces nondeterminism.  Helpers must "
            f"be pure functions. "
            f"See DISP-1: hidden_effect_or_nondeterminism_in_helper."
        ),
    ))
    return violations


def _lint_helper_owns_retry(
    source: SourceDeclaration,
    owns_retry: bool = False,
) -> list[LintViolation]:
    """Detect pure helpers that own retry logic.

    Retry logic is a property of durable subjects (steps, workflows).
    Pure helpers must not own retry configuration.

    Cross-references ``workflow-execution-mode-dispositions.yaml`` rule
    ``step_invokes_workflow_or_decorated_step`` (DISP-1).
    """
    violations: list[LintViolation] = []
    if not is_pure_helper(source) or not owns_retry:
        return violations
    violations.append(LintViolation(
        rule_id="DISP-1/step_invokes_workflow_or_decorated_step",
        source_id=source.source_id,
        message=(
            f"Pure helper {source.canonical_name!r} owns retry "
            f"configuration.  Retry is a property of durable subjects; "
            f"helpers must not own retry. "
            f"See DISP-1: step_invokes_workflow_or_decorated_step."
        ),
    ))
    return violations


def run_omission_lint(
    sources: tuple[SourceDeclaration, ...],
    helper_call_graph: dict[str, list[str]] | None = None,
    helper_mutates_state: dict[str, bool] | None = None,
    helper_owns_retry: dict[str, bool] | None = None,
) -> list[LintViolation]:
    """Run all static omission lint rules against a set of source declarations.

    Parameters
    ----------
    sources:
        The source declarations to lint.
    helper_call_graph:
        Optional mapping of helper names to callees for call-graph
        analysis.
    helper_mutates_state:
        Optional mapping of helper names to state-mutation flags.
    helper_owns_retry:
        Optional mapping of helper names to retry-ownership flags.

    Returns
    -------
    list[LintViolation]
        All discovered violations.
    """
    violations: list[LintViolation] = []
    for source in sources:
        violations.extend(_lint_workflow_declared_as_helper(source))
        violations.extend(_lint_step_declared_as_helper(source))
        violations.extend(_lint_effect_declared_as_helper(source))
        violations.extend(_lint_helper_calls_subworkflow(
            source, helper_call_graph,
        ))
        mutates = (
            helper_mutates_state.get(source.canonical_name, False)
            if helper_mutates_state
            else False
        )
        violations.extend(_lint_helper_mutates_state(source, mutates))
        retry = (
            helper_owns_retry.get(source.canonical_name, False)
            if helper_owns_retry
            else False
        )
        violations.extend(_lint_helper_owns_retry(source, retry))
    return violations


# ---------------------------------------------------------------------------
# Authored inline fixtures
# ---------------------------------------------------------------------------

#: Authored positive fixtures for the :func:`classify_subject` function.
#:
#: Each entry is a ``(source_id, kind_str, canonical_name, declared_durable,
#: expected_durable)`` tuple representing a source declaration that should
#: be correctly classified.
POSITIVE_FIXTURES: list[tuple[str, str | None, str, bool, SubjectKind | None]] = [
    ("wf-1", "workflow", "my_workflow", False, SubjectKind.WORKFLOW),
    ("step-1", "step", "my_step", False, SubjectKind.STEP),
    ("dt-1", "dynamic_task", "my_task", False, SubjectKind.DYNAMIC_TASK),
    ("effect-1", "effect", "my_effect", False, SubjectKind.EFFECT),
    ("hb-1", "human_boundary", "my_review_gate", False, SubjectKind.HUMAN_BOUNDARY),
    ("helper-1", None, "pure_calc", False, None),
]

#: Authored negative fixtures for the :func:`classify_subject` function.
#:
#: Each entry represents a source declaration that should fail or be
#: flagged — e.g. a pure helper calling a subworkflow, mutating state,
#: or owning retry.
NEGATIVE_FIXTURES: list[tuple[str, str | None, str, bool, bool, str]] = [
    (
        "bad-helper-1", None, "helper_calls_subworkflow",
        False, False,
        "step helper calling subworkflow — reclassify warning (DISP-1)",
    ),
    (
        "bad-helper-2", None, "helper_mutates_state",
        False, False,
        "step helper mutating state — reclassify warning (DISP-1)",
    ),
    (
        "bad-helper-3", None, "helper_owns_retry",
        False, False,
        "step helper owning retry — reclassify warning (DISP-1)",
    ),
]

#: REQUIRED hidden-effect fixture — a pure helper that reaches durable
#: behavior through a transitive call graph.
#:
#: This fixture models a helper decorated as ``pure`` whose transitive
#: call graph reaches a durable subject (e.g. a workflow or step).  The
#: lint engine should detect this as a ``hidden_effect_or_nondeterminism_in_helper``
#: violation (DISP-1) even though the helper itself is classified as pure.
HIDDEN_EFFECT_FIXTURE: tuple[str, str | None, str, bool, bool, dict[str, list[str]]] = (
    "hidden-effect-1", None, "transitively_durable_helper",
    False, False,
    {
        "transitively_durable_helper": ["calls_internal_fn", "my_workflow_step"],
    },
)
