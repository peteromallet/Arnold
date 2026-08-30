# Grok 4.6 Oracle brief — NBF-01 Batch 1 rework attempt 3 gate

## Mission and terminal contract

You are Grok 4.6, the independent Oracle and manager/validator for the NBF-01
Batch 1 attempt-3 hard gate. GPT-5.6 Luna executed the supplemental packet.
Validate the exact current candidate against every frozen NBF-01 criterion and
every RW3 requirement, commission exactly one fresh independent GPT-5.6 Luna
full review, then synthesize the final decision yourself.

Write the required review and Oracle artifacts specified below, and return only
one terminal token:

```text
PASS_BATCH_1
```

or

```text
ACCEPTED_ISSUES
```

`PASS_BATCH_1` is available only if every frozen must criterion, every RW3
acceptance criterion, the evidence protocol, and preservation/scope gates are
MET. Green counts, executor claims, or an out-of-scope test-environment failure
cannot substitute for behavioral proof. If anything material is NOT_MET or
UNEVIDENCED, return `ACCEPTED_ISSUES` with the complete issue list and smallest
next action in the Grok check-in before emitting the terminal token.

## Immutable candidate and evidence bindings

- Repository: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Candidate branch: `megado-nbf-guard-0826`
- Candidate HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Source and merge-base:
  `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Frozen tasklist: `.oracle/tasklist.md`
- Frozen tasklist SHA-256:
  `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- North Star SHA-256:
  `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Attempt-3 packet `.oracle/rework/batch-1-attempt-3.md` SHA-256:
  `c4c93f8b14e253060c0a403869e22a23aadc6444e63b32f48fd55cf95b63e779`
- Attempt-3 triage receipt
  `.oracle/receipts/rework-triage-batch-1-attempt-3-grok.md` SHA-256:
  `2d025f9614d5dcf3f4e00de881962f1152a8be222b7cb4868055cf5a47856f4b`
- Attempt-3 executor finding
  `.oracle/findings/execution-nbf01-rework3-luna.md` SHA-256:
  `4897b2c7484aa7cc221488f7535339b716f780f3e70d62a202096504ac254e9f`
- Attempt-3 executor receipt
  `.oracle/receipts/execution-nbf01-rework3-luna.md` SHA-256:
  `e34f901febedc434e27d778c3be5e070a6ded93a961a26dc1c4c62577339351f`
- Final tracked-production diff SHA-256:
  `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`
- New production CLI `incident/disposition.py` SHA-256:
  `2a59e440d7bcae53700b7ea63fdd2d15b1b1705eeb6914d24ea4f37300ab505a`
- New production CLI git blob:
  `291c66ed2ac9b984e2c3d1f763bafcf7b86ca1c1`

The final tracked-production digest was independently reproduced before this
brief with exactly:

```text
git diff origin/main -- arnold_pipelines/megaplan/incident/__init__.py arnold_pipelines/megaplan/incident/ledger.py arnold_pipelines/megaplan/incident/schema.py arnold_pipelines/megaplan/orchestration/phase_result.py arnold_pipelines/megaplan/orchestration/phase_result_classify.py | shasum -a 256
```

Before dispatching the review, independently re-hash every bound artifact,
resolve HEAD/branch/merge-base, reproduce the production digest, hash all owned
untracked production/test files, and record the complete changed-file inventory.
If source or tests differ from the executor-bound candidate, do not silently
review a moving tree: return `ACCEPTED_ISSUES` and require fresh executor
evidence for the exact tree.

## Required reading

Read completely before dispatch or decision:

- `.oracle/northstar.md`, `.oracle/agent_goal.md`, `.oracle/custody.md`;
- frozen `.oracle/tasklist.md`, settled `.oracle/plan.md`, and
  `.oracle/receipts/tasklist-freeze-v8.md`;
- `.oracle/rework/batch-1-attempt-1.md`,
  `.oracle/rework/batch-1-attempt-2.md`, and
  `.oracle/rework/batch-1-attempt-3.md`;
- all three Grok triage receipts;
- original, attempt-1, and attempt-2 Luna/Grok Batch 1 check-ins and receipts;
- attempt-3 Luna executor finding and receipt bound above;
- `.oracle/receipts/model-policy-grok-switch.md` and prior gate contract
  `.oracle/briefs/oracle-nbf01-rework2-grok.md`.

Inspect the current source and tests directly. Do not inherit an executor or
prior reviewer conclusion. Historical 52→61, unreproducible `4aee815d…`, failed
handoff `50c86490…`, attempt-1 78/78 and `e060f650…`, and attempt-2 production
digest `16f6f854…` remain historical observations, not targets or waivers.
RW-CUSTODY is already MET and must not be edited.

## Model policy and exact-one-review rule

Grok 4.6 is the Oracle. GPT-5.6 Luna owns Normal work and the independent review.
`[XHARD]` is none for this deterministic gate. Commission exactly ONE fresh
GPT-5.6 Luna full review. No fan-out, second opinion, helper review, Grok
self-review masquerading as the required independent pass, or reuse of the
attempt-2 Luna review is allowed.

Create a narrowly scoped review brief at:

`.oracle/briefs/oracle-nbf01-rework3-luna-review.md`

It must embed this full North Star, all immutable identities, the full frozen
C01–C41 and CP01–CP11 evaluation requirement, RW3-01 through RW3-06 plus
RW3-GATE, all A3-01 through A3-09 acceptance requirements, the preservation
list, the broad-suite relevance protocol, and the read-only boundary.

Launch the single fresh review as GPT-5.6 Luna. Require it to use a new isolated
transcript root:

`/tmp/oracle-nbf01-rework3-luna/`

No command transcript, probe, ledger root, or conclusion from attempt 1 or 2
may be reused as current evidence. Each transcript must bind exact argv, cwd,
exit status, complete stdout and stderr, and full SHA-256 of each byte stream.
Temporary probes and ledgers must live under that isolated root or a fresh
temporary child path, never in the repository.

The single Luna review must write exactly:

- `.oracle/checkins/batch-1-rework3-luna.md`
- `.oracle/receipts/oracle-nbf01-rework3-luna.md`

The review is read-only except for those two artifacts and its isolated `/tmp`
evidence. It must not edit production/tests, repair failures, stage, commit,
push, merge, mutate frozen artifacts, or start Batch 2.

## Independent Luna review contract

The Luna review must classify every frozen NBF-01 criterion C01–C41 and every
Batch 1 checkpoint CP01–CP11 as `MET`, `NOT_MET`, or `UNEVIDENCED`, with exact
source symbols, behavioral test/probe evidence, and transcript hashes. It must
also separately classify:

- RW3-01 foundations: persisted receipt-bound accepted-launch marker; complete
  payload/identity/OOM/unknown-death append matrix; authoritative reason-specific
  changed-precondition producers and coherent-forgery rejection;
- RW3-02 keyed provider projection and evidence/probe-bound single-use recovery;
- RW3-03 real composite fresh replay, injected composite failure, both-or-neither
  restart projection, and distinct-ID/conflicting-kind two-process terminal race;
- RW3-04 durable confirmation identity/TTL/replacement/restart/single-consumer
  semantics and direct non-signalling CLI 0/2/3/4/5;
- RW3-05 removal or frozen-caller justification and typed constraint for
  `reserve_provider_route_child_with_receipt`;
- RW3-06 exact stable-candidate evidence completeness;
- A3-01 through A3-09 individually, even where packed into one RW3 task;
- preserved prior-MET behavior, North Star alignment, KISS/YAGNI, scope, custody,
  and historical-evidence integrity.

The review must inspect implementations and test bodies for ceremonial coverage.
A test name or pass count is insufficient. It must independently probe the
specific attempt-2 failures against the current candidate, including:

1. a fully populated terminal without persisted accepted marker and each
   reservation/marker context mismatch;
2. every six-kind incompatible payload family at constructor, decode,
   validation, and append; typed worker identity; false/zero/negative OOM;
   legal positive OOM; fabricated killer/signal unknown death; legal unknown;
3. a coherent changed-precondition forgery with all hashes recomputed and a
   valid authoritative producer/consume single-use path;
4. success/ordinary/disposition targeting a non-latest provider stream across
   fresh replay, with cross-key isolation and no degradation for breaks;
5. absent/failed/mismatched/replayed/consumed probe/recovery authorization and
   valid one-composite same-route child reservation preserving streak;
6. fresh-ledger byte-identical composite receipt replay, injected failure at
   the real `_emit_locked` / receipt boundary, and distinct terminal IDs/kinds
   racing from separate OS processes;
7. every confirmation identity omission/mismatch, TTL/separation/replacement/
   restart/consume/expire edge, including expiry-after-consume rejection;
8. independent direct CLI subprocess cases for 0, malformed/schema 2, append/
   lock 3, invalid ledger 4, and missing/expired/distinct-already-consumed 5;
9. absence or justified typed constraint of the unofficial route-child alias;
10. replay failure on invalid schema/projection/cache mismatch and preservation
    of the one-journal/one-lock door.

At minimum rerun freshly and transcript the exact frozen focused suite, the
exact legacy suite, the transaction/provider/confirmation adversarial subsets,
all direct CLI subprocesses, `python -m py_compile`, `git diff --check`, and the
full megaplan test-directory sweep. Record observed counts, but never treat
counts as acceptance targets.

## Broad-suite missing-module relevance protocol

The executor's `pytest -q tests/arnold_pipelines/megaplan` collection stopped on:

- `ModuleNotFoundError: arnold.agent.costing.model_resource_capabilities`
  from `test_cli_check_validator.py`; and
- `ModuleNotFoundError: tools.environments.singularity`
  from `test_key_pool_codex.py`.

The Luna reviewer must freshly reproduce the sweep, inspect both import chains,
compare the missing modules/import sites against `origin/main`, and check whether
any owned attempt-3 source/test change introduced, removed, or made either import
reachable. Classify each blocker with evidence as exactly one of:

- `IN_SCOPE_REGRESSION` — caused by or coupled to the NBF candidate; fatal;
- `PRE_EXISTING_OUT_OF_SCOPE_BLOCKER` — reproducible on the source-base tree or
  demonstrably outside owned NBF seams; not itself fatal to frozen NBF-01, but
  recorded as reduced broad-suite coverage and never used to waive an in-scope
  criterion; or
- `UNEVIDENCED_RELEVANCE` — relevance cannot be established; the evidence gate
  remains incomplete and the recommendation is `ACCEPTED_ISSUES`.

Grok must independently verify Luna's classification. The collection blocker
is not automatically waived and not automatically fatal. Its consequence comes
only from demonstrated relevance to the frozen NBF-01 diff and criteria. Even a
proved pre-existing/out-of-scope blocker does not excuse any missing focused,
legacy, adversarial, or direct-probe evidence.

## Frozen scope and preservation gates

Preserve the single `_IncidentEventJournal`, sequence-sidecar flock, and one
`_locked` NBF mutation door. Confirm C03–C06, C08, C12, C15–C18, C22, C25, C26
shape, C29 order, C30/C31 matching stream behavior, C35, real two-process
reservation contention, CP04 journal count, CP05 increment rule, CP10, and
RW-CUSTODY remain MET. Confirm no second journal/store/projection, prepare/commit
protocol, admission caller, scheduler, T7/T8 policy, physical admission/
dispatch/death door, launch adapter, signal-site wiring, fallback policy, family
lease, rotator, or main-merge work entered the candidate.

The Batch 1 primitive may provide typed events and ledger contracts while later
batches wire physical doors. Do not fail it merely because later-batch wiring is
correctly absent; do fail any frozen NBF-01 primitive criterion that remains
unproved or behaviorally false.

## Grok synthesis and required outputs

After the one Luna review completes, independently:

1. re-hash its check-in/receipt and all candidate identities;
2. inspect every source/test seam cited by Luna and spot-check the fresh isolated
   transcripts/probes;
3. adjudicate C01–C41, CP01–CP11, RW3-01..RW3-06/RW3-GATE, and A3-01..A3-09;
4. verify the broad-suite relevance classification rather than automatically
   waiving or failing it;
5. judge North Star alignment, KISS/YAGNI, scope, custody, and evidence integrity;
6. emit one terminal decision only.

Write:

- `.oracle/checkins/batch-1-rework3-grok.md`
- `.oracle/receipts/oracle-nbf01-rework3-grok.md`

The Grok check-in must contain the full criterion matrices, issue evidence,
broad-suite classification, preserved-MET and North Star/KISS judgments, and
smallest next action if rejected. The Grok receipt must bind all immutable input
identities, the one Luna review brief/check-in/receipt hashes, final candidate
and diff identities, every fresh transcript digest relied on, reviewer count
exactly one, scope/history/custody result, and terminal decision.

Allowed repository writes during this Oracle turn are only the one Luna review
brief and the four required Luna/Grok review artifacts. Do not implement or edit
production/tests, stage, commit, push, merge, rebase, reset, clean, mutate the
frozen tasklist/plan/North Star/custody/history, or start Batch 2. Even on PASS,
stop after the receipt and terminal token; delivery/commit remains a separate
orchestrator action.

## Complete immutable North Star (verbatim)

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
