"""Shared, fail-closed admission of persisted relaunch commands.

The command itself remains a shell-wrapper concern.  This module owns the
decision whether a command persisted in a session marker may be reused.
"""

from __future__ import annotations

from collections.abc import Mapping
import os
import re


# G5 (rounds 2/5/10 findings 2): a persisted command must never re-select the
# SHARED /workspace/arnold checkout.  Pre-P4 builders wrote such commands into
# session markers; returning one verbatim would re-import from the shared root
# instead of the per-epic manifest runtime (residual builder selection).
# The admission covers the shared root in ANY command position — a PYTHONPATH
# or PATH entry, a `cd` target, an env-assignment value, or a python/binary
# invocation (bare, env-prefixed, exec'd, or quoted) — because every such
# token executes or imports from the shared checkout.  The match is
# token-boundary and path-component aware: a legitimate per-epic root such as
# /workspace/arnold-epics/... does NOT match, while /workspace/arnold (exact,
# prefix, suffix, quoted, or exported) and any /workspace/arnold/... subtree
# entry all do.  This subsumes the earlier PYTHONPATH-only (round-2) and
# cd-only (round-5) checks: assignment values are preceded by '=' or ':' and
# executable/script/cd targets by whitespace, a quote, or a shell separator.
_SHARED_ROOT_TOKEN_RE = re.compile(r"(?<![^\s\"'=:;&|({])/workspace/arnold(?![\w-])")

# G5 (round-11 finding 2): shell parameter expansion can smuggle the shared
# root past the token-boundary check above — the expansion operator
# characters ('-', '+', '?', '#', '%', '/') are not command boundaries, so
# /workspace/arnold inside ${VAR:-...}, ${VAR:=...}, ${VAR:+...}, or any
# other ${...} construct goes undetected.  Match the expansion context itself
# and require the path there too; per-epic roots still fail the (?![\w-])
# guard, so ${VAR:-/workspace/arnold-epics/...} stays admissible.
_SHARED_ROOT_PARAM_EXPANSION_RE = re.compile(r"\$\{[^}]*?/workspace/arnold(?![\w-])")

# G5 (round-11 finding 3): a persisted command must never reference a RETIRED
# runtime selector VARIABLE either — $MEGAPLAN_RUNTIME_SRC,
# $ARNOLD_REPAIR_RUNTIME_SRC, etc.  Pre-P4 builders persisted commands that
# expanded such a selector at relaunch time; returning one verbatim re-selects
# whatever runtime the ambient environment names instead of the per-epic
# manifest runtime (residual builder selection, same class as the literal
# shared-root checks above).  Admission rejects the variable in ANY command
# position and in both reference spellings shell accepts: bare `$NAME` and
# braced `${NAME...}` (defaults, assignments, substitutions, prefixes).  The
# match is name-boundary aware so a distinct variable that merely PREFIXES a
# retired name (e.g. ${MEGAPLAN_RUNTIME_SRC_EXTRA} or the non-selecting
# MEGAPLAN_SUPERVISOR_SOURCE_ROOT binding) is NOT rejected.  *_SYNC_BRANCH
# covers the retired branch selectors (CLOUD_WATCHDOG_SYNC_BRANCH,
# KIMI_GOAL_SYNC_BRANCH, MEGAPLAN_META_SYNC_BRANCH); the plain, manifest-derived
# SYNC_BRANCH is not a selector and stays admissible.
_RETIRED_SELECTOR_VAR_NAMES = (
    "MEGAPLAN_RUNTIME_SRC",
    "MEGAPLAN_LAUNCH_RUNTIME_SRC",
    "MEGAPLAN_SUPERVISOR_SOURCE",
    "ARNOLD_REPAIR_RUNTIME_SRC",
    "MEGAPLAN_DISCOVER_ARNOLD_SRC",
    "KIMI_GOAL_ARNOLD_SRC",
)
_RETIRED_SELECTOR_VAR_ALTERNATION = "|".join(
    re.escape(name) for name in _RETIRED_SELECTOR_VAR_NAMES
)
_RETIRED_SELECTOR_VAR_RE = re.compile(
    r"\$(?:"
    + _RETIRED_SELECTOR_VAR_ALTERNATION
    + r"|[A-Za-z_]\w*_SYNC_BRANCH)(?!\w)"
    r"|\$\{(?:"
    + _RETIRED_SELECTOR_VAR_ALTERNATION
    + r"|[A-Za-z_]\w*_SYNC_BRANCH)(?:[^}A-Za-z0-9_][^}]*)?\}"
)


