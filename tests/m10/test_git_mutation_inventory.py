"""Step 13E1 / 13E7 / 13E9 — Git mutation sink inventory gate (T24).

Validates ``evidence/m10-git-mutation-sinks.json``:

- 13E1: every one of the nine listed Git mutation modules is inventoried, and
  the static AST scanner finds no *unlisted* sink (completeness).
- 13E1: no inventory row is *stale* (its source anchor no longer matches the
  scanned source) and no inventory row references a sink the scanner no longer
  detects (phantom row).
- 13E7 (overflow gate): every mutating row carries a disposition in
  ``{migrated, action_off}``; no single numbered shard exceeds three
  ``migrated`` rows.
- 13E9: the six bake-off / CLI action-off rows carry owner, reason, expiry,
  source anchor, and a bypass-test id; all are disposition ``action_off``.
"""

from __future__ import annotations

import json
import os

import pytest

from tests.m10.git_sink_scanner import MODULES, scan_all

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
INVENTORY_PATH = os.path.join(REPO_ROOT, "evidence", "m10-git-mutation-sinks.json")

ACTION_OFF_MODULES = {
    "arnold_pipelines/megaplan/bakeoff/worktree.py",
    "arnold_pipelines/megaplan/bakeoff/merge.py",
    "arnold_pipelines/megaplan/cli/__init__.py",
}

REQUIRED_ROW_FIELDS = (
    "sink_id", "module", "enclosing_function", "def_line", "call_line",
    "subcommands", "effect_family", "destructive_level", "disposition",
    "global_effect_key_recipe", "source_anchor", "owner", "reason", "expiry",
    "bypass_test_id", "overflow_shard",
)


@pytest.fixture(scope="module")
def inventory() -> dict:
    with open(INVENTORY_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def scanned_sink_ids() -> set[str]:
    return {s.sink_id for s in scan_all()}


@pytest.fixture(scope="module")
def scanned_anchors() -> dict[str, str]:
    return {s.sink_id: s.source_anchor for s in scan_all()}


# ── 13E1: module coverage ───────────────────────────────────────────────────


class TestModuleCoverage:
    def test_all_nine_modules_listed(self, inventory: dict) -> None:
        listed = set(inventory["modules_inventoried"])
        assert listed == set(MODULES.values())

    def test_module_sink_index_covers_every_inventoried_module(
        self, inventory: dict
    ) -> None:
        index = inventory["module_sink_index"]
        for mod in inventory["modules_inventoried"]:
            assert mod in index, f"module {mod!r} missing from module_sink_index"


# ── 13E1: completeness (no unlisted sink) & no phantom / stale rows ─────────


class TestCompletenessAndFreshness:
    def test_no_unlisted_sink(self, inventory: dict, scanned_sink_ids: set) -> None:
        listed = {row["sink_id"] for row in inventory["sinks"]}
        missing = scanned_sink_ids - listed
        assert not missing, f"unlisted Git mutation sinks: {sorted(missing)}"

    def test_no_phantom_row(self, inventory: dict, scanned_sink_ids: set) -> None:
        listed = {row["sink_id"] for row in inventory["sinks"]}
        phantom = listed - scanned_sink_ids
        assert not phantom, (
            "inventory references sinks the scanner no longer detects "
            f"(stale inventory): {sorted(phantom)}"
        )

    def test_no_stale_anchor(self, inventory: dict, scanned_anchors: dict) -> None:
        stale = []
        for row in inventory["sinks"]:
            sid = row["sink_id"]
            if sid in scanned_anchors and row["source_anchor"] != scanned_anchors[sid]:
                stale.append(sid)
        assert not stale, f"stale source anchors: {sorted(stale)}"

    def test_every_row_has_required_fields(self, inventory: dict) -> None:
        for row in inventory["sinks"]:
            missing = [f for f in REQUIRED_ROW_FIELDS if f not in row]
            assert not missing, f"row {row.get('sink_id')!r} missing fields {missing}"


# ── 13E7: overflow gate ─────────────────────────────────────────────────────


class TestOverflowGate:
    def test_every_row_has_valid_disposition(self, inventory: dict) -> None:
        valid = {"migrated", "action_off"}
        for row in inventory["sinks"]:
            assert row["disposition"] in valid, (
                f"row {row['sink_id']!r} disposition {row['disposition']!r} not in {valid}"
            )

    def test_no_shard_exceeds_three_migrated_rows(self, inventory: dict) -> None:
        per_shard: dict[str, int] = {}
        for row in inventory["sinks"]:
            if row["disposition"] == "migrated":
                per_shard[row["overflow_shard"]] = (
                    per_shard.get(row["overflow_shard"], 0) + 1
                )
        for shard, count in per_shard.items():
            assert count <= 3, (
                f"overflow: shard {shard!r} migrated {count} rows (> 3 limit)"
            )

    def test_m10_baseline_is_all_action_off(self, inventory: dict) -> None:
        """SD3: production Git effects remain action-off throughout M10."""
        for row in inventory["sinks"]:
            assert row["disposition"] == "action_off", (
                f"row {row['sink_id']!r} is not action_off in M10 baseline"
            )


# ── 13E9: bake-off / CLI action-off rows ────────────────────────────────────


class TestActionOffRows:
    @pytest.fixture(scope="module")
    def action_off_rows(self, inventory: dict) -> list[dict]:
        return [r for r in inventory["sinks"] if r["module"] in ACTION_OFF_MODULES]

    def test_exactly_six_action_off_rows(self, action_off_rows: list) -> None:
        # Step 13E9 names six bake-off/CLI sinks.
        assert len(action_off_rows) == 6, (
            f"expected 6 bake-off/CLI action-off rows, got {len(action_off_rows)}"
        )

    @pytest.mark.parametrize(
        "field",
        ["owner", "reason", "expiry", "source_anchor", "bypass_test_id"],
    )
    def test_action_off_rows_carry_required_metadata(
        self, action_off_rows: list, field: str
    ) -> None:
        for row in action_off_rows:
            assert row.get(field), (
                f"action-off row {row['sink_id']!r} missing non-empty {field!r}"
            )

    def test_action_off_rows_are_disposition_action_off(
        self, action_off_rows: list
    ) -> None:
        for row in action_off_rows:
            assert row["disposition"] == "action_off"

    def test_action_off_rows_reference_expected_functions(
        self, action_off_rows: list
    ) -> None:
        funcs = {r["enclosing_function"] for r in action_off_rows}
        expected = {
            "create_named_worktree", "create_worktree", "remove_worktree",
            "_apply_patch", "_git_apply", "_reset_chain_worktree_target",
        }
        assert funcs == expected, f"unexpected action-off functions: {funcs ^ expected}"

    def test_bypass_test_ids_are_unique(self, action_off_rows: list) -> None:
        ids = [r["bypass_test_id"] for r in action_off_rows]
        assert len(ids) == len(set(ids)), "duplicate bypass_test_ids"


# ── Generator / scanner consistency ─────────────────────────────────────────


class TestScannerConsistency:
    def test_scanned_count_matches_inventory(self, inventory: dict, scanned_sink_ids: set) -> None:
        listed = {row["sink_id"] for row in inventory["sinks"]}
        assert listed == scanned_sink_ids

    def test_module_sink_index_matches_rows(self, inventory: dict) -> None:
        index = inventory["module_sink_index"]
        for mod, sids in index.items():
            row_sids = {
                r["sink_id"] for r in inventory["sinks"] if r["module"] == mod
            }
            assert set(sids) == row_sids, f"index mismatch for module {mod!r}"
