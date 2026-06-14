#!/usr/bin/env python3
"""adopt_plan.py — Adopt a pre-built FINALIZED megaplan plan into a chain run.

idempotent, resumable surgery: injects a fully-planned-and-finalized plan
directory into a chain so the chain RESUMES IT AT EXECUTE instead of
planning that milestone fresh.

Usage:
    python3 adopt_plan.py \
        --project-dir <DIR> \
        --spec <chain.yaml> \
        --milestone <label> \
        --from-plan-dir <SRC_FINALIZED_PLAN_DIR> \
        [--dry-run]

Mechanism:
1. Resolve milestone index from the spec's milestones[] list (match by label).
2. Refuse if milestone label is already in chain-state completed[].
3. Copy the source finalized plan dir into <project>/.megaplan/plans/<plan-name>.
4. Patch the copied plan's state.json: current_state='finalized', clear failures,
   clear stale active worker metadata, and bind config.project_dir to the target
   project.
5. Patch chain-state JSON: current_milestone_index → resolved index,
   current_plan_name → adopted plan name, last_state → null,
   retry_counts[<label>] → 0.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    sys.exit(
        "PyYAML is required. Install with: pip install pyyaml"
    )


# ---------------------------------------------------------------------------
# Helpers (inline copies, no dependency on megaplan internals)
# ---------------------------------------------------------------------------

def _compute_chain_state_path(spec_path: Path) -> Path:
    """Compute the chain-state JSON path from the resolved spec path.

    Mirrors megaplan.chain._state_path_for exactly:
        sha1(resolved_spec_path) → first 12 hex chars
        → .megaplan/plans/.chains/<stem>-<digest>.json
    """
    spec_resolved = spec_path.resolve()
    digest = hashlib.sha1(str(spec_resolved).encode("utf-8")).hexdigest()[:12]
    return (
        spec_resolved.parent
        / ".megaplan"
        / "plans"
        / ".chains"
        / f"{spec_resolved.stem}-{digest}.json"
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file, returning an empty dict on missing file."""
    if not path.exists():
        raise FileNotFoundError(f"spec file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"spec file {path} must be a YAML mapping")
    return data


def _load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file, returning an empty dict on missing file."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a JSON object")
    return data


