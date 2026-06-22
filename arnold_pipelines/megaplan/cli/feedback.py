from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.types import CliError, StepResponse
from arnold_pipelines.megaplan.planning.state import STATE_DONE, STATE_REVIEWED
from arnold_pipelines.megaplan._core import active_plan_dirs, load_plan, save_state
from arnold_pipelines.megaplan.orchestration.phase_result import ExitKind, _emit_phase_result
from .roots import _collect_megaplan_roots


def _build_epic_store(root: Path, *, actor_id: str | None = None):
    from arnold_pipelines.megaplan.store import MultiStore

    return MultiStore.for_project(root, actor_id=actor_id)


build_epic_store = _build_epic_store

def _collect_feedback_rows(
    root: Path,
    *,
    all_system: bool = False,
    include_db: bool = True,
) -> list[dict[str, Any]]:
    """Gather feedback rows from file-mode plan trees and (optionally) the DB.

    Each row is a dict with: ``plan``, ``profile``, ``repo``, ``state``,
    ``backend`` (``file`` or ``db``), ``feedback_path`` (file mode only),
    ``feedback`` (parsed dict from PlanFeedback.to_dict), ``plan_id`` (DB only).
    Duplicates between file and DB are de-duped by (plan name, repo).
    """

    from arnold_pipelines.megaplan._core.io import read_json
    from arnold_pipelines.megaplan.orchestration.feedback import feedback_path, load_feedback

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    # --- File backend: walk known megaplan project roots and read feedback.md
    for search_root in _collect_megaplan_roots(
        root, tree=not all_system, all_system=all_system
    ):
        for plan_dir in active_plan_dirs(search_root):
            fb = load_feedback(plan_dir)
            if fb is None or fb.is_empty():
                continue
            try:
                # cache-tolerant: feedback CLI scan.
                state = read_json(plan_dir / "state.json")
            except (FileNotFoundError, OSError):
                continue
            config = state.get("config") or {}
            profile = config.get("profile") if isinstance(config, dict) else None
            repo = config.get("project_dir") if isinstance(config, dict) else None
            key = (state.get("name", plan_dir.name), str(repo or search_root))
            seen.add(key)
            rows.append(
                {
                    "plan": state.get("name", plan_dir.name),
                    "profile": profile,
                    "repo": repo or str(search_root),
                    "state": state.get("current_state"),
                    "backend": "file",
                    "feedback_path": str(feedback_path(plan_dir)),
                    "feedback": fb.to_dict(),
                }
            )

    # --- DB backend: if an actor is configured, pull rows with non-empty feedback
    if include_db and (
        os.environ.get("MEGAPLAN_ACTOR_ID")
        or getattr(_collect_feedback_rows, "_actor_override", None)
    ):
        actor_id = (
            getattr(_collect_feedback_rows, "_actor_override", None)
            or os.environ["MEGAPLAN_ACTOR_ID"]
        )
        try:
            store = build_epic_store(root, actor_id=actor_id)
        except Exception:
            store = None
        if store is not None:
            try:
                for plan in store.list_plans(include_orphans=True):
                    fb_dict = getattr(plan, "feedback", None)
                    if not fb_dict:
                        continue
                    config = plan.config or {}
                    profile = (
                        config.get("profile") if isinstance(config, dict) else None
                    )
                    repo = (
                        config.get("project_dir") if isinstance(config, dict) else None
                    )
                    key = (plan.name, str(repo or ""))
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(
                        {
                            "plan": plan.name,
                            "profile": profile,
                            "repo": repo,
                            "state": plan.current_state,
                            "backend": "db",
                            "plan_id": plan.id,
                            "feedback": fb_dict,
                        }
                    )
            finally:
                close = getattr(store, "close", None)
                if callable(close):
                    close()
    return rows


def _filter_feedback_rows(
    rows: list[dict[str, Any]], args: argparse.Namespace
) -> list[dict[str, Any]]:
    profile = (getattr(args, "profile", None) or "").lower() or None
    repo = (getattr(args, "repo", None) or "").lower() or None
    min_rating = getattr(args, "min_rating", None)
    max_rating = getattr(args, "max_rating", None)
    stage = (getattr(args, "stage", None) or "").lower() or None
    has_comment = getattr(args, "has_comment", False)

    def _keep(row: dict[str, Any]) -> bool:
        if profile and profile not in (str(row.get("profile") or "")).lower():
            return False
        if repo and repo not in (str(row.get("repo") or "")).lower():
            return False
        fb = row.get("feedback") or {}
        overall = fb.get("overall") or {}
        rating = overall.get("rating")
        if rating is None:
            rating = overall.get("ai_rating")
        if min_rating is not None and (rating is None or rating < min_rating):
            return False
        if max_rating is not None and (rating is None or rating > max_rating):
            return False
        if has_comment:
            comment = (overall.get("comment") or "").strip() or (
                overall.get("ai_comment") or ""
            ).strip()
            if not comment:
                return False
        if stage:
            stage_entry = (fb.get("stages") or {}).get(stage)
            if not stage_entry:
                return False
            stage_rating = stage_entry.get("rating")
            if stage_rating is None:
                stage_rating = stage_entry.get("ai_rating")
            if stage_rating is None:
                return False
        return True

    return [r for r in rows if _keep(r)]


