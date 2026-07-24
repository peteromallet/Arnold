# Authority inventory reader audit

Audit date: 2026-07-10  
Scope: Sprint 1 T5, read-only repository audit  
Consumer: `authority/inventory.py` (T6)

## Contract used by the audit

Every configured source class must produce a registry record even when its
concrete path, command, backend, or credential is absent. The record needs:

- category and primary role: `observation`, `claim`, `decision`, or
  `projection`;
- reader and concrete/configured path;
- presence/degraded state and an exact reason;
- identity or fingerprint behavior;
- revision or sequence behavior;
- freshness fields; and
- contradiction findings with both source paths.

Roles describe what a source is allowed to contribute to the Sprint 1 shadow
view, not how legacy callers currently treat it. In particular, mutable status
files and labels remain projections or claims even when an existing caller
uses them as authority.

## Reader inventory

The following table is the implementation registry for T6. “Absent record” is
the degraded result the inventory must emit when the source is configured but
unavailable. `mtime` means filesystem modification time captured by the
collector; it is freshness evidence, not a revision.

| Category / source class | Role | Existing reader to reuse | Identity / fingerprint | Revision / sequence | Freshness | Absent or degraded record |
|---|---|---|---|---|---|---|
| Execute: `state.json` | projection | `PlanRepository.load_state()` only when R1 authority mode is known off; otherwise direct `PlanRepository.read_artifact_json("state.json")`/bytes plus hashing | plan-directory path, `name`, `schema_version`; `resolve_current_target()` already adds content SHA-256 and mtime | no durable monotonic run revision; `iteration`, history order, `meta.current_invocation_id`, and active-step `run_id`/`attempt` are partial identities only | file mtime; `created_at`; latest history timestamp; active-step `started_at`/`last_activity_at` | always emit configured plan path; missing, unreadable, non-object, or name/path mismatch |
| Execute: `finalize.json` | projection | `PlanRepository.read_artifact_json()` and `describe_artifact()` | path plus artifact SHA-256; `evidence_base_ref` is a Git reference, not run identity | no plan revision or sequence; array position and task IDs are mutable projection coordinates | file mtime only | missing/unreadable/non-object; task or sense-check IDs inconsistent with the plan subject registry |
| Execute: S4 batch artifacts | claim | `_core.io.list_batch_artifacts()` and `PlanRepository.describe_artifact()` | S4 `batch_<N>/tasks_<12-hex-digest>.json`; embedded `batch_scope` v1 proves batch number, canonical task/check IDs, and task-set digest | numeric batch index; no attempt, grant, coordinator fence, or evidence-set revision | file mtime; worker payload has no required observation timestamp | emit no-artifacts record when directory is absent; emit each unreadable/malformed artifact rather than dropping it |
| Execute: legacy `execution_batch_N.json` | claim (quarantined compatibility input) | `_core.io.list_batch_artifacts()` migration fallback | filename index only; normally lacks embedded durable scope | numeric filename index, but no dispatch revision/attempt/fence | file mtime only | explicitly report configured legacy class as absent when none exist; when present, report `missing_batch_scope` unless independently proven by the v1 resolver |
| Execute: `execution.json`, `execution_audit.json`, checkpoints/traces | projection | `PlanRepository.list_artifacts()` / `read_artifact_json()` | path and `PlanArtifact.sha256`; task IDs or checkpoint metadata are payload identifiers | no common sequence across files; trace line order is local only | mtime plus any payload timestamp | separate records per configured class; missing is expected and must not remove category coverage |
| Execute: `completion_verdict.json` | decision (legacy typed shadow decision) | `orchestration.completion_io.read_typed_completion_verdict()` | typed subject and evidence refs; artifact path | contract schema/mode, but no generic grant/attempt/fence/source sequence | evidence-specific timestamps if supplied; otherwise mtime | absent/corrupt/untyped is degraded, not an implicit accepting decision |
| Repository: plan tree | observation | `PlanRepository.from_plan_dir()`, `list_artifact_paths()`, `list_artifacts()` | bound canonical plan directory; typed artifacts carry SHA-256, role, version, batch, and phase | typed filename version/batch where present; no tree-wide cursor | per-artifact mtime; `PlanRepository.load_plan()` computes maximum mtime but should not be called by inventory because it mixes projections | missing plan directory, unbound repository, path escape, and untyped artifacts reported explicitly |
| Store: file backend epic events | claim/decision according to event kind | `FileEventMixin.list_epic_events_for_replay()` through the configured `Store` | event ID, epic ID, transaction ID, pre/post canonical SHA-256 | replay order is `occurred_at`, then ID; framed transaction IDs provide commit identity | `occurred_at`; backing file mtime as collector metadata | no configured Store is degraded; missing event file is present-empty, not an error |
| Store: DB backend epic events | claim/decision according to event kind | `DBEventMixin.list_epic_events_for_replay()` through the configured `Store` | same event/epic/transaction and state-hash fields as file mode | DB replay order is `occurred_at`, then ID; no universal integer sequence | `occurred_at`; collection time | unavailable backend/connection must be a degraded store record, not a fallback grant |
| Store: telemetry/progress events | observation | `Store.events_for_plan()` / `list_progress_events()` when a Store is configured | optional event ID, `run_id`, source method and scope | optional `seq`; sources without it sort after sequenced events and therefore do not share a strict global cursor | `occurred_at` | absent telemetry stream is present-empty; malformed lines are degraded evidence |
| Compatibility adapter | projection | `ArnoldStoreAdapter` read methods delegate to the configured `Store`; do not instantiate another backend | preserves underlying IDs; `_dump` only changes representation | preserves underlying ordering/revision behavior | preserves underlying timestamps | no separate source when no adapter/backend is configured; record compatibility class as absent/degraded |
| Authority evidence nucleus | claim/decision inputs | reuse `authority_readers.load_evidence_nucleus()` only over the already-selected plan and Git observation; use `authority_decision_for_task()` as a pure per-task evaluator | task subject, evidence refs, artifact refs, code hash and Git head | execution window base/head bounds freshness but is not a source sequence | evidence fields and collection-time Git observation | typed verdict or artifacts absent, evidence path missing, stale code/head, or evaluator error |
| Authority completion projection | projection | derive from preloaded evidence with `authority_decision_for_task()` / `is_task_satisfied()`; do not call the aggregate wrappers | task ID plus evidence identity | no global sequence; one result per collected evidence set | inherited evidence freshness | unknown/unsatisfied when evidence is incomplete; raw terminal label remains diagnostic only |
| Chain spec | claim (configuration) | `chain.spec.load_spec()` | configured spec path; content SHA-256 should be computed by inventory | no intrinsic revision | mtime | configured path missing, invalid YAML, or invalid shape |
| Chain state: canonical/digest path | projection | reuse `chain.spec._state_path_candidates_for()` for paths, then read JSON directly | state filename uses SHA-1 of normalized spec path; saved metadata includes `chain_spec_path` and `chain_spec_sha256` | `schema_version`, milestone index, completed prefix, and retry counters; no monotonic source sequence | mtime only | emit every configured candidate (canonical, resolved alias, legacy), including absent candidates |
| Chain state: legacy `chain_state.json` | projection (compatibility) | `_state_path_candidates_for()` plus direct JSON read | legacy path has no path digest; payload may carry no spec hash | progress fields only | mtime | absent legacy class is explicit; present legacy and canonical candidates are contradictory if identities or progress disagree |
| Chain status projection | projection | `build_chain_status_snapshot()` only with already-loaded facts in later composition; do not use it as the inventory collector | operation ID plus spec/plan/session resource references | inherits chain/operation fields; no new source sequence | no generated-at field in the projection | unavailable operation/resources are degraded. Note: current implementation calls `load_chain_state()` and is not read-only-safe |
| Cloud canonical session marker `<session>.json` | claim | `resolve_current_target(session, marker_dir=...)` and `session_markers.is_canonical_session_marker_path()` | session, workspace, run kind, remote spec, plan name, PID/pane PID | no marker revision or attempt binding | `started_at`, `updated_at`, file mtime collected by inventory | optional CLI session/marker not supplied, marker root missing, marker missing/unreadable, or marker lacking session/workspace/spec |
| Cloud current-target evidence | projection | `resolve_current_target()` followed by `normalize_evidence()` | `target_id`, target session; plan/chain content SHA-256 and paths | schema v1; event line count only; no authority source sequence | plan/chain/events mtimes, active-step timestamps, needs-human `recorded_at` | `ARNOLD_RESOLVER_OBSERVE` disabled is an explicit degraded record; optional marker inputs absent must also be explicit |
| Cloud status snapshot | projection | `load_cloud_status_snapshot(max_age_s=...)` | configured snapshot path, source label, session keys | no sequence; previous snapshot is only a rotation | `generated_at`, `watchdog_generated_at`; loader supplies stale reason against max age | missing, unreadable, non-object, missing timestamp, or stale snapshot reason |
| Cloud chain-health/progress sidecars | projection | `build_cloud_status_snapshot()` helpers or direct `_load_json()` over canonical suffixes | session plus suffix/path | no shared revision | `updated_at`, `events_mtime`, file mtime | each configured suffix (`chain-health.progress`, `progress`, `repair-progress`, `reap-progress`) receives an absent record |
| Watchdog live snapshot | projection | `watchdog.snapshot.build_snapshot()` | plan ID is canonical plan-dir basename; correlations bind PID to plan path by method | no persisted sequence | collection time, state/events mtimes, `last_event_age_seconds` | configured discovery root missing and process scanner unavailable are degraded; do not silently return “no plans” |
| Watchdog persisted report | projection | `cloud.status_snapshot._load_watchdog_report()` | report path and session key | no required sequence | `timestamp_utc` plus file mtime | both primary/fallback absent; unreadable/non-object; item without session |
| Watchdog registry NDJSON | projection | `WatchdogRegistry.load()` semantics, implemented read-only for inventory | `plan_id`; one latest entry wins on duplicate plan ID | observation list order, first/last seen; no durable global sequence | observation `ts`, `first_seen`, `last_seen`, file mtime | registry not configured/missing is absent; malformed file is degraded (the class currently clears all entries on any exception) |
| Repair needs-human marker | claim | `resolve_current_target()` / `classify_needs_human_blocker()` with preloaded payload | session/path; escalation/current pointer and plan refs when present | no generic revision/attempt/fence | `recorded_at`, file mtime | missing is present-false; invalid JSON, stale plan ref, superseded marker, or current pointer mismatch are contradictions |
| Repair data snapshot/index/attempts | projection | `repair_contract.load_json()`, `read_repair_index()`, `meta_repair.load_redacted_evidence()` patterns; inventory must avoid the latter's wall-clock `loaded_at` in deterministic output | session, repair attempt marker/attempt ID, problem signature, blocker fingerprint v1, index IDs | schema version and attempt records; JSONL line order where used; no common global sequence | `recorded_at`, `updated_at`, `completed_at`, deadlines, mtime | snapshot/index/attempt/sidecar classes each emitted when absent; malformed and unsupported additive fields degraded |
| Repair queue requests | claim | `repair_requests.iter_repair_requests(include_malformed=True)` | stable request ID hashes session, normalized problem signature, and redacted hint hash; `problem_signature_key`, blocker ID where available | schema version; immutable file per request, no sequence | `created_at`, file mtime | queue not configured/missing is absent; malformed files retained as degraded records |
| Repair queue decisions | decision | `repair_requests.iter_repair_decisions(include_malformed=True)` | decision ID hashes request, decision, reason, relation, and timestamp | immutable decision file; deterministic sort by timestamp/ID, no integer sequence | `created_at`, file mtime | missing decision directory is present-empty; malformed/orphan decisions degraded |
| Repair JSONL sidecars/incidents | claim/decision by record kind | `repair_contract.read_jsonl_records()` and typed append-file locations under `repair-data.d` | record IDs/attempt IDs/session and problem signatures when present | line order only; summaries validate record counts, no cross-file sequence | record timestamp plus mtime | configured sidecar kind absent; parse errors and records without session/attempt identity degraded |
| Git worktree observation | observation | reuse `cloud.repair_recurrence._probe_git_progress()` and `loop.git` status parsing, with a single inventory probe wrapper | repository root, HEAD commit SHA, base ref; dirty paths are workspace-relative | Git commit graph supplies revisions, not an inventory sequence | collection time only | no workspace, not a worktree, missing git, timeout, unresolved base, or command failure |
| Git branch/publication projection in chain state | projection | chain-state `branch_head`, `pr_head`, `last_pushed_commit`, `dirty_flag`, `sync_state`, `extra_repo_sync` | commit SHAs and repo paths | updated only when sync capture runs; no observed revision/timestamp | chain-state mtime only | missing fields are unknown, never clean by default in inventory |
| GitHub PR observation | observation | reuse `cloud.repair_recurrence._probe_pr_state()`; cached `_pr_facts()` is only a projection | repository, PR number, live state, `mergedAt`; head SHA requires a separate configured query because this probe does not return it | provider state transition, no sequence | collection time and `mergedAt` | no PR number/workspace, missing `gh`, auth/network failure, timeout, nonzero exit, invalid JSON |
| Process observation | observation | `watchdog.processes.scan_processes()` | PID, PPID, command line, category, cwd; PID alone is not stable across reuse | none | collection time, elapsed and CPU seconds | missing/failed `ps`, inaccessible cwd/procfs/lsof, or no matching signature |
| Tmux/session observation | observation | `cloud.status_snapshot.default_liveness_probe()`, injected `resolve_current_target()` session probe, and `runtime.process.TmuxSession.exists()` for private sockets | session name/socket plus marker session/PID correlation | none | collection time only | tmux missing/unreachable, session absent, probe exception, or marker/session identity mismatch |
| Active-step heartbeat in `state.json` | observation (legacy embedded) | `resolve_current_target()` / `NormalizedEvidence.liveness_detail` | active-step `run_id`, `session_id`, worker PID, phase, attempt | attempt is local and not bound to a generic grant/fence | `started_at`, `last_activity_at`; PID live probe at collection | missing active step is absent; live heartbeat with dead PID or live process with mismatched run/session is contradictory |
| Canonical `run_state` normalization | projection | `run_state.evidence.normalize_evidence()` over the single captured current-target record | inherits target, plan, chain, session, PID and fingerprint identities | inherits source-local fields; introduces no revision | inherits captured mtimes/timestamps | empty or incomplete current-target evidence resolves to explicit unknown fields |
| Canonical `run_state` resolution | decision (legacy operational classifier, not generic execution authority) | pure `run_state.resolver.resolve_run_state()` over preloaded evidence and optional blocker verdict | no new identity; result retains source/stale evidence paths | no CAS revision or source sequence | no clock read; freshness must already be encoded in evidence | conservative `UNKNOWN`, with contradictory blocker verdict retained as advisory rather than silently accepted |
| Plan `events.ndjson` | mixed observation/claim/projection; never blanket authority | parse with the schema behavior of `observability.events.read_events()` but use a no-materialization read path | plan path, event kind, transaction ID, optional run ID; model identity hashes in relevant events | `.events.seq` and per-event `seq` are monotonic per plan writer; detect duplicate/gap/out-of-order values | `ts_utc`, `ts_rel_init_s`, file mtime | file/seq sidecar absent, malformed lines, sequence disagreement, or events lacking IDs; preserve class when no events exist |
| Shadow state WAL fold | projection | `observability.fold.fold_events()` over already-read events | last `state_written` full snapshot | event `seq`; last-snapshot-wins only | source event timestamp/mtime | no `state_written`, malformed snapshots, or fold differing from `state.json` |
| Store-to-events compatibility projection | projection | `events_projection.project_events()` (pure after Store collection), not `ensure_events_projection()` | underlying Store event identity; synthetic transaction ID from plan/phase/seq | underlying sequence or enumeration fallback | normalized source timestamp | configured Store absent; projection hash differs from existing `events.ndjson`; existing legacy file is never overwritten by inventory |
| Transaction journal `_journal/tx-*.prepare.json` + `.commit` | decision about storage commit, not execution authority | inspect paths using `_core.io.journal_root()`, `journal_prepare_path()`, and JSON parsing; never call `recover_journal()` | transaction ID; content SHA-256, prior SHA-256, target/temp paths | no global sequence; prepare/commit pair is the state transition | `prepared_at`, file mtimes | journal directory absent; prepare without commit (uncommitted), commit without prepare (orphan), hash mismatch, or missing staged payload |
| Event-sourced state-store backend | configured-but-absent decision source | `EventSourcedStateStoreBackend` is deliberately unimplemented | none | none | none | always `absent/unimplemented` when `event_sourced` is configured; never fall back silently to forward-only state |

