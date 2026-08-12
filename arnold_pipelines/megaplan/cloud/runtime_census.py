"""Process-level execution map (the census): enumerate live arnold-ish processes.

Phase-0 deliverable of the fixer-unification design (``docs/
runtime-and-fixer-unification-design-20260807.md``): prove what is actually
running and from which tree BEFORE any runtime migration. This is a REPEATABLE
tool, not a one-off probe.

Read-only by design — safe to run as root. It only scans ``/proc``, does
``os.stat``/``readlink`` on process metadata, and runs read-only ``git -C``
probes. It never writes, mutates, or deletes anything.

Privacy contract: environ VALUES are never printed. ``RuntimeProcess.environ``
carries only variable NAMES by default; ``include_values=True`` keeps values on
the dataclass for local debugging only, and ``render_census_markdown`` masks
them regardless. Any value assigned to a key-like name (KEY, TOKEN, SECRET,
PASSWORD, API) is masked as ``<redacted>`` everywhere, including command lines.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from arnold_pipelines.megaplan.cloud.runtime_attestation import (
    _git_branch,
    _git_revision,
    _sha256_file,
)

REDACTED = "<redacted>"

# Match set from the Phase-0 census: every live arnold-ish process. Same set the
# design's census used (watchdog / repair-loop / meta-repair / auditor /
# resident / superfixer and friends).
_CMDLINE_MATCH_RE = re.compile(
    r"arnold|megaplan|watchdog|repair|schedule|fixer|resident|superfixer",
    re.IGNORECASE,
)

# Tree-resolution SRC vars, in priority order (declared runtime wins over cwd).
_SRC_VAR_NAMES = (
    "MEGAPLAN_RUNTIME_SRC",
    "CLOUD_WATCHDOG_ARNOLD_SRC",
    "ARNOLD_SRC",
    "MEGAPLAN_AUDIT_ARNOLD_SRC",
    "MEGAPLAN_META_ARNOLD_SRC",
    # Retired selectors (T-0023/G5): kept so census redaction flags any
    # re-introduced read; runtime identity now comes from the manifest only.
    "KIMI_GOAL_ARNOLD_SRC",
    "MEGAPLAN_DISCORD_DM_ARNOLD_SRC",
    "MEGAPLAN_DISCOVER_ARNOLD_SRC",
)

# Key-like fragments: any variable/flag name containing one of these is secret
# (or a model-routing override), and its value is masked as <redacted>
# everywhere — even with include_values=True (review finding #5).
_KEYLIKE_FRAGMENT = r"(?:KEY|TOKEN|SECRET|PASSWORD|API|MODEL)"

_MOUNT_MATCH_RE = re.compile(r"arnold|runtime|workspace", re.IGNORECASE)

_ENV_ASSIGN_RE = re.compile(
    rf"\b([A-Za-z_][A-Za-z0-9_]*{_KEYLIKE_FRAGMENT}[A-Za-z0-9_]*)=("
    rf"\"[^\"]*\"|'[^']*'|[^\s'\"]+)",
    re.IGNORECASE,
)
_FLAG_EQUALS_RE = re.compile(
    rf"(?P<flag>--?[A-Za-z0-9_-]*{_KEYLIKE_FRAGMENT}[A-Za-z0-9_-]*)="
    rf"(?P<value>\"[^\"]*\"|'[^']*'|[^\s'\"]+)",
    re.IGNORECASE,
)
_FLAG_SPACE_RE = re.compile(
    rf"(?P<flag>--?[A-Za-z0-9_-]*{_KEYLIKE_FRAGMENT}[A-Za-z0-9_-]*)"
    rf"(?P<sep>\s+)(?P<value>\S+)",
    re.IGNORECASE,
)

_UNRESOLVED_DIRTY = -1


@dataclass(frozen=True)
class RuntimeProcess:
    """One live arnold-ish process and its resolved execution provenance.

    ``environ`` holds environ variable NAMES only unless ``include_values=True``
    (for local debugging; the markdown renderer masks values regardless).
    ``tree_dirty_count`` is ``-1`` when the git dirty probe failed (unknown),
    ``0`` for a clean tree, and the number of modified/untracked files otherwise.
    """

    pid: int
    ppid: int
    cmdline: str
    cwd: str
    exe: str
    environ: tuple[str, ...]
    tree_path: str
    tree_head: str
    tree_branch: str
    tree_dirty_count: int
    module_file: str
    module_digest: str
    include_values: bool = False


@dataclass(frozen=True)
class GitTreeState:
    """One immediate subdirectory of a runtime-candidates root."""

    tree_name: str
    head_sha: str
    branch: str
    dirty_count: int
    is_git: bool


@dataclass(frozen=True)
class MountRecord:
    """One arnold/runtime/workspace bind mount from /proc/self/mountinfo."""

    target: str
    source: str
    readonly: bool
    filesystem: str


# ── git probes (read-only) ──────────────────────────────────────────────────


def _git_toplevel(root: Path) -> str:
    """Return the git work-tree root for *root*, or empty when not in a repo."""
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_is_repo(root: Path) -> bool:
    """True when *root* is itself a git work-tree root (not merely inside one).

    ``--is-inside-work-tree`` alone would flag every subdirectory of a repo
    (e.g. ``tests/cloud`` inside the arnold worktree); a candidate tree must be
    the toplevel of its own repository.
    """
    toplevel = _git_toplevel(root)
    return bool(toplevel) and Path(toplevel).resolve(strict=False) == root.resolve(
        strict=False
    )


def _git_dirty_count(root: Path) -> int:
    """Read-only dirty count: tracked modifications vs HEAD plus untracked files.

    Uses ``git diff --name-only HEAD`` and ``git ls-files --others
    --exclude-standard`` — both read-only — rather than ``git status``, which
    refreshes the index stat cache (a write to ``.git/index``). Returns ``-1``
    when either probe fails (unknown, e.g. an unborn branch).
    """
    modified = subprocess.run(
        ["git", "-C", str(root), "diff", "--name-only", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    untracked = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--others", "--exclude-standard"],
        check=False,
        capture_output=True,
        text=True,
    )
    if modified.returncode != 0 or untracked.returncode != 0:
        return _UNRESOLVED_DIRTY
    return len(
        [line for line in (modified.stdout + untracked.stdout).splitlines() if line.strip()]
    )


# ── /proc readers ───────────────────────────────────────────────────────────


def _read_cmdline(pid_dir: Path) -> str:
    try:
        raw = (pid_dir / "cmdline").read_bytes()
    except OSError:
        return ""
    return raw.replace(b"\0", b" ").decode("utf-8", "replace").strip()


def _read_ppid(pid_dir: Path) -> int:
    try:
        stat_text = (pid_dir / "stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    close = stat_text.rfind(")")
    if close < 0:
        return 0
    rest = stat_text[close + 1 :].split()
    if len(rest) < 2:
        return 0
    try:
        return int(rest[1])
    except ValueError:
        return 0


def _read_link(pid_dir: Path, name: str) -> str:
    try:
        return os.readlink(str(pid_dir / name))
    except OSError:
        return ""


def _read_environ_parts(pid_dir: Path) -> tuple[bytes, ...]:
    try:
        raw = (pid_dir / "environ").read_bytes()
    except OSError:
        return ()
    return tuple(part for part in raw.split(b"\0") if part)


def _env_map(parts: tuple[bytes, ...]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for part in parts:
        text = part.decode("utf-8", "replace")
        if "=" in text:
            name, value = text.split("=", 1)
            if name:
                mapping[name] = value
    return mapping


def _environ_entries(parts: tuple[bytes, ...], include_values: bool) -> tuple[str, ...]:
    entries: list[str] = []
    for part in parts:
        text = part.decode("utf-8", "replace")
        if not include_values:
            text = text.split("=", 1)[0]
        else:
            # include_values reveals values ONLY for non-key-like names;
            # values assigned to key-like names (KEY/TOKEN/SECRET/PASSWORD/
            # API/MODEL) are ALWAYS masked so raw credentials never land on
            # the public RuntimeProcess record.
            name, sep, value = text.partition("=")
            if sep and re.search(_KEYLIKE_FRAGMENT, name, re.IGNORECASE):
                text = f"{name}={REDACTED}"
        if text:
            entries.append(text)
    return tuple(sorted(entries))


def _mapped_module_candidates(pid_dir: Path) -> list[str]:
    """Loaded .py file paths from /proc/<pid>/maps, sorted for determinism."""
    try:
        text = (pid_dir / "maps").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    candidates: list[str] = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 6:
            continue
        pathname = " ".join(fields[5:])
        if pathname.endswith(" (deleted)"):
            pathname = pathname[: -len(" (deleted)")]
        if pathname.startswith("/") and pathname.endswith(".py"):
            candidates.append(pathname)
    return sorted(set(candidates))


def _resolve_module_file(pid_dir: Path, tree_path: str) -> str:
    """Best-effort loaded module file: maps first, then the tree's editable pointer.

    Preference: a mapped ``arnold_pipelines/megaplan/cloud`` python file (the
    fixer surface), then any mapped arnold-ish python file, then the first
    ``cloud/*.py`` under the resolved tree.
    """
    candidates = _mapped_module_candidates(pid_dir)
    for path in candidates:
        if "/megaplan/cloud/" in path:
            return path
    for path in candidates:
        if "arnold" in path:
            return path
    if tree_path:
        cloud_dir = Path(tree_path) / "arnold_pipelines" / "megaplan" / "cloud"
        try:
            files = sorted(cloud_dir.glob("*.py"))
        except OSError:
            files = []
        if files:
            return str(files[0])
    return ""


def _sha256_or_empty(path: str) -> str:
    if not path:
        return ""
    try:
        return _sha256_file(Path(path))
    except OSError:
        return ""


# ── process tree resolution ─────────────────────────────────────────────────


def _resolve_process_tree(env_map: dict[str, str], cwd: str) -> tuple[str, str, str, int]:
    """Resolve (tree_path, tree_head, tree_branch, dirty_count) for a process.

    The tree is the first non-empty SRC var, else the process cwd; the path is
    canonicalized to the git work-tree root when inside a repo. Git failures
    yield empty head/branch and dirty ``-1`` — the renderer records them as gaps.
    """
    candidate = ""
    for name in _SRC_VAR_NAMES:
        value = env_map.get(name, "").strip()
        if value:
            candidate = value
            break
    if not candidate and cwd:
        candidate = cwd
    if not candidate:
        return "", "", "", _UNRESOLVED_DIRTY
    root = _git_toplevel(Path(candidate))
    tree_path = root if root else candidate
    head = _git_revision(Path(tree_path))
    if not head:
        return tree_path, "", "", _UNRESOLVED_DIRTY
    branch = _git_branch(Path(tree_path))
    dirty = _git_dirty_count(Path(tree_path))
    return tree_path, head, branch, dirty


def _collect_process(pid_dir: Path, include_values: bool = False) -> RuntimeProcess | None:
    """Collect one process record from a /proc-like directory (the test seam).

    Returns ``None`` only when the process is unreadable (e.g. vanished, zombie
    with no cmdline). Every other probe failure degrades to an empty field that
    the renderer surfaces as a gap line.
    """
    cmdline = _read_cmdline(pid_dir)
    if not cmdline:
        return None
    environ_parts = _read_environ_parts(pid_dir)
    env_map = _env_map(environ_parts)
    cwd = _read_link(pid_dir, "cwd")
    exe = _read_link(pid_dir, "exe")
    tree_path, tree_head, tree_branch, tree_dirty = _resolve_process_tree(env_map, cwd)
    module_file = _resolve_module_file(pid_dir, tree_path)
    module_digest = _sha256_or_empty(module_file)
    return RuntimeProcess(
        pid=int(pid_dir.name),
        ppid=_read_ppid(pid_dir),
        cmdline=cmdline,
        cwd=cwd,
        exe=exe,
        environ=_environ_entries(environ_parts, include_values),
        tree_path=tree_path,
        tree_head=tree_head,
        tree_branch=tree_branch,
        tree_dirty_count=tree_dirty,
        module_file=module_file,
        module_digest=module_digest,
        include_values=include_values,
    )


# ── public census API ───────────────────────────────────────────────────────


def census_live_processes(include_values: bool = False) -> list[RuntimeProcess]:
    """Scan /proc for live arnold-ish processes (cmdline match set).

    Returns an empty list on non-Linux or when /proc is unreadable, so the tool
    degrades gracefully on a laptop or in tests.
    """
    if sys.platform != "linux" or not Path("/proc").is_dir():
        return []
    try:
        entries = sorted(Path("/proc").iterdir(), key=lambda p: p.name)
    except OSError:
        return []
    found: list[RuntimeProcess] = []
    for entry in entries:
        if not entry.name.isdigit():
            continue
        if not _CMDLINE_MATCH_RE.search(_read_cmdline(entry)):
            continue
        process = _collect_process(entry, include_values=include_values)
        if process is not None:
            found.append(process)
    return found


def census_git_trees(root: Path) -> list[GitTreeState]:
    """List immediate subdirectories of *root* with their git state.

    Hidden directories (dot-prefixed) are skipped; non-git directories are
    included with ``is_git=False`` so the report records them as gaps rather
    than silently omitting them.
    """
    root_path = Path(root)
    if not root_path.is_dir():
        return []
    states: list[GitTreeState] = []
    for child in sorted(root_path.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if _git_is_repo(child):
            head = _git_revision(child)
            states.append(
                GitTreeState(
                    tree_name=child.name,
                    head_sha=head,
                    branch=_git_branch(child),
                    dirty_count=_git_dirty_count(child),
                    is_git=True,
                )
            )
        else:
            states.append(
                GitTreeState(
                    tree_name=child.name,
                    head_sha="",
                    branch="",
                    dirty_count=_UNRESOLVED_DIRTY,
                    is_git=False,
                )
            )
    return states


def census_container_mounts() -> list[MountRecord]:
    """Best-effort read of arnold/runtime/workspace bind mounts.

    Pure /proc/self/mountinfo parsing; empty when not on Linux or when
    mountinfo is unreadable. ``readonly`` reflects the mount's ``ro`` option.
    """
    if sys.platform != "linux":
        return []
    mountinfo = Path("/proc/self/mountinfo")
    if not os.access(mountinfo, os.R_OK):
        return []
    records: list[MountRecord] = []
    try:
        text = mountinfo.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    for line in text.splitlines():
        fields = line.split()
        if "-" not in fields:
            continue
        dash = fields.index("-")
        mount_point = fields[4].replace("\\040", " ")
        fstype = fields[dash + 1]
        source = fields[dash + 2].replace("\\040", " ")
        options = fields[5]
        if not (_MOUNT_MATCH_RE.search(mount_point) or _MOUNT_MATCH_RE.search(source)):
            continue
        records.append(
            MountRecord(
                target=mount_point,
                source=source,
                readonly="ro" in options.split(","),
                filesystem=fstype,
            )
        )
    return sorted(records, key=lambda record: record.target)


# ── masking ─────────────────────────────────────────────────────────────────


def mask_cmdline(text: str) -> str:
    """Mask values assigned to key-like names (KEY/TOKEN/SECRET/PASSWORD/API).

    Covers ``NAME=value`` assignments, ``--flag=value``, and ``--flag value``
    forms. Non-secret content is returned unchanged.
    """
    masked = _FLAG_SPACE_RE.sub(
        lambda match: f"{match.group('flag')}{match.group('sep')}{REDACTED}",
        text,
    )
    masked = _FLAG_EQUALS_RE.sub(
        lambda match: f"{match.group('flag')}={REDACTED}",
        masked,
    )
    masked = _ENV_ASSIGN_RE.sub(
        lambda match: f"{match.group(1)}={REDACTED}",
        masked,
    )
    return masked


def _environ_names(environ: tuple[str, ...]) -> tuple[str, ...]:
    """Reduce environ entries to NAMES only — values are never rendered."""
    names: list[str] = []
    for entry in environ:
        name = entry.split("=", 1)[0]
        if name:
            names.append(name)
    return tuple(names)


def _cell(value: object) -> str:
    text = str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _derive_gaps(
    processes: list[RuntimeProcess],
    trees: list[GitTreeState],
) -> list[str]:
    gaps: list[str] = []
    for process in sorted(processes, key=lambda p: p.pid):
        if not process.cwd:
            gaps.append(f"pid {process.pid}: cwd unreadable")
        if not process.exe:
            gaps.append(f"pid {process.pid}: exe unreadable")
        if not process.tree_path:
            gaps.append(f"pid {process.pid}: no runtime SRC var / git tree resolved")
        elif not process.tree_head:
            gaps.append(f"pid {process.pid}: git tree unresolved at {process.tree_path}")
        if not process.module_file:
            gaps.append(f"pid {process.pid}: loaded module file not resolved")
        elif not process.module_digest:
            gaps.append(f"pid {process.pid}: module digest unreadable at {process.module_file}")
    for tree in sorted(trees, key=lambda t: t.tree_name):
        if not tree.is_git:
            gaps.append(f"tree {tree.tree_name}: not a git repository")
    return gaps


def render_census_markdown(
    processes: list[RuntimeProcess],
    trees: list[GitTreeState],
    mounts: list[MountRecord],
) -> str:
    """Render a deterministic markdown census report.

    Deterministic for identical inputs: every list is sorted before rendering.
    No environ values and no key-like values are ever emitted.
    """
    lines = [
        "# Runtime Census",
        "",
        "> Read-only snapshot. Environ values are never printed; values assigned "
        "to key-like names (KEY/TOKEN/SECRET/PASSWORD/API/MODEL) are masked.",
        "",
        f"## Processes ({len(processes)})",
        "",
        "| pid | ppid | cmdline | cwd | exe | tree_path | tree_head | branch | "
        "dirty | module_file | module_digest |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for process in sorted(processes, key=lambda p: p.pid):
        dirty = str(process.tree_dirty_count) if process.tree_dirty_count >= 0 else "-"
        environ = ", ".join(_environ_names(process.environ)) or "-"
        lines.append(
            "| {pid} | {ppid} | {cmdline} | {cwd} | {exe} | {tree_path} | "
            "{tree_head} | {tree_branch} | {dirty} | {module_file} | "
            "{module_digest} |".format(
                pid=_cell(process.pid),
                ppid=_cell(process.ppid),
                cmdline=_cell(mask_cmdline(process.cmdline)),
                cwd=_cell(process.cwd),
                exe=_cell(process.exe),
                tree_path=_cell(process.tree_path),
                tree_head=_cell(process.tree_head),
                tree_branch=_cell(process.tree_branch),
                dirty=_cell(dirty),
                module_file=_cell(process.module_file),
                module_digest=_cell(process.module_digest),
            )
        )
        lines.append(f"  - environ: {environ}")
    lines.extend(["", f"## Git trees ({len(trees)})", ""])
    if not trees:
        lines.append("_no trees scanned (pass --trees-root)_")
    else:
        lines.append("| tree | head | branch | dirty | is_git |")
        lines.append("|---|---|---|---|---|")
        for tree in sorted(trees, key=lambda t: t.tree_name):
            dirty = str(tree.dirty_count) if tree.dirty_count >= 0 else "-"
            lines.append(
                "| {name} | {head} | {branch} | {dirty} | {is_git} |".format(
                    name=_cell(tree.tree_name),
                    head=_cell(tree.head_sha),
                    branch=_cell(tree.branch),
                    dirty=_cell(dirty),
                    is_git=_cell(tree.is_git),
                )
            )
    lines.extend(["", f"## Bind mounts ({len(mounts)})", ""])
    if not mounts:
        lines.append("_none (not Linux or mountinfo unreadable)_")
    else:
        lines.append("| target | source | ro | fs |")
        lines.append("|---|---|---|---|")
        for mount in sorted(mounts, key=lambda m: m.target):
            lines.append(
                "| {target} | {source} | {ro} | {fs} |".format(
                    target=_cell(mount.target),
                    source=_cell(mount.source),
                    ro=_cell("ro" if mount.readonly else "rw"),
                    fs=_cell(mount.filesystem),
                )
            )
    gaps = _derive_gaps(processes, trees)
    lines.extend(["", f"## Gaps ({len(gaps)})", ""])
    if gaps:
        for gap in gaps:
            lines.append(f"- {gap}")
    else:
        lines.append("_no probe failures recorded_")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: print the census markdown and exit 0.

    Individual probe failures are recorded as gap lines and never crash the
    census. ``--include-values`` keeps environ values on the in-memory records
    for local debugging; the printed report still masks them.
    """
    parser = argparse.ArgumentParser(
        prog="runtime-census",
        description="Process-level execution map: prove what is running and from "
        "which tree before any runtime migration. Read-only.",
    )
    parser.add_argument(
        "--trees-root",
        type=Path,
        default=None,
        help="runtime-candidates root whose immediate git-repo subdirectories are "
        "enumerated (skipped when omitted)",
    )
    parser.add_argument(
        "--include-values",
        action="store_true",
        help="keep environ values on in-memory records for local debugging "
        "(the printed report still masks them)",
    )
    args = parser.parse_args(argv)
    processes = census_live_processes(include_values=args.include_values)
    trees = census_git_trees(args.trees_root) if args.trees_root is not None else []
    mounts = census_container_mounts()
    print(render_census_markdown(processes, trees, mounts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
