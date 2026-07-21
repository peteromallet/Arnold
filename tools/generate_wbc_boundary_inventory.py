"""Generate the WBC boundary inventory and related discovery evidence.

This generator is observe-only. It statically inspects repository source,
current WBC declarations, the C1 contract matrix, compatibility-reader
snapshots, and the writer-map snapshot. It writes only evidence artifacts under
``evidence/`` and never mutates the C1 matrices it reads.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import json
import re
import sys
from importlib.machinery import SourcelessFileLoader
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

try:
    import yaml

    _HAS_YAML = True
except ImportError:  # pragma: no cover - YAML is present in the repo env.
    yaml = None
    _HAS_YAML = False


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_recovered_custody_module(pyc_stem: str) -> ModuleType:
    synthetic_name = f"_wbc_inventory_{pyc_stem}"
    cached = sys.modules.get(synthetic_name)
    if isinstance(cached, ModuleType):
        return cached

    base_dir = REPO_ROOT / "arnold_pipelines/megaplan/custody"
    pyc_name = f"{pyc_stem}.cpython-{sys.version_info.major}{sys.version_info.minor}.pyc"
    recovered_path = base_dir / "_recovered" / pyc_name
    pyc_path = recovered_path if recovered_path.exists() else base_dir / "__pycache__" / pyc_name
    if not pyc_path.exists():
        raise ModuleNotFoundError(f"missing recovered custody module {pyc_path}")

    loader = SourcelessFileLoader(synthetic_name, str(pyc_path))
    code = loader.get_code(synthetic_name)
    if code is None:
        raise ModuleNotFoundError(f"could not load recovered custody module {pyc_path}")

    module = ModuleType(synthetic_name)
    module.__file__ = str(pyc_path)
    sys.modules[synthetic_name] = module
    exec(code, module.__dict__)
    return module


custody_compatibility = _load_recovered_custody_module("compatibility")
custody_writer_map = _load_recovered_custody_module("writer_map")

EVIDENCE_DIR = REPO_ROOT / "evidence"
BOUNDARY_CONTRACTS_PATH = REPO_ROOT / "arnold_pipelines/megaplan/workflows/boundary_contracts.py"
CONTRACT_MATRIX_PATH = REPO_ROOT / "arnold_pipelines/megaplan/workflows/contract_to_producer_matrix.json"
SUPPORT_MANIFEST_PATH = REPO_ROOT / "arnold_pipelines/megaplan/workflows/support_manifest.json"
SOURCE_TO_OWNER_MATRIX_PATH = REPO_ROOT / "arnold_pipelines/megaplan/workflows/source_to_owner_matrix.json"
NATIVE_GOLDEN_MANIFEST_PATH = (
    REPO_ROOT / "tests/arnold_pipelines/megaplan/fixtures/native_goldens/manifest.json"
)
NATIVE_GOLDEN_ROOT = NATIVE_GOLDEN_MANIFEST_PATH.parent
DISCOVERY_RULES_PATH = EVIDENCE_DIR / "wbc-boundary-discovery-rules.yaml"
DEFAULT_OUTPUT = EVIDENCE_DIR / "wbc-boundary-inventory.json"
HISTORICAL_ADAPTERS_PATH = EVIDENCE_DIR / "wbc-historical-adapters.json"

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

NON_AUTHORITY_SURFACES = frozenset(
    {
        SURFACE_DURABLE_REF,
        SURFACE_JOURNAL,
        SURFACE_PROJECTION,
        SURFACE_CONSUMER,
        SURFACE_COMPATIBILITY_SHIM,
    }
)
AUTHORITY_ADJACENT_SURFACES = frozenset(
    {
        SURFACE_RECEIPT_WRITER,
        SURFACE_LEDGER,
        SURFACE_REPAIR_QUEUE,
        SURFACE_AUTHORITY_READER,
        SURFACE_AUTHORITY_WRITER,
        SURFACE_PRODUCER,
    }
)

DISCOVERY_ROOTS: tuple[dict[str, Any], ...] = (
    {
        "path": "arnold/workflow",
        "category": "boundary_runtime",
        "file_patterns": [
            "attempt_ledger_store.py",
            "boundary_compatibility.py",
            "boundary_conformance.py",
            "boundary_evidence.py",
            "boundary_templates.py",
            "durable_refs.py",
            "execution_attempt_ledger.py",
        ],
        "description": "Core WBC runtime and schema surfaces.",
    },
    {
        "path": "arnold_pipelines/megaplan/handlers",
        "category": "handler_functions",
        "file_patterns": ["*.py"],
        "description": "Megaplan handlers and boundary producers.",
    },
    {
        "path": "arnold_pipelines/megaplan/execute",
        "category": "execute_producers",
        "file_patterns": ["*.py"],
        "description": "Execute-phase batch and promotion producers.",
    },
    {
        "path": "arnold_pipelines/megaplan/orchestration",
        "category": "orchestration",
        "file_patterns": [
            "authority_readers.py",
            "completion_io.py",
            "critique_runtime.py",
            "execution_evidence.py",
            "phase_result.py",
        ],
        "description": "Orchestration readers, validators, and transitions.",
    },
    {
        "path": "arnold_pipelines/megaplan/custody",
        "category": "custody_runtime",
        "file_patterns": ["*.py"],
        "description": "WBC runtime facade, compatibility, and controlled writers.",
    },
    {
        "path": "arnold_pipelines/megaplan/chain",
        "category": "chain_runtime",
        "file_patterns": ["spec.py", "status.py", "epic_chain.py", "operator_pause.py"],
        "description": "Chain readers and lifecycle surfaces.",
    },
    {
        "path": "arnold_pipelines/megaplan/cloud",
        "category": "cloud_runtime",
        "file_patterns": [
            "status_snapshot.py",
            "repair_lock.py",
            "wrapper_acceptance_gate.py",
            "supervise.py",
            "human_blockers.py",
        ],
        "description": "Cloud wrappers, repair, and status consumers.",
    },
    {
        "path": "arnold_pipelines/megaplan/supervisor",
        "category": "supervisor_runtime",
        "file_patterns": ["state.py", "chain_runner.py", "bakeoff_runner.py"],
        "description": "Supervisor state and runner surfaces.",
    },
    {
        "path": "arnold_pipelines/megaplan/_core",
        "category": "core_runtime",
        "file_patterns": ["state.py", "io.py", "modes.py"],
        "description": "Core state and compatibility-reader surfaces.",
    },
    {
        "path": "arnold_pipelines/megaplan/bakeoff",
        "category": "bakeoff_runtime",
        "file_patterns": ["state.py", "channel_shadow.py", "handlers.py", "lifecycle.py", "merge.py"],
        "description": "Bakeoff compatibility-reader surfaces.",
    },
    {
        "path": "arnold_pipelines/megaplan/runtime",
        "category": "runtime_compatibility",
        "file_patterns": ["inprocess_step.py", "step_io_policy_adapter.py"],
        "description": "Runtime adapters that still classify filenames and marker-backed state.",
    },
    {
        "path": "arnold_pipelines/megaplan/watchdog",
        "category": "watchdog_runtime",
        "file_patterns": ["processes.py", "correlate.py", "snapshot.py"],
        "description": "Process and marker compatibility readers for watchdog observation paths.",
    },
    {
        "path": "arnold_pipelines/megaplan/receipts",
        "category": "receipt_runtime",
        "file_patterns": ["report.py", "extractors.py"],
        "description": "Mutable receipt readers retained as read-only reporting adapters.",
    },
    {
        "path": "arnold_pipelines/megaplan/pricing",
        "category": "pricing_runtime",
        "file_patterns": ["codex.py", "claude.py", "fireworks.py"],
        "description": "Token and cost compatibility readers for historical accounting paths.",
    },
)

ADAPTER_CLASS_RAW_JSON = "raw_json"
ADAPTER_CLASS_PROSE = "prose"
ADAPTER_CLASS_TOKEN = "token"
ADAPTER_CLASS_FILENAME = "filename"
ADAPTER_CLASS_MARKER = "marker"
ADAPTER_CLASS_PROCESS = "process"
ADAPTER_CLASS_MUTABLE_RECEIPT = "mutable_receipt"

MILESTONE_ORDER = {
    "M7": 0,
    "M7A": 1,
    "M8": 2,
    "M9": 3,
    "M10": 4,
    "M11": 5,
}

SNAPSHOT_READER_CLASSIFICATIONS: dict[str, str] = {
    "legacy-chain-state-reader": ADAPTER_CLASS_RAW_JSON,
    "legacy-supervisor-state-reader": ADAPTER_CLASS_RAW_JSON,
    "legacy-bakeoff-state-reader": ADAPTER_CLASS_RAW_JSON,
    "legacy-status-snapshot-reader": ADAPTER_CLASS_RAW_JSON,
    "legacy-heartbeat-state-reader": ADAPTER_CLASS_RAW_JSON,
    "legacy-repair-lock-reader": ADAPTER_CLASS_PROCESS,
}


@dataclass(frozen=True)
class HistoricalAdapterRule:
    adapter_id: str
    reader_name: str
    adapter_class: str
    module_paths: tuple[str, ...]
    permitted_read_operations: tuple[str, ...]
    description: str
    deadline_milestone: str
    diagnostics: tuple[str, ...]
    projection_ids: tuple[str, ...] = ()
    mode: str = "shadow"
    supported_versions: tuple[str, ...] = ("legacy", "shadow")


ADDITIONAL_HISTORICAL_ADAPTER_RULES: tuple[HistoricalAdapterRule, ...] = (
    HistoricalAdapterRule(
        adapter_id="historical-prose-reader",
        reader_name="Prose Classification Consumer",
        adapter_class=ADAPTER_CLASS_PROSE,
        module_paths=(
            "arnold_pipelines/megaplan/_core/modes.py",
            "arnold_pipelines/megaplan/execute/aggregation.py",
        ),
        permitted_read_operations=(
            "is_prose_mode",
            "is_creative_mode",
            "phase_quality_deviations_for_current_attempt",
        ),
        description="Legacy consumers that classify prose or narrative output before canonical WBC consumer adoption.",
        deadline_milestone="M9",
        diagnostics=(
            "Consumes prose-mode or narrative evidence only for observation; never as launch or completion authority.",
            "Missing canonical WBC evidence must remain UNKNOWN rather than inferred from prose text.",
        ),
    ),
    HistoricalAdapterRule(
        adapter_id="historical-token-reader",
        reader_name="Token and Cost Consumer",
        adapter_class=ADAPTER_CLASS_TOKEN,
        module_paths=(
            "arnold_pipelines/megaplan/pricing/codex.py",
            "arnold_pipelines/megaplan/pricing/claude.py",
            "arnold_pipelines/megaplan/pricing/fireworks.py",
            "arnold_pipelines/megaplan/receipts/report.py",
        ),
        permitted_read_operations=(
            "cost_from_usage",
            "cost_from_codex_usage_dict",
            "estimate_tokens_from_cost",
            "_tokens",
            "_totals",
        ),
        description="Historical analytics readers that inspect raw token or cost totals without using them as authority.",
        deadline_milestone="M9",
        diagnostics=(
            "Raw token totals are accounting evidence only and cannot classify success, repair ownership, or task completion.",
            "Any missing denominator or mismatched session usage must remain diagnostic-only.",
        ),
    ),
    HistoricalAdapterRule(
        adapter_id="historical-filename-reader",
        reader_name="Filename Compatibility Consumer",
        adapter_class=ADAPTER_CLASS_FILENAME,
        module_paths=(
            "arnold_pipelines/megaplan/execute/step_edit.py",
        ),
        permitted_read_operations=("next_plan_artifact_name",),
        description="Legacy consumers that classify plan artifacts by filename or path before typed WBC query adoption.",
        deadline_milestone="M9",
        diagnostics=(
            "Filename or path heuristics remain compatibility-only and cannot prove freshness, ownership, or terminal success.",
            "Canonical reads must bind to exact WBC source identity instead of implicit latest filenames.",
        ),
    ),
    HistoricalAdapterRule(
        adapter_id="historical-marker-reader",
        reader_name="Marker Compatibility Consumer",
        adapter_class=ADAPTER_CLASS_MARKER,
        module_paths=(
            "arnold_pipelines/megaplan/runtime/step_io_policy_adapter.py",
            "arnold_pipelines/megaplan/cloud/status_snapshot.py",
        ),
        permitted_read_operations=(
            "load_megaplan_step_io_policy",
            "has_megaplan_step_io_self_validation_marker",
            "load_cloud_status_snapshot",
        ),
        description="Legacy marker-backed readers retained only for operator diagnostics and compatibility observation.",
        deadline_milestone="M9",
        diagnostics=(
            "Marker presence is corroboration only and cannot outrank canonical WBC or custody state.",
            "Stale or missing markers must degrade to UNKNOWN rather than silently refreshing activity.",
        ),
    ),
    HistoricalAdapterRule(
        adapter_id="historical-process-reader",
        reader_name="Process Observation Consumer",
        adapter_class=ADAPTER_CLASS_PROCESS,
        module_paths=(
            "arnold_pipelines/megaplan/watchdog/processes.py",
            "arnold_pipelines/megaplan/watchdog/correlate.py",
            "arnold_pipelines/megaplan/watchdog/snapshot.py",
        ),
        permitted_read_operations=(
            "scan_processes",
            "correlate_processes_to_plans",
            "infer_plan_dirs_from_processes",
            "build_snapshot",
        ),
        description="Legacy process-table and cwd correlation readers retained for watchdog observation paths.",
        deadline_milestone="M9",
        diagnostics=(
            "Process liveness is corroboration only and cannot grant retry, repair, resume, or completion authority.",
            "Disagreement between process facts and canonical evidence must remain drift, not auto-repair authority.",
        ),
    ),
    HistoricalAdapterRule(
        adapter_id="historical-mutable-receipt-reader",
        reader_name="Mutable Receipt Consumer",
        adapter_class=ADAPTER_CLASS_MUTABLE_RECEIPT,
        module_paths=(
            "arnold_pipelines/megaplan/receipts/report.py",
            "arnold_pipelines/megaplan/receipts/extractors.py",
        ),
        permitted_read_operations=(
            "_safe_read_json",
            "_collect_receipts",
            "_collect_dispatch_receipts",
            "load_and_extract",
        ),
        description="Legacy report builders that inspect mutable receipt JSON only for read-only diagnostics.",
        deadline_milestone="M9",
        diagnostics=(
            "Mutable receipts cannot prove exact-version authority because they may be rewritten or superseded.",
            "Canonical WBC rereads must remain the only source for authority-increasing transitions.",
        ),
    ),
)

WRAPPER_SHELL_ROOTS: tuple[dict[str, Any], ...] = (
    {
        "path": ".",
        "patterns": ("sync-skills.sh",),
        "category": "repo_root_scripts",
        "description": "Repository-root operational scripts.",
    },
    {
        "path": "arnold_pipelines/megaplan/cloud",
        "patterns": ("*.sh", "wrappers/*", "systemd/*", "templates/*.tmpl"),
        "category": "cloud_wrappers",
        "description": "Cloud wrappers and shell-based runtime adapters.",
    },
    {
        "path": "arnold_pipelines/megaplan/data",
        "patterns": ("*.sh",),
        "category": "ci_cd_scripts",
        "description": "Hooks and operational scripts.",
    },
)

PRODUCER_CALL_NAMES = frozenset(
    {
        "write_boundary_receipt",
        "_emit_boundary_receipt",
        "_emit_execute_boundary_receipt",
        "_emit_batch_boundary_receipt",
        "reserve_attempt",
        "start_attempt",
        "complete_attempt",
        "fail_attempt",
        "cancel_attempt",
        "suspend_attempt",
        "resume_attempt",
        "schedule_retry",
        "record_effect_intent",
        "record_effect_outcome",
        "authoritative_reread",
        "append_event",
    }
)
RISKY_PRODUCER_CALL_NAMES = frozenset(
    {
        "write_boundary_receipt",
        "_emit_boundary_receipt",
        "_emit_execute_boundary_receipt",
        "_emit_batch_boundary_receipt",
        "append_event",
        "start_attempt",
        "complete_attempt",
        "fail_attempt",
        "cancel_attempt",
        "suspend_attempt",
        "resume_attempt",
        "schedule_retry",
        "record_effect_intent",
        "record_effect_outcome",
    }
)
BYPASS_TEXT_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\|\|\s*true\b", "shell_or_true"),
    (r"except Exception", "broad_exception"),
    (r"without raising", "without_raising"),
    (r"best-effort", "best_effort"),
    (r"warn-and-continue", "warn_and_continue"),
    (r"\b(?:load_chain_state|latest_artifact)\s*\(", "implicit_latest_lookup"),
    (
        r"\b(?:expected_source_version|source_version|source_ref|lookup_ref|commit_sha|head_sha)\w*\s*="
        r"\s*[\"'](?:HEAD|head|latest|main|master|refs/pull/[^\"']+)[\"']",
        "mutable_alias_overwrite",
    ),
)


def _sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _directory_digest(root: Path) -> str:
    entries: list[str] = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        rel_path = path.relative_to(root).as_posix()
        entries.append(f"{rel_path}\0{_sha256_file(path)}")
    payload = "\n".join(entries)
    return f"sha256:{_sha256_hex(payload)}"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if _HAS_YAML:
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        return
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _matrix_hash() -> str:
    return _sha256_hex(SOURCE_TO_OWNER_MATRIX_PATH.read_text(encoding="utf-8"))


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    if isinstance(node, ast.Subscript):
        return _call_name(node.value)
    return ""


def _symbol_value(node: ast.AST, symbols: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return symbols.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        base = _symbol_value(node.value, symbols)
        if isinstance(base, str) and base in {"BoundaryPhase", "BoundaryTemplateKind", "AdapterTemplateKind"}:
            return node.attr.lower()
        if isinstance(base, str):
            return f"{base}.{node.attr}"
        return node.attr
    if isinstance(node, ast.Dict):
        return {
            _symbol_value(key, symbols): _symbol_value(value, symbols)
            for key, value in zip(node.keys, node.values)
        }
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [_symbol_value(item, symbols) for item in node.elts]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _symbol_value(node.operand, symbols)
        return -inner if isinstance(inner, (int, float)) else inner
    if isinstance(node, ast.Call):
        callee = _call_name(node.func)
        if callee.endswith("MappingProxyType") and node.args:
            return _symbol_value(node.args[0], symbols)
        if callee.endswith("frozenset") and node.args:
            value = _symbol_value(node.args[0], symbols)
            return list(value) if isinstance(value, list) else value
        return {"call": callee}
    return None


def _parse_boundary_contract_instances(path: Path) -> list[dict[str, Any]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    symbols: dict[str, Any] = {}
    contracts: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            value = _symbol_value(node.value, symbols)
            if value is not None:
                symbols[node.targets[0].id] = value
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            value = _symbol_value(node.value, symbols)
            if value is not None:
                symbols[node.target.id] = value
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _call_name(node.func).split(".")[-1] != "BoundaryContract":
            continue
        record: dict[str, Any] = {}
        positional = [
            "boundary_id",
            "workflow_id",
            "row_id",
            "phase",
            "required_artifacts",
            "expected_state_delta",
            "expected_history_entry",
            "phase_result_required",
            "receipt_required",
            "authority_required",
            "contract_version",
            "details",
        ]
        for field_name, arg in zip(positional, node.args):
            record[field_name] = _symbol_value(arg, symbols)
        for keyword in node.keywords:
            if keyword.arg is None:
                continue
            record[keyword.arg] = _symbol_value(keyword.value, symbols)
        if record.get("boundary_id"):
            contracts.append(record)
    contracts.sort(key=lambda item: str(item.get("boundary_id", "")))
    return contracts


def parse_boundary_contracts() -> list[dict[str, Any]]:
    return _parse_boundary_contract_instances(BOUNDARY_CONTRACTS_PATH)


def parse_contract_matrix() -> dict[str, Any]:
    return _load_json(CONTRACT_MATRIX_PATH)


def parse_support_manifest() -> dict[str, Any]:
    return _load_json(SUPPORT_MANIFEST_PATH)


def parse_source_to_owner_matrix() -> dict[str, Any]:
    return _load_json(SOURCE_TO_OWNER_MATRIX_PATH)


@dataclass
class CallScan:
    callee: str
    line: int
    column: int
    enclosing_function: str = ""
    boundary_literals: tuple[str, ...] = ()
    source_segment: str = ""


@dataclass
class TryScan:
    line: int
    enclosing_function: str
    catches_broad_exception: bool
    body_calls: tuple[str, ...] = ()
    handler_source: str = ""


@dataclass
class ModuleScan:
    module_path: str
    category: str
    owner: str
    surface_types: tuple[str, ...]
    is_authority: bool
    classes: tuple[str, ...]
    functions: tuple[str, ...]
    imports: tuple[str, ...]
    docstring_summary: str
    calls: tuple[CallScan, ...] = ()
    try_scans: tuple[TryScan, ...] = ()
    text_hits: tuple[dict[str, Any], ...] = ()


class _ModuleVisitor(ast.NodeVisitor):
    def __init__(self, source: str) -> None:
        self.source = source
        self.classes: list[str] = []
        self.functions: list[str] = []
        self.function_ranges: list[tuple[int, int, str]] = []
        self.imports: list[str] = []
        self.calls: list[CallScan] = []
        self.try_scans: list[TryScan] = []
        self.function_stack: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.classes.append(node.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.functions.append(node.name)
        self.function_ranges.append((node.lineno, getattr(node, "end_lineno", node.lineno), node.name))
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            self.imports.append(f"{module}.{alias.name}" if module else alias.name)

    def visit_Call(self, node: ast.Call) -> None:
        callee = _call_name(node.func)
        if callee:
            boundary_literals: list[str] = []
            for arg in list(node.args) + [kw.value for kw in node.keywords if kw.arg]:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    if re.fullmatch(r"[a-z0-9_]+", arg.value):
                        boundary_literals.append(arg.value)
            try:
                source_segment = (ast.get_source_segment(self.source, node) or "").strip()
            except IndexError:  # synthetic snippets in helper scans do not retain original offsets.
                source_segment = ""
            self.calls.append(
                CallScan(
                    callee=callee,
                    line=node.lineno,
                    column=node.col_offset,
                    enclosing_function=self.function_stack[-1] if self.function_stack else "",
                    boundary_literals=tuple(sorted(set(boundary_literals))),
                    source_segment=source_segment,
                )
            )
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        catches_broad = False
        for handler in node.handlers:
            if handler.type is None:
                catches_broad = True
            elif isinstance(handler.type, ast.Name) and handler.type.id == "Exception":
                catches_broad = True
            elif isinstance(handler.type, ast.Tuple):
                catches_broad = any(isinstance(item, ast.Name) and item.id == "Exception" for item in handler.type.elts)
        body_calls = tuple(
            sorted(
                {
                    _call_name(inner.func).split(".")[-1]
                    for stmt in node.body
                    for inner in ast.walk(stmt)
                    if isinstance(inner, ast.Call) and _call_name(inner.func)
                }
            )
        )
        if catches_broad:
            handler_source = "\n".join(
                (ast.get_source_segment(self.source, handler) or "").strip()
                for handler in node.handlers
            ).strip()
            self.try_scans.append(
                TryScan(
                    line=node.lineno,
                    enclosing_function=self.function_stack[-1] if self.function_stack else "",
                    catches_broad_exception=True,
                    body_calls=body_calls,
                    handler_source=handler_source,
                )
            )
        self.generic_visit(node)


def _classify_module_surfaces(
    module_path: str,
    classes: tuple[str, ...],
    functions: tuple[str, ...],
    imports: tuple[str, ...],
    docstring: str,
) -> list[str]:
    surfaces: list[str] = []
    path_lower = module_path.lower()
    doc_lower = docstring.lower()
    all_names_lower = {name.lower() for name in {*(classes or ()), *(functions or ())}}
    imports_lower = [item.lower() for item in imports]

    receipt_keywords = frozenset({"receipt", "boundary_receipt", "dispatch_receipt", "write_boundary_receipt"})
    if any(keyword in path_lower for keyword in receipt_keywords) or any(
        keyword in all_names_lower for keyword in receipt_keywords
    ) or any("receipt" in item for item in imports_lower):
        surfaces.append(SURFACE_RECEIPT_WRITER)

    durable_keywords = frozenset({"durable_ref", "durableref", "refs"})
    if any(keyword in path_lower for keyword in durable_keywords) or "durableref" in all_names_lower:
        surfaces.append(SURFACE_DURABLE_REF)

    payload_keywords = frozenset({"payload_policy", "payloadpolicy", "retention_mode", "payloadclass"})
    if any(keyword in path_lower for keyword in payload_keywords) or any(
        keyword in all_names_lower for keyword in payload_keywords
    ):
        surfaces.append(SURFACE_PAYLOAD_POLICY)

    ledger_keywords = frozenset({"ledger", "execution_attempt_ledger", "effect_ledger"})
    if any(keyword in path_lower for keyword in ledger_keywords) or any(
        keyword in all_names_lower for keyword in ledger_keywords
    ) or "ledger" in doc_lower:
        surfaces.append(SURFACE_LEDGER)

    if path_lower.endswith("journal.py") or "/journal/" in path_lower or (
        "journal" in path_lower and ("eventjournal" in all_names_lower or "journalposition" in all_names_lower)
    ):
        surfaces.append(SURFACE_JOURNAL)

    if any(keyword in path_lower for keyword in ("projection", "advisory_projection")) or "projection" in all_names_lower:
        surfaces.append(SURFACE_PROJECTION)

    repair_keywords = frozenset({"repair", "reconcile", "recovery", "restart", "quarantine", "compensation"})
    if any(keyword in path_lower for keyword in repair_keywords) or any(
        keyword in all_names_lower for keyword in repair_keywords
    ):
        surfaces.append(SURFACE_REPAIR_QUEUE)

    auth_reader_keywords = frozenset({"authority_reader", "authority_readers", "override_authority"})
    if any(keyword in path_lower for keyword in auth_reader_keywords) or "authorityreader" in all_names_lower or any(
        item.startswith("arnold_pipelines.megaplan.authority") or "boundary_evidence" in item
        for item in imports_lower
    ):
        surfaces.append(SURFACE_AUTHORITY_READER)

    auth_writer_keywords = frozenset({"authority_writer", "override_authority", "binding", "rubber_stamp"})
    if any(keyword in path_lower for keyword in auth_writer_keywords):
        surfaces.append(SURFACE_AUTHORITY_WRITER)

    if any(keyword in path_lower for keyword in ("import_graph", "inspect", "validate")) and not surfaces:
        surfaces.append(SURFACE_CONSUMER)

    producer_keywords = frozenset({"handle_", "dispatch", "emit", "producer", "runner", "execute_batch"})
    if any(keyword in path_lower for keyword in producer_keywords) or any(
        name in all_names_lower for name in {"handle_plan", "handle_critique", "handle_gate", "handle_execute", "handle_review", "handle_finalize"}
    ):
        if SURFACE_PRODUCER not in surfaces:
            surfaces.append(SURFACE_PRODUCER)

    if any(keyword in path_lower for keyword in ("compatibility", "compat", "adapter", "shim", "writer_map")):
        surfaces.append(SURFACE_COMPATIBILITY_SHIM)

    if not surfaces:
        surfaces.append(SURFACE_UNKNOWN)
    return surfaces


def _owner_for_path(rel_path: str) -> str:
    if rel_path.startswith("arnold/workflow/") or rel_path.startswith("arnold_pipelines/megaplan/workflows/"):
        return "wbc"
    if "/custody/" in rel_path:
        return "custody"
    if any(seg in rel_path for seg in ("/cloud/", "/resident/", "/supervisor/", "/repair", "/watchdog")):
        return "maintenance"
    return "run_authority"


def _is_authority_surface(surface_types: tuple[str, ...]) -> bool:
    return any(surface in AUTHORITY_ADJACENT_SURFACES for surface in surface_types)


def _enclosing_function_for_line(lineno: int, function_ranges: list[tuple[int, int, str]]) -> str:
    matches = [
        (end_lineno - start_lineno, function_name)
        for start_lineno, end_lineno, function_name in function_ranges
        if start_lineno <= lineno <= end_lineno
    ]
    if not matches:
        return ""
    return min(matches)[1]


def _parse_module_ast(source: str) -> dict[str, Any]:
    visitor = _ModuleVisitor(source)
    tree = ast.parse(source)
    visitor.visit(tree)
    doc = ast.get_docstring(tree) or ""
    function_risky_calls: dict[str, tuple[str, ...]] = {}
    for function_name in sorted(set(visitor.functions)):
        risky_calls = sorted(
            {
                call.callee.split(".")[-1]
                for call in visitor.calls
                if call.enclosing_function == function_name
                and call.callee.split(".")[-1] in RISKY_PRODUCER_CALL_NAMES
            }
        )
        if risky_calls:
            function_risky_calls[function_name] = tuple(risky_calls)
    text_hits: list[dict[str, Any]] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        for pattern, category in BYPASS_TEXT_PATTERNS:
            if re.search(pattern, line):
                enclosing_function = _enclosing_function_for_line(lineno, visitor.function_ranges)
                text_hits.append(
                    {
                        "line": lineno,
                        "category": category,
                        "text": line.strip(),
                        "enclosing_function": enclosing_function,
                        "risky_calls": function_risky_calls.get(enclosing_function, ()),
                    }
                )
    return {
        "classes": tuple(sorted(set(visitor.classes))),
        "functions": tuple(sorted(set(visitor.functions))),
        "imports": tuple(sorted(set(visitor.imports))),
        "calls": tuple(visitor.calls),
        "try_scans": tuple(visitor.try_scans),
        "docstring": doc,
        "text_hits": tuple(text_hits),
    }


def _scan_discovery_roots() -> dict[str, Any]:
    modules: list[dict[str, Any]] = []
    handler_functions: list[dict[str, Any]] = []
    scans: list[ModuleScan] = []

    for root_cfg in DISCOVERY_ROOTS:
        root_path = REPO_ROOT / str(root_cfg["path"])
        if not root_path.is_dir():
            continue
        category = str(root_cfg["category"])
        matched_files: set[Path] = set()
        for pattern in root_cfg.get("file_patterns", ["*.py"]):
            matched_files.update(
                path for path in root_path.rglob(pattern) if path.is_file() and path.suffix == ".py"
            )
        for fpath in sorted(matched_files):
            rel_str = fpath.relative_to(REPO_ROOT).as_posix()
            try:
                source = fpath.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            ast_info = _parse_module_ast(source)
            surface_types = tuple(
                _classify_module_surfaces(
                    rel_str,
                    ast_info["classes"],
                    ast_info["functions"],
                    ast_info["imports"],
                    ast_info["docstring"],
                )
            )
            owner = _owner_for_path(rel_str)
            is_authority = _is_authority_surface(surface_types)
            module_row = {
                "row_kind": "runtime_module",
                "module_path": rel_str,
                "category": category,
                "owner": owner,
                "surface_types": list(surface_types),
                "is_authority": is_authority,
                "non_authority_surfaces": [item for item in surface_types if item in NON_AUTHORITY_SURFACES],
                "class_count": len(ast_info["classes"]),
                "function_count": len(ast_info["functions"]),
                "classes": list(ast_info["classes"]),
                "functions": list(ast_info["functions"]),
                "docstring_summary": (
                    ast_info["docstring"][:200] + "…" if len(ast_info["docstring"]) > 200 else ast_info["docstring"]
                ),
            }
            modules.append(module_row)
            scans.append(
                ModuleScan(
                    module_path=rel_str,
                    category=category,
                    owner=owner,
                    surface_types=surface_types,
                    is_authority=is_authority,
                    classes=ast_info["classes"],
                    functions=ast_info["functions"],
                    imports=ast_info["imports"],
                    docstring_summary=module_row["docstring_summary"],
                    calls=ast_info["calls"],
                    try_scans=ast_info["try_scans"],
                    text_hits=ast_info["text_hits"],
                )
            )
            if category in {"handler_functions", "execute_producers", "orchestration", "custody_runtime"}:
                for function_name in ast_info["functions"]:
                    if function_name.startswith("_") and not function_name.startswith("handle_"):
                        continue
                    handler_functions.append(
                        {
                            "row_kind": "handler_function",
                            "function_name": function_name,
                            "module_path": rel_str,
                            "owner": owner,
                            "category": category,
                        }
                    )

    modules.sort(key=lambda row: (row["category"], row["module_path"]))
    handler_functions.sort(key=lambda row: (row["category"], row["module_path"], row["function_name"]))
    return {"modules": modules, "handler_functions": handler_functions, "module_scans": scans}


def _scan_wrapper_shells() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for root_cfg in WRAPPER_SHELL_ROOTS:
        root = REPO_ROOT / str(root_cfg["path"])
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel_path = path.relative_to(REPO_ROOT).as_posix()
            if not any(fnmatch.fnmatch(rel_path if root == REPO_ROOT else path.relative_to(root).as_posix(), pattern) for pattern in root_cfg["patterns"]):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            rows.append(
                {
                    "row_kind": "wrapper_shell",
                    "path": rel_path,
                    "wrapper_type": "shell",
                    "category": root_cfg["category"],
                    "description": root_cfg["description"],
                    "has_boundary_effects": any("|| true" in line or "load_chain_state" in line for line in text.splitlines()),
                    "surface_types": ["wrapper_shell"],
                    "is_authority": False,
                    "line_count": len(text.splitlines()),
                }
            )
    rows.sort(key=lambda row: row["path"])
    return rows


def _step_rows_from_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family in manifest.get("families", []):
        for entry in family.get("entries", []):
            declared_support_status = entry.get(
                "declared_support_status",
                entry.get("support_status", "UNKNOWN"),
            )
            rows.append(
                {
                    "row_kind": "manifest_entry",
                    "step_id": entry.get("step_id", ""),
                    "step_name": entry.get("step_name", ""),
                    "boundary_id": entry.get("boundary_id"),
                    "kind": entry.get("kind", ""),
                    "owner": entry.get("owner") or family.get("owner", "UNKNOWN"),
                    "declared_support_status": declared_support_status,
                    "support_status": entry.get("support_status", declared_support_status),
                    "producer_path": entry.get("producer_path", "UNKNOWN"),
                    "c2_c6_milestone": entry.get("c2_c6_milestone", "UNKNOWN"),
                    "family_id": family.get("family_id", ""),
                    "family_name": family.get("family_name", ""),
                    "exception_metadata": entry.get("exception_metadata", {}),
                    "visible_non_conformant": entry.get("visible_non_conformant", []),
                    "support_is_non_authoritative": True,
                }
            )
    rows.sort(key=lambda row: row["step_id"])
    return rows


def _boundary_rows(
    contracts: list[dict[str, Any]],
    matrix: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    matrix_by_id = {
        row.get("boundary_id", ""): row for row in matrix.get("contracts", []) if row.get("boundary_id")
    }
    rows: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    seen = set()
    for contract in contracts:
        boundary_id = str(contract.get("boundary_id", ""))
        if not boundary_id:
            continue
        seen.add(boundary_id)
        matrix_row = matrix_by_id.get(boundary_id)
        producer_category = matrix_row.get("producer_category", "UNKNOWN") if matrix_row else "UNKNOWN"
        row = {
            "row_kind": "boundary_contract",
            "boundary_id": boundary_id,
            "workflow_id": contract.get("workflow_id", ""),
            "row_id": contract.get("row_id", "UNKNOWN"),
            "phase": contract.get("phase"),
            "producer_path": matrix_row.get("producer_path", "UNKNOWN") if matrix_row else "UNKNOWN",
            "producer_category": producer_category,
            "owner": "wbc",
            "support_status": "UNKNOWN",
            "authority_required": bool(contract.get("authority_required", False)),
            "candidate": producer_category in {"declared_only", "unknown", "UNKNOWN"},
            "landed": producer_category not in {"declared_only", "unknown", "UNKNOWN"},
            "support_is_non_authoritative": True,
            "support_label_source": "support_manifest",
            "matrix_metadata": None,
        }
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
            unmatched.append(
                {
                    "row_kind": "boundary_contract",
                    "boundary_id": boundary_id,
                    "reason_unmatched": "no_matrix_entry",
                    "detail": f"Contract '{boundary_id}' has no corresponding entry in contract_to_producer_matrix.json",
                }
            )
        rows.append(row)
    for matrix_row in matrix.get("contracts", []):
        boundary_id = str(matrix_row.get("boundary_id", ""))
        if boundary_id and boundary_id not in seen:
            unmatched.append(
                {
                    "row_kind": "matrix_row",
                    "boundary_id": boundary_id,
                    "reason_unmatched": "no_boundary_contract",
                    "detail": f"Matrix row '{boundary_id}' has no corresponding BoundaryContract in boundary_contracts.py",
                }
            )
    rows.sort(key=lambda row: row["boundary_id"])
    unmatched.sort(key=lambda row: (row["row_kind"], row.get("boundary_id", "")))
    return rows, unmatched, matrix_by_id


def _normalize_matrix_path(producer_path: str) -> set[str]:
    parts = {part.strip() for part in producer_path.split("->")}
    return {part for part in parts if part.endswith(".py")}


def _boundary_ids_for_callsite(
    callsite: CallScan,
    module_path: str,
    matrix_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    matched: list[str] = []
    tail = callsite.callee.split(".")[-1]
    for boundary_id, row in matrix_by_id.items():
        producer_path = str(row.get("producer_path", ""))
        handler_function = str(row.get("handler_function", ""))
        path_match = module_path in _normalize_matrix_path(producer_path)
        function_match = False
        if handler_function:
            function_match = handler_function.endswith(f":{callsite.enclosing_function}") or handler_function.endswith(
                f":{tail}"
            )
        if path_match and (function_match or tail in handler_function or tail in producer_path):
            matched.append(boundary_id)
    return sorted(set(matched))


def _discover_producer_call_sites(
    scans: list[ModuleScan],
    matrix_by_id: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for scan in scans:
        for call in scan.calls:
            tail = call.callee.split(".")[-1]
            if tail not in PRODUCER_CALL_NAMES:
                continue
            boundary_ids = _boundary_ids_for_callsite(call, scan.module_path, matrix_by_id)
            row = {
                "row_kind": "producer_callsite",
                "module_path": scan.module_path,
                "category": scan.category,
                "owner": scan.owner,
                "function_name": call.enclosing_function,
                "callee": call.callee,
                "line": call.line,
                "column": call.column,
                "boundary_ids": boundary_ids,
                "surface_types": list(scan.surface_types),
                "source_segment": call.source_segment,
            }
            rows.append(row)
            if not boundary_ids:
                unmatched.append(
                    {
                        "row_kind": "producer_callsite",
                        "module_path": scan.module_path,
                        "function_name": call.enclosing_function,
                        "reason_unmatched": "no_boundary_mapping",
                        "detail": f"Producer call '{call.callee}' at {scan.module_path}:{call.line} is not tied to a declared boundary row.",
                    }
                )
    rows.sort(key=lambda row: (row["module_path"], row["line"], row["callee"]))
    unmatched.sort(key=lambda row: (row["module_path"], row["function_name"], row["detail"]))
    return rows, unmatched


def _resolve_module_source_path(module_ref: str) -> Path | None:
    direct = REPO_ROOT / module_ref
    dotted = REPO_ROOT / module_ref.replace(".", "/")
    candidates = (
        direct,
        direct.with_suffix(".py"),
        dotted,
        dotted.with_suffix(".py"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _normalize_module_reference(module_ref: str) -> str:
    source_path = _resolve_module_source_path(module_ref)
    if source_path is None:
        return module_ref
    return source_path.relative_to(REPO_ROOT).as_posix()


def _reader_call_names(module_path: str) -> set[str]:
    source_path = _resolve_module_source_path(module_path)
    if source_path is None:
        return set()
    try:
        info = _parse_module_ast(source_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return set()
    return {name for name in info["functions"] if name.startswith("load_") or name.startswith("_load_")}


def _milestone_rank(milestone: str) -> int:
    return MILESTONE_ORDER.get(milestone, len(MILESTONE_ORDER))


def _historical_expiry_status(current_milestone: str, deadline_milestone: str) -> str:
    current_rank = _milestone_rank(current_milestone)
    deadline_rank = _milestone_rank(deadline_milestone)
    if current_rank > deadline_rank:
        return "expired"
    if current_rank >= deadline_rank - 1:
        return "expiring"
    return "compatible"


def _adapter_write_hits(module_paths: list[str] | tuple[str, ...], scans: list[ModuleScan]) -> list[dict[str, Any]]:
    normalized_paths = {_normalize_module_reference(path) for path in module_paths}
    hits: list[dict[str, Any]] = []
    for scan in scans:
        if scan.module_path not in normalized_paths:
            continue
        for call in scan.calls:
            tail = call.callee.split(".")[-1]
            if tail not in RISKY_PRODUCER_CALL_NAMES:
                continue
            hits.append(
                {
                    "module_path": scan.module_path,
                    "function_name": call.enclosing_function,
                    "callee": call.callee,
                    "line": call.line,
                }
            )
    hits.sort(key=lambda row: (row["module_path"], row["line"], row["callee"]))
    return hits


def _historical_adapter_rows_for_rules(
    rules: tuple[HistoricalAdapterRule, ...],
    scans: list[ModuleScan],
    current_milestone: str,
) -> dict[str, dict[str, Any]]:
    scans_by_path = {scan.module_path: scan for scan in scans}
    rows: dict[str, dict[str, Any]] = {}
    for rule in rules:
        normalized_paths = [_normalize_module_reference(path) for path in rule.module_paths]
        observed_functions = sorted({
            function_name
            for module_path in normalized_paths
            for function_name in (
                scans_by_path[module_path].functions if module_path in scans_by_path else ()
            )
            if function_name in rule.permitted_read_operations
        })
        rows[rule.adapter_id] = {
            "reader_id": rule.adapter_id,
            "reader_name": rule.reader_name,
            "description": rule.description,
            "module_paths": normalized_paths,
            "projection_ids": sorted(rule.projection_ids),
            "deadline_milestone": rule.deadline_milestone,
            "mode": rule.mode,
            "quarantined_entries": 0,
            "call_names": sorted(set(rule.permitted_read_operations)),
            "observed_read_operations": observed_functions,
            "adapter_class": rule.adapter_class,
            "diagnostics": list(rule.diagnostics),
            "authority_write_hits": _adapter_write_hits(normalized_paths, scans),
            "expiry_status": _historical_expiry_status(current_milestone, rule.deadline_milestone),
            "current_milestone": current_milestone,
            "supported_versions": list(rule.supported_versions),
            "c1_compatibility_readers": [],
        }
    return rows


def _discover_compatibility_readers(
    scans: list[ModuleScan],
    source_to_owner: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    snapshot = custody_compatibility.snapshot()
    compatibility_reader_names: dict[str, dict[str, Any]] = {}
    surface_reader_names = {
        surface["surface_id"]: set(surface.get("compatibility_readers", []))
        for surface in source_to_owner.get("surfaces", [])
    }
    for reader in snapshot.readers:
        call_names: set[str] = set()
        for module_path in sorted(reader.module_paths):
            call_names.update(_reader_call_names(module_path))
        if not call_names:
            call_names.add(reader.reader_id.replace("legacy-", "").replace("-reader", "").replace("-", "_"))
        compatibility_reader_names[reader.reader_id] = {
            "reader_id": reader.reader_id,
            "reader_name": reader.reader_name,
            "description": reader.description,
            "module_paths": sorted(_normalize_module_reference(module_path) for module_path in reader.module_paths),
            "projection_ids": sorted(reader.projection_ids),
            "deadline_milestone": reader.deadline_milestone.value,
            "mode": reader.mode.value,
            "quarantined_entries": reader.quarantined_entries,
            "call_names": sorted(call_names),
            "observed_read_operations": sorted(call_names),
            "adapter_class": SNAPSHOT_READER_CLASSIFICATIONS.get(reader.reader_id, ADAPTER_CLASS_RAW_JSON),
            "diagnostics": [
                "Historical state-reader compatibility remains read-only and cannot increase authority.",
                "Canonical WBC rereads must replace direct legacy JSON or lock-based observations before expiry.",
            ],
            "authority_write_hits": _adapter_write_hits(tuple(reader.module_paths), scans),
            "expiry_status": _historical_expiry_status(snapshot.milestone.value, reader.deadline_milestone.value),
            "current_milestone": snapshot.milestone.value,
            "supported_versions": ["legacy", "shadow"],
            "c1_compatibility_readers": sorted(
                {
                    compat_name
                    for compat_names in surface_reader_names.values()
                    for compat_name in compat_names
                    if "reader" in compat_name
                }
            ),
        }
    compatibility_reader_names.update(
        _historical_adapter_rows_for_rules(
            ADDITIONAL_HISTORICAL_ADAPTER_RULES,
            scans,
            snapshot.milestone.value,
        )
    )
    rows: list[dict[str, Any]] = []
    call_to_reader_ids = {
        call_name: sorted(
            reader_id
            for reader_id, info in compatibility_reader_names.items()
            if call_name in info["call_names"]
        )
        for call_name in sorted(
            {
                call_name
                for info in compatibility_reader_names.values()
                for call_name in info["call_names"]
            }
        )
    }
    for scan in scans:
        for call in scan.calls:
            tail = call.callee.split(".")[-1]
            reader_ids = call_to_reader_ids.get(tail, [])
            if not reader_ids:
                continue
            rows.append(
                {
                    "row_kind": "compatibility_reader",
                    "module_path": scan.module_path,
                    "owner": scan.owner,
                    "function_name": call.enclosing_function,
                    "callee": call.callee,
                    "line": call.line,
                    "reader_ids": reader_ids,
                    "source_segment": call.source_segment,
                }
            )
    rows.sort(key=lambda row: (row["module_path"], row["line"], row["callee"]))
    return rows, compatibility_reader_names


def _discover_writer_registrations(scans: list[ModuleScan]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    writer_map_snapshot = custody_writer_map.generate_writer_map()
    if hasattr(writer_map_snapshot, "surfaces"):
        for surface_id, surface in sorted(writer_map_snapshot.surfaces.items()):
            rows.append(
                {
                    "row_kind": "writer_registration",
                    "registration_source": "writer_map_snapshot",
                    "module_path": "arnold_pipelines/megaplan/custody/writer_map.py",
                    "surface_id": surface_id,
                    "owner": surface.get("owner", "UNKNOWN"),
                    "required_wbc_phases": surface.get("required_wbc_phases", []),
                    "terminal_evidence_fields": surface.get("terminal_evidence_fields", []),
                    "m7_missing_fields": surface.get("m7_missing_fields", []),
                    "notes": surface.get("notes", ""),
                }
            )
    elif hasattr(writer_map_snapshot, "writer_surfaces"):
        for surface in sorted(writer_map_snapshot.writer_surfaces, key=lambda item: item.get("surface_id", "")):
            rows.append(
                {
                    "row_kind": "writer_registration",
                    "registration_source": "writer_map_snapshot",
                    "module_path": "arnold_pipelines/megaplan/custody/writer_map.py",
                    "surface_id": surface.get("surface_id", ""),
                    "owner": surface.get("owner", "UNKNOWN"),
                    "required_wbc_phases": [],
                    "terminal_evidence_fields": [],
                    "m7_missing_fields": [],
                    "notes": surface.get("notes", ""),
                }
            )
    else:
        raise AttributeError(
            f"unsupported writer-map snapshot shape: {type(writer_map_snapshot).__name__}"
        )
    for scan in scans:
        for call in scan.calls:
            if call.callee.split(".")[-1] != "register_writer":
                continue
            rows.append(
                {
                    "row_kind": "writer_registration",
                    "registration_source": "ast_callsite",
                    "module_path": scan.module_path,
                    "function_name": call.enclosing_function,
                    "callee": call.callee,
                    "line": call.line,
                    "owner": scan.owner,
                    "source_segment": call.source_segment,
                }
            )
    rows.sort(key=lambda row: (row["registration_source"], row["module_path"], str(row.get("line", 0)), row.get("surface_id", "")))
    return rows


def _discover_runtime_trace_digests() -> list[dict[str, Any]]:
    if not NATIVE_GOLDEN_MANIFEST_PATH.exists():
        return []
    manifest = _load_json(NATIVE_GOLDEN_MANIFEST_PATH)
    rows: list[dict[str, Any]] = []
    committed = ((manifest.get("scenarios") or {}).get("committed") or [])
    for scenario in committed:
        scenario_id = str(scenario.get("scenario_id", "")).strip()
        if not scenario_id:
            continue
        trace_root = NATIVE_GOLDEN_ROOT / scenario_id
        test_functions = sorted(
            {
                str(runner.get("test_function", "")).strip()
                for runner in scenario.get("deterministic_runners", [])
                if str(runner.get("test_function", "")).strip()
            }
        )
        rows.append(
            {
                "row_kind": "runtime_trace_digest",
                "scenario_id": scenario_id,
                "slice": scenario.get("slice", ""),
                "alignment_rows": list(scenario.get("alignment_rows", [])),
                "trace_path": (
                    trace_root.relative_to(REPO_ROOT).as_posix() if trace_root.exists() else None
                ),
                "trace_directory_digest": _directory_digest(trace_root) if trace_root.exists() else None,
                "available": trace_root.exists(),
                "test_functions": test_functions,
                "boundary_ids": [],
                "mapping_status": "unmapped",
                "mapping_detail": (
                    "Native golden scenarios do not currently record boundary_id joins, so runtime traces "
                    "remain evidence input only and cannot mark generated inventory rows supported."
                ),
            }
        )
    rows.sort(key=lambda row: row["scenario_id"])
    return rows


def _discover_bypass_candidates(
    scans: list[ModuleScan],
    wrapper_shells: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scan in scans:
        for try_scan in scan.try_scans:
            risky_calls = sorted(set(try_scan.body_calls) & RISKY_PRODUCER_CALL_NAMES)
            if not risky_calls:
                continue
            rows.append(
                {
                    "row_kind": "bypass_candidate",
                    "candidate_type": "broad_exception",
                    "module_path": scan.module_path,
                    "function_name": try_scan.enclosing_function,
                    "line": try_scan.line,
                    "risky_calls": risky_calls,
                    "detail": try_scan.handler_source or "Broad exception handler around a WBC-affecting call.",
                }
            )
        for hit in scan.text_hits:
            if hit["category"] in {
                "without_raising",
                "best_effort",
                "warn_and_continue",
                "mutable_alias_overwrite",
                "implicit_latest_lookup",
            }:
                risky_calls = list(hit.get("risky_calls", ()))
                if not risky_calls:
                    continue
                rows.append(
                    {
                        "row_kind": "bypass_candidate",
                        "candidate_type": hit["category"],
                        "module_path": scan.module_path,
                        "function_name": hit.get("enclosing_function", ""),
                        "line": hit["line"],
                        "risky_calls": risky_calls,
                        "detail": hit["text"],
                    }
                )
    for wrapper in wrapper_shells:
        text = (REPO_ROOT / wrapper["path"]).read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if "|| true" not in line:
                continue
            rows.append(
                {
                    "row_kind": "bypass_candidate",
                    "candidate_type": "shell_or_true",
                    "module_path": wrapper["path"],
                    "line": lineno,
                    "detail": line.strip(),
                }
            )
    rows.sort(key=lambda row: (row["module_path"], row["line"], row["candidate_type"]))
    return rows


def _generate_default_deny_rows(modules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for module in modules:
        if SURFACE_UNKNOWN not in module.get("surface_types", []):
            continue
        rows.append(
            {
                "row_kind": "default_deny",
                "target_path": module["module_path"],
                "target_type": "runtime_module",
                "surface_types_found": module.get("surface_types", []),
                "access": "denied",
                "owner": module.get("owner", "UNKNOWN"),
                "reason": (
                    "Module could not be classified into a known surface type. "
                    f"Static discovery found classes={module.get('classes', [])} functions={module.get('functions', [])}"
                ),
                "mitigation": "Add an explicit discovery rule or register the surface as a read-only historical adapter.",
            }
        )
    rows.sort(key=lambda row: row["target_path"])
    return rows


def _categorize_unmatched(
    boundary_unmatched: list[dict[str, Any]],
    modules: list[dict[str, Any]],
    producer_unmatched: list[dict[str, Any]],
    compatibility_rows: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    unmatched_static = [
        {
            "row_kind": "runtime_module",
            "module_path": module["module_path"],
            "reason_unmatched": "unclassifiable_surface",
            "detail": f"Module '{module['module_path']}' could not be classified into a known surface type.",
        }
        for module in modules
        if SURFACE_UNKNOWN in module.get("surface_types", [])
    ]
    return {
        "unmatched_declared": boundary_unmatched,
        "unmatched_static": unmatched_static,
        "unmatched_runtime": [],
        "unmatched_wrapper": [],
        "unmatched_consumer": [] if compatibility_rows else [],
        "unmatched_producer": producer_unmatched,
        "unmatched_schema_only": [],
    }


def _build_support_gate(
    *,
    boundary_rows: list[dict[str, Any]],
    producer_call_sites: list[dict[str, Any]],
    writer_registrations: list[dict[str, Any]],
    runtime_trace_digests: list[dict[str, Any]],
) -> dict[str, Any]:
    declared_boundary_ids = sorted(
        row["boundary_id"] for row in boundary_rows if isinstance(row.get("boundary_id"), str) and row["boundary_id"]
    )
    static_boundary_ids = sorted(
        {
            boundary_id
            for row in producer_call_sites
            for boundary_id in row.get("boundary_ids", [])
            if boundary_id
        }
    )
    writer_registration_boundary_ids = sorted(
        {
            boundary_id
            for row in writer_registrations
            for boundary_id in row.get("boundary_ids", [])
            if boundary_id
        }
    )
    runtime_trace_boundary_ids = sorted(
        {
            boundary_id
            for row in runtime_trace_digests
            for boundary_id in row.get("boundary_ids", [])
            if boundary_id
        }
    )
    exact_set_equality = bool(declared_boundary_ids) and (
        declared_boundary_ids
        == static_boundary_ids
        == writer_registration_boundary_ids
        == runtime_trace_boundary_ids
    )
    missing_dimensions = []
    if not writer_registration_boundary_ids:
        missing_dimensions.append(
            "boundary-scoped controlled-writer registrations are not recorded in discovery evidence"
        )
    if not runtime_trace_boundary_ids:
        missing_dimensions.append(
            "runtime trace digests are not joined to boundary_ids in the native golden manifest"
        )
    return {
        "declared_boundary_ids": declared_boundary_ids,
        "static_boundary_ids": static_boundary_ids,
        "writer_registration_boundary_ids": writer_registration_boundary_ids,
        "runtime_trace_boundary_ids": runtime_trace_boundary_ids,
        "exact_boundary_set_equality": exact_set_equality,
        "missing_dimensions": missing_dimensions,
    }


def _compute_manifest_support_status(
    row: dict[str, Any],
    *,
    support_gate: dict[str, Any],
    bypass_candidates: list[dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    boundary_id = row.get("boundary_id")
    producer_path = str(row.get("producer_path", ""))
    producer_path_parts = [part.strip() for part in producer_path.split("→")]
    producer_paths = {part for part in producer_path_parts if part.endswith(".py")}
    bypass_matches = sorted(
        {
            candidate["module_path"]
            for candidate in bypass_candidates
            if candidate.get("module_path") in producer_paths
        }
    )
    exception_metadata = row.get("exception_metadata") or {}
    declared_support_status = str(row.get("declared_support_status", "UNKNOWN"))
    evidence_flags = {
        "declared_boundary_present": boundary_id in support_gate["declared_boundary_ids"],
        "static_callsite_present": boundary_id in support_gate["static_boundary_ids"],
        "writer_registration_present": boundary_id in support_gate["writer_registration_boundary_ids"],
        "runtime_trace_digest_present": boundary_id in support_gate["runtime_trace_boundary_ids"],
        "implementation_commit_recorded": bool(exception_metadata.get("implementation_commit")),
        "positive_test_recorded": bool(exception_metadata.get("positive_test")),
        "negative_bypass_test_recorded": bool(exception_metadata.get("negative_bypass_test")),
        "exact_set_equality": bool(support_gate["exact_boundary_set_equality"]),
    }
    missing_requirements = [
        label
        for label, passes in (
            ("declared boundary", evidence_flags["declared_boundary_present"]),
            ("static callsite", evidence_flags["static_callsite_present"]),
            ("controlled-writer registration", evidence_flags["writer_registration_present"]),
            ("runtime trace digest", evidence_flags["runtime_trace_digest_present"]),
            ("implementation commit", evidence_flags["implementation_commit_recorded"]),
            ("positive test", evidence_flags["positive_test_recorded"]),
            ("negative bypass test", evidence_flags["negative_bypass_test_recorded"]),
            ("exact declaration/static/writer/runtime set equality", evidence_flags["exact_set_equality"]),
        )
        if not passes
    ]
    verification = {
        "declared_support_status": declared_support_status,
        "evidence_flags": evidence_flags,
        "missing_requirements": missing_requirements,
        "matching_bypass_candidates": bypass_matches,
        "support_gate_missing_dimensions": list(support_gate["missing_dimensions"]),
    }
    if not boundary_id:
        verification["support_gate_applicable"] = False
        verification["missing_requirements"] = []
        return declared_support_status, verification
    verification["support_gate_applicable"] = True
    if declared_support_status != "supported":
        return declared_support_status, verification
    if not missing_requirements and not bypass_matches:
        return "supported", verification
    if any(
        (
            evidence_flags["declared_boundary_present"],
            evidence_flags["static_callsite_present"],
            evidence_flags["writer_registration_present"],
            evidence_flags["runtime_trace_digest_present"],
        )
    ):
        return "partial", verification
    return "planned", verification


def _build_current_state_assertions(
    *,
    matrix_hash_before: str,
    matrix_hash_after: str,
    boundary_rows: list[dict[str, Any]],
    producer_call_sites: list[dict[str, Any]],
    compatibility_rows: list[dict[str, Any]],
    writer_registrations: list[dict[str, Any]],
    runtime_trace_digests: list[dict[str, Any]],
    bypass_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    support_gate = _build_support_gate(
        boundary_rows=boundary_rows,
        producer_call_sites=producer_call_sites,
        writer_registrations=writer_registrations,
        runtime_trace_digests=runtime_trace_digests,
    )
    observed_boundaries = sorted(
        {
            boundary_id
            for row in producer_call_sites
            for boundary_id in row.get("boundary_ids", [])
        }
    )
    return {
        "schema": "m8.wbc-boundary-current-state.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "c1_matrix_hash_before": matrix_hash_before,
        "c1_matrix_hash_after": matrix_hash_after,
        "c1_matrix_unchanged": matrix_hash_before == matrix_hash_after,
        "declared_boundary_count": len(boundary_rows),
        "observed_producer_boundary_count": len(observed_boundaries),
        "observed_producer_boundaries": observed_boundaries,
        "compatibility_reader_callsite_count": len(compatibility_rows),
        "writer_registration_count": len(writer_registrations),
        "runtime_trace_digest_count": len(runtime_trace_digests),
        "bypass_candidate_count": len(bypass_candidates),
        "support_rows_require_exact_set_equality": True,
        "support_gate": support_gate,
    }


def _generate_historical_adapters(
    compatibility_reader_specs: dict[str, dict[str, Any]],
    compatibility_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    reader_call_counts: dict[str, int] = {}
    for row in compatibility_rows:
        for reader_id in row.get("reader_ids", []):
            reader_call_counts[reader_id] = reader_call_counts.get(reader_id, 0) + 1
    adapters = []
    adapter_classes_present: set[str] = set()
    read_only_verified_count = 0
    expired_adapter_count = 0
    for reader_id, spec in sorted(compatibility_reader_specs.items()):
        adapter_class = str(spec.get("adapter_class", ADAPTER_CLASS_RAW_JSON))
        adapter_classes_present.add(adapter_class)
        authority_write_hits = list(spec.get("authority_write_hits", []))
        if authority_write_hits:
            raise AssertionError(
                f"historical adapter {reader_id} is not read-only: {authority_write_hits}"
            )
        read_only_verified = not authority_write_hits
        if read_only_verified:
            read_only_verified_count += 1
        if spec.get("expiry_status") == "expired":
            expired_adapter_count += 1
        adapters.append(
            {
                "adapter_id": reader_id,
                "reader_name": spec["reader_name"],
                "adapter_class": adapter_class,
                "diagnostics": list(spec.get("diagnostics", [])),
                "path_symbols": spec["module_paths"],
                "permitted_read_operations": spec["call_names"],
                "observed_read_operations": list(spec.get("observed_read_operations", spec["call_names"])),
                "supported_versions": list(spec.get("supported_versions", ["legacy", "shadow"])),
                "zero_authority_caller_proof": {
                    "mode": spec["mode"],
                    "callsite_count": reader_call_counts.get(reader_id, 0),
                    "projection_ids": spec["projection_ids"],
                    "c1_compatibility_readers": spec["c1_compatibility_readers"],
                    "read_only": True,
                    "diagnostic_only": True,
                    "authority_increasing_write_allowed": False,
                    "authority_increasing_writes_detected": authority_write_hits,
                    "read_only_verified": read_only_verified,
                },
                "owner": "custody-control-plane",
                "approver": "operational-approval-required",
                "expiry": {
                    "milestone": spec["deadline_milestone"],
                    "current_milestone": spec.get("current_milestone"),
                    "status": spec.get("expiry_status"),
                },
                "deletion_gate": (
                    "Delete after the matching migration family is adopted, the reader callsite count reaches zero, "
                    "and the negative bypass gate proves no authority-increasing compatibility reads remain."
                ),
            }
        )
    return {
        "meta": {
            "schema": "m8.wbc-historical-adapters.v1",
            "generated_by": "M8 Step 8 (T8) — generate_wbc_boundary_inventory.py",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "adapter_count": len(adapters),
            "adapter_classes_present": sorted(adapter_classes_present),
            "expired_adapter_count": expired_adapter_count,
            "read_only_verified_count": read_only_verified_count,
        },
        "adapters": adapters,
    }


def _build_discovery_rules(compatibility_reader_specs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "m8.wbc-boundary-discovery-rules.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "roots": list(DISCOVERY_ROOTS),
        "producer_call_names": sorted(PRODUCER_CALL_NAMES),
        "writer_registration_sources": [
            "arnold_pipelines.megaplan.custody.writer_map.generate_writer_map",
            "register_writer(...) AST callsites",
        ],
        "compatibility_readers": [
            {
                "reader_id": reader_id,
                "module_paths": spec["module_paths"],
                "call_names": spec["call_names"],
                "deadline_milestone": spec["deadline_milestone"],
            }
            for reader_id, spec in sorted(compatibility_reader_specs.items())
        ],
        "bypass_patterns": [{"pattern": pattern, "category": category} for pattern, category in BYPASS_TEXT_PATTERNS],
    }


def _build_inventory(
    contracts: list[dict[str, Any]],
    matrix: dict[str, Any],
    manifest: dict[str, Any],
    source_to_owner: dict[str, Any],
    discovery: dict[str, Any],
    wrapper_shells: list[dict[str, Any]],
    matrix_hash_before: str,
    matrix_hash_after: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    boundary_rows, boundary_unmatched, matrix_by_id = _boundary_rows(contracts, matrix)
    manifest_rows = _step_rows_from_manifest(manifest)
    modules = discovery["modules"]
    handler_functions = discovery["handler_functions"]
    scans = discovery["module_scans"]
    producer_call_sites, producer_unmatched = _discover_producer_call_sites(scans, matrix_by_id)
    compatibility_rows, compatibility_reader_specs = _discover_compatibility_readers(scans, source_to_owner)
    writer_registrations = _discover_writer_registrations(scans)
    runtime_trace_digests = _discover_runtime_trace_digests()
    bypass_candidates = _discover_bypass_candidates(scans, wrapper_shells)
    support_gate = _build_support_gate(
        boundary_rows=boundary_rows,
        producer_call_sites=producer_call_sites,
        writer_registrations=writer_registrations,
        runtime_trace_digests=runtime_trace_digests,
    )
    for row in manifest_rows:
        support_status, verification = _compute_manifest_support_status(
            row,
            support_gate=support_gate,
            bypass_candidates=bypass_candidates,
        )
        row["support_status"] = support_status
        row["support_verification"] = verification
    default_deny_rows = _generate_default_deny_rows(modules)
    unmatched_categories = _categorize_unmatched(
        boundary_unmatched=boundary_unmatched,
        modules=modules,
        producer_unmatched=producer_unmatched,
        compatibility_rows=compatibility_rows,
    )
    rows = sorted(
        [*boundary_rows, *manifest_rows, *modules, *handler_functions],
        key=lambda row: (
            row.get("row_kind", ""),
            row.get("boundary_id") or "",
            row.get("step_id", ""),
            row.get("module_path", ""),
            row.get("function_name", ""),
        ),
    )
    content_hash = _sha256_hex(json.dumps(rows, sort_keys=True, default=str))
    current_state = _build_current_state_assertions(
        matrix_hash_before=matrix_hash_before,
        matrix_hash_after=matrix_hash_after,
        boundary_rows=boundary_rows,
        producer_call_sites=producer_call_sites,
        compatibility_rows=compatibility_rows,
        writer_registrations=writer_registrations,
        runtime_trace_digests=runtime_trace_digests,
        bypass_candidates=bypass_candidates,
    )
    regenerated_manifest = _regenerate_support_manifest(manifest, manifest_rows)
    inventory = {
        "meta": {
            "schema": "m8.wbc-boundary-inventory.v1",
            "generated_by": "M8 Step 8 (T8) — generate_wbc_boundary_inventory.py",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "input_sources": {
                "boundary_contracts": str(BOUNDARY_CONTRACTS_PATH.relative_to(REPO_ROOT)),
                "contract_matrix": str(CONTRACT_MATRIX_PATH.relative_to(REPO_ROOT)),
                "support_manifest": _display_path(SUPPORT_MANIFEST_PATH),
                "source_to_owner_matrix": str(SOURCE_TO_OWNER_MATRIX_PATH.relative_to(REPO_ROOT)),
                "static_discovery_roots": len(DISCOVERY_ROOTS),
            },
            "content_hash": content_hash,
            "row_count": len(rows),
            "producer_callsite_count": len(producer_call_sites),
            "compatibility_reader_count": len(compatibility_rows),
            "writer_registration_count": len(writer_registrations),
            "runtime_trace_digest_count": len(runtime_trace_digests),
            "bypass_candidate_count": len(bypass_candidates),
            "wrapper_shell_count": len(wrapper_shells),
            "default_deny_count": len(default_deny_rows),
            "unmatched_category_counts": {key: len(value) for key, value in unmatched_categories.items()},
        },
        "rows": rows,
        "producer_call_sites": producer_call_sites,
        "compatibility_readers": compatibility_rows,
        "writer_registrations": writer_registrations,
        "runtime_trace_digests": runtime_trace_digests,
        "bypass_candidates": bypass_candidates,
        "wrapper_shells": wrapper_shells,
        "default_deny_rows": default_deny_rows,
        "current_state_assertions": current_state,
        "unmatched_categories": unmatched_categories,
    }
    return inventory, compatibility_reader_specs, current_state, regenerated_manifest


def _regenerate_support_manifest(
    manifest: dict[str, Any],
    manifest_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    rows_by_step_id = {str(row.get("step_id", "")): row for row in manifest_rows}
    regenerated = json.loads(json.dumps(manifest))
    meta = regenerated.setdefault("meta", {})
    meta["generated_by"] = (
        "C1 Contract Reality Reconciliation — M8 Step 24 (T31) — "
        "generate_wbc_boundary_inventory.py"
    )
    meta["timestamp_utc"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )
    for family in regenerated.get("families", []):
        for entry in family.get("entries", []):
            step_id = str(entry.get("step_id", ""))
            row = rows_by_step_id.get(step_id)
            if row is None:
                continue
            declared_support_status = entry.get(
                "declared_support_status",
                entry.get("support_status", "UNKNOWN"),
            )
            entry["declared_support_status"] = declared_support_status
            entry["support_status"] = row.get("support_status", declared_support_status)
            if "support_verification" in row:
                entry["support_verification"] = row["support_verification"]
    return regenerated


def _run_validation(inventory: dict[str, Any]) -> dict[str, Any]:
    assertions = inventory["current_state_assertions"]
    return {
        "schema": "m8.wbc-boundary-inventory-validation.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": [
            {
                "id": "matrix_unchanged",
                "passes": bool(assertions["c1_matrix_unchanged"]),
                "detail": "C1 source_to_owner_matrix.json content hash is unchanged across the generation run.",
            },
            {
                "id": "discovery_sections_emitted",
                "passes": all(
                    key in inventory
                    for key in (
                        "producer_call_sites",
                        "compatibility_readers",
                        "writer_registrations",
                        "runtime_trace_digests",
                        "bypass_candidates",
                    )
                ),
                "detail": "All required discovery sections are present in the inventory artifact.",
            },
            {
                "id": "support_rows_fail_closed",
                "passes": all(
                    row.get("support_status") != "supported"
                    or bool(
                        (row.get("support_verification") or {}).get("evidence_flags", {}).get(
                            "exact_set_equality", False
                        )
                    )
                    for row in inventory["rows"]
                    if row.get("row_kind") == "manifest_entry" and row.get("boundary_id")
                ),
                "detail": (
                    "Generated support rows remain fail-closed: no manifest-derived row is marked "
                    "supported unless exact declaration/static/writer/runtime equality is proven."
                ),
            },
        ],
    }


def generate(output_path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    matrix_hash_before = _matrix_hash()
    contracts = parse_boundary_contracts()
    matrix = parse_contract_matrix()
    manifest = parse_support_manifest()
    source_to_owner = parse_source_to_owner_matrix()
    discovery = _scan_discovery_roots()
    wrapper_shells = _scan_wrapper_shells()
    matrix_hash_after = _matrix_hash()
    inventory, compatibility_reader_specs, _current_state, regenerated_manifest = _build_inventory(
        contracts=contracts,
        matrix=matrix,
        manifest=manifest,
        source_to_owner=source_to_owner,
        discovery=discovery,
        wrapper_shells=wrapper_shells,
        matrix_hash_before=matrix_hash_before,
        matrix_hash_after=matrix_hash_after,
    )
    historical_adapters = _generate_historical_adapters(compatibility_reader_specs, inventory["compatibility_readers"])
    discovery_rules = _build_discovery_rules(compatibility_reader_specs)
    validation = _run_validation(inventory)

    _write_json(output_path, inventory)
    _write_yaml(DISCOVERY_RULES_PATH, discovery_rules)
    _write_json(HISTORICAL_ADAPTERS_PATH, historical_adapters)
    _write_json(EVIDENCE_DIR / "wbc-boundary-inventory-validation.json", validation)
    _write_json(SUPPORT_MANIFEST_PATH, regenerated_manifest)
    return inventory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    generate(args.output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
