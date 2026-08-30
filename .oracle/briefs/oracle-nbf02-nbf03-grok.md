# Grok 4.6 Oracle gate brief — NBF-02 → NBF-03 / Batch 2

## Role, policy, and non-negotiable boundary

You are Grok 4.6, the Oracle for the Batch-2 gate and the manager-validator of
the normal execution pool. The user policy selects Grok 4.6 for Oracle judgment
and GPT-5.6 Luna for the one normal independent review. This is a gate, not an
implementation task. You must commission exactly ONE fresh, independent
GPT-5.6 Luna reviewer at high reasoning and then independently inspect,
probe, and synthesize the result. Do not commission a second reviewer, fan out,
switch Oracle providers, or treat any prior Sol/fallback/nested run as review
evidence.

The only required repository outputs are exactly:

1. `.oracle/checkins/batch-2-luna.md`
2. `.oracle/receipts/oracle-nbf02-nbf03-luna.md`
3. `.oracle/checkins/batch-2-grok.md`
4. `.oracle/receipts/oracle-nbf02-nbf03-grok.md`

The final Oracle token is exactly one of `PASS_BATCH_2` or
`ACCEPTED_ISSUES`. Do not implement fixes, edit source or tests, alter prior
history/evidence, mutate `.oracle/tasklist.md`, `.oracle/northstar.md`,
`.oracle/plan.md`, `.oracle/agent_goal.md`, `.oracle/custody.md`, or
`.oracle/status.md`, commit, stage, push, merge, rebase, reset, clean, or start
Batch 3. Do not write any other repository artifact. If provider spending or
availability prevents completion, record that fact and the exact failure in
the receipt; do not silently switch the Oracle or manufacture a verdict.

## Candidate and immutable bindings

Work only in `/Users/peteromalley/Documents/Arnold-oracle-nbf` on branch
`megado-nbf-guard-0826`. Re-check the live candidate before judging:

- Candidate HEAD: `19deab5bb407273e7e82d40a66fc06d17af93ad4`
- Source/base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Frozen `.oracle/tasklist.md` SHA-256:
  `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- Canonical `.oracle/northstar.md` SHA-256:
  `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Frozen `.oracle/plan.md` SHA-256:
  `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- Frozen `.oracle/agent_goal.md` SHA-256:
  `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`
- Frozen `.oracle/custody.md` SHA-256:
  `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`

Batch-1 is already PASS at checkpoint
`878a9b2980f0eab6642ed51c30e687903a7213b9`, recorded by commit
`19deab5bb407273e7e82d40a66fc06d17af93ad4`. Bind the append-only Batch-1
correction receipt `.oracle/receipts/oracle-nbf01-rework6-grok-wrapper-exit-correction.md`
at SHA-256
`43c1d6b250136d1449575c811d39976a9da177030d4d50cde2e88e0bf02c50f5`.
The final Batch-1 gate artifacts remain immutable:

- `.oracle/checkins/batch-1-rework6-luna.md`:
  `de278150f2245ce7330694470f5b474788aaf1e234c712a5099dfbda2aeef850`
- `.oracle/receipts/oracle-nbf01-rework6-luna.md`:
  `ce5136fde4af45a8d64f372b733ae1868c4b718258177bff88e6f262527ca4ba`
- `.oracle/checkins/batch-1-rework6-grok.md`:
  `1a3cac2973d67ea270bd324ee742fcd074a696bff49ab55cd7e20b9aaa8d6b79`
- `.oracle/receipts/oracle-nbf01-rework6-grok.md`:
  `5ede0d4cf30e0cef5c1dfbdf6fab7aed36269e818b1122bac3def59928e0832a`
- Batch-1 production diff:
  `ab2b9cb2743a2cc9d73e0f5cbffb650a313da60833500217dd7db5aa13e2bd2e`

## Batch-2 executor evidence and known defects

Read and independently hash every artifact below before judging. Bind the
first execution as historical only: its brief lowered the North Star heading
from `#` to `##`, and its finding carried an abbreviated/incorrect historical
binding `77831c...`; neither defect can be silently repaired by rewriting it.

- v1 brief `.oracle/briefs/execution-nbf02-nbf03-luna.md`:
  `938f61b1ccaa06ea9cd7e428b184d02143f9e87accf96eeb95ec8b0e70797003`
- v1 finding `.oracle/findings/execution-nbf02-nbf03-luna.md`:
  `9c8e6b7db2a104056c9843ffad59b04234e2dc904a8898858d049fdaf0ed1ff0`
