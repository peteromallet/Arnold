# Luna execution brief — NBF-01 Batch 1 rework 5

## Leaf execution contract

You are GPT-5.6 Luna at high reasoning, executing the sealed attempt-5
supplemental packet as a **LEAF execution inside an already-running frozen
Megado pipeline**. Do not invoke Megaplan, Megado, a nested harness, or any
other orchestrator. Do not create plans or mutate plan state. Execute exactly
the packet's serial tasks:

```text
RW5-01 → RW5-02 → RW5-03
```

Use one repository writer at a time. Inspect the dirty tree and current build
first; build on existing work and preserve orchestrator-owned artifacts. Use
`apply_patch` for all source/test edits. Do not self-review, issue an Oracle
verdict, dispatch a reviewer, commit, stage, push, merge, rebase, reset, or
start Batch 2. The later independent review and Grok gate are separate phases.

Write exactly these executor artifacts after the stable post-fix tree and
validation are complete:

- `.oracle/findings/execution-nbf01-rework5-luna.md`
- `.oracle/receipts/execution-nbf01-rework5-luna.md`

These are executor evidence, not an Oracle review. Do not write or rewrite any
historical receipt, finding, check-in, brief, packet, frozen file, or custody
artifact.

## Immutable source and evidence bindings

Candidate repository:
`/Users/peteromalley/Documents/Arnold-oracle-nbf`

- branch: `megado-nbf-guard-0826`
- planning/current HEAD at packet sealing:
  `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- immutable source and merge-base:
  `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- frozen tasklist `.oracle/tasklist.md` SHA-256:
  `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- North Star `.oracle/northstar.md` SHA-256:
  `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- attempt-4 reviewed production diff SHA-256:
  `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41`

The attempt-5 packet and triage receipt are sealed inputs:

- `.oracle/rework/batch-1-attempt-5.md` SHA-256:
  `f2c2224d6b46eda303b1768a4a2e520fc08224eef9c93e506daa14ea3b2042d7`
- `.oracle/receipts/rework-triage-batch-1-attempt-5-grok.md` SHA-256:
  `dedf5870dc889b137484202290925482b4813a742414233dc83ecd7c5fa18b5a`

Bind the prior accepted-issues gate evidence and do not alter it:

- attempt-4 Luna check-in SHA-256:
  `01b8f596c33342fd3529f3982c9bba2605cd3fa41c44d36a0091b3dd8330972c`
- attempt-4 Luna receipt SHA-256:
  `de0c6265e58a477b120f944740d5b88ba1834347ae3829d3def4517922e345ee`
- attempt-4 Grok check-in SHA-256:
  `81a0018acd1d61835988bcc623d265376ec2a3ec8cac8634a902199b750936cf`
- attempt-4 Grok receipt SHA-256:
  `dfba88485d5e101e86aaec541131a22312bbebe1b910b90455c53545fe90a607`
- attempt-4 packet SHA-256:
  `4df7024a285e3d0c373278dbd72aed98a0d5af26b05f1f880cf64e9f20a2d534`
- attempt-4 triage receipt SHA-256:
  `3d20f7bc585e5b5495a38b7a2a26caf1050c90f6dc14f719a95d3203516cfa2c`
- attempt-4 executor finding SHA-256:
  `b277eced2d19b92a1a70a5496c40a75a19fc7e14aa116678dfad865aeef4d6c1`
- attempt-4 executor receipt SHA-256:
  `8739b5ebf73d2d4bdb9d9c089e7da80b3005f230794c0fe2fae306428f1a247f`

Also read and preserve `.oracle/agent_goal.md`, `.oracle/custody.md`, settled
plan v8, and all prior attempt artifacts. Historical attempt-1/2/3/4 digests,
the start-gate 52→61 observation, unreproducible `4aee815d…`, and failed
handoff `50c86490…` remain historical and must not be normalized or rewritten.

Before editing, report the actual candidate HEAD, branch, source/merge-base,
worktree status, packet/receipt hash matches, frozen tasklist/North Star hash
matches, and attempt-4 production-diff match. The final receipt must report
the post-fix candidate HEAD and new production diff identity; the attempt-4
digest is a baseline, not the attempt-5 target.

## Scope, ownership, and prohibited changes

Own only the NBF-01 primitive files already in the candidate: the existing
incident schemas/ledger, orchestration outcome/classification, disposition
helper/CLI, and the eight named NBF test modules. `test_incident_ledger.py`
remains unchanged relative to source.

Do not edit admission callers, schedulers, T7/T8 policy, launch adapters,
signal-site wiring, fallback policy, later-task files, custody, frozen
tasklist/plan/North Star/agent goal/status, or any historical evidence. Do not
add a second authority store, signature service, generic producer escape hatch,
second journal/store/projection, prepare/commit protocol, rotator, family
lease, policy owner, or speculative abstraction. Do not repair the broad-suite
missing modules. Do not reopen C36–C38, C01 overweight round-trip, C40
cache-mismatch expansion, RW4-03 keyed/recovery proof, RW4-04 race/crash proof,
RW4-06 evidence protocol, or C41 CLI redesign. Batch 2 remains prohibited.

