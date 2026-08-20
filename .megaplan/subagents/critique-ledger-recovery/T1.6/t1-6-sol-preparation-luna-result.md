# T1.6 Sol preparation — one fail-closed custody boundary for every production effect

Prepared read-only by Luna on 2026-08-02. All production-code evidence below was inspected from the exact clean recovery ancestor:

`6787d6363e8fc0603092913ae877db14f3b9fff8`

The working tree was not used as evidence and no production code, provider, cloud, SSH, deployment, or external service was mutated or called. The T1.6 acceptance contract was read from `docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md` in the current planning tree because that plan post-dates the recovery ancestor.

## Executive finding

T1.6 is not an adapter-wiring task. The system has many WBC-shaped adapters and receipts, but no single production effect boundary owns authorization, dispatch, ambiguity, and reconciliation. The recurring pattern is:

1. Run Authority and Custody checks are optional or represented by caller-supplied booleans/callbacks.
2. A missing adapter silently selects a legacy direct call.
3. A present adapter manufactures a shadow/synthetic grant and calls a caller-supplied `apply_fn` directly.
4. A provider exception after dispatch is recorded as `FAILED`, although the provider may have applied the effect and merely lost the acknowledgement.
5. The next retry or model fallback can therefore repeat a Discord message, Git publication, model charge, SSH/deploy command, or other external mutation.
6. Append-only WBC/process evidence describes some of this after the fact but does not possess the exclusive capability to make the call.

That is the root defect at heart: **custody is observational and optional; it is not the exclusive capability boundary**. Sol should implement one neutral platform dispatcher in `arnold/workflow`, make raw transports inaccessible to ordinary callers, migrate every production mutation-capable surface to it, and fail closed when any owner record or durable WBC start is missing, stale, ambiguous, or unwritable.

## T1.6 contract distilled from the recovery plan

T1.6 must enforce all of the following before any Discord/message chunk, outbound webhook, Git push/PR publication, model/provider request, cloud/SSH/deployment action, or equivalent production effect:

- a current, authoritative Run Authority grant with a matching revision/fence/capability/target;
- a current Custody occurrence and lease/epoch whose owner and target agree with Run Authority;
- a durably reserved and started WBC attempt under a stable Global Logical Effect Key (GLEK);
- a complete canonical request identity and runtime/contract generation;
- a just-before-send reread of the authoritative records;
- zero provider calls when any prerequisite is absent, stale, synthetic, shadow-only, contradictory, or throws;
- `INDETERMINATE`, never `FAILED`, when a call may have been applied but its acknowledgement was lost;
- no resend while outcome is unknown;
- authoritative reconciliation before adopting `APPLIED` or permitting a retry after `NOT_APPLIED`;
- stable child GLEKs and a persisted manifest for chunked/partial delivery;
- no direct fallback, fake success, synthetic authorization, environment-selected old implementation, or test-only provider mode in production.

The named recovery-plan tests are mandatory, not illustrative:

- `test_missing_adapter_shadow_or_synthetic_auth_makes_zero_provider_calls`
- `test_adapter_exception_has_no_direct_fallback`
- `test_enospc_before_wbc_start_produces_zero_provider_calls`
- `test_provider_applied_ack_lost_is_indeterminate_and_not_resent`
- `test_partial_chunks_use_stable_child_gleks_and_do_not_duplicate`
- `test_every_torn_run_authority_custody_wbc_write_order_fails_closed`
- `test_git_push_or_pr_ack_lost_does_not_duplicate_publication`

The broader exit contract also requires 200 identical observations to yield at most one accepted notification and requires crash/ENOSPC before WBC start to make zero external calls.

## What already exists, and why it is not yet production custody

### Useful primitives to retain

- `arnold/workflow/execution_attempt_ledger.py`: `GlobalEffectIdentity` hashes environment, action target/version, effect family, provider target, canonical request identity, and boundary schema hash. This is a sound starting vocabulary, although identities at current call sites are incomplete.
- `arnold/workflow/attempt_ledger_store.py`: `SqliteAttemptLedgerStore` uses WAL and `BEGIN IMMEDIATE`, reserves GLEKs, enforces a unique terminal outcome per GLEK, treats exact duplicates idempotently, quarantines divergent conflicts, and represents `INDETERMINATE`.
- `arnold/workflow/effect_reconciliation.py`: correctly distinguishes `APPLIED`, `NOT_APPLIED`, and `UNKNOWN`, and treats query failure as non-authoritative.
- `arnold_pipelines/megaplan/custody/common_worker_dispatch.py`: has a useful ordering skeleton—record WBC start before executing its callback—and explicit post-call ambiguity handling.

