# Batch-2 attempt-3 — independent Luna review C

## Boundary and invocation

Read-only authority/checker/integration review. No source, test, frozen input,
status, history, custody, prior artifact, or Batch-3 material was edited. No
model, subagent, delegate, fan-out, Sol verdict, commit, stage, push, merge, or
fix was performed. The only repository writes are this check-in and its paired
receipt.

Literal requested launcher command:

```text
PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model="codex:gpt-5.6-luna:high" --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/oracle-batch-2-attempt-3-luna-authority.md --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf --timeout=3600
```

Resolved model: `openai-codex/gpt-5.6-luna`; reasoning: high. The observed
launcher process was PID `34304`; its command was the literal command above.
Observed local process start was `2026-08-30T21:16:11` (`2026-08-30T19:16:11Z`
under the workstation timezone); review end capture was
`2026-08-30T19:32:27.195779000Z`. The reviewer returned normally; the wrapper
must record the final process exit. The active OMP command included
`--thinking high --model openai-codex/gpt-5.6-luna --no-session`.

## Rebound candidate identity

| Binding | Fresh observation |
|---|---|
| branch | `megado-nbf-guard-0826` |
| HEAD | `2297fb330cdb375b4e5bd048f0d5c37d0e06db30` |
| origin/main | `798c50619204010ed3f4297fbb57988fe9381924` |
| requested candidate checkpoint | `5da26ec5be4d13559948fe4256a114ad7626482b` |
| requested candidate checkpoint parent/tree | `19deab5bb407273e7e82d40a66fc06d17af93ad4` / `e3d0376482154c4f95d2ec5809d630c4a0c32e69` |
| current HEAD parent/tree | `5f172e3588e740bacd6692ca9e4cc50ae01f6a6b` / `85d20103923d7d4f8c2c70869a95283a196d9249` |
| source/test diff from requested checkpoint | `126804` bytes / `acb8ca400c1b0874cea1f030630ba2f186f16cd22ceedfc2a33fe7ab592a19ec` |
| production-only diff (`arnold_pipelines scripts`) | `f636e53dfdf83ab7bac8eeff80243822ce8b4bef43fbb445ce6713555c122549` |

The `HEAD^` observation is `5f172e...` because the dirty HEAD contains the two
post-checkpoint record commits. The sealed evidence correctly identifies
`5da26e...` as the candidate checkpoint and `19deab...` as its parent.

All sealed artifact/frozen hashes in the brief rehashed exactly: v2 finding
`7145641b...`, v2 receipt `58189132...`, v2 brief `5de88060...`, timeout
receipt `678e86f3...`, v3 finding `c216fc39...`, v3 receipt `cca7987c...`,
sealed manifest `2c60512f...`, tasklist `9d206c8f...`, North Star `d75f89f0...`,
plan `0ec216cc...`, goal `2299daef...`, and custody `94df44cc...`.

## Ordered root adjudication

| Root | Classification | Direct evidence |
|---|---|---|
| `R3-NATIVE-001` | **NOT_MET** | Production-shaped admission with a valid patched seed/runtime and a caller-supplied native `route_liveness_resolver` returning forged `identity`, digest, registry, proof, generations, and matching route returned `WorkerAdmissionReceipt` and created one reservation. `worker_dispatch.py:665-682` only recomputes content when `native_construction_seam` is present; without it, `:680-682` accepts the caller resolver after shape checks. This is the exact forged/stale native-proof bypass the root forbids. Native/OMP focused run still passed 12 tests, but those fixtures use `production_intent=False` or explicitly provide the construction seam and therefore do not close this production path. |
| `R3-TERM-002` | **NOT_MET** | The physical native path returns the raw worker tuple from `_production_worker_dispatch` (`workers/_impl.py:7483-7492`), and the OMP path returns a raw `WorkerResult` (`workers/omp.py:1254-1269`). The shared phase emission calls `_emit_phase_result` without `dispatch_outcome` (`handlers/shared.py:1059-1069`); execute does the same (`handlers/execute.py:1196-1240`). Thus the typed terminal outcome is committed in the ledger but is not transported into the public phase boundary. The generic terminal/lifecycle suite passed 39 tests, but `test_worker_dispatch_spy.py:101-104` monkeypatches `append_terminal_outcome` for `worker_disposition`, so that physical-kind case does not prove public terminal append. |
| `R3-LIFE-003` | **NOT_MET** | Fresh ledger probe accepted persisted states `closed` as the first marker, then `accepted`, then `entered`; projection remained valid. A second probe accepted `entered` after a committed `accepted` marker. `IncidentLedger.append_controlled_adapter_state` validates reservation binding and duplicate accepted payloads but does not validate a persisted state transition (`ledger.py:657-683`). `ControlledFinalLaunch.__init__` selects the strongest marker rather than rejecting contradictory history (`controlled_final_launch.py:42-64`). The corrected lifecycle suite passed 59 tests, but these direct journal contradictions remain admissible. |
| `R3-AUTH-004` | **NOT_MET** | Repository checker exited 0 with empty diagnostics and the independent raw-symbol scan exited 0 with empty output. The adversarial checker fixture command reached 13 passed assertions before the 180-second command deadline, so it is not a complete green run. Internal AST probes found a direct process construction in a function named `execute` with no diagnostic, and `if not wbc_dispatch: return final_launch()` receives only `raw_final_launch_access`, not the required contextual `absent_wbc_legacy_delegation` category. More importantly, the managed/babysitter door invokes `run_managed_command(spec)` directly inside the canonical closure (`cloud/babysitter/launch.py:545-600`); neither that door nor `managed_agent.py` uses the Common WBC adapter. The OMP no-WBC path enters `ControlledFinalLaunch` before its `wbc_dispatch is None` refusal (`workers/omp.py:1237-1242`), leaving an entered/unresolved reservation rather than a pre-entry zero-construction refusal. |

