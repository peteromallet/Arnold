---
id: 01KYSBGRHM1S8R6RQ1DGZ7843Y
title: Consolidate the post-M11 compatibility release before Native Parity
status: open
source: human
tags:
- bug
- validation
- pytest
- timeout
- recovery
- observability
- post-m11
- blocked-by-m11
- scope-drift
- run-authority
- admission
- native-platform-consumer
- containment
- do-not-wait-for-platform
- pre-native-blocker
codebase_id: null
created_at: '2026-07-30T11:10:56.052843+00:00'
last_edited_at: '2026-07-31T09:45:00+00:00'
epics:
- epic_id: megaplan-native-parity-corrective
  resolves_on_complete: false
  kind: associated
  provenance: post-m11-ticket-reconciliation-20260731
  linked_at: 2026-07-30 19:00:18.892153+00:00
---

## Classification

MUST COMPLETE AFTER M11 ACCEPTANCE AND BEFORE THE NATIVE PARITY EPIC STARTS. This is a one-time release and runtime-consolidation contract, not the owner of the long-term execution architecture.

## Scope

- Reconcile every M11 cloud runtime hotfix into one reviewed custody release vector.
- Include the all-wave accepted-attempt reader rule: a preferred latest artifact cannot erase an earlier authenticated accepted claim for the same current subject/binding.
- Include the narrow pre-epic fixes tracked by 01KYPNKD00Q48R7SSHGK4QJFMT, 01KYT5MGMXNKKAV6MV5QPWWJWW, and 01KYT4ZMFNK458MA5AFNR1ZM9R.
- Preserve the approved editable-install interpreter/import root until checkout, wheel, and installed-package canaries agree.
- Bind cloud marker, chain runtime identity, source commit, editable import root, and execution branch to one clean pushed vector.
- Retire detached runtime candidates and production-only source copies only after evidence is preserved.
- Preserve bounded 5+3 compatibility partitioning for genuinely admitted rework, with full task contracts and crash-safe continuation.
- Reject ID-only tasks and genuinely new scope; route them through revise/replan and normal admission.
- Preserve the M11 fixtures for reused batch indices, all-wave accepted-subject replay, no-pending reconstruction, accepted debt, runtime drift, generated/directory scope, stale review, T9/T42, false 100 percent status, and 60k-event replay.
- Freeze a content-addressed validation inventory from explicit owner/family
  selectors and `pytest --collect-only`. Keep the M11 acceptance shards
  distinct from the repository-wide baseline backstop; reject empty, duplicate,
  archived, hidden, root-helper, or unexpectedly changed node IDs.
- Make validation generators hermetic: tests write only to attempt-local output
  directories and compare those artifacts with committed evidence. They may not
  rewrite source-checkout evidence, consume `.pytest_cache/lastfailed` as an
  inventory, or inherit unrelated resident/delegation environment.
- Give every generator an admitted performance/resource budget and process
  receipt. Preserve the M11 WBC regression that caught per-AST-node
  `ast.get_source_segment` re-splitting whole modules: equivalent generation
  must remain comfortably below the existing 120-second gate and fail with a
  typed resource outcome rather than appearing stalled.
- Classify runtime-only tests by explicit applicability. The exact pinned
  editable-runtime case must pass on the cloud release vector; an ordinary
  local checkout is `not_applicable` with a recorded reason, never silently
  skipped and never misreported as a source regression.

## Acceptance

1. One clean pushed commit is the source of the cloud marker, editable runtime, and release candidate.
2. Checkout, editable install, wheel, and installed package produce equivalent authority and completion projections.
3. Killing the process before, between, and after bounded subwaves resumes without duplicate accepted work or effects.
4. Current authority contains no unresolved subject before status/adoption reports complete.
5. The three blocking stabilization tickets have passing exact fixtures and explicit receipts.
6. Watchdog supervision is re-enabled through bounded APIs.
7. Detached hotfix/runtime copies are inventoried, preserved where evidentiary, and otherwise retired through cleanup/release.
8. Native S1 preflight consumes the release manifest and fails closed on any commit, runtime, schema, cursor, or fixture mismatch.
9. The frozen validation inventory has exact union equality across its shards,
   while the independently recorded repository backstop reports baseline and
   new failures separately.
10. Re-running generators leaves the source checkout unchanged, records
    command/runtime/duration/resource identity, and reproduces identical
    structural fingerprints.
11. The WBC inventory performance regression covers Unicode, multiline, CRLF,
    form-feed, and Python AST byte offsets while remaining under its budget.
