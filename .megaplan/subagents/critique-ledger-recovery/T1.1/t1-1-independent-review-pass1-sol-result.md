# T1.1 raw-evidence admission — independent review pass 1

## Verdict: HARD FAIL

The candidate does not satisfy the review claim that every production materialization and mutation path is admitted from the exact raw eight-role authority set through an owner-authenticated decision and deterministic CAS/reconciliation boundary.

Four ordinary shipped-code bypasses/fail-open cases are present:

1. A normal Python caller can select the shipped hermetic SQLite backend, install its own verifier key and launch grant, optionally replace the predicate deriver, and obtain an accepted reservation by passing a plain boolean.
2. A root milestone with no `depends_on` and the default `prerequisite_policy: none` is expressly admitted to the legacy materialization path without CL1/Run Authority.
3. Direct `init`/control materialization remains generic and does not determine whether the selected brief is an owner-gated chain milestone, so an ordinary caller can bypass the chain admission path rather than reserve the protected target.
4. Removal/rollback of both the admission marker and projected metadata, combined with restoration under a non-deterministic plan-directory name, makes admission enforcement return “generic plan” without consulting the owner at all.

These are within the incident threat model. They require neither interpreter takeover nor mathematical impossibility. The fourth is the exact missing-marker/replacement-directory/state-rollback condition requested by the review brief. The failed probe involving a symlinked macOS temporary directory is explicitly excluded from the decision.

This report does not claim formal T1.1 completion. Deployed owner/integration receipts and production composition remain separate.

## Exact candidate reviewed

- Parent/base: `6787d6363e8fc0603092913ae877db14f3b9fff8`
- Candidate commit: `3ed353f8aa3d0df450c563c3cb8d76c87349e32d`
- Candidate tree: `f6c83fca884e9631c7518810ee521d75389815b3`
- Candidate diff: 19 files changed, 4,646 insertions, 34 deletions
- Worktree at inspection: clean (`git status --short` emitted no paths)
- Implementation report reviewed: `/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.1/t1-1-sol-implementation-result.md`

## BLOCKER 1 — caller-selectable hermetic backend mints accepted authority

`LocalSQLiteAdmissionBackend` is shipped in the production package and has a public constructor (`arnold_pipelines/run_authority_store.py:164-181`). Its public `initialize_authority` accepts caller-chosen run identity, authority revision/fence, exact launch-grant digest, verifier ID, and verifier key (`arnold_pipelines/run_authority_store.py:274-329`). Receipt authentication then trusts that caller-installed key (`arnold_pipelines/run_authority_store.py:331-354`).

The production admission adapter accepts that backend solely when the ordinary boolean `allow_non_production_backend=True` is supplied (`arnold_pipelines/megaplan/chain/prerequisite_admission.py:606-616`). The same backend-plus-boolean condition permits a caller-provided `predicate_allowlist`; the supplied deriver is used to produce the predicate decision (`arnold_pipelines/megaplan/chain/prerequisite_admission.py:337-435,619-655`).

This switch is threaded through ordinary shipped APIs, including legacy chain execution (`arnold_pipelines/megaplan/chain/__init__.py:6439-6455,6515-6525,7495-7591`), supervisor execution (`arnold_pipelines/megaplan/supervisor/chain_runner.py:306-323,372-410,532-580`), auto (`arnold_pipelines/megaplan/auto.py:6614-6660`), and supervisor requests (`arnold_pipelines/megaplan/supervisor/driver.py:42-57,94-106`). Packaging includes `arnold_pipelines`, so the seam is also installed-wheel code (`pyproject.toml:89-90`).

The committed positive fixture demonstrates the exploit composition: it computes the request digest, installs that digest and its own verifier key into the local backend, calls admission with the boolean, and materializes through the same seam (`tests/arnold_pipelines/megaplan/test_cl2_raw_evidence_admission.py:265-329,721-759`). The focused suite confirmed that accepted path remains live. A separate non-writing probe confirmed that the boolean changes a nominal local backend from rejected to accepted by `_backend_for_use`.

Defaults of `False` and absence of a CLI flag do not capability-seal an ordinary Python API. The hermetic backend and its authority-initialization helpers must be separately packaged or guarded by a capability that shipped callers cannot forge.

## BLOCKER 2 — root milestones silently bypass CL1/Run Authority

