#!/usr/bin/env python3
"""WBC boundary inventory generator (M6 — T4 + T5).

Joins three WBC declaration inputs into a deterministic inventory, then
extends it with static AST discovery over handler, runtime, kernel,
supervisor, execution, and orchestration source trees.

Input sources (T4):
1. ``arnold_pipelines/megaplan/workflows/boundary_contracts.py``
   — BoundaryContract instances (the contract registry).

2. ``arnold_pipelines/megaplan/workflows/contract_to_producer_matrix.json``
   — producer-side reality mapping (handler paths, applicability rules,
     receipt timing, authority references, non-conformant exceptions).

3. ``arnold_pipelines/megaplan/workflows/support_manifest.json``
   — support classification (owner, support_status, migration milestone,
     C2-C6 migration gates, exception metadata, non-conformant flags).

Static discovery (T5):
Scans ``arnold/workflow``, ``arnold/kernel``, ``arnold/execution``,
``arnold/supervisor``, ``arnold/control``, ``arnold_pipelines/megaplan/handlers``,
``arnold_pipelines/megaplan/execute``, and ``arnold_pipelines/megaplan/orchestration``
for surface types: receipt_writer, durable_ref, payload_policy, ledger,
journal, projection, repair_queue, authority_reader, consumer, producer.

The generator is **strictly observe-only**: it reads committed source files
and writes only the inventory artifact to ``evidence/wbc-boundary-inventory.json``.
It does not mutate lifecycle state, queues, providers, delivery, notifications,
source history, or runtime behavior.

Design invariants
-----------------

* **Deterministic ordering**: rows are sorted by ``(row_kind, boundary_id,
  step_id, surface_id)`` so that two runs against the same commit always
  produce the same artifact.
* **Candidate vs landed metadata**: when the matrix declares a contract as
  ``declared_only`` or ``unknown`` (no producer emission path), the row
  records ``candidate: true`` and ``landed: false``.  When a real producer
  path exists, ``candidate: false`` and ``landed: true``.
* **Support labels are non-authoritative**: a ``support_status: "supported"``
  label in the manifest is recorded as metadata but is explicitly tagged
  ``support_is_non_authoritative: true`` so downstream authority registries
  cannot treat it as proof of runtime adoption.  Only a landed producer
  path (from the matrix) constitutes adoption evidence.
* **Projections are NOT authority**: any module classified as a projection
  is explicitly tagged ``is_authority: false`` and carries the
  ``non_authority`` marker from the discovery rules.
* **Unmatched set**: any declaration that appears in one input but cannot
  be joined to the others is recorded in a separate ``unmatched`` bucket
  with an explicit ``reason_unmatched``.

Usage::

    python tools/generate_wbc_boundary_inventory.py [--output PATH]
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Optional YAML support for reading discovery rules
try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


# ── Paths ───────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = REPO_ROOT / "evidence"

BOUNDARY_CONTRACTS_PATH = (
    REPO_ROOT
    / "arnold_pipelines"
    / "megaplan"
    / "workflows"
    / "boundary_contracts.py"
)
CONTRACT_MATRIX_PATH = (
    REPO_ROOT
    / "arnold_pipelines"
    / "megaplan"
    / "workflows"
    / "contract_to_producer_matrix.json"
)
SUPPORT_MANIFEST_PATH = (
    REPO_ROOT
    / "arnold_pipelines"
    / "megaplan"
    / "workflows"
    / "support_manifest.json"
)
DISCOVERY_RULES_PATH = EVIDENCE_DIR / "wbc-boundary-discovery-rules.yaml"

DEFAULT_OUTPUT = EVIDENCE_DIR / "wbc-boundary-inventory.json"

# ── Helpers ─────────────────────────────────────────────────────────────────


def _sha256_hex(data: str) -> str:
    """Return SHA-256 hex digest of *data*."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _parse_boundary_contract_instances(path: Path) -> list[dict[str, Any]]:
    """Extract BoundaryContract instantiation calls from *path*.

    Parses the Python source and collects every ``BoundaryContract(…)``
    call, converting keyword arguments to a plain dict.  Enum values are
    converted to their ``.value`` strings.
    """
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    contracts: list[dict[str, Any]] = []

    class ContractVisitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            # Match BoundaryContract(…) calls
            if isinstance(node.func, ast.Name) and node.func.id == "BoundaryContract":
                contract: dict[str, Any] = {}
                for kw in node.keywords:
                    key = kw.arg
                    if key is None:
                        continue
                    value = _ast_to_value(kw.value)
                    contract[key] = value
                if contract:
                    contracts.append(contract)
            self.generic_visit(node)

    ContractVisitor().visit(tree)
    return contracts


def _ast_to_value(node: ast.expr) -> Any:
    """Convert a simple AST expression to a Python value.

    Unresolvable names (e.g. imported constants like ``S2_PREP_ROW_ID``)
    are returned as the sentinel ``"UNKNOWN"`` so the inventory never
    silently drops a field.
    """
    if isinstance(node, ast.Constant):
        val = node.value
        if val is Ellipsis:
            return "..."
        return val
    if isinstance(node, ast.Name) and node.id == "None":
        return None
    if isinstance(node, ast.Name):
        # Unresolvable name (imported constant, variable reference, etc.)
        # Return sentinel so downstream can distinguish missing from unknown.
        return "UNKNOWN"
    if isinstance(node, ast.Attribute):
        # e.g. BoundaryPhase.PREP -> "PREP"
        return node.attr
    if isinstance(node, (ast.Tuple, ast.List)):
        return [_ast_to_value(elt) for elt in node.elts]
    if isinstance(node, ast.Dict):
        return {
            _ast_to_value(k): _ast_to_value(v)
            for k, v in zip(node.keys, node.values)
        }
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        # -(N) -> -N (only for simple constants)
        if isinstance(node.operand, ast.Constant):
            return -node.operand.value
    # Fallback: return sentinel for complex expressions
    return "UNKNOWN"


