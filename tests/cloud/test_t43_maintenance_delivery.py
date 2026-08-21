"""Focused T4.3 proofs: fce-owner delivery/cutover with rollback."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.chain.spec import ChainState, save_chain_state
from arnold_pipelines.megaplan.cloud.current_target_liveness import (
    MutationCapability,
    MutationDenied,
    mint_mutation_capability,
)
from arnold_pipelines.megaplan.cloud.liveness_lease import LivenessLeasePublisher
from arnold_pipelines.megaplan.cloud.maintenance_delivery import (
    CUTOVER_ACTION,
    DELIVERY_JOURNAL_SCHEMA,
    DELIVERY_SENTINEL,
    PUBLICATION_BOUNDARIES,
    current_selector_marker_authority,
    deliver_runtime_cutover,
    inspect_transition,
    rollback_runtime_cutover,
    same_import_root_commit_after_cutover,
)
from arnold_pipelines.megaplan.cloud.occurrence_adoption import (
    plan_payload_without_pause,
    resume_cursor_bytes,
)
from arnold_pipelines.megaplan.cloud.operator_pause import PAUSE_ACTION
from arnold_pipelines.megaplan.cloud.runtime_cutover import (
    marker_runtime_identity,
    normalize_runtime_identity,
)
from arnold_pipelines.megaplan.cloud.runtime_manifest import (
    RuntimeManifest,
    write_manifest,
)
from arnold_pipelines.megaplan.cloud.runtime_provenance import (
    RUNTIME_MANIFEST_CUTOVER_ROLLBACK_SCHEMA,
    verify_runtime_manifest_cutover_rollback_receipt,
)
from arnold_pipelines.megaplan.cloud.target_rebind import REBIND_ACTION
from arnold_pipelines.megaplan.types import CliError

REPO_ROOT = Path(__file__).resolve().parents[2]


def _assert_disposable_root(root: Path) -> Path:
    resolved = root.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    assert resolved != REPO_ROOT
    assert "runtime-candidates" not in resolved.parts
    assert not (resolved / "arnold_pipelines" / "megaplan").exists()
    sentinel = resolved / ".t43-disposable-root"
    sentinel.write_text("disposable\n", encoding="utf-8")
    return resolved


def _digest(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_init(root: Path, message: str = "init") -> str:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t43@example.test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t43"], cwd=root, check=True)
    (root / "README").write_text(f"{message}\n", encoding="utf-8")
    subprocess.run(["git", "add", "README"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=root, check=True, capture_output=True)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def _live_tree(tmp_path: Path, name: str) -> tuple[Path, Path, str]:
    root = _assert_disposable_root(tmp_path / name)
    interpreter = root / "generation" / "bin" / "python"
    interpreter.parent.mkdir(parents=True, exist_ok=True)
    interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
    interpreter.chmod(0o755)
    head = _git_init(root, message=name)
    return root, interpreter, head


def _mint(
    tmp_path: Path,
    *,
    action: str,
    occurrence: str = "occ-1",
    target: str = "target-1",
    fence_epoch: int = 3,
    extra: dict[str, object] | None = None,
    ttl: timedelta | None = None,
) -> MutationCapability:
    live, interpreter, _head = _live_tree(tmp_path, name=f"{action}-root")
    payload: dict[str, object] = {
        "occurrence": occurrence,
        "target": target,
        "cursor": "cursor-1",
        "fence_epoch": fence_epoch,
        "evidence_digest": _digest({"occurrence": occurrence, "cursor": "cursor-1"}),
        "scope": action,
        "custody": f"custody:{occurrence}",
        "import_root": str(live),
        "interpreter": str(interpreter),
        "runtime_manifest": {
            "epic": {
                "runtime_root": str(live),
                "dependency_generation": {"interpreter_path": str(interpreter)},
            }
        },
    }
    if extra:
        payload.update(extra)
    kwargs: dict[str, object] = {}
    if ttl is not None:
        kwargs["ttl"] = ttl
        kwargs["now"] = datetime.now(timezone.utc)
    return mint_mutation_capability(
        action=action,
        evidence=payload,
        process_root=live,
        process_python=interpreter,
        **kwargs,  # type: ignore[arg-type]
    )


def _chain_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = _assert_disposable_root(tmp_path / "pause-root")
    initiative = root / ".megaplan" / "initiatives" / "demo"
    initiative.mkdir(parents=True)
    (initiative / "brief.md").write_text("# brief\n", encoding="utf-8")
    spec = initiative / "chain.yaml"
    spec.write_text(
        "anchors:\n  north_star: brief.md\n"
        "milestones:\n  - label: m7\n    idea: brief.md\n",
        encoding="utf-8",
    )
    plan = root / ".megaplan" / "plans" / "m7-plan"
    plan.mkdir(parents=True)
    (plan / "state.json").write_text(
        json.dumps(
            {
                "name": "m7-plan",
                "current_state": "blocked",
                "resume_cursor": {
                    "phase": "critique",
                    "retry_strategy": "repair_phase_contract",
                    "fence_epoch": 3,
                },
                "latest_failure": {
                    "kind": "deterministic_phase_failure",
                    "phase": "critique",
                    "message": "phase contract failed",
                },
                "meta": {"kept": True},
            }
        ),
        encoding="utf-8",
    )
    state = ChainState(
        current_milestone_index=0,
        current_plan_name="m7-plan",
        last_state="blocked",
        completed=[],
    )
    save_chain_state(spec, state)
    return root, spec, plan


def _generation_proof(interpreter_path: str) -> dict[str, object]:
    return {
        "id": "a" * 64,
        "frozen_spec_sha256": "a" * 64,
        "interpreter_path": interpreter_path,
        "venv_digest": "b" * 64,
        "created": "2026-08-07T00:00:00+00:00",
    }


def _make_manifest(
    *,
    runtime_root: str,
    expected_head: str,
    venv_path: str,
    repair_bin: str,
    interpreter_path: str,
    generation: int = 3,
    branch: str = "fixer/t43-demo",
) -> RuntimeManifest:
    return RuntimeManifest.from_dict(
        {
            "runtime_id": "runtime-t43",
            "schema": "1",
            "generation": generation,
            "epic_id": "epic-t43",
            "state": "active",
            "owner": "superfixer",
            "base": {
                "ref": "refs/heads/base/editable-install",
                "commit": expected_head,
                "editable_install_path": "",
                "venv_path": venv_path,
            },
            "epic": {
                "branch": branch,
                "worktree_path": runtime_root,
                "venv_path": venv_path,
                "runtime_root": runtime_root,
                "expected_head": expected_head,
                "repair_bin": repair_bin,
                "deps_lockfile": f"{runtime_root}/uv.lock",
                "dependency_generation": _generation_proof(interpreter_path),
            },
            "indirection": {
                "host_path": runtime_root,
                "container_path": "/workspace/t43",
                "mount_table": [],
                "execution_namespace": "t43-ns",
                "verified_head": expected_head,
                "last_verified_at": "2026-08-07T00:00:00+00:00",
                "attestation": {
                    "module_file": f"{runtime_root}/arnold_pipelines/__init__.py",
                    "module_digest": "d" * 32,
                    "mount_id": "0:42",
                },
            },
            "policy": {
                "policy_sha": "policy-sha-1",
                "model_policy_sha": "model-sha-1",
                "sync_policy": "push-on-promote",
            },
            "promotions": [],
            "timestamps": {
                "created": "2026-08-07T00:00:00+00:00",
                "updated": "2026-08-07T00:00:00+00:00",
                "closed": "",
            },
            "gc_policy": "closed-only",
            "commands": ["megaplan chain"],
        }
    )


def _runtime_identity(root: Path, revision: str) -> dict[str, object]:
    return normalize_runtime_identity(
        {
            "import_root": str(root),
            "source_revision": revision,
            "editable_root": str(root),
            "editable_revision": revision,
            "direct_url": {},
            "pth": [],
            "imports": {},
        }
    )


def _write_marker(
    path: Path,
    *,
    session: str,
    workspace: Path,
    spec: Path,
    identity: dict[str, object],
    relaunch: str,
) -> dict[str, object]:
    marker = {
        "session": session,
        "workspace": str(workspace),
        "remote_spec": str(spec),
        "run_kind": "chain",
        "run_id": f"{session}-run",
        "identity_digest": "t43",
        "started_at": "2026-08-20T00:00:00Z",
        "editable_source_head": identity["source_revision"],
        "editable_install_sync": {
            "status": "content-addressed-runtime",
            "source": identity["import_root"],
            "runtime_sha256": identity["content_sha256"],
        },
        "runtime_binding": {
            "schema": "arnold.megaplan.marker_runtime_binding.v1",
            "current_identity": identity,
            "rebind_events": [],
        },
        "relaunch_command": relaunch,
    }
    path.write_text(json.dumps(marker, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return marker


def _runtime_tree(tmp_path: Path, name: str, *, with_package: bool) -> tuple[Path, Path, Path, str]:
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    venv = root / ".venv"
    (venv / "bin").mkdir(parents=True, exist_ok=True)
    python = venv / "bin" / "python"
    python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    python.chmod(0o755)
    (venv / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
    repair = root / "bin" / "arnold-babysitter"
    if with_package:
        repair = (
            root
            / "arnold_pipelines"
            / "megaplan"
            / "cloud"
            / "wrappers"
            / "arnold-babysitter"
        )
    repair.parent.mkdir(parents=True, exist_ok=True)
    repair.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    repair.chmod(0o755)
    head = _git_init(root, message=name)
    return root, venv, repair, head


class _InjectCrash(Exception):
    def __init__(self, boundary: str) -> None:
        super().__init__(boundary)
        self.boundary = boundary


def _crash_at(wanted: str):
    def _inject(boundary: str) -> None:
        if boundary == wanted:
            raise _InjectCrash(boundary)

    return _inject


class _Fixture:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.binding = _assert_disposable_root(tmp_path / "binding")
        self.project, self.spec, self.plan = _chain_fixture(tmp_path)
        self.from_root, self.from_venv, self.from_repair, self.from_head = _runtime_tree(
            tmp_path, "from-runtime", with_package=False
        )
        self.to_root, self.to_venv, self.to_repair, self.to_head = _runtime_tree(
            tmp_path, "to-runtime", with_package=False
        )
        self.from_python = self.from_venv / "bin" / "python"
        self.to_python = self.to_venv / "bin" / "python"
        self.manifest_path = self.binding / "runtime-manifest.json"
        write_manifest(
            _make_manifest(
                runtime_root=str(self.from_root),
                expected_head=self.from_head,
                venv_path=str(self.from_venv),
                repair_bin=str(self.from_repair),
                interpreter_path=str(self.from_python),
            ),
            self.manifest_path,
        )
        self.from_identity = _runtime_identity(self.from_root, self.from_head)
        self.to_identity = _runtime_identity(self.to_root, self.to_head)
        self.from_relaunch = f"exec {self.from_root}/bin/chain # {self.from_head}"
        self.to_relaunch = f"exec {self.to_root}/bin/chain # {self.to_head}"
        self.marker_dir = self.binding / "markers"
        self.marker_dir.mkdir(parents=True, exist_ok=True)
        self.marker_path = self.marker_dir / "t43.json"
        self.marker = _write_marker(
            self.marker_path,
            session="t43",
            workspace=self.project,
            spec=self.spec,
            identity=self.from_identity,
            relaunch=self.from_relaunch,
        )
        identity_path = self.binding / "identity.json"
        receipt_path = self.binding / "provenance-receipt.json"
        identity_path.write_text(json.dumps(self.to_identity), encoding="utf-8")
        receipt_path.write_text(json.dumps({"schema": "arnold.megaplan.runtime_provenance_receipt.v1"}), encoding="utf-8")
        self.identity_path = identity_path
        self.provenance_receipt_path = receipt_path
        self.cutover_cap = _mint(tmp_path / "cutover", action=CUTOVER_ACTION)
        self.pause_cap = _mint(tmp_path / "pause", action=PAUSE_ACTION)
        rebind_evidence = {
            "occurrence": "occ-1",
            "target": "target-1",
            "cursor": "cursor-1",
            "fence_epoch": 3,
            "evidence_digest": _digest({"occurrence": "occ-1", "cursor": "cursor-1"}),
            "scope": REBIND_ACTION,
            "custody": "custody:occ-1",
            "import_root": str(self.from_root),
            "interpreter": str(self.from_python),
            "runtime_manifest": {
                "epic": {
                    "runtime_root": str(self.from_root),
                    "dependency_generation": {
                        "interpreter_path": str(self.from_python)
                    },
                }
            },
        }
        self.rebind_cap = mint_mutation_capability(
            action=REBIND_ACTION,
            evidence=rebind_evidence,
            process_root=self.from_root,
            process_python=self.from_python,
        )

    def kwargs(self) -> dict[str, object]:
        previous = marker_runtime_identity(json.loads(self.marker_path.read_text()))
        assert previous is not None
        return {
            "capability": self.cutover_cap,
            "pause_capability": self.pause_cap,
            "rebind_capability": self.rebind_cap,
            "occurrence": "occ-1",
            "target": "target-1",
            "fence_epoch": 3,
            "binding_root": self.binding,
            "spec_path": self.spec,
            "project_root": self.project,
            "reason": "t43 cutover",
            "pause_session": "t43",
            "expected_current_milestone": "m7",
            "expected_current_plan": "m7-plan",
            "identity": {"milestone_sequence": [{"index": 0, "label": "m7"}]},
            "from_import_root": str(self.from_root),
            "from_interpreter": str(self.from_python),
            "to_import_root": str(self.to_root),
            "to_interpreter": str(self.to_python),
            "manifest_path": self.manifest_path,
            "expect_manifest_sha256": _sha(self.manifest_path),
            "expect_generation": 3,
            "from_runtime_root": str(self.from_root),
            "from_expected_head": self.from_head,
            "to_runtime_root": str(self.to_root),
            "to_expected_head": self.to_head,
            "to_venv_path": str(self.to_venv),
            "to_repair_bin": str(self.to_repair),
            "runtime_identity_path": self.identity_path,
            "runtime_provenance_receipt_path": self.provenance_receipt_path,
            "to_dependency_generation": _generation_proof(str(self.to_python)),
            "marker_path": self.marker_path,
            "expected_marker_sha256": _sha(self.marker_path),
            "expected_previous_runtime_sha256": previous["content_sha256"],
            "active_runtime_identity": self.to_identity,
            "relaunch_command": self.to_relaunch,
            "marker": json.loads(self.marker_path.read_text()),
            "marker_dir": self.marker_dir,
        }


def _stub_identity(monkeypatch: pytest.MonkeyPatch, fixture: _Fixture) -> None:
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.runtime_manifest._require_resolvable_head",
        lambda runtime_root, head: head,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.runtime_manifest._verify_external_runtime_identity",
        lambda identity_path, receipt_path: fixture.to_identity,
    )


def test_report_cannot_trigger_delivery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _Fixture(tmp_path)
    _stub_identity(monkeypatch, fixture)
    with pytest.raises(CliError) as denied:
        deliver_runtime_cutover(
            **fixture.kwargs(),  # type: ignore[arg-type]
            report={"kind": "efficiency", "auto_materialization": False},
        )
    assert denied.value.code == "report_cannot_trigger_delivery"
    assert inspect_transition(fixture.binding) is None


def test_absent_root_capability_with_valid_evidence_rejects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _Fixture(tmp_path)
    _stub_identity(monkeypatch, fixture)
    kwargs = fixture.kwargs()
    kwargs["capability"] = None
    with pytest.raises(MutationDenied) as denied:
        deliver_runtime_cutover(**kwargs)  # type: ignore[arg-type]
    assert denied.value.code == "capability_absent"


def test_stale_token_rejects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _Fixture(tmp_path)
    _stub_identity(monkeypatch, fixture)
    stale = _mint(
        tmp_path / "stale",
        action=CUTOVER_ACTION,
        ttl=timedelta(seconds=-1),
    )
    kwargs = fixture.kwargs()
    kwargs["capability"] = stale
    with pytest.raises(MutationDenied) as denied:
        deliver_runtime_cutover(**kwargs)  # type: ignore[arg-type]
    assert denied.value.code == "capability_expired"


def test_live_writer_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _Fixture(tmp_path)
    _stub_identity(monkeypatch, fixture)
    publisher = LivenessLeasePublisher(
        "t43", marker_dir=fixture.marker_dir, target_pid=os.getpid()
    )
    publisher.publish_once()
    try:
        live_marker = json.loads(fixture.marker_path.read_text())
        kwargs = fixture.kwargs()
        kwargs["marker"] = live_marker
        with pytest.raises(CliError) as denied:
            deliver_runtime_cutover(**kwargs)  # type: ignore[arg-type]
        assert denied.value.code == "live_writer_refused"
    finally:
        publisher.close()


def test_manifest_marker_mismatch_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _Fixture(tmp_path)
    _stub_identity(monkeypatch, fixture)
    foreign = _runtime_identity(tmp_path / "foreign-runtime", "c" * 40)
    (tmp_path / "foreign-runtime").mkdir(parents=True, exist_ok=True)
    fixture.marker = _write_marker(
        fixture.marker_path,
        session="t43",
        workspace=fixture.project,
        spec=fixture.spec,
        identity=foreign,
        relaunch=f"exec {tmp_path / 'foreign-runtime'}/bin/chain # {'c' * 40}",
    )
    with pytest.raises(CliError) as denied:
        deliver_runtime_cutover(**fixture.kwargs())  # type: ignore[arg-type]
    assert denied.value.code == "manifest_marker_mismatch"


def test_happy_path_duplicate_and_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _Fixture(tmp_path)
    _stub_identity(monkeypatch, fixture)
    plan_before = json.loads((fixture.plan / "state.json").read_text())
    first = deliver_runtime_cutover(**fixture.kwargs())  # type: ignore[arg-type]
    assert first["status"] == "committed"
    assert first["changed"] is True
    receipt = verify_runtime_manifest_cutover_rollback_receipt(
        Path(first["rollback_receipt_path"]),
        expected_manifest_before_sha256=str(first["prior_selection"]["manifest_sha256"]),
    )
    assert receipt["schema"] == RUNTIME_MANIFEST_CUTOVER_ROLLBACK_SCHEMA
    updated = json.loads(fixture.manifest_path.read_text())
    assert updated["generation"] == 4
    assert Path(updated["epic"]["runtime_root"]).resolve() == fixture.to_root.resolve()
    marker = json.loads(fixture.marker_path.read_text())
    assert marker["runtime_binding"]["current_identity"]["import_root"] == str(
        fixture.to_root
    )
    plan_after = json.loads((fixture.plan / "state.json").read_text())
    assert resume_cursor_bytes(plan_after) == resume_cursor_bytes(plan_before)
    assert plan_payload_without_pause(plan_after) == plan_payload_without_pause(plan_before)

    duplicate = deliver_runtime_cutover(**fixture.kwargs())  # type: ignore[arg-type]
    assert duplicate["duplicate"] is True
    assert duplicate["idempotent"] is True
    assert duplicate["changed"] is False
    assert _sha(fixture.manifest_path) == first["current_selection"]["manifest_sha256"]

    current_marker = json.loads(fixture.marker_path.read_text())
    current_identity = marker_runtime_identity(current_marker)
    assert current_identity is not None
    rolled = rollback_runtime_cutover(
        capability=fixture.cutover_cap,
        rebind_capability=fixture.rebind_cap,
        occurrence="occ-1",
        target="target-1",
        fence_epoch=3,
        binding_root=fixture.binding,
        spec_path=fixture.spec,
        project_root=fixture.project,
        reason="t43 rollback",
        expected_current_milestone="m7",
        expected_current_plan="m7-plan",
        identity={"milestone_sequence": [{"index": 0, "label": "m7"}]},
        from_import_root=str(fixture.to_root),
        from_interpreter=str(fixture.to_python),
        to_import_root=str(fixture.from_root),
        to_interpreter=str(fixture.from_python),
        manifest_path=fixture.manifest_path,
        receipt_path=Path(first["rollback_receipt_path"]),
        expected_manifest_before_sha256=str(first["prior_selection"]["manifest_sha256"]),
        marker_path=fixture.marker_path,
        expected_marker_sha256=_sha(fixture.marker_path),
        expected_previous_runtime_sha256=current_identity["content_sha256"],
        prior_runtime_identity=fixture.from_identity,
        relaunch_command=fixture.from_relaunch,
    )
    restored = json.loads(fixture.manifest_path.read_text())
    assert restored["generation"] == 3
    assert Path(restored["epic"]["runtime_root"]).resolve() == fixture.from_root.resolve()
    restored_marker = marker_runtime_identity(json.loads(fixture.marker_path.read_text()))
    assert restored_marker is not None
    assert restored_marker["import_root"] == str(fixture.from_root)
    plan_rolled = json.loads((fixture.plan / "state.json").read_text())
    assert resume_cursor_bytes(plan_rolled) == resume_cursor_bytes(plan_before)
    assert plan_payload_without_pause(plan_rolled) == plan_payload_without_pause(plan_before)
    assert rolled["status"] == "rolled_back"


@pytest.mark.parametrize("boundary", list(PUBLICATION_BOUNDARIES))
def test_publication_boundary_crash_is_prior_or_resumable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    fixture = _Fixture(tmp_path)
    _stub_identity(monkeypatch, fixture)
    prior = json.loads(fixture.manifest_path.read_text())
    prior_marker = json.loads(fixture.marker_path.read_text())
    kwargs = fixture.kwargs()
    if boundary == "committed":
        result = deliver_runtime_cutover(**kwargs)  # type: ignore[arg-type]
        assert result["status"] == "committed"
        return
    with pytest.raises(_InjectCrash) as crashed:
        deliver_runtime_cutover(**kwargs, failure_injector=_crash_at(boundary))  # type: ignore[arg-type]
    assert crashed.value.boundary == boundary
    journal = inspect_transition(fixture.binding)
    assert journal is not None
    assert journal["schema"] == DELIVERY_JOURNAL_SCHEMA
    assert journal["resumable"] is True
    assert journal["status"] == "in_progress"
    current = json.loads(fixture.manifest_path.read_text())
    current_marker = json.loads(fixture.marker_path.read_text())
    prior_root = Path(prior["epic"]["runtime_root"]).resolve()
    current_root = Path(current["epic"]["runtime_root"]).resolve()
    prior_marker_root = Path(
        str((marker_runtime_identity(prior_marker) or {}).get("import_root") or "")
    ).resolve()
    current_marker_root = Path(
        str((marker_runtime_identity(current_marker) or {}).get("import_root") or "")
    ).resolve()
    if current_root == current_marker_root:
        authority = current_selector_marker_authority(
            manifest_path=fixture.manifest_path,
            marker_path=fixture.marker_path,
        )
        assert Path(str(authority["runtime_root"])).resolve() == current_root
    else:
        with pytest.raises(CliError) as torn:
            current_selector_marker_authority(
                manifest_path=fixture.manifest_path,
                marker_path=fixture.marker_path,
            )
        assert torn.value.code == "torn_selector_marker"
    if current_root == prior_root:
        assert current["generation"] == prior["generation"]
    else:
        assert journal.get("selector") or journal.get("stage") in {
            "after_selector",
            "after_receipt",
            "after_marker",
            "after_identity",
        }
        receipt_path = Path(str((journal.get("selector") or {}).get("rollback_receipt_path") or ""))
        if receipt_path.is_file():
            verify_runtime_manifest_cutover_rollback_receipt(
                receipt_path,
                expected_manifest_before_sha256=str(journal["prior_selection"]["manifest_sha256"]),
            )
    del prior_marker_root


def test_selector_cas_race_zero_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _Fixture(tmp_path)
    _stub_identity(monkeypatch, fixture)
    kwargs = fixture.kwargs()
    kwargs["expect_manifest_sha256"] = "a" * 64
    before = fixture.manifest_path.read_bytes()
    with pytest.raises(CliError):
        deliver_runtime_cutover(**kwargs)  # type: ignore[arg-type]
    assert fixture.manifest_path.read_bytes() == before


def test_incomplete_rollback_evidence_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _Fixture(tmp_path)
    _stub_identity(monkeypatch, fixture)
    first = deliver_runtime_cutover(**fixture.kwargs())  # type: ignore[arg-type]
    receipt_path = Path(first["rollback_receipt_path"])
    payload = json.loads(receipt_path.read_text())
    payload.pop("previous_manifest", None)
    payload.pop("content_sha256", None)
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")
    current_identity = marker_runtime_identity(json.loads(fixture.marker_path.read_text()))
    assert current_identity is not None
    with pytest.raises((CliError, ValueError)):
        rollback_runtime_cutover(
            capability=fixture.cutover_cap,
            rebind_capability=fixture.rebind_cap,
            occurrence="occ-1",
            target="target-1",
            fence_epoch=3,
            binding_root=fixture.binding,
            spec_path=fixture.spec,
            project_root=fixture.project,
            reason="t43 rollback",
            expected_current_milestone="m7",
            expected_current_plan="m7-plan",
            identity={"milestone_sequence": [{"index": 0, "label": "m7"}]},
            from_import_root=str(fixture.to_root),
            from_interpreter=str(fixture.to_python),
            to_import_root=str(fixture.from_root),
            to_interpreter=str(fixture.from_python),
            manifest_path=fixture.manifest_path,
            receipt_path=receipt_path,
            expected_manifest_before_sha256=str(first["prior_selection"]["manifest_sha256"]),
            marker_path=fixture.marker_path,
            expected_marker_sha256=_sha(fixture.marker_path),
            expected_previous_runtime_sha256=current_identity["content_sha256"],
            prior_runtime_identity=fixture.from_identity,
            relaunch_command=fixture.from_relaunch,
        )


def test_same_import_root_after_cutover_is_non_event_and_dance_must_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _Fixture(tmp_path)
    _stub_identity(monkeypatch, fixture)
    deliver_runtime_cutover(**fixture.kwargs())  # type: ignore[arg-type]
    result = same_import_root_commit_after_cutover(
        binding_root=fixture.binding,
        import_root=fixture.to_root,
        manifest_path=fixture.manifest_path,
        new_head="e" * 40,
    )
    assert result["non_event"] is True
    assert result["rebind"] is False
    assert result["generation_bump"] is False
    assert result["generation"] == 4
    with pytest.raises(CliError) as denied:
        same_import_root_commit_after_cutover(
            binding_root=fixture.binding,
            import_root=fixture.to_root,
            manifest_path=fixture.manifest_path,
            new_head="e" * 40,
            require_rebind=True,
            require_generation_bump=True,
        )
    assert denied.value.code == "same_import_root_is_non_event"


def test_static_search_proves_t43_consumes_fce_owners_and_no_7272_facade() -> None:
    path = REPO_ROOT / "arnold_pipelines/megaplan/cloud/maintenance_delivery.py"
    source = path.read_text(encoding="utf-8")
    assert "def deliver_runtime_cutover" in source
    assert "from arnold_pipelines.megaplan.cloud.operator_pause import" in source
    assert "from arnold_pipelines.megaplan.cloud.target_rebind import" in source
    assert "apply_runtime_manifest_cutover" in source
    assert "write_manifest" in source
    assert "update_marker_runtime" in source
    assert "cutover_runtime_identity" in source
    assert "observe_liveness_lease" in source
    assert "commit_chain_runtime_cutover" not in source
    assert "prepare_delivery" not in source
    tree = ast.parse(source)
    names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert "prepare_cutover" not in names
    assert "commit_delivery" not in names
    assert "prepare_runtime_manifest_cutover" not in names
    assert DELIVERY_SENTINEL in source
    tests = (REPO_ROOT / "tests/cloud/test_t43_maintenance_delivery.py").read_text()
    assert "require_rebind=True" in tests
    assert "same_import_root_is_non_event" in tests
    chain_cli = (REPO_ROOT / "arnold_pipelines/megaplan/chain/__init__.py").read_text()
    assert "from arnold_pipelines.megaplan.cloud.maintenance_delivery import" in chain_cli
    assert "deliver_runtime_cutover" in chain_cli
    assert "runtime cutover CAS is import_root plus generation interpreter, not SHA-256" in chain_cli
    assert "fce_adopt=adopt_occurrence" in chain_cli
    assert "expected_previous_runtime_sha256=args.from_runtime_sha256" not in chain_cli
    fixer = (
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/fixer_executable_recovery.py"
    ).read_text()
    assert "seed_gates_present: bool = False" in fixer


def test_production_runtime_cutover_cli_invokes_coordinator_and_refuses_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from argparse import Namespace

    from arnold_pipelines.megaplan.chain import run_chain_cli

    fixture = _Fixture(tmp_path)
    _stub_identity(monkeypatch, fixture)
    captured: dict[str, object] = {}

    def _capture(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"status": "committed", "changed": True, "coordinator": "deliver_runtime_cutover"}

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.maintenance_delivery.deliver_runtime_cutover",
        _capture,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.execution_binding.verify_external_runtime_identity",
        lambda identity_path, receipt_path: fixture.to_identity,
    )


    sha_args = Namespace(
        chain_action="runtime-cutover",
        spec=str(fixture.spec),
        project_dir=str(fixture.project),
        from_runtime_sha256="a" * 64,
        to_runtime_sha256="b" * 64,
        from_import_root=str(fixture.from_root),
        from_interpreter=str(fixture.from_python),
        to_import_root=str(fixture.to_root),
        to_interpreter=str(fixture.to_python),
        occurrence="occ-1",
        target="target-1",
        fence_epoch=3,
        capability_handle=None,
        pause_capability_handle=None,
        rebind_capability_handle=None,
        expected_current_milestone="m7",
        expected_current_plan="m7-plan",
        direction="cutover",
        reason="t43 production cutover",
        actor="operator",
        runtime_identity=str(fixture.identity_path),
        runtime_provenance_receipt=str(fixture.provenance_receipt_path),
        runtime_manifest=str(fixture.manifest_path),
        marker=str(fixture.marker_path),
        binding_root=str(fixture.binding),
        expect_manifest_sha256=None,
        expect_generation=None,
        from_expected_head=None,
        to_expected_head=None,
        to_venv_path=None,
        to_repair_bin=None,
        expected_marker_sha256=None,
        relaunch_command=None,
        receipt_path=None,
        mutation_capability=fixture.cutover_cap,
    )
    sha_rc = run_chain_cli(fixture.project, sha_args)
    assert sha_rc != 0
    assert captured == {}

    args = Namespace(
        chain_action="runtime-cutover",
        spec=str(fixture.spec),
        project_dir=str(fixture.project),
        from_runtime_sha256=None,
        to_runtime_sha256=None,
        from_import_root=str(fixture.from_root),
        from_interpreter=str(fixture.from_python),
        to_import_root=str(fixture.to_root),
        to_interpreter=str(fixture.to_python),
        occurrence="occ-1",
        target="target-1",
        fence_epoch=3,
        capability_handle=None,
        pause_capability_handle=None,
        rebind_capability_handle=None,
        expected_current_milestone="m7",
        expected_current_plan="m7-plan",
        direction="cutover",
        reason="t43 production cutover",
        actor="operator",
        runtime_identity=str(fixture.identity_path),
        runtime_provenance_receipt=str(fixture.provenance_receipt_path),
        runtime_manifest=str(fixture.manifest_path),
        marker=str(fixture.marker_path),
        binding_root=str(fixture.binding),
        expect_manifest_sha256=None,
        expect_generation=None,
        from_expected_head=None,
        to_expected_head=None,
        to_venv_path=str(fixture.to_venv),
        to_repair_bin=str(fixture.to_repair),
        expected_marker_sha256=None,
        relaunch_command=fixture.to_relaunch,
        receipt_path=None,
        mutation_capability=fixture.cutover_cap,
    )
    rc = run_chain_cli(fixture.project, args)
    assert rc == 0
    assert captured["from_import_root"] == str(fixture.from_root)
    assert captured["to_import_root"] == str(fixture.to_root)
    assert "expected_previous_runtime_sha256" in captured


def test_production_same_import_root_caller_demanding_rebind_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold_pipelines.megaplan.cloud.fixer_executable_recovery import (
        execute_fixer_recovery_contract,
    )

    fixture = _Fixture(tmp_path)
    _stub_identity(monkeypatch, fixture)
    deliver_runtime_cutover(**fixture.kwargs())  # type: ignore[arg-type]
    with pytest.raises(CliError) as denied:
        same_import_root_commit_after_cutover(
            binding_root=fixture.binding,
            import_root=fixture.to_root,
            manifest_path=fixture.manifest_path,
            new_head="e" * 40,
            require_rebind=True,
            require_generation_bump=True,
        )
    assert denied.value.code == "same_import_root_is_non_event"

    import inspect

    signature = inspect.signature(execute_fixer_recovery_contract)
    assert signature.parameters["seed_gates_present"].default is False
    non_event = same_import_root_commit_after_cutover(
        binding_root=fixture.binding,
        import_root=fixture.to_root,
        manifest_path=fixture.manifest_path,
        new_head="e" * 40,
    )
    assert non_event["seed_gates"] is False
    assert non_event["rebind"] is False
    assert json.loads(fixture.manifest_path.read_text())["generation"] == 4


def test_torn_selector_marker_is_unreadable_as_current_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _Fixture(tmp_path)
    _stub_identity(monkeypatch, fixture)
    kwargs = fixture.kwargs()
    with pytest.raises(_InjectCrash):
        deliver_runtime_cutover(
            **kwargs, failure_injector=_crash_at("after_selector")  # type: ignore[arg-type]
        )
    with pytest.raises(CliError) as denied:
        current_selector_marker_authority(
            manifest_path=fixture.manifest_path,
            marker_path=fixture.marker_path,
        )
    assert denied.value.code == "torn_selector_marker"
    journal = inspect_transition(fixture.binding)
    assert journal is not None
    assert journal["resumable"] is True



def test_production_occurrence_adopt_wraps_guarded_owner() -> None:
    chain_cli = (REPO_ROOT / "arnold_pipelines/megaplan/chain/__init__.py").read_text()
    adopt_block = chain_cli.split('if action == "occurrence-adopt":', 1)[1]
    adopt_block = adopt_block.split("if action ==", 1)[0]
    assert "guarded_occurrence_adoption(" in adopt_block
    assert "fce_adopt=adopt_occurrence" in adopt_block
    assert "payload = adopt_occurrence(" not in adopt_block
