Now I have all the evidence I need. Here's my ranked findings:

---

## LENS 6 — Errors, diagnostics & next_action: Audit Findings

### HIGH

1. **`next_action` silently lost in `_prepare_prompt` wrappers** — `session.py:855-860` and `session.py:886-891`. These catch-alls wrap `ValueError`/`RuntimeError`/`Exception` into fresh `RuntimeError("Workflow build failed: ...")` with **no `next_action`**. A `VibeComfyError` subclass carrying remediation guidance that somehow gets caught as a plain `RuntimeError` will have its `next_action` stripped before reaching the CLI's `print(exc)` at `commands/run.py:164`. The `VibeComfyError` branch at `session.py:851`/`882` protects only type-exact subclasses, but if any subclass happens to not match `isinstance(exc, VibeComfyError)` (e.g., due to some future refactor), the fallback silently discards the hint.

2. **Raw `RuntimeError` raised for session lifecycle violations — no `next_action`** — `session.py:230`, `session.py:240`, `session.py:257`, `session.py:264`, `session.py:399`, `session.py:456`, `session.py:592`, `session.py:607`, `session.py:611`. All these raises are domain-level errors (concurrent run, ensure_packs failure, stop-while-inflight) but use bare `RuntimeError`. They get caught at `commands/run.py:163` and printed as `"run failed: ..."` with no remediation hint. Some have obvious remediations (e.g., "wait for run to complete"), which should be `next_action` strings. This contradicts CLAUDE.md:491: "all extend `VibeComfyError(RuntimeError)` with an optional `next_action`".

3. **Duplicate diagnostics logic** — `environment_diagnostics.py:9` defines `metadata_environment_warnings()` that returns `list[str]`. The `diagnostics/` package (`diagnostics/health.py`) is a separate, richer diagnostics system with `SubcheckFinding`/`SubcheckResult`/`HealthReport` dataclasses. Both are wired in: `workbench.py:16` imports `environment_diagnostics`, `doctor.py:21` imports it too, but `health.py` has its own `run_doctor_readiness` that duplicates some doctor checks (missing nodes/models/outputs) in a different data model. Two diagnostics systems with different output schemas, one with structured severity codes (`health.py`) and one returning raw strings (`environment_diagnostics.py`). No obvious reconciliation path or deprecation comment.

### MED

4. **`SyntaxError` caught naked at `commands/run.py:163` — invisible to user** — The CLI catch tuple is `(OSError, RuntimeError, ValueError)`. A `SyntaxError` from importing a broken scratchpad/ready template would propagate uncaught to `cli.py:17` → traceback dump to stderr instead of a friendly `"run failed: ..."` message. This is inconsistent with the intent that the CLI catch should handle all user-facing errors gracefully.

5. **`QueueError` always carries `next_action="vibecomfy runtime doctor"`** — `session.py:334-336` and `session.py:518-520`. While consistent, the `next_action` is hardcoded and generic. If the underlying exception is e.g. a `KeyError` for a missing node, "runtime doctor" is misleading. The `next_action` should vary based on the wrapped exception type to be actionable.

6. **`OSError` from `EnvironmentError` subclasses NOT caught** — `commands/run.py:163` catches `OSError` but not `EnvironmentError`. On Python 3, `OSError` is the base for `FileNotFoundError`, `PermissionError`, etc., so those are caught. But `EnvironmentError` (the old Python 2 base) is an alias for `OSError` in Python 3, so this is technically fine. However, `ConnectionError` (a subclass of `OSError`) is caught, which is correct. **This is not actually a bug** — downgrading to note only.

### LOW

7. **`next_action` in `str()` has no spacing after message** — `errors.py:27`: `f"{msg} next action: {self.next_action}"` produces `"Workflow queue failed: ... next action: vibecomfy runtime doctor"` with no separator (comma, period, newline) before "next action". The CLI prints this verbatim at `commands/run.py:164`, producing a run-on sentence.

8. **`_session_url_healthy` returns `bool` but catches `ValueError`** — `session.py:694`. `urllib.request.urlopen` can raise `ValueError` for malformed URLs, which is caught alongside `OSError`/`URLError`. But the function returns `bool` silently — the caller at `active_session_metadata:661` treats `False` the same regardless of whether it was a malformed URL or a genuine connection failure. No logging to differentiate.

---

### **Worst thing in my lens**

**Raw `RuntimeError` proliferation in `session.py`** (item #2). The project states in CLAUDE.md:491 that all errors extend `VibeComfyError(RuntimeError)` with optional `next_action`. Yet the *execution hot path* — the session layer where most runtime failures originate — raises 9+ bare `RuntimeError`s with no `next_action`, no domain-specific subclass, and no structured error metadata. These hit the user as `"run failed: session already has a run in flight..."` with zero remediation hint. This is the highest-impact inconsistency because it directly contradicts the project's own error architecture where it matters most: the run path.