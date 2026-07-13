from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core import atomic_write_text, get_effective


def _canonical_instructions() -> str:
    return (
        resources.files("arnold_pipelines.megaplan")
        .joinpath("data", "instructions.md")
        .read_text(encoding="utf-8")
    )


_SKILL_HEADER = """\
---
name: megaplan
description: AI agent harness for coordinating Claude and GPT to make and execute extremely robust plans.
---

"""

_CURSOR_HEADER = """\
---
description: Use megaplan for high-rigor planning on complex, high-risk, or multi-stage tasks.
alwaysApply: false
---

"""


def bundled_agents_md() -> str:
    return _canonical_instructions()


def _subagent_appendix(filename: str) -> str:
    content = (
        resources.files("arnold_pipelines.megaplan")
        .joinpath("data", filename)
        .read_text(encoding="utf-8")
    )
    content = content.replace(
        "{max_execute_no_progress}",
        str(get_effective("execution", "max_execute_no_progress")),
    )
    content = content.replace(
        "{max_review_rework_cycles}",
        str(get_effective("execution", "max_review_rework_cycles")),
    )
    return content


def _claude_subagent_appendix() -> str:
    return _subagent_appendix("claude_subagent_appendix.md")


def _codex_subagent_appendix() -> str:
    return _subagent_appendix("codex_subagent_appendix.md")


def _canonical_tickets_skill() -> str:
    return (
        resources.files("arnold_pipelines.megaplan")
        .joinpath("data", "tickets_skill.md")
        .read_text(encoding="utf-8")
    )


def _canonical_prep_skill() -> str:
    # The megaplan-prep skill (formerly megaplan-setup, formerly
    # megaplan-decision). The on-disk file was renamed
    # decision_skill.md → setup_skill.md → prep_skill.md.
    return (
        resources.files("arnold_pipelines.megaplan")
        .joinpath("data", "prep_skill.md")
        .read_text(encoding="utf-8")
    )


def _canonical_epic_skill() -> str:
    return (
        resources.files("arnold_pipelines.megaplan")
        .joinpath("data", "epic_skill.md")
        .read_text(encoding="utf-8")
    )


def _canonical_observe_skill() -> str:
    return (
        resources.files("arnold_pipelines.megaplan")
        .joinpath("data", "observe_skill.md")
        .read_text(encoding="utf-8")
    )


def _canonical_cloud_skill() -> str:
    return (
        resources.files("arnold_pipelines.megaplan")
        .joinpath("data", "cloud_skill.md")
        .read_text(encoding="utf-8")
    )


def _canonical_bakeoff_skill() -> str:
    return (
        resources.files("arnold_pipelines.megaplan")
        .joinpath("data", "bakeoff_skill.md")
        .read_text(encoding="utf-8")
    )


def _canonical_babysit_skill() -> str:
    return (
        resources.files("arnold_pipelines.megaplan")
        .joinpath("data", "babysit_skill.md")
        .read_text(encoding="utf-8")
    )


def _canonical_subagent_launcher_skill() -> str:
    return (
        resources.files("arnold_pipelines.megaplan")
        .joinpath("skills", "subagent-launcher", "SKILL.md")
        .read_text(encoding="utf-8")
    )


def _canonical_data_skill(filename: str) -> str:
    """Read a single-source skill whose checked-in data file is canonical."""
    return (
        resources.files("arnold_pipelines.megaplan")
        .joinpath("data", filename)
        .read_text(encoding="utf-8")
    )


def _canonical_pre_commit_hook() -> str:
    return (
        resources.files("arnold_pipelines.megaplan")
        .joinpath("data", "pre-commit-hook.sh")
        .read_text(encoding="utf-8")
    )


def _canonical_composed(name: str) -> str:
    return (
        resources.files("arnold_pipelines.megaplan")
        .joinpath("data", "_composed", name)
        .read_text(encoding="utf-8")
    )


