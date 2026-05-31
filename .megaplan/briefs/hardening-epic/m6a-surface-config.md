# M6a — Surface & config cleanup

**Rubric:** `directed/full` (NOT light — prompts/profiles/CLI have real blast radius)
**Position in epic:** milestone 11 of 12. Depends on M5b (operates on the post-split `cli/` package — all `cli.py` line numbers below are pre-split and stale; resolve to the new submodule).

## Outcome
Clear user-facing surface and config cruft: hardcoded values that should be parameters, the profile-default sentinel, prompt template/dedup issues, and CLI flag inconsistencies.

## Scope (IN)
### Prompts
- Remove hardcoded model names from `prompts/critique_evaluator.py:378-379` (`deepseek-v4-pro`/`-flash`). **Per review: these are natural-language *examples* in guidance text, not executable config** — apply judgment; the concrete rule is "no model identifier string in any `.py` outside `profiles/*.toml` and `_pipeline/defaults.py`," and if the example is genuinely instructional, parameterize the name rather than delete the guidance.
- De-duplicate the three near-identical builder dicts `_CLAUDE_/_CODEX_/_HERMES_PROMPT_BUILDERS` (`prompts/__init__.py:73-134`); the `_execute_batch_prompt` inline approval-note (`prompts/execute.py:510-518`) vs the `_execute_approval_note` helper (`:205-213`) — de-dup by passing `state` to the helper.
- **`review_joke.py`/`review_doc.py` near-clones — de-dup CAREFULLY.** Per review, these have subtly different output strings ("Approved scene canvas" vs "Approved plan"); de-duplicating risks **prompt-output drift**, which violates "no behavior change to user-facing outputs." Either keep the output strings byte-identical to today (shared base + per-domain string params) with a snapshot test, or downgrade to a `# TODO` and skip.
- Genericize `PLAN_TEMPLATE` (`prompts/planning.py:90-120`, injected via `:315`) — it uses megaplan's own paths as the example shown to every repo. Done-criterion: `PLAN_TEMPLATE` contains zero `megaplan/` file-path references.

### Profiles / config
- Replace the `default = "partnered"` sentinel duplicated across 15 `profiles/*.toml`. **DECISION LOCKED (refined after Opus sense-check — the original framing had two landmines):** introduce a single module constant `SYSTEM_DEFAULT_PROFILE = "partnered"` in `profiles/__init__.py` as the **system fallback**, and delete the `default=` key from the *system* TOMLs.
  - **Preserve the user/project override path.** `load_profile_metadata` (`profiles/__init__.py:477-501`) merges user (`~/.config/megaplan/profiles.toml`) and project (`.megaplan/profiles.toml`) metadata over system — so today a user/project TOML can set its own `default=`. `resolve_pipeline_profile` (Layer 4, `:1121-1132`) must still honor a `default=` from those layers if present, falling back to `SYSTEM_DEFAULT_PROFILE` only when none is set. (The "arbitrary dict-iteration" rationale in earlier drafts was moot — all 15 system TOMLs are `partnered`, so the scan is already deterministic. The real win is killing the duplication, not fixing nondeterminism.)
  - **Update the two tests that hard-assert the keys — M6a MUST touch these or it fails unattended:** `tests/profiles/test_pipeline_profiles.py` `test_system_profiles_have_default_field` (`:93`, asserts every shipped profile has a `default` metadata key) and `test_partnered_has_default_field` (asserts `metadata["partnered"]["default"] == "partnered"`). Rewrite to assert the *resolved* system default is `partnered` via the constant, and that a user/project `default=` override still wins.
- Fix the contradicting feedback-lock comment (`profiles/__init__.py:1241-1255`): comment claims `claude:low` lock, code preserves whatever the profile sets. Decide which wins and align; decide whether `all-claude.toml`'s bare `feedback = "claude"` should be `claude:low`.
- Reconcile tier-spec format drift between `variable.toml` and `variable-claude.toml` (effort-suffix vs explicit model pins for the same tiers).

### CLI (target the post-M5b `cli/` package)
- Add the missing `--work-dir` flag to `tiebreaker-run` (was `cli.py:4117-4133`) — every sibling has it.
- Rename `migrate-local-plans`'s `--target-project-dir` (was `:3537`) to the universal `--project-dir`.
- Remove the dead `feedback --show` legacy flag (was `:3553-3571`) that just overwrites the positional `operation`. **Per review: confirm it's truly dead** (the flag is a separate dispatch path) before removing — guard against breaking external scripts.
- Stop `_add_vendor_critic_args` (was `:3062-3070`) injecting `--with-prep`/`--with-feedback` into loop/tiebreaker commands with no such phases; fix its stale "five subcommands" docstring.
- Drop "in-process" jargon from `--auto-start` help (was `:3273-3276`).

## Locked decisions
- Each item independent and small; per-area commits so one failure doesn't block others.
- No behavior change to user-facing pipeline *outputs* (prompt text especially — protect with snapshot tests where dedup touches output strings).
- CLI changes verified against the M0 parser snapshot (snapshot updated deliberately for intended flag changes).

## Open questions (for plan to resolve)
- Profile default override: should user/project `default=` overrides be preserved (recommended — they exist today via `load_profile_metadata`), or consciously dropped? Default to preserving them.
- Is `feedback --show` genuinely a no-op alias, or a distinct dispatch path? Verify before removing.

## Constraints
- `directed/full` — real blast radius; not gold-plating but not `light` either.
- Prompt output strings must not drift.

## Done criteria
- No hardcoded model identifiers in `.py` outside `profiles/*.toml`/`_pipeline/defaults.py`; `PLAN_TEMPLATE` has zero `megaplan/` paths.
- One explicit system-default profile mechanism (specified + wired); profile comments match code.
- CLI flags consistent (`--project-dir` everywhere; `tiebreaker-run` has `--work-dir`; no dead `--show`); M0 parser snapshot updated intentionally.
- Prompt-dedup changes proven output-identical by snapshot tests.
- M0 baselines green.

## Touchpoints
`megaplan/prompts/{critique_evaluator,__init__,execute,planning,review_joke,review_doc}.py`, `megaplan/profiles/__init__.py` + `profiles/*.toml`, the post-M5b `cli/` package, `tests/profiles/test_pipeline_profiles.py` (the two `default`-field tests), `tests/`.

## Anti-scope
- Do NOT touch `_core/workflow_data.py:113-119` `_ROBUSTNESS_WORKFLOW_LEVELS` — **verified it is a load-bearing fallback chain** (`"light":("full","light")` = look up light, fall back to full), NOT a redundant echo. The original audit was wrong; leave it.
- Do NOT bundle dead-code/test hygiene (M6b) or re-open M1-M5.
- **Guardrail:** do NOT normalize next-step resolution or merge the drive engines.
