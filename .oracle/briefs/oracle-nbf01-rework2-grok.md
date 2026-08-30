# Grok 4.6 Oracle brief — NBF-01 Batch 1 rework, attempt 2 gate

## Mission

You are Grok 4.6, the independent Oracle and manager/validator for the final
NBF-01 Batch 1 rework gate. GPT-5.6 Luna has executed the frozen supplemental
tasklist `.oracle/rework/batch-1-attempt-2.md`. Validate the resulting candidate
and decide whether Batch 1 passes. Do not implement, edit, commit, push, merge,
stage, reset, clean, rebase, mutate any frozen artifact, dispatch Batch 2, or
commission any reviewer other than the one review required below.

## Required inputs (read completely)

Read, in full, before deciding:

- `.oracle/northstar.md` and `.oracle/agent_goal.md` (latest goal and policy);
- frozen `.oracle/tasklist.md`, settled plan-v8 identity, and
  `.oracle/receipts/tasklist-freeze-v8.md`;
- all original Batch 1 check-ins: `.oracle/checkins/batch-1-luna.md`,
  `.oracle/checkins/batch-1-grok.md`, `.oracle/checkins/batch-1-rework1-luna.md`,
  `.oracle/checkins/batch-1-rework1-grok.md`;
- both supplemental tasklists:
  `.oracle/rework/batch-1-attempt-1.md` and
  `.oracle/rework/batch-1-attempt-2.md`;
- both triage receipts:
  `.oracle/receipts/rework-triage-batch-1-attempt-1-grok.md` and
  `.oracle/receipts/rework-triage-batch-1-attempt-2-grok.md`;
- `.oracle/receipts/model-policy-grok-switch.md` and all attempt-2 Luna
  execution receipt/finding/check-in artifacts that the executor publishes.

The frozen identities remain: source `origin/main@798c50619204010ed3f4297fbb57988fe9381924`,
candidate branch `megado-nbf-guard-0826`, North Star SHA-256
`d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`, settled
plan-v8 SHA-256 `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`,
and frozen tasklist SHA-256
`9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`.
The candidate/diff SHA must be measured from the exact post-execution tree and
recorded in the immutable execution receipt; never infer it from an old digest.

## Verbatim Megado delegation mandate

> DELEGATION MANDATE — You are a manager and validator of the normal execution pool, NOT a worker. Delegate as much as possible to the task's selected normal model: DeepSeek V4 Flash or GPT-5.6 Luna. Flash invocation: `omp -p @<brief>.md --model deepseek-v4-flash --cwd <worktree> --no-session --auto-approve --max-time=1800`; Luna invocation: `launch_hermes_agent.py --model="codex:gpt-5.6-luna" --query-file=<brief> --project-dir=<worktree>` (research-only briefs use read/search tools). Dispatch research, execution, and critique briefs to the selected model — critique passes optimize for elegance: KISS, YAGNI, cut scope that isn't pulling its weight; flag overengineering, not just bugs. Your job is to direct, then validate: read delegated output against the acceptance criteria; do work yourself only when delegation is impossible — the selected normal model already failed at it, or the piece is too small / too tightly coupled to your own reasoning to hand off. If you catch yourself implementing or researching directly, stop and ask whether a normal-pool brief would cover it. It almost always would.

Policy is exact: normal implementation and independent review are GPT-5.6 Luna;
Grok 4.6 is Oracle and `[XHARD]` only. `[XHARD]` is none for this deterministic
contract/test gate.

## Hard gate protocol

1. Require one and only one fresh, immutable GPT-5.6 Luna execution
   receipt/finding for attempt 2. It must identify the exact candidate commit/
   HEAD and production/test diff SHA, complete changed-file inventory, and for
   every command the full argv, cwd, exit code, stdout, stderr, and stdout/stderr
   SHA-256 (not abbreviated output or a count-only claim). It must include the
   focused nine-module pytest, legacy regression, OS-process contention,
   replay/torn/crash tests, CLI statuses 0/2/3/4/5, `python -m py_compile`, and
   `git diff --check`.
