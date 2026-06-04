# M2 — Typed result contracts & protocol collapse

Publishes `agent-edit-contracts.md` §3 (typed `TurnOutcome` incl per-field
`FieldChange[]`), §4 (typed envelope, always-non-empty `message`), §6
(provider-readiness). Consumes M1's §1/§2.

## Outcome
Every turn returns ONE typed, always-messaged outcome on ONE canonical protocol. A
turn can both edit and ask; a `message` is never empty; the preview can show the real
changed field and its new value. Reviewer checks: a turn emits `edit+clarify`; an
edit outcome carries `{uid, field_path, old, new}`; `message` is always present even
when the model emits no prose.

## Scope — IN (strict internal order)
1. **FIRST: collapse the protocol zoo.** Make `batch_repl` the one canonical product
   path; quarantine `delta`/`full` behind dev-only tests. The typed outcome wraps a
   single executor shape. (Fix-first — every contract below otherwise needs three-way
   compat branches.) **Sizing reality (validated):** this is NOT a flag-flip — the
   delta/full branches live INLINE in the shared response+audit builder
   (`agent_edit.py:2103-2134`), so it's a surgical extraction into per-contract
   builders, plus migrating/quarantining ~150 delta/full tests across ~5 files. This
   is the bulk of M2's first task and its biggest regression surface.
2. **§3 typed `TurnOutcome`** — discriminated union `edit | clarify | edit+clarify |
   failure | noop | budget`. The `edit` variants carry **`changes: FieldChange[]` =
   `{uid, field_path, old, new}`** (the preview/diff contract).
   *Validated implementation realities (this is code surgery, not UI work):*
   - `edit+clarify`: today `clarify()` early-returns BEFORE `apply_batch` and forces
     `graph_unchanged=True` (`agent_edit.py:985`/`:2108`), so landed edits are
     discarded. Making it first-class = break the mutual-exclusion at 3 levels: apply
     the batch before handling clarify; have the StageResult carry both; stop forcing
     `graph_unchanged` when edits landed.
   - `FieldChange.old` is NOT on the ops (`SetNodeFieldOp` has only `value`). Recover
     `old` by joining landed ops × the `original_ledger` snapshot — which is
     **protocol-independent (exists in `batch_repl`, does NOT require reviving
     `delta`)**. Stamp `old` at apply-time so `changes` is self-contained.
3. **§4 typed envelope + always-non-empty `message`.** Documented shape the UI reads
   as state: `message`, `TurnOutcome`, candidate + `eligibility`, `audit_ref`; raw
   gate booleans/hashes become debug-only fields. The **backend fallback synthesizer**
   guarantees `message` non-empty (sentence-shaped: precedence landed→done→diagnostic
   →budget) + the per-action message contract + the "User-facing reply" prompt
   instruction + the two-tier empty-prose nudge. *Validated:* for `batch_repl` the
   empty-message risk is `extract_batch_fence` returning empty prose
   (`agent_provider.py:159`) — put the fallback there; the worker's "Applied the
   requested edit." fallback (`megaplan_worker.py:85`) is dead code for `batch_repl`
   (safe delete), so step 5 is a deletion for the canonical path.
4. **§6 provider-readiness** — one `readiness() -> {ready, reason}` source.
5. **De-dup worker/parent parse+message fallback** (`megaplan_worker.py` vs
   `agent_provider.py`) so the synthesizer is the single owner.
6. **Parser hardening (tail-slip).** Cut the routine first-attempt missing-```batch
   fence retry. ONLY this may slip to a follow-on if M2 overruns.
7. **Turn cancellation — decide at planning (validated gap).** No cancellation
   primitive exists: `_run_worker` is a blocking `subprocess.run` with no handle, no
   `/cancel` route, no `cancelled` outcome (`megaplan_runtime.py:172`). M4's "Stop"
   is otherwise cosmetic. Either (a) add `Popen` + a handle registry + a `/cancel`
   route + a `cancelled` `TurnOutcome`/`FailureKind` variant (M2's runtime/outcome
   territory), or (b) descope M4's Stop to dismiss-UI-only. (a) is the better UX;
   (b) is the slip if M2 is tight — same slip class as parser hardening.

## Locked decisions
- `batch_repl` is canonical; `delta`/`full` quarantined, not deleted (yet).
- `FieldChange` is authoritative (from ops), not a client positional widget-diff.
- The synthesizer is backend-authoritative AFTER gates (the model writes prose before
  gate results exist).

## Open questions (planner resolves)
- Whether `batch_repl` can recover full `FieldChange` data directly, or needs the
  op-level `target/value` that delta exposes — and if so, how to carry it without
  reviving the delta path.
- Memory-context shape (compact block vs replay) is M3's, but the envelope/outcome
  must be shaped so M3 can wrap a `Message` around it.

## Constraints
- No behavior regression for the canonical path; the quarantined paths keep their
  dev-only tests green.
- `pytest tests/test_comfy_nodes_agent_*.py` green (modulo known baseline failures).

## Done criteria
- One canonical protocol; `delta`/`full` no longer on the product path.
- A turn emits `edit+clarify`; `message` never empty (synthesizer verified); an edit
  outcome carries per-field `changes`; `readiness()` is one signal.
- First-attempt malformed-fence retries ≈ 0 on the SD3-class prompt.

## Touchpoints
- `agent_provider.py` (`build_batch_messages` prompt contract; `extract_batch_fence`;
  parse/retry; synthesizer), `agent_edit.py` (protocol routing `:568/:2024/:2036/:2050`;
  the typed outcome + envelope; edits-and-asks; `changes` from ops), `agent_session.py`
  + `porting/` (recovering `FieldChange` from the executor), `megaplan_worker.py`
  (de-dup fallback), tests.

## Anti-scope
- Don't build the conversation/memory layer (M3) or the UI (M4). Don't touch M1's
  baseline authority except to consume it. Don't delete the quarantined protocols
  (just take them off the product path).

## Topological note
Collapsing three live executor paths into one reshapes shared contracts across
provider/session/response/UI — the sharpest topological case in the epic; a bad
consolidation breaks downstream non-locally. Premium planner, collapse sequenced
first. Profile: `partnered/full/high` @codex, no prep.
