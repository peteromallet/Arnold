"""Focused T6.3 negative-authority suite: observation cannot escalate.

Two evidence layers over ``ResidentJobHandlers.handle_daily_observation``:

* STATIC import/call-graph proof — the handler subgraph reaches exactly ONE
  T2.1 claim function (``ScheduleService.claim_superfixer_occurrence``), its
  only write is the single fence+token CAS-guarded custody release, its lazy
  imports are limited to schedule reads and the T6.2 runner seam, and NO
  ticket, repair-dispatch, provider/model-routing, schedule-definition, or
  authority-receipt writer is reachable.  The T2.1 module itself still
  exposes exactly two claim methods — this card added none.
* RUNTIME spies and byte snapshots — canonical M5 writer tripwires stay
  silent through every scenario, schedule definitions/heads are
  byte-identical across all paths, and an active Astrid/maintenance chain
  fixture remains byte-for-byte unchanged while every negative scenario
  runs against disposable runtime roots proven quarantined from live roots.

Behavioral coverage lives in
``tests/resident/test_daily_observation_handler.py``.
"""

from __future__ import annotations

import ast
import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.maintenance import efficiency_reporting as er
from arnold_pipelines.megaplan.maintenance import operational_reporting as opr
from arnold_pipelines.megaplan.resident import scheduler as scheduler_module
from arnold_pipelines.megaplan.resident import schedules as schedules_module
from tests.resident.test_daily_observation_handler import (
    Fixture,
    RecordingRunner,
    _disposable_root,
    _fixture,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Live/candidate runtime roots the suite must never touch.
_FORBIDDEN_LIVE_ROOTS = (
    _PROJECT_ROOT,
    _PROJECT_ROOT / ".megaplan",
    Path.home() / "Documents" / "Astrid",
    Path("/workspace"),
)


# ---------------------------------------------------------------------------
# Static call-graph extraction
# ---------------------------------------------------------------------------


def _scheduler_tree() -> ast.Module:
    return ast.parse(
        Path(scheduler_module.__file__).read_text(encoding="utf-8"),
        filename=str(scheduler_module.__file__),
    )


def _schedules_tree() -> ast.Module:
    return ast.parse(
        Path(schedules_module.__file__).read_text(encoding="utf-8"),
        filename=str(schedules_module.__file__),
    )


def _top_level_functions(tree: ast.Module) -> dict[str, ast.AST]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _class_methods(tree: ast.Module, class_name: str) -> dict[str, ast.AST]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                item.name: item
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
    raise AssertionError(f"class {class_name} not found")


def _call_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            if isinstance(sub.func, ast.Attribute):
                names.add(sub.func.attr)
            elif isinstance(sub.func, ast.Name):
                names.add(sub.func.id)
    return names


def _daily_observation_subgraph() -> tuple[set[str], dict[str, ast.AST]]:
    """Names callable from handle_daily_observation + the reachable defs."""
    methods = _class_methods(_scheduler_tree(), "ResidentJobHandlers")
    functions = _top_level_functions(_scheduler_tree())
    reachable_defs: dict[str, ast.AST] = {}
    frontier = ["handle_daily_observation"]
    seen: set[str] = set()
    while frontier:
        name = frontier.pop()
        if name in seen:
            continue
        seen.add(name)
        node = methods.get(name) or functions.get(name)
        if node is None:
            continue
        reachable_defs[name] = node
        for called in _call_names(node):
            if called in methods or called in functions:
                frontier.append(called)
    called_names: set[str] = set()
    for node in reachable_defs.values():
        called_names |= _call_names(node)
    return called_names, reachable_defs


# Forbidden authority families: none of these identifiers may appear as a
# called function/method anywhere in the handler subgraph.
FORBIDDEN_AUTHORITIES: dict[str, frozenset[str]] = {
    "ticket": frozenset(
        {
            "create_ticket", "update_ticket", "edit_ticket", "address_ticket",
            "link_ticket", "unlink_ticket", "resolve_ticket", "ticket_new",
            "TicketInput",
        }
    ),
    "repair_dispatch": frozenset(
        {
            "dispatch_repair", "claim_repair", "enqueue_repair", "simple_fixer",
            "SimpleFixerOccurrence", "repair_lock", "repair_requests",
            "claim_singleton_occurrence",
        }
    ),
    "provider_model_routing": frozenset(
        {
            "launch_subagent_task", "launch_superfixer_proactive_managed",
            "launch_managed_subagent_detached", "provider_runtime",
            "reroute_model", "select_model", "model_spec",
        }
    ),
    "schedule_definition_mutation": frozenset(
        {
            "create", "revise", "set_state", "materialize", "_exhaust",
            "_insert_occurrence", "replay", "ingest_event",
            "record_superfixer_single_shot",
        }
    ),
    "receipt_writer": frozenset(
        {
            "_append", "_atomic", "_transition_unlocked", "transition_path_write",
            "append_maintenance_event", "emit_daily_events", "emit_daily_report",
            "append_operational_report", "log_system_event",
            "create_scheduled_job", "update_scheduled_job", "create_message",
            "upsert_resident_conversation", "create_cloud_run",
            "update_cloud_run",
        }
    ),
}


# ---------------------------------------------------------------------------
# Static: one T2.1 claim function, nothing else
# ---------------------------------------------------------------------------


def test_handler_subgraph_uses_exactly_one_t21_claim_function() -> None:
    called, _defs = _daily_observation_subgraph()
    # Exactly one claim seam is reachable, and it is the T2.1 one-shot CAS.
    claim_reach = {name for name in called if name.startswith("claim")}
    assert claim_reach == {"claim_superfixer_occurrence"}, sorted(claim_reach)
    # The resident module defines no new claim authority of its own: the
    # two claim-custody helpers are thin wrappers that delegate to the
    # T2.1 CAS.  (``claim_due_jobs`` is the legacy store JOB-queue claimer,
    # not schedule custody; it predates this card and claims no occurrence.)
    tree = _scheduler_tree()
    custody_claims: list[str] = []
    legacy_job_claims: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        name = node.name
        if name.startswith("claim_due"):
            legacy_job_claims.append(name)
            continue
        if "claim" not in name:
            continue
        custody_claims.append(name)
        assert "claim_superfixer_occurrence" in _call_names(node), (
            f"{name} does not delegate to the T2.1 claim CAS"
        )
    assert sorted(custody_claims) == [
        "_claim_daily_observation",
        "_claim_superfixer_occurrence",
    ]
    assert set(legacy_job_claims) == {"claim_due_jobs"}


def test_schedules_module_claim_surface_is_exactly_the_two_t21_functions() -> None:
    """T6.3 added NO third claim method to the authoritative service."""
    service_methods = _class_methods(_schedules_tree(), "ScheduleService")
    claim_api = {name for name in service_methods if name.startswith("claim")}
    assert claim_api == {"claim", "claim_superfixer_occurrence"}
    repo_methods = _class_methods(_schedules_tree(), "ScheduleRepository")
    assert {name for name in repo_methods if name.startswith("claim")} == set()


# ---------------------------------------------------------------------------
# Static: no forbidden authority is reachable; the one write is CAS-guarded
# ---------------------------------------------------------------------------


def test_handler_subgraph_reaches_no_forbidden_authority() -> None:
    called, _defs = _daily_observation_subgraph()
    for family, forbidden in FORBIDDEN_AUTHORITIES.items():
        reached = called & forbidden
        assert not reached, f"{family} authority reachable: {sorted(reached)}"


def test_handler_single_write_is_the_cas_guarded_custody_release() -> None:
    """The ONLY state write in the subgraph is the fence+token CAS release."""
    _called, defs = _daily_observation_subgraph()
    transition_calls: list[ast.Call] = []
    for node in defs.values():
        for sub in ast.walk(node):
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == "transition"
            ):
                transition_calls.append(sub)
    assert len(transition_calls) == 1, "handler must perform exactly one transition"
    keywords = {kw.arg for kw in transition_calls[0].keywords}
    assert {"expected_fence", "expected_token"} <= keywords, (
        "custody release must be CAS-guarded by expected_fence and expected_token"
    )
    call_text = ast.dump(transition_calls[0])
    assert "daily_observation_completed" in call_text


