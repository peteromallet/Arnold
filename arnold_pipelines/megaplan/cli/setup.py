from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.profiles import DEFAULT_AGENT_ROUTING, effective_premium_vendor
from arnold_pipelines.megaplan.types import (
    CliError,
    PREMIUM_AGENT,
    StepResponse,
    parse_agent_spec,
)
from arnold_pipelines.megaplan._core import (
    atomic_write_text,
    detect_available_agents,
    load_config,
    save_config,
)
from .editor_setup import ensure_repo_editor_support, ensure_user_editor_support
from .skills import (
    _GLOBAL_TARGETS,
    _canonical_pre_commit_hook,
    _resolve_bundle_path,
    bundled_agents_md,
    bundled_global_file,
    handle_regen_composed,
)


def _install_owned_file(
    path: Path, content: str, *, force: bool = False
) -> dict[str, bool | str]:
    existed = path.exists()
    if existed and not force:
        if path.is_symlink():
            return {
                "path": str(path),
                "skipped": True,
                "existed": True,
                "reason": "symlinked",
            }
        if path.read_text(encoding="utf-8") == content:
            return {"path": str(path), "skipped": True, "existed": True}
    if path.is_symlink() or path.exists():
        path.unlink()
    atomic_write_text(path, content)
    return {"path": str(path), "skipped": False, "existed": existed}


def _install_owned_symlink(
    path: Path, target_path: Path, *, force: bool = False
) -> dict[str, bool | str]:
    try:
        canonical = target_path.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        return {
            "path": str(path),
            "skipped": True,
            "existed": path.exists() or path.is_symlink(),
            "reason": f"canonical missing: {exc}",
        }
    existed = path.exists() or path.is_symlink()
    if existed and not force and path.is_symlink():
        try:
            if path.resolve(strict=True) == canonical:
                return {
                    "path": str(path),
                    "target": str(canonical),
                    "skipped": True,
                    "existed": True,
                    "symlink": True,
                }
        except (FileNotFoundError, OSError):
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        path.unlink()
    path.symlink_to(canonical)
    return {
        "path": str(path),
        "target": str(canonical),
        "skipped": False,
        "existed": existed,
        "symlink": True,
    }


def _install_owned_dir_symlink(
    path: Path, target_dir: Path, *, force: bool = False
) -> dict[str, bool | str]:
    try:
        canonical = target_dir.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        return {
            "path": str(path),
            "skipped": True,
            "existed": path.exists() or path.is_symlink(),
            "reason": f"canonical missing: {exc}",
        }
    existed = path.exists() or path.is_symlink()
    if existed and not force and path.is_symlink():
        try:
            if path.resolve(strict=True) == canonical:
                return {
                    "path": str(path),
                    "target": str(canonical),
                    "skipped": True,
                    "existed": True,
                    "symlink": True,
                }
        except (FileNotFoundError, OSError):
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)
    path.symlink_to(canonical, target_is_directory=True)
    return {
        "path": str(path),
        "target": str(canonical),
        "skipped": False,
        "existed": existed,
        "symlink": True,
    }


def handle_setup_global(force: bool = False, home: Path | None = None) -> StepResponse:
    # Codex skills are generated from their canonical single-source documents.
    # Regenerate before resolving install targets so a clean/editable checkout
    # cannot silently skip a newly declared skill because its ignored bundle has
    # not been materialized yet.
    handle_regen_composed()
    if home is None:
        home = Path.home()
    installed: list[dict[str, Any]] = []
    detected_count = 0
    for target in _GLOBAL_TARGETS:
        agent_dir = home / target["detect"]
        if not agent_dir.is_dir():
            installed.append(
                {
                    "agent": target["agent"],
                    "path": str(home / target["path"]),
                    "skipped": True,
                    "reason": "not installed",
                }
            )
            continue
        detected_count += 1
        mode = target.get("install", "copy")
        if mode == "symlink":
            result = _install_owned_symlink(
                home / target["path"],
                _resolve_bundle_path(target["data"]),
                force=force,
            )
        elif mode == "dir_symlink":
            result = _install_owned_dir_symlink(
                home / target["path"],
                _resolve_bundle_path(target["data"]),
                force=force,
            )
        else:
            result = _install_owned_file(
                home / target["path"],
                bundled_global_file(target["data"]),
                force=force,
            )
        result["agent"] = target["agent"]
        installed.append(result)
    if detected_count == 0:
        return {
            "success": False,
            "step": "setup",
            "mode": "global",
            "summary": "No supported agents detected. Create one of ~/.claude/, ~/.codex/, or ~/.cursor/ and re-run.",
            "installed": installed,
        }
    available = detect_available_agents()
    config_path = None
    routing = None
    if available:
        vendor = effective_premium_vendor()

        def _resolve_default(spec: str) -> str:
            parsed = parse_agent_spec(spec)
            if parsed.agent == PREMIUM_AGENT:
                if parsed.effort:
                    return f"{vendor}:{parsed.effort}"
                return vendor
            return spec

        agents_config = {
            step: (
                resolved
                if parse_agent_spec(resolved).agent in available
                else available[0]
            )
            for step, default in DEFAULT_AGENT_ROUTING.items()
            for resolved in (_resolve_default(default),)
        }
        config = load_config(home)
        config["agents"] = agents_config
        config_path = save_config(config, home)
        routing = agents_config
    lines = []
    for rec in installed:
        if rec.get("reason") == "not installed":
            lines.append(f"  {rec['agent']}: skipped (not installed)")
        elif rec["skipped"]:
            lines.append(f"  {rec['agent']}: up to date")
        else:
            lines.append(
                f"  {rec['agent']}: {'overwrote' if rec['existed'] else 'created'} {rec['path']}"
            )
    result_data: dict[str, Any] = {
        "success": True,
        "step": "setup",
        "mode": "global",
        "summary": "Global setup complete:\n" + "\n".join(lines),
        "installed": installed,
    }
    if config_path is not None:
        result_data["config_path"] = str(config_path)
        result_data["routing"] = routing
    return result_data