Preserve every prior-MET behavior named in the sealed packet, especially one
`_IncidentEventJournal` and sequence-sidecar flock, one `_locked` NBF mutation
door, typed dispositions, keyed non-latest provider/recovery behavior,
canonical probe lease binding, composite replay/crash behavior, terminal race,
CLI statuses 0/2/3/4/5, and valid changed-precondition replay/consume-once
semantics.

## Serial task requirements

### RW5-01 — close changed-precondition authorization at every door

Criteria: C19–C21; preserve C22; RW4-01; A3-03. This is the first and blocking
task. Inspect `_authoritative_source`, `_produce_authoritative`, all
allowlisted reason-specific producers, `ChangedPrecondition.from_dict`,
`_validate_changed_precondition_wire`, `validate_nbf_event`,
`append_changed_precondition`, `_append_nbf`, `_append_nbf_locked`, projection,
`reserve`, and `consume_changed_precondition`.

The attempt-4 defect is concrete: a caller-shaped wire event can coherently
recompute after/before snapshots, content IDs, evidence digest, provider key,
and event ID, then pass `validate_nbf_event` and `_append_nbf`, project as
unconsumed authority, and authorize `reserve()`. Public producer handles are
already guarded; do not weaken that valid path.

Required outcome and acceptance:

- Every changed-precondition append authorization requires the matching
  reason-specific typed authoritative source handle/reader; self-consistent
  caller snapshots or recomputed hashes are never provenance.
- Producer identity, reason, subject, source version, cited persisted
  evidence, evidence digest, canonical before/after content, and provider-key
  derivation are bound and checked at decode, `validate_nbf_event`, canonical
  append/private append, and locked consume as applicable.
- Extend the existing coherent-forgery behavior test so it mutates the
  transition and recomputes every serializable hash/ID, then proves rejection
  at `from_dict`, `validate_nbf_event`, `_append_nbf`/locked append, projection,
  and `reserve()` authorization. A forged event must neither persist nor
  authorize a reservation.
- A legitimate reason-specific reader can still mint, append, project, and
  consume a valid event exactly once under the existing journal lock; matching
  replay remains supported and second consume is rejected.
- Keep the one journal/lock and existing producer/reducer design. No signing
  service, second authority, generic bypass, or speculative framework.

Use `apply_patch`; add the strongest obvious in-scope behavioral regression in
the existing named module. Do not proceed to RW5-02 until this hole is closed
and its targeted test fails on the pre-fix candidate and passes post-fix.

### RW5-02 — complete the six-kind payload and typed-identity matrix

Criteria: C02/C13; RW4-02; A3-02. After RW5-01, strengthen the existing named
tests and only the necessary owned validators at direct construction,
`from_dict`, `validate_nbf_event`, and real public locked append doors.

Required outcome and acceptance:

- Cover all six incompatible outcome/payload combinations through all four
  required doors, including public `append_terminal_outcome` and
  `append_disposition`, not only a private append or one worker-success case.
- Cover missing and fabricated typed worker, observed-death, and non-worker
  identities at each applicable door, with legal positive OOM, unknown-death,
  and non-worker cases retained.
- Preserve lossless `worker_disposition`, no-launch/unresolved distinctions,
  typed fields, and C03–C08/C12/C14 semantics. Do not reopen C01 or force an
  overweight `PhaseResult.from_dict` round-trip.
- Tests are behavioral and must fail against the unmodified attempt-4 tree
  for the named evidence hole.

This task follows RW5-01 and uses the same one-writer discipline over owned
schema/phase/ledger/test seams.

### RW5-03 — prove confirmation evidence-digest equality and omission

Criteria: C39; RW4-05; A3-07; rerun C41 only as regression. In the existing
`test_confirmation_compares_pid_start_progress_incarnation_cause` matrix,
add explicit wrong and omitted `second_evidence`/evidence-digest cases while
retaining every already-MET restart, replacement, expiration, reopen,
expiry-after-consume, and locked one-consumer race behavior.

Required outcome and acceptance:

- Every frozen confirmation identity/timing/evidence field remains required
  and compared, including PID, process-start identity, progress sequence,
  incarnation, cause, evidence digest, TTL/expiry, scan interval/separation,
  policy/version identity where required.
- Wrong and missing second evidence reject; matching evidence succeeds with
  the existing durable one-consumer semantics.
- C41 CLI 0/2/3/4/5 is rerun for regression only; do not redesign it.

This is last among behavioral fixes and must not alter RW5-01 or RW5-02
authority boundaries.

## Exact validation and evidence protocol

Use a fresh isolated evidence/transcript directory, for example
`/tmp/oracle-nbf01-rework5-luna/`. Do not reuse prior attempt directories.
For every command record exact argv, cwd, UTC start/end timestamps, exit code,
complete stdout and stderr (or immutable transcript paths), and full SHA-256
digests for stdout, stderr, and any structured transcript. No pass-count-only
claims.

