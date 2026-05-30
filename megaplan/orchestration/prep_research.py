"""Prep triage, read-only research fan-out, and distillation helpers."""

from __future__ import annotations

import json
import multiprocessing as mp
import queue
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from megaplan._core import atomic_write_json, atomic_write_text
from megaplan._core.hermes_fanout import (
    GenericScatterResult,
    scatter_gather,
    with_429_openrouter_fallback,
)
from megaplan.profiles import CANONICAL_PREP_MODELS
from megaplan.prompts import _prep_distill_prompt, _prep_research_prompt, _prep_triage_prompt
from megaplan.schemas import SCHEMAS, strict_schema
from megaplan.types import AgentMode, CliError, PlanState, normalize_robustness, parse_agent_spec
from megaplan.workers import WorkerResult, run_codex_prep_step

_PREP_RESEARCH_FINDING_SCHEMA = strict_schema(SCHEMAS["research.json"]["properties"]["findings"]["items"])
_PREP_RESEARCH_STATUSES = {"complete", "partial", "timed_out", "error", "not_needed"}
_PREP_RESEARCH_CONFIDENCE = {"high", "medium", "low"}

PREP_COMPATIBLE_KEYS = {
    "skip",
    "task_summary",
    "key_evidence",
    "relevant_code",
    "test_expectations",
    "constraints",
    "suggested_approach",
    "primary_criterion",
    "open_questions",
}
PREP_RESEARCH_TOOLSETS = ["file-readonly", "web"]
DEFAULT_PREP_RESEARCH_MAX_ITERATIONS = 12
DEFAULT_RESEARCH_HARD_KILL_GRACE_SECONDS = 2.0
PREP_AREA_CAPS: dict[str, int] = {
    "bare": 1,
    "light": 2,
    "full": 4,
    "thorough": 7,
    "extreme": 10,
}


@dataclass(frozen=True)
class PrepOrchestrationResult:
    worker: WorkerResult
    artifacts: list[str]
    summary: str
    agent: str
    mode: str
    refreshed: bool
    prep_metrics_hash: str | None = None


def compatible_skip_prep_payload() -> dict[str, Any]:
    return {
        "skip": True,
        "task_summary": "",
        "key_evidence": [],
        "relevant_code": [],
        "test_expectations": [],
        "constraints": [],
        "suggested_approach": "",
    }


def minimal_prep_metrics() -> dict[str, Any]:
    return {
        "area_count": 0,
        "fanout_count": 0,
        "forced_count": 0,
        "completed_count": 0,
        "partial_count": 0,
        "timed_out_count": 0,
        "error_count": 0,
        "missed_units": [],
        "total_cost_usd": 0.0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "elapsed_time_ms": 0,
        "files": [],
        "code_refs": [],
        "per_unit": [],
        "gap_notes": [],
        "contradiction_notes": [],
        "overlap_groups": [],
        "cross_reference": {
            "performed": False,
            "checked_files": [],
            "existing_files": [],
            "missing_files": [],
            "shared_files": [],
            "to_be_built_files": [],
        },
        "stage_metrics": {
            "triage": _stage_metrics(),
            "fanout": _stage_metrics(),
            "distill": _stage_metrics(),
        },
    }


def prep_area_cap(state: PlanState) -> int:
    robustness = normalize_robustness(state.get("config", {}).get("robustness", "full"))
    return PREP_AREA_CAPS.get(robustness, PREP_AREA_CAPS["full"])


def research_sentinel(area: dict[str, Any], status: str, error: str) -> dict[str, Any]:
    return {
        "area": str(area.get("id") or area.get("area") or "unknown"),
        "brief": str(area.get("brief") or area.get("area") or ""),
        "status": status,
        "findings": [],
        "files": [],
        "code_refs": [],
        "confidence": "low",
        "error": error,
    }


def _string_list(value: Any, *, field: str) -> list[str]:
    """Coerce a prep-research field into a list of non-empty strings.

    Models routinely return non-list shapes for fields like `files` and
    `code_refs` — a single path as a bare string, a dict mapping path→snippet,
    a comma-separated string. The schema wants list[str], but rejecting any
    non-list outright wastes the whole research area (the failure mode that
    bit area-1 helper-shape-enumeration on phase-3-5-block-a-extension-20260525-2048).
    Coerce where possible:
      * None / "" → []
      * list → keep items, str() each, drop empties
      * dict → take string keys (typically file paths in {path: snippet} maps)
      * str → split on comma/newline if it looks like a list; otherwise wrap
      * anything else → str() and wrap (better to keep noisy evidence than reject)
    """
    if value is None:
        return []
    if isinstance(value, list):
        items: list[Any] = value
    elif isinstance(value, dict):
        items = [k for k in value.keys() if isinstance(k, str)]
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if "\n" in stripped or "," in stripped:
            items = [part.strip() for part in stripped.replace("\n", ",").split(",")]
        else:
            items = [stripped]
    else:
        items = [str(value)]
    result: list[str] = []
    for item in items:
        text = str(item).strip()
        if text:
            result.append(text)
    return result


