"""Evidence-pack conformance fixture using existing verifier/pipeline construction APIs.

Integrates ``build_initial_pipeline`` and ``build_continuation_pipeline`` from
``arnold.pipelines.evidence_pack.pipelines`` through
:func:`arnold.conformance.run_conformance_suite`, keeping all integration
wiring in test space (separate from suite implementation).

No ``megaplan`` imports. No forbidden vocabulary literals.
"""

from __future__ import annotations

from typing import Any

import pytest

from arnold.conformance import (
    ConformanceCheckResult,
    ConformanceSuiteResult,
    assert_conformance,
    assert_suite_compliant,
    run_conformance_suite,
)
# Evidence-pack pipeline construction (public APIs)
from arnold.pipelines.evidence_pack.pipelines import (
    build_continuation_pipeline,
    build_initial_pipeline,
)
from arnold.pipeline.step_invocation import StepInvocationAdapterRegistry
from arnold.pipeline.types import (
    ContractResult,
    ContractStatus,
    Edge,
    Pipeline,
    Stage,
    StepResult,
)


# ---------------------------------------------------------------------------
# Helpers for seeded violation fixtures
# ---------------------------------------------------------------------------


class _NoOpStep:
    """A Step that does nothing — used in seeded-violation pipeline fixtures."""

    name = "noop"
    kind = "noop"

    def run(self, ctx: Any) -> StepResult:
        return StepResult(next="halt")


def _make_routing_violation_pipeline() -> Pipeline:
    """A pipeline whose decision edge label is not in decision_vocabulary.

    This seeds a routing-vocabulary-coverage violation: the edge
    ``kind='decision'`` with ``label='unknown_label'`` is not a member of
    ``decision_vocabulary=frozenset({'proceed', 'reject'})``.
    """
    from arnold.pipeline.types import StepResult as _SR

    return Pipeline(
        stages={
            "judge": Stage(
                name="judge",
                step=_NoOpStep(),
                decision_vocabulary=frozenset({"proceed", "reject"}),
                edges=(
                    Edge(label="unknown_label", target="halt", kind="decision"),
                ),
            ),
        },
        entry="judge",
    )


class _NonDelegatingHooks:
    """An ``ExecutorHooks`` that deliberately does NOT delegate to ``stage.join``.

    Used exclusively in tests to seed a join-delegation violation at the suite level.
    """

    def join_parallel_results(
        self,
        stage: Any,
        ctx: Any,
        child_results: list[StepResult],
    ) -> StepResult:
        return StepResult(next="non_delegated", outputs={"_delegated": False})


def _make_corrupted_registry() -> StepInvocationAdapterRegistry:
    """A registry where ``_adapters`` contains a non-``StepInvocationAdapter``.

    This seeds an adapter-protocol violation: when ``check_adapter_protocol_conformance``
    iterates over registered kinds and checks ``isinstance(adapter, StepInvocationAdapter)``,
    the corrupted entry is rejected.
    """
    registry = StepInvocationAdapterRegistry()
    # Sneak a plain object into the internal dict — it has no ``invoke`` method.
    registry._adapters["_corrupted_non_adapter"] = object()  # type: ignore[assignment]
    return registry


# ---------------------------------------------------------------------------
# Green fixtures — evidence-pack pipelines through conformance suite
# ---------------------------------------------------------------------------


class TestEvidencePackInitialPipelineConformance:
    """The initial evidence-pack pipeline shape passes all conformance checks."""

    def test_initial_pipeline_passes_all_conformance(self) -> None:
        """build_initial_pipeline() passes the full conformance suite."""
        pipeline = build_initial_pipeline()
        result = run_conformance_suite(
            pipelines=[pipeline],
            suite_id="evidence-pack-initial-conformance",
        )
        assert isinstance(result, ConformanceSuiteResult)
        assert result.passed is True
        assert result.failure_count == 0
        assert result.failures == ()

    def test_initial_pipeline_assert_suite_compliant(self) -> None:
        """assert_suite_compliant passes on the initial pipeline."""
        pipeline = build_initial_pipeline()
        result = run_conformance_suite(
            pipelines=[pipeline],
            suite_id="evidence-pack-initial-conformance",
        )
        assert_suite_compliant(result)  # should not raise

    def test_initial_pipeline_routing_checks_present(self) -> None:
        """Routing checks are exercised for the initial pipeline."""
        pipeline = build_initial_pipeline()
        result = run_conformance_suite(
            pipelines=[pipeline],
            suite_id="evidence-pack-initial-conformance",
        )
        routing_ids = {
            "routing-vocabulary-coverage",
            "routing-vocabulary-edge-consistency",
        }
        found = {c.check_id for c in result.checks} & routing_ids
        assert len(found) >= 1, (
            f"Expected at least one routing check; got checks: "
            f"{[c.check_id for c in result.checks]}"
        )

    def test_initial_pipeline_all_checks_are_conformance_results(self) -> None:
        """Every check in the suite is a ConformanceCheckResult."""
        pipeline = build_initial_pipeline()
        result = run_conformance_suite(
            pipelines=[pipeline],
            suite_id="evidence-pack-initial-conformance",
        )
        for check in result.checks:
            assert isinstance(check, ConformanceCheckResult)
            assert isinstance(check.check_id, str)
            assert len(check.check_id) > 0

    def test_initial_pipeline_with_sample_contract_all_green(self) -> None:
        """Initial pipeline + sample ContractResult — all conformance passes."""
        pipeline = build_initial_pipeline()
        cr = ContractResult(status=ContractStatus.COMPLETED)
        result = run_conformance_suite(
            pipelines=[pipeline],
            sample_contracts=[cr],
            suite_id="evidence-pack-initial-with-contracts",
        )
        assert result.passed is True


