# HARD FAIL

# T1.3 immutable producer/consumer bundles — independent Luna review pass 4

Date: 2026-08-02  
Reviewer: fresh GPT-5.6 Luna adversarial lane  
Scope: frozen T1.3 checklist and finite review matrix only

## Candidate identity and custody

Reviewed exactly:

- worktree: `/private/tmp/arnold-critique-recovery-contract-bundles-20260802`
- commit: `fe1786c298361454a73754536ecf7de2f7b4bd69`
- tree: `f11e71c1bbd6823a80bcba48c7bf88f655f44b8f`
- parent: `ddb764b30cedf3774ff5ca665a85a62090607b21`
- subject: `Harden T1.3 provider transcript authority`
- implementation report SHA-256 independently verified:
  `f5a052c08433d4442e0f4ed14f70e4a9d0c22d06fd19895cfb2a52b15de8f0fb`

The candidate was clean before and after review. I did not edit the candidate,
git state, code, cloud, provider, process owner, runtime owner, release state, or
checklist state. All adversarial execution used fresh `/tmp` directories or
one-shot processes and was removed afterward. No provider or cloud endpoint was
contacted. This review artifact is the only persistent write.

I did not trust the implementation report. Its focused tests and wheel claims
were independently reproduced where stated below.

## Binary verdict

**HARD FAIL.**

The happy-path parser and bundle hardening improved substantially, but two
finite-matrix invariants still fail with executable counterexamples:

1. route/session/attempt/channel identity is self-attested by the consumer and
   is not authenticated against the untouched provider stream; identical bytes
   can be replayed and accepted under a different allowed model and session;
2. a real alternate Arnold model-output boundary still parses and returns typed,
   passed authority without the shared bundle or any raw provider transcript.

There is also a structural ownership failure: the registry, binder, repair, and
preflight authority remain implemented and instantiated in the Megaplan package.
`arnold.pipeline.contract_bundles` is a neutral type/parser/callable container,
not the neutral platform-wide bundle authority required by the pass-3 brief.

Either counterexample is sufficient for HARD FAIL. They are
not provider-availability questions and require no redesign beyond the frozen
contract: transport authenticated identity with the raw capture and migrate or
fail-close the real alternate consumers.

## Frozen contract reviewed

The recovery plan T1.3 contract is at
`docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md:291-299`:

- bind prompt, transport/capture schema, parser ABI, normalizer, semantic
  validator, fixtures, and provider assumptions by content digest;
- forbid required-field synthesis/discard and mutable `latest` lookup;
- permit one invalid-pointer-only repair in the same object/bundle, followed by
  full revalidation;
- repair cannot alter valid fields or change bundles.

The frozen pass-3 brief additionally requires:

- untouched provider bytes/frame as the sole parser authority;
- authenticated exact provider/model/tool/session/attempt/channel identity;
- no normalized object, reconstructed JSON, legacy envelope, or post-processed
  state may mint acceptance;
- one neutral Arnold-core registry/binder/repair/preflight authority reused by
  Megaplan;
- unsupported non-Megaplan producer paths fail closed;
- environment/import/monkeypatch/path/compatibility aliases cannot select a
  second registry or parser;
- corruption, substitution, truncation, cross-route, replay, installed/source,
  and exact critique/finalize consumer negatives.

## Ranked blocking counterexamples

### 1. Cross-route and cross-session replay is accepted because identity is self-attested

This is the most direct failure of the finite matrix.

The production data structure does not carry a neutral `ProviderTranscript`
object or an authenticated transport receipt. `WorkerResult` is a mutable
dataclass whose `provider_transcript` is only `str | None`; provider/model/session/
channel/attempt are separate mutable fields
(`arnold_pipelines/megaplan/workers/_impl.py:709-750`).

At the two exact consumers:

- critique reads `worker.provider_transcript`, freezes the already-produced
  payload, and supplies `provider=agent`, `model=worker.model_actual`, plus a new
  `runtime_instance` made from the other worker fields
  (`orchestration/critique_runtime.py:953-993`);
- finalize repeats the same construction
  (`handlers/finalize.py:2440-2477`).

The compatibility binder then constructs a fresh `ProviderTranscript` from
those caller assertions inside `parse_output()`
(`contract_bundles/__init__.py:678-732`). `ProviderTranscript.capture()` checks
shape and hashes the raw bytes, but it does not authenticate who asserted the
metadata (`arnold/pipeline/contract_bundles.py:159-209`). The binding then hashes
the same caller-provided `runtime_instance`. That proves internal equality
between two copies of a claim; it does not prove the claim came from the provider
or adapter.

