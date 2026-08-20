# L4 — Immutable runtime/chain binding lineage

1. Question ID and verdict

**L4.** VJ24 cannot legally remain in the same semantic occurrence: the run crossed incompatible runtime/chain bindings without evidence of one accepted, occurrence-bound migration/rebind, so it requires quarantine plus an accepted migration/new attempt.

2. Classification

**Undetermined** for the exact remote rebind producer, but the legal disposition is clear.

Classification: **both** — existing contract violated or bypassed, and required canonical structure absent.

Baseline: [single-authoritative-runtime-history.md](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/custody-control-plane/decisions/single-authoritative-runtime-history.md:158), especially `arnold.megaplan.chain_execution_binding.v1`; supporting C01–C03 in [m10-m11-structural-conformance-closure-20260723.md](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/custody-control-plane/decisions/m10-m11-structural-conformance-closure-20260723.md:26).

3. Scope, files, and identity inventory

Vantage: local checkout plus the captured evidence pack; no SSH or remote mutation. `00-common.md` is absent from the permitted workspace.

Local inspected files:

- [incident evidence](/Users/peteromalley/Documents/Arnold/.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805.md), exists; 9,722 bytes; mtime `2026-08-05T11:12:23Z`; SHA-256 `5553df7b…df21b4a`.
- [Sol stage 1](/Users/peteromalley/Documents/Arnold/.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805-sol-stage1.md), exists; 8,483 bytes; mtime `2026-08-05T11:17:55Z`; SHA-256 `b0c0c358…384fa6a`.
- [binding decision](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/custody-control-plane/decisions/single-authoritative-runtime-history.md:158).
- [binding implementation note](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/custody-control-plane/notes/chain-execution-binding-implementation-20260714.md:24).
- [active chain spec code](/Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/chain/spec.py:1115); exists, SHA-256 `3d991db0…e511e6e`.
- [active chain CLI](/Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/chain/__init__.py); exists, but has no exact binding symbols.
- [active runtime environment](/Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/runtime/execution_environment.py:109); SHA-256 `73bcef68…6d159f`.
- [active cloud launcher](/Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/cloud/cli.py:1767); SHA-256 `c383e7d9…1295e4`.
- [runtime promotion receipt](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/custody-control-plane/evidence/runtime-promotion-receipt.json); exists, but is dated July 14 and binds a different runtime (`/workspace/arnold-custody-runtime`, revision `8f8733de…`), not r5.
- Temporary [cloud-chain fix snapshot](/Users/peteromalley/Documents/Arnold/.tmp/cloud_chain_fix/arnold_pipelines/megaplan/chain/__init__.py) references `execution_binding`, `operator_pause`, and `source_admission`, but those modules are absent from the active checkout and the temporary tree. It is not an adopted implementation.

Remote paths explicitly present in the evidence pack:

- `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold`
- `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold/.megaplan/initiatives/critique-ledger/chain.yaml`
- `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260803-1357`
- `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold/.megaplan/plans/.chains/chain-a5c760402ea2.json`
- `/workspace/runtime-candidates/arnold-wbc-full-20260804`, content SHA `d0fa249a…3e92c7d`
- plan artifacts: `state.json`, `execute_v2_raw.txt`, `plan_v1.meta.json`, `plan_v2.meta.json`, `plan_v2.md`, `execution.json`, `execution_audit.json`, `execute_batch_15_output.json`
- `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260803-1357/execute_batches/batch_15/tasks_35a34c851b8f.json`
- `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold/.megaplan/cloud-chain-critique-ledger-accountability-v3-r5-20260803.log`
- `/workspace/.megaplan/cloud-sessions/critique-ledger-accountability-v3-r5-20260803.liveness-lease.json`
- `/workspace/r5-watchdog-scope-c3b0be1398/watchdog-report.json`
- `/workspace/watchdog-report.json`
- `/workspace/.megaplan/cloud-sessions/repair-data/`

Remote file SHA-256, size, and mtime are not supplied by the evidence pack except for the pinned runtime content SHA and embedded report timestamps; they cannot be reconstructed.

Identities available:

- session: `critique-ledger-accountability-v3-r5-20260803`
- plan: `cl2-wbc-backed-ledger-20260803-1357`
- chain state: `chain-a5c760402ea2`
- source head at launch: `c116f38cc83de11a1a508eff6153205504d1ba5a`
- runtime: `/workspace/runtime-candidates/arnold-wbc-full-20260804`, SHA `d0fa249a…3e92c7d`
- validations: `VJ2`, `VJ8`, `VJ9`, `VJ19`, `VJ24`
- tasks: `T18`, `T23`
- sense checks: `SC18`, `SC23`
- selector: `tests/arnold/critique_ledger/test_replay_v2.py`
- lease: stopped; target PID `610293`; runner fence `11`
- watchdog scope: `r5-watchdog-scope-c3b0be1398`
- run revision, Run Authority fence, Custody occurrence/epoch, WBC attempt/GLEK, repair request/claim, and notification IDs: **not present in the evidence pack**.

4. Exact read-only checks

All commands ran with cwd `/Users/peteromalley/Documents/Arnold`.

