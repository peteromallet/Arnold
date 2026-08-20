# T2.2 offline release-candidate evidence — Luna preparation

Date: 2026-08-02  
Mode: read-only preparation, except for this report  
Ticket: `01KYSBGRHM1S8R6RQ1DGZ7843Y`  
Recovery base: `6787d6363e8fc0603092913ae877db14f3b9fff8`  
Verdict: **NOT READY; T2.2 is not complete and this report does not claim it**

## Executive result

There is no exact, clean, integrated T2.2 release candidate today. There is a
good historical evidence corpus and a usable set of fail-closed validators, but
the evidence is revision-specific, partial, or explicitly rejected. The current
T1 repair lanes are separate descendants of `6787d636...`, several have current
independent `HARD FAIL` verdicts, and no single clean integration commit contains
the accepted T1.1–T1.10 portfolio. The repository root and the locally cached
`origin/main` are not descendants of `6787d636...`; neither can silently stand in
for the requested clean recovery lineage.

The canonical ticket is still open and association-only. Its twelve acceptance
clauses combine pre-deploy evidence with production-only obligations. T2.2 may
produce an **offline candidate evidence receipt**, but it cannot:

- close the ticket;
- grant deployment authority;
- assert production runtime identity;
- treat a local, editable, wheel, or isolated installed run as the cloud run;
- mutate a Run Authority, Custody, WBC, release, ticket, Git remote, or cloud
  owner; or
- convert historical shard passes into exact-candidate acceptance.

The correct end state for this task is a distinct, content-addressed
`offline_candidate_evidence_complete` receipt for one clean integrated commit.
T2.6 may consume it as one input to a separate deploy-eligibility decision.
T3.6 remains the only checklist point that may accept the installed release and
close this ticket. This follows the recovery plan's T2.2 boundary at
`docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md:392-395`,
T2.6 at `:419-425`, and T3.6 at `:464-470`.

## Exact anchors inspected

### Canonical ticket

The canonical ticket was read from the exact recovery base because the current
dirty root does not contain this ticket path:

```text
commit  6787d6363e8fc0603092913ae877db14f3b9fff8
tree    83a22fc5f5930cbcbe5a439129706bb90bb28a92
parent  2460e24335f30c6856464f9a677782cd15ddedda
path    .megaplan/tickets/01KYSBGRHM1S8R6RQ1DGZ7843Y-budget-shard-and-recover-post-execute-validation-deterministically.md
blob    bea1fe296667a656272b2c18b1e5ee11032d61da
sha256  6d3db3fcaf0b71179b4ddaee95fcd11f26df7696247c98e098efcde43fc58e5b
```

The exact ticket says:

- `status: open` at lines 2–4;
- its Native Parity relation is `kind: associated` and
  `resolves_on_complete: false` at lines 25–30;
- it is a one-time release/runtime-consolidation contract, not the future
  architecture owner, at lines 33–35;
- its concrete scope is lines 39–64;
- its twelve acceptance clauses are lines 68–86;
- successor ownership and the prohibition on duplicate scheduler/reducer/
  ledger/registry owners are lines 88–95;
- association cannot manufacture release completion, and the exact release
  vector, inventory, runtime equivalence, canaries, watchdog, cleanup, and S1
  handoff remain required, at lines 114–121.

The cached remote-tracking `origin/main` is
`25e407d78339cc6f13112aec770188997577e85a` and contains the same open ticket
header. No network fetch was performed, so this is a local observation, not a
fresh remote attestation.

### Current repository and lineage

```text
root HEAD       36a10988717f9dfb0ab31d49baf05cc89bcfa989
root tree       c3f401de2f2e0bf621c7eb88339aaf9483e8bad0
root branch     main
root dirty      217 porcelain paths
6787 ancestor   no
origin/main     25e407d78339cc6f13112aec770188997577e85a
origin...root   865 left / 18 right
```

The root is therefore neither an exact candidate nor a safe source from which
to generate acceptance evidence. The clean base worktree
`/private/tmp/arnold-post-c7-release-recovery` is exactly `6787d636...` and
clean, but it predates every recovery fix and is only a base.

Current clean descendants of `6787d636...` are separate sibling lanes, not one
integrated candidate:

| Lane | HEAD | Tree | Dirty | Current disposition |
|---|---|---|---:|---|
| T1.3 bundles | `fe1786c298361454a73754536ecf7de2f7b4bd69` | `f11e71c1bbd6823a80bcba48c7bf88f655f44b8f` | 0 | independent `HARD FAIL` |
| T1.5 simple fixer | `4bfd5fb2cc0d174297260aee6da7cb9a347f6a6a` | `066c22a540ff9983380760088e2daa9113cbb539` | 0 | implementation evidence only; not accepted |
| T1.8 generation | `148465a109ade4318e4cb9ae13a83645a4bf2934` | `505b8104ba4fc5298e8efde384551e2310ec81e4` | 0 | independent `HARD FAIL` |
| T1.10 notifications | `0c3d662024bc0497ed3979991a20b3b48ecf19cd` | `d4c10e167be87e1655704d1beeaf92d6c4e46526` | 0 | independent `HARD FAIL` |
| T5.1 successor prep | `7c254f7f0d15ba4e835a6fe7cae40b47d29ef7cd` | `27e7b22ef0d7f3faeaa6b7cbcd63aabb2872d7e9` | 0 | independent `HARD FAIL`; four owner decisions pending |
| T1.1 admission | `6787d636...` | `83a22fc...` | 17 | active dirty implementation, no candidate |
| T1.7 storage | `6787d636...` | `83a22fc...` | 1 | active dirty implementation, no candidate |