The exact upstream physical provider is also collapsed to the worker name.
Hermes derives a physical provider/auth channel from its effective model at
`workers/hermes.py:2794-2805`, but critique/finalize pass `provider=agent`, which
is merely `hermes`. DeepSeek, Zhipu, Fireworks, and OpenRouter routes are therefore
not distinct provider identities in the contract binding.

#### Independent Hermes replay probe

One recorded raw response was bound twice through production
`CONTRACT_AUTHORITY.bind_output`: first as DeepSeek/session A/attempt 0, then as
GLM/session B/attempt 99/forged worker channel.

Observed:

```text
deepseek-v4-pro True accepted
  raw sha256:c4b1dd3db3c663bb4419a4072ec6cf47ec49fa9b9059d772c9646f243a7bd9be
  output sha256:5736feaaf330184b4ffcf9fa2df7ae05a89850c555b32f56f809a6911562ab89
  runtime sha256:15e70629edf9f17c78b39f48d97b10c678dfb65dcdfb13cc935017c6786ed8ae
glm-5.2 True accepted
  raw sha256:c4b1dd3db3c663bb4419a4072ec6cf47ec49fa9b9059d772c9646f243a7bd9be
  output sha256:5736feaaf330184b4ffcf9fa2df7ae05a89850c555b32f56f809a6911562ab89
  runtime sha256:8239712d35c7ccb1d8e36b95778d4e173f318e22f5db08c89c5c74372d80c3b6
```

The different runtime digest merely content-addresses the forged second claim.
Both route identities were accepted for identical raw bytes.

#### Independent Shannon embedded-identity contradiction

This counterexample is stronger because the recorded Shannon NDJSON itself names
`shannon-fixture-session` and `claude-sonnet-4-6`. `_parse_shannon()` extracts the
result object but does not compare event model/session identity with capture
metadata (`arnold/pipeline/contract_bundles.py:252-296`).

The exact same NDJSON was accepted twice:

```text
embedded=shannon-fixture-session claude-sonnet-4-6
claimed=shannon-fixture-session claude-sonnet-4-6 attempt=0
accepted=True accepted
raw=sha256:48ea96c4317455538847b9cb1d0950bca7ff6b6126f2b9218cf813960a2b2fef

embedded=shannon-fixture-session claude-sonnet-4-6
claimed=forged-session claude-opus-4-7 attempt=77
accepted=True accepted
raw=sha256:48ea96c4317455538847b9cb1d0950bca7ff6b6126f2b9218cf813960a2b2fef
```

This violates exact upstream route/session/attempt/channel binding, cross-route
substitution rejection, and replay rejection. Existing
`test_binding_rejects_channel_or_retry_attempt_drift` does not cover it: that test
creates a binding with one claim and validates it against a different claim. In
production, the binder creates and validates the binding from the same current
mutable fields, so a substituted claim agrees with itself and passes.

#### Exact-byte custody is also absent

Even without replay, the production type cannot preserve untouched bytes:

- `ProviderTranscript.capture` accepts a Python `str` and manufactures bytes by
  UTF-8 encoding it (`arnold/pipeline/contract_bundles.py:182-188`);
- `WorkerResult.provider_transcript` is a string
  (`workers/_impl.py:746-750`);
- Codex output files are read with `errors="replace"` before becoming the
  transcript (`workers/_impl.py:3913`, `3972`, `4125`);
- Hermes uses normalized `result["final_response"]`, including a possible
  follow-up result, as the transcript (`workers/hermes.py:1420-1497`, `2844`);
- Shannon likewise stores its selected decoded `raw` string (`workers/shannon.py:3130`).

Original byte corruption can therefore be normalized or replaced before the
neutral parser ever sees it. A digest of re-encoded text is not a digest of the
untouched provider bytes/frame.

Required bounded correction: carry one immutable capture/receipt from the adapter
containing the original bytes/frames and adapter-authenticated physical route,
model, session, attempt, and channels. The consumer must verify that object; it
must not manufacture its provenance from `WorkerResult` fields.

### Runtime-attestation limitation (not a T1.3 blocker): in-process code takeover

