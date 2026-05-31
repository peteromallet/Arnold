# Brief — first-class model override for `claude:` and `codex:` agent specs

## 1. Outcome

Extend megaplan's agent-spec format so a slot can pin a specific Claude Code or Codex CLI model in addition to (or instead of) the reasoning-effort tier — and let that model be overridden at init time AND mid-run, the same way `--phase-model` and `megaplan override set-profile` work today. Pin megaplan's own default models — **Opus 4.7 (`claude-opus-4-7`) for `claude:` / Shannon slots, GPT-5.5 for `codex:` slots** — so that a megaplan run is reproducible regardless of what model the user's local `claude` / `codex` CLI happens to be set to. Update the `megaplan-decision` / `megaplan-rubric` skill docs to document the new spec syntax, the override verb, and the pinned defaults.

## 2. Scope

**IN:**
- New spec syntax `<agent>[:<model>][:<effort>]` for `claude:` and `codex:` agents, with backward-compat for every existing spec shape.
- **Pinned default models** in a single new constant module (e.g. `megaplan/_pipeline/defaults.py`): `CLAUDE_DEFAULT_MODEL = "claude-opus-4-7"`, `CODEX_DEFAULT_MODEL = "gpt-5.5"`. When a spec has no explicit model, the worker uses these defaults (injects `--model claude-opus-4-7` to Claude Code and `-c model="gpt-5.5"` to codex). The planner must verify that `"gpt-5.5"` is the exact accepted CLI string by checking codex CLI's supported model list (`agent/hermes_cli/codex_models.py` has the list of known IDs) — if codex 5.5 ships under a slightly different alias (`gpt-5.5-codex`, etc.), pick the canonical one and document the choice in the review.
- **Skill doc updates**: update `/Users/peteromalley/.claude/skills/megaplan-decision/SKILL.md` (and any sibling `megaplan-rubric` doc with overlapping content) to document (a) the new `<agent>[:<model>][:<effort>]` spec syntax with examples; (b) the new `megaplan override set-model` verb in the "When the dials turn out wrong" section; (c) the pinned default models, including how to override them (`--phase-model`, override verb, or `[defaults]` block deferred to follow-up).
- `parse_agent_spec` (and any other parsers in `_pipeline/profile.py`, `_pipeline/registry.py`) updated to return `(agent, model_or_none, effort_or_none)` — or equivalent — without breaking existing callers.
- Worker plumbing in `workers/_impl.py` and `workers/shannon.py` so `model` is threaded into:
  - **Codex:** an extra `-c model="<id>"` arg alongside the existing `-c model_reasoning_effort=...`. Apply on both the fresh and `resume` branches of `run_codex_step`.
  - **Claude / Shannon:** a `--model <id>` arg added to the `claude` invocation. Shannon already passes `claudeArgs` through (`shannon.py:417-418`); thread the new model into that args list.
- `session_key_for(step, agent, model=model)` already exists at `_impl.py:1794` — pass the resolved model into it so sessions don't get resumed across model changes.
- `--depth` rewriter updated to operate on the *effort* slot only, leaving any pinned model alone (so `codex:gpt-5.3-codex:low` becomes `codex:gpt-5.3-codex:high` under `--depth high`).
- `--vendor` / `--critic cross` swappers updated to **refuse** when the slot has a pinned model — raise `CliError("vendor_swap_model_conflict", ...)` naming the offending slot. (Locked decision, see §3.)
- New override verb `megaplan override set-model --plan ID --phase PHASE --model MODEL [--effort EFFORT]`, mirroring `set-profile`. Mutates `state.config.profile[phase]` to the new spec. Effect: next invocation of that phase uses the new spec (same semantics as `set-profile` today).
- `--phase-model` accepts the new spec syntax automatically once the parser handles it — no separate work.
- Tests: parser round-trip across all spec shapes; effort-only vs model+effort vs model-only; vendor-swap refusal path; per-phase override roundtrip through `state.json`; CLI smoke that exercises codex `-c model=` injection and claude `--model` injection (mock the CLIs).

**OUT:**
- No new profile files. Built-in profiles keep using `claude` / `claude:low` / `codex:low` etc.
- No model-aliasing or model-validation in megaplan — pass the string through to the CLI and let it complain if invalid.
- No UI for picking models in the resident.
- No `[defaults]` block for default claude/codex models in `~/.config/megaplan/config.toml` — see §4 (deferred).
- No changes to hermes specs; they already carry a model.

Sized to ≤2 weeks of focused work.

## 3. Locked decisions

