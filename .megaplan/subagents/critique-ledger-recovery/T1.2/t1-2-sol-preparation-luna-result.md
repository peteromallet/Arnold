# T1.2 Sol implementation brief — critique attempt health and semantic results

Status: **read-only preparation, not implementation and not completion**

Prepared from:

- recovery ancestor `6787d6363e8fc0603092913ae877db14f3b9fff8`;
- frozen candidate T1.3 pass-2 commit `ddb764b30cedf3774ff5ca665a85a62090607b21`;
- T1.3 pass-2 report `contract-bundles-repair-pass2-result.md`, whose verdict is
  explicitly **FAIL** despite its focused 87-test pass;
- queued T1.3 pass-3 brief `contract-bundles-repair-pass3-luna-brief.md`;
- the T1.2 acceptance contract in
  `docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md`.

No provider, cloud, SSH, runtime-owner, worktree, or code mutation was performed.
This brief does not claim that T1.3 is frozen or that T1.2 is complete.

## Executive implementation decision

Implement T1.2 as a domain ledger layered on the **frozen neutral-core T1.3
capture/binding API**, not as another parser and not as another normalization
pass.

Every physical critic dispatch must produce one immutable attempt record whose
terminal health is exactly one of:

```
SUCCEEDED
PROVIDER_FAILED
PRODUCER_CONTRACT_FAILED
PARSER_FAILED
SANDBOX_FAILED
CANCELLED
```

Only `SUCCEEDED` may produce one semantic result:

```
FINDING
NO_FINDING
EXTERNAL_UNVERIFIABLE
```

The current failure is not principally that the system used a weak model. The
root defect is that failures from multiple layers are collapsed into a normal,
unflagged critique check. That synthetic check is then treated as if the critic
had successfully concluded that it found nothing. The custody and gate layers
have no independent attempt-completeness evidence with which to reject that
fiction.

The reducer must therefore be fail-closed:

```
selected mandatory lens occurrence
  -> one or more immutable physical attempts
  -> exactly one accepted SUCCEEDED attempt
  -> exactly one semantic result
  -> admitted round only when every mandatory occurrence is complete
```

Six failed critics must yield an incomplete critique round, no admitted
zero-finding custody receipt, and no gate invocation. A failed attempt must
never have a semantic result attached to it.

## Hard dependency on T1.3

Do not start the mutating T1.2 implementation against T1.3 pass 2. The pass-2
report records two remaining false invariants:

1. Hermes and Shannon construct canonical capture JSON from normalized worker
   state/tool calls instead of preserving untouched provider response bytes as
   the sole parser input.
2. The registry/parser/binder/repair authority remains Megaplan-local instead of
   a neutral Arnold core used by every pipeline seam.

The queued pass 3 is therefore a hard prerequisite. Freeze these interfaces
before T1.2 implementation begins:

- exact raw transcript/frame capture, including failure paths;
- authenticated provider, model, tool mode, session, attempt, channel, and
  capture identity;
- canonical neutral parser/binder and its accepted/rejected health result;
- exact immutable route and contract-bundle identity;
- the single invalid-pointer, same-response repair boundary;
- content-addressed artifacts and installed/materialized entrypoint behavior.

T1.2 must import those interfaces. It must not copy the T1.3 parser, manifests,
route registry, raw/object binding rules, or repair logic. If pass 3 changes the
neutral package location or public names, adapt this brief's suggested filenames
to the frozen API rather than creating a second authority.

Pass 2 improves fail-closed admission but does not solve T1.2. In particular,
its `ContractOutcome` combines producer/parser/semantic health in one enum, and
its accepted-object outcome is selected as `FINDING` when any finding is flagged
and otherwise `NO_FINDING`. It has no independent per-physical-attempt ledger,
no exact selected-lens completeness reducer, and no policy-scoped external
unverifiability result. The old parallel reducer also does not transport an
untouched capture for each child; it returns an aggregate `WorkerResult` with
`raw_output="parallel"`. Depending on exact framing, pass 2 may reject that
aggregate rather than admit it, but rejection alone still cannot classify,
persist, retry, or complete individual critic attempts correctly.

