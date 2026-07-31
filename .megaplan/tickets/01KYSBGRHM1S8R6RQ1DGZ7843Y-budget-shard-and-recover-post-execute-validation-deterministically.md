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
last_edited_at: '2026-07-31T06:17:01+00:00'
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
