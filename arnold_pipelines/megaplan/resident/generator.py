"""Deterministic resident-agent contract generator.

A *resident domain* is an operator persona that drives one external gateway
(such as the Astrid project gateway) on behalf of the megaplan resident.
For each domain the generator emits exactly four contracts:

1. **Domain agent prompt** — an omp agent-definition markdown file (YAML
   frontmatter plus the operator system prompt).  This is the file that is
   installed into ``.omp/agents/`` (project scope) or ``~/.omp/agent/agents/``
   (user scope) and discovered by omp's ``task``/``agent`` machinery.

2. **Policy contract** — tool/permission allowlist, credential environment
   variables, and the working-directory policy for the operator.

3. **Session contract** — session identity (``agent:<id>``), persistence,
   recovery, and concurrency (writer-epoch lease) rules.

4. **Evidence contract** — output normalization, typed media types, and
   ``MediaUsage`` cost emission into the resident store/ledger, plus
   supervision/heartbeat/delivery rules.

Generation is fully deterministic: the same domain definition always yields
byte-identical contract files, so the checked-in examples are reproducible
and the oracle can compare generated output against the committed artifacts.

Installation scope follows omp's agent discovery precedence
(project -> user -> bundled): project-scope installs land in ``.omp/agents/``
and shadow user-scope installs in ``~/.omp/agent/agents/``.  A project-scope
install of the same agent name is always the one that wins at runtime.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold_pipelines.megaplan.types import CliError


# ── Typed media vocabulary ──────────────────────────────────────────────────
# Content types the resident evidence contract records.  ``x-astrid-timeline``
# is the Astrid project timeline document type.

ASTrid_MEDIA_CONTENT_TYPES: tuple[str, ...] = (
    "video/mp4",
    "audio/wav",
    "x-astrid-timeline",
)


# ── Contract field names (stable keys, used by tests and docs) ─────────────

POLICY_CONTRACT_KEYS: tuple[str, ...] = (
    "contract",
    "domain",
    "tools",
    "permissions",
    "credentials",
    "cwd",
)
SESSION_CONTRACT_KEYS: tuple[str, ...] = (
    "contract",
    "domain",
    "identity",
    "persistence",
    "recovery",
    "concurrency",
)
EVIDENCE_CONTRACT_KEYS: tuple[str, ...] = (
    "contract",
    "domain",
    "output_normalization",
    "typed_media",
    "media_usage",
    "supervision",
    "heartbeat",
    "delivery",
)


class ResidentDomain:
    """Immutable description of one resident domain used by the generator."""

    __slots__ = (
        "slug",
        "agent_name",
        "description",
        "tools",
        "model",
        "thinking_level",
        "gateway_command",
        "credentials",
        "cwd_policy",
        "prompt_body",
    )

    def __init__(
        self,
        *,
        slug: str,
        agent_name: str,
        description: str,
        tools: Sequence[str],
        model: str = "@task",
        thinking_level: str = "medium",
        gateway_command: Sequence[str] = (),
        credentials: Mapping[str, str] = {},
        cwd_policy: Mapping[str, Any] = {},
        prompt_body: str,
    ) -> None:
        if not slug or not slug.isalnum():
            raise CliError("invalid_args", f"domain slug must be alphanumeric: {slug!r}")
        if not agent_name:
            raise CliError("invalid_args", "agent_name must be non-empty")
        self.slug = slug
        self.agent_name = agent_name
        self.description = description
        self.tools = tuple(tools)
        self.model = model
        self.thinking_level = thinking_level
        self.gateway_command = tuple(gateway_command)
        self.credentials = dict(credentials)
        self.cwd_policy = dict(cwd_policy)
        self.prompt_body = prompt_body.strip()


# ── Contract builders ───────────────────────────────────────────────────────


def _frontmatter_lines(domain: ResidentDomain) -> list[str]:
    lines = [
        "---",
        f"name: {domain.agent_name}",
        f"description: {domain.description}",
        "tools: " + ", ".join(domain.tools),
        f"model: {domain.model}",
        f"thinking-level: {domain.thinking_level}",
        "---",
        "",
    ]
    return lines


def build_domain_prompt(domain: ResidentDomain) -> str:
    """Contract 1 — the omp agent-definition markdown file."""
    parts: list[str] = _frontmatter_lines(domain)
    if domain.prompt_body:
        parts.append(domain.prompt_body.rstrip())
        parts.append("")
    return "\n".join(parts)


def build_policy_contract(domain: ResidentDomain) -> str:
    """Contract 2 — tool/permission, credential, and cwd policy (YAML)."""
    gateway = " ".join(domain.gateway_command) if domain.gateway_command else f"{domain.agent_name} next"
    tool_list = "\n".join(f"    - {tool}" for tool in domain.tools)
    cred_list = "\n".join(
        f"    - {var}  # {purpose}" for var, purpose in sorted(domain.credentials.items())
    )
    cwd_lines = "\n".join(
        f"    {key}: {value}" for key, value in sorted(domain.cwd_policy.items())
    )
    return f"""# {domain.slug} resident — tool/permission, credential, and cwd policy