## Evidence: the exact failure collapse at the recovery ancestor

### Producer and parse normalization

At `6787...`, `arnold_pipelines/megaplan/orchestration/parallel_critique.py`:

- `_parse_result` accepts an incoming `status/result=unverifiable` and creates a
  check with one `flagged: false` finding (lines 577-602 in the ancestor).
- If a worker returns multiple checks, it selects the matching check or simply
  the first dictionary instead of rejecting the response (lines 622-636).
- A wrong check ID is rewritten to the requested ID (lines 643-650).
- A missing/blank question is synthesized from the request (lines 651-656).
- `_on_unit_error` catches `CliError` and all other exceptions, persists a
  best-effort string/raw projection, and returns a successful-looking payload
  containing `_unverifiable_check_payload(...)`, no flags, and zero accounting
  (lines 684-723).
- Structural retry exhaustion takes the same synthetic-unverifiable route.
- The producer artifact names are iteration/lens based rather than physical
  attempt based, so retries can overwrite the prior attempt's evidence.
- The final reducer returns an ordinary successful `WorkerResult` with ordered
  checks and `raw_output="parallel"`.

This means provider errors, process errors, sandbox errors, parser errors,
contract errors, timeouts, and cancellations can all be projected into the same
semantic representation as a successful negative critique.

### Flag and custody collapse

At the ancestor:

- `arnold_pipelines/megaplan/orchestration/critique_status.py` recognizes both
  the structured `unverifiable` status and prose beginning with
  `unverifiable:`; this is annotation/inference rather than an authoritative
  result type.
- `arnold_pipelines/megaplan/flags.py` skips unverifiable checks when synthesizing
  flags.
- `arnold_pipelines/megaplan/orchestration/critique_custody.py` validates the
  normalized check IDs/findings/flags but has no attempt-health or selected-set
  completeness input.
- `write_critique_production_receipt` requires raw sources only when substantive
  findings exist (ancestor lines 259-273), computes `finding_count` from flags,
  and sets `admitted: true` unconditionally after those semantic shape checks
  (lines 274-303). Thus zero findings require no raw producer evidence.
- the custody validation consumed by the gate binds semantic artifacts and
  finding IDs, not every mandatory selection occurrence to a successful physical
  attempt and semantic result.

The exact dangerous sequence is therefore:

```
worker/transport/parser/sandbox failure
  -> broad exception
  -> synthetic status=unverifiable, flagged=false check
  -> skipped by flag synthesis
  -> finding_count=0
  -> admitted custody receipt
  -> gate sees no critique finding
```

### Gate and recovery behavior

The gate path compounds the collapse:

- `orchestration/gate_checks.py` classifies rate-limit/capacity/sandbox markers
  as operational unverifiability; existing tests explicitly allow those cases
  not to block a proceed decision.
- `handlers/override.py` can recover a blocked state based on those operational
  markers, including raw text markers.
- `gate_signals.py`, gate prompts, revise/feedback, and iteration pressure all
  consume the normalized semantic projection rather than an exact attempt
  completeness ledger.
- `orchestration/critique_runtime.py` has further recovery/normalization seams:
  outer parallel-to-sequential fallback, reparsing mutable/raw artifacts,
  unexpected-check filtering, and projection recovery. Those may be useful
  compatibility behaviors, but none may stand upstream of the new authority.
- `orchestration/outcomes.py` exposes only `CritiqueOutcome.COMPLETED`; it cannot
  represent incomplete attempt coverage separately from a clean semantic round.

## Full path map and required treatment

