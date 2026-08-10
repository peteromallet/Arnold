# Sol adversarial direction review — VJ24 recovery

Date: 2026-08-05
Reviewer: GPT-5.6 Sol, high reasoning, read-only
Question: validate the proposed occurrence-bound migration sprint, challenge
whether it is necessary to use a cloud sprint, and identify the shortest safe
route to recovery.

## Evidence supplied to Sol

- `.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805.md`
- `.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805-sol-stage1.md`
- `.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805-sol-stage2.md`
- `.megaplan/incident-ledger/evidence/luna/critique-v3-r5-vj24-20260805/README.md`
- `.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805-host-preflight.md`
- `.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805-follow-up-crosswalk.md`
- `.megaplan/initiatives/critique-ledger-vj24-migration-20260805/`
- `.megaplan/initiatives/critique-ledger-post-relaunch-completion/`
- `arnold_pipelines/megaplan/handlers/finalize.py`
- `arnold_pipelines/megaplan/custody/action_validator.py`
- `arnold_pipelines/run_authority/current_source.py`
- `arnold/workflow/attempt_ledger_store.py`

## Verdict

The root diagnosis and the fresh-child recovery model are sound. The original
VJ24 occurrence must remain immutable and quarantined; a generic resume or a
second `--fresh` launch would not establish causal custody.

The VJ24 stop is deterministic pre-dispatch evidence: T18/T23 were still
pending, batch 15 accepted nothing, VJ19 deferred, and no VJ24 result existed.
The remaining uncertainty is substantive and must be resolved from pinned
evidence, not guessed: legitimate prospective selector output versus stale
plan data versus a plan/runtime/revision split.

## Local versus cloud challenge

The cloud sprint is optional ceremony, not a safety invariant. The selector
patch is on the clean, pushed branch `fix/vj24-selector-contract-20260805`, so
implementation can be completed faster in a dedicated local worktree and then
promoted as an exact, content-addressed runtime. Cloud is still appropriate for
the long-lived execution and final host-side verification; it is not required
to author the migration primitive.

However, “do it locally” does not mean “resume locally.” The safety boundary is
the installed owner APIs and their authoritative rereads. The current evidence
shows the M7 action validator is shadow-only by default, and the Run Authority
cross-owner rereads are still placeholder/syntactic checks. If the deployed
generation has no real Run Authority writer/store, local code plus a cloud
launch would both be unsafe. The venue is secondary to making the owner
boundary real and enforcing it.

## Scope correction applied

The active cloud sprint is narrowed through an in-flight `override add-note` to
the local-equivalent implementation of:

1. one versioned, content-addressed `selector_task_output_contract.v1` digest
   consumed identically by Finalize, VJ19, VJ24, and Execute;
2. a typed `occurrence_child_migration.v1` prepare/commit API;
3. real Run Authority, Custody, and WBC owner adapters (no synthesized owner
   records and no migration-only authority store);
4. deterministic idempotency, CAS, conflict, partial-write, and restart tests;
5. effect-free preparation and independent owner rereads immediately before
   dispatch.

Observer display assertions and notification replay are deferred to F1/F2.
The sprint must not touch r5, manufacture receipts, or launch a child.

The cloud critique artifacts are preserved in the paused migration workspace at
`/workspace/critique-ledger-vj24-migration-20260805-269cbeef/arnold/.megaplan/plans/occurrence-bound-vj24-20260805-1134/`
(`plan_v1.md`, `evaluator_verdict.json`, and
`critique_evaluator_raw_v1.txt`). That audit did not implement code. It found
the generated plan was not execution-ready: its observer-projection step was
out of scope, allocator and override-wiring steps were too broad, and cursor
semantics/real store-level CAS enforcement needed resolution first.

One concrete enforcement gap was verified in the pinned cloud source before it
was stopped: `arnold_pipelines/megaplan/authority/binding.py:107-112` calls
`CASExpectation.assert_matches` with
`cursor=self.cas_expectation.expected_cursor`. That compares the expectation
to itself; it does not prove the cursor read from the authoritative store is
current. `execute/merge.py` has a separate path that supplies an observed
cursor, but the binding constructor cannot be treated as the CAS gate. Any
migration implementation must make the store-level compare explicit and test
stale, replayed, and divergent cursors.

## Mandatory pre-child invariants

Before any child launch, an authoritative receipt must bind the immutable parent
occurrence/fingerprint, accepted state version/cursor, plan/chain/source/runtime
and validator identities, retained evidence digests, operator decision,
deterministic migration key, fresh child Run Authority grant/fence/attempt,
fresh Custody occurrence/lease/epoch, WBC attempt and stable global logical
effect reservation, selector-contract digest, CAS result, and an independent
owner reread. It must explicitly state `same_occurrence_resume=false` and
`provider_effect_started=false`. A receipt is evidence, not bearer authority;
the final conjunctive owner reread grants dispatch authority.

## Shortest safe route

1. Complete the shared selector contract and typed migration API in the clean
   dedicated worktree; run focused and regression tests; review and push.
2. Promote that exact commit as a content-addressed runtime and verify import
   roots/interpreter on the host.
3. Capture one coherent authoritative parent snapshot. If occurrence,
   quarantine, or owner identity cannot be proven, remain `INDETERMINATE`.
4. Submit one operator-authorized, deterministic migration request; prepare
   effect-free, then commit through the actual Run Authority/Custody/WBC APIs.
5. Retry partial commits idempotently, independently reread all owners, and
   emit `occurrence_child_migration.v1`.
6. Immediately before dispatch, reread the receipt/current owners and provider
   preflight, then launch one fresh Critique child through the ordinary chain.
7. Only after the child produces accepted VJ24/T18/T23 envelopes and advances
   the cursor should the post-relaunch T6.2 handoff and follow-up epic unlock.

## Important semantic correction

Accepted VJ24/T18/T23 result envelopes are **post-launch outputs** of the child;
they cannot be prerequisites for launching the child that must produce them.
The prelaunch migration receipt proves admission and custody only. The T6.2
handoff may require both that receipt and the later accepted result envelopes.

## Unknowns that remain hard gates

- no supplied proof yet of a real authoritative Run Authority allocation/append
  API in the deployed generation;
- no exact pinned VJ24 reader/map plus remote plan/validator hashes;
- no authoritative parent quarantine receipt for this occurrence; and
- no accepted CI/test receipt yet for the selector-contract commit. A local
  clean-worktree smoke run now passes 43 focused/regression tests
  (`test_finalize_selector_contract.py` plus `test_m8a_execute_wiring.py`),
  but that is not a substitute for host-installed-generation verification.

Until these are observed from the owner stores and host, the correct state is
gated/indeterminate rather than “probably safe.”
