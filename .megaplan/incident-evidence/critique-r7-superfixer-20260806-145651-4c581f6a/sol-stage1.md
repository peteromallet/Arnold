## 1. Definitely broken vs. hypothesized

### Proven

- The canonical run is blocked and dead, not slow. The session PID and finalize worker are dead; heartbeat/event activity ended at 14:16Z; no authoritative driver, watchdog, finalizer, or recovery owner is live. The resident observer is not chain custody. Evidence: [evidence-pack.md](</workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-145651-4c581f6a/evidence-pack.md>), [events tail](</workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-145651-4c581f6a/raw/events-tail.ndjson>), [chain state](</workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/.chains/chain-880bd6e04632.json>).

- Finalize rejected the candidate before publication: 12 `dependency_unknown` diagnostics plus one `dependency_graph_invalid`, fingerprint `382e25a2…`, twice. There is no previously admitted finalize or feasibility hash. Evidence: [rejected candidate record](</workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/finalize_candidates/36bcefafd10ff23e6af1162c5b7186275630cec534cfd5aa0f257e9a9d69bc07.json>), [planner_repair.json](</workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/planner_repair.json>).

- The original 19-task model graph is dependency-consistent. The defect is introduced by the engine transform: `split_task` removes an original task ID and emits `_impl`/`_proof`; `split_high_complexity_tasks` does not rewrite references in other tasks. Feasibility rejects the resulting dangling IDs. The read-only reproduction exactly matches all 12 recorded pairs. Evidence: [task_splitter.py](</workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan/orchestration/task_splitter.py:212>), [task_feasibility.py](</workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan/orchestration/task_feasibility.py:305>), [reproduction output](</workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-145651-4c581f6a/raw/repro_splitter_feasibility.out.txt>).

- There is a second, currently masked reference-closure defect. The candidate’s `critique_resolution_coverage[].task_ids` and `sense_checks[].task_id` name original IDs such as `T1` and `T4`. Splitting removes those IDs. Post-split custody validates coverage against the transformed task set, so dependency-only normalization would still leave a contradictory producer/consumer contract. Evidence: [raw candidate](</workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/.megaplan/worker_tmp/local-strict-artifacts/finalize-15274aaf2cb2445487647129704dcccd.candidate.json:881>), [critique_custody.py](</workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan/orchestration/critique_custody.py:1469>), [finalize.py](</workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan/handlers/finalize.py:2146>).

- The planner-repair circuit is open because the same fingerprint occurred twice. Successful finalize owns the in-memory `meta.planner_repair` clear; the current `implementation_dispatch_allowed` value appears to be declarative—no enforcing reader was found in the pinned runtime. Evidence: [graph_admission.py](</workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan/orchestration/graph_admission.py:71>), [finalize.py](</workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan/handlers/finalize.py:2369>).

- Runtime identity and binding match the pin. The splitter came from `86c1de74c`, predating the v4 critique-custody fix. The two incidents are causally distinct.

### Still inferred or undecided

- The likely canonical replacement for dependency edges is `_impl`, but the semantics for coverage, sense checks, validation coverage, and other task-ID-bearing fields require Sol adjudication. “Always map everything to `_impl`” is not yet a proven universal rule.

- The complete reference-normalization surface may also include `validation.plan_steps_covered[].finalize_item_ids`, `user_actions[].blocks_task_ids`, and stance/task metadata. That inventory needs closure before fixing scope is final.

- It is unknown whether another feasibility or custody policy would reject the graph after all stale references are normalized.

- Same-occurrence continuation versus a migrated child, and the exact authority required to cross the open circuit, remain stage-2 decisions.

- The no-sibling-fingerprint result is bounded negative evidence, not proof that no deployment anywhere has the latent splitter defect.

## 2. Ranked root hypotheses with falsifiers

1. **Missing downstream rewiring in `split_high_complexity_tasks` — effectively confirmed.**  
   The transform removes referenced IDs and produces the exact recorded diagnostics.  
   **Falsifier:** apply the pinned splitter to the exact candidate in memory and show every resulting `depends_on` remains in the post-split ID set and that the recorded 12 pairs do not appear.

2. **Incomplete normalization of non-dependency task-ID references — high likelihood as the next blocker.**  
   Coverage and sense-check records retain removed IDs; custody validates at least coverage after splitting.  
   **Falsifier:** enumerate every task-ID-bearing field after the exact finalize mutation sequence and show that every ID resolves to a post-split task, or that an identity-matched consumer explicitly supports original-ID aliases.

3. **Open planner-repair/blocked-state contract independently prevents another publication attempt — high-confidence operational co-blocker.**  
   The graph defect caused the first rejection; the circuit and blocked projection now prevent ordinary progress without an authorized producer transition.  
   **Falsifier:** source and receipt inspection showing that the canonical finalize producer may enter directly from the current blocked state and clear/supersede the circuit under existing authority, without another ownership transition.

4. **A hidden second feasibility/custody failure remains after reference closure — medium/low likelihood.**  
   Current feasibility stops at dangling edges; corrected connectivity could expose seriality, overlap, custody, collision, or publication-order failures.  
   **Falsifier:** a read-only, in-memory execution of the full mutation and validation sequence using only the adjudicated normalization, yielding `admitted: true`, valid custody coverage, and no partial publication.

5. **Dead runner as an independent liveness blocker — certain, but downstream of the deterministic failure.**  
   Even a valid candidate cannot publish while no authoritative producer is alive.  
   **Falsifier:** a live identity-matched driver/finalizer with a fresh lease, heartbeat inside the poll window, and authoritative custody—not merely the resident listener or evidence observer.