- **Spec syntax**: `<agent>[:<model>][:<effort>]`. Disambiguation: if the first post-`:` token matches `_VALID_CLAUDE_EFFORTS` / `_VALID_CODEX_EFFORTS`, it's an effort (old shape). Otherwise it's a model, with optional `:<effort>` after.
- **Backward compat**: every existing spec shape (`claude`, `claude:low`, `codex:high`, `hermes:openai/gpt-5`, `hermes:fireworks:accounts/...`) parses to identical semantics. Zero behavior change for any existing profile or invocation.
- **Vendor-swap on pinned model**: **refuse**. `--vendor codex` against a profile slot like `claude:opus-4.7:high` raises `CliError("vendor_swap_model_conflict", ...)` naming the slot. Silent drops are how runs end up using the wrong model — force the user to be explicit. Same for `--critic cross`.
- **Session keying**: `session_key_for` already accepts `model`; thread the *resolved* model (after default fallback) through. A `set-model` override mid-plan implicitly creates a new session for the next invocation of that phase (because the key changes). That is the correct behavior — we never want to resume a Claude Code session into a different model.
- **Pinned defaults (replaces prior "defaults unchanged")**: when no model is in the spec, megaplan injects its own defaults — `claude-opus-4-7` for `claude:` / Shannon slots and `gpt-5.5` (or codex CLI's canonical 5.5 alias if different — planner verifies) for `codex:` slots. The user's `~/.codex/config.toml` `model =` and Claude Code's `/model` setting are **bypassed** when megaplan invokes these tools, so a megaplan run is reproducible regardless of local CLI configuration. Standalone `claude` / `codex` use outside megaplan is unaffected.
- **Codex spec quoting**: pass the model id as `-c model="<id>"` (quoted), matching how `model_reasoning_effort` is passed today.
- **Override verb shape**: clone `_override_set_profile` in `handlers/override.py` into `_override_set_model`. Register in the `_OVERRIDE_ACTIONS` map at `handlers/override.py:370` and add `"set-model"` to the `override_action` choices list in `cli.py:2290`. Validate that `--model`'s value isn't a reserved effort token before writing.

## 4. Open questions

- **(planner must resolve before execute)** Confirm the exact CLI string for "GPT-5.5" accepted by the local `codex` CLI. Check `agent/hermes_cli/codex_models.py` for the known model list and the actual codex CLI's accepted aliases. If the canonical 5.5 string is `gpt-5.5-codex` or some variant, use that and document the choice in the review write-up. The pinned constant is `CODEX_DEFAULT_MODEL`; this question is just about its exact value.
- **(deferred, NOT in this sprint)** Should `~/.config/megaplan/config.toml` get `[defaults] claude_model = "..."` / `codex_model = "..."` keys so a user can override the pinned defaults without per-invocation flags? Likely yes as a small follow-up, but not on this sprint's critical path. Mention in the review write-up as a one-line follow-up note.

## 5. Constraints

- **Strict back-compat.** Every existing spec, every existing profile, every existing invocation must produce identical resolved specs and identical CLI invocations after this change. Add a regression test that loads every built-in profile, resolves it under all `--depth` / `--vendor` / `--critic` combinations, and snapshot-compares the resolved phase->spec map against a baseline.
- **Performance**: parser is called many times per run. Keep the new branch O(1); don't introduce dict allocs in the common (effort-only) path.
- **No new deps.** Everything fits in the stdlib.
- **Validation**: model strings pass through unvalidated. Effort tokens continue to validate against `_VALID_CLAUDE_EFFORTS` / `_VALID_CODEX_EFFORTS` and raise `CliError("invalid_args", ...)` on mismatch.

## 6. Done criteria

A run is "done" when all of the following hold:

1. `megaplan init <brief> --profile partnered --phase-model critique=codex:gpt-5.3-codex:high` succeeds and the resulting `state.json` shows `critique` resolved to a three-part spec; the actual `codex` command executed for that phase contains both `-c model="gpt-5.3-codex"` and `-c model_reasoning_effort=high`.
2. Same for claude: `--phase-model plan=claude:sonnet-4.6:medium` produces a `claude` invocation containing `--model sonnet-4.6` (and the medium-effort plumbing Claude Code uses).
3. **Pinned defaults**: a vanilla `megaplan init <brief> --profile partnered` (no `--phase-model`, no model in any slot) produces codex invocations containing `-c model="gpt-5.5"` (or the planner-chosen canonical 5.5 alias) and claude invocations containing `--model claude-opus-4-7`. Verified by inspecting the actual command lines in worker output / test mocks.
4. `megaplan override set-model --plan ID --phase critique --model gpt-5.3-codex --effort high` mutates `state.config.profile.critique` and the *next* critique invocation uses the new spec.
5. `megaplan init ... --profile partnered --vendor codex` against a profile that includes a pinned-model slot raises `CliError("vendor_swap_model_conflict", ...)` with the slot name in the message.
6. The full existing test suite passes unchanged.
7. The regression test described in §5 (snapshot of every built-in profile under all dial combinations) passes — with one expected snapshot delta: every resolved claude/codex slot now carries the pinned default model. Update the snapshot baseline as part of the sprint, do not leave it stale.
8. New tests: parser round-trip, override verb roundtrip, refusal path, default-injection smoke tests, CLI injection smoke tests — all pass.
9. The `megaplan-decision` skill doc (`~/.claude/skills/megaplan-decision/SKILL.md` and any sibling rubric file) is updated to document the new spec syntax, the `set-model` override verb, and the pinned defaults — with at least one worked example each.

## 7. Touchpoints

- `megaplan/_pipeline/defaults.py` (NEW) — `CLAUDE_DEFAULT_MODEL = "claude-opus-4-7"`, `CODEX_DEFAULT_MODEL = "gpt-5.5"` (or canonical 5.5 alias). One place to change the pinned defaults later.
- `megaplan/types.py` — `parse_agent_spec`; `_VALID_CLAUDE_EFFORTS` / `_VALID_CODEX_EFFORTS` referenced for disambiguation.
- `megaplan/_pipeline/profile.py` — depth rewriter, vendor swapper, `--critic cross` handling. Look for the function that swaps `claude:X` ↔ `codex:X` and the one that rewrites effort suffixes.
- `megaplan/profiles/__init__.py` — `_swap_vendor` at line ~272; ensure refusal path lives here or in `_pipeline/profile.py`, whichever owns vendor swapping at resolution time.
- `megaplan/workers/_impl.py` — `run_claude_step` (line 1811), `run_codex_step` (line 1840), and the inner `-c model_reasoning_effort=...` injection at lines 1889 and 1959. Add `model: str | None = None` kwarg and thread it through. Update `session_key_for` callsites to pass model.
- `megaplan/workers/shannon.py` — `run_shannon_step`. Add `model` kwarg; append `--model <id>` to the claude args list before the prompt.
- `megaplan/handlers/override.py` — clone `_override_set_profile` (line 316) into `_override_set_model`; register in `_OVERRIDE_ACTIONS` at line 370.
- `megaplan/cli.py` — extend `override_action` choices at line 2290 with `"set-model"`; add `--model` and `--effort` args to the override subparser; add validation at the `args.command == "override"` branch around line 2820.
- `~/.claude/skills/megaplan-decision/SKILL.md` — add new-syntax section, new override verb, pinned defaults table. Look for a similar file under `~/.claude/skills/megaplan-rubric/` and update it the same way if the content overlaps.
- Tests: `tests/test_types.py` (or wherever `parse_agent_spec` is tested), `tests/test_profiles.py`, `tests/test_override.py`, `tests/test_workers_codex.py`, `tests/test_workers_shannon.py`. Add a new snapshot test for the regression check, and add a new test that asserts default-model injection happens for vanilla specs.

## 8. Anti-scope

- **Don't** refactor `parse_agent_spec`'s call sites beyond the minimum needed to consume the new return shape. If callers only need `(agent, effort)`, give them a small helper that discards the model field.
- **Don't** rename anything in the worker layer. `effort` stays `effort`.
- **Don't** add a `model =` field to any built-in profile TOML. Built-in profiles stay as they are.
- **Don't** touch the hermes spec parser or hermes worker plumbing.
- **Don't** add model validation, alias-resolution, or "we recommend you use X for Y" logic. Pass strings through.
- **Don't** add the `[defaults] claude_model = ...` config key in this sprint — it's deferred (see §4). The pinned-default *constants* land; the user-facing config key to override them does not.
- **Don't** refactor Shannon's claudeArgs construction beyond appending the new flag.
- **Don't** change pricing/cost accounting. `_codex_step_cost` already reads model from the rollout JSONL; it'll pick up the new model automatically.

---

**Profile notation:** `partnered/full/medium @codex +in-worktree`
**Invocation:**
```
megaplan init .megaplan/briefs/cli-spec-model-override.md \
  --profile partnered \
  --depth medium \
  --vendor codex \
  --in-worktree spec-model-override
```