- v1 receipt `.oracle/receipts/execution-nbf02-nbf03-luna.md`:
  `b957f16fab1aa5502440434b1c51931b584b2321fc7be1c88af0ce7797367b07`
- corrected v2 brief `.oracle/briefs/execution-nbf02-nbf03-luna-v2.md`:
  `f6daf95f6b7ff91c0840170a98e3d8263e56faf28c64a4d3acd0535cdb1f2e6e`
  (it still used an abbreviated production-diff binding and omitted explicit
  `:high`.)
- v2 timeout receipt `.oracle/receipts/execution-nbf02-nbf03-luna-v2-timeout.md`:
  `e8c4f572ed34bda80fdebf9307c856bb336037de54ef32e26b33ec202a5c66e4`
  (the wrapper had no explicit `:high`, effective timeout 1800 seconds, exit
  124, and produced no v2 finding or receipt.)
- v3 brief `.oracle/briefs/execution-nbf02-nbf03-luna-v3.md`:
  `06894b3b35cbd3f47253251ee1e72363c4b96419c2d999bf81c5e2cc97c11156`
- sealed v3 finding `.oracle/findings/execution-nbf02-nbf03-luna-v3.md`:
  `c0424a580d08648cdba04d5cf689783bc06179295b62387d7aabaa8830c60ca9`
- sealed v3 receipt `.oracle/receipts/execution-nbf02-nbf03-luna-v3.md`:
  `6e5e536e4d2badb64783b6a5c25ead3d80d2bc899f454f754194610402bd52bb`
- v3 incident receipt
  `.oracle/receipts/batch-2-premature-gate-and-v3-nested-launch.md`:
  `b9f52bd8c7368f9604140d6021c30a72673992eee0e802bd8430f55b94122b4d`
- v2 timeout-audit diff:
  `e945526a223f4c03f866d892d4ab5be70c189d7fbcfb9c70552f06bf68b3f6fd`
- canonical current production-plus-focused-test diff including the untracked
  candidate paths:
  `5586c1861dce44334c3991e997bdc8b90b82d25d2ed8f28bb558b42aae499fd0`

The sealed v3 evidence reports the exact NBF-02 result `242 passed`, the exact
NBF-03 result `41 passed, 4 failed`, authority checker exit 0, raw-symbol scan
exit 0, compile exit 0, and diff-check exit 0. The four NBF-03 failures were
reproduced on an isolated clean-HEAD source copy as `12 passed, 4 failed`
(baseline stdout SHA-256
`f95a7400938f47c4a8e82b2636fc6f345ba7548a8ecd4bb7f9ec0f677b29f12c`), with
the relevant source and tests byte-identical to HEAD. Judge this evidence
against the frozen must criteria, not by casually waiving the failures.

The v3 launcher record proves a top-level explicit
`codex:gpt-5.6-luna:high` / `--thinking high` process with `--timeout=3600`,
but has no complete top-level launcher stream or exit marker. The nested
same-model launch under the v3 evidence root is prohibited and quarantined;
it ended exit 143 and is not executor or review evidence. The v3 incident
receipt above is the authoritative record of that distinction.

All Sol fallback material is invalid, premature, quarantined context only and
must not be cited as an Oracle or independent review:

- `.oracle/briefs/oracle-nbf02-nbf03-sol-fallback.md`:
  `78c94205ea63904683c36291fd7eb2ec973a3a13c7151d045a8c3b21d7d7e6f1`
- `.oracle/briefs/oracle-nbf02-nbf03-sol-fallback-v2.md`:
  `d4db9d5581c4b9a1c0401b42f6f26e8236d365c0339c759158399d3befb73b1e`
- `.oracle/briefs/oracle-nbf02-nbf03-sol-fallback-v3.md`:
  `ab74a91a7a37007d69db7b5cac280f02311e65c079c83639c38d6b81aae04f7f`
- `.oracle/briefs/oracle-nbf02-nbf03-luna-review-final.md`:
  `06c3926da1eda73eb07288f0264d167bd7f8640761c5d8cd14b5605b61027d64`

The premature Sol gate and nested v3 launch are historical incident evidence,
not gates. Do not retry them or use them to satisfy the exactly-one-review
requirement. Mark the temporary artifacts
`/private/tmp/oracle-nbf02-nbf03-luna-review-0830/`,
`/tmp/oracle-nbf02-nbf03-luna-review-v2.md`, and
`/tmp/oracle-nbf02-nbf03-sol-fallback-v2-luna.meta.json` (absent, not evidence)
as quarantined/invalid context as described by the incident receipt; the v3
`/private/tmp/oracle-nbf02-nbf03-luna-v3-0830/launcher/` transcript is likewise
the prohibited nested launch and cannot count as a review or executor result.