## 3. Flash evidence commission and comparable-report contract

The DeepSeek V4 Flash swarm completed 8/8 questions. Briefs, reports, metadata, and aggregate custody are under the current evidence directory: [aggregate report](</workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-145651-4c581f6a/swarm/_report.json>).

- **fq-01:** Inspect `task_splitter.py` and `test_task_splitter.py`; establish replacement semantics, dependency-reason structure, collision/duplicate/self-dependency/chain edge cases. Informs minimal fix location and regression cases.
- **fq-02:** Search all pinned-runtime definitions and call sites of `split_task`, `split_high_complexity_tasks`, and `_split_finalize_tasks`. Informs blast radius and compatibility scope.
- **fq-03:** Trace finalize’s verification, user-action, coverage, split, feasibility, custody, and publication ordering against the raw candidate. Informs all task-ID-bearing fields and partial-publication risks.
- **fq-04:** Trace `record_rejected_candidate`, occurrence/circuit behavior, `clear_planner_repair`, and override consumers. Informs circuit ownership versus external-gate boundary.
- **fq-05:** Inspect prior authority receipts, v1 `zero_authority_rejected`, v4 handoff, and authority/Custody/WBC code. Informs same-occurrence versus migrated-child adjudication and empty-attempt negatives.
- **fq-06:** Inventory existing splitter, feasibility, finalize, graph-admission, and circuit tests without running them. Informs the focused regression set.
- **fq-07:** Search the bounded launch tree, sibling evidence, and repair-data for fingerprint `382e25a2…` and the 12-pair signature. Informs Horizon-B systemic scope.
- **fq-08:** Recheck authoritative liveness, recovery custody, leases/claims/WBC effects, and notification intent/effect/dedupe negatives. Informs immediate stop conditions and notification custody.

Exact report schema is persisted in [flash-report-contract.md](</workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-145651-4c581f6a/flash-report-contract.md>). Required ordered fields are:

```text
1 question_id
2 verdict: supported | refuted | undetermined
3 investigated_claim
4 vantage: hostname/container, workspace, runtime_or_commit, investigator
5 utc_window: started, ended
6 artifacts[]: absolute_path, exists, type, size_bytes, mtime_utc,
  sha256, role
7 commands[]: cwd, exact_command, started_utc, ended_utc, exit_code,
  stdout_summary, stderr_summary
8 trace: producer, produced_value_or_key, consumer, consumed_value_or_key,
  persistence, persisted_value_or_key, policy, predicate_and_result
9 adherence_classification: ADHERENCE | MISSING_STRUCTURE
10 missing_or_contradictory_structure
11 evidence_supporting_verdict
12 evidence_against_verdict
13 confidence
14 confidence_basis
15 immediate_decision_informed
16 durable_decision_informed
17 safety_observations
18 unresolved_questions
```

Classification rule:

- `ADHERENCE` requires an identity-matched, complete producer → consumer → persistence → policy trace.
- Any missing, ambiguous, contradictory, or unenforced required edge is `MISSING_STRUCTURE`, even if the persisted terminal value looks correct.
- Absence or ambiguity yields `undetermined`, not `refuted`.
- A report that exceeds its artifact/command bounds, omits hashes/command provenance, or performs a stateful read is quarantined as non-comparable; its self-declared verdict/classification is not adopted.

Accordingly, Flash verdicts are evidence inputs only. In particular, fq-04’s `ADHERENCE` claim is not accepted because it itself found an unenforced/write-only edge, and fq-07/fq-08 used commands outside their strict bounded allowlists.

## 4. Immediate safety constraints and Sol-only judgments

The fixer may not:

- Hand-edit `state.json`, chain state, `planner_repair.json`, candidate/finalize artifacts, receipts, leases, locks, gates, or ledgers.
- Use `--fresh`, force-proceed, force-unblock, or bypass feasibility/custody.
- Directly edit or transact against SQLite stores.
- Start a second chain, session, runner, watchdog, repair loop, or concurrent finalize owner.
- Launch, resume, rebind, migrate, or recover until stage 2 selects and authorizes a supported seam.
- Emit notifications or create notification intent/effect/dedupe records.
- Push, deploy, publish, or write outside the explicitly authorized runtime/re-entry seam.
- Treat Git ancestry, a clean worktree, passing tests, or reproduction success as execution authority.

Sol-only judgments reserved for stage 2:

- Exact fix scope: dependency fields only versus complete task-ID reference closure.
- `_impl` versus `_proof` mapping semantics for each reference family.
- Same-occurrence continuation versus authority-approved migrated child versus quarantine.
- Whether planner-repair clearing is owned by successful finalize while blocked-state admission remains an external gate.
- Whether the prior override’s authority and fingerprint binding cover this blocker.
- Sufficiency of collision, duplicate, self-reference, double-split, coverage, and partial-publication regressions.
- Whether bounded sibling negatives justify isolated or broader Horizon-B scope.
- Any stop/continue decision if identity, fingerprint, state hashes, liveness, or custody changes.

Integrity note: critical chain, plan, authority DB, WBC DB, runtime source, and candidate hashes match the pre-swarm fingerprint. One Flash investigator nevertheless opened the phase-WBC SQLite database through a normal SQLite read, refreshing its `-shm`/zero-byte `-wal` sidecar mtimes outside the evidence directory. The main database hash and mtime did not change and no logical attempt/effect was added, but this violated the strict procedural read-only boundary; fq-08 is therefore quarantined for compliance purposes.

No Horizon A/B recovery route is selected or proposed in this stage.