# Grok 4.6 Oracle brief — NBF-01 Batch 1 rework triage, attempt 1

## Role and hard boundaries

You are Grok 4.6 acting as the independent Oracle/sense-checker for the
failed-but-`ACCEPTED_ISSUES` NBF-01 Batch 1 handoff. You are a manager and
validator, not an implementer. Do not edit production or test code. Do not
commit, push, merge, stage, reset, clean, start Batch 2, mutate the frozen
`.oracle/tasklist.md`, or redesign the settled plan. This brief authorizes only
the two prose artifacts named below.

Write:

1. `.oracle/rework/batch-1-attempt-1.md` — the smallest coherent supplemental
   rework tasklist, with deduplicated tasks, dependencies, file ownership,
   acceptance criteria, and exact tests.
2. `.oracle/receipts/rework-triage-batch-1-attempt-1-grok.md` — a concise
   decision receipt naming the source identities, triage result, classifications,
   and any remaining blockers.

Do not write either artifact by claiming implementation is complete. The
rework tasklist must be ready for GPT-5.6 Luna normal execution, with Grok
reserved for Oracle and any genuinely exceptional `[XHARD]` task only.

## Authority, identities, and evidence set

Read all of these completely before deciding:

- `.oracle/northstar.md` (complete immutable North Star, reproduced below)
- `.oracle/agent_goal.md` (latest goal and authoritative model policy)
- `.oracle/plan.md` (complete settled plan v8, SHA-256
  `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`)
- `.oracle/tasklist.md` (complete frozen tasklist, SHA-256
  `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`)
- `.oracle/receipts/model-policy-grok-switch.md`
- `.oracle/checkins/batch-1-grok.md` (the eight accepted issues)
- `.oracle/checkins/batch-1-luna.md` (independent review and evidence)
- `.oracle/findings/execution-nbf01-luna.md`
- `.oracle/receipts/execution-nbf01-luna.md`
- `.oracle/custody.md` (especially the contradictory historical/source-base
  wording)
- `.oracle/briefs/execution-nbf01-sol.md` (execution contract and evidence
  custody language)
- `.oracle/briefs/oracle-nbf01-grok.md` (prior Oracle contract and mandate)

The immutable source base is `origin/main@798c50619204010ed3f4297fbb57988fe9381924`.
The candidate branch is `megado-nbf-guard-0826`. The North Star SHA-256 is
`d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`.
The executor receipt is internally contradicted: its start-gate claim was 52
focused tests and later became 61; Luna reproduced 61 focused and 78 legacy
tests; the claimed owned production digest `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`
does not reproduce, while Luna computed
`50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`.
Treat this as evidence mutation/integrity work, not as a harmless typo.

## Verbatim delegation mandate

> DELEGATION MANDATE — You are a manager and validator of the normal execution pool, NOT a worker. Delegate as much as possible to the task's selected normal model: DeepSeek V4 Flash or GPT-5.6 Luna. Flash invocation: `omp -p @<brief>.md --model deepseek-v4-flash --cwd <worktree> --no-session --auto-approve --max-time=1800`; Luna invocation: `launch_hermes_agent.py --model="codex:gpt-5.6-luna" --query-file=<brief> --project-dir=<worktree>` (research-only briefs use read/search tools). Dispatch research, execution, and critique briefs to the selected model — critique passes optimize for elegance: KISS, YAGNI, cut scope that isn't pulling its weight; flag overengineering, not just bugs. Your job is to direct, then validate: read delegated output against the acceptance criteria; do work yourself only when delegation is impossible — the selected normal model already failed at it, or the piece is too small / too tightly coupled to your own reasoning to hand off. If you catch yourself implementing or researching directly, stop and ask whether a normal-pool brief would cover it. It almost always would.

## Eight accepted issues to triage and deduplicate

Preserve the frozen NBF-01 scope. Combine issues only where they share one
authority and one coherent implementation seam; do not split into ceremonial
microtasks or duplicate ownership.

1. **Atomic CAS / one ledger door (blocker).** `IncidentLedger.reserve`,
   `append_terminal_outcome`, `reserve_provider_route_child`,
   `consume_changed_precondition`, `create_probe_lease`, and
   `reconcile_reservation` read/compare outside `_append_nbf`'s lock. Make the
   existing journal the single lock/read/compare/append authority and add real
   concurrent-process regressions.
2. **Strict schema and illegal-state matrix (blocker).** Close the complete
   `DispatchOutcome` payload matrix and version/enum/identity invariants for
   `WorkerDisposition`, `ObservedProcessDeath`, `NonWorkerSignalDisposition`,
   and reconciliation; reject false OOM evidence and fabricated unknown-death
   killer/signal values at decode and append paths.
3. **Evidence-bound changed-precondition producers (blocker).** Replace generic
   caller-controlled producer/version/subject/evidence/hash inputs with fixed
   reason-specific producers deriving identities from authoritative evidence;
   bind provider-failure-key before/after and consume atomically.
