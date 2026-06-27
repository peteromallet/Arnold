# Pi Transition Test Harness — Staged Test Plan

## Executive Summary

Replacing Arnold/Hermes subprocess agent launching with Pi's unified provider + agent runtime.
The current architecture runs every agent turn in an isolated `subprocess.run()` via `worker.py`,
which instantiates `ArnoldDispatcher → DeepSeekAdapter → AIAgent`. Pi replaces this with
`@earendil-works/pi-ai` (provider layer) + `@earendil-works/pi-agent-core` (agent runtime),
keeping the subprocess isolation boundary but swapping the dispatch engine.

**Risk profile:** Protocol drift (response contract shapes), credential routing regressions,
timeout behavior changes, subprocess lifecycle edge cases, parallel-turn interference.

**Acceptance gates** are staged at 5 levels (L0 → L4). Each gate must pass before advancing.
Gates L0–L2 run entirely offline (no credentials). L3 requires API keys. L4 is a live bakeoff.

---

## Stage 0 — Unit: Pi Runtime Contract (no subprocess, no vibecomfy)

**Goal:** Prove the Pi engine responds correctly to every contract shape
(`python`, `delta`, `batch_repl`, `json`, `text`) using Pi's built-in faux provider.
Zero vibecomfy code. These tests live entirely within Pi's test suite or a thin adapter.

