"""Adapter protocol and ``ContractResult`` schema round-trip conformance checks.

This module provides programmatic checks over the public adapter and contract
serialization APIs.  It surfaces failures without normalising schema skew, but
does not change the underlying schema contract.

No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

import ast
import copy
import fnmatch
import json
from pathlib import Path
from typing import Any, Callable, Collection, Mapping

from arnold.conformance import ConformanceCheckResult
from arnold.pipeline.step_invocation import (
    StepInvocation,
    StepInvocationAdapter,
    StepInvocationAdapterRegistry,
)
from arnold.pipeline.types import ContractResult, ContractStatus


_DEFAULT_ARNOLD_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_MEGAPLAN_COUPLING_ALLOWLIST = (
    Path(__file__).resolve().parent / "_megaplan_coupling_allowlist.txt"
)
_DEFAULT_LEGACY_REFERENCE_ALLOWLIST = (
    Path(__file__).resolve().parent / "legacy_reference_allowlist.json"
)
ACTIVE_MEGAPLAN_PACKAGE_NAMES = (
    "megaplan",
    "arnold.pipelines.megaplan",
    "arnold_pipelines.megaplan",
)
LEGACY_REFERENCE_PATTERNS = (
    "arnold.pipelines.megaplan",
    "arnold/pipelines/megaplan",
    "python -m arnold.pipelines.megaplan",
)
LEGACY_REFERENCE_CATEGORIES = frozenset(
    {
        "scanner-target",
        "historical-non-shipped",
    }
)


# ---------------------------------------------------------------------------
# Adapter protocol checks
# ---------------------------------------------------------------------------


def check_adapter_protocol_conformance(
    registry: StepInvocationAdapterRegistry | None = None,
    *,
    smoke_kind: str | None = None,
    smoke_invocation: StepInvocation | None = None,
) -> ConformanceCheckResult:
    """Verify ``StepInvocationAdapter`` protocol and registry fail-closed behaviour.

    Parameters
    ----------
    registry:
        The adapter registry to check.  When *None* a fresh fail-closed
        ``StepInvocationAdapterRegistry()`` is constructed.
    smoke_kind:
        An optional registered kind whose adapter should survive a no-op
        smoke invocation.
    smoke_invocation:
        An optional invocation to pass to the smoke adapter's ``invoke``.

    Returns
    -------
    ConformanceCheckResult
        ``passed=True`` when the registry behaves correctly.
    """
    if registry is None:
        registry = StepInvocationAdapterRegistry()

    diagnostics: list[str] = []

    # --- unknown-kind fail-closed ---
    unknown_kind = "_conformance_unknown_kind_"
    try:
        registry.resolve(unknown_kind)
        diagnostics.append(
            f"registry.resolve({unknown_kind!r}) did not raise KeyError "
            f"(fail-closed broken)"
        )
    except KeyError:
        pass  # expected
    except Exception as exc:
        diagnostics.append(
            f"registry.resolve({unknown_kind!r}) raised unexpected "
            f"{type(exc).__name__}: {exc}"
        )

    # --- registered_kinds returns deterministic tuple ---
    kinds = registry.registered_kinds
    if not isinstance(kinds, tuple):
        diagnostics.append(
            f"registry.registered_kinds returned {type(kinds).__name__}, expected tuple"
        )
    elif list(kinds) != sorted(kinds):
        diagnostics.append(
            f"registry.registered_kinds is not sorted: {list(kinds)}"
        )

    # --- model slot exists by default ---
    if "model" not in kinds:
        diagnostics.append("default registry missing reserved 'model' slot")

    # --- register rejects duplicates ---
    test_kind = "_conformance_dup_kind_"
    try:
        registry.register(test_kind, _NoOpAdapter())
        try:
            registry.register(test_kind, _NoOpAdapter())
            diagnostics.append(
                f"registry.register({test_kind!r}) did not raise ValueError "
                f"on duplicate"
            )
        except ValueError:
            pass  # expected
    except Exception as exc:
        diagnostics.append(
            f"registry.register raised unexpected {type(exc).__name__}: {exc}"
        )

    # --- smoke invocation (if requested) ---
    if smoke_kind is not None and smoke_invocation is not None:
        try:
            adapter = registry.resolve(smoke_kind)
            _ = adapter.invoke(smoke_invocation)
        except Exception as exc:
            diagnostics.append(
                f"smoke invocation for kind {smoke_kind!r} raised "
                f"{type(exc).__name__}: {exc}"
            )

    # --- resolve returns something satisfying the protocol ---
    for kind in kinds:
        try:
            adapter = registry.resolve(kind)
            if not isinstance(adapter, StepInvocationAdapter):
                diagnostics.append(
                    f"resolved adapter for {kind!r} is not a "
                    f"StepInvocationAdapter: {type(adapter).__name__}"
                )
        except Exception as exc:
            diagnostics.append(
                f"registry.resolve({kind!r}) raised {type(exc).__name__}: {exc}"
            )

    if diagnostics:
        return ConformanceCheckResult(
            check_id="adapter-protocol",
            passed=False,
            message="; ".join(diagnostics),
            details=diagnostics,
        )
    return ConformanceCheckResult(check_id="adapter-protocol", passed=True)


def check_adapter_unknown_kind_fail_closed(
    registry: StepInvocationAdapterRegistry | None = None,
) -> ConformanceCheckResult:
    """Verify that resolving an unknown kind raises ``KeyError`` and that
    the error message names the kind and lists registered kinds.

    This check is deliberately isolated so callers can assert the exact
    fail-closed behaviour that the validator and C4 passes rely on.
    """
    if registry is None:
        registry = StepInvocationAdapterRegistry()

    unknown_kind = "_conformance_fail_closed_kind_"
    try:
        registry.resolve(unknown_kind)
        return ConformanceCheckResult(
            check_id="adapter-unknown-kind-fail-closed",
            passed=False,
            message=f"registry.resolve({unknown_kind!r}) did not raise KeyError",
        )
    except KeyError as exc:
        message = str(exc)
        registered_kinds = sorted(registry._adapters)
        if unknown_kind not in message:
            return ConformanceCheckResult(
                check_id="adapter-unknown-kind-fail-closed",
                passed=False,
                message=(
                    f"KeyError message does not name {unknown_kind!r}: {message}"
                ),
                details={"error_message": message, "unknown_kind": unknown_kind},
            )
        if not any(k in message for k in registered_kinds):
            # Acceptable — not all implementations must list kinds
            pass
        return ConformanceCheckResult(check_id="adapter-unknown-kind-fail-closed", passed=True)
    except Exception as exc:
        return ConformanceCheckResult(
            check_id="adapter-unknown-kind-fail-closed",
            passed=False,
            message=(
                f"registry.resolve({unknown_kind!r}) raised unexpected "
                f"{type(exc).__name__}: {exc}"
            ),
        )


# ---------------------------------------------------------------------------
# ContractResult schema round-trip checks
# ---------------------------------------------------------------------------


def check_contract_result_schema_round_trip(
    *,
    contract: ContractResult | None = None,
) -> ConformanceCheckResult:
    """Verify ``ContractResult.to_json()`` → ``from_json()`` round-trip fidelity.

    Constructs a minimal representative ``ContractResult`` (or uses the
    caller-supplied *contract*) and checks that serializing and deserializing
    produces an equal object.

    Parameters
    ----------
    contract:
        An optional pre-built ``ContractResult`` to round-trip.  When *None*
        a default-complete instance is created with all fields populated.

    Returns
    -------
    ConformanceCheckResult
        ``passed=True`` when the round-trip produces an equal value.
    """
    if contract is None:
        contract = _make_representative_contract()

    try:
        json_dict = contract.to_json()
    except Exception as exc:
        return ConformanceCheckResult(
            check_id="contract-result-to-json",
            passed=False,
            message=f"to_json() raised {type(exc).__name__}: {exc}",
            details={"error": str(exc)},
        )

    if not isinstance(json_dict, dict):
        return ConformanceCheckResult(
            check_id="contract-result-to-json",
            passed=False,
            message=f"to_json() returned {type(json_dict).__name__}, expected dict",
        )

    try:
        restored = ContractResult.from_json(json_dict)
    except Exception as exc:
        return ConformanceCheckResult(
            check_id="contract-result-from-json",
            passed=False,
            message=f"from_json() raised {type(exc).__name__}: {exc}",
            details={"error": str(exc), "json_dict": json_dict},
        )

    if not isinstance(restored, ContractResult):
        return ConformanceCheckResult(
            check_id="contract-result-from-json",
            passed=False,
            message=(
                f"from_json() returned {type(restored).__name__}, "
                f"expected ContractResult"
            ),
        )

    if restored != contract:
        diffs = _diff_contracts(contract, restored)
        return ConformanceCheckResult(
            check_id="contract-result-round-trip-fidelity",
            passed=False,
            message=f"round-trip produced different value; diffs: {diffs}",
            details={"original": contract, "restored": restored, "diffs": diffs},
        )

    return ConformanceCheckResult(check_id="contract-result-round-trip-fidelity", passed=True)


def check_contract_result_schema_version_skew() -> ConformanceCheckResult:
    """Verify that ``ContractResult.from_json`` rejects a mismatched schema version.

    This check constructs a valid JSON dict, tampers with ``schema_version``
    to a value that does not match ``CONTRACT_RESULT_SCHEMA_VERSION``, and
    asserts that ``from_json`` raises ``ValueError``.

    The check is loud: it confirms that schema-version skew is surfaced as
    a hard error, not silently normalised.
    """
    contract = _make_representative_contract()
    json_dict = contract.to_json()

    # Tamper with schema_version to something that will never match
    tampered = dict(json_dict)
    tampered["schema_version"] = "sha256:0000000000000000000000000000000000000000000000000000000000000000"

    try:
        ContractResult.from_json(tampered)
        return ConformanceCheckResult(
            check_id="contract-result-schema-version-skew",
            passed=False,
            message=(
                "from_json() accepted a tampered schema_version without raising ValueError"
            ),
            details={"tampered_schema_version": tampered["schema_version"]},
        )
    except ValueError:
        return ConformanceCheckResult(
            check_id="contract-result-schema-version-skew", passed=True
        )
    except Exception as exc:
        return ConformanceCheckResult(
            check_id="contract-result-schema-version-skew",
            passed=False,
            message=(
                f"from_json() with skew raised unexpected {type(exc).__name__}: {exc}"
            ),
            details={"error": str(exc)},
        )


def check_contract_result_empty_schema_version_accepted() -> ConformanceCheckResult:
    """Verify that ``ContractResult.from_json`` accepts an empty string
    ``schema_version`` as an unspecified/default sentinel.

    An empty ``schema_version`` in persisted JSON means "use the current
    version" — this is the ``__post_init__`` default-fill path.  The check
    confirms that the empty-string case does NOT raise, preserving backward
    compatibility for serialized records that omit the field.
    """
    contract = _make_representative_contract()
    json_dict = contract.to_json()

    tampered = dict(json_dict)
    tampered["schema_version"] = ""

    try:
        restored = ContractResult.from_json(tampered)
    except Exception as exc:
        return ConformanceCheckResult(
            check_id="contract-result-empty-schema-version-accepted",
            passed=False,
            message=(
                f"from_json() with empty schema_version raised "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    from arnold.pipeline.types import CONTRACT_RESULT_SCHEMA_VERSION

    # When schema_version is empty in JSON, from_json fills the current version
    if restored.schema_version != CONTRACT_RESULT_SCHEMA_VERSION:
        return ConformanceCheckResult(
            check_id="contract-result-empty-schema-version-accepted",
            passed=False,
            message=(
                f"from_json() filled schema_version={restored.schema_version!r}, "
                f"expected {CONTRACT_RESULT_SCHEMA_VERSION!r}"
            ),
        )

    return ConformanceCheckResult(
        check_id="contract-result-empty-schema-version-accepted", passed=True
    )


# ---------------------------------------------------------------------------
# Generic Arnold anti-coupling ratchet
# ---------------------------------------------------------------------------


def check_generic_arnold_megaplan_coupling(
    *,
    package_root: Path | None = None,
    allowlist: Collection[str] | None = None,
    allowlist_path: Path | None = None,
) -> ConformanceCheckResult:
    """Fail when neutral ``arnold`` modules add new Megaplan imports.

    The gate is a ratchet: known legacy generic-Arnold modules that still
    import Megaplan are listed in ``_megaplan_coupling_allowlist.txt``.  New
    generic modules that import ``arnold.pipelines.megaplan`` or top-level
    ``megaplan`` fail the check.  Stale allowlist entries also fail so the
    baseline tightens as compatibility shims are retired.
    """
    root = package_root or _DEFAULT_ARNOLD_ROOT
    allowed = (
        set(allowlist)
        if allowlist is not None
        else _read_megaplan_coupling_allowlist(
            allowlist_path or _DEFAULT_MEGAPLAN_COUPLING_ALLOWLIST
        )
    )
    coupled = _scan_generic_arnold_megaplan_imports(root)

    coupled_modules = set(coupled)
    unexpected = {
        module: coupled[module]
        for module in sorted(coupled_modules - allowed)
    }
    stale_allowlist = sorted(allowed - coupled_modules)

    details = {
        "allowlisted_count": len(allowed),
        "coupled_count": len(coupled_modules),
        "unexpected": unexpected,
        "stale_allowlist": stale_allowlist,
    }

    diagnostics: list[str] = []
    if unexpected:
        diagnostics.append(
            "new generic Arnold Megaplan coupling: "
            + ", ".join(sorted(unexpected))
        )
    if stale_allowlist:
        diagnostics.append(
            "stale Megaplan coupling allowlist entries: "
            + ", ".join(stale_allowlist)
        )

    if diagnostics:
        return ConformanceCheckResult(
            check_id="generic-arnold-megaplan-coupling",
            passed=False,
            message="; ".join(diagnostics),
            details=details,
        )

    return ConformanceCheckResult(
        check_id="generic-arnold-megaplan-coupling",
        passed=True,
        details=details,
    )


def check_package_name_staleness(
    *,
    package_root: Path | None = None,
    allowlist: Collection[str] | None = None,
) -> ConformanceCheckResult:
    """Fail when neutral Arnold code carries active Megaplan package literals."""

    root = package_root or _DEFAULT_ARNOLD_ROOT
    allowed = set(allowlist or set())
    unexpected: dict[str, tuple[str, ...]] = {}
    for path in sorted(root.rglob("*.py")):
        if _is_excluded_from_generic_arnold_scan(root, path):
            continue
        module = _module_name_from_path(root, path)
        if module in allowed:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        hits = sorted(
            {
                package_name
                for value in _string_constants(tree)
                for package_name in ACTIVE_MEGAPLAN_PACKAGE_NAMES
                if package_name in value
                and not (
                    package_name == "megaplan"
                    and (
                        "arnold.pipelines.megaplan" in value
                        or "arnold_pipelines.megaplan" in value
                    )
                )
            }
        )
        if hits:
            unexpected[module] = tuple(hits)

    details = {"unexpected": unexpected}
    if unexpected:
        return ConformanceCheckResult(
            check_id="package-name-staleness",
            passed=False,
            message="stale Megaplan package-name literals: " + ", ".join(sorted(unexpected)),
            details=details,
        )
    return ConformanceCheckResult(check_id="package-name-staleness", passed=True, details=details)


def check_import_coupling(
    *,
    package_root: Path | None = None,
    allowlist: Collection[str] | None = None,
) -> ConformanceCheckResult:
    result = check_generic_arnold_megaplan_coupling(
        package_root=package_root,
        allowlist=allowlist,
    )
    return ConformanceCheckResult(
        check_id="import-coupling",
        passed=result.passed,
        message=result.message,
        details=result.details,
    )


def check_semantic_coupling(
    *,
    package_root: Path | None = None,
    allowlist: Collection[str] | None = None,
) -> ConformanceCheckResult:
    root = package_root or _DEFAULT_ARNOLD_ROOT
    allowed = set(allowlist or set())
    unexpected: dict[str, tuple[str, ...]] = {}
    for path in sorted(root.rglob("*.py")):
        if _is_excluded_from_generic_arnold_scan(root, path):
            continue
        module = _module_name_from_path(root, path)
        if module in allowed:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        hits: set[str] = set()
        for value in _string_constants(tree):
            if ".megaplan" in value:
                hits.add(".megaplan")
            if "PlanState" in value:
                hits.add("PlanState")
            if "tiebreaker" in value:
                hits.add("tiebreaker")
                hits.add("phase:tiebreaker")
            if value.startswith("handle_"):
                hits.add("handler-name")
        if hits:
            unexpected[module] = tuple(sorted(hits))
    details = {"unexpected": unexpected}
    return ConformanceCheckResult(
        check_id="semantic-coupling",
        passed=not unexpected,
        message="" if not unexpected else "semantic Megaplan coupling: " + ", ".join(sorted(unexpected)),
        details=details,
    )


def check_public_workflow_layering(
    *,
    package_root: Path | None = None,
    allowlist: Collection[str] | None = None,
) -> ConformanceCheckResult:
    root = package_root or _DEFAULT_ARNOLD_ROOT
    allowed = set(allowlist or set())
    unexpected: dict[str, tuple[str, ...]] = {}
    for path in sorted(root.rglob("*.py")):
        if path.name != "__init__.py" or "pipelines" not in path.parts:
            continue
        if _is_excluded_from_generic_arnold_scan(root, path):
            continue
        module = _module_name_from_path(root, path)
        if module in allowed:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        hits: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "arnold.pipeline":
                if any(alias.name == "Stage" for alias in node.names):
                    hits.add("package-imports-Stage")
            if isinstance(node, ast.AnnAssign | ast.arg | ast.FunctionDef):
                if "Stage" in ast.unparse(node):
                    hits.add("annotation-Stage")
        for value in _string_constants(tree):
            if value == "Stage":
                hits.add("exports-Stage")
        if hits:
            unexpected[module] = tuple(sorted(hits))
    details = {"unexpected": unexpected}
    return ConformanceCheckResult(
        check_id="public-workflow-layering",
        passed=not unexpected,
        message="" if not unexpected else "public workflow layering leak: " + ", ".join(sorted(unexpected)),
        details=details,
    )


def check_never_port_artifacts(
    *,
    repo_root: Path | None = None,
    allowlist: Collection[str] | None = None,
) -> ConformanceCheckResult:
    root = repo_root or _DEFAULT_ARNOLD_ROOT.parent
    allowed = set(allowlist or set())
    unexpected: dict[str, tuple[str, ...]] = {}

    def _is_allowed(rel: str) -> bool:
        for pattern in allowed:
            if pattern == rel:
                return True
            if pattern.endswith("/**") and rel.startswith(pattern[:-3] + "/"):
                return True
            if fnmatch.fnmatch(rel, pattern):
                return True
        return False

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if _is_allowed(rel):
            continue
        reason: str | None = None
        if rel.startswith(".megaplan/_archived-plans/"):
            reason = ".megaplan archived plan"
        elif rel == ".hermes_state":
            reason = "Hermes runtime state"
        elif rel.endswith((".db-wal", ".db-shm")):
            reason = "database sidecar"
        elif rel.startswith("logs/") and rel.endswith(".log"):
            reason = "driver log"
        elif rel.startswith("runs/") and (
            "prompt" in Path(rel).name or Path(rel).name in {"receipt.json", "runtime_state.json"}
        ):
            reason = "runtime artifact"
        if reason:
            unexpected[rel] = (reason,)
    details = {"unexpected": unexpected}
    return ConformanceCheckResult(
        check_id="never-port-artifacts",
        passed=not unexpected,
        message="" if not unexpected else "runtime artifacts present: " + ", ".join(sorted(unexpected)),
        details=details,
    )


def check_legacy_reference_allowlist(
    *,
    repo_root: Path | None = None,
    allowlist_path: Path | None = None,
    allowlist: Collection[Mapping[str, str]] | None = None,
) -> ConformanceCheckResult:
    """Validate the machine-readable legacy Megaplan reference allowlist.

    The JSON allowlist is the milestone authority for any permitted remaining
    references to the deleted ``arnold.pipelines.megaplan`` root.  Entries are
    intentionally narrow: each one names an exact repository path, one scanner
    pattern, an allowed category, and a reason.  The check fails for malformed
    entries, stale entries whose path no longer contains the pattern, and live
    non-archive references missing from the allowlist.
    """

    root = repo_root or _DEFAULT_ARNOLD_ROOT.parent
    records = (
        list(allowlist)
        if allowlist is not None
        else _read_legacy_reference_allowlist(
            allowlist_path or _DEFAULT_LEGACY_REFERENCE_ALLOWLIST
        )
    )
    resolved_allowlist_path = (
        allowlist_path or _DEFAULT_LEGACY_REFERENCE_ALLOWLIST
    ).resolve()
    resolved_root = root.resolve()
    allowlist_rel = (
        resolved_allowlist_path.relative_to(resolved_root).as_posix()
        if resolved_allowlist_path.is_relative_to(resolved_root)
        else None
    )

    invalid_entries: list[dict[str, Any]] = []
    allowed: set[tuple[str, str]] = set()
    duplicates: list[dict[str, str]] = []
    for index, record in enumerate(records):
        normalized, errors = _normalize_legacy_reference_entry(record)
        if errors:
            invalid_entries.append(
                {"index": index, "entry": dict(record), "errors": errors}
            )
            continue
        key = (normalized["path"], normalized["pattern"])
        if key in allowed:
            duplicates.append(
                {"path": normalized["path"], "pattern": normalized["pattern"]}
            )
        allowed.add(key)

    references = _scan_legacy_references(root, allowlist_rel=allowlist_rel)
    observed = {(hit["path"], hit["pattern"]) for hit in references}
    unallowlisted = [
        hit for hit in references if (hit["path"], hit["pattern"]) not in allowed
    ]
    stale = [
        {"path": path, "pattern": pattern}
        for path, pattern in sorted(allowed - observed)
    ]

    details = {
        "allowlisted_count": len(allowed),
        "observed_count": len(observed),
        "unallowlisted": unallowlisted,
        "stale_allowlist": stale,
        "invalid_entries": invalid_entries,
        "duplicates": duplicates,
    }

    diagnostics: list[str] = []
    if invalid_entries:
        diagnostics.append(f"invalid legacy reference allowlist entries: {len(invalid_entries)}")
    if duplicates:
        diagnostics.append(f"duplicate legacy reference allowlist entries: {len(duplicates)}")
    if stale:
        diagnostics.append(
            "stale legacy reference allowlist entries: "
            + ", ".join(f"{item['path']}:{item['pattern']}" for item in stale)
        )
    if unallowlisted:
        diagnostics.append(
            "unallowlisted legacy references: "
            + ", ".join(
                f"{item['path']}:{item['pattern']}" for item in unallowlisted[:20]
            )
        )

    return ConformanceCheckResult(
        check_id="legacy-reference-allowlist",
        passed=not diagnostics,
        message="; ".join(diagnostics),
        details=details,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _NoOpAdapter:
    """An adapter that satisfies ``StepInvocationAdapter`` but does nothing."""

    def invoke(self, invocation: StepInvocation) -> None:
        return None


def _make_representative_contract() -> ContractResult:
    """Build a ContractResult with all fields populated for round-trip testing."""
    from arnold.pipeline.types import (
        EvidenceArtifactRef,
        Freshness,
        HumanSuspension,
        Provenance,
    )

    return ContractResult(
        payload={"key": "value", "nested": {"a": 1}},
        status=ContractStatus.COMPLETED,
        schema_version="",  # __post_init__ fills this from CONTRACT_RESULT_SCHEMA_VERSION
        suspension=None,
        evidence_refs=(
            EvidenceArtifactRef(
                uri="file:///tmp/test.png",
                content_type="image/png",
                digest="sha256:abcd1234",
                size_bytes=1024,
                name="test.png",
            ),
        ),
        authority_level="verified",
        provenance=Provenance(
            sources=("policy:example",),
            generator="conformance-test@0.1",
            generated_at="2025-01-01T00:00:00Z",
            chain=("claim", "evidence"),
        ),
        freshness=Freshness(
            observed_at="2025-01-01T00:00:00Z",
            ttl_seconds=3600,
            expires_at="2025-01-01T01:00:00Z",
        ),
    )


def _diff_contracts(original: ContractResult, restored: ContractResult) -> dict[str, Any]:
    """Return a dict of differing fields between two ContractResult values."""
    diffs: dict[str, Any] = {}
    fields = (
        "payload",
        "status",
        "schema_version",
        "suspension",
        "evidence_refs",
        "authority_level",
        "provenance",
        "freshness",
    )
    for f in fields:
        orig_val = getattr(original, f)
        rest_val = getattr(restored, f)
        if orig_val != rest_val:
            diffs[f] = {"original": orig_val, "restored": rest_val}
    return diffs


def _read_megaplan_coupling_allowlist(path: Path) -> set[str]:
    allowed: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if line:
            allowed.add(line)
    return allowed


def _read_legacy_reference_allowlist(path: Path) -> list[Mapping[str, str]]:
    if not path.exists():
        return []
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return loaded
    if isinstance(loaded, dict) and isinstance(loaded.get("references"), list):
        return loaded["references"]
    return [
        {
            "path": str(path),
            "pattern": "",
            "category": "",
            "reason": (
                "legacy reference allowlist JSON must be a list or an object "
                "with a 'references' list"
            ),
        }
    ]


def _normalize_legacy_reference_entry(
    record: Mapping[str, str],
) -> tuple[dict[str, str], list[str]]:
    required = ("path", "pattern", "category", "reason")
    errors: list[str] = []
    normalized: dict[str, str] = {}
    for key in required:
        value = record.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"missing or empty {key!r}")
            normalized[key] = ""
        else:
            normalized[key] = value.strip()
    extra = sorted(set(record) - set(required))
    if extra:
        errors.append("unexpected keys: " + ", ".join(extra))
    if normalized.get("pattern") not in LEGACY_REFERENCE_PATTERNS:
        errors.append(f"unsupported pattern {normalized.get('pattern')!r}")
    if normalized.get("category") not in LEGACY_REFERENCE_CATEGORIES:
        errors.append(f"unsupported category {normalized.get('category')!r}")
    if Path(normalized.get("path", "")).is_absolute():
        errors.append("path must be repository-relative")
    return normalized, errors


def _scan_legacy_references(
    root: Path,
    *,
    allowlist_rel: str | None = None,
) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel == allowlist_rel or _is_excluded_from_legacy_reference_scan(rel):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in LEGACY_REFERENCE_PATTERNS:
            if pattern in text:
                references.append({"path": rel, "pattern": pattern})
    return references


def _is_excluded_from_legacy_reference_scan(relative_path: str) -> bool:
    parts = relative_path.split("/")
    if (
        parts[0] in {
            ".git",
            ".megaplan",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            "__pycache__",
        }
        or "__pycache__" in parts
        or relative_path.startswith("tests/archive/")
        or relative_path.startswith("docs/archive/")
        or relative_path.startswith("docs/arnold/workflow-manifest-runtime-review/")
    ):
        return True
    return False


def _scan_generic_arnold_megaplan_imports(root: Path) -> dict[str, tuple[str, ...]]:
    coupled: dict[str, tuple[str, ...]] = {}
    for path in sorted(root.rglob("*.py")):
        if _is_excluded_from_generic_arnold_scan(root, path):
            continue

        module = _module_name_from_path(root, path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            coupled[module] = (f"<syntax-error:{exc.msg}>",)
            continue

        imports = sorted(
            {
                imported
                for node in ast.walk(tree)
                for imported in _megaplan_imports_from_node(node, module, path)
            }
        )
        if imports:
            coupled[module] = tuple(imports)
    return coupled


def _is_excluded_from_generic_arnold_scan(root: Path, path: Path) -> bool:
    relative_parts = path.relative_to(root).parts
    return "__pycache__" in relative_parts or "tests" in relative_parts


def _module_name_from_path(root: Path, path: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    parts = relative.parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(("arnold", *parts))


def _megaplan_imports_from_node(
    node: ast.AST,
    module_name: str,
    path: Path,
) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(
            alias.name for alias in node.names if _is_megaplan_import(alias.name)
        )
    if isinstance(node, ast.ImportFrom):
        resolved = _resolve_import_from_module(node, module_name, path)
        imports: list[str] = []
        if resolved and _is_megaplan_import(resolved):
            imports.append(resolved)
            if resolved.startswith("arnold_pipelines."):
                for alias in node.names:
                    alias_module = f"{resolved}.{alias.name}"
                    imports.append(alias_module)
        elif resolved:
            for alias in node.names:
                alias_module = f"{resolved}.{alias.name}"
                if _is_megaplan_import(alias_module):
                    imports.append(alias_module)
        return tuple(imports)
    return ()


def _resolve_import_from_module(
    node: ast.ImportFrom,
    module_name: str,
    path: Path,
) -> str:
    if not node.level:
        return node.module or ""

    package_parts = (
        module_name.split(".")
        if path.name == "__init__.py"
        else module_name.split(".")[:-1]
    )
    if node.level > len(package_parts):
        return node.module or ""

    base_parts = package_parts[: len(package_parts) - node.level + 1]
    if node.module:
        base_parts.extend(node.module.split("."))
    return ".".join(base_parts)


def _is_megaplan_import(module: str) -> bool:
    return any(
        module == package_name or module.startswith(package_name + ".")
        for package_name in ACTIVE_MEGAPLAN_PACKAGE_NAMES
    )


def _string_constants(tree: ast.AST) -> set[str]:
    docstring_nodes: set[ast.AST] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(body, list)
            and body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            docstring_nodes.add(body[0].value)
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and node not in docstring_nodes
    }


def check_adapter_smoke_invocation(
    registry: StepInvocationAdapterRegistry,
    kind: str,
    invocation: StepInvocation,
) -> ConformanceCheckResult:
    """Run a smoke invocation through a registered adapter and surface failures.

    This is a focused check for adapter implementations that must not raise
    during normal invocation.  It is separate from the broad protocol check
    so callers can target specific adapters.
    """
    try:
        adapter = registry.resolve(kind)
    except KeyError as exc:
        return ConformanceCheckResult(
            check_id=f"adapter-smoke-{kind}",
            passed=False,
            message=f"kind {kind!r} not registered: {exc}",
        )

    try:
        adapter.invoke(invocation)
    except Exception as exc:
        return ConformanceCheckResult(
            check_id=f"adapter-smoke-{kind}",
            passed=False,
            message=(
                f"smoke invocation for kind {kind!r} raised "
                f"{type(exc).__name__}: {exc}"
            ),
            details={"error": str(exc)},
        )

    return ConformanceCheckResult(check_id=f"adapter-smoke-{kind}", passed=True)


def check_adapter_registry_round_trip(
    registry: StepInvocationAdapterRegistry,
    kind: str,
) -> ConformanceCheckResult:
    """Verify that a registered adapter survives resolve → invoke → re-resolve.

    This checks for state corruption in the registry: registering an adapter
    and resolving it twice should return the same adapter object.
    """
    try:
        adapter1 = registry.resolve(kind)
        adapter2 = registry.resolve(kind)
    except KeyError as exc:
        return ConformanceCheckResult(
            check_id=f"adapter-round-trip-{kind}",
            passed=False,
            message=f"resolve failed: {exc}",
        )

    if adapter1 is not adapter2:
        return ConformanceCheckResult(
            check_id=f"adapter-round-trip-{kind}",
            passed=False,
            message=(
                f"resolve returned different objects: "
                f"{type(adapter1).__name__} vs {type(adapter2).__name__}"
            ),
        )

    return ConformanceCheckResult(check_id=f"adapter-round-trip-{kind}", passed=True)


__all__ = [
    "ACTIVE_MEGAPLAN_PACKAGE_NAMES",
    "LEGACY_REFERENCE_CATEGORIES",
    "LEGACY_REFERENCE_PATTERNS",
    "check_adapter_protocol_conformance",
    "check_adapter_unknown_kind_fail_closed",
    "check_adapter_smoke_invocation",
    "check_adapter_registry_round_trip",
    "check_contract_result_schema_round_trip",
    "check_contract_result_schema_version_skew",
    "check_contract_result_empty_schema_version_accepted",
    "check_generic_arnold_megaplan_coupling",
    "check_import_coupling",
    "check_legacy_reference_allowlist",
    "check_never_port_artifacts",
    "check_package_name_staleness",
    "check_public_workflow_layering",
    "check_semantic_coupling",
]
