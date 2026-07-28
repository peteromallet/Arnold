"""AST-based Git mutation sink scanner shared by the M10 inventory generator
and the stale-anchor / unlisted-sink gate (Step 13E1/13E7/13E9).

A *mutation sink* is a function (top-level or nested) in one of the nine
inventoried Git mutation modules that constructs a git command list/tuple whose
leading subcommand (the first element, or the element immediately after the
literal ``"git"``) is a *mutating* subcommand, and routes it through a git
runner (``_run_git``, ``_git``, ``_restore_git``, ``_compat().subprocess.run``,
``subprocess.run/check_call/check_output/Popen``).

This module is deliberately dependency-free so it can be imported both at
inventory-generation time and inside the gate test.
"""

from __future__ import annotations

import ast
import hashlib
import os
from dataclasses import dataclass, field

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

MODULES = {
    "chain/git_ops.py": "arnold_pipelines/megaplan/chain/git_ops.py",
    "chain/target_rebind.py": "arnold_pipelines/megaplan/chain/target_rebind.py",
    "chain/__init__.py": "arnold_pipelines/megaplan/chain/__init__.py",
    "auto.py": "arnold_pipelines/megaplan/auto.py",
    "supervisor/pr_merge.py": "arnold_pipelines/megaplan/supervisor/pr_merge.py",
    "loop/git.py": "arnold_pipelines/megaplan/loop/git.py",
    "bakeoff/worktree.py": "arnold_pipelines/megaplan/bakeoff/worktree.py",
    "bakeoff/merge.py": "arnold_pipelines/megaplan/bakeoff/merge.py",
    "cli/__init__.py": "arnold_pipelines/megaplan/cli/__init__.py",
}

# Subcommands that change repository, working-tree, or ref state.
MUTATING_SUBCOMMANDS = {
    "add", "commit", "push", "reset", "clean", "checkout", "switch", "rebase",
    "stash", "apply", "revert", "update-ref", "merge", "rm", "mv", "worktree",
    "init", "clone", "branch", "tag", "fetch", "cherry-pick", "restore",
    "commit-tree", "replace", "notes", "reflog",
}

# Read-only subcommands — explicitly excluded even if they ever lead a list.
READ_SUBCOMMANDS = {
    "status", "log", "rev-parse", "show", "diff", "cat-file", "ls-files",
    "merge-base", "symbolic-ref", "for-each-ref", "ls-remote", "describe",
    "blame", "name-rev", "reflog", "fsck", "rev-list", "count-objects",
    "config", "remote", "var", "rev-list", "shortlog", "verify-pack",
    "bundle", "archive", "grep", "reflog",
}

# Tokens indicating the function actually *executes* a git command (as opposed
# to merely mentioning a subcommand string in a docstring/log).
GIT_RUNNER_TOKENS = (
    "_run_git", "_git", "_restore_git", "subprocess.run", "subprocess.check_call",
    "subprocess.check_output", "subprocess.Popen", "subprocess",
)

# Subcommands whose intent is unambiguously mutating when they lead a command.
_UNAMBIGUOUS_MUTATING = {
    "add", "commit", "push", "reset", "clean", "checkout", "switch", "rebase",
    "stash", "apply", "revert", "update-ref", "merge", "rm", "mv", "init",
    "clone", "cherry-pick", "restore", "commit-tree", "replace", "notes",
    "fetch", "reflog",
}

# ``worktree`` is mutating only for these actions; ``list`` is a read.
_WORKTREE_MUTATING_ACTIONS = {
    "add", "remove", "prune", "move", "lock", "unlock", "repair",
}

# ``branch`` is mutating when deleting, moving/renaming, or creating a named
# branch. These flags denote destructive/creating operations.
_BRANCH_MUTATING_FLAGS = {"-d", "-D", "--delete", "-m", "-M", "--move"}
_BRANCH_READ_FLAGS = {
    "--show-current", "-r", "--remotes", "-a", "--all", "-l", "--list",
    "-v", "--verbose", "--contains", "--no-contains", "--merged",
    "--no-merged", "-vv", "--sort", "--points-at", "--format",
}


def _elt_str(elt) -> str | None:
    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
        return elt.value
    return None


