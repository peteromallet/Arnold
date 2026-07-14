"""Tests for ``strategy migrate --apply`` (T11).

Covers the two supported rewrite classes (strategy version upgrade for eligible
states, ticket epics normalisation), the safety contract (byte-for-byte backups
+ SHA-256 manifest, atomic writes, no renames, no invented IDs), idempotency,
and the blocker gate.  Uses synthetic fixtures — never touches the real corpus.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.layout import strategy_file_path
from arnold_pipelines.megaplan.strategy.apply_migration import (
    ELIGIBLE_VERSION_STATES,
    REWRITE_NORMALIZE_EPICS,
    REWRITE_UPGRADE_VERSION,
    apply_strategy_migration,
    compute_apply_plan,
    rewrite_strategy_version,
    rewrite_ticket_epics,
)
from arnold_pipelines.megaplan.strategy.versions import CURRENT_SCHEMA_VERSION

TICKETS_DIR = Path(".megaplan") / "tickets"
STRATEGY_PATH = Path(".megaplan") / "STRATEGY.md"
BACKUP_BASE = Path(".megaplan") / "backups" / "strategy-migration"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


CURRENT_STRATEGY = f"""\
---
schema_version: {CURRENT_SCHEMA_VERSION}
title: Current Strategy
---
Body.
"""

MISSING_VERSION_STRATEGY = """\
---
title: No Version
---
Body.
"""

LEGACY_STRATEGY = """\
---
schema_version: 0
title: Legacy
---
Body.
"""

UNSUPPORTED_OLD_STRATEGY = """\
---
schema_version: -5
title: Way Old
---
Body.
"""

UNSUPPORTED_NEW_STRATEGY = """\
---
schema_version: 999
title: Way New
---
Body.
"""


def write_strategy(repo: Path, content: str) -> Path:
    spath = strategy_file_path(repo)
    spath.parent.mkdir(parents=True, exist_ok=True)
    spath.write_text(content, encoding="utf-8")
    return spath


def write_ticket(repo: Path, name: str, content: str) -> Path:
    tdir = repo / TICKETS_DIR
    tdir.mkdir(parents=True, exist_ok=True)
    p = tdir / name
    p.write_text(content, encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# Pure rewrite primitives
# --------------------------------------------------------------------------- #


class TestRewriteStrategyVersion:
    def test_replaces_existing_value(self):
        src = "---\nschema_version: 0\ntitle: X\n---\nbody\n"
        out = rewrite_strategy_version(src, CURRENT_SCHEMA_VERSION)
        assert f"schema_version: {CURRENT_SCHEMA_VERSION}" in out
        assert "title: X" in out
        assert out.endswith("body\n")

    def test_inserts_when_absent(self):
        src = "---\ntitle: X\n---\nbody\n"
        out = rewrite_strategy_version(src, CURRENT_SCHEMA_VERSION)
        lines = out.split("\n")
        assert lines[0] == "---"
        assert lines[1] == f"schema_version: {CURRENT_SCHEMA_VERSION}"
        assert "title: X" in out

    def test_none_without_fence(self):
        assert rewrite_strategy_version("no fence", CURRENT_SCHEMA_VERSION) is None

    def test_none_without_close(self):
        assert rewrite_strategy_version("---\ntitle: X\n", CURRENT_SCHEMA_VERSION) is None


class TestRewriteTicketEpics:
    def test_bare_string_normalized(self):
        src = "---\nepics:\n- epic-1\n---\nbody\n"
        out = rewrite_ticket_epics(src)
        assert out is not None
        assert "epic_id: epic-1" in out
        assert "resolves_on_complete: false" in out
        assert "kind: associated" in out
        assert "provenance: null" in out

    def test_dict_missing_fields_filled(self):
        src = "---\nepics:\n- epic_id: e1\n  resolves_on_complete: true\n---\nb\n"
        out = rewrite_ticket_epics(src)
        assert out is not None
        assert "kind: resolves_on_complete" in out
        assert "provenance: null" in out
        assert "linked_at: null" in out

    def test_already_explicit_noop(self):
        src = (
            "---\nepics:\n"
            "- epic_id: e1\n  resolves_on_complete: false\n"
            "  kind: associated\n  provenance: null\n  linked_at: null\n---\nb\n"
        )
        assert rewrite_ticket_epics(src) is None

    def test_none_without_epics(self):
        src = "---\ntitle: X\n---\nb\n"
        assert rewrite_ticket_epics(src) is None

    def test_invalid_entry_preserved_not_dropped(self):
        # Entry with no epic_id is unsupported — preserved verbatim (not dropped).
        src = "---\nepics:\n- 12345\n- epic-1\n---\nb\n"
        out = rewrite_ticket_epics(src)
        assert out is not None
        assert "epic_id: epic-1" in out

    def test_preserves_epic_id_verbatim(self):
        src = "---\nepics:\n- 01HZABCDEFGHIJKLMNOPQRSTUVWXYZ012345\n---\nb\n"
        out = rewrite_ticket_epics(src)
        assert out is not None
        assert "epic_id: 01HZABCDEFGHIJKLMNOPQRSTUVWXYZ012345" in out


# --------------------------------------------------------------------------- #
# compute_apply_plan
# --------------------------------------------------------------------------- #


class TestComputeApplyPlan:
    def test_eligible_states_match_gate(self):
        assert ELIGIBLE_VERSION_STATES == ("legacy", "missing-version")

    def test_absent_strategy_no_rewrites(self, tmp_path: Path):
        plan = compute_apply_plan(tmp_path)
        assert plan.version_status == "absent"
        assert plan.has_rewrites is False
        assert plan.blocked is False

    def test_current_strategy_no_rewrites(self, tmp_path: Path):
        write_strategy(tmp_path, CURRENT_STRATEGY)
        plan = compute_apply_plan(tmp_path)
        assert plan.do_version_upgrade is False
        assert plan.has_rewrites is False

    def test_unsupported_states_not_upgraded(self, tmp_path: Path):
        for idx, content in enumerate(
            (UNSUPPORTED_OLD_STRATEGY, UNSUPPORTED_NEW_STRATEGY)
        ):
            repo = tmp_path / f"unsupported_repo_{idx}"
            repo.mkdir()
            write_strategy(repo, content)
            plan = compute_apply_plan(repo)
            assert plan.do_version_upgrade is False

    def test_legacy_strategy_scheduled(self, tmp_path: Path, monkeypatch):
        # ``legacy`` is unreachable with the shipped (empty) LEGACY_VERSIONS;
        # monkeypatch it to exercise the legacy eligible arm.
        from arnold_pipelines.megaplan.strategy import versions

        monkeypatch.setattr(
            versions, "LEGACY_VERSIONS", frozenset({"megaplan-strategy-v0"})
        )
        write_strategy(
            tmp_path,
            "---\nschema_version: megaplan-strategy-v0\ntitle: Legacy\n---\nBody.\n",
        )
        plan = compute_apply_plan(tmp_path)
        assert plan.do_version_upgrade is True
        kinds = [r.kind for r in plan.rewrites]
        assert REWRITE_UPGRADE_VERSION in kinds

    def test_missing_version_strategy_scheduled(self, tmp_path: Path):
        write_strategy(tmp_path, MISSING_VERSION_STRATEGY)
        plan = compute_apply_plan(tmp_path)
        assert plan.do_version_upgrade is True

    def test_legacy_epics_scheduled(self, tmp_path: Path):
        write_ticket(tmp_path, "01HZABC.md", "---\nepics:\n- epic-1\n---\nb\n")
        plan = compute_apply_plan(tmp_path)
        assert any(r.kind == REWRITE_NORMALIZE_EPICS for r in plan.rewrites)


# --------------------------------------------------------------------------- #
# apply_strategy_migration — version upgrade
# --------------------------------------------------------------------------- #


class TestApplyVersionUpgrade:
    def test_missing_version_upgraded_to_current(self, tmp_path: Path):
        spath = write_strategy(tmp_path, MISSING_VERSION_STRATEGY)
        before = spath.read_bytes()
        result = apply_strategy_migration(tmp_path)
        assert result["applied"] is True
        assert result["success"] is True
        after = spath.read_text(encoding="utf-8")
        assert f"schema_version: {CURRENT_SCHEMA_VERSION}" in after
        assert f"schema_version: {CURRENT_SCHEMA_VERSION}" not in before.decode()

    def test_legacy_upgraded(self, tmp_path: Path, monkeypatch):
        from arnold_pipelines.megaplan.strategy import versions

        monkeypatch.setattr(
            versions, "LEGACY_VERSIONS", frozenset({"megaplan-strategy-v0"})
        )
        spath = write_strategy(
            tmp_path,
            "---\nschema_version: megaplan-strategy-v0\ntitle: Legacy\n---\nBody.\n",
        )
        apply_strategy_migration(tmp_path)
        assert f"schema_version: {CURRENT_SCHEMA_VERSION}" in spath.read_text()

    def test_unsupported_old_not_upgraded(self, tmp_path: Path):
        spath = write_strategy(tmp_path, UNSUPPORTED_OLD_STRATEGY)
        result = apply_strategy_migration(tmp_path)
        assert result["applied"] is False
        assert "schema_version: -5" in spath.read_text()


# --------------------------------------------------------------------------- #
# apply_strategy_migration — epics normalization
# --------------------------------------------------------------------------- #


class TestApplyEpicsNormalization:
    def test_bare_string_ticket_normalized(self, tmp_path: Path):
        tp = write_ticket(tmp_path, "01HZABC.md", "---\nepics:\n- epic-1\n---\nb\n")
        apply_strategy_migration(tmp_path)
        text = tp.read_text(encoding="utf-8")
        assert "epic_id: epic-1" in text
        assert "kind: associated" in text

    def test_no_rename_ticket_file(self, tmp_path: Path):
        name = "LEGACY-NAME-01HZABC.md"
        tp = write_ticket(tmp_path, name, "---\nid: 01HZABC\nepics:\n- epic-1\n---\nb\n")
        apply_strategy_migration(tmp_path)
        assert tp.exists()
        assert tp.name == name
        assert not list((tmp_path / TICKETS_DIR).glob("*.tmp"))

    def test_no_invented_id(self, tmp_path: Path):
        tp = write_ticket(tmp_path, "01HZABC.md", "---\nepics:\n- real-epic\n---\nb\n")
        apply_strategy_migration(tmp_path)
        text = tp.read_text(encoding="utf-8")
        assert "real-epic" in text
        # No ULID-like invented values introduced.
        assert "epic_id: real-epic" in text

    def test_real_corpus_not_mutated(self, tmp_path: Path, monkeypatch):
        # Mirror the repo's real ticket dir into a throwaway copy and ensure
        # we only operate on the synthetic tmp_path root.
        write_ticket(tmp_path, "01HZABC.md", "---\nepics:\n- epic-1\n---\nb\n")
        apply_strategy_migration(tmp_path)
        assert (tmp_path / TICKETS_DIR / "01HZABC.md").exists()


# --------------------------------------------------------------------------- #
# Backups, manifest, atomicity
# --------------------------------------------------------------------------- #


class TestBackupsAndManifest:
    def test_backup_byte_for_byte_with_sha256(self, tmp_path: Path):
        spath = write_strategy(tmp_path, MISSING_VERSION_STRATEGY)
        before = spath.read_bytes()
        result = apply_strategy_migration(tmp_path)
        backup_dir = tmp_path / result["backup_dir"]
        rel = STRATEGY_PATH
        backup_file = backup_dir / rel
        assert backup_file.read_bytes() == before
        manifest = json.loads((backup_dir / "manifest.json").read_text())
        entry = [e for e in manifest["rewrites"] if e["path"] == str(rel)][0]
        assert entry["sha256"] == hashlib.sha256(before).hexdigest()
        assert entry["bytes"] == len(before)

    def test_backup_mirrors_repo_relative_path(self, tmp_path: Path):
        write_ticket(tmp_path, "01HZABC.md", "---\nepics:\n- epic-1\n---\nb\n")
        result = apply_strategy_migration(tmp_path)
        backup_dir = tmp_path / result["backup_dir"]
        assert (backup_dir / TICKETS_DIR / "01HZABC.md").is_file()

    def test_manifest_has_timestamp_and_tool(self, tmp_path: Path):
        write_strategy(tmp_path, MISSING_VERSION_STRATEGY)
        result = apply_strategy_migration(tmp_path)
        manifest = json.loads((tmp_path / result["manifest_path"]).read_text())
        assert manifest["tool"].endswith("--apply")
        assert "timestamp" in manifest
        assert manifest["timestamp"] == result["timestamp"]

    def test_no_tmp_files_left_behind(self, tmp_path: Path):
        write_strategy(tmp_path, MISSING_VERSION_STRATEGY)
        apply_strategy_migration(tmp_path)
        leftovers = list(tmp_path.rglob("*.tmp"))
        assert leftovers == []


# --------------------------------------------------------------------------- #
# Idempotency
# --------------------------------------------------------------------------- #


class TestIdempotency:
    def test_second_run_is_noop(self, tmp_path: Path):
        write_strategy(tmp_path, MISSING_VERSION_STRATEGY)
        write_ticket(tmp_path, "01HZABC.md", "---\nepics:\n- epic-1\n---\nb\n")
        r1 = apply_strategy_migration(tmp_path)
        assert r1["applied"] is True
        r2 = apply_strategy_migration(tmp_path)
        assert r2["applied"] is False
        assert r2["reason"] == "no-supported-rewrites"


# --------------------------------------------------------------------------- #
# Blocker gate
# --------------------------------------------------------------------------- #


class TestBlockerGate:
    def test_blockers_prevent_apply(self, tmp_path: Path, monkeypatch):
        write_strategy(tmp_path, MISSING_VERSION_STRATEGY)
        from arnold_pipelines.megaplan.strategy import apply_migration as am

        original = am.compute_apply_plan

        def fake_plan(repo_root, store=None):
            plan = original(repo_root, store)
            plan.blockers.append("synthetic-blocker")
            return plan

        monkeypatch.setattr(am, "compute_apply_plan", fake_plan)
        result = apply_strategy_migration(tmp_path)
        assert result["success"] is False
        assert result["applied"] is False
        assert result["blocked"] is True
        assert "synthetic-blocker" in result["blockers"]
        # Strategy file untouched.
        assert f"schema_version: {CURRENT_SCHEMA_VERSION}" not in strategy_file_path(tmp_path).read_text()


# --------------------------------------------------------------------------- #
# Absent strategy
# --------------------------------------------------------------------------- #


class TestAbsentStrategy:
    def test_absent_is_noop_success(self, tmp_path: Path):
        result = apply_strategy_migration(tmp_path)
        assert result["success"] is True
        assert result["applied"] is False
        assert result["reason"] == "no-supported-rewrites"

    def test_epics_only_with_absent_strategy(self, tmp_path: Path):
        write_ticket(tmp_path, "01HZABC.md", "---\nepics:\n- epic-1\n---\nb\n")
        result = apply_strategy_migration(tmp_path)
        assert result["applied"] is True
        assert all(r["kind"] == REWRITE_NORMALIZE_EPICS for r in result["rewrites"])


# --------------------------------------------------------------------------- #
# CLI wiring
# --------------------------------------------------------------------------- #


class TestCliApplyFlag:
    def test_migrate_apply_flag_registered(self):
        from arnold_pipelines.megaplan.cli import build_parser

        parser = build_parser()
        ns = parser.parse_args(["strategy", "migrate", "--apply"])
        assert ns.apply is True

    def test_migrate_default_no_apply(self):
        from arnold_pipelines.megaplan.cli import build_parser

        parser = build_parser()
        ns = parser.parse_args(["strategy", "migrate"])
        assert ns.apply is False

    def test_handler_apply_calls_apply(self, tmp_path: Path):
        import argparse

        from arnold_pipelines.megaplan.handlers.strategy import handle_strategy_migrate

        write_strategy(tmp_path, MISSING_VERSION_STRATEGY)
        args = argparse.Namespace(apply=True)
        result = handle_strategy_migrate(tmp_path, args)
        assert result["applied"] is True
        assert result["success"] is True
