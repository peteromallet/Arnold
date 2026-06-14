"""Import-isolation and evidence-pack expressivity tests (M0a T3).

(A) Subprocess-based import-isolation: importing ContractResult,
    ContractStatus, EvidenceArtifactRef, Suspension from arnold.pipeline
    must NOT pull any megaplan.* module into sys.modules.

(B) Five-stage evidence-pack expressivity test: scan, multi-content-type
    fan-out, human suspend, verdict, failure — using only the frozen
    field types from ContractResult + friends.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

from arnold.pipeline.types import (
    CONTRACT_RESULT_SCHEMA_VERSION,
    ContractResult,
    ContractStatus,
    EvidenceArtifactRef,
    Freshness,
    Provenance,
    Suspension,
)


# ---------------------------------------------------------------------------
# (A) Subprocess import-isolation test
# ---------------------------------------------------------------------------


_IMPORT_ISOLATION_SCRIPT = """
import sys

# Import the specific symbols
from arnold.pipeline import (
    ContractResult,
    ContractStatus,
    EvidenceArtifactRef,
    Suspension,
)

# Assert no megaplan.* module appears in sys.modules
megaplan_modules = [k for k in sys.modules if k.startswith("megaplan.")]
if megaplan_modules:
    print("FAIL: megaplan modules leaked:", megaplan_modules)
    sys.exit(1)

# Also check arnold.pipelines.megaplan
arnold_megaplan_modules = [
    k for k in sys.modules if k.startswith("arnold.pipelines.megaplan")
]
if arnold_megaplan_modules:
    print("FAIL: arnold megaplan modules leaked:", arnold_megaplan_modules)
    sys.exit(1)

# Smoke: the imports resolved
assert ContractResult is not None
assert ContractStatus is not None
assert EvidenceArtifactRef is not None
assert Suspension is not None

