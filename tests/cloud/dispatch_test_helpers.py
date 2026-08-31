from __future__ import annotations

from pathlib import Path

from arnold_pipelines.megaplan.cloud.worker_dispatch import WorkerAdmissionRequest, _digest


def native_proof(
    *,
    backend: str = "codex",
    provider: str = "codex",
    model: str = "gpt-5.5",
    route: str = "codex:gpt-5.5",
    observed_at: str = "2026-08-30T00:00:00+00:00",
) -> dict[str, object]:
    registry = {"constructor": "tests.native:constructor", "generation": "registry-v1", "models": [model]}
    content = {
        "backend": backend,
        "provider": provider,
        "normalized_model": model,
        "route": route,
        "capability_registry": registry,
        "registry_generation": "registry-v1",
        "proof": {"constructable": True, "registry": registry, "preparation": {"ok": True, "backend": backend, "provider": provider, "model": model, "route": route, "operation": "test constructor"}},
        "proof_generation": "proof-v1",
        "family": "gpt" if backend == "codex" else "claude",
    }
    identity = _digest(content)
    return {
        **content,
        "kind": "native_backend",
        "identity": identity,
        "observed_at": observed_at,
        "digest": _digest({**content, "identity": identity, "observed_at": observed_at}),
    }


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
        "production_intent": False,
        "ledger_root": tmp_path,
        "route_liveness_resolver": lambda *_: {
            "kind": "native_backend",
            "identity": "backend",
            "digest": "b" * 64,
            "backend": "codex",
            "provider": "codex",
            "normalized_model": "gpt-5.5",
            "capability_registry": "test-native-registry",
            "proof": "test-native-proof",
            "route": "codex:gpt-5.5",
            "observed_at": "2026-01-01T00:00:00+00:00",
            "family": "gpt",
        },
        "memory_headroom_reader": lambda _spec: {"ok": True, "available_bytes": 10},
        "source_runtime_validator": lambda _request: {
            "ok": True,
            "source_revision": "a" * 40,
            "runtime_vector": {"runtime": "native"},
            "manifest_identity": "manifest",
            "seed_identity": "seed",
            "dependency_interpreter_identity": "/python",
        },
    }
    values.update(changes)
    return WorkerAdmissionRequest(**values)
