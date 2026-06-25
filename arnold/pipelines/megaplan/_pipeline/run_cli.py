"""``megaplan run <pipeline-name>`` — CLI for the pipeline registry.

Lets users invoke any registered pipeline (built-in or Python-module
discovered) from the command line. Examples::

    megaplan run --list
    megaplan run writing-panel-strict path/to/draft.md
    megaplan run writing-panel-strict path/to/draft.md \
        --profile @writing-panel-strict:standard

Demo pipelines (``doc-critique``, ``judges``) are not registered as
built-ins; run them directly via their Python modules::

    python -c "from arnold.pipelines.megaplan._pipeline.demos.doc_critique import run_demo; ..."
    python -c "from arnold.pipelines.megaplan._pipeline.demo_judges import run_demo; ..."

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

from arnold.pipeline.native.routing import (
    RUNTIME_NATIVE,
    RuntimeOwner,
    has_native_dispatch_capability,
    normalize_runtime_owner,
    select_fresh_runtime_owner,
)
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.runtime.resume import TRUST_TRUSTED
from arnold.pipelines.megaplan._core.state import write_plan_state


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
        "--runtime",
        choices=["graph", "native"],
        default=None,
        help=(
            "Runtime for this run. Use 'graph' as the compatibility fallback; "
            "native requires a pipeline with native dispatch capability."
        ),
    )
    parser.add_argument(
        "--executor",
        choices=["graph", "native"],
        default=None,
        help="Deprecated alias for --runtime.",
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

    from arnold.pipelines.megaplan._pipeline.registry import (
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

    from arnold.pipelines.megaplan._pipeline._bridge import run_pipeline_dispatch
    from arnold.pipelines.megaplan._pipeline.registry import (
        pipeline_metadata,
    )
    from arnold.pipelines.megaplan._pipeline.resume import with_entry
    from arnold.pipelines.megaplan._pipeline.types import StepContext
    from arnold.pipelines.megaplan.profiles import (
        apply_vendor_rewrite,
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

    from arnold.pipelines.megaplan.types import CliError

    pipeline = None
    try:
        _validate_run_parameters(args)
        if pipeline_name == "creative":
            pipeline = _build_pipeline_for_run(args)
    except CliError as error:
        _print_cli_error(error)
        return error.exit_code

    cli_profile = getattr(args, "profile", None)
    try:
        pipeline = pipeline or _build_pipeline_for_run(args)
        resolved_profile = _resolve_profile_for_run(
            pipeline_name=pipeline_name,
            metadata=metadata,
            pipeline=pipeline,
            cli_profile=cli_profile,
            default_profile=default_profile,
            megaplan_resolver=resolve_pipeline_profile,
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

    preflight_code = _validate_profile_for_run(
        pipeline_name=pipeline_name,
        resolved_profile=resolved_profile,
        profile_name=cli_profile or default_profile,
        vendor=vendor,
    )
    if preflight_code is not None:
        return preflight_code

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
        try:
            runtime_override = _runtime_selection_from_args(args)
            if runtime_override is not None:
                _validate_runtime_selection(
                    pipeline_name=pipeline_name,
                    pipeline=pipeline,
                    runtime=runtime_override,
                )
                runtime_owner = runtime_override
            else:
                runtime_owner = select_fresh_runtime_owner(
                    pipeline,
                    state=state,
                )
            runtime_envelope = _runtime_identity_block(
                pipeline_name=pipeline_name,
                metadata=metadata,
                state=state,
                plan_dir=plan_dir,
                runtime=runtime_owner,
            )
        except CliError as error:
            _print_cli_error(error)
            return error.exit_code
        state["_pipeline_name"] = runtime_envelope["plugin_id"]
        state["_pipeline_manifest_hash"] = runtime_envelope["manifest_hash"]
        state["_runtime_identity_schema_version"] = RuntimeEnvelope.schema_version
        state["runtime_envelope"] = runtime_envelope
        raw_meta = state.get("meta")
        meta = dict(raw_meta) if isinstance(raw_meta, dict) else {}
        meta["executor"] = runtime_owner
        state["meta"] = meta

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
            from arnold.pipelines.megaplan._pipeline.step_helpers import latest_artifact

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
        result = run_pipeline_dispatch(pipeline, ctx, artifact_root=plan_dir, pipeline_key=pipeline_name)
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

    from arnold.pipelines.megaplan._pipeline.registry import get_pipeline

    if args.pipeline_name == "creative":
        from arnold.pipelines.megaplan.pipelines.creative import build_pipeline

        return build_pipeline(
            form=getattr(args, "form", None) or "joke",
            primary_criterion=getattr(args, "primary_criterion", None),
        )
    return get_pipeline(args.pipeline_name)


def _validate_run_parameters(args: argparse.Namespace) -> None:
    from arnold.pipelines.megaplan.types import CliError

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


def _runtime_selection_from_args(args: argparse.Namespace) -> RuntimeOwner | None:
    """Resolve the documented runtime flag and deprecated executor alias."""
    from arnold.pipelines.megaplan.types import CliError

    runtime_raw = getattr(args, "runtime", None)
    executor_raw = getattr(args, "executor", None)
    runtime_owner = normalize_runtime_owner(runtime_raw)
    executor_owner = normalize_runtime_owner(executor_raw)

    if runtime_raw is not None and runtime_owner is None:
        raise CliError(
            "invalid_args",
            f"unsupported --runtime {runtime_raw!r}; expected 'graph' or 'native'",
            exit_code=2,
        )
    if executor_raw is not None and executor_owner is None:
        raise CliError(
            "invalid_args",
            f"unsupported --executor {executor_raw!r}; expected 'graph' or 'native'",
            exit_code=2,
        )
    if runtime_owner is not None and executor_owner is not None and runtime_owner != executor_owner:
        raise CliError(
            "invalid_args",
            "--runtime and --executor disagree; pass one runtime selection",
            extra={"runtime": runtime_raw, "executor": executor_raw},
            exit_code=2,
        )
    return runtime_owner or executor_owner


def _validate_runtime_selection(
    *,
    pipeline_name: str,
    pipeline: Any,
    runtime: RuntimeOwner,
) -> None:
    from arnold.pipelines.megaplan.types import CliError

    if runtime != RUNTIME_NATIVE:
        return
    if has_native_dispatch_capability(pipeline):
        return
    raise CliError(
        "native_runtime_unavailable",
        f"Pipeline '{pipeline_name}' cannot run with --runtime native; "
        "use --runtime graph or omit --runtime.",
        extra={"pipeline": pipeline_name, "runtime": runtime},
        exit_code=2,
    )


def _resolve_profile_for_run(
    *,
    pipeline_name: str,
    metadata: dict[str, Any],
    pipeline: Any,
    cli_profile: str | None,
    default_profile: str | None,
    megaplan_resolver: Any,
) -> dict[str, str]:
    from arnold.pipeline.profiles import (
        ProfileLoadError,
        load_profile_metadata,
        load_profiles,
        resolve_default_profile,
    )
    from arnold.pipelines.megaplan._pipeline.registry import canonical_pipeline_name

    if canonical_pipeline_name(pipeline_name) == "megaplan":
        return megaplan_resolver(
            cli_profile,
            pipeline_name=pipeline_name,
            default_profile=default_profile,
        )

    declared_stage_keys = frozenset(str(name) for name in getattr(pipeline, "stages", {}).keys())
    if not declared_stage_keys:
        return {}

    built_in_paths = _pipeline_profile_paths(pipeline_name, metadata)
    profiles = load_profiles(
        built_in_paths=built_in_paths,
        declared_stage_keys=declared_stage_keys,
        metadata_keys=frozenset({"default", "extends"}),
    )
    if not profiles:
        if cli_profile or default_profile:
            requested = cli_profile or default_profile or ""
            raise ProfileLoadError(
                "unknown_profile",
                f"Pipeline '{pipeline_name}' does not define any local profiles for {requested!r}.",
            )
        return {}

    metadata_map = load_profile_metadata(
        built_in_paths=built_in_paths,
        declared_stage_keys=declared_stage_keys,
        metadata_keys=frozenset({"default", "extends"}),
    )
    profile_name = _selected_pipeline_profile_name(
        cli_profile or default_profile,
        pipeline_name=pipeline_name,
    )
    _resolved_name, stage_map = resolve_default_profile(
        profiles,
        metadata=metadata_map,
        default_name=profile_name,
    )
    return stage_map


def _selected_pipeline_profile_name(
    profile_ref: str | None,
    *,
    pipeline_name: str,
) -> str | None:
    from arnold.pipeline.profiles import ProfileLoadError

    if not profile_ref:
        return None
    if not profile_ref.startswith("@"):
        return profile_ref

    reference = profile_ref[1:]
    if ":" not in reference:
        return reference or None

    ref_pipeline, ref_profile = reference.split(":", 1)
    if ref_pipeline and ref_pipeline != pipeline_name:
        raise ProfileLoadError(
            "unknown_profile",
            f"Profile {profile_ref!r} targets pipeline '{ref_pipeline}', "
            f"but run_cli only loads local profiles for '{pipeline_name}'.",
        )
    return ref_profile or None


def _pipeline_profile_paths(pipeline_name: str, metadata: dict[str, Any]) -> tuple[Path, ...]:
    candidates: list[Path] = []
    source_path = metadata.get("source_path")
    if isinstance(source_path, str) and source_path:
        source = Path(source_path)
        profile_dirs = []
        if source.name == "__init__.py":
            profile_dirs.append(source.parent / "profiles")
        profile_dirs.extend(
            (
                source.parent / pipeline_name / "profiles",
                source.parent / source.stem.replace("_", "-") / "profiles",
            )
        )
        for profile_dir in profile_dirs:
            if profile_dir.is_dir():
                candidates.extend(sorted(profile_dir.glob("*.toml")))

    home_dir = Path.home() / ".megaplan" / "pipelines" / pipeline_name / "profiles"
    if home_dir.is_dir():
        candidates.extend(sorted(home_dir.glob("*.toml")))

    deduped: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(candidate)
    return tuple(deduped)


def _validate_profile_for_run(
    *,
    pipeline_name: str,
    resolved_profile: dict[str, Any],
    profile_name: str | None,
    vendor: str | None = None,
) -> int | None:
    from arnold.runtime.operations import OperationKind, OperationRequest
    from arnold.pipelines.megaplan._pipeline import preflight as preflight_module
    from arnold.pipelines.megaplan._pipeline.registry import (
        canonical_pipeline_name,
        dispatch_operation_for,
        supported_operations_for,
    )

    if OperationKind.PROFILE_VALIDATE in supported_operations_for(pipeline_name):
        result = dispatch_operation_for(
            pipeline_name,
            OperationRequest(
                kind=OperationKind.PROFILE_VALIDATE,
                payload={
                    "profile": dict(resolved_profile),
                    "pipeline_name": pipeline_name,
                    "profile_name": profile_name,
                },
            ),
        )
        if result.ok:
            return None
        payload = result.payload if isinstance(result.payload, dict) else {}
        exit_code = payload.get("exit_code")
        if isinstance(exit_code, int):
            return exit_code
        return 1

    if canonical_pipeline_name(pipeline_name) != "megaplan":
        return None

    try:
        preflight_module.preflight_or_raise(
            resolved_profile,
            pipeline_name=pipeline_name,
            profile_name=profile_name,
            vendor=vendor,
        )
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int):
            return code
        return 0 if code is None else 1
    return None


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


def _runtime_identity_block(
    *,
    pipeline_name: str,
    metadata: dict[str, Any],
    state: dict[str, Any],
    plan_dir: Path,
    runtime: str,
) -> dict[str, Any]:
    from arnold.pipelines.megaplan._pipeline.registry import canonical_pipeline_name
    from arnold.pipeline.discovery.manifest import ManifestError, read_manifest
    from arnold.pipelines.megaplan.types import CliError

    plugin_id = canonical_pipeline_name(pipeline_name)
    manifest_hash = metadata.get("manifest_hash")
    if not isinstance(manifest_hash, str) or not manifest_hash:
        source_path = metadata.get("source_path")
        if isinstance(source_path, str) and source_path:
            manifest = read_manifest(Path(source_path))
            if not isinstance(manifest, ManifestError):
                manifest_hash = manifest.manifest_hash
    if not isinstance(plugin_id, str) or not plugin_id:
        raise CliError(
            "pipeline_identity_unavailable",
            "canonical pipeline identity is unavailable for this run",
        )
    if not isinstance(manifest_hash, str) or not manifest_hash:
        raise CliError(
            "pipeline_identity_unavailable",
            f"manifest identity metadata is unavailable for pipeline '{pipeline_name}'",
            extra={"pipeline": pipeline_name},
        )

    run_id = state.get("name")
    if not isinstance(run_id, str) or not run_id:
        run_id = plan_dir.name

    plugin_state_schema_version = metadata.get("plugin_state_schema_version", 0)
    if not isinstance(plugin_state_schema_version, int):
        plugin_state_schema_version = 0

    envelope = RuntimeEnvelope(
        plugin_id=plugin_id,
        manifest_hash=manifest_hash,
        plugin_state_schema_version=plugin_state_schema_version,
        run_id=run_id,
        artifact_root=str(plan_dir),
        resume_cursor=None,
        trust_state=TRUST_TRUSTED,
    )
    payload = json.loads(envelope.to_json())
    payload["runtime"] = runtime
    return payload


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

    from arnold.pipelines.megaplan._pipeline.registry import (
        canonical_pipeline_name,
        pipeline_disposition,
        pipeline_metadata,
        read_pipeline_skill_md,
        registered_pipelines,
    )

    name = canonical_pipeline_name(name)
    disposition = pipeline_disposition(name)
    if disposition is not None and disposition.status == "rejected":
        suffix = (
            f" [{disposition.rejection_code}]"
            if disposition.rejection_code
            else ""
        )
        print(
            f"Error: Pipeline {name!r} rejected: {disposition.reason}{suffix}",
            file=sys.stderr,
        )
        return 2

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
    manifest_hash = metadata.get("manifest_hash")
    if manifest_hash:
        lines.append(f"Manifest: {manifest_hash}")
    driver = metadata.get("driver")
    if driver:
        if isinstance(driver, (list, tuple)):
            driver_text = " / ".join(str(part) for part in driver)
        else:
            driver_text = str(driver)
        lines.append(f"Driver:   {driver_text}")
    registration_kind = metadata.get("registration_kind")
    if registration_kind:
        lines.append(f"Registration: {registration_kind}")
    disposition_state = getattr(disposition, "status", None) if disposition else None
    if disposition_state:
        lines.append(f"Disposition:  {disposition_state}")
    validation_code = metadata.get("validation_rejection_code")
    if validation_code:
        lines.append(f"Validation:   {validation_code}")
    validation_issues = metadata.get("validation_issues") or ()
    for issue in validation_issues:
        if isinstance(issue, dict):
            code = issue.get("code") or "validation"
            message = issue.get("message") or issue
            lines.append(f"  - [{code}] {message}")
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
