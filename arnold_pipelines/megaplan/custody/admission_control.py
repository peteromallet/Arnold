"""Fail-closed admission guards for authority-increasing plan mutations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

from arnold_pipelines.megaplan.types import CliError

from .controlled_writer_registry import (
    Cohort,
    ControlledWriter,
    WriteGuardDecision,
    register_writer,
    writer_guard,
)


INIT_ADMISSION_WRITER_ID = "megaplan.admission.init"
INIT_ADMISSION_SURFACE = "megaplan.admission.init"
AUTO_ADMISSION_WRITER_ID = "megaplan.admission.auto"
AUTO_ADMISSION_SURFACE = "megaplan.admission.auto"
SUPERVISOR_ADMISSION_WRITER_ID = "megaplan.admission.supervisor_driver"
SUPERVISOR_ADMISSION_SURFACE = "megaplan.admission.supervisor_driver"
CHAIN_RUNNER_ADMISSION_WRITER_ID = "megaplan.admission.chain_runner"
CHAIN_RUNNER_ADMISSION_SURFACE = "megaplan.admission.chain_runner"
SOURCE_BINDING_ADMISSION_WRITER_ID = "megaplan.admission.source_binding"
SOURCE_BINDING_ADMISSION_SURFACE = "megaplan.admission.source_binding"


@dataclass(frozen=True)
class AdmissionFence:
    identity: str
    expected: Any
    observed: Any
    satisfied: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "expected": self.expected,
            "observed": self.observed,
            "satisfied": self.satisfied,
            "detail": self.detail,
        }


def _controlled_writer(
    *,
    writer_id: str,
    surface_name: str,
    contract_id: str,
    source_file: str,
    function_name: str,
) -> ControlledWriter:
    return ControlledWriter(
        writer_id=writer_id,
        surface_name=surface_name,
        cohort=Cohort.ACTIVE,
        contract_ids=(contract_id,),
        source_file=source_file,
        function_name=function_name,
        required_wbc_phases=("source_lookup", "fence"),
        action_kind="admission",
    )


_ADMISSION_WRITERS: tuple[ControlledWriter, ...] = (
    _controlled_writer(
        writer_id=INIT_ADMISSION_WRITER_ID,
        surface_name=INIT_ADMISSION_SURFACE,
        contract_id="megaplan.admission.init.v1",
        source_file="arnold_pipelines/megaplan/handlers/init.py",
        function_name="handle_init",
    ),
    _controlled_writer(
        writer_id=AUTO_ADMISSION_WRITER_ID,
        surface_name=AUTO_ADMISSION_SURFACE,
        contract_id="megaplan.admission.auto.v1",
        source_file="arnold_pipelines/megaplan/auto.py",
        function_name="drive",
    ),
    _controlled_writer(
        writer_id=SUPERVISOR_ADMISSION_WRITER_ID,
        surface_name=SUPERVISOR_ADMISSION_SURFACE,
        contract_id="megaplan.admission.supervisor_driver.v1",
        source_file="arnold_pipelines/megaplan/supervisor/driver.py",
        function_name="DefaultRunDriver.drive",
    ),
    _controlled_writer(
        writer_id=CHAIN_RUNNER_ADMISSION_WRITER_ID,
        surface_name=CHAIN_RUNNER_ADMISSION_SURFACE,
        contract_id="megaplan.admission.chain_runner.v1",
        source_file="arnold_pipelines/megaplan/supervisor/chain_runner.py",
        function_name="run_chain",
    ),
    _controlled_writer(
        writer_id=SOURCE_BINDING_ADMISSION_WRITER_ID,
        surface_name=SOURCE_BINDING_ADMISSION_SURFACE,
        contract_id="megaplan.admission.source_binding.v1",
        source_file="arnold_pipelines/megaplan/planning/source_binding.py",
        function_name="capture_canonical_source_binding",
    ),
)


def register_admission_writers() -> None:
    for writer in _ADMISSION_WRITERS:
        try:
            register_writer(writer)
        except ValueError:
            continue


def _synthetic_source_record(
    *,
    selector: str,
    source_path: str,
    semantic_sha256: str = "",
    file_sha256: str = "",
) -> dict[str, Any]:
    return {
        "schema": "arnold.megaplan.admission_source_record.v1",
        "source_path": source_path,
        "project_relative_path": source_path,
        "exists": True,
        "semantic_sha256": semantic_sha256,
        "file_sha256": file_sha256,
        "git_revision": "",
        "git_blob": "",
        "errors": [],
        "selector": selector,
    }


def synthetic_text_source_record(*, selector: str, label: str, text: str) -> dict[str, Any]:
    import hashlib

    encoded = text.encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return _synthetic_source_record(
        selector=selector,
        source_path=f"inline://{label}",
        semantic_sha256=digest,
        file_sha256=digest,
    )


def source_record_for_path(*, source_path: Path, project_dir: Path) -> dict[str, Any]:
    from arnold_pipelines.megaplan.planning.source_binding import canonical_source_identity

    return canonical_source_identity(source_path, project_dir=project_dir)


def validate_admission_mutation(
    *,
    writer_id: str,
    surface_name: str,
    selector: str,
    source_record: Mapping[str, Any],
    fences: Sequence[AdmissionFence] = (),
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    selector_value = str(selector).strip()
    if not selector_value:
        raise CliError(
            "admission_selector_missing",
            f"{surface_name} admission requires a non-empty selector",
        )

    guard = writer_guard(
        writer_id=writer_id,
        surface_name=surface_name,
        override_enforcement=True,
        override_fail_closed=True,
    )
    if guard.decision is not WriteGuardDecision.ALLOWED:
        raise CliError(
            "admission_contract_missing",
            f"{surface_name} admission is not registered as an allowed controlled writer",
            extra={
                "selector": selector_value,
                "writer_guard": {
                    "decision": guard.decision.value,
                    "writer_id": guard.writer_id,
                    "surface_name": guard.surface_name,
                    "diagnostics": list(guard.diagnostics),
                },
            },
        )

    source = dict(source_record)
    if not source.get("exists", True) or source.get("errors"):
        raise CliError(
            "admission_manifest_missing",
            f"{surface_name} admission could not reread the exact source record for {selector_value!r}",
            extra={"selector": selector_value, "source_record": source},
        )

    failed_fence = next((fence for fence in fences if not fence.satisfied), None)
    if failed_fence is not None:
        raise CliError(
            "admission_fence_mismatch",
            f"{surface_name} admission fence {failed_fence.identity!r} is stale or missing",
            extra={
                "selector": selector_value,
                "fence": failed_fence.to_dict(),
                "source_record": source,
            },
        )

    payload = {
        "schema": "arnold.megaplan.admission_evidence.v1",
        "writer_id": writer_id,
        "surface_name": surface_name,
        "selector": selector_value,
        "source_record": source,
        "fences": [fence.to_dict() for fence in fences],
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


def record_admission_evidence(
    state: MutableMapping[str, Any],
    *,
    entry_key: str,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    meta = state.setdefault("meta", {})
    if not isinstance(meta, dict):
        meta = {}
        state["meta"] = meta
    controls = meta.setdefault("admission_controls", {})
    if not isinstance(controls, dict):
        controls = {}
        meta["admission_controls"] = controls
    controls[entry_key] = dict(evidence)
    return controls[entry_key]


__all__ = [
    "AUTO_ADMISSION_SURFACE",
    "AUTO_ADMISSION_WRITER_ID",
    "AdmissionFence",
    "CHAIN_RUNNER_ADMISSION_SURFACE",
    "CHAIN_RUNNER_ADMISSION_WRITER_ID",
    "INIT_ADMISSION_SURFACE",
    "INIT_ADMISSION_WRITER_ID",
    "SOURCE_BINDING_ADMISSION_SURFACE",
    "SOURCE_BINDING_ADMISSION_WRITER_ID",
    "SUPERVISOR_ADMISSION_SURFACE",
    "SUPERVISOR_ADMISSION_WRITER_ID",
    "record_admission_evidence",
    "register_admission_writers",
    "source_record_for_path",
    "synthetic_text_source_record",
    "validate_admission_mutation",
]