| Layer | Current path/seam | Failure now | T1.2 treatment |
|---|---|---|---|
| Lens policy | `audits/robustness.py`, `forms/provocations.py`, `audits/critique_evaluator.py` | Adaptive evaluator can select/skip catalog entries; coverage is not an immutable mandatory-occurrence authority | Freeze an exact content-addressed selection manifest before dispatch; at thorough/high every mandatory occurrence is selected |
| Parallel producer | `orchestration/parallel_critique.py` | Rewrites IDs, synthesizes fields, selects one of multiple checks, converts errors to unflagged checks | Dispatch through attempt service; no repair/normalization before T1.3 binding; reducer consumes typed receipts only |
| Worker fanout | `_core/worker_fanout.py` | `WorkerUnitResult` retains strings/fallback metadata, not typed terminal attempt health/raw binding | Carry attempt ID, manifest occurrence, raw-capture reference, T1.3 health, terminal state, and immutable attempt/result references |
| Batch/process bridge | `runtime/batch.py`, `_core/hermes_fanout.py` | Rich exceptions become `Exception(str(exc))`; timeout/cancel/process-exit provenance is lost; overall batch may be completed with child errors | Preserve structured outcome/cause through child boundary; emit per-child terminal attempt; batch completion is not critique completion |
| Fallback policy | `fallback_chains.py`, `_core/hermes_fanout.py`, `workers/_impl.py` | Configured, legacy MiniMax/OpenRouter, and ambient auth/connection fallbacks can create real provider attempts without durable attempt receipts | One bounded retry authority; every real dispatch gets a new attempt ID and parent/reason; suppress invisible ambient/legacy attempts |
| Hermes | `workers/hermes.py` | Internal empty-response retries and normalized/reconstructed capture hide attempt boundaries and untouched bytes | T1.3 raw capture first; each provider call is an attempt; classify provider versus parser/contract terminal state |
| Shannon | `workers/shannon.py` | Transcript NDJSON/stdout/file fallbacks and reconstruction can change parser authority | Preserve exact frames plus channel/session identity; neutral binder only; each dispatch/retry is recorded |
| Codex | `workers/_impl.py`, execution environment | CLI/process/sandbox/path failures can collapse to strings; trusted-container bypass changes isolation assumptions | Typed sandbox/process/provider boundary; bind sandbox attestation and raw transcript; do not infer semantic result |
| Sandbox | `runtime/execution_environment.py` and worker launchers | namespace/path/permission errors become operational unverifiability | `SANDBOX_FAILED`, with exact error/attestation; no result; retry only under bounded policy |
| Cancellation | `runtime/batch.py`, fanout bridge | cancellation/deadline is not wired through critique consistently and can become `RuntimeError` | Explicit authoritative cancellation becomes `CANCELLED`; retain issuer/reason/deadline; timeout is classified by cause, not automatically cancelled |
| T1.3 boundary | pass-3 neutral core | Pass 2 has exact bundles but incomplete raw authority/neutral placement | `SUCCEEDED` requires accepted frozen T1.3 binding for the exact attempt; all T1.3 rejection health maps to one non-success terminal state |
| Semantic reducer | parallel/runtime/flags | Absence of flags is treated as clean even when attempts failed | Semantic result exists only for succeeded attempt; clean requires every mandatory occurrence to be `NO_FINDING` |
| Custody | `orchestration/critique_custody.py` | Zero-finding receipt can be admitted without raw sources/attempt coverage | Receipt binds selection, every accepted attempt/result, plan, bundle, and raw digest; incomplete rounds cannot be admitted |
| Gate | `handlers/gate.py`, `gate_checks.py`, `gate_signals.py`, gate prompts | Operational unverifiability can proceed/recover | Gate receives only an admitted complete round; external unverifiability is explicit and never equivalent to clean |
| State/recovery | `critique_runtime.py`, `auto.py`, chain/history/state | Mutable latest artifacts and mtime/history can authorize recovery | Authority is content-addressed; mutable files/history are projections; crash recovery reduces immutable records idempotently |
| Non-Megaplan | `arnold/patterns/review.py`, `arnold/pipeline/model_seam.py`, native decorators, agent adapters | Alternate hooks/adapters may parse or accept output around the domain authority; generic one-shot step name `critique` is ambiguous | Use neutral T1.3 admission everywhere; opt into T1.2 only for an explicit critique-domain invocation; arbitrary review hooks must return domain receipts or remain non-authoritative |

## Exact domain contracts

### 1. Selection manifest

Create the authoritative manifest before any attempt is registered. It is
immutable and content-addressed. Minimum fields:

```json
{
  "schema_version": 1,
  "selection_manifest_id": "sha256:...",
  "iteration": 3,
  "round_id": "...",
  "plan_artifact": "plan_v3.json",
  "plan_sha256": "...",
  "robustness": "thorough",
  "policy_id": "...",
  "policy_sha256": "...",
  "catalog_sha256": "...",
  "contract_bundle_id": "critique:tool_enabled",
  "contract_bundle_digest": "sha256:...",
  "evaluator_attempt_id": "...",
  "evaluator_verdict_digest": "sha256:...",
  "mandatory_occurrence_count": 9,
  "occurrences": [
    {
      "occurrence_id": "...",
      "lens_id": "...",
      "lens_spec_sha256": "...",
      "question": "...",
      "category": "...",
      "mandatory": true,
      "route": {
        "provider": "...",
        "model": "...",
        "tool_mode": "..."
      },
      "expected_output_schema_sha256": "..."
    }
  ]
}
```

Rules:

- use occurrence IDs, not just lens IDs, so repeated lenses cannot alias;
- the evaluator verdict is an input to selection, not the authority;
- `other`/creative lenses may be additive, never substitutes for mandatory
  occurrences;
- thorough/high policy must select every mandatory catalog occurrence; if the
  repository names the top robustness levels `thorough`/`extreme`, codify the
  plan's “thorough/high” requirement as an explicit policy mapping and test it;
- changes to plan, robustness, catalog, lens text, route, schema, or bundle must
  change the manifest digest;
- every attempt and result must bind the same manifest ID and occurrence ID.

### 2. Attempt record

An attempt is one actual dispatch to one producer. Suggested lifecycle:

```
REGISTERED -> DISPATCHED -> one terminal state
```

Only the following terminal states are permitted:

| State | Classification |
|---|---|
| `SUCCEEDED` | Untouched capture exists; frozen T1.3 binder accepts exact route/runtime/bundle/raw/object; output semantically identifies exactly the selected occurrence |
| `PROVIDER_FAILED` | Auth, quota, rate limit, capacity, network, provider timeout, no response, provider crash, or provider-side refusal/availability failure |
| `PRODUCER_CONTRACT_FAILED` | Decodable/parseable response violates exact output contract: wrong/multiple occurrence IDs, missing fields, flag coercion, wrong provider/model/channel/attempt, raw/object disagreement, bundle/runtime mismatch, forbidden synthesis/discard |
| `PARSER_FAILED` | Captured bytes cannot be decoded/framed/parsed: duplicate key, non-finite number, truncation, prose around frame, malformed envelope, parser ABI failure, or missing parseable frame |
| `SANDBOX_FAILED` | Isolation setup, namespace, path policy, permission, mount, or sandbox runner failure |
| `CANCELLED` | An authoritative cancellation explicitly stopped the attempt before or during dispatch; record issuer/token/reason/deadline |

Provider wall timeout is normally `PROVIDER_FAILED` with a timeout code. A
deadline that triggers an explicit orchestration cancellation is `CANCELLED`.
Do not classify by string markers at the reducer; classify at the layer that has
the causal evidence.

Minimum immutable attempt receipt:

```json
{
  "schema_version": 1,
  "attempt_id": "...",
  "parent_attempt_id": null,
  "attempt_index": 0,
  "retry_or_fallback_reason": null,
  "round_id": "...",
  "selection_manifest_id": "sha256:...",
  "occurrence_id": "...",
  "plan_sha256": "...",
  "contract_bundle_id": "...",
  "contract_bundle_digest": "sha256:...",
  "provider": "...",
  "model": "...",
  "tool_mode": "...",
  "session_id": "...",
  "channel_id": "...",
  "capture_id": "...",
  "runtime_instance_digest": "sha256:...",
  "registered_at": "...",
  "dispatched_at": "...",
  "terminal_at": "...",
  "state": "PROVIDER_FAILED",
  "code": "provider_rate_limited",
  "detail": "...",
  "raw_artifact": "...",
  "raw_sha256": "sha256:...",
  "contract_binding_artifact": null,
  "contract_health_artifact": "...",
  "sandbox_attestation_artifact": "...",
  "cancellation_artifact": null,
  "request_metadata_digest": "sha256:...",
  "cost": 0.0,
  "input_tokens": 0,
  "output_tokens": 0
}
```