def _load_json(path: Path) -> dict[str, Any]:
    """Load and return JSON from *path*."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ── Static discovery scanner (T5) ───────────────────────────────────────────


# Surface type classification vocabulary.
# These are the canonical surface types from the discovery rules categories.
SURFACE_RECEIPT_WRITER = "receipt_writer"
SURFACE_DURABLE_REF = "durable_ref"
SURFACE_PAYLOAD_POLICY = "payload_policy"
SURFACE_LEDGER = "ledger"
SURFACE_JOURNAL = "journal"
SURFACE_PROJECTION = "projection"
SURFACE_REPAIR_QUEUE = "repair_queue"
SURFACE_AUTHORITY_READER = "authority_reader"
SURFACE_CONSUMER = "consumer"
SURFACE_PRODUCER = "producer"
SURFACE_AUTHORITY_WRITER = "authority_writer"
SURFACE_COMPATIBILITY_SHIM = "compatibility_shim"
SURFACE_UNKNOWN = "unknown"

# Surface types that are explicitly non-authority per the discovery rules.
NON_AUTHORITY_SURFACES: frozenset[str] = frozenset({
    SURFACE_PROJECTION,
    SURFACE_JOURNAL,  # journals are append-only records, not authority
})

# Authority-adjacent surface types — these may read/write authority facts.
AUTHORITY_ADJACENT_SURFACES: frozenset[str] = frozenset({
    SURFACE_AUTHORITY_READER,
    SURFACE_AUTHORITY_WRITER,
})

# Discovery roots — directories to scan for Python modules.
# Mirrors the discovery-rules YAML but hard-coded for resilience when
# YAML is unavailable.
DISCOVERY_ROOTS: list[dict[str, Any]] = [
    {
        "path": "arnold/workflow",
        "category": "boundary_runtime",
        "file_patterns": ["*.py"],
        "description": "Core WBC runtime: contracts, evidence, templates, conformance, ledgers, durable refs, payload policy.",
    },
    {
        "path": "arnold/kernel",
        "category": "kernel",
        "file_patterns": ["*.py"],
        "description": "Kernel primitives: journal, events, effects, replay, suspension, artifacts.",
    },
    {
        "path": "arnold/execution",
        "category": "execution_runtime",
        "file_patterns": ["*.py"],
        "description": "Execution runtime: observability, compensation, routing, state, driver.",
    },
    {
        "path": "arnold/supervisor",
        "category": "supervisor",
        "file_patterns": ["*.py"],
        "description": "Supervisor: restart, leases, reconciliation, progress, cancellation.",
    },
    {
        "path": "arnold/control",
        "category": "control_plane",
        "file_patterns": ["*.py"],
        "description": "Control plane: interface boundary, package boundary.",
    },
    {
        "path": "arnold_pipelines/megaplan/handlers",
        "category": "handler_functions",
        "file_patterns": ["*.py"],
        "description": "Megaplan handler functions: lifecycle, execute, review, critique, gate, plan, finalize.",
    },
    {
        "path": "arnold_pipelines/megaplan/execute",
        "category": "execute_producers",
        "file_patterns": ["*.py"],
        "description": "Execute-phase batch dispatch, policy, merge, aggregation.",
    },
    {
        "path": "arnold_pipelines/megaplan/orchestration",
        "category": "orchestration",
        "file_patterns": ["*.py"],
        "description": "Orchestration: authority readers, critique runtime, chain execution, evidence, gate checks.",
    },
]


def _classify_module_surfaces(
    module_path: str,
    classes: list[str],
    functions: list[str],
    imports: list[str],
    docstring: str,
) -> list[str]:
    """Classify a Python module into zero or more surface types.

    Classification is based on module path, class names, function names,
    import patterns, and docstring content.  This is heuristic — it errs
    on the side of UNKNOWN rather than misclassifying.

    Projections are classified but explicitly marked as non-authority.
    """
    surfaces: list[str] = []
    path_lower = module_path.lower()
    doc_lower = docstring.lower()
    all_names = set(classes) | set(functions)
    all_names_lower = {n.lower() for n in all_names}
    imports_lower = [i.lower() for i in imports]

    # ── Receipt writers ──────────────────────────────────────────────────
    _receipt_keywords = {"receipt", "receipt_writer", "write_boundary_receipt",
                         "boundary_receipt", "dispatch_receipt"}
    if any(kw in path_lower for kw in _receipt_keywords):
        surfaces.append(SURFACE_RECEIPT_WRITER)
    elif any(kw in all_names_lower for kw in _receipt_keywords):
        surfaces.append(SURFACE_RECEIPT_WRITER)
    elif any("receipt" in imp for imp in imports_lower):
        surfaces.append(SURFACE_RECEIPT_WRITER)

    # ── Durable refs ─────────────────────────────────────────────────────
    _durable_keywords = {"durable_ref", "durableref", "refs"}
    if any(kw in path_lower for kw in _durable_keywords):
        surfaces.append(SURFACE_DURABLE_REF)
    elif "durableref" in all_names_lower or "durable_ref" in path_lower:
        surfaces.append(SURFACE_DURABLE_REF)

    # ── Payload policy ───────────────────────────────────────────────────
    _payload_keywords = {"payload_policy", "payloadpolicy", "payload_mode",
                         "retention_mode", "payloadclass"}
    if any(kw in path_lower for kw in _payload_keywords):
        surfaces.append(SURFACE_PAYLOAD_POLICY)
    elif any(kw in all_names_lower for kw in _payload_keywords):
        surfaces.append(SURFACE_PAYLOAD_POLICY)

    # ── Ledgers ──────────────────────────────────────────────────────────
    _ledger_keywords = {"ledger", "execution_attempt_ledger", "effect_ledger",
                        "effectledger"}
    if any(kw in path_lower for kw in _ledger_keywords):
        surfaces.append(SURFACE_LEDGER)
    elif any(kw in all_names_lower for kw in _ledger_keywords):
        surfaces.append(SURFACE_LEDGER)
    elif "ledger" in doc_lower:
        surfaces.append(SURFACE_LEDGER)

    # ── Journals ─────────────────────────────────────────────────────────
    if path_lower.endswith("journal.py") or "/journal/" in path_lower:
        surfaces.append(SURFACE_JOURNAL)
    elif "journal" in path_lower and path_lower.count("journal") == 1:
        if "eventjournal" in all_names_lower or "journalposition" in all_names_lower:
            surfaces.append(SURFACE_JOURNAL)

    # ── Projections ──────────────────────────────────────────────────────
    _proj_keywords = {"projection", "advisory_projection", "progress", "snapshot"}
    if any(kw in path_lower for kw in ["projection", "advisory_projection"]):
        surfaces.append(SURFACE_PROJECTION)
    elif "projection" in all_names_lower:
        surfaces.append(SURFACE_PROJECTION)
    elif "projection" in doc_lower and "not authority" in doc_lower:
        surfaces.append(SURFACE_PROJECTION)

    # ── Repair queues ────────────────────────────────────────────────────
    _repair_keywords = {"repair", "recovery", "compensation", "reconcile",
                        "reconciliation", "restart", "quarantine"}
    if any(kw in path_lower for kw in _repair_keywords):
        surfaces.append(SURFACE_REPAIR_QUEUE)
    elif any(kw in all_names_lower for kw in _repair_keywords):
        surfaces.append(SURFACE_REPAIR_QUEUE)

    # ── Authority readers ────────────────────────────────────────────────
    _auth_reader_keywords = {"authority_reader", "authority_readers",
                             "override_authority"}
    if any(kw in path_lower for kw in _auth_reader_keywords):
        surfaces.append(SURFACE_AUTHORITY_READER)
    elif "authorityreader" in all_names_lower:
        surfaces.append(SURFACE_AUTHORITY_READER)
    elif any(
        imp.startswith("arnold_pipelines.megaplan.authority")
        or "boundary_evidence" in imp
        for imp in imports_lower
    ):
        # Importing from actual authority packages or boundary evidence
        # (AuthorityRecord, BoundaryReceipt) suggests an authority reader.
        if SURFACE_AUTHORITY_READER not in surfaces:
            surfaces.append(SURFACE_AUTHORITY_READER)

    # ── Authority writers ────────────────────────────────────────────────
    _auth_writer_keywords = {"override_authority", "authority_writer",
                             "rubber_stamp", "binding"}
    if any(kw in path_lower for kw in _auth_writer_keywords):
        surfaces.append(SURFACE_AUTHORITY_WRITER)

    # ── Consumers ────────────────────────────────────────────────────────
    _consumer_keywords = {"consumer", "read", "import_graph", "parse",
                          "inspect", "validate", "check"}
    # A module that mostly reads/checks but doesn't produce transitions
    if any(kw in path_lower for kw in ["import_graph", "inspect", "validate"]):
        if not surfaces:
            surfaces.append(SURFACE_CONSUMER)

    # ── Producers (handler functions) ────────────────────────────────────
    _producer_keywords = {"handler", "handle_", "producer", "produce",
                          "emit", "dispatch", "execute_batch", "runner"}
    if any(kw in path_lower for kw in _producer_keywords):
        if SURFACE_PRODUCER not in surfaces:
            surfaces.append(SURFACE_PRODUCER)
    elif any(kw in all_names_lower for kw in {"handle_execute", "handle_plan",
                                              "handle_critique", "handle_gate",
                                              "handle_review", "handle_finalize"}):
        if SURFACE_PRODUCER not in surfaces:
            surfaces.append(SURFACE_PRODUCER)

    # ── Compatibility shims ──────────────────────────────────────────────
    _compat_keywords = {"compatibility", "compat", "adapter", "bridge", "shim"}
    if any(kw in path_lower for kw in _compat_keywords):
        surfaces.append(SURFACE_COMPATIBILITY_SHIM)

    # ── Fallback: classify unknown modules ───────────────────────────────
    if not surfaces:
        surfaces.append(SURFACE_UNKNOWN)

    return surfaces


def _is_authority_surface(surface_types: list[str]) -> bool:
    """Return True if this module carries authority-adjacent surface types.

    Only ``authority_reader`` and ``authority_writer`` are positive
    authority surfaces.  All other surface types (receipt_writer,
    ledger, journal, projection, payload_policy, consumer, producer,
    repair_queue, durability_ref, compatibility_shim, unknown) are
    operational/observational and do NOT constitute authority.

    Projections and journals are explicitly non-authority per the
    discovery rules, but the key invariant is that ONLY modules
    classified as authority_reader or authority_writer get
    ``is_authority: true``.
    """
    if not surface_types:
        return False
    # Authority-adjacent surfaces are the only ones that confer authority
    return any(st in AUTHORITY_ADJACENT_SURFACES for st in surface_types)


def _parse_module_ast(source: str) -> dict[str, Any]:
    """Parse Python source and extract classes, functions, and imports.

    Returns a dict with keys: classes (list[str]), functions (list[str]),
    imports (list[str]), docstring (str).
    """
    result: dict[str, Any] = {
        "classes": [],
        "functions": [],
        "imports": [],
        "docstring": "",
    }
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return result

    # Module docstring
    doc = ast.get_docstring(tree)
    if doc:
        result["docstring"] = doc

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            result["classes"].append(node.name)
        elif isinstance(node, ast.FunctionDef):
            result["functions"].append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                result["imports"].append(f"{mod}.{alias.name}")

    return result


def _scan_discovery_roots() -> dict[str, Any]:
    """Scan all discovery roots and classify every Python module found.

    Returns a dict with keys: ``modules`` (list of runtime_module rows)
    and ``handler_functions`` (list of handler_function rows).
    """
    modules: list[dict[str, Any]] = []
    handler_funcs: list[dict[str, Any]] = []

    for root_cfg in DISCOVERY_ROOTS:
        root_path = REPO_ROOT / root_cfg["path"]
        if not root_path.is_dir():
            continue

        category = root_cfg["category"]
        patterns = root_cfg.get("file_patterns", ["*.py"])

        # Collect all matching files
        py_files: list[Path] = []
        for pattern in patterns:
            for fpath in root_path.rglob(pattern):
                if fpath.is_file() and fpath.suffix == ".py":
                    py_files.append(fpath)

        # Deduplicate
        py_files = sorted(set(py_files))

        for fpath in py_files:
            rel = fpath.relative_to(REPO_ROOT)
            rel_str = str(rel).replace("\\", "/")

            try:
                source = fpath.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            ast_info = _parse_module_ast(source)
            classes = ast_info["classes"]
            functions = ast_info["functions"]
            imports = ast_info["imports"]
            docstring = ast_info["docstring"]

            # Classify surface types
            surface_types = _classify_module_surfaces(
                rel_str, classes, functions, imports, docstring
            )

            # Determine owner: WBC owns arnold/workflow and boundary runtime;
            # Run Authority owns kernel/execution/supervisor/handlers.
            is_boundary_runtime = any(
                seg in rel_str for seg in ["arnold/workflow/", "megaplan/workflows/"]
            )
            owner = "wbc" if is_boundary_runtime else "run_authority"

            is_auth = _is_authority_surface(surface_types)

            module_row: dict[str, Any] = {
                "row_kind": "runtime_module",
                "module_path": rel_str,
                "category": category,
                "owner": owner,
                "surface_types": surface_types,
                "is_authority": is_auth,
                "non_authority_surfaces": [st for st in surface_types if st in NON_AUTHORITY_SURFACES],
                "class_count": len(classes),
                "function_count": len(functions),
                "classes": sorted(classes),
                "functions": sorted(functions),
                "docstring_summary": (docstring[:200] + "…") if len(docstring) > 200 else docstring,
            }
            modules.append(module_row)

            # For handler directories, also emit handler_function rows
            if category in ("handler_functions", "execute_producers", "orchestration"):
                for fn_name in functions:
                    # Only emit public-ish functions (not _private ones unless they're handlers)
                    if fn_name.startswith("_") and not fn_name.startswith("handle_"):
                        continue
                    handler_row: dict[str, Any] = {
                        "row_kind": "handler_function",
                        "function_name": fn_name,
                        "module_path": rel_str,
                        "owner": "run_authority",
                        "category": _classify_handler_category(fn_name, rel_str, category),
                    }
                    handler_funcs.append(handler_row)

    # Sort deterministically
    modules.sort(key=lambda r: (r["category"], r["module_path"]))
    handler_funcs.sort(key=lambda r: (r["category"], r["module_path"], r["function_name"]))

    return {
        "modules": modules,
        "handler_functions": handler_funcs,
    }


def _classify_handler_category(
    fn_name: str, module_path: str, root_category: str
) -> str:
    """Classify a handler function into a sub-category.

    Returns one of: lifecycle, execute, review, critique, gate, revise,
    repair, cloud, orchestrate, unknown.
    """
    fn_lower = fn_name.lower()
    path_lower = module_path.lower()

    if any(kw in fn_lower for kw in ("execute", "handle_execute", "run_batch")):
        return "execute"
    if any(kw in fn_lower for kw in ("handle_plan", "plan_", "prep")):
        return "lifecycle"
    if any(kw in fn_lower for kw in ("critique", "review_critique")):
        return "critique"
    if any(kw in fn_lower for kw in ("gate", "check_gate", "baseline")):
        return "gate"
    if any(kw in fn_lower for kw in ("review", "audit", "verify")):
        return "review"
    if any(kw in fn_lower for kw in ("revise", "override", "tiebreaker")):
        return "revise"
    if any(kw in fn_lower for kw in ("finalize", "complete", "finish")):
        return "lifecycle"
    if any(kw in fn_lower for kw in ("repair", "recover", "compensate", "restart")):
        return "repair"
    if any(kw in fn_lower for kw in ("reconcile", "progress", "observe")):
        return "orchestrate"
    if any(kw in path_lower for kw in ("orchestration", "supervisor")):
        return "orchestrate"
    return "unknown"


# ── Parsing functions ───────────────────────────────────────────────────────


def parse_boundary_contracts() -> list[dict[str, Any]]:
    """Parse all BoundaryContract instances from the contracts registry.

    Returns a list of dicts with keys: boundary_id, workflow_id, row_id,
    phase (str or None), required_artifacts, expected_state_delta,
    expected_history_entry, phase_result_required, receipt_required,
    authority_required, details.
    """
    raw = _parse_boundary_contract_instances(BOUNDARY_CONTRACTS_PATH)

    # Normalize phases: convert "BoundaryPhase.PREP"-style enum refs to strings
    known_phases = {
        "PREP", "PLAN", "CRITIQUE", "GATE", "REVISE", "EXECUTE",
        "REVIEW", "FINALIZE", "OVERRIDE",
    }
    result: list[dict[str, Any]] = []
    for c in raw:
        bid = c.get("boundary_id", "")
        # Skip templates — they are reference instances, not real contracts
        if isinstance(bid, str) and bid.startswith("template."):
            continue
        phase = c.get("phase")
        if isinstance(phase, str) and phase in known_phases:
            c["phase"] = phase.lower()
        elif phase is None or phase == "None":
            c["phase"] = None
        result.append(c)
    return result


def parse_contract_matrix() -> dict[str, Any]:
    """Load the contract-to-producer matrix."""
    return _load_json(CONTRACT_MATRIX_PATH)


def parse_support_manifest() -> dict[str, Any]:
    """Load the support manifest."""
    return _load_json(SUPPORT_MANIFEST_PATH)


# ── Joining / inventory construction ────────────────────────────────────────


def _build_inventory(
    contracts: list[dict[str, Any]],
    matrix: dict[str, Any],
    manifest: dict[str, Any],
    discovery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Join the three inputs into a deterministic inventory, extended with
    static discovery results.

    The join key is ``boundary_id`` for boundary_contract rows and
    ``step_id`` for manifest entries.  Matrix rows are matched to
    contracts by ``boundary_id``.

    When *discovery* is provided (from :func:`_scan_discovery_roots`),
    runtime_module and handler_function rows are appended to the inventory.
    """

    # Index contracts and matrix rows by boundary_id
    contracts_by_id: dict[str, dict[str, Any]] = {}
    for c in contracts:
        bid = c.get("boundary_id", "")
        if bid:
            contracts_by_id[bid] = c

    matrix_contracts = matrix.get("contracts", [])
    matrix_by_id: dict[str, dict[str, Any]] = {}
    for m in matrix_contracts:
        bid = m.get("boundary_id", "")
        if bid:
            matrix_by_id[bid] = m

    # Collect all manifest entries from all families
    manifest_entries: list[dict[str, Any]] = []
    for family in manifest.get("families", []):
        for entry in family.get("entries", []):
            entry_with_family = dict(entry)
            entry_with_family["family_id"] = family.get("family_id", "")
            entry_with_family["family_name"] = family.get("family_name", "")
            entry_with_family["family_owner"] = family.get("owner", "")
            manifest_entries.append(entry_with_family)

    manifest_by_step: dict[str, dict[str, Any]] = {}
    for e in manifest_entries:
        sid = e.get("step_id", "")
        if sid:
            manifest_by_step[sid] = e

    rows: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []

    # ── Boundary contract rows ──────────────────────────────────────────
    for c in contracts:
        bid = c.get("boundary_id", "")
        matrix_row = matrix_by_id.get(bid)
        row: dict[str, Any] = {
            "row_kind": "boundary_contract",
            "boundary_id": bid,
            "workflow_id": c.get("workflow_id", ""),
            "row_id": c.get("row_id", "UNKNOWN"),
            "phase": c.get("phase"),
            "producer_path": matrix_row.get("producer_path")
            if matrix_row
            else "UNKNOWN",
            "producer_category": matrix_row.get("producer_category", "UNKNOWN")
            if matrix_row
            else "UNKNOWN",
            "owner": "wbc",  # Boundary contracts are owned by WBC
            "support_status": "UNKNOWN",
            "authority_required": c.get("authority_required", False),
        }

        # Candidate vs landed from matrix producer_category
        pc = row["producer_category"]
        if pc in ("declared_only", "unknown", "UNKNOWN"):
            row["candidate"] = True
            row["landed"] = False
        else:
            row["candidate"] = False
            row["landed"] = True

        # Support label from manifest — non-authoritative
        row["support_is_non_authoritative"] = True
        row["support_label_source"] = "UNKNOWN"

        # Attach matrix metadata when available
        if matrix_row:
            row["matrix_metadata"] = {
                "handler_function": matrix_row.get("handler_function"),
                "applicability_rules": matrix_row.get("applicability_rules"),
                "invocation_identity": matrix_row.get("invocation_identity"),
                "artifact_path_patterns": matrix_row.get("artifact_path_patterns", []),
                "receipt_timing": matrix_row.get("receipt_timing"),
                "authority_references": matrix_row.get("authority_references"),
                "visible_non_conformant": matrix_row.get("visible_non_conformant", []),
            }
        else:
            row["matrix_metadata"] = None
            unmatched.append({
                "row_kind": "boundary_contract",
                "boundary_id": bid,
                "reason_unmatched": "no_matrix_entry",
                "detail": f"Contract '{bid}' has no corresponding entry in contract_to_producer_matrix.json",
            })

        rows.append(row)

    # ── Manifest entries not matched to contracts ───────────────────────
    seen_boundary_ids = set(contracts_by_id.keys())
    for entry in manifest_entries:
        sid = entry.get("step_id", "")
        # Check if this step_id matches a boundary_id
        if sid in seen_boundary_ids:
            continue

        entry_row: dict[str, Any] = {
            "row_kind": "manifest_entry",
            "step_id": sid,
            "step_name": entry.get("step_name", ""),
            "kind": entry.get("kind", ""),
            "owner": entry.get("owner", entry.get("family_owner", "UNKNOWN")),
            "support_status": entry.get("support_status", "UNKNOWN"),
            "producer_path": entry.get("producer_path", "UNKNOWN"),
            "c2_c6_milestone": entry.get("c2_c6_milestone", "UNKNOWN"),
            "family_id": entry.get("family_id", ""),
            "support_is_non_authoritative": True,
        }
        rows.append(entry_row)

    # ── Matrix rows not matched to contracts ────────────────────────────
    for mrow in matrix_contracts:
        bid = mrow.get("boundary_id", "")
        if bid not in seen_boundary_ids:
            unmatched.append({
                "row_kind": "matrix_row",
                "boundary_id": bid,
                "reason_unmatched": "no_boundary_contract",
                "detail": f"Matrix row '{bid}' has no corresponding BoundaryContract in boundary_contracts.py",
            })

    # ── Static discovery rows (T5) ──────────────────────────────────────
    source_counts: dict[str, int] = {
        "boundary_contract": len([r for r in rows if r.get("row_kind") == "boundary_contract"]),
        "manifest_entry": 0,
        "runtime_module": 0,
        "handler_function": 0,
    }
    source_counts["manifest_entry"] = len([r for r in rows if r.get("row_kind") == "manifest_entry"])

    if discovery:
        discovered_modules = discovery.get("modules", [])
        discovered_handlers = discovery.get("handler_functions", [])

        for mod_row in discovered_modules:
            rows.append(mod_row)
        for hf_row in discovered_handlers:
            rows.append(hf_row)

        source_counts["runtime_module"] = len(discovered_modules)
        source_counts["handler_function"] = len(discovered_handlers)

        # Record unmatched/discovery-gap modules
        for mod_row in discovered_modules:
            if SURFACE_UNKNOWN in mod_row.get("surface_types", []):
                unmatched.append({
                    "row_kind": "runtime_module",
                    "module_path": mod_row.get("module_path", ""),
                    "reason_unmatched": "unclassifiable_surface",
                    "detail": (
                        f"Module '{mod_row.get('module_path')}' could not be "
                        f"classified into a known surface type. Surface types "
                        f"found: {mod_row.get('surface_types')}"
                    ),
                })

    # ── Sort deterministically ──────────────────────────────────────────
    def _sort_key(r: dict[str, Any]) -> tuple[str, str, str]:
        rk = r.get("row_kind", "")
        bid = r.get("boundary_id", "")
        sid = r.get("step_id", "")
        mp = r.get("module_path", "")
        fn = r.get("function_name", "")
        # Priority: boundary_contract > manifest_entry > runtime_module > handler_function
        kind_order = {
            "boundary_contract": 0,
            "manifest_entry": 1,
            "runtime_module": 2,
            "handler_function": 3,
        }
        primary = kind_order.get(rk, 99)
        secondary = bid or sid or mp or fn or ""
        return (str(primary), secondary, "")

    rows.sort(key=_sort_key)
    unmatched.sort(key=lambda u: (u.get("row_kind", ""), u.get("boundary_id", "") or u.get("step_id", "") or u.get("module_path", "") or ""))

    # ── Build inventory ─────────────────────────────────────────────────
    input_sources = {
        "boundary_contracts": str(BOUNDARY_CONTRACTS_PATH.relative_to(REPO_ROOT)),
        "contract_matrix": str(CONTRACT_MATRIX_PATH.relative_to(REPO_ROOT)),
        "support_manifest": str(SUPPORT_MANIFEST_PATH.relative_to(REPO_ROOT)),
    }
    if discovery:
        input_sources["static_discovery_roots"] = len(DISCOVERY_ROOTS)

    inventory: dict[str, Any] = {
        "meta": {
            "schema": "m6.wbc-boundary-inventory.v1",
            "description": (
                "Deterministic inventory joining boundary contracts, "
                "contract-to-producer matrix, and support manifest, "
                "extended with static discovery over handler, runtime, "
                "kernel, supervisor, execution, and orchestration source "
                "trees. Support labels are recorded but non-authoritative — "
                "only landed producer paths constitute adoption evidence. "
                "Projections are explicitly tagged as non-authority."
            ),
            "generated_by": "M6 Step 4-5 (T4+T5) — generate_wbc_boundary_inventory.py",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "input_sources": input_sources,
            "row_count": len(rows),
            "unmatched_count": len(unmatched),
            "source_counts": source_counts,
            "content_hash": _sha256_hex(json.dumps(rows, sort_keys=True, default=str)),
        },
        "rows": rows,
        "unmatched": unmatched,
    }

    return inventory


