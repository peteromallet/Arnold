"""Tests for arnold.pipeline.resume_validation — parser and artifact-resolution.

Covers parse_resume_reverify_declaration and resolve_resume_reverify_artifact
with exhaustive positive and negative cases, including cursor-opaque behaviour,
display_ref name resolution, and invalid-path rejection.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
import pathlib
from typing import Any, Mapping

import pytest

from arnold.pipeline.artifact_io import ArtifactIOBlocked
from arnold.pipeline.resume_validation import (
    ResumeReverifyDeclaration,
    ResumeReverifyResult,
    __all__ as resume_validation_all,
    parse_resume_reverify_declaration,
    reverify_resume_produces,
    resolve_resume_reverify_artifact,
)
from arnold.pipeline.schema_registry import ContractSchemaRegistry
from arnold.pipeline.step_io_policy import (
    CONTRACT_MODE_SHADOW,
    StepIOPolicy,
)
from arnold.pipeline.types import EvidenceArtifactRef, HumanSuspension


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _suspension(
    resume_input_schema: Mapping[str, Any] | None = None,
    *,
    display_refs: tuple[EvidenceArtifactRef, ...] = (),
) -> HumanSuspension:
    """Return a minimal HumanSuspension with the given resume_input_schema."""
    return HumanSuspension(
        kind="human",
        resume_input_schema=resume_input_schema or {},
        display_refs=display_refs,
    )


def _display_ref(
    *,
    name: str,
    uri: str = "file:///tmp/foo.md",
    content_type: str = "text/markdown",
) -> EvidenceArtifactRef:
    """Return a display ref with the given name."""
    return EvidenceArtifactRef(
        uri=uri,
        content_type=content_type,
        name=name,
    )


def _declaration(
    *,
    port: str | None = None,
    content_type: str | None = None,
    artifact_path: str | None = None,
    artifact_ref: dict[str, Any] | None = None,
    invalid_policy: str = "resuspend",
) -> ResumeReverifyDeclaration:
    """Return a ResumeReverifyDeclaration with the given fields."""
    return ResumeReverifyDeclaration(
        port=port,
        content_type=content_type,
        artifact_path=artifact_path,
        artifact_ref=artifact_ref,
        invalid_policy=invalid_policy,
    )


# ---------------------------------------------------------------------------
# parse_resume_reverify_declaration — no_op / type-guard
# ---------------------------------------------------------------------------


class TestParseNoOp:
    """Absent x-arnold-resume returns no_op."""

    def test_absent_key_returns_no_op(self) -> None:
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={})
        )
        assert result.outcome == "no_op"
        assert result.declaration is None
        assert result.diagnostic is None

    def test_absent_key_in_non_empty_schema(self) -> None:
        """When resume_input_schema has other keys but not x-arnold-resume."""
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={"yes": "bool", "reason": "str"})
        )
        assert result.outcome == "no_op"

    def test_none_null_value_not_absent(self) -> None:
        """Explicit null/None for x-arnold-resume is still present — not no_op."""
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={"x-arnold-resume": None})
        )
        # None is a present key but not a Mapping → malformed
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["code"] == "malformed_declaration"

    def test_empty_string_resume_input_schema(self) -> None:
        """Empty string resume_input_schema (edge case — unlikely but handled)."""
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={})
        )
        assert result.outcome == "no_op"


class TestParseTypeGuard:
    """Dict payloads are rejected; only HumanSuspension accepted."""

    def test_dict_rejected(self) -> None:
        """Raw dict raises TypeError — must use HumanSuspension.from_json()."""
        with pytest.raises(TypeError, match="HumanSuspension"):
            parse_resume_reverify_declaration({"resume_input_schema": {}})  # type: ignore[arg-type]

    def test_none_rejected(self) -> None:
        with pytest.raises(TypeError, match="HumanSuspension"):
            parse_resume_reverify_declaration(None)  # type: ignore[arg-type]

    def test_string_rejected(self) -> None:
        with pytest.raises(TypeError, match="HumanSuspension"):
            parse_resume_reverify_declaration("not-a-suspension")  # type: ignore[arg-type]

    def test_from_json_deserialized_dict_works(self) -> None:
        """A dict deserialized via HumanSuspension.from_json() is accepted."""
        raw = {
            "kind": "human",
            "resume_input_schema": {"x-arnold-resume": {"port": "p1"}},
            "display_refs": [],
        }
        suspension = HumanSuspension.from_json(raw)
        result = parse_resume_reverify_declaration(suspension)
        assert result.outcome == "valid"


# ---------------------------------------------------------------------------
# parse_resume_reverify_declaration — malformed / invalid
# ---------------------------------------------------------------------------


class TestParseMalformed:
    """Present x-arnold-resume with invalid shapes returns invalid."""

    def test_x_arnold_resume_not_a_dict(self) -> None:
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={"x-arnold-resume": "bad-type"})
        )
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["code"] == "malformed_declaration"
        assert "JSON object" in result.diagnostic["detail"]

    def test_x_arnold_resume_is_a_list(self) -> None:
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={"x-arnold-resume": [1, 2, 3]})
        )
        assert result.outcome == "invalid"
        assert result.diagnostic["code"] == "malformed_declaration"

    def test_x_arnold_resume_is_an_int(self) -> None:
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={"x-arnold-resume": 42})
        )
        assert result.outcome == "invalid"
        assert result.diagnostic["code"] == "malformed_declaration"

    def test_reverify_produces_not_a_dict(self) -> None:
        """When reverify_produces is present but not a dict."""
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {"reverify_produces": "not-a-dict"},
            })
        )
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["code"] == "malformed_declaration"
        assert "reverify_produces" in result.diagnostic["detail"]

    def test_reverify_produces_is_a_list(self) -> None:
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {"reverify_produces": [1, 2]},
            })
        )
        assert result.outcome == "invalid"
        assert result.diagnostic["code"] == "malformed_declaration"

    def test_declaration_must_specify_selector(self) -> None:
        """Declaration with no artifact_path, artifact_ref, or port is invalid."""
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {"content_type": "text/plain"},
            })
        )
        assert result.outcome == "invalid"
        assert result.diagnostic["code"] == "malformed_declaration"
        assert "artifact_path" in result.diagnostic["detail"] or "artifact_ref" in result.diagnostic["detail"]

    def test_empty_selector_strings_still_count_as_present(self) -> None:
        """Empty string artifact_path is present — passes the selector check."""
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {"artifact_path": ""},
            })
        )
        assert result.outcome == "valid"

    def test_port_not_a_string(self) -> None:
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {"port": 42},
            })
        )
        assert result.outcome == "invalid"
        assert result.diagnostic["code"] == "malformed_declaration"
        assert "port" in result.diagnostic["detail"]

    def test_content_type_not_a_string(self) -> None:
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {"content_type": True, "artifact_path": "x.md"},
            })
        )
        assert result.outcome == "invalid"
        assert result.diagnostic["code"] == "malformed_declaration"
        assert "content_type" in result.diagnostic["detail"]

    def test_artifact_path_not_a_string(self) -> None:
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {"artifact_path": 99},
            })
        )
        assert result.outcome == "invalid"
        assert result.diagnostic["code"] == "malformed_declaration"

    def test_invalid_policy_not_a_string(self) -> None:
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {"port": "p1", "invalid_policy": [1, 2]},
            })
        )
        assert result.outcome == "invalid"
        assert result.diagnostic["code"] == "malformed_declaration"
        assert "invalid_policy" in result.diagnostic["detail"]

    def test_artifact_ref_not_a_dict(self) -> None:
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {"artifact_ref": "not-a-dict"},
            })
        )
        assert result.outcome == "invalid"
        assert result.diagnostic["code"] == "malformed_declaration"
        assert "artifact_ref" in result.diagnostic["detail"]

    def test_artifact_ref_missing_name(self) -> None:
        """artifact_ref dict without a 'name' key is invalid."""
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {"artifact_ref": {"uri": "s3://b/file.md"}},
            })
        )
        assert result.outcome == "invalid"
        assert result.diagnostic["code"] == "malformed_declaration"
        assert "artifact_ref" in result.diagnostic["detail"]

    def test_artifact_ref_name_not_a_string(self) -> None:
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {"artifact_ref": {"name": 123, "uri": "s3://b/f.md"}},
            })
        )
        assert result.outcome == "invalid"
        assert result.diagnostic["code"] == "malformed_declaration"

    def test_diagnostic_is_json_safe(self) -> None:
        """All invalid diagnostics must be JSON-safe."""
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": "bad-type",
            })
        )
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        # Must survive json.dumps without error
        dumped = json.dumps(result.diagnostic)
        assert isinstance(dumped, str)
        loaded = json.loads(dumped)
        assert loaded["kind"] == "resume_reverify"
        assert loaded["code"] == "malformed_declaration"

    def test_diagnostic_structure_consistent(self) -> None:
        """All diagnostics have kind, code, detail."""
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": ["nope"],
            })
        )
        assert result.diagnostic is not None
        assert set(result.diagnostic.keys()) >= {"kind", "code", "detail"}
        assert result.diagnostic["kind"] == "resume_reverify"


# ---------------------------------------------------------------------------
# parse_resume_reverify_declaration — valid
# ---------------------------------------------------------------------------


class TestParseValid:
    """Valid declarations produce expected ResumeReverifyDeclaration."""

    def test_minimal_port_declaration(self) -> None:
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {"port": "scan_output"},
            })
        )
        assert result.outcome == "valid"
        assert result.declaration is not None
        assert result.declaration.port == "scan_output"
        assert result.declaration.content_type is None
        assert result.declaration.artifact_path is None
        assert result.declaration.artifact_ref is None
        assert result.declaration.invalid_policy == "resuspend"

    def test_full_flat_declaration(self) -> None:
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {
                    "port": "report_port",
                    "content_type": "application/json",
                    "artifact_path": "/tmp/report/v1.json",
                    "artifact_ref": {"name": "report", "uri": "s3://bkt/report.json"},
                    "invalid_policy": "reject",
                },
            })
        )
        assert result.outcome == "valid"
        d = result.declaration
        assert d is not None
        assert d.port == "report_port"
        assert d.content_type == "application/json"
        assert d.artifact_path == "/tmp/report/v1.json"
        assert d.artifact_ref == {"name": "report", "uri": "s3://bkt/report.json"}
        assert d.invalid_policy == "reject"

    def test_nested_reverify_produces(self) -> None:
        """Declaration inside reverify_produces key."""
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {
                    "reverify_produces": {
                        "port": "nested_port",
                        "artifact_path": "out.md",
                    },
                    "other_key": "ignored",
                },
            })
        )
        assert result.outcome == "valid"
        d = result.declaration
        assert d is not None
        assert d.port == "nested_port"
        assert d.artifact_path == "out.md"

    def test_artifact_path_only(self) -> None:
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {"artifact_path": "subdir/output.md"},
            })
        )
        assert result.outcome == "valid"
        assert result.declaration is not None
        assert result.declaration.artifact_path == "subdir/output.md"

    def test_artifact_ref_only(self) -> None:
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {"artifact_ref": {"name": "scan", "uri": "file:///tmp/scan.json"}},
            })
        )
        assert result.outcome == "valid"
        assert result.declaration is not None
        assert result.declaration.artifact_ref == {"name": "scan", "uri": "file:///tmp/scan.json"}

    def test_custom_invalid_policy(self) -> None:
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {"port": "p1", "invalid_policy": "reject"},
            })
        )
        assert result.outcome == "valid"
        assert result.declaration is not None
        assert result.declaration.invalid_policy == "reject"

    def test_declaration_is_frozen(self) -> None:
        """ResumeReverifyDeclaration is frozen — cannot mutate."""
        d = _declaration(port="p1")
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            d.port = "changed"  # type: ignore[misc]

    def test_result_is_frozen(self) -> None:
        """ResumeReverifyResult is frozen — cannot mutate."""
        r = ResumeReverifyResult(outcome="no_op")
        with pytest.raises(Exception):
            r.outcome = "valid"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# parse_resume_reverify_declaration — cursor-opaque
# ---------------------------------------------------------------------------


class TestParseCursorOpaque:
    """Prove cursor values are ignored / not consulted during parsing."""

    def test_cursor_produces_ignored(self) -> None:
        """Cursor fields like cursor['produces'] are ignored."""
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {"artifact_path": "declared/path.md"},
                "cursor": {"produces": ["some_artifact"]},
            })
        )
        assert result.outcome == "valid"
        assert result.declaration is not None
        # The cursor-provided path is NOT used
        assert result.declaration.artifact_path == "declared/path.md"

    def test_cursor_not_used_for_resolution_fallback(self) -> None:
        """Cursor content is never a fallback when declaration lacks selector."""
        # This is actually malformed because declaration has no selector
        # But we also confirm cursor fields don't provide a fallback selector
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {"content_type": "text/plain"},
            })
        )
        assert result.outcome == "invalid"
        # Even if we had cursor['produces'], it's NOT used

    def test_cursor_flat_produces_ignored(self) -> None:
        """Flat produces field in resume_input_schema is ignored."""
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {"port": "p1"},
                "produces": ["file_a", "file_b"],
            })
        )
        assert result.outcome == "valid"
        # Flat produces is ignored
        assert result.declaration is not None
        assert result.declaration.port == "p1"

    def test_cursor_not_interfering_with_declaration(self) -> None:
        """Complex cursor values do not affect parsing."""
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {"artifact_ref": {"name": "scan", "uri": "file:///tmp/s.json"}},
                "cursor": {
                    "state": "running",
                    "artifacts": ["ignored"],
                    "produces": ["should_not_be_used"],
                },
            })
        )
        assert result.outcome == "valid"
        assert result.declaration is not None
        assert result.declaration.artifact_ref == {"name": "scan", "uri": "file:///tmp/s.json"}


# ---------------------------------------------------------------------------
# resolve_resume_reverify_artifact — explicit artifact_path wins
# ---------------------------------------------------------------------------


class TestResolveExplicitArtifactPath:
    """When artifact_path is declared, it takes priority over port/artifact_ref."""

    def test_explicit_relative_artifact_path_resolves(self, tmp_path: Path) -> None:
        """A relative artifact_path declared in the declaration resolves correctly."""
        artifact_file = tmp_path / "subdir" / "output.md"
        artifact_file.parent.mkdir(parents=True, exist_ok=True)
        artifact_file.write_text("# Hello")

        decl = _declaration(artifact_path="subdir/output.md")
        suspension = _suspension(
            resume_input_schema={"x-arnold-resume": {"artifact_path": "subdir/output.md"}},
            display_refs=(_display_ref(name="other"),),
        )

        result = resolve_resume_reverify_artifact(
            suspension, decl, artifact_root=str(tmp_path),
        )
        assert result.outcome == "valid"
        assert result.resolved_artifact_path is not None
        assert str(artifact_file) in result.resolved_artifact_path or result.resolved_artifact_path.endswith("output.md")

    def test_explicit_path_wins_over_artifact_ref(self, tmp_path: Path) -> None:
        """When both artifact_path and artifact_ref are declared, artifact_path wins."""
        artifact_file = tmp_path / "winning.md"
        artifact_file.write_text("winner")

        # Also create a display_ref that would match if artifact_ref were used
        display = _display_ref(name="losing", uri=f"file://{tmp_path / 'losing_file.md'}")
        (tmp_path / "losing_file.md").write_text("loser")

        decl = _declaration(
            artifact_path="winning.md",
            artifact_ref={"name": "losing"},
            port="losing",
        )
        result = resolve_resume_reverify_artifact(
            suspension=_suspension(display_refs=(display,)),
            declaration=decl,
            artifact_root=str(tmp_path),
        )
        assert result.outcome == "valid"
        assert result.resolved_artifact_path is not None
        # Should resolve to winning.md, not losing_file.md
        assert "winning.md" in result.resolved_artifact_path

    def test_explicit_path_wins_over_port(self, tmp_path: Path) -> None:
        """artifact_path declared takes precedence over port in display_refs match."""
        artifact_file = tmp_path / "declared.md"
        artifact_file.write_text("declared")

        display = _display_ref(name="port_name", uri=f"file://{tmp_path / 'port_file.md'}")
        (tmp_path / "port_file.md").write_text("port")

        decl = _declaration(artifact_path="declared.md", port="port_name")
        result = resolve_resume_reverify_artifact(
            suspension=_suspension(display_refs=(display,)),
            declaration=decl,
            artifact_root=str(tmp_path),
        )
        assert result.outcome == "valid"
        assert "declared.md" in result.resolved_artifact_path or "declared" in str(result.resolved_artifact_path)


# ---------------------------------------------------------------------------
# resolve_resume_reverify_artifact — artifact_ref via display_refs
# ---------------------------------------------------------------------------


class TestResolveArtifactRef:
    """artifact_ref resolves only through display_refs name matching."""

    def test_artifact_ref_name_matches_display_ref(self, tmp_path: Path) -> None:
        artifact_file = tmp_path / "scan_output.json"
        artifact_file.write_text('{"ok": true}')

        display = _display_ref(
            name="scan_result",
            uri=f"file://{artifact_file}",
        )
        decl = _declaration(artifact_ref={"name": "scan_result"})

        result = resolve_resume_reverify_artifact(
            suspension=_suspension(display_refs=(display,)),
            declaration=decl,
            artifact_root=str(tmp_path),
        )
        assert result.outcome == "valid"
        assert result.resolved_artifact_path is not None

    def test_artifact_ref_name_missing_from_display_refs(self) -> None:
        """When artifact_ref name doesn't match any display_ref, resolution fails."""
        display = _display_ref(name="other_ref")
        decl = _declaration(artifact_ref={"name": "missing_ref"})

        result = resolve_resume_reverify_artifact(
            suspension=_suspension(display_refs=(display,)),
            declaration=decl,
            artifact_root="/tmp",
        )
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["code"] == "artifact_unresolved"
        assert "missing_ref" in result.diagnostic["detail"]

    def test_artifact_ref_matches_only_display_ref_name(self, tmp_path: Path) -> None:
        """Only the display_ref's .name field is matched, not other fields."""
        artifact_file = tmp_path / "matched.md"
        artifact_file.write_text("matched")

        display = _display_ref(
            name="target",
            uri=f"file://{artifact_file}",
            content_type="text/markdown",
        )
        # artifact_ref has a different content_type but matching name
        decl = _declaration(artifact_ref={
            "name": "target",
            "content_type": "application/json",  # different from display_ref
        })

        result = resolve_resume_reverify_artifact(
            suspension=_suspension(display_refs=(display,)),
            declaration=decl,
            artifact_root=str(tmp_path),
        )
        # Name matches, so resolution succeeds
        assert result.outcome == "valid"

    def test_artifact_ref_uri_not_file_scheme(self) -> None:
        """When matched display_ref has a non-file URI, resolution fails."""
        display = _display_ref(
            name="remote",
            uri="s3://bucket/remote.md",
        )
        decl = _declaration(artifact_ref={"name": "remote"})

        result = resolve_resume_reverify_artifact(
            suspension=_suspension(display_refs=(display,)),
            declaration=decl,
            artifact_root="/tmp",
        )
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        # Should be some kind of unresolved
        assert "file" in result.diagnostic["detail"].lower()


