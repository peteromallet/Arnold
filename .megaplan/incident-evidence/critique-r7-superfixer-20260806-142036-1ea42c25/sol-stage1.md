# Sol Stage 1 — Read-only scoping result

Target occurrence: `occ_critique_r7_superfixer_now_20260806_v5_63a701ce7ce09258e1c322f2`

No files, chain state, runtime source, bindings, processes, or notifications were changed. This response is the persisted Stage 1 result.

## A. Definitely broken vs. hypothesized

### Definitely broken

| Fact | Evidence |
|---|---|
| The target chain is blocked at milestone 0, with no completed milestones; plan iteration is 5 and the last gate recommendation is `PROCEED`. | [chain-status.txt](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/raw/chain-status.txt), [chain-state.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/raw/chain-state.json), [plan-state.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/raw/plan-state.json) |
| Both finalize attempts rejected the same candidate before publication with 12 `dependency_unknown` diagnostics followed by `dependency_graph_invalid`. | [planner_repair.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/raw/planner_repair.json), [finalize_revise_feedback.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/raw/finalize_revise_feedback.json), [repro-output.txt](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/raw/repro-output.txt) |
| The two persisted candidate artifacts are byte-identical: SHA-256 `cfc7d701…`; candidate ID `36bcefaf…`; failure fingerprint `382e25a2…`. The circuit is open at occurrence count 2, and implementation dispatch is forbidden. | [finalize-15274…candidate.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/raw/local-strict-artifacts/finalize-15274aaf2cb2445487647129704dcccd.candidate.json), [finalize-59da…candidate.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/raw/local-strict-artifacts/finalize-59daae926dcd4447b40cbb790e68e36b.candidate.json), [planner_repair.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/raw/planner_repair.json) |
| `split_high_complexity_tasks` removes successfully split parents, but it does not rewrite dependencies in other tasks. This produces the exact observed dangling references after T1–T5 and T7 are split. | [task_splitter.py](/workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan/orchestration/task_splitter.py:294), [task_feasibility.py](/workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan/orchestration/task_feasibility.py:287), [repro_finalize_mutations.py](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/raw/repro_finalize_mutations.py) |
| The runner is dead, not merely slow: the session PID and finalize worker PID are absent, heartbeat stopped at `2026-08-06T14:16:28Z`, and no watchdog was observed. The synthetic `owner_pid: "0"` lease is not live recovery custody. | [active-step-heartbeat.snapshot.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/raw/active-step-heartbeat.snapshot.json), [session-marker.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/raw/session-marker.json), [override authority receipt](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/raw/boundary_receipts/override_recover_blocked_authority.json) |
| `phase_result.exit_kind: success` means the phase harness wrote its rejection artifacts; it does not mean the candidate was admitted. No prior admitted finalize or feasibility artifact exists. | [phase_result.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/raw/phase_result.json), [planner_repair.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/raw/planner_repair.json) |
| The raw candidate’s `sense_checks[].task_id` values still name removed parents such as T1–T5 and T7. The splitter changes only `tasks`; it does not transform `sense_checks` or coverage references. | [candidate artifact](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/raw/local-strict-artifacts/finalize-15274aaf2cb2445487647129704dcccd.candidate.json), [finalize.py](/workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan/handlers/finalize.py:2012) |
| The supplied precondition fingerprint is internally inconsistent: the prompt declares `c87809d8…`; the manifest’s `sha256` field and evidence-pack identity section say `4acc22eb…`; the evidence-pack fact section returns to `c87809d8…`; the manifest file bytes hash to `f98818ed…`. | [fingerprint-before.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/fingerprint-before.json), [evidence-pack.md](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/evidence-pack.md) |

The v4 `critique_finding_unresolved` defect is not the current blocker. Commit `9c41d0554` is an ancestor of bound engine HEAD `234ac352…`, and the later attempts reached a distinct finalize graph-admission failure.

### Hypothesized or unresolved

