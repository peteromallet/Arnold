"""Tests for native routing-purity validation."""

from __future__ import annotations

import datetime
import importlib
import inspect
import io
import os
import random
import secrets
import shutil
import socket
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path

import httpx
import requests

from arnold.pipeline.native import (
    NativeInstruction,
    NativeProgram,
    decision,
    phase,
    validate_decision_body,
    validate_pipeline_purity,
)


def _decision_program(*funcs, name: str = "demo", routing_topology: dict | None = None) -> NativeProgram:
    instructions = []
    for pc, func in enumerate(funcs):
        instructions.append(
            NativeInstruction(
                pc=pc,
                op="decision",
                name=getattr(func, "__decision_name__", func.__name__),
                func=func,
                branches={"yes": pc + 1},
            )
        )
    instructions.append(NativeInstruction(pc=len(funcs), op="halt"))
    return NativeProgram(
        name=name,
        instructions=tuple(instructions),
        routing_topology=routing_topology or {},
    )


def test_validate_decision_body_allows_routing_over_recorded_state() -> None:
    @decision(name="route_on_state")
    def route_on_state(ctx: dict) -> str:
        retries = ctx["state"].get("retries", 0)
        return "retry" if retries < 2 else "done"

    diagnostics = validate_decision_body(route_on_state, program_name="demo")

    assert diagnostics == []


def test_validate_decision_body_reports_line_specific_nondeterminism() -> None:
    @decision(name="route_with_random")
    def route_with_random(ctx: dict) -> str:
        coin = random.random()
        return "left" if coin < 0.5 else "right"

    diagnostics = validate_decision_body(route_with_random, program_name="demo")

    assert [diag.code for diag in diagnostics] == ["routing.nondeterministic_call"]
    expected_line = inspect.getsourcelines(route_with_random)[1] + 2
    assert diagnostics[0].line == expected_line
    assert diagnostics[0].decision == "route_with_random"
    assert diagnostics[0].recommendation == "Move live work into a step and route on recorded outputs."


def test_validate_decision_body_rejects_io_network_subprocess_and_dynamic_dispatch() -> None:
    @decision
    def does_io(ctx: dict) -> str:
        Path("x.txt").read_text()
        return "done"

    @decision
    def does_network(ctx: dict) -> str:
        urllib.request.urlopen("https://example.com")
        return "done"

    @decision
    def does_subprocess(ctx: dict) -> str:
        subprocess.run(["echo", "hi"], check=False)
        return "done"

    @decision
    def does_dynamic(ctx: dict) -> str:
        getattr(ctx, "keys")
        return "done"

    assert [diag.code for diag in validate_decision_body(does_io)] == ["routing.io_call"]
    assert [diag.code for diag in validate_decision_body(does_network)] == ["routing.network_call"]
    assert [diag.code for diag in validate_decision_body(does_subprocess)] == ["routing.subprocess_call"]
    assert [diag.code for diag in validate_decision_body(does_dynamic)] == ["routing.dynamic_dispatch"]


def test_validate_decision_body_rejects_routing_owned_state_mutation() -> None:
    @decision
    def mutates_route(ctx: dict) -> str:
        ctx["state"]["next_step"] = "shadow-route"
        return "done"

    diagnostics = validate_decision_body(mutates_route)

    assert [diag.code for diag in diagnostics] == ["routing.state_mutation"]
    assert "next_step" in diagnostics[0].message


def test_validate_pipeline_purity_ignores_phase_bodies() -> None:
    @phase
    def impure_step(ctx: dict) -> dict:
        socket.socket()
        return {"ok": True}

    program = NativeProgram(
        name="phase_only",
        instructions=(
            NativeInstruction(pc=0, op="phase", name="impure_step", func=impure_step, next_pc=1),
            NativeInstruction(pc=1, op="halt"),
        ),
    )

    report = validate_pipeline_purity(program)

    assert report.ok


def test_validate_pipeline_purity_recurses_into_subpipelines() -> None:
    @decision
    def child_route(ctx: dict) -> str:
        random.random()
        return "done"

    child = _decision_program(child_route, name="child")
    parent = NativeProgram(
        name="parent",
        instructions=(
            NativeInstruction(pc=0, op="subpipeline", name="child", subprogram=child, next_pc=1),
            NativeInstruction(pc=1, op="halt"),
        ),
    )

    report = validate_pipeline_purity(parent)

    assert [diag.program for diag in report.diagnostics] == ["child"]
    assert [diag.code for diag in report.diagnostics] == ["routing.nondeterministic_call"]