def _is_mutating_subcommand(cmd: str, following: list) -> bool:
    """Decide whether git subcommand *cmd* (with the literal *following* list
    elements) is a mutation."""
    nxt = _elt_str(following[0]) if following else None
    if cmd in _UNAMBIGUOUS_MUTATING:
        return True
    if cmd == "worktree":
        return nxt in _WORKTREE_MUTATING_ACTIONS
    if cmd == "branch":
        if nxt in _BRANCH_MUTATING_FLAGS:
            return True
        if nxt is None:
            return False  # bare ``git branch`` lists branches
        if nxt in _BRANCH_READ_FLAGS or nxt.startswith("-"):
            return False
        return True  # a positional branch name ⇒ create/delete
    if cmd == "tag":
        if nxt in {"-d", "-D", "--delete"}:
            return True
        if nxt is None or (nxt and nxt.startswith("-")):
            return False
        return True
    return False


@dataclass
class Sink:
    module: str
    function: str
    def_line: int
    call_line: int
    subcommands: tuple[str, ...]
    source_anchor: str

    @property
    def sink_id(self) -> str:
        return f"{self.module}::{self.function}"


def _leading_subcommands(node: ast.AST) -> list[str]:
    """Return mutating subcommands that lead any List/Tuple literal under *node*.

    A list/tuple leads with a mutating subcommand if its first element is a
    string in ``MUTATING_SUBCOMMANDS`` *or* its first element is the literal
    ``"git"`` and its second element is a mutating subcommand.
    """
    found: list[str] = []

    class _V(ast.NodeVisitor):
        def visit_List(self, n: ast.List) -> None:
            self._scan(n.elts)
            self.generic_visit(n)

        def visit_Tuple(self, n: ast.Tuple) -> None:
            self._scan(n.elts)
            self.generic_visit(n)

        def _scan(self, elts: list) -> None:
            if elts and isinstance(elts[0], ast.Constant) and isinstance(elts[0].value, str):
                first = elts[0].value
                cmd = None
                rest: list = []
                if first == "git" and len(elts) > 1:
                    cmd = _elt_str(elts[1])
                    rest = elts[2:]
                elif first != "git":
                    cmd = first
                    rest = elts[1:]
                if cmd and _is_mutating_subcommand(cmd, rest):
                    found.append(cmd)

    _V().visit(node)
    # de-duplicate, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for s in found:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _text_uses_git_runner(seg: str) -> bool:
    return any(tok in seg for tok in GIT_RUNNER_TOKENS)


def scan_module(relpath: str) -> list[Sink]:
    abspath = os.path.join(REPO_ROOT, relpath.replace("/", os.sep))
    source = open(abspath, encoding="utf-8").read()
    tree = ast.parse(source, filename=abspath)
    lines = source.splitlines()
    sinks: list[Sink] = []

    def _walk_func(func: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        subs = _leading_subcommands(func)
        runner = _text_uses_git_runner(ast.get_source_segment(source, func) or "")
        if subs and runner:
            # Find the line of the first list/tuple literal that leads with a
            # mutating subcommand (the "call site").
            call_line = func.lineno
            for n in ast.walk(func):
                elts = None
                if isinstance(n, (ast.List, ast.Tuple)):
                    elts = n.elts
                if elts and isinstance(elts[0], ast.Constant) and isinstance(elts[0].value, str):
                    first = elts[0].value
                    cmd = None
                    rest: list = []
                    if first == "git" and len(elts) > 1:
                        cmd = _elt_str(elts[1])
                        rest = elts[2:]
                    elif first != "git":
                        cmd = first
                        rest = elts[1:]
                    if cmd and _is_mutating_subcommand(cmd, rest):
                        call_line = n.lineno
                        break
            seg = lines[call_line - 1].strip() if call_line - 1 < len(lines) else ""
            anchor = hashlib.sha256(
                f"{relpath}|{func.name}|{subs[0]}|{seg}".encode("utf-8")
            ).hexdigest()[:16]
            sinks.append(
                Sink(
                    module=relpath,
                    function=func.name,
                    def_line=func.lineno,
                    call_line=call_line,
                    subcommands=tuple(subs),
                    source_anchor=anchor,
                )
            )

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _walk_func(node)
    return sinks


def scan_all() -> list[Sink]:
    out: list[Sink] = []
    for relpath in MODULES.values():
        out.extend(scan_module(relpath))
    return out


if __name__ == "__main__":
    import json

    for s in scan_all():
        print(json.dumps({
            "module": s.module,
            "function": s.function,
            "def_line": s.def_line,
            "call_line": s.call_line,
            "subcommands": list(s.subcommands),
            "anchor": s.source_anchor,
        }))