# G5 (round-14 finding 1): the blacklists above only reject the SHARED
# /workspace/arnold checkout and RETIRED selector text — they cannot see a
# persisted command that names a DIFFERENT per-epic runtime (e.g. a command
# referencing /workspace/runtime-candidates/arnold-old while the manifest
# accepts arnold-new).  Returning such a command verbatim re-selects the
# stale runtime at relaunch (residual builder selection, same class as the
# shared-root checks).  When the accepted root is supplied, every absolute
# runtime-path reference in the persisted command — a `cd` target, an
# env-assignment value (PYTHONPATH and friends), an executable/script path
# (including a script invoked under a checkout's /arnold_pipelines/
# component), or a literal path inside a ${...} parameter expansion — must
# be the accepted root or a subpath of it; any other path marks the command
# stale so it is regenerated from the accepted root.  A command carrying no
# runtime-path reference (a pure `chain start` style) stays admissible.
# Non-runtime path positions (--project-dir/--spec arguments, redirect
# targets, [[ -f ... ]] file tests) are deliberately NOT scanned.
_ACCEPTED_ROOT_ASSIGNMENT_RE = re.compile(
    r"(?:^|[;&|({]\s*|\s)(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*="
    r"(?P<token>\"[^\"]*\"|'[^']*'|\S+)"
)
_ACCEPTED_ROOT_CD_RE = re.compile(r"\bcd\s+(?P<token>\"[^\"]*\"|'[^']*'|\S+)")
_ACCEPTED_ROOT_EXEC_RE = re.compile(
    r"(?:^|[;&|({]\s*|&&\s*|\|\|\s*|then\s+|do\s+|else\s+|\bexec\s+)"
    r"(?P<token>\"[^\"]*\"|'[^']*'|\S+)"
)
_ACCEPTED_ROOT_ENV_EXEC_RE = re.compile(
    r"\benv\s+(?:[^\s;&|]+=\S*\s+|[^\s;&|]+\s+)*?"
    r"(?P<token>\"[^\"]*\"|'[^']*'|\S+)"
)
_ACCEPTED_ROOT_PARAM_EXPANSION_RE = re.compile(r"\$\{[^}]*?(?P<path>/[^\s}]+)")
# A script invoked by an interpreter (``python -P <checkout>/arnold_pipelines/
# .../start.py``) executes that checkout's code, so the checkout root before
# the package component is a runtime reference (round-10 invocation class).
_ACCEPTED_ROOT_SCRIPT_PATH_RE = re.compile(r"(?P<root>/[^\s\"';&|()<>]*?)/arnold_pipelines/")


def _absolute_paths_in(token: str) -> list[str]:
    """Literal absolute paths inside one shell token.

    The token is a raw ``\\S+``/quoted capture; PYTHONPATH-style values are
    colon-separated, and a bare capture may have glued on a trailing shell
    word (``;``, ``&&``, a redirect, a flag) that a later position owns.
    """
    paths: list[str] = []
    for piece in re.split(r":", token):
        piece = piece.strip("\"'")
        if not piece.startswith("/"):
            continue
        piece = re.split(r"[;&|()<>\"]", piece, maxsplit=1)[0]
        piece = piece.rstrip("/")
        if piece:
            paths.append(piece)
    return paths


def _runtime_path_references(value: str) -> set[str]:
    """Absolute runtime-path references in *value* (runtime-selecting
    positions only: env-assignment values, cd targets, executable command
    words, and literal paths inside parameter expansions)."""
    refs: set[str] = set()
    for token_re in (
        _ACCEPTED_ROOT_ASSIGNMENT_RE,
        _ACCEPTED_ROOT_CD_RE,
        _ACCEPTED_ROOT_EXEC_RE,
        _ACCEPTED_ROOT_ENV_EXEC_RE,
    ):
        for match in token_re.finditer(value):
            refs.update(_absolute_paths_in(match.group("token")))
    for match in _ACCEPTED_ROOT_PARAM_EXPANSION_RE.finditer(value):
        refs.add(match.group("path").rstrip("/"))
    for match in _ACCEPTED_ROOT_SCRIPT_PATH_RE.finditer(value):
        refs.add(match.group("root").rstrip("/"))
    return refs


