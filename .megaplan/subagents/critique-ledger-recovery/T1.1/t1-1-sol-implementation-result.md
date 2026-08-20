# T1.1 Sol implementation result — raw-evidence admission

Status: **implementation candidate committed; not formally complete**.

Formal completion is intentionally withheld. No accepted owner/integration
receipt or production trust-root/backend composition was available, and the
remaining limitations below require owner/integration disposition.

## Ancestry and exact result

- Recovery ancestor: `6787d6363e8fc0603092913ae877db14f3b9fff8`
- Starting `HEAD`: exactly the recovery ancestor
- Implementation commit: `3ed353f8aa3d0df450c563c3cb8d76c87349e32d`
- Tree: `f6c83fca884e9631c7518810ee521d75389815b3`
- Commit subject: `Implement raw-evidence admission boundary`
- Final worktree status: clean (`git status --porcelain` emitted no paths)
- Incident target use: offline fixture/read-only evidence only; no incident
  marker, plan, owner decision, provider, cloud, deployment, or containment
  state was mutated.

## Implemented boundary

- Added persistence-neutral Run Authority admission contracts with closed
  schemas, canonical JSON/digests, duplicate-field rejection, typed target and
  predicate decisions, deterministic request/idempotency/plan identities, and
  exact reservation/reconciliation outcomes.
- Added a visibly non-production local SQLite owner reference backend using
  `BEGIN IMMEDIATE`, unique constraints, exact immutable launch-grant matching,
  owner revisions/fences, exact replay/conflict handling, receipt HMAC checks,
  response-loss reconciliation, and process-safe CAS.
- Added a materialization claim/completion interlock. Authority advancement is
  refused while an exact plan materialization is in flight; the claim is
  completed only after the admission marker and plan state are durably written.
- Added the Megaplan typed `machine_prerequisite` adapter. CL1 v1 derives from
  an exact eight-role content-addressed authority object set:
  reviewer verdict, coherence evidence, proof result, ownership map, portfolio
  decision, amendment record, blocker register, and a checked handoff
  projection. The projection cannot override the raw-role derivation.
- Bound manifest and authenticated receipt hashes, predicate id/version/digest,
  exact target tuple, source/spec/brief/chain identity, deterministic intended
  plan id, installed runtime generation, owner revision/fence, nonce, and
  expiry. Missing, stale, wrong-target, unknown, duplicate/extra, corrupt,
  unreadable, symlinked, partial, throwing, substituted, or mismatched evidence
  rejects closed.
- Moved legacy Git subprocess preflight after evidence evaluation/reservation;
  false/missing admission therefore launches no process. Supervisor and legacy
  paths share the owner boundary; the environment routing flag cannot select a
  weaker prerequisite path.
- Reserved identity is passed explicitly through init. Timestamp naming cannot
  mint a chain successor. Existing directories reconcile only with the exact
  owner marker/state pair; partial or unverifiable materialization is typed
  indeterminate.
- Added pre-materialization denial for dependency-only chain milestones and
  early denial of custom pack runners/drivers on owner-gated specs.
- Added owner checks to shared `load_plan`/`load_plan_locked`, auto, resume,
  finalize, override, phase handlers, step/feedback/user-action CLI routing,
  and contract mode/self-validation mutations. Auto verifies before its local
  engine-default state write.
- Added a static, discovered inventory for every shipped non-Megaplan pipeline
  root and a negative T0.2 fixture proving accepted preservation evidence is
  not live CL1/Run Authority admission authority.

## Changed files

1. `arnold_pipelines/megaplan/_core/state.py`
2. `arnold_pipelines/megaplan/auto.py`
3. `arnold_pipelines/megaplan/chain/__init__.py`
4. `arnold_pipelines/megaplan/chain/prerequisite_admission.py`
5. `arnold_pipelines/megaplan/chain/spec.py`
6. `arnold_pipelines/megaplan/cli/__init__.py`
7. `arnold_pipelines/megaplan/handlers/finalize.py`
8. `arnold_pipelines/megaplan/handlers/init.py`
9. `arnold_pipelines/megaplan/handlers/override.py`
10. `arnold_pipelines/megaplan/supervisor/chain_runner.py`
11. `arnold_pipelines/megaplan/supervisor/driver.py`
12. `arnold_pipelines/run_authority/__init__.py`
13. `arnold_pipelines/run_authority/admission.py`
14. `arnold_pipelines/run_authority_store.py`
15. `tests/arnold_pipelines/megaplan/test_cl2_raw_evidence_admission.py`
16. `tests/arnold_pipelines/run_authority/test_admission_reservation.py`
17. `tests/arnold_pipelines/run_authority/test_non_megaplan_bypass_inventory.py`
18. `tests/fixtures/admission/non_megaplan_pipeline_inventory.json`
19. `tests/fixtures/admission/t0_2_offline_negative_fixture.json`

