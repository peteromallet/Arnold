# T2.5 Luna preparation — prove every configured model route is contract-compatible

Date: 2026-08-02  
Role: GPT-5.6 Luna, read-only preparation  
Scope: platform-wide Arnold model dispatch, not Megaplan alone  
Code lineage inspected: `6787d6363e8fc0603092913ae877db14f3b9fff8`  
T1.3 interface-awareness worktree: `/private/tmp/arnold-critique-recovery-contract-bundles-20260802` at committed HEAD `ddb764b30cedf3774ff5ca665a85a62090607b21`, with an uncommitted pass-3 repair in progress  
Mutation status: no code, cloud, process, provider, secret, owner, release, or checklist state was changed. This preparation report is the only artifact created.

## Verdict

T2.5 is not launchable as a completion proof yet. It is launchable as a static
inventory and offline conformance-preparation slice.

The central finding is that a “configured route” cannot mean only a TOML string.
The platform currently has at least four independently changing route layers:

1. a logical profile slot such as `critique = [A, B, C]`;
2. a managed backend such as Claude, Codex, Hermes, or Shannon;
3. a physical provider, endpoint, credential set, request protocol, and resolved
   model;
4. hidden retry, ambient substitution, provider aggregation, and helper-agent
   paths that can make additional physical requests outside the visible profile.

The exact ancestor contains hard bypasses that make a repo-profile-only proof
unsound:

- Megaplan may replace an unavailable non-explicit agent with the first detected
  runtime agent and reset the model (`workers/_impl.py:4278-4293`).
- Claude/Shannon and Codex dispatch each contain an inner retry on timeout/stall/
  connection classes (`workers/_impl.py:5007-5029`, `5046-5092`).
- an ambient auth/connection fallback can dispatch another detected agent outside
  the selected profile chain (`workers/_impl.py:5239-5293`).
- Hermes can infer, alias, dynamically discover, or change providers at runtime;
  OpenRouter is itself an aggregator. A capture that says only `provider=hermes`
  does not prove the actual upstream provider.
- `arnold/agent/run_agent.py` has its own request, retry, compression,
  continuation, empty-response, and fallback loops, and several tools and
  residents call provider clients outside Megaplan.

Therefore every physical dispatch must be admitted by one frozen route registry,
receive a T1.2 attempt identity before effect, and bind the untouched T1.3 capture
to exact physical route evidence. Any route that is unavailable, ambiguous,
malformed, truncated, mismatched, or uninstrumented is `INADMISSIBLE`; it cannot
emit `NO_FINDING` and cannot silently fall through to another provider.

This report does **not** claim T2.5 complete, does not claim any live route works,
and did not contact a provider.

Static inventory headline: 20 built-in Megaplan profiles, two pipeline-local
profile families, 17 step/schema identities, and 29 unique built-in logical route
spellings (three symbolic, five Claude, thirteen Codex, and eight Hermes). These
are not the final physical-route count: user/project/runtime configuration and
provider/credential/endpoint expansion can only be counted from the exact
deployment snapshot.

## Governing contract and inspected evidence

### Normative recovery contract

The recovery plan defines T2.5 at
`docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md:410-417`:

- owner is model-routing plus WBC;
- every allowed tier must prove exact availability/auth, request and response
  transport, capture schema, truncation/termination, immutable parser/normalizer,
  timeout, and provider ambiguity;
- a failed route is inadmissible, never `NO_FINDING`;
- fallback is a fresh pre-approved attempt under the same owner budgets.

File SHA-256:
`edddb198701c7567325aac5827100321addbe9e7c5dd458c1329628e82472e0c`.

### T1.2 preparation dependency

Inspected:
`.megaplan/subagents/critique-ledger-recovery/T1.2/t1-2-sol-preparation-luna-result.md`.
SHA-256:
`c25a28f2b6f247340d759930be1363dd307ad86eb05b5eb297f9f8c8097c8206`.

T1.2 proposes six terminal physical-attempt states (`:28-33`):

- `SUCCEEDED`
- `PROVIDER_FAILED`
- `PRODUCER_CONTRACT_FAILED`
- `PARSER_FAILED`
- `SANDBOX_FAILED`
- `CANCELLED`

Only `SUCCEEDED` may produce `FINDING`, `NO_FINDING`, or
`EXTERNAL_UNVERIFIABLE` (`:36-41`). Every provider dispatch, including hidden
retries and ambient fallbacks, must be a fresh physical attempt (`:399-413`). A
round with one failed mandatory occurrence remains incomplete (`:385-393`).

T2.5 must consume those attempt receipts; it must not invent a parallel attempt
ledger.

### T1.3 pass-3 dependency and interface risk

Inspected pass-3 brief:
`.megaplan/subagents/critique-ledger-recovery/T1.3/contract-bundles-repair-pass3-luna-brief.md`.
SHA-256:
`67695d73a206c6d21f15b9ee8f2db5d08f662fde901579c92026a2ceffa61880`.