At minimum execute and record these exact commands from the repository root:

1. RW5-01 targeted regression:

   ```text
   python -m pytest -q tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py
   ```

   Include the named coherent-forgery/reader test and an explicit wire,
   private-append, projection, and `reserve()` authorization probe transcript.

2. RW5-02 named payload/identity matrix:

   ```text
   python -m pytest -q tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py
   ```

3. RW5-03 confirmation matrix:

   ```text
   python -m pytest -q tests/arnold_pipelines/megaplan/test_supervision_confirmation.py
   ```

4. Frozen focused suite, all eight new modules plus unchanged legacy ledger
   coverage:

   ```text
   python -m pytest -q tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py tests/arnold_pipelines/megaplan/test_provider_route_projection.py tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_supervision_confirmation.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_incident_ledger.py
   ```

5. Required legacy incident/phase coverage, if separately invoked by the
   packet's existing command, must be recorded exactly; at minimum preserve
   the explicit legacy command above and report its result independently.

6. CLI status regression required by the packet (0/2/3/4/5, including expired
   and already-consumed confirmation/replay cases): run the packet's existing
   independent subprocess matrix against
   `python -m arnold_pipelines.megaplan.incident.disposition record`, recording
   each exact payload, ledger root, argv, status, stdout/stderr and transcript
   digest. The CLI must emit one JSON acknowledgement on stdout for status 0
   and diagnostics only on stderr for failures; do not signal from the CLI.

7. Compile and whitespace checks:

   ```text
   python -m py_compile arnold_pipelines/megaplan/incident/__init__.py arnold_pipelines/megaplan/incident/ledger.py arnold_pipelines/megaplan/incident/schema.py arnold_pipelines/megaplan/incident/disposition.py arnold_pipelines/megaplan/orchestration/phase_result.py arnold_pipelines/megaplan/orchestration/phase_result_classify.py
   git diff --check
   ```

8. Required broad sweep exactly once, because the sealed packet requires full
   sweep evidence:

   ```text
   python -m pytest -q tests/arnold_pipelines/megaplan
   ```

   Preserve its complete collection output and classify absent
   `arnold.agent.costing.model_resource_capabilities` and
   `tools.environments.singularity` imports as
   `PRE_EXISTING_OUT_OF_SCOPE_BLOCKER` only if independently confirmed absent
   at candidate and source. Do not repair them or silently rerun the broad
   sweep.

After tests, capture final candidate identity and owned production diff using
the five tracked production paths plus `incident/disposition.py`; record the
exact command, output, exit, and digest. Inventory every modified tracked file
and every new owned production/test file with both `git hash-object` and full
SHA-256. Include the unchanged legacy ledger hash/blob identity and prove no
later-batch path entered the diff.

## Required executor finding and receipt

`.oracle/findings/execution-nbf01-rework5-luna.md` must be an evidence-backed
executor finding, not a verdict. It must state the serial task outcomes,
source/base/branch/HEAD identities, packet and triage-receipt hashes, frozen
tasklist/North Star hashes, exact changed paths, preserved prior-MET behavior,
production diff digest, all test commands/results, and broad-sweep relevance.

`.oracle/receipts/execution-nbf01-rework5-luna.md` must contain the full
invocation metadata and transcript manifest: model `codex:gpt-5.6-luna`, high
reasoning, timestamps, cwd, exact commands/exit statuses, complete stream or
transcript paths and SHA-256s, candidate and artifact identities, per-file
`git hash-object` plus SHA-256 inventory, and final production diff SHA-256.
Report failures honestly; a passing focused suite does not waive a missing
authorization boundary or incomplete matrix.

Do not place an Oracle token in either executor artifact. Do not call the work
accepted or start the later independent review. Return the evidence paths and
measured identities to the pipeline only after all three serial tasks and
required validation are complete.

## North Star — Arnold self-healing supervision (verbatim)

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

## Megado delegation mandate (verbatim)

> DELEGATION MANDATE — You are a manager and validator of the normal execution pool, NOT a worker. Delegate as much as possible to the task's selected normal model: DeepSeek V4 Flash or GPT-5.6 Luna. Flash invocation: `omp -p @<brief>.md --model deepseek-v4-flash --cwd <worktree> --no-session --auto-approve --max-time=1800`; Luna invocation: `launch_hermes_agent.py --model="codex:gpt-5.6-luna" --query-file=<brief> --project-dir=<worktree>` (research-only briefs use read/search tools). Dispatch research, execution, and critique briefs to the selected model — critique passes optimize for elegance: KISS, YAGNI, cut scope that isn't pulling its weight; flag overengineering, not just bugs. Your job is to direct, then validate: read delegated output against the acceptance criteria; do work yourself only when delegation is impossible — the selected normal model already failed at it, or the piece is too small / too tightly coupled to your own reasoning to hand off. If you catch yourself implementing or researching directly, stop and ask whether a normal-pool brief would cover it. It almost always would.