The candidate defends against rebinding module names and registry globals, but an
arbitrary actor already executing inside the interpreter can replace a Python
function object's `__code__`, so every captured reference observes the changed
behavior. `ImmutableContractAuthority` stores callables directly
(`arnold/pipeline/contract_bundles.py:318-359`).

The Megaplan enforcement check verifies code location for its own functions, but
for the neutral parser it checks only `__module__`
(`contract_bundles/__init__.py:908-951`). It does not compare the invoked parser's
code/artifact digest at the consumer boundary.

Independent disposable-process probe:

```python
import arnold.pipeline.contract_bundles as neutral
from arnold_pipelines.megaplan.contract_bundles import CONTRACT_AUTHORITY

def forged_parser(capture):
    return VALID_CRITIQUE

neutral.parse_provider_transcript.__code__ = forged_parser.__code__
neutral.parse_provider_transcript.__globals__["PAYLOAD"] = VALID_CRITIQUE

_, binding, health = CONTRACT_AUTHORITY.bind_output(
    "critique", VALID_CRITIQUE, b"not-json-at-all",
    provider="hermes", model="deepseek-v4-pro",
    tool_mode="tool_enabled", runtime_instance=SELF_ASSERTED_RUNTIME,
    expected_ids=["C1"],
)
```

Observed:

```text
before arnold.pipeline.contract_bundles .../arnold/pipeline/contract_bundles.py
after  arnold.pipeline.contract_bundles <stdin>
RESULT True accepted
raw sha256:317455fa1c343819869154cfbcc6885b64d968c11dc170db0462eed0fb1a4b52
```

Malformed bytes became an accepted no-finding-shaped critique through the
captured parser.

This is **not** used as a T1.3 local blocker. Arbitrary in-process code-object
takeover can defeat any Python-only guard and belongs to the T1.8/T1.9 fenced
generation, installed-entrypoint provenance, and process-isolation boundary. The
probe is retained so those owners do not overstate what local frozen defaults
protect. T1.3 should not grow a bespoke runtime integrity system to address it.

### 2. A real alternate Arnold model seam still accepts without the shared boundary

The pass-3 brief requires every Arnold pipeline/model seam to migrate to the
neutral authority or fail closed. The candidate changes no real non-Megaplan
consumer.

`arnold.pipeline.model_seam.capture_step_output()` still:

1. accepts a Python mapping or JSON string;
2. parses it independently;
3. runs registered normalizers and compatibility projections;
4. returns a `ContractResult` with `authority_level="typed"` after its own audit.

Evidence: `arnold/pipeline/model_seam.py:972-1025`. A product-local `AgentStep`
uses that path directly and carries its contract result
(`arnold_pipelines/megaplan/steps/agent.py:69-117`). Neither imports nor invokes
`CONTRACT_AUTHORITY`.

Independent probe with an enforced model invocation and a Python mapping—no raw
provider transcript, route binding, bundle, session, attempt, or channel:

```text
passed typed {'output': 'accepted-without-provider-transcript'}
arnold.pipeline.model_seam
```

This is a live hidden bypass, not merely a source grep. It violates neutral
platform-wide authority and “no normalized-state reconstruction.”

The candidate test
`test_unsupported_pipeline_model_route_fails_closed_at_shared_authority`
(`tests/arnold_pipelines/megaplan/test_contract_bundles.py:896-906`) calls the new
authority with a fake unsupported step and observes rejection. It does not call
the actual alternate path and therefore does not prove bypass closure.

Required bounded correction: route every model-owned output admission through
the neutral authority with a real capture/binding, or make unsupported model
output fail closed. A test must exercise each actual consumer, not call the new
API hypothetically.

### 3. The platform-wide authority remains Megaplan-owned

This is a structural violation and explains blocker 2.

`arnold.pipeline.contract_bundles` owns:

- neutral error/types;
- raw parser helpers;
- `ProviderTranscript`;
- a dataclass container that accepts injected callables.

It does **not** own the shipped bundle registry, manifest loader, binder,
normalizer, schema/semantic validation, repair boundary, or preflight.

Those are implemented only in
`arnold_pipelines.megaplan.contract_bundles.__init__`. The sole production
`CONTRACT_AUTHORITY` is constructed there by injecting Megaplan's
`_capture_authority_bind()`, `repair_once`, and `preflight_contract_bundles`
(`contract_bundles/__init__.py:1663-1723`). Repository search finds no
`CONTRACT_AUTHORITY` under `arnold/`; only the Megaplan object and its two
Megaplan consumers exist.

