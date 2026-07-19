"""Focused tests for Transaction Spine replay fixtures (M6 — T8).

Covers:
- Content-hash stability (regeneration produces the same hash)
- Redaction of unstable workspace paths
- Schema validation for the fixture artifact
- Explicit limitation encoding for missing original workspace
- Deterministic ordering invariant
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

# Generator module under test
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "tools"))
# The generator module is at tools/generate_m6_replay_fixtures.py
import importlib.util as _iu


def _import_generator():
    """Import the generator module dynamically."""
    spec = _iu.spec_from_file_location(
        "generate_m6_replay_fixtures",
        str(REPO_ROOT / "tools" / "generate_m6_replay_fixtures.py"),
    )
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_gen = _import_generator()

FIXTURE_PATH = REPO_ROOT / "evidence" / "replay" / "transaction-spine.json"


# ── helpers ────────────────────────────────────────────────────────────────


def _load_fixture() -> dict[str, Any]:
    """Load the fixture artifact, skipping if not found."""
    if not FIXTURE_PATH.exists():
        pytest.skip("Transaction Spine fixture not yet generated")
    with open(FIXTURE_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


# ── schema tests ───────────────────────────────────────────────────────────


class TestTransactionSpineFixtureSchema:
    """Validate the top-level structure of the fixture artifact."""

    def test_has_correct_schema(self) -> None:
        fixture = _load_fixture()
        assert fixture["schema"] == "m6.transaction-spine-replay-fixture.v1"

    def test_has_generated_at(self) -> None:
        fixture = _load_fixture()
        assert "generated_at" in fixture
        assert fixture["generated_at"]

    def test_has_composite_hash(self) -> None:
        fixture = _load_fixture()
        assert "composite_hash" in fixture
        assert len(fixture["composite_hash"]) == 64  # SHA-256 hex

    def test_has_section_hashes(self) -> None:
        fixture = _load_fixture()
        assert "section_hashes" in fixture
        sh = fixture["section_hashes"]
        for key in ("handoff_documents", "incident_summaries", "repair_data"):
            assert key in sh, f"Missing section hash for {key}"
            assert len(sh[key]) == 64

    def test_has_limitations(self) -> None:
        fixture = _load_fixture()
        assert "limitations" in fixture
        lim = fixture["limitations"]
        assert "missing_original_workspace" in lim
        assert "path_redaction" in lim

    def test_has_sections(self) -> None:
        fixture = _load_fixture()
        assert "sections" in fixture
        sections = fixture["sections"]
        for key in ("handoff_documents", "incident_summaries", "repair_data"):
            assert key in sections, f"Missing section: {key}"


class TestHandoffDocumentsSection:
    """Validate the handoff_documents section."""

    def test_has_documents(self) -> None:
        fixture = _load_fixture()
        docs = fixture["sections"]["handoff_documents"]["documents"]
        assert len(docs) >= 2, "At least two handoff documents expected"

    def test_transaction_spine_handoff_present(self) -> None:
        fixture = _load_fixture()
        docs = fixture["sections"]["handoff_documents"]["documents"]
        ts_docs = [
            d for d in docs
            if "transaction-spine" in d.get("kind", "")
        ]
        assert len(ts_docs) >= 1, "Transaction Spine handoff missing"
        assert ts_docs[0]["status"] == "present"

    def test_documents_have_content_hash(self) -> None:
        fixture = _load_fixture()
        docs = fixture["sections"]["handoff_documents"]["documents"]
        for d in docs:
            if d["status"] == "present":
                assert d["content_sha256"] is not None
                assert len(d["content_sha256"]) == 64
            else:
                assert d["content_sha256"] is None

    def test_documents_are_sorted(self) -> None:
        fixture = _load_fixture()
        docs = fixture["sections"]["handoff_documents"]["documents"]
        kinds = [d["kind"] for d in docs]
        assert kinds == sorted(kinds), "Documents must be deterministically sorted"


class TestIncidentSummariesSection:
    """Validate the incident_summaries section."""

    def test_has_incidents(self) -> None:
        fixture = _load_fixture()
        incidents = fixture["sections"]["incident_summaries"]["incidents"]
        assert len(incidents) > 0

    def test_has_problems(self) -> None:
        fixture = _load_fixture()
        problems = fixture["sections"]["incident_summaries"]["problems"]
        assert len(problems) > 0

    def test_incidents_are_sorted(self) -> None:
        fixture = _load_fixture()
        incidents = fixture["sections"]["incident_summaries"]["incidents"]
        ids = [i["incident_id"] for i in incidents]
        assert ids == sorted(ids)

    def test_problems_are_sorted(self) -> None:
        fixture = _load_fixture()
        problems = fixture["sections"]["incident_summaries"]["problems"]
        ids = [p["problem_id"] for p in problems]
        assert ids == sorted(ids)


class TestRepairDataSection:
    """Validate the repair_data section."""

    def test_repair_data_present(self) -> None:
        fixture = _load_fixture()
        rd = fixture["sections"]["repair_data"]
        assert rd["status"] == "present"

    def test_has_redacted_flag(self) -> None:
        fixture = _load_fixture()
        rd = fixture["sections"]["repair_data"]
        assert rd["redacted"] is True

    def test_has_content_hash(self) -> None:
        fixture = _load_fixture()
        rd = fixture["sections"]["repair_data"]
        assert rd["content_hash"] is not None
        assert len(rd["content_hash"]) == 64

    def test_has_incident_summaries(self) -> None:
        fixture = _load_fixture()
        rd = fixture["sections"]["repair_data"]
        assert len(rd["incident_summaries"]) > 0


# ── Redaction tests ────────────────────────────────────────────────────────


class TestRedaction:
    """Verify that unstable paths are properly redacted."""

    def test_no_unredacted_data_paths(self) -> None:
        """Data sections must not contain raw /workspace/ paths."""
        fixture = _load_fixture()

        # The data sections (handoff, incident summaries, repair)
        # should NOT contain raw /workspace/<something> paths.
        # The limitations section intentionally documents the redaction
        # pattern and the missing workspace name.
        sections = fixture["sections"]
        sections_raw = json.dumps(sections, sort_keys=True, ensure_ascii=False)

        # Find /workspace/ occurrences
        matches = list(re.finditer(r"/workspace/(?!\[REDACTED:)", sections_raw))
        # The handoff documents contain /workspace/ paths in their content,
        # but those go through _redact_paths before being stored in the fixture.
        # Any remaining raw /workspace/ in sections data is a leak.
        assert len(matches) == 0, (
            f"Found {len(matches)} unredacted /workspace/ paths in data sections: "
            f"{[m.group(0)[:60] for m in matches]}"
        )

    def test_redacted_tokens_present_somewhere(self) -> None:
        """Redacted tokens should appear somewhere in the fixture (sections or metadata).

        The handoff content preview may be truncated before paths, but the
        repository_root field and the full content hashes bear evidence of redaction.
        """
        fixture = _load_fixture()
        # Check the full fixture JSON for redacted tokens
        full_raw = json.dumps(fixture, sort_keys=True, ensure_ascii=False)
        tokens = re.findall(r"\[REDACTED:[a-f0-9]+\]", full_raw)
        assert len(tokens) > 0, (
            "Expected redacted tokens somewhere in the fixture; "
            "found none in full JSON"
        )

        # The repository_root must be redacted (tested separately),
        # and handoff documents with workspace paths must have non-None
        # content_sha256 computed from redacted content.
        for doc in fixture["sections"]["handoff_documents"]["documents"]:
            if doc["status"] == "present" and doc.get("line_count", 0) > 100:
                assert doc["content_sha256"] is not None, (
                    f"Handoff doc {doc['kind']} must have content hash"
                )

    def test_repository_root_is_redacted(self) -> None:
        """The repository_root field must be redacted."""
        fixture = _load_fixture()
        root = fixture["repository_root"]
        assert "[REDACTED:" in root, (
            f"repository_root must be redacted, got: {root}"
        )
        # Should not contain a raw checkout path
        assert not re.match(r"^/workspace/[a-zA-Z]", root), (
            f"repository_root appears unredacted: {root}"
        )


# ── Content-hash stability tests ───────────────────────────────────────────


class TestContentHashStability:
    """Verify that regeneration produces identical hashes."""

    def test_section_hashes_match_content(self) -> None:
        """Each section's embedded content_hash must match recomputation."""
        mod = _import_generator()
        fixture = _load_fixture()

        sections = fixture["sections"]
        for section_name, section_data in sections.items():
            recomputed = mod._hash_dict(section_data)
            embedded = fixture["section_hashes"][section_name]
            assert recomputed == embedded, (
                f"Content hash mismatch for {section_name}: "
                f"embedded={embedded[:12]}... recomputed={recomputed[:12]}..."
            )

    def test_composite_hash_matches_sections(self) -> None:
        """The composite hash must be derivable from section hashes."""
        fixture = _load_fixture()

        section_hashes = fixture["section_hashes"]
        composite_payload = json.dumps(
            dict(sorted(section_hashes.items())),
            sort_keys=True,
            ensure_ascii=False,
        )
        expected = _sha256_hex(composite_payload)
        assert fixture["composite_hash"] == expected, (
            f"Composite hash mismatch: "
            f"expected={expected[:12]}... got={fixture['composite_hash'][:12]}..."
        )

    def test_regeneration_is_stable(self, tmp_path: Path) -> None:
        """Two runs against the same repo state produce the same composite hash."""
        mod = _import_generator()

        out1 = tmp_path / "run1.json"
        out2 = tmp_path / "run2.json"

        fixture1 = mod.generate_transaction_spine(output_path=out1)
        fixture2 = mod.generate_transaction_spine(output_path=out2)

        # Composite hashes must match
        assert fixture1["composite_hash"] == fixture2["composite_hash"], (
            "Regeneration must produce stable composite hash"
        )

        # Section hashes must match
        assert (
            fixture1["section_hashes"] == fixture2["section_hashes"]
        ), "Regeneration must produce stable section hashes"

        # File contents must be identical (modulo generated_at which we skip)
        data1 = json.loads(out1.read_text(encoding="utf-8"))
        data2 = json.loads(out2.read_text(encoding="utf-8"))

        # Timestamps differ but everything else must match
        for key in data1:
            if key == "generated_at":
                continue
            assert data1[key] == data2[key], (
                f"Field '{key}' differs between regeneration runs"
            )