`ChainSpec.prerequisite_policy` defaults to `none` (`arnold_pipelines/megaplan/chain/spec.py:927-955,1070-1075`). `validate_materialization_prerequisites` demands `machine_prerequisite` only when the chain policy is `required` or the milestone has a nonempty `depends_on` (`arnold_pipelines/megaplan/chain/spec.py:1188-1199`). There is no explicit owner-allowlisted no-prerequisite contract.

Both production runners invoke that validator, but reserve only when `machine_prerequisite is not None` (`arnold_pipelines/megaplan/chain/__init__.py:6460-6525,7495-7511`; `arnold_pipelines/megaplan/supervisor/chain_runner.py:340-410,532-580`). Otherwise the legacy runner calls `_init_plan` with no reservation/admission context (`arnold_pipelines/megaplan/chain/__init__.py:7561-7591`), and the supervisor default pack runner likewise prepares the plan without owner authority.

Minimal non-writing reproduction:

```text
case 1: {milestones: [{label: root, idea: root.md}]}
result: ACCEPTED_WITHOUT_MACHINE_PREREQUISITE

case 2: same milestone with prerequisite_policy: required
result: CliError machine_prerequisite_missing
```

The first case is an ordinary launch bypass. Platform-wide policy cannot interpret absence as authorization; a root milestone needs an explicit owner-allowlisted no-prerequisite decision.

## BLOCKER 3 — direct handler/control initialization bypasses the protected chain target

The shared `_init_plan` accepts `reserved_successor=None` and `admission_context=None`. In that case it invokes ordinary installed `megaplan init` rather than the typed owner path (`arnold_pipelines/megaplan/chain/__init__.py:388-409,421-478`). `handle_init` only revalidates and claims when hidden reservation/context attributes are present; otherwise it creates the plan directory and state through the generic path (`arnold_pipelines/megaplan/handlers/init.py:455-528,538-626`).

There is no lookup from the supplied idea/brief path to an owner-gated chain target before this materialization. Other shipped callers also reach generic `handle_init`, including the control-plane sprint adapter (`arnold_pipelines/megaplan/control.py:399-424`) and the deployed workflow-canary helper (`arnold_pipelines/megaplan/cloud/m11_workflow_canary_runner.py:225-236`). The canary itself is not treated as an authority violation; the blocker is that the same generic path can select a brief declared by a protected `machine_prerequisite` spec without detecting or reserving that target.

This is not a demand to put all generic Megaplan work behind CL1. It is a narrowly scoped identity/lookup requirement: a materialization request matching an owner-gated milestone brief/spec must not be able to discard that target identity merely by entering through direct `init`, a wrapper, or a control handler.

## BLOCKER 4 — missing marker plus rollback/rename downgrades owner truth to “generic”

`enforce_materialized_plan_admission` treats a missing marker as owner-gated only when `state.json` still projects `meta.admission_reservation` or the directory name matches the deterministic owner-ID regex (`arnold_pipelines/megaplan/chain/prerequisite_admission.py:866-903`). The owner is consulted only after that branch, when a marker exists (`arnold_pipelines/megaplan/chain/prerequisite_admission.py:904-912`).

The shared mutation boundary depends on that function (`arnold_pipelines/megaplan/_core/state.py:339-350,900-910`), including execute (`arnold_pipelines/megaplan/handlers/execute.py:686-704`). Therefore a restored/replaced admitted plan directory can be downgraded to generic by all three of the conditions explicitly called out in the brief: marker loss, projection rollback, and replacement/rename of the directory.

Minimal reproduction created an admitted-shaped directory, renamed it to `restored-plan`, removed the marker, rolled `state.json` back to empty metadata, and passed an owner spy:

```text
admission_result= None owner_lookup_calls= 0
```

That is a false success at the admission boundary: owner truth is not merely unavailable; it is never queried. Production absence or lookup failure must reject closed, and intended-plan identity must be reconcilable independently of mutable marker/projection state.

## Commands and observed counts

The review used finite, single-flight commands only:

1. `git status --short` and `git rev-parse HEAD HEAD^{tree} HEAD^`
   - clean status;
   - exact commit/tree/parent matched the identities above.
2. `git diff --stat` and `git diff --name-status 6787d6...3ed353f`
   - 19 changed paths; 4,646 insertions; 34 deletions.
