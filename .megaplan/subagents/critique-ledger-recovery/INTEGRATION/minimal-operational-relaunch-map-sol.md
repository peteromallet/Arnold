# Minimal operational relaunch map — Sol

Date: 2026-08-02  
Posture: read-only operational cut; no checklist-completion claim  
Decision: **four bounded code changes, then one serial deploy/fence/launch canary**

## Controlling state and outcome

Use these inputs as controlling:

- RA-CONTAIN local substrate `48e13e1bcbc6769aff753270331d52ac1c148125`.
- Root-accepted T1.8 `06d41e6b7148db4e5b464131762d63fd697db056`,
  tree `a8a67b2e01b9129673afdc7931cb3ffdce03a2de`.
- Independently accepted T1.9 v2 specification
  `T1.9/t1-9-stage-a-implementation-delta-v2-sol.md`, SHA-256
  `9a604b05637d2f9eba54db6a6f42e488e2d2979105a6b0d1d6dcb5665688ad11`;
  it is a specification, not code or launch authority.
- T1.5 pass 3 is the sole current mutation lane. Its result is not integrable
  until a fresh independent review accepts the exact commit/tree.
- The exact gated-stall/notification patch begins only after accepted T1.5 and
  must be based on that frozen interface.

The canary proves only this operational proposition:

> one installed generation maps the exact unchanged `gated/finalize ->
> manual_review` incident state to one durable occurrence, at most one ordinary
> fixer and one initial notification; permanently fences v2; starts one fresh
> v3 runner through T1.9; accepts an owner cursor strictly beyond v2's old
> stall; and closes the launch envelope before execute or publication.

It does not prove semantic CL2 correctness, authorize execution/publication, or
complete the broader recovery checklist.

## Direct-causal gate only

| Work | Canary disposition | Causal reason |
| --- | --- | --- |
| T1.5 operational slice | **Must integrate** | The observed loop lacked one canonical occurrence/result and trusted ordinary fixer path. Pass 3 must reject coordinated result+receipt substitution and bind exact resident provenance/one-shot execution. |
| Exact stall handler | **Must implement** | The unchanged gated/manual-review observation must converge to the same T1.5 occurrence instead of reopening/relaunching. This is a narrow incident-state adapter, not generalized graph repair. |
| Notification transition slice | **Must implement** | The incident produced 201 duplicate DMs because blank pre-provenance state and direct fallback were repeatedly treated as new work. Identity-before-provenance, one durable intent/outcome and 200-scan silence directly close it. |
| T1.8 | **Accepted; must integrate/deploy** | Exact generation selection, rollback/forward-fix and live-vector attestation are required before any recovery/launch process is trusted. |
| T1.9 operational implementation | **Must implement** | It is the sole one-upload/one-start/exact-stop authority and prevents `--fresh`, tmux, watchdog or response-loss relaunch. |
| RA-CONTAIN/v2 fence | **Must integrate/use** | A late v2 writer/effect would invalidate any v3 observation. |
| T1.1 | **Defer** | Generic raw-CL1 admission is not consumed. This single canary uses one owner-signed, exact v3 seed/spec/identity decision and grants no broader admission authority. |
| T1.2 | **Defer** | Critic completeness is semantic release hardening. The operational canary makes no clean-round or feature-correctness claim; any inability to reach the target safely stops and is not success. |
| T1.3 | **Defer despite local acceptance** | Authenticated model-output custody is not needed to prove one process/occurrence/notification/cursor transaction. Model output remains nonauthoritative for broader work and the envelope closes before execute/publication. |
| General T1.4 | **Defer** | Only the exact existing `gated/finalize -> manual_review` transition-to-occurrence adapter is causal. No model graph repair, retry or budget generalization enters this candidate. |
| Universal T1.6 | **Defer** | Implement only the exact effect ports consumed here: T1.9 upload/start/observe/stop and one incident notification intent/send/reconcile. Do not claim platform effect migration or enable any other family. |
| T1.7 | **Defer** | T1.5/T1.8/T1.9/notification owner-local stores must pass their own crash/concurrency/corruption tests; no generic store migration is consumed. |
| Full T1.10 | **Defer** | Key rotation, reminders, chunks, auxiliary writers and platform UX are not needed. The installed operational route must nevertheless have no direct fallback and must dedupe one initial transition. |

The one-route model call is pinned by the release manifest with no fallback, but
this canary does not treat its content as semantic acceptance. Unused effect
families are unavailable in the installed canary generation.

## Remaining code sequence

### C1 — accept T1.5 pass 3

The exact pass-3 commit may enter integration only if independent probes prove:

- coordinated result plus receipt substitution returns typed unknown/conflict,
  never forged projected bytes and never redispatches;
- the exact resident provenance tuple is bound before ordinary execution;
- the ordinary imported fixer path invokes only the canonical owner endpoint;
- immediate trigger and reconciler converge on one occurrence/claim/result;
- missing/wrong provenance is one terminal non-claimable result, not a child,
  fallback agent or alternate scheduler; and
- the prior passing point-of-use retirements remain intact.

