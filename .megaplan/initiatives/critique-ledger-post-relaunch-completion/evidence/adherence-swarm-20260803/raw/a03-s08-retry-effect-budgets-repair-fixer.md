# a03-s08-retry-effect-budgets-repair-fixer: retry-effect-budgets × repair-fixer

## Verdict

FAIL. The repository has a canonical identity/claim boundary, but no durable occurrence-wide retry/effect budget or shared idempotency authority. `simple_fixer` resets its budget on every new session; queue, auditor, watchdog, repair-loop, and meta-repair paths maintain separate counters and deadlines. This permits cross-process/restart budget bypasses and can misreport dispatch or terminal recovery.

## Intended canonical contract

The intended topology is one durable failure occurrence, one trigger, one singleton `simple_fixer`, at most one canonical target runner, and one missed-event reconciliation path (`m11-conformance-and-legacy-retirement.md:33-45`). Every mutation must use exact F01 identity, current Run Authority/Custody/WBC gates, durable effect intent before execution, provider reconciliation before retry, and one terminal or explicit `INDETERMINATE` result (`m10-safe-retry-recovery-and-effects.md:44-83`, `:93-97`).

The canonical implementation to retain is `simple_fixer`’s exact occurrence/claim/runner plus `repair_delegation`’s typed adapter (`simple_fixer.py:1-29`; `repair_delegation.py:218-245`). No canonical durable repair-effect budget currently exists. The intended durable authority is WBC effect intents/outcomes plus M7 custody lease/epoch; the design explicitly forbids a second effect or custody ledger (`m10-safe-retry-recovery-and-effects.md:44-53`).

## Evidence and complete path inventory

I searched with `rg --files` and `rg -n` across `arnold_pipelines`, `arnold`, `scripts`, `tests`, `docs`, and `.megaplan` for repair/fixer/retrigger/meta-repair/retry/budget/idempotency/claim/lock/attempt/subprocess, then inspected numbered source, schema, wrapper, test, and contract-document ranges. I also searched all production and test call sites for `MutationBudget`, `RetryLoop`, `RepairRunner`, `retrigger_ordinary_repair`, and repair-loop commands.

- **Canonical writers/callers:** `SimpleFixerSession` creates an in-memory `MutationBudget` at construction and records mutations only in memory (`simple_fixer.py:411-465`, `:473-532`). `delegate_to_simple_fixer` creates a fresh session per call and releases the occurrence claim immediately afterward (`repair_delegation.py:301-340`).

- **Durable queue writers:** `enqueue_repair_request` derives request IDs from session, normalized problem signature, hint hash, and optional identity (`repair_requests.py:669-694`, `:931-953`). Decisions and dispatch attempts are append-only files (`repair_requests.py:1422-1535`). Claim-failure retry counting is read-count-then-write (`repair_requests.py:1538-1593`).

- **Durable readers/status consumers:** `project_repair_custody` counts queue attempts and derives a one-or-three-attempt projection, but does not reserve admission (`repair_contract.py:1484-1494`, `:1543-1555`). Trigger scans consume requests and decisions; terminal audit consumes snapshots and verifier receipts (`arnold-repair-trigger:484-525`, `terminal_audit.py:162-284`).

- **Additional retry authorities:** L3 escalation keeps its own two-failure/ two-launch budgets in escalation state (`progress_auditor_escalation.py:63-74`, `:1159-1237`, `:1367-1400`). The six-hour auditor changes the blocked-task identity and event signature for each retry ordinal (`six_hour_auditor.py:320-367`). `watchdog.RetryLoop` keeps a process-local three-attempt counter (`watchdog/retry.py:140-249`). The shell repair loop uses an independent 7200-second deadline (`wrappers/arnold-repair-loop:148-151`, `:265-272`). Meta-repair uses 5400 seconds (`meta_repair.py:83-88`).

- **Legacy/direct surfaces:** `meta_repair.retrigger_ordinary_repair` can release a lock and call `subprocess.run` directly (`meta_repair.py:2296-2375`). `watchdog.RepairRunner` remains an exported executor surface, although its megaplan path currently rejects direct execution (`watchdog/repair_runner.py:305-313`, `:508-572`).

## Adherence gaps

1. **P0 — authority mutation: budget is not durable or occurrence-wide.**  
   `MutationBudget` is instantiated with zero counters on every new `SimpleFixerSession`; its `to_dict()` is not persisted or reloaded (`simple_fixer.py:411-465`, `:487-494`). The delegation shim creates a new session for each caller and releases the claim after one attempt (`repair_delegation.py:301-314`). Therefore a retry, restart, or second container can re-enter the same occurrence with a fresh budget. Existing tests prove only same-process behavior (`tests/cloud/test_simple_fixer.py:281-343`).

2. **P0 — authority mutation: effect idempotency is absent at the fixer boundary.**  
   The canonical runner accepts an arbitrary mutation callable and only compares before/after fingerprints (`simple_fixer.py:499-532`, `:902-926`). No durable effect intent, provider outcome, or effect idempotency key is recorded. The occurrence claim prevents simultaneous holders, not repeated effects after release or restart.

