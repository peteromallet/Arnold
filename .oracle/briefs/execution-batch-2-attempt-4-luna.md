# Batch-2 attempt-4 — GPT-5.6 Luna execution brief

## Leaf execution boundary

You are the sole Normal GPT-5.6 Luna/high implementation executor for the
bounded attempt-4 packet. Read the packet first:
.oracle/rework/batch-2-attempt-4.md
Packet SHA-256:
888467b711d8c4de2de0ecfedab7245e0bad3af398e45f0c530dfb089749f078

Execute its four tasks directly and strictly serially:
R3-NATIVE-001 → R3-TERM-002 → R3-LIFE-003 → R3-AUTH-004.

This is a leaf execution, not planning, triage, review, or Oracle judgment.
Use apply_patch for every source/test edit. Do not invoke Megaplan, Megado,
OMP, another model, reviewer, agent, delegation harness, or nested launcher.
Do not commit, stage, push, merge, rewrite history, start Batch 3, or mutate
.oracle/tasklist.md, .oracle/northstar.md, .oracle/plan.md,
.oracle/agent_goal.md, .oracle/custody.md, .oracle/status.md, execution
history, or any prior artifact. Do not self-review or emit PASS_BATCH_2 or
ACCEPTED_ISSUES; produce executor evidence only. Preserve valid prior work and
the passed B2-RTB-001, B2-CHILD-005, B2-OMP-006, and B2-SCHED-008 roots.

The operator launch metadata (the executor must not run it) is exactly:

    PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model="codex:gpt-5.6-luna:high" --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/execution-batch-2-attempt-4-luna.md --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf --timeout=7200

## Immutable bindings

| Binding | Identity |
|---|---|
| Repository / branch | /Users/peteromalley/Documents/Arnold-oracle-nbf / megado-nbf-guard-0826 |
| Current HEAD | 2297fb330cdb375b4e5bd048f0d5c37d0e06db30 |
| Immutable source/base | origin/main@798c50619204010ed3f4297fbb57988fe9381924 |
| Candidate implementation | 5da26ec5be4d13559948fe4256a114ad7626482b |
| Candidate parent / tree | 19deab5bb407273e7e82d40a66fc06d17af93ad4 / e3d0376482154c4f95d2ec5809d630c4a0c32e69 |
| Candidate canonical diff | 5586c1861dce44334c3991e997bdc8b90b82d25d2ed8f28bb558b42aae499fd0 |
| Current source/test diff | acb8ca400c1b0874cea1f030630ba2f186f16cd22ceedfc2a33fe7ab592a19ec |
| Attempt-4 packet | .oracle/rework/batch-2-attempt-4.md — 888467b711d8c4de2de0ecfedab7245e0bad3af398e45f0c530dfb089749f078 |
| Source Sol check-in / receipt | .oracle/checkins/batch-2-attempt-3-sol.md — f48bffe73211a01ec8a95acb1a1cde99fc9ce6276165d64fac32b302609a27ad; .oracle/receipts/oracle-batch-2-attempt-3-sol.md — 4dad76f10aaf0a3407ecaff7948ec09d1f07457bf2d04afb683a076cef719759 |
| Clean sealed manifest | .oracle/evidence/batch-2-attempt-3-sealed.md — 2c60512f34311883849d1530af4c5b719cab7bb29434087985905c36b2573cbf |
| Frozen tasklist | .oracle/tasklist.md — 9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589 |
| Frozen North Star | .oracle/northstar.md — d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e |
| Frozen plan / goal / custody | 0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1 / 2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864 / 94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0 |
| Review-policy override | .oracle/receipts/review-policy-override-multi-luna-single-sol.md — 1e22ec54c1c1afb33e3d1faf81d2e49b8b540f6f62dbd7e0b264249716c4bccc |

Rehash all bindings before editing. The current dirty tree belongs to the
existing run; audit it and preserve necessary changes. Do not consume or copy
quarantined invalid/nested/fallback/premature-Batch-3 artifacts as evidence.

## North Star — canonical byte-for-byte block

<!-- NORTH_STAR_SHA256_BEGIN -->
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
<!-- NORTH_STAR_SHA256_END -->

Verify that the bytes between the markers, including the final newline, equal
.oracle/northstar.md exactly and hash to
d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e.

## Serial implementation requirements

### R3-NATIVE-001 — authoritative native proof