The brief requires untouched provider bytes/frame plus authenticated provider,
model, tool, session, attempt, and channel metadata as the sole parsing authority
(`:9-21`), and one neutral Arnold-wide authority with installed-entrypoint parity
(`:22-37`).

The active, dirty pass-3 candidate was inspected only for interface awareness.
Its current neutral file has SHA-256
`1f0dfbcc901973dadf914c59bda10c6f2038091204beef20653eb9686114d1f5`.
At inspection time:

- `ContractOutcome` begins at `arnold/pipeline/contract_bundles.py:32`;
- `ContractHealthCode` begins at `:43`;
- `ContractBinding` begins at `:104`;
- exact capture fields are declared at `:159-169`;
- `ProviderTranscript.capture` is at `:182-209`;
- Shannon framing is parsed at `:252-296`;
- route-dependent parsing begins at `:299`.

The current candidate capture fields are worker-facing: `provider`, `model`,
`tool_mode`, `session_id`, `attempt_index`, `worker_channel`, `auth_channel`, and
`capture_channel`. Parsing currently treats `shannon` specially and accepts
worker labels such as `hermes`, `codex`, and `claude` as providers. That is enough
to identify a worker, but not necessarily enough to prove the physical upstream
provider, endpoint, provider request ID, requested versus resolved model, finish
reason, truncation status, or immutable T1.2 attempt ID.

This is a dependency-changing interface issue. Before T1.3 freezes, its owner
must choose one of these two non-forking designs:

1. enrich the authenticated T1.3 transport envelope with exact physical route
   and termination identity; or
2. freeze an extensible T1.3 raw-capture binding and let T2.5 add a separate
   immutable `RouteTransportReceipt` bound to the T1.3 raw digest and the T1.2
   attempt ID.

The second design is safer if T1.3 is otherwise ready: the receipt may add
transport facts, but it must never parse response content or become a second
parser authority.

Current pass-3 bundle hashes at inspection time:

| Bundle | SHA-256 |
|---|---|
| `critique_prompt_only_v1.json` | `999d06cea72b8a1e1d5741492a11655f04c9fd455fa7326c065be4f1d2025cc6` |
| `critique_tool_enabled_v1.json` | `ce263c3cd5f1c84be965ff2e99ddd69cd9f194e096fcca2b51ad03d36feeacab` |
| `finalize_prompt_only_v1.json` | `9b85cbcde1945a06c37e8f318f300b5539d0960ae4509c8e93e6104aa2b46649` |
| `finalize_tool_enabled_v1.json` | `698fc326c6a6a07ebbd5961846b323bb64aea8d2dacd5767222280590372cc45` |

These are awareness hashes, not accepted release hashes. The worktree was dirty,
so they can change before T1.3 review and freeze.

## What exactly counts as a route

T2.5 must inventory a deployment snapshot, not merely source literals. One
`route_id` should commit to all of the following:

```text
product / pipeline / entrypoint / phase / slot / profile source
tier / primary-or-fallback ordinal / logical backend
physical provider / endpoint origin / credential-set ID
requested model / resolved model / actual model
effort / tool mode / request protocol / response framing
capture schema / T1.3 bundle+parser ABI / semantic validator
timeout / retry policy / attempt budget / runtime generation
```

The ID should be a canonical digest of those non-secret fields. Human aliases are
labels, not identity. `hermes`, `premium`, `claude`, `codex`, `glm`, and `kimi`
are not physical route identities until fully resolved.

Required route lifecycle states:

| State | Meaning |
|---|---|
| `CANDIDATE` | discovered from an authoritative source but not yet proven |
| `OFFLINE_COMPATIBLE` | static resolution and fixture conformance passed |
| `LIVE_VERIFIED` | exact installed generation and credential set passed a bounded canary |
| `INADMISSIBLE` | configured but unavailable, ambiguous, incompatible, or uninstrumented |
| `RETIRED` | intentionally removed and blocked by negative tests |

Credential presence, `/models` discovery, a successful neighboring model, or a
worker process being installed must never imply `LIVE_VERIFIED`.

## Exhaustive authoritative source inventory

### A. Megaplan profile and override sources

The exact ancestor loads these layers:

1. built-in profile TOML;
2. user `config_dir(home)/profiles.toml`;
3. project `.megaplan/profiles.toml`;
4. built-in pipeline-local profile directories;
5. user pipeline-local profile directories under `~/.megaplan/pipelines`;
6. `extends` chains, including system and pipeline-local parents;
7. command/runtime modifiers: `--profile`, `--vendor`, `--critic`, `--depth`,
   `--phase-model`, tier routing, prep routes, and adaptive critique;
8. environment/default resolution, including the symbolic `premium` vendor.

Evidence: `profiles/__init__.py:533-577` for built-in/user/project layering and
`:628-900` for pipeline-local discovery and inheritance. The ancestor blob is
`a30c3500526365636aff645c72b59ba1f27503cb`.

Built-in Megaplan profile names at the ancestor:

```text
all-claude
all-codex
all-deepseek-flash
all-deepseek-pro-direct
all-deepseek-pro
all-fireworks-deepseek
all-open
apex
arnold-openrouter
directed
partnered
partnered-3
partnered-4
partnered-5
partnered-5-glm
premium
solo
variable
variable-claude
variable-codex
```

`all-fireworks-deepseek` is a legacy/misleading name in this lineage and must be
recorded by content, not inferred by filename.

Pipeline-local route surfaces found:

- `epic-blitz/profiles/standard.toml`: high/mid/low critic slots plus revision
  and readiness slots, primarily `claude:low`;
- `writing_panel_strict/profiles/standard.toml`: pessimist, optimist,
  structuralist, synthesis, and revision slots, primarily `claude:low`.

Every resolved profile cell must appear separately in the inventory even if many
cells collapse to one physical transport canary.

### B. Exact logical route specifications found in built-in profiles

The unique route families include:

| Backend | Exact configured forms |
|---|---|
| symbolic | `premium`, `premium:low`, `premium:medium` |
| Claude | `claude`; `claude:low`; `claude:claude-haiku-4-5`; `claude:claude-sonnet-4-6`; `claude:claude-opus-4-7` |
| Codex | `codex`; `codex:low`; `codex:medium`; `codex:high`; `codex:gpt-5.4`; `codex:gpt-5.5`; `codex:gpt-5.6-luna:low`; `codex:gpt-5.6-sol:medium`; `codex:gpt-5.6-sol:high`; `codex:gpt-5.6-sol:xhigh`; `codex:gpt-5.6-terra:low`; `codex:gpt-5.6-terra:medium`; `codex:gpt-5.6-terra:high` |
| Hermes / DeepSeek | `hermes:deepseek:deepseek-v4-flash`; `hermes:deepseek:deepseek-v4-pro` |
| Hermes / Fireworks | `hermes:fireworks:accounts/fireworks/models/glm-5p2`; `hermes:fireworks:accounts/fireworks/models/kimi-k2p6` |
| Hermes / OpenRouter | `hermes:openrouter:deepseek/deepseek-chat`; `hermes:openrouter:deepseek/deepseek-r1` |
| Hermes / Zhipu | `hermes:zhipu:glm-5.2` |
| Hermes inferred | `hermes:glm-5.1` |

Bare Claude and Codex defaults are pinned elsewhere in the ancestor:
`claude-opus-4-7` and `gpt-5.6-sol`. Native managed routing has different bare
defaults: Hermes `deepseek:deepseek-v4-pro`, Codex `gpt-5.6-terra`, and Claude
`opus` (`arnold/agent/routing.py:16-24`). Both resolvers must be reconciled rather
than assumed equivalent.

The profiles also contain tiered execute routes 1-10, critique routes 1-5,
prep-stage routes, phase overrides, and ordered fallback arrays. T2.5 must emit a
machine-generated expanded cell for each `(profile source, profile, phase, tier,
ordinal)`; a hand-maintained list is not sufficient.

Known fallback families include:

- same-provider Codex Sol -> Terra -> Luna chains;
- Zhipu GLM 5.2 -> Fireworks GLM 5p2 -> Codex fallback chains;
- DeepSeek flash/pro chains;
- OpenRouter DeepSeek routes;
- a `partnered-5-glm` pattern with a repeated Zhipu route. Duplicate physical
  routes must be rejected as fake independence, not counted as resilience.

### C. Megaplan step and schema surface

`step_contracts.py` defines 17 model-bearing identities or sub-identities:

```text
execute, finalize, critique, review, gate, plan, prep,
critique_evaluator, revise, prep_triage, prep_distill, prep_research,
feedback, loop_plan, loop_execute,
tiebreaker_researcher, tiebreaker_challenger
```

Each has a schema/capture key and most have default routing
(`step_contracts.py:87-268`; ancestor blob
`3696befd83bf621bbb0df54847d9bc89a3088fc1`). The generated inventory must join
every resolved route cell to the exact step schema, T1.3 bundle where applicable,
tool mode, and semantic validator. A transport-compatible critique route is not
automatically compatible with `execute`, `gate`, or arbitrary native output.

### D. Native managed-agent routing

`arnold/agent/routing.py` is process- and Megaplan-independent and therefore a
separate authoritative surface. It provides:

- managed backends `hermes`, `codex`, and `claude`;
- aliases `chatgpt -> codex`, `shannon -> claude`;
- backend/model family inference;
- bare defaults;
- Hermes normalization including bare GLM aliases;
- declared raw-stream and timeout capabilities.

Blob: `f2866a12086ead956041687aeee77599a634c338`.

Every consumer of `resolve_managed_agent_route` and every consumer that bypasses
it must be enumerated. Alias acceptance must be tested bidirectionally: accepted
aliases resolve to one canonical physical route, while an alias cannot make a
backend/model mismatch pass.

### E. Hermes physical provider and model catalogs

`arnold/agent/providers/pool.py` defines provider keys/base URLs for at least:

```text
zhipu, kimi, minimax, mimo, openrouter, google,
deepseek, fireworks, xai
```

It supports environment base-URL overrides and Kimi endpoint selection based on
credential form. Blob:
`258ff944199fb2c76da3c2523c183724fb73c1fb`.

`arnold/agent/hermes_cli/models.py` exposes a wider and differently named catalog:

```text
openrouter, nous, openai-codex, copilot, copilot-acp,
zai, kimi-coding, minimax, minimax-cn, anthropic, deepseek,
fireworks, opencode-zen, opencode-go, ai-gateway, kilocode, alibaba
```

It also has aliases such as `glm`/`zhipu -> zai`, `github -> copilot`,
`kimi`/`moonshot -> kimi-coding`, and `claude -> anthropic`, plus dynamic model
discovery. Blob: `f65609aec2d5e117b52b4c87850e35e207a140b7`.

The two catalogs are not a single canonical namespace. T2.5 must freeze a
versioned provider-identity table containing canonical provider, accepted input
aliases, endpoint-origin policy, request protocol, auth scheme, and model spelling.
Dynamic discovery may report evidence, but it cannot expand the production
allowlist by itself.

### F. Fallback and retry authorities

The exact ancestor has these separate retry/fallback authorities:

1. profile fallback arrays and encoded phase-model fallback chains;
2. `fallback_chains.py` classification based partly on strings/messages;
3. worker-level configured fallback;
4. inner Shannon/Claude retry;
5. inner Codex retry;
6. runtime first-detected-agent substitution;
7. ambient auth/connection fallback;
8. Hermes/AIAgent provider/model fallbacks and retry loops;
9. provider key-pool rotation or endpoint selection;
10. outer fanout or parallel-to-sequential recovery;
11. diagnostic, resident, and cloud-wrapper retry loops.

`fallback_chains.py:15-34` defines retry classes; `:308-323` infers provider
family; `:384-429` classifies retryability and fallback eligibility. Blob:
`5d0db52631b588492ed5b5a6f1ea893422827b11`.

This is observational policy, not sufficient attempt authority. Text matching
must not authorize a provider effect. All retry/fallback decisions must consume a
typed transport failure receipt and mint a child T1.2 attempt before dispatch.

### G. Platform-wide direct-call and bypass surface

The following active families require call-graph inventory and either migration
to the common route dispatcher or an explicit fail-closed retirement:

- `agentbox/resident_profile.py`;
- `arnold/agent/adapters/codex.py`, `deepseek.py`, `shannon.py`, and one-shot
  adapters;
- `arnold/agent/agent/anthropic_adapter.py`;
- `arnold/agent/agent/auxiliary_client.py`;
- `arnold/agent/cron/scheduler.py`;
- `arnold/agent/run_agent.py`;
- `arnold/agent/tools/approval.py`;
- `arnold/agent/tools/mixture_of_agents_tool.py`;
- `arnold/execution/registries.py`;
- Megaplan `_core/worker_fanout.py`, workers, worker adapters, and `_impl.py`;
- `orchestration/parallel_critique.py`;
- resident `agent_loop.py` and `runtime.py`;
- `skills/subagent-launcher/fan.py` and `launch_hermes_agent.py`;
- cloud wrappers and scheduled scripts that invoke Codex, Claude, Shannon, or
  Hermes directly.

Important direct-client blobs at the ancestor:

| Surface | Ancestor blob |
|---|---|
| `arnold/agent/run_agent.py` | `4eb227eb774062386ee2d7e94f5cd75cdce1d133` |
| `arnold/agent/tools/mixture_of_agents_tool.py` | `3aa8a5e9bbdf9a4a485ab3729ee05c2b6e53c4f7` |
| `arnold/agent/agent/auxiliary_client.py` | `c09175589afc7f7b9dce3b83d378577becbfe85a` |
| Megaplan `workers/_impl.py` | `aaa1a80142eb17ce76127bc554f95c0c6083db32` |

`run_agent.py` includes direct Responses, Anthropic Messages, and Chat
Completions calls, plus retry/fallback behavior around invalid output, rate
limits, request failures, context compression, continuation, malformed tool
calls, and empty responses. The mixture-of-agents tool performs fanout and an
aggregator call. An “all configured routes” proof must include these internal
logical roles and each physical request, even when the user sees only one agent
turn.

## Required canonical artifacts

The implementation should produce this evidence directory:

```text
evidence/critique-ledger-recovery/T2.5/
  README.md
  generation.json
  route-inventory.json
  route-source-coverage.json
  provider-identity-registry.json
  route-conformance-matrix.json
  bypass-inventory.json
  offline-fixture-results.json
  installed-parity-results.json
  live-canary-plan.json
  live-canary-results.json
  credential-attestation.json
  negative-results.json
  verifier-result.json
  files.sha256
```

`route-inventory.json` must be generated from the exact installed configuration
snapshot and contain, for every source cell:

```json
{
  "route_id": "sha256:...",
  "source": {"kind": "built-in|user|project|pipeline|cli|env|native|resident|tool", "digest": "sha256:..."},
  "consumer": {"entrypoint": "...", "pipeline": "...", "phase": "...", "slot": "...", "tier": null},
  "fallback": {"ordinal": 0, "parent_route_id": null, "allowed_failure_codes": [], "attempt_budget": 1},
  "backend": "hermes",
  "provider": "deepseek",
  "endpoint_origin": "built_in",
  "endpoint_digest": "sha256:...",
  "credential_set_id": "opaque-owner-issued-id",
  "requested_model": "deepseek-v4-pro",
  "resolved_model": "deepseek-v4-pro",
  "effort": null,
  "tool_mode": "prompt_only",
  "request_protocol": "openai_chat_completions",
  "response_framing": "json",
  "capture_schema": "...",
  "contract_bundle_digest": "sha256:...",
  "parser_abi_digest": "sha256:...",
  "semantic_validator_digest": "sha256:...",
  "timeout_policy_digest": "sha256:...",
  "runtime_generation": "...",
  "status": "CANDIDATE"
}
```

No secret, authorization header, raw API key, cookie, session token, or
credential-derived reversible value may appear.

## Raw transcript, attempt health, and semantic-result contract

For each physical request, the authoritative sequence must be:

```text
resolve frozen route
  -> WBC admission/budget/effect key
  -> mint T1.2 physical attempt ID
  -> dispatch exactly once
  -> capture untouched provider bytes/frames and transport receipt
  -> bind with frozen T1.3 parser/bundle
  -> assign T1.2 terminal health
  -> only on SUCCEEDED create semantic result
  -> reduce required occurrence/round
```

Required transport receipt fields:

- T1.2 attempt ID and parent attempt/retry reason;
- route ID and runtime generation;
- backend, exact physical provider, endpoint-origin digest, credential-set ID;
- requested, resolved, and provider-reported actual model;
- provider request ID where supplied;
- request protocol, tool mode, and capture channel;
- request-start, first-byte, last-byte, and terminal timestamps from a trusted
  monotonic/attested source;
- HTTP/RPC status and typed provider error code, without secret headers;
- provider finish/stop reason and usage where supplied;
- raw frame count, byte count, digest, completeness, and response-loss status;
- timeout/cancellation authority;
- T1.3 binding/bundle/parser/runtime digests.

The receipt must be content-bound to the untouched T1.3 capture. It cannot carry
a separately reconstructed response object.

### Provider ambiguity reconciliation

T1.2 currently proposes `PROVIDER_FAILED` for provider timeout/no response. WBC
effect semantics must distinguish:

- `NOT_APPLIED`: provider rejected before accepting the request; may terminalize
  as `PROVIDER_FAILED`;
- `APPLIED`: exact response is captured; continue through T1.3;
- `UNKNOWN`: request may have been accepted but response custody is lost.

`UNKNOWN` must remain quarantined/incomplete until WBC reconciliation; it must not
be prematurely called `PROVIDER_FAILED` and retried as if no effect occurred.
T1.2 and WBC owners must decide whether this is represented as a nonterminal
attempt state or an external effect record. T2.5 must not add a seventh terminal
state unilaterally.

## Offline test matrix

These tests can be implemented before provider contact. Each row applies to every
relevant route/protocol/tool-mode combination.