def _normalize_research_finding(area: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    status = str(payload.get("status") or "").strip()
    if status not in _PREP_RESEARCH_STATUSES:
        raise CliError("worker_parse_error", f"Prep research returned invalid status {status!r}")
    confidence = str(payload.get("confidence") or "").strip()
    if confidence not in _PREP_RESEARCH_CONFIDENCE:
        raise CliError(
            "worker_parse_error",
            f"Prep research returned invalid confidence {confidence!r}",
        )
    return {
        "area": str(payload.get("area") or area.get("id") or area.get("area") or "unknown"),
        "brief": str(payload.get("brief") or area.get("brief") or area.get("area") or "").strip(),
        "status": status,
        "findings": _string_list(payload.get("findings"), field="findings"),
        "files": _string_list(payload.get("files"), field="files"),
        "code_refs": _string_list(payload.get("code_refs"), field="code_refs"),
        "confidence": confidence,
        "error": str(payload.get("error") or "").strip(),
    }


def _research_unit_payload(
    finding: dict[str, Any],
    *,
    elapsed_time_ms: int,
) -> dict[str, Any]:
    return {
        "finding": finding,
        "metrics": {
            "area": str(finding.get("area") or "unknown"),
            "status": str(finding.get("status") or "error"),
            "elapsed_time_ms": max(0, int(elapsed_time_ms)),
            "files": list(finding.get("files") or []),
            "code_refs": list(finding.get("code_refs") or []),
        },
    }


def _reject_write_capable_prep_provider(spec: str, *, stage: str) -> AgentMode:
    parsed = parse_agent_spec(spec)
    if parsed.agent in {"claude", "shannon"}:
        raise CliError(
            "invalid_prep_model",
            f"Explicit {parsed.agent!r} prep model for {stage} is not allowed until a read-only runner exists.",
        )
    if parsed.agent == "codex" and stage == "fanout":
        raise CliError(
            "invalid_prep_model",
            "Codex prep fanout is not allowed; research fanout must use the read-only Hermes runner.",
        )
    if parsed.agent not in {"codex", "hermes"} and stage in {"triage", "distill"}:
        raise CliError(
            "invalid_prep_model",
            f"Prep {stage} currently supports only read-only Codex or Hermes runners.",
        )
    if parsed.agent != "hermes" and stage == "fanout":
        raise CliError(
            "invalid_prep_model",
            "Prep fanout currently supports only the process-isolated read-only Hermes runner.",
        )
    return AgentMode(
        agent=parsed.agent,
        mode="ephemeral",
        refreshed=True,
        model=parsed.model,
        effort=parsed.effort,
        resolved_model=parsed.model,
    )


def resolve_prep_stage_model(state: PlanState, stage: str) -> AgentMode:
    raw_models = state.get("config", {}).get("prep_models", {})
    if isinstance(raw_models, dict) and stage in raw_models:
        raw_spec = raw_models[stage]
        if not isinstance(raw_spec, str) or not raw_spec.strip():
            raise CliError("invalid_prep_model", f"prep_models.{stage} must be a non-empty string")
        return _reject_write_capable_prep_provider(raw_spec, stage=stage)
    try:
        return _reject_write_capable_prep_provider(CANONICAL_PREP_MODELS[stage], stage=stage)
    except KeyError as exc:
        raise CliError("invalid_prep_model", f"Unknown prep stage: {stage}") from exc


def _compatible_prep_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key in PREP_COMPATIBLE_KEYS}


def _stage_metrics(
    *,
    cost_usd: float = 0.0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    elapsed_time_ms: int = 0,
) -> dict[str, Any]:
    return {
        "cost_usd": float(cost_usd or 0.0),
        "prompt_tokens": int(prompt_tokens or 0),
        "completion_tokens": int(completion_tokens or 0),
        "total_tokens": int(total_tokens or 0),
        "elapsed_time_ms": max(0, int(elapsed_time_ms or 0)),
    }


def _hash_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_json(plan_dir: Path, filename: str, payload: dict[str, Any]) -> str:
    atomic_write_json(plan_dir / filename, payload, _plan_dir=plan_dir)
    return _hash_file(plan_dir / filename)


def _artifact_text(plan_dir: Path, filename: str, text: str) -> str:
    atomic_write_text(plan_dir / filename, text, _plan_dir=plan_dir)
    return _hash_file(plan_dir / filename)


def _forced_upstream_areas(state: PlanState) -> list[dict[str, Any]]:
    """Derive one forced prep research area per upstream dependency label.

    Reads ``state.meta.chain_policy.contract_context`` and creates an area
    for each ``dependency_label`` with a brief covering the upstream planned
    interfaces so downstream prep research accounts for the contract surface.
    """
    meta = state.get("meta")
    if not isinstance(meta, dict):
        return []
    chain_policy = meta.get("chain_policy")
    if not isinstance(chain_policy, dict):
        return []
    contract_context = chain_policy.get("contract_context")
    if not isinstance(contract_context, dict):
        return []
    if contract_context.get("plan_only") is not True:
        return []
    dep_labels = contract_context.get("dependency_labels")
    if not isinstance(dep_labels, list) or not dep_labels:
        return []
    upstream_contracts = contract_context.get("upstream_contracts")
    if not isinstance(upstream_contracts, list):
        upstream_contracts = []

    # Build a label→paths index from upstream contracts
    label_paths: dict[str, set[str]] = {}
    for item in upstream_contracts:
        if not isinstance(item, dict):
            continue
        label = str(item.get("milestone_label") or item.get("label") or "").strip()
        if not label:
            continue
        provides = item.get("provides", [])
        if not isinstance(provides, list):
            provides = []
        paths = label_paths.setdefault(label, set())
        for provide in provides:
            if not isinstance(provide, dict):
                continue
            for interface in provide.get("interfaces", []) or []:
                if isinstance(interface, dict):
                    path = str(interface.get("path", "")).strip()
                    if path:
                        paths.add(path)

    forced: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for label in dep_labels:
        if not isinstance(label, str):
            continue
        label = label.strip()
        if not label or label in seen_ids:
            continue
        seen_ids.add(label)
        paths = sorted(label_paths.get(label, []))
        suggested_files = paths[:10]  # keep the area focused
        forced.append({
            "id": f"upstream-{label}",
            "area": f"Upstream contract: {label}",
            "brief": (
                f"Research planned upstream interfaces provided by milestone `{label}` "
                f"so prep can account for contract-surface shape, path expectations, "
                f"and signature constraints during downstream planning."
            ),
            "suggested_files": suggested_files,
        })
    return forced