# Generated deterministically by arnold_pipelines.megaplan.resident.generator.
contract: resident-policy
domain: {domain.slug}
tools:
{tool_list}
permissions:
    - gateway actions returned by `{gateway}` are the ONLY
      legal actions; never freelance outside the returned command
    - file tools constrained to the run directory ({domain.cwd_policy.get('run_root_template', '<run-root>')})
credentials:
{cred_list}
cwd:
{cwd_lines}
"""


def build_session_contract(domain: ResidentDomain) -> str:
    """Contract 3 — session identity, persistence, recovery, concurrency (YAML)."""
    gateway = " ".join(domain.gateway_command) if domain.gateway_command else f"{domain.agent_name} next"
    status_cmd = gateway.replace(" next", " status", 1)
    return f"""# {domain.slug} resident — session identity, persistence, recovery, concurrency
# Generated deterministically by arnold_pipelines.megaplan.resident.generator.
contract: resident-session
domain: {domain.slug}
identity:
    agent_id: agent:{domain.agent_name}
    attaches: projects/<slug>/
    operates: runs/<slug>/
persistence:
    store: megaplan resident store (FileStore/DBStore)
    artifacts: run-relative artifact root
    cursor: resume_cursor.json under the run root
recovery:
    reorient: `{status_cmd}` after restart or uncertainty
    resume: read the persisted resume cursor and re-enter the gateway loop
concurrency:
    writer_epoch: obey lease writer-epoch rules on conflict
    takeover: only through the supported session takeover protocol
    never: run two operators against the same run
"""


def build_evidence_contract(domain: ResidentDomain) -> str:
    """Contract 4 — evidence/output normalization, typed media, supervision.

    Typed media outputs (``video/mp4``, ``audio/wav``, ``x-astrid-timeline``)
    are recorded as evidence records in the resident store together with the
    ``MediaUsage`` cost entries that account for them.  Notifications,
    heartbeat, watchdog, and restart-recovery paths all consume the same
    evidence records from the store, so emission into the store is the single
    write surface.
    """
    media_list = "\n".join(f"    - {content_type}" for content_type in ASTrid_MEDIA_CONTENT_TYPES)
    gateway = " ".join(domain.gateway_command) if domain.gateway_command else f"{domain.agent_name} next"
    return f"""# {domain.slug} resident — evidence/output normalization, typed media, supervision
# Generated deterministically by arnold_pipelines.megaplan.resident.generator.
contract: resident-evidence
domain: {domain.slug}
output_normalization:
    gateway_action: execute exactly the one legal action returned by
        `{gateway}` (bootstrap, run: ..., or ack ...)
    artifact: emit one normalized evidence record per produced artifact
typed_media:
{media_list}
media_usage:
    unit: video_second | audio_second | image | token | timeline_document
    emit: MediaUsage record with the producing tool call and cost entries
supervision:
    ledger: append evidence to the resident ledger
    heartbeat: every turn touches the heartbeat after evidence emission
    watchdog: evidence records are visible to the watchdog custody sweep
delivery:
    manifest: evidence is serialized into the resident manifest
    restart_recovery: evidence survives restart via the resident store
"""


# ── Deterministic generation ────────────────────────────────────────────────


def generate_domain_contracts(
    domain: ResidentDomain,
) -> dict[str, str]:
    """Return the four contract texts keyed by stable output file names."""
    return {
        f"{domain.agent_name}.md": build_domain_prompt(domain),
        f"{domain.slug}-policy.yaml": build_policy_contract(domain),
        f"{domain.slug}-session.yaml": build_session_contract(domain),
        f"{domain.slug}-evidence.yaml": build_evidence_contract(domain),
    }


def contracts_digest(contracts: Mapping[str, str]) -> str:
    """Stable digest over the ordered contract texts (for tests/audit)."""
    digest = hashlib.sha256()
    for name in sorted(contracts):
        digest.update(name.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(contracts[name].encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()


# ── Installation scopes ─────────────────────────────────────────────────────

USER_AGENTS_DIR = "~/.omp/agent/agents"
PROJECT_AGENTS_DIR = ".omp/agents"


def _user_agents_dir() -> Path:
    return Path(USER_AGENTS_DIR).expanduser()


def _project_agents_dir(project_root: Path) -> Path:
    return project_root / PROJECT_AGENTS_DIR


def resolve_install_dirs(project_root: Path, scope: str) -> tuple[Path, ...]:
    """Return the install directories for the requested scope.

    ``project`` installs into ``<project_root>/.omp/agents`` and shadows the
    user scope (``~/.omp/agent/agents``); ``user`` installs only into the user
    directory.  omp resolution precedence is project -> user -> bundled.
    """
    if scope == "project":
        return (_project_agents_dir(project_root),)
    if scope == "user":
        return (_user_agents_dir(),)
    raise CliError("invalid_args", f"unknown install scope: {scope!r}")


def install_contracts(
    contracts: Mapping[str, str],
    *,
    project_root: Path,
    scope: str,
) -> list[Path]:
    """Write the contracts into the scope's agents directory.

    Returns the written paths.  Project-scope installs always shadow user
    scope for the same agent name at omp runtime.
    """
    written: list[Path] = []
    for install_dir in resolve_install_dirs(project_root, scope):
        install_dir.mkdir(parents=True, exist_ok=True)
        for name, text in sorted(contracts.items()):
            target = install_dir / name
            target.write_text(text, encoding="utf-8")
            written.append(target)
    return written