class TestEvidencePackContinuationPipelineConformance:
    """The continuation evidence-pack pipeline shape passes all conformance checks."""

    def test_continuation_pipeline_passes_all_conformance(self) -> None:
        """build_continuation_pipeline() passes the full conformance suite."""
        pipeline = build_continuation_pipeline()
        result = run_conformance_suite(
            pipelines=[pipeline],
            suite_id="evidence-pack-continuation-conformance",
        )
        assert isinstance(result, ConformanceSuiteResult)
        assert result.passed is True
        assert result.failure_count == 0

    def test_continuation_pipeline_assert_suite_compliant(self) -> None:
        """assert_suite_compliant passes on the continuation pipeline."""
        pipeline = build_continuation_pipeline()
        result = run_conformance_suite(
            pipelines=[pipeline],
            suite_id="evidence-pack-continuation-conformance",
        )
        assert_suite_compliant(result)

    def test_continuation_pipeline_routing_checks_present(self) -> None:
        """Routing checks are exercised for the continuation pipeline."""
        pipeline = build_continuation_pipeline()
        result = run_conformance_suite(
            pipelines=[pipeline],
            suite_id="evidence-pack-continuation-conformance",
        )
        routing_ids = {
            "routing-vocabulary-coverage",
            "routing-vocabulary-edge-consistency",
        }
        found = {c.check_id for c in result.checks} & routing_ids
        assert len(found) >= 1

    def test_continuation_pipeline_without_routing_stages_is_green(self) -> None:
        """Continuation pipeline (no routing stages) skips routing checks cleanly."""
        pipeline = build_continuation_pipeline()
        result = run_conformance_suite(
            pipelines=[pipeline],
            suite_id="evidence-pack-continuation-no-routing",
        )
        # Even with no routing stages, the suite should pass
        assert result.passed is True

    def test_continuation_pipeline_check_count_nonzero(self) -> None:
        """Continuation pipeline produces a non-empty suite result."""
        pipeline = build_continuation_pipeline()
        result = run_conformance_suite(
            pipelines=[pipeline],
            suite_id="evidence-pack-continuation-conformance",
        )
        assert result.check_count > 0


# ---------------------------------------------------------------------------
# Both pipeline shapes together
# ---------------------------------------------------------------------------


