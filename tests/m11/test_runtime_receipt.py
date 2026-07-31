from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import generate_m11_runtime_receipt as runtime_receipt


IDENTITY_COMPONENTS = (
    "interpreter",
    "editable_checkout",
    "pth_files",
    "imports",
    "source_lineage",
    "wrappers",
    "supervisor_command",
    "target_marker",
)


def _candidate(tmp_path: Path) -> dict:
    interpreter = tmp_path / "python"
    wrapper = tmp_path / "wrappers" / "arnold-supervisor"
    marker = tmp_path / "target.json"
    pth = tmp_path / "runtime.pth"
    candidate = {
        "schema": runtime_receipt.CANDIDATE_SCHEMA,
        "promotion_status": "promoted",
        "repo_root": str(tmp_path / "repo"),
        "revision": "a" * 40,
        "interpreter": str(interpreter),
        "interpreter_sha256": "1" * 64,
        "pth_hashes": {str(pth): "2" * 64},
        "import_paths": {
            "arnold": str(tmp_path / "repo/arnold/__init__.py"),
            "arnold_pipelines": str(tmp_path / "repo/arnold_pipelines/__init__.py"),
            "megaplan": str(tmp_path / "repo/arnold_pipelines/megaplan/__init__.py"),
        },
        "supervisor_python": str(interpreter),
        "supervisor_argv": [
            str(interpreter), "-P", "-m",
            "arnold_pipelines.megaplan.cloud.supervise",
        ],
        "wrapper_dir": str(wrapper.parent),
        "wrapper_hashes": {str(wrapper): "3" * 64},
        "target_marker_path": str(marker),
        "target_marker_sha256": "4" * 64,
        "target_fields": {
            "session_id": "custody-control-plane-20260714",
            "status": "executing",
        },
    }
    candidate["candidate_sha256"] = runtime_receipt.candidate_digest(candidate)
    return candidate


def _identity(*, invalid: str | None = None, error: str = "mismatch") -> dict:
    components = {
        name: {"ok": name != invalid, "errors": [error] if name == invalid else []}
        for name in IDENTITY_COMPONENTS
    }
    errors = [f"{invalid}_invalid"] if invalid else []
    return {
        "schema": "arnold.megaplan.m11_bound_runtime_identity.v1",
        "valid": invalid is None,
        "errors": errors,
        "components": components,
        "content_sha256": "5" * 64,
    }


def test_receipt_is_deterministic_and_has_exact_aggregate_components(
    tmp_path: Path,
) -> None:
    candidate = _candidate(tmp_path)
    calls: list[dict] = []

    def builder(**kwargs):
        calls.append(kwargs)
        return _identity()

    first = runtime_receipt.build_runtime_receipt(
        candidate, identity_builder=builder
    )
    second = runtime_receipt.build_runtime_receipt(
        candidate, identity_builder=builder
    )
    assert first == second
    assert first["schema"] == "m11.runtime-receipt.v1"
    assert first["valid"] is True
    assert set(first["components"]) == {
        "interpreter", "editable_root", "pth", "import_roots",
        "source_lineage", "process_command", "systemd_wrapper",
        "target_marker", "runtime_provenance_receipt",
    }
    assert all(
        row["ok"] is True
        and row["evidence_sha256"].startswith("sha256:")
        and len(row["evidence_sha256"]) == 71
        for row in first["components"].values()
    )
    assert calls[0]["strict"] is True
    assert calls[0]["expected_supervisor_argv"] == candidate["supervisor_argv"]


@pytest.mark.parametrize(
    "component",
    [
        "interpreter",
        "editable_checkout",
        "pth_files",
        "imports",
        "source_lineage",
        "wrappers",
        "supervisor_command",
        "target_marker",
    ],
)
def test_rejects_every_invalid_runtime_binding(
    tmp_path: Path, component: str
) -> None:
    with pytest.raises(runtime_receipt.RuntimeReceiptError, match="runtime_identity_invalid"):
        runtime_receipt.build_runtime_receipt(
            _candidate(tmp_path),
            identity_builder=lambda **_kwargs: _identity(invalid=component),
        )


def test_rejects_dirty_lineage(tmp_path: Path) -> None:
    with pytest.raises(runtime_receipt.RuntimeReceiptError, match="source_lineage"):
        runtime_receipt.build_runtime_receipt(
            _candidate(tmp_path),
            identity_builder=lambda **_kwargs: _identity(
                invalid="source_lineage", error="source_checkout_dirty"
            ),
        )


def test_rejects_candidate_digest_mismatch(tmp_path: Path) -> None:
    candidate = _candidate(tmp_path)
    candidate["revision"] = "b" * 40
    with pytest.raises(
        runtime_receipt.RuntimeReceiptError, match="candidate_digest_mismatch"
    ):
        runtime_receipt.build_runtime_receipt(
            candidate, identity_builder=lambda **_kwargs: _identity()
        )


def test_rejects_supervisor_without_safe_path_flag(tmp_path: Path) -> None:
    candidate = _candidate(tmp_path)
    candidate["supervisor_argv"].remove("-P")
    candidate["candidate_sha256"] = runtime_receipt.candidate_digest(candidate)
    with pytest.raises(
        runtime_receipt.RuntimeReceiptError,
        match="supervisor_safe_path_flag_missing",
    ):
        runtime_receipt.build_runtime_receipt(
            candidate, identity_builder=lambda **_kwargs: _identity()
        )


def test_unpromoted_candidate_never_writes_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = _candidate(tmp_path)
    candidate["promotion_status"] = "candidate"
    candidate["candidate_sha256"] = runtime_receipt.candidate_digest(candidate)
    candidate_path = tmp_path / "candidate.json"
    output = tmp_path / "runtime.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
    monkeypatch.setattr(
        runtime_receipt,
        "m11_bound_runtime_identity",
        lambda **_kwargs: _identity(),
    )
    with pytest.raises(SystemExit) as caught:
        runtime_receipt.main([
            "--candidate", str(candidate_path),
            "--output", str(output),
        ])
    assert caught.value.code == 2
    assert not output.exists()
