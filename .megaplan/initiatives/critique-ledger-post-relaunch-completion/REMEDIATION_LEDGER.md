# Cross-pipeline remediation ledger

This is the durable source of truth for the 2026-08-03 Critique recovery and the
pipeline-wide adherence audit. A row is not `fixed` until it names an integration
commit, focused verification, and retirement or reachability proof. Raw Luna
reports are evidence inputs, not authority; findings may be accepted, merged,
rejected, or deferred after parent review.

## Status vocabulary

- `auditing`: evidence collection is incomplete.
- `accepted`: evidenced and admitted to the remediation graph.
- `fixing`: mutation-authorized Luna work is active.
- `fixed-local`: integrated and verified locally, not cloud-canary proven.
- `proven-cloud`: deployed and proven across the relevant topology.
- `follow-up`: deliberately outside the Critique relaunch gate, with an epic task.
- `rejected`: unsupported, duplicate, unreachable, or worse than the canonical design.

## Definitive ledger

| ID | Severity | Finding / invariant breach | Scope | Status | Fix / evidence | Remaining proof |
|---|---|---|---|---|---|---|
| MP-001 | P0 | Watchdog report writes could expose partial JSON and collapse status collection | cross-pipeline status | fixed-local | `c3b0be1398` | cloud crash-write canary |
| MP-002 | P0 | Critique adapter discarded supported metadata and could synthesize false zero-findings | critique transport | fixed-local | `f69bf6c880` | provider canary with preserved payload |
| MP-003 | P0 | Failure identity collapsed distinct attempts and accepted stale results | orchestration | fixed-local | `abce65bef8` | restart/incarnation canary |
| MP-004 | P0 | Notification occurrence was not durably established before provenance resolution, causing repeated alerts | notification/escalation | fixed-local | `952b7b3eca` | same-occurrence replay and Discord quietness |
| MP-005 | P0 | Provider schema dialect and typed failure routing were incomplete | all model phases | fixed-local | `f401431b7a`, `b168edbca0`, `18b279f5ef` | GLM/DeepSeek/Sol live canaries |
| MP-006 | P0 | Finalize expected inline capture, rejected a valid artifact receipt, used the wrong post-handler schema, and retried outside the inner budget | Finalize | fixed-local | `3b71e91b7d`, `5ce4605a33` | adopt recovered artifact under a new immutable attempt |
| MP-007 | P0 | Bare PID evidence and foreign PID namespaces could report a live runner dead | status/liveness | fixed-local | `f39e0133ae`, `cfc65d7b76` | real sibling-container test |
| MP-008 | P0 | Repair claim/lock paths could reclaim a foreign-container owner and create duplicate fixers | repair/fixer | fixed-local | integration `9ceacd85de`; source `d4eb9ddb6d`; 205 focused tests | real sibling-container contention canary |
| MP-009 | P0 | Current-target consumers independently converted incomplete/foreign evidence into booleans that authorized repair, retrigger, or escalation | status → repair/escalation | fixed-local | integration `c694c06f0c`; source `8cece78a36`; 569 focused tests | shell-wrapper cutover and publisher parity |
| MP-010 | P0 | Active-step orphan recovery or state-load reconciliation can treat foreign/unknown custody as dead and redispatch or erase the effect | execute/runtime | fixed-local | integration `3a0f1496d2`, `82ea057edd`; source `49bdac1a95`, `d313f8ef3f`; source suite 189 passed, 1 platform skip | combined rerun, Linux SIGSTOP, real sibling-container canary |
| MP-011 | P1 | Legacy status reducers and shell wrappers can bypass canonical bound liveness | CLI/wrappers | accepted | MP-009 audit gaps; 50-cell audit in progress | consolidate readers and prove bypass deletion |
| MP-012 | P1 | Plan/auto launch paths may not publish the same bound owner lease as chain runs | launch/runtime | accepted | MP-009 audit gap | publisher parity tests and rollout |
| MP-013 | P1 | Historical tmux/status fields remain operator-visible despite being non-authoritative | status UX | accepted | MP-009 audit gap | wording/schema migration; no control consumers |
| MP-014 | P1 | Hermes/Shannon occurrence-wide retry and artifact handoff parity is not yet proven | provider runtime | accepted | Finalize adversarial review | parity implementation/tests or rejection with proof |
| MP-015 | P1 | Atomic JSON and primary-corrupt fallback behavior are not universal | persistence/projection | auditing | 50-cell Luna audit | enumerate writers/readers, consolidate, fault injection |
| MP-016 | P1 | Runtime/profile provenance is not universal across plan, epic, watchdog, and resident launch | launch/provenance | auditing | 50-cell Luna audit | dependency-closed launch identity contract |
| MP-017 | P1 | Incident version/dedupe rules may still contain hard-coded or payload-conflict bypasses | notification/escalation | auditing | 50-cell Luna audit | occurrence/version tests and canonical writer cutover |
| MP-018 | P1 | M7 cursor reconciliation may not be epoch/incarnation-bound everywhere | event journal | accepted | follow-up epic `340d76a36f` design evidence | implement and prove restart recovery |
| MP-019 | P1 | Stale sibling sessions can be resurrected without explicit lineage/retirement proof | chain/session discovery | auditing | 50-cell Luna audit | lineage admission and negative resurrection tests |
| MP-020 | — | Remaining invariant × surface cells | all pipeline surfaces | auditing | `evidence/adherence-swarm-20260803/raw/` | rolling triage into concrete rows |
| MP-021 | P0 | Default-reachable legacy force-proceed mutates state/debt/projections outside CAS custody | critique/revise/gate | fixing | raw audit `a01-s02`; Luna worktree `fix/canonical-force-proceed-20260803` | sole-owner retirement proof, tests, integration, cloud canary |
| MP-022 | P1 | Critique recovery can adopt a pre-existing unbound scratch artifact after current invocation failure | critique transport | accepted | raw audit `a01-s02` | shared invocation-bound artifact protocol or delete fallback |
| MP-023 | P1 | Revise/finalize control reads `gate_carry.json` projection without canonical evidence pairing | gate/revise/finalize | accepted | raw audit `a01-s02` | verified gate reader and tamper tests |
| MP-024 | P1 | Critique custody receipts are replaceable and insufficiently bound to iteration/path | critique custody | accepted | raw audit `a01-s02` | create-once receipt and binding tests |
| MP-025 | P1 | Init/run/bridge have split initial-state ownership and may swallow durable persistence failure | prep/plan/runtime bridge | accepted | raw audit `a01-s01` | transactional canonical initializer and failure propagation |
| MP-026 | P1 | Raw `state.json` reads and conditional R1 mode let a declared projection become authority | prep/plan/general state | accepted | raw audit `a01-s01` | unconditional authority reader and direct-reader retirement |
| MP-027 | P1 | Missing/corrupt `prep.json` becomes an empty blast-radius input instead of failing closed | prep/plan | accepted | raw audit `a01-s01` | structured failure plus corrupt/missing tests |
| MP-028 | P0 | Execute merge accepts scoped entries with no dispatch/envelope authority metadata | execute merge | fixing | raw audit `a01-s04`; Luna worktree `fix/execute-authority-single-owner-20260803` | fail-closed retirement, tests, integration |
| MP-029 | P0 | Execute recovery adopts latest unbound scratch/checkpoint and stamps it with current authority | execute provider recovery | fixing | raw audit `a01-s04`; same Luna worktree | attempt-bound handoff and stale-artifact tests |
| MP-030 | P0 | Top-level artifact evidence can synthesize done/check acknowledgement outside accepted envelopes | execute evidence | fixing | raw audit `a01-s04`; same Luna worktree | advisory-only evidence and mutation tests |
| MP-031 | P1 | Epic child disagreement preserves projection-derived complete and advances parent | review/epic chain | accepted | raw audit `a01-s05` | validated child acceptance and fail-closed disagreement |
| MP-032 | P1 | Shadow/supervisor completion writers remain live beside CAS acceptance | chain completion | accepted | raw audit `a01-s05` | sole CAS writer and legacy-mode retirement |
| MP-033 | P1 | Cloud status accepts receipt-shaped dictionaries without canonical receipt validation | status/chain | accepted | raw audit `a01-s05` | canonical validator cutover and forgery tests |
| MP-034 | P1 | Review may transition done when required provider/evidence is unavailable | review | accepted | raw audit `a01-s05` | explicit evidence policy and transactional binding |
| MP-035 | P0 | Auto performs an unlocked stale whole-document rewrite of `finalize.json`, which can erase concurrent execution evidence/status | Finalize/Execute boundary | accepted | raw audit `a01-s03` | field-scoped CAS mutator; queued after overlapping MP-028–MP-030 work |
| MP-036 | P1 | Post-Finalize execution, timeout, merge, and backstop paths independently rewrite `finalize.json` without one typed mutation owner | Finalize/Execute boundary | accepted | raw audit `a01-s03` | consolidate all active writers and prove direct-writer retirement |
| MP-037 | P1 | Finalize model call is marked mutable, disabling configured provider fallback | Finalize provider routing | accepted | raw audit `a01-s03` | explicit model-only fallback capability and provider matrix |
| MP-038 | P1 | Finalize promotion evidence attests the persisted schema rather than the model-capture schema and is not durable | Finalize evidence | accepted | raw audit `a01-s03` | correct schema binding and receipt persistence |