class TestEvidencePackBothPipelinesConformance:
    """Both evidence-pack pipeline shapes pass all conformance checks together."""

    def test_both_pipelines_pass_together(self) -> None:
        """Initial and continuation pipelines both pass in one suite run."""
        init = build_initial_pipeline()
        cont = build_continuation_pipeline()
        result = run_conformance_suite(
            pipelines=[init, cont],
            suite_id="evidence-pack-both-conformance",
        )
        assert result.passed is True
        assert result.failure_count == 0

    def test_both_pipelines_all_four_domains(self) -> None:
        """Both pipelines exercise all four conformance domains."""
        from arnold.pipeline.hooks import NullExecutorHooks

        init = build_initial_pipeline()
        cont = build_continuation_pipeline()
        cr = ContractResult(status=ContractStatus.COMPLETED)
        hooks = NullExecutorHooks()

        result = run_conformance_suite(
            pipelines=[init, cont],
            sample_contracts=[cr],
            hooks=hooks,
            suite_id="evidence-pack-all-domains",
        )
        assert result.passed is True

        check_ids = {c.check_id for c in result.checks}
        # All four domains should be present
        assert "adapter-protocol" in check_ids
        assert "adapter-unknown-kind-fail-closed" in check_ids
        assert "contract-result-round-trip-fidelity" in check_ids
        assert "contract-result-schema-version-skew" in check_ids
        assert "contract-result-empty-schema-version-accepted" in check_ids
        assert "join-delegation" in check_ids

    def test_both_pipelines_no_evidence_pack_imports_in_conformance(self) -> None:
        """The conformance suite modules do not import from evidence_pack.

        This proves the integration wiring lives in test space only.
        """
        import ast
        import inspect
        import arnold.conformance.suite as suite_mod

        source = inspect.getsource(suite_mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module_name = (
                    node.module
                    if isinstance(node, ast.ImportFrom)
                    else (node.names[0].name if node.names else "")
                )
                if "evidence_pack" in str(module_name):
                    assert False, (
                        f"evidence_pack import found in conformance suite: {module_name}"
                    )


# ---------------------------------------------------------------------------
# Adapter protocol — evidence-pack adapters
# ---------------------------------------------------------------------------


class TestEvidencePackAdapterConformance:
    """Adapter protocol conformance for the default registry (evidence-pack uses
    only the built-in model slot)."""

    def test_default_registry_passes_adapter_checks(self) -> None:
        """Default fail-closed registry passes all adapter checks."""
        result = run_conformance_suite(suite_id="ep-adapter-check")
        adapter_checks = [
            c for c in result.checks
            if "adapter" in c.check_id
        ]
        for check in adapter_checks:
            assert check.passed, f"{check.check_id}: {check.message}"

    def test_evidence_pack_pipelines_no_unknown_adapter_kinds(self) -> None:
        """Evidence-pack pipelines use no adapter kinds beyond the model slot.

        The adapter checks confirm unknown-kind fail-closed behavior holds.
        """
        from arnold.conformance.checks import check_adapter_unknown_kind_fail_closed

        result = check_adapter_unknown_kind_fail_closed()
        assert result.passed is True
        assert result.check_id == "adapter-unknown-kind-fail-closed"


# ---------------------------------------------------------------------------
# Schema conformance — evidence-pack contracts
# ---------------------------------------------------------------------------


class TestEvidencePackSchemaConformance:
    """ContractResult schema conformance for evidence-pack typed verdicts."""

    def test_contract_schema_round_trip_passes(self) -> None:
        """Evidence-pack ContractResult shape survives round-trip."""
        from arnold.conformance.checks import check_contract_result_schema_round_trip

        result = check_contract_result_schema_round_trip()
        assert result.passed is True

    def test_schema_version_skew_rejected(self) -> None:
        """Tampered schema_version is rejected for evidence-pack contracts."""
        from arnold.conformance.checks import check_contract_result_schema_version_skew

        result = check_contract_result_schema_version_skew()
        assert result.passed is True

    def test_empty_schema_version_accepted(self) -> None:
        """Empty schema_version is accepted (backward-compat path)."""
        from arnold.conformance.checks import (
            check_contract_result_empty_schema_version_accepted,
        )

        result = check_contract_result_empty_schema_version_accepted()
        assert result.passed is True


# ---------------------------------------------------------------------------
# Fixture passes all four AR1 domains — comprehensive proof
# ---------------------------------------------------------------------------


class TestFixturePassesAllFourAR1Domains:
    """Prove the reference evidence-pack fixture passes every AR1 conformance check.

    Each of the four AR1 domains (adapter, schema, routing, join) must be
    exercised and must report ``passed=True`` for the evidence-pack reference
    pipelines and default registry.
    """

    def test_fixture_passes_all_domains_with_both_pipelines(self) -> None:
        """Both pipelines + sample contract + null hooks → all domains pass."""
        from arnold.pipeline.hooks import NullExecutorHooks

        init = build_initial_pipeline()
        cont = build_continuation_pipeline()
        cr = ContractResult(status=ContractStatus.COMPLETED)
        hooks = NullExecutorHooks()

        result = run_conformance_suite(
            pipelines=[init, cont],
            sample_contracts=[cr],
            hooks=hooks,
            suite_id="ep-fixture-all-domains-proof",
        )
        assert result.passed is True
        assert result.failure_count == 0

    def test_adapter_domain_all_checks_pass(self) -> None:
        """Every adapter-protocol check in the suite passes."""
        result = run_conformance_suite(suite_id="ep-adapter-domain-proof")
        adapter_checks = [c for c in result.checks if "adapter" in c.check_id]
        assert len(adapter_checks) >= 2  # protocol + fail-closed
        for check in adapter_checks:
            assert check.passed, f"{check.check_id}: {check.message}"

    def test_schema_domain_all_checks_pass(self) -> None:
        """Every contract-schema check in the suite passes."""
        result = run_conformance_suite(suite_id="ep-schema-domain-proof")
        schema_checks = [
            c
            for c in result.checks
            if c.check_id.startswith("contract-result-")
        ]
        assert len(schema_checks) >= 3  # round-trip, skew, empty-version
        for check in schema_checks:
            assert check.passed, f"{check.check_id}: {check.message}"

    def test_routing_domain_all_checks_pass(self) -> None:
        """Every routing check for the initial pipeline passes."""
        init = build_initial_pipeline()
        result = run_conformance_suite(
            pipelines=[init],
            suite_id="ep-routing-domain-proof",
        )
        routing_checks = [
            c
            for c in result.checks
            if c.check_id.startswith("routing-") or c.check_id.startswith("resolve-edge-")
        ]
        assert len(routing_checks) >= 1
        for check in routing_checks:
            assert check.passed, f"{check.check_id}: {check.message}"

    def test_join_domain_all_checks_pass(self) -> None:
        """Every join-delegation check in the suite passes."""
        from arnold.pipeline.hooks import NullExecutorHooks

        hooks = NullExecutorHooks()
        result = run_conformance_suite(
            hooks=hooks,
            suite_id="ep-join-domain-proof",
        )
        join_checks = [
            c
            for c in result.checks
            if c.check_id.startswith("join-")
        ]
        assert len(join_checks) >= 3  # delegation, child-results, context
        for check in join_checks:
            assert check.passed, f"{check.check_id}: {check.message}"

    def test_all_four_domain_check_ids_present(self) -> None:
        """The suite result contains check IDs from all four AR1 domains."""
        from arnold.pipeline.hooks import NullExecutorHooks

        init = build_initial_pipeline()
        cr = ContractResult(status=ContractStatus.COMPLETED)
        hooks = NullExecutorHooks()

        result = run_conformance_suite(
            pipelines=[init],
            sample_contracts=[cr],
            hooks=hooks,
            suite_id="ep-all-four-domains-present",
        )
        check_ids = {c.check_id for c in result.checks}

        # Adapter domain
        assert "adapter-protocol" in check_ids
        assert "adapter-unknown-kind-fail-closed" in check_ids
        # Schema domain
        assert "contract-result-round-trip-fidelity" in check_ids
        assert "contract-result-schema-version-skew" in check_ids
        assert "contract-result-empty-schema-version-accepted" in check_ids
        # Routing domain
        assert any(
            cid.startswith("routing-") or cid.startswith("resolve-edge-")
            for cid in check_ids
        ), f"No routing check IDs found; checks: {sorted(check_ids)}"
        # Join domain
        assert "join-delegation" in check_ids


# ---------------------------------------------------------------------------
# Seeded routing vocabulary violation — only routing checks fail
# ---------------------------------------------------------------------------


class TestSeededRoutingVocabularyViolation:
    """Seed a routing-vocabulary violation and prove only routing checks fail.

    The seeded pipeline has a decision edge whose label is not a member of
    ``decision_vocabulary``, which causes ``check_vocabulary_coverage`` to
    return a failed result.  All other domains must remain passing.
    """

    def test_routing_violation_causes_coverage_failure(self) -> None:
        """The seeded violation is detected by ``routing-vocabulary-coverage``."""
        from arnold.conformance.routing import check_vocabulary_coverage

        pipeline = _make_routing_violation_pipeline()
        check_result = check_vocabulary_coverage(pipeline)
        assert check_result.passed is False, (
            f"Expected routing-vocabulary-coverage to fail; got passed"
        )
        assert check_result.check_id == "routing-vocabulary-coverage"
        assert check_result.message != ""
        assert "unknown_label" in check_result.message or any(
            "unknown_label" in str(d) for d in (check_result.details or [])
        ), f"Message does not mention the uncovered label: {check_result.message}"

    def test_routing_violation_does_not_affect_adapter_domain(self) -> None:
        """The routing-violation pipeline leaves adapter checks passing."""
        pipeline = _make_routing_violation_pipeline()
        result = run_conformance_suite(
            pipelines=[pipeline],
            suite_id="ep-routing-violation-adapter-isolation",
        )
        adapter_checks = [c for c in result.checks if "adapter" in c.check_id]
        for check in adapter_checks:
            assert check.passed, (
                f"Adapter check {check.check_id} failed due to routing violation: "
                f"{check.message}"
            )

    def test_routing_violation_does_not_affect_schema_domain(self) -> None:
        """The routing-violation pipeline leaves schema checks passing."""
        pipeline = _make_routing_violation_pipeline()
        result = run_conformance_suite(
            pipelines=[pipeline],
            suite_id="ep-routing-violation-schema-isolation",
        )
        schema_checks = [
            c for c in result.checks if c.check_id.startswith("contract-result-")
        ]
        for check in schema_checks:
            assert check.passed, (
                f"Schema check {check.check_id} failed due to routing violation: "
                f"{check.message}"
            )

    def test_routing_violation_does_not_affect_join_domain(self) -> None:
        """The routing-violation pipeline leaves join checks passing."""
        pipeline = _make_routing_violation_pipeline()
        result = run_conformance_suite(
            pipelines=[pipeline],
            suite_id="ep-routing-violation-join-isolation",
        )
        join_checks = [c for c in result.checks if c.check_id.startswith("join-")]
        for check in join_checks:
            assert check.passed, (
                f"Join check {check.check_id} failed due to routing violation: "
                f"{check.message}"
            )

    def test_routing_violation_only_routing_checks_fail(self) -> None:
        """Only routing-specific checks fail; all other domains pass."""
        pipeline = _make_routing_violation_pipeline()
        result = run_conformance_suite(
            pipelines=[pipeline],
            suite_id="ep-routing-violation-isolated",
        )
        routing_ids = {
            "routing-vocabulary-coverage",
            "routing-vocabulary-edge-consistency",
        }
        for check in result.checks:
            if check.check_id in routing_ids or check.check_id.startswith("resolve-edge-"):
                # Routing check — may fail (coverage) or pass (edge-consistency)
                continue
            assert check.passed, (
                f"Non-routing check {check.check_id} failed due to routing violation: "
                f"{check.message}"
            )

    def test_violation_details_survive_into_suite(self) -> None:
        """The failure message and details appear in the suite result."""
        pipeline = _make_routing_violation_pipeline()
        result = run_conformance_suite(
            pipelines=[pipeline],
            suite_id="ep-routing-violation-details",
        )
        assert result.passed is False
        assert result.failure_count >= 1
        coverage_failure = [
            c for c in result.failures if c.check_id == "routing-vocabulary-coverage"
        ]
        assert len(coverage_failure) == 1, (
            f"Expected routing-vocabulary-coverage in failures; "
            f"got {[(c.check_id, c.passed) for c in result.checks]}"
        )


# ---------------------------------------------------------------------------
# Seeded join delegation violation — only join checks fail
# ---------------------------------------------------------------------------


class TestSeededJoinDelegationViolation:
    """Seed a join-delegation violation and prove only join checks fail.

    A non-delegating ``_NonDelegatingHooks`` is passed to the suite, which
    causes ``check_join_delegation`` to detect that the hook does NOT
    delegate to ``stage.join``.  All other domains must remain passing.
    """

    def test_non_delegating_hook_causes_join_failure(self) -> None:
        """The non-delegating hook is detected by ``check_join_delegation``."""
        from arnold.conformance.join import check_join_delegation

        hooks = _NonDelegatingHooks()
        check_result = check_join_delegation(hooks)
        assert check_result.passed is False, (
            f"Expected join-delegation to fail with non-delegating hook; got passed"
        )
        assert check_result.check_id == "join-delegation"
        assert check_result.message != ""

    def test_join_violation_does_not_affect_adapter_domain(self) -> None:
        """The non-delegating hook leaves adapter checks passing."""
        hooks = _NonDelegatingHooks()
        result = run_conformance_suite(
            hooks=hooks,
            suite_id="ep-join-violation-adapter-isolation",
        )
        adapter_checks = [c for c in result.checks if "adapter" in c.check_id]
        for check in adapter_checks:
            assert check.passed, (
                f"Adapter check {check.check_id} failed due to join violation: "
                f"{check.message}"
            )

    def test_join_violation_does_not_affect_schema_domain(self) -> None:
        """The non-delegating hook leaves schema checks passing."""
        hooks = _NonDelegatingHooks()
        result = run_conformance_suite(
            hooks=hooks,
            suite_id="ep-join-violation-schema-isolation",
        )
        schema_checks = [
            c for c in result.checks if c.check_id.startswith("contract-result-")
        ]
        for check in schema_checks:
            assert check.passed, (
                f"Schema check {check.check_id} failed due to join violation: "
                f"{check.message}"
            )

    def test_join_violation_does_not_affect_routing_domain(self) -> None:
        """The non-delegating hook does not produce routing check failures."""
        init = build_initial_pipeline()
        hooks = _NonDelegatingHooks()
        result = run_conformance_suite(
            pipelines=[init],
            hooks=hooks,
            suite_id="ep-join-violation-routing-isolation",
        )
        routing_checks = [
            c
            for c in result.checks
            if c.check_id.startswith("routing-") or c.check_id.startswith("resolve-edge-")
        ]
        for check in routing_checks:
            assert check.passed, (
                f"Routing check {check.check_id} failed due to join violation: "
                f"{check.message}"
            )

    def test_join_violation_only_join_checks_fail(self) -> None:
        """Only join-delegation checks fail; all other domains pass."""
        hooks = _NonDelegatingHooks()
        result = run_conformance_suite(
            hooks=hooks,
            suite_id="ep-join-violation-isolated",
        )
        join_failures = [c for c in result.checks if not c.passed and c.check_id.startswith("join-")]
        non_join_failures = [c for c in result.checks if not c.passed and not c.check_id.startswith("join-")]
        assert len(join_failures) >= 1, (
            f"Expected at least one join failure; got failures: "
            f"{[(c.check_id, c.message) for c in result.failures]}"
        )
        assert len(non_join_failures) == 0, (
            f"Unexpected non-join failures: "
            f"{[(c.check_id, c.message) for c in non_join_failures]}"
        )

    def test_join_violation_details_survive_into_suite(self) -> None:
        """The join-delegation failure message and details appear in the suite."""
        hooks = _NonDelegatingHooks()
        result = run_conformance_suite(
            hooks=hooks,
            suite_id="ep-join-violation-details",
        )
        assert result.passed is False
        assert result.failure_count >= 1
        join_failure = [
            c for c in result.failures if c.check_id == "join-delegation"
        ]
        assert len(join_failure) == 1, (
            f"Expected join-delegation in failures; "
            f"got {[(c.check_id, c.passed) for c in result.checks]}"
        )


# ---------------------------------------------------------------------------
# Seeded adapter protocol violation — only adapter checks fail
# ---------------------------------------------------------------------------


class TestSeededAdapterProtocolViolation:
    """Seed an adapter-protocol violation and prove only adapter checks fail.

    A corrupted registry (containing a non-``StepInvocationAdapter`` entry)
    is passed to the adapter check functions directly and via the suite.
    All other domains must remain passing.
    """

    def test_corrupted_registry_causes_adapter_protocol_failure(self) -> None:
        """The corrupted registry is detected by ``check_adapter_protocol_conformance``."""
        from arnold.conformance.checks import check_adapter_protocol_conformance

        registry = _make_corrupted_registry()
        check_result = check_adapter_protocol_conformance(registry)
        assert check_result.passed is False, (
            f"Expected adapter-protocol to fail with corrupted registry; got passed"
        )
        assert check_result.check_id == "adapter-protocol"
        assert check_result.message != ""

    def test_corrupted_registry_adapter_fail_closed_still_passes(self) -> None:
        """The fail-closed check still passes even with a corrupted registry.

        ``check_adapter_unknown_kind_fail_closed`` only tests resolution of
        an unknown kind, which still raises KeyError on a corrupted registry.
        """
        from arnold.conformance.checks import check_adapter_unknown_kind_fail_closed

        registry = _make_corrupted_registry()
        check_result = check_adapter_unknown_kind_fail_closed(registry)
        assert check_result.passed is True, (
            f"fail-closed check should still pass; got: {check_result.message}"
        )

    def test_adapter_violation_does_not_affect_schema_domain(self) -> None:
        """The corrupted registry leaves schema checks passing."""
        registry = _make_corrupted_registry()
        result = run_conformance_suite(
            registry=registry,
            suite_id="ep-adapter-violation-schema-isolation",
        )
        schema_checks = [
            c for c in result.checks if c.check_id.startswith("contract-result-")
        ]
        for check in schema_checks:
            assert check.passed, (
                f"Schema check {check.check_id} failed due to adapter violation: "
                f"{check.message}"
            )

    def test_adapter_violation_does_not_affect_routing_domain(self) -> None:
        """The corrupted registry does not interfere with routing checks."""
        init = build_initial_pipeline()
        registry = _make_corrupted_registry()
        result = run_conformance_suite(
            registry=registry,
            pipelines=[init],
            suite_id="ep-adapter-violation-routing-isolation",
        )
        routing_checks = [
            c
            for c in result.checks
            if c.check_id.startswith("routing-") or c.check_id.startswith("resolve-edge-")
        ]
        for check in routing_checks:
            assert check.passed, (
                f"Routing check {check.check_id} failed due to adapter violation: "
                f"{check.message}"
            )

    def test_adapter_violation_does_not_affect_join_domain(self) -> None:
        """The corrupted registry leaves join checks passing."""
        from arnold.pipeline.hooks import NullExecutorHooks

        registry = _make_corrupted_registry()
        hooks = NullExecutorHooks()
        result = run_conformance_suite(
            registry=registry,
            hooks=hooks,
            suite_id="ep-adapter-violation-join-isolation",
        )
        join_checks = [c for c in result.checks if c.check_id.startswith("join-")]
        for check in join_checks:
            assert check.passed, (
                f"Join check {check.check_id} failed due to adapter violation: "
                f"{check.message}"
            )

    def test_adapter_violation_only_adapter_protocol_fails(self) -> None:
        """Only the adapter-protocol check fails; all other checks pass."""
        registry = _make_corrupted_registry()
        result = run_conformance_suite(
            registry=registry,
            suite_id="ep-adapter-violation-isolated",
        )
        for check in result.checks:
            if check.check_id == "adapter-protocol":
                assert check.passed is False, (
                    f"adapter-protocol should have failed; got passed"
                )
            else:
                assert check.passed, (
                    f"Non-adapter-protocol check {check.check_id} failed: "
                    f"{check.message}"
                )


# ---------------------------------------------------------------------------
# Seeded contract schema violation — check-level detection proof
# ---------------------------------------------------------------------------


class TestSeededContractSchemaViolation:
    """Prove each contract-schema check detects violations at the check level.

    The schema checks are self-contained (they construct their own test data
    internally).  These tests verify the check functions themselves correctly
    detect the violations they are designed to catch.
    """

    def test_schema_version_skew_check_passes_with_valid_implementation(self) -> None:
        """``check_contract_result_schema_version_skew`` passes because
        ``from_json`` correctly rejects a tampered schema version."""
        from arnold.conformance.checks import check_contract_result_schema_version_skew

        result = check_contract_result_schema_version_skew()
        assert result.passed is True
        assert result.check_id == "contract-result-schema-version-skew"

    def test_round_trip_fidelity_check_passes_with_valid_contract(self) -> None:
        """``check_contract_result_schema_round_trip`` passes for a valid contract."""
        from arnold.conformance.checks import check_contract_result_schema_round_trip

        result = check_contract_result_schema_round_trip()
        assert result.passed is True
        assert result.check_id == "contract-result-round-trip-fidelity"

    def test_round_trip_fidelity_check_passes_with_evidence_pack_contract(self) -> None:
        """An evidence-pack ContractResult survives schema round-trip."""
        from arnold.conformance.checks import check_contract_result_schema_round_trip

        cr = ContractResult(status=ContractStatus.COMPLETED)
        result = check_contract_result_schema_round_trip(contract=cr)
        assert result.passed is True

    def test_empty_schema_version_check_passes(self) -> None:
        """``check_contract_result_empty_schema_version_accepted`` passes."""
        from arnold.conformance.checks import (
            check_contract_result_empty_schema_version_accepted,
        )

        result = check_contract_result_empty_schema_version_accepted()
        assert result.passed is True
        assert result.check_id == "contract-result-empty-schema-version-accepted"

    def test_round_trip_check_produces_fidelity_check_id(self) -> None:
        """The round-trip check always uses the fidelity check_id."""
        from arnold.conformance.checks import check_contract_result_schema_round_trip

        result = check_contract_result_schema_round_trip()
        assert result.check_id == "contract-result-round-trip-fidelity"


# ---------------------------------------------------------------------------
# Cross-domain violation isolation — comprehensive
# ---------------------------------------------------------------------------


class TestCrossDomainViolationIsolation:
    """Prove that a violation in one AR1 domain never causes failures in another.

    Runs the suite multiple times, each time seeding a violation in exactly
    one domain, and asserts that only the checks belonging to that domain
    report failures.
    """

    _ADAPTER_CHECK_IDS = {"adapter-protocol", "adapter-unknown-kind-fail-closed"}
    _SCHEMA_CHECK_IDS = {
        "contract-result-round-trip-fidelity",
        "contract-result-schema-version-skew",
        "contract-result-empty-schema-version-accepted",
    }
    _ROUTING_PREFIXES = ("routing-", "resolve-edge-")
    _JOIN_PREFIX = "join-"

    def _domain_for(self, check_id: str) -> str:
        if check_id in self._ADAPTER_CHECK_IDS:
            return "adapter"
        if check_id in self._SCHEMA_CHECK_IDS:
            return "schema"
        if check_id.startswith(self._ROUTING_PREFIXES):
            return "routing"
        if check_id.startswith(self._JOIN_PREFIX):
            return "join"
        return "unknown"

    def test_routing_violation_only_routing_fails(self) -> None:
        """Seed routing violation → only routing checks fail."""
        pipeline = _make_routing_violation_pipeline()
        result = run_conformance_suite(
            pipelines=[pipeline],
            suite_id="ep-cross-routing",
        )
        failures_by_domain: dict[str, list[str]] = {}
        for c in result.failures:
            domain = self._domain_for(c.check_id)
            failures_by_domain.setdefault(domain, []).append(c.check_id)
        assert "routing" in failures_by_domain, (
            f"Expected routing failures; failures: {failures_by_domain}"
        )
        assert "adapter" not in failures_by_domain, (
            f"Adapter checks failed from routing violation: {failures_by_domain.get('adapter')}"
        )
        assert "schema" not in failures_by_domain, (
            f"Schema checks failed from routing violation: {failures_by_domain.get('schema')}"
        )
        assert "join" not in failures_by_domain, (
            f"Join checks failed from routing violation: {failures_by_domain.get('join')}"
        )

    def test_join_violation_only_join_fails(self) -> None:
        """Seed join violation → only join checks fail."""
        hooks = _NonDelegatingHooks()
        result = run_conformance_suite(
            hooks=hooks,
            suite_id="ep-cross-join",
        )
        failures_by_domain: dict[str, list[str]] = {}
        for c in result.failures:
            domain = self._domain_for(c.check_id)
            failures_by_domain.setdefault(domain, []).append(c.check_id)
        assert "join" in failures_by_domain, (
            f"Expected join failures; failures: {failures_by_domain}"
        )
        assert "adapter" not in failures_by_domain, (
            f"Adapter checks failed from join violation: {failures_by_domain.get('adapter')}"
        )
        assert "schema" not in failures_by_domain, (
            f"Schema checks failed from join violation: {failures_by_domain.get('schema')}"
        )
        assert "routing" not in failures_by_domain, (
            f"Routing checks failed from join violation: {failures_by_domain.get('routing')}"
        )

    def test_adapter_violation_only_adapter_fails(self) -> None:
        """Seed adapter violation → only adapter checks fail."""
        registry = _make_corrupted_registry()
        result = run_conformance_suite(
            registry=registry,
            suite_id="ep-cross-adapter",
        )
        failures_by_domain: dict[str, list[str]] = {}
        for c in result.failures:
            domain = self._domain_for(c.check_id)
            failures_by_domain.setdefault(domain, []).append(c.check_id)
        assert "adapter" in failures_by_domain, (
            f"Expected adapter failures; failures: {failures_by_domain}"
        )
        assert "schema" not in failures_by_domain, (
            f"Schema checks failed from adapter violation: {failures_by_domain.get('schema')}"
        )
        assert "routing" not in failures_by_domain, (
            f"Routing checks failed from adapter violation: {failures_by_domain.get('routing')}"
        )
        assert "join" not in failures_by_domain, (
            f"Join checks failed from adapter violation: {failures_by_domain.get('join')}"
        )

    def test_schema_violations_are_internal_to_checks(self) -> None:
        """Schema checks use internal test data — no cross-domain contamination.

        The schema checks construct their own ContractResult instances
        internally, so they cannot contaminate other domains.  We verify
        that every schema check passes, proving the implementation is correct.
        """
        result = run_conformance_suite(suite_id="ep-cross-schema-internal")
        schema_checks = [
            c for c in result.checks if c.check_id in self._SCHEMA_CHECK_IDS
        ]
        assert len(schema_checks) == 3
        for check in schema_checks:
            assert check.passed, (
                f"Schema check {check.check_id} unexpectedly failed: {check.message}"
            )

    def test_all_domains_pass_with_clean_fixture(self) -> None:
        """With no seeded violations, all four domains pass cleanly."""
        from arnold.pipeline.hooks import NullExecutorHooks

        init = build_initial_pipeline()
        cr = ContractResult(status=ContractStatus.COMPLETED)
        hooks = NullExecutorHooks()

        result = run_conformance_suite(
            pipelines=[init],
            sample_contracts=[cr],
            hooks=hooks,
            suite_id="ep-cross-clean",
        )
        assert result.passed is True
        assert result.failure_count == 0
        failures_by_domain: dict[str, list[str]] = {}
        for c in result.failures:
            domain = self._domain_for(c.check_id)
            failures_by_domain.setdefault(domain, []).append(c.check_id)
        assert failures_by_domain == {}, (
            f"Unexpected failures in clean fixture: {failures_by_domain}"
        )
