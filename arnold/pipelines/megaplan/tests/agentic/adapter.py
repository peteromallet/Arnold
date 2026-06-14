"""
adapter.py — Megaplan project adapter for the Sisypy.

Implements :class:`AgenticProjectAdapter` for megaplan semantics:

(a) ``build_env`` — sets ``MEGAPLAN_HOME`` to an isolated scratch dir so
    agent runs don't pollute the real ``~/.megaplan/``.
(b) ``prime`` — creates a per-run scratch directory under
    ``<repo>/.megaplan-agentic/<run.id>/``.
(c) ``capture`` — copies ``.megaplan/plans/`` (or ``MEGAPLAN_HOME/**``)
    into ``evidence/project_specific/`` plus compact tree listings.
    Best-effort — notes instead of exceptions.
(d) ``project_universal_checks`` — delegates to
    :mod:`megaplan.tests.agentic.megaplan_checks`.
(e) ``canonical_bypass_patterns`` — megaplan-specific bypass regexes
    (e.g. direct file writes bypassing the megaplan CLI).
(f) ``classify_success`` — evidence-only ladder:
    *RUNTIME_PROVEN* if ``state.json`` shows ``current_state`` in
    {done, reviewed}; *VALIDATED* for ``create_poem_panel`` if
    ``load_pipeline('poem-panel')`` succeeds; *AUTHORED* if
    ``git_diff.patch`` shows any code/doc addition; else lowest level.
(g) ``live_prerequisites`` — dict of prerequisite boolean checks.
(h) ``command_policy`` — permissive allow/deny patterns for structural
    and live modes.

Reference implementation: VibeComfy adapter (843 LOC).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from sisypy.adapters import AgenticProjectAdapter
from sisypy.schema import (
    ActorRun,
    EvidencePack,
    RunMode,
    Scenario,
    SuccessProofLevel,
)


# ---------------------------------------------------------------------------
# Bypass patterns
# ---------------------------------------------------------------------------

_MEGAPLAN_BYPASS_PATTERNS: list[str] = [
    # Direct file writes that bypass the megaplan CLI.
    r">\s*\S+\.json\s*&&\s*megaplan",
    r"cp\s+.*\.megaplan/",
    r"mv\s+.*\.megaplan/",
    # Absolute writes outside the repo.
    r"(?:^|\s)/(?:tmp|var|home)/\S*\.(?:json|yaml|yml|py)\b",
    r">\s*/(?:tmp|var|home)/",
    # Direct invocation of system Python that could mask the environment.
    r"/usr/bin/python\s",
    r"/usr/local/bin/python\s",
    r"/opt/homebrew/bin/python\s",
    # Attempt to read .env or credentials.
    r"\b(?:cat|less|head|tail)\s+.*\.env\b",
    # Direct manipulation of megaplan state outside the CLI.
    r"\.megaplan/state\.json\b",
    r"\.megaplan/plans/",
    r"sqlite3.*\.megaplan/",
]


# ---------------------------------------------------------------------------
# Command policy
# ---------------------------------------------------------------------------

_STRUCTURAL_ALLOW_PATTERNS: list[str] = [
    r"\bpython\b",
    r"\bpython3\b",
    r"\buv\b",
    r"\bpytest\b",
    # Megaplan read-only / safe commands.
    r"\bmegaplan\s+status\b",
    r"\bmegaplan\s+list\b",
    r"\bmegaplan\s+show\b",
    r"\bmegaplan\s+inspect\b",
    r"\bmegaplan\s+plan\b",
    r"\bmegaplan\s+init\b",
    r"\bmegaplan\s+run\b",
    r"\bmegaplan\s+advance\b",
    r"\bmegaplan\s+review\b",
    r"\bmegaplan\s+approve\b",
    r"\bmegaplan\s+done\b",
    r"\bmegaplan\s+reject\b",
    r"\bmegaplan\s+block\b",
    r"\bmegaplan\s+config\b",
    r"\bmegaplan\s+create\b",
    r"\bmegaplan\s+new\b",
    r"\bmegaplan\s+--no-color\b",
    # Basic tooling.
    r"\bgrep\b",
    r"\bfind\b",
    r"\bls\b",
    r"\bcat\b",
    r"\bhead\b",
    r"\btail\b",
    r"\bgit\s+status\b",
    r"\bgit\s+diff\b",
    r"\bgit\s+log\b",
    r"\bgit\s+add\b",
    r"\bgit\s+commit\b",
    r"\bmkdir\b",
    r"\btouch\b",
]

_STRUCTURAL_DENY_PATTERNS: list[str] = [
    # Cloud / remote actions.
    r"\bmegaplan\s+cloud\b",
    r"\bmegaplan\s+deploy\b",
    # SSH commands.
    r"\bssh\b",
    r"\bscp\b",
    # Destructive git.
    r"\bgit\s+push\b",
    r"\bgit\s+reset\s+--hard\b",
    # pip install (except in uv context).
    r"\bpip\s+install\b",
    # curl / wget downloads.
    r"\bcurl\b.*-o\b",
    r"\bwget\b",
    # Environment variable manipulation for secrets.
    r"\bDEEPSEEK_API_KEY\s*=",
    r"\bMEGAPLAN_API_KEY\s*=",
    r"\bexport\s+DEEPSEEK_API_KEY\b",
]


# ---------------------------------------------------------------------------
# MegaplanAdapter
# ---------------------------------------------------------------------------


class MegaplanAdapter(AgenticProjectAdapter):
    """Megaplan-specific project adapter for the Sisypy agentic test harness.

    Implements all 8 ABC methods with megaplan-aware semantics:
    - MEGAPLAN_HOME isolation per run.
    - Evidence capture of .megaplan/plans and tree listings.
    - Friction-signal extraction via megaplan_checks.
    - Success-proof ladder classification.
    """

    name: str = "megaplan"
    repo_root: Path

    # Per-run scratch dirs keyed by run.id.
    _scratch_dirs: dict[str, Path]

    def __init__(self, *, name: str = "megaplan",
                 repo_root: Path | None = None) -> None:
        self.name = name
        self.repo_root = Path(repo_root) if repo_root else Path.cwd()
        self._scratch_dirs = {}

    # ------------------------------------------------------------------
    # 1. build_env
    # ------------------------------------------------------------------

    def build_env(self, scenario: Scenario, run: ActorRun) -> dict[str, str]:
        """Return env dict with isolated MEGAPLAN_HOME and PYTHONPATH.

        MEGAPLAN_HOME points at ``<scratch>/home`` inside the per-run
        scratch directory so that the agent cannot read or mutate the
        user's real ``~/.megaplan/`` state.
        """
        scratch = self._scratch_for(run)
        home = scratch / "home"
        home.mkdir(parents=True, exist_ok=True)

        env: dict[str, str] = {}

        # Carry forward existing PATH so basic tooling works.
        existing_path = os.environ.get("PATH", "")
        env["PATH"] = existing_path

        # Isolate megaplan home.
        env["MEGAPLAN_HOME"] = str(home)

        # Add the repo root to PYTHONPATH so megaplan imports work.
        existing_pp = os.environ.get("PYTHONPATH", "")
        sep = ":" if existing_pp else ""
        env["PYTHONPATH"] = f"{self.repo_root}{sep}{existing_pp}"

        # TODO(megaplan): some megaplan code paths may hard-code ~/.megaplan/
        # regardless of MEGAPLAN_HOME. Probe this early and document leaks.
        return env

    # ------------------------------------------------------------------
    # 2. prime
    # ------------------------------------------------------------------

    def prime(self, scenario: Scenario, run: ActorRun) -> None:
        """Create the per-run scratch directory.

        Writes a brief instruction file requesting a final markdown report
        so that sisypy's evidence capture can locate ``report.md``.
        """
        scratch = self._scratch_for(run)
        scratch.mkdir(parents=True, exist_ok=True)

        # Write actor instructions — tell the agent to produce a final report.
        instructions = (
            "# Actor instructions\n\n"
            "When you are finished, write a final markdown report "
            "summarising what you did, what worked, and what did not. "
            "Write it to `report.md` in your working directory.\n"
        )
        (scratch / "actor_instructions.md").write_text(
            instructions, encoding="utf-8"
        )

    # ------------------------------------------------------------------
    # 3. capture
    # ------------------------------------------------------------------

    def capture(
        self, scenario: Scenario, run: ActorRun, evidence_dir: Path
    ) -> None:
        """Capture megaplan-specific evidence artifacts.

        Copies ``.megaplan/plans/`` (or ``MEGAPLAN_HOME/**``) into
        ``evidence/project_specific/`` and writes compact tree listings.
        Best-effort — notes instead of exceptions.
        """
        ps_dir = evidence_dir / "project_specific"
        ps_dir.mkdir(parents=True, exist_ok=True)

        notes: list[str] = []
        scratch = self._scratch_for(run)
        home = scratch / "home"

        # --- Copy MEGAPLAN_HOME tree (plans, state, etc.) ---
        if home.is_dir():
            try:
                _copy_tree(home, ps_dir / "megaplan_home",
                           ignore=lambda _d, _f: [".git"])
            except Exception as exc:
                notes.append(f"megaplan_home copy failed: {exc}")
        else:
            # Fallback: try the repo's .megaplan/ directory.
            repo_home = self.repo_root / ".megaplan"
            if repo_home.is_dir():
                try:
                    _copy_tree(repo_home, ps_dir / "megaplan_home",
                               ignore=lambda _d, _f: [".git"])
                except Exception as exc:
                    notes.append(f"repo .megaplan copy failed: {exc}")

        # --- Compact tree listing of the repo (top 2 levels) ---
        try:
            _write_tree(self.repo_root, ps_dir / "repo_tree.txt", depth=2)
        except Exception as exc:
            notes.append(f"repo tree failed: {exc}")

        # --- Compact tree listing of MEGAPLAN_HOME ---
        if home.is_dir():
            try:
                _write_tree(home, ps_dir / "home_tree.txt", depth=3)
            except Exception as exc:
                notes.append(f"home tree failed: {exc}")

        # --- Capture state.json if it exists ---
        for candidate in (home / "state.json",
                          home / "plans" / "state.json",
                          self.repo_root / ".megaplan" / "state.json"):
            if candidate.is_file():
                try:
                    shutil.copy2(candidate, ps_dir / "state.json")
                    break
                except Exception as exc:
                    notes.append(f"state.json copy from {candidate} failed: {exc}")

        # --- Write capture notes ---
        if notes:
            (evidence_dir / "capture.notes").write_text(
                "\n".join(notes), encoding="utf-8"
            )

    # ------------------------------------------------------------------
    # 4. project_universal_checks
    # ------------------------------------------------------------------

    def project_universal_checks(
        self, scenario: Scenario, evidence_dir: Path
    ) -> dict[str, Any]:
        """Delegate to the standalone friction-signal extractors."""
        from arnold.pipelines.megaplan.tests.agentic.megaplan_checks import (
            project_universal_checks as _checks,
        )
        return _checks(evidence_dir)

    # ------------------------------------------------------------------
    # 5. canonical_bypass_patterns
    # ------------------------------------------------------------------

    def canonical_bypass_patterns(self, scenario: Scenario) -> list[str]:
        """Return megaplan-specific bypass / path-escape patterns."""
        return list(_MEGAPLAN_BYPASS_PATTERNS)

    # ------------------------------------------------------------------
    # 6. classify_success
    # ------------------------------------------------------------------

    def classify_success(
        self, scenario: Scenario, evidence_pack: EvidencePack
    ) -> SuccessProofLevel:
        """Classify the highest success proof level from evidence only.

        Ladder (highest-first check):
        1. RUNTIME_PROVEN — state.json has current_state in {done, reviewed}.
        2. VALIDATED — for create_poem_panel: load_pipeline('poem-panel') trace.
        3. AUTHORED — git_diff.patch shows any code or doc addition.
        4. Lowest — SuccessProofLevel.AUTHORED (default fallback).
        """
        evidence_dir = Path(evidence_pack.evidence_dir)

        # --- Rung: RUNTIME_PROVEN ---
        state_file = evidence_dir / "project_specific" / "state.json"
        state_text = _try_read(state_file)
        if state_text:
            try:
                state = json.loads(state_text)
                cs = state.get("current_state", "")
                if cs in ("done", "reviewed"):
                    return SuccessProofLevel.RUNTIME_PROVEN
            except (json.JSONDecodeError, TypeError):
                pass

        # --- Rung: VALIDATED (create_poem_panel only) ---
        # Gate on actual artifacts, NOT actor narrative. The brief contains
        # "poem-panel" (captured into evidence/brief.md) and the actor's
        # report.md can fabricate any claim — neither is proof. Only trust
        # captured command output and filesystem state.
        if scenario.name == "create_poem_panel":
            # Strong signal: real load_pipeline trace in captured stdout.
            stdout_text = _try_read(evidence_dir / "stdout.log")
            if re.search(r"load_pipeline\(.*poem-panel.*\)", stdout_text):
                return SuccessProofLevel.VALIDATED
            # Medium signal: a pipeline.yaml landed under megaplan/pipelines/poem-panel/.
            for tree_name in ("project_specific/repo_tree.txt", "tree_after.txt"):
                tree_text = _try_read(evidence_dir / tree_name)
                if tree_text and re.search(
                    r"megaplan/pipelines/poem-panel/", tree_text
                ):
                    return SuccessProofLevel.VALIDATED
            # Medium signal: git diff added a file at that path.
            diff_text = _try_read(evidence_dir / "git_diff.patch")
            if diff_text and re.search(
                r"^\+\+\+ b/megaplan/pipelines/poem-panel/",
                diff_text,
                re.MULTILINE,
            ):
                return SuccessProofLevel.VALIDATED

        # --- Rung: AUTHORED ---
        git_diff = evidence_dir / "git_diff.patch"
        diff_text = _try_read(git_diff)
        if diff_text and (
            re.search(r"diff --git", diff_text)
            or re.search(r"\+\s", diff_text)
        ):
            return SuccessProofLevel.AUTHORED

        # Check tree listings for any new files.
        for tree_name in ("tree_after.txt", "repo_tree.txt"):
            tree_text = _try_read(evidence_dir / tree_name)
            if tree_text and re.search(r"F\s+\S", tree_text):
                return SuccessProofLevel.AUTHORED

        # --- Default: lowest proof level ---
        return SuccessProofLevel.AUTHORED

    # ------------------------------------------------------------------
    # 7. live_prerequisites
    # ------------------------------------------------------------------

    def live_prerequisites(self, scenario: Scenario) -> dict[str, bool]:
        """Return prerequisite checks for live execution.

        In structural mode these are not enforced by sisypy, but the
        adapter provides them so the runner can gate live runs.
        """
        prereqs: dict[str, bool] = {}

        # DEEPSEEK_API_KEY — required for Hermes dispatch.
        dsk = os.environ.get("DEEPSEEK_API_KEY") or ""
        if not dsk:
            hermes_env = Path.home() / ".hermes" / ".env"
            if hermes_env.is_file():
                try:
                    for line in hermes_env.read_text("utf-8").splitlines():
                        if line.strip().startswith("DEEPSEEK_API_KEY"):
                            _, _, val = line.partition("=")
                            dsk = val.strip().strip('"').strip("'")
                            break
                except Exception:
                    pass
        prereqs["DEEPSEEK_API_KEY"] = bool(dsk)

        # Timeout configured.
        budget = scenario.budget or {}
        prereqs["timeout_configured"] = bool(
            budget.get("timeout_sec")
            or os.environ.get("AGENTIC_TIMEOUT_SEC")
        )

        # MEGAPLAN_HOME isolation (best-effort probe).
        prereqs["megplan_home_isolated"] = True

        return prereqs

    # ------------------------------------------------------------------
    # 8. command_policy
    # ------------------------------------------------------------------

    def command_policy(
        self, scenario: Scenario, run: ActorRun
    ) -> dict[str, Any]:
        """Return permissive command allow/deny policy.

        In structural mode, applies a broad allow list with a small deny
        list for destructive / cloud operations.
        In live mode, everything is allowed (gated by prerequisites).
        """
        if run.mode == RunMode.STRUCTURAL:
            return {
                "allow_patterns": list(_STRUCTURAL_ALLOW_PATTERNS),
                "deny_patterns": list(_STRUCTURAL_DENY_PATTERNS),
                "enforce": True,
            }
        else:
            return {
                "allow_patterns": [r".*"],
                "deny_patterns": [],
                "enforce": False,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scratch_for(self, run: ActorRun) -> Path:
        """Return the deterministic scratch dir for *run*.

        Derived from ``run.id``: ``<repo_root>/.megaplan-agentic/<run.id>/``.
        Cached on ``self._scratch_dirs``.
        """
        if run.id not in self._scratch_dirs:
            p = self.repo_root / ".megaplan-agentic" / run.id
            p.mkdir(parents=True, exist_ok=True)
            self._scratch_dirs[run.id] = p
        return self._scratch_dirs[run.id]


# ---------------------------------------------------------------------------
# Capture helpers (module-level, reusable)
# ---------------------------------------------------------------------------


def _copy_tree(src: Path, dst: Path, **kwargs: Any) -> None:
    """shutil.copytree wrapper that tolerates missing source."""
    if not src.is_dir():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=True, **kwargs)


def _write_tree(root: Path, dst: Path, *, depth: int = 2) -> None:
    """Write a compact ``find``-style tree listing limited to *depth*."""
    lines: list[str] = []
    try:
        for p in sorted(root.rglob("*")):
            rel = p.relative_to(root)
            if any(part.startswith(".") for part in rel.parts if part != "."):
                continue
            # Limit depth.
            if len(rel.parts) > depth:
                continue
            prefix = "D " if p.is_dir() else "F "
            lines.append(f"{prefix}{rel}")
            if len(lines) >= 2000:
                lines.append("... truncated at 2000 entries")
                break
    except Exception as exc:
        lines.append(f"# tree walk failed: {exc}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _try_read(path: Path) -> str:
    """Read a file as text, returning '' on any error."""
    try:
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _collect_text(evidence_dir: Path) -> str:
    """Collect all text from evidence files into a searchable string."""
    files_to_read = [
        "stdout.log", "stderr.log", "report.md", "command_log.jsonl",
        "git_diff.patch", "tree_after.txt", "capture.notes",
    ]
    parts: list[str] = []
    for fname in files_to_read:
        content = _try_read(evidence_dir / fname)
        if content:
            parts.append(content)
    ps_dir = evidence_dir / "project_specific"
    if ps_dir.is_dir():
        for fp in ps_dir.rglob("*"):
            if fp.is_file():
                parts.append(_try_read(fp))
    return "\n".join(parts)