| ID | Test | Expected authoritative result |
|---|---|---|
| O-01 | enumerate built-in, user, project, pipeline, CLI, env, native, resident, tool sources | every active cell has one route ID; zero unknown cells |
| O-02 | expand inheritance, symbolic premium, defaults, phase overrides, tiers, fallback arrays | deterministic full expansion with source provenance |
| O-03 | same alias via every accepted spelling | one canonical route identity; alias retained only as input provenance |
| O-04 | backend/model family mismatch | configuration rejected before attempt/effect |
| O-05 | unknown provider/model/effort/tool mode | route `INADMISSIBLE`; no provider call |
| O-06 | duplicate fallback physical route | configuration rejected as non-independent/redundant |
| O-07 | mutable dynamic catalog introduces unapproved model | remains unconfigured/inadmissible |
| O-08 | endpoint env override changes physical destination | new route ID and fresh approval required |
| O-09 | profile source shadowing | winning source and shadowed source both evidenced; only winner dispatchable |
| O-10 | source checkout versus built wheel/materialized entrypoint | identical route registry, parser, bundle, and schema digests |
| R-01 | realistic untouched success response | T1.3 accepts exact bytes; T1.2 `SUCCEEDED` |
| R-02 | explicit valid finding | semantic `FINDING` only after success |
| R-03 | explicit valid no-finding | semantic `NO_FINDING` only after success |
| R-04 | valid external-unverifiable where policy permits | semantic `EXTERNAL_UNVERIFIABLE`, complete-but-not-clean |
| R-05 | duplicate JSON key | `PARSER_FAILED`; raw retained; no result |
| R-06 | non-finite number | `PARSER_FAILED`; no result |
| R-07 | invalid UTF-8/encoding | `PARSER_FAILED`; no result |
| R-08 | prose before/after frame | `PARSER_FAILED`; no permissive extraction |
| R-09 | partial/truncated JSON or NDJSON | `PARSER_FAILED`; no result |
| R-10 | multiple Shannon result frames | fail exact framing; no result |
| R-11 | missing result frame | parser/producer failure per frozen T1.3 mapping; no result |
| R-12 | normalized object disagrees with raw | fail binding; raw wins |
| R-13 | wrong provider/model/tool/session/attempt/channel | contract failure; no result |
| R-14 | requested model differs from actual provider model | route mismatch; inadmissible pending explicit new route |
| R-15 | bundle/parser/schema/runtime digest mismatch | fail closed; no result |
| R-16 | single allowed invalid-pointer repair | same T1.2 attempt and raw capture; repair counter only |
| R-17 | any second repair or content repair | rejected; no new semantic result |
| T-01 | finish=`stop` with complete valid response | may succeed if all bindings pass |
| T-02 | finish=`length` | truncated/inadmissible unless frozen contract proves complete response and explicitly permits it |
| T-03 | finish=`tool_calls` in prompt-only route | contract failure |
| T-04 | finish=`content_filter`/safety refusal | typed provider/producer outcome; never no-finding |
| T-05 | empty response with nominal 200 | failure; hidden retry forbidden |
| T-06 | response bytes captured but finish reason missing | fail if the physical protocol guarantees finish metadata; otherwise route policy must explicitly attest limitation |
| T-07 | timeout before request accepted | typed not-applied provider failure; fresh fallback may be eligible |
| T-08 | timeout after possible acceptance/partial bytes | WBC `UNKNOWN`; quarantine, no automatic retry |
| T-09 | authoritative cancellation before dispatch | `CANCELLED`; no provider effect |
| T-10 | authoritative cancellation mid-stream | `CANCELLED` plus ambiguity evidence; no semantic result |
| F-01 | configured retryable primary failure | exactly one new child attempt for next pre-approved route |
| F-02 | nonretryable contract/parser failure | no provider fallback unless policy explicitly names a fresh diagnostic occurrence |
| F-03 | 401/403 auth failure | typed failure; no ambient agent substitution |
| F-04 | 429 with retry-after | bounded child attempt only; budget and reason evidenced |
| F-05 | 5xx/capacity | bounded child attempt only under frozen policy |
| F-06 | context-window failure | no invisible model change; explicit pre-approved child route or fail |
| F-07 | Codex/Shannon inner retry tries to dispatch | test fails; dispatcher must own the child attempt |
| F-08 | first-detected-agent runtime substitution | test fails before provider effect |
| F-09 | key rotation changes credential set | distinct physical attempt/credential-set evidence |
| F-10 | OpenRouter selects unpinned/unknown upstream | ambiguity; route inadmissible for authoritative use |
| F-11 | outer parallel-to-sequential retry | every provider call has its own T1.2 attempt; no merged success |
| F-12 | five no-findings plus one failed mandatory occurrence | round incomplete, not clean |
| B-01 | monkeypatch/import/path selects second parser/registry | fail closed |
| B-02 | legacy adapter parses/normalizes before neutral boundary | bypass scan/test fails |
| B-03 | direct provider SDK call without route admission | bypass scan/test fails |
| B-04 | helper/approval/summary/aggregator call lacks route role | bypass scan/test fails |
| B-05 | installed wheel omits registry/bundle/fixture | parity test fails |
| B-06 | editable source shadows installed generation | attestation fails |
| S-01 | logs/evidence include API key/auth header/cookie | hard fail and quarantine evidence |
| S-02 | raw key hash used as credential ID | hard fail; require opaque owner-issued ID/HMAC |
| S-03 | synthetic canary prompt contains repo/private data | hard fail before dispatch |

## Live canary requirements

Offline fixtures prove adapters and contracts, not actual availability, auth, or
wire compatibility. A live canary is required for every allowed physical
combination of:

```text
provider + endpoint policy + credential set + model + request protocol
+ response framing + tool mode + installed runtime generation
```

Multiple logical profile cells may reuse one transport canary only when all those
physical fields are identical. Each different schema/bundle/phase still needs
offline contract fixtures.

The canary procedure must be:

1. run only after T1.2/T1.3 freeze and WBC admission;
2. use the exact installed candidate generation, not an editable checkout;
3. resolve and persist the route before dispatch;
4. use a public synthetic prompt with a deterministic tiny structured response;
5. disable tools unless testing a separately approved tool-mode route;
6. cap input/output, wall time, attempts, cost, and concurrency;
7. make exactly one request per physical canary attempt;
8. retain untouched response bytes/frames plus provider request/finish metadata;
9. independently verify requested/resolved/actual provider and model, T1.3
   binding, T1.2 attempt state, and absence of secret leakage;
10. mark failures `INADMISSIBLE`, not clean, and do not automatically fan out;
11. record freshness and invalidate the result on generation, endpoint,
   credential set, protocol, bundle, parser, or model change.