| Command | Exit | Relevant result |
|---|---:|---|
| `find /Users/peteromalley/Documents/Arnold -name '00-common.md'` | 0 | No output; file absent. |
| `rg -n 'chain_runtime_binding_drift\|chain_execution_binding_drift\|editable_runtime_import_root_mismatch' arnold_pipelines tests agentbox scripts --glob '*.py'` | 1 | No active implementation hits. |
| `test -e arnold_pipelines/megaplan/chain/execution_binding.py` | 1 | Module absent. |
| `test -e arnold_pipelines/megaplan/chain/operator_pause.py` | 1 | Module absent. |
| `test -e arnold_pipelines/megaplan/chain/source_admission.py` | 1 | Module absent. |
| `rg -n 'identity_digest\|chain_spec_sha256\|runtime_identity' arnold_pipelines/megaplan/cloud/cli.py arnold_pipelines/megaplan/chain/spec.py` | 0 | Active code has short session identity and mutable spec metadata, not the required immutable runtime bundle. |
| `stat …; shasum -a 256 …` on the listed local artifacts | 0 | Metadata and hashes reported above. |

Relevant local excerpts:

- Contract: “Launch-bound fields are immutable”; resume must raise `chain_execution_binding_drift`; rebind requires an “explicit operator-approved, content-addressed migration event.”
- Implementation note: the current implementation “does not mint … an operator-approved rebind event” and does not bind whole-tree diff, wrapper/config/template/schema digests, or process identity.
- Active runtime code describes the engine checkout as “live process context, not a plan-pinned identity.”
- Active cloud code derives `identity_digest` from `slug:seed:labels` using truncated SHA-1 and checks that digest in the marker; it does not bind the complete runtime/source/import vector.

5. UTC timeline

- `2026-08-03T15:40:52Z`: r5 watchdog report: `alive_sessions=0`, `status=repair_unavailable`; requires a claimed repair request.
- `2026-08-03T17:52:40Z`: older generic watchdog reports `alive`, with repair disabled; later contradicted by authoritative-looking stopped lease/blocked plan evidence.
- `2026-08-04T10:24:44Z`, `10:24:54Z`: VJ2 exited `None`.
- `2026-08-04T11:27:18Z`: persistent execute attempt blocked after model work.
- `2026-08-04T15:21:17Z`: VJ8 exited `1`.
- `2026-08-04T16:42:29Z`, `16:44:34Z`: DeepSeek execution unavailable because `DEEPSEEK_API_KEY` was missing.
- `2026-08-04T16:59:49Z`: VJ9 exited `1`.
- `2026-08-04T19:35:41Z`: primary marker last updated; still says `should_run=true`, with no current status/error.
- `2026-08-04T20:30:48Z`: VJ24 rejected the missing task-output selector; plan became/remaining `blocked`.
- Binding refusal order, without event timestamps: expected→active `e5de49a5ead7→117b71d9caf9`; then `chain_spec_sha256` drift with `editable_runtime_import_root_mismatch`; then `117b71d9caf9→cb6afb801753`; then `d0fa249a1310→bf86f59d7417`.
- `2026-08-05`: evidence captured; local evidence pack mtime `11:12:23Z`, Sol stage-1 mtime `11:17:55Z`.

6. Positive and bounded negative evidence

Positive evidence:

- The chain log records multiple typed runtime/execution binding refusals, including import-root mismatch and chain-spec hash drift.
- The later runtime cutover was content-addressed, but the pack provides no accepted migration event joining it to the original occurrence.
- Relaunch used `resume_existing=true` and `chain start --no-git-refresh --no-push`.
- The lease is stopped, no chain/tmux process remains, and VJ24 stopped before T18/T23.
- The pack explicitly says no durable r5 repair request/dispatch exists.

Bounded negative search scope:

- Exact-symbol search covered active `arnold_pipelines`, `tests`, `agentbox`, and `scripts` Python files.
- Binding module existence checks covered the active `arnold_pipelines/megaplan/chain` package.
- No remote source checkout was available for independent code inspection; absence claims about remote modules are therefore not made.

Stale projection versus real drift:

- `should_run=true`, generic watchdog `alive`, and the later marker’s successful verification are projection/observation claims.
- The typed refusal entries and differing expected/active identities are evidence of actual binding disagreement, not merely stale marker text.

7. Strongest alternative

Alternative: the refusal strings were stale projection text from pre-cutover runtime attempts, while the final pinned runtime was coherent.

Falsifier: an authoritative, immutable launch/migration manifest showing exact chain-spec SHA, source revision, runtime content SHA, import root, process identity, and accepted operator migration event, with every VJ19/VJ24 artifact joined to that lineage and the same occurrence.

8. Confidence

**Medium overall; high for the recovery disposition.** The direct refusal identities and explicit baseline contract strongly establish that same-occurrence resume is unsafe. Confidence is reduced only because `00-common.md` and the remote source/runtime artifacts are unavailable for independent verification.

9. Recovery decision

VJ24 should be quarantined with its failed occurrence preserved. Sol should require an accepted migration/new attempt with fresh immutable runtime/chain lineage before any recovery action. A marker, pinned path, or successful launch-verification projection is insufficient.

10. Decision for Sol

Immediate recovery: **do not resume the existing semantic occurrence**. Preserve the blocked cursor and evidence; obtain authoritative Run Authority/Custody/WBC identity and an accepted migration or new-attempt decision.

Durable architecture: adopt one canonical content-addressed launch manifest and append-only rebind/migration transaction covering chain bytes, source/tree, runtime content, import roots, interpreter, wrapper/config, process identity, and occurrence/run revision. The current local launcher’s short marker digest and mutable runtime observation are not sufficient.