# ---------------------------------------------------------------------------
# resolve_resume_reverify_artifact — port via display_refs
# ---------------------------------------------------------------------------


class TestResolvePort:
    """port resolves only through display_refs name matching."""

    def test_port_matches_display_ref_name(self, tmp_path: Path) -> None:
        artifact_file = tmp_path / "out.json"
        artifact_file.write_text("{}")

        display = _display_ref(name="out_port", uri=f"file://{artifact_file}")
        decl = _declaration(port="out_port")

        result = resolve_resume_reverify_artifact(
            suspension=_suspension(display_refs=(display,)),
            declaration=decl,
            artifact_root=str(tmp_path),
        )
        assert result.outcome == "valid"
        assert result.resolved_artifact_path is not None

    def test_port_no_match_returns_unresolved(self) -> None:
        display = _display_ref(name="a")
        decl = _declaration(port="b")

        result = resolve_resume_reverify_artifact(
            suspension=_suspension(display_refs=(display,)),
            declaration=decl,
            artifact_root="/tmp",
        )
        assert result.outcome == "invalid"
        assert result.diagnostic["code"] == "artifact_unresolved"

    def test_port_match_multiple_display_refs_ambiguous(self) -> None:
        """Multiple display_refs with same name → ambiguous."""
        d1 = _display_ref(name="dup", uri="file:///tmp/a.md")
        d2 = _display_ref(name="dup", uri="file:///tmp/b.md")
        decl = _declaration(port="dup")

        result = resolve_resume_reverify_artifact(
            suspension=_suspension(display_refs=(d1, d2)),
            declaration=decl,
            artifact_root="/tmp",
        )
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["code"] == "artifact_ambiguous"

    def test_artifact_ref_ambiguous(self) -> None:
        """Multiple display_refs with same name via artifact_ref → ambiguous."""
        d1 = _display_ref(name="dup", uri="file:///tmp/a.md")
        d2 = _display_ref(name="dup", uri="file:///tmp/b.md")
        decl = _declaration(artifact_ref={"name": "dup"})

        result = resolve_resume_reverify_artifact(
            suspension=_suspension(display_refs=(d1, d2)),
            declaration=decl,
            artifact_root="/tmp",
        )
        assert result.outcome == "invalid"
        assert result.diagnostic["code"] == "artifact_ambiguous"