The independent current failure receipts are:

- T1.3: `.megaplan/subagents/critique-ledger-recovery/T1.3/contract-bundles-independent-review-pass4-luna-result.md`,
  SHA-256 `04fdf319699a28bdef634920a26237d7a6a51b5e8fa55f590d674dee904ab144`;
- T1.8: `.megaplan/subagents/critique-ledger-recovery/T1.8/gen-deploy-independent-review-pass3-sol-result.md`,
  SHA-256 `bff46dc2b888e989ae9099d6270f4a4dac0c37dbdaf80e1fd1eba43fdf9b887a`;
- T1.10: `.megaplan/subagents/critique-ledger-recovery/T1.10/notification-ux-independent-review-pass4-luna-result.md`,
  SHA-256 `2fba7fd07882c98b2080ae9867dc8a739b77625b311dadad820547636ab9584b`;
- T5.1: `.megaplan/subagents/critique-ledger-recovery/T5.1/t5-1-independent-review-pass3-luna-result.md`,
  SHA-256 `00909428779d6258e11e68b6ea21b90eb46d8ff4394c2efc569554dbb5036609`.

These are current negative evidence and must be consumed as blockers. They are
not candidate inputs that can be waived by a broad green test count.

## Authority semantics: offline evidence is not deploy authority

The platform-wide ownership split must remain explicit:

| Layer | Owns | T2.2 may do | T2.2 must not do |
|---|---|---|---|
| Domain owners | Semantics and versioned contracts for T1.1–T1.10 | Bind accepted local candidate commits and suites | Invent acceptance for another owner |
| Run Authority | Grants, fences, accepted transitions | Verify schemas and fail-closed consumers offline | Issue or mutate a production grant/fence |
| Custody | Occurrence, lease, epoch and durable ownership | Exercise hermetic fixtures | Claim a production lease/epoch |
| WBC | GLEK, intent, attempt, ambiguity and effect receipts | Prove offline effect denial and replay | Call a provider or relabel `INDETERMINATE` |
| Release Authority | Candidate selection and deployment decisions | Sign/record an evidence-only candidate decision if its real interface exists | Treat a Markdown verdict or verifier exit code as release authority |
| Independent verifier | Recompute facts from immutable inputs | Rehash, rerun, compare and reject | Grant release/deploy/ticket closure authority |
| Ticket store | Durable issue status and association | Read current ticket and cite its digest | Mark the ticket closed during T2.2 |

An offline receipt is therefore a proof object, not an owner decision. It should
contain `authority_effect: none`, `deployment_authorized: false`,
`ticket_closure_authorized: false`, and `production_identity_satisfied: false`.
Any consumer that interprets it otherwise fails the platform contract even if
every local test passes.

## Existing schema conflict that must be fixed or avoided

At `6787d636...`, `scripts/validate_post_m11_release_evidence.py:17-25`
defines `candidate_ready`, but the only residuals it permits to remain pending
are:

```text
production-canary
runtime-selector-promotion
acceptance-tag
critique-runtime-rebind
critique-launch
```

At `:568-582`, it rejects `candidate_ready` while any other residual remains
pending, then validates a structure named `final_acceptance`. The canonical
ledger still has these pre-deploy or promotion residuals pending at
`docs/megaplan/post-m11-release-evidence-20260731.json:540-610`:

- final integrated validation;
- final no-debt validation;
- final packaging artifacts;
- cloud image build;
- direct main promotion;
- source tag;
- content-addressed runtime;
- cutover preflight;
- runtime selector promotion;
- production canary;
- critique runtime rebind;
- critique launch; and
- acceptance tag.

That old `candidate_ready` state is a post-promotion/pre-canary release state,
not T2.2's offline state. T2.2 must not make direct-main promotion, source tag,
cloud image, or content-addressed production runtime look complete merely to
pass this validator.

Use one of these finite remedies:

1. preferred: create a separate
   `critique-ledger-recovery.offline-candidate-evidence.v1` manifest and leave
   the historical post-M11 ledger `in_progress`; or
2. version the release-evidence schema with an explicit
   `offline_candidate_ready` state and an enumerated deployment-only residual
   set, while retaining `candidate_ready` for its historical meaning.

Do not overload or rename `final_acceptance` in place without a version bump.
Existing exact tests at `tests/test_post_m11_release_evidence.py:161-215` and
`:252-364` protect the current semantics and must remain backward compatible.

## Exact ticket requirement inventory

The following matrix turns the ticket's twelve clauses into finite T2.2 and
later-release obligations. `MISSING` means no exact integrated recovery-candidate
receipt exists. `PRODUCTION` means it cannot be satisfied offline. `HISTORICAL`
means useful regression provenance but not current-candidate evidence.

