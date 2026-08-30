from __future__ import annotations

from pathlib import Path

from arnold_pipelines.megaplan.cloud.worker_dispatch import WorkerAdmissionRequest


def request(tmp_path: Path, **changes: object) -> WorkerAdmissionRequest:
    values: dict[str, object] = {
        "plan_id": "plan",
        "phase": "execute",
        "dispatch_family_id": "family",
        "logical_dispatch_id": "logical",
        "physical_door_id": "door",
        "configured_spec": "codex:gpt-5.5",
        "selected_spec": "codex:gpt-5.5",
        "source_revision": "a" * 40,
        "runtime_vector": {"runtime": "native"},
        "manifest_identity": "manifest",
        "seed_identity": "seed",
        "dependency_interpreter_identity": "/python",
        "prompt_or_phase_input_identity": "prompt",
        "configured_fallback_chain_identity": "",
        "authorized_route_identity": "codex:gpt-5.5",
        "projection_key": "projection",
        "ledger_root": tmp_path,
        "route_liveness_resolver": lambda *_: {"kind": "native_backend", "identity": "backend", "digest": "b" * 64},
        "memory_headroom_reader": lambda _spec: {"ok": True, "available_bytes": 10},
        "source_runtime_validator": lambda _request: True,
    }
    values.update(changes)
    return WorkerAdmissionRequest(**values)
