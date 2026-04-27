from __future__ import annotations

import argparse
import sys
from typing import Any

from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.runtime.run import run_embedded_sync, run_sync
from vibecomfy.runtime.session import find_active_session
from vibecomfy.schema import get_schema_provider


_OVERRIDE_HINTS = {
    "prompt": (
        "--prompt is only wired when the workflow contains a known mainline prompt encoder "
        "(see vibecomfy.metadata.PROMPT_NODE_CLASSES). Edit the source workflow's prompt "
        "fields directly, or extend PROMPT_NODE_CLASSES if a custom-node class genuinely "
        "accepts a free-form image prompt."
    ),
    "steps": (
        "--steps is only wired when the workflow contains a known mainline sampler "
        "(see vibecomfy.metadata.STEPS_NODE_CLASSES). Edit the source workflow's sampler "
        "step count directly, or extend STEPS_NODE_CLASSES if a custom-node class exposes "
        "a true sample-step count."
    ),
}


def load_workflow_reference(value: str, **kwargs: Any):
    return load_workflow_any(value)


def _override_unwired_message(workflow_id: str, flag: str, override: str) -> str:
    hint = _OVERRIDE_HINTS[override]
    return (
        f"run failed: workflow {workflow_id!r} has no eligible target for {flag}. {hint}"
    )


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        session_url = args.server_url
        if session_url is None and args.runtime in {"auto", "server"}:
            session_url = find_active_session("default")
        schema_provider = get_schema_provider("auto", server_url=session_url)
        workflow = load_workflow_reference(
            args.path,
            schema_provider=schema_provider,
            allow_scratchpad=True,
            ready=args.ready,
        )
        if args.prompt is not None:
            if workflow.inputs.get("prompt") is None:
                print(_override_unwired_message(workflow.id, "--prompt", "prompt"), file=sys.stderr)
                return 2
            workflow.set_prompt(args.prompt)
        if args.seed is not None:
            workflow.set_seed(args.seed)
        if args.steps is not None:
            if workflow.inputs.get("steps") is None:
                print(_override_unwired_message(workflow.id, "--steps", "steps"), file=sys.stderr)
                return 2
            workflow.set_steps(args.steps)
        if args.runtime == "embedded":
            result = run_embedded_sync(workflow, backend=args.backend)
        elif args.runtime == "auto":
            if session_url:
                result = run_sync(workflow, server_url=session_url, backend=args.backend)
            else:
                result = run_embedded_sync(workflow, backend=args.backend)
        elif args.runtime == "server":
            result = run_sync(workflow, server_url=session_url, backend=args.backend)
        else:
            print(f"unknown runtime: {args.runtime}", file=sys.stderr)
            return 2
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"run failed: {exc}", file=sys.stderr)
        return 1
    print(f"run_id: {result.run_id}")
    print(f"prompt_id: {result.prompt_id}")
    for output in result.outputs:
        print(f"output: {output}")
    print(f"metadata: {result.metadata_path}")
    print(f"log: {result.log_path}")
    return 0


def register(subparsers) -> None:
    run = subparsers.add_parser("run")
    run.add_argument("path")
    run.add_argument("--ready", action="store_true")
    run.add_argument("--runtime", choices=["auto", "embedded", "server"], default="auto")
    run.add_argument("--server-url")
    run.add_argument("--backend", default="api")
    run.add_argument("--prompt")
    run.add_argument("--seed", type=int)
    run.add_argument("--steps", type=int)
    run.set_defaults(func=_cmd_run)