## Cross-contract classification

| Contract item | Result | Evidence/status |
|---|---|---|
| source/runtime/manifest/seed/interpreter binding | **MET** | `worker_dispatch.py:422-521` derives current seed evidence and compares all request identities; sealed v3 evidence and focused runtime gates are bound. |
| timeout budget | **MET** | `_validate_basic` rejects non-positive, non-finite budgets; dispatch loop uses the bounded deadline (`worker_dispatch.py:612-617`, `966-994`). |
| memory headroom | **MET** | Production admission requires a positive typed memory proof (`worker_dispatch.py:698-704`). |
| semantic fingerprint | **MET** | Canonical fingerprint is derived before reservation (`worker_dispatch.py:705-707`). |
| exact live OMP membership | **MET** | `omp models --json` is the production membership authority (`worker_dispatch.py:384-402`, `643-659`); focused OMP test passed. |
| authoritative native proof | **NOT_MET** | Caller resolver bypass above. |
| typed T7 cooldown / zero worker construction | **MET** | Cooldown returns `SchedulingCondition` before reservation; dispatch waits with a bounded typed loop (`worker_dispatch.py:691-697`, `979-993`). |
| explicit lifecycle / at-most-once | **NOT_MET** | Persisted marker order is not enforced; direct contradiction probe accepted. |
| one authority across native, OMP, managed, chain, no-WBC | **NOT_MET** | Native and OMP have canonical gates, but managed lacks WBC and OMP no-WBC enters before refusal. |
| six payload kinds, direct/wire decode, validation | **MET** for generic construction/decode/validation; **UNEVIDENCED** for every physical door | 39 terminal/transport tests passed; disposition physical append was monkeypatched. |
| public terminal and disposition append | **UNEVIDENCED** end-to-end | Ledger doors validate typed records, but the physical disposition test bypasses terminal append and no production phase projection carries the typed outcome. |
| provider / ox-alpha / keyed streak | **MET** | Corrected lifecycle/provider suite: 59 passed; sealed focused OMP/route evidence covers ox-alpha and exact membership. |
| confirmation and evidence digest | **MET** | Confirmation/reconciliation suite included in the 59-pass run; schema and ledger recheck evidence are bound. |
| killer/signal/elapsed death retention through terminal/crash/contention | **UNEVIDENCED** | `WorkerDisposition` retains the fields and terminal links its disposition ID, but no direct physical crash/contention projection proof was established in this review. |
| NBF-03 exact/baseline | **NOT_MET** | Sealed v3 records the same four known baseline failures: `test_babysitter_routing_defaults_to_legacy_deepseek`, `test_legacy_managed_spec_keeps_hermes_controller`, `test_renderer_requires_single_flash_orchestrator_contract`, and `test_renderer_cli_mentions_single_flash_contract`. |
| checker / raw scan | **NOT_MET** as complete adversarial coverage | CLI checker and raw scan are green, but checker fixtures were incomplete/timeout and the semantic evasion probes above succeeded. |
| compile / diff-check / path-hash / manifest / CLI status | **MET** by sealed v3 evidence | Sealed v3 records compile and diff-check exit 0, exact 18-path hashes, manifest integrity, and CLI status evidence. |
| no T8 / KISS-YAGNI | **MET** / no contrary evidence | No T8 or second authority/journal was found in the reviewed candidate; the remaining failures are missing bindings/order, not added architecture. |

## Verification stream ledger

All commands used cwd `/Users/peteromalley/Documents/Arnold-oracle-nbf`.
Empty stream SHA-256 is
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

| Command | Exit | stdout bytes / SHA-256 | stderr bytes / SHA-256 |
|---|---:|---:|---:|
| `python -m pytest -q --tb=short tests/cloud/test_worker_dispatch_admission.py tests/cloud/test_worker_dispatch_spy.py -k 'native or omp_static or physical_door'` | 0 | 113 / `5618a9beffa50effdadbbf715634e5ed3887caaefa477ade056eccc0286de6f` | 0 / empty |
| `python -m pytest -q --tb=short tests/cloud/test_dispatch_reconciliation.py tests/cloud/test_dispatch_with_admission.py tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py tests/arnold_pipelines/megaplan/test_provider_route_projection.py tests/arnold_pipelines/megaplan/test_supervision_confirmation.py` | 0 | 99 / `ac4af16154992f60216c77ae87f971d29b10ce3c34a1734326911b1bbc629a27` | 0 / empty |
| `PYTHONDONTWRITEBYTECODE=1 python -B scripts/check_worker_admission_authority.py --check` | 0 | 213 / `e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2` | 0 / empty |
| `if rg -n 'refresh_runtime_launch_seed_for_worker_dispatch|require_configured_runtime_launch|worker_launch_preflight' arnold_pipelines/megaplan/workers/_impl.py arnold_pipelines/megaplan/workers/omp.py arnold_pipelines/megaplan/cloud/babysitter/launch.py; then exit 1; fi` | 0 | 0 / empty | 0 / empty |
| `python -m pytest -q --tb=short tests/cloud/test_worker_admission_authority.py` | timeout at 180s after 13 passed | incomplete; no final stream bound | 0 / empty |

No Sol verdict or Batch-2 acceptance token is issued by this review. The four
ordered roots remain open on direct evidence above.