def test_handler_lazy_imports_are_limited_to_reads_and_runner_seam() -> None:
    _called, defs = _daily_observation_subgraph()
    imported_modules: set[str] = set()
    for node in defs.values():
        for sub in ast.walk(node):
            if isinstance(sub, ast.ImportFrom):
                imported_modules.add("." * sub.level + (sub.module or ""))
            elif isinstance(sub, ast.Import):
                for alias in sub.names:
                    imported_modules.add(alias.name)
    assert imported_modules == {".schedules", "importlib"}

    # The runner seam stays lazy: no eager import of the maintenance package
    # or the T6.2 runner anywhere in the resident scheduler module imports.
    tree = _scheduler_tree()
    for node in ast.walk(tree):
        modules = []
        if isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        for module in modules:
            assert "maintenance" not in module, f"eager maintenance import: {module}"
            assert "daily_runner" not in module, f"eager runner import: {module}"


def test_runner_seam_constants_name_the_t62_contract() -> None:
    """ONE module, ONE entry point: the single integration adaptation point."""
    assert scheduler_module.DAILY_RUNNER_MODULE == (
        "arnold_pipelines.megaplan.maintenance.daily_runner"
    )
    assert scheduler_module.DAILY_RUNNER_ENTRYPOINT == "run_daily_efficiency"
    source = Path(scheduler_module.__file__).read_text(encoding="utf-8")
    assert "importlib.import_module" in source  # resolved by import, never re-implemented