A read-only `/models` or auth probe is useful preflight but cannot replace one
minimal completion for transport compatibility. A neighboring model's success
cannot certify another model. Provider status pages cannot certify credential or
schema behavior.

### Live acceptance matrix

| ID | Live assertion | Acceptance |
|---|---|---|
| L-01 | auth for exact credential set | accepted without exposing secret material |
| L-02 | exact requested/resolved model | provider accepts and actual model matches |
| L-03 | request protocol | exact installed adapter request succeeds |
| L-04 | raw response capture | byte/frame digest and completeness independently verified |
| L-05 | termination | expected finish reason and no truncation |
| L-06 | T1.3 admission | exact frozen bundle/parser/runtime binding succeeds |
| L-07 | T1.2 health/result | one attempt `SUCCEEDED`, one explicit semantic result |
| L-08 | timeout enforcement | supervisor boundary demonstrated without hidden retry |
| L-09 | provider aggregation | actual upstream pinned and evidenced, or route inadmissible |
| L-10 | fallback fault canary | primary synthetic failure produces one pre-approved child attempt only |
| L-11 | installed parity | verifier reads exact generation and route digests from running entrypoint |
| L-12 | cost/attempt custody | WBC budget and effect receipt reconcile exactly |

Do not deliberately submit invalid credentials or destructive tool requests to a
provider. Auth, timeout, malformed, and loss negatives should use a local faithful
transport emulator unless an owner-approved provider sandbox exists.

## Secrets-safe execution procedure

- Use an owner-issued opaque `credential_set_id`. If correlation is required,
  compute an HMAC with an audit-only secret; never store a plain hash of an API
  key.
- Never dump environment variables, process environments, request headers,
  cookies, query strings, or CLI auth stores.
- Redact authorization-bearing metadata before evidence creation; fail the run if
  redaction changes response-body bytes that T1.3 must bind.
- Use synthetic public prompts so preserving raw provider responses is safe.
- Store only an endpoint canonical digest and approved origin classification when
  the URL could contain tokens.
- Keep provider request IDs only after validating they are non-secret identifiers.
- Separate secret-owner attestation from model-routing verification: the verifier
  proves the opaque credential set used, not the secret value.
- Scan the complete evidence tree for known secret patterns and canary tokens
  before acceptance.
- Never paste provider failures into chat/notifications without the same
  structured redaction boundary.

## Exact acceptance criteria

T2.5 may be marked complete only when all of the following are true:

1. The tested generation is exact, immutable, installed, and independently
   attested.
2. T1.3 is frozen and accepted, with one parser/registry/bundle authority across
   source, wheel, materialized entrypoint, and fresh process.
3. T1.2 is frozen and every physical provider call has an attempt receipt before
   effect.
4. The deployment-snapshot route inventory covers every built-in, user, project,
   pipeline, CLI/env override, native, resident, tool, helper, and cloud-wrapper
   call surface.
5. Every active inventory entry is either `LIVE_VERIFIED` or `INADMISSIBLE`;
   there are zero active `CANDIDATE`, unknown, or silently ignored entries.
6. Every route has exact backend/provider/endpoint/credential-set/requested/
   resolved/actual model identity and contract digests.
7. Every allowed physical route passed its live canary at the accepted generation
   and within the approved freshness window.
8. Every relevant schema/bundle/tool-mode pairing passed realistic offline raw
   transcript fixtures and all negative cases.
9. No failed, cancelled, ambiguous, parser-failed, or contract-failed attempt has
   a semantic result.
10. No runtime substitution, inner retry, key rotation, provider aggregation, or
    outer retry can dispatch without a fresh pre-approved child attempt.
11. Provider-effect ambiguity remains quarantined and cannot trigger unsafe retry
    or clean reduction.
12. Duplicate or same-physical-route fallbacks do not count as independent.
13. The bypass inventory has zero unowned direct model calls and zero alternate
    parser/normalizer authorities.
14. Evidence contains no secrets and its manifest hashes independently verify.
15. An independent verifier, not the implementation process, returns accepted
    status from the evidence alone.

## What can proceed before T1.2/T1.3 freeze

Safe now, without provider contact:

- implement a read-only route-source scanner against the exact ancestor/candidate;
- generate an expanded static inventory for all built-in and fixture user/project
  profiles;
- inventory direct SDK/CLI call sites and hidden retry loops;
- define the canonical provider identity/alias table;
- detect duplicate fallbacks, unresolved aliases, default drift, and endpoint
  overrides;
- write faithful local transport fixtures for every request/response protocol;
- run parser/frame/termination/timeout/fallback negative tests against the current
  T1.3 candidate as non-acceptance feedback;
- define the route receipt schema and T1.2/T1.3 joins;
- prepare the live-canary plan without invoking it;
- build source/wheel/materialized parity harnesses;
- add a static prohibition on direct client calls outside the future dispatcher.

Must wait for accepted freezes:

- final route and receipt schema binding;
- semantic success/failure mapping;
- installed-entrypoint acceptance proof;
- live auth/model/transport canaries;
- authoritative fallback/fault canaries;
- any T2.5 completion claim.

## Dependencies and required owner decisions

### T1.3 owner

Before freeze, answer whether physical provider/model/request/finish metadata lives
inside the authenticated capture envelope or in a transport receipt bound to its
raw digest. Ensure the exact provider is not merely the worker name `hermes` or
`shannon`. Ensure bundle provider/model allowlists are generated from the route
registry or explicitly joined to it; the current pass-3 manifests appear to omit
configured forms such as Claude Haiku, Fireworks GLM spelling, and OpenRouter
DeepSeek while using broad worker-level provider labels.

### T1.2 owner

Freeze attempt identity before physical dispatch; make every hidden/internal
retry observable; bind route ID, parent, and typed reason. Reconcile WBC
`UNKNOWN` provider effect with the six proposed terminal states. Never allow a
failed route to mint a semantic result.

### WBC owner

Define effect keys, budgets, response-loss reconciliation, provider-attempt
admission, and independent cost/attempt accounting. A route canary is still an
external effect and must not bypass custody because it is cheap.

### Model-routing owner

Own the one provider identity registry, route source expander, allowed-route
manifest, timeout/fallback policy, and retirement negative tests. Do not let
runtime model discovery mutate the allowlist.

### Release/integration owner

Run live canaries only on the exact installed candidate; independently verify
evidence; block T2.6 if any route or bypass is unknown.

## Launch-ready Luna implementation/verification brief

> Act as GPT-5.6 Luna on checklist item T2.5, platform-wide. Begin from the exact
> release-owner-approved lineage and accepted frozen T1.2/T1.3 interfaces. Do not
> infer those interfaces from this preparation report; verify their commit/tree,
> installed generation, test evidence, and owner decisions first.
>
> Build one canonical route inventory and conformance harness for every model
> dispatch in Arnold: Megaplan built-in/user/project/pipeline profiles, phase/tier/
> fallback overrides, native managed routes, Agentbox/resident/cron surfaces,
> AIAgent helpers, tools, subagent launchers, direct SDK/CLI paths, and cloud
> wrappers. Expand every source cell to exact backend, physical provider,
> endpoint-origin digest, opaque credential-set ID, requested/resolved/actual
> model, effort, tool mode, request protocol, response framing, schema, frozen
> T1.3 bundle/parser/runtime digests, timeout, retry policy, WBC budget, and T1.2
> attempt policy. Dynamic provider/model discovery may attest availability but
> may not expand the allowlist.
>
> Eliminate or instrument every hidden retry, first-detected-agent substitution,
> ambient auth/connection fallback, key rotation, outer fanout retry, provider
> aggregation, and helper-model call. Every physical provider request must have a
> pre-effect WBC admission and fresh T1.2 attempt ID. Fallback is only a fresh,
> pre-approved child attempt under the same owner budget and typed failure reason.
> Provider-effect `UNKNOWN` remains quarantined. Never map any route failure to
> `NO_FINDING`.
>
> Bind untouched bytes/frames through the single frozen T1.3 authority. Add no
> alternate parser. If transport facts are separate, use an immutable
> `RouteTransportReceipt` bound to the T1.3 raw digest and T1.2 attempt. Prove
> duplicate-key, non-finite, invalid encoding, prose framing, partial/truncated,
> multiple/missing frame, wrong provider/model/tool/session/attempt/channel,
> actual-model mismatch, bundle/runtime mismatch, every finish reason, timeout,
> cancellation, response loss, and single-pointer-repair behavior.
>
> First produce offline inventory, fixture, bypass, and installed-parity evidence.
> Then, only under accepted WBC/release authority, run one bounded secrets-safe
> synthetic canary for every allowed physical provider+endpoint-policy+credential-
> set+model+protocol+framing+tool-mode+generation combination. Preserve raw
> capture and provider termination/request identity. Failed or ambiguous routes
> become `INADMISSIBLE`; do not automatically fan out.
>
> Write the canonical artifacts under
> `evidence/critique-ledger-recovery/T2.5/` exactly as specified in this report,
> with a content hash manifest and independent verifier result. Run the complete
> offline and live matrices. Leave zero active unknown routes, zero direct-call
> bypasses, zero hidden physical attempts, zero semantic results on failed
> attempts, and zero secret leaks. Do not claim T2.5 complete or change checklist/
> release state; return exact commit/tree/generation, route counts by state,
> tests, canary receipts, negative proofs, costs, limitations, and evidence hashes
> for independent review.

## Verification of this preparation

- The exact ancestor was inspected with `git show`/`git grep`; no checkout or
  ancestor mutation occurred.
- The active T1.3 pass-3 worktree was read only and remained dirty as found.
- No provider or cloud endpoint was contacted.
- No test was represented as a live route proof.
- The existing root worktree was heavily dirty before this task; no pre-existing
  change was modified.

This is a preparation and launch brief, not acceptance evidence.
