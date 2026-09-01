from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.chain.spec import ChainState, _state_path_for, load_chain_state, save_chain_state
from arnold_pipelines.megaplan.incident.chain_control import (
    ChainControlTamper,
    UnattributedStateChange,
    apply_chain_lifecycle,
    chain_id_for_spec,
    journal_for,
    state_digest_for,
    verify_bound_state_matches_journal,
)
from arnold_pipelines.megaplan.store.compat import ArnoldStoreAdapter
from arnold_pipelines.megaplan.store.db import DBStore

ROOT = Path(__file__).resolve().parents[3]
RESEARCH = ROOT / ".oracle/research/nbf08-control-surface-inventory.md"
RESEARCH_SHA = "e7882d57ed32a237ad0aa6f0774ea35776717e6891a5724d4e97360f0618d5d8"
GENERATOR = ROOT / ".oracle/scripts/nbf08_surface_inventory_v1.py"
INVENTORY = ROOT / ".oracle/evidence/nbf08-chain-control-surface-inventory.json"


def _load_generator():
    spec = importlib.util.spec_from_file_location("nbf08_surface_inventory_v1", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _DummyStore:
    _IDEMPOTENT_METHODS = ArnoldStoreAdapter._IDEMPOTENT_METHODS

    def create_epic(self, **kwargs):
        return {"id": "epic-1"}


def test_compat_adapter_rejects_context_free_bound_mutation() -> None:
    adapter = ArnoldStoreAdapter(_DummyStore())  # type: ignore[arg-type]
    with pytest.raises(UnattributedStateChange):
        adapter._call("create_epic", chain_bound=True, name="x")


def test_raw_marker_edit_is_tamper_hold(tmp_path: Path) -> None:
    initiative = tmp_path / ".megaplan" / "initiatives" / "demo"
    initiative.mkdir(parents=True)
    (initiative / "brief.md").write_text("# brief\n")
    spec = initiative / "chain.yaml"
    spec.write_text("anchors:\n  north_star: brief.md\nmilestones:\n  - label: M1\n    idea: brief.md\n")
    save_chain_state(spec, ChainState(current_milestone_index=0, last_state="ready"))
    apply_chain_lifecycle(
        spec,
        tmp_path,
        intent_kind="start",
        actor={"id": "t", "class": "test"},
        effect=lambda _txn: {"pre_state_digest": "ready", "post_state_digest": "started"},
    )
    save_chain_state(spec, ChainState(current_milestone_index=0, last_state="started"))
    state_path = _state_path_for(spec)
    journal = journal_for(tmp_path)
    chain_id = chain_id_for_spec(spec)
    replay_before = journal.replay_strict()
    cursor_before = replay_before["semantic_by_chain"][chain_id]
    committed = [
        event
        for event in replay_before["accepted"]
        if event["event_kind"] == "chain_control.committed" and event.get("chain_id") == chain_id
    ]
    last_digest = committed[-1]["post_state_digest"]
    assert len(last_digest) == 64
    current = json.loads(state_path.read_text(encoding="utf-8"))
    current["tampered"] = True
    current["current_milestone_index"] = 99
    state_path.write_text(json.dumps(current) + "\n", encoding="utf-8")
    assert last_digest != state_digest_for(json.loads(state_path.read_text(encoding="utf-8")))
    with pytest.raises(ChainControlTamper):
        load_chain_state(spec)
    replay_after_load = journal.replay_strict()
    assert replay_after_load["semantic_by_chain"][chain_id] == cursor_before
    on_disk = json.loads(state_path.read_text(encoding="utf-8"))
    assert on_disk.get("tampered") is True
    assert on_disk["current_milestone_index"] == 99
    with pytest.raises(ChainControlTamper):
        save_chain_state(spec, ChainState(current_milestone_index=1, last_state="x"))
    replay_after_save = journal.replay_strict()
    assert replay_after_save["semantic_by_chain"][chain_id] == cursor_before
    assert "chain_control.tamper_detected" in [event["event_kind"] for event in replay_after_save["accepted"]]


def _state_authority_fixture(tmp_path: Path) -> tuple[Path, dict, dict, dict]:
    initiative = tmp_path / ".megaplan" / "initiatives" / "demo"
    initiative.mkdir(parents=True)
    spec = initiative / "chain.yaml"
    spec.write_text(
        "anchors:\n  north_star: brief.md\nmilestones:\n  - label: M1\n    idea: brief.md\n",
        encoding="utf-8",
    )
    (initiative / "brief.md").write_text("# brief\n", encoding="utf-8")
    state0 = {"current_milestone_index": 0, "last_state": "paused"}
    state1 = {"current_milestone_index": 0, "last_state": "rebound"}
    state2 = {"current_milestone_index": 0, "last_state": "rebound-again"}
    journal = journal_for(tmp_path)
    chain_id = chain_id_for_spec(spec)
    journal.ensure_genesis(chain_id=chain_id, actor={"id": "t", "class": "test"})
    return spec, state0, state1, state2


def test_runtime_rebound_is_latest_state_authority_without_generic_commit(tmp_path: Path) -> None:
    spec, state0, state1, _state2 = _state_authority_fixture(tmp_path)
    journal = journal_for(tmp_path)
    journal.mutate(
        chain_id=chain_id_for_spec(spec),
        operation_id="op-runtime-only",
        intent_kind="runtime-rebind",
        actor={"id": "t", "class": "test"},
        committed_event_kind="chain_control.runtime_rebound",
        effect=lambda _txn: {
            "pre_state_digest": state_digest_for(state0),
            "post_state_digest": state_digest_for(state1),
        },
    )
    verify_bound_state_matches_journal(spec, state1)
    with pytest.raises(ChainControlTamper):
        verify_bound_state_matches_journal(spec, {**state1, "last_state": "tampered"})


def test_runtime_rebound_follows_generic_commit_and_rejects_post_tamper(tmp_path: Path) -> None:
    spec, state0, state1, state2 = _state_authority_fixture(tmp_path)
    journal = journal_for(tmp_path)
    chain_id = chain_id_for_spec(spec)
    journal.mutate(
        chain_id=chain_id,
        operation_id="op-generic",
        intent_kind="save_chain_state",
        actor={"id": "t", "class": "test"},
        effect=lambda _txn: {
            "pre_state_digest": state_digest_for(state0),
            "post_state_digest": state_digest_for(state1),
        },
    )
    journal.mutate(
        chain_id=chain_id,
        operation_id="op-runtime-after-generic",
        intent_kind="runtime-rebind",
        actor={"id": "t", "class": "test"},
        committed_event_kind="chain_control.runtime_rebound",
        effect=lambda _txn: {
            "pre_state_digest": state_digest_for(state1),
            "post_state_digest": state_digest_for(state2),
        },
    )
    verify_bound_state_matches_journal(spec, state2)
    with pytest.raises(ChainControlTamper):
        verify_bound_state_matches_journal(spec, {**state2, "last_state": "tampered"})


def test_direct_sql_without_operation_id_rejects(tmp_path: Path) -> None:
    class _Probe(DBStore):
        def __init__(self) -> None:  # noqa: D401
            self._require_actor = lambda: "actor"  # type: ignore[method-assign]

    probe = object.__new__(_Probe)
    probe._require_actor = lambda: "actor"  # type: ignore[method-assign]
    with pytest.raises(UnattributedStateChange):
        DBStore._run_idempotent_mutation(
            probe,
            "create_epic",
            lambda *a, **k: None,
            (),
            {"chain_bound": True},
        )


def test_projection_rebuild_matches_file_authority(tmp_path: Path) -> None:
    initiative = tmp_path / ".megaplan" / "initiatives" / "demo"
    initiative.mkdir(parents=True)
    (initiative / "brief.md").write_text("# brief\n")
    spec = initiative / "chain.yaml"
    spec.write_text("anchors:\n  north_star: brief.md\nmilestones:\n  - label: M1\n    idea: brief.md\n")
    apply_chain_lifecycle(
        spec,
        tmp_path,
        intent_kind="start",
        actor={"id": "t", "class": "test"},
        effect=lambda _txn: {"pre_state_digest": None, "post_state_digest": "started"},
    )
    from arnold_pipelines.megaplan.incident.chain_control import projection_rebuild

    journal = journal_for(tmp_path)
    projection = projection_rebuild(journal)
    replay = journal.replay_strict()
    assert projection["physical_sequence"] == replay["physical_sequence"]
    assert projection["physical_tip_digest"] == replay["physical_tip_digest"]
    assert projection["authority"] == "file"


def test_external_shell_scripts_are_syntax_valid_and_claimless() -> None:
    scripts = [
        ROOT / "arnold_pipelines/megaplan/data/pre-commit-hook.sh",
        ROOT / "sync-skills.sh",
    ]
    for script in scripts:
        assert script.is_file()
        completed = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        assert completed.returncode == 0, completed.stderr
        text = script.read_text(encoding="utf-8")
        assert "chain_control" not in text
        assert "save_chain_state" not in text


def test_s7_static_and_inventory_checkers(tmp_path: Path) -> None:
    static = subprocess.run(
        [
            sys.executable,
            str(ROOT / ".oracle/scripts/nbf08_static_contract_check_v1.py"),
            "--root",
            str(ROOT),
            "--check-lock-order",
            "--check-sequence-migration",
            "--reject-direct-save",
        ],
        capture_output=True,
        text=True,
    )
    assert static.returncode == 0, static.stdout + static.stderr
    inventory = tmp_path / "inventory.json"
    gen = subprocess.run(
        [
            sys.executable,
            str(GENERATOR),
            "--research",
            str(RESEARCH),
            "--expected-sha256",
            RESEARCH_SHA,
            "--expected-ids",
            "CC-001..CC-083",
            "--output",
            str(inventory),
            "--check",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert gen.returncode == 0, gen.stdout + gen.stderr
    body = json.loads(inventory.read_text(encoding="utf-8"))
    assert body["surface_count"] == 83
    assert body["surface_ids"][0] == "CC-001"
    assert body["surface_ids"][-1] == "CC-083"
    assert body["schema_version"] == "nbf08-chain-control-surface-inventory-v1"
    assert body["research_inventory_sha256"] == RESEARCH_SHA
    assert [item["ambiguity_id"] for item in body["ambiguity_dispositions"]] == [
        f"AMB-{n:03d}" for n in range(1, 7)
    ]
    assert {item["disposition"] for item in body["ambiguity_dispositions"]} <= {
        "resolved",
        "modified",
        "rejected",
    }
    first = body["surfaces"][0]
    assert first["surface_id"] == "CC-001"
    assert first["path"].endswith(".py")
    assert first["symbol"]
    assert first["authority_class"] in {
        "chain-authoritative",
        "linked-domain",
        "read-only",
        "external-unknown",
    }
    assert first["closure_status"] != "implemented" or first["path"]


def _valid_body(tmp_path: Path) -> dict:
    gen = _load_generator()
    output = tmp_path / "inventory.json"
    rc = gen.main(
        [
            "--research",
            str(RESEARCH),
            "--expected-sha256",
            RESEARCH_SHA,
            "--expected-ids",
            "CC-001..CC-083",
            "--output",
            str(output),
            "--check",
        ]
    )
    assert rc == 0
    return json.loads(output.read_text(encoding="utf-8"))


def test_inventory_checker_fails_closed_on_stale_digest(tmp_path: Path, monkeypatch) -> None:
    gen = _load_generator()
    monkeypatch.chdir(ROOT)
    body = _valid_body(tmp_path)
    body["research_inventory_sha256"] = "0" * 64
    errors = gen._validate(body, ROOT, RESEARCH_SHA)
    assert any("stale research digest" in item for item in errors)


def test_inventory_checker_fails_closed_on_missing_and_duplicate_ids(tmp_path: Path, monkeypatch) -> None:
    gen = _load_generator()
    monkeypatch.chdir(ROOT)
    body = _valid_body(tmp_path)
    missing = dict(body)
    missing["surfaces"] = list(body["surfaces"][:-1])
    missing["surface_count"] = 82
    missing["surface_ids"] = body["surface_ids"][:-1]
    missing_errors = gen._validate(missing, ROOT, RESEARCH_SHA)
    assert any("CC-001..CC-083" in item or "missing" in item for item in missing_errors)
    duplicate = dict(body)
    rows = [dict(row) for row in body["surfaces"]]
    rows[1] = dict(rows[0])
    duplicate["surfaces"] = rows
    duplicate_errors = gen._validate(duplicate, ROOT, RESEARCH_SHA)
    assert any("duplicate" in item or "missing" in item for item in duplicate_errors)


def test_inventory_checker_fails_closed_on_blanket_default_rows(tmp_path: Path, monkeypatch) -> None:
    gen = _load_generator()
    monkeypatch.chdir(ROOT)
    body = _valid_body(tmp_path)
    body["surfaces"] = [
        {"surface_id": f"CC-{i:03d}", "closure_status": "implemented"} for i in range(1, 84)
    ]
    errors = gen._validate(body, ROOT, RESEARCH_SHA)
    assert any("blanket/default row" in item for item in errors)


def test_inventory_checker_fails_closed_on_missing_evidence_targets(tmp_path: Path, monkeypatch) -> None:
    gen = _load_generator()
    monkeypatch.chdir(ROOT)
    body = _valid_body(tmp_path)
    row = dict(body["surfaces"][0])
    row["evidence_paths"] = list(row["evidence_paths"]) + ["does/not/exist.py"]
    row["evidence_digests"] = list(row["evidence_digests"]) + ["a" * 64]
    body["surfaces"] = [row, *body["surfaces"][1:]]
    errors = gen._validate(body, ROOT, RESEARCH_SHA)
    assert any("missing/nonexistent evidence target" in item for item in errors)


def test_inventory_checker_fails_ast_only_implemented(tmp_path: Path, monkeypatch) -> None:
    gen = _load_generator()
    monkeypatch.chdir(ROOT)
    body = _valid_body(tmp_path)
    row = dict(body["surfaces"][0])
    row["closure_status"] = "implemented"
    row["symbol"] = "this_symbol_is_never_called_in_production_zzzz"
    row["source_paths"] = list(row.get("source_paths") or [row["path"]])
    body["surfaces"] = [row, *body["surfaces"][1:]]
    errors = gen._validate(body, ROOT, RESEARCH_SHA)
    assert any("AST-only implemented" in item for item in errors)
    bakeoff = [item for item in body["surfaces"] if item["surface_id"] in {"CC-031", "CC-032"}]
    rebuilt = _valid_body(tmp_path)
    for item in rebuilt["surfaces"]:
        if item["surface_id"] in {"CC-031", "CC-032"}:
            assert item["closure_status"] in {"planned", "held"}
        if item["surface_id"] == "CC-004":
            assert item["closure_status"] == "implemented"
    _ = bakeoff


def test_inventory_checker_fails_closed_on_held_unresolved_ambs(tmp_path: Path, monkeypatch) -> None:
    gen = _load_generator()
    monkeypatch.chdir(ROOT)
    body = _valid_body(tmp_path)
    dispositions = [dict(item) for item in body["ambiguity_dispositions"]]
    dispositions[0]["disposition"] = "held"
    body["ambiguity_dispositions"] = dispositions
    errors = gen._validate(body, ROOT, RESEARCH_SHA)
    assert any("held/unresolved ambiguity" in item for item in errors)


def test_canonical_inventory_artifact_matches_generator() -> None:
    gen = _load_generator()
    assert hashlib.sha256(RESEARCH.read_bytes()).hexdigest() == RESEARCH_SHA
    assert INVENTORY.is_file()
    recorded = json.loads(INVENTORY.read_text(encoding="utf-8"))
    rebuilt = gen.build_inventory(ROOT, RESEARCH, RESEARCH_SHA)
    assert recorded["inventory_digest"] == rebuilt["inventory_digest"]
    assert recorded["surface_count"] == 83
    assert [row["surface_id"] for row in recorded["surfaces"]] == [
        f"CC-{i:03d}" for i in range(1, 84)
    ]
    for row in recorded["surfaces"]:
        assert set(row) >= {
            "surface_id",
            "domain",
            "surface",
            "path",
            "symbol",
            "owner",
            "authority_class",
            "claim_class",
            "coverage_tests",
            "required_commands",
            "evidence_paths",
            "evidence_digests",
            "status",
            "closure_status",
        }
        assert (ROOT / row["path"]).is_file()
    for item in recorded["ambiguity_dispositions"]:
        assert item["disposition"] in {"resolved", "modified", "rejected"}
        assert item["source_evidence"]
        assert item["test_evidence"]
