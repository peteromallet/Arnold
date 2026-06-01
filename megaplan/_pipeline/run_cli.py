"""``megaplan run <pipeline-name>`` — CLI for the pipeline registry.

Lets users invoke any registered pipeline (built-in or Python-module
discovered) from the command line. Examples::

    megaplan run --list
    megaplan run writing-panel-strict path/to/draft.md
    megaplan run writing-panel-strict path/to/draft.md \
        --profile @writing-panel-strict:standard

Demo pipelines (``doc-critique``, ``judges``) are not registered as
built-ins; run them directly via their Python modules::

    python -c "from megaplan._pipeline.demos.doc_critique import run_demo; ..."
    python -c "from megaplan._pipeline.demo_judges import run_demo; ..."

Single dispatch path: every pipeline is resolved through
:mod:`megaplan._pipeline.registry`. The human-gate resume path is
preserved — paused runs reload state, swap the primary input to the
latest artifact when the user picks ``continue``, then re-enter at the
paused stage via :func:`megaplan._pipeline.resume.with_entry`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from megaplan._core.state import write_plan_state


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
        help="Positional input file path; maps to the 'draft' input.",
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
             "Defaults to 'code' for pipelines with no supported_modes; "
             "otherwise uses the first supported mode if unset.",
    )
    parser.add_argument(
        "--profile", default=None,
        help="Optional profile name to load. Use the "
             "@<pipeline>:<profile> syntax for pipeline-local profiles.",
    )
    parser.add_argument(
        "--describe", action="store_true",
        help="Print the pipeline's description without running it.",
    )
    parser.add_argument(
        "--resume-choice", default=None,
        help="Resume a paused human_gate with this choice.",
    )
    parser.add_argument(
        "--vendor", default=None,
        choices=["claude", "codex"],
        help="Vendor override for premium slots in profiles.",
    )
    parser.add_argument(
        "--form",
        default=None,
        help="Creative form for parameterized pipelines such as 'creative'.",
    )
    parser.add_argument(
        "--primary-criterion",
        default=None,
        help="Primary creative criterion for the 'creative' pipeline.",
    )
    parser.set_defaults(func=cli_run)


def cli_run(args: argparse.Namespace) -> int:
    """Dispatch ``megaplan run`` — list / describe / execute by name.

    Thin wrapper around the registry: every action resolves the
    pipeline through :class:`megaplan._pipeline.registry.PipelineRegistry`
    with no YAML dispatch branch.
    """

    from megaplan._pipeline.registry import (
        describe_pipeline,
        pipeline_metadata,
        registered_pipelines,
    )

    if args.list_pipelines:
        names = list(registered_pipelines())
        if not names:
            print("(no pipelines registered)")
            return 0
        print("Pipelines:")
        for name in names:
            desc = describe_pipeline(name)
            if not desc:
                meta = pipeline_metadata(name)
                desc = str(meta.get("description", "") or "")
            print(f"  {name:24s} {desc}")
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
        return _describe_pipeline(args.pipeline_name)

    reg_names = set(registered_pipelines())
    if args.pipeline_name not in reg_names:
        print(
            f"Error: Unknown pipeline {args.pipeline_name!r}. "
            f"Available: {', '.join(sorted(reg_names)) if reg_names else '(none)'}",
            file=sys.stderr,
        )
        return 2

    return _run_pipeline(args)


def _run_pipeline(args: argparse.Namespace) -> int:
    """Build the pipeline from the registry, apply preflight, then execute.

    Preserves the human-gate resume contract: when ``--resume-choice``
    is supplied, prior state and ``awaiting_user.json`` are reloaded
    from the plan_dir, the primary input is repointed to the latest
    artifact (continue-loop), and the executor re-enters at the paused
    stage via :func:`with_entry`.
    """

    from megaplan._pipeline.executor import run_pipeline
    from megaplan._pipeline.preflight import preflight_or_raise
    from megaplan._pipeline.registry import (
        pipeline_metadata,
    )
    from megaplan._pipeline.resume import with_entry
    from megaplan._pipeline.types import StepContext
    from megaplan.profiles import (
        apply_vendor_rewrite,
        load_profile_metadata,
        load_profiles,
        resolve_pipeline_profile,
    )

    pipeline_name = args.pipeline_name
    metadata = pipeline_metadata(pipeline_name)
    supported_modes = tuple(metadata.get("supported_modes", ()) or ())
    default_profile = metadata.get("default_profile") or None

    # Mode validation — only when the user explicitly passes a mode.
    mode = args.mode
    if mode and supported_modes and mode not in supported_modes:
        print(
            f"Error: Pipeline '{pipeline_name}' does not support mode "
            f"'{mode}'. Supported modes: {', '.join(supported_modes)}",
            file=sys.stderr,
        )
        return 2
    if not mode:
        mode = supported_modes[0] if supported_modes else "code"

    from megaplan.types import CliError

    pipeline = None
    try:
        _validate_run_parameters(args)
        if pipeline_name == "creative":
            pipeline = _build_pipeline_for_run(args)
    except CliError as error:
        _print_cli_error(error)
        return error.exit_code

    # Profile resolution (4-layer order).
    cli_profile = getattr(args, "profile", None)
    system_profiles = load_profiles()
    system_metadata = load_profile_metadata()
    try:
        resolved_profile = resolve_pipeline_profile(
            cli_profile,
            pipeline_name=pipeline_name,
            system_profiles=system_profiles,
            system_metadata=system_metadata,
            default_profile=default_profile,
        )
    except Exception as exc:  # noqa: BLE001 — surface as CLI error
        print(f"Error resolving profile: {exc}", file=sys.stderr)
        return 2

    vendor = getattr(args, "vendor", None)
    if vendor:
        try:
            resolved_profile = apply_vendor_rewrite(resolved_profile, vendor)
        except Exception as exc:  # noqa: BLE001
            print(f"Error applying --vendor: {exc}", file=sys.stderr)
            return 2

    try:
        preflight_or_raise(
            resolved_profile,
            pipeline_name=pipeline_name,
            profile_name=cli_profile or default_profile,
        )
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int):
            return code
        return 0 if code is None else 1

    inputs = _parse_inputs(args.inputs)
    input_file: str | None = getattr(args, "input_file", None)
    if input_file and "draft" not in inputs:
        inputs["draft"] = Path(input_file)
    user_supplied_inputs = bool(inputs)

    plan_dir = _resolve_plan_dir(args.plan_dir, pipeline_name)
    plan_dir.mkdir(parents=True, exist_ok=True)

    resume_choice = getattr(args, "resume_choice", None)
    paused_stage: str | None = None
    awaiting_user_data: dict[str, Any] | None = None
    if resume_choice and (plan_dir / "state.json").exists():
        try:
            existing_state = json.loads((plan_dir / "state.json").read_text())
        except (json.JSONDecodeError, OSError):
            existing_state = {}
        state: dict[str, Any] = existing_state
        paused_stage = existing_state.get("_pipeline_paused_stage")
        stored_inputs = existing_state.get("_inputs")
        if isinstance(stored_inputs, dict) and not user_supplied_inputs:
            inputs = {k: Path(v) for k, v in stored_inputs.items()}
        awaiting_path = plan_dir / "awaiting_user.json"
        if awaiting_path.exists():
            try:
                awaiting_user_data = json.loads(awaiting_path.read_text())
            except (json.JSONDecodeError, OSError):
                awaiting_user_data = None
    else:
        state = json.loads(args.state) if args.state else {}

    if not resume_choice:
        state["_pipeline_name"] = pipeline_name
        manifest_hash = metadata.get("manifest_hash")
        if isinstance(manifest_hash, str) and manifest_hash:
            state["_pipeline_manifest_hash"] = manifest_hash

    # Continue-loop input swap: repoint the primary input to the latest
    # version of the artifact the human edited. The "primary input" is
    # the first key of the persisted ``_inputs`` snapshot (dict
    # insertion order, preserved since Python 3.7). Falls back to no-op
    # if the snapshot is empty.
    if (
        resume_choice == "continue"
        and not user_supplied_inputs
        and awaiting_user_data is not None
        and inputs
    ):
        artifact_stage = awaiting_user_data.get("artifact_stage")
        if isinstance(artifact_stage, str) and artifact_stage:
            from megaplan._pipeline.step_helpers import latest_artifact

            latest = latest_artifact(plan_dir / artifact_stage)
            if latest is not None:
                primary_input = next(iter(inputs.keys()))
                inputs[primary_input] = latest

    if inputs:
        state["_inputs"] = {k: str(v) for k, v in inputs.items()}
        if "_inputs_original" not in state:
            state["_inputs_original"] = dict(state["_inputs"])

    if pipeline_name == "creative":
        _seed_creative_runtime_state(args, state, inputs)

    if pipeline is None:
        pipeline = _build_pipeline_for_run(args)
    if paused_stage and paused_stage in pipeline.stages:
        pipeline = with_entry(pipeline, paused_stage)

    ctx_inputs = dict(inputs)
    ctx_inputs.setdefault("_pipeline", pipeline_name)

    ctx = StepContext(
        plan_dir=plan_dir,
        state=state,
        profile=resolved_profile,
        mode=mode,
        inputs=ctx_inputs,
    )

    # Persist state.json before running so the executor's state-merge
    # carries forward our identity snapshot.
    try:
        write_plan_state(plan_dir, mode="replace", state=state)
    except OSError:
        pass

    try:
        result = run_pipeline(pipeline, ctx, artifact_root=plan_dir)
    except Exception as exc:  # noqa: BLE001 — CLI surface
        print(f"Error running pipeline: {exc}", file=sys.stderr)
        return 1

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


def _build_pipeline_for_run(args: argparse.Namespace):
    """Build a pipeline, applying CLI parameters for parameterized pipelines."""

    from megaplan._pipeline.registry import get_pipeline

    if args.pipeline_name == "creative":
        from megaplan.pipelines.creative import build_pipeline

        return build_pipeline(
            form=getattr(args, "form", None) or "joke",
            primary_criterion=getattr(args, "primary_criterion", None),
        )
    return get_pipeline(args.pipeline_name)


def _validate_run_parameters(args: argparse.Namespace) -> None:
    from megaplan.types import CliError

    pipeline_name = getattr(args, "pipeline_name", None)
    form = getattr(args, "form", None)
    primary_criterion = getattr(args, "primary_criterion", None)

    if pipeline_name != "creative":
        creative_options = []
        if form is not None:
            creative_options.append("--form")
        if primary_criterion is not None:
            creative_options.append("--primary-criterion")
        if creative_options:
            raise CliError(
                "invalid_args",
                ", ".join(creative_options)
                + " are only supported with the 'creative' pipeline.",
                exit_code=2,
            )


def _print_cli_error(error: CliError) -> None:
    payload: dict[str, Any] = {
        "success": False,
        "error": error.code,
        "message": error.message,
    }
    if error.valid_next:
        payload["valid_next"] = error.valid_next
    if error.extra:
        payload["details"] = dict(error.extra)
    print(json.dumps(payload))


def _seed_creative_runtime_state(
    args: argparse.Namespace,
    state: dict[str, Any],
    inputs: dict[str, Path],
) -> None:
    raw_config = state.get("config", {})
    config = dict(raw_config) if isinstance(raw_config, dict) else {}
    config["mode"] = "creative"
    config["form"] = getattr(args, "form", None) or config.get("form") or "joke"
    primary_criterion = getattr(args, "primary_criterion", None)
    if primary_criterion is not None:
        config["primary_criterion"] = primary_criterion
    else:
        config.setdefault("primary_criterion", "")
    config.setdefault("project_dir", str(Path.cwd()))
    state["config"] = config
    state.setdefault("idea", _creative_idea_seed(args, inputs))


def _creative_idea_seed(args: argparse.Namespace, inputs: dict[str, Path]) -> str:
    raw_state = getattr(args, "state", None)
    if raw_state:
        try:
            parsed = json.loads(raw_state)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            idea = parsed.get("idea")
            if isinstance(idea, str):
                return idea

    for key in ("idea", "draft"):
        path = inputs.get(key)
        if path is not None:
            try:
                return path.read_text(encoding="utf-8")
            except OSError:
                return str(path)
    return ""


def _describe_pipeline(name: str) -> int:
    """Describe a pipeline using registry metadata + SKILL.md.

    Reads the pipeline's per-name metadata dict from
    :attr:`PipelineRegistry.metadata` and the colocated ``SKILL.md``
    (when present) from :meth:`PipelineRegistry.read_skill_md`. Returns
    ``0`` on success and ``2`` when the name is unknown.
    """

    from megaplan._pipeline.registry import (
        pipeline_metadata,
        read_pipeline_skill_md,
        registered_pipelines,
    )

    if name not in registered_pipelines():
        print(f"Error: Unknown pipeline {name!r}", file=sys.stderr)
        return 2

    metadata = pipeline_metadata(name)
    lines: list[str] = [f"Pipeline: {name}"]
    source_path = metadata.get("source_path")
    if source_path:
        lines.append(f"Source:   {source_path}")
    description = metadata.get("description")
    if description:
        lines.append("")
        lines.append(str(description))
    default_profile = metadata.get("default_profile")
    if default_profile:
        lines.append("")
        lines.append(f"Default profile: {default_profile}")
    recommended = metadata.get("recommended_profiles") or ()
    if recommended:
        lines.append(f"Recommended:     {', '.join(recommended)}")
    supported_modes = metadata.get("supported_modes") or ()
    if supported_modes:
        lines.append(f"Modes:           {', '.join(supported_modes)}")

    skill_md = read_pipeline_skill_md(name)
    if skill_md:
        lines.append("")
        lines.append("─── SKILL.md ───")
        lines.append(skill_md.strip())

    print("\n".join(lines))
    return 0


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
