<!-- M5 Phase 1 inventory: CLI command mapping. -->

# M5 CLI Command Mapping

| Old command | New command / disposition | Transition behavior | M6 disposition |
| --- | --- | --- | --- |
| `arnold workflow check` | new | Validate a `--module package.module:build_pipeline` target. | keep |
| `arnold workflow manifest` | new | Emit compiled manifest YAML/JSON. | keep |
| `arnold workflow dot` | new | Emit DOT graph for the compiled manifest. | keep |
| `arnold workflow dry-run` | new | Print dry-run report without executing. | keep |
| `arnold workflow run` | new | Execute compiled manifest via `arnold.execution.run`. | keep |
| `arnold workflow resume` | new | Resume from checkpoint/cursor. | keep |
| `arnold workflow describe` | new | Manifest-backed describe (replaces pipeline describe). | keep |
| `arnold pipelines list` | delete | Use `arnold workflow describe --module ...` or registry JSON. | delete |
| `arnold pipelines check` | delete | Replaced by `arnold workflow check --module ...`. | delete |
| `arnold pipelines describe` | delete | Replaced by `arnold workflow describe --module ...`. | delete |
| `arnold pipelines doctor` | delete | Replaced by inventory scanners. | delete |
| `arnold pipelines new` | delete | Replaced by explicit-node scaffold (Phase 4). | delete |
| `arnold <module> run` | delete | Use `arnold workflow run --module ...`. | delete |
| `arnold <module> check` | delete | Use `arnold workflow check --module ...`. | delete |
| `arnold <module> describe` | delete | Use `arnold workflow describe --module ...`. | delete |
| `arnold <module> auto` | delete | Auto driver is internal to Megaplan plugin. | delete |
| `arnold run` | delete | Legacy Megaplan driver; use `arnold workflow run`. | delete |
| `arnold auto` | delete | Legacy Megaplan auto driver. | delete |
| `arnold megaplan override ...` | delete | Legacy planning override surface. | delete |
| `arnold override ...` | `arnold override` | Retained operator command for control transitions. | keep |
| `arnold status` | `arnold status` | Retained operator command; reads event journal/artifact root. | keep |
| `arnold trace` | `arnold trace` | Retained operator command; prints event journal. | keep |
| `arnold inspect` | `arnold inspect` | Retained operator command; inspects manifest + control transitions. | keep |
| `arnold progress` | delete | Folded into `arnold status`. | delete |
| `arnold watch` | delete | Superseded by event-journal observation. | delete |
| `arnold resume` | `arnold workflow resume` | Resume via workflow runtime. | keep |
| `arnold init` | delete | Megaplan planning command. | delete |
| `arnold plan/prep/critique/revise/gate/finalize/execute/review` | delete | Megaplan planning step commands. | delete |
| `arnold setup` | delete | Megaplan agent-config installer. | delete |
| `arnold config` | delete | Megaplan configuration command. | delete |
| `arnold brief/ticket/epic/contract/audit/feedback/migrate-local-plans` | delete | Megaplan planning/support commands. | delete |
| `arnold execution run-manifest` | keep | Existing compiled-manifest runner; companion to `arnold workflow run`. | keep |

## Notes

- Retained operator commands (`status`, `trace`, `inspect`, `override`) project only from manifests, event journals, artifacts, and control transitions.
- The `arnold` top-level dispatch routes `arnold workflow ...` directly without importing legacy Megaplan CLI modules.
