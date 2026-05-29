# a6 — Is the `prompt_override` dispatch seam honest, or a half-measure?

**Verdict: HONEST. `prompt_override` is the right shared boundary for the dispatch
service. There is NO thin reusable prompt-assembly primitive hiding inside the
planning builders to extract, and attempting to extract one is out of scope and
would not pay for itself.**

---

## 1. Is prompt assembly coupled to planning state, or is there a reusable primitive?

**Tightly coupled, by design. There is no model-agnostic "messages/context → string"
assembly primitive.**

Evidence:

- `megaplan/prompts/__init__.py` exposes `create_prompt(agent, step, state, plan_dir, root, **kwargs)`
  and the thin per-agent wrappers `create_codex_prompt` / `create_hermes_prompt` /
  `create_claude_prompt`. This IS a reusable seam — but its reuse axis is **agent ×
  planning-step**, not "arbitrary messages." `_AGENT_REGISTRY` maps `claude/codex/hermes`
  → a builder dict keyed by the fixed planning step vocabulary
  (`plan, prep, prep-triage, prep-distill, critique, critique_evaluator, revise, gate,
  finalize, execute, review, feedback`). `_resolve_builder` then branches further on
  `state.config.mode` (`code` / `doc` / creative / `joke`). Add a step that isn't in
  this vocabulary and `create_prompt` raises `unsupported_step`.
- The individual builders are bespoke planning-phase f-strings, not parameterized
  renderers. Across `megaplan/prompts/*.py` there are **188** references that read
  deep `state` fields or planning artifact files. The builders hydrate themselves from
  **15+ distinct planning-phase artifact files** under `plan_dir`:
  `prep.json, prep_triage.json, prep_metrics.json, critique.json, critique_output.json,
  gate.json, gate_carry.json, finalize.json, review.json, review_output.json,
  execution.json, execution_audit.json, execution_checkpoint.json,
  tiebreaker_decisions.json, state.json`. Examples:
  - `_plan_prompt` (`planning.py:189`) reads `state["config"]` (project_dir, from_doc,
    mode, output_path, primary_criterion), `state["idea"]`, `state["meta"]["imported_decisions"]`.
  - `_execute_prompt` (`execute.py:376`) reads `finalize.json`, `latest_plan_meta_path`,
    a gate summary, `review.json` (prior-review block + rerun guidance), execution nudges,
    user-action resolutions, and a debt block.
- These files are *outputs of earlier planning phases*. The prompt for phase N is
  literally a projection of the artifacts phases 1..N-1 wrote. That is the definition of
  planning-state coupling, and it is intrinsic to what a planning prompt *is* — not an
  accident waiting to be refactored out.

There is no inner "render messages for model X with this context" helper. The only
genuinely model-specific formatting is small and lives **on the dispatch side already**:
the JSON-output contract / schema reminder (`_append_json_output_contract` in shannon,
`OUTPUT FILE` + template scaffolding in hermes, `--output-schema` for codex). That is the
*envelope*, and it is correctly owned by the worker, not the builder.

## 2. With `prompt_override`, what must the caller build itself? Reasonable boundary?

**The caller builds only the prompt body. Everything reusable about dispatch stays in the
service. The boundary is reasonable — it pushes the *workflow-specific* work (which is
inherently un-shareable) to the caller and keeps the *model-specific* work shared.**

When `prompt_override` is passed, the workers still own (do NOT delegate to the caller):

- session resolution + reuse: `session_key_for(step, agent, model)`, `state["sessions"]`,
  headroom/eviction (codex `_impl.py:1717-1739`, shannon `:938`, hermes `:741`).
- working-directory resolution: `resolve_work_dir(state)`.
- schema selection per step/mode and the **model-specific output contract** appended
  *after* the override (shannon `_append_json_output_contract` `:959`; hermes template +
  `OUTPUT FILE` block `:806-827`; codex `--output-schema`/`-o`).
