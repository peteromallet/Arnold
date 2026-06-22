<!-- M5 Phase 1 inventory: CLI dispatch chain. -->

# M5 CLI Dispatch Chain

## Entrypoints

| Entrypoint | Target function | Behavior |
| --- | --- | --- |
| Console script `arnold` | `arnold.cli:cli_entry` | Lazy dispatcher; `workflow` and retained operator commands avoid importing legacy Megaplan modules. |
| `python -m arnold` | `arnold.__main__` -> `arnold.cli.cli_entry` | Same as console script. |
| `python -m arnold.cli.execution` | `arnold.cli.execution:main` | Compiled-manifest runner (existing). |
| `python -m arnold.pipelines.megaplan` | `arnold_pipelines.megaplan.cli:main` | Legacy Megaplan CLI (transition-only). |
| `python -m arnold_pipelines.megaplan` | `arnold_pipelines.megaplan.__main__` | Alias to legacy Megaplan CLI. |

## Dispatch flow

```text
arnold [argv...]
  |
  +-- arnold.cli.cli_entry()
        |
        +-- arnold.cli.main(argv)
              |
              +-- "workflow" -> arnold.cli.workflow.main(rest)
              |
              +-- "status"   -> arnold.cli.operators.status(rest)
              +-- "trace"    -> arnold.cli.operators.trace(rest)
              +-- "inspect"  -> arnold.cli.operators.inspect(rest)
              +-- "override" -> arnold.cli.operators.override(rest)
              |
              +-- legacy commands -> lazy import arnold.pipelines.megaplan.cli.arnold
```

## Completion generators

| Generator source | Produced artifact | M6 disposition |
| --- | --- | --- |
| `arnold_pipelines/megaplan/cli/parser.py` | shell completion for legacy Megaplan CLI | delete |
| `arnold_pipelines/megaplan/cli/arnold.py` | top-level parser surface | delete |
| `arnold/cli/workflow.py` | workflow subcommand parser | keep |
| `arnold/cli/operators.py` | operator subcommand parser | keep |

## Lazy-import rules

- `arnold workflow ...` must not trigger an import of `arnold.pipelines.megaplan.cli.arnold`, `arnold_pipelines.megaplan.cli`, or any old `arnold.pipeline` authoring module.
- Retained operator commands import only `arnold.execution.*`, `arnold.manifest.*`, and `arnold.workflow` public surfaces.
- Legacy commands remain reachable for transition but are gated behind an explicit lazy import.
