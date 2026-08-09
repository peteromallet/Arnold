"""Bounded, review-gated learning records for the SuperFixer stack.

This module deliberately does not edit prompts, classifiers, source files, or
runtime state.  It preserves immutable failure episodes, derives deterministic
recurrence signals, and promotes only allow-listed lesson identifiers after
ground-truth recovery and human review have been proved.

The control-plane contract is intentionally split in two:

* an episode records what happened, why, which fixer failed, and which
  backstop missed it; and
* a lesson is an approved, content-addressed activation proposal.  Prompt
  consumers receive reviewed template identifiers and structured facts, never
  model-authored free-form instructions.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import fcntl
import json
import os
from pathlib import Path
import re
from typing import Any


EPISODE_SCHEMA = "arnold-superfixer-failure-episode-v1"
LESSON_SCHEMA = "arnold-superfixer-validated-lesson-v1"
L3_CLASSIFICATION_SCHEMA = "arnold-superfixer-retroactive-l3-v1"

LAYERS = frozenset({"watchdog", "L1", "L2", "L3", "deployment", "runtime"})
FAILURE_AXES = frozenset({"TRACKED", "FIXED", "INTENT", "CONTEXT"})
GROUND_TRUTH_SOURCES = (
    "live_process",
    "marker_json",
    "chain_json",
    "plan_state",
    "log_tail",
    "external_state",
)
GROUND_TRUTH_RESULTS = frozenset({"pass", "fail", "not_applicable"})
TARGET_LAYERS = frozenset({"L1", "L2", "L3"})

PROMPT_TEMPLATE_IDS = frozenset(
    {
        "include_raw_failure_mechanism",
        "require_fixer_and_backstop_receipts",
        "require_ground_truth_reverification",
        "require_sibling_failure_hunt",
        "reject_guard_weakening",
    }
)
CLASSIFIER_FEATURE_IDS = frozenset(
    {
        "accepted_unclaimed_repair_request",
        "deterministic_failure_exhaustion",
        "false_success_ground_truth_disagreement",
        "installed_wrapper_drift",
        "missing_meta_repair_evidence",
        "stale_watchdog_report",
        "watchdog_observation_path_failure",
    }
)

SIBLING_REQUIREMENTS: Mapping[str, tuple[str, ...]] = {
    "dependency_import_failure": (
        "watchdog_import_bootstrap",
        "repair_trigger_import_bootstrap",
        "repair_loop_import_bootstrap",
        "meta_repair_import_bootstrap",
        "progress_auditor_import_bootstrap",
        "supervisor_zero_marker_scan",
    ),
    "false_success": (
        "watchdog_dispatch_receipt",
        "l1_ground_truth_recheck",
        "l2_commit_and_retrigger_custody",
        "l3_retroactive_replay",
    ),
    "token_drift": (
        "state_token_writer_inventory",
        "watchdog_dispatch_token_inventory",
        "repair_loop_token_inventory",
        "progress_auditor_token_inventory",
    ),
}

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_FORBIDDEN_LESSON_KEYS = frozenset(
    {"code", "instructions", "patch", "prompt", "prompt_text", "shell", "source"}
)


class EpisodeValidationError(ValueError):
    """Raised when an episode or lesson would weaken evidence custody."""


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _text(value: object) -> str:
    return str(value or "").strip()


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def content_digest(value: object) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _episode_payload(episode: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(episode)
    payload.pop("episode_id", None)
    return payload


def episode_id(episode: Mapping[str, Any]) -> str:
    return "episode-" + content_digest(_episode_payload(episode))


def recurrence_fingerprint(episode: Mapping[str, Any]) -> str:
    mechanism = _mapping(episode.get("mechanism"))
    root = _mapping(episode.get("root_cause"))
    identity = {
        "mechanism_kind": _text(mechanism.get("kind")),
        "mechanism_signature": _text(mechanism.get("signature")),
        "root_layer": _text(root.get("layer")),
        "root_axis": _text(root.get("axis")),
        "failure_class": _text(root.get("failure_class")),
    }
    return "failure-" + content_digest(identity)


def archive_raw_evidence(
    source_path: Path,
    *,
    evidence_root: Path,
    kind: str,
    observed_at: str,
) -> dict[str, Any]:
    """Copy exact bytes into a content-addressed evidence store.

    Raw evidence is never embedded in a prompt or lesson by this module.  The
    copied blob remains available for audit/replay even when operational logs
    rotate.  Existing blobs are byte-verified before reuse.
    """

    data = source_path.read_bytes()
    digest = sha256(data).hexdigest()
    blob = evidence_root / "raw" / digest[:2] / digest
    blob.parent.mkdir(parents=True, exist_ok=True)
    if blob.exists():
        if sha256(blob.read_bytes()).hexdigest() != digest:
            raise EpisodeValidationError(f"evidence blob digest mismatch: {blob}")
    else:
        temporary = blob.with_name(f".{blob.name}.{os.getpid()}.tmp")
        temporary.write_bytes(data)
        os.chmod(temporary, 0o600)
        os.replace(temporary, blob)
    stat = source_path.stat()
    return {
        "kind": kind,
        "source_path": str(source_path),
        "archive_path": str(blob),
        "sha256": digest,
        "size_bytes": len(data),
        "source_mtime_ns": stat.st_mtime_ns,
        "observed_at": observed_at,
    }


def build_episode(
    *,
    observed_at: str,
    session: str,
    plan: str,
    symptom: Mapping[str, Any],
    mechanism: Mapping[str, Any],
    root_cause: Mapping[str, Any],
    missed_backstop: Mapping[str, Any],
    evidence: Sequence[Mapping[str, Any]],
    contradictions: Sequence[Mapping[str, Any]] = (),
    facts: Mapping[str, Any] | None = None,
    parent_episode_id: str = "",
) -> dict[str, Any]:
    episode: dict[str, Any] = {
        "schema_version": EPISODE_SCHEMA,
        "observed_at": observed_at,
        "session": session,
        "plan": plan,
        "symptom": dict(symptom),
        "mechanism": dict(mechanism),
        "root_cause": dict(root_cause),
        "missed_backstop": dict(missed_backstop),
        "evidence": [dict(item) for item in evidence],
        "contradictions": [dict(item) for item in contradictions],
        "facts": dict(facts or {}),
        "parent_episode_id": parent_episode_id,
        "learning_status": "observed",
    }
    episode["recurrence_fingerprint"] = recurrence_fingerprint(episode)
    episode["episode_id"] = episode_id(episode)
    validate_episode(episode)
    return episode


def revise_episode(
    episode: Mapping[str, Any],
    **changes: object,
) -> dict[str, Any]:
    """Create an immutable successor instead of rewriting episode history."""

    validate_episode(episode)
    revised = deepcopy(dict(episode))
    revised.update(deepcopy(changes))
    revised["parent_episode_id"] = episode["episode_id"]
    revised["recurrence_fingerprint"] = recurrence_fingerprint(revised)
    revised["episode_id"] = episode_id(revised)
    validate_episode(revised)
    return revised


def validate_episode(episode: Mapping[str, Any]) -> None:
    errors: list[str] = []
    if episode.get("schema_version") != EPISODE_SCHEMA:
        errors.append("schema_version_invalid")
    for key in ("observed_at", "session", "plan"):
        if not _text(episode.get(key)):
            errors.append(f"{key}_missing")
    try:
        parsed = datetime.fromisoformat(_text(episode.get("observed_at")).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            errors.append("observed_at_not_timezone_aware")
    except ValueError:
        errors.append("observed_at_invalid")

    symptom = _mapping(episode.get("symptom"))
    mechanism = _mapping(episode.get("mechanism"))
    root = _mapping(episode.get("root_cause"))
    backstop = _mapping(episode.get("missed_backstop"))
    if not _text(symptom.get("kind")) or not _text(symptom.get("summary")):
        errors.append("symptom_incomplete")
    if not _text(mechanism.get("kind")) or not _text(mechanism.get("signature")):
        errors.append("mechanism_incomplete")
    if _text(root.get("layer")) not in LAYERS:
        errors.append("root_cause_layer_invalid")
    if _text(root.get("axis")) not in FAILURE_AXES:
        errors.append("root_cause_axis_invalid")
    if not _text(root.get("failure_class")):
        errors.append("failure_class_missing")
    if _text(backstop.get("layer")) not in LAYERS:
        errors.append("missed_backstop_layer_invalid")
    if _text(backstop.get("axis")) not in FAILURE_AXES:
        errors.append("missed_backstop_axis_invalid")
    if _text(backstop.get("layer")) == _text(root.get("layer")):
        errors.append("backstop_must_be_distinct_from_root_layer")

    evidence = _list(episode.get("evidence"))
    if not evidence:
        errors.append("raw_evidence_missing")
    for index, item in enumerate(evidence):
        ref = _mapping(item)
        digest = _text(ref.get("sha256"))
        if not _text(ref.get("kind")):
            errors.append(f"evidence_{index}_kind_missing")
        if not _text(ref.get("archive_path")):
            errors.append(f"evidence_{index}_archive_missing")
        if not _SHA256_RE.fullmatch(digest):
            errors.append(f"evidence_{index}_digest_invalid")
    expected_fingerprint = recurrence_fingerprint(episode)
    if episode.get("recurrence_fingerprint") != expected_fingerprint:
        errors.append("recurrence_fingerprint_mismatch")
    if episode.get("episode_id") != episode_id(episode):
        errors.append("episode_id_mismatch")
    if errors:
        raise EpisodeValidationError(", ".join(errors))


def persist_episode(root: Path, episode: Mapping[str, Any]) -> Path:
    """Persist an immutable episode and append a custody journal receipt."""

    validate_episode(episode)
    identifier = _text(episode.get("episode_id"))
    destination = root / "episodes" / f"{identifier}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(dict(episode), indent=2, sort_keys=True) + "\n"
    if destination.exists():
        if destination.read_text(encoding="utf-8") != encoded:
            raise EpisodeValidationError("immutable episode id collision")
        return destination
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    temporary.write_text(encoded, encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, destination)

    journal = root / "events.ndjson"
    journal.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event": "failure_episode_recorded",
        "episode_id": identifier,
        "episode_sha256": sha256(encoded.encode("utf-8")).hexdigest(),
        "path": str(destination),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    with journal.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(_canonical_json(event) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return destination


def deterministic_recurrence(
    episodes: Iterable[Mapping[str, Any]],
    *,
    threshold: int = 3,
) -> list[dict[str, Any]]:
    if threshold < 2:
        raise ValueError("deterministic recurrence threshold must be at least 2")
    items = list(episodes)
    counts = Counter(_text(item.get("recurrence_fingerprint")) for item in items)
    results: list[dict[str, Any]] = []
    for fingerprint, count in sorted(counts.items()):
        if not fingerprint:
            continue
        representative = next(
            item for item in items if _text(item.get("recurrence_fingerprint")) == fingerprint
        )
        failure_class = _text(_mapping(representative.get("root_cause")).get("failure_class"))
        results.append(
            {
                "fingerprint": fingerprint,
                "count": count,
                "deterministic": count >= threshold,
                "circuit_breaker_required": count >= threshold,
                "sibling_hunt_required": count >= threshold,
                "required_sibling_classes": list(SIBLING_REQUIREMENTS.get(failure_class, ())),
            }
        )
    return results


def retroactive_l3_classification(episode: Mapping[str, Any]) -> dict[str, Any]:
    """Classify a historical episode without model judgement.

    This is the integration seam for L3 gather/replay.  It emits deterministic
    reason identifiers and a bounded structured context, never a repair action.
    """

    validate_episode(episode)
    symptom = _mapping(episode.get("symptom"))
    mechanism = _mapping(episode.get("mechanism"))
    root = _mapping(episode.get("root_cause"))
    backstop = _mapping(episode.get("missed_backstop"))
    facts = _mapping(episode.get("facts"))
    reasons: list[str] = []
    if (
        _text(root.get("layer")) == "watchdog"
        and _text(root.get("axis")) == "TRACKED"
        and _text(mechanism.get("kind")) == "dependency_import_failure"
    ):
        reasons.append("watchdog_observation_path_failure")
    if facts.get("accepted_unclaimed_request") is True:
        reasons.append("accepted_unclaimed_repair_request")
    if facts.get("watchdog_report_stale") is True:
        reasons.append("stale_watchdog_report")
    if facts.get("l3_deterministic_evidence_empty") is True:
        reasons.append("missing_meta_repair_evidence")
    if facts.get("repair_reported_dispatched_without_claim") is True:
        reasons.append("false_success_ground_truth_disagreement")

    actionable = bool(
        reasons
        and _text(symptom.get("kind")) in {"runner_stopped", "repair_not_claimed"}
        and _text(backstop.get("layer")) in {"L2", "L3"}
        and _text(mechanism.get("signature"))
        and episode.get("evidence")
    )
    return {
        "schema_version": L3_CLASSIFICATION_SCHEMA,
        "episode_id": episode.get("episode_id"),
        "detected": bool(reasons),
        "actionable_context": actionable,
        "reasons": reasons,
        "failure_episode": {
            "symptom": dict(symptom),
            "mechanism": dict(mechanism),
            "root_cause": dict(root),
            "missed_backstop": dict(backstop),
            "evidence_refs": [
                {
                    "kind": _mapping(item).get("kind"),
                    "archive_path": _mapping(item).get("archive_path"),
                    "sha256": _mapping(item).get("sha256"),
                }
                for item in _list(episode.get("evidence"))
            ],
        },
        "repair_authorized": False,
    }


def _receipt_names(receipts: Sequence[Mapping[str, Any]]) -> set[str]:
    return {_text(item.get("kind")) for item in receipts if _text(item.get("kind"))}


def validate_episode_for_learning(episode: Mapping[str, Any]) -> None:
    """Require end-to-end custody before an episode can teach future layers."""

    validate_episode(episode)
    errors: list[str] = []
    repair = _mapping(episode.get("repair"))
    verification = _mapping(episode.get("verification"))
    review = _mapping(episode.get("review"))
    regression_receipts = [
        _mapping(item) for item in _list(episode.get("regression_receipts"))
    ]
    detection_rules = [
        _mapping(item) for item in _list(episode.get("detection_rules"))
    ]
    sibling_receipts = [
        _mapping(item) for item in _list(episode.get("sibling_hunt_receipts"))
    ]
    ground_truth = _mapping(verification.get("ground_truth"))

    if repair.get("fixer_fixed") is not True:
        errors.append("failed_fixer_not_fixed")
    if repair.get("backstop_fixed") is not True:
        errors.append("missed_backstop_not_fixed")
    if not _COMMIT_RE.fullmatch(_text(repair.get("commit_sha"))):
        errors.append("accepted_commit_custody_missing")
    if not _text(repair.get("ordinary_retrigger_run_id")):
        errors.append("ordinary_retrigger_run_missing")
    if not _text(repair.get("ordinary_retrigger_manifest_path")):
        errors.append("ordinary_retrigger_manifest_missing")
    if verification.get("original_session_advanced") is not True:
        errors.append("original_session_did_not_advance")
    if verification.get("guard_weakened") is not False:
        errors.append("guard_weakening_not_disproved")
    if verification.get("fix_deployed") is not True:
        errors.append("running_fix_not_verified")

    for source in GROUND_TRUTH_SOURCES:
        result = _mapping(ground_truth.get(source))
        if _text(result.get("result")) not in GROUND_TRUTH_RESULTS:
            errors.append(f"ground_truth_{source}_missing")
        if _text(result.get("result")) != "not_applicable" and not (
            _text(result.get("path")) and _SHA256_RE.fullmatch(_text(result.get("sha256")))
        ):
            errors.append(f"ground_truth_{source}_receipt_invalid")

    receipt_names = _receipt_names(regression_receipts)
    if "historical_episode_replay" not in receipt_names:
        errors.append("retroactive_auditor_regression_missing")
    if "sibling_failure_class" not in receipt_names:
        errors.append("sibling_regression_missing")
    for index, receipt in enumerate(regression_receipts):
        if receipt.get("pre_fix_failed") is not True:
            errors.append(f"regression_{index}_pre_fix_failure_missing")
        if receipt.get("post_fix_passed") is not True:
            errors.append(f"regression_{index}_post_fix_pass_missing")
        if not _text(receipt.get("test_node")):
            errors.append(f"regression_{index}_test_node_missing")

    if not detection_rules:
        errors.append("deterministic_detection_rule_missing")
    for index, rule in enumerate(detection_rules):
        if not _text(rule.get("rule_id")) or not _text(rule.get("implementation_path")):
            errors.append(f"detection_rule_{index}_incomplete")
        if not _list(rule.get("test_nodes")):
            errors.append(f"detection_rule_{index}_tests_missing")

    failure_class = _text(_mapping(episode.get("root_cause")).get("failure_class"))
    required_siblings = set(SIBLING_REQUIREMENTS.get(failure_class, ()))
    observed_siblings = {
        _text(item.get("sibling_class"))
        for item in sibling_receipts
        if item.get("checked") is True
    }
    if required_siblings - observed_siblings:
        errors.append("required_sibling_hunt_incomplete")

    if review.get("approved") is not True:
        errors.append("human_review_approval_missing")
    if not _text(review.get("reviewer")) or not _text(review.get("approved_at")):
        errors.append("review_custody_incomplete")
    if not _text(review.get("rollback_ref")):
        errors.append("rollback_ref_missing")
    if errors:
        raise EpisodeValidationError(", ".join(errors))


def _forbidden_keys(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in _FORBIDDEN_LESSON_KEYS:
                found.add(str(key).lower())
            found.update(_forbidden_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_forbidden_keys(child))
    return found


def promote_validated_lesson(
    episode: Mapping[str, Any],
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    """Return an approved-but-not-activated bounded lesson manifest."""

    validate_episode_for_learning(episode)
    errors: list[str] = []
    forbidden = _forbidden_keys(proposal)
    if forbidden:
        errors.append("free_form_self_modification_forbidden:" + ",".join(sorted(forbidden)))
    templates = {_text(item) for item in _list(proposal.get("prompt_template_ids"))}
    features = {_text(item) for item in _list(proposal.get("classifier_feature_ids"))}
    targets = {_text(item) for item in _list(proposal.get("target_layers"))}
    detector_rules = {_text(item) for item in _list(proposal.get("detector_rule_ids"))}
    implemented_rules = {
        _text(_mapping(item).get("rule_id"))
        for item in _list(episode.get("detection_rules"))
    }
    if not templates or not templates <= PROMPT_TEMPLATE_IDS:
        errors.append("prompt_template_not_allowlisted")
    if not features or not features <= CLASSIFIER_FEATURE_IDS:
        errors.append("classifier_feature_not_allowlisted")
    if not targets or not targets <= TARGET_LAYERS:
        errors.append("target_layer_not_allowlisted")
    if not detector_rules or not detector_rules <= implemented_rules:
        errors.append("detector_rule_not_validated_by_episode")
    rollback = _mapping(proposal.get("rollback"))
    if not _text(rollback.get("ref")) or not _text(rollback.get("procedure_id")):
        errors.append("bounded_rollback_contract_missing")
    if errors:
        raise EpisodeValidationError(", ".join(errors))

    body = {
        "schema_version": LESSON_SCHEMA,
        "source_episode_id": episode.get("episode_id"),
        "source_episode_fingerprint": episode.get("recurrence_fingerprint"),
        "prompt_template_ids": sorted(templates),
        "classifier_feature_ids": sorted(features),
        "detector_rule_ids": sorted(detector_rules),
        "target_layers": sorted(targets),
        "review": dict(_mapping(episode.get("review"))),
        "repair_commit_sha": _mapping(episode.get("repair")).get("commit_sha"),
        "rollback": dict(rollback),
        "activation_status": "approved_not_activated",
    }
    body["lesson_id"] = "lesson-" + content_digest(body)
    return body


def bounded_prompt_projection(lessons: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Project identifiers only; reviewed code owns their static wording."""

    accepted = [
        lesson
        for lesson in lessons
        if lesson.get("schema_version") == LESSON_SCHEMA
        and lesson.get("activation_status") in {"approved_not_activated", "active"}
    ]
    return {
        "schema_version": "arnold-superfixer-bounded-prompt-projection-v1",
        "lesson_ids": sorted(_text(item.get("lesson_id")) for item in accepted),
        "prompt_template_ids": sorted(
            {
                _text(template)
                for item in accepted
                for template in _list(item.get("prompt_template_ids"))
                if _text(template)
            }
        ),
        "classifier_feature_ids": sorted(
            {
                _text(feature)
                for item in accepted
                for feature in _list(item.get("classifier_feature_ids"))
                if _text(feature)
            }
        ),
        "free_form_text": False,
    }


__all__ = [
    "CLASSIFIER_FEATURE_IDS",
    "EPISODE_SCHEMA",
    "EpisodeValidationError",
    "LESSON_SCHEMA",
    "PROMPT_TEMPLATE_IDS",
    "SIBLING_REQUIREMENTS",
    "archive_raw_evidence",
    "bounded_prompt_projection",
    "build_episode",
    "content_digest",
    "deterministic_recurrence",
    "episode_id",
    "persist_episode",
    "promote_validated_lesson",
    "recurrence_fingerprint",
    "revise_episode",
    "retroactive_l3_classification",
    "validate_episode",
    "validate_episode_for_learning",
]