def _render_feedback_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(no matches)"
    lines: list[str] = []
    header = f"{'PLAN':<28} {'PROFILE':<14} {'OVR':>4}  {'BK':<4} REPO"
    lines.append(header)
    lines.append("-" * len(header))
    for row in rows:
        fb = row.get("feedback") or {}
        overall = fb.get("overall") or {}
        rating = overall.get("rating")
        ai_only = rating is None
        if rating is None:
            rating = overall.get("ai_rating")
        if rating is None:
            rating_s = "—"
        else:
            rating_s = f"{rating}/10 (AI)" if ai_only else f"{rating}/10"
        repo = str(row.get("repo") or "")
        if len(repo) > 40:
            repo = "…" + repo[-39:]
        lines.append(
            f"{(row.get('plan') or '')[:28]:<28} "
            f"{(row.get('profile') or '—')[:14]:<14} "
            f"{rating_s:>4}  "
            f"{(row.get('backend') or '?'):<4} {repo}"
        )
        user_comment = (overall.get("comment") or "").strip()
        ai_comment = (overall.get("ai_comment") or "").strip()
        if user_comment:
            comment = user_comment
            comment_prefix = ""
        elif ai_comment:
            comment = ai_comment
            comment_prefix = "(AI) "
        else:
            comment = ""
            comment_prefix = ""
        if comment:
            first_line = comment_prefix + comment.splitlines()[0]
            if len(first_line) > 70:
                first_line = first_line[:67] + "…"
            lines.append(f"  └ {first_line}")
    return "\n".join(lines) + "\n"


def _parse_ai_feedback(payload: Any, raw_output: str) -> Any:
    """Coerce a worker payload (preferred) or raw JSON output into a PlanFeedback.

    Returns None when neither source yields a parseable feedback structure.
    Reads ``overall.rating/comment`` and ``stages.<name>.rating/comment``.
    """
    from arnold_pipelines.megaplan.orchestration.feedback import PlanFeedback, StageFeedback

    data: Any = payload if isinstance(payload, dict) and payload else None
    if data is None:
        try:
            data = json.loads(raw_output)
        except (TypeError, ValueError):
            return None
    if not isinstance(data, dict):
        return None
    overall = data.get("overall")
    stages = data.get("stages") or {}
    if not isinstance(overall, dict) or not isinstance(stages, dict):
        return None

    def _coerce_rating(v: Any) -> int | None:
        if isinstance(v, bool):
            return None
        if isinstance(v, int) and 0 <= v <= 10:
            return v
        return None

    def _coerce_comment(v: Any) -> str | None:
        if isinstance(v, str) and v.strip():
            return v.strip()
        return None

    fb = PlanFeedback()
    fb.overall = StageFeedback(
        ai_rating=_coerce_rating(overall.get("rating")),
        ai_comment=_coerce_comment(overall.get("comment")),
    )
    for stage_name, entry in stages.items():
        if not isinstance(stage_name, str) or not isinstance(entry, dict):
            continue
        fb.stages[stage_name.lower()] = StageFeedback(
            ai_rating=_coerce_rating(entry.get("rating")),
            ai_comment=_coerce_comment(entry.get("comment")),
        )
    return fb if not fb.is_empty() else None


