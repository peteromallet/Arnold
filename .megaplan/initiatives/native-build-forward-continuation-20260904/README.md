# Native Build Forward — C2 continuation 2026-09-04

This is the sole proposed execution initiative after the original NBF chain
was left paused and held. The old chain is immutable history and must not be
reconciled, rebound, resumed, or edited by this continuation.

The chain begins at `native-c2-completion-evaluation` and references the
canonical unexecuted C2-through-Platformization briefs. The six-prefix custody
claim is carried by `HANDOFF.md`, which records the old state/spec/plan/marker
digests and explicitly does not claim `chain_completed`.

## Identities

- Candidate ref: `docs/nbf-durable-start-20260903`
- Candidate SHA: `18d4f7b9787edf5931b5c483da2cca1f5b1fb7e3`
- Candidate tree: `73f94dec7b0190352d51502e2f904c90d97bd98f`
- Chain session: `nbf-continuation-c2-20260904`
- Runtime/workspace root: `/workspace/nbf-continuation-c2-20260904/Arnold`
- Runtime manifest identity: `native-build-forward-continuation-20260904`
- First operation namespace: `nbf-continuation-c2-20260904` (the supported
  cloud identity tuple is the explicit workspace/session/shared runner in
  `cloud.yaml`; operation IDs remain journal-owned and are never caller-
  invented).
- Chain lifecycle phases and tiebreaker roles resolve to
  `meta/muse-spark-1.3-contributor`, thinking `high`, through
  `.megaplan/profiles.toml`. Product fixer/oracle/researcher role binding is
  not expressible by the current profile schema and is therefore not claimed.
  `cloud.yaml` sets the supported babysitter mode to `off` so the resident
  DeepSeek superfixer default cannot silently dispatch. A supported product
  role-binding seam must be verified before launch. This is distinct from the
  local Megado Luna/Grok model policy.

## Pre-launch identity guards

The committed cloud contract is machine-checkable only when
`repo.workspace`, `chain_session`, and `ssh.container` are explicit. Local
preflight must reject the old `/workspace/runtime-candidates/native-build-forward`
workspace, the old chain/marker session, implicit `megaplan-chain`, and any
missing identity field. The shared `megaplan-cloud-agent` is not a new
container; uniqueness comes from the continuation workspace/session tuple.
Operation IDs are journal-owned under the
`nbf-continuation-c2-20260904` namespace and must be derived by the supported
transaction, never supplied by a caller or reused from the old chain.

No remote container, checkout, hold, marker, plan, or chain has been created
or launched by this artifact update. Use the canonical cloud recipe only after
fresh custody, object, package, profile, capacity, and one-owner preflight.
