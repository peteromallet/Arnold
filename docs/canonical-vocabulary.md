# M4 Canonical Vocabulary Map

> **Status:** Living document — amendable during implementation when edge cases are discovered.
>
> **Purpose:** Resolve domain-vocabulary homonyms and synonym drift so a reader can tell what a term means without tracing call sites. This document is the single source of truth for M4 naming decisions and is used by automated grep verification gates.

---

## 1. Vocabulary Map

Each entry maps a domain concept to its canonical identifier, explains what it means, and records any legacy/stale identifiers that must not appear in active code after M4.

### 1.1 Pipeline Verdict Dataclass

| Field | Value |
|---|---|
| **Canonical name** | `PipelineVerdict` |
| **Location** | `megaplan/_pipeline/types.py` |
| **Meaning** | Frozen dataclass representing the structured output of a `judge`-kind pipeline step. Contains `score`, `flags`, `notes`, `payload`, `recommendation`, and `override`. |
| **Legacy/stale identifier** | `Verdict` (the bare class name — ambiguous with bakeoff/audit Verdict concepts) |
| **Persistence** | Not directly persisted; embedded in `StepResult.verdict` (field name unchanged) |
| **Grep verification** | Search for `Verdict` where used as a class construction/annotation/import from `_pipeline`. The following are NOT stale: `JudgeVerdict`, `EvaluatorVerdict`, `StepResult.verdict`, `review_verdict`, `reviewer_verdict`, `sense_checks[].verdict`, schema `verdict` fields, domain-prose uses of "verdict." |

### 1.2 Human Decision Pipeline Step

| Field | Value |
|---|---|
| **Canonical name** | `HumanDecisionStep` |
| **Location** | `megaplan/_pipeline/steps/human_gate.py` (file path unchanged) |
| **Meaning** | A pipeline step that pauses execution and waits for human input via `awaiting_user.json`. The human makes a *decision* (e.g., approve/reject) and the pipeline resumes. |
| **Legacy/stale identifier** | `HumanGateStep` |
| **Persistence** | Writes `awaiting_user.json` to plan directory; file name and format unchanged |
| **Grep verification** | Search for `HumanGateStep` in active `.py/.md/.json/.yaml/.yml` files |
| **Non-rename** | AI quality checkpoint gate terminology (`handle_gate`, `gate_carry.json`, `gate.json`, gate commands, gate prompt fields, `kind == "gate"` edge kinds) all remain. The "gate" → "decision" rename applies ONLY to the human pause pipeline step. |

### 1.3 Active Execution Metadata TypedDict

| Field | Value |
|---|---|
| **Canonical name** | `ActivePhase` |
| **Location** | `megaplan/types.py` |
| **Meaning** | TypedDict representing the currently executing phase's metadata (agent, mode, model, run_id, etc.). Written into `PlanState.active_step`. |
| **Legacy/stale identifier** | `ActiveStep` (the TypedDict class name) |
| **Inner key (new writes)** | `"phase"` — replaces the legacy inner key `"step"` |
| **Inner key (legacy reads)** | `"step"` — still read as a fallback: `active.get("phase") or active.get("step")` at all 13 inner-key reader sites |
| **Top-level key** | `active_step` — **NOT changed**. The persisted `state["active_step"]` key stays. |
| **Function signature** | `set_active_step(step=...)` — **NOT changed**. The parameter name `step` is preserved even though the inner key it writes becomes `"phase"`. |
| **Persistence behavior** | New writes use inner key `"phase"`. All 13 readers use `active.get("phase")` first, falling back to `active.get("step")`. `HistoryEntry.step` and `entry["step"]` in workflow/history are intentionally separate vocabulary and unchanged. |
| **Grep verification** | Search for `ActiveStep` as a TypedDict class usage (import, annotation, cast). Do NOT flag `active_step` (the top-level dict key) or `set_active_step` (the function name). |
| **Import update** | `megaplan/schemas/sprint1.py` must import `ActivePhase` (not `ActiveStep`) and use `cast(ActivePhase, ...)`. |

### 1.4 State Constant for Awaiting Human