def test_validate_pipeline_purity_checks_static_routing_topology() -> None:
    @decision
    def choose(ctx: dict) -> str:
        return "done"

    program = _decision_program(
        choose,
        routing_topology={
            "nodes": [{"name": "choose"}, {"name": "finish"}],
            "routes": [
                {"source": "choose", "label": "done", "target": "finish"},
                {"source": "choose", "label": 7, "target": "missing"},
            ],
        },
    )

    report = validate_pipeline_purity(program)

    assert {diag.code for diag in report.diagnostics} == {
        "routing.topology_invalid_label",
        "routing.topology_unknown_target",
    }


# ---------------------------------------------------------------------------
# Accepted pure decision patterns
# ---------------------------------------------------------------------------


def test_accepted_pure_decision_constant_return() -> None:
    @decision
    def constant_route(ctx: dict) -> str:
        return "done"

    assert validate_decision_body(constant_route) == []


def test_accepted_pure_decision_with_arithmetic_and_comparisons() -> None:
    @decision
    def compute_route(ctx: dict) -> str:
        score = ctx["state"].get("score", 0)
        threshold = 50
        doubled = score * 2
        return "pass" if doubled >= threshold else "fail"

    assert validate_decision_body(compute_route) == []


def test_accepted_pure_decision_with_string_operations() -> None:
    @decision
    def label_route(ctx: dict) -> str:
        kind = ctx["state"].get("kind", "default")
        normalized = kind.strip().lower()
        return normalized if normalized in ("alpha", "beta") else "other"

    assert validate_decision_body(label_route) == []


def test_accepted_pure_decision_with_builtin_calls() -> None:
    @decision
    def builtin_route(ctx: dict) -> str:
        items = ctx["state"].get("items", [])
        count = len(items)
        total = sum(items) if items else 0
        return "many" if count > 10 else "few"

    assert validate_decision_body(builtin_route) == []


def test_accepted_loop_guard_over_recorded_state_for_loop() -> None:
    @decision
    def for_loop_route(ctx: dict) -> str:
        attempts = ctx["state"].get("attempts", [])
        for entry in attempts:
            if entry.get("status") == "failed":
                return "retry"
        return "done"

    assert validate_decision_body(for_loop_route) == []


def test_accepted_loop_guard_over_recorded_state_while_loop() -> None:
    @decision
    def while_loop_route(ctx: dict) -> str:
        limit = ctx["state"].get("retry_limit", 3)
        count = ctx["state"].get("retries", 0)
        remaining = limit - count
        return "retry" if remaining > 0 else "done"

    assert validate_decision_body(while_loop_route) == []


def test_accepted_pure_decision_with_dict_and_list_comprehensions() -> None:
    @decision
    def comprehension_route(ctx: dict) -> str:
        entries = ctx["state"].get("entries", [])
        active = [e for e in entries if e.get("active")]
        return "continue" if len(active) > 0 else "halt"

    assert validate_decision_body(comprehension_route) == []


def test_accepted_pure_decision_with_set_membership() -> None:
    @decision
    def set_route(ctx: dict) -> str:
        allowed = {"alpha", "beta", "gamma"}
        stage = ctx["state"].get("stage", "")
        return stage if stage in allowed else "unknown"

    assert validate_decision_body(set_route) == []


# ---------------------------------------------------------------------------
# Rejected nondeterministic patterns — clocks / random / UUID / entropy
# ---------------------------------------------------------------------------


def test_rejects_time_clock_calls() -> None:
    @decision
    def uses_time_time(ctx: dict) -> str:
        t = time.time()
        return "done"

    @decision
    def uses_time_monotonic(ctx: dict) -> str:
        t = time.monotonic()
        return "done"

    @decision
    def uses_time_perf_counter(ctx: dict) -> str:
        t = time.perf_counter()
        return "done"

    assert [diag.code for diag in validate_decision_body(uses_time_time)] == [
        "routing.nondeterministic_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_time_monotonic)] == [
        "routing.nondeterministic_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_time_perf_counter)] == [
        "routing.nondeterministic_call"
    ]


def test_rejects_datetime_now_and_today() -> None:
    @decision
    def uses_datetime_now(ctx: dict) -> str:
        now = datetime.datetime.now()
        return "done"

    @decision
    def uses_datetime_utcnow(ctx: dict) -> str:
        now = datetime.datetime.utcnow()
        return "done"

    @decision
    def uses_date_today(ctx: dict) -> str:
        today = datetime.date.today()
        return "done"

    assert [diag.code for diag in validate_decision_body(uses_datetime_now)] == [
        "routing.nondeterministic_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_datetime_utcnow)] == [
        "routing.nondeterministic_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_date_today)] == [
        "routing.nondeterministic_call"
    ]


