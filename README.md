# VibeComfy

VibeComfy is a Python package for discovering, normalizing, validating, analyzing, and running ComfyUI workflows through one editable intermediate representation: `VibeWorkflow`. JSON workflows are treated as input and output formats; edits and higher-level tooling should operate on `VibeWorkflow`.

There are two core paths:

```text
JSON/UI workflow source -> normalized API dict -> VibeWorkflow
authored scratchpad -> VibeWorkflow -> Comfy API dict -> runtime queue
```

`convert` bridges the two paths by generating scratchpad files from ingested
JSON/UI workflows. Generated scratchpads and run outputs live under `out/`.

## Project Layout

- `vibecomfy/workflow.py`: the editable workflow IR, compile targets, validation report types, and convenience setters.
- `vibecomfy/ingest/`: JSON and UI workflow loading, normalization, conversion, and index writing.
- `vibecomfy/registry/`: lookup helpers for indexed workflows and ready Python templates.
- `vibecomfy/runtime/`: embedded and server-backed Comfy runtime helpers.
- `vibecomfy/commands/`: CLI command modules registered by `vibecomfy.cli`.
- `vibecomfy/schema/`: schema-provider home for `/object_info` and local node metadata.
- `vibecomfy/analysis/`: graph analysis primitives and CLI-backed inspection commands.
- `vibecomfy/search/`: node and workflow search indexes, aliases, and ranking.

See `docs/vibeworkflow.md` for the IR contract and `docs/old_vibecomfy_port_rationale.md` for the staged port rationale.

## CLI

Run commands with `python -m vibecomfy.cli ...` from the repository root. The installed console script is `vibecomfy = "vibecomfy.cli:main"` when the package is installed.

- `sources sync`: index official workflows, external workflow examples, and custom-node examples.
- `workflows list`: list indexed workflows; add `--ready` to list ready Python templates.
- `nodes list`: list indexed Comfy node classes.
- `inspect <workflow>`: show workflow metadata, requirements, inputs, and runnable status.
- `convert <workflow> --out <path>`: generate a Python scratchpad from a workflow.
- `validate <workflow>`: validate a JSON workflow or generated scratchpad.
- `doctor <workflow>`: report workflow requirements and runtime readiness.
- `runtime doctor`: check runtime dependencies.
- `runtime smoke`: run a minimal runtime smoke check.
- `run <workflow>`: execute through the embedded runtime by default; add `--ready` to run a ready Python template by id.
- `logs tail`: tail recent run logs.
- `analyze ...`: graph analysis commands such as `info`, `trace`, `path`, `values`, and `diff`.
- `search <query>`: weighted node/workflow search with task aliases such as `i2v`, `controlnet`, `wan`, `ltx`, and `audio_reactive`.

## Quick Start

```bash
python -m vibecomfy.cli sources sync
python -m vibecomfy.cli workflows list --limit 5
python -m vibecomfy.cli workflows list --ready --limit 5
python -m vibecomfy.cli inspect z_image
python -m vibecomfy.cli convert z_image --out out/scratchpads/z_image.py
python -m vibecomfy.cli validate out/scratchpads/z_image.py
python -m vibecomfy.cli analyze info workflow_corpus/official/image/z_image.json
python -m vibecomfy.cli search wan --task i2v
python -m vibecomfy.cli run out/scratchpads/z_image.py --runtime embedded
```

The local workflow corpus is rooted at `workflow_corpus/`. Ready Python templates are under `ready_templates/` and remain addressable with the `--ready` flags on `workflows list` and `run`.
