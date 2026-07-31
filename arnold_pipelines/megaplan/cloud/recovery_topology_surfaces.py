"""M11 route-authority surface schema and Python/command scanner adapters.

Step 25 (route-authority surface schema): defines the surface classes, states,
owner/expiry/target-step fields, and zero-positive-authority proof requirements
that gate every later route-authority migration.  A surface may only be
classified as non-authoritative (planned-pending, historical-report-only, or
closed) when it carries an ``owner``, an ``expiry``, a ``target_step``, and a
``ZeroPositiveAuthorityProof`` that explicitly forbids deriving authority from
labels, liveness, WBC receipts, or rebuildable projections.

Step 26 (Python and command-authority scanner adapters): statically detects the
live repair-authority surfaces that must be migrated before final route closure:

* Python call sites — ``subprocess.run/Popen/call/check_output/check_call``,
  ``exec``, ``os.system``, ``shutil.which``, ``RepairRunner`` (class definition
  and ``.run()`` invocations), direct repair-queue calls
  (``enqueue_repair_request`` / ``enqueue_human_gate_repair_request``), and the
  enqueue producers that wrap them.
* Command-authority surfaces — ``arnold-repair-trigger``, ``trigger_once``,
  direct ``python -m arnold_pipelines.megaplan <repair-subcommand>`` module
  launches, and the legacy ``arnold-repair-loop`` wrapper.

Step 27 (shell repair-authority scanner adapter): statically detects shell-based
legacy repair surfaces that must be migrated before final route closure:

* Watchdog, auditor, meta, and Kimi module launches from shell.
* Legacy repair-loop relaunch and wrapper-loop patterns.
* Tmux-based long-running repair sessions.
* Bash heredoc-delimited inline repair scripts.
* Shell wrapper functions and alias definitions that materialize repair.

Step 28 (systemd repair-authority scanner adapter): statically detects systemd
repair surfaces:

* Path, service, and timer unit file references.
* Systemctl enable/start/stop commands targeting repair units.
* Systemd-run invocations that wrap repair logic.
* Unit dependency directives (Wants/Requires/After/BindsTo/PartOf) that
  chain repair services.

Step 29 (template/ensure scanner adapter): statically detects deployment
template and ensure-script repair surfaces:

* Deployment templates (Jinja2, cloud-init, shell-substitution) that
  reference repair commands.
* Rendered entrypoints (cloud-init runcmd/bootcmd, ignition, user-data).
* Ensure/guarantee/verify scripts that materialize repair authority.
* Wrapper materializers — Makefile targets, Dockerfile ENTRYPOINT/CMD,
  and CI pipeline repair-gate steps.

Detected surfaces are recorded as ``LIVE_AUTHORITY`` until a later migration
step supplies owner/expiry/target-step/proof and reclassifies them.  The scanner
never *grants* authority: it enumerates concrete static call sites that already
exist.  It cannot promote a label, a liveness signal, a WBC receipt, or a
rebuildable projection into authority — those derivation paths are forbidden by
``ZeroPositiveAuthorityProof`` and are not consulted by any detector.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


# ── Schema: surface states ─────────────────────────────────────────────────


class SurfaceState(str, Enum):
    """Lifecycle state of a recovery-topology authority surface.

    * ``LIVE_AUTHORITY`` — a concrete call site / command surface that currently
      grants repair authority.  These are the surfaces that must be migrated
      before final route closure.  A live surface must NOT carry a zero-authority
      proof: doing so would be self-contradictory.
    * ``PLANNED_PENDING`` — scheduled for migration but not yet closed.  Requires
      owner, expiry, target_step, and a complete zero-authority proof.
    * ``HISTORICAL_REPORT_ONLY`` — a historical reference with no live authority
      (e.g. a retired command documented for audit).  Requires the full closure
      evidence so a stale label can never masquerade as retired.
    * ``CLOSED`` — migrated / fully closed.  Requires the full closure evidence.
    """

    LIVE_AUTHORITY = "live_authority"
    PLANNED_PENDING = "planned_pending"
    HISTORICAL_REPORT_ONLY = "historical_report_only"
    CLOSED = "closed"


class SurfaceFamily(str, Enum):
    """Which scanner adapter produced a surface.

    Step 25 defines the full family set so later scanner steps (27-32) populate
    adapters against a stable schema rather than inventing their own.
    """

    PYTHON_COMMAND = "python_command"
    SHELL = "shell"
    SYSTEMD = "systemd"
    TEMPLATE = "template"
    HOT_UPLOAD = "hot_upload"
    SIMULATION = "simulation"
    MARKDOWN = "markdown"


class ForbiddenAuthoritySource(str, Enum):
    """Authority-derivation paths that may NEVER grant repair authority.

    A zero-positive-authority proof must affirmatively forbid every one of these.
    This enum is the single source of truth for the SC19 contract: no detector,
    classifier, or proof may turn any of these into positive repair authority.
    """

    LABEL = "label"
    LIVENESS = "liveness"
    WBC_RECEIPT = "wbc_receipt"
    REBUILDABLE_PROJECTION = "rebuildable_projection"


#: The complete set of forbidden authority sources.  A zero-authority proof is
#: only "complete" when it forbids every member of this set.
ALL_FORBIDDEN_AUTHORITY_SOURCES: frozenset[ForbiddenAuthoritySource] = frozenset(
    ForbiddenAuthoritySource
)


# ── Schema: zero-positive-authority proof ──────────────────────────────────


@dataclass(frozen=True)
class ZeroPositiveAuthorityProof:
    """Proof that a surface grants zero positive repair authority.

    Required to retire (planned-pending / historical-report-only / close) any
    surface.  The proof is only *complete* when it forbids every
    :class:`ForbiddenAuthoritySource`, so a surface can never be silently
    retired on the strength of a label, a liveness signal, a WBC receipt, or a
    rebuildable projection.
    """

    proof_kind: str
    """How the absence of positive authority was established (e.g.
    ``static_call_site_inventory``, ``runtime_trace_absence``,
    ``installed_runtime_canary``)."""

    evidence_ref: str
    """Content-addressed reference to the evidence backing this proof."""

    forbids: tuple[ForbiddenAuthoritySource, ...] = ()
    """Every forbidden authority source this proof explicitly covers.  A
    complete proof lists all of :data:`ALL_FORBIDDEN_AUTHORITY_SOURCES`."""

    verified_at: str = ""
    """Optional ISO-8601 timestamp of the last verification."""

    def __post_init__(self) -> None:
        if not self.proof_kind:
            raise ValueError("ZeroPositiveAuthorityProof.proof_kind is required")
        if not self.evidence_ref:
            raise ValueError("ZeroPositiveAuthorityProof.evidence_ref is required")
        if not self.forbids:
            raise ValueError(
                "ZeroPositiveAuthorityProof.forbids must enumerate at least one "
                "ForbiddenAuthoritySource"
            )
        for src in self.forbids:
            if not isinstance(src, ForbiddenAuthoritySource):
                raise ValueError(
                    f"forbids entry {src!r} is not a ForbiddenAuthoritySource"
                )

    def is_complete(self) -> bool:
        """True iff the proof forbids every forbidden authority source."""
        return ALL_FORBIDDEN_AUTHORITY_SOURCES.issubset(frozenset(self.forbids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_kind": self.proof_kind,
            "evidence_ref": self.evidence_ref,
            "forbids": sorted(s.value for s in self.forbids),
            "verified_at": self.verified_at,
            "complete": self.is_complete(),
        }


# ── Schema: authority surface ──────────────────────────────────────────────


#: Fields every non-live surface must populate before it may be retired.
REQUIRED_NON_LIVE_FIELDS: tuple[str, ...] = (
    "owner",
    "expiry",
    "target_step",
    "zero_authority_proof",
)


@dataclass(frozen=True)
class AuthoritySurface:
    """A single recovery-topology surface that may carry repair authority.

    Live authority surfaces are emitted by the scanners with no proof.  To move
    a surface out of ``LIVE_AUTHORITY`` the migration must populate
    ``owner``/``expiry``/``target_step`` and attach a *complete*
    :class:`ZeroPositiveAuthorityProof`; the ``__post_init__`` invariant enforces
    this so a half-evidenced retirement is impossible to construct.
    """

    family: SurfaceFamily
    state: SurfaceState
    kind: str
    """Specific detection kind, e.g. ``python.subprocess.run`` or
    ``command.arnold-repair-trigger``."""

    location: str
    """File path (and optional ``:line``) where the surface lives."""

    surface_id: str = ""
    """Stable identifier; auto-derived from family/kind/location when empty."""

    content_hash: str = ""
    """SHA-256 of the exact source fragment detected at ``location``.

    ``surface_id`` deliberately remains stable when content changes at the same
    location.  Closure therefore binds both identity and content: changing a
    call without moving it produces a content mismatch instead of silently
    inheriting the old closure.
    """

    owner: str = ""
    """Accountable owner for a non-live surface."""

    expiry: str = ""
    """ISO-8601 date by which the migration/proof must be re-verified."""

    target_step: str = ""
    """Plan step that owns closing this surface (e.g. ``Step 41``)."""

    zero_authority_proof: Optional[ZeroPositiveAuthorityProof] = None
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.surface_id:
            # Frozen dataclass: bypass __setattr__ via object.__setattr__.
            object.__setattr__(self, "surface_id", _derive_surface_id(self))
        if not self.content_hash:
            object.__setattr__(
                self,
                "content_hash",
                _hash_surface_content(self.detail),
            )
        if self.state is SurfaceState.LIVE_AUTHORITY:
            if self.zero_authority_proof is not None:
                raise ValueError(
                    f"LIVE_AUTHORITY surface {self.surface_id!r} must not carry a "
                    "zero-authority proof; a live surface grants authority by "
                    "definition and cannot simultaneously prove zero authority"
                )
            return
        # Non-authoritative states require the full closure evidence.
        missing = [
            name
            for name in ("owner", "expiry", "target_step")
            if not getattr(self, name)
        ]
        if missing:
            raise ValueError(
                f"{self.state.value} surface {self.surface_id!r} is missing required "
                f"closure fields {missing}; authority may not be retired without them"
            )
        if self.zero_authority_proof is None:
            raise ValueError(
                f"{self.state.value} surface {self.surface_id!r} requires a "
                "ZeroPositiveAuthorityProof; authority may not be retired on a label"
            )
        if not self.zero_authority_proof.is_complete():
            raise ValueError(
                f"{self.state.value} surface {self.surface_id!r} carries an "
                "incomplete zero-authority proof; it must forbid every "
                "ForbiddenAuthoritySource (label, liveness, wbc_receipt, "
                "rebuildable_projection)"
            )

    def to_dict(self) -> dict[str, Any]:
        proof = None if self.zero_authority_proof is None else self.zero_authority_proof.to_dict()
        return {
            "surface_id": self.surface_id,
            "content_hash": self.content_hash,
            "family": self.family.value,
            "state": self.state.value,
            "kind": self.kind,
            "location": self.location,
            "owner": self.owner,
            "expiry": self.expiry,
            "target_step": self.target_step,
            "zero_authority_proof": proof,
            "detail": self.detail,
        }


def _derive_surface_id(surface: AuthoritySurface) -> str:
    raw = "|".join(
        (surface.family.value, surface.kind, surface.location)
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _hash_surface_content(content: str) -> str:
    """Return a full content-address for one detected source fragment."""
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


# ── Step 26: Python AST scanner adapter ────────────────────────────────────

#: ``(module, attr)`` call pairs and the detection kind they map to.
_ATTR_CALL_KINDS: dict[tuple[str, str], str] = {
    ("subprocess", "run"): "python.subprocess.run",
    ("subprocess", "Popen"): "python.subprocess.Popen",
    ("subprocess", "call"): "python.subprocess.call",
    ("subprocess", "check_output"): "python.subprocess.check_output",
    ("subprocess", "check_call"): "python.subprocess.check_call",
    ("os", "system"): "python.os.system",
    ("shutil", "which"): "python.shutil.which",
}

#: Direct ``Name(...)`` calls and the detection kind they map to.
_NAME_CALL_KINDS: dict[str, str] = {
    "exec": "python.exec",
    "enqueue_repair_request": "python.queue.enqueue_repair_request",
    "enqueue_human_gate_repair_request": "python.queue.enqueue_human_gate_repair_request",
}

#: Attribute calls (``module.enqueue_repair_request``) that materialize queue
#: authority regardless of the receiver module.
_QUEUE_ATTRS: frozenset[str] = frozenset(
    {"enqueue_repair_request", "enqueue_human_gate_repair_request"}
)

#: Variable names that, when assigned from ``RepairRunner(...)``, mark a
#: ``.run()`` call as a ``RepairRunner.run`` authority surface.
_REPAIR_RUNNER_CLASS = "RepairRunner"

#: All detection kinds emitted by the Python AST scanner.
PYTHON_DETECTION_KINDS: tuple[str, ...] = (
    "python.subprocess.run",
    "python.subprocess.Popen",
    "python.subprocess.call",
    "python.subprocess.check_output",
    "python.subprocess.check_call",
    "python.os.system",
    "python.shutil.which",
    "python.exec",
    "python.RepairRunner.class",
    "python.RepairRunner.run",
    "python.queue.enqueue_repair_request",
    "python.queue.enqueue_human_gate_repair_request",
    "python.enqueue_producer",
)


class _PythonAuthorityVisitor(ast.NodeVisitor):
    """Collect live repair-authority surfaces from a single Python AST."""

    def __init__(self, location: str, source: str) -> None:
        self.location = location
        self.source = source
        self.surfaces: list[AuthoritySurface] = []
        self._scope_stack: list[tuple[str, int, str]] = []
        self._runner_names: set[str] = set()
        self._producers: dict[str, tuple[int, str]] = {}

    # -- scope tracking ---------------------------------------------------

    def _current_scope(self) -> tuple[str, int, str]:
        return (
            self._scope_stack[-1]
            if self._scope_stack
            else ("<module>", 0, "")
        )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._scope_stack.append(
            (
                node.name,
                node.lineno,
                ast.get_source_segment(self.source, node)
                or f"{node.name}:{node.lineno}",
            )
        )
        self.generic_visit(node)
        self._scope_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    # -- class / assignment tracking -------------------------------------

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if node.name == _REPAIR_RUNNER_CLASS:
            self._add(
                "python.RepairRunner.class",
                node.lineno,
                detail=f"class {node.name}",
                content=ast.get_source_segment(self.source, node),
            )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        ctor = _repair_runner_constructor_name(node.value)
        if ctor is not None:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self._runner_names.add(target.id)
        self.generic_visit(node)

    # -- call detection ---------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        kind = self._classify_call(node)
        if kind is not None:
            self._add(
                kind,
                node.lineno,
                detail=kind,
                content=ast.get_source_segment(self.source, node),
            )
            if kind.startswith("python.queue."):
                scope_name, scope_line, scope_content = self._current_scope()
                if scope_name != "<module>":
                    # Record the enclosing function as an enqueue producer.
                    self._producers.setdefault(
                        scope_name,
                        (scope_line, scope_content),
                    )
        self.generic_visit(node)

    # -- helpers ----------------------------------------------------------

    def _classify_call(self, node: ast.Call) -> Optional[str]:
        func = node.func
        if isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name):
                key = (func.value.id, func.attr)
                mapped = _ATTR_CALL_KINDS.get(key)
                if mapped is not None:
                    return mapped
            if func.attr == "run" and isinstance(func.value, ast.Name):
                if (
                    func.value.id == _REPAIR_RUNNER_CLASS
                    or func.value.id in self._runner_names
                ):
                    return "python.RepairRunner.run"
            if func.attr in _QUEUE_ATTRS:
                return f"python.queue.{func.attr}"
            return None
        if isinstance(func, ast.Name):
            return _NAME_CALL_KINDS.get(func.id)
        return None

    def _add(
        self,
        kind: str,
        lineno: int,
        *,
        detail: str = "",
        content: str | None = None,
    ) -> None:
        location = f"{self.location}:{lineno}" if lineno else self.location
        self.surfaces.append(
            AuthoritySurface(
                family=SurfaceFamily.PYTHON_COMMAND,
                state=SurfaceState.LIVE_AUTHORITY,
                kind=kind,
                location=location,
                content_hash=_hash_surface_content(
                    detail if content is None else content
                ),
                detail=detail,
            )
        )

    def finish(self) -> list[AuthoritySurface]:
        """Emit enqueue-producer surfaces after the walk completes."""
        for name, (line, content) in sorted(
            self._producers.items(),
            key=lambda kv: (kv[1][0], kv[0]),
        ):
            self._add(
                "python.enqueue_producer",
                line,
                detail=f"producer:{name}",
                content=content,
            )
        # Deduplicate by surface_id while preserving order.
        seen: set[str] = set()
        unique: list[AuthoritySurface] = []
        for surface in self.surfaces:
            if surface.surface_id in seen:
                continue
            seen.add(surface.surface_id)
            unique.append(surface)
        return unique


def _repair_runner_constructor_name(value: ast.AST) -> Optional[str]:
    """Return the constructor name if *value* is a ``RepairRunner(...)`` call."""
    if not isinstance(value, ast.Call):
        return None
    func = value.func
    if isinstance(func, ast.Name) and func.id == _REPAIR_RUNNER_CLASS:
        return _REPAIR_RUNNER_CLASS
    if isinstance(func, ast.Attribute) and func.attr == _REPAIR_RUNNER_CLASS:
        return _REPAIR_RUNNER_CLASS
    return None


def scan_python_source(source: str, location: str) -> list[AuthoritySurface]:
    """Detect live Python repair-authority surfaces in *source*.

    *location* is an opaque label (typically a file path) attached to each
    emitted surface.  Returns surfaces in ``LIVE_AUTHORITY`` state.
    """
    tree = ast.parse(source)
    visitor = _PythonAuthorityVisitor(location, source)
    visitor.visit(tree)
    return visitor.finish()


# ── Step 26: command-authority scanner adapter ────────────────────────────

#: ``(kind, compiled_pattern)`` pairs for command-authority surfaces.  These are
#: text patterns so the adapter works on Python string literals, shell scripts,
#: rendered templates, and Markdown alike.
_COMMAND_AUTHORITY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "command.arnold-repair-trigger",
        re.compile(r"\barnold-repair-trigger\b"),
    ),
    (
        "command.arnold-repair-loop",
        re.compile(r"\barnold-repair-loop\b"),
    ),
    (
        "command.trigger_once",
        re.compile(r"\btrigger_once\b"),
    ),
    (
        "command.python_module_repair",
        re.compile(
            r"python(?:3)?\b[^\n|]*?-m\s+arnold_pipelines\.megaplan\b"
            r"[^\n]*?\b(doctor|auto|resume)\b"
        ),
    ),
)

#: All detection kinds emitted by the command-authority scanner.
COMMAND_AUTHORITY_DETECTION_KINDS: tuple[str, ...] = tuple(
    kind for kind, _ in _COMMAND_AUTHORITY_PATTERNS
)


def scan_command_authority(text: str, location: str) -> list[AuthoritySurface]:
    """Detect command-authority surfaces in arbitrary *text*.

    Matches ``arnold-repair-trigger``, ``arnold-repair-loop``, ``trigger_once``,
    and direct ``python -m arnold_pipelines.megaplan <repair-subcommand>``
    module launches.  Returns surfaces in ``LIVE_AUTHORITY`` state.
    """
    surfaces: list[AuthoritySurface] = []
    for kind, pattern in _COMMAND_AUTHORITY_PATTERNS:
        for match in pattern.finditer(text):
            lineno = text.count("\n", 0, match.start()) + 1
            surfaces.append(
                AuthoritySurface(
                    family=SurfaceFamily.PYTHON_COMMAND,
                    state=SurfaceState.LIVE_AUTHORITY,
                    kind=kind,
                    location=f"{location}:{lineno}",
                    detail=match.group(0),
                )
            )
    return surfaces


def scan_python_file(
    path: Path,
    *,
    location: str | None = None,
) -> list[AuthoritySurface]:
    """Scan a single Python file with both adapters.

    AST-unparseable files still receive command-authority text scanning so a
    syntax glitch cannot hide a command string.
    """
    text = path.read_text(encoding="utf-8")
    location = str(path) if location is None else location
    surfaces: list[AuthoritySurface] = []
    try:
        surfaces.extend(scan_python_source(text, location))
    except SyntaxError:
        pass
    surfaces.extend(scan_command_authority(text, location))
    # Step 30/31 overlays: Python files (e.g. ``scripts/cloud_hot_upload.py``)
    # also materialize hot-upload/session-exec authority and simulation success
    # gates, so those text adapters are applied alongside the AST adapter.
    surfaces.extend(scan_hot_upload_authority(text, location))
    surfaces.extend(scan_simulation_authority(text, location))
    # Deduplicate by surface_id (an AST call and its command-string literal at
    # the same line can both surface).
    seen: set[str] = set()
    unique: list[AuthoritySurface] = []
    for surface in surfaces:
        if surface.surface_id in seen:
            continue
        seen.add(surface.surface_id)
        unique.append(surface)
    return unique


# ── Step 27: Shell repair-authority scanner adapter ─────────────────────────

#: ``(kind, compiled_pattern)`` pairs for shell-based repair authority.
#: These patterns detect legacy shell scripts, bash wrappers, heredoc-delimited
#: repair launchers, tmux-based long-running repair sessions, and direct module
#: invocations from shell (watchdog, auditor, meta, Kimi, repair-loop relaunch).
_SHELL_AUTHORITY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # ── repair/watchdog/auditor/meta/Kimi module launches ──────────────
    (
        "shell.watchdog_repair",
        re.compile(
            r"(?:python(?:3)?\s+(?:-m\s+)?arnold_pipelines\.megaplan\.watchdog\b"
            r"|arnold-watchdog\b)"
        ),
    ),
    (
        "shell.auditor_repair",
        re.compile(
            r"(?:python(?:3)?\s+(?:-m\s+)?arnold_pipelines\.megaplan\.audits?\b"
            r"|arnold-auditor\b)"
        ),
    ),
    (
        "shell.meta_repair",
        re.compile(
            r"(?:python(?:3)?\s+(?:-m\s+)?arnold_pipelines\.megaplan\.meta\b"
            r"|arnold-meta-repair\b)"
        ),
    ),
    (
        "shell.kimi_repair",
        re.compile(
            r"(?:python(?:3)?\s+(?:-m\s+)?arnold_pipelines\.megaplan\.kimi\b"
            r"|arnold-kimi\b)"
        ),
    ),
    (
        "shell.module_repair",
        re.compile(
            r"python(?:3)?\s+-m\s+arnold_pipelines\.megaplan\b"
            r"[^\n]*?\b(?:doctor|auto|resume|repair|fix|heal)\b"
        ),
    ),
    # ── legacy repair-loop relaunch patterns ───────────────────────────
    (
        "shell.repair_loop_relaunch",
        re.compile(
            r"(?:nohup\s+)?(?:bash\s+)?(?:\./)?arnold-repair-loop\b"
            r"|(?:exec\s+)?arnold-repair-loop\s"
        ),
    ),
    (
        "shell.repair_loop_wrapper",
        re.compile(
            r"(?:while\s+true|for\s+\S+\s+in|until)\s*;?\s*do\b"
            r"[^\n]*?\b(?:arnold-repair|trigger_once|enqueue_repair)"
        ),
    ),
    # ── tmux-based repair sessions ─────────────────────────────────────
    (
        "shell.tmux_repair",
        re.compile(
            r"tmux\s+[^\n]*?\b(?:arnold|repair|doctor|auto|resume)\b"
        ),
    ),
    # ── bash heredoc / inline repair scripts ───────────────────────────
    (
        "shell.heredoc_repair",
        re.compile(
            r"(?:bash|sh)\s+(?:-c\s+)?(?:<<|<<-)\s*\w+\s*$",
            re.MULTILINE,
        ),
    ),
    # ── wrapper materializers (bash functions / aliases that wrap repair) ──
    (
        "shell.wrapper_function",
        re.compile(
            r"(?:function\s+)?\w*(?:repair|doctor|heal|fix)\w*\s*\(\s*\)\s*\{"
        ),
    ),
    (
        "shell.alias_repair",
        re.compile(
            r"alias\s+\w*(?:repair|doctor|heal|fix)\w*="
        ),
    ),
)

#: All detection kinds emitted by the shell scanner.
SHELL_DETECTION_KINDS: tuple[str, ...] = tuple(
    kind for kind, _ in _SHELL_AUTHORITY_PATTERNS
)


def scan_shell_authority(text: str, location: str) -> list[AuthoritySurface]:
    """Detect shell-based repair-authority surfaces in arbitrary *text*.

    Matches watchdog/auditor/meta/Kimi module launches, repair-loop relaunch
    patterns, tmux-based repair sessions, heredoc repair scripts, and shell
    wrapper functions/aliases that materialize repair authority.

    Returns surfaces in ``LIVE_AUTHORITY`` state.
    """
    surfaces: list[AuthoritySurface] = []
    for kind, pattern in _SHELL_AUTHORITY_PATTERNS:
        for match in pattern.finditer(text):
            lineno = text.count("\n", 0, match.start()) + 1
            surfaces.append(
                AuthoritySurface(
                    family=SurfaceFamily.SHELL,
                    state=SurfaceState.LIVE_AUTHORITY,
                    kind=kind,
                    location=f"{location}:{lineno}",
                    detail=match.group(0).strip(),
                )
            )
    return surfaces


# ── Step 28: Systemd repair-authority scanner adapter ───────────────────────

#: ``(kind, compiled_pattern)`` pairs for systemd-based repair authority.
#: Detects unit file references (.path, .service, .timer), systemctl
#: enable/start/stop commands targeting repair units, and systemd-run
#: invocations that wrap repair logic.
_SYSTEMD_AUTHORITY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # ── systemd path units (trigger repair on filesystem events) ──────
    (
        "systemd.path_unit_repair",
        re.compile(
            r"\b(?:arnold|repair|doctor|heal).*?\.path\b"
        ),
    ),
    # ── systemd service units ──────────────────────────────────────────
    (
        "systemd.service_unit_repair",
        re.compile(
            r"\b(?:arnold|repair|doctor|heal|watchdog).*?\.service\b"
        ),
    ),
    # ── systemd timer units ────────────────────────────────────────────
    (
        "systemd.timer_unit_repair",
        re.compile(
            r"\b(?:arnold|repair|doctor|heal).*?\.timer\b"
        ),
    ),
    # ── systemctl enable/start/stop targeting repair units ─────────────
    (
        "systemd.systemctl_repair",
        re.compile(
            r"systemctl\s+(?:enable|start|stop|restart|reload|daemon-reload)\s+"
            r"[^\n]*?\b(?:arnold|repair|doctor|watchdog|heal)"
        ),
    ),
    # ── systemd-run wrapping repair invocations ────────────────────────
    (
        "systemd.systemd_run_repair",
        re.compile(
            r"systemd-run\b[^\n]*?\b(?:arnold|repair|doctor|heal)"
        ),
    ),
    # ── Wants/Requires/After directives that chain repair units ────────
    (
        "systemd.unit_dependency_repair",
        re.compile(
            r"^\s*(?:Wants|Requires|After|Before|BindsTo|PartOf)\s*=\s*"
            r"[^\n]*?\b(?:arnold|repair|doctor|heal)",
            re.MULTILINE,
        ),
    ),
)

#: All detection kinds emitted by the systemd scanner.
SYSTEMD_DETECTION_KINDS: tuple[str, ...] = tuple(
    kind for kind, _ in _SYSTEMD_AUTHORITY_PATTERNS
)


def scan_systemd_authority(text: str, location: str) -> list[AuthoritySurface]:
    """Detect systemd-based repair-authority surfaces in arbitrary *text*.

    Matches .path/.service/.timer unit file references, systemctl commands
    targeting repair units, systemd-run invocations, and unit dependency
    directives that chain repair services.

    Returns surfaces in ``LIVE_AUTHORITY`` state.
    """
    surfaces: list[AuthoritySurface] = []
    for kind, pattern in _SYSTEMD_AUTHORITY_PATTERNS:
        for match in pattern.finditer(text):
            lineno = text.count("\n", 0, match.start()) + 1
            surfaces.append(
                AuthoritySurface(
                    family=SurfaceFamily.SYSTEMD,
                    state=SurfaceState.LIVE_AUTHORITY,
                    kind=kind,
                    location=f"{location}:{lineno}",
                    detail=match.group(0).strip(),
                )
            )
    return surfaces


# ── Step 29: Template and ensure scanner adapter ────────────────────────────

#: ``(kind, compiled_pattern)`` pairs for template/ensure-based repair authority.
#: Detects deployment templates (Jinja2, shell-substitution, cloud-init) that
#: reference repair paths, rendered entrypoints, ensure/guarantee scripts, and
#: wrapper materializers.
_TEMPLATE_AUTHORITY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # ── deployment templates referencing repair commands ───────────────
    (
        "template.deploy_repair_ref",
        re.compile(
            r"\{\{[^}]*?\b(?:arnold|repair|doctor|heal|trigger_once)"
            r"[^}]*?\}\}"
        ),
    ),
    # ── rendered entrypoints (cloud-init, user-data, ignition) ────────
    (
        "template.cloud_init_repair",
        re.compile(
            r"(?:runcmd|bootcmd|write_files)\s*:\s*[^\n]*?\b"
            r"(?:arnold|repair|doctor|heal|trigger)"
        ),
    ),
    # ── shell-substitution templates ───────────────────────────────────
    (
        "template.shell_subst_repair",
        re.compile(
            r"\$\{[^}]*?\b(?:arnold|repair|doctor|heal)\b[^}]*?\}"
        ),
    ),
    # ── ensure / guarantee scripts ─────────────────────────────────────
    (
        "template.ensure_script",
        re.compile(
            r"\b(?:ensure|guarantee|assert|verify)_(?:repair|heal|doctor|fix)\w*",
            re.IGNORECASE,
        ),
    ),
    # ── wrapper materializers (Makefiles, Dockerfiles, CI configs) ─────
    (
        "template.makefile_repair",
        re.compile(
            r"^\s*(?:repair|doctor|heal|fix|auto-resume)\s*:",
            re.MULTILINE,
        ),
    ),
    (
        "template.docker_repair",
        re.compile(
            r"(?:ENTRYPOINT|CMD)\s+[^\n]*?\b(?:arnold|repair|doctor|heal|trigger)"
        ),
    ),
    # ── CI / pipeline repair gate steps ────────────────────────────────
    (
        "template.ci_repair_gate",
        re.compile(
            r"(?:run|script|command)\s*:\s*[^\n]*?\b"
            r"(?:arnold-repair|trigger_once|python\s+-m\s+arnold_pipelines\.megaplan)"
        ),
    ),
)

#: All detection kinds emitted by the template scanner.
TEMPLATE_DETECTION_KINDS: tuple[str, ...] = tuple(
    kind for kind, _ in _TEMPLATE_AUTHORITY_PATTERNS
)


def scan_template_authority(text: str, location: str) -> list[AuthoritySurface]:
    """Detect template/ensure-based repair-authority surfaces in arbitrary *text*.

    Matches deployment template references to repair commands, cloud-init
    / rendered entrypoints, shell-substitution patterns, ensure/guarantee
    scripts, Makefile/Dockerfile repair targets, and CI pipeline repair gates.

    Returns surfaces in ``LIVE_AUTHORITY`` state.
    """
    surfaces: list[AuthoritySurface] = []
    for kind, pattern in _TEMPLATE_AUTHORITY_PATTERNS:
        for match in pattern.finditer(text):
            lineno = text.count("\n", 0, match.start()) + 1
            surfaces.append(
                AuthoritySurface(
                    family=SurfaceFamily.TEMPLATE,
                    state=SurfaceState.LIVE_AUTHORITY,
                    kind=kind,
                    location=f"{location}:{lineno}",
                    detail=match.group(0).strip(),
                )
            )
    return surfaces


# ── Shared dedupe helper ────────────────────────────────────────────────────


def _dedupe_surfaces(surfaces: list[AuthoritySurface]) -> list[AuthoritySurface]:
    """Deduplicate surfaces by ``surface_id`` while preserving first-seen order."""
    seen: set[str] = set()
    unique: list[AuthoritySurface] = []
    for surface in surfaces:
        if surface.surface_id in seen:
            continue
        seen.add(surface.surface_id)
        unique.append(surface)
    return unique


# ── Step 30: Hot-upload scanner adapter ──────────────────────────────────────

#: ``(kind, compiled_pattern)`` pairs for hot-upload / session-exec repair
#: authority.  Detects legacy-bin upload destinations, caller-supplied session
#: commands, ``exec {command}`` strings, and explicit upload overrides that
#: materialize repair authority by pushing or restarting a live repair binary
#: or tmux session (see ``scripts/cloud_hot_upload.py``).
_HOT_UPLOAD_AUTHORITY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # ── legacy-bin upload destinations ──────────────────────────────────
    (
        "hot_upload.legacy_bin_destination",
        re.compile(r"/usr/local/bin/arnold-[\w-]+|\bREMOTE_BIN_DIR\b"),
    ),
    # ── caller-supplied session commands ────────────────────────────────
    (
        "hot_upload.session_command",
        re.compile(
            r"--session-command\b|parse_session_commands\b|session[-_]command\b"
        ),
    ),
    # ── exec {command} strings (docker exec, remote exec into a container) ──
    (
        "hot_upload.exec_command",
        re.compile(r"docker\s+exec\b|\bexec\s+[^=\n]{0,60}?bash\s+-l[a-z]*"),
    ),
    # ── explicit upload / restart / wrapper overrides ───────────────────
    (
        "hot_upload.upload_override",
        re.compile(
            r"--(?:upload|restart-session|wrapper|env-name|env-file)\b"
        ),
    ),
)

#: All detection kinds emitted by the hot-upload scanner.
HOT_UPLOAD_DETECTION_KINDS: tuple[str, ...] = tuple(
    kind for kind, _ in _HOT_UPLOAD_AUTHORITY_PATTERNS
)


def scan_hot_upload_authority(text: str, location: str) -> list[AuthoritySurface]:
    """Detect hot-upload / session-exec repair-authority surfaces in *text*.

    Matches legacy-bin upload destinations, caller-supplied session commands,
    ``exec {command}`` strings, and explicit upload/restart/wrapper overrides
    that materialize repair authority by pushing or restarting a live repair
    binary or session.  Returns surfaces in ``LIVE_AUTHORITY`` state.
    """
    surfaces: list[AuthoritySurface] = []
    for kind, pattern in _HOT_UPLOAD_AUTHORITY_PATTERNS:
        for match in pattern.finditer(text):
            lineno = text.count("\n", 0, match.start()) + 1
            surfaces.append(
                AuthoritySurface(
                    family=SurfaceFamily.HOT_UPLOAD,
                    state=SurfaceState.LIVE_AUTHORITY,
                    kind=kind,
                    location=f"{location}:{lineno}",
                    detail=match.group(0).strip(),
                )
            )
    return surfaces


# ── Step 31: Simulation scanner adapter ──────────────────────────────────────

#: Markers that a text block is a simulation / dry-run context.  A return-code
#: success gate is only flagged when at least one of these appears in the text,
#: so an ordinary ``x == 0`` comparison is never mistaken for repair authority.
_SIMULATION_CONTEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"--dry-run\b"),
    re.compile(r"\bdry[-_ ]?run\b"),
    re.compile(r"\bsimulate[(_\s]"),
    re.compile(r"\bsimulation\b"),
    re.compile(r"\brun_simulation\b"),
)

#: ``(kind, compiled_pattern)`` pairs for simulation repair-authority surfaces.
_SIMULATION_AUTHORITY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # simulation / dry-run subprocess invocations
    (
        "simulation.dry_run_subprocess",
        re.compile(
            r"--dry-run\b|dry[-_ ]?run\b|simulate[(_\s]|simulation\b|run_simulation\b"
        ),
    ),
)

#: Return-code success gates.  Only flagged inside a simulation context so the
#: scanner never manufactures authority from a plain numeric comparison.
_RETURN_CODE_SUCCESS_PATTERN = re.compile(
    r"\.returncode\s*==\s*0\b|\.returncode\s*!=\s*0\b|\breturncode\s*==\s*0\b"
)

#: All detection kinds emitted by the simulation scanner.
SIMULATION_DETECTION_KINDS: tuple[str, ...] = (
    "simulation.dry_run_subprocess",
    "simulation.returncode_success_gate",
)


def simulation_success_cannot_publish_accepted_repair() -> dict[str, Any]:
    """Prove a simulation subprocess return-code success is NOT accepted repair.

    A return-code zero from a simulated/dry-run subprocess is a *liveness*
    signal (the process exited) and a *rebuildable projection* (re-running the
    simulation may differ).  Both are :class:`ForbiddenAuthoritySource` members,
    so no detector, migration, or proof may promote a simulation success into
    positive repair authority.  This written proof is embedded in the baseline
    so a future migration cannot quietly derive authority from a return code.
    """
    return {
        "claim": (
            "A simulation/dry-run subprocess return-code success cannot publish "
            "accepted repair."
        ),
        "reason": (
            "Return-code success is a liveness signal (process exit) and a "
            "rebuildable projection (re-running the simulation may differ); both "
            "are ForbiddenAuthoritySource members and may never grant repair "
            "authority."
        ),
        "forbids": sorted(
            {
                ForbiddenAuthoritySource.LIVENESS.value,
                ForbiddenAuthoritySource.REBUILDABLE_PROJECTION.value,
            }
        ),
        "requires_instead": (
            "Accepted repair must come from a deterministic verifier receipt "
            "emitted by the canonical runner, never from a simulation return code."
        ),
    }


def scan_simulation_authority(text: str, location: str) -> list[AuthoritySurface]:
    """Detect simulation success-path repair-authority surfaces in *text*.

    Matches simulation/dry-run subprocess invocations and, only when the text is
    in a simulation context, the return-code success gates that could otherwise
    be misread as accepted repair.  The scanner never grants authority from a
    return code — see :func:`simulation_success_cannot_publish_accepted_repair`.
    Returns surfaces in ``LIVE_AUTHORITY`` state.
    """
    surfaces: list[AuthoritySurface] = []
    for kind, pattern in _SIMULATION_AUTHORITY_PATTERNS:
        for match in pattern.finditer(text):
            lineno = text.count("\n", 0, match.start()) + 1
            surfaces.append(
                AuthoritySurface(
                    family=SurfaceFamily.SIMULATION,
                    state=SurfaceState.LIVE_AUTHORITY,
                    kind=kind,
                    location=f"{location}:{lineno}",
                    detail=match.group(0).strip(),
                )
            )
    if any(pattern.search(text) for pattern in _SIMULATION_CONTEXT_PATTERNS):
        for match in _RETURN_CODE_SUCCESS_PATTERN.finditer(text):
            lineno = text.count("\n", 0, match.start()) + 1
            surfaces.append(
                AuthoritySurface(
                    family=SurfaceFamily.SIMULATION,
                    state=SurfaceState.LIVE_AUTHORITY,
                    kind="simulation.returncode_success_gate",
                    location=f"{location}:{lineno}",
                    detail=match.group(0).strip(),
                )
            )
    return surfaces


# ── Step 32: Markdown scanner adapter ────────────────────────────────────────

#: Operator-facing Markdown roots the scanner must cover before final route
#: closure.  Missing any of these would leave a documented live command
#: un-inventoried.  ``docs`` reaches ``docs/ops/tiered-repair-and-audit-loop.md``;
#: the package-local ``arnold_pipelines/megaplan/data`` root reaches skill/data
#: Markdown, generated ``_codex_skills``, and ``auditor_signal_swarm_briefs``.
MARKDOWN_SCAN_ROOTS: tuple[str, ...] = (
    "docs",
    "arnold_pipelines/megaplan/data",
    "arnold_pipelines/megaplan/cloud/rollout.md",
    "README.md",
)

#: Inline repair-command references that, when documented in operator-facing
#: Markdown, mark the file as carrying repair-authority documentation.
_MARKDOWN_COMMAND_REF_PATTERN = re.compile(
    r"\b(?:arnold-repair-trigger|arnold-repair-loop|trigger_once"
    r"|arnold-watchdog\b|arnold-auditor\b|arnold-kimi\b|arnold-meta-repair\b"
    r"|python(?:3)?\s+-m\s+arnold_pipelines\.megaplan\b"
    r"[^\n`]{0,80}?\b(?:doctor|auto|resume|repair|fix|heal)\b)"
)

class _FencedBlock:
    __slots__ = ("start_line", "content")

    def __init__(self, start_line: int, content: str) -> None:
        self.start_line = start_line
        self.content = content


def _iter_fenced_blocks(text: str):
    """Yield :class:`_FencedBlock` for each fenced code block in *text*.

    ``start_line`` is 1-indexed.  Unterminated fences are treated as closed at
    end-of-text so a truncated operator doc still surfaces its block.
    """
    lines = text.splitlines()
    n = len(lines)
    i = 0
    while i < n:
        match = re.match(r"^([`~]{3,})", lines[i])
        if not match:
            i += 1
            continue
        fence_char = match.group(1)[0]
        min_width = len(match.group(1))
        start_line = i + 1
        body: list[str] = []
        j = i + 1
        closed = False
        while j < n:
            close = re.match(rf"^[{re.escape(fence_char)}]{{{min_width},}}\s*$", lines[j])
            if close:
                closed = True
                break
            body.append(lines[j])
            j += 1
        yield _FencedBlock(start_line=start_line, content="\n".join(body))
        i = j + 1 if closed else j


#: All detection kinds emitted by the Markdown scanner.
MARKDOWN_DETECTION_KINDS: tuple[str, ...] = (
    "markdown.repair_command_reference",
    "markdown.fenced_repair_block",
)


def scan_markdown_authority(text: str, location: str) -> list[AuthoritySurface]:
    """Detect repair-authority surfaces documented in operator-facing Markdown.

    Matches inline repair-command references and fenced code blocks that contain
    a repair command.  Operator docs that describe how to run a live repair
    command are authority surfaces: an operator following the doc materializes
    repair.  Returns surfaces in ``LIVE_AUTHORITY`` state.
    """
    surfaces: list[AuthoritySurface] = []
    for match in _MARKDOWN_COMMAND_REF_PATTERN.finditer(text):
        lineno = text.count("\n", 0, match.start()) + 1
        surfaces.append(
            AuthoritySurface(
                family=SurfaceFamily.MARKDOWN,
                state=SurfaceState.LIVE_AUTHORITY,
                kind="markdown.repair_command_reference",
                location=f"{location}:{lineno}",
                detail=match.group(0).strip(),
            )
        )
    for block in _iter_fenced_blocks(text):
        if _MARKDOWN_COMMAND_REF_PATTERN.search(block.content):
            surfaces.append(
                AuthoritySurface(
                    family=SurfaceFamily.MARKDOWN,
                    state=SurfaceState.LIVE_AUTHORITY,
                kind="markdown.fenced_repair_block",
                location=f"{location}:{block.start_line}",
                content_hash=_hash_surface_content(block.content),
                detail="fenced_repair_block",
            )
            )
    return _dedupe_surfaces(surfaces)


def scan_markdown_file(
    path: Path,
    *,
    location: str | None = None,
) -> list[AuthoritySurface]:
    """Scan a single Markdown file with the Markdown + command + hot-upload adapters.

    Markdown code blocks frequently embed shell commands and hot-upload
    overrides, so those text adapters are overlaid in addition to the Markdown
    adapter itself.
    """
    text = path.read_text(encoding="utf-8")
    location = str(path) if location is None else location
    surfaces: list[AuthoritySurface] = []
    surfaces.extend(scan_markdown_authority(text, location))
    surfaces.extend(scan_command_authority(text, location))
    surfaces.extend(scan_hot_upload_authority(text, location))
    return _dedupe_surfaces(surfaces)


# ── Unified file scanner ────────────────────────────────────────────────────


def scan_text_file(
    path: Path,
    *,
    location: str | None = None,
) -> list[AuthoritySurface]:
    """Scan a non-Python text file with shell, systemd, and template adapters.

    Use this for ``.sh``, ``.bash``, ``.service``, ``.timer``, ``.path``,
    ``.yaml``, ``.yml``, ``.j2``, ``Dockerfile``, ``Makefile``, and CI configs.
    """
    text = path.read_text(encoding="utf-8")
    location = str(path) if location is None else location
    surfaces: list[AuthoritySurface] = []
    surfaces.extend(scan_shell_authority(text, location))
    surfaces.extend(scan_systemd_authority(text, location))
    surfaces.extend(scan_template_authority(text, location))
    # Step 30 overlay: deployment templates and rendered entrypoints may carry
    # docker exec / upload overrides that materialize hot-upload authority.
    surfaces.extend(scan_hot_upload_authority(text, location))
    # Deduplicate by surface_id.
    seen: set[str] = set()
    unique: list[AuthoritySurface] = []
    for surface in surfaces:
        if surface.surface_id in seen:
            continue
        seen.add(surface.surface_id)
        unique.append(surface)
    return unique


# ── Schema descriptor / evidence emission ──────────────────────────────────


def schema_descriptor() -> dict[str, Any]:
    """Deterministic, machine-readable description of the surface schema.

    Used by ``scripts/check_recovery_topology_surfaces.py`` to emit and validate
    ``evidence/m11-recovery-topology-surfaces.json``.  Contains no timestamps so
    the descriptor is byte-stable across runs.
    """
    return {
        "schema_version": 1,
        "module": "arnold_pipelines.megaplan.cloud.recovery_topology_surfaces",
        "plan_steps": [
            "Step 25",
            "Step 26",
            "Step 27",
            "Step 28",
            "Step 29",
            "Step 30",
            "Step 31",
            "Step 32",
        ],
        "states": sorted(state.value for state in SurfaceState),
        "surface_families": sorted(family.value for family in SurfaceFamily),
        "forbidden_authority_sources": sorted(
            source.value for source in ForbiddenAuthoritySource
        ),
        "required_non_live_fields": list(REQUIRED_NON_LIVE_FIELDS),
        "zero_authority_proof_contract": (
            "A non-live surface requires a ZeroPositiveAuthorityProof that forbids "
            "every forbidden_authority_source; authority may never be derived from "
            "a label, liveness, a WBC receipt, or a rebuildable projection."
        ),
        "live_authority_contract": (
            "LIVE_AUTHORITY surfaces carry no zero-authority proof; they are "
            "concrete static call sites that currently grant repair authority and "
            "must be migrated before final route closure."
        ),
        "python_detection_kinds": list(PYTHON_DETECTION_KINDS),
        "command_authority_detection_kinds": list(COMMAND_AUTHORITY_DETECTION_KINDS),
        "shell_detection_kinds": list(SHELL_DETECTION_KINDS),
        "systemd_detection_kinds": list(SYSTEMD_DETECTION_KINDS),
        "template_detection_kinds": list(TEMPLATE_DETECTION_KINDS),
        "hot_upload_detection_kinds": list(HOT_UPLOAD_DETECTION_KINDS),
        "simulation_detection_kinds": list(SIMULATION_DETECTION_KINDS),
        "markdown_detection_kinds": list(MARKDOWN_DETECTION_KINDS),
        "markdown_scan_roots": list(MARKDOWN_SCAN_ROOTS),
    }


def dump_schema_descriptor(path: str | Path) -> dict[str, Any]:
    """Write the schema descriptor to *path* and return it."""
    descriptor = schema_descriptor()
    payload = json.dumps(descriptor, indent=2, sort_keys=True) + "\n"
    Path(path).write_text(payload, encoding="utf-8")
    return descriptor


# ── Step 33: Pre-migration route-authority baseline ──────────────────────────

#: The plan steps whose scanner adapters feed the pre-migration baseline.  This
#: is the deterministic coverage contract that migration consumes.
BASELINE_PLAN_STEPS: tuple[str, ...] = (
    "Step 25",
    "Step 26",
    "Step 27",
    "Step 28",
    "Step 29",
    "Step 30",
    "Step 31",
    "Step 32",
)


def build_route_authority_baseline(
    surfaces: list[AuthoritySurface],
    scan_roots: dict[str, list[str]],
    *,
    emitted_before_migration: bool = True,
) -> dict[str, Any]:
    """Build the deterministic pre-migration route-authority baseline payload.

    The baseline is emitted *before* any repair migration consumes it, so every
    inventoried surface must be ``LIVE_AUTHORITY`` unless it already carries a
    full retirement proof (owner + expiry + target_step + a complete
    ``ZeroPositiveAuthorityProof``).  The payload is sorted and timestamp-free,
    so it is byte-stable across runs (deterministic).
    """
    ordered = _dedupe_surfaces(list(surfaces))
    by_family: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    for surface in ordered:
        by_family[surface.family.value] = by_family.get(surface.family.value, 0) + 1
        by_kind[surface.kind] = by_kind.get(surface.kind, 0) + 1
    non_live = [s for s in ordered if s.state is not SurfaceState.LIVE_AUTHORITY]
    return {
        "schema_version": 1,
        "baseline_kind": "pre_migration_route_authority_baseline",
        "module": "arnold_pipelines.megaplan.cloud.recovery_topology_surfaces",
        "plan_steps_covered": list(BASELINE_PLAN_STEPS),
        "emitted_before_migration": bool(emitted_before_migration),
        "forbidden_authority_sources": sorted(
            source.value for source in ForbiddenAuthoritySource
        ),
        "scanner_families": sorted(family.value for family in SurfaceFamily),
        "scan_roots": {key: sorted(values) for key, values in scan_roots.items()},
        "summary": {
            "total_surfaces": len(ordered),
            "by_family": dict(sorted(by_family.items())),
            "by_kind": dict(sorted(by_kind.items())),
            "non_live_surface_count": len(non_live),
        },
        "simulation_success_proof": simulation_success_cannot_publish_accepted_repair(),
        "surfaces": [surface.to_dict() for surface in ordered],
        "validation": {
            "all_surfaces_are_live_authority": len(non_live) == 0,
            "non_live_surfaces_require_owner_expiry_target_step_and_complete_proof": True,
            "baseline_is_deterministic": True,
        },
        "schema": schema_descriptor(),
    }


def dump_baseline(
    path: str | Path,
    surfaces: list[AuthoritySurface],
    scan_roots: dict[str, list[str]],
    *,
    emitted_before_migration: bool = True,
) -> dict[str, Any]:
    """Write the pre-migration route-authority baseline to *path* and return it."""
    payload = build_route_authority_baseline(
        surfaces,
        scan_roots,
        emitted_before_migration=emitted_before_migration,
    )
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    Path(path).write_text(text, encoding="utf-8")
    return payload


__all__ = [
    "ALL_FORBIDDEN_AUTHORITY_SOURCES",
    "AuthoritySurface",
    "BASELINE_PLAN_STEPS",
    "COMMAND_AUTHORITY_DETECTION_KINDS",
    "ForbiddenAuthoritySource",
    "HOT_UPLOAD_DETECTION_KINDS",
    "MARKDOWN_DETECTION_KINDS",
    "MARKDOWN_SCAN_ROOTS",
    "PYTHON_DETECTION_KINDS",
    "REQUIRED_NON_LIVE_FIELDS",
    "SHELL_DETECTION_KINDS",
    "SIMULATION_DETECTION_KINDS",
    "SYSTEMD_DETECTION_KINDS",
    "TEMPLATE_DETECTION_KINDS",
    "SurfaceFamily",
    "SurfaceState",
    "ZeroPositiveAuthorityProof",
    "build_route_authority_baseline",
    "dump_baseline",
    "dump_schema_descriptor",
    "scan_command_authority",
    "scan_hot_upload_authority",
    "scan_markdown_authority",
    "scan_markdown_file",
    "scan_python_file",
    "scan_python_source",
    "scan_shell_authority",
    "scan_simulation_authority",
    "scan_systemd_authority",
    "scan_template_authority",
    "scan_text_file",
    "schema_descriptor",
    "simulation_success_cannot_publish_accepted_repair",
]