def _merge_feedback(existing: Any, ai_fb: Any) -> Any:
    """Return a PlanFeedback with user fields from ``existing`` and ai_* from ``ai_fb``.

    Either or both may be None. User ``rating`` / ``comment`` always win; AI
    fields are taken from ``ai_fb`` when present, else fall back to existing.
    """
    from arnold_pipelines.megaplan.orchestration.feedback import PlanFeedback, StageFeedback

    merged = PlanFeedback()

    def _merge_stage(
        user_sf: StageFeedback | None, ai_sf: StageFeedback | None
    ) -> StageFeedback:
        rating = user_sf.rating if user_sf else None
        comment = user_sf.comment if user_sf else None
        if ai_sf is not None and ai_sf.ai_rating is not None:
            ai_rating = ai_sf.ai_rating
        elif user_sf is not None:
            ai_rating = user_sf.ai_rating
        else:
            ai_rating = None
        if ai_sf is not None and ai_sf.ai_comment:
            ai_comment = ai_sf.ai_comment
        elif user_sf is not None:
            ai_comment = user_sf.ai_comment
        else:
            ai_comment = None
        return StageFeedback(
            rating=rating,
            comment=comment,
            ai_rating=ai_rating,
            ai_comment=ai_comment,
        )

    user_overall = existing.overall if existing else None
    ai_overall = ai_fb.overall if ai_fb else None
    merged.overall = _merge_stage(user_overall, ai_overall)

    stage_names: set[str] = set()
    if existing:
        stage_names.update(existing.stages.keys())
    if ai_fb:
        stage_names.update(ai_fb.stages.keys())
    for name in stage_names:
        merged.stages[name] = _merge_stage(
            existing.stages.get(name) if existing else None,
            ai_fb.stages.get(name) if ai_fb else None,
        )
    return merged


def _push_feedback_to_db(
    root: Path, *, plan_name: str, feedback_dict: dict[str, Any]
) -> dict[str, Any]:
    """Push a parsed feedback dict to the DB plan row, if a DB actor is configured.

    Returns a small status dict describing what happened. A missing actor or
    missing DB row is a soft skip — file-mode users shouldn't need a DB at all.
    """

    actor_id = getattr(_push_feedback_to_db, "_actor_override", None) or os.environ.get(
        "MEGAPLAN_ACTOR_ID"
    )
    if not actor_id:
        return {"db_synced": False, "reason": "no actor configured"}
    store = build_epic_store(root, actor_id=actor_id)
    try:
        match = next(
            (p for p in store.list_plans(include_orphans=True) if p.name == plan_name),
            None,
        )
        if match is None:
            return {"db_synced": False, "reason": f"no DB plan named {plan_name!r}"}
        store.update_plan(
            match.id, expected_revision=match.revision, feedback=feedback_dict
        )
        return {"db_synced": True, "plan_id": match.id}
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


