from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path

from arnold.pipelines.megaplan.model_seam import assert_all_compatibility_modes_native


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "tests/fixtures/model_dispatch_inventory.json"
_CLASSIFICATIONS = {
    "owned_dispatch",
    "dont_touch",
    "future_no_dispatch",
    "test_fake",
}
_SEAM_IMPORT_NAMES = {
    "render_step_message",
    "render_prompt_for_dispatch",
    "capture_step_output",
}
_APPROVED_SEAM_IMPORTS = {
    "arnold/pipelines/megaplan/_core/worker_fanout.py": {"render_step_message"},
    "arnold/pipelines/megaplan/execute/batch.py": {"render_step_message", "capture_step_output"},
    "arnold/pipelines/megaplan/execute/timeout.py": {"capture_step_output"},
    "arnold/pipelines/megaplan/orchestration/tiebreaker.py": {"render_prompt_for_dispatch"},
    "arnold/pipelines/megaplan/prompts/tiebreaker_orchestrator.py": {"render_prompt_for_dispatch"},
    "arnold/pipelines/megaplan/resident/runtime.py": {"render_step_message"},
    "arnold/pipelines/megaplan/workers/_impl.py": {"render_prompt_for_dispatch", "capture_step_output"},
    "arnold/pipelines/megaplan/workers/hermes.py": {"render_prompt_for_dispatch", "capture_step_output"},
    "arnold/pipelines/megaplan/workers/shannon.py": {
        "render_step_message",
        "render_prompt_for_dispatch",
        "capture_step_output",
    },
}

_PATTERNS = (
    re.compile(r"\bcreate_(?:claude|codex|hermes)_prompt\("),
    re.compile(r"\brun_conversation\("),
    re.compile(r"\brun_step_with_worker\("),
    re.compile(r"\b(?:self\.)?runner\.run\("),
    re.compile(r"\bset_response_format\("),
    re.compile(r"--output-schema"),
    re.compile(r"\bdef _recover_payload_with_provenance\("),
    re.compile(r"\b_recover_payload_with_provenance\("),
    re.compile(r"\bdef validate_payload\("),
    re.compile(r"\bvalidate_payload\("),
)


@dataclass(frozen=True)
class DispatchCandidate:
    path: str
    line: int
    snippet: str


def _load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _inventory_paths(fixture: dict[str, object]) -> set[str]:
    return {str(entry["path"]) for entry in fixture["inventory"]}


def _inventory_only_paths(fixture: dict[str, object]) -> set[str]:
    return set(fixture.get("inventory_only_files", []))


def _collect_candidates(root: Path, rel_paths: list[str]) -> list[DispatchCandidate]:
    candidates: list[DispatchCandidate] = []
    for rel_path in rel_paths:
        text = (root / rel_path).read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if any(pattern.search(stripped) for pattern in _PATTERNS):
                candidates.append(
                    DispatchCandidate(
                        path=rel_path,
                        line=line_no,
                        snippet=stripped,
                    )
                )
    return candidates


def _is_classified(candidate: DispatchCandidate, entries: list[dict[str, str]]) -> bool:
    for entry in entries:
        if entry["path"] != candidate.path:
            continue
        anchor = entry["anchor"]
        if anchor in candidate.snippet or candidate.snippet in anchor:
            return True
    return False


def _entry_text(entry: dict[str, object]) -> str:
    return (REPO_ROOT / str(entry["path"])).read_text(encoding="utf-8")


def _assert_entry_guards(entry: dict[str, object]) -> None:
    text = _entry_text(entry)
    for guard in entry.get("required_guards", []):
        assert guard in text, f"missing guard for {entry['path']}: {guard}"


def _collect_model_seam_imports(root: Path) -> dict[str, set[str]]:
    imports: dict[str, set[str]] = {}
    megaplan_root = root / "arnold/pipelines/megaplan"
    for path in megaplan_root.rglob("*.py"):
        rel_path = path.relative_to(root).as_posix()
        if "/agent/" in rel_path:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module != "arnold.pipelines.megaplan.model_seam":
                continue
            names = {alias.name for alias in node.names if alias.name in _SEAM_IMPORT_NAMES}
            if names:
                imports.setdefault(rel_path, set()).update(names)
    return imports


def _collect_model_seam_calls(root: Path, rel_path: str) -> set[str]:
    tree = ast.parse((root / rel_path).read_text(encoding="utf-8"))
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _SEAM_IMPORT_NAMES:
                calls.add(node.func.id)
    return calls


def test_model_dispatch_inventory_entries_exist() -> None:
    fixture = _load_fixture()
    entries = fixture["inventory"]
    assert isinstance(entries, list) and entries, "dispatch inventory fixture must stay populated"
    for entry in entries:
        path = REPO_ROOT / entry["path"]
        text = path.read_text(encoding="utf-8")
        assert entry["anchor"] in text, f"missing inventory anchor: {entry['path']} :: {entry['anchor']}"
        assert entry["classification"] in _CLASSIFICATIONS, f"unknown dispatch classification: {entry['classification']}"
        _assert_entry_guards(entry)


def test_dispatch_inventory_paths_are_explicitly_scanned_or_whitelisted() -> None:
    fixture = _load_fixture()
    scan_files = set(fixture["scan_files"])
    inventory_only = _inventory_only_paths(fixture)
    assert inventory_only <= _inventory_paths(fixture)
    assert _inventory_paths(fixture) <= scan_files | inventory_only


def test_structural_detector_requires_classification_for_scanned_candidates() -> None:
    fixture = _load_fixture()
    rel_paths = list(fixture["scan_files"])
    entries = list(fixture["inventory"])
    missing = [
        f"{candidate.path}:{candidate.line}: {candidate.snippet}"
        for candidate in _collect_candidates(REPO_ROOT, rel_paths)
        if not _is_classified(candidate, entries)
    ]
    assert missing == []


def test_structural_detector_fails_unclassified_owned_dispatch_candidate(tmp_path: Path) -> None:
    synthetic = tmp_path / "synthetic_dispatch.py"
    synthetic.write_text(
        "def drive(agent):\n"
        "    return agent.run_conversation('hello')\n",
        encoding="utf-8",
    )
    candidate = _collect_candidates(tmp_path, ["synthetic_dispatch.py"])
    assert candidate == [
        DispatchCandidate(
            path="synthetic_dispatch.py",
            line=2,
            snippet="return agent.run_conversation('hello')",
        )
    ]
    assert not _is_classified(candidate[0], [])


def test_execute_and_resident_dispatch_sites_require_render_or_model_metadata_guards() -> None:
    fixture = _load_fixture()
    guarded = [
        entry
        for entry in fixture["inventory"]
        if entry["classification"] == "owned_dispatch" and entry.get("required_guards")
    ]
    assert guarded, "expected explicit guarded dispatch inventory entries"
    for entry in guarded:
        _assert_entry_guards(entry)


def test_phase_5_requires_all_compatibility_modes_native_before_deletion() -> None:
    assert_all_compatibility_modes_native()


def test_only_approved_production_files_import_model_seam_dispatch_helpers() -> None:
    assert _collect_model_seam_imports(REPO_ROOT) == _APPROVED_SEAM_IMPORTS


def test_production_model_seam_dispatch_imports_are_exercised() -> None:
    for rel_path, expected_imports in _APPROVED_SEAM_IMPORTS.items():
        used = _collect_model_seam_calls(REPO_ROOT, rel_path)
        assert expected_imports <= used, (
            f"{rel_path} imports model_seam dispatch helpers that are not exercised:\n"
            f"  imported: {sorted(expected_imports)}\n"
            f"  used:     {sorted(used)}"
        )
