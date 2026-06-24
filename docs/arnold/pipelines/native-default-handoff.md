# Native Default Handoff

This handoff is for the M7 native-default rollout. It documents the runtime
owner contract as implemented in this worktree and the release controls that
must be checked before promoting native-default behavior beyond canaries.

## Authority

- Runtime owner selection lives in `arnold/pipeline/native/routing.py`.
- `megaplan run` and `arnold pipelines run` persist fresh-run ownership through
  `state.json.runtime_envelope.runtime` and `state.json.meta.executor`.
- Resume cursor classification lives in `arnold/pipeline/native/checkpoint.py`.
- Graph-to-native cursor upgrade is explicit through
  `arnold pipelines upgrade-cursor <plan-dir>` and `--write`.

## Rollback Procedure

Use graph rollback for fresh runs when native execution is suspected, when a
canary trips, or when a converted pipeline needs emergency comparison against
the compatibility path.

1. Stop expanding the native canary.
2. For fresh runs, force graph execution:

   ```bash
   arnold pipelines run <pipeline> ... --runtime graph
   megaplan run <pipeline> ... --runtime graph
   ```

   `--executor graph` is still accepted as a deprecated alias.
3. Confirm the run wrote `state.json.runtime_envelope.runtime == "graph"` and
   `state.json.meta.executor == "graph"`.
4. Leave graph-born in-flight plans on graph. Do not auto-upgrade their cursor.
5. Leave native-born plans on native if they can resume safely. If the native
   runtime itself is broken, preserve the native plan directory for forensic
   inspection and restart from the last accepted artifact in a new graph-forced
   plan directory; there is no native-to-graph cursor downgrade command.
6. Re-run the scoped runtime selection and resume routing suites before
   re-opening the canary.

## Per-run Graph Fallback

Per-run fallback is implemented and covered by CLI tests:

- `--runtime graph` forces a fresh run onto the graph executor, even when the
  pipeline is native-capable.
- `--runtime native` forces native only when the pipeline has native dispatch
  capability. Graph-only targets fail with `native_runtime_unavailable` and do
  not write `state.json`.
- `--executor graph|native` remains as a deprecated compatibility alias.
- If `--runtime` and `--executor` disagree, the CLI rejects the run.

## Global Kill Switch

The release plan names `ARNOLD_PIPELINE_RUNTIME=graph|native` as the global
runtime kill switch. In this worktree, that switch is not yet consumed by
`arnold/pipeline/native/routing.py`, `run_cli.py`, or the neutral executor.

Release sign-off must therefore treat `ARNOLD_PIPELINE_RUNTIME` as a blocking
gap until a code consumer and tests land. Until then, the only reliable broad
rollback is operational: inject `--runtime graph` at the caller/wrapper level
for fresh runs. The older `ARNOLD_NATIVE_RUNTIME=1` gate still protects direct
native runtime entrypoints, but unsetting it is not a graph rollback strategy
for native-default fresh runs because the dispatch decision may still choose
native and then fail when the native runtime is disabled.

Before public rollout, verify:

```bash
rg -n "ARNOLD_PIPELINE_RUNTIME" arnold tests docs
```

There must be a routing/helper implementation and tests, not only plan or
documentation references.

## Run Identification

Fresh runs identify their owner in `state.json`:

- `runtime_envelope.runtime == "native"` and `meta.executor == "native"`:
  native-owned fresh run.
- `runtime_envelope.runtime == "graph"` and `meta.executor == "graph"`:
  graph-owned fresh run or explicit graph fallback.
- `_native_execution` is a deprecated compatibility alias only. Modern markers
  win over it.

Resume cursors identify their owner in `resume_cursor.json`:

- Native-born cursor: top-level `native` object with integer `pc` and `version`.
- Graph-born cursor: cursor exists with no top-level `native` key, or
  `native: null`.
- Corrupt native cursor: top-level `native` exists but is not a valid object
  with integer `pc` and `version`; routing must fail closed.
- Upgraded graph cursor: write mode records native ownership and retains the
  original graph cursor backup.

## Resume Compatibility Matrix