- The semantically correct replacement for a downstream dependency on removed parent `Tn` is probably `Tn_proof`, but that is not yet established by an authoritative execution contract.
- `sense_checks`, programmatic coverage’s `finalize_item_ids`, or other task-reference fields may become a second latent referential-integrity defect after dependency rewiring.
- `_apply_programmatic_coverage`’s reproduced `KeyError: -1` may be only a malformed minimal-state artifact; it was not the observed production blocker.
- A source correction alone may not restart this occurrence because plan state is blocked and the planner-repair circuit remains open.
- The same splitter defect may affect sibling plans or the M8A reporting consumer even though the bounded workspace search found no sibling with this exact failure fingerprint.

## B. Ranked root hypotheses

### H1 — Missing batch-level reference rewriting is the proximate blocker

**Support:** Successful splits remove T1–T5 and T7, while downstream `depends_on` and matching `dependency_reasons` remain unchanged. The replay produces the exact canonical 12+1 diagnostics.

**Falsifier:** A read-only replay using the exact canonical state and candidate, with only a complete parent-ID mapping applied, still produces any original `dependency_unknown` diagnostic—or shows those parent IDs were not removed.

### H2 — Downstream dependencies should resolve to the proof subtask

**Support:** A proof depends on its implementation and represents verified completion of the original task contract. Mapping dependents to `_impl` may permit consumption before proof completes.

**Falsifier:** An authoritative scheduler, task-contract specification, or existing golden fixture explicitly defines the split parent’s externally consumable completion as `_impl`, with `_proof` non-blocking or independently scheduled.

### H3 — The split transformation has a wider task-reference closure defect

**Support:** The candidate has `sense_checks[].task_id` for every original task, and `_apply_programmatic_coverage` runs before splitting and records original task IDs. `split_high_complexity_tasks` transforms only the task list.

**Falsifier:** An exhaustive producer/consumer trace shows every non-task reference is either atomically remapped later or intentionally bound to stable logical parent IDs that remain valid after task removal.

### H4 — `_apply_programmatic_coverage`’s `KeyError: -1` is a reproduction-fixture artifact

**Support:** The reproduction manufactured a minimal `plan_versions` shape. Both real finalize attempts progressed through graph splitting and feasibility reporting, which would not occur if coverage had raised first.

**Falsifier:** Resolving `latest_plan_path(plan_dir, canonical_state)` against the captured real state raises `KeyError: -1`, or production logs show coverage failed and was suppressed.

### H5 — Recovery requires a supported blocked-state transition, not an ad hoc circuit-file reset

**Support:** `clear_planner_repair` is called only after successful finalization, but this occurrence is already blocked and advertises `override recover-blocked`. The prior override applied to a different failure fingerprint and was consumed before the two new failures.

**Falsifier:** Read-only CLI/control-flow inspection proves a normal finalize invocation from the present blocked state both re-evaluates the corrected candidate and clears the circuit without a new authority-bearing recovery transition.

## C. Bounded DeepSeek V4 Flash evidence questions

