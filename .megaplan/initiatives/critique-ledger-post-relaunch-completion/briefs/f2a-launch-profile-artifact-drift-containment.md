# F2A — Cross-pipeline provider-policy and execution-binding drift containment

## Outcome

Make it impossible for any registered production pipeline or chain to silently
run a different provider/profile/phase policy or different remote bytes than
the epic approved. Detect any later drift deterministically, terminate only the
wrong bound workers, restore the last approved admissible binding, attempt one
idempotent relaunch, and notify a person only if that bounded repair cannot
restore service.

The normative design target is
`provider-policy-execution-binding-contract.json`. Its current intended map
also makes the follow-up epic's actual expectation explicit: `vendor: codex`
does not mean all-Codex; the partnered profiles retain their exact approved
DeepSeek/Zhipu/Fireworks/Codex phase routes. Missing provider capability is a
typed no-spawn result, not authority to substitute all-Codex.

The companion normative design target
`provider-schema-dialect-family-contract.json` closes the response-schema
boundary inside that same execution binding. It preserves provider-neutral
canonical semantics, compiles an exact provider wire dialect only when lossless,
and otherwise selects canonical local strict validation. Response enforcement
and tool mode are independent axes. Historical M9 unsupported-keyword fixtures
and current r5 implementation commits `f401431b7a`/`b168edbca0`/`18b279f5ef`
are retained as input evidence; none is accepted deployment proof by itself.

## Difficulty and dependencies

Difficulty **5/5 — VERY HARD**. This joins policy resolution, credentials,
serialization, remote durability, process identity, watchdog containment,
rollback, idempotency and user-visible effects across crash boundaries. A
locally green component can still produce the wrong remote execution.

Hard dependencies:

- F1 supplies durable owner, repair-attempt, process-isolation and notification
  occurrence/version primitives.
- F2 supplies universal admission, typed attempt/model handling, provider
  identity evidence and release qualification.
- F3 and every later ordinary Critique product milestone wait for F2A's
  independently accepted completion manifest.

Within F2A, the registry/policy schema lane, canonical remote-bundle lane,
watchdog/rollback lane and all-pipeline fixture lane may run in parallel after
the contract is frozen. Integration, installed/cloud tests and rollout wait for
all four lanes.

## Existing cross-pipeline substrate to reuse

Do not introduce a second Megaplan-only authority system. The source audit
found reusable neutral contracts already in Arnold:

- `arnold.manifest.WorkflowManifest.manifest_hash` and
  `arnold.kernel.ids.WorkflowIdentity` provide canonical workflow identity;
- `arnold.execution.registries.AuthorityRegistry` is the fail-closed mutation-
  authority seam, while `OperationKind.PROFILE_VALIDATE` is the neutral profile
  validation operation;
- `arnold.agent.contracts.AgentRequest.attestation` and `ResultProvenance`
  carry dispatch/result evidence;
- `arnold.workflow.execution_attempt_ledger.AttemptProvenance` carries causal
  attempt lineage.

Megaplan's `chain.execution_binding` and cloud `runtime_provenance` already
contain useful content/runtime drift primitives, but their current package
location and schemas are product-specific. Extract or adapt those primitives
behind the neutral Arnold contracts; Megaplan becomes one consumer.

The broader missing seam is a typed neutral object that joins workflow identity,
the exact resolved provider map, exact remote readback bytes, child-loaded bytes
and repair custody. Current generic operation payloads and result provenance
are too permissive/optional to establish that join. There is also no registry-
closed test proving every production pipeline and launcher uses it. F2A must
close both gaps rather than merely add fields to a Critique cloud wrapper.

## Scope

- Inventory every shipped production pipeline, chain driver, cloud launcher,
  resident/scheduler path and compatibility entry point in a registry closed
  by CI. A new launcher without conformance fixtures fails CI.
- Add a versioned epic/run policy artifact containing the immutable intended
  profile, provider, model, fallback and tier route for every enabled phase of
  every milestone. Bind its exact committed bytes, source/spec/config/profile-
  resolver versions, plan/run/incarnation and admitted credential capabilities.
