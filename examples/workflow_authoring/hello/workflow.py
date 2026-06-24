"""Hello-world example of a Python-shaped Arnold workflow.

This is a deliberately small V1-authored workflow. It demonstrates that a
shipped pipeline can be a `workflow.py` file plus typed component imports.
"""

from __future__ import annotations

from arnold.workflow.authoring import workflow

from .components import greet, respond


@workflow(id="hello-world", version="1.0")
def hello(name: str) -> None:
    greeting = greet(id="greet", name=name)
    respond(id="respond", greeting=greeting)
