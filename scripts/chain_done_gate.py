from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml


BLOCKING_COMPLETION_MODES = {"off", "shadow", "warn"}
BLOCKING_BACKSTOP_MODES = {"off", "shadow"}
RESOLVED_BLOCKER_STATUSES = {"resolved", "accepted", "closed", "done"}


def _chain_state_path_for(spec_path: Path) -> Path:
    resolved = spec_path.resolve(strict=False)
    digest = hashlib.sha1(str(resolved).encode("utf-8")).hexdigest()[:12]
    return (
        resolved.parent
        / ".megaplan"
        / "plans"
        / ".chains"
        / f"{resolved.stem}-{digest}.json"
    )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"missing file: {path}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return raw


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"missing file: {path}") from None
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return raw


def _milestone_labels(spec: dict[str, Any]) -> list[str]:
    milestones = spec.get("milestones")
    if not isinstance(milestones, list):
        raise ValueError("chain spec must contain a milestones list")
    labels: list[str] = []
    for index, milestone in enumerate(milestones):
        if not isinstance(milestone, dict) or not isinstance(milestone.get("label"), str):
            raise ValueError(f"milestones[{index}] must contain a string label")
        labels.append(milestone["label"])
    return labels


def _plans_root_candidates(
    *, root: Path, state: dict[str, Any], explicit: Path | None
) -> list[Path]:
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit)
    candidates.append(root / ".megaplan" / "plans")

    resolved_workspace = state.get("resolved_workspace")
    if isinstance(resolved_workspace, str) and resolved_workspace:
        candidates.append(Path(resolved_workspace) / ".megaplan" / "plans")

    metadata = state.get("metadata")
    if isinstance(metadata, dict):
        env = metadata.get("execution_environment")
        if isinstance(env, dict):
            for key in ("target_root", "project_root", "work_dir"):
                value = env.get(key)
                if isinstance(value, str) and value:
                    candidates.append(Path(value) / ".megaplan" / "plans")

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        marker = str(candidate.resolve(strict=False))
        if marker not in seen:
            seen.add(marker)
            deduped.append(candidate)
    return deduped


def _read_plan_state(plan_name: str, plans_roots: list[Path]) -> tuple[Path | None, dict[str, Any] | None]:
    for plans_root in plans_roots:
        state_path = plans_root / plan_name / "state.json"
        if not state_path.exists():
            continue
        return state_path, _load_json(state_path)
    return None, None


def _open_blockers(blockers_path: Path | None) -> list[str]:
    if blockers_path is None:
        return []
    data = _load_json(blockers_path)
    raw_blockers = data.get("blockers", [])
    if not isinstance(raw_blockers, list):
        raise ValueError(f"{blockers_path}: blockers must be a list")
    errors: list[str] = []
    for index, blocker in enumerate(raw_blockers):
        if not isinstance(blocker, dict):
            errors.append(f"blockers[{index}] is not an object")
            continue
        status = blocker.get("status", "open")
        if not isinstance(status, str) or status.lower() not in RESOLVED_BLOCKER_STATUSES:
            blocker_id = blocker.get("id", f"blockers[{index}]")
            source = blocker.get("source", "unknown source")
            title = blocker.get("title", "untitled blocker")
            errors.append(
                f"unresolved blocker {blocker_id!r}: {title} ({source}); status={status!r}"
            )
    return errors


def check_chain_done(
    *,
    spec_path: Path,
    state_path: Path | None = None,
    plans_root: Path | None = None,
    blockers_path: Path | None = None,
) -> list[str]:
    spec = _load_yaml(spec_path)
    state = _load_json(state_path or _chain_state_path_for(spec_path))
    root = spec_path.resolve(strict=False).parent
    errors: list[str] = []

    completion_mode = str(state.get("completion_contract_mode", "shadow"))
    if completion_mode in BLOCKING_COMPLETION_MODES:
        errors.append(
            "completion_contract_mode must be enforce before chain completion "
            f"can be accepted; got {completion_mode!r}"
        )
    backstop_mode = str(state.get("full_suite_backstop_mode", "shadow"))
    if backstop_mode in BLOCKING_BACKSTOP_MODES:
        errors.append(
            "full_suite_backstop_mode must be enforce before chain completion "
            f"can be accepted; got {backstop_mode!r}"
        )

    completed_raw = state.get("completed")
    if not isinstance(completed_raw, list):
        errors.append("chain state completed field must be a list")
        completed_raw = []
    completed: dict[str, dict[str, Any]] = {}
    for entry in completed_raw:
        if isinstance(entry, dict) and isinstance(entry.get("label"), str):
            completed[entry["label"]] = entry

    plans_roots = _plans_root_candidates(root=root, state=state, explicit=plans_root)
    for label in _milestone_labels(spec):
        record = completed.get(label)
        if record is None:
            errors.append(f"milestone {label!r} is not recorded in chain_state.completed")
            continue
        if record.get("status") != "done":
            errors.append(
                f"milestone {label!r} completed status must be 'done'; got {record.get('status')!r}"
            )
        plan_name = record.get("plan")
        if not isinstance(plan_name, str) or not plan_name:
            errors.append(f"milestone {label!r} completed record has no plan name")
            continue
        state_file, plan_state = _read_plan_state(plan_name, plans_roots)
        if plan_state is None:
            roots = ", ".join(str(path) for path in plans_roots)
            errors.append(
                f"milestone {label!r} plan {plan_name!r} has no readable state.json "
                f"under any plans root: {roots}"
            )
            continue
        current_state = plan_state.get("current_state")
        if current_state != "done":
            errors.append(
                f"milestone {label!r} plan {plan_name!r} has current_state={current_state!r} "
                f"in {state_file}; expected 'done'"
            )

    errors.extend(_open_blockers(blockers_path))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fail a chain completion if any milestone's plan state is not done, "
            "if chain backstops are non-blocking, or if review blockers remain open."
        )
    )
    parser.add_argument("--spec", type=Path, help="Path to chain.yaml")
    parser.add_argument("--state", type=Path, help="Path to the persisted chain state JSON")
    parser.add_argument(
        "--plans-root",
        type=Path,
        help="Override .megaplan/plans root used to find per-milestone state.json files",
    )
    parser.add_argument(
        "--blockers",
        type=Path,
        help="Optional JSON blocker checklist; any non-resolved blocker fails the gate",
    )
    parser.add_argument(
        "--blockers-only",
        action="store_true",
        help="Only evaluate the selected blocker checklist; requires --blockers",
    )
    args = parser.parse_args(argv)

    try:
        if args.blockers_only:
            if args.blockers is None:
                parser.error("--blockers-only requires --blockers")
            if args.spec is not None or args.state is not None or args.plans_root is not None:
                parser.error("--blockers-only cannot be combined with --spec, --state, or --plans-root")
            errors = _open_blockers(args.blockers)
        else:
            if args.spec is None:
                parser.error("--spec is required unless --blockers-only is used")
            errors = check_chain_done(
                spec_path=args.spec,
                state_path=args.state,
                plans_root=args.plans_root,
                blockers_path=args.blockers,
            )
    except ValueError as exc:
        print(f"chain done gate failed: {exc}", file=sys.stderr)
        return 2

    if errors:
        for error in errors:
            print(f"chain done gate failed: {error}", file=sys.stderr)
        return 1
    print("chain done gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