- Resolve the complete milestone map through the same generic Arnold pipeline
  resolver used by launch. Compare canonical maps exactly before any process
  spawn. Report expected/actual digests and the first differing route.
- Canonicalize and upload the launch bundle first. Atomically publish it on the
  remote host, read the bytes back, verify size and SHA-256, then persist the
  execution binding from those exact bytes. Spawn only from that immutable
  remote object. The child re-verifies its loaded bytes and route before its
  first provider call.
- Add deterministic watchdog classes for provider, profile, phase/model,
  execution-binding and loaded-byte drift. Fence new dispatch, target cgroup
  plus PID start identity, perform bounded graceful/hard termination, and prove
  the wrong-profile process tree is gone.
- Roll back only to the last approved binding whose provider capabilities and
  source/runtime policy remain admissible. Perform at most one relaunch under a
  durable compare-and-swap key of occurrence + intended-map digest + remote-
  bundle digest. Preserve the budget through watchdog/process/host restart.
- Always write a durable audit event, but do not send a user/provider
  notification on initial detection. Successful automatic repair emits zero
  incident notifications. Unsafe, failed or exhausted containment/rollback/
  relaunch emits one occurrence/version-deduplicated failure notification.
- Compile every canonical response schema after exact provider/profile/model/
  runtime resolution and before dispatch. Attest canonical and wire schema
  hashes, compiler version/source hash, response enforcement, independent tool
  mode, runtime/image and canary identity. A provider dialect limitation may
  choose local strict JSON but may never rewrite canonical semantics.
- Preserve open/dynamic maps used by `finalize`, `feedback` and `loop_plan`.
  Mutation fixtures cover unsupported keywords and prove exact dynamic keys and
  nested values survive canonical local validation.
- Route deterministic `provider_contract/schema_error` through one phase
  invocation and no generic/model fallback. Launch one provenance-safe fixer
  for the durable occurrence or fail closed; admit exactly one repair-commit-
  bound same-phase retry. Crash, restart and response loss cannot multiply the
  attempt, fixer claim, retry or notification.
- Harden `_normalize_stdin_text` at the path-probe boundary: `OSError`, including
  `ENAMETOOLONG`, for a long one-line inline prompt returns the original bytes.
  A read failure after a real file is established remains a typed input error.
- For ephemeral Codex calls, locate and hash exact rollout/session usage under
  the bound `CODEX_HOME`, or emit typed unavailable provenance with bounded
  search evidence. Numeric `$0` is never authoritative evidence of zero tokens,
  a free call or an observed model when the rollout is missing.

## Locked decisions

- This is generic Arnold pipeline infrastructure. No invariant, registry or
  test may be implemented only in Megaplan or only for Critique.
- Reuse the neutral manifest/workflow identity, authority registry, profile-
  validate operation, agent attestation/result provenance and attempt lineage.
  Extract reusable Megaplan execution/runtime-binding primitives behind that
  neutral seam; do not fork their semantics into another product-local schema.
- Policy is intent, not a credential fallback suggestion. An all-Codex map is
  legal only when the approved artifact explicitly contains all-Codex.
- Resolution is complete before seal. No remote launcher, environment variable,
  wrapper, watchdog or provider failure may re-resolve or silently substitute.
- Metadata, an expected path, an upload success code or an object-store ETag is
  not remote-byte evidence. Readback bytes and child-loaded bytes both bind.
- Secrets never enter the canonical bundle or receipts. Only non-secret
  credential capability/identity evidence is bound.
- PID alone is not worker identity. Kill authority requires the bound cgroup,
  process-start identity and execution binding; unrelated workers survive.
- Rollback cannot revive a provider/profile whose credential or policy
  admission has expired.
- Notification suppression never suppresses the internal audit ledger.
- Tool availability does not choose or weaken response enforcement, and
  response enforcement does not silently disable tools. The four-value cross
  product is required acceptance evidence.
- A schema error before transport has zero provider calls; a provider rejection
  has one maximum. “One call” never means one per fallback model or after each
  observer/restart poll.
- A fixer is counted only after durable delegation provenance, a validated
  managed manifest, live child proof and atomic claim transfer. Otherwise the
  occurrence transitions once to deduplicated manual review with zero fixer.
