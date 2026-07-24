"""Deterministic default test-blast-radius selection helpers."""

from __future__ import annotations

import logging
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

log = logging.getLogger("arnold_pipelines.megaplan.test_selection")


def _normalize_relpath(path: str) -> str:
    return Path(path).as_posix().lstrip("./")


def _is_pytest_test_file(rel_path: str) -> bool:
    path = Path(rel_path)
    return path.suffix == ".py" and (
        path.name.startswith("test_") or path.name.endswith("_test.py")
    )


def _is_archived_or_hidden_test_path(rel_path: str) -> bool:
    path = Path(_normalize_relpath(rel_path))
    parts = path.parts
    return any(part.startswith(".") for part in parts) or "archive" in parts


# Prose-documentation files cannot change test outcomes, so a change confined to
# them must NOT force the full suite (that would run 5k tests for a README edit).
# Everything else non-Python (data, fixtures, golden files, config) CAN affect
# tests the import graph can't see, so it forces full — the fail-safe direction.
_DOCUMENTATION_EXTENSIONS = frozenset({".md", ".rst", ".adoc", ".markdown"})


def _is_documentation_path(rel_path: str) -> bool:
    path = Path(rel_path)
    if path.suffix.lower() in _DOCUMENTATION_EXTENSIONS:
        return True
    parts = path.parts
    return bool(parts) and parts[0] in {"docs", "doc"}


def _only_documentation_paths(paths: Iterable[str]) -> bool:
    normalized = [
        _normalize_relpath(path)
        for path in paths
        if isinstance(path, str) and path.strip()
    ]
    return bool(normalized) and all(_is_documentation_path(path) for path in normalized)


def _existing_file(repo_root: Path, rel_path: str) -> bool:
    candidate = repo_root / rel_path
    return candidate.is_file()


def _existing_pytest_selector_path(repo_root: Path, rel_path: str) -> bool:
    selector_path = rel_path.split("::", 1)[0].strip()
    if not selector_path:
        return False
    if _is_archived_or_hidden_test_path(selector_path):
        return False
    candidate = repo_root / selector_path
    return candidate.is_file() or candidate.is_dir()


def _direct_selector_candidates(rel_path: str) -> list[str]:
    path = Path(rel_path)
    rel_dir = path.parent.as_posix()
    stem = path.stem
    candidates: list[str] = []

    if rel_dir == ".":
        rel_dir = ""

    def add(candidate: str) -> None:
        if candidate not in candidates:
            candidates.append(candidate)

    if rel_dir:
        add(f"tests/{rel_dir}/test_{stem}.py")
        add(f"tests/{rel_dir}/{stem}_test.py")
    else:
        add(f"tests/test_{stem}.py")
        add(f"tests/{stem}_test.py")

    add(f"tests/test_{stem}.py")
    add(f"tests/{stem}_test.py")

    if rel_dir:
        add(f"{rel_dir}/test_{stem}.py")
        add(f"{rel_dir}/{stem}_test.py")
    else:
        add(f"test_{stem}.py")
        add(f"{stem}_test.py")

    return candidates


def _bounded_selector_candidates(repo_root: Path, stem: str) -> list[str]:
    tests_dir = repo_root / "tests"
    if not tests_dir.is_dir():
        return []

    matches: list[str] = []
    for path in sorted(tests_dir.rglob("*.py")):
        if path.name.startswith(".") or any(part.startswith(".") for part in path.relative_to(repo_root).parts):
            continue
        name = path.name
        if name == f"test_{stem}.py" or (
            name.endswith("_test.py") and stem in name[: -len("_test.py")]
        ):
            rel_path = path.relative_to(repo_root).as_posix()
            if _is_archived_or_hidden_test_path(rel_path):
                continue
            if rel_path not in matches:
                matches.append(rel_path)
    return matches


def _looks_like_repo_path(value: str) -> bool:
    path = value.split("::", 1)[0].strip()
    if not path or path.startswith("-") or Path(path).is_absolute():
        return False
    if path == "tests" or path.startswith("tests/"):
        return True
    return Path(path).suffix == ".py"