def _deduplicate_areas(
    forced: list[dict[str, Any]],
    triage_areas: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Insert forced areas before triage areas, keeping the first seen ID.

    Returns a list where forced areas appear first (preserving insertion order)
    and triage areas that share an ``id`` with a forced area are dropped.
    """
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for area in forced:
        aid = str(area.get("id") or area.get("area") or "").strip()
        if aid and aid not in seen:
            seen.add(aid)
            merged.append(area)
    for area in triage_areas:
        aid = str(area.get("id") or area.get("area") or "").strip()
        if aid and aid not in seen:
            seen.add(aid)
            merged.append(area)
    return merged


def _cap_research_areas(
    state: PlanState,
    areas: list[Any],
    *,
    forced_count: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    cap = prep_area_cap(state)
    normalized: list[dict[str, Any]] = []
    for index, area in enumerate(areas):
        if not isinstance(area, dict):
            raise CliError("parse_error", f"prep triage area at index {index} must be an object")
        normalized.append(dict(area))

    # Always retain forced areas even when forced_count > cap.
    if forced_count >= cap:
        # All slots go to forced areas; triage areas are culled.
        return normalized[:forced_count], cap

    return normalized[:cap], cap


def _prep_metrics(
    *,
    original_area_count: int,
    capped_area_count: int,
    forced_count: int = 0,
    findings: list[dict[str, Any]],
    fanout: GenericScatterResult,
    triage_worker: WorkerResult,
    distill_worker: WorkerResult,
) -> dict[str, Any]:
    per_unit = [item for item in fanout.side_results if isinstance(item, dict)]
    files = sorted({path for item in per_unit for path in item.get("files", []) if str(path).strip()})
    code_refs = sorted({ref for item in per_unit for ref in item.get("code_refs", []) if str(ref).strip()})
    triage_stage = _stage_metrics(
        cost_usd=triage_worker.cost_usd,
        prompt_tokens=triage_worker.prompt_tokens,
        completion_tokens=triage_worker.completion_tokens,
        total_tokens=triage_worker.total_tokens,
        elapsed_time_ms=triage_worker.duration_ms,
    )
    fanout_stage = _stage_metrics(
        cost_usd=fanout.total_cost,
        prompt_tokens=fanout.total_prompt_tokens,
        completion_tokens=fanout.total_completion_tokens,
        total_tokens=fanout.total_tokens,
        elapsed_time_ms=sum(int(item.get("elapsed_time_ms", 0) or 0) for item in per_unit),
    )
    distill_stage = _stage_metrics(
        cost_usd=distill_worker.cost_usd,
        prompt_tokens=distill_worker.prompt_tokens,
        completion_tokens=distill_worker.completion_tokens,
        total_tokens=distill_worker.total_tokens,
        elapsed_time_ms=distill_worker.duration_ms,
    )
    return {
        "area_count": original_area_count,
        "fanout_count": capped_area_count,
        "forced_count": forced_count,
        "completed_count": sum(1 for item in findings if item.get("status") == "complete"),
        "partial_count": sum(1 for item in findings if item.get("status") == "partial"),
        "timed_out_count": sum(1 for item in findings if item.get("status") == "timed_out"),
        "error_count": sum(1 for item in findings if item.get("status") == "error"),
        "missed_units": [
            str(item.get("area", index))
            for index, item in enumerate(findings)
            if item.get("status") in {"timed_out", "error"}
        ],
        "total_cost_usd": triage_stage["cost_usd"] + fanout_stage["cost_usd"] + distill_stage["cost_usd"],
        "prompt_tokens": triage_stage["prompt_tokens"]
        + fanout_stage["prompt_tokens"]
        + distill_stage["prompt_tokens"],
        "completion_tokens": triage_stage["completion_tokens"]
        + fanout_stage["completion_tokens"]
        + distill_stage["completion_tokens"],
        "total_tokens": triage_stage["total_tokens"]
        + fanout_stage["total_tokens"]
        + distill_stage["total_tokens"],
        "elapsed_time_ms": triage_stage["elapsed_time_ms"]
        + fanout_stage["elapsed_time_ms"]
        + distill_stage["elapsed_time_ms"],
        "files": files,
        "code_refs": code_refs,
        "per_unit": per_unit,
        "gap_notes": [],
        "contradiction_notes": [],
        "overlap_groups": [],
        "cross_reference": {
            "performed": False,
            "checked_files": [],
            "existing_files": [],
            "missing_files": [],
            "shared_files": [],
            "to_be_built_files": [],
        },
        "stage_metrics": {
            "triage": triage_stage,
            "fanout": fanout_stage,
            "distill": distill_stage,
        },
    }


def _research_overlap_groups(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], set[str]] = {}
    for finding in findings:
        area = str(finding.get("area") or "unknown")
        for path in finding.get("files", []) or []:
            text = str(path).strip()
            if text:
                buckets.setdefault(("file", text), set()).add(area)
        for ref in finding.get("code_refs", []) or []:
            text = str(ref).strip()
            if text:
                buckets.setdefault(("code_ref", text), set()).add(area)
    overlaps: list[dict[str, Any]] = []
    for (kind, value), areas in sorted(buckets.items()):
        if len(areas) < 2:
            continue
        overlaps.append(
            {
                "kind": kind,
                "value": value,
                "areas": sorted(areas),
            }
        )
    return overlaps


def _contradiction_notes(findings: list[dict[str, Any]], overlaps: list[dict[str, Any]]) -> list[str]:
    by_area = {str(item.get("area") or "unknown"): item for item in findings}
    notes: list[str] = []
    for overlap in overlaps:
        areas = overlap["areas"]
        statuses = {str(by_area.get(area, {}).get("status") or "unknown") for area in areas}
        bullet_sets = {
            tuple(sorted(str(bullet).strip() for bullet in by_area.get(area, {}).get("findings", []) if str(bullet).strip()))
            for area in areas
        }
        if len(statuses) > 1 or len(bullet_sets) > 1:
            notes.append(
                f"{overlap['kind']} {overlap['value']} appears in multiple areas with differing evidence/status: "
                + ", ".join(f"{area}={by_area.get(area, {}).get('status', 'unknown')}" for area in areas)
            )
    return notes


def _gap_notes(
    findings: list[dict[str, Any]],
    prep_payload: dict[str, Any],
    cross_reference: dict[str, Any],
) -> list[str]:
    notes: list[str] = []
    for finding in findings:
        area = str(finding.get("area") or "unknown")
        status = str(finding.get("status") or "unknown")
        if status == "partial":
            notes.append(f"{area}: research returned partial coverage.")
        elif status == "timed_out":
            notes.append(f"{area}: research timed out before the area could be closed.")
        elif status == "error":
            error = str(finding.get("error") or "unknown error")
            notes.append(f"{area}: research failed with {error}.")
    if not prep_payload.get("key_evidence"):
        notes.append("Distill produced no compatible key_evidence entries.")
    if not prep_payload.get("relevant_code"):
        notes.append("Distill produced no compatible relevant_code entries.")
    if not prep_payload.get("test_expectations"):
        notes.append("Distill produced no compatible test_expectations entries.")
    missing_files = cross_reference.get("missing_files", [])
    if missing_files:
        notes.append("Referenced files missing during bounded cross-reference: " + ", ".join(missing_files))
    to_be_built = cross_reference.get("to_be_built_files", [])
    if to_be_built:
        labels = sorted(set(
            str(item["upstream_milestone"])
            for item in to_be_built
            if isinstance(item, dict) and item.get("upstream_milestone")
        ))
        paths = sorted(set(
            str(item["path"])
            for item in to_be_built
            if isinstance(item, dict) and item.get("path")
        ))
        notes.append(
            "Files expected from upstream milestone(s) "
            + ", ".join(labels)
            + " (not yet built locally): "
            + ", ".join(paths)
        )
    return notes


def _collect_upstream_provided_paths(state: PlanState) -> dict[str, str]:
    """Return a mapping of provided path → upstream milestone label.

    Reads ``state.meta.chain_policy.contract_context.upstream_contracts``
    and extracts interface paths keyed by their upstream milestone so
    ``_cross_reference_prep_output`` can classify them as to-be-built files.
    """
    meta = state.get("meta")
    if not isinstance(meta, dict):
        return {}
    chain_policy = meta.get("chain_policy")
    if not isinstance(chain_policy, dict):
        return {}
    contract_context = chain_policy.get("contract_context")
    if not isinstance(contract_context, dict):
        return {}
    if contract_context.get("plan_only") is not True:
        return {}
    upstream_contracts = contract_context.get("upstream_contracts")
    if not isinstance(upstream_contracts, list):
        return {}

    path_map: dict[str, str] = {}
    for item in upstream_contracts:
        if not isinstance(item, dict):
            continue
        label = str(item.get("milestone_label") or item.get("label") or "").strip()
        if not label:
            continue
        provides = item.get("provides")
        if not isinstance(provides, list):
            provides = []
        for provide in provides:
            if not isinstance(provide, dict):
                continue
            for interface in provide.get("interfaces", []) or []:
                if not isinstance(interface, dict):
                    continue
                path = str(interface.get("path", "")).strip()
                if path and path not in path_map:
                    path_map[path] = label
    return path_map


def _cross_reference_prep_output(
    *,
    root: Path,
    findings: list[dict[str, Any]],
    prep_payload: dict[str, Any],
    upstream_provided_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    finding_files = {
        str(path).strip()
        for finding in findings
        for path in finding.get("files", []) or []
        if str(path).strip()
    }
    prep_files = {
        str(item.get("file_path") or "").strip()
        for item in prep_payload.get("relevant_code", []) or []
        if isinstance(item, dict) and str(item.get("file_path") or "").strip()
    }
    checked_files = sorted(finding_files | prep_files)

    # Classify upstream-provided paths as to-be-built before filesystem checks.
    provided = upstream_provided_paths or {}
    to_be_built_files: list[dict[str, Any]] = []
    for path in checked_files:
        label = provided.get(path)
        if label:
            to_be_built_files.append({"path": path, "upstream_milestone": label})

    # Only report a file as missing when it is NOT an upstream-provided path
    # (those are expected to not exist locally yet).
    upstream_path_set = set(provided.keys())
    existing_files = sorted(
        path for path in checked_files if (root / path).exists()
    )
    missing_files = sorted(
        path for path in checked_files
        if not (root / path).exists() and path not in upstream_path_set
    )
    return {
        "performed": bool(checked_files),
        "checked_files": checked_files,
        "existing_files": existing_files,
        "missing_files": missing_files,
        "shared_files": sorted(finding_files & prep_files),
        "to_be_built_files": to_be_built_files,
    }


def _assemble_prep_outputs(
    *,
    root: Path,
    triage: dict[str, Any],
    capped_areas: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    metrics: dict[str, Any],
    prep_payload: dict[str, Any],
    upstream_provided_paths: dict[str, str] | None = None,
) -> tuple[dict[str, Any], str]:
    overlaps = _research_overlap_groups(findings)
    cross_reference = _cross_reference_prep_output(
        root=root,
        findings=findings,
        prep_payload=prep_payload,
        upstream_provided_paths=upstream_provided_paths,
    )
    contradiction_notes = _contradiction_notes(findings, overlaps)
    gap_notes = _gap_notes(findings, prep_payload, cross_reference)
    metrics["overlap_groups"] = overlaps
    metrics["contradiction_notes"] = contradiction_notes
    metrics["gap_notes"] = gap_notes
    metrics["cross_reference"] = cross_reference
    return metrics, _prep_dossier_text(
        triage=triage,
        capped_areas=capped_areas,
        findings=findings,
        metrics=metrics,
    )


def _prep_dossier_text(
    *,
    triage: dict[str, Any],
    capped_areas: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    metrics: dict[str, Any],
) -> str:
    lines = [
        "# Prep Research Dossier",
        "",
        "## Triage",
        "",
        str(triage.get("triage_framing") or "").strip() or "(no triage framing)",
        "",
        "## Research Areas",
        "",
    ]
    if capped_areas:
        for index, area in enumerate(capped_areas, start=1):
            label = area.get("id") or area.get("area") or f"area-{index}"
            brief = area.get("brief") or area.get("area") or ""
            lines.append(f"{index}. {label}: {brief}")
    else:
        lines.append("(none)")
    lines.extend(["", "## Findings", ""])
    if findings:
        for finding in findings:
            area = finding.get("area") or "unknown"
            status = finding.get("status") or "unknown"
            brief = finding.get("brief") or ""
            lines.append(f"### {area} ({status})")
            if brief:
                lines.append("")
                lines.append(str(brief))
            bullets = finding.get("findings")
            if isinstance(bullets, list) and bullets:
                lines.append("")
                for bullet in bullets:
                    lines.append(f"- {bullet}")
            error = finding.get("error")
            if error:
                lines.append("")
                lines.append(f"Error: {error}")
            lines.append("")
    else:
        lines.append("(none)")
        lines.append("")
    lines.extend(
        [
            "## Adjudication",
            "",
            "### Gap Notes",
            "",
        ]
    )
    gap_notes = metrics.get("gap_notes", [])
    if gap_notes:
        for note in gap_notes:
            lines.append(f"- {note}")
    else:
        lines.append("- (none)")
    lines.extend(["", "### Contradiction Notes", ""])
    contradiction_notes = metrics.get("contradiction_notes", [])
    if contradiction_notes:
        for note in contradiction_notes:
            lines.append(f"- {note}")
    else:
        lines.append("- (none)")
    lines.extend(["", "### Overlap Groups", ""])
    overlap_groups = metrics.get("overlap_groups", [])
    if overlap_groups:
        for overlap in overlap_groups:
            areas = ", ".join(overlap.get("areas", [])) or "(none)"
            lines.append(f"- {overlap.get('kind')}: {overlap.get('value')} [{areas}]")
    else:
        lines.append("- (none)")
    cross_reference = metrics.get("cross_reference", {})
    to_be_built = cross_reference.get("to_be_built_files", [])
    to_be_built_lines: list[str] = []
    if to_be_built:
        for item in to_be_built:
            if isinstance(item, dict):
                to_be_built_lines.append(
                    f"- {item.get('path', '?')} (from {item.get('upstream_milestone', '?')})"
                )
    lines.extend(
        [
            "",
            "### Bounded Cross-Reference",
            "",
            f"- Performed: {'yes' if cross_reference.get('performed') else 'no'}",
            f"- Shared files: {', '.join(cross_reference.get('shared_files', [])) or '(none)'}",
            f"- Missing files: {', '.join(cross_reference.get('missing_files', [])) or '(none)'}",
        ]
    )
    if to_be_built_lines:
        lines.append(f"- Expected from upstream (not yet built):")
        lines.extend(to_be_built_lines)
    lines.extend(
        [
            "",
            "## Metrics",
            "",
            f"- Areas triaged: {metrics.get('area_count', 0)}",
            f"- Fan-out units run: {metrics.get('fanout_count', 0)}",
            f"- Complete: {metrics.get('completed_count', 0)}",
            f"- Partial: {metrics.get('partial_count', 0)}",
            f"- Timed out: {metrics.get('timed_out_count', 0)}",
            f"- Errors: {metrics.get('error_count', 0)}",
            f"- Missed units: {', '.join(metrics.get('missed_units', [])) or '(none)'}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def run_prep_triage(state: PlanState, plan_dir: Path, *, root: Path) -> WorkerResult:
    model = resolve_prep_stage_model(state, "triage")
    prompt = _prep_triage_prompt(state, plan_dir, root=root)
    if model.agent == "hermes":
        from megaplan.workers.hermes import run_hermes_step

        return run_hermes_step(
            "prep-triage",
            state,
            plan_dir,
            root=root,
            fresh=True,
            model=model.model,
            effort=model.effort,
            prompt_override=prompt,
        )
    return run_codex_prep_step(
        "prep-triage",
        state,
        plan_dir,
        root=root,
        prompt_override=prompt,
        effort=model.effort,
        model=model.model,
    )


def write_skip_prep_artifacts(plan_dir: Path) -> dict[str, Any]:
    payload = compatible_skip_prep_payload()
    atomic_write_json(plan_dir / "prep.json", payload)
    atomic_write_json(plan_dir / "prep_metrics.json", minimal_prep_metrics())
    return payload


def _import_hermes_runtime():
    import megaplan.agent  # noqa: F401
    from hermes_state import SessionDB
    from run_agent import AIAgent

    return AIAgent, SessionDB


def _run_research_child(payload: dict[str, Any], out_queue: mp.Queue) -> None:
    area = payload["area"]
    plan_dir = Path(payload["plan_dir"])
    root = Path(payload["root"])
    state = payload["state"]
    model = payload["model"]
    timeout_seconds = payload["timeout_seconds"]
    max_iterations = payload["max_iterations"]
    session_id = str(uuid.uuid4())
    agent = None
    timer: threading.Timer | None = None
    started = time.monotonic()
    try:
        AIAgent, SessionDB = _import_hermes_runtime()
        db_path = plan_dir / ".hermes_state" / f"state_prep_research_{payload['index']}.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        output_path = plan_dir / ".hermes_state" / f"prep_research_{payload['index']}.json"
        prompt = _prep_research_prompt(
            state,
            plan_dir,
            area=area,
            output_path=output_path,
            root=root,
        )
        from megaplan.runtime.key_pool import resolve_model as _resolve_model
        from megaplan.workers.hermes import (
            _resolve_hermes_cost,
            _streaming_run_kwargs,
            clean_parsed_payload,
            parse_agent_output,
        )
        resolved_model, agent_kwargs = _resolve_model(model)
        agent_max_tokens = 32768
        run_kwargs = _streaming_run_kwargs(model, agent_max_tokens)

        def _timeout() -> None:
            if agent is not None:
                agent.interrupt("research timeout")

        timer = threading.Timer(timeout_seconds, _timeout)
        timer.daemon = True
        timer.start()

        def _make_agent(current_model: str, current_kwargs: dict[str, Any]) -> Any:
            nonlocal agent
            agent = AIAgent(
                model=current_model,
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
                enabled_toolsets=PREP_RESEARCH_TOOLSETS,
                session_id=session_id,
                session_db=SessionDB(db_path=db_path),
                max_iterations=max_iterations,
                max_tokens=agent_max_tokens,
                **current_kwargs,
            )
            agent._print_fn = lambda *args, **kwargs: print(*args, **kwargs, file=sys.stderr)
            return agent

        def _run_attempt(
            current_agent: Any,
            current_output_path: Path,
        ) -> tuple[dict[str, Any], dict[str, Any], float, int, int, int]:
            result = current_agent.run_conversation(user_message=prompt, **run_kwargs)
            parsed, _raw_output = parse_agent_output(
                current_agent,
                result,
                output_path=current_output_path,
                schema=_PREP_RESEARCH_FINDING_SCHEMA,
                step="prep",
                project_dir=Path(state["config"]["project_dir"]),
                plan_dir=plan_dir,
                run_kwargs=run_kwargs,
            )
            clean_parsed_payload(parsed, _PREP_RESEARCH_FINDING_SCHEMA, "prep")
            finding = _normalize_research_finding(area, parsed)
            cost_usd, prompt_tokens, completion_tokens, total_tokens = _resolve_hermes_cost(result)
            return result, finding, cost_usd, prompt_tokens, completion_tokens, total_tokens

        runner = _make_agent(resolved_model, agent_kwargs)
        try:
            result, finding, cost_usd, prompt_tokens, completion_tokens, total_tokens = _run_attempt(runner, output_path)
        except Exception as exc:
            result, finding, cost_usd, prompt_tokens, completion_tokens, total_tokens = (
                with_429_openrouter_fallback(
                    model=model,
                    agent_kwargs=agent_kwargs,
                    exc=exc,
                    log_prefix="[prep-research]",
                    rebuild_template_fn=lambda: output_path,
                    make_agent_fn=lambda m, kw: _make_agent(m, kw),
                    run_attempt_fn=lambda a, op: _run_attempt(a, op),
                    on_fail_message=lambda primary_exc, fallback_exc: (
                        "Prep research failed "
                        f"(both primary and fallback): primary={str(primary_exc) or primary_exc.__class__.__name__}; "
                        f"fallback={str(fallback_exc) or fallback_exc.__class__.__name__}"
                    ),
                    stream=sys.stderr,
                )
            )
        unit_payload = _research_unit_payload(
            finding,
            elapsed_time_ms=int((time.monotonic() - started) * 1000),
        )
        out_queue.put(
            {
                "ok": True,
                "index": payload["index"],
                "payload": unit_payload,
                "cost_usd": cost_usd,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "session_id": session_id,
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
        )
    except BaseException as exc:
        finding = research_sentinel(area, "error", str(exc) or exc.__class__.__name__)
        out_queue.put(
            {
                "ok": False,
                "index": payload["index"],
                "payload": _research_unit_payload(
                    finding,
                    elapsed_time_ms=int((time.monotonic() - started) * 1000),
                ),
                "cost_usd": 0.0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "session_id": session_id,
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
        )
    finally:
        if timer is not None:
            timer.cancel()


def run_hermes_research_unit_process(
    *,
    index: int,
    area: dict[str, Any],
    state: PlanState,
    plan_dir: Path,
    root: Path,
    model: str,
    timeout_seconds: float,
    hard_kill_grace_seconds: float = DEFAULT_RESEARCH_HARD_KILL_GRACE_SECONDS,
    max_iterations: int = DEFAULT_PREP_RESEARCH_MAX_ITERATIONS,
    child_target: Any = _run_research_child,
) -> tuple[int, dict[str, Any], float, int, int, int]:
    ctx = mp.get_context("spawn")
    out_queue: mp.Queue = ctx.Queue()
    payload = {
        "index": index,
        "area": area,
        "state": dict(state),
        "plan_dir": str(plan_dir),
        "root": str(root),
        "model": model,
        "timeout_seconds": timeout_seconds,
        "max_iterations": max_iterations,
    }
    proc = ctx.Process(target=child_target, args=(payload, out_queue))
    proc.start()
    proc.join(timeout_seconds + hard_kill_grace_seconds)
    if proc.is_alive():
        proc.terminate()
        proc.join(hard_kill_grace_seconds)
    if proc.is_alive():
        proc.kill()
        proc.join()
    try:
        result = out_queue.get_nowait()
    except queue.Empty:
        return (
            index,
            _research_unit_payload(
                research_sentinel(area, "timed_out", "research timeout"),
                elapsed_time_ms=int((timeout_seconds + hard_kill_grace_seconds) * 1000),
            ),
            0.0,
            0,
            0,
            0,
        )
    unit_payload = result.get("payload")
    if not isinstance(unit_payload, dict) or not isinstance(unit_payload.get("finding"), dict):
        unit_payload = _research_unit_payload(
            research_sentinel(area, "error", "research child returned invalid finding"),
            elapsed_time_ms=int(result.get("duration_ms", 0) or 0),
        )
    return (
        index,
        unit_payload,
        float(result.get("cost_usd", 0.0) or 0.0),
        int(result.get("prompt_tokens", 0) or 0),
        int(result.get("completion_tokens", 0) or 0),
        int(result.get("total_tokens", 0) or 0),
    )


def run_research_fanout(
    state: PlanState,
    plan_dir: Path,
    *,
    root: Path,
    areas: list[dict[str, Any]],
    timeout_seconds: float = 900.0,
    max_concurrent: int | None = None,
) -> GenericScatterResult:
    model = resolve_prep_stage_model(state, "fanout")
    resolved_model = model.model or model.resolved_model or "deepseek:deepseek-v4-flash"

    def _unpack_unit_result(
        result: Any,
    ) -> tuple[int, dict[str, Any], float, int, int, int]:
        index, payload, cost_usd, pt, ct, tt = result
        if not isinstance(payload, dict) or not isinstance(payload.get("finding"), dict):
            raise CliError("worker_parse_error", "Prep research unit returned invalid payload")
        return index, payload, cost_usd, pt, ct, tt

    def _submit(executor: Any) -> list[Any]:
        futures = []
        for index, area in enumerate(areas):
            future = executor.submit(
                run_hermes_research_unit_process,
                index=index,
                area=area,
                state=state,
                plan_dir=plan_dir,
                root=root,
                model=resolved_model,
                timeout_seconds=timeout_seconds,
            )
            future._megaplan_unit_index = index
            futures.append(future)
        return futures

    raw = scatter_gather(
        num_units=len(areas),
        submit_unit_fn=_submit,
        max_concurrent=max_concurrent,
        unpack_unit_result=_unpack_unit_result,
        on_unit_error=lambda index, exc: (
            _research_unit_payload(
                research_sentinel(areas[index], "error", str(exc) or exc.__class__.__name__),
                elapsed_time_ms=0,
            ),
            0.0,
            0,
            0,
            0,
        ),
    )
    findings: list[dict[str, Any]] = []
    per_unit: list[dict[str, Any]] = []
    for item in raw.ordered_results:
        if not isinstance(item, dict):
            raise CliError("worker_parse_error", "Prep research fan-out returned invalid ordered payload")
        finding = item.get("finding")
        metrics = item.get("metrics")
        if not isinstance(finding, dict) or not isinstance(metrics, dict):
            raise CliError("worker_parse_error", "Prep research fan-out payload missing finding metrics")
        findings.append(finding)
        per_unit.append(metrics)
    return GenericScatterResult(
        ordered_results=findings,
        total_cost=raw.total_cost,
        total_prompt_tokens=raw.total_prompt_tokens,
        total_completion_tokens=raw.total_completion_tokens,
        total_tokens=raw.total_tokens,
        side_results=per_unit,
    )


def distill_prep(
    state: PlanState,
    plan_dir: Path,
    *,
    root: Path,
    triage: dict[str, Any],
    findings: list[dict[str, Any]],
) -> WorkerResult:
    model = resolve_prep_stage_model(state, "distill")
    prompt = _prep_distill_prompt(
        state,
        plan_dir,
        triage=triage,
        findings=findings,
        root=root,
    )
    if model.agent == "hermes":
        from megaplan.workers.hermes import run_hermes_step

        result = run_hermes_step(
            "prep-distill",
            state,
            plan_dir,
            root=root,
            fresh=True,
            model=model.model,
            effort=model.effort,
            prompt_override=prompt,
        )
    else:
        result = run_codex_prep_step(
            "prep-distill",
            state,
            plan_dir,
            root=root,
            prompt_override=prompt,
            effort=model.effort,
            model=model.model,
        )
    result.payload = _compatible_prep_payload(result.payload)
    return result


def run_prep_orchestration(
    state: PlanState,
    plan_dir: Path,
    *,
    root: Path,
) -> PrepOrchestrationResult:
    """Run the triage -> fan-out -> distill prep pipeline.

    The returned ``WorkerResult`` is shaped as the prep worker so existing
    summary, history, session, and receipt code can treat the orchestration as a
    single prep phase.
    """
    started = time.monotonic()
    # Resolve all stages before running anything so fallback validation failures
    # are surfaced before partial artifact writes.
    stage_models = {
        stage: resolve_prep_stage_model(state, stage)
        for stage in ("triage", "fanout", "distill")
    }

    triage_worker = run_prep_triage(state, plan_dir, root=root)
    triage = triage_worker.payload
    _artifact_json(plan_dir, "prep_triage.json", triage)
    areas = triage.get("areas", [])
    if not isinstance(areas, list):
        raise CliError("parse_error", "prep triage output field 'areas' must be a list")
    forced_areas = _forced_upstream_areas(state)
    upstream_provided_paths = _collect_upstream_provided_paths(state)
    merged_areas = _deduplicate_areas(forced_areas, areas)
    capped_areas, _area_cap = _cap_research_areas(
        state, merged_areas, forced_count=len(forced_areas),
    )

    if not capped_areas:
        payload = write_skip_prep_artifacts(plan_dir)
        metrics_hash = _hash_file(plan_dir / "prep_metrics.json")
        worker = WorkerResult(
            payload=payload,
            raw_output=triage_worker.raw_output,
            duration_ms=int((time.monotonic() - started) * 1000),
            cost_usd=triage_worker.cost_usd,
            session_id=triage_worker.session_id,
            trace_output=triage_worker.trace_output,
            rendered_prompt=triage_worker.rendered_prompt,
            model_actual=triage_worker.model_actual,
            prompt_tokens=triage_worker.prompt_tokens,
            completion_tokens=triage_worker.completion_tokens,
            total_tokens=triage_worker.total_tokens,
        )
        return PrepOrchestrationResult(
            worker=worker,
            artifacts=["prep.json", "prep_metrics.json", "prep_triage.json"],
            summary="Prep skipped: triage returned no research areas.",
            agent=stage_models["triage"].agent,
            mode=stage_models["triage"].mode,
            refreshed=True,
            prep_metrics_hash=metrics_hash,
        )

    fanout = run_research_fanout(state, plan_dir, root=root, areas=capped_areas)
    findings = [item for item in fanout.ordered_results if isinstance(item, dict)]
    distill_worker = distill_prep(
        state,
        plan_dir,
        root=root,
        triage=triage,
        findings=findings,
    )
    compatible_payload = _compatible_prep_payload(distill_worker.payload)
    _artifact_json(plan_dir, "prep.json", compatible_payload)
    metrics = _prep_metrics(
        original_area_count=len(areas),
        capped_area_count=len(capped_areas),
        forced_count=len(forced_areas),
        findings=findings,
        fanout=fanout,
        triage_worker=triage_worker,
        distill_worker=distill_worker,
    )
    metrics, dossier_text = _assemble_prep_outputs(
        root=root,
        triage=triage,
        capped_areas=capped_areas,
        findings=findings,
        metrics=metrics,
        prep_payload=compatible_payload,
        upstream_provided_paths=upstream_provided_paths,
    )
    _artifact_json(plan_dir, "research.json", {"findings": findings})
    metrics_hash = _artifact_json(plan_dir, "prep_metrics.json", metrics)
    _artifact_text(plan_dir, "prep_dossier.md", dossier_text)
    total_prompt_tokens = (
        triage_worker.prompt_tokens + fanout.total_prompt_tokens + distill_worker.prompt_tokens
    )
    total_completion_tokens = (
        triage_worker.completion_tokens
        + fanout.total_completion_tokens
        + distill_worker.completion_tokens
    )
    total_tokens = triage_worker.total_tokens + fanout.total_tokens + distill_worker.total_tokens
    worker = WorkerResult(
        payload=compatible_payload,
        raw_output=distill_worker.raw_output,
        duration_ms=int((time.monotonic() - started) * 1000),
        cost_usd=triage_worker.cost_usd + fanout.total_cost + distill_worker.cost_usd,
        session_id=distill_worker.session_id or triage_worker.session_id,
        trace_output=distill_worker.trace_output,
        rendered_prompt=distill_worker.rendered_prompt,
        model_actual=distill_worker.model_actual,
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
        total_tokens=total_tokens,
    )
    code_refs = len(worker.payload.get("relevant_code", []))
    test_refs = len(worker.payload.get("test_expectations", []))
    return PrepOrchestrationResult(
        worker=worker,
        artifacts=["prep.json", "prep_dossier.md", "prep_metrics.json", "prep_triage.json", "research.json"],
        summary=(
            f"Prep complete: captured {code_refs} relevant code reference(s), "
            f"{test_refs} test expectation(s), and {len(findings)} research finding(s)."
        ),
        agent=stage_models["distill"].agent,
        mode=stage_models["distill"].mode,
        refreshed=True,
        prep_metrics_hash=metrics_hash,
    )