Keep the raw capture reference even on failure. If there truly are no response
bytes, record an authenticated empty/no-response capture artifact and provider
failure metadata; do not omit the evidence slot.

An attempt is append-only. A transition is represented by an immutable event or
finalized receipt backed by atomic/content-addressed storage; a retry never edits
or overwrites its parent.

### 3. Semantic result record

Create exactly one result only after `SUCCEEDED`:

```json
{
  "schema_version": 1,
  "result_id": "sha256:...",
  "attempt_id": "...",
  "round_id": "...",
  "selection_manifest_id": "sha256:...",
  "occurrence_id": "...",
  "result": "NO_FINDING",
  "admitted_payload_sha256": "sha256:...",
  "contract_binding_sha256": "sha256:...",
  "finding_ids": [],
  "external_policy": null
}
```

Semantics:

- `FINDING`: accepted producer output includes at least one flagged finding;
- `NO_FINDING`: the accepted producer explicitly completed that lens and
  reported no finding; it is never inferred from a missing result, empty flags,
  worker error, or synthetic payload;
- `EXTERNAL_UNVERIFIABLE`: an accepted successful critic conclusion that an
  external subject dependency cannot be verified under an allowlisted policy.
  It must bind a policy ID/scope, dependency, and evidence. It may not encode
  provider availability, parser failure, sandbox failure, cancellation, missing
  response, or output-contract failure.

`EXTERNAL_UNVERIFIABLE` may make the selected lens semantically complete under
the explicit policy, but it is not evidence of a clean plan and must not be
projected to zero findings.

### 4. Round reducer

The reducer operates only on selection manifests, immutable attempts, and
immutable semantic results. It must reject:

- a mandatory occurrence with no accepted succeeded attempt/result;
- a result attached to a non-succeeded attempt;
- multiple accepted succeeded attempts/results for one occurrence without an
  explicit deterministic winner/obsolescence relation;
- an attempt/result bound to another manifest, plan, bundle, route, iteration,
  or occurrence;
- missing or duplicated mandatory occurrences;
- mutable/latest-path evidence in place of content-addressed evidence.

Suggested round states:

```
INCOMPLETE
COMPLETE_FINDINGS_PRESENT
COMPLETE_CLEAN
COMPLETE_EXTERNAL_UNVERIFIABLE_PRESENT
```

`COMPLETE_CLEAN` is valid only if every mandatory occurrence has exactly one
accepted result and every such result is `NO_FINDING`. A round with any failed
mandatory attempt remains `INCOMPLETE`, even if all other critics return no
findings. A complete round containing `EXTERNAL_UNVERIFIABLE` is separately
visible and follows its policy/manual-review route; it never becomes clean.

Only a complete round may mint a critique custody receipt or advance the plan to
`critiqued`. The gate worker must not be invoked for `INCOMPLETE`.

## Retry, repair, fallback, cancellation, and crash rules

1. Every provider dispatch, including a configured route fallback, ambient
   fallback, internal empty-response retry, 429 retry, outer
   parallel-to-sequential fallback, or diagnostic retry, is a new physical
   attempt with a new ID and a durable parent/reason edge.
2. Replace competing hidden retry layers with one bounded critique retry
   authority. Worker/provider libraries may report retry advice but may not
   silently dispatch again.
3. T1.3's one invalid-pointer repair is not a new provider attempt: it repairs
   exactly one independently invalid pointer in the same captured response,
   preserves valid subtrees, and increments the contract object revision. Bind
   `repair_attempt=1` in the same attempt's T1.3 evidence.
4. A fresh model/provider call intended to fix malformed output is a new
   attempt, not T1.3 pointer repair.
5. A cancellation before launch creates a terminal cancelled attempt and causes
   zero provider calls. Mid-flight cancellation preserves capture/process
   evidence and cancellation authority.
6. Process timeout, SIGTERM/SIGKILL, child exit without result, and batch
   deadline retain typed provenance across the process bridge. They must not be
   converted to `RuntimeError(str(...))` before classification.
7. Crash/restart replays immutable attempt events and completes/retries under the
   same bounded policy. It cannot recover authority from mutable latest files,
   mtime, prose history, or a normalized critique projection.

