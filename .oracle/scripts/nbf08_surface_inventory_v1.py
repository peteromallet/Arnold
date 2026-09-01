#!/usr/bin/env python3
"""Generate and strictly validate the frozen NBF08 S7 surface inventory."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

EXPECTED_SHA = "e7882d57ed32a237ad0aa6f0774ea35776717e6891a5724d4e97360f0618d5d8"
GENERATOR_VERSION = "nbf08-surface-inventory-v1"
SCHEMA_VERSION = "nbf08-chain-control-surface-inventory-v1"
INVENTORY_RELPATH = ".oracle/evidence/nbf08-chain-control-surface-inventory.json"
RESEARCH_RELPATH = ".oracle/research/nbf08-control-surface-inventory.md"
EXPECTED_IDS = [f"CC-{i:03d}" for i in range(1, 84)]
EXPECTED_AMBS = [f"AMB-{n:03d}" for n in range(1, 7)]
ID_RE = re.compile(r"^\| (CC-\d{3}) \|")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
BACKTICK_RE = re.compile(r"`([^`]+)`")

AUTHORITY_CLASSES = {"chain-authoritative", "linked-domain", "read-only", "external-unknown"}
CLAIM_CLASSES = {"required", "linked", "evidence-only", "claimless-read", "held"}
CLOSURE_STATUSES = {"planned", "implemented", "verified", "held", "excluded"}
COVERAGE_STATUSES = {"covered", "held", "excluded"}
AMB_DISPOSITIONS = {"resolved", "modified", "rejected", "held"}
REQUIRED_ROW_FIELDS = {
    "surface_id",
    "domain",
    "surface",
    "path",
    "source_paths",
    "symbol",
    "mutation",
    "owner",
    "authority_class",
    "claim_class",
    "required_event_kinds",
    "linked_domain_receipts",
    "coverage_tests",
    "required_commands",
    "evidence_paths",
    "evidence_digests",
    "authority_mode",
    "replay_contract",
    "ambiguity_ids",
    "gate_ids",
    "status",
    "closure_status",
    "reason",
}
BLANKET_TOKENS = {"", "implemented", "planned", "default", "todo", "unknown", "n/a"}

GATES = {
    "S1": "uv run pytest -q tests/arnold_pipelines/megaplan/test_chain_control_journal.py",
    "S2": "uv run pytest -q tests/arnold_pipelines/megaplan/test_chain_control_replay.py",
    "S3": "uv run pytest -q tests/arnold_pipelines/megaplan/test_chain_control_chain.py",
    "S4": "uv run pytest -q tests/arnold_pipelines/megaplan/test_chain_control_plan.py",
    "S5": "uv run pytest -q tests/cloud/test_chain_control_cloud.py tests/arnold_pipelines/megaplan/test_chain_control_schedule.py",
    "S6": "uv run pytest -q tests/arnold_pipelines/megaplan/test_chain_control_domains.py",
    "S7": (
        "python .oracle/scripts/nbf08_surface_inventory_v1.py "
        "--research .oracle/research/nbf08-control-surface-inventory.md "
        f"--expected-sha256 {EXPECTED_SHA} --expected-ids CC-001..CC-083 "
        f"--output {INVENTORY_RELPATH} --check"
    ),
}
S7_STATIC = (
    "python .oracle/scripts/nbf08_static_contract_check_v1.py --root . "
    "--check-lock-order --check-sequence-migration --reject-direct-save"
)
GATE_TESTS = {
    "S1": "tests/arnold_pipelines/megaplan/test_chain_control_journal.py",
    "S2": "tests/arnold_pipelines/megaplan/test_chain_control_replay.py",
    "S3": "tests/arnold_pipelines/megaplan/test_chain_control_chain.py",
    "S4": "tests/arnold_pipelines/megaplan/test_chain_control_plan.py",
    "S5": "tests/cloud/test_chain_control_cloud.py",
    "S6": "tests/arnold_pipelines/megaplan/test_chain_control_domains.py",
    "S7": "tests/arnold_pipelines/megaplan/test_chain_control_domains.py",
}

AMB_ROWS: dict[str, list[str]] = {
    "AMB-001": ["CC-061"],
    "AMB-002": ["CC-039", "CC-053", "CC-054", "CC-055", "CC-056"],
    "AMB-003": ["CC-036", "CC-057"],
    "AMB-004": ["CC-035"],
    "AMB-005": ["CC-062"],
    "AMB-006": [],
}
AMB_TESTS = {
    "AMB-001": "NBF08-S6-T061",
    "AMB-002": "NBF08-S6-T039",
    "AMB-003": "NBF08-S6-T036",
    "AMB-004": "NBF08-S6-T035",
    "AMB-005": "NBF08-S7-T062",
    "AMB-006": "NBF08-S7-T006",
}
AMB_COMMANDS = {
    **{key: [GATES["S6"]] for key in ("AMB-001", "AMB-002", "AMB-003", "AMB-004")},
    "AMB-005": [
        "python -m arnold_pipelines.megaplan.incident.chain_control rebind-suffix --ledger <path> --chain-id <id> --expected-physical-tip <event/hash> --expected-control-tip <event/hash> --from-authority <id> --to-authority <id> --source-manifest <path> --expected-base-sha256 <sha256> --expected-source-sha256 <sha256> --expected-manifest-sha256 <sha256> --reason <code> --actor <redacted-id> --receipt <output>",
        "python -m arnold_pipelines.megaplan.incident.chain_control rebind-nbf07-dependency --ledger <path> --chain-id <id> --tasklist .oracle/tasklist.md --chain-spec <path> --expected-tasklist-sha256 <sha256> --expected-chain-spec-sha256 <sha256> --suffix-tip <event/hash> --expected-base-sha256 <sha256> --expected-source-sha256 <sha256> --expected-manifest-sha256 <sha256> --candidate-sha <sha> --inventory-sha256 <sha256> --framed-diff-sha256 <sha256> --actor <redacted-id> --receipt <output>",
    ],
    "AMB-006": [
        "bash -n arnold_pipelines/megaplan/data/pre-commit-hook.sh",
        "bash -n sync-skills.sh",
    ],
}

# Implementation-time dispositions. Each is grounded in named source/test
# symbols; none is a reviewer assertion. Held is forbidden at S7.
AMB_SPECS: dict[str, dict[str, Any]] = {
    "AMB-001": {
        "disposition": "modified",
        "rationale": (
            "Generic atomic writers in _core/io.py and arnold/runtime/state_persistence.py "
            "remain the physical primitive and are callable without chain context. The census "
            "over-stated that gap as unresolved chain authority: bound save_chain_state/"
            "save_epic_chain_state reject context-free writes, and persist/load now compare "
            "the live file digest to the last committed 64-hex post_state_digest and raise "
            "ChainControlTamper without advancing the journal cursor."
        ),
        "source_evidence": [
            "arnold_pipelines/megaplan/_core/io.py:_write_bytes_direct",
            "arnold_pipelines/megaplan/chain/spec.py:save_chain_state",
            "arnold_pipelines/megaplan/chain/spec.py:load_chain_state",
            "arnold_pipelines/megaplan/incident/chain_control.py:verify_bound_state_matches_journal",
            "arnold_pipelines/megaplan/incident/chain_control.py:persist_bound_chain_state",
        ],
        "test_evidence": [
            "tests/arnold_pipelines/megaplan/test_chain_control_chain.py:test_context_free_bound_save_fails_closed",
            "tests/arnold_pipelines/megaplan/test_chain_control_domains.py:test_raw_marker_edit_is_tamper_hold",
        ],
        "authority_mode": "file",
        "replay_contract": "unattributed or partial bound write is tamper_detected + hold; it is never replayed as committed",
        "row_status": "covered",
        "row_closure": "implemented",
        "row_authority": "linked-domain",
        "row_claim": "linked",
    },
    "AMB-002": {
        "disposition": "resolved",
        "rationale": (
            "DBStore._run_idempotent_mutation rejects chain_bound mutations that lack a "
            "transaction-scoped chain_operation_id and an active LockedChainControlTransaction. "
            "File/DB Store mixins remain Store-authoritative linked-domain surfaces; raw SQL "
            "without operation context cannot commit a bound mutation."
        ),
        "source_evidence": [
            "arnold_pipelines/megaplan/store/db.py:_run_idempotent_mutation",
            "arnold_pipelines/megaplan/store/compat.py:_call",
        ],
        "test_evidence": [
            "tests/arnold_pipelines/megaplan/test_chain_control_domains.py:test_direct_sql_without_operation_id_rejects",
        ],
        "authority_mode": "db-projection",
        "replay_contract": "same operation_id is idempotent; file/DB parity drift is hold; context-free bound SQL rejects",
        "row_status": "covered",
        "row_closure": "implemented",
        "row_authority": "linked-domain",
        "row_claim": "linked",
    },
    "AMB-003": {
        "disposition": "resolved",
        "rationale": (
            "ArnoldStoreAdapter._call rejects context-free bound mutators. Compatibility "
            "wrapper/reader/deletion lifecycle (CC-057) remains a linked-domain non-authoritative "
            "adapter: replay delegates to Store and never creates a second journal."
        ),
        "source_evidence": [
            "arnold_pipelines/megaplan/store/compat.py:_call",
            "arnold_pipelines/megaplan/compatibility/__init__.py:WrapperRegistry.register",
        ],
        "test_evidence": [
            "tests/arnold_pipelines/megaplan/test_chain_control_domains.py:test_compat_adapter_rejects_context_free_bound_mutation",
        ],
        "authority_mode": "db-projection",
        "replay_contract": "adapter/wrapper replay delegates to the authoritative Store and never creates a second journal",
        "row_status": "covered",
        "row_closure": "implemented",
        "row_authority": "linked-domain",
        "row_claim": "linked",
    },
    "AMB-004": {
        "disposition": "rejected",
        "rationale": (
            "PipelineRegistry.register, dispatch_operation_for, and ResidentProfile."
            "_register_default_tools are plugin/tool registration, not bound-chain mutations. "
            "Admin/automation-actor grants already require an actor via Store. Missing "
            "actor/context cannot be replayed as an accepted chain mutation; chain-bound "
            "Store writes are fenced by AMB-003."
        ),
        "source_evidence": [
            "arnold_pipelines/megaplan/registry.py:register",
            "arnold_pipelines/megaplan/registry.py:dispatch_operation_for",
            "arnold_pipelines/megaplan/resident/profile.py:_register_default_tools",
            "arnold_pipelines/megaplan/store/_db/operations.py:create_automation_actor",
        ],
        "test_evidence": [
            "tests/arnold_pipelines/megaplan/test_chain_control_domains.py:test_compat_adapter_rejects_context_free_bound_mutation",
            "tests/arnold_pipelines/megaplan/test_chain_control_domains.py:test_direct_sql_without_operation_id_rejects",
        ],
        "authority_mode": "file",
        "replay_contract": "registration is not a chain mutation; missing actor/context rejects and cannot replay as accepted",
        "row_status": "covered",
        "row_closure": "implemented",
        "row_authority": "chain-authoritative",
        "row_claim": "required",
    },
    "AMB-005": {
        "disposition": "resolved",
        "rationale": (
            "rebind_suffix and rebind_nbf07_dependency exist as dedicated non-interactive "
            "CLI surfaces. Drift holds leave old authority untouched; dependency rebind is "
            "gated on a verified suffix_rebound receipt. The inventory generator does not "
            "invoke either ceremony."
        ),
        "source_evidence": [
            "arnold_pipelines/megaplan/incident/chain_control.py:rebind_suffix",
            "arnold_pipelines/megaplan/incident/chain_control.py:rebind_nbf07_dependency",
            "arnold_pipelines/megaplan/incident/chain_control.py:_cli",
        ],
        "test_evidence": [
            "tests/arnold_pipelines/megaplan/test_chain_control_replay.py:test_rebind_suffix_cli_and_gated_nbf07_dependency",
        ],
        "authority_mode": "file",
        "replay_contract": "exact-tip replay returns the prior receipt; any drift leaves old authority untouched and emits hold; dependency rebind is unavailable without a verified suffix receipt",
        "row_status": "covered",
        "row_closure": "implemented",
        "row_authority": "chain-authoritative",
        "row_claim": "required",
    },
    "AMB-006": {
        "disposition": "rejected",
        "rationale": (
            "pre-commit-hook.sh and sync-skills.sh are operator-environment setup, not "
            "admitted chain mutations. They are outside the Python registry and cannot "
            "claim chain authority; unknown replay is rejected. Syntax evidence is bash -n."
        ),
        "source_evidence": [
            "arnold_pipelines/megaplan/data/pre-commit-hook.sh",
            "sync-skills.sh",
        ],
        "test_evidence": [
            "tests/arnold_pipelines/megaplan/test_chain_control_domains.py:test_external_shell_scripts_are_syntax_valid_and_claimless",
        ],
        "authority_mode": "external-unknown",
        "replay_contract": "no ambient caller may claim chain authority; unknown replay is rejected/held",
        "row_status": "excluded",
        "row_closure": "excluded",
        "row_authority": "external-unknown",
        "row_claim": "claimless-read",
    },
}

# CC-038 is AMBIG in the census but is not one of AMB-001..006. Tamper
# detection on bound load/persist is the executable closure.
ROW_OVERLAYS: dict[str, dict[str, str]] = {
    "CC-038": {
        "status": "covered",
        "closure_status": "implemented",
        "authority_class": "chain-authoritative",
        "claim_class": "evidence-only",
        "reason": (
            "Out-of-band JSON/marker replacement is detected against the last committed "
            "64-hex post_state_digest; load_chain_state and persist_bound_chain_state raise "
            "ChainControlTamper and do not advance the journal cursor."
        ),
    },
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _source_index_revision(root: Path) -> str:
    """Return a stable 40-char identity for the indexed source tree.

    The generated inventory is excluded so committing it cannot change the
    identity that it records.  Indexed mode/object/stage/path records retain
    the same Git source-index semantics across worktrees and commits.
    """
    records = subprocess.check_output(
        ["git", "ls-files", "-s"], cwd=root, text=True
    ).splitlines()
    records = sorted(
        record
        for record in records
        if record.split("\t", 1)[-1] != INVENTORY_RELPATH
    )
    return hashlib.sha1(("\n".join(records) + "\n").encode("utf-8")).hexdigest()


def _parse_row(line: str) -> list[str]:
    cols = [item.strip() for item in line.strip().strip("|").split("|")]
    if len(cols) == 18 and cols[0] == "CC-043":
        return [cols[0], " | ".join(cols[1:10]), *cols[10:]]
    return cols


def _read_rows(raw: bytes) -> list[list[str]]:
    rows = [_parse_row(line) for line in raw.decode("utf-8").splitlines() if ID_RE.match(line)]
    for row in rows:
        if len(row) != 10:
            raise ValueError(f"malformed inventory row {row[0]!r}: {len(row)} columns")
    return rows


def _is_source_path(token: str) -> bool:
    if token.startswith("python -m "):
        return False
    return token.endswith((".py", ".sh")) or token.startswith(
        ("arnold/", "arnold_pipelines/", "tests/", ".oracle/", "sync-skills")
    )


def _paths(surface: str) -> list[str]:
    if surface.startswith("Oracle-only future ceremony"):
        return ["arnold_pipelines/megaplan/incident/chain_control.py"]
    paths: list[str] = []
    for token in BACKTICK_RE.findall(surface):
        token = token.strip()
        if _is_source_path(token) and token not in paths:
            paths.append(token)
    return paths


def _symbols(surface: str, paths: list[str]) -> str:
    tokens = [
        token
        for token in BACKTICK_RE.findall(surface)
        if token not in paths and not token.startswith("python -m ") and not _is_source_path(token)
    ]
    return "; ".join(tokens) or surface


def _authority(label: str) -> str:
    mapped = {
        "IN-SCOPE": "chain-authoritative",
        "LINK": "linked-domain",
        "READ": "read-only",
        "AMBIG": "external-unknown",
    }.get(label.split("/", 1)[0].strip(), "")
    if not mapped:
        raise ValueError(f"unclassified authority class: {label}")
    return mapped


def _claim_for(authority: str, table_claim: str) -> str:
    if table_claim in CLAIM_CLASSES:
        mapped = {
            "chain-authoritative": "required",
            "linked-domain": "linked",
            "read-only": "claimless-read",
            "external-unknown": "held",
        }[authority]
        if table_claim != mapped and table_claim != "evidence-only":
            raise ValueError(f"claim_class {table_claim!r} does not match {authority} (mapped {mapped})")
        return table_claim
    raise ValueError(f"invalid table claim_class {table_claim!r}")


def _events(value: str) -> list[str]:
    out: list[str] = []
    for token in BACKTICK_RE.findall(value):
        for item in token.split(","):
            kind = item.strip().strip("'")
            if not kind or kind.startswith("None"):
                continue
            kind = "tamper_detected" if kind == "tamper" else kind
            kind = kind if kind.startswith("chain_control.") else "chain_control." + kind
            if kind not in out:
                out.append(kind)
    return out


def _receipts(value: str) -> list[str]:
    out = re.findall(
        r"[A-Za-z][A-Za-z0-9_.-]*(?:receipt|event|digest|marker|record|link|authority|cursor|projection|manifest|lease|proof|state|evidence|outcome)[A-Za-z0-9_.-]*",
        value,
        re.I,
    )
    return list(dict.fromkeys(out)) or [value.strip().lower().replace(" ", "_")]


def _gates(owner: str) -> list[str]:
    found = [f"S{n}" for n in sorted({int(x[1:]) for x in re.findall(r"S[1-7]", owner)})]
    if not found:
        raise ValueError(f"missing gate owner: {owner}")
    return found


def _domain(path: str) -> str:
    if path.startswith("arnold/"):
        return "arnold-runtime"
    prefix = "arnold_pipelines/megaplan/"
    if path.startswith(prefix):
        return path[len(prefix) :].split("/", 1)[0]
    if path.startswith("tests/"):
        return "gate-evidence"
    if path.endswith(".sh") or path.startswith(".oracle/"):
        return "external-boundary"
    return "chain-control"


def _names_in(path: Path) -> set[str]:
    if path.suffix != ".py" or not path.is_file():
        return set()
    text = path.read_text(encoding="utf-8")
    found: set[str] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return found
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            found.add(node.name)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    found.add(item.name)
                    found.add(f"{node.name}.{item.name}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found.add(target.id)
    return found


def _is_checkable_symbol(token: str) -> bool:
    token = token.strip()
    if not token or token.startswith(("action", "--", "python ")):
        return False
    if any(marker in token for marker in ("|", " ", "=", "/", "\\")):
        return False
    return all(part.isidentifier() for part in token.split("."))


CHAIN_CONTROL_DOORS = {
    "apply_chain_lifecycle",
    "persist_bound_chain_state",
    "cas_chain_state_effect",
    "ensure_genesis",
    "mutate",
    "require_bound_context",
    "ChainControlJournal",
    "journal_for",
    "rebind_suffix",
    "rebind_nbf07_dependency",
}
MUST_WIRE_OR_HOLD = {"CC-004", "CC-031", "CC-032"}


def _call_names(path: Path) -> set[str]:
    if path.suffix != ".py" or not path.is_file():
        return set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            found.add(func.id)
        elif isinstance(func, ast.Attribute):
            found.add(func.attr)
    return found


_PRODUCTION_CALLS: dict[str, set[str]] = {}


def _production_call_names(root: Path) -> set[str]:
    key = str(root.resolve())
    cached = _PRODUCTION_CALLS.get(key)
    if cached is not None:
        return cached
    called: set[str] = set()
    for base in (root / "arnold_pipelines" / "megaplan",):
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if "tests" in path.parts:
                continue
            called |= _call_names(path)
    _PRODUCTION_CALLS[key] = called
    return called


def _symbol_called_in_production(root: Path, paths: list[str], symbol: str) -> bool:
    tokens = [token.strip() for token in symbol.split(";") if token.strip()]
    checkable = [token.split(".")[-1] for token in tokens if _is_checkable_symbol(token)]
    if not checkable:
        return all((root / path).is_file() for path in paths)
    called = _production_call_names(root)
    return any(token in called for token in checkable)


def _source_reaches_chain_control(root: Path, paths: list[str]) -> bool:
    for path in paths:
        rel = str(path)
        if rel.endswith("incident/chain_control.py"):
            return True
        names = _call_names(root / path)
        if names & CHAIN_CONTROL_DOORS:
            return True
    return False


def _symbols_present(root: Path, paths: list[str], symbol: str) -> bool:
    names: set[str] = set()
    for path in paths:
        names |= _names_in(root / path)
    if not names:
        return all((root / path).is_file() for path in paths)
    tokens = [token.strip() for token in symbol.split(";") if token.strip()]
    checkable = [token for token in tokens if _is_checkable_symbol(token)]
    if not checkable:
        return True
    for token in checkable:
        last = token.split(".")[-1]
        if token not in names and last not in names:
            return False
    return True


def _symbol_in_source(root: Path, spec: str) -> bool:
    if ":" not in spec:
        return (root / spec).is_file()
    path, name = spec.split(":", 1)
    target = root / path
    if not target.is_file():
        return False
    if target.suffix != ".py":
        return True
    names = _names_in(target)
    last = name.split(".")[-1]
    return name in names or last in names


def _commands_for(gates: list[str]) -> list[str]:
    commands: list[str] = []
    for gate in gates:
        command = GATES[gate]
        if command not in commands:
            commands.append(command)
        if gate == "S7" and S7_STATIC not in commands:
            commands.append(S7_STATIC)
    return commands


def _authority_mode(authority: str, surface: str) -> str:
    if authority in {"chain-authoritative", "read-only", "external-unknown"} or "ledger" in surface.lower():
        return "file"
    return "db-projection"


def _replay(authority: str) -> str:
    if authority == "read-only":
        return "read-only inspection does not append or advance chain state"
    if authority == "external-unknown":
        return "unknown or unattributed replay is rejected and held; it cannot advance authority"
    return "same operation_id returns the prior receipt; no second journal or external effect"


def _research_status(authority: str) -> tuple[str, str, str]:
    if authority == "external-unknown":
        return "held", "held", "unresolved ambiguity row"
    if authority == "read-only":
        return "excluded", "excluded", "read-only surface; no chain mutation authority"
    return "covered", "planned", ""


def _evidence_pairs(root: Path, paths: list[str], gates: list[str], research_digest: str) -> tuple[list[str], list[str]]:
    evidence_paths = [INVENTORY_RELPATH, RESEARCH_RELPATH]
    evidence_digests = [research_digest, research_digest]
    for gate in gates:
        test_path = GATE_TESTS[gate]
        if test_path not in evidence_paths and (root / test_path).is_file():
            evidence_paths.append(test_path)
            evidence_digests.append(_sha256_file(root / test_path))
    source = paths[0]
    if source not in evidence_paths and (root / source).is_file():
        evidence_paths.append(source)
        evidence_digests.append(_sha256_file(root / source))
    if gates[0] == "S5":
        extra = "tests/arnold_pipelines/megaplan/test_chain_control_schedule.py"
        if extra not in evidence_paths:
            evidence_paths.append(extra)
            evidence_digests.append(_sha256_file(root / extra))
    return evidence_paths, evidence_digests


def _surface(row: list[str], root: Path, research_digest: str) -> dict[str, Any]:
    sid, surface, mutation, context, receipt, negative, owner, events, label, table_claim = row
    authority = _authority(label)
    claim = _claim_for(authority, table_claim)
    paths = _paths(surface)
    if not paths:
        raise ValueError(f"missing source path for {sid}")
    missing = [path for path in paths if not (root / path).is_file()]
    if missing:
        raise ValueError(f"missing source target for {sid}: {missing}")
    gates = _gates(owner)
    ambiguities = [key for key, rows in AMB_ROWS.items() if sid in rows]
    status, closure, reason = _research_status(authority)
    symbol = _symbols(surface, paths)
    present = _symbols_present(root, paths, symbol)
    called = _symbol_called_in_production(root, paths, symbol)
    wired = _source_reaches_chain_control(root, paths)
    if status == "covered" and present and called:
        if sid in MUST_WIRE_OR_HOLD and not wired:
            closure = "planned"
            reason = "production door is not routed through ChainControlJournal"
        else:
            closure = "implemented"
    elif status == "covered" and present and not called:
        closure = "planned"
        reason = "census symbols are AST-only; no production call reachability"
    if status == "covered" and not present:
        closure = "planned"
        reason = "census symbols not all present in current source"
    for amb_id in ambiguities:
        spec = AMB_SPECS[amb_id]
        status = spec["row_status"]
        closure = spec["row_closure"]
        claim = spec["row_claim"]
        authority = spec["row_authority"]
        reason = spec["rationale"]
    if sid in ROW_OVERLAYS:
        overlay = ROW_OVERLAYS[sid]
        status = overlay["status"]
        closure = overlay["closure_status"]
        authority = overlay["authority_class"]
        claim = overlay["claim_class"]
        reason = overlay["reason"]
    if ambiguities:
        test_id = AMB_TESTS[ambiguities[0]]
        commands = list(AMB_COMMANDS[ambiguities[0]])
        for command in _commands_for(gates):
            if command not in commands:
                commands.append(command)
    else:
        test_id = f"NBF08-{gates[0]}-T{sid[-3:]}"
        commands = _commands_for(gates)
    evidence_paths, evidence_digests = _evidence_pairs(root, paths, gates, research_digest)
    return {
        "surface_id": sid,
        "domain": _domain(paths[0]),
        "surface": mutation,
        "path": paths[0],
        "source_paths": paths,
        "symbol": symbol,
        "mutation": mutation,
        "operation_context": context,
        "domain_receipt": receipt,
        "negative_test": negative,
        "owner": owner,
        "authority_class": authority,
        "claim_class": claim,
        "required_event_kinds": _events(events),
        "linked_domain_receipts": _receipts(receipt),
        "coverage_tests": [test_id],
        "required_commands": commands,
        "evidence_paths": evidence_paths,
        "evidence_digests": evidence_digests,
        "authority_mode": _authority_mode(authority, surface),
        "replay_contract": _replay(authority),
        "ambiguity_ids": ambiguities,
        "gate_ids": gates,
        "status": status,
        "closure_status": closure,
        "reason": reason,
    }


def _ambiguity_dispositions(root: Path) -> list[dict[str, Any]]:
    rows = []
    for amb_id in EXPECTED_AMBS:
        spec = AMB_SPECS[amb_id]
        evidence_paths = [INVENTORY_RELPATH]
        for item in spec["source_evidence"] + spec["test_evidence"]:
            path = item.split(":", 1)[0]
            if path not in evidence_paths:
                evidence_paths.append(path)
        missing = [path for path in evidence_paths if path != INVENTORY_RELPATH and not (root / path).is_file()]
        if missing:
            raise ValueError(f"{amb_id}: missing disposition evidence {missing}")
        missing_symbols = [item for item in spec["source_evidence"] + spec["test_evidence"] if not _symbol_in_source(root, item)]
        if missing_symbols:
            raise ValueError(f"{amb_id}: disposition symbols absent {missing_symbols}")
        rows.append(
            {
                "ambiguity_id": amb_id,
                "disposition": spec["disposition"],
                "rationale": spec["rationale"],
                "inventory_rows": list(AMB_ROWS[amb_id]),
                "coverage_test": AMB_TESTS[amb_id],
                "required_commands": list(AMB_COMMANDS[amb_id]),
                "source_evidence": list(spec["source_evidence"]),
                "test_evidence": list(spec["test_evidence"]),
                "evidence_paths": evidence_paths,
                "authority_mode": spec["authority_mode"],
                "replay_contract": spec["replay_contract"],
            }
        )
    return rows


def _is_blanket_row(row: dict[str, Any]) -> bool:
    keys = {key for key in row if key != "surface_id"}
    if keys <= {"closure_status"}:
        return True
    if len(REQUIRED_ROW_FIELDS - set(row)) > 0:
        return True
    symbol = str(row.get("symbol") or "").strip().lower()
    path = str(row.get("path") or "").strip().lower()
    if symbol in BLANKET_TOKENS or path in BLANKET_TOKENS:
        return True
    if row.get("closure_status") == "implemented" and not row.get("path"):
        return True
    if not row.get("authority_class") or not row.get("owner"):
        return True
    return False


def _validate(body: dict[str, Any], root: Path, expected_digest: str) -> list[str]:
    errors: list[str] = []
    if body.get("research_inventory_sha256") != expected_digest:
        errors.append("stale research digest")
    if body.get("schema_version") != SCHEMA_VERSION:
        errors.append("invalid schema_version")
    if body.get("surface_ids") != EXPECTED_IDS or body.get("surface_count") != 83:
        errors.append("surface IDs/count are not exactly CC-001..CC-083")
    rows = body.get("surfaces")
    if not isinstance(rows, list) or len(rows) != 83:
        return errors + ["surface rows are not exactly 83"]
    ids = [row.get("surface_id") for row in rows if isinstance(row, dict)]
    if ids != EXPECTED_IDS or len(set(ids)) != len(ids):
        errors.append("missing, duplicate, orphan, or non-contiguous surface ID")
    closures: set[str] = set()
    distinct_paths: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            errors.append("non-object surface row")
            continue
        sid = row.get("surface_id")
        if _is_blanket_row(row):
            errors.append(f"{sid}: blanket/default row")
            continue
        missing = sorted(REQUIRED_ROW_FIELDS - set(row))
        if missing:
            errors.append(f"{sid}: missing fields {missing}")
            continue
        closures.add(str(row.get("closure_status")))
        distinct_paths.add(str(row.get("path")))
        if not row["path"] or not (root / str(row["path"])).is_file():
            errors.append(f"{sid}: missing source target")
        for path in row.get("source_paths") or []:
            if not (root / str(path)).is_file():
                errors.append(f"{sid}: missing source target {path}")
        if not row["symbol"] or str(row["symbol"]).strip().lower() in BLANKET_TOKENS:
            errors.append(f"{sid}: missing source symbol")
        if row["authority_class"] not in AUTHORITY_CLASSES or row["claim_class"] not in CLAIM_CLASSES:
            errors.append(f"{sid}: invalid authority/claim class")
        if row["status"] not in COVERAGE_STATUSES or row["closure_status"] not in CLOSURE_STATUSES:
            errors.append(f"{sid}: invalid status")
        if not all(row[field] for field in ("coverage_tests", "required_commands", "evidence_paths", "evidence_digests", "gate_ids", "replay_contract", "domain", "surface", "owner")):
            errors.append(f"{sid}: missing closure evidence")
        if row["status"] in {"held", "excluded"} and not row["reason"]:
            errors.append(f"{sid}: held/excluded row missing reason")
        if row["closure_status"] == "implemented":
            source_paths = list(row.get("source_paths") or [row.get("path")])
            if not _symbol_called_in_production(root, [str(p) for p in source_paths if p], str(row.get("symbol") or "")):
                errors.append(f"{sid}: AST-only implemented")
            if sid in MUST_WIRE_OR_HOLD and not _source_reaches_chain_control(root, [str(p) for p in source_paths if p]):
                errors.append(f"{sid}: implemented without production chain-control wiring")
        if row["authority_class"] == "external-unknown" and row["status"] == "held":
            errors.append(f"{sid}: unresolved external-unknown row")
        for path in row.get("evidence_paths") or []:
            if not (root / str(path)).is_file():
                errors.append(f"{sid}: missing/nonexistent evidence target {path}")
        digests = row.get("evidence_digests") or []
        if not isinstance(digests, list) or not digests or not all(isinstance(item, str) and SHA_RE.match(item) for item in digests):
            errors.append(f"{sid}: missing evidence digests")
        elif len(digests) != len(row.get("evidence_paths") or []):
            errors.append(f"{sid}: evidence_paths/evidence_digests length mismatch")
        else:
            for path, digest in zip(row["evidence_paths"], digests, strict=True):
                if path == INVENTORY_RELPATH:
                    continue
                target = root / str(path)
                if target.is_file() and _sha256_file(target) != digest:
                    errors.append(f"{sid}: stale evidence digest for {path}")
    if len(distinct_paths) < 2 and len(rows) == 83:
        errors.append("blanket/default rows: all surfaces share one path")
    if closures == {"implemented"} and all(_is_blanket_row(row) or set(row) <= {"surface_id", "closure_status"} for row in rows if isinstance(row, dict)):
        errors.append("blanket/default rows: all closure_status=implemented")
    dispositions = body.get("ambiguity_dispositions")
    if not isinstance(dispositions, list):
        errors.append("missing ambiguity dispositions")
        return errors
    actual = [item.get("ambiguity_id") for item in dispositions if isinstance(item, dict)]
    if actual != EXPECTED_AMBS:
        errors.append("missing, duplicate, or unordered ambiguity dispositions")
    for item in dispositions:
        if not isinstance(item, dict):
            errors.append("non-object ambiguity disposition")
            continue
        amb_id = item.get("ambiguity_id")
        disposition = item.get("disposition")
        if disposition not in AMB_DISPOSITIONS or disposition == "held":
            errors.append(f"{amb_id}: held/unresolved ambiguity")
        if not item.get("rationale"):
            errors.append(f"{amb_id}: missing rationale")
        if not item.get("source_evidence") or not item.get("test_evidence"):
            errors.append(f"{amb_id}: missing source/test evidence")
        for spec in list(item.get("source_evidence") or []) + list(item.get("test_evidence") or []):
            if not _symbol_in_source(root, str(spec)):
                errors.append(f"{amb_id}: missing/nonexistent evidence target {spec}")
        for path in item.get("evidence_paths") or []:
            if path != INVENTORY_RELPATH and not (root / str(path)).is_file():
                errors.append(f"{amb_id}: missing/nonexistent evidence target {path}")
    if body.get("ambiguity_ids") != EXPECTED_AMBS:
        errors.append("top-level ambiguity_ids are not exactly AMB-001..AMB-006")
    return errors


def build_inventory(root: Path, research: Path, expected_sha256: str) -> dict[str, Any]:
    raw = research.read_bytes()
    digest = _sha256_bytes(raw)
    if digest != expected_sha256:
        raise ValueError(f"stale research digest: {digest} != {expected_sha256}")
    rows = _read_rows(raw)
    ids = [row[0] for row in rows]
    if ids != EXPECTED_IDS or len(set(ids)) != len(ids):
        raise ValueError(f"ID mismatch: got {len(ids)} expected 83 contiguous CC-001..CC-083")
    research_rel = str(research.resolve().relative_to(root.resolve())) if research.is_absolute() else str(research)
    surfaces = [_surface(row, root, digest) for row in rows]
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "base_revision": _source_index_revision(root),
        "generator_version": GENERATOR_VERSION,
        "research_inventory_path": research_rel,
        "research_inventory_sha256": digest,
        "surface_count": len(surfaces),
        "surface_id_range": "CC-001..CC-083",
        "surface_ids": EXPECTED_IDS,
        "ambiguity_ids": EXPECTED_AMBS,
        "ambiguity_dispositions": _ambiguity_dispositions(root),
        "surfaces": surfaces,
    }
    body["inventory_digest"] = _sha256_bytes(_canonical({key: value for key, value in body.items() if key != "inventory_digest"}))
    return body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--research", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--expected-ids", default="CC-001..CC-083")
    parser.add_argument("--output", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.expected_ids != "CC-001..CC-083":
            print(f"inventory check FAIL: expected-ids must be CC-001..CC-083, got {args.expected_ids}", file=sys.stderr)
            return 1
        root = Path.cwd()
        body = build_inventory(root, Path(args.research), args.expected_sha256)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
        if args.check:
            errors = _validate(body, root, args.expected_sha256)
            if errors:
                for error in errors:
                    print(f"inventory check FAIL: {error}", file=sys.stderr)
                return 1
            print(f"inventory check PASS ids={body['surface_count']} digest={body['inventory_digest']}")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"inventory check FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