In cloud/worker_dispatch.py and the native construction seam used by
workers/_impl.py::run_step_with_worker, replace caller-trusted or resolver-only
proof with authoritative recomputation. Require exactly proof.constructable is
True; recompute and bind model/content/generation, registry/family,
backend/provider/route, observation freshness, and digest. Unknown/expired
models, negative/stale/forged/missing/ambiguous proof, and every mismatch must
refuse typedly before reservation, WBC, client, process, RPC, or launch
construction. Valid proof admits once. Add focused regression tests for every
refusal and zero-construction cardinality while retaining passed admission and
retry-boundary behavior. Do not add speculative network probes, an OMP rewrite,
provider threshold, or T8 policy.

### R3-TERM-002 — physical typed terminal transport

Depends on R3-NATIVE-001. Own the real native
workers/_impl.py::run_step_with_worker closure, OMP
workers/omp.py::run_omp_step and _run_omp_with_admission, managed
cloud/babysitter/launch.py::_admit_managed_launch, shared
cloud/worker_dispatch.py::_normalize_outcome and dispatch_with_admission, and
handlers/shared.py and handlers/execute.py transport. Each physical door must
produce typed success, ordinary failure, provider exhaustion, and worker
disposition with complete admission, dispatch, receipt, fingerprint, route,
phase/spec, worker, timing, and accepted-launch context. Compare identities and
reject mismatch; never overwrite. Record one canonical terminal before
projection. Typed death exceptions remain typed/context-complete; append/link
failure remains unresolved and holds reservation; worker disposition is never
coerced or appended twice. Add real-door tests, not generic lambda-only probes.
Do not reopen generic schemas or signal-site scope.

### R3-LIFE-003 — global persisted transition validation

Depends on R3-TERM-002. In the canonical locked ledger/reconciliation/reopen
path, enforce the frozen transition matrix globally and idempotently, including
receipt-bound physical evidence and commit-before-projection. Do not simplify
the matrix to a single happy path. Reject closed-first,
accepted-before-entered, entered-after-accepted, stale not-started,
conflicting duplicates, mixed-door histories, and selective earlier-ID
reconciliation when accepted/entered markers exist. Reopen validates complete
history rather than selecting the strongest marker. Preserve valid no-launch,
replay, at-most-once, recovered-terminal, and durable-ambiguous-hold behavior.
Do not add a second journal or scheduler.

### R3-AUTH-004 — physical WBC and contextual checker

Depends on R3-LIFE-003. In workers/omp.py and its actual OMP closure, flag-on
routes must forward the canonical WBC adapter. wbc_dispatch=None constructs it
or refuses before controlled entry/reservation and never reaches raw launch. In
scripts/check_worker_admission_authority.py, scan every configured door call
regardless of enclosing function spelling and diagnose qualified/import/module/
assignment/call aliases, truthy/reversed/multiline absent-WBC forms, aliased
process and raw launch calls, nested/double admission, chain preflight/launch,
and WBC ordering with contextual frozen categories. Add one negative fixture per
category plus an independent empty raw-symbol scan. Keep the checker static and
focused; it is not runtime authority or a general linter.

## Exact validation order

Capture a fresh external evidence directory. Every command must preserve literal
argv, UTC start/end, exit, cwd, pre/post porcelain, separate stdout/stderr byte
counts and SHA-256, and changed-path hashes. Run focused groups in serial task
order, then every exact frozen NBF-02/NBF-03 command from the packet and frozen
contract, including baseline proof, compile, checker/raw scan, and diff check.
Record failures honestly; prove unchanged babysitter failures against the clean
baseline and do not relabel them as rework.

Focused commands are the exact commands in packet
.oracle/rework/batch-2-attempt-4.md, including native-proof, physical typed
terminal, lifecycle matrix, checker-alias fixtures, full checker, and raw-symbol
scan. Do not replace them with an approximate suite. Then run all frozen
preservation commands and these final checks:

    PYTHONDONTWRITEBYTECODE=1 python -m compileall -q arnold_pipelines scripts tests
    git diff --check
    git diff --binary --full-index 5da26ec5be4d13559948fe4256a114ad7626482b -- arnold_pipelines scripts tests | shasum -a 256

Do not stop at focused green results: run the exact frozen broad gates once
unless an identical authoritative receipt is explicitly reused and bound.
Preserve all output/error streams and digest metadata.

## Required executor artifacts

After implementation and validation, create only:

- .oracle/findings/execution-batch-2-attempt-4-luna.md
- .oracle/receipts/execution-batch-2-attempt-4-luna.md

These are executor evidence, not a review or verdict. Bind every changed path,
all source/candidate/frozen/packet/Sol/policy identities, exact command/result
transcripts and digests, baseline classification, final production and full
source/test diff digests, and North Star byte-match. State explicitly that no
commit/stage/push/merge, nested model, review, verdict, Batch 3, frozen/history/
status mutation occurred. Do not alter prior artifacts.
