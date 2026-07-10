from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vibecomfy.registry import load_workflow_reference
from vibecomfy.runtime.session import EmbeddedSession, SessionConfig
from vibecomfy.schema import get_schema_provider


def _loaded_model_count() -> int | None:
    try:
        from comfy.model_management import current_loaded_models
    except (ImportError, AttributeError):
        return None
    try:
        return len(current_loaded_models)
    except TypeError:
        return None


async def _run(args: argparse.Namespace) -> int:
    provider = get_schema_provider("auto")
    first = load_workflow_reference(
        args.first,
        schema_provider=provider,
        allow_scratchpad=True,
        ready=args.ready,
    )
    second_ref = args.second or args.first
    second = load_workflow_reference(
        second_ref,
        schema_provider=provider,
        allow_scratchpad=True,
        ready=args.ready,
    )
    session = EmbeddedSession(SessionConfig.from_workflow_metadata(first))
    try:
        start = time.perf_counter()
        first_result = await session.run(first, backend=args.backend)
        first_elapsed = time.perf_counter() - start
        print(f"first_elapsed_s: {first_elapsed:.3f}")
        print(f"first_prompt_id: {first_result.prompt_id}")
        print(f"loaded_models_after_first: {_loaded_model_count()}")

        start = time.perf_counter()
        second_result = await session.run(second, backend=args.backend)
        second_elapsed = time.perf_counter() - start
        print(f"second_elapsed_s: {second_elapsed:.3f}")
        print(f"second_prompt_id: {second_result.prompt_id}")
        print(f"loaded_models_after_second: {_loaded_model_count()}")
    finally:
        await session.stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run two workflow references through one EmbeddedSession for manual GPU smoke."
    )
    parser.add_argument("first", help="First workflow reference or path.")
    parser.add_argument("second", nargs="?", help="Second workflow reference or path; defaults to first.")
    parser.add_argument("--ready", action="store_true")
    parser.add_argument("--backend", default="api")
    args = parser.parse_args(argv)
    Path("out/runs").mkdir(parents=True, exist_ok=True)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