def handle_setup_hooks(
    target_dir: Path | None = None, *, force: bool = False
) -> StepResponse:
    start = (target_dir or Path.cwd()).resolve()
    hook_path = resolve_pre_commit_hook_path(start)
    if hook_path is None:
        raise CliError(
            "not_git_repo",
            f"Cannot install hooks because {start} is not inside a git repository.",
        )
    content = _canonical_pre_commit_hook()
    if hook_path.exists() and not force:
        if hook_path.read_text(encoding="utf-8") == content:
            return {
                "success": True,
                "step": "setup",
                "mode": "hooks",
                "summary": f"Pre-commit hook already up to date at {hook_path}",
                "path": str(hook_path),
                "skipped": True,
            }
        raise CliError(
            "hook_exists",
            f"Pre-commit hook already exists at {hook_path}. Re-run with --force to replace it.",
        )
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(hook_path, content)
    hook_path.chmod(0o755)
    return {
        "success": True,
        "step": "setup",
        "mode": "hooks",
        "summary": f"Installed pre-commit hook at {hook_path}",
        "path": str(hook_path),
        "skipped": False,
    }


def resolve_pre_commit_hook_path(start: Path) -> Path | None:
    """Resolve git's effective pre-commit hook path, including worktrees."""

    proc = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--git-path", "hooks/pre-commit"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    path = Path(proc.stdout.strip())
    return path.resolve() if path.is_absolute() else (start / path).resolve()


def pre_commit_hook_status(start: Path) -> tuple[str, Path | None]:
    """Return ``missing``, ``current``, or ``stale`` for the effective hook."""

    hook_path = resolve_pre_commit_hook_path(start.resolve())
    if hook_path is None or not hook_path.exists():
        return "missing", hook_path
    try:
        installed = hook_path.read_text(encoding="utf-8")
    except OSError:
        return "stale", hook_path
    return (
        ("current" if installed == _canonical_pre_commit_hook() else "stale"),
        hook_path,
    )


def handle_setup_hook_check(target_dir: Path | None = None) -> StepResponse:
    """Fail actionably when an installed hook differs from the template."""

    start = (target_dir or Path.cwd()).resolve()
    status, hook_path = pre_commit_hook_status(start)
    if status == "stale":
        raise CliError(
            "stale_pre_commit_hook",
            "Installed pre-commit hook is stale at "
            f"{hook_path}. Refresh it with: "
            "python -m arnold_pipelines.megaplan setup --install-hooks --force",
        )
    return {
        "success": True,
        "step": "setup",
        "mode": "hook-check",
        "status": status,
        "path": str(hook_path) if hook_path is not None else None,
        "summary": (
            f"Pre-commit hook is {status}"
            + (f" at {hook_path}" if hook_path is not None else "")
        ),
    }


def handle_setup(args: argparse.Namespace) -> StepResponse:
    if getattr(args, "regen_composed", False):
        result = handle_regen_composed()
        if getattr(args, "stage_regenerated", False) and result.get("changed_paths"):
            subprocess.run(
                ["git", "add", "--", *result["changed_paths"]],
                check=True,
            )
        return result
    if getattr(args, "editors", False):
        target_dir = Path(args.target_dir).resolve() if args.target_dir else Path.cwd()
        changes = ensure_repo_editor_support(target_dir)
        if getattr(args, "user_editors", False):
            changes.extend(ensure_user_editor_support(Path.home()))
        lines = [
            f"  {change.target}: {change.status} {change.path}"
            + (f" ({change.reason})" if change.reason else "")
            for change in changes
        ]
        return {
            "success": True,
            "step": "setup",
            "mode": "editors",
            "summary": "Editor setup complete:\n" + "\n".join(lines),
            "changes": [change.as_dict() for change in changes],
        }
    if getattr(args, "install_hooks", False):
        target_dir = Path(args.target_dir).resolve() if args.target_dir else Path.cwd()
        return handle_setup_hooks(target_dir, force=args.force)
    if getattr(args, "check_hooks", False):
        target_dir = Path(args.target_dir).resolve() if args.target_dir else Path.cwd()
        return handle_setup_hook_check(target_dir)
    local = args.local or args.target_dir
    if not local:
        return handle_setup_global(force=args.force)
    target_dir = Path(args.target_dir).resolve() if args.target_dir else Path.cwd()
    target = target_dir / "AGENTS.md"
    content = bundled_agents_md()
    if target.exists() and not args.force:
        existing = target.read_text(encoding="utf-8")
        if "megaplan" in existing.lower():
            return {
                "success": True,
                "step": "setup",
                "summary": f"AGENTS.md already contains megaplan instructions at {target}",
                "skipped": True,
            }
        atomic_write_text(target, existing + "\n\n" + content)
        return {
            "success": True,
            "step": "setup",
            "summary": f"Appended megaplan instructions to existing {target}",
            "file": str(target),
        }
    atomic_write_text(target, content)
    return {
        "success": True,
        "step": "setup",
        "summary": f"Created {target}",
        "file": str(target),
    }