These are ingredients. None is presently the only way to reach a provider.

### Systemic contract holes

1. **Optional/synthetic authority.** `arnold/workflow/effect_protocol.py:113-137` makes Run Authority and Custody callbacks optional; absence returns true. `EffectProtocol.dispatch` checks them only when configured. This turns missing control-plane wiring into synthetic authorization.
2. **Action-off is not a production barrier.** `effect_protocol.py:271` blocks only when the provider registry says `production_enabled=True`, while `effect_reconciliation.py` registers only fake/unknown providers and both are false. Unknown/unregistered production callers therefore do not acquire a meaningful gate.
3. **Adapters bypass the protocol dispatcher.** Delivery, Git, publication, and SSH adapters reserve/record an intent and then invoke arbitrary caller-provided `apply_fn` functions directly. The raw capability remains in caller hands.
4. **Shadow is accepted as authorization.** `custody/action_gate.py` has an empty default enforced-family set (`_DEFAULT_ENFORCED = frozenset()`), skips absent RA/Custody checks in its legacy verdict, and emits shadow authorization. `custody/wbc_runtime.py` admits `SHADOW_PASS`.
5. **Synthetic worker context.** `custody/worker_dispatch_wbc.py:159-172` constructs an action-off, enforcement-disabled facade, and `:404-429` manufactures grant/attempt identity with fence token zero. `workers/_impl.py:4701-4726` explicitly falls back to the legacy provider path if no WBC dispatch spec exists.
6. **Evidence is mistaken for custody.** `kernel/native_wbc.py` writes append-only NDJSON, explicitly says it grants no authority, generates random attempt IDs, has no GLEK/CAS, and silently no-ops when no evidence root exists. `custody/process_adapter_wbc.py` similarly records random-ID process evidence but cannot block, deduplicate, or reconcile a call.
7. **Inventory is not proof of adoption.** `evidence/wbc-boundary-inventory.json` has 1,328 rows, including 487 unmatched and 591 default-deny rows; its producer call sites are mainly event/receipt writers rather than provider dispatch points. Its own labels are non-authoritative. It cannot be used to claim boundary closure.

## Production effect-boundary inventory

### 1. Discord and other message delivery

#### Megaplan resident Discord

- `arnold_pipelines/megaplan/resident/delivery_effects.py:121-139`: absent action gate becomes `SHADOW_AUTHORIZED`.
- `delivery_effects.py:143-153`: delivery GLEK uses only target identity; it omits the exact payload/rendered-byte digest.
- `delivery_effects.py:155-174`: run/workflow/grant identities are synthesized from the attempt.
- `delivery_effects.py:197-207`: production/shadow state only produces a warning.
- `delivery_effects.py:219-260`: uses a random attempt UUID, records reserve/intent, calls `apply_fn` directly, and maps every apply exception to `FAILED`. An applied/lost-ACK delivery becomes retryable.
- `arnold_pipelines/megaplan/resident/discord.py:418-425`: routing through delivery effects is optional; otherwise execution falls through to direct Discord calls.
- `discord.py:485-557`: sends chunks with `channel.send` directly. Discord nonces help, but there is no durable per-child GLEK/manifest. Reply/thread failure paths send again; if the first call applied and its response failed, fallback can duplicate or change target.
- `discord.py:580-641`: `_send_via_delivery_effects` supplies an `apply_fn` that returns `{"delivered": true}` without calling Discord. This is fake success, not a transport boundary. Adapter failure/exception then falls back to direct delivery.
- `discord.py:864-881` and helper paths around `:1231-1250`: reactions are sent directly and retried without WBC ambiguity custody.
- Interaction-response paths around `discord.py:1610`, `:1655`, and `:1687` also send directly.
- `arnold_pipelines/megaplan/resident/cli.py:994-1001`: the production resident constructs `DiscordOutboundSink` without a delivery adapter at all.

#### Direct Discord DM and wrappers

