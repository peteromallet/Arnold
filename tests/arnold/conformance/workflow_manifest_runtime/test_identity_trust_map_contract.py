"""Conformance checks for the locked M1 identity and trust map."""

from __future__ import annotations

from pathlib import Path


DOC_PATH = Path("docs/arnold/workflow-migration.md")
SECTION_HEADING = "## Discovery, Trust, And Identity Map"
NEXT_SECTION_HEADING = "## Deferred Hardening And Quarry Notes"


def _identity_section() -> str:
    text = DOC_PATH.read_text(encoding="utf-8")
    start = text.index(SECTION_HEADING)
    end = text.index(NEXT_SECTION_HEADING, start)
    return text[start:end]


def test_identity_map_section_uses_locked_m1_formulas() -> None:
    section = _identity_section()

    required_fragments = (
        "stable workflow alias plus `WorkflowManifest.manifest_hash`",
        'pipeline_identity = sha256_text(f"workflow:{alias}@{manifest_hash}")',
        'derive_registry_runtime_id(alias, manifest_hash) = sha256_text(f"workflow-registry:{alias}@{manifest_hash}")',
        'derive_discovery_pipeline_id(alias, manifest_hash) = sha256_text(f"workflow-discovery:{alias}@{manifest_hash}")',
        'derive_workflow_tenant_id(alias, manifest_hash) = "workflow_" + sha256(f"workflow-tenant:{alias}@{manifest_hash}")[:24]',
        "`generated_artifact_identity_header_fields(alias, manifest_hash)` returns `workflow_alias`, `manifest_hash`, and `pipeline_identity`",
        "`GeneratedArtifactProvenance` accepts the triple only all-present or all-absent",
        "Computed property equal to `derive_pipeline_identity(alias, manifest_hash)`",
        'derive_judge_sidecar_cross_reference_identity(alias, manifest_hash) = sha256_text(f"workflow-judge-sidecar:{alias}@{manifest_hash}")',
    )

    for fragment in required_fragments:
        assert fragment in section


def test_identity_map_section_rejects_provisional_identity_language() -> None:
    section = _identity_section().lower()

    forbidden_phrases = (
        "re-chartered",
        "regenerated or validated from",
        "future runtime coordinates derive from",
    )

    for phrase in forbidden_phrases:
        assert phrase not in section


def test_trust_map_requires_manifest_hash_backed_runtime_anchor() -> None:
    section = _identity_section()

    for grade in ("TrustGrade.AUTO_EXEC", "TrustGrade.QUARANTINED", "TrustGrade.BLESSED"):
        assert grade in section
    assert section.count("Exactly one runtime anchor") == 3
    assert section.count("WorkflowTrustDecision") == 3
    assert section.count("pipeline_identity = derive_pipeline_identity(alias, manifest_hash)") == 3
    assert "Path-derived `classify()` can describe package discovery metadata only" in section
    assert "Missing or malformed `manifest_hash` evidence fails closed" in section
    assert "JudgeManifestCrossReference" in section
    assert "False-pass prevention rule: deletion, replay, and runtime trust gates must reject" in section
    assert "lacks a manifest-hash-backed identity triple" in section
    assert "stand in for `alias`, `manifest_hash`, and the derived `pipeline_identity`" in section