def bundled_global_file(name: str) -> str:
    # Single-source skills: the canonical file already carries its frontmatter,
    # so this function just returns the canonical content unchanged. Do not
    # prepend headers — that's how the May 2026 megaplan-decision shadow-doc
    # regression happened (double frontmatter, drift between header and doc).
    if name == "tickets_skill.md":
        return _canonical_tickets_skill()
    if name == "prep_skill.md":
        return _canonical_prep_skill()
    if name in {"setup_skill.md", "decision_skill.md", "rubric_skill.md"}:
        # prep_skill.md is canonical; setup_skill.md / decision_skill.md /
        # rubric_skill.md are retained as legacy aliases for back-compat.
        return _canonical_prep_skill()
    if name == "epic_skill.md":
        return _canonical_epic_skill()
    if name == "observe_skill.md":
        return _canonical_observe_skill()
    if name == "cloud_skill.md":
        return _canonical_cloud_skill()
    if name == "bakeoff_skill.md":
        return _canonical_bakeoff_skill()
    if name == "babysit_skill.md":
        return _canonical_babysit_skill()
    if name in {"superfixer_debug_skill.md", "progress_auditor_debug_skill.md"}:
        return _canonical_data_skill(name)
    if name == "subagent_launcher_skill.md":
        return _canonical_subagent_launcher_skill()
    if name == "claude_skill.md":
        return _canonical_composed("claude_skill.md")
    if name == "codex_skill.md":
        return _canonical_composed("codex_skill.md")
    if name == "cursor_rule.mdc":
        return _canonical_composed("cursor_rule.mdc")
    content = _canonical_instructions()
    if name == "skill.md":
        return _SKILL_HEADER + content
    return content


_GLOBAL_TARGETS = [
    {"agent": "claude", "detect": ".claude", "path": ".claude/skills/megaplan/SKILL.md", "data": "_composed/claude_skill.md", "install": "symlink"},
    {"agent": "codex", "detect": ".codex", "path": ".codex/skills/megaplan", "data": "_codex_skills/megaplan", "install": "symlink"},
    {"agent": "cursor", "detect": ".cursor", "path": ".cursor/rules/megaplan.mdc", "data": "_composed/cursor_rule.mdc", "install": "symlink"},
    {"agent": "claude", "detect": ".claude", "path": ".claude/skills/megaplan-bakeoff/SKILL.md", "data": "bakeoff_skill.md", "install": "symlink"},
    {"agent": "codex", "detect": ".codex", "path": ".codex/skills/megaplan-bakeoff", "data": "_codex_skills/megaplan-bakeoff", "install": "symlink"},
    {"agent": "claude", "detect": ".claude", "path": ".claude/skills/megaplan-tickets/SKILL.md", "data": "tickets_skill.md", "install": "symlink"},
    {"agent": "codex", "detect": ".codex", "path": ".codex/skills/megaplan-tickets", "data": "_codex_skills/megaplan-tickets", "install": "symlink"},
    {"agent": "claude", "detect": ".claude", "path": ".claude/skills/megaplan-prep/SKILL.md", "data": "prep_skill.md", "install": "symlink"},
    {"agent": "codex", "detect": ".codex", "path": ".codex/skills/megaplan-prep", "data": "_codex_skills/megaplan-prep", "install": "symlink"},
    {"agent": "claude", "detect": ".claude", "path": ".claude/skills/superfixer-debug/SKILL.md", "data": "superfixer_debug_skill.md", "install": "symlink"},
    {"agent": "codex", "detect": ".codex", "path": ".codex/skills/superfixer-debug", "data": "_codex_skills/superfixer-debug", "install": "symlink"},
    {"agent": "claude", "detect": ".claude", "path": ".claude/skills/progress-auditor-debug/SKILL.md", "data": "progress_auditor_debug_skill.md", "install": "symlink"},
    {"agent": "codex", "detect": ".codex", "path": ".codex/skills/progress-auditor-debug", "data": "_codex_skills/progress-auditor-debug", "install": "symlink"},
    {"agent": "claude", "detect": ".claude", "path": ".claude/skills/megaplan-epic/SKILL.md", "data": "epic_skill.md", "install": "symlink"},
    {"agent": "codex", "detect": ".codex", "path": ".codex/skills/megaplan-epic", "data": "_codex_skills/megaplan-epic", "install": "symlink"},
    {"agent": "claude", "detect": ".claude", "path": ".claude/skills/megaplan-observe/SKILL.md", "data": "observe_skill.md", "install": "symlink"},
    {"agent": "codex", "detect": ".codex", "path": ".codex/skills/megaplan-observe", "data": "_codex_skills/megaplan-observe", "install": "symlink"},
    {"agent": "claude", "detect": ".claude", "path": ".claude/skills/megaplan-cloud/SKILL.md", "data": "cloud_skill.md", "install": "symlink"},
    {"agent": "codex", "detect": ".codex", "path": ".codex/skills/megaplan-cloud", "data": "_codex_skills/megaplan-cloud", "install": "symlink"},
    {"agent": "claude", "detect": ".claude", "path": ".claude/skills/babysit/SKILL.md", "data": "babysit_skill.md", "install": "symlink"},
    {"agent": "codex", "detect": ".codex", "path": ".codex/skills/babysit", "data": "_codex_skills/babysit", "install": "symlink"},
    {"agent": "claude", "detect": ".claude", "path": ".claude/skills/subagent-launcher", "data": "skills/subagent-launcher", "install": "symlink"},
    {"agent": "codex", "detect": ".codex", "path": ".codex/skills/subagent-launcher", "data": "skills/subagent-launcher", "install": "symlink"},
    {"agent": "hermes", "detect": ".hermes", "path": ".hermes/skills/subagent-launcher", "data": "skills/subagent-launcher", "install": "symlink"},
    {"agent": "agents", "detect": ".agents", "path": ".agents/skills/subagent-launcher", "data": "skills/subagent-launcher", "install": "symlink"},
    {"agent": "claude", "detect": ".claude", "path": ".claude/skills/cleanup-loose-branches", "data": "skills/cleanup-loose-branches", "install": "symlink"},
    {"agent": "codex", "detect": ".codex", "path": ".codex/skills/cleanup-loose-branches", "data": "skills/cleanup-loose-branches", "install": "symlink"},
    {"agent": "hermes", "detect": ".hermes", "path": ".hermes/skills/cleanup-loose-branches", "data": "skills/cleanup-loose-branches", "install": "symlink"},
    {"agent": "agents", "detect": ".agents", "path": ".agents/skills/cleanup-loose-branches", "data": "skills/cleanup-loose-branches", "install": "symlink"},
]


