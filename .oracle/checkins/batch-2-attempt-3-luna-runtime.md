# Batch-2 attempt-3 — independent Luna review B: runtime, terminal, lifecycle

## Boundary and execution identity

Review-only. No source, test, frozen `.oracle` input, status, index, history,
commit, stage, push, merge, delegation, nested model, or Sol verdict was
performed. Only this checkin and its paired receipt are written.

The brief's literal launch shape is recorded here:

```text
PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model="codex:gpt-5.6-luna:high" --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/oracle-batch-2-attempt-3-luna-runtime.md --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf --timeout=3600
```

It was **not executed**: this review session is already the authorized
`openai-codex/gpt-5.6-luna` reviewer with high reasoning, and the sealed brief
forbids launching another model. Therefore nested-launch PID/exit/streams are
`N/A`, not fabricated. The direct verification process was PID `35917` in cwd
`/Users/peteromalley/Documents/Arnold-oracle-nbf`.

## Sealed binding rehash

| Binding | Observed result |
|---|---|
| HEAD / branch | `2297fb330cdb375b4e5bd048f0d5c37d0e06db30` / `megado-nbf-guard-0826` |
| source/base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| candidate checkpoint | `5da26ec5be4d13559948fe4256a114ad7626482b`; parent `19deab5bb407273e7e82d40a66fc06d17af93ad4`; tree `e3d0376482154c4f95d2ec5809d630c4a0c32e69` |
| source/test diff | `126804` bytes; SHA-256 `acb8ca400c1b0874cea1f030630ba2f186f16cd22ceedfc2a33fe7ab592a19ec` |
| production-only diff | SHA-256 `f636e53dfdf83ab7bac8eeff80243822ce8b4bef43fbb445ce6713555c122549`; `84905` bytes |
| frozen tasklist / northstar / plan / goal / custody | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` / `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` / `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` / `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` / `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| sealed manifest | SHA-256 `2c60512f34311883849d1530af4c5b719cab7bb29434087985905c36b2573cbf` |
| v2/v3 finding and receipt | `7145641b049ec9d84efece8f35786e08abeaf80423f607be312e7f6d26b32e0f` / `58189132e6a5660a6812bffd3a020badb0a503a50858febd244ae73a0f12310b`; v3 `c216fc39fcdec21cf81f8a3bb43656b7dca5ef949a050a85ac1a81b0523569ee` / `cca7987c9f23eab5ec6c2a4cf80ceb1af84fd1d5e2503bc20421ef2685cb0bcf` |

The brief's `parent=5da26...` field is the candidate checkpoint, not the
current HEAD's immediate parent. Direct ancestry shows HEAD parent
`5f172e3588e740bacd6692ca9e4cc50ae01f6a6b`, and checkpoint `5da26...` parent
`19deab...`. The production/test diff and sealed checkpoint hashes match.

Prior immutable artifacts also rehashed exactly to their sealed values,
including the v2 brief/finding/receipt, timeout receipt, v3 finding/receipt,
and all five frozen documents.

## Root dispositions