# ── Limitation tests ───────────────────────────────────────────────────────


class TestLimitationEncoding:
    """Verify that evidence limitations are explicitly encoded."""

    def test_missing_workspace_limitation_present(self) -> None:
        fixture = _load_fixture()
        lim = fixture["limitations"]["missing_original_workspace"]
        assert "severity" in lim
        assert lim["severity"] == "limitation"
        assert "description" in lim
        assert "mitigations" in lim
        assert len(lim["mitigations"]) >= 2

    def test_limitation_mentions_transaction_spine(self) -> None:
        """The limitation must name the specific missing workspace."""
        fixture = _load_fixture()
        desc = fixture["limitations"]["missing_original_workspace"]["description"]
        assert "Transaction Spine" in desc, (
            "Limitation must identify the Transaction Spine workspace"
        )
        assert "agent-edit" in desc.lower(), (
            "Limitation must identify the specific missing workspace"
        )

    def test_path_redaction_limitation_present(self) -> None:
        fixture = _load_fixture()
        lim = fixture["limitations"]["path_redaction"]
        assert "description" in lim
        assert "pattern" in lim
        assert "applied_to" in lim
        assert len(lim["applied_to"]) >= 3


# ── Deterministic ordering tests ───────────────────────────────────────────


class TestDeterministicOrdering:
    """Verify all data lists are deterministically sorted."""

    def test_handoff_documents_sorted(self) -> None:
        fixture = _load_fixture()
        docs = fixture["sections"]["handoff_documents"]["documents"]
        kinds = [d["kind"] for d in docs]
        assert kinds == sorted(kinds)

    def test_incidents_sorted(self) -> None:
        fixture = _load_fixture()
        incs = fixture["sections"]["incident_summaries"]["incidents"]
        ids = [i["incident_id"] for i in incs]
        assert ids == sorted(ids)

    def test_problems_sorted(self) -> None:
        fixture = _load_fixture()
        probs = fixture["sections"]["incident_summaries"]["problems"]
        ids = [p["problem_id"] for p in probs]
        assert ids == sorted(ids)

    def test_repair_incidents_sorted(self) -> None:
        fixture = _load_fixture()
        rd = fixture["sections"]["repair_data"]["incident_summaries"]
        ids = [r["session_id"] for r in rd]
        assert ids == sorted(ids)