def test_rejects_uuid_generation() -> None:
    @decision
    def uses_uuid1(ctx: dict) -> str:
        uid = uuid.uuid1()
        return "done"

    @decision
    def uses_uuid4(ctx: dict) -> str:
        uid = uuid.uuid4()
        return "done"

    assert [diag.code for diag in validate_decision_body(uses_uuid1)] == [
        "routing.nondeterministic_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_uuid4)] == [
        "routing.nondeterministic_call"
    ]


def test_rejects_os_urandom_and_secrets() -> None:
    @decision
    def uses_os_urandom(ctx: dict) -> str:
        data = os.urandom(16)
        return "done"

    @decision
    def uses_secrets(ctx: dict) -> str:
        token = secrets.token_hex(16)
        return "done"

    assert [diag.code for diag in validate_decision_body(uses_os_urandom)] == [
        "routing.nondeterministic_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_secrets)] == [
        "routing.nondeterministic_call"
    ]


# ---------------------------------------------------------------------------
# Rejected filesystem / pathlib I/O
# ---------------------------------------------------------------------------


def test_rejects_os_filesystem_calls() -> None:
    @decision
    def uses_listdir(ctx: dict) -> str:
        os.listdir("/tmp")
        return "done"

    @decision
    def uses_makedirs(ctx: dict) -> str:
        os.makedirs("/tmp/x", exist_ok=True)
        return "done"

    @decision
    def uses_remove(ctx: dict) -> str:
        os.remove("/tmp/x")
        return "done"

    assert [diag.code for diag in validate_decision_body(uses_listdir)] == [
        "routing.io_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_makedirs)] == [
        "routing.io_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_remove)] == [
        "routing.io_call"
    ]


def test_rejects_os_rename_replace_rmdir_unlink() -> None:
    @decision
    def uses_rename(ctx: dict) -> str:
        os.rename("a", "b")
        return "done"

    @decision
    def uses_replace(ctx: dict) -> str:
        os.replace("a", "b")
        return "done"

    @decision
    def uses_rmdir(ctx: dict) -> str:
        os.rmdir("/tmp/x")
        return "done"

    @decision
    def uses_unlink(ctx: dict) -> str:
        os.unlink("/tmp/x")
        return "done"

    assert [diag.code for diag in validate_decision_body(uses_rename)] == [
        "routing.io_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_replace)] == [
        "routing.io_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_rmdir)] == [
        "routing.io_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_unlink)] == [
        "routing.io_call"
    ]


def test_rejects_pathlib_io_methods() -> None:
    @decision
    def uses_path_read_bytes(ctx: dict) -> str:
        Path("x.bin").read_bytes()
        return "done"

    @decision
    def uses_path_write_text(ctx: dict) -> str:
        Path("x.txt").write_text("hi")
        return "done"

    @decision
    def uses_path_write_bytes(ctx: dict) -> str:
        Path("x.bin").write_bytes(b"hi")
        return "done"

    @decision
    def uses_path_mkdir(ctx: dict) -> str:
        Path("d").mkdir()
        return "done"

    @decision
    def uses_path_touch(ctx: dict) -> str:
        Path("x").touch()
        return "done"

    assert [diag.code for diag in validate_decision_body(uses_path_read_bytes)] == [
        "routing.io_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_path_write_text)] == [
        "routing.io_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_path_write_bytes)] == [
        "routing.io_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_path_mkdir)] == [
        "routing.io_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_path_touch)] == [
        "routing.io_call"
    ]


def test_rejects_pathlib_rename_replace_rmdir_unlink() -> None:
    @decision
    def uses_path_rename(ctx: dict) -> str:
        Path("a").rename("b")
        return "done"

    @decision
    def uses_path_replace(ctx: dict) -> str:
        Path("a").replace("b")
        return "done"

    @decision
    def uses_path_rmdir(ctx: dict) -> str:
        Path("d").rmdir()
        return "done"

    @decision
    def uses_path_unlink(ctx: dict) -> str:
        Path("x").unlink()
        return "done"

    assert [diag.code for diag in validate_decision_body(uses_path_rename)] == [
        "routing.io_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_path_replace)] == [
        "routing.io_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_path_rmdir)] == [
        "routing.io_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_path_unlink)] == [
        "routing.io_call"
    ]