| ID | Ticket requirement | T2.2 offline acceptance | Current evidence | State now | Later authority |
|---|---|---|---|---|---|
| A01 | One clean pushed commit sources marker, editable runtime and release candidate (`ticket:68`) | Select one clean integrated commit/tree descended from `6787...`; prove every T1 lane disposition. A local offline candidate may be unpushed but must say so. | Separate clean sibling commits; root dirty/divergent; cached `origin/main` divergent | **MISSING** | Push/marker equality is T3/Release Authority |
| A02 | Checkout/editable/wheel/installed authority and completion equivalence (`:69`) | Run source, editable, fresh wheel, isolated installed package against one commit/runtime contract; compare normalized projections | Historical wheel tests and T1 lane tests only | **MISSING exact candidate** | Exact cloud installed vector at T3 |
| A03 | Kill before/between/after subwaves resumes without duplicate accepted work/effects (`:70`) | Hermetic crash matrix through installed entrypoints, stable occurrences/GLEKs, zero provider calls | M11 fixtures and partial historical receipts | **MISSING exact candidate** | Production no-duplicate observation at T3 |
| A04 | No unresolved current-authority subject before complete (`:71`) | Recompute from raw owner evidence; reject unresolved/unknown/stale/wrong-target | T1.1 not accepted; T5.1 raw CL1 blockers remain pending | **MISSING / BLOCKED** | Owner decisions remain authoritative |
| A05 | Three narrow tickets have exact passing fixtures/receipts (`:72`) | Bind fresh exact-candidate fixtures and receipts for all three IDs | All three tickets are still `status: open` at `6787...` | **MISSING** | Their owners/ticket closure, then T3.6 umbrella closure |
| A06 | Watchdog re-enabled through bounded APIs (`:73`) | Prove bounded API contract and disabled unsafe legacy topology offline | Historical 488-test compatibility evidence; T1.5 changes topology; no integrated result | **MISSING** | Re-enable/three-cycle proof is production-only |
| A07 | Detached copies inventoried/preserved/retired (`:74`) | Freeze exact source-universe disposition; no cleanup | Historical inventory and current worktree survey | **PARTIAL** | Retirement/cleanup requires separate authority, T3/T4 |
| A08 | Native S1 consumes manifest and fails on commit/runtime/schema/cursor/fixture mismatch (`:75`) | Run hermetic consumer mismatch matrix with candidate manifest | Historical validators; no recovery-candidate S1 handoff | **MISSING** | Live handoff/adoption after accepted release |
| A09 | Exact frozen inventory union; repo baseline/new failures separate (`:76-78`) | Fresh collect-only inventory plus disjoint shard union; independent backstop on base and candidate | July 31 partial/mixed-revision corpus | **MISSING exact candidate** | None if fully proven offline; rerun if tree changes |
| A10 | Hermetic generators; unchanged source; process/runtime/duration/resource identities; structural fingerprints (`:79-81`) | Run twice from clean archives into attempt-local dirs and compare; dirty diff is failure | Generator code/tests exist; no exact integrated receipt | **MISSING exact candidate** | None if fully proven offline |
| A11 | WBC Unicode/multiline/CRLF/form-feed/AST byte offsets under budget (`:82-83`) | Exact performance fixture, admitted budget and resource receipt, <120 s | Historical WBC regression and current tests | **MISSING exact candidate** | None if fully proven offline |
| A12 | Explicit local/editable/wheel/installed applicability; only bound production satisfies production identity (`:84-86`) | Emit four typed applicability receipts; local variants must say `production_identity_satisfied=false` | Historical code distinguishes some runtime identity; no unified receipts | **MISSING** | Exact installed production identity at T3.6 |

### Scope requirements not safely reducible to the twelve rows

Ticket lines 39–64 also require these explicit candidate checks:

| ID | Requirement | Current state |
|---|---|---|
| S01 | Reconcile every M11 hotfix into one reviewed vector | Missing: no integrated recovery vector |
| S02 | All-wave accepted-attempt reader cannot erase earlier authenticated accepted claim | Historical implementation/tests only; rerun exact candidate |
| S03 | Include tickets `01KYPNKD...`, `01KYT5MG...`, `01KYT4ZM...` | Missing exact current receipts; all remain open |
| S04 | Preserve editable interpreter/import root until parity | T1.8 current candidate hard-fails; no accepted vector |
| S05 | Bind marker, chain runtime, source, import root and execution branch | Production-only final proof; offline schema/mismatch tests required |
| S06 | Preserve evidence before retiring detached copies | Historical inventory exists; no cleanup authorized here |
| S07 | Preserve bounded 5+3 admitted rework, full contracts, crash continuation | Historical fixtures only; exact candidate replay missing |
| S08 | Reject ID-only and new scope; route revise/replan | Exact integrated replay missing |
| S09 | Preserve named M11 fixture families including 60k replay | Test surfaces exist; exact candidate suite missing |
| S10 | Freeze selectors plus `--collect-only`; reject empty/duplicate/archived/hidden/root-helper/changed node IDs | Runner/tests exist; exact candidate inventory missing |
| S11 | Attempt-local hermetic generators; no source rewrite, `lastfailed`, or unrelated resident environment | Code/tests exist; exact candidate two-run proof missing |
| S12 | Admitted budgets and typed resource outcome; WBC <120 seconds | Test exists; exact candidate resource receipt missing |
| S13 | Runtime-only tests produce explicit applicability, not silent skip | No unified exact-candidate applicability ledger |