3. **P1 — authority mutation and status misreporting: queue admission is not an atomic budget reservation.**  
   Attempt IDs include timestamp, PID, command, and manifest (`repair_requests.py:1490-1518`), so repeated dispatches for one logical request can create distinct attempts. Claim-failure retries count existing files before writing a new decision without a CAS/lock (`repair_requests.py:1550-1579`); concurrent callers can both observe the same count and exceed the intended retry cap. The projection merely counts afterward (`repair_contract.py:1489-1494`), so it cannot prevent the mutation.

4. **P1 — authority mutation: retry identity is split by layer.**  
   The six-hour backstop embeds `attempt:N` into `blocked_task_id` and `event_signature` (`six_hour_auditor.py:323-367`). Since those fields participate in normalized request identity (`repair_requests.py:685-694`, `:931-953`), retries can become new blocker/request identities and evade the original occurrence’s budget.

5. **P1 — status misreporting: terminal audit is structurally unable to perform its canonical retrigger.**  
   `capture_terminal_snapshot` returns no `repair_target` (`terminal_audit.py:115-133`), but `run_terminal_audit` reads it as the delegation target (`terminal_audit.py:208-220`), yielding zero-authority rejection. It also constructs `marker_dir/repair-queue` instead of the required absolute `<workspace>/.megaplan/repair-queue` (`terminal_audit.py:223-233`; `repair_requests.py:546-581`). Finally, `returncode or 73` converts a successful zero return code into rejection (`terminal_audit.py:257-264`). The verifier fabricates positive observation fields before independent evidence exists (`terminal_audit.py:265-282`).

6. **P2 — dormant duplicate/status risk: legacy meta/watchdog/repair-loop authorities remain.**  
   Meta-repair’s direct subprocess retrigger and independent deadline (`meta_repair.py:2296-2368`) and watchdog’s in-memory `RetryLoop` (`watchdog/retry.py:157-222`) are not consolidated with the canonical occurrence. The trigger hard-codes `meta_dispatch=False` (`arnold-repair-trigger:512-518`), making its managed-launch branch unreachable; its current fallback only invokes a fingerprint-preserving no-op (`arnold-repair-trigger:1577-1610`). This is currently mostly a typed-failure/status problem, but retained entrypoints remain bypass candidates.

## Incident reachability and severity

The Critique-shaped failure is reachable independently of its original details: two callers can use the same occurrence, release/reacquire the singleton claim, and each obtain a fresh mutation budget. A process kill after an external effect but before local receipt also permits a blind reattempt because no durable intent/outcome or provider reconciliation exists. This is P0 authority risk.

The terminal-audit defects are independently reachable and currently produce false rejection rather than duplicate mutation. The queue retry race and retry-ordinal identity split can create excess retry decisions or new budget scopes. The legacy paths are lower-confidence in current production reachability because direct call-site search found their strongest uses in tests and guarded/rejection paths; they nevertheless violate the required retirement proof.

## Minimal generalized remediation

- Make the existing `simple_fixer` occurrence fingerprint the sole repair identity, but replace its in-memory `MutationBudget` with one durable WBC effect-intent/outcome record keyed by `(occurrence, effect kind, deterministic attempt key)`, guarded by current Run Authority fence and M7 lease/epoch.
- Atomically reserve budget before mutation; persist intent first; reconcile unknown provider outcomes before retry; make outcome commits idempotent. Recreate sessions from this record after restart.
- Route trigger, manual, six-hour, terminal, meta, watchdog, and reconciliation callers through one occurrence-dispatch API. Store `retry_ordinal` as metadata, never as a new blocker/task identity.
- Fix terminal audit to obtain the exact target from the durable request and use `repair_requests.repair_queue_dir`; remove fabricated observations and the `returncode or 73` bug.
- Make queue decision/attempt reservation atomic and derive IDs from stable occurrence/effect keys, not timestamps/PIDs.
- Migrate existing requests by exact F01 identity; ambiguous records become typed `INDETERMINATE`. Then delete or make unreachable direct subprocess/retry-loop/repair-loop mutation paths.

## Required tests and retirement proof

Require deterministic tests for:

- concurrent threads/processes/two containers racing one occurrence: exactly one reservation/effect;
- restart after intent, after provider timeout, and after durable outcome: no duplicate effect;
- provider success, retryable failure, timeout/unknown, and non-queryable provider;
- unchanged fingerprint budget across recreated sessions and retry layers;
- stale lease/fence, PID reuse, foreign PID namespace, and cross-host claim attempts;
- immediate trigger plus three-hour backstop sharing one request/effect key;
- terminal audit successful zero return code, missing target, wrong queue path, and independent verification.

Retirement proof must include static and runtime negative scans showing no production callers or reachable definitions for direct `subprocess` repair execution, `RetryLoop` mutation admission, legacy repair-loop relaunch, or per-layer budget writers. Invoke each retired entrypoint in a two-container test and require typed rejection with no mutation, no attempt reservation, and no managed-agent manifest. This satisfies the required proof that bypasses are deleted or unreachable, not merely wrapped.

## Unknowns

The snapshot does not establish whether an external WBC provider already stores repair-effect intents outside this repository, nor whether `arnold-repair-loop` is independently launched by deployment configuration not present here. Those must be verified before migration; absent such evidence, the repository-local behavior is nonconformant.