from __future__ import annotations

import logging
import json
import re
from pathlib import Path
from typing import Any, Callable
from types import MappingProxyType

from arnold_pipelines.megaplan._core import load_flag_registry, save_flag_registry
from arnold_pipelines.megaplan.orchestration.critique_status import is_unverifiable_check
from arnold_pipelines.megaplan.types import FlagRecord, FlagRegistry


FLAG_NORMALIZATION_POLICY = MappingProxyType(
    {
        "allowed_categories": (
            "correctness",
            "security",
            "completeness",
            "performance",
            "maintainability",
            "doc-quality",
            "other",
            "verifiability",
        ),
        "default_category": "other",
        "default_severity_hint": "uncertain",
        "severity_hint_to_severity": {
            "likely-significant": "significant",
            "likely-minor": "minor",
            "uncertain": "significant",
        },
        "unexpected_severity_default": "significant",
    }
)


def next_flag_number(flags: list[FlagRecord]) -> int:
    highest = 0
    for flag in flags:
        match = re.fullmatch(r"FLAG-(\d+)", flag["id"])
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def make_flag_id(number: int) -> str:
    return f"FLAG-{number:03d}"


def resolve_severity(hint: str) -> str:
    resolved = FLAG_NORMALIZATION_POLICY["severity_hint_to_severity"].get(hint)
    if resolved is not None:
        return str(resolved)
    logging.getLogger("megaplan").warning(f"Unexpected severity_hint: {hint!r}, defaulting to significant")
    return str(FLAG_NORMALIZATION_POLICY["unexpected_severity_default"])


def _coerce_flag_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [_coerce_flag_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value).strip()


def normalize_flag_record(raw_flag: dict[str, Any], fallback_id: str) -> FlagRecord:
    category = raw_flag.get("category", FLAG_NORMALIZATION_POLICY["default_category"])
    if category not in FLAG_NORMALIZATION_POLICY["allowed_categories"]:
        category = FLAG_NORMALIZATION_POLICY["default_category"]
    severity_hint = raw_flag.get("severity_hint") or FLAG_NORMALIZATION_POLICY["default_severity_hint"]
    if severity_hint not in FLAG_NORMALIZATION_POLICY["severity_hint_to_severity"]:
        severity_hint = FLAG_NORMALIZATION_POLICY["default_severity_hint"]
    raw_id = raw_flag.get("id")
    return {
        "id": fallback_id if raw_id in {None, "", "FLAG-000"} else raw_id,
        "concern": _coerce_flag_text(raw_flag.get("concern")),
        "category": category,
        "severity_hint": severity_hint,
        "evidence": _coerce_flag_text(raw_flag.get("evidence")),
    }


def _review_flag_id(check_id: str, index: int) -> str:
    stem = re.sub(r"[^A-Z0-9]+", "_", check_id.upper()).strip("_") or "CHECK"
    return f"REVIEW-{stem}-{index:03d}"


def _synthesize_flags_from_checks(
    checks: list[dict[str, Any]],
    *,
    category_map: dict[str, str],
    get_check_def: Callable[[str], Any],
    id_prefix: str,
) -> list[dict[str, Any]]:
    synthetic_flags: list[dict[str, Any]] = []
    for check in checks:
        if is_unverifiable_check(check):
            continue
        check_id = check.get("id", "")
        if not isinstance(check_id, str) or not check_id:
            continue
        flagged_findings = [
            finding
            for finding in check.get("findings", [])
            if isinstance(finding, dict) and finding.get("flagged")
        ]
        for index, finding in enumerate(flagged_findings, start=1):
            check_def = get_check_def(check_id)
            if isinstance(check_def, dict):
                severity = check_def.get("default_severity", "uncertain")
            else:
                severity = getattr(check_def, "default_severity", "uncertain")
            if id_prefix == "REVIEW":
                flag_id = _review_flag_id(check_id, index)
            else:
                flag_id = check_id if len(flagged_findings) == 1 else f"{check_id}-{index}"
            synthetic_flags.append(
                {
                    "id": flag_id,
                    "concern": f"{check.get('question', '')}: {finding.get('detail', '')}",
                    "category": category_map.get(check_id, "correctness"),
                    "severity_hint": severity,
                    "evidence": finding.get("detail", ""),
                    "source_check_id": check_id,
                }
            )
    return synthetic_flags