## Existing candidate artifacts, receipts, and tests

### A. Current and accepted only for their stated purpose

These are reusable inputs, not T2.2 acceptance:

| Artifact | Digest / identity | Classification |
|---|---|---|
| T0.2 off-volume manifest | `evidence/critique-ledger-recovery/T0.2/manifest.json`, SHA-256 `c45030bd29c57d1eb0d1694c705aebb3dd55ca04fa3b612ad0d287e32e4dc791` | **ACCEPTED/current evidence preservation**; 319 claims, not release proof |
| T0.4 incident inventory | `evidence/critique-ledger-recovery/T0.4/inventory.json`, SHA-256 `2984a983ae7a307d02b6d36cb53ab42122e5d9ad63d5d5eb0ff8d0c89ff5bff8` | **ACCEPTED/current incident projection**; 342 rows, not owner authority |
| Canonical ticket | blob/digest above | **CURRENT/open system-of-record input** |
| Clean recovery base | `6787d636...`, tree `83a22fc...` | **CURRENT base**, not candidate |
| Historical release ledger | `docs/megaplan/post-m11-release-evidence-20260731.json`, SHA-256 `a16cf87130d6f28ab7452037f837f58552710a06d42431c10fc5ae5b28b46cdf` | **VALID in-progress historical ledger**, explicitly not complete |
| Historical narrative | `docs/megaplan/post-m11-release-evidence-20260731.md`, SHA-256 `f42f1da997de9f2a48657e2c1bd13d536d4060cdc5771d9c1b8af95e7a88e8a8` | Projection only; says final work pending |
| Ticket reconciliation | `docs/megaplan/post-m11-ticket-reconciliation-2026-07-31.md`, SHA-256 `eaf6dc7aa6ea7ee5070e0f630a7a9d8f2e72efef6797f19382b541ea875ac508` | Historical open-ticket ledger |
| Direct-promotion policy | `docs/megaplan/post-m11-direct-promotion-policy-override-20260731.md` | Current historical policy: ordinary FF CAS only; not a mutation grant for this task |

The T0.2/T0.4 evidence is transitively relevant because the T1 lanes depend on
T0.2 and the old session evidence must remain recoverable. It does not cure the
missing exact-candidate tests.

### B. Historical checkpoint corpus

The local corpus is under
`/Users/peteromalley/Documents/Arnold-validation-checkpoints`. It is valuable
for defect provenance and regression selection. Every receipt is bound to an
older commit; none is bound to a future integrated T2.2 commit.

| Root | Main result | Classification for T2.2 |
|---|---|---|
| `e9c88f6f93-shards005-037-discovery-20260731` | shards 005/006 green; 007 initially 648/654 then fixed at another revision; later through 014 across multiple revisions; shard 013 had 20 skips | **HISTORICAL mixed-revision discovery**, never union acceptance |
| `78fae10-shards014-037-discovery-20260731` | shard 014 771/771; shard 015 472/475 | **HISTORICAL failed discovery** |
| `be164da-shard015-exact-20260731` | 475/475, receipt SHA-256 `8494218e...` | **HISTORICAL accepted shard-only proof**, stale for candidate |
| `f149b568-shards016-037-discovery-20260731` | 612 passed, 21 failed, 4 errors, 4 skips; custody SHA `bb9ad6...`, log SHA `f6c391...` | **HISTORICAL failure** |
| `ddebf0870c-shard031-exact-20260731` | 202/205, receipt SHA-256 `b123ec18...` | **HISTORICAL failure** |
| `70b087d325-shard031-exact-20260731` | 205/205 on a non-ancestor side lineage | **HISTORICAL shard-only pass**, not recovery-lineage acceptance |
| `bf5449ae0e-full-no-debt-20260731` | shard 000 green; shard 001 had 1 failure + 1 skip + debt | **HISTORICAL failed partial run** |
| `bf5449ae0e-full-no-debt-seeded-20260731` | explicitly `aborted-superseded` | **SUPERSEDED/REJECTED for acceptance** |
| `cd7c6ac0ee-full-no-debt-20260731` | shards 000/001 green; shard 002 had 9 failures | **HISTORICAL failed partial run** |
| `a911803c33-full-no-debt-20260731` | shards 000–002 green; shard 003 had 2 failures | **HISTORICAL failed partial run** |
| `d0befb1ea6-full-no-debt-20260731` | shards 000–003 green; shard 004 never produced a main terminal receipt | **HISTORICAL incomplete partial run** |
| `1a10886218-full-no-debt-20260731` | shards 000–004 green but later defect record; only 1,702 full-suite nodes shown across those shards | **HISTORICAL incomplete partial run** |
| `5642cdd1ac-full-no-debt-20260731` | paused before shards due opaque node-ID parser defect | **HISTORICAL preflight failure** |
| `730fbf08c0-full-no-debt-20260731` | superseded before shards | **SUPERSEDED** |
| `6027584-shards016-037-discovery-20260731` | inventory/discovery artifacts, no main terminal shard receipts | **HISTORICAL incomplete** |
| `postgres16-local-gate-20260731-f056234f9a` | local database gate corpus | **HISTORICAL component evidence**, not full candidate |