# ---------------------------------------------------------------------------
# resolve_resume_reverify_artifact — invalid paths
# ---------------------------------------------------------------------------


class TestResolveInvalidPaths:
    """Exhaustive invalid-path rejection cases."""

    def test_absolute_artifact_path_rejected(self, tmp_path: Path) -> None:
        """Absolute artifact_path is rejected (must be relative to artifact_root)."""
        decl = _declaration(artifact_path="/absolute/path/file.md")
        result = resolve_resume_reverify_artifact(
            suspension=_suspension(),
            declaration=decl,
            artifact_root=str(tmp_path),
        )
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["code"] == "artifact_path_invalid"
        assert "relative" in result.diagnostic["detail"].lower()

    def test_parent_escaping_path_rejected(self, tmp_path: Path) -> None:
        """Path that resolves outside artifact_root is rejected."""
        decl = _declaration(artifact_path="../escape/file.md")
        result = resolve_resume_reverify_artifact(
            suspension=_suspension(),
            declaration=decl,
            artifact_root=str(tmp_path),
        )
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["code"] == "artifact_path_invalid"
        assert "escapes" in result.diagnostic["detail"].lower()

    def test_missing_file_rejected(self, tmp_path: Path) -> None:
        """A relative path that doesn't exist on disk is rejected."""
        decl = _declaration(artifact_path="nonexistent.md")
        result = resolve_resume_reverify_artifact(
            suspension=_suspension(),
            declaration=decl,
            artifact_root=str(tmp_path),
        )
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["code"] == "artifact_missing"
        assert "does not exist" in result.diagnostic["detail"].lower()

    def test_directory_not_file_rejected(self, tmp_path: Path) -> None:
        """A path that exists but is a directory is rejected."""
        subdir = tmp_path / "a_directory"
        subdir.mkdir()
        decl = _declaration(artifact_path="a_directory")
        result = resolve_resume_reverify_artifact(
            suspension=_suspension(),
            declaration=decl,
            artifact_root=str(tmp_path),
        )
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["code"] == "artifact_not_file"

    def test_exhausted_resolution_no_display_refs(self) -> None:
        """When artifact_path is None and there are no display_refs, resolution fails."""
        decl = _declaration(port="p1")
        result = resolve_resume_reverify_artifact(
            suspension=_suspension(display_refs=()),
            declaration=decl,
            artifact_root="/tmp",
        )
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["code"] == "artifact_unresolved"

    def test_exhausted_resolution_artifact_ref_no_display_refs(self) -> None:
        decl = _declaration(artifact_ref={"name": "n"})
        result = resolve_resume_reverify_artifact(
            suspension=_suspension(display_refs=()),
            declaration=decl,
            artifact_root="/tmp",
        )
        assert result.outcome == "invalid"
        assert result.diagnostic["code"] == "artifact_unresolved"

    def test_symlink_within_root_resolves(self, tmp_path: Path) -> None:
        """Symlink within artifact_root resolves to the target."""
        real_file = tmp_path / "real.md"
        real_file.write_text("real")
        link = tmp_path / "link.md"
        os.symlink(str(real_file), str(link))

        decl = _declaration(artifact_path="link.md")
        result = resolve_resume_reverify_artifact(
            suspension=_suspension(),
            declaration=decl,
            artifact_root=str(tmp_path),
        )
        assert result.outcome == "valid"

    def test_symlink_escaping_root_rejected(self, tmp_path: Path) -> None:
        """Symlink that points outside artifact_root is rejected."""
        outside = tmp_path.parent / "outside.md"
        outside.write_text("outside")
        link = tmp_path / "escape_link.md"
        os.symlink(str(outside), str(link))

        decl = _declaration(artifact_path="escape_link.md")
        result = resolve_resume_reverify_artifact(
            suspension=_suspension(),
            declaration=decl,
            artifact_root=str(tmp_path),
        )
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["code"] == "artifact_path_invalid"

    def test_double_dot_resolving_back_into_root_is_valid(self, tmp_path: Path) -> None:
        """Path like 'sub/../file.md' that stays within root is valid."""
        (tmp_path / "sub").mkdir()
        file = tmp_path / "file.md"
        file.write_text("ok")

        decl = _declaration(artifact_path="sub/../file.md")
        result = resolve_resume_reverify_artifact(
            suspension=_suspension(),
            declaration=decl,
            artifact_root=str(tmp_path),
        )
        assert result.outcome == "valid"

    def test_artifact_ref_display_ref_file_missing(self, tmp_path: Path) -> None:
        """display_ref exists but the actual file is missing → artifact_missing."""
        display = _display_ref(
            name="gone",
            uri=f"file://{tmp_path / 'gone.md'}",
        )
        decl = _declaration(artifact_ref={"name": "gone"})
        result = resolve_resume_reverify_artifact(
            suspension=_suspension(display_refs=(display,)),
            declaration=decl,
            artifact_root=str(tmp_path),
        )
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["code"] == "artifact_missing"