3. Focused `rg`/`nl` inventories over admission, chain, supervisor, auto, CLI, handlers, store, and tests.
   - 32 shipped occurrences of the non-production admission switch across 7 Python files in the focused switch inventory;
   - 2 production runner call sites for `validate_materialization_prerequisites`;
   - 0 explicit shipped owner/no-prerequisite allowlist contracts found.
4. `pytest -q tests/arnold_pipelines/megaplan/test_cl2_raw_evidence_admission.py tests/arnold_pipelines/run_authority/test_admission_reservation.py tests/arnold_pipelines/run_authority/test_non_megaplan_bypass_inventory.py`
   - **57 passed in 7.51s**.
5. Non-writing root-policy Python probe.
   - 1 default root accepted without a machine prerequisite;
   - 1 required-policy root rejected with `machine_prerequisite_missing`.
6. Temporary marker/projection rollback and owner-spy probe.
   - admission result `None`;
   - owner lookup calls: 0.
7. Isolated wheel build/install/import/hash comparison.
   - wheel SHA-256: `184095a674ca8e2c75f63883762f03c6faf36bc9244d546473bade3f53aecc96`;
   - 5 of 5 critical installed files matched source bytes: admission contract, owner store, prerequisite adapter, chain spec, and init handler.

One attempted end-to-end direct-init probe is not evidence for any blocker: fixture setup rejected the SQLite database path because the host temporary-directory ancestry contained a symlink. It exited before admission or materialization. That environment artifact is excluded; no claim is based on it.

## Eight-role, CAS, parity, and preservation findings

Within the focused tests, the typed evaluator correctly requires the exact eight roles and rejects role-set mismatch, duplicate role/path/digest aliases, unknown fields, target mismatch, corrupt/truncated/partial content, symlinked evidence, stale evidence, substituted manifest/receipt/runtime, and projection disagreement. The raw derivation at `arnold_pipelines/megaplan/chain/prerequisite_admission.py:72-83,246-328` does not let the handoff projection override the other seven roles.

The SQLite reference backend has meaningful deterministic request, immutable launch-grant, reservation, exact replay/conflict, fencing, claim/completion, and response-loss reconciliation tests. Those properties do not cure BLOCKER 1 because the caller controls the nominal owner/key/grant when the boolean seam is enabled.

Installed/source parity was independently confirmed for the five critical files, so the blockers are present in the built wheel rather than being source-only artifacts.

The T0.2 preservation hashes remain in an offline negative fixture, with both `cl1_machine_handoff_present` and `run_authority_owner_record_present` false. The focused negative test verifies that this fixture cannot parse as a live `RawEvidenceManifest`. No preservation-evidence-as-live-authority success was reproduced.

## Nonblocking limitations

1. No accepted production owner backend, immutable production trust-root pin, or deployed integration receipt exists in this candidate. Current installed production composition fails closed. That is an integration prerequisite and prevents a positive production proof, but it is not itself a false-success blocker.
2. `ChainState` remains revisionless. More importantly, the field named `chain_state_sha256` is derived from a small static target tuple rather than the supplied `ChainState` object (`arnold_pipelines/megaplan/chain/prerequisite_admission.py:518-554`). This leaves stale/rollback semantics under-specified. The focused suite did not reproduce a second deterministic plan identity or duplicate side effect from this fact alone, so it is recorded as a nonblocking limitation rather than an additional blocker; BLOCKER 4 covers the reproduced rollback fail-open.
3. The non-Megaplan inventory is a useful static tripwire and matched the three discovered non-Megaplan roots in the focused suite, but token scanning is not a complete dynamic/import-alias proof. No separate non-Megaplan false-success path was reproduced.
4. The wheel check proves byte parity and importability, not a positive installed production-owner launch. The latter remains dependent on owner integration.
5. No full-repository green claim is made. The independent decision relies on the 57-test focused suite and finite hostile probes above.

## Required disposition

HARD FAIL this candidate for T1.1 admission. At minimum, capability-seal or separately package the hermetic backend and predicate override; require an explicit owner-allowlisted no-prerequisite contract for roots; bind protected target identity across direct/wrapper/control init paths; and make missing-marker/replacement reconciliation consult owner truth and reject closed.

Do not mark T1.1 complete from this report. Production owner composition and deployed integration receipts remain separate acceptance evidence.

Report-body SHA-256 (UTF-8 bytes preceding this line, including the immediately preceding newline): `fb3ae3d2839bccc8b5eb9e2c72f1fa6006d4f1c6caaa1f2a82213d2145c7f55f`