## Required contradiction catalogue

T6 should calculate contradictions from already collected records. It must not
re-read files, Git, processes, APIs, or the clock during reduction.

1. `state.json` name differs from the plan-directory name, or its active-step
   run/session identity differs from the selected cloud marker.
2. `state.json` task/execution phase says terminal while a matching live
   process exists; conversely, an active step or marker says running while the
   PID and session are dead.
3. `state.json` differs from the last `state_written` WAL snapshot. Report both
   paths and hashes; do not repair the cache.
4. `finalize.json` labels conflict with proven, scoped batch claims or a typed
   completion verdict. Mutable finalize labels do not win.
5. A batch path index, filename task digest, embedded batch number, embedded
   task-set digest, or known subject set disagree. Missing legacy scope is a
   contradiction/quarantine, not an inference from `finalize.json`.
6. Two S4 files claim the same batch index with different task digests or
   payload hashes. `list_batch_artifacts()` currently selects only the first;
   inventory must enumerate all siblings before applying compatibility
   selection.
7. Canonical, resolved-alias, and legacy chain-state candidates disagree on
   spec identity, current plan, completed prefix, cursor, PR, or Git heads.
8. Chain marker plan differs from chain-state current plan, or a terminal plan
   is paired with a nonterminal stale chain state.
9. Cloud marker workspace/spec is missing, outside the workspace, or points to
   a different run kind; a live sibling supersedes the selected marker.