**Location:** `tests/pi_transition/unit/test_pi_contracts.py` (Python adapter) or
Pi-side `packages/coding-agent/test/suite/regressions/` (TypeScript, using Pi's faux harness).

### L0.1 — Faux provider contract smoke
- Register Pi's `registerFauxProvider` with per-contract response sequences.
- Assert each contract shape returns correctly structured output:
  - `python` → `{"python": "<str>", "message": "<str>"}`
  - `delta` → `{"delta": [<ops>], "message": "<str>"}`
  - `batch_repl` → `{"content": "<str containing ```batch fence>"}`
  - `json` → `{"content": "<str>", "json": {<parsed>}}`
  - `text` → `{"content": "<str>"}`
- **GATE:** All 5 contract shapes pass with faux provider and zero network calls.

### L0.2 — Empty/no-fixture fallback
- Exhaust the faux response queue → verify error messages propagate correctly
  (not silent hangs), match the shape of Arnold's current error envelope:
  `{"error": "<msg>", "error_type": "<type>", "runtime_unavailable": True/False}`.
- **GATE:** Error path produces structured, non-crashing output for all contracts.

### L0.3 — System/user message passthrough
- Verify Pi preserves system + user message content faithfully through the turn.
- Verify no truncation, reordering, or injection of extra tokens.
- **GATE:** Message fidelity proven.

### L0.4 — Response factory (context-aware)
- Use Pi's `FauxResponseFactory` (function-of-context) to assert the faux provider
  has access to the full context (system prompt, messages, tools) before responding.
  This proves we can later inject contract-specific parsing logic.
- **GATE:** Factory receives context; call count tracking works.

**✅ L0 ACCEPTANCE GATE: Pi contracts pass unit tests; zero external dependencies.**

---

## Stage 1 — Integration: Subprocess JSON Fixtures (isolation boundary)

**Goal:** Prove the `request.json → subprocess → result.json` protocol works
with Pi as the worker engine, using **JSON fixture files** instead of live LLM calls.
No credentials, no network. Tests are pure Python/pytest.

**Location:** `tests/pi_transition/integration/test_pi_worker_fixtures.py`

### L1.1 — Fixture-backed subprocess harness
- Create a `PiWorkerHarness` test class that:
  1. Writes `request.json` to a temp directory (matching current protocol shape).
  2. Invokes Pi worker via `subprocess.run([node, pi_worker_script, req_path, res_path], ...)`.
  3. Reads `result.json` and returns structured result.
- The Pi worker script reads `request.json`, creates a Pi agent turn with a
  **fixture-backed provider** (reads predefined responses from a fixtures directory
  keyed by contract type), and writes `result.json`.
- **GATE:** Round-trip passes with fixture data. No Arnold imports anywhere.

### L1.2 — Contract shape parity matrix
- For every contract (`python`, `delta`, `batch_repl`, `json`, `text`):
  - Feed a known input fixture → assert output matches expected schema exactly.
  - Cross-reference against current Arnold worker output for the same fixture.
- Use the existing `tests/fixtures/editor_sessions/` pattern: create Pi-specific
  fixture files under `tests/pi_transition/fixtures/`.
- **GATE:** All contracts produce byte-identical output shapes to Arnold for the
  same fixture input.

### L1.3 — Error path fixtures
- Fixture scenarios: module-not-found, auth-failure, timeout, malformed response.
- Verify each produces the correct error envelope (`error`, `error_type`,
  `runtime_unavailable` where appropriate).
- **GATE:** Error classifications match Arnold's current taxonomy.

### L1.4 — Credential routing fixture
- Write fixtures that simulate credential resolution:
  - `OPENROUTER_API_KEY` from env → passed through to Pi provider.
  - `~/.hermes/.env` file → parsed and key forwarded.
  - Missing key → readiness reports `ready: false`.
- **GATE:** Credential routing mirrors current `_resolve_openrouter_key()` behavior.

**✅ L1 ACCEPTANCE GATE: JSON fixture subprocess tests pass; contract parity proven.**

---

## Stage 2 — System: Timeout, Parallel, and Lifecycle Tests

**Goal:** Prove the Pi worker handles all operational edge cases:
timeouts, concurrent turns, subprocess crashes, and resource cleanup.
Still uses fixture-backed provider (no real API calls).

**Location:** `tests/pi_transition/system/test_pi_timeout.py`,
`tests/pi_transition/system/test_pi_parallel.py`,
`tests/pi_transition/system/test_pi_lifecycle.py`

### L2.1 — Timeout tests
- **Slow fixture:** A Pi fixture that deliberately delays past `VIBECOMFY_AGENT_TURN_TIMEOUT`
  → verify `TimeoutError` is raised, partial output captured, temp directory cleaned.
- **Near-timeout:** Fixture completes at `TIMEOUT - 1s` → success, no race.
- **Child-process hang:** Pi worker infinite-loops → parent kills after timeout,
  no zombie processes, no fd leak.
- **Zero timeout:** `VIBECOMFY_AGENT_TURN_TIMEOUT=0` → immediate timeout, clear error.
- **GATE:** Timeout behavior identical to current `_TURN_TIMEOUT_SECONDS` path.

### L2.2 — Parallel turn tests
- **Concurrent subprocess isolation:** Launch 10 Pi workers simultaneously with
  distinct temp directories → all complete independently, no cross-contamination
  of `request.json` / `result.json`, no shared mutable state.
- **Port/pid collision:** Ensure Pi's internal port binding (if any) doesn't
  collide when multiple workers start.
- **Rate-limit simulation:** Workers started in rapid succession → none starve.
- **GATE:** Parallelism works; no shared-state leaks.

### L2.3 — Lifecycle tests
- **Clean startup:** Pi worker. bootstraps without Arnold package on sys.path.
- **Clean shutdown:** Temp directory removed after success AND after failure.
- **Repeated reuse:** Run 50 turns sequentially through the same `_run_worker`
  pattern → no memory growth, no fd leak, consistent latency per turn.
- **Interrupted subprocess:** Send SIGTERM to worker mid-turn → parent receives
  appropriate error, no orphaned children.
- **Disk-full scenario:** Simulate ENOSPC on result.json write → graceful error,
  not silent corruption.
- **GATE:** Lifecycle robustness matches or exceeds current worker.

**✅ L2 ACCEPTANCE GATE: Operational edge cases handled; parallel isolation proven.**

---

## Stage 3 — Fake Provider Mode / Deterministic Contract Tests

**Goal:** Wire Pi into the existing vibecomfy structural harness (`sisypy`-based)
using a **fake dispatcher** that drives Pi's faux provider. This runs the full
end-to-end vibecomfy agent-edit loop but with deterministically scripted responses
instead of live LLM calls.

**Location:** `tests/pi_transition/structural/test_pi_structural_harness.py`

### L3.1 — Pi-backed fake dispatcher
- Create a `DISPATCHER_FAKE_PI` variant that, instead of calling Arnold's
  `AIAgent`, calls the Pi worker with a fixture-backed faux provider.
- The existing structural actors (`build_m2_image_generation_evidence`, etc.)
  continue to produce their compile-only evidence packs. The Pi worker is
  called but returns pre-scripted responses.
- **GATE:** All existing structural scenarios pass with Pi dispatcher.

### L3.2 — Response contract mapping
- Map Pi's response format to vibecomfy's `AgentTurnResult` / `BatchTurnResult`
  dataclasses. This is the critical adapter layer.
- Verify:
  - `python` contract → `AgentTurnResult(python=..., message=...)`
  - `delta` contract → `AgentTurnResult` with delta ops
  - `batch_repl` contract → `BatchTurnResult(batch=..., message=...)`
  - `json` contract → parsed `json` payload
  - `text` contract → raw content
- **GATE:** All contract adapters round-trip without data loss.

### L3.3 — Readiness gate integration
- Pi's readiness check should report `ready: true` when the faux provider is
  active, matching the current `fixture_provider.readiness()` pattern.
- Missing Pi installation → `ready: false` with actionable guidance.
- **GATE:** Readiness gate indistinguishable from current behavior.

### L3.4 — Structural evidence parity
- Run the full structural harness suite with the Pi dispatcher.
- Compare frozen evidence packs (diff `freeze_manifest.json`, `actions.jsonl`,
  `metadata.json`) between Arnold and Pi dispatchers.
- **GATE:** Evidence packs are byte-identical or semantically equivalent
  (differences documented and approved).

**✅ L3 ACCEPTANCE GATE: Full structural harness passes with Pi fake dispatcher.**

---

## Stage 4 — Golden Real-Brief Bakeoff (live credentials)

**Goal:** Run identical briefs through both Arnold and Pi with real API credentials
and compare outputs. This is the final confidence gate before switching production.

**Location:** `tests/pi_transition/bakeoff/test_pi_bakeoff.py`
**Requires:** `pytest --run-live` flag; valid `OPENROUTER_API_KEY`.

### L4.1 — Single-turn matching
- 20 curated briefs covering all contract types and complexity levels:
  - Simple classification (json/text contract)
  - Workflow explanation (python contract)
  - Node editing (delta contract)
  - Multi-edit batch (batch_repl contract)
  - Refusal/impossible request (all contracts)
  - Long-context prompts (>4K tokens)
  - Non-English prompts
- For each brief, run through BOTH Arnold and Pi → compare:
  - Contract shape validity (does Pi produce correctly structured output?)
  - Key content signals (does the response contain the expected semantic content?)
  - Latency (P50, P95, P99 for each path)
- **GATE:** Pi response validity ≥ Arnold; latency within ±20%.

### L4.2 — Multi-turn session bakeoff
- Run 5 multi-turn sessions (3–5 turns each) through both paths.
- Verify Pi maintains conversation context across turns.
- Verify Pi correctly handles follow-up clarifications.
- **GATE:** Multi-turn parity; no context drift.

### L4.3 — Production workload replay
- Select 20 real production briefs (from logs, anonymized).
- Replay through both Arnold and Pi.
- Classify outcomes: identical, equivalent (different wording, same action),
  divergent (different action), error (one failed).
- Target: ≥90% identical+equivalent; 0% Pi-only errors that Arnold didn't also hit.
- **GATE:** Bakeoff scorecard passes threshold.

### L4.4 — Stress test
- Run 100 consecutive briefs through Pi → no degradation, no memory leak.
- Run 10 concurrent briefs → all complete, no interference.
- **GATE:** Sustained throughput and stability.

**✅ L4 ACCEPTANCE GATE: Live bakeoff passes; production switch authorized.**

---

## Implementation Sequence

| Phase | Files to Create | Depends On |
|-------|----------------|------------|
| L0 | Pi-side contract tests (TypeScript, in Pi repo) | Pi installation |
| L1 | `tests/pi_transition/integration/test_pi_worker_fixtures.py`, `fixtures/` | Pi worker script |
| L2 | `tests/pi_transition/system/test_pi_timeout.py`, `test_pi_parallel.py`, `test_pi_lifecycle.py` | L1 |
| L3 | `tests/pi_transition/structural/test_pi_structural_harness.py` | L1 + sisypy |
| L4 | `tests/pi_transition/bakeoff/test_pi_bakeoff.py` | L1 + API keys |

## Key Design Decisions

1. **Subprocess boundary preserved.** Pi runs in the same isolated subprocess
   pattern as Arnold — no in-process Pi imports. This avoids the same
   `sys.modules` collision that motivated the worker pattern.

2. **Fake provider mode is the backbone of L0–L3.** Pi's `registerFauxProvider`
   is the gold standard here and should be the test engine for ALL non-live tests.
   Vibecomfy's existing `fixture_provider` pattern (reading from
   `tests/fixtures/editor_sessions/`) can be adapted to drive Pi's faux provider
   with the same fixture data.

3. **Response contract compatibility layer.** The critical adapter is
   `PiTurnResult → vibecomfy AgentTurnResult / BatchTurnResult`. This must be
   a pure data transformation (no side effects) and thoroughly tested at L1.

4. **Parallel isolation relies on the existing `TemporaryDirectory` pattern.**
   Pi's agent harness creates its own temp dirs internally — confirm no
   cross-talk at L2.2.

5. **Timeout is configurable and tested at L2.1.**
   `VIBECOMFY_AGENT_TURN_TIMEOUT` env var must gate Pi the same way it gates Arnold.

6. **Quarantine integration.** Any known differences between Pi and Arnold output
   go into `tests/quarantine/pi_transition.txt` with owner/reason metadata,
   following the existing quarantine convention in `conftest.py`.