- `arnold_pipelines/megaplan/discord_dm.py:63-77`: delivery adapter is optional.
- `discord_dm.py:129-154`: the function named `_fake_transport` performs the live Discord HTTP calls and sends all chunks beneath one parent GLEK.
- `discord_dm.py:176-217`: adapter exception falls back to direct `urllib` POST; absence also calls directly. Every exception becomes `send_failed`, with no indeterminate state.
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-discord-dm:9-19`: `MEGAPLAN_DISCORD_DM_ARNOLD_SRC` can select an alternate import root.
- The same wrapper calls `send_discord_dm` without an adapter and exits zero even when the returned delivery reports failure. This is both an environment bypass and fake process success.
- `agentbox_adapter.py` completion-DM handling calls direct DM delivery when no adapter exists and swallows all exceptions.
- `agentbox/notify.py`, `agentbox/reset_notifications.py`, and guardian notification paths construct/use direct outbound sinks.

#### Non-Megaplan message tools

- `arnold/agent/tools/send_message_tool.py:270-357`: chunks long messages directly, with no parent/child GLEK or persisted chunk manifest. A partial send followed by an error is flattened to an error result.
- `send_message_tool.py:400-420`: Telegram format failure causes a second send; the first may already have applied.
- `send_message_tool.py:481-666`: Discord, Slack, WhatsApp, Signal, SMTP, and Twilio paths make direct network calls and flatten ambiguous errors.
- `send_message_tool.py:239-267`: an environment/target heuristic returns `success=true, skipped=true` for a presumed cron duplicate. It is not an authoritative WBC terminal and is therefore a fake-success path.

#### Existing tests that encode unsafe behavior and must be inverted

- `tests/m10/test_resident_delivery_callers.py:170-188` expects lost acknowledgement to become `OUTCOME_FAILED`; T1.6 must change this to durable `INDETERMINATE` and prove no resend.
- Resident Discord tests currently validate direct chunk sends and reply/thread fallbacks; they need WBC parent/child expectations and ambiguity assertions.
- `tests/arnold_pipelines/megaplan/test_discord_dm.py` exercises a direct opener and therefore preserves the bypass contract.

### 2. Outbound webhook / generic HTTP publication

No dedicated outbound-webhook sink was found in the clean ancestor. The occurrences named “webhook” are predominantly inbound GitHub/GitLab configuration. That absence must not become a loophole:

- reserve a first-class `webhook.http` effect family now;
- treat generic mutating HTTP methods (`POST`, `PUT`, `PATCH`, `DELETE`) as production capability tunnels;
- route message-service web APIs and future outbound webhooks through the same dispatcher;
- statically deny direct mutating HTTP outside registered transport modules.

Direct HTTP-capable modules requiring classification include `arnold/agent/agent/anthropic_adapter.py`, `arnold/agent/hermes_cli/models.py`, browser providers, Home Assistant, `send_message_tool.py`, skills hub, security broker/client code, resident Discord, and auxiliary model/web tools. Read-only/authentication traffic may be explicitly classified separately, but “generic HTTP helper” cannot be a blanket allowlist entry.

### 3. Git, push, PR, issue, and publication effects

#### Existing Git adapter is scaffolding, not the actual production boundary

- `arnold_pipelines/megaplan/chain/git_effect_adapter.py` is referenced by its own tests/scaffolding but does not own the ordinary chain Git calls.
- It treats absent gate as shadow authorization, manufactures identity/grant data, and only warns in production.
- Its canonical request identity is target-only and omits commit/source OID, destination ref/base, expected remote OID/lease, and content digests.
- It uses a random attempt UUID, invokes caller `apply_fn` directly, maps all exceptions to `FAILED`, and optionally reconciles through caller callbacks.
- An `APPLIED` reconciliation can be reported as completed without first proving an authoritative WBC terminal was durably adopted.
- It hardcodes the fake-effect provider and can return an empty GLEK on protocol failure.

Unsafe tests explicitly preserve the bypass:

- `tests/m10/test_git_effect_adapter_13e4_13e5.py:713`: `test_route_remote_without_reconciliation_dispatches_directly`
- `tests/m10/test_git_effect_adapter_13e6.py:573`: `test_route_pr_no_reconciliation_query_dispatches`
- `tests/m10/test_git_effect_adapter_13e6.py:697`: `test_route_pr_production_warns_but_still_works`

#### Actual mutation paths

- `arnold_pipelines/megaplan/chain/git_ops.py` uses direct command execution for fetch/checkout/reset/rebase, add/commit, pushes, `gh pr ready`, and PR creation. Mutation sites include regions around lines 820+, 1015, 1055, 1829, 1912, 1999, 2009, and 2111+ at the recovery ancestor.
- `arnold_pipelines/megaplan/chain/__init__.py` directly performs stash/checkout/fetch paths.
- `arnold_pipelines/megaplan/loop/git.py` exposes a generic direct `_run_git` tunnel.
- `arnold_pipelines/megaplan/agentbox/github.py` directly creates PRs/issues/comments with `gh`; issue creation is around `:166-207`, commenting around `:210-253`.
- `arnold_pipelines/megaplan/agentbox/git_worktree.py`, cleanup, repository, and sync modules execute Git directly.
- `arnold_pipelines/megaplan/supervisor/pr_merge.py:328-341` calls the generic Git command runner for `gh pr view`. This exact call is read-only, but the shared runner is a capability tunnel and must not be allowlisted wholesale.
- `arnold_pipelines/megaplan/cloud/github_sync.py` makes its publication adapter optional. Its supposedly fake create/comment callbacks call live `agentbox.github` functions; adapter absence falls back directly.
- `PublicationAdapter` repeats the shadow/synthetic/direct-apply/exception-to-FAILED pattern; its request identity omits publication body digest, and its indeterminate recorder can swallow reservation failure while returning a GLEK as though it were durable.

A Git GLEK must include repository identity, operation, source OID, destination ref/base, expected old remote OID or force-with-lease value, exact title/body/payload digest, provider target, and contract/runtime generation. Reconciliation must query remote ref/OID or a durable PR/issue marker. Query failure or ambiguous matches remain `INDETERMINATE` and cannot grant a resend.

### 4. Model/provider effects

- `arnold_pipelines/megaplan/workers/_impl.py:4701-4726`: if WBC worker-dispatch metadata is missing, execution explicitly falls back to `_run_step_with_worker_legacy`.
- The legacy path makes direct Hermes, Shannon, and Codex calls. Regions around `:4960+` contain provider execution; `:5213+` contains cross-model fallback.
- Retry classes include stalls, timeouts, and connection failures. A timeout after the provider accepted a request can therefore charge/execute once and then trigger the same logical request on another model.
- `arnold_pipelines/megaplan/workers/hermes.py` directly invokes `agent.run_conversation` at several sites (including lines 1428, 1549, 1581, 1619, and 2319), including repair/fallback calls.
- Shannon/Codex worker routes spawn CLIs through generic command runners.
- `arnold_pipelines/megaplan/_oneshot.py` synthesizes ephemeral plan state/random naming and calls workers without a durable phase/WBC owner; its temporary state disappears after execution.
- `arnold/agent/adapters/deepseek.py` calls `AIAgent.run_conversation` or an injected transport directly and accepts environment key/base-URL fallbacks.
- `arnold/agent/agent/anthropic_adapter.py`, `arnold/agent/hermes_cli/models.py`, auxiliary/OpenRouter/model/transcription tools, and other native-agent model clients call providers without the shared authority envelope.

Provider output may be textual, but a model request is still a cost-bearing external effect and can also trigger provider-side work. Post-dispatch timeout is `INDETERMINATE`. A fallback model must be a new, explicitly authorized logical child attempt with its own GLEK and budget/custody decision; it cannot be a hidden resend of the same effect. Where a provider lacks reliable idempotency or status lookup, the conservative contract is at-most-once after durable start: no blind resend after ambiguity.

### 5. Cloud, SSH, deployment, and command runners

#### SSH/cloud adapters and providers

- `arnold_pipelines/megaplan/cloud/ssh_effect_adapter.py` makes the gate optional, accepts shadow/synthetic grants, computes target-only GLEKs that omit command/payload identity, warns rather than blocks in production, directly invokes `apply_fn`, and records all exceptions as `FAILED`.
- `arnold_pipelines/megaplan/cloud/providers/ssh.py` makes the adapter optional; `_maybe_route_through_wbc` directly applies when absent. Build/deploy/destroy fall through to direct execution, while `ssh_exec`, upload, archive, and down paths are always direct.
- `arnold_pipelines/megaplan/cloud/providers/base.py` constructs `SshProvider(spec)` without an adapter. Its process-adapter attempt is evidence only.
- `arnold_pipelines/megaplan/cloud/cli.py` constructs providers and directly invokes build, deploy, exec, resume, pause, retire, down, and destroy. Dynamic `provider.ssh_exec` calls can carry arbitrary shell.
- `arnold_pipelines/megaplan/cloud/providers/local.py` directly runs Docker/compose and mutates `.env`; compose fallback can repeat an ambiguous effect.
- `arnold_pipelines/megaplan/cloud/providers/on_box.py` runs arbitrary `bash -lc` commands and local copy/extract operations with evidence-only receipts.
- Install/sync, service, tmux, systemctl, watcher/repair, and agentbox lifecycle modules likewise reach command runners directly.

#### Shared subprocess surface

- `arnold/runtime/process.py::spawn` and `spawn_async` provide unrestricted argv execution with shell-injection hygiene but no RA/Custody/WBC custody. Megaplan re-exports this surface and adds tmux lifecycle execution.
- Direct subprocess families span agentbox cleanup/worktree/GitHub/repos/services/reconcile/tmux; Arnold Docker/local/SSH/singularity environments, code-execution/checkpoint/skills/model adapters; Megaplan workers, residents/subagents, chain Git, cloud providers, managed-agent/watchdog/repair, and execution modules.
- `custody/process_adapter_wbc.py` cannot authorize or reconcile these calls; it only records evidence around them.

Do not classify a command as safe by string heuristics. Introduce a structured `ProcessEffect` with exact executable identity, argv digest, cwd, allowlisted environment digest, mutation class, declared external target, and reconciliation contract. Arbitrary `bash -lc`, SSH command strings, environment-selected executables/import roots, or generic runner exports are capability tunnels: deny them in production or decompose them into explicitly registered effect types. Read-only probes may be registered separately, but a runner capable of both reads and writes cannot be globally exempted.

### 6. Non-Megaplan/native pipelines

- `arnold/execution/backend.py:401-410`: `_wbc_effect_protocol()` returns `None` by default.
- Its effect path persists intent only when that optional protocol exists, then executes the effect registry directly. The exception path around `:1461-1480` records `FAILED` even after a possibly-applied provider call.
- `arnold/pipeline/native/hooks.py:399-400` explicitly returns when no effect protocol is attached.
- `native/hooks.py:430-443` writes Native WBC evidence before the instruction, but that evidence is not authoritative custody.
- `native/hooks.py:445-466` can classify an intended duplicate as `retry`; there is no mandatory authoritative provider reconciliation here.
- `native/hooks.py:526-539` marks every instruction exception as `FAILED`, including acknowledgement-loss ambiguity.
- `arnold/kernel/native_wbc.py` is an audit surface, not a global effect ledger or authority owner.
- `arnold/runtime/effect.py:55-84` defines replay/idempotency metadata whose provenance is explicitly “recorded but never used for control flow.” It does not guard dispatch.
- Native agent browser, Home Assistant, web API, message, and model tools can make production mutations outside Megaplan and must adopt the neutral platform boundary.

T1.6 is incomplete if Megaplan is safe but a native pipeline or general agent tool can reach the same provider directly.

## Sol implementation design

### A. Put the boundary in a neutral platform package

Implement the exclusive effect boundary under `arnold/workflow`, not under Megaplan. Suggested modules:

- `arnold/workflow/effect_envelope.py`
- `arnold/workflow/effect_dispatcher.py`
- `arnold/workflow/provider_capabilities.py`
- `arnold/workflow/effect_errors.py`
- `arnold/workflow/effect_manifest.py`

Refactor/extend:

- `arnold/workflow/effect_protocol.py`
- `arnold/workflow/execution_attempt_ledger.py`
- `arnold/workflow/attempt_ledger_store.py`
- `arnold/workflow/effect_reconciliation.py`

The API must not accept optional booleans, optional adapters, caller-supplied `apply_fn`, or arbitrary callback-based reconciliation in production. Raw transports should have non-public constructors or require an unforgeable dispatcher-issued capability so ordinary callers cannot invoke them.

### B. Immutable authorized effect envelope

Define an immutable `AuthorizedEffectEnvelope` carrying at least:

- authoritative Run Authority record ID, revision, fence, owner, capability, scope, and target;
- authoritative Custody occurrence ID, lease ID, epoch/fence, owner, and target;
- WBC attempt ID, GLEK, durable reservation/start receipt, canonical intent digest, and store generation;
- contract-bundle generation and runtime vector/attestation generation;
- effect family, exact provider/target, canonical request digest, schema version;
- provider idempotency key and declared reconciliation capability;
- parent/child GLEK relation for multipart effects.

Do not permit strings named “grant” or projections/shadow receipts to satisfy this type. The dispatcher must reread owner records through frozen, authoritative owner ports and verify coherent cursors immediately before dispatch. Missing owner adapter, exception, timeout, stale revision, split-brain records, or unknown state is denial with zero external calls.

### C. Required cross-owner saga

For every production effect:

1. Reread Run Authority, Custody, runtime, and contract owners at coherent current cursors.
2. Canonicalize the complete immutable request and compute GLEK.
3. Durably reserve/start WBC and persist the complete intent (and full chunk manifest when applicable).
4. Reread all authoritative records just before the send; verify the same owner/fence/epoch/GLEK/runtime generation.
5. Make exactly one raw provider call through the registered transport.
6. Record only:
   - `COMPLETED` after an unambiguous positive acknowledgement is durable;
   - `FAILED` only after an authoritative definite pre-dispatch rejection or definite `NOT_APPLIED` result;
   - `INDETERMINATE` for any exception/timeout/cancellation/process loss after the call boundary begins.
7. Reread/reconcile through a registered provider capability:
   - authoritative `APPLIED`: durably adopt the terminal outcome, never resend;
   - authoritative `NOT_APPLIED`: retry only when the capability contract permits it, with the same provider key or a new fenced WBC attempt as specified;
   - unsupported, query exception, ambiguous/multiple matches, or `UNKNOWN`: remain `INDETERMINATE`, surface review, and do not resend.

An unknown state never grants authority, marks completion, or triggers a notification.

### D. Multipart/chunk contract

Before sending the first byte, render and persist an immutable chunk manifest containing renderer/schema version, total count, exact byte digest for every chunk, target, and parent GLEK.

Derive each child GLEK from:

`parent_glek + renderer_version + zero_based_index + total_count + sha256(exact_rendered_bytes)`

Each child receives its own reservation, start, provider idempotency key/nonce, and outcome. Resume uses the persisted bytes and retries only children authoritatively proven `NOT_APPLIED`; it never rerenders or resends an unknown child. Discord nonce can be derived from the child GLEK but cannot replace the ledger.

### E. Real provider capability registry

Replace the fake/unknown-only registry with explicit production capabilities per operation, not merely per provider:

- Discord message/reaction/interaction and DM;
- Slack/Telegram/email/SMS/other message tools;
- Git remote ref update, GitHub PR/issue/comment publication;
- each model transport and CLI;
- SSH execution, file transfer, cloud build/deploy/destroy, Docker/service lifecycle;
- generic outbound webhook HTTP;
- native pipeline effect implementations.

For each operation declare: native idempotency support, key mapping, authoritative query method, what proves `APPLIED`/`NOT_APPLIED`, ambiguity rules, and whether retry is ever legal. Unsupported reconciliation must be explicit and conservative, not a caller callback default.

### F. Static and runtime closure

Add a generated, reviewed boundary manifest and AST/Semgrep-style CI gate. Outside allowlisted raw transport modules, reject:

- direct `urllib`, `requests`, `httpx`, or `aiohttp` mutating requests;
- Discord sends/reactions/interactions and SDK publication calls;
- SMTP/Telegram/Slack/Twilio/provider SDK calls;
- `git`, `gh`, `ssh`, `scp`, `rsync`, `docker`, `systemctl`, `tmux`, and deployment commands;
- generic subprocess/runtime-process imports capable of mutation;
- dynamic `getattr`/wrapper aliases that reach these sinks;
- environment or `sys.path` switches that select an old/unattested implementation.

The scanner must resolve aliases and wrappers and generate a complete exception manifest; hand-maintained greps will drift. Runtime spy transports should independently prove call counts in adversarial tests.

Wrappers must require an authority-envelope reference and verified runtime vector, never credentials alone; must not accept environment-selected source roots/executables; and must exit nonzero for blocked, failed, or indeterminate outcomes.

## Exact mutation scope for Sol

### Core platform

- Refactor the four `arnold/workflow` modules named above and add the neutral envelope/dispatcher/capability/manifest/error modules.
- Make authoritative Run Authority/Custody/store ports mandatory constructor dependencies in production composition roots.
- Remove `production_enabled` warning semantics and all shadow/synthetic success from the production type path.

### Megaplan producers and transports

- Replace the implementation contracts of:
  - `resident/delivery_effects.py`
  - `chain/git_effect_adapter.py`
  - `cloud/publication_adapter.py` (or its actual publication-adapter path)
  - `cloud/ssh_effect_adapter.py`
  - `custody/worker_dispatch_wbc.py`
  - `custody/common_worker_dispatch.py`
- Wire the dispatcher through:
  - `resident/discord.py`, `resident/cli.py`, `discord_dm.py`
  - `agentbox_adapter.py`, `agentbox/notify.py`, `agentbox/reset_notifications.py`, guardian notification modules
  - `cloud/github_sync.py`, `agentbox/github.py`
  - `chain/git_ops.py`, `chain/__init__.py`, `loop/git.py`, Git worktree/cleanup/repository helpers
  - cloud provider factory, `providers/ssh.py`, `providers/local.py`, `providers/on_box.py`, cloud CLI/install-sync/wrappers
  - `workers/_impl.py`, Hermes/Shannon/Codex provider entry points, `_oneshot.py`, resident agent/subagent launch paths
  - service/tmux/systemctl/watchdog/repair/deployment wrappers that can mutate external state.

Delete direct fallback branches rather than retaining “backward compatibility” in production. Tests use an explicit fake dispatcher/capability, never adapter absence.

### Native/non-Megaplan adoption

- `arnold/execution/backend.py`
- `arnold/pipeline/native/hooks.py`
- `arnold/kernel/native_wbc.py` (clarify audit-only role; do not let it authorize)
- `arnold/agent/tools/send_message_tool.py`
- native agent/model adapters including DeepSeek/Anthropic/Hermes/OpenRouter paths
- `arnold/runtime/process.py` and mutation-capable environment/browser/Home Assistant/web tools.

Do not make this an unbounded hand edit of every subprocess call. Land the structured process-effect boundary plus generated manifest first, then migrate every mutation-capable unmatched sink until CI reports zero. Explicitly classify read-only probes so the scanner remains usable.

## Dependency and integration risks

1. **T1.1 Run Authority owner contract.** The recovery plan currently lists T1.6 as depending only on T0.2, but the ancestor does not expose a clearly authoritative durable Run Authority store at every boundary. T1.6 must integrate to the frozen/accepted owner port from T1.1; it must not invent another grant string or treat a projection as authority. This is a real dependency correction/coordination point.
2. **T1.3 contract bundles.** Contract/runtime bundle generation belongs in the envelope and GLEK so an old implementation cannot replay under a new contract.
3. **T1.5 occurrence/fixer.** T1.5 owns occurrence and simple-fixer policy; T1.6 owns the one safe external-effect worker it invokes. Avoid duplicating recovery state machines.
4. **T1.7 durable storage.** T1.7 owns byte/inode reservation, WAL/fsync, corruption, and ENOSPC semantics. T1.6 should consume that accepted storage API and prove zero calls unless reserve/start is durably acknowledged. Do not implement a competing store.
5. **T1.8 runtime/wrappers.** T1.8 owns runtime-vector and wrapper attestation; T1.6 requires those references and removes wrapper bypasses without duplicating deployment mechanics.
6. **T1.9 diagnostic launch.** All launch/stop effects must flow through this dispatcher, but launcher/provenance lifecycle remains T1.9.
7. **T1.10 notification UX.** T1.10 owns aggregation/throttling/clear messaging; T1.6 owns hard admission and effect identity. Notification throttling cannot substitute for GLEK custody.
8. **T2 routing.** Later capability/model routing must not bypass the dispatcher. A route change after ambiguity is a new authorized child attempt, not a retry loophole.
9. **Migration compatibility.** Existing tests deliberately expect shadow operation and direct fallback. Maintaining them would preserve the incident mechanism. Use explicit test composition rather than a legacy production mode.
10. **Deadlock/latency risk.** Just-before-send owner rereads and durable starts add latency and potential lock ordering. Define a single lock/order protocol: owner snapshots first, WBC transaction second, final immutable reread without holding provider locks, provider call last. Test crash at every edge.
11. **Provider reconciliation limits.** Some model/message providers cannot prove non-application. Do not fake certainty; these operations must remain indeterminate and require review rather than resend.
12. **Identity drift.** Target-only or body-less identities cause false dedupe; random-attempt identities cause duplicate effects. Canonical serialization and golden-vector tests are essential.

## Adversarial verification suite

### Core dispatcher and ownership

Create:

- `tests/arnold/workflow/test_effect_envelope.py`
- `tests/arnold/workflow/test_effect_dispatcher.py`
- `tests/arnold/workflow/test_provider_capabilities.py`
- extend attempt-ledger and reconciliation tests with real capability fakes.

Required cases:

1. Missing owner adapter, missing grant, missing custody, missing WBC store, shadow/synthetic record, projection-only record, owner exception, stale fence, stale epoch, target mismatch, and runtime-generation mismatch each make exactly zero raw calls.
2. Exhaustively/property-test every torn ordering of RA update, Custody update, WBC reserve/start, provider call, and outcome write. No incoherent order may call the provider or grant completion.
3. Crash/kill/ENOSPC before durable WBC start: zero calls. ENOSPC after start but before call: zero calls and recoverable pending intent. ENOSPC/lost ACK after call begins: `INDETERMINATE`, no resend.
4. Same GLEK/same request is idempotent; same GLEK/different request quarantines; same logical request/random attempt cannot evade GLEK uniqueness.
5. Reconciliation `APPLIED` adopts once; `NOT_APPLIED` retries only per capability contract; `UNKNOWN`, exception, timeout, conflicting/multiple matches never resend.
6. A raw transport cannot be instantiated/called without dispatcher capability.

### Delivery

- Invert the unsafe M10 delivery tests.
- Persist a 3+ chunk manifest, crash after each child, restart repeatedly, and prove each child is accepted at most once.
- Change renderer/config between restart and prove persisted bytes/child GLEKs are reused.
- Simulate Discord applied + response timeout for original, reply, thread, reaction, DM, and interaction paths; assert indeterminate and no fallback send.
- Run 200 identical observations/concurrent workers; exactly one notification parent GLEK is admitted and no more than one accepted external notification appears.
- Missing adapter is a construction error/zero-call denial, never direct delivery.
- Wrapper reports nonzero for blocked/failed/indeterminate and rejects source-root override.

### Git/publication

- Push applies remotely then local process loses ACK: reconcile remote OID, adopt, and never push twice.
- PR/issue/comment creation applies then ACK is lost: locate by durable marker/request digest, adopt exactly one publication; ambiguous matches remain indeterminate.
- Body/title/source OID/base/ref changes alter GLEK; runtime-only/random attempt changes do not create a duplicate logical publication.
- No reconciliation adapter/query: zero direct fallback.
- Force-with-lease mismatch is definite `NOT_APPLIED`, not permission to silently drop the lease or force-push.

### Model/provider

- Provider accepts a request and transport times out: one provider call, one cost-bearing attempt, no same-model retry and no cross-model fallback.
- Definite pre-dispatch rejection permits policy-authorized new child attempt; verify distinct explicit GLEK/authority and budget record.
- Missing WBC worker spec, missing phase ledger, `_oneshot`, native model tools, and provider CLI paths all make zero calls unless an envelope is supplied.
- Model identity includes exact messages/tool schema/model/settings/runtime contract; any material change yields a new explicit logical effect.

### Cloud/SSH/deployment/process

- SSH command applies and connection drops: indeterminate/no rerun.
- Upload partially applies: stable content/object child keys; reconcile or remain indeterminate.
- Docker compose first command applies but returns ambiguous failure: no alternate compose command fallback without authoritative `NOT_APPLIED`.
- Arbitrary `bash -lc`, generic `ssh_exec`, env-selected binary/import root, and direct process spawn are rejected outside registered process transports.
- Separate read-only probe tests prove the allowlist is narrow and cannot be changed to a mutating argv at runtime.

### Native and boundary closure

- Native backend/hook composition without dispatcher: zero provider calls, not legacy execution.
- Native instruction exception after effect dispatch: indeterminate, never ordinary failed/retry.
- Runtime spies monkeypatch every raw transport and assert the dispatcher is the sole caller.
- Add `tests/integration/test_effect_boundary_closure.py` to run the generated static inventory and fail on any new unmatched mutation-capable sink, alias, wrapper, or environment bypass.
- Golden inventory must explicitly include Discord/message, webhook HTTP, Git/GitHub, model APIs/CLIs, cloud/SSH/deployment, and generic process/native-pipeline families.

## Definition of done for T1.6

T1.6 is done only when all of these are simultaneously true:

- one neutral dispatcher is the exclusive production capability for every inventoried external mutation;
- authoritative Run Authority, Custody, WBC start, contract bundle, and runtime vector are mandatory and coherently reread;
- no shadow/synthetic authorization, optional adapter, direct fallback, or fake success remains in production composition;
- no provider exception after call start can become ordinary `FAILED`;
- chunked effects have durable stable child GLEKs/manifests;
- real provider reconciliation contracts are explicit and conservative;
- native/non-Megaplan effects obey the same boundary;
- wrappers and generic runners cannot bypass it;
- the generated boundary inventory has zero unmatched mutation-capable production sinks;
- all named recovery-plan and adversarial tests pass, including 200-observation notification dedupe and crash/ENOSPC/lost-ACK cases.

Anything less would improve telemetry while retaining the exact incident mechanism.
