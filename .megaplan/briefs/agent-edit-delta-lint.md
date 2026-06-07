# Agent-edit delta hygiene: a single deterministic pre-apply `lint()` pass

## Status / sequencing
This is the deliberate **10%-that-gets-90%** follow-on to the agent-edit-hardening epic
(m1 typed contract #60, m2 scoped apply #61, m3 module split, m4 real-browser tier). It is a
SINGLE-MILESTONE sprint — explicitly NOT the full delta-correctness epic. Run it only AFTER:
(a) the hardening epic's four milestones are merged, and (b) the full live RuneXX-style E2E
test pass on :8199 has been completed and any regressions it surfaced are fixed.

It captures the user-visible robustness win of delta hygiene without the parts that take 90% of
the effort for the last sliver (transcript-mined eval corpus, projection refactor, prompt tuning,
schema-constrained generation). Those are a documented fast-follow, NOT in scope here.

## Background (so the planner needs no outside context)
Production agent-edit uses the **`batch_repl`** protocol (NOT the dev-only `delta` protocol):
the model emits Python-REPL-style ops (`ksampler_2.seed = 999`, then `done()`) over a read-only
projection of the ComfyUI graph; ops are applied over the verbatim original to produce a review
candidate. `apply_delta`/`resolve_delta` in `vibecomfy/porting/edit_apply.py` already defends the
graph against malformed input (typed `unknown_node_target`, cross-scope-link, bad-slot, full-UI
preservation guards). The pipeline stages live in `vibecomfy/comfy_nodes/agent_edit.py`
(`ingest -> project -> agent_delta/batch_repl -> apply -> summarize`); the projection is built by
`vibecomfy/porting/edit_projection.py` (`render_edit_projection`); op parsing/normalization is in
`vibecomfy/comfy_nodes/agent_provider.py` + `vibecomfy/porting/edit_ops.py`; downstream no-op
filtering exists only AFTER field-change extraction (`_field_change_is_noop`/`_real_field_changes`
in agent_edit.py ~:258).

### Observed live failure modes (the gremlins this sprint kills)
1. **No-op re-emission** — the model emits ops where `old == new` (e.g. set seed to 999 when it
   is already 999) and even narrates it ("already 999 … but I'll apply it to be safe"). Reaches
   the user as a fake "landed edit" / pointless review turn. MOST COMMON, MOST VISIBLE.
2. **Identity confusion** — the projection prints BOTH a canonical `target=[scope_path, uid]`
   and the LiteGraph `id=`, adjacent to slot names; ops sometimes reference the wrong one,
   producing "unknown source" endpoints.
3. **Bad slots / link-id-as-slot** — `output_slot` carrying a link id rather than a slot index.
4. **Machine-text leak** — gate / "from null" / raw-dict fragments in user-facing messages
   (largely fixed downstream already; lint makes the rejection messages human at the source).

### Why this is the right 10%
apply already catches the structural malformations, so what actually LEAKS to the user today is
the no-op and the confusing messages. A single deterministic pre-apply pass fixes those at one
typed boundary that every future delta-correctness fix can consolidate into.

## Outcome
A pure, deterministic, offline-testable `lint()` pass runs between the model's emitted ops and the
apply stage, normalizing/rejecting the malformation class with typed, human-named results — so no
no-op ever reaches a user-visible "landed edit," and identity/slot confusion becomes an explicit
named rejection instead of a downstream symptom. Shipped behind a flag, reversible.

## Scope (IN)
1. **`lint(ops, original_ui, projection_index) -> LintResult`** — a pure function (no model
   calls, no I/O) in a new focused module under `vibecomfy/porting/` (e.g. `edit_lint.py`).
   Returns normalized ops + a list of typed rejections/normalizations, each naming the op and the
   node/field/link in human terms. The four checks:
   a. **No-op normalization** — drop ops whose effect is identity (`old == new` field assigns;
      links re-emitted identical to baseline). Normalization, not a hard fail. Record what was
      dropped (for audit/debug, not the top-line message).
   b. **Dual-identity resolution** — accept EITHER the canonical uid OR the LiteGraph id for a
      node/endpoint reference and resolve both to the single canonical identity; only fail
      (typed) when neither resolves. (This is the cheap stand-in for the deferred projection
      refactor — it removes the confusion's *consequence* without changing the projection.)
   c. **Slot/endpoint validation** — validate link endpoints against the node's real slot schema;
      turn link-id-as-slot / dangling endpoints into a named typed error.
   d. **Human rejection messages** — every rejection carries a human sentence
      ("KSampler `seed` is already 999 — no change needed", "no input slot `imagez` on
      VAEDecode") with machine detail kept in audit/debug only.
2. **Wire it before apply** for the production `batch_repl` path (and the dev `delta` path if it
   shares the apply entry) — lint runs, normalized ops flow to apply, rejections surface through
   the existing typed failure/response contract (reuse the m1 `outcome.kind`/contract surfaces;
   do not invent a new envelope).
3. **~15 hand-written unit tests** derived from the observed failure modes above (NOT a
   transcript-mined corpus). Each asserts lint's normalize/reject decision deterministically with
   no model call.
4. **Flag-gated rollout** — env flag (e.g. `VIBECOMFY_AGENT_EDIT_LINT=1`, default ON once green;
   off-switch documented) so it is reversible without a revert.

## Locked decisions
- Single deterministic function, pure, offline-testable; no model calls in lint.
- No-ops are NORMALIZED (dropped) not hard-rejected; structural malformations are typed
  rejections that flow through the EXISTING m1 contract surfaces.
- Dual-identity TOLERANCE in the linter is the chosen approach over a projection refactor.
- batch_repl is the production target; delta is dev-only — cover both only insofar as they share
  the apply entry point.
- Reuse `outcome.kind` / response-contract from m1 (merged) and the apply typed errors from
  `edit_apply.py`; do NOT add a parallel error taxonomy.

## Open questions for the planner
- Exactly where `lint()` slots in for batch_repl: the REPL executes ops to produce field_changes
  /ops — lint should operate on the resolved op set just before `apply_delta`/the candidate is
  built. Confirm the single chokepoint both protocols pass through.
- Whether no-op dropping belongs in lint or should reuse/absorb the existing
  `_field_change_is_noop` logic (prefer: lint owns it; the downstream filter becomes redundant
  and is removed or delegates to lint — but do not change downstream behavior beyond delegation).

## Constraints
- Pure/deterministic: lint has zero model calls and zero filesystem/network I/O.
- All existing suites green at fork (counts as of the hardening epic merge): roundtrip_smoke,
  agent_edit_lifecycle, agent_edit_response_contract (node --test), and
  pytest tests/test_comfy_nodes_agent_*.py. Add lint's unit tests on top.
- No behavior change when the flag is off.
- Do NOT modify out/editor_sessions evidence.

## Done criteria
- A submitted edit that is a pure no-op produces NO candidate / NO "landed edit" and a natural
  "already X — no change needed" message (verifiable by an existing-shape test).
- Each observed malformed op (wrong-identity ref, link-id-as-slot, dangling endpoint) is rejected
  pre-apply with a human-named typed error.
- `lint()` is pure and unit-tested (~15 cases) with no model; all prior suites stay green.
- Flag off ⇒ byte-identical behavior to pre-sprint.

## Touchpoints
`vibecomfy/porting/edit_lint.py` (new), `vibecomfy/porting/edit_apply.py` (call site / shared
chokepoint), `vibecomfy/comfy_nodes/agent_edit.py` (wire before apply; delegate/remove redundant
no-op filter), `vibecomfy/porting/edit_ops.py` / `edit_projection.py` (read for identity/slot
indices), tests under `tests/` (new lint unit tests + any updated expectations).

## Anti-scope (the deferred 90%-effort 10%-value — do NOT do here)
- NO transcript-mined eval corpus / replay harness (that is the fast-follow that makes prompt &
  projection changes safe; out of scope).
- NO projection refactor (dual-identity tolerance in lint stands in for it).
- NO prompt / system-message changes (the "don't emit no-ops" prompt nudge waits for the corpus).
- NO schema-constrained / structured generation.
- NO semantic-correctness work (right-shape-wrong-node); lint is malformation hygiene only.
- Do NOT touch ready_templates/, workflow_corpus/, the VibeComfy IR/CLI/router, or the
  model/provider delta-generation prompts.

## Recommended dials
`directed` / `light` / depth low, vendor codex. Rationale: deterministic compiler-front-end work
behind a hard green gate (difficulty-not-stakes → no premium critique needed); a premium planner
nails the lint API + the single chokepoint + identity-resolution contract, execution is mechanical
and routed per task. Shorthand: `directed/light @codex`.