# ── Redaction function unit tests ──────────────────────────────────────────


class TestRedactionFunction:
    """Unit tests for the _redact_paths helper."""

    def test_redacts_simple_workspace_path(self) -> None:
        mod = _import_generator()
        result = mod._redact_paths("/workspace/my-project/file.txt")
        assert "/workspace/my-project/file.txt" not in result
        assert result.startswith("/workspace/[REDACTED:")

    def test_redacts_nested_path(self) -> None:
        mod = _import_generator()
        result = mod._redact_paths(
            "Path: /workspace/agent-edit/vibecomfy/plan/state.json"
        )
        assert "/workspace/agent-edit" not in result
        assert "[REDACTED:" in result

    def test_preserves_non_workspace_paths(self) -> None:
        mod = _import_generator()
        text = "File at /home/user/data.txt and /tmp/cache"
        result = mod._redact_paths(text)
        assert result == text, "Non-workspace paths must be preserved"

    def test_redaction_is_deterministic(self) -> None:
        mod = _import_generator()
        path = "/workspace/agent-edit-verifiable-transaction-spine/vibecomfy"
        r1 = mod._redact_paths(f"a {path} b")
        r2 = mod._redact_paths(f"x {path} y")
        # Same path should produce same redacted token
        token1 = re.search(r"\[REDACTED:([a-f0-9]+)\]", r1).group(1)
        token2 = re.search(r"\[REDACTED:([a-f0-9]+)\]", r2).group(1)
        assert token1 == token2, (
            f"Same path must produce same redaction token: {token1} vs {token2}"
        )

    def test_different_paths_different_tokens(self) -> None:
        mod = _import_generator()
        r1 = mod._redact_paths("/workspace/project-a/file.txt")
        r2 = mod._redact_paths("/workspace/project-b/file.txt")
        token1 = re.search(r"\[REDACTED:([a-f0-9]+)\]", r1).group(1)
        token2 = re.search(r"\[REDACTED:([a-f0-9]+)\]", r2).group(1)
        assert token1 != token2, "Different paths must produce different tokens"