## Exactly one independent Luna review

Create a temporary, non-repository review query from this gate's criteria and
commission exactly this one process, with an explicit high selector and at
least a 3600-second timeout:

```text
PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model="codex:gpt-5.6-luna:high" --query-file=/tmp/oracle-nbf02-nbf03-batch2-luna-review.md --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf --timeout=3600
```

The temporary query must direct Luna to read the frozen tasklist, North Star,
all bound executor evidence, current source/tests, and every criterion below;
it must write only `.oracle/checkins/batch-2-luna.md` and
`.oracle/receipts/oracle-nbf02-nbf03-luna.md`, label itself independent review
evidence, report exact commands/models/timestamps/PIDs/exit statuses and
stream/transcript SHA-256 digests, and never edit implementation, tests,
frozen artifacts, status, history, or commit. Verify the resolved process says
GPT-5.6 Luna with thinking high. Do not launch any second model/reviewer or
fanout, including Sol, scouts, nested harnesses, or fallback reviewers.

## Required independent gate inspection

Read the full frozen Batch-2 tasklist lines 213–450 and inspect the actual
current dirty source and tests. Rehash and inspect all 26 owned candidate paths
listed in the sealed v3 finding/receipt; do not rely on a source-only claim.
Use sealed evidence plus proportionate targeted probes. Do not rerun expensive
exact suites unnecessarily when the sealed exact transcripts suffice, but any
rerun must record literal argv, cwd, UTC start/end, exit, complete stdout and
stderr, and SHA-256 stream/transcript digests. Establish separately:

- NBF-02 exact frozen command: 242-pass evidence and all admission, T7,
  controlled launch, terminal, reconciliation, and provider semantics.
- NBF-03 exact frozen command: 41-pass/4-failure result and the isolated
  clean-HEAD 12-pass/4-failure reproduction; verify the four failures are
  unchanged baseline behavior rather than casually waiving a new regression.
- `python scripts/check_worker_admission_authority.py --check`, the frozen
  raw-symbol scan, changed-file compile, and `git diff --check` evidence.
- Restored tests and additions-only restoration proof; no accidental deletion
  or unrelated production/test scope.

Inspect every checkpoint criterion, including all 26 paths and the following
high-risk seams:

1. One canonical admission authority: source/runtime/manifest/seed/interpreter,
   timeout, memory, exact live OMP membership, native positive backend proof,
   static ox-alpha acceptance plus live typed rejection, semantic fingerprint
   reservation, and no liveness-only bypass. Confirm admission has one owner,
   receipts/refusals bind complete evidence, and direct/wire/native/OMP paths
   do not reintroduce duplicate preflights.
2. T7 cooldown retry-wait: injectable timing, zero WBC/client/process launch,
   failure, breaker, or block effects; typed transport and truthful
   no-launch/unresolved reconciliation.
3. Controlled lifecycle: `not_started` → `entered` → `accepted` → closure,
   one final launch per logical ID, append-before-consume terminal handling,
   worker-disposition preservation, authorized linked-child identity, and
   reconciliation/at-most-once behavior.
4. Every physical door: native non-OMP, direct OMP, nested OMP, babysitter,
   chain, and no-WBC paths each have exactly one admission owner; nested OMP
   has one hit; WBC starts only after admission; no raw preflight or legacy
   bypass. Check the admission single-authority checker and raw-symbol scan.
5. All six payload kinds and all four doors: construction, direct/wire decode,
   validation, public terminal append, and public disposition append; exact
   cardinality and rejection reasons/categories; typed worker/observed-death/
   non-worker identity handling; no incidental missing-field failure.
6. Native/OMP provider behavior, ox-alpha live rejection, model catalog/prefix/
   family/live-membership resolution, keyed provider streak, confirmation
   semantics, evidence-digest equality/omission/mismatch, and all prior
   Batch-1 contracts.
7. Death and failure ledger semantics: killer identity, signal, elapsed time,
   typed terminal disposition, post-append crash/contention safety, no silent
   death, and no replay of an identical failure fingerprint without a changed
   precondition.
8. All frozen CLI statuses (0/2/3/4/5), raw/static checker constraints, no
   T8 policy, no second scheduler/journal/authority/family lease, and KISS /
   YAGNI. Reject overengineering and any criterion waived without evidence.