def synthesize_critique_flags(critique: dict[str, Any]) -> list[dict[str, Any]]:
    """Materialize every flagged check finding as a durable top-level flag.

    Critique workers may express the same finding in both ``checks`` and
    ``flags``.  Preserve the explicit flag and add a synthetic flag only when
    no explicit flag from the same check carries the same evidence.  This is
    deliberately idempotent because custody preparation and registry update
    both call it at different persistence boundaries.
    """
    from arnold_pipelines.megaplan.audits.robustness import (
        build_check_category_map,
        get_check_by_id,
    )

    raw_flags = critique.setdefault("flags", [])
    if not isinstance(raw_flags, list):
        return []
    synthetic = _synthesize_flags_from_checks(
        critique.get("checks", []),
        category_map=build_check_category_map(),
        get_check_def=get_check_by_id,
        id_prefix="CRITIQUE",
    )
    for candidate in synthetic:
        source_check_id = candidate.get("source_check_id")
        evidence = _coerce_flag_text(candidate.get("evidence"))
        already_present = False
        for flag in raw_flags:
            if not isinstance(flag, dict) or _coerce_flag_text(flag.get("evidence")) != evidence:
                continue
            existing_source = flag.get("source_check_id")
            if existing_source not in {None, "", source_check_id}:
                continue
            if not existing_source:
                flag["source_check_id"] = source_check_id
            already_present = True
            break
        if not already_present:
            raw_flags.append(candidate)
    return raw_flags


_NEAR_CF_REFERENCE_RE = re.compile(r"^CF-[0-9A-F]{18,22}$")
_CF_CANDIDATE_RE = re.compile(r"^CF-[0-9A-F]{20}$")
_FLAG_REFERENCE_EDIT_RADIUS = 2


def _bounded_edit_distance(source: str, target: str, *, cap: int) -> int | None:
    """Case-sensitive Levenshtein distance, or ``None`` once it exceeds ``cap``."""
    if abs(len(source) - len(target)) > cap:
        return None
    previous = list(range(len(target) + 1))
    for i, src_char in enumerate(source, start=1):
        current = [i]
        row_min = i
        for j, tgt_char in enumerate(target, start=1):
            cost = 0 if src_char == tgt_char else 1
            value = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost)
            current.append(value)
            if value < row_min:
                row_min = value
        if row_min > cap:
            return None
        previous = current
    distance = previous[-1]
    return distance if distance <= cap else None


def _record_unmatched_reference(
    registry: FlagRegistry,
    *,
    reference: str,
    recorded_in: str,
    reference_kind: str,
    reason: str,
    candidates: list[str],
) -> None:
    """Append a deterministic typed row for a flag reference no flag matched."""
    rows = registry.setdefault("unmatched_flag_references", [])
    rows.append(
        {
            "source": recorded_in,
            "reference": reference,
            "reference_kind": reference_kind,
            "reason": reason,
            "candidates": sorted(candidates),
        }
    )


def resolve_flag_reference(
    reference: str,
    registry: FlagRegistry,
    by_id: dict[str, FlagRecord],
    *,
    recorded_in: str,
    reference_kind: str,
    at_iteration: int | None = None,
) -> tuple[str | None, dict[str, Any] | None]:
    """Exact-first flag reference resolution with bounded unique near-miss correction.

    Returns ``(resolved_id, correction_record)``. An exact registry match always
    wins and produces no correction metadata. Otherwise a canonical ``CF-``
    near-reference corrects to the UNIQUE registry candidate within edit radius
    2, and the matched flag records ``id_correction`` provenance (first
    correction wins). Zero or ambiguous near-misses mutate nothing and append a
    typed ``unmatched_flag_references`` row to the registry — never silent.
    """
    if reference in by_id:
        return reference, None
    candidates: list[str] = []
    if _NEAR_CF_REFERENCE_RE.fullmatch(reference):
        for candidate_id in by_id:
            if not _CF_CANDIDATE_RE.fullmatch(candidate_id):
                continue
            if _bounded_edit_distance(reference, candidate_id, cap=_FLAG_REFERENCE_EDIT_RADIUS) is not None:
                candidates.append(candidate_id)
    if len(candidates) == 1:
        matched_id = candidates[0]
        correction: dict[str, Any] = {
            "from": reference,
            "to": matched_id,
            "recorded_in": recorded_in,
            "reference_kind": reference_kind,
        }
        if at_iteration is not None:
            correction["at_iteration"] = at_iteration
        matched_flag = by_id[matched_id]
        existing = matched_flag.get("id_correction")
        if not isinstance(existing, dict) or not existing:
            matched_flag["id_correction"] = correction
        return matched_id, correction
    reason = "ambiguous" if len(candidates) > 1 else "no_match"
    _record_unmatched_reference(
        registry,
        reference=reference,
        recorded_in=recorded_in,
        reference_kind=reference_kind,
        reason=reason,
        candidates=candidates,
    )
    return None, None