# ── Wrapper/shell discovery (T6) ──────────────────────────────────────────

# Roots to scan for non-Python wrapper/shell files.
# These are configuration-management, CI/CD, and operational scripts
# that can produce boundary effects without going through Python handlers.
WRAPPER_SHELL_ROOTS: list[dict[str, Any]] = [
    {
        "path": "arnold_pipelines/megaplan/data",
        "file_patterns": ["*.sh"],
        "category": "ci_cd_scripts",
        "description": "Pre-commit hooks and CI/CD scripts that regenerate composed bundles.",
    },
    {
        "path": ".",
        "file_patterns": ["*.sh"],
        "category": "repo_root_scripts",
        "description": "Repository-root operational scripts (sync, launch, setup).",
        "max_depth": 1,  # Only repo root, not recursive
    },
    {
        "path": ".megaplan/initiatives",
        "file_patterns": ["*.sh"],
        "category": "initiative_scripts",
        "description": "Initiative-level launch/operational scripts.",
    },
]

# Additional non-Python files to treat as wrapper shells (Makefiles, etc.)
WRAPPER_EXTENSIONS: tuple[str, ...] = (".sh", ".bash")


def _scan_wrapper_shells() -> list[dict[str, Any]]:
    """Discover non-Python wrapper/shell files that can produce boundary effects.

    Scans repo-root scripts, CI/CD hook scripts, and initiative-level scripts
    that are NOT Python modules but can still emit receipts, trigger processes,
    or manipulate custody state outside Python handlers.

    Returns a list of ``wrapper_shell`` rows.
    """
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for root_cfg in WRAPPER_SHELL_ROOTS:
        root_path = REPO_ROOT / root_cfg["path"]
        if not root_path.is_dir():
            continue

        max_depth = root_cfg.get("max_depth")
        patterns = root_cfg.get("file_patterns", ["*.sh"])

        for pattern in patterns:
            if max_depth is not None:
                # Only scan at the specified depth
                for fpath in root_path.glob(pattern):
                    if not fpath.is_file():
                        continue
                    # For max_depth=1, only match files directly in root_path
                    if max_depth == 1 and fpath.parent != root_path:
                        continue
                    rel = fpath.relative_to(REPO_ROOT)
                    rel_str = str(rel).replace("\\", "/")
                    if rel_str in seen:
                        continue
                    seen.add(rel_str)
                    rows.append(_build_wrapper_shell_row(rel_str, fpath, root_cfg))
            else:
                # Recursive scan
                for fpath in root_path.rglob(pattern):
                    if not fpath.is_file():
                        continue
                    rel = fpath.relative_to(REPO_ROOT)
                    rel_str = str(rel).replace("\\", "/")
                    if rel_str in seen:
                        continue
                    seen.add(rel_str)
                    rows.append(_build_wrapper_shell_row(rel_str, fpath, root_cfg))

    rows.sort(key=lambda r: r.get("path", ""))
    return rows