12. Local, editable, wheel, and installed-runtime applicability decisions are
    explicit receipts; only the exact bound production runtime can satisfy the
    M11 production identity obligation.

## Explicit ownership after this ticket

- Native C1/C2: completion vocabulary, immutable binding/evaluation, shadow non-authority, stable occurrence identity.
- Native S5A/S5B/S7: product review/rework routing, current-authority reconciliation, cap policy, and cumulative regression replay.
- Platform S1/S2A/S4/S5: neutral retry/generation/fanout lifecycle, durable substrate, bounded cursor primitives, extraction, and unrelated-consumer proof.
- No successor may introduce a second scheduler, authority reducer, attempt ledger, or status registry.

The historical native-platform-followup M5/M6 is not the owner of this future work and must not be cited as the resolver.

## 2026-07-31 superseded-session relaunch residual

The live seven-day cloud projection exposed an operator-paused, superseded M10
session whose marker correctly had `should_run: false`, while the cloud status
reducer recomputed `should_be_running: true` solely because its effective
status was `stopped`. That contradictory projection invited the watchdog to
keep relaunching intentionally retired work and contributed to the apparent
inventory of random recent agents.

Commit `e4ccb78b05` makes explicit stop custody and an active operator pause
outrank status-shape heuristics. This is immediate release containment, not a
new scheduler or lifecycle registry. Final runtime acceptance must demonstrate
that the same superseded marker projects `should_be_running: false`, is not
relaunched for three watchdog cycles, and does not contribute to the
`should_be_running_count`. Marker retirement remains a separate cleanup action
subject to its existing evidence and approval rules.

## 2026-07-31 reconciliation

This remains the one-time release umbrella and is not resolved by any successor
epic. The consolidated source now contains the M11 lineage and substantial
bounded/recovery fixes, but closure still requires the exact release vector,
validation inventory, runtime-equivalence proof, production canaries, watchdog
re-enable, cleanup evidence, and Native S1 handoff manifest. The Native link is
association-only so chain completion cannot manufacture release completion.

## 2026-07-31 shard 007 release-discovery residual

The exact no-debt discovery run at `e9c88f6f93` passed shards 005 and 006,
then stopped on shard 007 with an exact 654-node inventory: 648 passed and six
failed, with no skips, xfail, xpass, collection gap, or parser ambiguity.

The failures were release-consolidation drift rather than reasons to restore
compatibility surfaces:

- three topology tests imported the intentionally retired
  `arnold.pipelines.folder_audit` package;
- an import scan required the intentionally retired
  `arnold.pipelines._deliberation_example._hooks` module;
- malformed evidence-pack checkpoint input leaked an implementation `KeyError`
  before the typed schema validator could reject it; and
- one placeholder assertion retained the old `verify` step kind after the
  canonical projected-pipeline contract standardized adapter steps on
  `native_phase`.

The resolving change keeps the retired packages absent and explicitly
nonimportable, moves real-pipeline topology stability coverage to the retained
canonical evidence-pack pipeline, routes malformed checkpoint shapes through
the schema validator's `ValueError`, and aligns the stale assertion with the
existing native projection contract. It does not restore a shim, skip or xfail
the failures, or weaken topology/import/schema assertions.

Discovery custody, terminal receipts, logs, environment gates, and the frozen
17,620-node inventory are preserved under
`Arnold-validation-checkpoints/e9c88f6f93-shards005-037-discovery-20260731/`.
The ticket remains open until the exact final release revision passes the
complete frozen no-debt inventory and the other release acceptance conditions.

## 2026-07-31 shard 008 release-discovery residual

The follow-on exact run stopped before issuing an acceptance receipt for shard
008. Pytest ran 335 tests (333 passed, two failed), but four committed
`.native_wbc` files changed during execution, so the shard runner correctly
rejected the dirty post-run revision.

This exposed three distinct release defects:

- the runtime import-boundary fixture had not admitted the four canonical
  neutral broker-approval exports;
- the broker client and server passed arbitrary configured workspace paths
  directly to AF_UNIX, whose path-byte limit is shorter on macOS; and
- four security audit tests invoked the native runtime without an explicit
  artifact root while running from the source checkout, so the valid legacy
  default (`.`) placed WBC evidence in committed fixture paths.

