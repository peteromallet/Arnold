"""``megaplan run <pipeline-name>`` — CLI for the pipeline registry.

Lets users invoke any registered pipeline from the command line.
Examples::

    megaplan run --list
    megaplan run doc-critique --inputs doc=/tmp/fixture.md --plan-dir /tmp/dcdemo
    megaplan run judges --inputs doc=/tmp/note.md --plan-dir /tmp/jd
    megaplan run my-custom-pipeline --plan-dir /tmp/out --mode joke

When a user registers their own pipeline (via
``register_pipeline("name", builder)``), it shows up here
automatically — no CLI surgery required.

YAML pipeline support (Sprint A):
    megaplan run writing-panel-strict path/to/draft.md
    megaplan run writing-panel-strict path/to/draft.md --profile @writing-panel-strict:standard
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def build_run_parser(subparsers: Any) -> None:
    """Attach the ``megaplan run`` subcommand to the main CLI."""

    parser = subparsers.add_parser(
        "run",
        help="Run a registered Pipeline by name (see --list).",
    )
    parser.add_argument(
        "pipeline_name",
        nargs="?",
        help="Name of the pipeline. Omit when using --list.",
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default=None,
        help="Input file path (for YAML pipelines maps to 'draft' input).",
    )
    parser.add_argument(
        "--list", "-l", action="store_true",
        dest="list_pipelines",
        help="List every registered pipeline + description and exit.",
    )
    parser.add_argument(
        "--plan-dir", default=None,
        help="Where the pipeline writes artifacts. "
             "Defaults to .megaplan/runs/<pipeline-name>/<timestamp>/.",
    )
    parser.add_argument(
        "--inputs", default=None,
        help="Comma-separated key=path pairs threaded into ctx.inputs "
             "(e.g. --inputs doc=/tmp/fixture.md,extra=/tmp/x.json).",
    )
    parser.add_argument(
        "--state", default=None,
        help="JSON string used to seed ctx.state.",
    )
    parser.add_argument(
        "--mode", default=None,
        help="Mode dispatch (code|doc|joke|creative|...). "
             "Defaults to 'code' for registered pipelines; "
             "for YAML pipelines, uses the first supported mode if unset.",
    )
    parser.add_argument(
        "--profile", default=None,
        help="Optional profile name to load via load_profile(). "
             "For YAML pipelines, use @<pipeline>:<profile> syntax.",
    )
    parser.add_argument(
        "--describe", action="store_true",
        help="Print the pipeline's description without running it.",
    )
    parser.add_argument(
        "--resume-choice", default=None,
        help="For YAML pipelines: resume a paused human_gate with this choice.",
    )
    parser.add_argument(
        "--vendor", default=None,
        choices=["claude", "codex"],
        help="Vendor override for premium slots in YAML profiles.",
    )
    parser.set_defaults(func=cli_run)


def cli_run(args: argparse.Namespace) -> int:
    from megaplan._pipeline.registry import (
        describe_pipeline,
        registered_pipelines,
        run_pipeline_by_name,
    )

    if args.list_pipelines:
        # List both registered and YAML pipelines
        _list_all_pipelines()
        return 0

    if not args.pipeline_name:
        print(
            "usage: megaplan run <pipeline-name> [--inputs k=v,...] "
            "[--plan-dir PATH]\n"
            "       megaplan run --list",
            file=sys.stderr,
        )
        return 2

    if args.describe:
        _describe_pipeline(args.pipeline_name)
        return 0

    # Try registered pipeline first, then YAML pipeline
    reg_names = list(registered_pipelines())
    yaml_names = _yaml_pipeline_names()

    if args.pipeline_name in yaml_names:
        return _run_yaml_pipeline(args)

    if args.pipeline_name in reg_names:
        return _run_registered_pipeline(args)

    # Not found
    all_names = sorted(set(reg_names) | set(yaml_names))
    print(
        f"Error: Unknown pipeline {args.pipeline_name!r}. "
        f"Available: {', '.join(all_names) if all_names else '(none)'}",
        file=sys.stderr,
    )
    return 2


# ── YAML pipeline execution ───────────────────────────────────────────


def _yaml_pipeline_names() -> set[str]:
    """Return the set of discoverable YAML pipeline names."""
    from megaplan._pipeline.loader import list_pipeline_names
    return set(list_pipeline_names())


def _run_yaml_pipeline(args: argparse.Namespace) -> int:
    """Run a YAML-defined pipeline."""
    from megaplan._pipeline.loader import load_pipeline
    from megaplan._pipeline.compiler import compile_pipeline, inject_pipeline_context
    from megaplan._pipeline.types import StepContext
    from megaplan._pipeline.executor import run_pipeline
    from megaplan._pipeline.preflight import preflight_or_raise
    from megaplan.profiles import (
        load_profiles,
        load_profile_metadata,
        resolve_pipeline_profile,
        apply_vendor_rewrite,
    )

    pipeline_name = args.pipeline_name

    # Load the pipeline spec
    lp = load_pipeline(pipeline_name)

    # Mode validation — only when the user explicitly passes a mode.
    # If no mode is given, default to the first supported mode (or None).
    mode = args.mode
    if mode:
        # User gave a mode — validate against supported_modes.
        if lp.spec.supported_modes and mode not in lp.spec.supported_modes:
            print(
                f"Error: Pipeline '{pipeline_name}' does not support mode '{mode}'. "
                f"Supported modes: {', '.join(lp.spec.supported_modes)}",
                file=sys.stderr,
            )
            return 2
    elif lp.spec.supported_modes:
        # No mode flag → use the first supported mode as default.
        mode = lp.spec.supported_modes[0]

    # Profile resolution (4-layer order)
    cli_profile = getattr(args, "profile", None)
    system_profiles = load_profiles()
    system_metadata = load_profile_metadata()

    try:
        resolved_profile = resolve_pipeline_profile(
            cli_profile,
            pipeline_name=pipeline_name,
            system_profiles=system_profiles,
            system_metadata=system_metadata,
            default_profile=lp.spec.default_profile,
        )
    except Exception as exc:
        print(f"Error resolving profile: {exc}", file=sys.stderr)
        return 2

    # Vendor rewrite (if --vendor flag is set)
    vendor = getattr(args, "vendor", None)
    if vendor:
        try:
            resolved_profile = apply_vendor_rewrite(resolved_profile, vendor)
        except Exception as exc:
            print(f"Error applying --vendor: {exc}", file=sys.stderr)
            return 2

    # Credential preflight — fail before any stage runs
    try:
        preflight_or_raise(
            resolved_profile,
            pipeline_name=pipeline_name,
            profile_name=cli_profile or lp.spec.default_profile,
        )
    except SystemExit as exc:
        return exc.code

    # Prepare inputs — positional input_file maps to 'draft' for YAML pipelines.
    inputs = _parse_inputs(args.inputs)
    input_file: str | None = getattr(args, "input_file", None)
    if input_file and "draft" not in inputs:
        inputs["draft"] = Path(input_file)
    # Did the user explicitly supply inputs on THIS invocation? (Used on
    # resume to decide whether an explicit override takes precedence over
    # the human-gate continue-loop input swap.)
    user_supplied_inputs = bool(inputs)

    plan_dir = _resolve_plan_dir(args.plan_dir, pipeline_name)
    plan_dir.mkdir(parents=True, exist_ok=True)

    resume_choice = getattr(args, "resume_choice", None)

    # If resuming, re-read state and inputs from disk so artifact paths
    # are fresh and we re-enter at the paused stage.
    paused_stage: str | None = None
    awaiting_user_data: dict[str, Any] | None = None
    if resume_choice and (plan_dir / "state.json").exists():
        try:
            existing_state = json.loads((plan_dir / "state.json").read_text())
        except (json.JSONDecodeError, OSError):
            existing_state = {}
        state = existing_state
        paused_stage = existing_state.get("_pipeline_paused_stage")
        # Re-read inputs from disk if stored. If the user explicitly
        # supplied inputs on this invocation, those win (override).
        stored_inputs = existing_state.get("_inputs")
        if isinstance(stored_inputs, dict) and not user_supplied_inputs:
            inputs = {k: Path(v) for k, v in stored_inputs.items()}
        # Read awaiting_user.json (still present before the human-gate
        # step runs and unlinks it) so we know which artifact the human
        # was editing.
        awaiting_path = plan_dir / "awaiting_user.json"
        if awaiting_path.exists():
            try:
                awaiting_user_data = json.loads(awaiting_path.read_text())
            except (json.JSONDecodeError, OSError):
                awaiting_user_data = None
    else:
        state = json.loads(args.state) if args.state else {}

    # Snapshot pipeline identity into state (on fresh runs, not resume)
    if not resume_choice:
        state["_pipeline_name"] = pipeline_name
        state["_pipeline_version"] = lp.spec.version
        state["_content_hash"] = lp.content_hash

    # On human-gate resume with 'continue' (no explicit user override),
    # repoint the primary pipeline input to the latest version of the
    # artifact the human was editing. This realises the locked decision
    # that user edits to e.g. revise/v1.md flow into the next loop
    # iteration as the new draft. See brief decision #16.
    if (
        resume_choice == "continue"
        and not user_supplied_inputs
        and awaiting_user_data is not None
        and lp.spec.inputs
    ):
        artifact_stage = awaiting_user_data.get("artifact_stage")
        if isinstance(artifact_stage, str) and artifact_stage:
            from megaplan._pipeline.steps.agent import _latest_artifact
            latest = _latest_artifact(plan_dir / artifact_stage)
            if latest is not None:
                primary_input = lp.spec.inputs[0].name
                inputs[primary_input] = latest

    # Persist resolved inputs into state so subsequent resumes (whether
    # or not the user edits artifacts in-between) always have them.
    # Audit-trail rationale: future inspection can recover what the run
    # actually consumed at this point. The very first set is preserved
    # under `_inputs_original` for traceability.
    if inputs:
        state["_inputs"] = {k: str(v) for k, v in inputs.items()}
        if "_inputs_original" not in state:
            state["_inputs_original"] = dict(state["_inputs"])

    # Build the runtime pipeline
    pipeline = compile_pipeline(
        lp.spec,
        pipeline_dir=lp.dir,
        worker=None,  # Workers are wired by the executor path
        resume_choice=resume_choice,
        mode=mode,
    )

    # On resume, re-enter at the paused stage so prior stages are not re-run.
    if paused_stage and paused_stage in pipeline.stages:
        from megaplan._pipeline.resume import with_entry
        pipeline = with_entry(pipeline, paused_stage)

    ctx = StepContext(
        plan_dir=plan_dir,
        state=state,
        profile=resolved_profile,
        mode=mode,
        inputs=inputs,
    )

    # Inject _pipeline from spec.name
    ctx = inject_pipeline_context(ctx, lp.spec.name)

    # Persist state.json BEFORE running so the executor's
    # _merge_state_to_disk (which preserves on-disk values for keys it
    # hasn't explicitly mutated) carries forward our _inputs / identity
    # snapshot. Without this, a stale on-disk _inputs from the prior run
    # would clobber the resume-time swap on the first state merge.
    try:
        (plan_dir / "state.json").write_text(
            json.dumps(state, indent=2, sort_keys=True)
        )
    except OSError:
        pass

    try:
        result = run_pipeline(pipeline, ctx, artifact_root=plan_dir)
    except Exception as exc:
        print(f"Error running pipeline: {exc}", file=sys.stderr)
        return 1

    # Check if paused (human_gate)
    if result.get("halt_reason") == "awaiting_user":
        print(
            f"\nPipeline '{pipeline_name}' paused. "
            f"Review the artifact and resume with:\n"
            f"  megaplan run {pipeline_name} --plan-dir {plan_dir} "
            f"--resume-choice <choice>\n",
        )
        return 0

    payload = {
        "pipeline": pipeline_name,
        "plan_dir": str(plan_dir),
        "final_stage": result.get("final_stage"),
        "halt_reason": result.get("halt_reason"),
        "state": result.get("state"),
    }
    print(json.dumps(payload, indent=2, default=str))
    return 0


def _run_registered_pipeline(args: argparse.Namespace) -> int:
    """Run a registered Python pipeline (existing path, unchanged)."""
    from megaplan._pipeline.registry import run_pipeline_by_name
    from megaplan._pipeline.profile import load_profile as load_registry_profile

    inputs = _parse_inputs(args.inputs)
    state = json.loads(args.state) if args.state else {}

    plan_dir = _resolve_plan_dir(args.plan_dir, args.pipeline_name)
    plan_dir.mkdir(parents=True, exist_ok=True)

    profile = None
    if args.profile:
        profile = load_registry_profile(args.profile)

    try:
        result = run_pipeline_by_name(
            args.pipeline_name,
            plan_dir=plan_dir,
            inputs=inputs,
            state=state,
            mode=args.mode or "code",
            profile=profile,
        )
    except KeyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    payload = {
        "pipeline": args.pipeline_name,
        "plan_dir": str(plan_dir),
        "final_stage": result.get("final_stage"),
        "halt_reason": result.get("halt_reason"),
        "state": result.get("state"),
    }
    print(json.dumps(payload, indent=2, default=str))
    return 0


def _list_all_pipelines() -> None:
    """List both registered and YAML pipelines."""
    from megaplan._pipeline.registry import (
        describe_pipeline,
        registered_pipelines,
    )
    from megaplan._pipeline.loader import list_pipeline_names

    reg_names = list(registered_pipelines())
    yaml_names = list(list_pipeline_names())

    if reg_names:
        print("Registered pipelines:")
        for name in reg_names:
            desc = describe_pipeline(name)
            print(f"  {name:24s} {desc}")

    if yaml_names:
        if reg_names:
            print()
        print("YAML pipelines:")
        for name in yaml_names:
            from megaplan._pipeline.loader import load_pipeline
            lp = load_pipeline(name)
            desc = lp.spec.description or ""
            print(f"  {name:24s} {desc}")

    if not reg_names and not yaml_names:
        print("(no pipelines found)")


def _describe_pipeline(name: str) -> None:
    """Describe a pipeline (try YAML first, then registered)."""
    from megaplan._pipeline.loader import list_pipeline_names, describe_pipeline as yaml_describe
    from megaplan._pipeline.registry import describe_pipeline as reg_describe, registered_pipelines

    yaml_names = list_pipeline_names()
    reg_names = list(registered_pipelines())

    if name in yaml_names:
        print(yaml_describe(name))
    elif name in reg_names:
        desc = reg_describe(name)
        if desc:
            print(desc)
        else:
            print(f"(no description registered for {name!r})")
    else:
        print(f"Error: Unknown pipeline {name!r}", file=sys.stderr)


def _parse_inputs(spec: str | None) -> dict[str, Path]:
    if not spec:
        return {}
    inputs: dict[str, Path] = {}
    for pair in spec.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            raise ValueError(f"--inputs entry {pair!r} must be key=value")
        key, value = pair.split("=", 1)
        inputs[key.strip()] = Path(value.strip())
    return inputs


def _resolve_plan_dir(explicit: str | None, pipeline_name: str) -> Path:
    if explicit:
        return Path(explicit)
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    return Path(".megaplan") / "runs" / pipeline_name / ts