def handle_feedback(root: Path, args: argparse.Namespace) -> StepResponse:
    """Scaffold, edit, or display ``feedback.md`` for a plan.

    The local ``feedback.md`` is always the editor surface. If a DB actor is
    configured (``--actor`` or ``MEGAPLAN_ACTOR_ID``), parsed feedback is also
    pushed to the ``plans.feedback`` column so backends stay in sync.
    """

    import subprocess

    from arnold_pipelines.megaplan._core.io import atomic_write_text
    from arnold_pipelines.megaplan.orchestration.feedback import (
        FEEDBACK_FILENAME,
        PlanFeedback,
        feedback_path,
        format_summary,
        load_feedback,
        render_template,
    )

    actor_override = getattr(args, "actor", None)
    if actor_override:
        _push_feedback_to_db._actor_override = actor_override  # type: ignore[attr-defined]
        _collect_feedback_rows._actor_override = actor_override  # type: ignore[attr-defined]

    operation = getattr(args, "operation", "edit")

    # --- search: scan plans across backends, apply filters, render
    if operation == "search":
        rows = _collect_feedback_rows(root, all_system=getattr(args, "all", False))
        filtered = _filter_feedback_rows(rows, args)
        if getattr(args, "emit_json", False):
            return {
                "success": True,
                "step": "feedback",
                "operation": "search",
                "count": len(filtered),
                "scanned": len(rows),
                "rows": filtered,
            }
        return {
            "success": True,
            "step": "feedback",
            "operation": "search",
            "count": len(filtered),
            "scanned": len(rows),
            "rows": filtered,
            "summary": (
                f"{len(filtered)} of {len(rows)} plans with feedback match.\n\n"
                + _render_feedback_table(filtered)
            ),
        }

    # edit / show both require --plan
    if not getattr(args, "plan", None):
        raise CliError(
            "invalid_args", "feedback edit/show/workflow require --plan <name>"
        )

    plan_dir, state = load_plan(root, args.plan)
    path = feedback_path(plan_dir)

    # --- workflow: AI-rated feedback for the auto-driver
    if operation == "workflow":
        current_state = state.get("current_state")
        if current_state != STATE_REVIEWED:
            raise CliError(
                "invalid_state",
                f"feedback workflow requires plan in {STATE_REVIEWED!r} state, "
                f"but plan is in {current_state!r}",
            )

        existing_fb: PlanFeedback | None = (
            load_feedback(plan_dir) if path.exists() else None
        )
        force = bool(getattr(args, "force", False))

        def _has_user_fields(fb: PlanFeedback | None) -> bool:
            if fb is None:
                return False
            if fb.overall.rating is not None or (fb.overall.comment or "").strip():
                return True
            for sf in fb.stages.values():
                if sf.rating is not None or (sf.comment or "").strip():
                    return True
            return False

        if _has_user_fields(existing_fb) and not force:
            state["current_state"] = STATE_DONE
            save_state(plan_dir, state)
            _emit_phase_result(
                "feedback",
                state,
                plan_dir,
                exit_kind=ExitKind.success.value,
                artifacts_written=(str(path),),
            )
            return {
                "success": True,
                "step": "feedback",
                "operation": "workflow",
                "plan": state["name"],
                "plan_dir": str(plan_dir),
                "feedback_path": str(path),
                "feedback_present": True,
                "ai_filled": False,
                "state": "done",
                "summary": "skipped AI pass — user feedback already exists",
            }

        ai_filled = False
        ai_fb: PlanFeedback | None = None
        try:
            from arnold_pipelines.megaplan.handlers.shared import _run_worker

            worker, _agent, _mode, _refreshed = _run_worker(
                "feedback", state, plan_dir, args, root=root
            )
            ai_fb = _parse_ai_feedback(worker.payload, worker.raw_output)
            ai_filled = ai_fb is not None
        except (
            Exception
        ) as exc:  # noqa: BLE001 — feedback failure must not sink the plan
            sys.stderr.write(
                f"[feedback] worker failed, scaffolding empty template: {exc}\n"
            )

        merged = _merge_feedback(existing_fb, ai_fb)
        template = render_template(
            state["name"], idea=state.get("idea"), prefilled=merged
        )
        atomic_write_text(path, template)

        state["current_state"] = STATE_DONE
        save_state(plan_dir, state)
        _emit_phase_result(
            "feedback",
            state,
            plan_dir,
            exit_kind=ExitKind.success.value,
            artifacts_written=(str(path),),
        )

        return {
            "success": True,
            "step": "feedback",
            "operation": "workflow",
            "plan": state["name"],
            "plan_dir": str(plan_dir),
            "feedback_path": str(path),
            "feedback_present": True,
            "ai_filled": ai_filled,
            "state": "done",
            "summary": (
                "populated AI ratings — review and edit anytime"
                if ai_filled
                else "scaffolded feedback.md — fill in whenever"
            ),
        }

    if operation == "show":
        fb = load_feedback(plan_dir)
        if fb is None:
            return {
                "success": True,
                "step": "feedback",
                "plan": state["name"],
                "plan_dir": str(plan_dir),
                "feedback_path": str(path),
                "feedback_present": False,
                "summary": f"No {FEEDBACK_FILENAME} for this plan yet.",
            }
        return {
            "success": True,
            "step": "feedback",
            "plan": state["name"],
            "plan_dir": str(plan_dir),
            "feedback_path": str(path),
            "feedback_present": True,
            "summary": format_summary(fb),
            "feedback": fb.to_dict(),
        }

    created = False
    if not path.exists():
        template = render_template(state["name"], idea=state.get("idea"))
        atomic_write_text(path, template)
        created = True

    opened = False
    if not getattr(args, "no_edit", False):
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
        if editor:
            try:
                subprocess.run([*editor.split(), str(path)], check=False)
                opened = True
            except (FileNotFoundError, OSError):
                opened = False

    fb = load_feedback(plan_dir)
    db_status = {"db_synced": False, "reason": "no edits to push"}
    if fb is not None and not fb.is_empty():
        try:
            db_status = _push_feedback_to_db(
                root, plan_name=state["name"], feedback_dict=fb.to_dict()
            )
        except (
            Exception
        ) as exc:  # noqa: BLE001 — surface failure but don't break editor flow
            db_status = {"db_synced": False, "reason": f"db push failed: {exc}"}

    msg_parts: list[str] = []
    msg_parts.append("Created" if created else "Found existing")
    msg_parts.append(FEEDBACK_FILENAME)
    if opened:
        msg_parts.append("(opened in $EDITOR)")
    if db_status.get("db_synced"):
        msg_parts.append("→ synced to DB")
    return {
        "success": True,
        "step": "feedback",
        "plan": state["name"],
        "plan_dir": str(plan_dir),
        "feedback_path": str(path),
        "feedback_present": path.exists(),
        "created": created,
        "opened_in_editor": opened,
        "db_status": db_status,
        "summary": f"{' '.join(msg_parts)} at {path}",
    }