def test_rejects_shutil_and_io_open() -> None:
    @decision
    def uses_shutil(ctx: dict) -> str:
        shutil.copy("a", "b")
        return "done"

    @decision
    def uses_io_open(ctx: dict) -> str:
        io.open("x.txt")
        return "done"

    assert [diag.code for diag in validate_decision_body(uses_shutil)] == [
        "routing.io_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_io_open)] == [
        "routing.io_call"
    ]


# ---------------------------------------------------------------------------
# Rejected network I/O
# ---------------------------------------------------------------------------


def test_rejects_requests_network_calls() -> None:
    @decision
    def uses_requests_get(ctx: dict) -> str:
        requests.get("https://example.com")
        return "done"

    @decision
    def uses_requests_post(ctx: dict) -> str:
        requests.post("https://example.com", json={})
        return "done"

    assert [diag.code for diag in validate_decision_body(uses_requests_get)] == [
        "routing.network_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_requests_post)] == [
        "routing.network_call"
    ]


def test_rejects_httpx_network_calls() -> None:
    @decision
    def uses_httpx_get(ctx: dict) -> str:
        httpx.get("https://example.com")
        return "done"

    assert [diag.code for diag in validate_decision_body(uses_httpx_get)] == [
        "routing.network_call"
    ]


def test_rejects_socket_calls() -> None:
    @decision
    def uses_socket(ctx: dict) -> str:
        socket.socket()
        return "done"

    @decision
    def uses_socket_connect(ctx: dict) -> str:
        s = socket.socket()
        s.connect(("localhost", 80))
        return "done"

    assert [diag.code for diag in validate_decision_body(uses_socket)] == [
        "routing.network_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_socket_connect)] == [
        "routing.network_call"
    ]


def test_rejects_http_client_and_urllib3() -> None:
    import http.client

    @decision
    def uses_http_client(ctx: dict) -> str:
        http.client.HTTPConnection("example.com")
        return "done"

    assert [diag.code for diag in validate_decision_body(uses_http_client)] == [
        "routing.network_call"
    ]


# ---------------------------------------------------------------------------
# Rejected subprocess / shell
# ---------------------------------------------------------------------------


def test_rejects_os_system_and_popen() -> None:
    @decision
    def uses_os_system(ctx: dict) -> str:
        os.system("echo hi")
        return "done"

    @decision
    def uses_os_popen(ctx: dict) -> str:
        os.popen("echo hi")
        return "done"

    assert [diag.code for diag in validate_decision_body(uses_os_system)] == [
        "routing.subprocess_call"
    ]
    assert [diag.code for diag in validate_decision_body(uses_os_popen)] == [
        "routing.subprocess_call"
    ]


# ---------------------------------------------------------------------------
# Rejected dynamic dispatch / import tricks
# ---------------------------------------------------------------------------


def test_rejects_dynamic_import_and_importlib() -> None:
    @decision
    def uses_dunder_import(ctx: dict) -> str:
        __import__("os")
        return "done"

    @decision
    def uses_importlib(ctx: dict) -> str:
        importlib.import_module("os")
        return "done"

    assert [diag.code for diag in validate_decision_body(uses_dunder_import)] == [
        "routing.dynamic_dispatch"
    ]
    assert [diag.code for diag in validate_decision_body(uses_importlib)] == [
        "routing.dynamic_dispatch"
    ]


def test_rejects_import_statement_in_decision_body() -> None:
    @decision
    def has_import(ctx: dict) -> str:
        import json

        return "done"

    @decision
    def has_import_from(ctx: dict) -> str:
        from os import path

        return "done"

    assert [diag.code for diag in validate_decision_body(has_import)] == [
        "routing.dynamic_import"
    ]
    assert [diag.code for diag in validate_decision_body(has_import_from)] == [
        "routing.dynamic_import"
    ]


def test_rejects_globals_locals_vars_setattr() -> None:
    @decision
    def uses_globals(ctx: dict) -> str:
        globals()
        return "done"

    @decision
    def uses_locals(ctx: dict) -> str:
        locals()
        return "done"

    @decision
    def uses_vars(ctx: dict) -> str:
        vars(ctx)
        return "done"

    @decision
    def uses_setattr(ctx: dict) -> str:
        setattr(ctx, "x", 1)
        return "done"

    assert [diag.code for diag in validate_decision_body(uses_globals)] == [
        "routing.dynamic_dispatch"
    ]
    assert [diag.code for diag in validate_decision_body(uses_locals)] == [
        "routing.dynamic_dispatch"
    ]
    assert [diag.code for diag in validate_decision_body(uses_vars)] == [
        "routing.dynamic_dispatch"
    ]
    assert [diag.code for diag in validate_decision_body(uses_setattr)] == [
        "routing.dynamic_dispatch"
    ]


