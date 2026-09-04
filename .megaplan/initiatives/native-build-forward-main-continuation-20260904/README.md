# Native Build Forward — C2 continuation 2026-09-04

This is the sole proposed execution initiative after the original NBF chain
was left paused and held. The old chain is immutable history and must not be
reconciled, rebound, resumed, or edited by this continuation.

The chain begins at `native-c2-completion-evaluation` and references the
canonical unexecuted C2-through-Platformization briefs. The six-prefix custody
claim is carried by `HANDOFF.md`, which records the old state/spec/plan/marker
digests and explicitly does not claim `chain_completed`.

## Identities

- Published ref: `main` (the exact SHA is captured by the deployment receipt)
- Published source authority: branch `main`; the exact SHA/tree are read from
  the deployment receipt and immutable runtime manifest at launch. They are
  intentionally not duplicated here, so this document cannot become stale.
- Chain session: `nbf-main-continuation-live12-20260904`
- Runtime/workspace root: `/workspace/nbf-main-continuation-live12-20260904/Arnold`
- Runtime manifest identity: `native-build-forward-main-continuation-20260904`
- First operation namespace: `nbf-main-continuation-live12-20260904` (the supported
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
  `nbf-main-continuation-live12-20260904` namespace and must be derived by the supported
transaction, never supplied by a caller or reused from the old chain.

No remote container, checkout, hold, marker, plan, or chain has been created
or launched by this artifact update. Use the canonical cloud recipe only after
fresh custody, object, package, profile, capacity, and one-owner preflight.