The frozen inventory in the July 31 discovery family had 17,620 node IDs
(`ticket:149-153`). Its existence proves the method and preserves defects; it
does not prove the new candidate because node IDs, selectors, code, runtime and
test semantics may change. Exact inventory evidence is invalidated by any tree
change and must be regenerated after integration freezes.

### C. Explicitly rejected evidence

These artifacts must be placed in a denylist in the T2.2 proof map so no later
aggregator accidentally promotes them:

| Identity | Why rejected | Canonical ticket lines |
|---|---|---|
| `c88ebe00ac29901049766dc19c4b3ee43b4b70ea` | Fake deployed-canary verifier trusted caller-supplied pass booleans/labels and arbitrary JSON | 315–324 |
| `667b76115f9bbf621c7cf227865bd29af937e280` | Semantic reader allowed cross-stitching, noncanonical events, caller-selected runtime, future times and forged verdict | 363–369 |
| `bf5449ae0e-full-no-debt-seeded-20260731` | Seeded attempt explicitly aborted/superseded | historical ledger `:421-454` |
| Every receipt with failure, error, skip, xfail/xpass, debt, source mutation, missing terminal sidecar or partial union | Fails exact no-debt semantics | generator `generate_m11_no_debt.py:138-193,256-287` |
| Old package artifacts | Historical code-gate evidence only; must rebuild exact commit | ticket 459–463; ledger 552–560 |
| A prose `PASS`, checklist edit, tag, ancestry relation, marker text or status label | Projection, not immutable owner evidence | promotion policy lines 31–48 |

Commit `5f30fb0c0fd1ac0d71345fbedb79e5da02e9b7c8` is not rejected code: it
honestly records a pending deployed-canary obligation and removes fake
placeholders. Its `pending` verdict is accepted as honest negative evidence,
not as a canary pass (`ticket:353-378`).

### D. Candidate tooling and regression surfaces at `6787...`

These exact tools exist and should be reused after auditing them against the
new T1 contracts:

```text
scripts/generate_m11_a7_inventory.py
scripts/generate_m11_acceptance_receipt.py
scripts/generate_m11_audit_manifest.py
scripts/generate_m11_cross_contract_acceptance.py
scripts/generate_m11_no_debt.py
scripts/generate_m11_predecessor_wrappers.py
scripts/generate_m11_runtime_receipt.py
scripts/run_m11_lifecycle_correction.py
scripts/run_m11_validation_shard.py
scripts/validate_post_m11_release_evidence.py
```

Existing core tests:

```text
tests/m11/test_acceptance_receipt.py
tests/m11/test_audit_manifest.py
tests/m11/test_cross_contract_acceptance.py
tests/m11/test_cross_contract_acceptance_hardening.py
tests/m11/test_lifecycle_correction.py
tests/m11/test_no_debt_receipt.py
tests/m11/test_predecessor_wrapper_derivation.py
tests/m11/test_runtime_receipt.py
tests/m11/test_validation_shard_runner.py
tests/m11/test_wbc_acceptance_semantics.py
tests/test_post_m11_release_evidence.py
tests/test_post_m11_release_evidence_policy.py
```

Existing packaging and cloud-canary tests:

```text
tests/installed_wheel/conftest.py
tests/installed_wheel/test_import_workflow_kernel.py
tests/installed_wheel/test_m5_wheel_smoke.py
tests/cloud/test_m11_canary_cohort.py
tests/cloud/test_m11_live_canary.py
tests/cloud/test_m11_workflow_canary.py
```

Relevant code contracts already fail closed on important cases:

- `run_m11_validation_shard.py:288-318` performs collect-only and rejects empty
  or duplicate node IDs;
- `:413-417` separately collects and executes;
- `:486-549` compares exact inventory and rejects drift;
- `generate_m11_no_debt.py:174-185` rejects nonzero exit, nonexact inventory,
  any failure/error/skip/xfail/xpass/debt, or nonempty debt;
- `:256-287` rejects missing, unexpected, duplicate or overlapping shard
  receipts and unequal union;
- `validate_post_m11_release_evidence.py:196-279` enforces disjoint complete
  terminal inventory equality;
- `tests/test_post_m11_release_evidence.py:321-364` proves superseded evidence
  cannot be promoted and nonacceptance outcomes fail.

Those are foundations, not proof that all new T1 domains and platform-wide
effect paths are in the inventory. Before using them, add the recovery-specific
contract portfolio and verify selectors include all source, wheel, installed,
native, cloud-wrapper, and effect-boundary tests introduced by T1.

## Dependency map

### T0

The formal task graph at recovery-plan lines 85–118 says T2.2 depends on
T1.1–T1.10. Those lanes transitively depend on T0.2, which is complete. T0.2 and
T0.4 are therefore valid preserved inputs.

T0.0/T0.1 remain blocked and T0.3 remains incomplete. They do not authorize
skipping offline evidence, but they impose a safety boundary: T2.2 must execute
only in disposable isolated scope with all production adapters unavailable and
zero external effects. Any test whose setup can reach the poisoned session,
provider, cloud selector, marker, owner store, or installed production runtime
must fail closed or be classified `not_applicable`; it may not run opportunistically.

T0.3 storage/capacity proof becomes a hard dependency for installed/deployment
work and production effect safety. A local resource-budget receipt may be
generated at T2.2, but it does not satisfy cloud byte/inode reserve, WAL, restore,
or ENOSPC acceptance.