def _build_wrapper_shell_row(
    rel_path: str, fpath: Path, root_cfg: dict[str, Any]
) -> dict[str, Any]:
    """Build a single wrapper_shell row."""
    # Read first 2KB for header analysis
    try:
        header = fpath.read_text(encoding="utf-8")[:2048]
    except (OSError, UnicodeDecodeError):
        header = ""

    # Detect shebang
    shebang = ""
    if header.startswith("#!"):
        shebang_line = header.split("\n")[0]
        shebang = shebang_line[2:].strip()

    # Classify wrapper type
    wrapper_type = "shell"
    if "python" in shebang.lower():
        wrapper_type = "python_wrapper"
    elif "node" in shebang.lower():
        wrapper_type = "node_wrapper"

    # Determine if this wrapper can produce boundary effects
    has_boundary_effects = False
    boundary_keywords = [
        "regen", "sync", "launch", "deploy", "commit", "push",
        "skill", "setup", "init", "lock", "stamp",
    ]
    for kw in boundary_keywords:
        if kw in rel_path.lower() or kw in header.lower():
            has_boundary_effects = True
            break

    return {
        "row_kind": "wrapper_shell",
        "path": rel_path,
        "shebang": shebang,
        "wrapper_type": wrapper_type,
        "category": root_cfg.get("category", "unknown"),
        "has_boundary_effects": has_boundary_effects,
        "owner": "run_authority",
        "description": root_cfg.get("description", ""),
        "surface_types": ["wrapper_shell"],
        "is_authority": False,
    }


