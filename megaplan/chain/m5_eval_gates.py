"""Scoped M5-eval source gates.

These checks protect the new Evaluand SDK path from drifting back toward the
old bare-float judge surface or a second eval-specific journal.  They are
deliberately scoped to new M5 eval modules so legacy demo/planning/cost
surfaces can remain compatible while the new path hardens around events.ndjson.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent.parent

NEW_EVAL_MODULES: tuple[str, ...] = (
    "megaplan/_pipeline/eval_judge_wrapper.py",
    "megaplan/_pipeline/judge_manifest.py",
    "megaplan/_pipeline/judge_manifest_discovery.py",
    "megaplan/observability/evaluand.py",
)

OLD_PATH_ALLOWLIST: tuple[str, ...] = (
    "megaplan/_pipeline/demo_judges.py",
    "megaplan/_pipeline/planning_bindings.py",
    "megaplan/editorial/gating.py",
    "megaplan/observability/cost.py",
)

GUARDED_CALIBRATION_TARGETS: tuple[str, ...] = (
    "megaplan/auto.py",
    "megaplan/observability/cost.py",
    "megaplan/calibration/**/*.py",
)

REPLAY_ORACLE_MARKER_PATH = "tests/oracles/test_evaluand_replay_oracle.py"
REPLAY_ORACLE_MARKER_NAME = "REPLAY_ORACLE_CORPUS_SIZE"

_EVAL_JOURNAL_NAMES: tuple[str, ...] = (
    "evaluand.ndjson",
    "evaluands.ndjson",
    "evaluand.jsonl",
    "evaluands.jsonl",
    "eval-ledger.ndjson",
    "eval_ledger.ndjson",
    "evaluand-ledger.ndjson",
    "evaluand_ledger.ndjson",
)

_JOIN_FORBIDDEN_IMPORT_PARTS: tuple[str, ...] = (
    ".cost",
    "observability.cost",
)

_JOIN_FORBIDDEN_CALL_NAMES: tuple[str, ...] = (
    "judge",
    "score",
    "scorer",
    "write_evaluand",
    "write_evaluand_event",
    "_classify_vendor",
)

_GUARDED_LEDGER_CALL_NAMES: tuple[str, ...] = (
    "better",
    "read_evaluand_events",
    "re_judge",
    "write_evaluand",
    "write_evaluand_event",
)

_GUARDED_LEDGER_IMPORT_NAMES: tuple[str, ...] = (
    "BetterResult",
    "EvaluandRecord",
    "ReJudgeOutcome",
    "better",
    "read_evaluand_events",
    "re_judge",
    "write_evaluand",
    "write_evaluand_event",
)

_VENDOR_SUBSTRINGS: tuple[str, ...] = (
    "claude",
    "codex",
    "openai",
    "anthropic",
    "deepseek",
    "hermes",
    "gemini",
    "kimi",
)


@dataclass(frozen=True)
class M5EvalGateFinding:
    path: str
    line: int
    code: str
    detail: str


@dataclass(frozen=True)
class M5EvalGateResult:
    passed: bool
    findings: tuple[M5EvalGateFinding, ...] = field(default_factory=tuple)


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _candidate_paths(root: Path, paths: Sequence[str] | None) -> tuple[Path, ...]:
    selected = paths if paths is not None else NEW_EVAL_MODULES
    return tuple(root / path for path in selected)


def _guarded_target_paths(root: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    for pattern in GUARDED_CALIBRATION_TARGETS:
        if "**" in pattern or "*" in pattern:
            paths.extend(sorted(root.glob(pattern)))
            continue
        path = root / pattern
        if path.exists():
            paths.append(path)
    return tuple(paths)


def _is_numeric_literal(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, (int, float))


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _import_module_name(node: ast.AST) -> str:
    if isinstance(node, ast.Import):
        return ",".join(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return node.module or ""
    return ""


def _imported_names(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.asname or alias.name.rsplit(".", 1)[-1] for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return tuple(alias.asname or alias.name for alias in node.names)
    return ()


def _find_bare_float_judgments(
    tree: ast.AST,
    *,
    rel_path: str,
) -> Iterable[M5EvalGateFinding]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            call_name = _call_name(node.func)
            for keyword in node.keywords:
                if keyword.arg != "score" or not _is_numeric_literal(keyword.value):
                    continue
                if call_name.endswith("EvaluandRecord"):
                    continue
                yield M5EvalGateFinding(
                    rel_path,
                    node.lineno,
                    "M5_EVAL_BARE_FLOAT_JUDGMENT",
                    "new eval modules must record judgments as EvaluandRecord events, not bare score literals",
                )
            if call_name.endswith("write_evaluand") and len(node.args) >= 2:
                if _is_numeric_literal(node.args[1]):
                    yield M5EvalGateFinding(
                        rel_path,
                        node.lineno,
                        "M5_EVAL_BARE_FLOAT_JUDGMENT",
                        "write_evaluand must not receive a bare numeric judgment",
                    )
            if call_name.endswith("write_evaluand_event") and len(node.args) >= 2:
                if _is_numeric_literal(node.args[1]):
                    yield M5EvalGateFinding(
                        rel_path,
                        node.lineno,
                        "M5_EVAL_BARE_FLOAT_JUDGMENT",
                        "write_evaluand_event must receive an EvaluandRecord",
                    )


def check_no_bare_float_judgments(
    root: Path | str = REPO_ROOT,
    *,
    paths: Sequence[str] | None = None,
) -> tuple[M5EvalGateFinding, ...]:
    repo_root = Path(root)
    findings: list[M5EvalGateFinding] = []
    for path in _candidate_paths(repo_root, paths):
        if not path.exists():
            continue
        rel_path = _relative_path(path, repo_root)
        if rel_path in OLD_PATH_ALLOWLIST:
            continue
        tree = ast.parse(_read_source(path), filename=rel_path)
        findings.extend(_find_bare_float_judgments(tree, rel_path=rel_path))
    return tuple(findings)


def check_no_second_eval_journals(
    root: Path | str = REPO_ROOT,
    *,
    paths: Sequence[str] | None = None,
) -> tuple[M5EvalGateFinding, ...]:
    repo_root = Path(root)
    findings: list[M5EvalGateFinding] = []
    for path in _candidate_paths(repo_root, paths):
        if not path.exists():
            continue
        rel_path = _relative_path(path, repo_root)
        for line_no, line in enumerate(_read_source(path).splitlines(), start=1):
            for journal_name in _EVAL_JOURNAL_NAMES:
                if journal_name in line and "events.ndjson" not in line:
                    findings.append(
                        M5EvalGateFinding(
                            rel_path,
                            line_no,
                            "M5_EVAL_SECOND_JOURNAL",
                            f"eval records must use events.ndjson, not {journal_name}",
                        )
                    )
    return tuple(findings)


def _better_function(tree: ast.AST) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "better":
            return node
    return None


def check_better_join_is_pure(
    root: Path | str = REPO_ROOT,
    *,
    rel_path: str = "megaplan/observability/evaluand.py",
) -> tuple[M5EvalGateFinding, ...]:
    repo_root = Path(root)
    path = repo_root / rel_path
    tree = ast.parse(_read_source(path), filename=rel_path)
    function = _better_function(tree)
    if function is None:
        return (
            M5EvalGateFinding(
                rel_path,
                1,
                "M5_EVAL_BETTER_JOIN_MISSING",
                "better(...) must exist as the recorded-ledger join",
            ),
        )

    findings: list[M5EvalGateFinding] = []
    for node in ast.walk(function):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_name = _import_module_name(node)
            if any(part in module_name for part in _JOIN_FORBIDDEN_IMPORT_PARTS):
                findings.append(
                    M5EvalGateFinding(
                        rel_path,
                        node.lineno,
                        "M5_EVAL_BETTER_COST_IMPORT",
                        "better(...) must not import cost attribution code",
                    )
                )
        elif isinstance(node, ast.Call):
            call_name = _call_name(node.func)
            if any(call_name.endswith(name) for name in _JOIN_FORBIDDEN_CALL_NAMES):
                findings.append(
                    M5EvalGateFinding(
                        rel_path,
                        node.lineno,
                        "M5_EVAL_BETTER_LIVE_JUDGE_CALL",
                        "better(...) must only fold recorded Evaluand events",
                    )
                )
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            lowered = node.value.lower()
            if any(vendor in lowered for vendor in _VENDOR_SUBSTRINGS):
                findings.append(
                    M5EvalGateFinding(
                        rel_path,
                        node.lineno,
                        "M5_EVAL_BETTER_VENDOR_HEURISTIC",
                        "better(...) must not classify vendors by substring",
                    )
                )
    return tuple(findings)


def replay_oracle_corpus_marker(
    root: Path | str = REPO_ROOT,
    *,
    rel_path: str = REPLAY_ORACLE_MARKER_PATH,
) -> int | None:
    repo_root = Path(root)
    path = repo_root / rel_path
    if not path.exists():
        return None

    tree = ast.parse(_read_source(path), filename=rel_path)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Name)
                and target.id == REPLAY_ORACLE_MARKER_NAME
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, int)
            ):
                return node.value.value
    return None


def check_calibration_source_purity(
    root: Path | str = REPO_ROOT,
) -> tuple[M5EvalGateFinding, ...]:
    """Scan ``megaplan/calibration/**/*.py`` for prohibited patterns.

    Enforces three invariants on calibration source files:

    1. **No bare numeric outcomes** — ``outcome = 0.72`` or
       ``CapabilityClaim(outcome=0.72)`` inside calibration sources.
    2. **No STATE_\\* imports or usages** — any import of a ``STATE_*``
       constant from ``megaplan.types`` or bare ``STATE_*`` reference.
    3. **No GateRecommendation references** — any import, type annotation,
       or bare name ``GateRecommendation`` detected via AST (does NOT
       require the symbol to be importable).

    The check is purely AST-based for (2) and (3) — it never imports the
    symbols it is checking for.
    """
    repo_root = Path(root)
    findings: list[M5EvalGateFinding] = []

    for path in sorted(repo_root.glob("megaplan/calibration/**/*.py")):
        rel_path = _relative_path(path, repo_root)
        tree = ast.parse(_read_source(path), filename=rel_path)
        findings.extend(
            _find_bare_numeric_outcomes(tree, rel_path=rel_path)
        )
        findings.extend(
            _find_state_star_references(tree, rel_path=rel_path)
        )
        findings.extend(
            _find_gaterecommendation_refs(tree, rel_path=rel_path)
        )

    return tuple(findings)


def _find_bare_numeric_outcomes(
    tree: ast.AST,
    *,
    rel_path: str,
) -> list[M5EvalGateFinding]:
    """Detect ``outcome = <numeric>`` and ``Fn(outcome=<numeric>)`` in AST."""
    findings: list[M5EvalGateFinding] = []

    for node in ast.walk(tree):
        # Assignment: outcome = 0.72
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "outcome":
                    if _is_numeric_literal(node.value):
                        findings.append(
                            M5EvalGateFinding(
                                rel_path,
                                node.lineno,
                                "M5_CAL_BARE_NUMERIC_OUTCOME",
                                "calibration sources must not assign a bare numeric literal to 'outcome'",
                            )
                        )
        # Keyword argument: CapabilityClaim(outcome=0.72, ...)
        elif isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "outcome" and _is_numeric_literal(keyword.value):
                    findings.append(
                        M5EvalGateFinding(
                            rel_path,
                            node.lineno,
                            "M5_CAL_BARE_NUMERIC_OUTCOME",
                            "calibration sources must not pass a bare numeric literal as outcome=",
                        )
                    )

    return findings


def _find_state_star_references(
    tree: ast.AST,
    *,
    rel_path: str,
) -> list[M5EvalGateFinding]:
    """Detect ``STATE_*`` imports and bare ``STATE_*`` name references in AST."""
    findings: list[M5EvalGateFinding] = []

    for node in ast.walk(tree):
        # Import: import megaplan.types (allows types.STATE_*)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname and alias.asname.startswith("STATE_"):
                    findings.append(
                        M5EvalGateFinding(
                            rel_path,
                            node.lineno,
                            "M5_CAL_STATE_STAR_IMPORT",
                            f"calibration sources must not import STATE_* names: {alias.asname}",
                        )
                    )

        # ImportFrom: from megaplan.types import STATE_INITIALIZED, ...
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                if name.startswith("STATE_"):
                    findings.append(
                        M5EvalGateFinding(
                            rel_path,
                            node.lineno,
                            "M5_CAL_STATE_STAR_IMPORT",
                            f"calibration sources must not import STATE_*: {name}",
                        )
                    )

        # Bare Name usage: STATE_INITIALIZED, etc.
        elif isinstance(node, ast.Name) and node.id.startswith("STATE_"):
            # Only flag if it's a reference (not an assignment target)
            # But assignments to STATE_* in calibration would also be bad.
            findings.append(
                M5EvalGateFinding(
                    rel_path,
                    node.lineno,
                    "M5_CAL_STATE_STAR_USAGE",
                    f"calibration sources must not reference STATE_* names: {node.id}",
                )
            )

        # Attribute access: types.STATE_INITIALIZED
        elif isinstance(node, ast.Attribute) and node.attr.startswith("STATE_"):
            findings.append(
                M5EvalGateFinding(
                    rel_path,
                    node.lineno,
                    "M5_CAL_STATE_STAR_USAGE",
                    f"calibration sources must not reference STATE_* attributes: .{node.attr}",
                )
            )

    return findings


def _find_gaterecommendation_refs(
    tree: ast.AST,
    *,
    rel_path: str,
) -> list[M5EvalGateFinding]:
    """Detect ``GateRecommendation`` imports and name references in AST.

    This is a pure AST string-match — it does **not** require
    ``GateRecommendation`` to be an importable symbol anywhere.
    """
    findings: list[M5EvalGateFinding] = []

    for node in ast.walk(tree):
        # Import: import foo.GateRecommendation
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name
                if "GateRecommendation" in name:
                    findings.append(
                        M5EvalGateFinding(
                            rel_path,
                            node.lineno,
                            "M5_CAL_GATEREC_IMPORT",
                            "calibration sources must not import GateRecommendation",
                        )
                    )

        # ImportFrom: from x import GateRecommendation
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                if name == "GateRecommendation":
                    findings.append(
                        M5EvalGateFinding(
                            rel_path,
                            node.lineno,
                            "M5_CAL_GATEREC_IMPORT",
                            "calibration sources must not import GateRecommendation",
                        )
                    )

        # Bare Name: GateRecommendation (type annotation, variable, etc.)
        elif isinstance(node, ast.Name) and node.id == "GateRecommendation":
            findings.append(
                M5EvalGateFinding(
                    rel_path,
                    node.lineno,
                    "M5_CAL_GATEREC_REFERENCE",
                    "calibration sources must not reference GateRecommendation",
                )
            )

    return findings


def check_calibration_guard_targets(
    root: Path | str = REPO_ROOT,
) -> tuple[M5EvalGateFinding, ...]:
    repo_root = Path(root)
    marker = replay_oracle_corpus_marker(repo_root)
    findings: list[M5EvalGateFinding] = []
    gate_result = run_m5_eval_gates(repo_root)

    for path in _guarded_target_paths(repo_root):
        rel_path = _relative_path(path, repo_root)
        tree = ast.parse(_read_source(path), filename=rel_path)
        consumes_ledger = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if any(name in _GUARDED_LEDGER_IMPORT_NAMES for name in _imported_names(node)):
                    consumes_ledger = True
                    line = node.lineno
                    break
            elif isinstance(node, ast.Call):
                call_name = _call_name(node.func)
                if any(call_name.endswith(name) for name in _GUARDED_LEDGER_CALL_NAMES):
                    consumes_ledger = True
                    line = node.lineno
                    break
        else:
            line = 1

        if not consumes_ledger:
            continue

        if not gate_result.passed:
            findings.append(
                M5EvalGateFinding(
                    rel_path,
                    line,
                    "M5_EVAL_CALIBRATION_GUARD_GREP_GATE",
                    "guarded calibration/routing targets may consume Evaluand ledger APIs only after run_m5_eval_gates() passes",
                )
            )
        if marker is None or marker <= 0:
            findings.append(
                M5EvalGateFinding(
                    rel_path,
                    line,
                    "M5_EVAL_CALIBRATION_GUARD_REPLAY_MARKER",
                    "guarded calibration/routing targets require a non-empty replay oracle corpus marker",
                )
            )

    return tuple(findings)


def assert_m5_eval_gates_before_calibration(
    repo_root: Path | str = REPO_ROOT,
) -> None:
    findings = check_calibration_guard_targets(repo_root)
    if findings:
        raise AssertionError(format_findings(findings))


def run_m5_eval_gates(root: Path | str = REPO_ROOT) -> M5EvalGateResult:
    findings = (
        check_no_bare_float_judgments(root)
        + check_no_second_eval_journals(root)
        + check_better_join_is_pure(root)
        + check_calibration_source_purity(root)
    )
    return M5EvalGateResult(passed=not findings, findings=findings)


def format_findings(findings: Sequence[M5EvalGateFinding]) -> str:
    return "\n".join(
        f"{finding.path}:{finding.line}: {finding.code}: {finding.detail}"
        for finding in findings
    )


__all__ = [
    "M5EvalGateFinding",
    "M5EvalGateResult",
    "NEW_EVAL_MODULES",
    "OLD_PATH_ALLOWLIST",
    "GUARDED_CALIBRATION_TARGETS",
    "REPLAY_ORACLE_MARKER_NAME",
    "REPLAY_ORACLE_MARKER_PATH",
    "assert_m5_eval_gates_before_calibration",
    "check_better_join_is_pure",
    "check_calibration_guard_targets",
    "check_calibration_source_purity",
    "check_no_bare_float_judgments",
    "check_no_second_eval_journals",
    "format_findings",
    "replay_oracle_corpus_marker",
    "run_m5_eval_gates",
]