### T1

T2.2's direct prerequisite is the accepted T1.1–T1.10 portfolio. Current state:

| Task | Current usable state | T2.2 consequence |
|---|---|---|
| T1.1 | preparation plus dirty implementation; no accepted commit | Cannot prove raw-evidence admission or A04 |
| T1.2 | preparation only | Cannot prove failed critics never become semantic no-findings |
| T1.3 | clean candidate but current independent `HARD FAIL` | Cannot bind authentic provider/session/model contract bundle |
| T1.4 | implementation brief only | Cannot prove one typed narrow graph repair/budget |
| T1.5 | clean implementation evidence, not independently accepted | Cannot prove singleton simple-fixer topology |
| T1.6 | detailed preparation, no accepted implementation | Cannot prove exclusive effect boundary/ambiguity semantics |
| T1.7 | dirty implementation | Cannot prove crash/concurrency/storage safety |
| T1.8 | clean candidate, current independent `HARD FAIL` | Cannot prove generation/rollback/source-installed identity |
| T1.9 | preparation only and explicitly blocked on owner interfaces | Cannot prove authorized launch/stop transaction contract |
| T1.10 | clean candidate, current independent `HARD FAIL` | Cannot prove notification dedupe and installed delivery |

The integration rule is finite: each lane supplies one accepted exact commit,
tree, parent/base, changed-path allowlist, result digest, independent verifier
digest and owner-interface digest. An integrator then combines them once on a
fresh descendant of `6787...`. Every lane's focused suite and the cross-lane
portfolio rerun on the integrated commit. No lane's prior PASS survives a
conflict resolution or later tree change without rerun.

### T5.1

T5.1 is **not a prerequisite of T2.2**. The formal graph starts T5.1 early in
parallel, but T5.2 depends on T1.1, T1.3, T3.6 and T5.1. Thus the direction is:

```text
T1 portfolio -> T2.2 -> T2.3/T2.5/T2.4 -> T2.6 -> T3.6 -> T5.2
          T5.1 ----------------------------------------------^
```

Do not merge the current T5.1 candidate merely to make the release source
universe look complete. Its exact current review is `HARD FAIL`; all four
external owner decisions remain pending, and the old CL1 handoff remains
`accepted_for_cl2=false`. T2.2 should record T5.1 as a separate deferred
successor lane and prove that no v2 generated state, owner identity, GLEK,
notification ID or mutable artifact entered the recovery release.

T2.2 does depend on the **shared T1.1/T1.3 interfaces** that T5.2 will later
consume. Those interfaces need one platform-wide definition; T5.1 must not
introduce a second admission owner or contract-bundle registry. This is an
interface-coherence dependency, not permission for T2.2 to resolve CL1 owner
decisions.

## Finite offline acceptance matrix

T2.2 is eligible for an independent `PASS` only when every mandatory row below
is `PASS` on one exact integrated commit. `DEFERRED_PRODUCTION` is a successful
offline classification only for the enumerated production rows; it is not a
pass on the underlying ticket obligation.

| Gate | Required machine fact | Required result |
|---|---|---|
| G01 lineage | Candidate commit exists, is a commit, exact tree matches, base `6787...` is ancestor, worktree clean, no submodule/symlink/type drift, intended branch/ref recorded | PASS |
| G02 source universe | Every relevant T1 lane, loose commit/worktree/ref/checkpoint has a unique `LANDED`, `SUPERSEDED`, `REJECTED`, or `DEFERRED` disposition with immutable proof; no unique intended delta omitted | PASS |
| G03 T1 portfolio | T1.1–T1.10 each name accepted commit/tree/interface/test/review digests; integrated tree contains exactly accepted content | PASS |
| G04 no current hard fail | No independent review bound to any integrated lane remains `HARD FAIL`; every counterexample has a linked closing test and receipt | PASS |
| G05 three ticket fixtures | All three ticket IDs have exact integrated fixtures, zero-debt results and explicit receipts | PASS |
| G06 frozen inventory | One canonical sorted content-addressed collect-only inventory from explicit selectors; no empty/duplicate/hidden/archived/helper/changed IDs | PASS |
| G07 shard partition | Deterministic disjoint partition, every node exactly once, both `full_suite` and `semantic_carrier`, exact union equality | PASS |
| G08 no debt | All nodes pass; zero failure/error/skip/xfail/xpass/deselect/debt/mutation/parser ambiguity/timeout | PASS |
| G09 repo backstop | Base and candidate backstops independently run; baseline failures and new failures separate; new failures zero; no baseline waiver for candidate-touched semantics | PASS |
| G10 generator hermeticity | Two clean-archive runs, attempt-local output, identical structural fingerprints, source status/tree unchanged, no `lastfailed`/resident env influence | PASS |
| G11 budgets | Command, interpreter/runtime, duration, peak RSS, bytes read/written, process identity and typed timeout/resource outcome; WBC boundary test <120 s | PASS |
| G12 source/editable parity | Same contract/authority/completion projections, exact import roots recorded, production identity false | PASS |
| G13 wheel/installed parity | Fresh build from exact commit; wheel/sdist/RECORD hashes; forbidden-content absence; isolated install; CLI/module/wrapper help and behavior parity | PASS |
| G14 crash/replay | Kill before/between/after bounded waves and owner-order faults; stable occurrence/GLEKs; no duplicate accepted work/effects; unknown never redispatched | PASS |
| G15 effect closure | Static inventory plus runtime spies cover Discord/webhook/Git/PR/model/cloud/deploy/process paths; all production adapters unavailable; external call count zero | PASS |
| G16 applicability | Explicit receipts for local/source/editable/wheel/installed-isolated; every one says `production_identity_satisfied=false`; no silent skip | PASS |
| G17 S1 preflight | Hermetic consumer accepts exact manifest and rejects commit/tree/runtime/schema/cursor/fixture/receipt substitution | PASS |
| G18 detached resources | Exact preserved inventory and disposition plan; T2.2 performs no retirement or cleanup | PASS |
| G19 production obligations | Push/remote/CI, cloud image/runtime, marker/chain/selectors, re-enable/three cycles, deployed canaries, cleanup, live S1 adoption, tag and ticket closure | DEFERRED_PRODUCTION with named T3/T4 owner |
| G20 authority receipt | Offline manifest says no authority/effects; independent verifier recomputes; Release Authority records candidate evidence separately; ticket remains open | PASS |