# ---------------------------------------------------------------------------
# Rejected routing-owned state mutation (extended patterns)
# ---------------------------------------------------------------------------


def test_rejects_state_mutation_via_augassign_on_routing_key() -> None:
    @decision
    def mutates_augassign(ctx: dict) -> str:
        ctx["state"]["retry_count"] = ctx["state"].get("retry_count", 0) + 1
        ctx["state"]["route"] += "/suffix"
        return "done"

    diag = validate_decision_body(mutates_augassign)
    # Only the route mutation is caught (retry_count is not a routing-owned key)
    assert [diag.code for diag in diag] == ["routing.state_mutation"]
    assert "route" in diag[0].message


def test_rejects_state_mutation_via_direct_state_variable() -> None:
    @decision
    def mutates_direct_state(ctx: dict) -> str:
        state = ctx["state"]
        state["next_step"] = "shadow"
        return "done"

    diag = validate_decision_body(mutates_direct_state)
    assert [diag.code for diag in diag] == ["routing.state_mutation"]
    assert "next_step" in diag[0].message


def test_rejects_state_mutation_on_multiple_routing_keys() -> None:
    @decision
    def mutates_branch(ctx: dict) -> str:
        ctx["state"]["branch"] = "alt"
        return "done"

    @decision
    def mutates_override_route(ctx: dict) -> str:
        ctx["state"]["override_route"] = "/alt"
        return "done"

    @decision
    def mutates_decision_key(ctx: dict) -> str:
        ctx["state"]["decision"] = "reroute"
        return "done"

    @decision
    def mutates_current_state(ctx: dict) -> str:
        ctx["state"]["current_state"] = "new"
        return "done"

    assert [diag.code for diag in validate_decision_body(mutates_branch)] == [
        "routing.state_mutation"
    ]
    assert [diag.code for diag in validate_decision_body(mutates_override_route)] == [
        "routing.state_mutation"
    ]
    assert [diag.code for diag in validate_decision_body(mutates_decision_key)] == [
        "routing.state_mutation"
    ]
    assert [diag.code for diag in validate_decision_body(mutates_current_state)] == [
        "routing.state_mutation"
    ]


# ---------------------------------------------------------------------------
# Allowed impure code inside @phase bodies (phase bodies are unconstrained)
# ---------------------------------------------------------------------------


def test_phase_bodies_allow_all_impure_operations() -> None:
    @phase
    def impure_everything(ctx: dict) -> dict:
        random.random()
        time.time()
        datetime.datetime.now()
        uuid.uuid4()
        os.urandom(16)
        secrets.token_hex(8)
        Path("x.txt").read_text()
        os.listdir("/tmp")
        shutil.copy("a", "b")
        io.open("x.txt")
        requests.get("https://example.com")
        httpx.get("https://example.com")
        socket.socket()
        subprocess.run(["echo", "hi"], check=False)
        os.system("echo hi")
        __import__("os")
        importlib.import_module("sys")
        eval("1+1")
        exec("x=1")
        globals()
        locals()
        setattr(ctx, "x", 1)
        ctx["state"]["route"] = "override"
        ctx["state"].update({"next_step": "x"})
        return {"ok": True}

    program = NativeProgram(
        name="impure_phase_program",
        instructions=(
            NativeInstruction(
                pc=0, op="phase", name="impure_everything", func=impure_everything, next_pc=1
            ),
            NativeInstruction(pc=1, op="halt"),
        ),
    )

    report = validate_pipeline_purity(program)
    assert report.ok


def test_phase_bodies_allow_network_and_subprocess() -> None:
    @phase
    def network_phase(ctx: dict) -> dict:
        urllib.request.urlopen("https://example.com")
        return {"ok": True}

    @phase
    def subprocess_phase(ctx: dict) -> dict:
        subprocess.run(["ls"], check=False)
        return {"ok": True}

    program = NativeProgram(
        name="phase_network_subprocess",
        instructions=(
            NativeInstruction(pc=0, op="phase", name="network_phase", func=network_phase, next_pc=1),
            NativeInstruction(pc=1, op="phase", name="subprocess_phase", func=subprocess_phase, next_pc=2),
            NativeInstruction(pc=2, op="halt"),
        ),
    )

    report = validate_pipeline_purity(program)
    assert report.ok
