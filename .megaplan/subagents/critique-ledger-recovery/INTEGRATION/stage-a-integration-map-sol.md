# Stage-A integration map — Sol read-only analysis

Date observed: 2026-08-02 22:10 CEST  
Common ancestor: `6787d6363e8fc0603092913ae877db14f3b9fff8`  
Verdict: **integration is structurally tractable; preserve exact accepted ancestry and make `handle_finalize` an explicit semantic join**

## Candidate DAG and patch identity

Every frozen commit has merge-base exactly `6787d636...` with every other
candidate. None contains another candidate. Therefore a tip-only cherry-pick is
incorrect: each tip is the last incremental repair in a lane, not a squash of
the complete lane.

| Lane | Exact lineage after `6787d636...` | Net patch from base |
| --- | --- | --- |
| T1.3 accepted | `e0b91992 -> 97904d0f -> ddb764b3 -> fe1786c2 -> 40992256 -> 2f1500ae` | 28 files, +6,519/-1,102. Neutral/ Megaplan contract bundles, model seams, workers, critique/finalize producer binding, package data. |
| T1.5 reviewing | `bf6af7db -> 4bfd5fb2 -> ea7fb2aa` | 98 files, +7,034/-72,064. Canonical `arnold.recovery`, broad legacy fixer/wrapper retirement, CLI and packaging. Do not integrate unless the frozen review accepts the large deletion/retirement set. |
| T1.8 reviewing | `69be0008 -> dae901e9 -> 148465a1 -> 26d24033 -> 06d41e6b` | 26 files, +13,788/-35. New Release Authority package/bootstrap, packaging pins, installed probes and `uv.lock`. Do not integrate until frozen review PASS. |
| RA-CONTAIN locally accepted | `6a4be1aa -> 0b757880 -> eaeca1e7 -> e019cf45 -> a0334cfb -> 611321c7 -> 25dc0265 -> 48648b48 -> 6ef77beb -> fd038f3a -> 6ec80660 -> 78641320 -> 88393e2d -> 48e13e1b` | 6 files, +3,828/-2. `run_authority.containment`, lazy public exports, tests, cryptography dependency/lock. |
| T1.1 provisional only | committed head `3ed353f8` is a direct child of base; current worktree has a further uncommitted repair | Current tracked repair: 14 files, +638/-1,351 relative to `3ed353f8`, binary diff SHA-256 `521bc06cdbd262a5752a82709d723c06f4de6c763cb7c32ac8003756d13a3c80`. Four untracked files add the production owner client/test endpoint. This is an observation, not a candidate identity. |

Observed T1.1 untracked object SHA-256 values:

- `arnold_pipelines/run_authority/owner_client.py`: `f3e93f5c819c8805095a9ce7ea51bd2dee2a224f9388113d981158a3d87dc606`
- `tests/arnold_pipelines/run_authority/conformance_backend.py`: `b18c8977d5621919ee7025d6923aeaf07550d21e2c00936d64c13c984afdaad6`
- `tests/arnold_run_authority_owner/__init__.py`: `c3351ecb8f82ad7c8749dcad8162b193e24ca1fa2a418cea682d8333405c7335`
- `tests/arnold_run_authority_owner/endpoint.py`: `7f2a76fa74031b72d33982481f8fce5387554d4ba410713c80effe81050fa04b`

The dirty T1.1 repair removes the caller-owned backend from
`run_authority_store.py`, adds `AdmissionOwnerClient`, tightens
`resolve_init_authority`/materialization identity, and rewires chain, supervisor,
init/finalize/override admission. Recompute all hashes and overlaps after it is
committed; do not carry these bytes by copy.

## Pairwise overlap/conflict matrix

Classic read-only `git merge-tree` was used against the common base. “Auto”
means textual merge succeeds, not that the combined behavior is accepted.