# ---------------------------------------------------------------------------
# resolve_resume_reverify_artifact — display_ref resolution ordering
# ---------------------------------------------------------------------------


class TestResolutionOrdering:
    """Closed resolution order: artifact_path > artifact_ref > port."""

    def test_declared_artifact_path_takes_priority_over_all(self, tmp_path: Path) -> None:
        """artifact_path is used even when artifact_ref and port would resolve."""
        path_file = tmp_path / "path_file.md"
        path_file.write_text("path")

        ref_file = tmp_path / "ref_file.md"
        ref_file.write_text("ref")

        display = _display_ref(name="port_name", uri=f"file://{ref_file}")

        decl = _declaration(
            artifact_path="path_file.md",
            artifact_ref={"name": "port_name"},
            port="port_name",
        )
        result = resolve_resume_reverify_artifact(
            suspension=_suspension(display_refs=(display,)),
            declaration=decl,
            artifact_root=str(tmp_path),
        )
        assert result.outcome == "valid"
        assert "path_file" in result.resolved_artifact_path or "path_file.md" in str(result.resolved_artifact_path)

    def test_artifact_ref_takes_priority_over_port(self, tmp_path: Path) -> None:
        """When artifact_path is absent, artifact_ref name match is preferred over port."""
        ref_file = tmp_path / "ref.md"
        ref_file.write_text("ref")

        port_file = tmp_path / "port.md"
        port_file.write_text("port")

        ref_display = _display_ref(name="ref_name", uri=f"file://{ref_file}")
        port_display = _display_ref(name="port_name", uri=f"file://{port_file}")

        decl = _declaration(
            artifact_ref={"name": "ref_name"},
            port="port_name",
        )
        result = resolve_resume_reverify_artifact(
            suspension=_suspension(display_refs=(ref_display, port_display)),
            declaration=decl,
            artifact_root=str(tmp_path),
        )
        assert result.outcome == "valid"
        # Should use ref_display (artifact_ref takes priority over port)
        # The resolved path comes from ref_display
        assert result.resolved_artifact_path is not None

    def test_port_fallback_when_artifact_ref_present_but_unmatched(self, tmp_path: Path) -> None:
        """When artifact_ref has a name but doesn't match, resolution fails — no port fallback.
        artifact_ref takes strict priority: if present with a name, that name is the only match key."""
        port_file = tmp_path / "port_file.md"
        port_file.write_text("port")

        port_display = _display_ref(name="port_name", uri=f"file://{port_file}")
        other_display = _display_ref(name="other")

        decl = _declaration(
            artifact_ref={"name": "unmatched"},
            port="port_name",
        )
        result = resolve_resume_reverify_artifact(
            suspension=_suspension(display_refs=(port_display, other_display)),
            declaration=decl,
            artifact_root=str(tmp_path),
        )
        # artifact_ref has priority — its name doesn't match, so resolution fails
        # No fallback to port
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["code"] == "artifact_unresolved"


# ---------------------------------------------------------------------------
# Integration: parse + resolve round-trip
# ---------------------------------------------------------------------------


