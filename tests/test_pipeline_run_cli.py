"""Tests for the ``megaplan run`` CLI subcommand + YAML pipeline CLI paths."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest


# ── Subprocess CLI tests ───────────────────────────────────────────────


def test_run_list_shows_builtin_pipelines() -> None:
    """``megaplan run --list`` shows registered pipelines.

    Demo pipelines (doc-critique, judges) are no longer registered as
    built-ins; only planning and discovered pipelines appear.
    """
    proc = subprocess.run(
        [sys.executable, "-m", "megaplan", "run", "--list"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "planning" in proc.stdout


def test_run_describe_returns_description() -> None:
    """``megaplan run <name> --describe`` for a registered pipeline."""
    proc = subprocess.run(
        [sys.executable, "-m", "megaplan", "run", "planning", "--describe"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "planning" in proc.stdout.lower() or "production" in proc.stdout.lower()


def test_run_doc_critique_demo_module_drives_to_done(tmp_path: Path) -> None:
    """The doc-critique demo is runnable directly from its Python module.

    Since demo pipelines are no longer registered as built-ins, invoke
    via ``from megaplan._pipeline.demos.doc_critique import run_demo``
    instead of the CLI registry.
    """
    from megaplan._pipeline.demos.doc_critique import run_demo

    fixture = tmp_path / "fixture.md"
    fixture.write_text(
        "This is the doc the critique loop reads.\n"
        "Three critique passes apply deterministic rubric edits.\n"
    )
    plan_dir = tmp_path / "out"

    result = run_demo(fixture_path=fixture, artifact_root=plan_dir, mode="code")

    assert result["final_stage"] == "critique"
    assert result["state"]["critique_iter"] == 3

    # Exact artifact set landed.
    assert (plan_dir / "critique_versions" / "critique_v1.json").exists()
    assert (plan_dir / "critique_versions" / "critique_v2.json").exists()
    assert (plan_dir / "critique_versions" / "critique_v3.json").exists()
    assert (plan_dir / "doc_versions" / "doc_v1.md").exists()
    assert (plan_dir / "doc_versions" / "doc_v2.md").exists()


def test_run_unknown_pipeline_returns_error() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "megaplan", "run", "does-not-exist",
         "--plan-dir", "/tmp/discard"],
        capture_output=True, text=True,
    )
    assert proc.returncode != 0
    assert "unknown pipeline" in (proc.stdout + proc.stderr).lower()


def test_run_list_includes_epic_blitz() -> None:
    """``megaplan run --list`` includes epic-blitz."""
    proc = subprocess.run(
        [sys.executable, "-m", "megaplan", "run", "--list"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "epic-blitz" in proc.stdout


def test_run_describe_epic_blitz_prints_metadata() -> None:
    """``megaplan run epic-blitz --describe`` prints metadata + SKILL.md."""
    proc = subprocess.run(
        [sys.executable, "-m", "megaplan", "run", "epic-blitz", "--describe"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Three-round" in proc.stdout
    assert "epic-blitz" in proc.stdout


# ── Registry-backed CLI tests (Python-level, no subprocess) ───────────


def test_registered_pipelines_includes_writing_panel_strict() -> None:
    """The registry surfaces writing-panel-strict alongside the built-ins."""
    from megaplan._pipeline.registry import registered_pipelines
    names = registered_pipelines()
    assert "writing-panel-strict" in names
    assert "planning" in names


def test_registered_pipelines_includes_epic_blitz() -> None:
    """The registry surfaces epic-blitz alongside the built-ins."""
    from megaplan._pipeline.registry import registered_pipelines
    names = registered_pipelines()
    assert "epic-blitz" in names


def test_registered_pipelines_does_not_expose_demo_pipelines() -> None:
    """Demo pipelines (doc-critique, judges) are not in the production registry."""
    from megaplan._pipeline.registry import registered_pipelines
    names = registered_pipelines()
    assert "doc-critique" not in names, (
        f"doc-critique must not appear in registered_pipelines(); got {names!r}"
    )
    assert "judges" not in names, (
        f"judges must not appear in registered_pipelines(); got {names!r}"
    )


def test_describe_pipeline_writing_panel_strict(capsys) -> None:
    """_describe_pipeline for writing-panel-strict prints metadata."""
    from megaplan._pipeline.run_cli import _describe_pipeline
    rc = _describe_pipeline("writing-panel-strict")
    assert rc == 0
    captured = capsys.readouterr()
    assert "writing-panel-strict" in captured.out
    assert "adversarial" in captured.out.lower() or "Adversarial" in captured.out


def test_describe_pipeline_unknown(capsys) -> None:
    """_describe_pipeline for unknown name prints error and returns 2."""
    from megaplan._pipeline.run_cli import _describe_pipeline
    rc = _describe_pipeline("nonexistent-pipeline-xyz")
    assert rc == 2
    captured = capsys.readouterr()
    assert "unknown" in captured.err.lower() or "Unknown" in captured.err


def test_describe_pipeline_epic_blitz(capsys) -> None:
    """_describe_pipeline for epic-blitz prints metadata + SKILL.md."""
    from megaplan._pipeline.run_cli import _describe_pipeline
    rc = _describe_pipeline("epic-blitz")
    assert rc == 0
    captured = capsys.readouterr()
    assert "epic-blitz" in captured.out
    assert "Three-round" in captured.out


def test_handle_list_pipelines() -> None:
    """handle_list with list_target='pipelines' returns pipeline listing."""
    from megaplan.cli import handle_list
    args = argparse.Namespace(
        list_target="pipelines",
        verbose=False,
        filter_status=None,
        no_tree=False,
        include_done=False,
        summary=False,
        all=False,
    )
    result = handle_list(Path.cwd(), args)
    assert result["success"] is True
    assert result["step"] == "list"
    assert len(result["pipelines"]) >= 2  # at minimum writing-panel-strict + planning
    names = [p["name"] for p in result["pipelines"]]
    assert "writing-panel-strict" in names
    assert "planning" in names
    assert "epic-blitz" in names


def test_handle_list_pipelines_verbose() -> None:
    """handle_list with list_target='pipelines' and verbose includes extra fields."""
    from megaplan.cli import handle_list
    args = argparse.Namespace(
        list_target="pipelines",
        verbose=True,
        filter_status=None,
        no_tree=False,
        include_done=False,
        summary=False,
        all=False,
    )
    result = handle_list(Path.cwd(), args)
    assert result["success"] is True
    # writing-panel-strict's registered metadata carries default_profile + modes;
    # locate it and assert the verbose-mode metadata surface.
    wps = next(
        (p for p in result["pipelines"] if p["name"] == "writing-panel-strict"),
        None,
    )
    assert wps is not None
    assert "default_profile" in wps
    assert "modes" in wps
    # The kind='yaml'|'python' distinction was dropped in 0.22.0.
    assert all("kind" not in entry for entry in result["pipelines"])


def test_handle_describe_writing_panel_strict(capsys) -> None:
    """handle_describe for writing-panel-strict prints metadata + SKILL.md."""
    from megaplan.cli import handle_describe
    args = argparse.Namespace(pipeline_name="writing-panel-strict")
    result = handle_describe(args)
    captured = capsys.readouterr()
    assert result["success"] is True
    assert result["step"] == "describe"
    assert result["pipeline"] == "writing-panel-strict"
    assert "writing-panel-strict" in captured.out
    assert "Adversarial review" in captured.out or "adversarial" in captured.out.lower()


def test_handle_describe_unknown_pipeline() -> None:
    """handle_describe for unknown pipeline returns error."""
    from megaplan.cli import handle_describe
    args = argparse.Namespace(pipeline_name="nonexistent-pipeline-xyz")
    result = handle_describe(args)
    assert result["success"] is False
    assert result["step"] == "describe"


def test_handle_describe_epic_blitz(capsys) -> None:
    """handle_describe for epic-blitz prints metadata + SKILL.md."""
    from megaplan.cli import handle_describe
    args = argparse.Namespace(pipeline_name="epic-blitz")
    result = handle_describe(args)
    captured = capsys.readouterr()
    assert result["success"] is True
    assert result["step"] == "describe"
    assert result["pipeline"] == "epic-blitz"
    assert "epic-blitz" in captured.out
    assert "Three-round" in captured.out


def test_cli_run_list_dispatches(monkeypatch) -> None:
    """cli_run with --list prints the registered pipeline names."""
    from megaplan._pipeline.run_cli import cli_run

    args = argparse.Namespace(
        list_pipelines=True,
        pipeline_name=None,
        describe=False,
    )
    # Should exit 0 after listing
    result = cli_run(args)
    assert result == 0


def test_cli_run_describe_dispatches(monkeypatch) -> None:
    """cli_run with --describe for a YAML pipeline prints description."""
    from megaplan._pipeline.run_cli import cli_run

    args = argparse.Namespace(
        list_pipelines=False,
        pipeline_name="writing-panel-strict",
        describe=True,
    )
    result = cli_run(args)
    assert result == 0


def test_cli_run_unknown_pipeline_returns_2() -> None:
    """cli_run with unknown pipeline name returns 2."""
    from megaplan._pipeline.run_cli import cli_run

    args = argparse.Namespace(
        list_pipelines=False,
        pipeline_name="does-not-exist-xyz",
        describe=False,
    )
    result = cli_run(args)
    assert result == 2


def _run_args(
    *,
    pipeline_name: str,
    plan_dir: Path,
    state: dict | None = None,
    form: str | None = None,
    primary_criterion: str | None = None,
    inputs: str | None = None,
    input_file: str | None = None,
) -> argparse.Namespace:
    return argparse.Namespace(
        list_pipelines=False,
        pipeline_name=pipeline_name,
        input_file=input_file,
        plan_dir=str(plan_dir),
        inputs=inputs,
        state=json.dumps(state) if state is not None else None,
        mode=None,
        profile=None,
        describe=False,
        resume_choice=None,
        vendor=None,
        form=form,
        primary_criterion=primary_criterion,
    )


def test_creative_invalid_form_validates_before_profile_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from megaplan import profiles as profiles_module
    from megaplan._pipeline import preflight as preflight_module
    from megaplan._pipeline.run_cli import cli_run

    def fail_profile_load(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("profile resolution should not run")

    def fail_preflight(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("preflight should not run")

    monkeypatch.setattr(profiles_module, "load_profiles", fail_profile_load)
    monkeypatch.setattr(preflight_module, "preflight_or_raise", fail_preflight)

    rc = cli_run(
        _run_args(
            pipeline_name="creative",
            plan_dir=tmp_path / "creative-invalid",
            form="not-a-real-form",
        )
    )

    assert rc == 2
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["error"] == "invalid_args"
    assert "not-a-real-form" in payload["message"]
    assert "Available" in payload["message"]
    assert captured.err == ""


def test_creative_only_options_rejected_for_non_creative_before_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from megaplan import profiles as profiles_module
    from megaplan._pipeline import preflight as preflight_module
    from megaplan._pipeline.run_cli import cli_run

    monkeypatch.setattr(
        profiles_module,
        "load_profiles",
        lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError("profile resolution should not run")
        ),
    )
    monkeypatch.setattr(
        preflight_module,
        "preflight_or_raise",
        lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError("preflight should not run")
        ),
    )

    rc = cli_run(
        _run_args(
            pipeline_name="planning",
            plan_dir=tmp_path / "planning",
            form="poem",
            primary_criterion="most surprising exact image",
        )
    )

    assert rc == 2
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["error"] == "invalid_args"
    assert "--form" in payload["message"]
    assert "--primary-criterion" in payload["message"]
    assert "creative" in payload["message"]
    assert captured.err == ""


def test_run_pipeline_injects_pipeline_context_without_persisting_internal_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from megaplan._pipeline import executor as executor_module
    from megaplan._pipeline import preflight as preflight_module
    from megaplan._pipeline.run_cli import cli_run

    captured = {}

    def fake_run_pipeline(pipeline, ctx, *, artifact_root):  # noqa: ANN001
        captured["inputs"] = dict(ctx.inputs)
        captured["state"] = dict(ctx.state)
        return {"final_stage": pipeline.entry, "state": dict(ctx.state)}

    monkeypatch.setattr(
        preflight_module,
        "preflight_or_raise",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(executor_module, "run_pipeline", fake_run_pipeline)

    rc = cli_run(
        _run_args(
            pipeline_name="planning",
            plan_dir=tmp_path / "planning-context",
        )
    )

    assert rc == 0
    assert captured["inputs"]["_pipeline"] == "planning"
    assert "_pipeline" not in captured["state"].get("_inputs", {})


def test_creative_run_seeds_runtime_state_before_step_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from megaplan._pipeline import executor as executor_module
    from megaplan._pipeline import preflight as preflight_module
    from megaplan._pipeline.run_cli import cli_run

    idea_file = tmp_path / "idea.md"
    idea_file.write_text("write a poem about a blue door", encoding="utf-8")
    captured = {}

    def fake_run_pipeline(pipeline, ctx, *, artifact_root):  # noqa: ANN001
        captured["inputs"] = dict(ctx.inputs)
        captured["state"] = dict(ctx.state)
        return {"final_stage": pipeline.entry, "state": dict(ctx.state)}

    monkeypatch.setattr(
        preflight_module,
        "preflight_or_raise",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(executor_module, "run_pipeline", fake_run_pipeline)

    rc = cli_run(
        _run_args(
            pipeline_name="creative",
            plan_dir=tmp_path / "creative-state",
            form="poem",
            primary_criterion="most surprising exact image",
            inputs=f"idea={idea_file}",
        )
    )

    assert rc == 0
    state = captured["state"]
    assert state["_pipeline_name"] == "creative"
    assert state["idea"] == "write a poem about a blue door"
    assert state["config"]["mode"] == "creative"
    assert state["config"]["form"] == "poem"
    assert state["config"]["primary_criterion"] == "most surprising exact image"
    assert state["config"]["project_dir"] == str(Path.cwd())
    assert captured["inputs"]["_pipeline"] == "creative"


def test_cli_run_list_includes_epic_blitz(capsys) -> None:
    """cli_run --list output includes epic-blitz."""
    from megaplan._pipeline.run_cli import cli_run

    args = argparse.Namespace(
        list_pipelines=True,
        pipeline_name=None,
        describe=False,
    )
    result = cli_run(args)
    assert result == 0
    captured = capsys.readouterr()
    assert "epic-blitz" in captured.out


def test_cli_run_describe_epic_blitz(capsys) -> None:
    """cli_run --describe for epic-blitz prints metadata + SKILL.md."""
    from megaplan._pipeline.run_cli import cli_run

    args = argparse.Namespace(
        list_pipelines=False,
        pipeline_name="epic-blitz",
        describe=True,
    )
    result = cli_run(args)
    assert result == 0
    captured = capsys.readouterr()
    assert "epic-blitz" in captured.out
    assert "Three-round" in captured.out


# ── Credential preflight CLI path tests ────────────────────────────────


def test_preflight_or_raise_exits_7_non_tty_cli(monkeypatch, capsys) -> None:
    """Non-TTY credential failure exits 7 with structured stderr message."""
    from megaplan._pipeline.preflight import preflight_or_raise

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

    profile = {"synth": "claude", "revise": "codex"}

    with pytest.raises(SystemExit) as exc_info:
        preflight_or_raise(profile, pipeline_name="test-pipe", profile_name="test-prof")

    assert exc_info.value.code == 7
    captured = capsys.readouterr()
    assert "test-pipe" in captured.err
    assert "ANTHROPIC_API_KEY" in captured.err
    assert "OPENAI_API_KEY" in captured.err


def test_render_credential_failure_non_tty_structure(monkeypatch) -> None:
    """Non-TTY credential message has env var hints, no interactive options."""
    from megaplan._pipeline.preflight import render_credential_failure

    # No credentials at all → deterministic getting-started guidance.
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY",
                "FIREWORKS_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    missing = [
        {"slot": "critique", "spec": "codex", "agent": "codex",
         "env_var": "OPENAI_API_KEY"},
    ]
    msg = render_credential_failure(
        missing, pipeline_name="pipe", profile_name="prof", is_tty=False,
    )

    assert "pipe" in msg
    assert "prof" in msg
    assert "OPENAI_API_KEY" in msg
    # Non-TTY: no interactive options
    assert "[1]" not in msg
    assert "[2]" not in msg
    # With no creds, the getting-started guidance lists every supported key.
    assert "No model credentials found" in msg
    assert "ANTHROPIC_API_KEY" in msg
    assert "DEEPSEEK_API_KEY" in msg


def test_preflight_feedback_slot_is_soft(monkeypatch) -> None:
    """The opt-in feedback slot must not gate the run. A Codex-only user can
    run all-codex (which pins feedback=claude:low) without an Anthropic key."""
    from megaplan._pipeline.preflight import preflight_check_profile

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    profile = {"plan": "codex", "execute": "codex", "feedback": "claude:low"}
    missing = preflight_check_profile(profile, profile_name="all-codex")
    # feedback's ANTHROPIC requirement is soft → nothing missing.
    assert missing == []


def test_preflight_resolves_symbolic_premium_with_selected_vendor(monkeypatch) -> None:
    from megaplan._pipeline.preflight import preflight_check_profile

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    missing = preflight_check_profile(
        {"plan": "premium", "feedback": "premium:low"},
        profile_name="premium",
        vendor="codex",
    )

    assert missing == [
        {
            "slot": "plan",
            "spec": "codex",
            "agent": "codex",
            "env_var": "OPENAI_API_KEY",
        }
    ]


def test_preflight_resolves_symbolic_premium_with_default_vendor(monkeypatch) -> None:
    from megaplan import profiles as profiles_module
    from megaplan._pipeline import preflight as preflight_module

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        profiles_module,
        "effective_premium_vendor",
        lambda *args, **kwargs: "claude",
    )

    missing = preflight_module.preflight_check_profile(
        {"plan": "premium:low"},
        profile_name="premium",
    )

    assert missing == [
        {
            "slot": "plan",
            "spec": "claude:low",
            "agent": "claude",
            "env_var": "ANTHROPIC_API_KEY",
        }
    ]


def test_render_credential_failure_recommends_available_vendor_profile(
    monkeypatch,
) -> None:
    """When the chosen profile needs a key the user lacks but they DO have
    Anthropic creds, the message points them at all-claude and at the DeepSeek
    route for the cost-tiered profiles — and does NOT suggest the codex
    profile (no OpenAI key present)."""
    from megaplan._pipeline.preflight import render_credential_failure

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)

    missing = [
        {"slot": "plan", "spec": "hermes:fireworks:deepseek-v4-pro",
         "agent": "hermes/fireworks", "env_var": "FIREWORKS_API_KEY"},
    ]
    msg = render_credential_failure(
        missing, pipeline_name="code", profile_name="solo", is_tty=False,
    )
    assert "--profile all-claude" in msg
    assert "DEEPSEEK_API_KEY" in msg
    assert "all-codex" not in msg


def test_render_credential_failure_no_self_recommendation(monkeypatch) -> None:
    """Don't recommend the profile the user already tried: on all-claude with
    no Anthropic key, the message must not loop back to --profile all-claude."""
    from megaplan._pipeline.preflight import render_credential_failure

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)

    missing = [
        {"slot": "plan", "spec": "claude", "agent": "claude",
         "env_var": "ANTHROPIC_API_KEY"},
    ]
    msg = render_credential_failure(
        missing, profile_name="all-claude", is_tty=False,
    )
    assert "--profile all-claude" not in msg


# ── Premium vendor routing preflight tests ─────────────────────────────


def test_preflight_codex_vendor_requires_only_openai_for_premium_slots(
    monkeypatch,
) -> None:
    """With ``--vendor codex``, premium placeholder slots need OpenAI, not Anthropic."""
    from megaplan._pipeline.preflight import preflight_check_profile

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-present")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    profile = {"plan": "premium", "revise": "premium:low"}
    missing = preflight_check_profile(
        profile, profile_name="premium", vendor="codex",
    )

    assert len(missing) >= 1
    env_vars = {m["env_var"] for m in missing}
    assert "OPENAI_API_KEY" in env_vars
    assert "ANTHROPIC_API_KEY" not in env_vars, (
        "codex vendor should not require Anthropic for premium slots"
    )
    # All missing slots should be codex-bound
    for m in missing:
        assert m["agent"] == "codex"


def test_preflight_claude_vendor_requires_only_anthropic_for_premium_slots(
    monkeypatch,
) -> None:
    """With ``--vendor claude``, premium placeholder slots need Anthropic, not OpenAI."""
    from megaplan._pipeline.preflight import preflight_check_profile

    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-present")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    profile = {"plan": "premium", "revise": "premium:low"}
    missing = preflight_check_profile(
        profile, profile_name="premium", vendor="claude",
    )

    assert len(missing) >= 1
    env_vars = {m["env_var"] for m in missing}
    assert "ANTHROPIC_API_KEY" in env_vars
    assert "OPENAI_API_KEY" not in env_vars, (
        "claude vendor should not require OpenAI for premium slots"
    )
    for m in missing:
        assert m["agent"] == "claude"


def test_preflight_mixed_explicit_pins_report_both_providers(
    monkeypatch,
) -> None:
    """Explicit mixed pins (plan=claude, execute=codex) report both providers."""
    from megaplan._pipeline.preflight import preflight_check_profile

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    profile = {"plan": "claude", "execute": "codex", "revise": "codex"}
    missing = preflight_check_profile(
        profile, profile_name="mixed-pins",
    )

    env_vars = {m["env_var"] for m in missing}
    assert "ANTHROPIC_API_KEY" in env_vars
    assert "OPENAI_API_KEY" in env_vars


def test_preflight_explicit_phase_model_pins_override_selected_vendor(
    monkeypatch,
) -> None:
    """Explicit concrete ``phase_model`` pins take precedence over vendor."""
    from megaplan._pipeline.preflight import preflight_check_profile

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-ok")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    # Profile has concrete pins: plan=codex, revise=codex
    # These are already concrete, so vendor is irrelevant for them.
    # The key scenario: the profile has already-expanded specs but
    # vendor should not reintroduce symbolic resolution.
    profile = {"plan": "codex", "revise": "codex", "execute": "codex"}
    missing = preflight_check_profile(
        profile, profile_name="codex-pinned", vendor="claude",
    )

    assert len(missing) >= 1
    # All missing should be OPENAI, never ANTHROPIC — the concrete
    # specs override the selected vendor.
    for m in missing:
        assert m["agent"] == "codex"
        assert m["env_var"] == "OPENAI_API_KEY"

    # Conversely, with claude pins, Anthropic is required regardless of
    # selected codex vendor.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-ok")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    profile2 = {"plan": "claude", "revise": "claude", "execute": "claude"}
    missing2 = preflight_check_profile(
        profile2, profile_name="claude-pinned", vendor="codex",
    )

    assert len(missing2) >= 1
    for m in missing2:
        assert m["agent"] == "claude"
        assert m["env_var"] == "ANTHROPIC_API_KEY"


# ── Existing helper tests ─────────────────────────────────────────────


def test_parse_inputs_helper() -> None:
    from megaplan._pipeline.run_cli import _parse_inputs
    parsed = _parse_inputs("doc=/tmp/x.md,extra=/tmp/y.json")
    assert parsed == {"doc": Path("/tmp/x.md"), "extra": Path("/tmp/y.json")}
    assert _parse_inputs("") == {}
    assert _parse_inputs(None) == {}
    with pytest.raises(ValueError, match="must be key=value"):
        _parse_inputs("no-equals")
