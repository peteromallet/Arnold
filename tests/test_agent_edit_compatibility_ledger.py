"""Guards for the agent-edit legacy alias compatibility ledger."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SCAN_ROOTS = (
    Path("vibecomfy/comfy_nodes/agent"),
    Path("vibecomfy/comfy_nodes/web"),
    Path("tests/fixtures/payload_contracts"),
    Path("tests/fixtures/e2e_sessions"),
    Path("tests/characterization"),
)

TEXT_SUFFIXES = {".js", ".mjs", ".py", ".json", ".md", ".txt"}

LEDGER_PATH = ROOT / "tests/fixtures/agent_edit/compatibility_ledger.md"
ARCHITECTURE_LEDGER_PATH = ROOT / "docs/architecture/compatibility-ledger.md"

ALIAS_PATTERNS = {
    "queue_allowed": re.compile(r"\bqueue_allowed\b"),
    "candidate_graph": re.compile(r"\bcandidate_graph\b"),
}

# 2026-06-24 M2 alias-token inventory across SCAN_ROOTS before tightening:
# queue_allowed: 16 files / ~169 hits; candidate_graph: 11 files / ~56 hits;
# candidate_graph_hash: 9 files / ~93 hits. Only queue_allowed and
# candidate_graph are compatibility-specific and bounded enough for explicit
# scanner allowlists. candidate_graph_hash is canonical; apply_eligible and
# apply_eligibility are broader apply-eligibility behavior surfaces, so keep
# those covered by adapter/contract behavior tests instead of broad regex
# scanner allowlists.
ALLOWED_ALIAS_FILES = {
    "queue_allowed": {
        "tests/fixtures/payload_contracts/agent_edit_accept_response.json",
        "tests/fixtures/payload_contracts/agent_edit_rebaseline_response.json",
        "tests/fixtures/payload_contracts/chat_rehydrate_response.json",
        "vibecomfy/comfy_nodes/agent/audit.py",
        "vibecomfy/comfy_nodes/agent/contracts.py",
        "vibecomfy/comfy_nodes/agent/edit.py",
        "vibecomfy/comfy_nodes/agent/gates.py",
        "vibecomfy/comfy_nodes/agent/routes.py",
        "vibecomfy/comfy_nodes/agent/session.py",
        "vibecomfy/comfy_nodes/web/agent_edit_response_contract.js",
        "vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js",
    },
    "candidate_graph": {
        "vibecomfy/comfy_nodes/agent/contracts.py",
        "vibecomfy/comfy_nodes/agent/edit.py",
        "vibecomfy/comfy_nodes/agent/routes.py",
        "vibecomfy/comfy_nodes/agent/session.py",
        "vibecomfy/comfy_nodes/web/agent_edit_response_contract.js",
        "vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js",
        "vibecomfy/comfy_nodes/web/agent_status_poller.js",
        "vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js",
    },
}

PROHIBITED_ALLOWLIST_FRAGMENTS = (
    "panel_thread.js",
    "agent_edit_lifecycle_transcript",
    "transcript",
    "detail_selector",
    "bubble_detail",
    "model_provider",
    "provider_model",
)


def _iter_text_files() -> list[Path]:
    files: list[Path] = []
    for scan_root in SCAN_ROOTS:
        for path in (ROOT / scan_root).rglob("*"):
            if path.is_file() and path.suffix in TEXT_SUFFIXES:
                files.append(path)
    return sorted(files)


def _ledger_scannable_backend_aliases() -> set[str]:
    text = LEDGER_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"Deliberately scannable bounded backend aliases:\s*(?P<aliases>.+)",
        text,
    )
    assert match, "Compatibility ledger must list deliberately scannable backend aliases."
    return set(re.findall(r"`([^`]+)`", match.group("aliases")))


def _read_ledgers() -> dict[str, str]:
    return {
        "fixture": LEDGER_PATH.read_text(encoding="utf-8"),
        "architecture": ARCHITECTURE_LEDGER_PATH.read_text(encoding="utf-8"),
    }


def _normalized_ledgers() -> dict[str, str]:
    return {name: re.sub(r"\s+", " ", text) for name, text in _read_ledgers().items()}


def test_agent_edit_legacy_aliases_stay_inside_compatibility_ledger_allowlist() -> None:
    violations: list[str] = []

    for path in _iter_text_files():
        rel_path = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        for alias_name, pattern in ALIAS_PATTERNS.items():
            if rel_path in ALLOWED_ALIAS_FILES[alias_name]:
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    violations.append(f"{alias_name}: {rel_path}:{line_number}: {line.strip()}")

    assert not violations, (
        "Legacy agent-edit aliases must stay within tests/fixtures/agent_edit/"
        "compatibility_ledger.md allowlists:\n" + "\n".join(violations)
    )


def test_ledger_listed_scannable_backend_aliases_have_scanner_patterns() -> None:
    scannable_aliases = _ledger_scannable_backend_aliases()

    assert scannable_aliases == {
        "queue_allowed",
        "candidate_graph",
    }
    assert not (scannable_aliases - set(ALIAS_PATTERNS))
    assert not (scannable_aliases - set(ALLOWED_ALIAS_FILES))
    assert set(ALIAS_PATTERNS) == scannable_aliases
    assert set(ALLOWED_ALIAS_FILES) == scannable_aliases


def test_ledger_scanner_allowlists_do_not_cover_frontend_render_or_routing_paths() -> None:
    offending_paths = sorted(
        f"{alias_name}: {path}"
        for alias_name, paths in ALLOWED_ALIAS_FILES.items()
        for path in paths
        if any(fragment in path for fragment in PROHIBITED_ALLOWLIST_FRAGMENTS)
    )

    assert not offending_paths, (
        "Compatibility scanner allowlists must stay limited to true legacy "
        "aliases/shims, without broad frontend render, transcript/detail, or "
        "model/provider routing exceptions:\n" + "\n".join(offending_paths)
    )


def test_ledgers_document_required_retained_aliases_and_shims() -> None:
    required_markers = {
        "AgentError": (
            "`AgentError`",
            "Python import compatibility alias",
            "AgentError = FailureEnvelope",
        ),
        "failure_hint_camelcase": (
            "camelCase inputs",
            "`failureKind`",
            "`nextAction`",
            "historical persisted error outcomes",
        ),
        "apply_eligible": (
            "`apply_eligible`",
            "Canonical executor/apply authorization",
            "compatibility fallback",
        ),
        "clarify_forbidden_keys": (
            "_CLARIFY_FORBIDDEN_KEYS",
            "route contract guard",
            "not a compatibility",
        ),
    }

    for ledger_name, text in _normalized_ledgers().items():
        for marker_name, markers in required_markers.items():
            missing = [marker for marker in markers if marker not in text]
            assert not missing, f"{ledger_name} ledger missing {marker_name}: {missing}"


def test_ledgers_classify_graph_hash_fields_without_legacy_alias_scanner_escape() -> None:
    for ledger_name, text in _normalized_ledgers().items():
        for marker in (
            "`client_graph_hash`",
            "`candidate_graph_hash`",
            "canonical",
            "N/A",
            "`submitted_client_graph_hash` / `action_client_graph_hash`",
            "Session migration",
        ):
            assert marker in text, f"{ledger_name} ledger missing graph-hash marker: {marker}"
        assert (
            "not a removable legacy alias" in text
            or "not removable legacy aliases" in text
        ), f"{ledger_name} ledger must classify graph hashes as canonical, not legacy aliases"
        assert (
            "Delete only after" in text
            or "Remove only after" in text
        ), f"{ledger_name} ledger missing graph-hash migration deletion trigger"

    scannable_aliases = _ledger_scannable_backend_aliases()
    assert "client_graph_hash" not in scannable_aliases
    assert "candidate_graph_hash" not in scannable_aliases
    assert "client_graph_hash" not in ALIAS_PATTERNS
    assert "candidate_graph_hash" not in ALIAS_PATTERNS