print("OK: import isolation verified")
"""


def test_import_isolation_via_subprocess() -> None:
    """Importing ContractResult etc. must not pull megaplan into sys.modules."""
    result = subprocess.run(
        [sys.executable, "-c", _IMPORT_ISOLATION_SCRIPT],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"import isolation subprocess failed:\n"
        f"stdout={result.stdout}\n"
        f"stderr={result.stderr}"
    )
    assert "OK: import isolation verified" in result.stdout


# ---------------------------------------------------------------------------
# (B) Five-stage evidence-pack expressivity test
# ---------------------------------------------------------------------------


class TestEvidencePackExpressivity:
    """Construct five well-specified ContractResult instances covering the
    scan → fan-out → suspend → verdict → failure lifecycle, then assert
    standard round-trip + json.dumps for each."""

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _scan_evidence() -> EvidenceArtifactRef:
        return EvidenceArtifactRef(
            uri="s3://evidence/scan-001.json",
            content_type="application/json",
            digest="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            size_bytes=1024,
            name="security-scan-001",
        )

    @staticmethod
    def _png_evidence(path: str) -> EvidenceArtifactRef:
        return EvidenceArtifactRef(
            uri=f"s3://evidence/{path}",
            content_type="image/png",
            digest="sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            size_bytes=2048,
            name=path,
        )

    @staticmethod
    def _markdown_evidence(path: str) -> EvidenceArtifactRef:
        return EvidenceArtifactRef(
            uri=f"s3://evidence/{path}",
            content_type="text/markdown",
            digest="sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
            size_bytes=512,
            name=path,
        )

    @staticmethod
    def _provenance(generator: str = "test@1.0") -> Provenance:
        return Provenance(
            sources=(),
            generator=generator,
            generated_at="2026-06-05T22:00:00Z",
            chain=(),
        )

    @staticmethod
    def _freshness(ttl: int = 3600) -> Freshness:
        return Freshness(
            observed_at="2026-06-05T22:00:00Z",
            ttl_seconds=ttl,
            expires_at="2026-06-05T23:00:00Z",
        )

    def _assert_round_trip(self, cr: ContractResult) -> ContractResult:
        """Standard round-trip: to_json → from_json, then json.dumps/json.loads."""
        rt = ContractResult.from_json(cr.to_json())
        assert rt == cr, f"Round-trip inequality: {rt} != {cr}"
        # Also ensure json.dumps survives
        s = json.dumps(cr.to_json(), sort_keys=True)
        loaded = json.loads(s)
        rt2 = ContractResult.from_json(loaded)
        assert rt2 == cr
        return rt

    # -- stage 1: scan -----------------------------------------------------

    def test_stage_1_scan(self) -> None:
        """Scan stage produces a completed result with scan evidence."""
        cr = ContractResult(
            payload={
                "scan_type": "security",
                "findings": 0,
                "target": "repo:example/main",
            },
            status=ContractStatus.COMPLETED,
            schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
            evidence_refs=(self._scan_evidence(),),
            authority_level="verified",
            provenance=self._provenance("scanner@1.2"),
            freshness=self._freshness(),
        )
        rt = self._assert_round_trip(cr)
        assert rt.status == ContractStatus.COMPLETED
        assert rt.suspension is None
        assert len(rt.evidence_refs) == 1
        assert rt.evidence_refs[0].name == "security-scan-001"
        assert rt.authority_level == "verified"

    # -- stage 2: multi-content-type fan-out --------------------------------

    def test_stage_2_multi_content_type_fan_out(self) -> None:
        """Fan-out produces result with evidence of multiple content types."""
        cr = ContractResult(
            payload={
                "fan_out_count": 3,
                "strategy": "broadcast",
            },
            status=ContractStatus.COMPLETED,
            schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
            evidence_refs=(
                self._png_evidence("diagram-1.png"),
                self._markdown_evidence("report-1.md"),
                self._png_evidence("diagram-2.png"),
            ),
            authority_level="advisory",
            provenance=self._provenance("fanout@1.0"),
            freshness=self._freshness(ttl=600),
        )
        rt = self._assert_round_trip(cr)
        assert rt.status == ContractStatus.COMPLETED
        assert len(rt.evidence_refs) == 3
        content_types = {r.content_type for r in rt.evidence_refs}
        assert "image/png" in content_types
        assert "text/markdown" in content_types
        assert rt.authority_level == "advisory"

    # -- stage 3: human suspend --------------------------------------------

    def test_stage_3_human_suspend(self) -> None:
        """Human-gate step suspends with display refs."""
        display = EvidenceArtifactRef(
            uri="s3://prompts/approval-diff.png",
            content_type="image/png",
            name="approval-diff",
        )
        sus = Suspension(
            kind="human",
            awaitable="approval/gate-1",
            prompt="Please review the security scan results and approve.",
            display_refs=(display,),
            resume_input_schema={"approved": "bool", "comment": "str"},
            thread_ref="thread/gate-1",
            actor="security-reviewer",
            deadline="2026-06-06T00:00:00Z",
            on_timeout="reject",
            default_action="reject",
        )
        cr = ContractResult(
            payload={"gate": "security-approval"},
            status=ContractStatus.SUSPENDED,
            schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
            suspension=sus,
            evidence_refs=(self._scan_evidence(), display),
            authority_level="asserted",
            provenance=self._provenance("human-gate@1.0"),
            freshness=self._freshness(),
        )
        rt = self._assert_round_trip(cr)
        assert rt.status == ContractStatus.SUSPENDED
        assert rt.suspension is not None
        assert rt.suspension.kind == "human"
        assert rt.suspension.prompt.startswith("Please review")
        assert len(rt.suspension.display_refs) == 1
        assert rt.suspension.display_refs[0].name == "approval-diff"
        assert rt.suspension.default_action == "reject"

    # -- stage 4: verdict --------------------------------------------------

    def test_stage_4_verdict(self) -> None:
        """Verdict step produces a completed result with adjudication payload."""
        cr = ContractResult(
            payload={
                "verdict": "pass",
                "score": 0.97,
                "reasoning": "All gates green, no findings.",
            },
            status=ContractStatus.COMPLETED,
            schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
            evidence_refs=(),
            authority_level="verified",
            provenance=self._provenance("verdict-engine@2.0"),
            freshness=self._freshness(),
        )
        rt = self._assert_round_trip(cr)
        assert rt.status == ContractStatus.COMPLETED
        assert rt.payload["verdict"] == "pass"
        assert rt.payload["score"] == 0.97
        assert rt.authority_level == "verified"
        assert rt.evidence_refs == ()

    # -- stage 5: failure --------------------------------------------------

    def test_stage_5_failure(self) -> None:
        """Failure produces FAILED status with error payload."""
        cr = ContractResult(
            payload={
                "error": "timeout",
                "step": "security-scan",
                "retries": 3,
            },
            status=ContractStatus.FAILED,
            schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
            evidence_refs=(
                EvidenceArtifactRef(
                    uri="s3://logs/scan-error.log",
                    content_type="text/plain",
                    name="scan-error-log",
                ),
            ),
            authority_level="asserted",
            provenance=self._provenance("scanner@1.2"),
            freshness=self._freshness(ttl=0),
        )
        rt = self._assert_round_trip(cr)
        assert rt.status == ContractStatus.FAILED
        assert rt.suspension is None
        assert rt.payload["error"] == "timeout"
        assert rt.payload["retries"] == 3
        assert len(rt.evidence_refs) == 1
        assert rt.evidence_refs[0].name == "scan-error-log"

    # -- cross-cutting: schema_version present in all stages ----------------

    def test_all_stages_have_schema_version_in_json(self) -> None:
        """Every stage's to_json() must contain the correct schema_version."""
        stages = [
            self._make_scan(),
            self._make_fan_out(),
            self._make_suspend(),
            self._make_verdict(),
            self._make_failure(),
        ]
        for i, cr in enumerate(stages):
            j = cr.to_json()
            assert j["schema_version"] == CONTRACT_RESULT_SCHEMA_VERSION, (
                f"Stage {i} has wrong schema_version"
            )

    def _make_scan(self) -> ContractResult:
        return ContractResult(
            payload={"scan_type": "security"},
            schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
            evidence_refs=(self._scan_evidence(),),
            authority_level="verified",
            provenance=self._provenance("scanner@1.2"),
            freshness=self._freshness(),
        )

    def _make_fan_out(self) -> ContractResult:
        return ContractResult(
            payload={"fan_out_count": 3},
            schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
            evidence_refs=(
                self._png_evidence("d1.png"),
                self._markdown_evidence("r1.md"),
            ),
            authority_level="advisory",
            provenance=self._provenance("fanout@1.0"),
            freshness=self._freshness(600),
        )

    def _make_suspend(self) -> ContractResult:
        display = EvidenceArtifactRef(
            uri="s3://prompts/diff.png",
            content_type="image/png",
            name="diff",
        )
        return ContractResult(
            payload={"gate": "approval"},
            status=ContractStatus.SUSPENDED,
            schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
            suspension=Suspension(
                kind="human",
                prompt="Approve?",
                display_refs=(display,),
                default_action="reject",
            ),
            evidence_refs=(display,),
            authority_level="asserted",
            provenance=self._provenance("human-gate@1.0"),
            freshness=self._freshness(),
        )

    def _make_verdict(self) -> ContractResult:
        return ContractResult(
            payload={"verdict": "pass", "score": 0.95},
            schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
            authority_level="verified",
            provenance=self._provenance("verdict@2.0"),
            freshness=self._freshness(),
        )

    def _make_failure(self) -> ContractResult:
        return ContractResult(
            payload={"error": "timeout", "retries": 3},
            status=ContractStatus.FAILED,
            schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
            evidence_refs=(
                EvidenceArtifactRef(
                    uri="s3://logs/error.log",
                    content_type="text/plain",
                    name="error-log",
                ),
            ),
            authority_level="asserted",
            provenance=self._provenance("scanner@1.2"),
            freshness=self._freshness(0),
        )