def _apply_flag_updates(
    payload: dict[str, Any],
    *,
    plan_dir: Path,
    iteration: int,
    artifact_prefix: str,
    skip_flag_ids: frozenset[str] | None = None,
) -> FlagRegistry:
    registry = load_flag_registry(plan_dir)
    flags = registry.setdefault("flags", [])
    by_id: dict[str, FlagRecord] = {flag["id"]: flag for flag in flags}
    next_number = next_flag_number(flags)
    _skip = skip_flag_ids or frozenset()

    for verified_id in payload.get("verified_flag_ids", []):
        if not isinstance(verified_id, str) or not verified_id:
            continue
        resolved_id, _correction = resolve_flag_reference(
            verified_id,
            registry,
            by_id,
            recorded_in=artifact_prefix,
            reference_kind="verified",
            at_iteration=iteration,
        )
        if resolved_id is None or resolved_id in _skip:
            continue
        by_id[resolved_id]["status"] = "verified"
        by_id[resolved_id]["verified"] = True
        by_id[resolved_id]["verified_in"] = f"{artifact_prefix}_v{iteration}.json"

    for disputed_id in payload.get("disputed_flag_ids", []):
        if not isinstance(disputed_id, str) or not disputed_id:
            continue
        resolved_id, _correction = resolve_flag_reference(
            disputed_id,
            registry,
            by_id,
            recorded_in=artifact_prefix,
            reference_kind="disputed",
            at_iteration=iteration,
        )
        if resolved_id is None or resolved_id in _skip:
            continue
        by_id[resolved_id]["status"] = "disputed"

    for raw_flag in payload.get("flags", []):
        proposed_id = raw_flag.get("id")
        if not proposed_id or proposed_id in {"", "FLAG-000"}:
            proposed_id = make_flag_id(next_number)
            next_number += 1
        normalized = normalize_flag_record(raw_flag, proposed_id)
        if normalized["id"] in _skip:
            continue
        if normalized["id"] in by_id:
            existing = by_id[normalized["id"]]
            existing.update(normalized)
            existing["status"] = "open"
            existing["severity"] = resolve_severity(normalized.get("severity_hint", "uncertain"))
            existing["raised_in"] = f"{artifact_prefix}_v{iteration}.json"
            continue
        severity = resolve_severity(normalized.get("severity_hint", "uncertain"))
        created: FlagRecord = {
            **normalized,
            "raised_in": f"{artifact_prefix}_v{iteration}.json",
            "status": "open",
            "severity": severity,
            "verified": False,
        }
        flags.append(created)
        by_id[created["id"]] = created

    save_flag_registry(plan_dir, registry)
    return registry


def apply_flag_verifications(
    plan_dir: Path,
    verifications: list[dict[str, Any]],
) -> set[str]:
    """Apply evaluator flag_verifications before the critic runs.

    Sets flag status/verified fields per outcome and writes verify_rationale.
    For 'open': resets verified=False and clears verified_in so build_gate_signals
    and review consumers don't see stale verified state.

    Returns the set of flag_ids adjudicated (caller passes this to
    update_flags_after_critique as skip_flag_ids so the critic cannot override
    the evaluator's verdict).
    """
    if not verifications:
        return set()
    registry = load_flag_registry(plan_dir)
    by_id: dict[str, Any] = {flag["id"]: flag for flag in registry.get("flags", [])}
    adjudicated: set[str] = set()
    for fv in verifications:
        fid = fv.get("flag_id", "")
        outcome = fv.get("outcome", "")
        rationale = fv.get("rationale", "")
        if not isinstance(fid, str) or not fid:
            continue
        resolved_id, _correction = resolve_flag_reference(
            fid,
            registry,
            by_id,
            recorded_in="evaluator",
            reference_kind="verification",
        )
        if resolved_id is None:
            continue
        flag = by_id[resolved_id]
        flag["verify_rationale"] = rationale
        if outcome == "verified":
            flag["status"] = "verified"
            flag["verified"] = True
            flag["verified_in"] = "evaluator_verdict.json"
        elif outcome == "open":
            flag["status"] = "open"
            flag["verified"] = False
            flag.pop("verified_in", None)
        elif outcome == "accepted_tradeoff":
            flag["status"] = "accepted_tradeoff"
        adjudicated.add(resolved_id)
    save_flag_registry(plan_dir, registry)
    return adjudicated


def update_flags_after_critique(
    plan_dir: Path,
    critique: dict[str, Any],
    *,
    iteration: int,
    skip_flag_ids: frozenset[str] | None = None,
) -> FlagRegistry:
    synthesize_critique_flags(critique)
    return _apply_flag_updates(
        critique,
        plan_dir=plan_dir,
        iteration=iteration,
        artifact_prefix="critique",
        skip_flag_ids=skip_flag_ids,
    )


