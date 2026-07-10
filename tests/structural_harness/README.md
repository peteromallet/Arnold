# Structural Agentic Tests

This directory contains **structural agentic tests**: deterministic scenarios
that exercise real executor and agent-edit paths on real workflows, but use
scripted model responses instead of real model/provider calls.

Builders use fake/faking actors to freeze evidence for workflow, executor,
routing, and failure-mode invariants. These runs are not live agentic tests.
True live agentic tests belong in `tests/live_agentic_harness/` and must use a real
dispatcher with production-like tools.

## Quick start

```bash
# Run structural contract scenarios in no-GPU mode with the fake actor:
python -m tests.structural_harness.runner --mode structural --actor fake --tag run
```

For the operator-level boundary matrix across structural, live-headless,
browser harness, and browser e2e lanes, see
`../../docs/testing/headless-agentic-harnesses.md`.

## Layout

```
tests/structural_harness/
  __init__.py        Package init
  adapter.py         VibeComfyProjectAdapter (extends FakeProjectAdapter)
  runner.py          Scenario runner: load YAML, dispatch actors, freeze evidence
  actors.py          Structural evidence builders for scenario families
  actors_m4/         M4 recovery evidence builders
  actors_m5/         M5 runtime/readiness evidence builders
  scenarios/         Scenario YAML files (one per user ask)
  briefs/            User-shaped markdown briefs (referenced by scenario YAML)
  README.md          This file
```

Evidence packs land in `out/agentic/reports/<tag>/`. Do not commit generated
evidence packs under `tests/structural_harness/`; the `evidence/` path used in scenario YAML is
the frozen-evidence subdirectory inside each run report.

## Structural vs Live Agentic

Determinism belongs in the harness and judge, not in a live agentic
subject-under-test.

| Lane | Subject-under-test | Dispatcher | Evidence source |
|---|---|---|---|
| `structural_contract` | Deterministic builder / scripted route fixture | `fake` or `faking` | Builder-frozen JSON/JSONL/artifacts |
| `live_agentic` | Real model/agent using production-like tools | non-fake live dispatcher | Artifacts produced by the real run |

Structural contract scenarios are still valuable: they pin invariants, capture
regressions, and make failure modes cheap to check. They must not be described
as proof that a live model researched, reasoned, or edited successfully.

## How to add a scenario

1. Write a user-shaped brief in `tests/structural_harness/briefs/<name>.md`.
2. Create a scenario YAML in `tests/structural_harness/scenarios/<name>.yaml` referencing the brief.
3. Define `assessment.enforced`, `assessment.graded`, and `assessment.observed` rubric
   items anchored to frozen evidence (compiled API JSON, metadata.json, file existence,
   or action logs) — **never** to `report.md` narrative.
4. Run the scenario: `python -m tests.structural_harness.runner --name <name>`.
5. Verify the evidence pack in `out/agentic/reports/<tag>/`.

## Metadata contract

### `entrypoint` / `layer` stamping

At the ops/blocks/patches boundary, VibeComfy stamps `workflow.metadata` with:

- `entrypoint`: `"op"`, `"block"`, or `"patch"` (identifies how the workflow graph was produced)
- `layer`: e.g. `"ops/image.py:t2i"`, `"ops/video.py:i2v"` (identifies the specific authoring layer)

These use first-writer-wins (set-if-absent) semantics. The runtime metadata writer
(``vibecomfy/runtime/session.py::_run_metadata``) reads these fields from workflow metadata
and copies them into `out/runs/<id>/metadata.json`.

### `chain_id` / `parent_run_id`

Multi-stage chains (like image→video) thread linkage through the runtime:

- `chain_id`: shared across all stages in the chain
- `parent_run_id`: the `run_id` of the immediately preceding stage

These flow through `Artifact.run(..., chain_id=..., parent_run_id=...)` →
`run_sync` / `run_embedded_sync` → `_run_metadata` → `RunResult`.

### `patch_applications`

When a workflow goes through the canonical `Patch.apply()` boundary, runtime metadata
copies `workflow.metadata["patch_applications"]` into `metadata.json` as additive
telemetry for structural grading.

- `called=true` means the patch boundary was invoked, even if the graph stayed unchanged.
- `layer="patch"` identifies the metadata entry as coming from the patch layer.
- `topology_changed=true` means the patch rewired or extended the graph.
- `introduced_edges` lists newly-added connections.
- `rewritten_edges` lists replaced connections, including the previous source and new source.
- No-op patch calls still emit an entry with `called=true` and `topology_changed=false`.

This lets scenarios distinguish "the actor called the canonical patch" from
"the patch materially changed the workflow."

## Evidence pack shape

Each evidence pack under `out/agentic/reports/<tag>/<scenario>/` contains:

| File | Content |
|---|---|
| `report.md` | Actor narrative (never used for proof) |
| `stdout.txt` | Captured stdout |
| `stderr.txt` | Captured stderr |
| `command_log.json` | Commands executed |
| `actions.jsonl` | Structured action log |
| `evidence/` | Frozen evidence files (compiled API JSON, metadata, output paths) |
| `tree_before.txt` / `tree_after.txt` | Directory snapshots |
| `git_diff.txt` | Git diff |

## Faking actor guard

`--actor faking` produces plausible narrative but intentionally omits frozen evidence
anchors. The enforced checks MUST fail the faking actor even if `report.md` claims success.
This guard proves the harness discriminates narrative from evidence.

## Evidence-vs-narrative falsification results

The harness classifies success from **frozen evidence only** (compiled API JSON,
metadata JSON, actions.jsonl, and output files). `report.md` is never used for
pass/fail decisions. The adversarial test suite proves the following invariants:

| Test | Action | Expected result | Verified? |
|---|---|---|---|
| `report.md` removal | Delete `report.md` while keeping all required evidence | Pass (COMPILED or VALIDATED) | ✅ |
| `report.md` lies | Write "FAILED" in `report.md` while evidence is complete | Pass (COMPILED or VALIDATED) | ✅ |
| Missing compiled API | Remove `stage1/compiled_api.json` but keep a glowing `report.md` | Fail (AUTHORED) | ✅ |
| Missing metadata | Remove `stage2/metadata.json` with `report.md` present | Fail (AUTHORED) | ✅ |
| Faking actor | Run `--actor faking` with only `report.md` + stdout/stderr | Fail (AUTHORED) | ✅ |

**Key design rule:** Rubric items in `assessment.enforced`, `assessment.graded`,
and `assessment.observed` must be anchored to frozen evidence files — **never**
to narrative text in `report.md`. If a check can be satisfied by editing
`report.md` alone, it is not an evidence-based check and must be rewritten.

## M6 Executor Contract Scenarios

These are structural contract scenarios that exercise the same executor
entrypoint the frontend/API uses (`POST /vibecomfy/agent-executor` →
`vibecomfy.executor.core.run_executor`) with scripted fake actors:

- `explore-hotshot-xl-workflow` — research ask. The fake actor builds an
  `ExecutorRequest` for "Hotshot XL SVD-XT workflow", calls `run_executor`, and
  freezes `executor_result.json`, `executor_report.json`,
  `implementation_payload.json`, `implementation_result.json`, and `messages.jsonl`.
  The enforced checks require `ok=true`, `plan.research=true`, and a research brief
  with Hotshot/SVD-XT anchors entering the agent-edit research loop.
- `distilled-faster-research-route` — regression for vague speedup asks such as
  "is there a distilled/faster way to run?". The fake actor proves triage expands
  that sentence into AnimateDiff/distilled/lightning/LCM search directions before
  agent-edit records a focused research call in `messages.jsonl`.
- `explain-simple-workflow` — graph explanation ask. The fake actor loads the
  fixture at `tests/fixtures/agent_edit/flat.json`, calls `run_executor`, and freezes
  `executor_result.json`, `executor_report.json`, and `implementation_result.json`
  (also surfaced as `graph_report.txt`). The enforced checks require
  `plan.intent=explain_graph`, `plan.implement=true`, and a reply/report that names
  the key nodes and edges.

Run just these two scenarios:

```bash
python -m tests.structural_harness.runner \
  --mode structural --actor fake --tag executor-verify \
  --name explore-hotshot-xl-workflow --name distilled-faster-research-route \
  --name explain-simple-workflow
```

Evidence lands in `out/agentic/reports/executor-verify/`.

Every run freezes a `flow_metadata.json` that classifies the harness boundary.
The two poles are **`structural_contract`** (deterministic builder, fake/faking
actor, no live model) and **`live_agentic`** (real agent + production-like tools,
optionally GPU runtime). The adapter auto-derives these from mode + dispatcher
when a scenario does not declare an explicit `extras.flow_kind`.

A scenario MAY supply a more specific `extras.flow_kind` (e.g.
`executor_research_scripted`, `direct_agent_edit_scripted`) to tag a sub-type
of `structural_contract`. The frozen `flow_metadata.json` also records
`dispatcher`, `mode`, and `model_behavior` (`scripted` vs `agentic`) so a
structural fake can never be mistaken for an end-to-end live model test.

## Handoff for M2–M6

- **M2 (discovery & limits):** Add negative scenarios proving the actor recognizes unwired
  ops and missing templates. The adapter dispatches structural scenarios through the
  `_M2_BUILDERS` dict (a mapping of scenario slug → builder function in `adapter.py`).
  Each scenario YAML declares `extras.required_frozen_evidence` — the exact set of frozen
  evidence files the harness must find for a COMPILED or VALIDATED classification. The
  faking actor guard (`_capture_structural_evidence` → `build_faking_structural_chain`)
  deliberately produces only `report.md`, `stdout.txt`, `stderr.txt` — omitting all frozen
  evidence anchors — so the faking actor always achieves at most AUTHORED, proving the
  harness discriminates narrative from evidence. The `project_universal_checks` hook
  reports missing required evidence as a hard error, and `classify_success` returns
  AUTHORED when any required frozen evidence is absent.
- **M3 (compose correctly):** Add block-based composition scenarios. The `entrypoint=block`
  marker will already be stamped. Scenario `#8` (`add-depth-controlnet-image`) proves
  positive image composition by requiring both the ControlNet topology rewrite and the
  controlnet patch marker in metadata. Scenario `#9` (`controlnet-video-noop`) is the
  companion no-op case: the action log must explicitly acknowledge `patch.apply` as
  `status=no_effect`, and metadata may still show a `patch_applications` entry with
  `called=true` plus `topology_changed=false`. Scenario `#12`
  (`add-save-node-finalize`) covers the finalize trap: the builder must add the save
  node and call `wf.finalize_metadata()` so `metadata.json.requirements.models` is
  non-empty before grading.
- **M4 (diagnose & recover):** Extend the recovery pattern established in scenario #4.
- **M5 (remote GPU):** Structural runtime/readiness scenarios currently freeze
  watchdog and command-log evidence without running a live model. True
  `mode=live` scenarios must use a non-fake dispatcher and production-like tools;
  `prime()` and `capture()` are the integration points.
- **M6 (robustness backbone):** Add adversarial scenarios and expand `project_universal_checks`.