The resolution keeps those broker symbols public, preserves the configured
socket pathname as the external endpoint identity, and gives server/client
callers sanitized actionable diagnostics when the host rejects an overlong
path. Round-trip tests use one reusable short-socket fixture outside long
workspace roots. The audit tests now pass unique disposable artifact roots.
The native runtime's established `artifact_root="."` contract remains intact
and separately proves default behavior under an isolated temporary CWD,
source-tree stability, and durable WBC emission for explicit roots.

The rejected shard log, custody receipt, source-mutation patch, status snapshot,
and checksums are preserved under
`Arnold-validation-checkpoints/e9c88f6f93-shards005-037-discovery-20260731/shard008-defect/`.

## 2026-07-31 shard 010 release-discovery residual

The exact 743-node shard 010 run on the shard-008 candidate completed 742 tests
and failed one default inventory-coverage assertion. The WBC inventory and its
supported-boundary projection correctly included fourteen authority-bearing
contracts introduced after M10, but the older F01-F17 artifact still named only
`execute_approval` and `gate_to_revise`. The join therefore exposed real
cross-milestone evidence drift rather than a test-runner failure.

The resolution makes provider/effect-fault applicability orthogonal to generic
WBC support. The generated supported-boundary artifact now declares an exact,
content-bound `effect_fault_coverage_required` scope for the two M10 fault
consumers (`execute_approval` and `gate_to_revise`), including inventory-source
and supported-projection hashes. The validator requires exact matrix coverage
of that scope, rejects undeclared proxy references, and surfaces source,
support, or scope-hash drift. A newly supported evidence/classification
boundary therefore does not acquire fake F01-F17 coverage, while a newly
declared effect boundary fails closed until a real scenario references it.

Independent semantic-health gaps found during the investigation are also
covered by negative fixtures for `chain_milestone_completion` and
`cloud_custody_unmanaged_running_warning`; these tests remain separate from
provider-fault applicability.

The ticket remains open until the final consolidated revision passes the whole
frozen no-debt inventory and the release-level acceptance conditions above.

## 2026-07-31 shard 013 release-discovery residual

The exact shard 013 run on `21626bcb2a` collected 404 nodes and terminated with
384 passed and 20 skipped. There were no failures, errors, xfails, xpasses,
inventory gaps, or parser ambiguities. All twenty skips came from the single
module-wide marker in
`tests/arnold_pipelines/megaplan/test_compositional_workflow.py`, which declares
the old 12-node compatibility-shell parity suite retired in favor of the
current 14-node native contract.

This is canonical-inventory debt, not a reason to admit skips or restore the
retired shell. Before removing or archiving the obsolete module, preserve an
assertion-by-assertion crosswalk to the active coverage in
`test_workflows_planning.py` and `test_native_contract.py`; add any genuinely
missing semantic assertion to the active suites. Then regenerate the frozen
inventory and require shard 013 to report zero skipped nodes.

The immutable discovery receipt is
`Arnold-validation-checkpoints/e9c88f6f93-shards005-037-discovery-20260731/receipts/full-suite-013-after-21626b.json`
with content SHA-256
`bf65b7b695b24b87418a966069e1d95f1830bd31b3f8ef030d41be537a338204`.
This remains an immediate release blocker under this umbrella; it does not
justify a separate platform or Native Parity ticket.

## 2026-07-31 shard 015 release-discovery residual

The exact shard 015 run on `78fae10fef` collected and executed 475 nodes:
472 passed and three failed, with no skip, xfail, xpass, timeout, source-tree
mutation, inventory gap, or parser ambiguity. The immutable terminal receipt
has content SHA-256
`a371783f31cf34d4031d8554c333e750ec2e70b7401ac650edd7e1966b6d1916`.

One failure was a release-evidence construction bug. Synthetic verifiability
flags used duplicate `evidence` keys in dictionary literals, so the later
source-criterion string silently replaced the audit disposition. The retained
record could not prove the audit verdict, rationale, and missing capabilities
that produced the flag. Commit `069fedf857` removes the duplicate-key path and
binds one non-empty `concern == evidence` record to both the audit disposition
and its source criterion.

The other two failures exposed an authority-boundary bug, not a slow heartbeat
implementation. An `active-step-heartbeat` cache write called lifecycle
handoff reconciliation. Given an already-persisted `executed` state and live
execute custody, that observation-only write could reinterpret or clear the
active step before persisting the heartbeat, yielding a false stale/dead-worker
view. The reviewed immediate containment is commit `be164da4cb`: it
narrowly prevents only `active-step-heartbeat` writes from reconciling a
lifecycle handoff, while authoritative lifecycle writes retain their existing
behavior. It merged into the consolidation vector at `6027584bf9`.
The broader nonlanded classifier experiment at `a242f6ea78` was rejected
because transport-mode names are not a sound general proxy for lifecycle
authority.