## Legacy compatibility contract

Compatibility artifacts remain projections only:

- `critique_vN.json`, `faults.json`, `StepResponse.checks`, history/status text,
  and `CritiqueOutcome.COMPLETED` may be generated only from an admitted round;
- add an explicit incomplete/blocked domain outcome rather than overloading
  `COMPLETED`;
- `WorkerResult` may remain as a thin transport compatibility object but an
  error may not produce a synthetic check payload;
- mutable `evaluator_verdict.json`, per-lens raw filenames, and “latest” paths
  are convenience pointers to immutable authority, never authority themselves;
- old `status=unverifiable` and `unverifiable:` prose are legacy/unclassified
  query data. They cannot authorize a gate or be retroactively promoted into a
  successful attempt/result;
- `_recover_valid_critique_output`, unexpected-check filtering, wrong-ID
  rewriting, question synthesis, multiple-check selection, flag coercion, and
  prose inference must be removed from or placed strictly downstream of the
  authoritative boundary;
- the deprecated direct `_run_check` path must call the same attempt service or
  be retired;
- test-only monkeypatches of `select_active_checks` (including the M11 canary)
  must become explicit injected fixture manifests, never production selection
  overrides.

For historical artifacts that lack attempts, expose `LEGACY_UNCLASSIFIED` only
in migration/query views. Do not add that value to the six new-run terminal
states and do not allow legacy projection to satisfy new-run completeness.

## Installed entrypoints and non-Megaplan seams

The implementation is incomplete unless the same authority is exercised from:

- `python -P -m arnold_pipelines.megaplan critique` and the normal module form;
- `arnold_pipelines/megaplan/__main__.py` through CLI command mapping;
- `handlers/critique.py` and direct handler import;
- native manifest/workflow `handler_ref` and `runtime/inprocess_step.py`;
- chain and auto/resume/recovery paths;
- cloud M11 canary fixtures without contacting cloud;
- a freshly built and installed wheel outside the source tree;
- a materialized runtime/entrypoint wrapper.

Inventory these non-Megaplan seams after T1.3 pass 3 chooses the neutral core:

- `arnold/patterns/review.py::critique` accepts an arbitrary `critique_ref`;
- `arnold/pipeline/native/decorators.py` can map generic critique lenses;
- `arnold/pipeline/model_seam.py` is neutral transport/capture but currently has
  no critique attempt/result algebra;
- `arnold/agent/adapters/_oneshot.py` and the Megaplan one-shot compatibility
  adapter use `step="critique"` for generic one-shot requests.

Do not interpret every read-only one-shot as a critique-domain occurrence merely
because its transport step is named `critique`. All model output admission must
use neutral T1.3, but T1.2 applies only when an explicit critique-domain request
provides a selection manifest and occurrence identity. An arbitrary
`critique_ref` used to authorize a gate must return neutral domain receipts or
fail closed; otherwise it may remain a non-authoritative application callback.

## Suggested mutation scope for Sol

Exact neutral-core filenames must follow the T1.3 pass-3 freeze. A sensible
shape is:

### Neutral Arnold core

- extend the pass-3 neutral contract/capture package with small critique-domain
  modules equivalent to `critique_selection.py`, `critique_attempts.py`, and
  `critique_reducer.py`;
- add atomic/content-addressed attempt, semantic-result, and round-receipt
  storage using existing repository storage primitives;
- keep the T1.2 algebra independent of Megaplan prompt/gate policy;
- add explicit adapters from frozen T1.3 binding health to the six attempt
  states; no new parsing logic.

### Megaplan producer/orchestration

- `arnold_pipelines/megaplan/orchestration/parallel_critique.py`
- `arnold_pipelines/megaplan/orchestration/critique_runtime.py`
- `arnold_pipelines/megaplan/orchestration/critique_custody.py`
- `arnold_pipelines/megaplan/orchestration/critique_status.py`
- `arnold_pipelines/megaplan/orchestration/outcomes.py`
- `arnold_pipelines/megaplan/flags.py`
- `arnold_pipelines/megaplan/audits/robustness.py`
- `arnold_pipelines/megaplan/audits/critique_evaluator.py`
- `arnold_pipelines/megaplan/_core/worker_fanout.py`
- `arnold_pipelines/megaplan/_core/hermes_fanout.py`
- `arnold_pipelines/megaplan/runtime/batch.py`
- `arnold_pipelines/megaplan/fallback_chains.py`
- `arnold_pipelines/megaplan/workers/_impl.py`
- `arnold_pipelines/megaplan/workers/hermes.py`
- `arnold_pipelines/megaplan/workers/shannon.py`

