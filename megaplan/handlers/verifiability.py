from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from megaplan.types import CliError, StepResponse
from megaplan.planning.state import STATE_AWAITING_HUMAN_VERIFY, STATE_DONE
from megaplan._core import atomic_write_json, latest_plan_meta_path, load_plan, now_utc, read_json, save_state_merge_meta
from .shared import _warn_read_fallback


def get_human_verification_status(
    plan_dir: Path,
    plan_meta: dict[str, Any],
    *,
    worker_caps: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    """Return latest-verdict human-verification status for a plan.

    Latest-verdict semantics: a later ``fail`` revokes an earlier ``pass``;
    a later ``pass`` satisfies a previous ``fail``.  For records with the
    same timestamp, file-order is the tiebreaker (earlier in the list wins
    for determinism, meaning the *last* occurrence in file order is the
    latest verdict).

    Returns a dict with keys ``rows``, ``all_deferred_must_verified``,
    ``semantics``, ``pending``, and ``verified``.
    """
    success_criteria: list[dict[str, Any]] = plan_meta.get("success_criteria", [])

    # --- classify deferred human criteria -----------------------------------
    if worker_caps is not None:
        from arnold.pipelines.megaplan.orchestration.verifiability import classify_criteria
        _, human_deferred = classify_criteria(success_criteria, worker_caps)
    else:
        # Without worker caps we cannot classify – treat everything as
        # deferred so the caller can still run latest-verdict on existing
        # records.  This path is used by the remote list command when
        # worker capabilities are not available.
        human_deferred = list(success_criteria)

    deferred_must_idxs: set[int] = {
        i for i, sc in enumerate(success_criteria)
        if sc in human_deferred and sc.get("priority") == "must"
    }

    # --- load verification records ------------------------------------------
    verifications_path = plan_dir / "human_verifications.json"
    raw_verifications: list[dict[str, Any]] = []
    if verifications_path.exists():
        try:
            loaded = json.loads(verifications_path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                raw_verifications = loaded
        except json.JSONDecodeError:
            _warn_read_fallback(
                "M3A_WARN_CORRUPT_VERIFICATIONS",
                path=verifications_path,
                reason="corrupt_json",
            )
            raw_verifications = []
        except (OSError, UnicodeDecodeError):
            _warn_read_fallback(
                "M3A_WARN_CORRUPT_VERIFICATIONS",
                path=verifications_path,
                reason="unreadable",
            )
            raw_verifications = []

    # --- group by criterion_idx, pick latest per criterion ------------------
    # We iterate in file order (ascending index).  For records with equal
    # timestamps the later one in the file wins (last-write-wins per the
    # append-only log convention).
    latest: dict[int, dict[str, Any]] = {}
    for rec in raw_verifications:
        if not isinstance(rec, dict):
            continue
        idx = rec.get("criterion_idx")
        if not isinstance(idx, int) or idx < 0 or idx >= len(success_criteria):
            continue
        ts = rec.get("timestamp", "")
        if not isinstance(ts, str) or not ts:
            continue
        verdict = rec.get("verdict")
        if verdict not in ("pass", "fail"):
            continue

        existing = latest.get(idx)
        if existing is None:
            latest[idx] = rec
        else:
            existing_ts = existing.get("timestamp", "")
            if ts > existing_ts:
                latest[idx] = rec
            elif ts == existing_ts:
                # Same timestamp → later in file order wins (deterministic).
                latest[idx] = rec

    # --- build rows ---------------------------------------------------------
    rows: list[dict[str, Any]] = []
    verified_count = 0
    pending_count = 0
    for i, sc in enumerate(success_criteria):
        is_deferred_must = i in deferred_must_idxs
        rec = latest.get(i)

        if rec is not None and rec.get("verdict") == "pass":
            row_verified = True
            verified_count += 1
        else:
            row_verified = False
            if is_deferred_must:
                pending_count += 1

        rows.append({
            "criterion_idx": i,
            "criterion": sc.get("criterion", ""),
            "priority": sc.get("priority", ""),
            "latest_verdict": rec.get("verdict") if rec else None,
            "latest_timestamp": rec.get("timestamp") if rec else None,
            "verified": row_verified,
            "deferred_must": is_deferred_must,
        })

    all_deferred_must_verified = pending_count == 0

    return {
        "rows": rows,
        "all_deferred_must_verified": all_deferred_must_verified,
        "semantics": "latest_verdict",
        "pending": pending_count,
        "verified": verified_count,
    }


def handle_verify_human(root: Path, args: argparse.Namespace) -> StepResponse:
    plan_dir, state = load_plan(root, args.plan)

    list_flag = getattr(args, "list_flag", False)
    json_flag = getattr(args, "json_flag", False)

    # ── list mode ───────────────────────────────────────────────────────
    # Branch BEFORE the ``awaiting_human_verify`` state gate so listing
    # works for completed, stale, diagnostic, and awaiting plans.
    if list_flag:
        plan_meta = read_json(latest_plan_meta_path(plan_dir, state))
        hv_status = get_human_verification_status(plan_dir, plan_meta)
        rows = hv_status["rows"]

        if json_flag:
            # Machine-readable JSON output with latest_verdict semantics marker.
            return {
                "success": True,
                "step": "verify-human",
                "plan": state["name"],
                "pending": hv_status["pending"],
                "verified": hv_status["verified"],
                "rows": rows,
                "all_deferred_must_verified": hv_status["all_deferred_must_verified"],
                "semantics": "latest_verdict",
            }

        # Human-readable table in the style of ``megaplan run --list``.
        if not rows:
            return {
                "success": True,
                "step": "verify-human",
                "plan": state["name"],
                "summary": "No success criteria found for this plan.",
            }

        # Build a simple aligned table.
        col_widths = {
            "idx": max(4, max(len(str(r["criterion_idx"])) for r in rows)),
            "criterion": max(9, max(len(str(r.get("criterion", ""))) for r in rows)),
            "priority": max(8, max(len(str(r.get("priority", ""))) for r in rows)),
            "verdict": max(7, max(len(str(r.get("latest_verdict") or "-")) for r in rows)),
            "status": max(7, 7),
        }
        header = (
            f"{'Idx':>{col_widths['idx']}}  "
            f"{'Criterion':<{col_widths['criterion']}}  "
            f"{'Priority':<{col_widths['priority']}}  "
            f"{'Verdict':<{col_widths['verdict']}}  "
            f"{'Status'}"
        )
        sep = "  ".join("-" * w for w in col_widths.values())
        lines = [header, sep]
        for r in rows:
            verdict = r.get("latest_verdict") or "-"
            status = "verified" if r["verified"] else ("pending" if r["deferred_must"] else "deferred")
            lines.append(
                f"{r['criterion_idx']:>{col_widths['idx']}}  "
                f"{r.get('criterion', ''):<{col_widths['criterion']}}  "
                f"{r.get('priority', ''):<{col_widths['priority']}}  "
                f"{verdict:<{col_widths['verdict']}}  "
                f"{status}"
            )

        return {
            "success": True,
            "step": "verify-human",
            "plan": state["name"],
            "summary": (
                f"Verification status: {hv_status['verified']} verified, "
                f"{hv_status['pending']} pending. "
                + ("All deferred must criteria verified." if hv_status["all_deferred_must_verified"]
                   else f"{hv_status['pending']} deferred must criteria remaining.")
                + "\n\n" + "\n".join(lines)
            ),
        }

    # ── verdict recording mode ──────────────────────────────────────────
    if state["current_state"] != STATE_AWAITING_HUMAN_VERIFY:
        raise CliError(
            "wrong_state",
            f"verify-human requires state 'awaiting_human_verify', got '{state['current_state']}'.",
        )

    criterion_ref = args.criterion
    passed = getattr(args, "pass_flag", False)
    failed = getattr(args, "fail_flag", False)
    evidence = args.evidence

    if criterion_ref is None:
        raise CliError("missing_criterion", "Criterion is required when not using --list.")
    if not passed and not failed:
        raise CliError("missing_verdict", "--pass or --fail is required when not using --list.")
    if evidence is None:
        raise CliError("missing_evidence", "--evidence is required when not using --list.")

    plan_meta = read_json(latest_plan_meta_path(plan_dir, state))
    success_criteria = plan_meta.get("success_criteria", [])

    target_idx: int | None = None
    try:
        idx = int(criterion_ref)
        if 0 <= idx < len(success_criteria):
            target_idx = idx
    except (ValueError, TypeError):
        for i, sc in enumerate(success_criteria):
            if sc.get("criterion", "") == criterion_ref:
                target_idx = i
                break

    if target_idx is None:
        raise CliError("invalid_criterion", f"Criterion not found: {criterion_ref!r}")

    verifications_path = plan_dir / "human_verifications.json"
    verifications: list[dict[str, Any]] = []
    if verifications_path.exists():
        verifications = read_json(verifications_path)
        if not isinstance(verifications, list):
            verifications = []

    verifications.append({
        "criterion_idx": target_idx,
        "criterion": success_criteria[target_idx].get("criterion", ""),
        "verdict": "pass" if passed else "fail",
        "evidence": evidence,
        "timestamp": now_utc(),
    })
    atomic_write_json(verifications_path, verifications)

    # Use the shared helper with latest-verdict semantics.
    from arnold.pipelines.megaplan.audits.capabilities import get_worker_capabilities
    worker_caps = get_worker_capabilities(state)
    hv_status = get_human_verification_status(
        plan_dir, plan_meta, worker_caps=worker_caps
    )

    all_verified = hv_status["all_deferred_must_verified"]
    if all_verified:
        state["current_state"] = STATE_DONE
        # ``verify-human`` uses ``load_plan`` (no lock); merge meta to avoid
        # clobbering concurrent override appends.
        save_state_merge_meta(plan_dir, state)
        summary = "All deferred must criteria verified. Plan transitioned to done."
    else:
        summary = (
            f"Verification recorded. {hv_status['pending']} deferred must "
            f"criteria remaining."
        )

    return {
        "success": True,
        "step": "verify-human",
        "plan": state["name"],
        "state": state["current_state"],
        "summary": summary,
        "criterion_idx": target_idx,
        "verdict": "pass" if passed else "fail",
    }


def handle_audit_verifiability(root: Path, args: argparse.Namespace) -> StepResponse:
    plan_dir, state = load_plan(root, args.plan)

    plan_meta = read_json(latest_plan_meta_path(plan_dir, state))
    success_criteria = plan_meta.get("success_criteria", [])

    from arnold.pipelines.megaplan.audits.capabilities import get_worker_capabilities
    from arnold.pipelines.megaplan.orchestration.verifiability import audit_criteria, validate_requires

    worker_caps = get_worker_capabilities(state)
    audits = audit_criteria(success_criteria, worker_caps)
    issues = validate_requires(success_criteria)

    audit_results = []
    for audit in audits:
        sc = success_criteria[audit.criterion_idx] if audit.criterion_idx < len(success_criteria) else {}
        audit_results.append({
            "criterion_idx": audit.criterion_idx,
            "criterion": sc.get("criterion", ""),
            "priority": sc.get("priority", ""),
            "verdict": audit.verdict,
            "rationale": audit.rationale,
            "missing_caps": audit.missing_caps,
        })

    return {
        "success": True,
        "step": "audit-verifiability",
        "plan": state["name"],
        "summary": f"Audited {len(success_criteria)} criteria: {sum(1 for a in audits if a.verdict == 'machine_verifiable')} machine-verifiable, {sum(1 for a in audits if a.verdict == 'human_only')} human-only, {sum(1 for a in audits if a.verdict == 'unverifiable_no_worker')} unverifiable.",
        "audits": audit_results,
        "validation_issues": issues,
    }