# Keep the generated Codex bundles in one registry.  The install targets above
# deliberately point at these directories, so adding a target without adding a
# generator entry must be caught by packaging tests rather than producing a
# dangling skill at runtime.
_CODEX_SINGLE_FILE_SKILLS = {
    "megaplan-bakeoff": "bakeoff_skill.md",
    "megaplan-tickets": "tickets_skill.md",
    "megaplan-prep": "prep_skill.md",
    "superfixer-debug": "superfixer_debug_skill.md",
    "progress-auditor-debug": "progress_auditor_debug_skill.md",
    "megaplan-epic": "epic_skill.md",
    "megaplan-observe": "observe_skill.md",
    "megaplan-cloud": "cloud_skill.md",
    "babysit": "babysit_skill.md",
}


def _resolve_bundle_path(data_name: str) -> Path:
    if data_name.startswith("skills/"):
        return Path(str(resources.files("arnold_pipelines.megaplan").joinpath(data_name)))
    return Path(str(resources.files("arnold_pipelines.megaplan").joinpath("data", data_name)))


def handle_regen_composed() -> dict[str, Any]:
    instructions = _canonical_instructions()
    targets = {
        "claude_skill.md": _SKILL_HEADER
        + instructions
        + "\n\n"
        + _claude_subagent_appendix(),
        "codex_skill.md": _SKILL_HEADER
        + instructions
        + "\n\n"
        + _codex_subagent_appendix(),
        "cursor_rule.mdc": _CURSOR_HEADER + instructions,
    }
    codex_skill_dirs = {"_codex_skills/megaplan/SKILL.md": targets["codex_skill.md"]}
    codex_skill_dirs.update(
        {
            f"_codex_skills/{skill_name}/SKILL.md": bundled_global_file(source)
            for skill_name, source in _CODEX_SINGLE_FILE_SKILLS.items()
        }
    )
    composed_dir = resources.files("arnold_pipelines.megaplan").joinpath("data", "_composed")
    Path(str(composed_dir)).mkdir(parents=True, exist_ok=True)
    changed: list[str] = []
    for name, computed in targets.items():
        target_path = Path(str(composed_dir)) / name
        current = (
            target_path.read_text(encoding="utf-8") if target_path.is_file() else ""
        )
        if current != computed:
            atomic_write_text(target_path, computed)
            changed.append(name)
    data_dir = Path(str(resources.files("arnold_pipelines.megaplan").joinpath("data")))
    for name, computed in codex_skill_dirs.items():
        target_path = data_dir / name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        current = target_path.read_text(encoding="utf-8") if target_path.is_file() else ""
        if target_path.is_symlink() or current != computed:
            atomic_write_text(target_path, computed)
            changed.append(name)
    if changed:
        return {
            "success": False,
            "changed": changed,
            "summary": f"Regenerated {len(changed)} composed bundle(s): {', '.join(changed)}.",
        }
    return {"success": True, "changed": [], "summary": "No composed bundles changed."}
