from __future__ import annotations

from arnold.conformance import run_conformance_suite
from arnold.execution.hooks import NullExecutorHooks
from arnold.pipelines.evidence_pack.pipeline import build_pipeline


def test_evidence_pack_pipeline_passes_shared_conformance_suite() -> None:
    suite = run_conformance_suite(
        pipelines=[build_pipeline()],
        hooks=[NullExecutorHooks()],
        suite_id="evidence-pack-native",
    )

    assert suite.suite_id == "evidence-pack-native"
    expected = {
        "routing-vocabulary-coverage",
        "routing-vocabulary-edge-consistency",
        "join-delegation",
        "join-delegation-child-results",
        "join-delegation-context-forwarding",
    }
    assert expected.issubset({check.check_id for check in suite.checks})
    assert [
        failure.check_id for failure in suite.failures if failure.check_id in expected
    ] == []