# ═══════════════════════════════════════════════════════════════════════════════
# Strategy Roadmap fixture tests (M6 — T9)
# ═══════════════════════════════════════════════════════════════════════════════

SR_FIXTURE_PATH = REPO_ROOT / "evidence" / "replay" / "strategy-roadmap.json"


def _load_sr_fixture() -> dict[str, Any]:
    """Load the Strategy Roadmap fixture, skipping if not found."""
    if not SR_FIXTURE_PATH.exists():
        pytest.skip("Strategy Roadmap fixture not yet generated")
    with open(SR_FIXTURE_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


class TestStrategyRoadmapFixtureSchema:
    """Validate the top-level structure of the Strategy Roadmap fixture."""

    def test_has_correct_schema(self) -> None:
        fixture = _load_sr_fixture()
        assert fixture["schema"] == "m6.strategy-roadmap-replay-fixture.v1"

    def test_has_generated_at(self) -> None:
        fixture = _load_sr_fixture()
        assert "generated_at" in fixture
        assert fixture["generated_at"]

    def test_has_composite_hash(self) -> None:
        fixture = _load_sr_fixture()
        assert "composite_hash" in fixture
        assert len(fixture["composite_hash"]) == 64

    def test_has_section_hashes(self) -> None:
        fixture = _load_sr_fixture()
        assert "section_hashes" in fixture
        sh = fixture["section_hashes"]
        for key in (
            "initiative_artifacts",
            "handoff_context",
            "incident_data",
            "repair_data",
            "compaction_baseline",
        ):
            assert key in sh, f"Missing section hash for {key}"
            assert len(sh[key]) == 64

    def test_has_limitations(self) -> None:
        fixture = _load_sr_fixture()
        assert "limitations" in fixture
        lim = fixture["limitations"]
        assert "missing_original_workspace" in lim
        assert "path_redaction" in lim
        assert "compaction_and_productive_baselines_unknown" in lim

    def test_has_sections(self) -> None:
        fixture = _load_sr_fixture()
        assert "sections" in fixture
        sections = fixture["sections"]
        for key in (
            "initiative_artifacts",
            "handoff_context",
            "incident_data",
            "repair_data",
            "compaction_baseline",
        ):
            assert key in sections, f"Missing section: {key}"


class TestStrategyRoadmapInitiativeArtifactsSection:
    """Validate the initiative_artifacts section."""

    def test_has_artifacts(self) -> None:
        fixture = _load_sr_fixture()
        arts = fixture["sections"]["initiative_artifacts"]["artifacts"]
        assert len(arts) >= 3, "At least 3 initiative artifacts expected"

    def test_chain_yaml_present(self) -> None:
        fixture = _load_sr_fixture()
        arts = fixture["sections"]["initiative_artifacts"]["artifacts"]
        chain = [a for a in arts if a["kind"] == "chain_yaml"]
        assert len(chain) == 1
        assert chain[0]["status"] == "present"
        assert chain[0]["content_sha256"] is not None

    def test_strategy_md_present(self) -> None:
        fixture = _load_sr_fixture()
        arts = fixture["sections"]["initiative_artifacts"]["artifacts"]
        strat = [a for a in arts if a["kind"] == "strategy_md"]
        assert len(strat) == 1
        assert strat[0]["status"] == "present"
        assert strat[0]["content_sha256"] is not None

    def test_artifacts_are_sorted(self) -> None:
        fixture = _load_sr_fixture()
        arts = fixture["sections"]["initiative_artifacts"]["artifacts"]
        kinds = [a["kind"] for a in arts]
        assert kinds == sorted(kinds), "Artifacts must be deterministically sorted"


class TestStrategyRoadmapHandoffContextSection:
    """Validate the handoff_context section."""

    def test_handoff_context_present(self) -> None:
        fixture = _load_sr_fixture()
        hc = fixture["sections"]["handoff_context"]
        assert hc["status"] == "present"

    def test_has_extraction_note(self) -> None:
        fixture = _load_sr_fixture()
        hc = fixture["sections"]["handoff_context"]
        assert "note" in hc
        assert "does not have a dedicated handoff" in hc["note"]

    def test_has_strategy_excerpt(self) -> None:
        fixture = _load_sr_fixture()
        hc = fixture["sections"]["handoff_context"]
        assert hc["strategy_excerpt_line_count"] > 0
        assert hc["strategy_excerpt_preview"]


class TestStrategyRoadmapIncidentDataSection:
    """Validate the incident_data section."""

    def test_incident_present(self) -> None:
        fixture = _load_sr_fixture()
        inc = fixture["sections"]["incident_data"]["incident"]
        assert inc["status"] == "present"
        assert inc["incident_id"] == "inc-repository-strategy-roadmap"

    def test_problem_present(self) -> None:
        fixture = _load_sr_fixture()
        prob = fixture["sections"]["incident_data"]["problem"]
        assert prob["status"] == "present"
        assert prob["problem_id"] == "problem-72f87afd3954"

    def test_problem_has_linked_incidents(self) -> None:
        fixture = _load_sr_fixture()
        prob = fixture["sections"]["incident_data"]["problem"]
        assert "inc-repository-strategy-roadmap" in prob["linked_incident_ids"]

    def test_problem_has_occurrence_count(self) -> None:
        fixture = _load_sr_fixture()
        prob = fixture["sections"]["incident_data"]["problem"]
        assert prob["occurrence_count"] > 0


class TestStrategyRoadmapRepairDataSection:
    """Validate the repair_data section for Strategy Roadmap."""

    def test_repair_data_present(self) -> None:
        fixture = _load_sr_fixture()
        rd = fixture["sections"]["repair_data"]
        assert rd["status"] == "present"

    def test_has_redacted_flag(self) -> None:
        fixture = _load_sr_fixture()
        rd = fixture["sections"]["repair_data"]
        assert rd["redacted"] is True

    def test_has_content_hash(self) -> None:
        fixture = _load_sr_fixture()
        rd = fixture["sections"]["repair_data"]
        assert rd["content_hash"] is not None
        assert len(rd["content_hash"]) == 64

    def test_has_strategy_incident_count(self) -> None:
        fixture = _load_sr_fixture()
        rd = fixture["sections"]["repair_data"]
        assert "strategy_roadmap_incident_count" in rd
        assert rd["strategy_roadmap_incident_count"] >= 1


class TestStrategyRoadmapCompactionBaseline:
    """Validate the compaction_baseline section — must be UNKNOWN."""

    def test_compaction_baseline_unknown(self) -> None:
        fixture = _load_sr_fixture()
        cb = fixture["sections"]["compaction_baseline"]
        assert cb["status"] == "UNKNOWN"
        assert cb["compaction_baseline"] == "UNKNOWN"
        assert cb["productive_versus_replayed_baseline"] == "UNKNOWN"

    def test_has_evidence_reference(self) -> None:
        fixture = _load_sr_fixture()
        cb = fixture["sections"]["compaction_baseline"]
        assert "evidence_reference" in cb
        assert "active-epics-latency-synthesis" in cb["evidence_reference"]

    def test_has_reason(self) -> None:
        fixture = _load_sr_fixture()
        cb = fixture["sections"]["compaction_baseline"]
        assert "reason" in cb
        assert "not separately timed" in cb["reason"]


class TestStrategyRoadmapLimitationEncoding:
    """Verify that Strategy Roadmap evidence limitations are explicitly encoded."""

    def test_missing_workspace_limitation(self) -> None:
        fixture = _load_sr_fixture()
        lim = fixture["limitations"]["missing_original_workspace"]
        assert lim["severity"] == "limitation"
        assert "description" in lim
        assert "mitigations" in lim
        assert len(lim["mitigations"]) >= 3

    def test_limitation_mentions_strategy_roadmap(self) -> None:
        fixture = _load_sr_fixture()
        desc = fixture["limitations"]["missing_original_workspace"]["description"]
        assert "Strategy Roadmap" in desc

    def test_compaction_limitation_present(self) -> None:
        fixture = _load_sr_fixture()
        lim = fixture["limitations"]["compaction_and_productive_baselines_unknown"]
        assert lim["severity"] == "limitation"
        assert "affected_fields" in lim
        assert "compaction_baseline.compaction_baseline" in lim["affected_fields"]
        assert "compaction_baseline.productive_versus_replayed_baseline" in lim["affected_fields"]


class TestStrategyRoadmapRedaction:
    """Verify that unstable paths are properly redacted in Strategy Roadmap fixture."""

    def test_no_unredacted_data_paths(self) -> None:
        fixture = _load_sr_fixture()
        sections = fixture["sections"]
        sections_raw = json.dumps(sections, sort_keys=True, ensure_ascii=False)
        # The handoff excerpt may contain /workspace/ as part of redacted
        # text but no raw /workspace/<something> should appear unredacted
        matches = list(re.finditer(r"/workspace/(?!\[REDACTED:)", sections_raw))
        assert len(matches) == 0, (
            f"Found {len(matches)} unredacted /workspace/ paths in data sections"
        )

    def test_repository_root_is_redacted(self) -> None:
        fixture = _load_sr_fixture()
        root = fixture["repository_root"]
        assert "[REDACTED:" in root
        assert not re.match(r"^/workspace/[a-zA-Z]", root)


class TestStrategyRoadmapContentHashStability:
    """Verify that regeneration produces identical hashes for Strategy Roadmap."""

    def test_section_hashes_match_content(self) -> None:
        mod = _import_generator()
        fixture = _load_sr_fixture()
        sections = fixture["sections"]
        for section_name, section_data in sections.items():
            recomputed = mod._hash_dict(section_data)
            embedded = fixture["section_hashes"][section_name]
            assert recomputed == embedded, (
                f"Content hash mismatch for {section_name}: "
                f"embedded={embedded[:12]}... recomputed={recomputed[:12]}..."
            )

    def test_composite_hash_matches_sections(self) -> None:
        fixture = _load_sr_fixture()
        section_hashes = fixture["section_hashes"]
        composite_payload = json.dumps(
            dict(sorted(section_hashes.items())),
            sort_keys=True,
            ensure_ascii=False,
        )
        expected = _sha256_hex(composite_payload)
        assert fixture["composite_hash"] == expected, (
            f"Composite hash mismatch"
        )

    def test_regeneration_is_stable(self, tmp_path: Path) -> None:
        mod = _import_generator()
        out1 = tmp_path / "sr_run1.json"
        out2 = tmp_path / "sr_run2.json"
        fixture1 = mod.generate_strategy_roadmap(output_path=out1)
        fixture2 = mod.generate_strategy_roadmap(output_path=out2)
        assert fixture1["composite_hash"] == fixture2["composite_hash"]
        assert fixture1["section_hashes"] == fixture2["section_hashes"]
        data1 = json.loads(out1.read_text(encoding="utf-8"))
        data2 = json.loads(out2.read_text(encoding="utf-8"))
        for key in data1:
            if key == "generated_at":
                continue
            assert data1[key] == data2[key], f"Field '{key}' differs between runs"


class TestStrategyRoadmapDeterministicOrdering:
    """Verify all data lists are deterministically sorted."""

    def test_initiative_artifacts_sorted(self) -> None:
        fixture = _load_sr_fixture()
        arts = fixture["sections"]["initiative_artifacts"]["artifacts"]
        kinds = [a["kind"] for a in arts]
        assert kinds == sorted(kinds)

    def test_linked_incidents_sorted(self) -> None:
        fixture = _load_sr_fixture()
        prob = fixture["sections"]["incident_data"]["problem"]
        ids = prob["linked_incident_ids"]
        assert ids == sorted(ids)

    def test_repair_incidents_sorted(self) -> None:
        fixture = _load_sr_fixture()
        rd = fixture["sections"]["repair_data"]
        if rd.get("incident_summaries"):
            ids = [r["session_id"] for r in rd["incident_summaries"]]
            assert ids == sorted(ids)
