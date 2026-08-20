# T3.4 live cloud-vector attestation — Luna preparation

Verdict: **NO ATTESTATION; preparation only.** No cloud contact or completion claim.

## Exact live vector

The attested subject is one independently observed tuple, not a deployment manifest's claims:

```text
host/provider/instance/boot/mount/volume identities
source commit + tree + clean/immutable checkout identity
wheel/sdist/RECORD/package version and installed-file digests
container image manifest/config/layers/platform and running container ID
interpreter/venv/dependency-lock/.pth/sys.path/import-origin digests
rendered cloud config, environment-policy digest and secret-reference names (never values)
supervisor/systemd/tmux/unit/drop-in/wrapper/entrypoint bytes and argv
every live PID start-time/uid/cgroup/container/executable/cmdline/open source root
service/socket/port and selected runtime-generation identities
authoritative volume/device/mount/schema/migration/WAL/store identities
Run Authority revision/fence, Custody epoch/leases, WBC generation/GLEK heads
contract-bundle/model-route/schema digests
T2.6 decision, T3.1 receipt, T3.2 fence and deployed-generation receipt
```

The expected vector is supplied and signed by Release Authority before observation. It cannot be derived from the runtime being attested.

## Two-observer protocol

Observer A is an owner-installed privileged inventory adapter that reads OS/container/filesystem/service/owner stores without using application projections. Observer B is an independent verifier using a disjoint read-only channel and separately pinned code/key/runtime. Neither may be build producer, deployer, service process, manifest author or the other's data source. Each emits canonical raw observations; a joiner compares exact values and signs only their equality to the independently supplied expectation. The attestation hashes external observation bundles and does not embed or self-hash its own claimed digest.

Two observations bracket a bounded quiet interval and bind monotonic plus UTC clocks, boot ID and owner heads. Recommended freshness is five minutes and expires before T3.5 starts. Any process restart, selector/config/package/image/schema/route/owner revision or fence/key/revocation change invalidates it immediately and requires full re-observation.

## Mismatch and UNKNOWN

Missing permission, unavailable observer, unreadable path, ambiguous symlink/overlay/import origin, mutable tag, digest disagreement, extra process/writer, unknown volume/schema, stale owner head, clock uncertainty, response loss or observer disagreement yields typed `MISMATCH` or `UNKNOWN`; both block progression. UNKNOWN is preserved and reconciled through the owning system, never converted from absence to equality. A manifest, marker, `pip show`, container tag, process name, status projection or producer-signed receipt alone is insufficient.

## Finite test matrix

1. Exact happy-path two-observer equality over every vector field.
2. Wrong commit/tree, dirty checkout, substituted wheel/RECORD or editable import shadow.
3. Mutable/repointed image tag, changed layer/config/platform or old running container.
4. Changed rendered config/env policy/wrapper/unit/drop-in/argv/entrypoint.
5. Extra old PID, PID reuse, wrong uid/cgroup/executable/import root or restarted supervisor.
6. Wrong volume/mount/device, schema/migration/WAL/store generation.
7. Stale/revoked RA fence/revision, Custody epoch/lease or WBC head.
8. Route/bundle/schema drift and unavailable configured model route.
9. Forged producer manifest, self-hashed observation, observer key/code substitution or A→B data replay.
10. Observation race before/between/after reads; any mixed snapshot rejects.
11. Expired/future timestamp, boot change, clock rollback or revocation during join.
12. Response loss after signed attestation commit returns UNKNOWN until exact idempotent owner replay.

The positive fixture uses a disposable synthetic host/vector. Negative tests patch raw observer inputs, never production state. Static inventory must prove all templates, wrappers and status probes consume the same canonical vector contract; projections remain diagnostic only.

## Evidence and dependency boundary

Emit `expected-vector.json`, two raw observation bundles, observer code/key/runtime receipts, exact comparison matrix, freshness/revocation snapshot and one owner-bound attestation receipt. It must bind accepted T1.8 generation semantics, T2.3 installed canary contract, T3.1 predeploy receipt and T3.2 fence. T3.4 does not deploy, switch selectors, run the production canary or grant acceptance.

Current attestation is impossible: no accepted integrated generation/T2.6/T3.1/T3.2/deployment receipt or owner-installed observers exist. No code, Git, cloud, provider, process, owner or checklist state was mutated. This report is the sole write; SHA-256 is external.