def update_flags_after_review(plan_dir: Path, review_payload: dict[str, Any], *, iteration: int) -> FlagRegistry:
    from arnold_pipelines.megaplan.review.checks import build_check_category_map, get_check_by_id

    payload_for_registry = dict(review_payload)
    payload_for_registry["flags"] = [*list(review_payload.get("flags", [])), *(
        _synthesize_flags_from_checks(
            review_payload.get("checks", []),
            category_map=build_check_category_map(),
            get_check_def=get_check_by_id,
            id_prefix="REVIEW",
        )
    )]
    return _apply_flag_updates(payload_for_registry, plan_dir=plan_dir, iteration=iteration, artifact_prefix="review")


def update_flags_after_revise(
    plan_dir: Path,
    flags_addressed: list[Any],
    *,
    plan_file: str,
    summary: str,
) -> FlagRegistry:
    plan_match = re.fullmatch(r"plan_v([1-9][0-9]*)\.md", str(plan_file))
    revise_iteration = int(plan_match.group(1)) if plan_match else None
    raw_items: list[tuple[str, dict[str, Any] | None]] = []
    for item in flags_addressed:
        if isinstance(item, str) and item:
            raw_items.append((item, None))
            continue
        if not isinstance(item, dict):
            continue
        flag_id = item.get("id")
        if not isinstance(flag_id, str) or not flag_id:
            continue
        raw_items.append((flag_id, item))

    registry = load_flag_registry(plan_dir)
    by_id: dict[str, FlagRecord] = {flag["id"]: flag for flag in registry["flags"]}
    addressed_ids: set[str] = set()
    item_resolutions: dict[str, dict[str, Any]] = {}
    for reference, item in raw_items:
        resolved_id, _correction = resolve_flag_reference(
            reference,
            registry,
            by_id,
            recorded_in="revise",
            reference_kind="addressed",
            at_iteration=revise_iteration,
        )
        if resolved_id is None:
            continue
        if item is None:
            addressed_ids.add(resolved_id)
            continue
        resolution = item.get("resolution", "addressed")
        reason = item.get("reason", "")
        where = item.get("where", "")
        # Write resolution for any matched flag (addressed or rejected).
        # Rejected items do NOT get status flipped to addressed.
        if resolution == "rejected":
            item_resolutions[resolved_id] = {
                "kind": "rejected",
                "claim": reason,
                "where": where if isinstance(where, str) else "",
            }
        else:
            addressed_ids.add(resolved_id)
            item_resolutions[resolved_id] = {
                "kind": "fixed",
                "claim": reason,
                "where": where if isinstance(where, str) else "",
            }
    for flag in registry["flags"]:
        fid = flag["id"]
        if fid in addressed_ids:
            flag["status"] = "addressed"
            flag["addressed_in"] = plan_file
        if fid in item_resolutions:
            flag["resolution"] = item_resolutions[fid]
    save_flag_registry(plan_dir, registry)
    return registry


def flag_resolution_summary(flag: dict[str, Any]) -> str:
    """Return the revise resolution claim when present, else fall back to evidence.

    Consumers that show 'what the revise did' after the evidence-overwrite bug
    was fixed should call this instead of reading flag["evidence"] directly.
    """
    resolution = flag.get("resolution")
    if isinstance(resolution, dict) and resolution.get("claim"):
        return resolution["claim"]
    return flag.get("evidence", "")


def update_flags_after_gate(
    plan_dir: Path,
    resolutions: list[dict[str, Any]],
) -> FlagRegistry:
    """Persist flag status changes from validated gate resolutions."""
    registry = load_flag_registry(plan_dir)
    by_id: dict[str, FlagRecord] = {flag["id"]: flag for flag in registry["flags"]}
    for res in resolutions:
        raw_flag_id = res.get("flag_id", "")
        action = res.get("action", "")
        if not isinstance(raw_flag_id, str) or not raw_flag_id:
            continue
        resolved_id, _correction = resolve_flag_reference(
            raw_flag_id,
            registry,
            by_id,
            recorded_in="gate",
            reference_kind="resolution",
        )
        if resolved_id is None:
            continue
        flag_id = resolved_id
        if action == "dispute":
            by_id[flag_id]["status"] = "gate_disputed"
        elif action == "accept_tradeoff":
            by_id[flag_id]["status"] = "accepted_tradeoff"
        elif action == "verify_fixed":
            by_id[flag_id]["status"] = "verified"
            by_id[flag_id]["verified"] = True
            by_id[flag_id]["verified_in"] = "gate.json"
        by_id[flag_id]["gate_resolution"] = {
            "action": action,
            "evidence": _coerce_flag_text(res.get("evidence")),
            "rationale": _coerce_flag_text(res.get("rationale")),
        }
    save_flag_registry(plan_dir, registry)
    return registry