- sandbox/writable-roots, container detection, model/effort flags, json-trace, timeouts,
  retry-on-stall, runtime fallback (`run_step_with_worker` `:2510-2657`).
- per-phase tool/web-search guidance (hermes `:766-782`).

So the caller (Arnold) supplies: the rendered body string, plus a **minimal shim_state**.
`loop/engine.py:run_loop_worker` (`:505-527`) is the existence proof: it calls its own
`build_loop_prompt(...)`, constructs `shim_state = {"config": ..., "sessions": ...}`, and
dispatches through `run_step_with_worker(..., prompt_override=prompt)`. The resident loop
never touches a single planning artifact file and never calls `create_prompt`. That is
exactly the contract m2 wants to lock.

The body is *not* reusable across callers by nature: a loop prompt, a planning prompt, and
an Arnold prompt encode different workflows reading different state. There is nothing to
share there. The model-specific formatting that *is* reusable is already shared in the
worker. So the override boundary does **not** push the genuinely-hard reusable work onto
callers — it pushes the genuinely-unshareable work onto them, which is correct.

## 3. Is there a thin reusable render primitive that SHOULD be the seam instead?

**No.** The candidate would be "given messages + context, format for model X." But:

- The only model-X-specific formatting (JSON contract, output-file scaffolding, schema
  reminder, tool guidance) is keyed off `step` and `schema`, and already lives on the
  dispatch side, after the override branch. It is effectively already "the shared seam,"
  just not named as a standalone primitive — and it does not need the caller's
  cooperation, so it should stay internal to the worker.
- Everything else in the builders is workflow content, not formatting. Extracting a
  "primitive" would mean extracting 188 planning-coupled reads, which only re-creates the
  planning builders under a new name.

If anything is worth a *tiny* tidy, it is naming/centralizing the post-override output
contract (today three near-parallel implementations across codex/shannon/hermes). But that
is a worker-internal DRY nit, not a new caller-facing seam, and explicitly not what m2 is.

## 4. VERDICT + plan implications

- **Honest, not a half-measure.** "Prompt assembly" is not a single reusable hard thing
  that the override leaves stranded; it is per-workflow content that *cannot* be shared,
  plus per-model formatting that *is already* shared inside the workers. The override seam
  draws the line in exactly the right place: shared = dispatch (sessions, sandbox, schema,
  contract, retry, fallback); caller-owned = the workflow body + a `{config, sessions}`
  shim.
- **No plan change required for m2.** Locking the shared dispatch service to the
  `prompt_override` + minimal-`shim_state` path is the correct boundary and is already
  battle-proven by `loop/engine.py`. The epic should NOT add a prompt-assembly primitive
  to scope — there is no honest reusable primitive to extract, and a forced one would just
  rename the planning builders.
- **One small hardening to fold in (optional, cheap):** make the dispatch service's
  contract *explicit* that callers pass `prompt_override` AND a shim_state carrying at
  least `config.project_dir`, `config.mode`, `name`, and `sessions` — because the workers
  still read those even when the body is overridden (shannon reads `state["name"]` at
  `:908`; all read `config.mode` for schema selection; all read `sessions`). A caller that
  passes `prompt_override` but a too-thin shim will `KeyError` at dispatch, not at a clean
  boundary. Documenting/validating the shim contract is the only real sharp edge.

## Residual uncertainty

- I did not enumerate every Arnold call site (Arnold isn't in-tree yet); the conclusion
  rests on the loop driver as the canonical precedent. If Arnold needs phases *outside*
  the fixed planning-step vocabulary AND wants the worker's auto-built fallback (no
  override), that fallback would `unsupported_step`. But under the override contract that
  is a non-issue — the override is precisely how you escape the planning vocabulary.
- The three parallel output-contract appenders (codex/shannon/hermes) are a latent
  inconsistency risk (a model could get a subtly different contract), but that is
  pre-existing and orthogonal to the seam decision.