| Root | Status | Finding |
|---|---|---|
| `R3-NATIVE-001` | **NOT_MET** | The supplied native construction seam is authoritative when present: forged resolver content disagreed with the seam and returned `AdmissionRefusal(code=route_liveness_invalid)` with zero reservations. However the default `_native_construction_proof` (`workers/_impl.py:7347-7390`) only hashes the selected Python callable/route metadata and sets `constructable=True`; it does not construct/probe the native backend or verify the model. Directly asking it for `codex:model-that-does-not-exist` returned a positive proof. Authentic native capability proof is therefore not established by the production default seam. |
| `R3-TERM-002` | **NOT_MET** | A direct ledger-backed closure transported `success`, `ordinary_terminal_failure`, `provider_exhausted`, and `worker_disposition`; each produced one terminal projection and preserved receipt/fingerprint/phase/spec/worker/timing. But physical failure exceptions are not losslessly terminalized: `_outcome_from_terminal_exception` only handles provider/ordinary codes (`worker_dispatch.py:293-341`), while a typed worker-disposition exception produced `unresolved_launch` with no disposition or terminal event. Append/link failure is also collapsed at `worker_dispatch.py:1043-1046` to an identity-free unresolved outcome. This violates death coverage and lossless context despite the generic transport tests passing. |
| `R3-LIFE-003` | **NOT_MET** | Normal lifecycle sequencing, commit-before-projection, replay, concurrent terminal linkage, and at-most-once closure passed. A direct persisted sequence `not_started → entered → accepted`, followed by an additional stale receipt-bound `not_started` marker, reopened as state `accepted` without rejecting the contradictory journal. `ControlledFinalLaunch.__init__` selects the strongest marker (`controlled_final_launch.py:42-64`) and the run guard prevents a second call, but it does not reject globally contradictory/out-of-order markers. |
| `R3-AUTH-004` | **NOT_MET** | `python scripts/check_worker_admission_authority.py --check` returned empty diagnostics and exit 0; the independent AST scan found no raw authority/final-launch calls and no direct process construction in the admission door scopes. It did inventory direct OMP calls at `_impl.py:6999,7802` and `omp.py:1244`, plus the managed call at `babysitter/launch.py:599`. The flag-on `_omp_to_agent_result` path at `_impl.py:7882-7902` calls `run_omp_step` without forwarding `wbc_dispatch`; the checker does not diagnose this alternate nested OMP/no-WBC path. Static green output is therefore insufficient for the requested complete door/WBC/nested-admission contract. |

## Direct runtime transcripts

### Native proof and reservation boundary

Using `tests.cloud.dispatch_test_helpers.native_proof()`:

```text
good=WorkerAdmissionReceipt calls=[('codex','gpt-5.5','codex:gpt-5.5')] reservations=1
forged=AdmissionRefusal route_liveness_invalid reservations=0
bogus_native_proof={'constructable': True, ... 'normalized_model': 'model-that-does-not-exist', 'route': 'codex:model-that-does-not-exist'}
```

The first two lines establish the fixed seam comparison and pre-reservation
refusal. The third is the default-proof authenticity failure above.

### T7 cooldown

A two-attempt injected cooldown returned one typed wait, slept exactly `2.0`,
performed zero launches during the wait, then admitted and launched once:

```text
outcome=success waits=[2.0] launches=1 events=admission_reserved,controlled_adapter_state,controlled_adapter_state,controlled_adapter_state,worker_terminal_outcome,controlled_adapter_state
```

This is MET for the shared T7 scheduling behavior; no failure/breaker/blocked
projection was observed.

### Terminal transport

The corrected direct probe used a gate-fixed receipt (not a second admission)
and printed:

```text
success success 1 0 admission_reserved,controlled_adapter_state,controlled_adapter_state,controlled_adapter_state,worker_terminal_outcome,controlled_adapter_state
ordinary_terminal_failure ordinary_terminal_failure 1 0 admission_reserved,controlled_adapter_state,controlled_adapter_state,controlled_adapter_state,worker_terminal_outcome,controlled_adapter_state
provider_exhausted provider_exhausted 1 0 admission_reserved,controlled_adapter_state,controlled_adapter_state,controlled_adapter_state,worker_terminal_outcome,controlled_adapter_state
worker_disposition worker_disposition 1 1 admission_reserved,controlled_adapter_state,controlled_adapter_state,worker_disposition,controlled_adapter_state,worker_terminal_outcome,controlled_adapter_state
```

Columns are `input kind`, `outcome kind`, terminal count, disposition count,
and event types. This proves the generic append/projection path, not that real
native/OMP exceptions are converted to these outcomes.

The death exception probe printed:

```text
exception_disposition=unresolved_launch events=admission_reserved,controlled_adapter_state,controlled_adapter_state,controlled_adapter_state terminals=0 dispositions=0
```