Any `FAIL`, `MISSING`, `UNKNOWN`, unclassified skip, dirty tree, altered selector,
unbound receipt, unavailable artifact, or owner ambiguity makes T2.2 `FAIL`.
There is no retry-count or majority-vote path around this matrix.

## Exact evidence bundle to implement

Create the following only after the integrated commit is frozen. The path names
are proposed; schema and owner review must freeze them before execution.

```text
evidence/critique-ledger-recovery/T2.2/
  offline-candidate-manifest.json
  candidate-git-binding.json
  source-universe.json
  t1-contract-portfolio.json
  counterexample-closure-index.json
  ticket-requirement-proof-map.json
  three-ticket-fixture-index.json
  collection/
    selectors.json
    collect-only-receipt.json
    expected-inventory.json
    partition.json
  shards/
    *.receipt.json
    *.custody.json
    *.terminal.json
  no-debt-receipt.json
  repository-backstop-base.json
  repository-backstop-candidate.json
  generator-replay-receipt.json
  resource-budget-receipts.json
  applicability/
    source.json
    editable.json
    wheel.json
    installed-isolated.json
    production-pending.json
  packaging/
    build-receipt.json
    artifacts.sha256
    record-verification.json
    installed-parity.json
  crash-replay-matrix.json
  effect-boundary-inventory.json
  native-s1-preflight-receipt.json
  detached-resource-disposition.json
  production-obligations-pending.json
  independent-verifier-receipt.json
```

`offline-candidate-manifest.json` must bind, at minimum:

```text
schema/version
ticket id + ticket blob + ticket SHA-256
recovery base commit/tree
candidate commit/tree/parent(s)/branch/local-or-pushed status
source-universe digest
T1 portfolio digest
frozen inventory digest/count
partition + every terminal receipt digest
no-debt digest
base/candidate backstop digests
generator/resource/applicability/package/crash/effect/S1 digests
independent verifier identity, code digest, runtime and output digest
authority_effect=none
deployment_authorized=false
ticket_closure_authorized=false
production_identity_satisfied=false
production obligations with exact next owner/task
```

The manifest must not hash itself. Use an external signed/owner-authenticated
receipt over the canonical manifest bytes, or bind the manifest by Git
commit/tree plus an independent receipt. Unkeyed SHA-256 proves content identity,
not owner authenticity.

## Exact implementation and verification sequence

### Phase 1 — freeze contracts before integration

1. Freeze the T1.1–T1.10 interface matrix, counterexample set and owner for each
   result. No broad architecture reopening after freeze unless a new executable
   counterexample proves the contract unsound.
2. Repair current T1.3, T1.8 and T1.10 hard failures; finish T1.1, T1.2, T1.4,
   T1.5, T1.6, T1.7 and T1.9; obtain independent exact-commit decisions.
3. Freeze the offline schema above, including explicit non-authority fields and
   the exact `DEFERRED_PRODUCTION` allowlist.
4. Freeze selectors and budgets only after all accepted T1 test paths exist.

Stop if any lane lacks a clean commit, exact review, owner interface, or closing
test for every counterexample.

### Phase 2 — build one clean `6787...` descendant

1. Create a fresh integration worktree/branch from exact `6787d636...`.
2. Apply accepted lane commits in declared order. Do not copy dirty worktree
   bytes or merge current root/main by convenience.
3. Resolve conflicts once under the named integrator. Record each resolution
   against both source commits and rerun both owners' focused suites.
4. Produce the exhaustive source-universe disposition. Keep T5.1 separate unless
   a frozen shared-interface change is explicitly required and accepted.
5. Commit the integrated source. Verify commit type, tree, parent ancestry,
   exact changed paths, clean status, no ignored generated residue and no
   alternate import root.

Stop if a relevant unique delta is unclassified, if root/origin divergence is
implicitly absorbed, or if the integrated tree differs after evidence begins.

### Phase 3 — generate exact inventory and component evidence

1. Export the exact candidate with `git archive` into a disposable path.
2. Create locked source, editable, build, wheel and installed environments from
   the same candidate; record interpreter, dependency lock/freeze, import roots,
   entrypoints and wrapper digests.