The exact rerun at `be164da4cb` passed all 475 frozen shard nodes with zero
failures, errors, skips, xfails, xpasses, deselections, debt, inventory gaps, or
source mutation. Its receipt is
`Arnold-validation-checkpoints/be164da-shard015-exact-20260731/receipts/full-suite-015-be164da.json`
with content SHA-256
`8494218e44063815fa1a622a49d81656a74ab17d62505c70f31e8bd36b36a0c2`.
That proves the shard 015 immediate residual, including heartbeat versus
execute/review custody, stale-run rejection, existing-handoff preservation,
and authoritative `executing -> executed` recovery.

This release umbrella remains open for the exact complete frozen inventory,
one clean release vector, and deployed live canaries. The broader replacement
of transport write modes with an explicit lifecycle write-intent/delta API is
follow-up architecture recorded in `01KTH21EXMWBHWBA62QC5Y8D3D`; it is not a
reason to defer this proven release correction.

## 2026-07-31 shard 016 release-discovery residual

The exact shard 016 discovery run on `f149b56870` collected 641 nodes and
terminated with 612 passed, 21 failed, four errors, and four skipped. There
were no xfails or xpasses. The immutable custody receipt and complete pytest
log are preserved under
`Arnold-validation-checkpoints/f149b568-shards016-037-discovery-20260731/receipts/`;
their SHA-256 digests are respectively
`bb9ad6e7392c655ad3e84e1c8e71ef477c57d56a44e78a98e56966e7c6f9a5e3`
and
`f6c3910d906b0d23173dab6e216032ae4c6e43ff5625ebd319d0a9d6d2acf4be`.

The outcomes resolve into four defect families:

- One retired-initiative test reached generic git-worktree preflight before
  retirement admission, returning `chain_git_worktree_required` instead of
  the authoritative `initiative_retired` disposition. Commit `ad03c09542`
  makes retirement a fail-closed, pre-mutation chain-admission guard and proves
  it for both valid and invalid worktree roots; merge commit `8c77044ec0`
  carries it into the release vector.
- Four installed-package composition tests invoked `python -m pip` through the
  frozen shard interpreter, whose intentionally pipless environment could not
  build a wheel. Commit `0c7e75bf90` creates an explicit disposable build
  environment with pip before building and installing the artifact; merge
  commit `1e632e968c` carries the hermetic wheel fixture.
- All twenty remaining M6 prerequisite failures came from loading the same tool
  under two module identities, so monkeypatches changed one module while the
  tested functions read globals from the other. The M6 acceptance generator
  tests could also write regenerated evidence into the source checkout.
  Commit `7fd618348d` imports the prerequisite tool through one canonical module
  identity, binds every generator output to an attempt-local copied evidence
  root, routes WBC side artifacts beside the requested output, and asserts the
  source checkout is byte-for-byte git-status stable. Merge commit
  `a53ee96b43` carries the correction.
- The four skipped `test_live_smoke.py` cases were credential-gated
  placeholders: they asserted only that a temporary directory existed and
  therefore could never prove deployed behavior. The nonlanded experiment
  `c88ebe00ac` attempted to replace them with a content-addressed deployed
  workflow-canary receipt, but independent review rejected it as acceptance
  laundering: its verifier trusted caller-supplied pass booleans, evidence-kind
  labels, and arbitrary hashed JSON instead of deriving the semantic outcomes
  from canonical event/projection evidence. That commit is rejected evidence,
  is not a fix, and must not be merged or cited as satisfying release
  acceptance.

The first three fixes close their discovered local defect mechanisms, but they
do not by themselves close this ticket. The exact shard rerun and complete
frozen inventory remain release evidence. The four fake live placeholders
remain an unresolved immediate release blocker until the release selects and
proves one honest alternative:

1. a deployed semantic verifier derives each required workflow outcome from
   canonical event-journal and authoritative projection evidence, with exact
   deployment/runtime/revision and source-window bindings; or
2. the fake suite is honestly removed from the executable inventory while an
   explicit pending live obligation remains fail-closed in the release manifest
   and cannot project release completion.

Local schema tests, hashes over producer-authored claims, status fields, and
manufactured labels are not deployed proof. No live-canary implementation is
selected or accepted by this ticket update.