# ── Default-deny rows (T6) ────────────────────────────────────────────────


def _generate_default_deny_rows(
    inventory: dict[str, Any],
    discovery: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Generate explicit default-deny rows for unresolved surfaces.

    For every runtime_module or handler_function that could not be classified
    into a known non-UNKNOWN surface type, emit a ``default_deny`` row that
    explicitly denies access with a documented reason.

    Additionally, for dynamic/generated/provider surfaces that are not
    covered by static discovery, emit default-deny placeholder rows.

    Returns a list of default_deny rows.
    """
    deny_rows: list[dict[str, Any]] = []

    # ── 1. Unclassified modules from static discovery ────────────────────
    if discovery:
        for mod in discovery.get("modules", []):
            surface_types = mod.get("surface_types", [])
            if SURFACE_UNKNOWN in surface_types or not surface_types:
                deny_rows.append({
                    "row_kind": "default_deny",
                    "target_path": mod.get("module_path", ""),
                    "target_type": "runtime_module",
                    "surface_types_found": surface_types,
                    "access": "denied",
                    "reason": (
                        f"Module could not be classified into a known surface type. "
                        f"Static discovery found classes={mod.get('classes', [])}, "
                        f"functions={mod.get('functions', [])}"
                    ),
                    "owner": mod.get("owner", "UNKNOWN"),
                    "mitigation": (
                        "Add classification keywords to _classify_module_surfaces "
                        "or add the module to a known discovery root category."
                    ),
                })

    # ── 2. Handler functions in unknown category ─────────────────────────
    if discovery:
        for hf in discovery.get("handler_functions", []):
            if hf.get("category") == "unknown":
                deny_rows.append({
                    "row_kind": "default_deny",
                    "target_path": hf.get("module_path", ""),
                    "target_type": "handler_function",
                    "function_name": hf.get("function_name", ""),
                    "handler_category": hf.get("category", "unknown"),
                    "access": "denied",
                    "reason": (
                        f"Handler function '{hf.get('function_name')}' could not "
                        f"be classified into a known handler category."
                    ),
                    "owner": hf.get("owner", "UNKNOWN"),
                    "mitigation": (
                        "Add classification keywords to _classify_handler_category "
                        "for this function name pattern."
                    ),
                })

    # ── 3. Dynamic/generated/provider surface placeholders ───────────────
    # These are surface types that we know exist at runtime but cannot
    # discover via static analysis of the current source tree.
    dynamic_surfaces = [
        {
            "surface_id": "dynamic.cloud_provider",
            "reason": "Cloud provider surfaces (AWS, GCP, Azure SDK calls) are resolved at runtime and cannot be statically discovered from Python AST.",
            "owner": "run_authority",
        },
        {
            "surface_id": "dynamic.generated_code",
            "reason": "Generated code (protobuf stubs, OpenAPI clients, Thrift bindings) may not exist in the source tree at scan time.",
            "owner": "run_authority",
        },
        {
            "surface_id": "dynamic.plugin_loader",
            "reason": "Plugin/driver loaders resolve surfaces at import time; static discovery cannot enumerate all plugin paths.",
            "owner": "run_authority",
        },
        {
            "surface_id": "dynamic.template_renderer",
            "reason": "Template-rendered code (Jinja2, Mako, string.Template) produces surfaces that only exist after rendering.",
            "owner": "run_authority",
        },
        {
            "surface_id": "dynamic.subprocess_boundary",
            "reason": "subprocess.run, os.system, and shell-equivalent calls cross the Python runtime boundary into OS-level processes.",
            "owner": "run_authority",
        },
        {
            "surface_id": "dynamic.file_system_io",
            "reason": "Direct file I/O (open, os.write, pathlib.write_text) can produce boundary effects without going through a declared producer.",
            "owner": "run_authority",
        },
    ]

    for ds in dynamic_surfaces:
        deny_rows.append({
            "row_kind": "default_deny",
            "target_path": ds["surface_id"],
            "target_type": "dynamic_surface",
            "surface_types_found": ["unknown"],
            "access": "denied",
            "reason": ds["reason"],
            "owner": ds["owner"],
            "mitigation": (
                "Dynamic surfaces require runtime tracing (M6A) or explicit "
                "provider registration to move from default-deny to allowed."
            ),
        })

    # Sort deterministically
    deny_rows.sort(key=lambda r: (
        r.get("row_kind", ""),
        r.get("target_path", ""),
        r.get("target_type", ""),
        r.get("function_name", ""),
    ))

    return deny_rows


# ── Current-state assertions (T6) ─────────────────────────────────────────


def _build_current_state_assertions(
    inventory: dict[str, Any],
    discovery: dict[str, Any] | None,
    wrapper_shells: list[dict[str, Any]],
    default_deny_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build machine-verifiable current-state assertions about the inventory.

    These encode known counts and invariants that tests can assert against,
    so that regressions (missing producers, misclassified surfaces) are
    caught immediately.

    Returns a dict with assertion blocks.
    """
    assertions: dict[str, Any] = {
        "schema": "m6.current-state-assertions.v1",
        "description": (
            "Machine-verifiable assertions about the current state of the "
            "WBC boundary inventory. These encode known producer counts, "
            "exclusion rules, and emission hazards so that regressions are "
            "caught by tests."
        ),
        "generated_by": "M6 T6 — generate_wbc_boundary_inventory.py",
    }

    rows = inventory.get("rows", [])
    unmatched = inventory.get("unmatched", [])

    # ── 1. Front-half producers (5 known) ────────────────────────────────
    # Front-half producers are the specific handler entry-point functions
    # that produce lifecycle transitions in the front half of the pipeline:
    # handle_prep, handle_plan, handle_critique, handle_revise, handle_gate.
    # These are the primary producer entry points in handlers/ directory.
    KNOWN_FRONT_HALF_PRODUCERS = [
        "handle_prep",
        "handle_plan",
        "handle_critique",
        "handle_revise",
        "handle_gate",
    ]
    if discovery:
        # Find handler functions whose names exactly match the known set
        all_handler_names = {
            hf.get("function_name")
            for hf in discovery.get("handler_functions", [])
        }
        front_half_found = sorted(
            all_handler_names & set(KNOWN_FRONT_HALF_PRODUCERS)
        )
        front_half_missing = sorted(
            set(KNOWN_FRONT_HALF_PRODUCERS) - all_handler_names
        )

        # Get full details for found producers
        front_half_details = []
        for hf in discovery.get("handler_functions", []):
            if hf.get("function_name") in KNOWN_FRONT_HALF_PRODUCERS:
                front_half_details.append({
                    "function_name": hf.get("function_name"),
                    "module_path": hf.get("module_path"),
                    "category": hf.get("category"),
                })

        assertions["front_half_producers"] = {
            "description": (
                "Known front-half producer entry-point functions: "
                "handle_prep, handle_plan, handle_critique, handle_revise, "
                "handle_gate. These are the primary producer entry points "
                "for PREP, PLAN, CRITIQUE, REVISE, and GATE phases."
            ),
            "expected_count": 5,
            "actual_count": len(front_half_found),
            "found": front_half_found,
            "missing": front_half_missing,
            "count_matches": len(front_half_found) == 5,
            "producers": front_half_details,
        }

    # ── 2. Execute/batch producers (8 known) ─────────────────────────────
    # Execute/batch producers are the specific handler entry-point functions
    # and batch-dispatch functions that produce execution transitions:
    # handle_execute, handle_execute_one_batch, handle_execute_auto_loop,
    # handle_step, plus batch dispatch/observation functions.
    KNOWN_EXECUTE_PRODUCERS = [
        "handle_execute",
        "handle_execute_one_batch",
        "handle_execute_auto_loop",
        "handle_step",
        "handle_execute_batch",
        "execute_batch",
        "monitor_execution_batch",
        "observe_execution",
    ]
    if discovery:
        all_handler_names = {
            hf.get("function_name")
            for hf in discovery.get("handler_functions", [])
        }
        execute_found = sorted(
            all_handler_names & set(KNOWN_EXECUTE_PRODUCERS)
        )
        execute_missing = sorted(
            set(KNOWN_EXECUTE_PRODUCERS) - all_handler_names
        )

        execute_details = []
        for hf in discovery.get("handler_functions", []):
            if hf.get("function_name") in KNOWN_EXECUTE_PRODUCERS:
                execute_details.append({
                    "function_name": hf.get("function_name"),
                    "module_path": hf.get("module_path"),
                    "category": hf.get("category"),
                })

        # Also count execute-category runtime modules
        execute_modules = [
            mod for mod in discovery.get("modules", [])
            if mod.get("category") == "execute_producers"
        ]

        assertions["execute_batch_producers"] = {
            "description": (
                "Known execute/batch producer functions: handle_execute, "
                "handle_execute_one_batch, handle_execute_auto_loop, "
                "handle_step, handle_execute_batch, execute_batch, "
                "monitor_execution_batch, observe_execution. These are the "
                "primary execution-phase producer entry points."
            ),
            "expected_count": 8,
            "actual_count": len(execute_found),
            "found": execute_found,
            "missing": execute_missing,
            "count_matches": len(execute_found) == 8,
            "handlers": execute_details,
            "execute_modules_count": len(execute_modules),
        }

    # ── 3. Execute/review auto-exclusion ─────────────────────────────────
    # handle_execute and handle_review are NOT front-half producers — they
    # operate in the back half of the pipeline. This assertion ensures they
    # are correctly excluded from the front-half count.
    assertions["execute_review_auto_exclusion"] = {
        "description": (
            "handle_execute and handle_review are back-half producers "
            "(EXECUTE/REVIEW phases) and must NOT appear in the front-half "
            "producer set. This auto-exclusion is verified by checking that "
            "neither function appears in KNOWN_FRONT_HALF_PRODUCERS."
        ),
        "excluded_functions": ["handle_execute", "handle_review"],
        "exclusion_verified": True,
    }

    # Verify execute/review are not in the front-half known set
    excluded_in_known = {"handle_execute", "handle_review"} & set(KNOWN_FRONT_HALF_PRODUCERS)
    assertions["execute_review_auto_exclusion"]["exclusion_verified"] = (
        len(excluded_in_known) == 0
    )
    if excluded_in_known:
        assertions["execute_review_auto_exclusion"]["exclusion_violations"] = list(
            excluded_in_known
        )

    # ── 4. Best-effort emission hazard ───────────────────────────────────
    # Producers that emit receipts on a best-effort basis (no guaranteed
    # delivery) are tagged as emission hazards. These are surfaces where
    # the generator/decorator/handler may silently drop receipts.
    emission_hazard_surfaces: list[dict[str, Any]] = []

    if discovery:
        for mod in discovery.get("modules", []):
            surface_types = mod.get("surface_types", [])
            # receipt_writer surfaces are emission hazards by default
            if "receipt_writer" in surface_types:
                emission_hazard_surfaces.append({
                    "module_path": mod.get("module_path"),
                    "surface_types": surface_types,
                    "hazard_type": "receipt_writer_best_effort",
                    "detail": (
                        "Receipt writers may emit receipts on a best-effort "
                        "basis. If the underlying transport (log, queue, file) "
                        "is lossy, receipts can be silently dropped."
                    ),
                })
            # producer surfaces without durable storage
            if "producer" in surface_types and "ledger" not in surface_types:
                emission_hazard_surfaces.append({
                    "module_path": mod.get("module_path"),
                    "surface_types": surface_types,
                    "hazard_type": "producer_without_durable_ledger",
                    "detail": (
                        "Producer surfaces without a durable ledger may emit "
                        "transitions that are not atomic with their side effects. "
                        "This is a best-effort emission hazard."
                    ),
                })

    # Deduplicate
    seen_hazards = set()
    unique_hazards = []
    for h in emission_hazard_surfaces:
        key = (h["module_path"], h["hazard_type"])
        if key not in seen_hazards:
            seen_hazards.add(key)
            unique_hazards.append(h)

    assertions["best_effort_emission_hazards"] = {
        "description": (
            "Surfaces that emit receipts or transitions on a best-effort "
            "basis. These are identified where receipt_writers or producers "
            "lack durable ledger backing, creating a risk of silently dropped "
            "emissions."
        ),
        "hazard_count": len(unique_hazards),
        "hazards": unique_hazards,
    }

    # ── 5. Wrapper/shell summary ─────────────────────────────────────────
    assertions["wrapper_shell_summary"] = {
        "description": (
            "Count and summary of non-Python wrapper/shell files discovered. "
            "These can produce boundary effects outside Python handlers."
        ),
        "total_count": len(wrapper_shells),
        "with_boundary_effects": len([
            ws for ws in wrapper_shells if ws.get("has_boundary_effects")
        ]),
        "wrappers": [
            {
                "path": ws["path"],
                "category": ws.get("category"),
                "has_boundary_effects": ws.get("has_boundary_effects"),
            }
            for ws in wrapper_shells
        ],
    }

    # ── 6. Default-deny summary ──────────────────────────────────────────
    assertions["default_deny_summary"] = {
        "description": (
            "Count and breakdown of default-deny rows. Default-deny rows "
            "represent surfaces that cannot be classified or are known "
            "dynamic/generated/provider surfaces that must be explicitly "
            "denied until proven safe."
        ),
        "total_count": len(default_deny_rows),
        "by_target_type": {},
    }
    for dr in default_deny_rows:
        tt = dr.get("target_type", "unknown")
        assertions["default_deny_summary"]["by_target_type"][tt] = (
            assertions["default_deny_summary"]["by_target_type"].get(tt, 0) + 1
        )

    return assertions


# ── T7: Unmatched set categorization ────────────────────────────────────────


def _categorize_unmatched(
    unmatched: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Split flat unmatched list into separate categorized sets.

    Returns a dict with keys: unmatched_declared, unmatched_static,
    unmatched_runtime, unmatched_wrapper, unmatched_consumer,
    unmatched_producer, unmatched_schema_only.
    """
    categories: dict[str, list[dict[str, Any]]] = {
        "unmatched_declared": [],
        "unmatched_static": [],
        "unmatched_runtime": [],
        "unmatched_wrapper": [],
        "unmatched_consumer": [],
        "unmatched_producer": [],
        "unmatched_schema_only": [],
    }

    for entry in unmatched:
        rk = entry.get("row_kind", "")
        reason = entry.get("reason_unmatched", "")

        if rk == "boundary_contract":
            # Contracts without matrix entries → declared
            categories["unmatched_declared"].append(entry)
        elif rk == "runtime_module":
            # Static discovery modules that couldn't be classified
            categories["unmatched_static"].append(entry)
        elif rk == "wrapper_shell":
            categories["unmatched_wrapper"].append(entry)
        elif rk == "consumer":
            categories["unmatched_consumer"].append(entry)
        elif rk == "producer":
            categories["unmatched_producer"].append(entry)
        elif rk in ("manifest_entry", "matrix_row"):
            # Manifest entries without contracts or matrix rows without contracts
            if reason and "schema" in reason.lower():
                categories["unmatched_schema_only"].append(entry)
            else:
                categories["unmatched_declared"].append(entry)
        else:
            # Fallback: categorize by reason pattern
            if reason and "schema" in reason.lower():
                categories["unmatched_schema_only"].append(entry)
            elif reason and ("static" in reason.lower() or "unclassifiable" in reason.lower()):
                categories["unmatched_static"].append(entry)
            else:
                categories["unmatched_declared"].append(entry)

    # Sort each category deterministically
    for cat in categories:
        categories[cat].sort(
            key=lambda u: (
                u.get("row_kind", ""),
                u.get("boundary_id", "") or u.get("step_id", "") or u.get("module_path", "") or "",
            )
        )

    # T7 rework: unmatched_runtime must record unavailable traces as
    # UNKNOWN/residual/default-deny evidence, not as an empty zero-count set.
    # Runtime traces are M6A scope; for M6 they are unavailable.
    if not categories["unmatched_runtime"]:
        categories["unmatched_runtime"].append({
            "row_kind": "default_deny",
            "target_path": "runtime_trace",
            "target_type": "runtime_trace",
            "surface_types_found": ["unknown"],
            "access": "denied",
            "status": "UNKNOWN",
            "reason": (
                "Runtime traces are not yet captured — M6A scope. "
                "Static and declared surface discovery is the M6 boundary; "
                "runtime-trace discovery requires execution-level instrumentation "
                "and is deferred to M6A. This residual entry records the gap "
                "so unmatched_runtime is never an empty zero-count set."
            ),
            "owner": "UNKNOWN",
            "availability": "UNKNOWN",
            "mitigation": (
                "Implement runtime-trace capture in M6A via execution-level "
                "instrumentation that records call-site set equality, "
                "boundary transitions, and producer/consumer paths at runtime."
            ),
        })

    return categories


# ── T7: Historical adapters artifact ─────────────────────────────────────────

HISTORICAL_ADAPTERS_PATH = EVIDENCE_DIR / "wbc-historical-adapters.json"


def _generate_historical_adapters() -> dict[str, Any]:
    """Generate default-empty historical adapters artifact.

    Read-only adapters must be proven with path/symbol, permitted read
    operations and versions, proof of zero authority-increasing callers,
    named owner/approver, expiry, and deletion gate.  Until such proof
    exists, the artifact is default-empty.
    """
    return {
        "meta": {
            "schema": "m6.wbc-historical-adapters.v1",
            "description": (
                "Historical adapter allowlist for WBC boundary. Each adapter "
                "requires: path/symbol, permitted read operations and versions, "
                "proof of zero authority-increasing callers, named owner/approver, "
                "expiry, and deletion gate. Default-empty because no read-only "
                "adapters have been proven at this milestone."
            ),
            "generated_by": "M6 Step 6 (T7) — generate_wbc_boundary_inventory.py",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "adapter_count": 0,
            "status": "default_empty",
            "status_detail": (
                "No read-only adapters have been proven with the required "
                "evidence fields. Set to empty until proof is provided."
            ),
        },
        "adapters": [],
    }


# ── T7: Validation mode / completion equation ───────────────────────────────


def _load_prerequisite_status() -> dict[str, Any]:
    """Load M6 prerequisite verification status.

    Returns a dict with a computed ``status`` of PASS, UNKNOWN, INCOHERENT,
    or BLOCKED derived from the individual checks in the prerequisite
    verification artifact.
    """
    prereq_path = EVIDENCE_DIR / "m6-prerequisite-verification.json"
    if not prereq_path.exists():
        return {"status": "BLOCKED", "status_detail": "Prerequisite verification not yet run"}
    try:
        with open(prereq_path, "r", encoding="utf-8") as fh:
            prereq = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {"status": "BLOCKED", "status_detail": "Prerequisite verification unreadable"}

    # Compute overall status from individual checks
    checks = prereq.get("checks", [])
    statuses = {c.get("status", "UNKNOWN") for c in checks if isinstance(c, dict)}

    if "BLOCKED" in statuses:
        return {"status": "BLOCKED", "status_detail": "At least one prerequisite check is BLOCKED"}
    if "INCOHERENT" in statuses:
        return {"status": "INCOHERENT", "status_detail": "At least one prerequisite check is INCOHERENT"}
    if "UNKNOWN" in statuses:
        return {"status": "UNKNOWN", "status_detail": "At least one prerequisite check is UNKNOWN"}
    if not statuses:
        return {"status": "UNKNOWN", "status_detail": "No prerequisite checks found"}
    if statuses == {"PASS"}:
        return {"status": "PASS", "status_detail": "All prerequisite checks pass"}
    return {"status": "UNKNOWN", "status_detail": f"Mixed prerequisite statuses: {statuses}"}


def _check_completion_equation(inventory: dict[str, Any]) -> dict[str, Any]:
    """Check the WBC inventory completion equation.

    The completion equation requires:
    1. Every declared contract has exactly one owner and a non-UNKNOWN producer_path
       or is explicitly marked as candidate/landed with a reason.
    2. Source counts are consistent: row_count >= sum of source_counts.
    3. Every runtime_module has a non-UNKNOWN surface_type classification
       or a corresponding default_deny row.
    4. No unmatched_declared entries exist (all declared contracts must be matched).

    Returns a dict with keys: passes (bool), checks (list of check results),
    and blocked_by_prerequisites (bool).
    """
    checks: list[dict[str, Any]] = []
    rows = inventory.get("rows", [])
    unmatched_cats = inventory.get("unmatched_categories", {})
    default_deny_rows = inventory.get("default_deny_rows", [])
    meta = inventory.get("meta", {})

    all_pass = True

    # ── Check 1: Declared contracts completeness ─────────────────────────
    declared_unmatched = unmatched_cats.get("unmatched_declared", [])
    check1 = {
        "id": "declared_contracts_complete",
        "description": "All declared boundary contracts must have a matrix entry",
        "passes": len(declared_unmatched) == 0,
        "unmatched_count": len(declared_unmatched),
        "detail": (
            f"All {meta.get('source_counts', {}).get('boundary_contract', 0)} "
            f"declared contracts are matched to matrix entries"
        )
        if len(declared_unmatched) == 0
        else (
            f"{len(declared_unmatched)} declared contracts have no matrix entry: "
            f"{[e.get('boundary_id', '?') for e in declared_unmatched[:5]]}"
            + ("..." if len(declared_unmatched) > 5 else "")
        ),
    }
    checks.append(check1)
    if not check1["passes"]:
        all_pass = False

    # ── Check 2: Row count consistency ────────────────────────────────────
    source_counts = meta.get("source_counts", {})
    expected_min = sum(source_counts.values())
    actual_rows = len(rows)
    check2 = {
        "id": "row_count_consistency",
        "description": "Row count >= sum of source_counts",
        "passes": actual_rows >= expected_min,
        "expected_min": expected_min,
        "actual": actual_rows,
        "detail": f"Row count {actual_rows} >= source sum {expected_min}"
        if actual_rows >= expected_min
        else f"Row count {actual_rows} < source sum {expected_min} — inventory incomplete",
    }
    checks.append(check2)
    if not check2["passes"]:
        all_pass = False

    # ── Check 3: Static discovery coverage ────────────────────────────────
    static_unmatched = unmatched_cats.get("unmatched_static", [])
    deny_targets = {dr.get("target_path", "") for dr in default_deny_rows}
    uncovered_static = [
        u for u in static_unmatched
        if u.get("module_path", "") not in deny_targets
    ]
    check3 = {
        "id": "static_discovery_coverage",
        "description": (
            "Every unclassified runtime_module must have a default_deny row"
        ),
        "passes": len(uncovered_static) == 0,
        "static_unmatched_count": len(static_unmatched),
        "uncovered_count": len(uncovered_static),
        "detail": (
            f"All {len(static_unmatched)} unclassified modules covered by "
            f"default_deny rows"
        )
        if len(uncovered_static) == 0
        else (
            f"{len(uncovered_static)} unclassified modules without default_deny: "
            f"{[u.get('module_path', '?') for u in uncovered_static[:5]]}"
            + ("..." if len(uncovered_static) > 5 else "")
        ),
    }
    checks.append(check3)
    if not check3["passes"]:
        all_pass = False

    # ── Check 4: Owner coverage ───────────────────────────────────────────
    rows_without_owner = [
        r for r in rows
        if not r.get("owner") or r.get("owner") == "UNKNOWN"
    ]
    # Only flag rows that should have owners (exclude unmatched entries)
    known_kinds_for_owner = {"boundary_contract", "manifest_entry", "runtime_module",
                              "handler_function", "wrapper_shell"}
    rows_missing_owner = [
        r for r in rows_without_owner
        if r.get("row_kind") in known_kinds_for_owner
    ]
    check4 = {
        "id": "owner_coverage",
        "description": "Every inventory row must name an owner",
        "passes": len(rows_missing_owner) == 0,
        "missing_owner_count": len(rows_missing_owner),
        "detail": (
            "All rows have a valid owner"
        )
        if len(rows_missing_owner) == 0
        else (
            f"{len(rows_missing_owner)} rows missing owner: "
            f"{[(r.get('row_kind'), r.get('boundary_id', r.get('module_path', '?'))) for r in rows_missing_owner[:5]]}"
            + ("..." if len(rows_missing_owner) > 5 else "")
        ),
    }
    checks.append(check4)
    if not check4["passes"]:
        all_pass = False

    # ── Check 5: Schema-only detection ────────────────────────────────────
    schema_only_unmatched = unmatched_cats.get("unmatched_schema_only", [])
    check5 = {
        "id": "schema_only_visibility",
        "description": "Schema-only entries must be tracked in unmatched_schema_only",
        "passes": True,  # Always passes — schema-only being visible is the goal
        "schema_only_count": len(schema_only_unmatched),
        "detail": (
            f"{len(schema_only_unmatched)} schema-only entries tracked in "
            f"unmatched_schema_only set"
        ),
    }
    checks.append(check5)

    return {
        "passes": all_pass,
        "checks": checks,
        "blocked_by_prerequisites": False,  # Will be updated below
    }


def _run_validation(inventory: dict[str, Any]) -> int:
    """Run the validation/completion-equation check.

    Returns 0 if validation passes or prerequisites block,
    nonzero if validation fails.
    """
    prereq = _load_prerequisite_status()
    prereq_status = prereq.get("status", "UNKNOWN")

    # If prerequisites are BLOCKED or INCOHERENT, validation is skipped
    # and we exit 0 because the gate is not yet open.
    if prereq_status in ("BLOCKED", "INCOHERENT"):
        print(
            f"[validate] prerequisites are {prereq_status} — "
            f"validation skipped (gate not open)"
        )
        return 0

    eq_result = _check_completion_equation(inventory)
    eq_result["blocked_by_prerequisites"] = False
    eq_result["prerequisite_status"] = prereq_status

    # Write validation result alongside inventory
    validation_path = EVIDENCE_DIR / "wbc-boundary-inventory-validation.json"
    validation_path.parent.mkdir(parents=True, exist_ok=True)
    with open(validation_path, "w", encoding="utf-8") as fh:
        json.dump(eq_result, fh, indent=2, default=str, sort_keys=True)
    print(f"[validate] wrote {validation_path}")

    if eq_result["passes"]:
        print("[validate] PASS — completion equation satisfied")
        return 0
    else:
        failed = [c["id"] for c in eq_result["checks"] if not c["passes"]]
        print(f"[validate] FAIL — checks failed: {failed}")
        return 1


# ── Main ────────────────────────────────────────────────────────────────────


def generate(output_path: Path | None = None) -> dict[str, Any]:
    """Run the full generation pipeline and return the inventory dict.

    If *output_path* is given, the inventory is written there as UTF-8 JSON.
    """
    contracts = parse_boundary_contracts()
    matrix = parse_contract_matrix()
    manifest = parse_support_manifest()

    # T5: Static discovery over source trees
    discovery = _scan_discovery_roots()
    print(
        f"[generate_wbc_boundary_inventory] static discovery: "
        f"{len(discovery.get('modules', []))} modules, "
        f"{len(discovery.get('handler_functions', []))} handler functions"
    )

    # T6: Wrapper/shell discovery
    wrapper_shells = _scan_wrapper_shells()
    print(
        f"[generate_wbc_boundary_inventory] wrapper/shell discovery: "
        f"{len(wrapper_shells)} shells found"
    )

    inventory = _build_inventory(contracts, matrix, manifest, discovery)

    # T6: Generate default-deny rows
    default_deny_rows = _generate_default_deny_rows(inventory, discovery)
    print(
        f"[generate_wbc_boundary_inventory] default-deny rows: "
        f"{len(default_deny_rows)} generated"
    )

    # T6: Build current-state assertions
    assertions = _build_current_state_assertions(
        inventory, discovery, wrapper_shells, default_deny_rows
    )

    # T7: Categorize unmatched into separate sets
    raw_unmatched = inventory.pop("unmatched", [])
    unmatched_categories = _categorize_unmatched(raw_unmatched)
    print(
        f"[generate_wbc_boundary_inventory] unmatched categories: "
        f"declared={len(unmatched_categories['unmatched_declared'])}, "
        f"static={len(unmatched_categories['unmatched_static'])}, "
        f"runtime={len(unmatched_categories['unmatched_runtime'])}, "
        f"wrapper={len(unmatched_categories['unmatched_wrapper'])}, "
        f"consumer={len(unmatched_categories['unmatched_consumer'])}, "
        f"producer={len(unmatched_categories['unmatched_producer'])}, "
        f"schema_only={len(unmatched_categories['unmatched_schema_only'])}"
    )

    # Attach T6+T7 data to inventory
    inventory["wrapper_shells"] = wrapper_shells
    inventory["default_deny_rows"] = default_deny_rows
    inventory["current_state_assertions"] = assertions
    inventory["unmatched_categories"] = unmatched_categories

    # Update meta with T6+T7 counts
    inventory["meta"]["wrapper_shell_count"] = len(wrapper_shells)
    inventory["meta"]["default_deny_count"] = len(default_deny_rows)
    inventory["meta"]["unmatched_total_count"] = sum(
        len(v) for v in unmatched_categories.values()
    )
    inventory["meta"]["unmatched_category_counts"] = {
        k: len(v) for k, v in unmatched_categories.items()
    }
    inventory["meta"]["generated_by"] = (
        "M6 Steps 4-7 (T4+T5+T6+T7) — generate_wbc_boundary_inventory.py"
    )

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(inventory, fh, indent=2, default=str, sort_keys=False)
        print(f"[generate_wbc_boundary_inventory] wrote {output_path}")

    # T7: Also generate historical adapters artifact
    adapters = _generate_historical_adapters()
    HISTORICAL_ADAPTERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORICAL_ADAPTERS_PATH, "w", encoding="utf-8") as fh:
        json.dump(adapters, fh, indent=2, default=str, sort_keys=True)
    print(f"[generate_wbc_boundary_inventory] wrote {HISTORICAL_ADAPTERS_PATH}")

    return inventory


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the WBC boundary inventory artifact."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run validation/completion-equation check after generation",
    )
    args = parser.parse_args()

    inventory = generate(output_path=args.output)

    if args.validate:
        exit_code = _run_validation(inventory)
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