| Field | Value |
|---|---|
| **Canonical name** | `STATE_AWAITING_HUMAN_VERIFY` |
| **Location** | `megaplan/types.py` |
| **Meaning** | Python constant representing the plan state where execution is paused waiting for human verification of results. |
| **Legacy/stale identifier** | `STATE_AWAITING_HUMAN` (the Python constant name) |
| **Persisted string** | `"awaiting_human_verify"` — **NOT changed**. Every on-disk `state.json` uses this string. Only the Python identifier is renamed. |
| **Canonical plan state literal** | `"awaiting_human_verify"` in `PlanCurrentState` — unchanged |
| **Grep verification** | Search for `STATE_AWAITING_HUMAN` as a constant usage (import, reference) that is NOT the new `STATE_AWAITING_HUMAN_VERIFY`. The bare string `"awaiting_human_verify"` is expected in JSON/MD and is NOT stale. |

### 1.5 Gate Carry Artifact

| Field | Value |
|---|---|
| **Canonical key** | `"recommendation"` |
| **File** | `gate_carry.json` (written to plan directory) |
| **Meaning** | The gate phase's actionable recommendation: `PROCEED`, `ITERATE`, or `ESCALATE`. |
| **Legacy/stale key** | `"verdict"` — duplicate of `"recommendation"` in the same artifact; dropped from new writes |
| **Persistence behavior (new writes)** | `_build_gate_carry()` writes `"recommendation"` only. No `"verdict"` key. |
| **Persistence behavior (legacy reads)** | Consumers read `carry.get("recommendation") or carry.get("verdict")` as a fallback for artifacts written before M4. |
| **Prompt synthesis** | `prompts/_shared.py:_gate_summary_or_skipped` synthesizes a carry dict from `gate.json` — the synthesized `"verdict"` key is removed. |
| **Grep verification** | New `gate_carry.json` artifacts must contain `"recommendation"` and NOT contain `"verdict"`. Active code must not write `carry["verdict"]`. |

### 1.6 Dead Execute Dispatch Aliases

| Field | Value |
|---|---|
| **Canonical name** | `handle_execute_auto_loop` and `handle_execute_one_batch` |
| **Location** | `megaplan/handlers/execute.py` |
| **Meaning** | Direct handler functions for executing batches within the auto loop or individually. |
| **Legacy/stale identifier** | `dispatch_execute_auto_loop` and `dispatch_execute_one_batch` (dead import-time aliases with zero external callers) |
| **Grep verification** | Search for `dispatch_execute_auto_loop` or `dispatch_execute_one_batch` in active `.py/.md/.json/.yaml` — zero hits expected. Test monkeypatch string references must use the direct function names. |

### 1.7 Backend Literal Type

| Field | Value |
|---|---|
| **Canonical name** | `Backend = Literal["file", "db"]` |
| **Canonical location** | `megaplan/schemas/base.py` |
| **Meaning** | The single source of truth for the backend literal type used by both the Store protocol and Pydantic storage models. |
| **Legacy/stale definition** | `Backend = Literal["file", "db"]` in `megaplan/store/base.py` — removed and replaced with an import from `megaplan.schemas.base` |
| **Compatibility alias** | `HomeBackend = Backend` is kept in `megaplan/schemas/base.py` for consumers that already import `HomeBackend`. Persisted field `home_backend` is unchanged. |
| **Grep verification** | Only `megaplan/schemas/base.py` defines `Backend = Literal[...]`. `megaplan/store/base.py` imports it. |

### 1.8 Critique vs Review

| Field | Value |
|---|---|
| **Canonical distinction** | Critique is the **pre-execute** plan-quality pass. Review is the **post-execute** implementation-evidence pass. |
| **Handler renames** | **None.** Both handler names, commands, prompt fields, and artifacts are preserved. The distinction is documented as an invariant. |
| **Persistence** | No change. |

---

## 2. Three Distinct Verdict-Class-Bearing Concepts

M4 introduces three distinct concepts that all carry "Verdict" in their class name. These must NOT be confused or cross-renamed.

### 2.1 PipelineVerdict (pipeline dataclass)

- **File:** `megaplan/_pipeline/types.py:108`
- **Kind:** `@dataclass(frozen=True)`
- **Purpose:** Structured output of a `judge`-kind pipeline `Step`. Contains `score`, `flags`, `notes`, `payload`, `recommendation`, `override`.
- **M4 action:** Renamed from `Verdict` to `PipelineVerdict`. No compatibility alias.
- **Export:** `megaplan/_pipeline/__init__.py` exports `PipelineVerdict`.

### 2.2 JudgeVerdict (bakeoff TypedDict)