| ID | Question and exact artifacts | Read-only method | Decision informed |
|---|---|---|---|
| **FQ-01** | Where is the smallest complete reference-closure boundary for splitting? Inspect [task_splitter.py](/workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan/orchestration/task_splitter.py), [finalize.py](/workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan/handlers/finalize.py), [task_feasibility.py](/workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan/orchestration/task_feasibility.py), the two candidate artifacts, and `raw/repro-output.txt`. | `git show`, `sed`, `rg`, `jq`, `sha256sum`; reconstruct the before/after ID and dependency sets in memory with `python -B`, with no writes. | Whether the minimal source boundary belongs in generic `split_high_complexity_tasks`, finalize-only orchestration, or another existing normalization layer. |
| **FQ-02** | Does the execution contract make `_impl` or `_proof` the semantic successor of the removed parent? Inspect `task_splitter.py`, `orchestration/task_feasibility.py`, `execute/batch.py`, `runtime/batch.py`, `handlers/execute.py`, `orchestration/execution_evidence.py`, and `tests/.../test_task_splitter.py`. | Static call/data-flow trace and existing assertions only; quote the precise scheduling and completion semantics. | Which dependent-rewire target is correct without weakening proof ordering. |
| **FQ-03** | Which fields besides `depends_on` and `dependency_reasons` carry task identities through finalize? Inspect the candidate’s `sense_checks`, `watch_items`, and `validation`; `finalize.py`; `orchestration/validation_jobs.py`; `orchestration/graph_admission.py`; and `orchestration/execution_evidence.py`. | Enumerate task IDs before and after the stored mutation pipeline; trace every structured consumer using `rg` and `git show`. Do not infer IDs from unrelated prose. | Whether `sense_checks`, coverage `finalize_item_ids`, validation jobs, or watch items need the same transformation policy. |
| **FQ-04** | Is `_apply_programmatic_coverage` actually defective on the captured canonical state? Inspect [repro_finalize_mutations.py](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/raw/repro_finalize_mutations.py), `raw/plan-state.json`, `handlers/finalize.py::_apply_programmatic_coverage`, and `_core/state.py::latest_plan_path`. | Compare the fake state shape to canonical `plan_versions`; use `jq`, `sed`, and, only if necessary, `PYTHONDONTWRITEBYTECODE=1 python -B` for a non-writing resolution call. | Whether a second latent coverage defect exists or the `KeyError: -1` must be excluded from source scope. |
| **FQ-05** | Did the 14:13 and 14:16 model responses or candidates differ in any contract-relevant way? Inspect both local-strict candidates, both `response-finalize-*.json`, both occurrence response objects, both model-response JSONL objects, `repair-0.json`, and plan history. | `sha256sum`, `cmp`, canonicalized `jq -S`, and bounded timestamp/correlation extraction. | Whether the failure is deterministic over one candidate identity and whether any candidate/task-contract hash must be preserved across correction. |
| **FQ-06** | What exactly enters `candidate_id`, `candidate_graph_hash`, `task_contract_hash`, and `failure_fingerprint`, and do transformed sense checks affect identity? Inspect `orchestration/graph_admission.py`, task-contract hashing in `task_feasibility.py`, `finalize.py`, `planner_repair.json`, and both candidates. | Static hash-input trace; independently recompute canonical hashes in memory using the implementation’s documented serialization. | Whether identity should remain the raw model candidate’s identity or be regenerated for the fully transformed graph. |
| **FQ-07** | Does existing test coverage lock only parent replacement, or also downstream reference closure and finalize admission? Inspect `tests/arnold_pipelines/megaplan/test_task_splitter.py`, `test_task_feasibility.py`, `test_handler_behaviors.py`, `test_m8a_finalize_wiring.py`, and `test_graph_admission.py`. | `rg` and `sed` over test names, fixtures, and assertions; do not execute pytest because this stage forbids cache or artifact writes. | The smallest regression surface needed to lock behavior and whether a finalize-pipeline test is required in addition to a unit test. |
| **FQ-08** | By which supported operation can this exact planner-repair circuit be retried after a source correction? Inspect `handlers/finalize.py`, `handlers/override.py`, `orchestration/graph_admission.py`, `planning/state.py`, `tests/.../test_auto_recover_blocked.py`, `test_s6_override_control.py`, and the existing override receipt. | Static state-machine and CLI-route trace. Report preconditions, authority records, state transitions, and where `clear_planner_repair` is called. | Whether a new `override recover-blocked` is required and whether any separate reset operation is supported. |
| **FQ-09** | Is this defect present in any sibling plan/session, and which fingerprint is the valid one-effect guard? Inspect the bounded workspace `.megaplan/plans/`, `/workspace/.megaplan/cloud-sessions/`, engine call sites for `split_high_complexity_tasks`, [fingerprint-before.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/fingerprint-before.json), and `evidence-pack.md`. | Bounded `rg`, `find`, `jq`, `git grep`, and `sha256sum`; no repository-wide or cloud-wide mutation. Explicitly distinguish declared fingerprint, embedded fingerprint, file-byte hash, and manifest entries. | Whether scope must include a sibling consumer and which exact identity tuple Sol may authorize as the pre-effect guard. |