The recut does not wait for restoring every historical 741 assertion. It does
require hostile proof over every normally reachable operational resident/fixer
entrypoint in the installed candidate.

### C2 — one exact incident stall/notification commit

Build on accepted T1.5. Do not cherry-pick T1.10 commit `0c3d6620...` wholesale;
its broad candidate has known owner/supervision/runtime/direct-writer gaps. Port
only the operationally needed shape:

1. Derive one stable occurrence from exact session, plan, installed generation,
   owner cursor/state version and `gated/finalize/manual_review` transition.
2. Persist occurrence and diagnostic-attempt identity before resident
   provenance validation.
3. Resolve provenance. Missing/malformed data writes one terminal typed result
   against that occurrence and cannot request direct fallback delivery.
4. Invoke the T1.5 ordinary fixer at most once under the same occurrence; an
   unchanged observation only reads/reconciles its current result.
5. Persist one notification intent keyed by occurrence plus meaningful state
   version before provider entry. Use one fixed installed provider adapter and
   immutable bytes. Provider response loss is sticky possibly-applied and is
   never resent without authoritative exact reconciliation.
6. Two processes and 200 unchanged observations create no second occurrence,
   fixer claim, notification intent or provider call. A genuinely changed state
   version may create the next transition; prose/timestamp/observer changes may
   not.

Expected files are the accepted T1.5 owner seam plus the narrow subset of
`cloud/human_review_diagnostic.py`, `cloud/incident_notification.py`,
`cloud/notification_worker.py`, fixed production adapter/worker wiring,
`resident/runtime.py`, the installed notification wrapper and focused tests.
The old watchdog/progress/repair-loop wrappers must stay retired; do not merge
notification code back into them.

### C3 — bounded T1.9 implementation

Implement the accepted v2 spec against only these frozen operational ports:

- RA containment/fence/current cursor;
- T1.5 occurrence/topology and the C2 incident transition owner;
- an owner-local narrow effect port for exact upload/start/observe/stop only;
- T1.8 installed generation/attestation/process observer; and
- one owner-signed canary seed, fresh identities, target cursor, TTL and
  longer-lived cleanup-only stop capability.

Production `execute` must still implement v2's exact authority provenance,
owner-operation replay, cross-owner stop saga, no redispatch after `STARTED`,
clock/boot expiry rules, collisions, one runner, raw-launch denial and
independent `SUCCEEDED_CLOSED` verification. Omit the v2 GO-manifest fields for
deferred T1.1/T1.2/T1.3/universal-T1.6/T1.7 from the positive GO join: preserve
the canonical schema, but record each as typed
`NOT_CONSUMED_OPERATIONAL_CANARY` with no capability or completion claim. Add an
owner-signed `operational_canary_only=true` decision whose allowed effects are
exactly one input upload, one runner start, the pinned model route, the C2
fixer/notification transition and one exact stop. It contains no execute or
publish capability, and the verifier rejects any attempt to treat the typed
deferred rows as authority.

### C4 — clean integration/packaging commit

Create one clean descendant of `6787d636...` containing exact accepted
RA-CONTAIN, T1.8, final T1.5, C2 and C3 commits. Resolve only composition:

- `pyproject.toml`: keep T1.8's hatchling/pydantic/`cryptography>=42` pins;
  retain `arnold-gen-deploy`, T1.5 simple-fixer commands, the fixed notification
  worker if required, and `arnold launch-authority` without a second console
  script;
- `uv.lock`: regenerate once from the composite; do not splice RA/T1.8 locks;
- `arnold/cli/__init__.py`: preserve simple-fixer dispatch and add only the
  opaque-handle launch-authority route;
- `cloud/template.py` and materialized wrappers: install the owner, ordinary
  fixer, notification worker/observer and T1.9 client only; no watchdog,
  resident recovery launcher, meta repair or boot-time chain start;
- `cloud/cli.py`, chain/supervisor start seams: T1.9 is the sole mutation path;
  legacy status remains read-only.

Known conflict hot spot: the T1.5 and prior T1.10 lineages overlap
`cloud/template.py`, the watchdog/progress/repair-loop wrappers and
`tests/cloud/test_watchdog_wrappers.py`. Resolve in favor of T1.5 retirement and
port the new notification worker as a separate installed surface. T1.8 and
RA-CONTAIN conflict on `pyproject.toml`/`uv.lock`; T1.8's stricter dependency
and one regenerated composite lock control.

## Local GO proof before any cloud mutation

Issue a scoped deploy decision only if one exact commit/tree/wheel passes all of
the following:

1. Exact component ancestry and clean worktree; source, wheel, installed
   `python -P`, fixed executables and materialized wrapper digests agree.
2. T1.5 forged-replay/provenance/one-shot probes and normal fixer installed
   path pass.
3. Replayed incident fixture produces one occurrence, one fixer result and at
   most one initial notification; two processes/200 observations are silent;
   response loss remains non-redispatchable.
4. T1.9 crash/response-loss tests at every owner/provider boundary produce one
   upload, one runner slot/start and one stop; collision/expiry/PID-reuse and
   raw `--fresh`/tmux/watchdog launch aliases reject before mutation.