## Verification performed

- Final focused Run Authority + CL2 + inventory suite: **57 passed**.
- Broad chain/import dependency closure across 29 test modules: **614 passed**
  with 25 pre-existing merge-policy warnings.
- Additional targeted closure runs during implementation:
  - **131 passed** across Run Authority, CL2, chain worktree, and auto suites.
  - **102 passed** across launch-precondition, execution-binding, and CL2 suites.
- Adversarial coverage includes true/false/missing/stale/wrong-target/unknown/
  throwing predicates; raw/projection disagreement; manifest/receipt/verifier/
  runtime substitution; duplicate/extra/corrupt/symlink/partial evidence;
  ENOSPC; stale fence; immutable launch grant; response loss; exact/conflicting
  replay; two threads; two reservation processes; two plan-materialization
  processes; crash after claim/directory; advance-before and advance-after
  claim; deterministic restart identity; 200 observers; legacy/supervisor/
  environment/custom-wrapper/direct-handler denial; marker plus projection
  loss; and non-Megaplan bypass inventory.
- `ruff check` on all new admission implementation/test files: passed.
- `python -m compileall` on implementation/package surfaces: passed.
- `git diff --check` / cached diff check: passed.
- Wheel built and installed without dependencies into an isolated target:
  `arnold-0.23.0-py3-none-any.whl`, SHA-256
  `184095a674ca8e2c75f63883762f03c6faf36bc9244d546473bade3f53aecc96`.
  `python -P` imported Run Authority, owner store, admission adapter, and auto
  from the wheel target. Critical installed/source file hashes matched.
- Installed wheel CLI rejected a dependency-only CL2 spec with
  `machine_prerequisite_missing` and created no `.megaplan/plans` layout.
- Accepted T0.2 hashes retained in the offline negative fixture:
  manifest `c45030bd29c57d1eb0d1694c705aebb3dd55ca04fa3b612ad0d287e32e4dc791`;
  verification receipt
  `5144410224eac921f644d15bdc10a88e123fddb5901c0a92313f8b11d3120f23`.
- Independent read-only Sol review reproduced and drove fixes for caller alias
  CAS, backend target-key recomputation, receipt authentication, runtime/source
  binding, late-fence materialization, pre-reservation Git processes, immutable
  launch grants, raw-role derivation, late custom-driver rejection, shared
  handler gating, auto pre-write gating, and contract mutation gating. Its final
  delta check passed 20 focused regressions and confirmed those fixes.

## Remaining limitations / required owner disposition

1. There is no accepted production Run Authority backend, pinned owner root,
   or owner/integration receipt. The installed production path deliberately
   supplies no trust-root pin and fails closed. A positive installed production
   owner path therefore cannot be proven in T1.1 alone.
2. `LocalSQLiteAdmissionBackend` remains an explicit hermetic test reference
   selected by an internal Python `allow_non_production_backend=True` seam. It
   is nominally rejected by the production constructor and has no production
   attestation, but the independent reviewer correctly identified the public
   test switch as weaker than a separately packaged, unforgeable test
   capability. Owner/integration should remove or capability-seal this seam
   before formal completion.
3. A root milestone with neither `depends_on` nor chain-level
   `prerequisite_policy: required` can still use the generic legacy chain path.
   Dependency-only milestones and required-policy specs reject, including the
   incident-shaped gap, but a platform-wide owner-allowlisted explicit
   no-prerequisite contract is not yet implemented.
4. `ChainState` itself remains revisionless and its historical projection
   persistence remains outside the new owner CAS. Owner reservations prevent
   competing admitted successors from minting distinct plans, but the legacy
   chain projection has not been converted into a full owner-revisioned state
   store.
5. Missing-marker detection uses the deterministic reserved plan-name shape and
   projected metadata when no owner backend is composed. A production owner
   lookup by intended plan identity is pending the production backend.
6. The installed-wheel proof is a build/install/import/hash/negative-entrypoint
   exercise, not a positive installed production-owner initialization, because
   no accepted production owner composition exists.
7. A prior wider repository attempt encountered host ENOSPC in unrelated tests;
   no full-repository green claim is made. The final focused and 614-test chain
   dependency closure above completed green after space recovery.

No T1.1 completion marker, owner decision, integration receipt, incident
resolution, or deployment status was written.