## Rolling disposition log

| Time (Europe/Berlin) | Input | Disposition |
|---|---|---|
| 2026-08-03 20:55 | P0 repair ownership Luna implementation | Accepted, integrated as `9ceacd85de`, remains `fixed-local` pending real two-container canary. |
| 2026-08-03 20:55 | P0 bound current-target liveness Luna implementation | Accepted, integrated as `c694c06f0c`; explicit wrapper/publisher gaps split into MP-011–MP-013. |
| 2026-08-03 20:58 | Combined MP-008/MP-009 regression | 224 tests passed on the integration head across repair lock/request, current target/liveness, repair goal, terminal audit, and progress-auditor paths. |
| 2026-08-03 21:01 | P0 active-step incarnation Luna implementation | Integrated as `3a0f1496d2`; conflict resolved by retaining full lease identity plus target PID; 53 combined tests passed, 1 Linux-only skip. |
| 2026-08-03 21:02 | Raw audits `a01-s01`, `a01-s02` | Accepted MP-021–MP-027; immediate P0 force-proceed fixer dispatched. P2 duplicates remain source inputs pending deduplication. |
| 2026-08-03 21:05 | Raw audits `a01-s04`, `a01-s05` | Accepted MP-028–MP-034. P0 Execute single-owner Luna fixer launched immediately; P1 review/chain work dependency-queued. |
| 2026-08-03 21:05 | P0 active-step follow-up | Integrated `82ea057edd` so state-load reconciliation also preserves LIVE/UNKNOWN custody; source suite 189 passed, 1 skip. |
| 2026-08-03 21:07 | Raw audit `a01-s03` | Accepted MP-035–MP-038. MP-035 is P0 but overlaps the active Execute-authority fixer in `auto.py`/execute writers, so it is dependency-queued rather than creating conflicting concurrent edits. |
| 2026-08-03 20:49 | 50-cell Luna audit matrix | Started with five concurrent read-only agents; every completed report will be triaged here before fixer dispatch. |

## Admission and completion rule

For each raw report:

1. Verify cited code and reachability on the integration head.
2. Merge duplicates into one invariant-level item; preserve all source report IDs.
3. Reject speculative or display-only issues incorrectly presented as authority mutation.
4. Order accepted work by dependency and overlapping files.
5. Dispatch Luna with one mutation scope and one worktree per non-overlapping item.
6. Require a commit, focused tests, regression tests, and explicit duplicate-path retirement proof.
7. Integrate, rerun the combined suite, then promote only after the relevant cloud canary.
