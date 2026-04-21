"""Smoke tests for handle_init's doc-mode arg validation (--mode/--output)."""
from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path

import pytest

import megaplan
import megaplan._core
import megaplan._core.io as io_module
import megaplan.cli
from megaplan.types import CliError


def _bootstrap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    def _config_dir(home: Path | None = None) -> Path:
        del home
        return config_path

    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    monkeypatch.setattr(io_module, "config_dir", _config_dir)
    monkeypatch.setattr(megaplan.cli, "config_dir", _config_dir)
    return root, project_dir


def _args(project_dir: Path, **overrides: object) -> Namespace:
    data: dict[str, object] = {
        "plan": None,
        "idea": "doc-mode test",
        "name": None,
        "project_dir": str(project_dir),
        "auto_approve": None,
        "robustness": "standard",
        "agent": None,
        "mode": "code",
        "output": None,
        "from_doc": None,
        "hermes": None,
    }
    data.update(overrides)
    return Namespace(**data)


def _load_state(root: Path, plan_name: str) -> dict:
    plan_dir = megaplan.plans_root(root) / plan_name
    return json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))


def test_doc_mode_requires_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    with pytest.raises(CliError) as info:
        megaplan.handle_init(root, _args(project_dir, mode="doc", output=None))
    assert info.value.code == "invalid_args"
    assert "--output" in str(info.value)


def test_output_rejects_absolute_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    with pytest.raises(CliError) as info:
        megaplan.handle_init(
            root,
            _args(project_dir, mode="doc", output="/etc/passwd"),
        )
    assert info.value.code == "invalid_args"
    assert "relative" in str(info.value).lower() or "absolute" in str(info.value).lower()


def test_output_rejects_parent_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    with pytest.raises(CliError) as info:
        megaplan.handle_init(
            root,
            _args(project_dir, mode="doc", output="../escape.md"),
        )
    assert info.value.code == "invalid_args"
    assert ".." in str(info.value)


def test_doc_mode_accepts_relative_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    response = megaplan.handle_init(
        root,
        _args(project_dir, name="doc-plan", mode="doc", output="docs/result.md"),
    )
    state = _load_state(root, response["plan"])
    assert state["config"]["mode"] == "doc"
    assert state["config"]["output_path"] == "docs/result.md"


def test_code_mode_without_output_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Code mode without --output is the common case and must keep working."""
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    response = megaplan.handle_init(
        root,
        _args(project_dir, name="code-plan", mode="code", output=None),
    )
    state = _load_state(root, response["plan"])
    assert state["config"]["mode"] == "code"
    assert "output_path" not in state["config"]


def test_code_mode_with_output_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--output is meaningless in code mode; accepting it silently has
    historically masked dropped --mode doc flags. Reject it loudly."""
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    with pytest.raises(CliError) as info:
        megaplan.handle_init(
            root,
            _args(project_dir, mode="code", output="docs/foo.md"),
        )
    assert info.value.code == "invalid_args"
    assert "--output" in str(info.value)
    assert "--mode doc" in str(info.value)


def test_metaplan_mode_is_alias_for_doc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--mode metaplan is a user-facing alias for --mode doc; state should
    record 'doc' so all downstream `mode == 'doc'` checks keep working."""
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    response = megaplan.handle_init(
        root,
        _args(project_dir, name="metaplan-alias", mode="metaplan", output="docs/design.md"),
    )
    state = _load_state(root, response["plan"])
    assert state["config"]["mode"] == "doc"
    assert state["config"]["output_path"] == "docs/design.md"


def test_from_doc_valid_path_populates_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    prior_doc = project_dir / "docs" / "prior.md"
    prior_doc.parent.mkdir(parents=True, exist_ok=True)
    prior_doc.write_text(
        """# Prior Doc

## Settled Decisions
- id: SD-001
  load_bearing: true
  decision: Keep the current data model
  rationale: External integrations depend on it.
- id: SD-002
  load_bearing: true
  decision: Preserve the CLI entrypoint names
  rationale: Existing automation depends on them.
- id: SD-003
  load_bearing: false
  decision: Keep the current docs directory layout
  rationale: Reviewers recognize it.
