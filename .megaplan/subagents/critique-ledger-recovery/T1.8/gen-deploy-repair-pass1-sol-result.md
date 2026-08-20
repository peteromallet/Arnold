# T1.8 GEN-DEPLOY — Sol repair pass 2 result

## Candidate identity

- Reviewed base: `69be00087f0d469b1e551fa8617c257f28783b7a`
- New review candidate: `dae901e9bf2ecf289ad0aa201c50116f8bf1f899`
- Commit subject: `repair GEN-DEPLOY authority boundaries`
- Worktree after commit: clean
- This is a review candidate only. It does not claim formal T1.8 completion or production availability.

## Repairs completed

1. Production authority is fail-closed. `owner-installed` store construction and offline receipt verification return typed `production_authority_integration_missing`; no caller JSON, same-UID file, metadata, key, root, adapter object, path, environment variable, or process registry can create production authority. The data-only external contract pins venue/domain/target/store/lock/root/WAL/SHM identities, protected ancestry, trust/custody/executor/observer keys, authenticated peer/channel/adapter identity, full descriptor lifetime, and privileged discovery/provisioning signatures. No shipped API accepts the record as a capability.
2. Every external effect is preceded by durable intent. Error, response loss, missing/invalid receipt, or unproven reconciliation after effect attempt can never terminalize rejection. In-process NOT_APPLIED assertions can drive exact idempotent replay but are not independent proof; otherwise the result is indeterminate. All eight deployment operations, including bootstrap materialization, have effect-then-error and effect-then-invalid-receipt regressions.
3. Recovery has an explicit store/target/result transition table, prevalidated before effects. Rollback and forward-fix use durable intent, fresh live selector/fence/runtime/writer checks, response-loss reconciliation, exact signed replay, crash hooks, and idempotent completion. Rollback target state and replay receipt are one atomic hermetic JSON update. Cached receipts are never accepted without fresh target agreement.
4. Offline custody is authenticated by a separately pinned Ed25519 custody key. The signed root covers authority/store/trust/envelope/decision/effect digests, complete ordered event head/count/digest, selector/revision/fence, writer identities, authorization and terminal times, exact terminal outcome, and bootstrap retirement. Verification checks event ordering, intent/effect lineage, current-envelope temporal bounds, exact terminal payload semantics, and complete root reconstruction. Recomputed event/root tampering fails without the pinned key; even legitimately re-signed semantically invalid terminal or temporal histories fail.
5. Production observation remains unavailable unless a future privileged venue returns fresh challenge-bound evidence signed by the pinned observer/executor identity. Duck-typed/stale observers are rejected. The production contract now defines the complete signed effect-observation shape for APPLIED/NOT_APPLIED/UNKNOWN reconciliation.
6. The declared Pydantic range is `>=2.11,<3`; the lock resolves 2.12.5. A dependency-safe stdlib bootstrap produces typed startup failure when dependency import fails. Isolated minimum-2.11.0 and locked-2.12.5 environments have no system site-packages and prove canonical bytes, digests, fixed Ed25519 signatures, schemas, round trips, CLI execution, and module origins. The locked runtime and exact-pinned Hatchling build backend are installed/built from lock-exported hashes with hash enforcement.
7. The name-mangled permit and unforgeability claim were removed. Shipped mutations are explicitly hermetic; production mutation requires a future opaque service-held capability outside the caller address space.
8. Hermetic filesystem defense uses protected directories, no-follow opens, regular-file/link-count checks, pinned device/inode identities, store revalidation, a stable parent-directory lock plus lock-file lock, and exit revalidation. Symlink, hardlink, unlink/replace, active-holder replacement, and two-process exclusion regressions pass. These are hermetic defenses, not a claim that Python can protect production from a same-UID attacker; the external contract requires privileged descriptor custody and prevention of ancestor/object replacement for the complete session.

Additional completeness repairs include authenticated external adapter identity in the production binding; production `resolve`, `deploy`, and `verify` failure before store/input touch; one `PUBLIC_CONTRACTS` registry driving both validation and schemas, including decision/custody/observation wire models; isolated hash-locked wheel proof; and same-directory temp/write/file-fsync/replace/directory-fsync atomic JSON output with controlled pre- and post-rename failure tests.

## Exact validation results

- `uv run pytest -q tests/arnold_pipelines/release_authority`
  - `139 passed in 7.61s`
- Focused repair/execution/security run during final repair:
  - `90 passed in 4.70s`
- Final temporal/terminal probes (second-generation receipt, predating event, terminal payload):
  - `3 passed in 0.38s`
- Independent final effect/recovery re-probes:
  - `116 passed in 9.62s`
  - forged NOT_APPLIED => indeterminate, never rejected
  - rollback crash => exact replay resolved
  - unauthorized revision 99 => rejected before target effect
  - stale cached receipt after target drift => indeterminate, unresolved
- `uv run pytest -q tests/installed_wheel/test_release_authority_entrypoint.py`
  - `5 passed in 58.58s`
  - isolated Pydantic 2.11.0 minimum and locked 2.12.5
  - hash-required locked runtime artifacts and hash-constrained exact-pinned build backend
- `uv run pytest -q tests/characterization/test_import_surface.py tests/test_pipeline_run_cli.py`
  - `78 passed in 3.94s`
- Static and packaging controls:
  - Ruff: `All checks passed!`
  - `python -m compileall`: passed
  - `uv lock --check`: `Resolved 84 packages in 4ms`
  - `uv pip check`: `Checked 76 packages in 2ms` / `All installed packages are compatible`
  - `git diff --check`: passed
- Three scoped final adversarial re-reviews reported no remaining blocker after the last temporal fix.

## Remaining external integration limitations

Production is deliberately and typed unavailable. This candidate ships no privileged provisioner, authenticated discovery channel, opaque production mutation session, production SQLite descriptor/sidecar custody service, production executor, production observer, production receipt signer, or venue trust-root installation. The signed production observation/effect and filesystem contracts are precise integration requirements, not local facsimiles. Until an external venue implements and independently validates those contracts, `owner-installed` mutation, verification, recovery, and offline custody verification must continue to fail closed.

No deployment, SSH, cloud mutation, or master-checklist edit was performed.