Consequently a non-Megaplan pipeline cannot reuse the actual authority without
depending on Megaplan policy. The neutral module's type ownership is genuine,
but the pass-3 requirement was neutral **registry/binder/repair/preflight
ownership**, not merely a neutral callable holder.

Required bounded correction: move the policy-neutral authority implementation
and registry contract into `arnold.pipeline`; leave Megaplan schema/prompt policy
as injected, content-addressed bundle data or a thin adapter. Then migrate actual
consumers. Do not create a second parser or registry.

## Finite-matrix result

| Invariant | Result | Evidence |
|---|---|---|
| Candidate identity/clean lineage | PASS | exact commit/tree/parent; clean before/after |
| Strict duplicate-key/non-finite/UTF-8/prose/truncation rejection at narrow neutral parser | PASS | focused tests reproduced |
| Untouched raw provider bytes are sole production parser authority | **FAIL** | string/re-encoding/replacement and normalized `final_response` before boundary |
| Exact physical provider/model binding | **FAIL** | worker label `hermes`; identical bytes accepted as DeepSeek and GLM |
| Exact session/attempt/channel binding | **FAIL** | Shannon embedded identity contradicted by accepted caller claims |
| Cross-route substitution/replay rejection | **FAIL** | two executable replay probes |
| Neutral `arnold.pipeline` registry/binder/repair/preflight owner | **FAIL** | authority implementation/instance remains Megaplan-only |
| Megaplan reuses neutral authority | PARTIAL | neutral types/parser are reused; real bundle authority is not neutral |
| Alternate consumer bypass closure | **FAIL** | `capture_step_output` returns typed/passed authority without bundle/raw |
| Deep immutable manifest containers | PASS | tuples/mapping proxies; old base-list mutation closed |
| Canonical registry object/rebind defense | PASS at ordinary name-rebind boundary | frozen defaults and use-site manifest reread |
| In-place parser/callable takeover | OUT OF T1.3 | limitation recorded for T1.8/T1.9 runtime provenance/isolation; not used in verdict |
| Content-addressed manifests/artifact references | PASS for shipped source/wheel files | independent wheel build/preflight |
| Source/installed artifact inclusion/parity | PASS for inspected artifacts | independent archive build/install |
| Exact model allowlist versus family spoof | PASS at current logical worker/model table | prior family-spoof bug closed |
| One independently derived invalid-pointer repair | PASS in reproduced focused suite | prior caller-forged error-map bug closed |
| Repair cannot alter valid fields/change bundle | PASS in reproduced focused suite | bounded repair and canonical bundle checks |
| Critique immutable admitted payload use | PASS at inspected local projection boundary | frozen authority then materialized projection |
| Finalize admitted payload reset before harness derivation | PASS at inspected local projection boundary | reset at `finalize.py:2521-2569` |
| Raw preserved on local critique/finalize failure path | PASS for selected worker string | raw artifact written before health check; original network bytes still absent |
| Self-authenticated receipt rejection | **FAIL** | consumer creates receipt from current mutable assertions |

## Independent test reproduction

### Focused T1.3/dependency matrix

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 \
python -m pytest -p no:cacheprovider -q \
  tests/arnold/pipeline/test_contract_bundles.py \
  tests/arnold_pipelines/megaplan/test_contract_bundles.py \
  tests/orchestration/test_critique_custody.py \
  tests/orchestration/test_parallel_critique.py \
  tests/arnold_pipelines/megaplan/test_m8a_finalize_wiring.py \
  tests/arnold_pipelines/megaplan/test_model_seam_recovery.py \
  tests/arnold_pipelines/megaplan/test_phase_wbc_resume_lifecycle.py

116 passed in 2.56s
```

### Producer/adapter matrix

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 \
python -m pytest -p no:cacheprovider -q \
  tests/test_workers_shannon_session.py \
  tests/test_shannon_adapter.py \
  tests/test_codex_adapter.py \
  tests/workers/test_hermes_execute_recovery.py \
  tests/workers/test_hermes_tool_markup.py \
  tests/workers/test_hermes_double_encoded_json.py \
  tests/orchestration/test_codex_output_schema.py

48 passed in 0.25s
```

These passes are real but do not include the counterexamples above.

### Independent source/installed wheel proof