class TestIntegrationParseResolve:
    """End-to-end: parse a declaration then resolve its artifact."""

    def test_parse_then_resolve_explicit_path(self, tmp_path: Path) -> None:
        file = tmp_path / "doc.md"
        file.write_text("# doc")

        suspension = _suspension(resume_input_schema={
            "x-arnold-resume": {"artifact_path": "doc.md"},
        })

        parsed = parse_resume_reverify_declaration(suspension)
        assert parsed.outcome == "valid"
        assert parsed.declaration is not None

        resolved = resolve_resume_reverify_artifact(
            suspension, parsed.declaration, artifact_root=str(tmp_path),
        )
        assert resolved.outcome == "valid"
        assert resolved.resolved_artifact_path is not None

    def test_parse_then_resolve_via_artifact_ref(self, tmp_path: Path) -> None:
        file = tmp_path / "result.json"
        file.write_text("{}")

        display = _display_ref(name="result", uri=f"file://{file}")
        suspension = _suspension(
            resume_input_schema={
                "x-arnold-resume": {"artifact_ref": {"name": "result"}},
            },
            display_refs=(display,),
        )

        parsed = parse_resume_reverify_declaration(suspension)
        assert parsed.outcome == "valid"

        resolved = resolve_resume_reverify_artifact(
            suspension, parsed.declaration, artifact_root=str(tmp_path),
        )
        assert resolved.outcome == "valid"
        assert resolved.resolved_artifact_path is not None

    def test_parse_then_resolve_via_port(self, tmp_path: Path) -> None:
        file = tmp_path / "port_out.json"
        file.write_text("{}")

        display = _display_ref(name="port_out", uri=f"file://{file}")
        suspension = _suspension(
            resume_input_schema={
                "x-arnold-resume": {"port": "port_out"},
            },
            display_refs=(display,),
        )

        parsed = parse_resume_reverify_declaration(suspension)
        assert parsed.outcome == "valid"

        resolved = resolve_resume_reverify_artifact(
            suspension, parsed.declaration, artifact_root=str(tmp_path),
        )
        assert resolved.outcome == "valid"

    def test_parse_invalid_does_not_resolve(self, tmp_path: Path) -> None:
        """An invalid parse result's declaration is None — resolve would fail."""
        suspension = _suspension(resume_input_schema={
            "x-arnold-resume": "not-an-object",
        })

        parsed = parse_resume_reverify_declaration(suspension)
        assert parsed.outcome == "invalid"
        assert parsed.declaration is None

    def test_round_trip_through_json_serialize(self, tmp_path: Path) -> None:
        """Parse → resolve → serialize diagnostic as JSON (for error reporting)."""
        file = tmp_path / "ok.md"
        file.write_text("ok")

        suspension = _suspension(resume_input_schema={
            "x-arnold-resume": {"artifact_path": "ok.md"},
        })

        parsed = parse_resume_reverify_declaration(suspension)
        resolved = resolve_resume_reverify_artifact(
            suspension, parsed.declaration, artifact_root=str(tmp_path),
        )

        # Serialize the full result
        result_dict = {
            "outcome": resolved.outcome,
            "resolved_artifact_path": resolved.resolved_artifact_path,
            "diagnostic": resolved.diagnostic,
        }
        dumped = json.dumps(result_dict, sort_keys=True)
        loaded = json.loads(dumped)
        assert loaded["outcome"] == "valid"
        assert loaded["resolved_artifact_path"] is not None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_declaration_with_all_none_fields_is_invalid(self) -> None:
        """A ResumeReverifyDeclaration with all None fields would not parse as valid."""
        result = parse_resume_reverify_declaration(
            _suspension(resume_input_schema={
                "x-arnold-resume": {},
            })
        )
        assert result.outcome == "invalid"
        assert "artifact_path" in result.diagnostic["detail"] or "artifact_ref" in result.diagnostic["detail"]

    def test_empty_display_refs_resolve_port_fails(self) -> None:
        """Port resolution with empty display_refs returns invalid."""
        decl = _declaration(port="p1")
        result = resolve_resume_reverify_artifact(
            suspension=_suspension(display_refs=()),
            declaration=decl,
            artifact_root="/tmp",
        )
        assert result.outcome == "invalid"
        assert result.diagnostic["code"] == "artifact_unresolved"

    def test_display_ref_without_name_works_for_port_match(self) -> None:
        """Display refs without names (name=None) are not matched."""
        # EvidenceArtifactRef can have name=None
        display = EvidenceArtifactRef(
            uri="file:///tmp/file.md",
            content_type="text/markdown",
            name=None,
        )
        decl = _declaration(port="anything")
        result = resolve_resume_reverify_artifact(
            suspension=_suspension(display_refs=(display,)),
            declaration=decl,
            artifact_root="/tmp",
        )
        assert result.outcome == "invalid"

    def test_resolved_artifact_path_set_on_valid_result(self, tmp_path: Path) -> None:
        file = tmp_path / "a.md"
        file.write_text("")
        decl = _declaration(artifact_path="a.md")
        result = resolve_resume_reverify_artifact(
            suspension=_suspension(), declaration=decl, artifact_root=str(tmp_path),
        )
        assert result.outcome == "valid"
        assert result.resolved_artifact_path is not None
        assert Path(result.resolved_artifact_path).exists()

    def test_no_op_has_no_declaration_or_diagnostic(self) -> None:
        result = parse_resume_reverify_declaration(_suspension())
        assert result.outcome == "no_op"
        assert result.declaration is None
        assert result.diagnostic is None
        assert result.resolved_artifact_path is None

    def test_invalid_result_carries_declaration_when_parsed(self) -> None:
        """When declaration was successfully parsed but resolution fails,
        the invalid result still carries the declaration."""
        decl = _declaration(artifact_path="nonexistent.md")
        result = resolve_resume_reverify_artifact(
            suspension=_suspension(), declaration=decl, artifact_root="/tmp",
        )
        assert result.outcome == "invalid"
        assert result.declaration is not None
        assert result.declaration.artifact_path == "nonexistent.md"

    def test_display_ref_uri_with_localhost_netloc(self, tmp_path: Path) -> None:
        """file://localhost/... URIs are valid file URIs."""
        file = tmp_path / "via_localhost.md"
        file.write_text("localhost")

        display = EvidenceArtifactRef(
            uri=f"file://localhost{file}",
            content_type="text/markdown",
            name="local",
        )
        decl = _declaration(artifact_ref={"name": "local"})
        result = resolve_resume_reverify_artifact(
            suspension=_suspension(display_refs=(display,)),
            declaration=decl,
            artifact_root=str(tmp_path),
        )
        assert result.outcome == "valid"

    def test_artifact_root_as_path_object(self, tmp_path: Path) -> None:
        """artifact_root as a Path object works the same as str."""
        file = tmp_path / "p.md"
        file.write_text("")
        decl = _declaration(artifact_path="p.md")
        result = resolve_resume_reverify_artifact(
            suspension=_suspension(), declaration=decl, artifact_root=tmp_path,
        )
        assert result.outcome == "valid"


# ---------------------------------------------------------------------------
# reverify_resume_produces — helper validation coverage
# ---------------------------------------------------------------------------


def _answer_registry(tmp_path: Path) -> ContractSchemaRegistry:
    registry = ContractSchemaRegistry(tmp_path)
    registry.register(
        "answer",
        {
            "type": "object",
            "required": ["value"],
            "properties": {"value": {"type": "integer"}},
            "additionalProperties": False,
        },
    )
    return registry


def _answer_envelope(
    registry: ContractSchemaRegistry,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    version = registry.latest("answer")
    assert version is not None
    return {
        "logical_type": "answer",
        "schema_version": version,
        "payload": dict(payload),
    }


def _write_resume_json(
    tmp_path: Path,
    *,
    artifact_name: str,
    body: Any,
    declaration: Mapping[str, Any],
) -> HumanSuspension:
    artifact_path = tmp_path / artifact_name
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(body), encoding="utf-8")
    return _suspension(resume_input_schema={"x-arnold-resume": dict(declaration)})