- Canary evidence is candidate-bound, not feature-commit-bound. The final
  candidate must be `18b279f5ef...` or a descendant proving `18b` ancestry, and
  the final candidate, deployed runtime, tested runtime and canary receipt
  commits must be identical. A canary at earlier `b168edbca0...` is rejected.

## Done criteria

- The normative JSON contract validates and the current epic's complete
  intended milestone map is immutable, content-addressed and exact.
- Preflight refuses missing/extra/reordered milestones, resolver/profile-source
  drift, unexpected all-Codex or other substitution, fallback/tier drift and
  credential mismatch before spawn, with typed actionable differences.
- Launch receipts prove canonicalize → upload → fsync/atomic publish → remote
  byte readback → durable binding → spawn → child-loaded-byte/map attestation
  in that order. No provider call precedes the child attestation.
- Drift fixtures prove deterministic classification, dispatch fencing,
  cgroup/start-identity process-tree termination, still-admissible rollback and
  no harm to unrelated workers.
- Crash/response-loss/reboot/concurrency tests prove one relaunch maximum for
  the exact durable dedupe key and no second execution after ambiguity.
- Successful automatic recovery produces zero user/provider notifications.
  Failed, unsafe or exhausted repair produces exactly one deduplicated failure
  notification; provider loss and 200 unchanged polls cannot multiply it.
- A registry-closed matrix runs across every production pipeline/chain/launcher
  on source, wheel, installed and cloud surfaces. It covers missing credentials,
  resolver/env drift, malformed and TOCTOU uploads, spawn loss, watchdog crash,
  reboot, PID reuse, kill/rollback failure, concurrent drift, relaunch success/
  failure and notification response loss.
- The completion manifest hashes the launcher registry, intended and resolved
  maps, local/uploaded/readback/loaded byte digests, runtime attestations, drift
  and repair ledger, notification effects and the complete all-pipeline matrix.
- The provider-schema dialect contract validates. Tests prove the response-
  enforcement/tool-mode cross product, canonical/wire/compiler/provider/
  profile/runtime/image hashes and child readback before provider dispatch.
- `finalize`, `feedback` and `loop_plan` dynamic maps plus M9 mutations
  (`default`, `const`, `oneOf`, `minimum`) preserve canonical semantics and
  select local strict validation whenever the provider dialect is insufficient.
- Deterministic schema-error fixtures prove one phase invocation, zero-or-one
  provider transport call, no generic/model fallback, one managed fixer or
  fail-closed outcome and exactly one same-occurrence post-repair retry. Process
  restart, host restart, launch/response loss and 200 polls preserve one claim
  and one terminal notification maximum; successful repair emits none.
- A fresh installed-cloud real Codex canary binds canonical/wire/compiler,
  provider/profile/model/runtime/image, raw response and canonical validation
  hashes in a content-addressed receipt. A registry-closed matrix rejects every
  untested production pipeline, phase, provider, profile, runtime and launcher.
- Inline-prompt regressions cover real and injected `ENAMETOOLONG`, long Unicode,
  newline bypass, exact-byte preservation, normal prompt-file reads and typed
  established-file read failure. No filesystem-probe exception escapes.
- Ephemeral Codex regressions cover exact session lookup, bounded missing-ID
  correlation, missing/unreadable/malformed rollout, unpriced versus unavailable
  usage, concurrent-rollout isolation and crash/restart. Missing evidence is
  typed unavailable and cannot silently authorize `$0`, zero tokens or model
  provenance.
- The final canary completion manifest proves `18b279f5ef...` is the tested
  commit or an ancestor of it, and exact equality across final candidate,
  deployed runtime, canary-tested and canary-receipt commits. Its receipt is
  later than the bound deployment receipt; `b168edbca0...` cannot pass.

## Anti-scope

Do not launch or repair the currently blocked r5 chain, mutate cloud state,
change its provider policy, or treat this follow-up milestone as proof that the
immediate root branch is deployed. Do not rename or renumber the fifteen closed
F1/F2 obligation IDs.