def _save_json(path: Path, data: dict[str, Any]) -> None:
    """Atomically save JSON to path (write tmp, rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    tmp.replace(path)


def _find_milestone(spec: dict[str, Any], label: str) -> tuple[int, dict[str, Any]]:
    """Find milestone by label in spec['milestones'].

    Returns (index, milestone_dict). Raises ValueError if not found.
    """
    milestones: list[dict[str, Any]] = spec.get("milestones") or []
    if not isinstance(milestones, list):
        raise ValueError("spec 'milestones' must be a list")

    for idx, m in enumerate(milestones):
        if isinstance(m, dict) and m.get("label") == label:
            return idx, m

    available = [
        m["label"] for m in milestones if isinstance(m, dict) and "label" in m
    ]
    raise ValueError(
        f"milestone '{label}' not found in spec milestones. "
        f"Available: {available}"
    )


def _check_not_completed(chain_state: dict[str, Any], label: str) -> None:
    """Raise SystemExit if label is already in completed[]."""
    completed: list[dict[str, Any]] = chain_state.get("completed") or []
    for entry in completed:
        if isinstance(entry, dict) and entry.get("label") == label:
            sys.exit(
                f"ERROR: milestone '{label}' is already in chain-state completed[] "
                f"(plan={entry.get('plan')!r}, status={entry.get('status')!r}). "
                "Refusing to adopt over a completed milestone."
            )


def _resolve_plan_name(from_plan_dir: Path) -> str:
    """Extract plan name from the source plan directory name."""
    return from_plan_dir.resolve().name


def _target_plan_path(project_dir: Path, plan_name: str) -> Path:
    """Return the target path for the adopted plan in the project."""
    return project_dir / ".megaplan" / "plans" / plan_name


def _rewrite_premium_vendor(spec: Any, vendor: str) -> Any:
    """Rewrite claude:/codex: premium specs to the chain-selected vendor."""
    if vendor not in {"claude", "codex"}:
        return spec
    if isinstance(spec, str):
        if "=" in spec:
            phase, value = spec.split("=", 1)
            return f"{phase}={_rewrite_premium_vendor(value, vendor)}"
        for premium in ("claude", "codex"):
            if spec == premium:
                return vendor
            if spec.startswith(f"{premium}:"):
                return f"{vendor}:{spec.split(':', 1)[1]}"
        return spec
    if isinstance(spec, list):
        return [_rewrite_premium_vendor(item, vendor) for item in spec]
    if isinstance(spec, dict):
        return {key: _rewrite_premium_vendor(value, vendor) for key, value in spec.items()}
    return spec


def _patch_config_from_milestone(
    config: dict[str, Any],
    milestone: dict[str, Any],
) -> dict[str, Any]:
    """Apply chain milestone knobs to a copied finalized plan config."""
    for key in ("profile", "robustness", "depth", "vendor", "deepseek_provider"):
        value = milestone.get(key)
        if value is not None:
            config[key] = value
    vendor = config.get("vendor")
    if isinstance(vendor, str):
        for key in ("agent", "phase_model", "tier_models"):
            if key in config:
                config[key] = _rewrite_premium_vendor(config[key], vendor)
    return config


# ---------------------------------------------------------------------------
# Core adoption logic
# ---------------------------------------------------------------------------

def adopt(
    project_dir: Path,
    spec_path: Path,
    milestone_label: str,
    from_plan_dir: Path,
    *,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Execute or dry-run the adoption.

    Returns a list of change descriptions (for reporting).
    """
    changes: list[dict[str, Any]] = []

    # 1. Load spec + resolve milestone index
    spec = _load_yaml(spec_path)
    milestone_idx, milestone = _find_milestone(spec, milestone_label)

    changes.append({
        "action": "resolve_milestone",
        "label": milestone_label,
        "index": milestone_idx,
    })

    # 2. Load chain-state
    chain_state_path = _compute_chain_state_path(spec_path)
    chain_state = _load_json(chain_state_path)

    changes.append({
        "action": "load_chain_state",
        "path": str(chain_state_path),
        "exists": chain_state_path.exists(),
    })

    # 3. Refuse if already completed
    _check_not_completed(chain_state, milestone_label)

    changes.append({
        "action": "check_completed",
        "label": milestone_label,
        "already_completed": False,
    })

    # 4. Resolve plan name + target path
    plan_name = _resolve_plan_name(from_plan_dir)
    target_plan_dir = _target_plan_path(project_dir, plan_name)

    changes.append({
        "action": "resolve_plan_name",
        "plan_name": plan_name,
        "source": str(from_plan_dir),
        "target": str(target_plan_dir),
    })

    # 5. Validate source plan exists and has state.json
    if not from_plan_dir.exists():
        sys.exit(f"ERROR: source plan directory not found: {from_plan_dir}")
    if not (from_plan_dir / "state.json").exists():
        sys.exit(
            f"ERROR: source plan directory has no state.json: {from_plan_dir}"
        )

    source_state = _load_json(from_plan_dir / "state.json")
    source_current = source_state.get("current_state", "(missing)")

    changes.append({
        "action": "validate_source",
        "path": str(from_plan_dir),
        "current_state_before": source_current,
    })

    # 6. Copy (or idempotent re-copy) plan directory
    if dry_run:
        changes.append({
            "action": "copy_plan_dir",
            "source": str(from_plan_dir),
            "target": str(target_plan_dir),
            "dry_run": True,
        })
    else:
        if target_plan_dir.resolve() == from_plan_dir.resolve():
            # Source is already at target — nothing to copy
            changes.append({
                "action": "copy_plan_dir",
                "source": str(from_plan_dir),
                "target": str(target_plan_dir),
                "note": "source is already at target; skipping copy",
            })
        else:
            if target_plan_dir.exists():
                shutil.rmtree(target_plan_dir)
                changes.append({
                    "action": "remove_existing_target",
                    "path": str(target_plan_dir),
                })
            shutil.copytree(from_plan_dir, target_plan_dir)
            changes.append({
                "action": "copy_plan_dir",
                "source": str(from_plan_dir),
                "target": str(target_plan_dir),
            })

    # 7. Patch the copied plan's state.json
    target_state_path = target_plan_dir / "state.json"
    if not dry_run:
        plan_state = _load_json(target_state_path)
        plan_state_before_current = plan_state.get("current_state")
        plan_state_before_latest_failure = plan_state.get("latest_failure")
        plan_state_before_last_failure = plan_state.get("last_failure")
        plan_state_before_project_dir = (
            plan_state.get("config", {}).get("project_dir")
            if isinstance(plan_state.get("config"), dict)
            else None
        )
        plan_state_before_vendor = (
            plan_state.get("config", {}).get("vendor")
            if isinstance(plan_state.get("config"), dict)
            else None
        )
        plan_state_before_active_step = plan_state.get("active_step")

        plan_state["current_state"] = "finalized"
        plan_state["latest_failure"] = None
        plan_state["last_failure"] = None
        plan_state.pop("active_step", None)
        config = plan_state.get("config")
        if not isinstance(config, dict):
            config = {}
            plan_state["config"] = config
        config["project_dir"] = str(project_dir)
        patched_config = _patch_config_from_milestone(config, milestone)
        _save_json(target_state_path, plan_state)

        changes.append({
            "action": "patch_plan_state",
            "path": str(target_state_path),
            "current_state": {
                "before": plan_state_before_current,
                "after": "finalized",
            },
            "latest_failure": {
                "before": plan_state_before_latest_failure,
                "after": None,
            },
            "last_failure": {
                "before": plan_state_before_last_failure,
                "after": None,
            },
            "active_step": {
                "before": plan_state_before_active_step,
                "after": None,
            },
            "config.project_dir": {
                "before": plan_state_before_project_dir,
                "after": str(project_dir),
            },
            "config.vendor": {
                "before": plan_state_before_vendor,
                "after": patched_config.get("vendor"),
            },
        })
    else:
        source_config = source_state.get("config")
        source_project_dir = (
            source_config.get("project_dir")
            if isinstance(source_config, dict)
            else None
        )
        source_vendor = (
            source_config.get("vendor")
            if isinstance(source_config, dict)
            else None
        )
        changes.append({
            "action": "patch_plan_state",
            "path": str(target_state_path),
            "current_state": {"before": "(source)", "after": "finalized"},
            "latest_failure": {"before": "(source)", "after": None},
            "last_failure": {"before": "(source)", "after": None},
            "active_step": {"before": source_state.get("active_step"), "after": None},
            "config.project_dir": {
                "before": source_project_dir,
                "after": str(project_dir),
            },
            "config.vendor": {
                "before": source_vendor,
                "after": milestone.get("vendor", source_vendor),
            },
            "dry_run": True,
        })

    # 8. Patch the chain-state JSON
    chain_before_index = chain_state.get("current_milestone_index")
    chain_before_plan = chain_state.get("current_plan_name")
    chain_before_last = chain_state.get("last_state")
    chain_before_retries = chain_state.get("retry_counts", {}).get(milestone_label)

    if not dry_run:
        chain_state["current_milestone_index"] = milestone_idx
        chain_state["current_plan_name"] = plan_name
        chain_state["last_state"] = None

        retry_counts = chain_state.get("retry_counts")
        if not isinstance(retry_counts, dict):
            retry_counts = {}
            chain_state["retry_counts"] = retry_counts
        retry_counts[milestone_label] = 0

        _save_json(chain_state_path, chain_state)

    changes.append({
        "action": "patch_chain_state",
        "path": str(chain_state_path),
        "current_milestone_index": {
            "before": chain_before_index,
            "after": milestone_idx,
        },
        "current_plan_name": {
            "before": chain_before_plan,
            "after": plan_name,
        },
        "last_state": {
            "before": chain_before_last,
            "after": None,
        },
        "retry_counts": {
            "before": {
                milestone_label: chain_before_retries,
            },
            "after": {
                milestone_label: 0,
            },
        },
        "dry_run": dry_run,
    })

    return changes


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Adopt a pre-built FINALIZED plan into a chain run at EXECUTE",
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        type=Path,
        help="Path to the project root (e.g. /Users/peteromalley/Documents/megaplan)",
    )
    parser.add_argument(
        "--spec",
        required=True,
        type=Path,
        help="Path to the chain spec YAML (e.g. chain.yaml)",
    )
    parser.add_argument(
        "--milestone",
        required=True,
        type=str,
        help="Milestone label to adopt (e.g. m5a-node-library)",
    )
    parser.add_argument(
        "--from-plan-dir",
        required=True,
        type=Path,
        help="Path to the source finalized plan directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned mutations without making changes",
    )

    args = parser.parse_args()

    # Resolve paths
    project_dir = args.project_dir.resolve()
    spec_path = args.spec.resolve()
    from_plan_dir = args.from_plan_dir.resolve()

    if not project_dir.is_dir():
        sys.exit(f"ERROR: project directory not found: {project_dir}")
    if not spec_path.is_file():
        sys.exit(f"ERROR: spec file not found: {spec_path}")
    if not from_plan_dir.is_dir():
        sys.exit(f"ERROR: source plan directory not found: {from_plan_dir}")

    try:
        changes = adopt(
            project_dir=project_dir,
            spec_path=spec_path,
            milestone_label=args.milestone,
            from_plan_dir=from_plan_dir,
            dry_run=args.dry_run,
        )
    except FileNotFoundError as e:
        sys.exit(f"ERROR: {e}")
    except ValueError as e:
        sys.exit(f"ERROR: {e}")
    except yaml.YAMLError as e:
        sys.exit(f"ERROR: YAML parse error in spec: {e}")
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: JSON parse error: {e}")

    # Report
    mode = "DRY RUN" if args.dry_run else "EXECUTED"
    print(f"=== adopt_plan.py {mode} ===")
    for change in changes:
        action = change["action"]
        print(f"\n  [{action}]")
        for key, val in change.items():
            if key == "action":
                continue
            if isinstance(val, dict):
                print(f"    {key}:")
                for sub_k, sub_v in val.items():
                    print(f"      {sub_k}: {_fmt(sub_v)}")
            else:
                print(f"    {key}: {_fmt(val)}")

    if not args.dry_run:
        chain_state_path = _compute_chain_state_path(args.spec)
        print(f"\n✓ Adoption complete.")
        print(f"  Chain state: {chain_state_path}")
        print(f"  Plan:        {_target_plan_path(project_dir, _resolve_plan_name(from_plan_dir))}")
        print(f"  Milestone:   {args.milestone} (index {changes[0].get('index')})")
        print(f"\nNext chain run will RESUME at EXECUTE for this milestone.")
    else:
        print(f"\n✓ Dry-run complete. No changes were made.")


def _fmt(val: Any) -> str:
    """Format a value for display."""
    if val is None:
        return "<null>"
    if isinstance(val, Path):
        return str(val)
    return repr(val)


if __name__ == "__main__":
    main()