I exported exact commit `fe1786c...` with `git archive` to disposable scratch,
built `arnold-0.23.0-py3-none-any.whl`, installed it with `--no-deps` into a fresh
`--system-site-packages` venv, changed working directory away from the source,
and imported/preflighted the installed artifact.

Observed installed neutral path:

```text
.../venv/lib/python3.11/site-packages/arnold/pipeline/contract_bundles.py
```

Observed four bundle digests:

```text
critique:prompt_only sha256:4affe2b5980c38fc3cf7ffb7b02244e7a81a47b01e5c03027c885703b1c87916
critique:tool_enabled sha256:8602937a5c9187f8a519367c0009f368c42eef17f37a36d4a47556f1d1f74b81
finalize:prompt_only sha256:718cf90f237585d8a89e9a5cb158c913e60c876cf7e3d7afd1e2c1f11a9b8404
finalize:tool_enabled sha256:60d1f5486cd8cad2f7cc7d24d33e528433d091b30b4903aee3f67b939d3622cc
```

Wheel inventory included:

- `arnold/pipeline/contract_bundles.py`;
- all four manifests;
- critique/finalize golden fixtures;
- Hermes JSON fixture;
- Shannon JSONL fixture.

This establishes artifact inclusion and local source/installed parity. It does
not repair the route/session identity or alternate-consumer flaws, which
reproduce from the installed design as well. Arbitrary in-process code takeover
remains a T1.8/T1.9 runtime-attestation limitation.

### Static integrity

- `git diff --check ddb764b... fe1786c...`: passed.
- candidate status after tests/probes: clean.
- final identity remained commit `fe1786c...`, tree `f11e71c...`, parent
  `ddb764b...`.

Key candidate file SHA-256 values:

| File | SHA-256 |
|---|---|
| `arnold/pipeline/contract_bundles.py` | `1f0dfbcc901973dadf914c59bda10c6f2038091204beef20653eb9686114d1f5` |
| `arnold_pipelines/megaplan/contract_bundles/__init__.py` | `def95aaaa2bd020ca35bde4a45a7a1d87ef4ea3afbe757e4778f0fef80c3f30f` |
| `orchestration/critique_runtime.py` | `83961cc15db4a48e2546a63ce87ce018cc1924fd50c7a0418f5db305ac28248e` |
| `handlers/finalize.py` | `c11d592b318a905c0adbfc7ca5daf859ea8558ac5a574ad62904da8966287175` |
| `workers/_impl.py` | `885ac7ba1c363831a82b755dbc67b8c36ed382dc4e4ca649193fd2e783d21432` |
| `workers/hermes.py` | `27f0c572cb5039cb62f5ea07992ecc2303a35f930f114bc98c0b996fafcc5912` |
| `workers/shannon.py` | `4c64d7bbb521843112bbe67fc9e0ff2fb6b2fe96c5c05550b931f12c6fce89b1` |

## Treatment of reported broad-suite failures

I did not use the implementation report's eight broad-suite failures as evidence
for either PASS or FAIL, and did not need to classify them as base failures. The
HARD FAIL rests entirely on independently reproduced focused passes and new
counterexamples inside the changed T1.3 boundary. Therefore no unproven
“unrelated base failure” exception is part of this verdict.

## Required disposition

Do not freeze or accept T1.3 at `fe1786c...`. Do not mark the checklist item
complete and do not use this review to authorize deployment.

Keep the correction bounded to the concrete counterexamples:

1. transport one immutable raw byte/frame capture plus authenticated physical
   provider/model/session/attempt/channel identity from the adapter; reject
   caller-reconstructed provenance and embedded Shannon identity disagreement;
2. move the actual policy-neutral registry/binder/repair/preflight ownership into
   `arnold.pipeline` and make Megaplan a thin consumer;
3. migrate each real alternate model-output consumer or make it fail closed;
4. retain the parts that passed: strict framing, exact logical model allowlist,
   deep-frozen manifests, canonical registry use-site revalidation, bounded
   pointer repair, immutable admitted payload, and wheel packaging.

Record the in-process code-takeover probe for T1.8/T1.9; do not expand T1.3 to
solve arbitrary interpreter compromise.

After repair, rerun this exact focused/producer/wheel matrix and the authoritative
counterexample probes. Acceptance requires the Hermes replay, Shannon embedded-
identity contradiction, and alternate model-seam probe all to fail closed. The
in-place parser replacement probe is a handoff to T1.8/T1.9, not a T1.3 gate.

Verdict: **HARD FAIL**.
