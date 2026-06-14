# m6 — Runtime Foundation (cross-cutting carriers → `arnold/runtime/`)

## Why this milestone exists (and why it is its own gate)
Every runtime extraction above this — the agent runtime (m7) and the state/lifecycle
runtime (m8) — reads the SAME three cross-cutting things from megaplan today: the run
**envelope** (cost/taint/lineage/deadline/cancellation/retry-budget), a shared **error
base**, and the per-step **runtime context**. If those are not generic FIRST, every
later "extraction" silently re-imports `arnold.pipelines.megaplan` and the
"zero-megaplan-imports" outcome is false on day one. This is a small change set with an
outsized blast radius, so it gets its own isolated, gated checkpoint: prove the
foundation flips cleanly (megaplan now imports these FROM arnold, full suite green)
BEFORE piling agent/state extraction on top. A botched envelope move discovered while
also moving 8.5k lines of agent runtime would conflate two hard problems.

## In scope
1. **Unify the run envelope (the load-bearing seam).** There are TWO competing types
   today: the real `RunEnvelope` (`megaplan/_pipeline/envelope.py:15-56`) with the
   `join()` semilattice that key_pool/governor/sandbox/event-writer actually use, and a
   shape-incompatible stub `CrossCuttingEnvelope` (`arnold/runtime/envelope.py:53-100`,
   different field types, no `join()`). **Move the REAL `RunEnvelope` + its `join()`
   algebra to `arnold/runtime/envelope.py`**; demote/replace the stub as the
   identity-bootstrap layer it actually is; make megaplan import the envelope FROM arnold.
2. **Generic error base.** No generic error exists; `CliError`
   (`megaplan/types.py:599-614`) is used in 50+ sites and substrate modules each invent
   their own (`RoutingError`, `SchemaRegistryError`, …). Lift a minimal
   `ArnoldError(Exception)` (`code`, `message`, `exit_code` only — NO `valid_next`/`extra`,
   those are CLI semantics) to `arnold/runtime/errors.py`; `CliError` subclasses it.
3. **`RunContext` access on the generic `StepContext`.** The generic `StepContext`
   (`arnold/pipeline/types.py:114-131`) has no way for a step to read cost/lineage/taint/
   cancellation/deadline; only megaplan's `StepContext` carries `envelope`. Add an
   optional `envelope: RunContext | None` field where `RunContext` is a read-only
   **Protocol** (taint, cost, lineage, cancellation, deadline, retry_budget). `RunEnvelope`
   implements it. This avoids dragging the full `join()` semilattice into the step Protocol
   while giving any pipeline's steps access to cross-cutting state.

## Out of scope
The governor + budget_authority enforcement policy (stays megaplan, wraps the generic
pool in m7); the planning STATE vocabulary; anything that reads the envelope (those move
in m7/m8 and simply import it from arnold now).

## Done criteria
- `arnold/runtime/{envelope,errors}.py` carry the canonical `RunEnvelope` (+`join()`),
  `RunContext` protocol, and `ArnoldError`, importing **zero** `arnold.pipelines.megaplan`.
- Megaplan imports `RunEnvelope`/`ArnoldError` FROM `arnold.runtime`; `CliError`
  subclasses `ArnoldError`; old import paths re-export as compat shims.
- Generic `StepContext` exposes optional `envelope: RunContext`; existing megaplan steps
  read cost/taint/etc. through it unchanged.
- Full suite green; envelope `join()` algebra has parity tests; no behavior change.

## Locked decisions
- MOVE + dependency-inversion, not a rewrite. Preserve the envelope `join()` semantics and
  `CliError`'s public attributes exactly (50+ callers).
- The generic substrate owns the carrier *shape*; megaplan owns the *enforcement* (governor,
  budget) and *vocabulary* (error codes), layered on top.

---

## Ground-truth validation (2026-06-09) — judgment-filtered

A neutral validator checked the envelope claim against the code. Two corrections, one
of them against the validator's own recommended direction:

- **Envelope is a MERGE-AND-RECONCILE, not a clean MOVE.** The real `RunEnvelope`'s
  imports are fully generic (movable ✓), but the existing `arnold/runtime/envelope.py`
  stub `CrossCuttingEnvelope` has **incompatible field shapes** (`taint: tuple` vs `str`,
  `cost: Mapping` vs `float`, `cancellation: str|None` vs `bool`, `retry_budget: Mapping`
  vs `int`) and is a *composed sub-record inside* `RuntimeEnvelope` that consumers depend
  on. So task 1 is: reconcile the two shapes + migrate `RuntimeEnvelope` consumers, not a
  file relocation. **My call (against the validator's "promote megaplan's flat one"):**
  keep the stub's RICHER structured shapes (`taint` as a tuple of sources, `cost` as a
  per-category mapping) — they are the better generic design — and port megaplan's
  `join()` algebra + the `lease_id`/`fencing_token`/`capacity_grant` fields ONTO the
  reconciled type. Also rename the `MEGAPLAN_ENVELOPE_IN` env var + `[megaplan-envelope]`
  stderr tag to neutral names. Size this M, not S.

- **Boundary enforcement: add a runtime import test (closes the leak-gate's real holes).**
  The m0 static leak gate (`tests/arnold/test_boundary_skeleton.py`) is stronger than
  feared (AST catches TYPE_CHECKING; raw token scan catches literal-string `importlib`),
  but has two genuine blind spots: dynamically-COMPUTED import paths (f-strings/config) and
  ContextVar-smuggled megaplan objects. Do NOT chase these with cleverer static analysis —
  add a **runtime check** to this milestone and reuse it in m7/m8: in a venv where
  `megaplan` is absent, `import arnold.runtime` (and later `arnold.agent`) must succeed.
  This catches ALL coupling — static, dynamic, and object-smuggled — empirically.