| Run shape | Marker/cursor | Expected owner | Notes |
| --- | --- | --- | --- |
| Fresh native-capable converted pipeline | no cursor, no override | native | Persists `runtime_envelope.runtime` and `meta.executor` as `native`. |
| Fresh graph-only pipeline | no cursor, no override | graph | Graph-only remains graph-default until it has native capability and parity coverage. |
| Fresh run with `--runtime graph` | explicit CLI override | graph | Emergency fallback path. |
| Fresh run with `--runtime native` | native-capable target | native | Fails clearly if the target lacks native capability. |
| Fresh run with conflicting `--runtime` and `--executor` | explicit disagreement | none | CLI rejects before execution. |
| Existing graph-born plan | cursor has no valid `native` object | graph | No automatic upgrade. |
| Existing graph-born plan after dry-run upgrade | unchanged graph cursor | graph | Dry run reports diagnostics only. |
| Existing graph-born plan after `upgrade-cursor --write` | valid native cursor plus backup | native | Only when graph stage maps to exactly one native reentry point. |
| Existing native-born plan | valid `native.pc` and `native.version` | native | Corrupt native payloads fail closed. |
| Plan with modern persisted graph marker and in-memory native marker | `state.json` says graph | graph | Persisted modern marker wins. |
| Plan with modern persisted native marker and in-memory graph marker | `state.json` says native | native | Persisted modern marker wins. |

## Deprecation Window And Canary Policy

Keep the graph executor and retained graph scaffolds for at least one release
cycle after native-default promotion unless the release owner records a longer
window. Do not remove additional graph fallback code during the canary.

Canary policy:

- Start with converted pipelines that have parity and resume coverage.
- Require `--runtime graph` fallback verification before admitting a pipeline
  to canary.
- Track native failure rate, graph fallback volume, corrupt-native-cursor
  failures, upgrade-cursor diagnostics, and parity test status.
- Any cursor-corruption failure, graph fallback regression, or repeated
  native-only artifact/state mismatch pauses the canary and triggers rollback.
- Close the canary only after the full deprecation window completes without
  rollback criteria firing.

## Graph Scaffolding Removal And Retention

Removal list for this handoff:

- No graph executor files are deleted in this batch.
- No hand-built graph fallback files are deleted in this batch.
- The graph-scaffolding cleanup is currently a documentation/scaffold-default
  change: new scaffolds default to native declarations, and explicit
  `--driver graph` scaffolds are labeled deprecated fallback.

Retained intentionally:

- `arnold/pipelines/megaplan/_pipeline/executor.py` and graph dispatch paths for
  graph-born plans and per-run fallback.
- `arnold/pipelines/megaplan/_pipeline/_bridge.py` fallback dispatch and
  bridged graph execution.
- `project_graph(...)` and graph validation for derived public topology.
- `arnold pipelines new --driver graph` as a deprecated fallback scaffold.
- Graph parity fixtures and tests that prove native-derived behavior remains
  compatible with the graph path.
- Graph cursor backups written by `upgrade-cursor --write`.

Do not treat retained graph code as dead until the canary window closes and a
separate cleanup task has fresh `rg` evidence proving the symbol is neither a
fallback path nor a parity baseline.

## Sign-off Checklist

- [ ] `ARNOLD_PIPELINE_RUNTIME=graph|native` has an implemented routing helper
  consumer and tests, or the release explicitly blocks on that gap.
- [ ] `--runtime graph` and deprecated `--executor graph` are tested on a
  native-capable pipeline and persist graph ownership markers.
- [ ] `--runtime native` rejects graph-only pipelines with
  `native_runtime_unavailable`.
- [ ] Native-born, graph-born, missing, and corrupt cursor routing cases are
  covered by full test files or modules.
- [ ] `upgrade-cursor` dry-run and `--write` behavior is verified, including
  graph cursor backup retention.
- [ ] Docs and pipeline `SKILL.md` files describe native-default behavior and
  graph fallback consistently.
- [ ] Canary entry pipelines have parity coverage and a named rollback owner.
- [ ] No retained graph executor, graph projection, fallback scaffold, or parity
  fixture is removed before the deprecation window closes.