### Megaplan consumers/projections

- `handlers/critique.py`, `handlers/structured_output.py`, `handlers/shared.py`
- `handlers/gate.py`, `handlers/override.py`
- `orchestration/gate_checks.py`, `gate_signals.py`, gate prompts
- revise/feedback/iteration-pressure consumers
- auto, chain, state, history, status, and resume/recovery projections
- relevant types/schema/runtime/manifest composition files.

### Neutral/native/adapter seams

- `arnold/patterns/review.py`
- `arnold/pipeline/model_seam.py`
- native decorators/dispatcher/in-process entrypoints
- `arnold/agent` contracts, dispatcher, and adapters
- Megaplan compatibility adapters only as thin delegates.

Do not alter T1.3 parser/bundle/repair semantics while implementing T1.2. If a
missing T1.3 capability is discovered, stop that slice and return it to T1.3
rather than implementing a local workaround. T1.2 owns attempt/result domain
truth; later effect-custody work may own execution authorization, but provider
dispatches cannot escape the attempt ledger in the meantime.

Recommended implementation order:

1. Freeze and independently review T1.3 pass 3.
2. Add neutral T1.2 types, invariants, content-addressed store, and pure reducer.
3. Add exact selection manifest and robustness policy.
4. Instrument per-dispatch producer/fanout/batch/retry/cancel/sandbox adapters.
5. Replace synthetic-unverifiable and normalization recovery with typed receipts.
6. Require attempt/result completeness in custody and gate entry.
7. Generate legacy projections only from admitted authority.
8. Close neutral/native/installed/materialized bypasses and run the adversarial
   suite.

## Adversarial verification suite

All provider-facing cases should use recorded exact captures/fixtures. Do not
contact providers or cloud.

### Pure state-machine tests

- each of the six terminal failure states rejects semantic result creation;
- `SUCCEEDED` requires accepted T1.3 binding and exactly one result;
- a forged `NO_FINDING` attached to any failed attempt is rejected;
- six selected mandatory lenses ending in the six failure states reduce to
  `INCOMPLETE`, no custody admission, no gate call;
- five succeeded/`NO_FINDING` plus one failure remains incomplete;
- all mandatory succeeded/`NO_FINDING` is the only zero-finding clean case;
- any `FINDING` produces findings-present;
- policy-allowed `EXTERNAL_UNVERIFIABLE` is separately complete but not clean;
- provider/sandbox/parser failure cannot be relabeled external unverifiable;
- missing, duplicate, wrong-occurrence, wrong-manifest, wrong-plan,
  wrong-bundle, and wrong-route receipts fail closed;
- concurrent duplicate terminals/results and crash/restart replay are
  deterministic and immutable.

### Producer/transport/parser tests

- provider auth, quota, rate limit, capacity, network failure, no response, and
  timeout -> `PROVIDER_FAILED`, no result;
- sandbox namespace/path/permission/setup failure -> `SANDBOX_FAILED`, no result;
- explicit pre-launch and mid-flight cancellation -> `CANCELLED`, no result;
- process exit without result and timeout kill retain typed cause across batch
  and fanout;
- invalid UTF-8, duplicate key, non-finite number, truncation, prose framing,
  malformed tool envelope, and parser ABI failure -> `PARSER_FAILED`;
- wrong/multiple check IDs, missing field, synthesized question, boolean/flag
  coercion, raw/object mismatch, wrong provider/model/session/channel/attempt,
  and bundle/runtime mismatch -> `PRODUCER_CONTRACT_FAILED`;
- no parser path selects the first check, rewrites IDs, filters unexpected
  checks, or infers success from prose;
