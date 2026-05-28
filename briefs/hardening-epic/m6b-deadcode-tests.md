# M6b — Dead code & test hygiene

**Rubric:** `directed/light` (genuinely low-risk)
**Position in epic:** milestone 12 of 12. Depends on M6a. The cheapest, lowest-blast-radius cleanup — runs last on a fully-cleaned tree.

## Outcome
Remove dead/demo code and the remaining re-export shim, and apply the two highest-value test-hygiene fixes, without changing any behavior.

## Scope (IN)
### Dead code / demos
- Unregister the demo pipelines (`_pipeline/demos/doc_critique.py`, `_pipeline/demo_judges.py`) from the production registry (`_pipeline/registry.py:420-442`) or clearly mark them non-production so they're not user-facing `megaplan run` targets.
- **Collapse the `audits/verifiability.py` re-export shim — but it has 4 callers, not 1 (corrected per review).** Import sites: `handlers/verifiability.py:32` and `:290`, `handlers/execute.py:224`, `handlers/plan.py:146`, `audits/__init__.py:24`. Repoint **all** of them to the canonical `orchestration.verifiability` (or keep the shim with a documented deprecation) — collapsing into one caller while three others still import it breaks the build.
- Inline or rename the 16-line `_pipeline/defaults.py` (2 constants, misleading "discovery" docstring). **Note:** it stays an allowed home for model-identifier constants per M6a's rule.
- **(Added per gap-hunt)** Remove the dead no-op hook `attach_handler_steps()` (`_pipeline/stages/handler_step.py:56-58`, "reserved for Sprint-3", grep-confirmed zero callers).
- **(Added per gap-hunt)** The demo-only prompt renderers `_critique_default`/`_critique_doc`/`_critique_joke`/`_revise_default` registered into the production `PromptRegistry` at import (`_pipeline/prompts.py:125-167`) — same demo-in-production issue as the demo pipelines; unregister or gate them.

### Test hygiene
- Split `tests/test_workers.py` (5,323 lines / 179 flat functions, no classes) into per-concern modules.
- Replace the duplicated `_bootstrap` / `_make_args` helpers across the test files with the existing `conftest.py` `make_args_factory` / `plan_fixture`. **Per review: the 9 copies have incompatible signatures** (`tuple[Path,Path]` / `None` / different construction) — this is 9 separate migrations, not one pattern; adapt per-file.

## Locked decisions
- Each item independent; per-area commits.
- No behavior change. Demo unregistration must not break the demo tests (`tests/test_pipeline_demo_judges.py` etc.) — adjust those to call the demos directly rather than via the production registry if needed.
- `light` robustness is justified here: dead shims + test reorganization, no production-output surface.

## Open questions (for plan to resolve)
- Demos: unregister entirely, or move behind an explicit `--demo`/internal flag? (pick based on whether anything legitimately uses them)
- `audits/verifiability.py`: full collapse to all 4 callers, or keep shim + deprecation note?

## Constraints
- `light` — do not gold-plate; the two named test fixes only, no broader coverage work.
- Splitting `test_workers.py` must not silently drop a test. **HARD GATE (Codex sense-check — `directed/light` review alone is too thin to catch a dropped parametrized case):** capture `pytest tests/test_workers.py --collect-only -q | wc -l` before the split and assert the post-split collected count across the new modules is **exactly equal**. This is a mechanical check independent of review depth.

## Done criteria
- Demo pipelines not exposed as production `megaplan run` targets; demo tests still pass.
- `audits/verifiability.py` resolved across all 4 callers (collapsed or deprecation-documented); build green.
- `test_workers.py` split into per-concern modules with **identical `pytest --collect-only` count** before/after (the hard gate); duplicated bootstraps replaced with conftest factories.
- M0 baselines green.

## Touchpoints
`megaplan/_pipeline/{registry,defaults,prompts}.py` + `_pipeline/demos/` + `stages/handler_step.py`, `megaplan/audits/verifiability.py` + the 4 callers, `tests/test_workers.py`, `tests/conftest.py`, `tests/test_pipeline_demo_judges.py`.

## Anti-scope
- Do NOT chase test coverage gaps beyond the two named hygiene fixes — this is cleanup, not a test-writing sprint.
- Do NOT bundle the deferred two-drive-engine unification (`auto.py` vs `loop/engine.py`, the double next-step resolution) — separate future epic.
- Do NOT re-open M1-M6a.
