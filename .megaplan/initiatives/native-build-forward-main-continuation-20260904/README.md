# Native Build Forward — C2 continuation 2026-09-04

This is the sole proposed execution initiative after the original NBF chain
was left paused and held. The old chain is immutable history and must not be
reconciled, rebound, resumed, or edited by this continuation.

The chain begins at `native-c2-completion-evaluation` and references the
canonical unexecuted C2-through-Platformization briefs. The six-prefix custody
claim is carried by `HANDOFF.md`, which records the old state/spec/plan/marker
digests and explicitly does not claim `chain_completed`.

## Three-root execution contract

This continuation intentionally separates three roots:

1. `/workspace/arnold` is the clean reviewed source checkout. It is the
   canonical provenance/supervisor input and must remain clean; it is never the
   chain's mutable project directory.
2. `/workspace/projects/native-build-forward-main-continuation-20260904/Arnold`
   is the unique writable operation/project root. The uploaded chain spec lives
   here, and chain state, plans, projections, logs, and operation evidence are
   expected to live under its `.megaplan` directory.
3. `/workspace/runtime-candidates/native-build-forward-main-continuation-20260904`
   is the manifest-created immutable runtime candidate. The chain launcher
   derives its cwd, `PYTHONPATH`, and generation interpreter from this
   candidate's runtime manifest; it is not the chain state root.

The container itself is unique (`nbf-main-continuation-clean2-20260904`) and
the mounted host workspace is unique. The default supervisor runtime/receipt
root (`/workspace/.megaplan/supervisor-python`) is therefore operation-local to
this isolated container. The canonical image entrypoint must run so it can
execute `arnold-supervisor-runtime --prepare`; an idle-shell entrypoint
override is prohibited because it skips the supervisor receipt.

## Identities

- Published ref: `main` (the exact SHA is captured by the deployment receipt)
- Published source authority: branch `main`; the exact SHA/tree are read from
  the deployment receipt and immutable runtime manifest at launch. They are
  intentionally not duplicated here, so this document cannot become stale.
- Chain session: `nbf-continuation-main-clean2-20260904`
- Writable operation/project root: `/workspace/projects/native-build-forward-main-continuation-20260904/Arnold`
- Reviewed source root: `/workspace/arnold`
- Runtime candidate root: `/workspace/runtime-candidates/native-build-forward-main-continuation-20260904`
- Runtime manifest identity: `native-build-forward-main-continuation-20260904`
- First operation namespace: `nbf-continuation-main-clean2-20260904` (the supported
  cloud identity tuple is the explicit workspace/session/shared runner in
  `cloud.yaml`; operation IDs remain journal-owned and are never caller-
  invented).
- Chain lifecycle, tiebreaker, fixer, oracle, researcher, and superfixer roles
  all resolve to `omp:openrouter/meta/muse-spark-1.3-contributor:high` through
  the canonical continuation runtime binding and are checked by preflight and
  the exact-output provider receipt. `cloud.yaml` enables the supported
  superfixer/babysitter mode after that probe. This is distinct from the local
  Megado Luna/Grok model policy.

## Pre-launch identity guards

The committed cloud contract is machine-checkable only when
`repo.workspace`, `chain_session`, and `ssh.container` are explicit. Local
preflight must reject the old `/workspace/runtime-candidates/native-build-forward`
workspace, the old chain/marker session, implicit `megaplan-chain`, and any
missing identity field. The shared `megaplan-cloud-agent` is not a new
container; uniqueness comes from the continuation workspace/session tuple.
Operation IDs are journal-owned under the
  `nbf-continuation-main-clean2-20260904` namespace and must be derived by the supported
transaction, never supplied by a caller or reused from the old chain.

No remote container, checkout, hold, marker, plan, or chain has been created
or launched by this artifact update. Host provisioning must first place the
clean exact source at `/workspace/arnold` and clone the same SHA separately
into the writable operation root. Then use the canonical image entrypoint,
not `sleep infinity`, before runtime creation, manifest/probe generation, and
chain launch. Use the canonical cloud recipe only after fresh custody, object,
package, profile, capacity, and one-owner preflight.
