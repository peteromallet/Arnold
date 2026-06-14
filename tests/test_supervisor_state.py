from __future__ import annotations

from pathlib import Path

import pytest

from arnold.pipelines.megaplan.run_outcome import RunOutcome
from arnold.pipelines.megaplan.supervisor.model import (
    BakeoffParallelGroup,
    DependencyAssertion,
    RunNode,
    RunRecord,
    SupervisorState,
    SupervisorVariantKind,
    dependency_assertions_for_nodes,
)
from arnold.pipelines.megaplan.supervisor.state import (
    load_supervisor_state,
    save_supervisor_state,
    supervisor_state_path,
    supervisor_state_root,
    validate_supervisor_state,
)
from arnold.pipelines.megaplan.types import CliError


def _chain_state(*, depends_on: tuple[str, ...] = ("seed",)) -> SupervisorState:
    return SupervisorState(
        variant=SupervisorVariantKind.CHAIN,
        run_nodes=[
            RunNode(node_id="seed", spec_ref="seed"),
            RunNode(node_id="m1", spec_ref="milestone:m1"),
        ],
        dependency_assertions=[
            DependencyAssertion(node_id="m1", depends_on=depends_on),
        ],
        run_records=[
            RunRecord(node_id="seed", attempt=1, outcome=RunOutcome.SUCCEEDED),
        ],
        current_node_id="m1",
        completed_node_ids=["seed"],
        metadata={"source": "test"},
    )


def test_load_supervisor_state_returns_none_when_missing(tmp_path: Path) -> None:
    assert load_supervisor_state(tmp_path, "chain-spec.yaml") is None


def test_save_supervisor_state_creates_directory_and_round_trips(tmp_path: Path) -> None:
    state = _chain_state()

    saved_path = save_supervisor_state(tmp_path, "chain-spec.yaml", state)

    assert saved_path.parent == supervisor_state_root(tmp_path)
    assert saved_path.exists()
    assert saved_path.parent.exists()
    assert load_supervisor_state(tmp_path, "chain-spec.yaml") == state


def test_save_supervisor_state_uses_atomic_write_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _chain_state()
    captured: dict[str, object] = {}

    def _fake_atomic_write_json(path: Path, data: object) -> None:
        captured["path"] = path
        captured["data"] = data
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr("arnold.pipelines.megaplan.supervisor.state.atomic_write_json", _fake_atomic_write_json)

    saved_path = save_supervisor_state(tmp_path, "chain-spec.yaml", state)

    assert saved_path == captured["path"]
    assert captured["data"] == state.to_dict()


def test_save_supervisor_state_rejects_chain_dependency_on_later_node(
    tmp_path: Path,
) -> None:
    state = _chain_state(depends_on=("m1",))

    with pytest.raises(CliError, match="earlier nodes"):
        save_supervisor_state(tmp_path, "chain-spec.yaml", state)


def test_save_supervisor_state_rejects_unknown_dependency(tmp_path: Path) -> None:
    state = _chain_state(depends_on=("ghost",))

    with pytest.raises(CliError, match="unknown node"):
        save_supervisor_state(tmp_path, "chain-spec.yaml", state)


def test_validate_supervisor_state_accepts_chain_dependency_on_earlier_node() -> None:
    validate_supervisor_state(_chain_state())


def test_validate_supervisor_state_rejects_unknown_dependency_assertion_node() -> None:
    state = _chain_state()
    state.dependency_assertions.append(
        DependencyAssertion(node_id="ghost", depends_on=("seed",))
    )

    with pytest.raises(CliError, match="references unknown node 'ghost'"):
        validate_supervisor_state(state)


def test_bakeoff_state_allows_non_serial_dependency_order(tmp_path: Path) -> None:
    state = SupervisorState(
        variant=SupervisorVariantKind.BAKEOFF,
        run_nodes=[
            RunNode(node_id="left", spec_ref="profile:left"),
            RunNode(node_id="right", spec_ref="profile:right"),
        ],
        dependency_assertions=[
            DependencyAssertion(node_id="left", depends_on=("right",)),
        ],
    )

    save_supervisor_state(tmp_path, "bakeoff-run", state)

    assert load_supervisor_state(tmp_path, "bakeoff-run") == state


def test_bakeoff_state_round_trips_parallel_group_shape(tmp_path: Path) -> None:
    state = SupervisorState(
        variant=SupervisorVariantKind.BAKEOFF,
        run_nodes=[
            RunNode(node_id="alpha", spec_ref="profile:alpha", parallel_group_id="g1"),
            RunNode(node_id="beta", spec_ref="profile:beta", parallel_group_id="g1"),
            RunNode(node_id="compare", spec_ref="compare:g1"),
        ],
        dependency_assertions=[
            DependencyAssertion(node_id="compare", depends_on=("alpha", "beta")),
        ],
        run_records=[
            RunRecord(
                node_id="alpha",
                attempt=1,
                outcome=RunOutcome.SUCCEEDED,
                current_state="done",
                resume_cursor={"phase": "execute"},
            ),
        ],
        bakeoff_parallel_groups=[
            BakeoffParallelGroup(
                group_id="g1",
                member_node_ids=("alpha", "beta"),
                comparison_node_id="compare",
                selection_node_id="winner",
                merge_node_id="merge",
            )
        ],
        current_node_id="compare",
        completed_node_ids=["alpha", "beta"],
    )

    save_supervisor_state(tmp_path, "bakeoff-run", state)

    loaded = load_supervisor_state(tmp_path, "bakeoff-run")
    assert loaded == state
    assert loaded is not None
    assert loaded.bakeoff_parallel_groups[0].to_dict() == {
        "group_id": "g1",
        "member_node_ids": ["alpha", "beta"],
        "comparison_node_id": "compare",
        "selection_node_id": "winner",
        "merge_node_id": "merge",
    }


def test_load_supervisor_state_rejects_invalid_json(tmp_path: Path) -> None:
    state_path = supervisor_state_path(tmp_path, "chain-spec.yaml")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(CliError, match="invalid JSON"):
        load_supervisor_state(tmp_path, "chain-spec.yaml")


def test_dependency_assertions_for_nodes_projects_metadata_dependencies() -> None:
    nodes = [
        RunNode(node_id="seed", spec_ref="seed"),
        RunNode(
            node_id="m1",
            spec_ref="milestone:m1",
            metadata={"depends_on": ["seed", "", 3]},
        ),
        RunNode(
            node_id="m2",
            spec_ref="milestone:m2",
            metadata={"depends_on": "m1"},
        ),
    ]

    assert dependency_assertions_for_nodes(nodes) == [
        DependencyAssertion(node_id="seed", depends_on=()),
        DependencyAssertion(node_id="m1", depends_on=("seed",)),
        DependencyAssertion(node_id="m2", depends_on=("m1",)),
    ]


def test_supervisor_state_path_is_stable_for_same_id(tmp_path: Path) -> None:
    first = supervisor_state_path(tmp_path, "chain-spec.yaml")
    second = supervisor_state_path(tmp_path, "chain-spec.yaml")

    assert first == second
