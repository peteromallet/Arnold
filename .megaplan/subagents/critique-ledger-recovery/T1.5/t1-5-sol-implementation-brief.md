# GPT-5.6 Sol implementation brief — T1.5 canonical simple_fixer

Start only when a mutating-lane slot is free. Use GPT-5.6 Sol with high
reasoning in a fresh isolated worktree/branch from exact clean recovery ancestor
`6787d6363e8fc0603092913ae877db14f3b9fff8`. Do not base on dirty/diverged main.
This is a 🔥 VERY HARD task.

Read completely before editing:

- T1.5 and its dependencies/evidence contract in
  `docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md`.
- `arnold_pipelines/megaplan/skills/fix-the-fixer/SKILL.md`, its referenced
  historical runs, and the zero-authority `superfixer-debug` history.
- `.megaplan/subagents/critique-ledger-recovery/T1.5/rendered-fix-the-fixer-goal.md`.
- The T0.2/T0.4 exact incident evidence and current notification/authority
  findings. Treat historical host/tmux/wrapper commands as non-authoritative.

Goal: replace the repair hierarchy with one durable M11-owned `simple_fixer`
path. The current `simple_fixer.py` is not sufficient: it uses process-local
callables, filesystem locks, mutable in-memory budget/session objects, and lives
beside still-executable watchdog/repair/meta/auditor child-launch paths.

Required end state:

1. One immutable exact occurrence is created immediately from the canonical F01
   tuple before any agent/provenance launch. Invalid/incomplete identity becomes
   terminal non-claimable intake plus one linked durable obligation; it is never
   queued, retried, or treated as missing work. Occurrence creation and identity
   must be accepted by canonical Custody, not a label/projection/local path.
2. An immediate deterministic non-agent trigger and the three-hour missed-event
   reconciler use the same occurrence and same atomic singleton claim. The claim,
   lease/epoch/fence, attempt intent, budget, result, ambiguity, and release are
   durable owner records with crash/restart/process/concurrency safety. No local
   mkdir lock, in-memory `MutationBudget`, request label, heartbeat, marker, or
   WBC receipt may mint authority.
3. Exactly one canonical runner executes one bounded `simple_fixer` mutation
   attempt under current Run Authority grant/fence, Custody lease/epoch, and WBC
   GLEK. It is a leaf: it cannot delegate children, investigators, fallback
   agents, meta-fixers, or alternative schedulers. Failure creates no child and
   no second recovery route. Provider-applied/ack-lost stays INDETERMINATE and
   non-redispatchable.
4. Retire/remove/hard-fail production authority from watchdog, repair-loop,
   L1/L2/L3 investigator/meta-repair, six-hour/progress-auditor agent dispatch,
   periodic audit agent, Kimi goal operator, managed-child recovery, direct
   relaunch, and every shell/cloud wrapper bypass. Observation/reporting may
   remain read-only. Old installed/materialized wrappers must delegate to the
   canonical owner boundary or fail closed; environment flags cannot re-enable
   them.
5. The three-hour reconciler is deterministic and non-agentic. It detects a
   missed eligible occurrence, attempts the same atomic claim, and either finds
   the prior/current ordinary fixer result or invokes that same runner once. It
   never creates a new occurrence, budget, identity, agent, scheduler, or effect
   route. Immediate and delayed triggers converge byte-for-byte on one durable
   result/receipt.
6. Fix-the-fixer becomes a distinct, explicitly authorized recovery transaction
   for the ordinary fixer implementation/backstop—not a resident delegation
   fallback. It may exist only behind a separately accepted authority envelope;
   it repairs source/backstop, retriggers the ordinary fixer, and cannot
   self-certify. With no such envelope it is typed unavailable. The v2
   `DelegationProvenanceError` must produce one durable linked obligation and one
   quiet incident transition, never notification/retry amplification.
7. Shared platform boundary: extract generic occurrence/claim/runner contracts
   outside Megaplan-specific policy where appropriate, with Megaplan adapters on
   top. Inventory non-Megaplan pipelines and prove they cannot bypass the shared
   recovery/effect authority.
8. Installed production CLI/API and materialized wrappers must expose the same
   immutable schemas/help digests and fail closed when owner services are absent.
   Local hermetic fakes must be visibly non-production and unable to cross the
   production constructor.

Required adversarial proof includes: two simultaneous initializers/processes;
immediate/reconciler races; crash at every claim/intent/effect/receipt boundary;
restart, stale lease, fence/epoch change, response loss, ENOSPC/read corruption;
wrong/missing/forked occurrence; invalid identity obligation dedupe; budget
replay/reset; forged local locks/markers/env/receipts; child/delegation attempts;
all retired wrappers/flags/direct launches; 200 observers; installed wheel and
materialized parity; and non-Megaplan bypass inventory. Prove at most one
ordinary mutation effect and zero alternate-agent launches.

Use the incident target only as an offline fixture:
`critique-ledger-accountability-v2-20260728 / cl2-wbc-backed-ledger-20260731-1411`.
Do not contact cloud/providers, deploy, restart, edit markers, or retrigger the
real epic in T1.5. Actual install/retrigger/advance proof belongs after accepted
T1.6/T1.8/T1.9 and cloud release. Local success must state those prerequisites.

Run focused, dependency-closure, concurrency/crash/fault, wrapper retirement,
installed-wheel, materialized parity, static/diff/compile, and bypass scans.
Commit only scoped work; leave the worktree clean; write exact commit/tree/files,
tests and limitations to
`.megaplan/subagents/critique-ledger-recovery/T1.5/t1-5-sol-implementation-result.md`.
Do not check T1.5 or claim formal completion without independent Sol review and
owner receipts.
