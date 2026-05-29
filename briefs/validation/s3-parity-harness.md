Here's the full audit:

## Phase-0 Scaffolding Audit

| # | Claim | Status | File:Line | Note | Quote |
|---|-------|--------|-----------|------|-------|
| 1 | **Mock-worker stub** (deterministic fn of step/iteration/config) | **EXISTS** | `megaplan/types.py:385`, `megaplan/workers/_impl.py:1579–1602`, `tests/conftest.py:119` | `MOCK_ENV_VAR="MEGAPLAN_MOCK_WORKERS"` wired into `_mock_step` + `mock_worker_output`; conftest sets it. Guard `_check_mock_safe(:1562)` blocks non-pytest use. | `"MOCK_ENV_VAR = \"MEGAPLAN_MOCK_WORKERS\""` / `"def mock_worker_output(step, state, plan_dir..."` |
| 2 | **`make_worker_sequence`** (per-test mock overrides) | **EXISTS** | `tests/conftest.py:303–313` | Simple iterator-based sequencer returning `(WorkerResult, agent, model, is_persistent)` tuples. Used in `test_gate.py`. | `"def make_worker_sequence(results: list[...], call_counter: dict[...]) -> Callable[...]"` |
| 3 | **Parity test** (dual-run legacy handlers vs InProcessHandlerStep) | **PARTIAL** | `tests/test_pipeline_parity.py:162–198` | `test_direct_and_pipeline_produce_identical_artifacts` exists, runs `handle_*` vs `InProcessHandlerStep` loop, SHA256-compares 10 artifacts. But **one happy-path only** — no reprompt/downgrade/tiebreaker branches, no `make_worker_sequence` overrides, no `extract_decision_fields`. | `"def test_direct_and_pipeline_produce_identical_artifacts(...)"` — compares `artifacts_a` vs `artifacts_b` via `hashlib.sha256` |
| 4 | **`extract_decision_fields()`** (diff handler-vs-pipeline outputs) | **ABSENT** | — | grep across `megaplan/` + `tests/` → zero results. Only appears in briefs (`pipeline-unification-planning-as-pack.md:412`, `foundation-hardening-sprint.md:54`). Not implemented. | N/A |
| 5a | **`MEGAPLAN_UNIFIED_DISPATCH`** toggle | **ABSENT** | — | grep repo-wide → zero results. Proposed in brief but never created. | N/A |
| 5b | **`MEGAPLAN_PIPELINE_AUTO`** + `pipeline_runtime_enabled()` | **PARTIAL** | `megaplan/_pipeline/runtime.py:191–199` | Function exists, reads env var, defaults to `"0"`. But **zero callers** in `megaplan/` — the toggle is defined but never gates dispatch. Only tested in isolation (`tests/test_auto_pipeline_runtime.py`). | `"def pipeline_runtime_enabled() -> bool: ... return os.environ.get(\"MEGAPLAN_PIPELINE_AUTO\", \"0\") == \"1\""` |

---

**Verdict:** The mock-worker stub and `make_worker_sequence` helper are fully built. A single happy-path parity test skeleton exists but lacks `extract_decision_fields`, branch coverage, and per-test mock-override sequencing. The `MEGAPLAN_PIPELINE_AUTO` toggle is defined but orphaned (never wired to dispatch), and `MEGAPLAN_UNIFIED_DISPATCH` doesn't exist at all. **~40% of Phase 0 exists; the parity gate's real value (decision-field diffing + branch-coverage CI armor) and the dispatch toggle must still be built.**