""",
        encoding="utf-8",
    )

    response = megaplan.handle_init(
        root,
        _args(
            project_dir,
            name="doc-with-import",
            mode="doc",
            output="docs/new-plan.md",
            from_doc="docs/prior.md",
        ),
    )

    state = _load_state(root, response["plan"])
    assert state["config"]["from_doc"] == "docs/prior.md"
    assert state["meta"]["imported_decisions"] == [
        {
            "id": "SD-001",
            "load_bearing": True,
            "decision": "Keep the current data model",
            "rationale": "External integrations depend on it.",
        },
        {
            "id": "SD-002",
            "load_bearing": True,
            "decision": "Preserve the CLI entrypoint names",
            "rationale": "Existing automation depends on them.",
        },
        {
            "id": "SD-003",
            "load_bearing": False,
            "decision": "Keep the current docs directory layout",
            "rationale": "Reviewers recognize it.",
        },
    ]
    assert "warnings" not in response


def test_from_doc_nonexistent_path_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    with pytest.raises(CliError) as info:
        megaplan.handle_init(
            root,
            _args(
                project_dir,
                name="missing-from-doc",
                mode="doc",
                output="docs/new-plan.md",
                from_doc="docs/missing.md",
            ),
        )
    assert info.value.code == "invalid_args"
    assert "--from-doc" in str(info.value)
    assert "does not exist" in str(info.value)


def test_from_doc_absolute_path_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    with pytest.raises(CliError) as info:
        megaplan.handle_init(
            root,
            _args(
                project_dir,
                name="absolute-from-doc",
                mode="doc",
                output="docs/new-plan.md",
                from_doc="/etc/passwd",
            ),
        )
    assert info.value.code == "invalid_args"
    assert "--from-doc" in str(info.value)
    assert "relative" in str(info.value).lower() or "absolute" in str(info.value).lower()


def test_from_doc_parent_traversal_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    with pytest.raises(CliError) as info:
        megaplan.handle_init(
            root,
            _args(
                project_dir,
                name="parent-from-doc",
                mode="doc",
                output="docs/new-plan.md",
                from_doc="../outside.md",
            ),
        )
    assert info.value.code == "invalid_args"
    assert "--from-doc" in str(info.value)
    assert ".." in str(info.value)


def test_from_doc_doc_with_no_section_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    prior_doc = project_dir / "docs" / "prior.md"
    prior_doc.parent.mkdir(parents=True, exist_ok=True)
    prior_doc.write_text("# Prior Doc\n\nNo settled decisions here.\n", encoding="utf-8")

    response = megaplan.handle_init(
        root,
        _args(
            project_dir,
            name="doc-with-empty-import",
            mode="doc",
            output="docs/new-plan.md",
            from_doc="docs/prior.md",
        ),
    )

    state = _load_state(root, response["plan"])
    assert state["config"]["from_doc"] == "docs/prior.md"
    assert state["meta"]["imported_decisions"] == []
    assert "warnings" not in response


def test_from_doc_valid_with_code_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    prior_doc = project_dir / "docs" / "prior.md"
    prior_doc.parent.mkdir(parents=True, exist_ok=True)
    prior_doc.write_text(
        """## Settled Decisions
- id: SD-004
  load_bearing: true
  decision: Code-mode plans can still inherit doc decisions
""",
        encoding="utf-8",
    )

    response = megaplan.handle_init(
        root,
        _args(
            project_dir,
            name="code-with-import",
            mode="code",
            from_doc="docs/prior.md",
        ),
    )

    state = _load_state(root, response["plan"])
    assert state["config"]["mode"] == "code"
    assert state["config"]["from_doc"] == "docs/prior.md"
    assert state["meta"]["imported_decisions"] == [
        {
            "id": "SD-004",
            "load_bearing": True,
            "decision": "Code-mode plans can still inherit doc decisions",
            "rationale": "",
        }
    ]


def test_from_doc_parse_warnings_surface_in_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    prior_doc = project_dir / "docs" / "prior.md"
    prior_doc.parent.mkdir(parents=True, exist_ok=True)
    prior_doc.write_text(
        """## Settled Decisions
- decision: Missing an ID should warn
  rationale: This should not fail init.
""",
        encoding="utf-8",
    )

    response = megaplan.handle_init(
        root,
        _args(
            project_dir,
            name="doc-with-warning-import",
            mode="doc",
            output="docs/new-plan.md",
            from_doc="docs/prior.md",
        ),
    )

    state = _load_state(root, response["plan"])
    assert response["warnings"] == ["Dropped malformed settled decision entry missing id"]
    assert state["config"]["from_doc"] == "docs/prior.md"
    assert state["meta"]["imported_decisions"] == []
    assert state["meta"]["notes"][-1]["note"] == "Dropped malformed settled decision entry missing id"
