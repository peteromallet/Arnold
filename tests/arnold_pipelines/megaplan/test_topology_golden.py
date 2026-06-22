"""Manifest topology fixture lock and amendment enforcement.

The canonical M4 Megaplan topology is locked in
``tests/arnold_pipelines/megaplan/fixtures/megaplan_m4_topology.yaml``.
If the compiled manifest diverges from this fixture, the test fails and
requires an amendment in ``docs/arnold/workflow-manifest-amendments.md``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "megaplan_m4_topology.yaml"
AMENDMENT_PATH = Path(__file__).parents[3] / "docs" / "arnold" / "workflow-manifest-amendments.md"


@pytest.fixture
def fixture() -> dict:
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _fixture_has_m4_amendment() -> bool:
    if not AMENDMENT_PATH.exists():
        return False
    text = AMENDMENT_PATH.read_text(encoding="utf-8")
    return "## M4 Megaplan Product Migration" in text


class TestTopologyFixtureLock:
    def test_compiled_manifest_matches_locked_topology(self, fixture: dict) -> None:
        manifest = build_and_compile_pipeline()
        assert manifest.id == fixture["manifest_id"]
        assert manifest.manifest_hash == fixture["manifest_hash"]
        assert manifest.topology_hash == fixture["topology_hash"]

    def test_compiled_nodes_match_fixture(self, fixture: dict) -> None:
        manifest = build_and_compile_pipeline()
        node_ids = {n.id for n in manifest.nodes}
        assert node_ids == set(fixture["nodes"])

    def test_compiled_capabilities_match_fixture(self, fixture: dict) -> None:
        manifest = build_and_compile_pipeline()
        cap_ids = {c.capability_id for c in manifest.capabilities}
        assert cap_ids == set(fixture["capabilities"])

    def test_compiled_gate_edges_match_fixture(self, fixture: dict) -> None:
        manifest = build_and_compile_pipeline()
        gate_edges = {
            (e.label, e.target)
            for e in manifest.edges
            if e.source == "gate"
        }
        expected = {(item["label"], item["target"]) for item in fixture["gate_targets"]}
        assert gate_edges == expected

    def test_compiled_tiebreaker_edges_match_fixture(self, fixture: dict) -> None:
        manifest = build_and_compile_pipeline()
        edges = {
            (e.label, e.target)
            for e in manifest.edges
            if e.source == "tiebreaker_decide"
        }
        expected = {(item["label"], item["target"]) for item in fixture["tiebreaker_targets"]}
        assert edges == expected


class TestAmendmentEnforcement:
    def test_structural_fixture_changes_require_amendment(self, fixture: dict) -> None:
        manifest = build_and_compile_pipeline()
        # If the manifest or topology hash changed from the locked fixture,
        # an M4 amendment must exist explaining the change.
        if (
            manifest.manifest_hash != fixture["manifest_hash"]
            or manifest.topology_hash != fixture["topology_hash"]
        ):
            assert _fixture_has_m4_amendment(), (
                "Manifest/topology hash changed; add an M4 amendment to "
                "docs/arnold/workflow-manifest-amendments.md"
            )