def _always_run_path_args(value: str) -> list[str]:
    import shlex

    stripped = value.strip()
    if not stripped:
        return []

    try:
        parts = shlex.split(stripped)
    except ValueError:
        return []

    if not parts:
        return []

    if len(parts) == 1:
        normalized = _normalize_relpath(parts[0])
        return [normalized] if _looks_like_repo_path(normalized) else []

    pytest_index: int | None = None
    for idx, part in enumerate(parts):
        if part == "pytest" or part.endswith("/pytest"):
            pytest_index = idx
            break
    if pytest_index is None:
        return []

    paths: list[str] = []
    for part in parts[pytest_index + 1 :]:
        normalized = _normalize_relpath(part)
        if _looks_like_repo_path(normalized):
            paths.append(normalized)
    return paths


def _sanitize_blast_radius_paths(
    radius: dict[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    """Keep only existing pytest path selectors in plan-time baseline metadata."""

    sanitized = dict(radius)
    missing: list[str] = []

    selectors = radius.get("selectors")
    if isinstance(selectors, list):
        kept_selectors: list[dict[str, Any]] = []
        for selector in selectors:
            if not isinstance(selector, dict):
                continue
            if selector.get("kind") != "path":
                kept_selectors.append(dict(selector))
                continue
            value = selector.get("value")
            if not isinstance(value, str) or not value.strip():
                continue
            normalized = _normalize_relpath(value.strip())
            if _existing_pytest_selector_path(repo_root, normalized):
                kept = dict(selector)
                kept["value"] = normalized
                kept_selectors.append(kept)
            else:
                missing.append(normalized)
        sanitized["selectors"] = kept_selectors

    always_run = radius.get("always_run")
    if isinstance(always_run, list):
        kept_commands: list[str] = []
        for command in always_run:
            if not isinstance(command, str) or not command.strip():
                continue
            paths = _always_run_path_args(command)
            missing_for_command = [
                path
                for path in paths
                if not _existing_pytest_selector_path(repo_root, path)
            ]
            if missing_for_command:
                missing.extend(missing_for_command)
                continue
            kept_commands.append(command.strip())
        sanitized["always_run"] = kept_commands

    if missing:
        existing_missing = sanitized.get("missing_test_selectors")
        all_missing: list[str] = []
        seen: set[str] = set()
        for value in [
            *(existing_missing if isinstance(existing_missing, list) else []),
            *missing,
        ]:
            if isinstance(value, str) and value not in seen:
                seen.add(value)
                all_missing.append(value)
        sanitized["missing_test_selectors"] = all_missing
        rationale = str(sanitized.get("rationale") or "").strip()
        suffix = (
            " Dropped nonexistent pytest path(s) from plan-time baseline metadata: "
            + ", ".join(all_missing)
            + "."
        )
        sanitized["rationale"] = (rationale + suffix).strip()
    return sanitized


sanitize_blast_radius_paths = _sanitize_blast_radius_paths


def compute_default_blast_radius(
    changed_files: Iterable[str],
    repo_root: Path,
) -> dict[str, Any]:
    """Compute the deterministic M1 default test blast radius."""

    normalized = sorted({_normalize_relpath(path) for path in changed_files if path})
    changed_test_files = [
        rel_path
        for rel_path in normalized
        if _is_pytest_test_file(rel_path) and not _is_archived_or_hidden_test_path(rel_path)
    ]
    missing_test_files = [
        rel_path for rel_path in changed_test_files if not _existing_file(repo_root, rel_path)
    ]
    changed_test_files = [
        rel_path for rel_path in changed_test_files if _existing_file(repo_root, rel_path)
    ]
    changed_python_surfaces = [
        rel_path
        for rel_path in normalized
        if rel_path.endswith(".py") and not _is_pytest_test_file(rel_path)
    ]
    non_python_changes = [
        rel_path for rel_path in normalized if not rel_path.endswith(".py")
    ]
    # Data/fixture/golden/config changes force the full suite; prose docs do not.
    non_python_data = [
        rel_path for rel_path in non_python_changes if not _is_documentation_path(rel_path)
    ]
    non_python_docs = [
        rel_path for rel_path in non_python_changes if _is_documentation_path(rel_path)
    ]

    selectors: list[dict[str, str]] = []
    seen_selector_values: set[str] = set()

    def add_selector(value: str, reason: str) -> None:
        if value in seen_selector_values:
            return
        selectors.append({"kind": "path", "value": value, "reason": reason})
        seen_selector_values.add(value)

    for rel_path in changed_test_files:
        add_selector(rel_path, "changed test file")

    uncovered: list[str] = []
    used_bounded_search = False
    name_covered_surfaces: set[str] = set()

    for rel_path in changed_python_surfaces:
        direct_matches = [
            candidate
            for candidate in _direct_selector_candidates(rel_path)
            if _existing_file(repo_root, candidate)
        ]
        if direct_matches:
            name_covered_surfaces.add(rel_path)
            for match in direct_matches:
                add_selector(match, f"deterministic mirror for {rel_path}")
            continue

        bounded_matches = _bounded_selector_candidates(repo_root, Path(rel_path).stem)
        if bounded_matches:
            used_bounded_search = True
            name_covered_surfaces.add(rel_path)
            for match in bounded_matches:
                add_selector(match, f"bounded basename match for {rel_path}")
            continue

    import_graph_degraded = False
    import_graph_dependent_tests: set[str] = set()
    import_graph_covered_surfaces: set[str] = set()
    import_graph_unresolved: set[str] = set()

    if changed_python_surfaces:
        try:
            from arnold_pipelines.megaplan.orchestration.import_graph import ImportGraph

            graph = ImportGraph.build(repo_root)
            for rel_path in changed_python_surfaces:
                resolution = graph.tests_importing(
                    [rel_path],
                    is_test_file=_is_pytest_test_file,
                )
                import_graph_degraded = import_graph_degraded or resolution.degraded
                import_graph_unresolved.update(resolution.unresolved)
                if resolution.test_files:
                    import_graph_covered_surfaces.add(rel_path)
                for test_file in resolution.test_files:
                    import_graph_dependent_tests.add(test_file)
                    add_selector(
                        test_file,
                        "import-graph dependent of changed surface",
                    )
        except Exception:
            import_graph_degraded = False
            import_graph_dependent_tests = set()
            import_graph_covered_surfaces = set()
            import_graph_unresolved = set()

    for rel_path in changed_python_surfaces:
        if rel_path in name_covered_surfaces:
            continue
        if rel_path in import_graph_covered_surfaces:
            continue
        uncovered.append(rel_path)

    has_scoped_selectors = bool(selectors)
    if has_scoped_selectors:
        strategy = "scoped"
        confidence = "low" if missing_test_files or non_python_data or uncovered else (
            "medium" if used_bounded_search or import_graph_degraded else "high"
        )
    elif missing_test_files or non_python_data or uncovered:
        strategy = "full"
        confidence = "low"
    elif not changed_test_files and not changed_python_surfaces:
        strategy = "none"
        confidence = "medium"
    else:
        strategy = "scoped"
        confidence = (
            "medium" if used_bounded_search or import_graph_degraded else "high"
        )

    rationale_parts: list[str] = []
    if changed_test_files:
        rationale_parts.append(
            f"Included {len(changed_test_files)} changed pytest file(s) directly."
        )
    if missing_test_files:
        rationale_parts.append(
            "Declared pytest selector path(s) do not exist, so the default stays on the full-suite path: "
            + ", ".join(missing_test_files)
            + "."
        )
    if changed_python_surfaces:
        rationale_parts.append(
            f"Tracked {len(changed_python_surfaces)} changed non-test Python surface(s)."
        )
    if used_bounded_search:
        rationale_parts.append(
            "Used bounded basename search under tests/ for at least one changed surface."
        )
    if import_graph_dependent_tests:
        rationale_parts.append(
            f"Added {len(import_graph_dependent_tests)} import-graph dependent test selector(s)."
        )
    if uncovered:
        rationale_parts.append(
            "Some changed Python surfaces have no deterministic selector, so the default stays on the full-suite path."
        )
    if non_python_data:
        rationale_parts.append(
            "Non-Python data/fixture/golden changes force the full suite because they can affect tests outside the Python import graph: "
            + ", ".join(non_python_data)
            + "."
        )
    if non_python_docs:
        rationale_parts.append(
            "Ignored documentation-only change(s) for selector derivation: "
            + ", ".join(non_python_docs)
            + "."
        )
    if not rationale_parts:
        rationale_parts.append("No Python changes were detected for M1 selector derivation.")

    result: dict[str, Any] = {
        "strategy": strategy,
        "confidence": confidence,
        "selectors": selectors,
        "changed_surfaces": changed_python_surfaces,
        "always_run": [],
        "full_suite_fallback": True,
        "rationale": " ".join(rationale_parts),
        "import_graph": {
            "degraded": import_graph_degraded,
            "dependent_tests": len(import_graph_dependent_tests),
            "unresolved": sorted(import_graph_unresolved),
        },
    }
    if uncovered:
        result["uncovered_changes_justification"] = ", ".join(uncovered)
    if missing_test_files:
        result["missing_test_selectors"] = missing_test_files
    return result


compute_test_blast_radius = compute_default_blast_radius


def _scoped_command_for_paths(paths: list[str]) -> str:
    """Build a scoped baseline command for a homogeneous selector set.

    ``node --test`` suites are path-oriented too, but forcing them through
    pytest turns a valid JS baseline into a guaranteed collection error.
    """
    normalized = [path.strip() for path in paths if isinstance(path, str) and path.strip()]
    if normalized and all(path.endswith((".mjs", ".cjs", ".js")) for path in normalized):
        return "node --test " + " ".join(shlex.quote(path) for path in normalized)
    return "pytest " + " ".join(shlex.quote(path) for path in normalized)


def merge_blast_radius_floor(
    floor: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Merge a model-proposed blast radius with a deterministic minimum floor.

    The deterministic radius is a hard floor: callers may widen with extra
    selectors or a broader strategy, but they may not remove floor selectors or
    narrow a full/scoped floor. Malformed fields are treated as missing so this
    helper remains deterministic and non-raising for handler use.
    """
    if not isinstance(floor, dict):
        floor = None
    if not isinstance(candidate, dict):
        candidate = None
    if floor is None:
        return candidate
    if candidate is None:
        return floor

    def selector_key(selector: Any) -> tuple[str, str] | None:
        if not isinstance(selector, dict):
            return None
        kind = selector.get("kind")
        value = selector.get("value")
        if not isinstance(kind, str) or not kind.strip():
            return None
        if not isinstance(value, str) or not value.strip():
            return None
        return kind.strip(), value.strip()

    def selector_items(radius: dict[str, Any]) -> list[dict[str, Any]]:
        selectors = radius.get("selectors")
        if not isinstance(selectors, list):
            return []
        items: list[dict[str, Any]] = []
        for selector in selectors:
            if selector_key(selector) is None:
                continue
            items.append(dict(selector))
        return items

    def merge_selectors() -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for selector in [*selector_items(floor), *selector_items(candidate)]:
            key = selector_key(selector)
            if key is None or key in seen:
                continue
            seen.add(key)
            merged.append(selector)
        return merged

    def list_strings(radius: dict[str, Any], key: str) -> list[str]:
        values = radius.get(key)
        if not isinstance(values, list):
            return []
        return [
            value.strip()
            for value in values
            if isinstance(value, str) and value.strip()
        ]

    def union_strings(key: str) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for value in [*list_strings(floor, key), *list_strings(candidate, key)]:
            if value in seen:
                continue
            seen.add(value)
            merged.append(value)
        return merged

    def merged_strategy() -> str:
        floor_strategy = floor.get("strategy")
        candidate_strategy = candidate.get("strategy")

        # An explicit scoped baseline with concrete selectors and full-suite
        # fallback should remain scoped even when the deterministic floor
        # escalates to full (e.g. because of non-Python data). The fallback
        # preserves the full-suite hard gate; the baseline gives finalize a
        # trusted scoped command.
        # Only keep the candidate's scoped baseline if it explicitly asks for
        # the full suite as a fallback; otherwise the full floor wins.
        if (
            floor_strategy == "full"
            and candidate_strategy == "scoped"
            and selector_items(candidate)
            and candidate.get("full_suite_fallback") is True
        ):
            return "scoped"

        if "full" in {floor_strategy, candidate_strategy}:
            return "full"
        if "scoped" in {floor_strategy, candidate_strategy}:
            return "scoped"
        return "none"

    def merged_confidence() -> str:
        rank = {"low": 0, "medium": 1, "high": 2}
        values = [
            value
            for value in (floor.get("confidence"), candidate.get("confidence"))
            if isinstance(value, str) and value in rank
        ]
        if not values:
            return "low"
        return min(values, key=lambda value: rank[value])

    def fallback_value(radius: dict[str, Any]) -> bool:
        value = radius.get("full_suite_fallback", True)
        return value if isinstance(value, bool) else True

    selectors = merge_selectors()
    candidate_selector_keys = {
        key
        for key in (selector_key(selector) for selector in selector_items(candidate))
        if key is not None
    }
    merged_selector_keys = {
        key
        for key in (selector_key(selector) for selector in selectors)
        if key is not None
    }

    candidate_rationale = candidate.get("rationale")
    candidate_rationale_text = (
        candidate_rationale.strip()
        if isinstance(candidate_rationale, str) and candidate_rationale.strip()
        else ""
    )
    rationale_parts: list[str] = []
    if candidate_rationale_text.startswith("Floor:"):
        rationale_parts.append(candidate_rationale_text)
    else:
        floor_rationale = floor.get("rationale")
        if isinstance(floor_rationale, str) and floor_rationale.strip():
            rationale_parts.append(f"Floor: {floor_rationale.strip()}")
        if candidate_rationale_text:
            rationale_parts.append(f"Candidate: {candidate_rationale_text}")
    if len(merged_selector_keys) > len(candidate_selector_keys):
        rationale_parts.append(
            "Floor widened the candidate by preserving deterministic selector(s)."
        )
    if not rationale_parts:
        rationale_parts.append("Merged deterministic floor with candidate blast radius.")

    result: dict[str, Any] = {
        "strategy": merged_strategy(),
        "confidence": merged_confidence(),
        "selectors": selectors,
        "changed_surfaces": union_strings("changed_surfaces"),
        "always_run": union_strings("always_run"),
        "full_suite_fallback": fallback_value(floor) or fallback_value(candidate),
        "rationale": " ".join(rationale_parts),
    }
    if "import_graph" in floor:
        result["import_graph"] = floor["import_graph"]
    return result


# ---------------------------------------------------------------------------
# M2 — Shared metadata helpers for reading plan_v{N}.meta.json
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanBlastRadius:
    """The ``test_blast_radius`` extracted from a plan's metadata file.

    When *plan_meta* could not be read or did not contain a valid
    ``test_blast_radius``, ``value`` is ``None`` and callers must treat
    the blast radius as absent (full-suite fallback).
    """

    value: dict[str, Any] | None
    """The raw ``test_blast_radius`` dict from ``plan_v{N}.meta.json``, or
    ``None`` when missing / unreadable / malformed."""

    meta_path: Path | None = None
    """Absolute path to the ``plan_v{N}.meta.json`` that was read, if any."""

    @property
    def is_present(self) -> bool:
        return self.value is not None


@dataclass(frozen=True)
class PlanChangedFiles:
    """Trustworthy per-plan changed-file provenance.

    Missing, ambiguous, or untrusted data is represented as *uncertain*, so
    downstream ladders can fall back to the full suite.

    .. code-block::

        provenance = resolve_changed_file_provenance(plan_dir, state)
        if provenance.uncertain:
            # Fall back to full suite — we do not trust the file list.
    """

    files: list[str]
    """The per-plan changed-file list when provenance is trustworthy;
    empty otherwise."""

    uncertain: bool = False
    """``True`` when the source of the file list cannot be trusted."""

    source: str = ""
    """Human-readable description of where the file list came from, for
    observability/debug logs."""


def read_plan_blast_radius(
    plan_dir: Path,
    state: dict[str, Any],
) -> PlanBlastRadius:
    """Read ``test_blast_radius`` from the latest ``plan_v{N}.meta.json``.

    Uses the established ``latest_plan_meta_path`` accessor so the
    metadata is read from the file written by the plan handler — **not**
    from ``state['meta']``.  If the file cannot be read or the field is
    missing / malformed, the returned object carries ``value=None``.
    """
    from arnold_pipelines.megaplan._core import latest_plan_meta_path, read_json

    try:
        meta_path = latest_plan_meta_path(plan_dir, state)
    except Exception:
        log.debug("Cannot resolve latest plan meta path; blast radius unavailable.")
        return PlanBlastRadius(value=None, meta_path=None)

    try:
        meta = read_json(meta_path)
    except Exception:
        log.debug("Cannot read plan meta %s; blast radius unavailable.", meta_path)
        return PlanBlastRadius(value=None, meta_path=None)

    if not isinstance(meta, dict):
        log.debug("Plan meta %s is not a JSON object; blast radius unavailable.", meta_path)
        return PlanBlastRadius(value=None, meta_path=None)

    blast_radius = meta.get("test_blast_radius")
    if not isinstance(blast_radius, dict):
        log.debug("Plan meta %s has no valid test_blast_radius.", meta_path)
        return PlanBlastRadius(value=None, meta_path=meta_path)

    return PlanBlastRadius(value=blast_radius, meta_path=meta_path)


def resolve_changed_file_provenance(
    plan_dir: Path,
    state: dict[str, Any],
) -> PlanChangedFiles:
    """Return a trustworthy per-plan changed-file list, or an uncertain representation.

    The **only** trustworthy source is the ``changed_surfaces`` list inside
    ``test_blast_radius`` in ``plan_v{N}.meta.json`` — that was recorded at
    plan time before any execution mutated the working tree.  Post-execute
    diffs, raw ``state['meta']`` entries, and ad-hoc ``git diff`` scans are
    explicitly excluded.

    When the metadata file is missing, the blast radius is absent, or the
    ``changed_surfaces`` list is missing / non-list, the returned object has
    ``uncertain=True`` so downstream callers fall back to the full suite.
    """
    blast_radius = read_plan_blast_radius(plan_dir, state)

    if not blast_radius.is_present:
        return PlanChangedFiles(
            files=[],
            uncertain=True,
            source="no plan blast radius available",
        )

    changed_surfaces = blast_radius.value.get("changed_surfaces")  # type: ignore[union-attr]
    if not isinstance(changed_surfaces, list):
        return PlanChangedFiles(
            files=[],
            uncertain=True,
            source=(
                f"plan blast radius present at {blast_radius.meta_path} "
                "but changed_surfaces is missing or not a list"
            ),
        )

    # Validate that every entry is a non-empty string.
    clean: list[str] = []
    for item in changed_surfaces:
        if isinstance(item, str) and item.strip():
            clean.append(item.strip())
        else:
            return PlanChangedFiles(
                files=[],
                uncertain=True,
                source=(
                    f"plan blast radius changed_surfaces at {blast_radius.meta_path} "
                    f"contains a non-string or empty entry: {item!r}"
                ),
            )

    return PlanChangedFiles(
        files=clean,
        uncertain=False,
        source=f"plan_v*.meta.json test_blast_radius.changed_surfaces ({blast_radius.meta_path})",
    )


# ---------------------------------------------------------------------------
# M2 — Baseline test-selection resolution (used by _write_finalize_artifacts)
# ---------------------------------------------------------------------------


def resolve_baseline_test_selection(
    plan_dir: Path,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Decide whether the baseline capture should use a scoped or full command.

    Returns a dict with:

    * ``mode``: ``"scoped"``, ``"full"``, ``"none"``, or ``"unresolved"``
    * ``reason``: human-readable explanation
    * ``command_override``: scoped pytest command string when *mode* is
      ``"scoped"``, otherwise ``None``
    * ``selectors_used``: the raw selector list from the blast radius
      (present only when *mode* is ``"scoped"``)

    Callers (``_write_finalize_artifacts``) use *command_override* to set
    ``config["test_command"]`` before calling ``_capture_test_baseline``,
    and record *mode* / *reason* in the payload for observability.
    """
    import shlex

    config = state.get("config", {}) if isinstance(state, dict) else {}

    # 1. Default-ON: scoped selection runs for EVERY plan unless it explicitly
    #    opts out with test_selection="full". Missing or invalid scoped metadata
    #    is unresolved, not an implicit full-suite request; callers must either
    #    recover a scoped command from another trusted pre-execute source or fail
    #    before invoking the suite runner.
    test_selection = config.get("test_selection", "scoped")
    if test_selection == "full":
        return {
            "mode": "full",
            "reason": (
                "test_selection config is 'full' (explicit opt-out of scoped selection)"
            ),
            "command_override": None,
        }

    # 2. Read blast radius from plan metadata.
    blast_radius = read_plan_blast_radius(plan_dir, state)
    if not blast_radius.is_present:
        return {
            "mode": "unresolved",
            "reason": "No test_blast_radius in plan metadata; scoped baseline selection is unresolved",
            "command_override": None,
        }

    value = blast_radius.value
    if not isinstance(value, dict):
        return {
            "mode": "unresolved",
            "reason": "test_blast_radius is not a dict; scoped baseline selection is unresolved",
            "command_override": None,
        }

    strategy = value.get("strategy")
    selectors = value.get("selectors")

    # 3. Only "scoped" strategy with non-empty selectors produces a scoped
    # command. Explicit "none" is a valid no-baseline declaration for plans
    # with no test-relevant surfaces.
    if strategy == "none":
        return {
            "mode": "none",
            "reason": "test_blast_radius strategy is 'none'; no baseline tests apply",
            "command_override": None,
            "selectors_used": [],
        }
    if strategy != "scoped":
        return {
            "mode": "unresolved",
            "reason": (
                f"test_blast_radius strategy is {strategy!r} "
                "(not 'scoped'); scoped baseline selection is unresolved"
            ),
            "command_override": None,
        }

    if not isinstance(selectors, list) or not selectors:
        changed_surfaces = value.get("changed_surfaces")
        missing_selectors = value.get("missing_test_selectors")
        docs_only_changed = (
            isinstance(changed_surfaces, list)
            and _only_documentation_paths(changed_surfaces)
        )
        docs_only_missing = (
            isinstance(missing_selectors, list)
            and _only_documentation_paths(missing_selectors)
        )
        if docs_only_changed and (not missing_selectors or docs_only_missing):
            return {
                "mode": "none",
                "reason": (
                    "test_blast_radius is scoped but contains only documentation "
                    "surfaces; no pytest baseline applies"
                ),
                "command_override": None,
                "selectors_used": [],
                "changed_surfaces": list(changed_surfaces),
            }
        return {
            "mode": "unresolved",
            "reason": (
                "test_blast_radius strategy is 'scoped' but selectors are "
                "missing or empty; scoped baseline selection is unresolved"
            ),
            "command_override": None,
        }

    non_path_kinds = sorted(
        {
            str(sel.get("kind"))
            for sel in selectors
            if isinstance(sel, dict) and sel.get("kind") != "path"
        }
    )

    # 4. Build scoped pytest command from path selectors.
    path_values: list[str] = []
    for sel in selectors:
        if isinstance(sel, dict) and sel.get("kind") == "path":
            v = sel.get("value")
            if isinstance(v, str) and v.strip():
                path_values.append(v.strip())

    if not path_values:
        return {
            "mode": "unresolved",
            "reason": (
                "test_blast_radius includes non-path selector kind(s) "
                + ", ".join(non_path_kinds)
                + " and no path selectors; scoped baseline selection is unresolved "
                "because pytest paths cannot faithfully express the model's wider intent"
                if non_path_kinds
                else (
                    "test_blast_radius strategy is 'scoped' but no path selectors "
                    "with non-empty values; scoped baseline selection is unresolved"
                )
            ),
            "command_override": None,
        }

    repo_root = Path(config.get("project_dir") or plan_dir.parent.parent.parent)
    missing_paths = [
        path
        for path in path_values
        if not _existing_pytest_selector_path(repo_root, path)
    ]
    if missing_paths:
        return {
            "mode": "unresolved",
            "reason": (
                "test_blast_radius scoped path selector(s) do not exist: "
                + ", ".join(missing_paths)
            ),
            "command_override": None,
        }

    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique_paths: list[str] = []
    for p in path_values:
        if p not in seen:
            seen.add(p)
            unique_paths.append(p)

    always_run_paths: list[str] = []
    always_run = value.get("always_run")
    if isinstance(always_run, list):
        for item in always_run:
            if not isinstance(item, str) or not item.strip():
                continue
            for path in _always_run_path_args(item):
                if path not in seen:
                    seen.add(path)
                    unique_paths.append(path)
                    always_run_paths.append(path)

    missing_always_run_paths = [
        path
        for path in always_run_paths
        if not _existing_pytest_selector_path(repo_root, path)
    ]
    if missing_always_run_paths:
        return {
            "mode": "unresolved",
            "reason": (
                "test_blast_radius always_run pytest path(s) do not exist: "
                + ", ".join(missing_always_run_paths)
            ),
            "command_override": None,
        }

    scoped_command = _scoped_command_for_paths(unique_paths)
    reason = f"Scoped to {len(unique_paths)} path selector(s) from plan metadata"
    if always_run_paths:
        reason += f"; folded in {len(always_run_paths)} always_run path(s)"
    if non_path_kinds:
        reason += (
            "; ignored non-path selector kind(s) "
            + ", ".join(non_path_kinds)
            + " for baseline capture"
        )
    return {
        "mode": "scoped",
        "reason": reason,
        "command_override": scoped_command,
        "selectors_used": list(selectors),
    }