def _rejects_foreign_runtime_path(value: str, accepted_root: str | None) -> bool:
    """Return whether a command references a runtime path other than the
    accepted root.  Without an accepted root the comparison cannot run and
    the command stays admissible (the shared-root/selector blacklists above
    still apply)."""
    root = str(accepted_root or "").strip()
    if not root:
        return False
    root = os.path.normpath(root)
    for reference in _runtime_path_references(value):
        normalized = os.path.normpath(reference)
        if normalized == root or normalized.startswith(root + "/"):
            continue
        return True
    return False


_STALE_MARKER_FRAGMENTS = (
    "source checkout dirty; using clean runtime mirror",
    "source checkout has local commits not contained in origin/",
    "attempting push",
    'git -C "$SRC" push origin',
    "pip install ",
    "pip3 install ",
    "python -m pip install ",
    "python3 -m pip install ",
    "git push ",
    "git pull ",
    "git fetch ",
    "git clone ",
    "git checkout ",
    "git switch ",
    "git reset ",
    "git merge ",
    "git rebase ",
    "git commit ",
    "rm ",
    "mv ",
    "cp ",
    "touch ",
    "mkdir ",
    "chmod ",
    "chown ",
    "tee ",
    "sed -i ",
    " >>",
    " >",
)


def is_stale_marker_relaunch_command(
    command: str,
    accepted_root: str | None = None,
) -> bool:
    """Return whether a persisted command must be regenerated.

    When ``accepted_root`` is supplied (the manifest runtime root a relaunch
    must bind), any absolute runtime-path reference in the command — a `cd`
    target, an env-assignment value (PYTHONPATH and friends), an
    executable/script path, or a literal path inside a ${...} expansion —
    must be the accepted root or a subpath of it.  A reference to ANY other
    path (a different per-epic checkout, the shared root, a retired runtime
    mirror) marks the command stale so it is regenerated from the accepted
    root.  A command carrying no runtime-path reference (a pure `chain
    start` style) stays admissible.
    """
    value = str(command or "")
    if not value.strip():
        return True
    if any(fragment in value for fragment in _STALE_MARKER_FRAGMENTS):
        return True
    if "[megaplan-refresh] refusing editable install refresh:" in value:
        return True
    if re.search(
        r"git\s+(?:-C\s+\S+\s+)?(?:push|pull|fetch|clone|checkout|switch|reset|merge|rebase|commit)(?:\s|$)",
        value,
    ):
        return True
    if _SHARED_ROOT_TOKEN_RE.search(value):
        return True
    if _SHARED_ROOT_PARAM_EXPANSION_RE.search(value):
        return True
    if _RETIRED_SELECTOR_VAR_RE.search(value):
        return True
    if _rejects_foreign_runtime_path(value, accepted_root):
        return True
    return False


def relaunch_matches_runtime(
    command: str,
    identity: Mapping[str, object],
) -> bool:
    """Require a content-addressed relaunch command to name its bound runtime."""

    runtime_root = str(
        identity.get("import_root") or identity.get("editable_root") or ""
    ).strip()
    revision = str(
        identity.get("source_revision") or identity.get("editable_revision") or ""
    ).strip()
    if runtime_root and runtime_root not in command:
        return False
    if len(revision) == 40 and revision not in command:
        return False
    return True


def marker_relaunch_command(
    marker: Mapping[str, object],
    accepted_root: str | None = None,
) -> str | None:
    """Return the marker command only when it is current and admissible.

    ``accepted_root`` (the manifest runtime root) is threaded into the
    stale-marker predicate so a persisted command referencing a DIFFERENT
    per-epic runtime path is regenerated rather than returned verbatim.
    """
    command = str(
        marker.get("relaunch_command") or marker.get("launch_command") or ""
    ).strip()
    if is_stale_marker_relaunch_command(command, accepted_root):
        return None
    binding = marker.get("runtime_binding")
    identity = binding.get("current_identity") if isinstance(binding, Mapping) else None
    if isinstance(identity, Mapping) and not relaunch_matches_runtime(command, identity):
        # A content-addressed marker must relaunch the same immutable runtime.
        # Merely blacklist-checking the shell text admitted commands left over
        # from an earlier cutover.
        return None
    return command


__all__ = [
    "is_stale_marker_relaunch_command",
    "marker_relaunch_command",
    "relaunch_matches_runtime",
]