10. Needs-human, repair-data, repair request, decision, or attempt records name
    a different session/plan/blocker fingerprint than current-target evidence.
11. A repair decision has no request, multiple effective terminal decisions
    conflict, or an active claim/repair remains after a terminal outcome.
12. Watchdog report/registry says alive or repairing while current process,
    tmux, marker, and repair freshness evidence says stopped/stale; or the
    inverse.
13. Git HEAD, chain `branch_head`, `last_pushed_commit`, remote/PR head, and
    execution evidence `head_sha` disagree; dirty/unknown must not collapse to
    clean.
14. Cached PR number/state conflicts with live `gh pr view`, including merged
    state without `mergedAt` or a different repository/workspace.
15. Process correlation is ambiguous (repo cwd matches multiple plans), PID is
    reused/mismatched, or tmux session and process evidence refer to different
    sessions/runs.
16. Event sequence is duplicated, missing, out of order, disagrees with
    `.events.seq`, or Store projection triples differ from the existing
    `events.ndjson` stream.
17. Transaction journal prepare/commit pairing or content hashes disagree with
    the target artifact.
18. Any legacy input lacks revision, subject attempt, capability grant,
    coordinator fence, and evidence identity. Such a record is explicitly
    non-authoritative even when internally consistent.

## Read-only hazards and collector choices

