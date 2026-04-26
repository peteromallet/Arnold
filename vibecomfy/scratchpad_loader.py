from __future__ import annotations

import importlib.util
from pathlib import Path

from vibecomfy.schema import SchemaProvider

from .workflow import VibeWorkflow


def load_scratchpad(path: str | Path) -> VibeWorkflow:
    path = Path(path)
    spec = importlib.util.spec_from_file_location(f"vibecomfy_scratchpad_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not import scratchpad {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    build = getattr(module, "build", None)
    if build is None:
        raise ValueError(f"Scratchpad {path} must define build()")
    workflow = build()
    if not isinstance(workflow, VibeWorkflow):
        raise TypeError(f"Scratchpad build() must return VibeWorkflow, got {type(workflow).__name__}")
    return workflow


def render_scratchpad(source: str, *, source_is_path: bool = False, schema_provider: SchemaProvider | None = None) -> str:
    loader = "workflow_from_file" if source_is_path else "workflow_from_template"
    provider_arg = ', schema_provider=get_schema_provider("auto")' if schema_provider is not None else ""
    source_literal = repr(str(source))
    return f'''from vibecomfy import {loader}, run
from vibecomfy.schema import get_schema_provider


def build():
    workflow = {loader}({source_literal}{provider_arg})
    # Edit this file with VibeWorkflow methods, for example:
    # workflow.set_prompt("a cinematic robot painter")
    # workflow.set_seed(123)
    # workflow.set_steps(20)
    return workflow


async def main():
    result = await run(build())
    print(result.outputs)
'''