- **File:** `megaplan/bakeoff/judge.py:21`
- **Kind:** `TypedDict`
- **Purpose:** LLM comparison ranking result in the bakeoff system. Contains `judge_model`, `rank`, `rationale_per_profile`, `scope_drift_flags`, `concerns`.
- **M4 action:** **NOT renamed.** This is a distinct bakeoff concept.
- **Import:** `megaplan/bakeoff/comparison.py:10` imports `JudgeVerdict`.

### 2.3 EvaluatorVerdict (audits TypedDict)

- **File:** `megaplan/audits/critique_evaluator.py:181`
- **Kind:** `TypedDict(total=False)`
- **Purpose:** Schema for the critique evaluator's output payload. Contains `selections`, `skipped`, `evaluator_model`, `flag_verifications`.
- **M4 action:** **NOT renamed.** This is a distinct audits concept.

---

## 3. Deliberate Non-Renames

The following identifiers are intentionally preserved and must NOT be renamed during M4:

| Identifier | Reason |
|---|---|
| `JudgeVerdict` (bakeoff) | Distinct bakeoff concept; see §2.2 |
| `EvaluatorVerdict` (audits) | Distinct audits concept; see §2.3 |
| `StepResult.verdict` (field) | Schema field; carries a `PipelineVerdict` instance |
| `review_verdict` (field) | Review handler field; domain prose, not pipeline class |
| `reviewer_verdict` (field) | Plan/review schema field |
| `sense_checks[].verdict` (schema field) | Plan schema; pass/fail judgment on a sense check |
| `schemas/runtime.py` verdict field | Required schema key; distinct from gate_carry |
| `"awaiting_human_verify"` (string) | Persisted state value in every `state.json` |
| `PlanCurrentState` `"awaiting_human_verify"` literal | Canonical plan state string |
| `PlanState.active_step` (top-level key) | Top-level state dict key; only inner key changes |
| `set_active_step(step=...)` (function signature) | Parameter name preserved even though inner write key changes |
| `HistoryEntry.step` / `entry["step"]` | Workflow/history vocabulary; separate from active metadata |
| `handle_gate`, `gate_carry.json`, `gate.json` | AI quality checkpoint terminology |
| Gate commands (`gate`, `revise`, etc.) | CLI command vocabulary |
| Gate prompt fields | Prompt template keys |
| `EdgeKind = "gate"` | Pipeline edge dispatch kind |
| `kind == "gate"` edge dispatch | Pipeline executor dispatch logic |
| `HomeBackend` (compatibility alias) | Kept as `HomeBackend = Backend` in `schemas/base.py` |
| `home_backend` (persisted field) | Storage model field; unchanged |
| `_pipeline/steps/` and `_pipeline/stages/` directories | Physical rename deferred to M5b |
| Critique handler names, commands, prompt fields | Critique/review distinction is documented, not renamed |

---

## 4. Canonical Plan State Strings

The following are the canonical Python constants and their corresponding persisted state strings. The persisted strings must NOT change.

| Python Constant | Persisted String |
|---|---|
| `STATE_INITIALIZED` | `"initialized"` |
| `STATE_PREPPED` | `"prepped"` |
| `STATE_PLANNED` | `"planned"` |
| `STATE_CRITIQUED` | `"critiqued"` |
| `STATE_GATED` | `"gated"` |
| `STATE_FINALIZED` | `"finalized"` |
| `STATE_EXECUTED` | `"executed"` |
| `STATE_REVIEWED` | `"reviewed"` |
| `STATE_DONE` | `"done"` |
| `STATE_ABORTED` | `"aborted"` |
| `STATE_FAILED` | `"failed"` |
| `STATE_BLOCKED` | `"blocked"` |
| `STATE_PAUSED` | `"paused"` |
| `STATE_CANCELLED` | `"cancelled"` |
| `STATE_AWAITING_PR_MERGE` | `"awaiting_pr_merge"` |
| `STATE_AWAITING_HUMAN_VERIFY` | `"awaiting_human_verify"` |
| `STATE_TIEBREAKER_PENDING` | `"tiebreaker_pending"` |
| `STATE_TIEBREAKER_READY` | `"tiebreaker_ready"` |

**Note:** `STATE_AWAITING_HUMAN_VERIFY` is the renamed Python constant. The persisted string `"awaiting_human_verify"` and the `PlanCurrentState` literal `"awaiting_human_verify"` are unchanged. `AUTOMATION_TERMINAL_STATES` and `CANONICAL_PLAN_STATES` must reference the new constant name.

---

## 5. Verdict Prose Update Rule

When updating `_pipeline/` module docstrings and code comments:

1. **Class-name references** to the pipeline dataclass become `PipelineVerdict`. Example: `:class:\`PipelineVerdict\`` or `` `PipelineVerdict` ``.
2. **Generic domain prose** about "verdicts" (as a concept, e.g., "the step returns a verdict") remains unchanged. Only the class-name token changes.
3. **StepResult.verdict field annotation** changes from `"Verdict | None"` to `"PipelineVerdict | None"`.
4. **Bakeoff `JudgeVerdict`** and **audits `EvaluatorVerdict`** prose references are untouched.
5. **Schema/user-facing verdict fields** (`review_verdict`, `reviewer_verdict`, `sense_checks[].verdict`) are untouched.

---

## 6. Grep Verification Patterns

The following patterns are used in the final stale-identifier verification (Step 10.3). Run over active `.py`, `.json`, `.md`, `.yaml`, `.yml` files, excluding the zones listed in §7.

### 6.1 Stale identifiers to verify are ABSENT

| Pattern | What it catches |
|---|---|
| `dispatch_execute_auto_loop` | Dead execute alias (must be zero hits in active files) |
| `dispatch_execute_one_batch` | Dead execute alias (must be zero hits in active files) |
| `HumanGateStep` | Stale human-gate step class name |
| `STATE_AWAITING_HUMAN[^_]` | Stale state constant (must NOT match `STATE_AWAITING_HUMAN_VERIFY`) |
| `ActiveStep` (as TypedDict class) | Stale TypedDict — but NOT `active_step` (top-level key) or `set_active_step` (function) |
| `active_step.*"step"` (inner key write) | New writes using inner key `"step"` instead of `"phase"` |
| `Verdict` (pipeline dataclass usage) | Stale pipeline dataclass — BUT must classify hits as intentional (JudgeVerdict, EvaluatorVerdict, schema fields, domain prose) vs. stale |

### 6.2 Intentional Verdict occurrences to classify (NOT stale)

When grepping for `Verdict`, occurrences of these are intentional:
- `JudgeVerdict` — bakeoff comparison ranking
- `EvaluatorVerdict` — critique evaluation output
- `review_verdict` — review handler field
- `reviewer_verdict` — plan/review schema field
- `sense_checks[].verdict` — plan schema field
- Schema `"verdict"` keys (not in gate_carry context)
- Domain-prose uses of "verdict" (lowercase, in docs/comments)

---

## 7. Explicit Exclusion Zones

The following paths are excluded from stale-identifier grep verification. References to legacy identifiers in these zones are tolerated and do NOT block the M4 gate.

| Zone | Pattern | Reason |
|---|---|---|
| Archive docs | `docs/archive/**` | Historical sprint documents preserved for context |
| Plan metadata | `.megaplan/**` | Plan version history, receipts, internal state |
| Plan version docs | `plan_v[0-9]*.md` | Iterative plan drafts that reference old names in their change descriptions |
| Brief docs | `.megaplan/briefs/**` | Engineering briefs that describe the pre-M4 state |
| CHANGELOG | `CHANGELOG.md` | Historical change log entries |
| Vendored agent material | `megaplan/hermes/**` (if applicable) | Vendored third-party agent code |

**Amendment rule:** If a genuinely historical, generated, or vendored directory is discovered during implementation that contains legacy references, add it to this table visibly and document the rationale.

---

## 8. Persistence Behavior Summary

| Artifact | What changes | What stays |
|---|---|---|
| `state.json` | `STATE_AWAITING_HUMAN` constant renamed; `active_step` inner key becomes `"phase"` for new writes | `PlanState.active_step` top-level key; `"awaiting_human_verify"` string value; `entry["step"]` in history |
| `gate_carry.json` | `"verdict"` key dropped from new writes | `"recommendation"` key; all other fields; legacy `"verdict"`-only artifacts still readable as fallback |
| `awaiting_user.json` | `HumanGateStep` → `HumanDecisionStep` class rename only | File name, format, and contents unchanged |
| Pipeline YAML | Step class references: `HumanGateStep` → `HumanDecisionStep` | YAML structure, other step types |

---

## 9. Amendable Note

This document is a living reference. If edge cases are discovered during implementation that require:
- Adding a new exclusion zone,
- Refining a grep verification pattern,
- Documenting an additional deliberate non-rename,
- Clarifying a persistence rule,

amend this document visibly (with a dated note) rather than silently diverging. The vocabulary map is the contract that later grep verification gates depend on.
