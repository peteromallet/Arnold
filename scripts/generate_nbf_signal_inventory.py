#!/usr/bin/env python3
"""Generate/check the repository-wide NBF-05 signal inventory.

The Python half deliberately reuses the reviewed AST discovery in
``tests/arnold_pipelines/megaplan/test_python_signal_inventory.py`` so the
generated artifact and its focused regression test cannot silently develop
different notions of a signal site.  The shell half is intentionally narrow:
it scans executable shell files, systemd units, the cloud wrapper directory,
and shell files elsewhere in the live tree for command-level ``kill``/``pgrep``
and ``wait``/supervision forms, ignoring comments and prose.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/nbf-signal-inventory.json"
GENERATOR_VERSION = "nbf05-signal-inventory-v1"
SCHEMA_VERSION = "nbf-signal-inventory-v1"
DISCOVERY_RULES_VERSION = "nbf05-discovery-rules-v1"
SOURCE_DIGEST_VERSION = "nbf05-source-inputs-v2"
SKIP_PARTS = {
    ".git",
    ".oracle",
    ".megaplan",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "tests",
    "vendor",
    "generated",
}
PYTHON_ROOTS = ("arnold", "arnold_pipelines", "agentbox", "scripts", "tools")
SHELL_EXTENSIONS = {".sh", ".bash", ".service"}
SHELL_SIGNAL_RE = re.compile(
    r"(?:^|[;&|()]|\b(?:if|then|do|exec|env)\s+|\bxargs(?:\s+[-A-Za-z0-9_=]+)*\s+)"
    r"\s*(?:(?:sudo)\s+)?(kill|pkill|killall|start-stop-daemon)(?=\s|$)"
)
SHELL_CANONICAL_HELPER_RE = re.compile(
    r"(?:^|[;&|()]|\b(?:if|then|do)\s+)\s*"
    r"arnold_supervisor_signal_(?:non_worker_pid|bound_pid)\b"
)
TMUX_KILL_RE = re.compile(r"(?:^|[;&|()]|\b(?:if|then|do)\s+)\s*tmux(?:\s+-S\s+[^\s]+)?\s+kill-(?:session|server)\b")
PGREP_RE = re.compile(r"(?:^|[;&|()]|\b(?:if|then|do|command)\s+)\s*pgrep\b")
WAIT_RE = re.compile(r"(?:^|[;&|()]|\b(?:if|then|do)\s+)\s*wait(?:\s|$)")
FUNCTION_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(\)\s*\{")

DISCOVERY_RULES = {
    "python": "reviewed AST call discovery from test_python_signal_inventory.py",
    "shell": "command-level kill/pkill/killall/start-stop-daemon/tmux kill-session, pgrep, kill -0, and wait; comments/prose excluded",
    "shell_roots": ["arnold_pipelines/megaplan/cloud/wrappers", "arnold_pipelines/megaplan/cloud/systemd", "repository shell extensions"],
    "stable_key": "language + relative source path + function/branch + normalized expression + occurrence; line number is locator only",
    "source_inputs": "framed relative path and bytes digest over live Python/shell inputs; excludes this generated JSON, Git revision, and self-digest",
}


def _git(*args: str) -> bytes:
    env = os.environ.copy()
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"})
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
    return result.stdout


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _skipped(path: Path) -> bool:
    return bool(SKIP_PARTS.intersection(path.relative_to(ROOT).parts))


@lru_cache(maxsize=1)
def _load_python_discovery() -> Any:
    path = ROOT / "tests/arnold_pipelines/megaplan/test_python_signal_inventory.py"
    if not path.is_file():
        raise RuntimeError(f"reviewed Python discovery is missing: {path}")
    spec = importlib.util.spec_from_file_location("nbf04_python_signal_inventory", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load reviewed Python discovery")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _python_entries() -> list[dict[str, Any]]:
    discovery = _load_python_discovery()
    entries: list[dict[str, Any]] = []
    for site in discovery.discover_all_signal_sites():
        if not discovery._is_reviewed(site):
            raise RuntimeError(f"unclassified Python signal site: {site.key}")
        probe = site.action == "probe"
        worker_kill = not probe and site.target_class in {"worker", "canonical-disposition"}
        fan_lifecycle = site.target_class == "non-worker-lifecycle"
        entries.append(
            {
                "site_id": f"python:{site.key}",
                "source_file": site.path,
                "function_or_branch": site.branch_label,
                "source_locator": f"{site.path}:{site.lineno}",
                "signal_or_probe": f"{site.action}:{site.symbol}",
                "subject_class": site.target_class,
                "worker_kill": worker_kill,
                "killer_kind": None if probe else site.symbol,
                "context_resolver": (
                    "liveness-probe" if probe else "canonical-non-worker-disposition" if fan_lifecycle else site.target_class
                ),
                "two_scan_required": False,
                "two_scan_owner": None,
                "confirmation_policy_identity": None,
                "disposition_test_id": "test_python_signal_sites_are_live_and_classified",
                "failure_order_test_id": "test_record_failure_is_fail_closed",
                "exclusion_reason": (
                    "mechanical liveness probe; signal argument is zero"
                    if probe
                    else discovery.REVIEWED_CLASS_REASONS.get(site.target_class)
                ),
            }
        )
    return entries


def _shell_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or _skipped(path):
            continue
        rel = path.relative_to(ROOT)
        in_wrappers = "arnold_pipelines/megaplan/cloud/wrappers" in rel.as_posix()
        in_systemd = "arnold_pipelines/megaplan/cloud/systemd" in rel.as_posix()
        if path.suffix in SHELL_EXTENSIONS or (in_wrappers and not path.suffix) or (in_systemd and not path.suffix):
            files.append(path)
    return sorted(files, key=_relative)


def _shell_command(line: str) -> tuple[str, str] | None:
    code = line.split("#", 1)[0].rstrip()
    if not code.strip():
        return None
    if re.match(r"^\s*arnold_supervisor_signal_(?:non_worker_pid|bound_pid)\s*\(\)\s*\{", code):
        return None
    if re.search(r"\bkill\s+-0\b", code):
        return ("probe", "kill -0")
    if SHELL_CANONICAL_HELPER_RE.search(code):
        token = (
            "arnold_supervisor_signal_bound_pid"
            if "arnold_supervisor_signal_bound_pid" in code
            else "arnold_supervisor_signal_non_worker_pid"
        )
        return ("signal", token)
    match = SHELL_SIGNAL_RE.search(code) or TMUX_KILL_RE.search(code)
    if match:
        if "kill-session" in match.group(0):
            token = "tmux kill-session"
        elif "kill-server" in match.group(0):
            token = "tmux kill-server"
        else:
            token = match.group(1)
        return ("signal", token)
    if PGREP_RE.search(code):
        return ("probe", "pgrep")
    if WAIT_RE.search(code):
        return ("supervision", "wait")
    return None


def _shell_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    counts: dict[tuple[str, str, str], int] = {}
    for path in _shell_files():
        rel = _relative(path)
        function = "<module>"
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            found = _shell_command(line)
            function_match = FUNCTION_RE.match(line)
            if function_match:
                function = function_match.group(1)
            if found is None:
                continue
            action, token = found
            key = (rel, function, action, token)
            counts[key] = counts.get(key, 0) + 1
            occurrence = counts[key]
            probe = action == "probe"
            canonical_signal = action == "signal" and token in {
                "arnold_supervisor_signal_bound_pid",
                "arnold_supervisor_signal_non_worker_pid",
            }
            watchdog_tmux_cleanup = (
                action == "signal"
                and token == "tmux kill-session"
                and rel.endswith("arnold-watchdog")
            )
            if probe:
                subject = "liveness-probe"
                exclusion = "mechanical shell liveness probe; it cannot signal a worker"
            elif action == "supervision":
                subject = "process-supervision"
                exclusion = "wait-only supervision site; it does not issue a signal"
            elif canonical_signal:
                subject = "non-worker-lifecycle"
                exclusion = "canonical shell non-worker lifecycle disposition; worker identity is not fabricated"
            elif watchdog_tmux_cleanup:
                subject = "non-worker-lifecycle"
                exclusion = "direct watchdog tmux cleanup after canonical post-proof checks; not a managed worker disposition"
            elif rel.endswith("ensure-megaplan-watchdog") or rel.endswith("ensure-megaplan-resident"):
                subject = "non-worker-lifecycle"
                exclusion = "canonical ensure-service lifecycle cleanup after identity/post-proof checks, not a managed worker disposition"
            else:
                subject = "worker"
                exclusion = None
            lifecycle_cleanup = rel.endswith("ensure-megaplan-watchdog") or rel.endswith("ensure-megaplan-resident")
            two_scan = canonical_signal
            entries.append(
                {
                    "site_id": f"shell:{rel}|{function}|{action}:{token}|{occurrence}",
                    "source_file": rel,
                    "function_or_branch": function,
                    "source_locator": f"{rel}:{lineno}",
                    "signal_or_probe": f"{action}:{token}",
                    "subject_class": subject,
                    "worker_kill": action == "signal" and subject == "worker",
                    "killer_kind": None if probe or action == "supervision" else token,
                    "context_resolver": (
                        "canonical-non-worker-disposition" if canonical_signal
                        else "canonical-supervisor-post-proof-cleanup" if lifecycle_cleanup or watchdog_tmux_cleanup
                        else "arnold-watchdog" if "watchdog" in rel else subject
                    ),
                    "two_scan_required": two_scan,
                    "two_scan_owner": (
                        "arnold-supervisor-runtime-lib" if canonical_signal
                        else "arnold-watchdog" if two_scan else None
                    ),
                    "confirmation_policy_identity": (
                        "shell-nbf05-v1" if canonical_signal else None
                    ),
                    "disposition_test_id": "test_shell_signal_sites_are_classified",
                    "failure_order_test_id": "test_shell_inventory_exclusions_are_explicit",
                    "exclusion_reason": exclusion,
                }
            )
    return entries


PYTHON_SHELL_RE = re.compile(
    r"(?:tmux\s+kill-(?:session|server)|kill\s+-0|xargs[^\n]*\bkill\b|trap[^\n]*\bkill\b|"
    r"arnold_supervisor_signal_non_worker_pid)"
)

NON_EXECUTABLE_DICT_KEYS = frozenset(
    {
        "forbidden_shortcuts", "safety_guarantees", "requirements", "procedure",
        "operational_caveat", "transport_choice", "help", "description", "notes",
        "policy", "policies", "prompt", "prompts", "instructions",
    }
)


def _python_generated_shell_entries() -> list[dict[str, Any]]:
    """Find command strings/lists that generate a shell signal control.

    These are not duplicate AST signal calls: they are Python expressions
    whose child process receives a command such as ``tmux kill-session`` or a
    shell trap.  Only exact command-shaped strings and argv lists are kept;
    prose, identifiers, and generic ``terminate`` words are ignored.
    """
    entries: list[dict[str, Any]] = []
    for root_name in PYTHON_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if _skipped(path):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError):
                continue
            rel = _relative(path)
            if rel == "scripts/generate_nbf_signal_inventory.py":
                continue
            counts: dict[tuple[str, str], int] = {}
            functions: list[str] = []
            non_executable_nodes: set[ast.AST] = set()
            for parent in ast.walk(tree):
                if not isinstance(parent, ast.Dict):
                    continue
                for key, value in zip(parent.keys, parent.values):
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        if key.value.strip().lower() in NON_EXECUTABLE_DICT_KEYS:
                            non_executable_nodes.update(ast.walk(value))

            class Visitor(ast.NodeVisitor):
                def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                    functions.append(node.name)
                    self.generic_visit(node)
                    functions.pop()

                def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                    functions.append(node.name)
                    self.generic_visit(node)
                    functions.pop()

                def visit_Constant(self, node: ast.Constant) -> None:
                    if not isinstance(node.value, str):
                        return
                    if node in non_executable_nodes:
                        return
                    match = PYTHON_SHELL_RE.search(node.value)
                    if match:
                        add(node.lineno, match.group(0).strip())

                def visit_List(self, node: ast.List) -> None:
                    values = [item.value for item in node.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)]
                    if "tmux" in values and ("kill-session" in values or "kill-server" in values):
                        add(node.lineno, "tmux kill-session" if "kill-session" in values else "tmux kill-server")
                    self.generic_visit(node)

            def add(lineno: int, expression: str) -> None:
                function = "/".join(functions) if functions else "<module>"
                key = (function, expression)
                counts[key] = counts.get(key, 0) + 1
                occurrence = counts[key]
                entries.append(
                    {
                        "site_id": f"python-shell:{rel}|{function}|{expression}|{occurrence}",
                        "source_file": rel,
                        "function_or_branch": function,
                        "source_locator": f"{rel}:{lineno}",
                        "signal_or_probe": f"shell-generated:{expression}",
                        "subject_class": "non-worker-lifecycle",
                        "worker_kill": False,
                        "killer_kind": expression,
                        "context_resolver": "python-generated-shell",
                        "two_scan_required": False,
                        "two_scan_owner": None,
                        "confirmation_policy_identity": None,
                        "disposition_test_id": "test_python_generated_shell_controls_are_classified",
                        "failure_order_test_id": "test_shell_inventory_exclusions_are_explicit",
                        "exclusion_reason": "Python-generated shell lifecycle control is not a managed worker disposition",
                    }
                )

            Visitor().visit(tree)
    return entries


def _source_inputs(entries: list[dict[str, Any]], generated: Path) -> list[Path]:
    paths = {ROOT / str(entry["source_file"]) for entry in entries}
    paths.discard(generated.resolve())
    return sorted(paths, key=_relative)


def _source_digest(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    def frame(value: bytes) -> None:
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)

    frame(SOURCE_DIGEST_VERSION.encode("ascii"))
    frame(GENERATOR_VERSION.encode("ascii"))
    frame(DISCOVERY_RULES_VERSION.encode("ascii"))
    frame(json.dumps(DISCOVERY_RULES, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    for path in paths:
        rel = _relative(path).encode("utf-8")
        data = path.read_bytes()
        frame(rel)
        frame(hashlib.sha256(data).hexdigest().encode("ascii"))
    return digest.hexdigest()


def build_inventory(output: Path = OUTPUT) -> dict[str, Any]:
    entries = sorted(_python_entries() + _python_generated_shell_entries() + _shell_entries(), key=lambda item: item["site_id"])
    if any(not item.get("site_id") or not item.get("source_file") for item in entries):
        raise RuntimeError("unclassified inventory entry")
    source_files = _source_inputs(entries, output)
    artifact: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "discovery_rules_version": DISCOVERY_RULES_VERSION,
        "discovery_rules": DISCOVERY_RULES,
        "entries": entries,
        "source_inputs_sha256": _source_digest(source_files),
    }
    return artifact


def _render(artifact: dict[str, Any]) -> bytes:
    return (json.dumps(artifact, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    expected = _render(build_inventory(output))
    if args.check:
        if not output.is_file():
            print(f"missing inventory: {output}", file=sys.stderr)
            return 1
        actual = output.read_bytes()
        if actual != expected:
            print(f"stale inventory: {output}", file=sys.stderr)
            return 1
        print(f"fresh inventory: {output}")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(expected)
    print(f"generated inventory: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