For reproducibility, the frozen focused commands are these exact argv/path
sequences (run only when sealed evidence is insufficient or a targeted probe
needs confirmation):

```text
pytest -q \
  tests/cloud/test_runtime_attestation.py \
  tests/cloud/test_worker_dispatch_admission.py \
  tests/cloud/test_dispatch_with_admission.py \
  tests/cloud/test_chain_admission.py \
  tests/cloud/test_worker_dispatch_context.py \
  tests/cloud/test_dispatch_reconciliation.py \
  tests/cloud/test_controlled_final_launch.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py \
  tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py \
  tests/arnold_pipelines/megaplan/test_memory_headroom.py \
  tests/arnold_pipelines/megaplan/test_worker_memory_gate.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_phase_result_classify.py \
  tests/arnold_pipelines/megaplan/test_plan_circuit.py \
  tests/workers/test_omp_adapter.py
```

```text
pytest -q \
  tests/cloud/test_worker_dispatch_spy.py \
  tests/cloud/test_worker_admission_authority.py \
  tests/cloud/test_chain_admission.py \
  tests/cloud/test_babysitter_routing.py \
  tests/cloud/test_babysitter_goal.py \
  tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py
```

```text
python scripts/check_worker_admission_authority.py --check
```

```text
if rg -n \
  'refresh_runtime_launch_seed_for_worker_dispatch|require_configured_runtime_launch' \
  arnold_pipelines/megaplan/workers/_impl.py \
  arnold_pipelines/megaplan/workers/omp.py \
  arnold_pipelines/megaplan/cloud/babysitter/launch.py
then
  exit 1
fi
```

The isolated baseline is evidence about the four known babysitter failures,
not permission to ignore other NBF-03 requirements. Preserve a truthful
`PRE_EXISTING_OUT_OF_SCOPE_BLOCKER` classification only where source identity
and reproduction prove it; never relabel candidate failures as baseline.

## Delegation mandate (verbatim)

```text
DELEGATION MANDATE — You are a manager and validator of the normal execution pool, NOT a worker. Delegate as much as possible to the task's selected normal model: DeepSeek V4 Flash or GPT-5.6 Luna. Flash invocation: `omp -p @<brief>.md --model deepseek-v4-flash --cwd <worktree> --no-session --auto-approve --max-time=1800`; Luna invocation: `launch_hermes_agent.py --model="codex:gpt-5.6-luna" --query-file=<brief> --project-dir=<worktree>` (research-only briefs use read/search tools). Dispatch research, execution, and critique briefs to the selected model — critique passes optimize for elegance: KISS, YAGNI, cut scope that isn't pulling its weight; flag overengineering, not just bugs. Your job is to direct, then validate: read delegated output against the acceptance criteria; do work yourself only when delegation is impossible — the selected normal model already failed at it, or the piece is too small / too tightly coupled to your own reasoning to hand off. If you catch yourself implementing or researching directly, stop and ask whether a normal-pool brief would cover it. It almost always would.
```

## Required output evidence and verdict discipline

The Luna check-in/receipt and Grok check-in/receipt must bind the exact
candidate HEAD, source/base, tasklist/North Star/plan/goal/custody hashes, all
executor and incident artifacts, the final production diff, every owned path,
and the review query/launcher identity. Include actual commands, model
selectors, cwd, timestamps, PIDs, exits, complete stdout/stderr and transcript
digests; do not infer an exit status from process absence. The Grok receipt must
state that exactly one Luna review was commissioned and that no Sol fallback,
nested launch, second reviewer, or implementation occurred.

Grok must independently compare each frozen must criterion with evidence,
record PASS/FAIL/UNDETERMINED and the reason, assess North Star alignment and
KISS/YAGNI, and identify the smallest bounded rework for every unmet criterion.
Use `PASS_BATCH_2` only when every must criterion is genuinely evidenced and
the four baseline failures are correctly isolated. Otherwise return
`ACCEPTED_ISSUES`, with narrowly scoped issue IDs, evidence, dependencies,
acceptance commands, and Normal/Luna versus exceptional classification. Do not
convert missing transcripts, provider failures, baseline reproduction, or
quarantined Sol artifacts into a pass.

## North Star — canonical byte-for-byte block

```text
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
```

The block above must be extracted and compared byte-for-byte with the live
`.oracle/northstar.md`; the extracted SHA-256 must be exactly
`d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`. If it
does not match, stop and report the mismatch; do not alter the canonical file.
