# Arnold Authoring Guide

Arnold is the module-oriented face of Megaplan pipelines. Use it when a workflow
should be discoverable as a named module, runnable from the CLI, inspectable by
the pipeline checker, and documented for agents through a sibling `SKILL.md`.

This page is authored guidance. Code-owned field lists, schema surfaces, defect
templates, command inventories, and vocabulary live in the generated reference:
[`docs/reference/arnold-projections.md`](../reference/arnold-projections.md).

## Choose the Right Artifact

Author a pipeline module when the workflow has a stable graph and can be
expressed as typed stages. Author a prompt or skill-only extension when the
existing planning pipeline already has the right control flow and only needs
domain instructions. Build a Capsule when you need a replayable outward
projection of an epic's exported evidence. Build a Warrant only when the source
projection is complete enough to sign.

Those boundaries matter because the three terminal sinks have different trust
contracts:

- Builder modules describe executable behavior and are validated by pipeline
  discovery and graph checks.
- Capsules package exported evidence and declared contract facts into
  content-addressed records.
- Warrants sign a frozen source projection and must reject incomplete source
  inventory before any signing key is used.

## Scaffold a Module

Start with the documented Arnold command:

```bash
arnold pipelines new my-module --driver graph
```

The command creates a Python module under `megaplan/pipelines/` and a sibling
`SKILL.md` directory. `--driver graph` is the accepted driver today; the command
is intentionally explicit so later driver shapes have room to appear without
changing the current scaffold.

The generated module is a small graph builder. Replace the placeholder
description, prompt path, and pipeline stages, then keep the module-level
metadata accurate enough for no-import discovery. The canonical package and
manifest facts are generated in the Arnold projection reference rather than
copied here by hand.

## Build the Graph

Prefer `Pipeline.builder(...)` for normal module authoring. It keeps stage
construction readable and still returns the plain frozen `Pipeline` type used by
the executor.

```python
from pathlib import Path

from megaplan._pipeline.types import Pipeline

_PIPELINE_DIR = Path(__file__).parent / "my-module"

name = "my-module"
description = "Review a draft and emit a revised Markdown artifact."
driver = ("graph", "dispatch+emit")
entrypoint = "build_pipeline"
arnold_api_version = "1.0"
capabilities = ("document-review",)


def build_pipeline() -> Pipeline:
    return (
        Pipeline.builder(
            name,
            description=description,
            pipeline_dir=_PIPELINE_DIR,
        )
        .input("draft", file=True)
        .agent("review", prompt="prompts/review.md", inputs=["draft"])
        .agent("revise", prompt="prompts/revise.md", inputs=["review"])
        .build()
    )
```

Use the lower-level `Stage` and `Edge` dataclasses only when the builder cannot
express the shape cleanly. If a stage emits typed recommendations, route with
gate edges instead of ad hoc string labels so contract checks and future replay
tools can reason about the topology.

## Keep Metadata Boring

Discovery reads manifest-like module metadata without importing the module when
manifest-first discovery is enabled. Keep top-level metadata simple literals:
strings, tuples, and dict/list values that can be parsed statically. Do not hide
metadata behind function calls, environment reads, or imports.

If the module needs dynamic inputs at runtime, declare the stable facts anyway
and let unresolved dynamic inputs show up in the static behavioral manifest. An
explicit unresolved input is better than an accidental import-time side effect.

## Validate Locally

Run the checker after every structural edit:

```bash
megaplan pipelines check my-module
arnold pipelines check my-module
```

Use `doctor` when discovery itself is surprising:

```bash
megaplan pipelines doctor
arnold pipelines doctor
```

The checker validates executable graphs and judge manifests. The generated
reference lists the current defect surfaces and CLI facts; this guide only
explains when to use them.

## Package Evidence Deliberately

Capsules are not a replacement for the old deterministic epic export. The
Capsule build path consumes the export, stores records through the
content-addressed Capsule writer, and references Evidence payloads by path and
hash instead of inlining their bytes. By default, export errors stop the build.
Use degraded output only when the caller intentionally accepts an incomplete
projection:

```bash
MEGAPLAN_M7_SINKS=1 megaplan epic capsule build EPIC_ID
MEGAPLAN_M7_SINKS=1 megaplan epic capsule build EPIC_ID --allow-degraded
```

Treat `replay_ready=false` as meaningful. Current Capsule builds may preserve
evidence and contracts before all replay requirements are satisfiable.

## Sign Only Complete Sources

Warrants are signed attestations over source projections, not free-form
summaries. Build the source projection first, inspect its completeness, and
sign only when required fields are present. The inventory adapter is read-only:
missing or unsupported facts stay missing or unsupported rather than being
invented or written into receipts.

Configure the signing key with `MEGAPLAN_SIGNING_WARRANT_KEY` or pass an
explicit key through the API. Empty keys are errors.

## Update Generated References Separately

When code-owned facts change, update the generated reference instead of editing
fact tables into these authored docs:

```bash
python scripts/generate_arnold_docs.py --write
python scripts/generate_arnold_docs.py --check
```

Authored pages should explain why and when to use a surface. Generated pages
should carry exact fields, constants, schemas, and inventories.