## D. Comparable-report contract

Every Flash report must use this exact structure:

1. `question_id`: one FQ ID only.
2. `verdict`: exactly `supported`, `refuted`, or `undetermined`.
3. `vantage_point`: host/container identity, repository root, engine HEAD, runtime content identity.
4. `utc_interval`: observation start and end in UTC.
5. `artifacts`: absolute path plus SHA-256 for every inspected artifact.
6. `commands`: exact read-only commands, in execution order.
7. `cwd`: absolute working directory for each command group.
8. `exit_codes`: command-to-exit-code mapping.
9. `raw_excerpts`: bounded verbatim evidence with line numbers or JSON pointers.
10. `trace`: explicit `producer -> consumer -> persistence -> policy` chain; use `none observed` where a leg genuinely does not exist.
11. `confidence`: `high`, `medium`, or `low`, with one-sentence basis.
12. `structure_classification`: exactly `adherent` or `missing_structure`; list missing fields if the latter.
13. `immediate_decision_informed`: the occurrence-bound decision.
14. `durable_decision_informed`: the regression, invariant, or broader contract decision.

A report missing any required structural field is `missing_structure`; its substantive verdict must be treated as `undetermined` until corrected. Absence of evidence is not a `refuted` verdict unless the search boundary and negative observation are both explicit.

## E. Sol-only safety and identity decisions

The fixer must return to Sol before any mutation. It must not:

- edit `state.json`, chain-state JSON, `planner_repair.json`, receipts, heartbeat, session marker, candidates, or model-response evidence directly;
- use `--fresh`, start or relaunch the chain, invoke finalize, recover-blocked, replan, or force-proceed;
- reset or delete the planner-repair circuit manually;
- patch, commit, push, rebind, install, or refresh the bound engine;
- create or adopt custody, kill processes, start a watchdog, or claim PID `0` as live custody;
- notify any person or external system;
- modify the project checkout;
- combine a source effect with a recovery/state-transition effect.

The later one-effect barrier is:

1. One authorized source/test effect only.
2. Stop and recompute identity and fingerprints.
3. Return to Sol with the diff and evidence.
4. Only after separate Sol authorization may recovery, rebind, launch, or notification be considered.

Before any future effect, the fixer must prove the full guard tuple still matches:

- session, workspace, plan, iteration 5, milestone index 0, and occurrence;
- engine root `/workspace/runtime-candidates/arnold-r7-fresh-child-20260805`;
- engine HEAD `234ac3524da29c1f630aee90ab1767a142a68a83`;
- runtime content `a99e74e6…`;
- execution binding and runtime binding both `match`;
- candidate `36bcefaf…` and failure fingerprint `382e25a2…`;
- plan remains blocked with no completed milestone and no live authoritative runner;
- project and engine tracked status remain clean.

The pre-fingerprint cannot currently serve as a single-value mutation guard. Sol must first reconcile, without substitution:

- prompt-declared guard: `c87809d84919f000e2dced2139d38920692a702f30ed4e8fbecdea8a9cd72c12`;
- manifest-declared guard: `4acc22ebfd48fbf6273f0d236807f755f84183e16a58b339aeff1b65d8b3a709`;
- manifest file-byte SHA-256: `f98818edf952d5799661e57322157f2abe9dab710c817f2f937425760161dcb4`.

Any identity drift, new heartbeat, live custody, changed candidate, changed circuit count, changed binding, or unresolved fingerprint semantics is a mandatory stop-and-return-to-Sol condition.