- raw bytes/no-response evidence is present for every terminal attempt;
- Hermes, Shannon, and Codex recorded fixtures exercise successful, provider,
  parser, contract, sandbox, cancellation, retry, and capture-disagreement cases.

### Retry and repair tests

- every configured provider/model fallback is a separate child attempt;
- ambient auth/connection fallback cannot dispatch invisibly;
- internal empty-response and 429 retries cannot dispatch invisibly;
- outer parallel-to-sequential fallback is either removed or recorded within the
  same bounded budget;
- retry artifacts never overwrite parent raw/producer artifacts;
- T1.3 valid single-pointer repair remains the same attempt and increments only
  object revision;
- malformed/unparseable output cannot use pointer repair; a new provider call is
  a new attempt;
- retry exhaustion remains incomplete and never produces an unflagged check.

### Selection tests

- thorough/high requires every mandatory lens occurrence; adaptive evaluation
  cannot weaken the set;
- standard/light/bare selection follows an explicit versioned policy;
- repeated lens occurrences retain distinct IDs;
- `other` entries are additive;
- plan, catalog, lens text, robustness, route, schema, and contract-bundle changes
  alter the manifest digest;
- each attempt/result with a stale manifest is rejected.

### Custody/gate/compatibility tests

- custody rejects missing attempt/result completeness even when
  `finding_count=0`;
- custody requires raw/binding evidence for zero-finding results too;
- the gate worker is not invoked for incomplete rounds;
- `EXTERNAL_UNVERIFIABLE` does not produce a clean signal or automatic proceed;
- invert existing operational-unverifiable tests in
  `tests/arnold_pipelines/megaplan/test_gate_checks.py`: rate-limit, capacity,
  sandbox namespace, and raw marker text cannot authorize proceed/recovery;
- replace existing assertions in
  `tests/orchestration/test_parallel_critique.py` that worker error,
  flags-only sandbox output, or exhausted blank concern/evidence become normal
  unverifiable checks;
- add custody tests for six failed critics and mixed coverage;
- legacy artifacts remain readable/queryable but cannot satisfy new authority;
- `critique_vN.json`, flags, history, and `StepResponse` are byte-stable
  projections of the admitted round where compatibility requires it.

### Entrypoint and bypass tests

- source-tree and freshly installed wheel parity;
- `python -P -m arnold_pipelines.megaplan critique` parity;
- direct handler, CLI, native manifest, in-process, chain, auto/resume, and
  materialized wrapper parity;
- static scan forbids `_unverifiable_check_payload` or equivalent synthetic
  success in authoritative paths;
- static scan forbids alternate contract parsers/registries and direct mutable
  recovery around neutral T1.3;
- generic one-shot requests do not accidentally mint critique-domain success;
- explicit non-Megaplan critique-domain consumers must provide the same manifest,
  attempt, result, and reducer authority.

## Acceptance gates for T1.2

T1.2 may be proposed for independent review only when all of the following are
demonstrated from a clean commit based on frozen T1.3:

1. The six exact attempt terminal states are the only new-run terminal states.
2. No semantic result can exist unless its attempt is `SUCCEEDED` under the
   frozen T1.3 binding.
3. Every mandatory lens occurrence at thorough/high is present in one frozen
   selection manifest.
4. Six failed critics produce an incomplete round and cannot mint admitted zero
   findings.
5. Retry/fallback/cancel/sandbox/provider/parser/contract provenance survives
   process boundaries and crash recovery without mutable overwrite.
6. Custody and gate authorization bind the complete selected set and immutable
   attempt/result evidence.
7. Legacy artifacts are projections only and cannot bypass the new authority.
8. Source, installed-wheel, `python -P`, direct-handler, native, chain/auto, and
   materialized entrypoints agree.
9. The adversarial suite passes without provider/cloud access, and static bypass
   scans find no alternate parser, synthetic-unverifiable success, or invisible
   provider retry.
10. An independent Luna review and release-owner/integration evidence are
    recorded; passing local tests alone is not formal completion.

Immediate stop condition during implementation: if any attempt failure can be
projected as semantic success, if any real dispatch lacks an immutable attempt,
or if any mandatory selected occurrence can disappear before custody/gate, stop
and repair that authority boundary before continuing.