2. Dispatch exactly ONE fresh independent GPT-5.6 Luna full review against the
   original 41 criteria C01–C41, every preserved prior-MET criterion, and the
   supplemental requirements RW2-01, RW2-02, RW2-03, and RW2-04. The review must
   be independent of the executor's narrative and classify every criterion
   `MET`, `NOT_MET`, or `UNEVIDENCED`, with source/test/evidence citations.
3. Only after that single review, synthesize the Oracle verdict. Return exactly
   one terminal decision: `PASS_BATCH_1` when every must criterion and evidence
   gate is met, or `ACCEPTED_ISSUES` with a complete issue list and smallest
   next action when any criterion is not met or evidence is incomplete.

The hard gate fails if the receipt is mutable, candidate-unbound, abbreviated,
missing any command digest, or if a second reviewer is used. A green test count
alone never passes the gate.

## Scope and preservation checks

RW2-01 must close the one-door locked CAS/reservation context, strict schema
matrix and append validation, and authoritative changed-precondition producers;
RW2-02 must close complete keyed provider replay/rekey/reset/break semantics;
RW2-03 must close durable two-scan confirmation, replacement/expiry/reopen,
single-consumer CAS, and exact CLI 0/2/3/4/5; RW2-04 must provide deterministic
behavioral coverage, immutable candidate-bound evidence, and remove/constrain
unofficial generic aliases/constructors. No T8 policy, admission callers,
scheduler, physical doors, launch adapters, signal wiring, second journal,
family lease, rotator, or main merge is allowed.

Confirm prior MET behavior remains intact, including one journal and existing
`_locked` mechanism; C03–C06, C08, C12, C15–C18, C25, C26 shape, C35; real
two-process reservation contention; and all custody decisions. `RW-CUSTODY` is
already MET: do not edit `.oracle/custody.md`. Keep `f8725af516da8d4249eb0d63563c37776d80daf8`
historical, keep `origin/main@798c50619204010ed3f4297fbb57988fe9381924` current,
and do not rewrite the historical 52→61 count mutation, `4aee815d...`, failed
handoff digest, or prior receipts.

## Complete immutable North Star

# North Star — Arnold self-healing supervision

**End state:** An agent harness where no worker can be launched onto a spec that
isn't live, a box that won't survive it, or a seed bound to the wrong interpreter — and where every worker death carries its killer's identity in a typed record that the recovery loop consumes before it ever retries the same fingerprint.

**Enduring principles**
- One door per invariant: admission, dispatch, and death are each enforced at exactly one place; duplicate preflights are deleted, not patched around.
- Deaths speak: SIGKILL, timeout, terminate, restack — every termination emits `{killer, signal, elapsed_s}` into the failure ledger. Silent death is a bug.
- Models are admitted, not assumed: a model id must resolve against catalog, prefix map, family classifier, and live provider membership at dispatch time, typedly rejecting expired or unknown ids.
- Fixes ship on main through the fixer contract; hotfixes that live only as deployed-but-uncommitted files do not exist.

**Anti-patterns to avoid**
- Single-scan verdicts treated as sustained truth (wedge kills, restacks).
- Anonymous integer exit codes where a disposition belongs.
- Judgment-based "healthy" claims without positive proof (live pid + advancing seq).
- Redispatch of an identical failure fingerprint without a changed precondition identity.

**Aligned progress feels like:** fewer incident classes over time, each new stall arriving with evidence attached and leaving with a root fix on main.

## Required output

Write one concise immutable Grok receipt/check-in naming the single Luna review,
exact candidate and diff identities, all command/stdout/stderr digests, the
C01–C41 and RW2-01..04 disposition matrix, preserved-MET result, North Star and
KISS/YAGNI judgment, custody/history judgment, and terminal decision. Do not
write implementation, tasklist, plan, custody, or historical-receipt changes.
End with exactly one of:

```text
PASS_BATCH_1
```

or

```text
ACCEPTED_ISSUES
```

No Batch 2 dispatch or push is authorized by this brief. Even on PASS, stop
after the Oracle receipt; later delivery requires the separate frozen gates.