### Lifecycle contradiction

```text
persisted_states=['not_started','entered','accepted','not_started'] reopened_state=accepted run_guard=RuntimeError controlled final launch closure may be called only once
```

The guard blocks relaunch, but the contradiction remains accepted rather than
being rejected as unresolved/invalid journal state.

### OMP catalog/live route

The actual command returned exit 0. Its captured metadata was:

```text
command: omp models --json
pid: 35917
UTC: 2026-08-30T19:28:00.392280+00:00 → 2026-08-30T19:28:02.517086+00:00
stdout: 197368 bytes; SHA-256 3c400ef15296f675f063a2348cae8d1b3dcf7034ca6fb9efedeb8d7e1cbfab2c
stderr: 0 bytes; SHA-256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
ox-alpha row: provider=stealth, selector=stealth/ox-alpha
```

Production admission of `omp:openrouter/stealth/ox-alpha` then returned
`AdmissionRefusal(code=route_liveness_missing)` with zero reservations. The
static table accepts the expired-looking row, while exact live membership
rejects it; this criterion is MET.

### Static checker and focused tests

Checker capture:

```text
command: python scripts/check_worker_admission_authority.py --check
pid: 35917
UTC: 2026-08-30T19:27:45.588994+00:00 → 2026-08-30T19:28:00.391992+00:00
exit: 0
stdout: 213 bytes; SHA-256 e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2
stderr: 0 bytes; SHA-256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
result: {"diagnostics":[],"ok":true}
```

Independent focused dispatch/lifecycle/authority tests:

```text
command: python -m pytest -q tests/cloud/test_dispatch_with_admission.py tests/cloud/test_controlled_final_launch.py tests/cloud/test_dispatch_reconciliation.py tests/cloud/test_worker_dispatch_admission.py tests/cloud/test_worker_admission_authority.py tests/cloud/test_worker_dispatch_spy.py tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py
UTC: 2026-08-30T19:34:52.407766+00:00 → 2026-08-30T19:37:37.974823+00:00
pid: 35917; exit: 0
stdout: 111 bytes; SHA-256 eb18e9a2e32d2734128304c8b45edd3e3034aceefdef6a2c7f5892293d74142e
stderr: 0 bytes; SHA-256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
result: 64 passed

command: python -m pytest -q tests/arnold_pipelines/megaplan/test_provider_route_projection.py tests/workers/test_omp_adapter.py tests/arnold_pipelines/megaplan/test_worker_disposition.py
UTC: 2026-08-30T19:33:45.252281+00:00 → 2026-08-30T19:34:44.471620+00:00
pid: 35917; exit: 0
stdout: 180 bytes; SHA-256 8fa2acd8ee2ada90fbf3349323c18d90dab95d672cb7868cbc2126b9d5c7c6cb
stderr: 0 bytes; SHA-256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
result: 90 passed
```

The 154 focused tests are evidence for the implemented generic contracts. They
do not erase the direct production-shaped gaps above.

## Preserved / unevidenced criteria

- Exact native/OMP/managed physical execution with a real worker failure,
  signal killer, elapsed timing, and public disposition append: **NOT_MET** for
  the exception path above; no external model was launched.
- Confirmation identity and two-scan consumption across every signal site:
  **UNEVIDENCED** in this lens; the focused command did not exercise all
  supervisor sites.
- Compile, diff-check, path manifests, clean-baseline restoration, CLI status
  matrix, and no-T8/KISS/YAGNI evidence: **UNEVIDENCED independently**. The
  sealed v3 executor manifest records those external gates, but this review did
  not duplicate or rewrite them.
- Keyed provider streak, provider recovery authorization, replay, and digest
  semantics: **MET** for the focused provider projection suite (`90 passed`),
  subject to the physical exception limitation above.

No Sol judgment is issued. These are independent runtime-lens dispositions only.