5. The isolated finite runner can reach the exact target cursor and then close;
   failure stops without success or relaunch. Execute, Git, PR, product deploy
   and every unused effect family are demonstrably unavailable.
6. T1.8 backup, compatible rollback or forward-fix, selector response-loss,
   wrong-target rejection, writer-lineage and independent live-vector probes
   pass against the composite package.
7. Capacity manifest reserves bytes, inodes, WAL/checkpoint and receipt space
   for deploy, v2 fence, canary and reconciliation.

Any missing/unknown/stale/revoked result is NO-GO. A green component commit,
status, marker, log or bot message cannot replace the joined proof.

## Serial cloud sequence and stop/go proofs

1. **Capacity recheck — GO:** current byte/inode/WAL/receipt reserve exceeds the
   signed candidate requirement. **STOP:** any shortfall/read error; perform
   only separately authorized exact cleanup.
2. **Scoped release decision — GO:** binds candidate commit/tree/wheel,
   generation, fixed owner endpoints, operational route/effect allowlist,
   tests, expiry, rollback/forward-fix, exclusions and prior owner heads.
   **STOP:** mismatch, expiry or missing signer.
3. **Pre-cutover fence — GO:** old-generation writers/effects reject under
   current owner queries. **STOP:** any old writer/effect succeeds.
4. **T1.8 deploy/CAS — GO:** install and select the exact tested generation;
   preserve displaced-writer lineage. **STOP:** ambiguous selector outcome is
   reconciled, never repeated blindly.
5. **Independent live attestation — GO:** two observers match bytes,
   interpreter/imports, processes, wrappers, services, owner endpoints and
   configuration to the release vector. **STOP:** rollback/forward-fix through
   T1.8 while old writers remain fenced.
6. **Installed operational canaries — GO:** exact gated-stall replay gives one
   occurrence/fixer/notification and 200 silent scans; upload/start/stop
   response-loss reconciles without a second effect; exact stop works; rollback
   or forward-fix canary is accepted. **STOP:** duplicate or unknown effect
   truth remains visible/fenced; do not proceed to v2 retirement.
7. **Installed-release receipt — GO:** independently binds the current live
   vector and all canary receipts. It is operational-canary scope only.
8. **Permanent v2 fence — GO:** quarantine the exact v2 tuple, revoke
   resume/repair/execute/publish/notify and all effect grants, advance Custody
   epoch/tombstone, terminalize or preserve sticky-indeterminate old GLEKs, and
   CAS selection away without editing the marker. **STOP:** any late v2 write,
   effect or GLEK redispatch succeeds.
9. **Fresh v3 decision — GO:** one owner-signed canary seed binds fresh
   noncolliding session/workspace/plan/branch/worktree/state/marker/runner-slot
   identities, immutable spec/input bytes, installed generation, v2 cursor,
   exact target transition, TTL and pre-issued stop. This is the narrow explicit
   substitute for generic T1.1 admission and grants no reusable policy.
   **STOP:** collision, stale head, absent stop or identity disagreement.
10. **Launch through T1.9 — GO:** one upload, one exact process and current
    owner heads. **STOP:** unknown/multiple/wrong process enters fence/stop;
    never launch another.
11. **Operational acceptance — GO:** independent owner receipts prove the first
    exact v3 cursor strictly beyond v2's gated/finalize cursor, one runner, no
    duplicate fixer/notification, no accepted v2 effect, and
    `SUCCEEDED_CLOSED` by exact stop or independently proven expired-and-fenced
    denial. **STOP:** phase/model/finalizer failure is safe failure, not success;
    quarantine v3 and require a new owner decision for any future attempt.

After GO, do not expand authority. Preserve the stopped/fenced v3 canary as
operational evidence and resume the deferred hardening initiative before real
CL2 execute/publication.

## Explicitly deferred

- T1.1 generic target-bound admission and CL1 recomputation.
- T1.2 typed critic-attempt completeness and semantic admission.
- T1.3 contract-bundle/model-output authority integration.
- generalized T1.4 graph repair and retry budgets.
- universal T1.6 effect migration; Git/PR/deploy/other models/webhooks remain
  unavailable rather than falling back.
- T1.7 generic owner-store adoption.
- full T1.10 key rotation, reminders/chunks, auxiliary notifications and
  platform-wide direct-writer migration.
- all model routes, broad legacy-test restoration, archival/freeze
  generalization, execution/publication, product release and 24h/72h/7d closure.

These are preserved obligations in the follow-up epic. The operational canary
cannot be cited as their completion or as semantic/product acceptance.

## Commit estimate

Estimated remaining substantive mutating commits before cloud canary: **4**:

1. accepted T1.5 pass-3 repair;
2. one exact stall/notification operational patch;
3. one bounded T1.9 implementation;
4. one clean integration/packaging/conflict-resolution commit.

Mechanical merge commits and evidence-only review receipts are not counted. If
T1.9 is split into contracts/reducer and adapter/runner commits for review, the
count becomes **5** without changing scope.

No source, Git, cloud/provider, owner, checklist, worktree or existing session
was mutated. This map is the sole artifact write.