| Pair | Direct overlap | Merge result / required resolution | Risk |
| --- | --- | --- | --- |
| RA × final T1.1 | `arnold_pipelines/run_authority/__init__.py`; symbols `__all__`, RA `__getattr__`, admission imports | Manual conflict. Union the admission exports with the containment exports; preserve lazy containment loading and do not expose a production-selectable local admission backend. Then prove both packages share the intended owner anchor/incarnation rather than parallel roots. | High authority seam |
| T1.3 × T1.1 | `arnold_pipelines/megaplan/handlers/finalize.py`; `handle_finalize` | Current provisional patch auto-merges, but requires semantic resolution. T1.9 phase claim and T1.1 admission/revalidation must occur before lock/layout/model calls; T1.3 raw capture/binding and T1.2 health precede T1.4 graph admission and any finalized artifact/RA target CAS. | **Highest** |
| T1.3 × T1.5 | `pyproject.toml` | Auto/separate sections: retain T1.5 fixer scripts and T1.3 package-data globs. | Low |
| T1.3 × T1.8 | `pyproject.toml` | Auto/separate sections: retain T1.3 package data and all T1.8 build/dependency/script constraints. | Low |
| T1.3 × RA | `pyproject.toml` | Auto/separate sections. T1.8's later cryptography constraint will supersede RA's minimum. | Low |
| T1.5 × T1.8 | `pyproject.toml`, `[project.scripts]` | Manual conflict. Keep `arnold-simple-fixer`, `arnold-simple-fixer-reconcile`, and `arnold-gen-deploy`; keep T1.8's hatchling/pydantic/dependency-group pins. | Medium packaging |
| T1.5 × RA | `pyproject.toml` | Auto/separate dependency and script sections. | Low |
| T1.8 × RA | `pyproject.toml`, `uv.lock` | Manual conflict. Use T1.8's stricter `cryptography>=42` (it subsumes RA's `>=41.0`) and regenerate one composite lock; never hand-splice the lock. | Medium packaging/runtime |
| T1.5 × T1.1 | No current file overlap | Semantic only: T1.1 launch admission must not reach any T1.5-retired recovery launcher. | Medium bypass |
| T1.8 × T1.1 | No current file overlap | Semantic only: T1.1 owner endpoint/generation must be installed and attested by T1.8, never selected by caller config. | Medium authority |

All four committed lanes touch `pyproject.toml`; only RA and T1.8 touch
`uv.lock`. Resolve `pyproject.toml` once as a union, regenerate the lock once
after the last base-lane merge, then treat both files as frozen inputs to wheel
qualification.

## Safest integration order

### Preserve evidence ancestry

Use a clean integration branch rooted at `6787d636...` and merge accepted exact
tips with explicit merge commits. This makes the integration commit a real
descendant containing every accepted candidate commit. Do **not** rebase an
already accepted/reviewed lane, and do not cherry-pick only its tip.

Recommended order:

1. Merge exact RA-CONTAIN `48e13e1b...`.
2. Before T1.1 is frozen for review, replay/rebase its current repair onto
   `48e13e1b...`, resolve the public export/owner-root seam, and accept that new
   clean descendant. Then fast-forward/merge that final T1.1 lineage. The
   present dirty worktree is not integrable evidence.
3. Merge accepted T1.3 `2f1500ae...`; manually adjudicate the semantic order in
   `handle_finalize` even if Git reports an automatic merge.
4. Merge T1.5 `ea7fb2aa...` only after its current independent review PASS.
   Preserve the retirement/deletion set; conflict resolution must not resurrect
   a copied fixer, watchdog, resident or direct repair writer.
5. Merge T1.8 `06d41e6b...` only after review PASS. Resolve the script union,
   retain its stricter build/runtime pins, regenerate `uv.lock`, and record the
   resulting composite package vector.

If linear history is mandatory, cherry-pick each **full range** oldest-to-newest
in the same lane/order and record an old-to-new commit map in the integration
manifest. That is less safe because exact accepted ancestry is lost. Rebase is
appropriate only for the not-yet-frozen T1.1 repair; it is not appropriate for
the accepted/frozen candidate tips.

## Dependent-layer order and cycle break

Do not build T1.2/T1.4/T1.6/T1.9 as new independent branches from the common
ancestor. Base every dependent commit on the frozen composite above. Split the
T1.6/T1.9 circular dependency explicitly:

1. **T1.9 contract-only commit:** add strict launch/effect/stop request records,
   golden vectors and ports only. No owner service, provider adapter, CLI or
   production execute. This gives T1.6 exact upload/start/observe/stop shapes.
2. **T1.6 neutral-core commit:** add the append-only effect reducer, capability
   registry, sticky `INDETERMINATE`, no-redispatch semantics and exact
   registered capability protocols. No legacy fallback.
3. **T1.2 route commit:** layer on accepted T1.3 plus the T1.6 model-effect port;
   add typed attempts/exact selected-set reduction and make gate consume only an
   admitted round. It must not reopen T1.3 capture or mint transport identity.
4. **T1.4 route commit:** layer on T1.2/T1.3/T1.6; add stable graph fingerprint,
   terminal rejection or one narrow repair, full re-admission and zero generic
   retry/reset/revise authority. Resolve `handle_finalize` against the explicit
   ordering below.
5. **T1.6 production-closure commit:** migrate the one model route, exact
   upload/start/stop, one T1.5 fixer and one accepted T1.10 notification port;
   install the unavailable-family registry and bypass inventory. T1.6 is not
   accepted before this join passes.
6. **T1.9 transaction/runner commit last:** consume final T1.1/T1.5/T1.6/T1.8
   ports and T1.2/T1.3/T1.4 runtime receipts; add owner transaction, reservation,
   exact replay/expiry/stop, finite runner and installed CLI. It may not repair
   any dependency boundary.

Required `handle_finalize` order in the composite:

```text
T1.9 process-bound phase claim / current-head recheck
-> T1.1 target-bound materialized-plan admission revalidation
-> local plan lock/load
-> T1.6 model-effect intent + sole dispatch
-> T1.3 authenticated raw capture/bundle binding
-> T1.2 terminal attempt health + exact-set receipt
-> T1.4 graph admission or one WBC-owned narrow repair + full re-admission
-> compute/freeze the final payload and artifact digest without publishing it
-> precommit and perform the exact T1.9/RA target-transition CAS
-> on exact accepted/replayed receipt, publish only the pre-bound artifacts/projections
-> T1.9 fence/stop saga
```

No formatting-only conflict resolution may move any effect ahead of its owner
claim or accept status/latest-file evidence in place of a receipt.

## Focused qualification after each seam

Run large suites single-flight because the active state records local ENOSPC
risk.

| Seam | Minimum focused qualification before adding the next layer |
| --- | --- |
| RA alone | `tests/arnold_pipelines/run_authority/test_containment.py`, `test_contracts.py`, `test_reducer.py`; exact stale-anchor, operation-receipt replay and concurrent-observer probes. |
| RA + final T1.1 | All RA tests plus `tests/arnold_pipelines/run_authority/test_admission_reservation.py`, `tests/arnold_pipelines/megaplan/test_cl2_raw_evidence_admission.py`, `tests/arnold_run_authority_owner/`, chain launch/worktree safety, direct init/finalize/override denial, 2/200 initializer/observer cases, source and installed owner lookup. |
| + T1.3 | `tests/arnold/pipeline/test_contract_bundles.py`, `test_model_seam_neutral.py`, `tests/arnold_pipelines/megaplan/test_contract_bundles.py`, model-seam recovery, real producer fixtures, critique/finalize promotion and worker adapter tests. Add one integration probe proving T1.1 rejects before `_run_worker` and T1.3 writes, while admitted finalize binds only the exact owner-authenticated receipt. |
| + T1.5 | Canonical simple-fixer/retirement suites, `tests/cloud/recovery_retirement_contract.py`, simple-fixer retirement, source-initiative/manual/meta repair denial, wrapper-authority bypass, watchdog/managed-agent/fix-the-fixer tests, fresh wheel scripts. Scan for newly resurrected normally importable writers. |
| + T1.8 and packaging join | Entire `tests/arnold_pipelines/release_authority/`, installed release-authority entrypoint/probes, RA cryptographic vectors under `cryptography>=42`, lock check, clean wheel contents/import, source/wheel/`python -P` parity and rollback wrong-target replay. |
| + T1.9 contracts / T1.6 core | Contract golden vectors, strict parsing/forgery tests, `tests/arnold/workflow/test_stage_a_effect_dispatcher.py` core reducer/crash/response-loss subset; no production raw call yet. |
| + T1.2 | `test_critique_attempts_stage_a.py`, installed critique parity, existing parallel-critique/custody/gate suites, T1.3 source/installed parity; six failures and provider ACK loss must create no semantics and no fallback. |
| + T1.4 | `tests/orchestration/test_finalizer_repair.py`, `test_v3_finalizer_route.py`, installed finalizer repair, handler/model-seam/boundary receipt/workflow composition suites; new combined T1.1/T1.2/T1.3/T1.4 finalize-order probe. |
| + T1.6 production closure | Stage-A dispatcher full matrix, `tests/integration/test_effect_boundary_closure.py`, common-worker WBC, exact upload/process adapters, T1.5 immediate/reconciler race, accepted T1.10 one-send/200-silent scans, source/wheel/materialized wrapper capability inventory. |
| + final T1.9 | The complete v2 T1.9 launch suites: authority provenance, GO join, reservation saga, every owner/provider crash boundary, target-CAS later-history replay, expiry/boot discontinuity, exact stop, 2/200 concurrent launch/reconcile, finite budget, bypass closure and installed parity. Then run isolated `admit -> run -> verify`; owner receipts—not marker/log/status—are the oracle. |

After every seam, record exact integration commit/tree, component ancestry,
resolved-conflict diff, test command/result digest and package vector. A green
component suite before the merge is not evidence for the joined seam.

## Single riskiest conflict

`arnold_pipelines/megaplan/handlers/finalize.py::handle_finalize` is the single
riskiest conflict. Git currently auto-merges T1.1 and T1.3, which makes it easy
to miss the semantic hazard: a misplaced admission/phase guard can allow a
model call or T1.3 transcript/artifact write before current owner admission, or
a later T1.4 repair can bypass T1.2 health and T1.9's one-target budget. Treat
this function as a hand-built ordered join and require the combined hostile
probe before accepting the integration commit.

No worktree, Git object/ref/index, source, cloud/provider, owner, checklist or
session was mutated. This integration map is the sole artifact write.