No standalone live-canary ticket is warranted yet: resolving the blocker is
already a direct acceptance obligation of this release umbrella and the final
cloud promotion runbook. If the chosen implementation is deliberately deferred
beyond this release, that decision must first create an explicit pending live
ticket/obligation and amend the release gate rather than silently deleting the
proof. The long-term reusable owners are narrower: Platformization owns
product-neutral retirement/tombstone admission and hermetic
conformance-generator contracts; the release process retains ownership of this
concrete M11 wheel and semantic deployed-canary proof.

## 2026-07-31 shard 016 live-canary disposition

The release selected the second honest alternative above. Commit
`5f30fb0c0f` deletes the four credential-gated placeholders, admits the exact
deployment target/id, full revision, and strict runtime receipt, and can emit
only an immutable non-passing `pending` verdict. Conformance categorically
rejects `verified` under this pending schema, including a fully shaped,
correctly self-hashed forged verdict. Focused validation passed 53 tests with
Ruff, evidence regeneration, conformance validation, and diff checks green.

An earlier nonlanded semantic-reader attempt, `667b76115f`, is also rejected
evidence. Independent review proved that it could count arbitrary route events
as gate iterations, modeled resume unlike the real runner, used noncanonical
tiebreaker kinds, allowed cross-stitching unrelated journal/WBC/acceptance
records, accepted caller-selected runtime identity and future timestamps, and
let a forged standalone verdict satisfy conformance. It must never be merged
or cited as deployed proof.

The deliberate deferral now has explicit owner
`01KYVJ7A47TMH4BRGEV9JFTK10`. That ticket requires a runner for the exact
deployed backend, non-stitchable journal/WBC/acceptance/runtime joins, real
suspension/reentry, real gate iterations, canonical tiebreaker routing, frozen
stores, independent re-derivation, adversarial tests, and exact cloud commands. This release
umbrella remains open until that ticket produces the four real deployed
proofs; the pending verdict makes the missing work visible but does not close
it.

Subsequent inspection split the ownership more precisely. The immediate
`01KYVJ7A47TMH4BRGEV9JFTK10` runner proves the exact currently deployed
SQLite-backed path. Backend-neutral SQLite/PostgreSQL persistence and universal
workflow evidence joins are follow-up ticket `01KYVKPN6JHD19ZRM3WQF9XV8S`,
associated with Native Parity and Platformization. The split narrows the
release implementation without weakening its four real deployed proofs.

## 2026-07-31 shard 031 release-discovery residual

Shard 031 first ran from the clean consolidation vector
`ddebf0870cb75c0cfa87f2fc6373ac76a2ba4af6`, which already contains the
honest deployed workflow canary. The frozen 22-file partition collected and
executed exactly 205 nodes: 202 passed and three failed, with zero skips,
xfails, xpasses, deselections, inventory gaps, parser ambiguities, or source
mutation. The immutable failing receipt is
`Arnold-validation-checkpoints/ddebf0870c-shard031-exact-20260731/receipts/full-suite-031-ddebf0870c.json`
with content SHA-256
`b123ec18c600b6f13c8e4bc1056f3cb3c3f481325b0f16b3fee5ec60fa0f688b`.

Two failures were stale replay-oracle assumptions. The routed
`force-proceed` path now deliberately exceeds legacy behavior by atomically
retaining every critique disposition as explicit debt custody. Requiring byte
parity with the uncustodied legacy state would delete the proof that prevents
a manufactured `done` result. The corrected oracle therefore proves the
routed path is a strict authority-preserving superset: every current finding
has a stable disposition, the override binds the custody transaction and exact
debt count, and the gate projection names the same subjects.

The third failure exposed a real routed-resume projection gap. Both paths
completed the durable prep WBC lifecycle, and the routed response returned the
new reentry invocation, but the routed override record did not persist that
identity. The correction writes the reentry ID into the same atomic state
transition that clears the suspension and advances to `prepped`; it fails
closed if the matching durable override row is absent. The replay fixture now
constructs an authentic STARTED/SUSPENDED attempt and proves both paths reach
STARTED/SUSPENDED/RESUMED/COMPLETED with their own non-stitched reentry
lineage.

This update does not declare the release ticket complete. A terminal label may
be repaired when underlying acceptance is already proven, but it may not
substitute for the remaining exact-inventory, runtime-equivalence, deployed
canary, supervision, cleanup, and Native S1 handoff obligations.