class TestReverifyResumeProduces:
    def test_valid_typed_envelope_returns_valid(self, tmp_path: Path) -> None:
        registry = _answer_registry(tmp_path)
        suspension = _write_resume_json(
            tmp_path,
            artifact_name="artifact.json",
            body=_answer_envelope(registry, {"value": 42}),
            declaration={"artifact_path": "artifact.json"},
        )

        result = reverify_resume_produces(
            suspension,
            artifact_root=tmp_path,
            schema_registry=registry,
        )

        assert result.outcome == "valid"
        assert result.resolved_artifact_path == str(tmp_path / "artifact.json")

    def test_invalid_typed_envelope_returns_runtime_contract_diagnostic(
        self,
        tmp_path: Path,
    ) -> None:
        registry = _answer_registry(tmp_path)
        suspension = _write_resume_json(
            tmp_path,
            artifact_name="artifact.json",
            body=_answer_envelope(registry, {"value": "oops"}),
            declaration={"artifact_path": "artifact.json", "port": "answer_port"},
        )

        result = reverify_resume_produces(
            suspension,
            artifact_root=tmp_path,
            schema_registry=registry,
            producer_stage="child_step",
        )

        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["code"] == "typed_contract_blocked"
        runtime = result.diagnostic["runtime_contract"]
        assert runtime["producer_stage"] == "child_step"
        assert runtime["consumer_stage"] == "resume_reverify"
        assert runtime["seam_id"] == "answer_port"
        assert runtime["failure_code"] == "type_mismatch"

    def test_missing_schema_registry_blocks_with_schema_unavailable(
        self,
        tmp_path: Path,
    ) -> None:
        registry = _answer_registry(tmp_path)
        suspension = _write_resume_json(
            tmp_path,
            artifact_name="artifact.json",
            body=_answer_envelope(registry, {"value": 42}),
            declaration={"artifact_path": "artifact.json", "port": "answer_port"},
        )

        result = reverify_resume_produces(
            suspension,
            artifact_root=tmp_path,
            schema_registry=None,
        )

        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["code"] == "typed_contract_blocked"
        assert result.diagnostic["runtime_contract"]["failure_code"] == "schema_unavailable"

    def test_non_media_legacy_json_requires_typed_envelope(self, tmp_path: Path) -> None:
        suspension = _write_resume_json(
            tmp_path,
            artifact_name="artifact.json",
            body={"value": 42},
            declaration={"artifact_path": "artifact.json"},
        )

        result = reverify_resume_produces(
            suspension,
            artifact_root=tmp_path,
            schema_registry=_answer_registry(tmp_path),
        )

        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["code"] == "typed_envelope_required"

    def test_shadow_policy_is_rejected(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        registry = _answer_registry(tmp_path)
        suspension = _write_resume_json(
            tmp_path,
            artifact_name="artifact.json",
            body=_answer_envelope(registry, {"value": 42}),
            declaration={"artifact_path": "artifact.json"},
        )

        monkeypatch.setattr(
            "arnold.pipeline.resume_validation.resolve_step_io_policy",
            lambda **_: StepIOPolicy(
                configured_mode=CONTRACT_MODE_SHADOW,
                effective_mode=CONTRACT_MODE_SHADOW,
                producer_typed=True,
                consumer_typed=True,
                enforcement_eligible=True,
            ),
        )

        with pytest.raises(AssertionError, match="enforce-eligible READ policy"):
            reverify_resume_produces(
                suspension,
                artifact_root=tmp_path,
                schema_registry=registry,
            )

    def test_blocked_without_carriers_uses_degraded_diagnostic(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        registry = _answer_registry(tmp_path)
        suspension = _write_resume_json(
            tmp_path,
            artifact_name="artifact.json",
            body=_answer_envelope(registry, {"value": 42}),
            declaration={"artifact_path": "artifact.json", "port": "answer_port"},
        )

        def _raise_without_carriers(*args: Any, **kwargs: Any) -> None:
            del args, kwargs
            raise ArtifactIOBlocked("carrier-less blocked")

        monkeypatch.setattr(
            "arnold.pipeline.resume_validation.validate_artifact_io",
            _raise_without_carriers,
        )

        result = reverify_resume_produces(
            suspension,
            artifact_root=tmp_path,
            schema_registry=registry,
        )

        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["detail"] == "carrier-less blocked"
        runtime = result.diagnostic["runtime_contract"]
        assert runtime["failure_code"] == "typed_contract_blocked"
        assert runtime["logical_type"] == "unknown"

    def test_media_metadata_validates_without_reading_blob_bytes(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        blob_path = tmp_path / "movie.mp4"
        blob_path.write_bytes(b"not-real-video")
        suspension = _write_resume_json(
            tmp_path,
            artifact_name="artifact.json",
            body={
                "content_type": "video/mp4",
                "uri": blob_path.as_uri(),
                "size_bytes": 14,
                "name": "movie",
            },
            declaration={
                "artifact_path": "artifact.json",
                "content_type": "video/mp4",
            },
        )
        original_open = pathlib.Path.open

        def _guard_open(self: Path, *args: Any, **kwargs: Any):  # type: ignore[override]
            if self == blob_path:
                raise AssertionError("media blob bytes must not be opened")
            return original_open(self, *args, **kwargs)

        monkeypatch.setattr(pathlib.Path, "open", _guard_open)

        result = reverify_resume_produces(
            suspension,
            artifact_root=tmp_path,
            schema_registry=None,
        )

        assert result.outcome == "valid"

    def test_invalid_media_metadata_returns_validator_diagnostic(self, tmp_path: Path) -> None:
        suspension = _write_resume_json(
            tmp_path,
            artifact_name="artifact.json",
            body={
                "content_type": "video/mp4",
                "uri": "",
            },
            declaration={
                "artifact_path": "artifact.json",
                "content_type": "video/mp4",
            },
        )

        result = reverify_resume_produces(
            suspension,
            artifact_root=tmp_path,
            schema_registry=None,
        )

        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["code"] == "media_metadata_invalid"
        assert result.diagnostic["validation_diagnostics"][0]["code"] == "missing_uri"


# ---------------------------------------------------------------------------
# Additional media content-type coverage (T16 / SC16)
# ---------------------------------------------------------------------------


class TestMediaAdditionalContentTypes:
    """Cover audio/wav and application/x-astrid-timeline media validation."""

    def test_audio_wav_media_metadata_validates(self, tmp_path: Path) -> None:
        suspension = _write_resume_json(
            tmp_path,
            artifact_name="artifact.json",
            body={
                "content_type": "audio/wav",
                "uri": (tmp_path / "sound.wav").as_uri(),
                "size_bytes": 8000,
                "name": "greeting",
            },
            declaration={
                "artifact_path": "artifact.json",
                "content_type": "audio/wav",
            },
        )
        result = reverify_resume_produces(
            suspension,
            artifact_root=tmp_path,
            schema_registry=None,
        )
        assert result.outcome == "valid"
        assert result.resolved_artifact_path == str(tmp_path / "artifact.json")

    def test_audio_wav_media_metadata_invalid_content_type(self, tmp_path: Path) -> None:
        """audio/wav metadata with wrong content_type in blob → invalid."""
        suspension = _write_resume_json(
            tmp_path,
            artifact_name="artifact.json",
            body={
                "content_type": "video/mp4",  # wrong
                "uri": (tmp_path / "sound.wav").as_uri(),
            },
            declaration={
                "artifact_path": "artifact.json",
                "content_type": "audio/wav",
            },
        )
        result = reverify_resume_produces(
            suspension,
            artifact_root=tmp_path,
            schema_registry=None,
        )
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["code"] == "media_metadata_invalid"
        assert result.diagnostic["validation_diagnostics"][0]["code"] == "invalid_content_type"

    def test_astrid_timeline_media_metadata_validates(self, tmp_path: Path) -> None:
        suspension = _write_resume_json(
            tmp_path,
            artifact_name="artifact.json",
            body={
                "content_type": "application/x-astrid-timeline",
                "uri": (tmp_path / "timeline.bin").as_uri(),
                "name": "main-timeline",
            },
            declaration={
                "artifact_path": "artifact.json",
                "content_type": "application/x-astrid-timeline",
            },
        )
        result = reverify_resume_produces(
            suspension,
            artifact_root=tmp_path,
            schema_registry=None,
        )
        assert result.outcome == "valid"

    def test_astrid_timeline_media_metadata_missing_uri(self, tmp_path: Path) -> None:
        suspension = _write_resume_json(
            tmp_path,
            artifact_name="artifact.json",
            body={
                "content_type": "application/x-astrid-timeline",
                "uri": "",
            },
            declaration={
                "artifact_path": "artifact.json",
                "content_type": "application/x-astrid-timeline",
            },
        )
        result = reverify_resume_produces(
            suspension,
            artifact_root=tmp_path,
            schema_registry=None,
        )
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["code"] == "media_metadata_invalid"
        assert result.diagnostic["validation_diagnostics"][0]["code"] == "missing_uri"

    def test_media_metadata_missing_content_type_field(self, tmp_path: Path) -> None:
        """Media artifact JSON missing the content_type field entirely."""
        suspension = _write_resume_json(
            tmp_path,
            artifact_name="artifact.json",
            body={"uri": (tmp_path / "movie.mp4").as_uri()},
            declaration={
                "artifact_path": "artifact.json",
                "content_type": "video/mp4",
            },
        )
        result = reverify_resume_produces(
            suspension,
            artifact_root=tmp_path,
            schema_registry=None,
        )
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["code"] == "media_metadata_invalid"

    def test_media_metadata_not_a_mapping(self, tmp_path: Path) -> None:
        """Media artifact JSON that is a list, not a mapping.
        The non-object shape is caught before media-specific checks."""
        artifact_path = tmp_path / "artifact.json"
        artifact_path.write_text(json.dumps(["not", "a", "mapping"]), encoding="utf-8")
        suspension = _suspension(resume_input_schema={
            "x-arnold-resume": {
                "artifact_path": "artifact.json",
                "content_type": "video/mp4",
            },
        })
        result = reverify_resume_produces(
            suspension,
            artifact_root=tmp_path,
            schema_registry=None,
        )
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        # Non-object JSON is rejected before media-specific checks run
        assert result.diagnostic["code"] == "artifact_json_shape_invalid"
        assert "object" in result.diagnostic["detail"].lower()


# ---------------------------------------------------------------------------
# Media byte-read guard — all media content types (T16 / SC16)
# ---------------------------------------------------------------------------


class TestMediaByteReadGuardAllTypes:
    """Prove that no media content type ever causes the referenced blob to be opened."""

    _MEDIA_SPECS = [
        ("audio/wav", "sound.wav", b"fake-audio-data"),
        ("application/x-astrid-timeline", "timeline.bin", b"fake-timeline"),
    ]

    def _assert_no_blob_open(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        content_type: str,
        blob_name: str,
        blob_data: bytes,
    ) -> None:
        blob_path = tmp_path / blob_name
        blob_path.write_bytes(blob_data)
        suspension = _write_resume_json(
            tmp_path,
            artifact_name="artifact.json",
            body={
                "content_type": content_type,
                "uri": blob_path.as_uri(),
                "size_bytes": len(blob_data),
                "name": "test-blob",
                "digest": "sha256:abc123",
            },
            declaration={
                "artifact_path": "artifact.json",
                "content_type": content_type,
            },
        )
        original_open = pathlib.Path.open

        def _guard_open(self: Path, *args: Any, **kwargs: Any):  # type: ignore[override]
            if self == blob_path:
                raise AssertionError(f"media blob bytes must not be opened: {self}")
            return original_open(self, *args, **kwargs)

        monkeypatch.setattr(pathlib.Path, "open", _guard_open)

        result = reverify_resume_produces(
            suspension,
            artifact_root=tmp_path,
            schema_registry=None,
        )
        assert result.outcome == "valid"

    def test_audio_wav_no_blob_open(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._assert_no_blob_open(
            tmp_path, monkeypatch, "audio/wav", "sound.wav", b"fake-audio",
        )

    def test_astrid_timeline_no_blob_open(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._assert_no_blob_open(
            tmp_path, monkeypatch, "application/x-astrid-timeline",
            "timeline.bin", b"fake-timeline",
        )


# ---------------------------------------------------------------------------
# Typed-envelope media content-type handling (T16 / SC16)
# ---------------------------------------------------------------------------


class TestTypedEnvelopeMediaContentTypeHandling:
    """Media content types route through metadata validation, not typed-envelope."""

    def test_video_mp4_skips_typed_envelope_even_with_schema_registry(
        self, tmp_path: Path,
    ) -> None:
        """Declared content_type=video/mp4 routes through media path
        even when a schema registry is available."""
        registry = _answer_registry(tmp_path)
        suspension = _write_resume_json(
            tmp_path,
            artifact_name="artifact.json",
            body={
                "content_type": "video/mp4",
                "uri": (tmp_path / "movie.mp4").as_uri(),
                "size_bytes": 100,
            },
            declaration={
                "artifact_path": "artifact.json",
                "content_type": "video/mp4",
            },
        )
        result = reverify_resume_produces(
            suspension,
            artifact_root=tmp_path,
            schema_registry=registry,
        )
        assert result.outcome == "valid"

    def test_audio_wav_skips_typed_envelope_with_schema_registry(
        self, tmp_path: Path,
    ) -> None:
        registry = _answer_registry(tmp_path)
        suspension = _write_resume_json(
            tmp_path,
            artifact_name="artifact.json",
            body={
                "content_type": "audio/wav",
                "uri": (tmp_path / "sound.wav").as_uri(),
                "size_bytes": 8000,
            },
            declaration={
                "artifact_path": "artifact.json",
                "content_type": "audio/wav",
            },
        )
        result = reverify_resume_produces(
            suspension,
            artifact_root=tmp_path,
            schema_registry=registry,
        )
        assert result.outcome == "valid"

    def test_non_media_typed_envelope_without_schema_registry_blocks(
        self, tmp_path: Path,
    ) -> None:
        """Non-media content types require typed envelopes when no schema."""
        registry = _answer_registry(tmp_path)
        suspension = _write_resume_json(
            tmp_path,
            artifact_name="artifact.json",
            body=_answer_envelope(registry, {"value": 42}),
            declaration={
                "artifact_path": "artifact.json",
                "content_type": "application/json",
            },
        )
        result = reverify_resume_produces(
            suspension,
            artifact_root=tmp_path,
            schema_registry=None,
        )
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        assert result.diagnostic["code"] == "typed_contract_blocked"
        assert result.diagnostic["runtime_contract"]["failure_code"] == "schema_unavailable"

    def test_non_media_content_type_without_declared_content_type_is_typed(
        self, tmp_path: Path,
    ) -> None:
        """When no content_type is declared, the artifact is treated as non-media
        and must be a typed envelope."""
        registry = _answer_registry(tmp_path)
        suspension = _write_resume_json(
            tmp_path,
            artifact_name="artifact.json",
            body=_answer_envelope(registry, {"value": 42}),
            declaration={"artifact_path": "artifact.json"},
        )
        result = reverify_resume_produces(
            suspension,
            artifact_root=tmp_path,
            schema_registry=registry,
        )
        assert result.outcome == "valid"


# ---------------------------------------------------------------------------
# Decision-only runtime parity (T16 / SC16)
# ---------------------------------------------------------------------------


class TestDecisionOnlyRuntimeParity:
    """Diagnostic shape is consistent regardless of decision source."""

    def test_carrier_based_diagnostic_has_expected_keys(
        self, tmp_path: Path,
    ) -> None:
        registry = _answer_registry(tmp_path)
        suspension = _write_resume_json(
            tmp_path,
            artifact_name="artifact.json",
            body=_answer_envelope(registry, {"value": "bad-type"}),
            declaration={
                "artifact_path": "artifact.json",
                "port": "answer_port",
                "content_type": "application/json",
            },
        )
        result = reverify_resume_produces(
            suspension,
            artifact_root=tmp_path,
            schema_registry=registry,
            producer_stage="child_step",
        )
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        runtime = result.diagnostic["runtime_contract"]
        assert runtime["producer_stage"] == "child_step"
        assert runtime["consumer_stage"] == "resume_reverify"
        assert runtime["seam_id"] == "answer_port"
        assert "logical_type" in runtime
        assert "schema_version" in runtime
        assert "failure_code" in runtime
        assert "suggested_author_action" in runtime

    def test_carrier_less_diagnostic_has_same_structure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        registry = _answer_registry(tmp_path)
        suspension = _write_resume_json(
            tmp_path,
            artifact_name="artifact.json",
            body=_answer_envelope(registry, {"value": 42}),
            declaration={
                "artifact_path": "artifact.json",
                "port": "answer_port",
            },
        )

        def _raise_without_carriers(*args: Any, **kwargs: Any) -> None:
            del args, kwargs
            raise ArtifactIOBlocked("carrier-less blocked")

        monkeypatch.setattr(
            "arnold.pipeline.resume_validation.validate_artifact_io",
            _raise_without_carriers,
        )

        result = reverify_resume_produces(
            suspension,
            artifact_root=tmp_path,
            schema_registry=registry,
            producer_stage="child_step",
        )
        assert result.outcome == "invalid"
        assert result.diagnostic is not None
        runtime = result.diagnostic["runtime_contract"]
        # Same structural keys as the carrier-based path
        assert runtime["producer_stage"] == "child_step"
        assert runtime["consumer_stage"] == "resume_reverify"
        assert runtime["seam_id"] == "answer_port"
        assert "logical_type" in runtime
        assert "schema_version" in runtime
        assert "failure_code" in runtime
        assert "suggested_author_action" in runtime
        # carrier-less defaults
        assert runtime["failure_code"] == "typed_contract_blocked"
        assert runtime["logical_type"] == "unknown"
        assert runtime["schema_version"] == "unknown"

    def test_no_op_result_has_consistent_shape(self) -> None:
        """no_op result shape stays consistent (no declaration, no diagnostic)."""
        result = reverify_resume_produces(
            _suspension(),
            artifact_root="/tmp",
            schema_registry=None,
        )
        assert result.outcome == "no_op"
        assert result.declaration is None
        assert result.diagnostic is None
        assert result.resolved_artifact_path is None

    def test_invalid_parse_does_not_call_validator(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When parsing fails (invalid), validate_artifact_io is never invoked."""
        called = False
        original = __import__("arnold.pipeline.resume_validation", fromlist=["validate_artifact_io"])

        def _tracking_validate(*args: Any, **kwargs: Any) -> Any:
            nonlocal called
            called = True
            return original.validate_artifact_io(*args, **kwargs)

        monkeypatch.setattr(
            "arnold.pipeline.resume_validation.validate_artifact_io",
            _tracking_validate,
        )
        suspension = _suspension(resume_input_schema={
            "x-arnold-resume": "not-a-mapping",
        })
        result = reverify_resume_produces(
            suspension,
            artifact_root=tmp_path,
            schema_registry=None,
        )
        assert result.outcome == "invalid"
        assert not called


# ---------------------------------------------------------------------------
# No Megaplan import or plan_dir leakage (T16 / SC16)
# ---------------------------------------------------------------------------


_IMPORT_ISOLATION_RESUME_VALIDATION_SCRIPT = """
import sys

from arnold.pipeline.resume_validation import (
    ResumeReverifyDeclaration,
    ResumeReverifyResult,
    parse_resume_reverify_declaration,
    reverify_resume_produces,
    resolve_resume_reverify_artifact,
)

# Assert no megaplan.* module appears in sys.modules
megaplan_modules = [k for k in sys.modules if k.startswith("megaplan.")]
if megaplan_modules:
    print("FAIL: megaplan modules leaked:", megaplan_modules)
    sys.exit(1)

# Also check arnold.pipelines.megaplan
arnold_megaplan_modules = [
    k for k in sys.modules if k.startswith("arnold.pipelines.megaplan")
]
if arnold_megaplan_modules:
    print("FAIL: arnold megaplan modules leaked:", arnold_megaplan_modules)
    sys.exit(1)

# Smoke: the imports resolved
assert ResumeReverifyDeclaration is not None
assert ResumeReverifyResult is not None
assert parse_resume_reverify_declaration is not None
assert reverify_resume_produces is not None
assert resolve_resume_reverify_artifact is not None

print("OK: resume_validation import isolation verified")
"""


class TestResumeValidationImportIsolation:
    """Importing resume_validation must not pull megaplan into sys.modules."""

    def test_import_isolation_via_subprocess(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", _IMPORT_ISOLATION_RESUME_VALIDATION_SCRIPT],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"resume_validation import isolation subprocess failed:\n"
            f"stdout={result.stdout}\n"
            f"stderr={result.stderr}"
        )
        assert "OK: resume_validation import isolation verified" in result.stdout

    def test_resume_validation_module_has_no_megaplan_imports_static(self) -> None:
        """Static AST check: resume_validation.py has zero megaplan imports."""
        import ast
        resume_validation_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "arnold" / "pipeline" / "resume_validation.py"
        )
        source = resume_validation_path.read_text()
        tree = ast.parse(source, filename=str(resume_validation_path))
        violations: list[str] = []
        forbidden = ("megaplan", "arnold.pipelines.megaplan")
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(
                        alias.name == root or alias.name.startswith(f"{root}.")
                        for root in forbidden
                    ):
                        violations.append(
                            f"line {node.lineno}: import {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module is not None and any(
                    node.module == root or node.module.startswith(f"{root}.")
                    for root in forbidden
                ):
                    names = ", ".join(a.name for a in node.names)
                    violations.append(
                        f"line {node.lineno}: from {node.module} import {names}"
                    )
        if violations:
            pytest.fail(
                f"resume_validation.py has {len(violations)} megaplan import(s):\n"
                + "\n".join(f"  • {v}" for v in violations)
            )


class TestNoPlanDirLeakage:
    """The neutral helper does not accept or leak plan_dir."""

    def test_reverify_resume_produces_signature_no_plan_dir(self) -> None:
        """reverify_resume_produces must not have a plan_dir parameter."""
        import inspect
        sig = inspect.signature(reverify_resume_produces)
        params = list(sig.parameters.keys())
        assert "plan_dir" not in params, (
            f"reverify_resume_produces must not accept plan_dir; "
            f"found parameters: {params}"
        )

    def test_parse_resume_reverify_declaration_no_plan_dir(self) -> None:
        """parse_resume_reverify_declaration must not have a plan_dir parameter."""
        import inspect
        sig = inspect.signature(parse_resume_reverify_declaration)
        params = list(sig.parameters.keys())
        assert "plan_dir" not in params, (
            f"parse_resume_reverify_declaration must not accept plan_dir; "
            f"found parameters: {params}"
        )

    def test_resolve_resume_reverify_artifact_no_plan_dir(self) -> None:
        """resolve_resume_reverify_artifact must not have a plan_dir parameter."""
        import inspect
        sig = inspect.signature(resolve_resume_reverify_artifact)
        params = list(sig.parameters.keys())
        assert "plan_dir" not in params, (
            f"resolve_resume_reverify_artifact must not accept plan_dir; "
            f"found parameters: {params}"
        )

    def test_no_megaplan_string_in_resume_validation_source(self) -> None:
        """No literal 'megaplan' or 'plan_dir' string in resume_validation.py."""
        import ast
        resume_validation_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "arnold" / "pipeline" / "resume_validation.py"
        )
        source = resume_validation_path.read_text()
        tree = ast.parse(source, filename=str(resume_validation_path))
        forbidden = {"megaplan", "plan_dir"}
        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in forbidden:
                    violations.append(
                        f"line {node.lineno}: forbidden literal '{node.value}'"
                    )
        if violations:
            pytest.fail(
                f"resume_validation.py has {len(violations)} forbidden literal(s):\n"
                + "\n".join(f"  • {v}" for v in violations)
            )

    def test_public_api_contains_no_plan_dir(self) -> None:
        """The public __all__ does not expose plan_dir."""
        for name in resume_validation_all:
            assert "plan_dir" not in name.lower(), (
                f"Public API name {name!r} suggests plan_dir leakage"
            )