3. Run explicit selector discovery and `pytest --collect-only`; canonicalize
   opaque node IDs without lossy parsing; reject empty/duplicate/unexpected IDs.
4. Generate deterministic shard partition and semantic carrier partition.
5. Run generators twice into distinct attempt-local directories with resident,
   delegation and unrelated provider environment removed. Compare canonical
   structural fingerprints and prove source bytes/tree/status unchanged.
6. Run WBC performance and Unicode/line-ending/byte-offset cases under admitted
   resource budgets.

Stop on any skipped applicability decision, missing terminal receipt, runtime
drift, source mutation, or changed collection.

### Phase 4 — execute and aggregate

1. Run every shard through the installed runner with custody/start/terminal
   receipts and exact runtime/revision binding.
2. Independently verify each receipt hash, command, runtime, inventory, count,
   source stability, duration and resource record before aggregation.
3. Generate no-debt only after both required kinds exist and the inventories
   are disjoint and equal the frozen union.
4. Run the repository-wide backstop at base `6787...` and candidate. Classify
   each base failure by immutable node ID and raw output; candidate-introduced
   failure count must be zero. A test touched by the candidate cannot be waived
   as an unrelated baseline failure.
5. Run the cross-T1 installed portfolio, three-ticket fixtures, crash/replay
   matrix, effect-boundary spies, package parity and Native S1 mismatch matrix.

Stop on the first hard gate failure. Preserve the failed attempt as historical
evidence, fix on a new commit, and regenerate **all** revision-bound evidence.
Never patch a receipt or resume an old inventory under the new commit.

### Phase 5 — independent recomputation and evidence-only decision

1. Freeze the candidate and evidence tree.
2. A fresh verifier starts from immutable Git objects and external receipt
   bytes, not the producer's in-memory claims.
3. Recompute commit/tree/ancestry, every file digest, selector/inventory union,
   receipt graph, structural fingerprints, package RECORD, runtime/import roots,
   baseline delta, negative cases and the twenty gates above.
4. Run hostile substitutions: forged candidate head/tree, wrong ticket blob,
   omitted source row, duplicate/overlapping shard, stale receipt, swapped
   runtime, fabricated pass boolean, wrong provider/model/session/attempt,
   altered owner identity, missing applicability, unknown effect replay and
   re-signed-but-semantically-invalid records.
5. Emit an independent receipt. Only if all offline rows pass may the Release
   Authority record an evidence-only candidate decision through its real owner
   interface.
6. Leave ticket `01KYSBGR...` open. Hand the exact manifest digest and production
   obligation list to T2.3/T2.5/T2.4, then T2.6. No Git push, cloud build,
   selector change, provider call, runtime promotion or ticket edit occurs in
   T2.2.

## Why current evidence cannot be completed by aggregation alone

It is tempting to combine the many July 31 green shards. That would be false for
four independent reasons:

1. They bind different commits and trees. Exact inventory is revision-bound.
2. Several attempts terminate before complete union and several contain explicit
   failure, skip, debt, mutation or missing terminal receipts.
3. The recovery changes alter admission, model contracts, fixer topology,
   effects, storage, generation, launch and notifications. Those semantics did
   not exist in the old inventory and require new selectors and cross-contract
   tests.
4. Production identity and deployed canary obligations are categorically not
   satisfiable from local receipts.

Historical evidence should seed the regression list and establish baseline
facts. It must never be copied into `final_acceptance` or given
`acceptance_effect=final_acceptance`. The existing validator's explicit
non-promotion tests are correct and should be preserved.

## Present blockers, in order

1. No accepted T1.1–T1.10 portfolio.
2. Current independent hard failures in T1.3, T1.8 and T1.10.
3. No clean integrated descendant of `6787...`.
4. No exhaustive current source-universe disposition.
5. All three narrow stabilization tickets remain open and lack exact integrated
   receipts.
6. No exact recovery-candidate frozen inventory/no-debt union.
7. No exact source/editable/wheel/installed applicability/parity bundle.
8. No exact candidate backstop, generator replay, performance, crash/effect or
   S1 consumer receipt.
9. Legacy `candidate_ready` schema conflates T2.2 with later promotion; a new
   offline state/manifest is required.
10. Production-only obligations intentionally remain for T3/T4/T3.6.

## Read-only custody statement

This preparation inspected Git objects, local worktrees, current report/evidence
files and the local `Arnold-validation-checkpoints` corpus. It ran only read-only
Git, filesystem, JSON and hashing commands. It did not run candidate tests,
contact a provider or cloud endpoint, fetch/push Git, edit tickets/checklists,
change branches/worktrees, start/stop processes, mutate owner state, clean
storage, deploy, or alter any existing evidence. The only persistent write is
this report.

## Final disposition

T2.2 is **not complete**. The historical ledger is useful and the no-debt
mechanics are substantially present, but there is no exact integrated candidate
to which evidence can bind. The finite path is: accept every T1 lane, integrate
once from `6787...`, generate a fresh complete offline bundle, independently
recompute it, record non-authoritative offline candidacy, and leave all
production/ticket authority to T2.6/T3/T3.6.

The SHA-256 of this report is intentionally recorded externally after the final
byte is written; embedding a report's own digest inside itself would be
self-referential.