- Do **not** call `chain.spec.load_chain_state()` from inventory. It chooses a
  “best” candidate, normalizes stale state, and may call `save_chain_state()`.
  Reuse its path-candidate and schema logic, but read candidates directly.
- Do **not** call `observability.events.read_events()` or
  `observability.fold.read_events()` directly. Both call
  `ensure_events_projection()` and can materialize `events.ndjson`. Parse an
  existing file read-only, then reuse `fold_events()`.
- Do **not** call `_core.io.read_plan_state_cached(..., mode="authority")`.
  With R1 enabled it may rewrite `state.json` and emit a drift event.
- Do **not** call `_core.io.recover_journal()`, status snapshot writers, repair
  classifiers that persist drift events, or any repair/chain save helper.
- `PlanRepository.from_plan_dir(..., store=store)` can ensure an events
  projection. Bind without a Store for filesystem inventory and collect Store
  records separately.
- `resolve_current_target()` is reusable and currently read-only, but it reads
  the environment feature gate and live process state. Capture its returned
  evidence once and pass it into `NormalizedEvidence` and later reducers.
- Do **not** use `authority_readers.corroborated_completed_task_ids()` or its
  scheduler/execute wrappers during collection: they can emit authority-drift
  events. Collect with `load_evidence_nucleus()` and reduce each task with the
  pure `authority_decision_for_task()` after all inputs have been captured.
- Git, GitHub, process, and tmux probes are observations with a collection
  timestamp supplied by the inventory caller. They never supply execution
  authority.

## Registry completeness rule

The deterministic registry key should be `(category, source_class,
configured_path_or_identity)`. Sort by that key, not discovery order. Emit one
record for every row/source class above, including optional and unimplemented
classes. Concrete multi-file classes add sorted child records while retaining
their parent class record. This makes “not configured,” “configured but
absent,” “present-empty,” “present,” “degraded,” and “contradictory” distinct
states and prevents filesystem sparsity from becoming an authority decision.
