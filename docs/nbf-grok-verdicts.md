# NBF failure-marathon — Grok 4.6 verdicts (full text, restored)

Six glm-5.3-flash investigators examined the six shipped fix classes; Grok 4.6
adjudicated deep-structural vs adherence. Restored from session output after
Sol found the committed copy truncated.

## Per-class verdicts

| Class | Verdict | Confidence |
|---|---|---|
| A Identity-routing | **ADHERENCE** | high |
| B Catalog/family | **MIXED** (lean DEEP) | high |
| C Turn-timeout | **MIXED** (lean DEEP) | high |
| D Runtime-resilience | **MIXED** | high |
| E Dispatch-unification | **DEEP** | high |
| F Supervision-ops | **MIXED** | high |

**A — ADHERENCE.** `_PREFIX_MAP` had a documented `omp:` identity branch
(docstring, SKILL.md) and a rewrite of a subprocess script dropped it. Nothing
imported `launch_omp_agent.py`, so coverage never saw it. Drift from an existing
contract, preventable by a unit test of `_translate_model("omp:openrouter/…")`.
The expired-row issue is class B composing with A, not the identity defect.

**B — MIXED, lean DEEP.** Chain: `parse_omp_spec` yields `model_id =
"z-ai/glm-5.3-flash"`, `_PROVIDER_PREFIXES` has no `z-ai/`, GLM matched only
`glm-|glm/`, enforced-tier rethrow killed gate 3×. The patch (`"z-ai/glm"`) is
string-specific adherence; the defect is two independently mutated vocabularies
(`_OMP_CATALOG_MODELS` vs `classify_model_family`) with no coupling invariant.
The next nested OpenRouter slug hits the same hole.

**C — MIXED, lean DEEP.** The 1800→7200 bump only covers launcher rc=124; rc=-15
at 1401.9s was NOT the launcher (under the 1800s bound). The patch is a constant;
the defect is the receipt schema: `_write_metadata` stores `status`+`exit_code`
only; babysitter receipts `returncode` only. Launcher TimeoutExpired (CPython
SIGKILL), resident `worker.terminate()`, watchdog SIGTERM all collapse to an
anonymous integer. Ledger row 12 needed host ftrace — schema gap recurring across
every chain.

**D — MIXED.** Cgroup OOM is DEEP: dispatch was model-blind, SIGKILL uncatchable —
prevent-at-dispatch + `oom_kill` counter is the honest design. Seed custody is
ADHERENCE: interpreter vectors were recorded; `ready:true` came from an errors
list omitting the check. The WIP `require_production_worker_dispatch_runtime`
with zero production callers is class E.

**E — DEEP.** Three production doors, three contracts: orchestration
(`_impl.py:7580-7634` raw refresh/require pair), chain
(`chain/__init__.py:7500-7539` own raises), backend (`run_omp_step`,
`omp.py:1110` has none, dies late at `omp.py:482-488` generic). Typed gate at
`runtime_attestation.py:2923` has zero production callsites. N doors with
inconsistent preflight is architectural.

**F — MIXED.** Restack classifier + two-scan wedge are DEEP; stall-reap bump is
adherence. #1 and #3 are the same hole: one observation instant treated as
sustained truth.

## Cross-cutting themes

1. **Five model vocabularies, no joint admission** — frozen catalog
   (`workers/omp.py:88-117`), `_PREFIX_MAP`, `_PROVIDER_PREFIXES`/classify,
   live models.yml, babysitter env pin. Ledger rows 5 & 12.
2. **Deaths without killer identity** — OOM SIGKILL, launcher timeout, resident
   terminate, watchdog SIGTERM, restack pkill all land anonymous. Why the night
   was 24h, not 2h.
3. **Non-unique control plane** — invariants as comments/WIP/one-of-N paths;
   single stale `completed.json` triggered kills; wedge SIGTERM on one
   `_tree_has_live_work()` false.

## The one systemic guard

A required `worker_disposition` record: unique admission function
(`require_production_worker_dispatch_runtime` expansion) wired to the three
launch doors; every terminate site appends
`{killer, timeout_source, signal, elapsed_s}`; incomplete disposition = typed
block; redispatch of same fingerprint = typed block. Structural spy: wrap the
gate, drive one `_run_step_with_worker` and one `run_omp_step` under a
production manifest, assert both hit it exactly once.

## Sol amendments (sense-check REVISE)

1. Spy: `run_step_with_worker` (workers/_impl.py:7347), not the underscore name;
   no mock early-return; intercept final spawn/RPC; cover babysitter/launch.py.
2. Don't double-gate: `_impl.py:7698-7713` delegates to `run_omp_step`.
3. Reuse existing pieces; expired-ID test proves "static accepts, live catalog
   rejects typed".
4. `signal_hung_fixer_children` + ensure-restack still single-observation —
   extend two-scan + live-pid/seq proof to both.
5. One typed disposition helper over `IncidentLedger.append_event`; test every
   signal branch (launcher pre-exception kill; resident ladders).
6. Fingerprint: add PRE-LAUNCH enforcement, not 3rd-attempt diagnosis.