4. **Forgeable terminal/reconciliation context (blocker).** Bind terminal
   plan/phase/projection/fingerprint/receipt/logical identity to the reservation;
   prove the three legal reconciliation resolutions from persisted authoritative
   evidence, reject blind/closed/accepted release, and make replay/conflict
   decisions atomic.
5. **Global/incomplete keyed provider replay (major).** Project by the frozen
   projection/failure key, preserve streak through probe and single-use
   `provider_recovery_verified`, allow the matching child transition, and reset
   or rekey only for authoritative key-changing evidence. Do not implement T8
   thresholds or policy here.
6. **Timestamp-only two-scan confirmation (major).** Make confirmation
   ledger-owned and durable across restart, compare PID/process-start/progress/
   incarnation/cause/evidence identity, record replacement/expiry, and enforce
   locked single consumption.
7. **Incomplete disposition CLI contract (major).** Implement exact frozen
   statuses 0/2/3/4/5, validate ledger location, require consumed confirmation,
   and preserve one JSON acknowledgement/no signalling behavior.
8. **Thin/mutated acceptance evidence (major).** Add behavioral regressions for
   every frozen must criterion that the review says is absent (multi-process
   races, crash/torn composite, forged valid hashes, context mismatch, positive
   OOM/unknown death, replacement/incarnation/restart, CLI 4/5, replay byte
   identity). Reconcile the 52-versus-61 test-count mutation and replace the
   unreproducible owned-diff digest with a reproducible command transcript and
   digest bound to the actual candidate source. Do not rewrite history or
   fabricate evidence.

Also correct the custody wording as an evidence-only correction: the old
`f8725af...` value in `.oracle/custody.md` must be explicitly labeled
historical, while refreshed source custody is
`798c50619204010ed3f4297fbb57988fe9381924`. Do not silently alter the frozen
tasklist, candidate code, or source base. Decide whether this correction belongs
in the rework receipt/evidence protocol or requires a separately authorized
custody-document task; call out that boundary explicitly.

## Required triage output

In `.oracle/rework/batch-1-attempt-1.md`:

- State that this is supplemental rework only; NBF-01 remains unaccepted and
  Batch 2 is prohibited until the rework passes a fresh Oracle gate.
- Deduplicate the eight issues into the minimum coherent task set. For every
  task, provide: ID, severity, normal vs `[XHARD]` classification and the
  exceptional-threshold rationale, executor model, exact dependencies, exact
  owned production/test/evidence files, prohibited files/behaviors, acceptance
  criteria, and exact test commands (including concurrency/replay/crash tests).
- Apply the user policy exactly: normal implementation, exploration, critique,
  and review are GPT-5.6 Luna; Grok 4.6 is Oracle and `[XHARD]` only. Do not
  classify ordinary deterministic contract/test work as `[XHARD]` merely because
  it is broad. If no item meets the exceptional threshold, say `none`.
- Keep the frozen ownership boundary: NBF-01 primitives only; no admission,
  scheduler, T7/T8 policy, physical doors, launch adapters, signal-site wiring,
  fallback policy, second journal, second projection, or main merge.
- Include exact focused command from settled plan §6/NBF-01, plus explicit
  commands for subprocess contention, replay/torn-write/crash boundaries,
  `python -m py_compile`, `git diff --check`, and CLI status branches. Make
  evidence tests deterministic and avoid merely inflating test count.
- Include a final gate requiring a fresh Luna execution/review result, corrected
  immutable evidence receipt, and a separate Grok Oracle decision. No commit,
  push, merge, plan mutation, or Batch 2 dispatch is authorized by this brief.

In `.oracle/receipts/rework-triage-batch-1-attempt-1-grok.md`, record the exact
source hashes, the eight-to-task mapping, model classifications, custody-source
correction, evidence-mutation correction, and the final recommendation. The
receipt must state that no implementation was performed.

## Complete immutable North Star

# North Star — Arnold self-healing supervision

**End state:** An agent harness where no worker can be launched onto a spec that
isn't live, a box that won't survive it, or a seed bound to the wrong interpreter —
and where every worker death carries its killer's identity in a typed record that
the recovery loop consumes before it ever retries the same fingerprint.

**Enduring principles**
- One door per invariant: admission, dispatch, and death are each enforced at
  exactly one place; duplicate preflights are deleted, not patched around.
- Deaths speak: SIGKILL, timeout, terminate, restack — every termination emits
  `{killer, signal, elapsed_s}` into the failure ledger. Silent death is a bug.
- Models are admitted, not assumed: a model id must resolve against catalog,
  prefix map, family classifier, and live provider membership at dispatch time,
  typedly rejecting expired or unknown ids.
- Fixes ship on main through the fixer contract; hotfixes that live only as
  deployed-but-uncommitted files do not exist.

**Anti-patterns to avoid**
- Single-scan verdicts treated as sustained truth (wedge kills, restacks).
- Anonymous integer exit codes where a disposition belongs.
- Judgment-based "healthy" claims without positive proof (live pid + advancing seq).
- Redispatch of an identical failure fingerprint without a changed precondition.

**Aligned progress feels like:** fewer incident classes over time, each new stall
arriving with evidence attached and leaving with a root fix on main.