# ---------------------------------------------------------------------------
# Runtime: M5 writer tripwires stay silent through every scenario
# ---------------------------------------------------------------------------


def test_m5_writer_tripwires_stay_silent_through_full_handoff(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold_pipelines.megaplan.maintenance.ledger import MaintenanceLedger

    def _tripwire(*_args, **_kwargs):
        raise AssertionError("canonical M5 writer reached from the observer handoff")

    monkeypatch.setattr(MaintenanceLedger, "append", _tripwire)
    monkeypatch.setattr(er, "emit_daily_events", _tripwire)
    monkeypatch.setattr(opr, "append_operational_report", _tripwire)

    fixture = _fixture(tmp_path)
    handlers = fixture.handlers(RecordingRunner())

    asyncio.run(handlers.handle_daily_observation(fixture.payload))  # success
    fixture.settle()
    asyncio.run(handlers.handle_daily_observation(fixture.payload))  # terminal replay

    # A fresh occurrence exercises the failing-runner leg: the failure
    # propagates and the M5 writers still stay silent.
    retryable = _fixture(tmp_path, schedule_id="sched_neg_tripwire_failure")
    failing = retryable.handlers(RecordingRunner(error=RuntimeError("boom")))
    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(failing.handle_daily_observation(retryable.payload))


def _tree_digest(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_schedule_definitions_and_heads_byte_identical_across_all_paths(tmp_path) -> None:
    fixture = _fixture(tmp_path)
    store_root = fixture.root / "store"

    def protected_digests() -> dict[str, str]:
        digest: dict[str, str] = {}
        for section in ("definitions", "heads", "idempotency"):
            base = store_root / "schedules" / section
            if base.exists():
                digest.update(
                    {
                        f"{section}/{path.relative_to(base)}": hashlib.sha256(
                            path.read_bytes()
                        ).hexdigest()
                        for path in sorted(base.rglob("*"))
                        if path.is_file()
                    }
                )
        return digest

    before = protected_digests()

    happy = RecordingRunner()
    asyncio.run(fixture.handlers(happy).handle_daily_observation(fixture.payload))
    failing = RecordingRunner(error=RuntimeError("boom"))
    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(
            fixture.handlers(failing).handle_daily_observation(fixture.payload)
        )

    assert protected_digests() == before
    # No non-launch receipt channel appeared either.
    assert not (store_root / "schedules" / "superfixer-singleshots.jsonl").exists()


# ---------------------------------------------------------------------------
# Runtime: active Astrid / maintenance chain fixtures stay byte-identical
# ---------------------------------------------------------------------------


def _seed_active_chain_fixture(root: Path) -> Path:
    """A representative ACTIVE chain fixture set inside a disposable root."""
    initiative = root / ".megaplan" / "initiatives" / "demo-chain"
    initiative.mkdir(parents=True)
    (initiative / "chain.yaml").write_text(
        "driver:\n  require_anchor: true\nmilestones:\n"
        "  - label: m1-observation\n    title: Daily observation\n",
        encoding="utf-8",
    )
    (initiative / "NORTHSTAR.md").write_text(
        "# North Star\n\nObserve without escalating.\n", encoding="utf-8"
    )
    plans = initiative / "plans"
    plans.mkdir()
    (plans / "demo-plan.md").write_text(
        "---\nname: demo-plan\nstate: executing\n---\n\n## Step 1\nDo the work.\n",
        encoding="utf-8",
    )
    ledger_dir = root / "incident-ledger"
    ledger_dir.mkdir()
    events = [
        {"kind": "operational_report", "seq": 1, "digest": "a" * 64},
        {"kind": "checkpoint_verification", "seq": 2, "digest": "b" * 64},
    ]
    (ledger_dir / "events.jsonl").write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )
    return root


def test_active_chain_fixture_bytes_unchanged_across_every_negative_scenario(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain_root = _seed_active_chain_fixture(_disposable_root(tmp_path / "chain"))
    before = _tree_digest(chain_root)

    monkeypatch.chdir(tmp_path)  # even cwd drift cannot reach live roots

    # Every scenario class from the handler suite, against fresh runtime
    # roots under tmp_path, with the chain fixture sitting untouched beside
    # them.
    success = _fixture(tmp_path, schedule_id="sched_neg_success")
    runner = RecordingRunner()
    asyncio.run(success.handlers(runner).handle_daily_observation(success.payload))
    success.settle()

    missing = _fixture(tmp_path, schedule_id="sched_neg_missing")
    corrupted = json.loads(json.dumps(missing.payload))
    corrupted["payload"].pop("schedule_owned")
    missing.persist_payload(corrupted["payload"])
    with pytest.raises(ValueError, match="daily_observation"):
        asyncio.run(
            missing.handlers(RecordingRunner()).handle_daily_observation(
                missing.payload
            )
        )

    foreign = _fixture(tmp_path, schedule_id="sched_neg_foreign")
    other = Fixture(tmp_path, schedule_id="sched_neg_other")
    tampered = json.loads(json.dumps(foreign.payload))
    context = other.payload["payload"]["schedule_occurrence"]
    tampered["payload"]["schedule_occurrence"] = dict(context)
    tampered["payload"]["recurrence_owner"] = other.definition.schedule_id
    foreign.persist_payload(tampered["payload"])
    with pytest.raises(RuntimeError, match="not bound to job"):
        asyncio.run(
            foreign.handlers(RecordingRunner()).handle_daily_observation(
                foreign.payload
            )
        )

    failing = _fixture(tmp_path, schedule_id="sched_neg_failure")
    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(
            failing.handlers(RecordingRunner(error=RuntimeError("boom"))).handle_daily_observation(
                failing.payload
            )
        )
    assert failing.projection_now().state == "claimed"  # retained, retryable

    assert _tree_digest(chain_root) == before  # BYTE-FOR-BYTE unchanged


def test_disposable_roots_are_quarantined_from_live_runtime_roots(tmp_path) -> None:
    """Every root this suite writes into is provably outside the live world."""
    fixture_root = _disposable_root(tmp_path)
    chain_root = _seed_active_chain_fixture(_disposable_root(tmp_path / "chain"))
    for candidate in (fixture_root, chain_root, tmp_path.resolve()):
        for live in _FORBIDDEN_LIVE_ROOTS:
            if live.exists():
                assert not candidate.is_relative_to(live), (
                    f"{candidate} lives inside live root {live}"
                )
                assert not live.is_relative_to(candidate), (
                    f"live root {live} lives inside {candidate}"
                )
        assert ".megaplan-worktrees" not in candidate.parts
        assert "runtime-candidates" not in candidate.parts


