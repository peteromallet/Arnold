# M1 — Triage & Safety Net

## Outcome
A trustworthy `pytest` baseline and a de-noised tree, so every later milestone
can refactor behavior-preservingly against a green suite. Plus a verified
duplication inventory that M2 consumes.

## Why this is first
The audit (see `../audit/`) found the test suite is **not currently
trustworthy**: a broken import means part of it never runs, and the public
testing API ships `NotImplementedError` stubs. You cannot safely collapse
validation triads or carve a 3304-line emitter on top of a suite you don't
trust. This milestone establishes the safety net the rest of the epic depends on.

## Scope (do all of these)
1. **Fix the broken test import.** `tests/test_agentic_affordances.py:25` imports
   `plan_eval_node` from `vibecomfy.runtime.eval`; it lives in `eval_plan.py`.
   Fix the import so the module collects and runs. (Verified ImportError.)
2. **Wire the public testing API.** `vibecomfy/testing/__init__.py:76-80` assigns
   `_not_yet_implemented` stubs for `vibecomfy_workflow_factory`,
   `vibecomfy_handle_factory`, `dry_runtime`, `make_workflow_factory`,
   `make_handle_factory` while real impls exist in `vibecomfy/testing/fixtures.py`.
   Re-export the real implementations; remove the stubs. Ensure `_pytest_plugin.py`
   re-exports the full set.
3. **Guard optional-dep tests.** `tests/test_sisypy_integration.py:11` does a bare
   `import sisypy` at module scope — add `pytest.importorskip("sisypy")` (mirror
   `tests/test_fixtures.py:12`'s `importorskip("av")`).
4. **Delete confirmed dead code.** `vibecomfy/source_map.py` (149 LOC, zero imports
   anywhere — verified). `_regen_templates.py` (abandoned one-shot migration, hardcodes
   an author machine path). The `NotImplementedError`-only branch
   `eval.py:103 queue_eval_subgraph` — delete or quarantine with a tracking note
   (do NOT resolve the eval-module question here; that is M4).
5. **Repo hygiene — verify tracked status with `git ls-files` BEFORE removing anything.**
   Untrack only genuine artifacts: `__pycache__/` dirs and `vendor/.DS_Store`.
   **DO NOT touch `template_index.json`** — it is *tracked and repo-owned* (CLAUDE.md:116:
   "the repo-owned `template_index.json` for ready templates"); removing it breaks the
   ready-template discovery contract. `node_index.json` is *not* tracked (verified via
   `git ls-files`), so there is nothing to untrack there. The audit's lens-10 claim that
   these are "committed generated artifacts" is **wrong** for `template_index.json` —
   confirm every file's tracked status against `git ls-files` before acting. Confirm
   `this.env` is gitignored; do NOT commit or print its contents.
6. **Close the parity-fixture gap (the M5 gate).** `vibecomfy/testing/snapshot_registry.py`
   maps **9** ready-template stems, but `tests/parity/fixtures/` contains only ~4 typed
   parity fixtures. Backfill the missing fixtures so all 9 declared stems have a parity
   fixture. This is done in M1 — not M5 — because byte-level parity across the full
   template set is the gate the emitter-split milestone (M5a) relies on; a split gated by
   <half the templates is not behavior-preserving in any meaningful sense.
7. **Produce the duplication inventory artifact.** Write
   `docs/megaplan_chains/pristine_cleanup/artifacts/m1-duplication-inventory.md`
   listing every duplicated helper with file:line and a one-line note on how the
   copies diverge: `_literal_value` (×4), `_call_name` (×3), `_is_link` (×8),
   `_sort_key` (×2), `_git_head` (×2), `UI_ONLY_CLASS_TYPES` (×2), and the duplicated
   `OPAQUE_COMPONENT_CLASS_RE` regexes. This is M2's input-of-record.

## Locked decisions
- This milestone is **non-structural** beyond deletions of dead code. No god-file
  splits, no validation/eval consolidation — those are later milestones.
- The eval-module question (3 modules) is explicitly **deferred to M4**. Here we only
  remove the unconditionally-`NotImplementedError` dead branch if it has zero callers.

## Done criteria
- `pytest` is **fully green — zero failures, zero collection errors, zero known-prior
  reds.** No "catalogued as pre-existing" escape hatch: this milestone exists to make the
  suite trustworthy, so a red suite means M1 is not done. (If a test is genuinely
  un-fixable in M1's scope, it must be `xfail`-marked with a written reason + a tracking
  note, not left red.)
- A **golden-gate artifact** `docs/audits/m1-safety-gate.md` records the concrete,
  re-runnable gate every later milestone must pass: the exact `pytest` invocation,
  CLI JSON-snapshot commands (`workflows list --ready --json`, `port check <sample>
  --json`), the import-surface check, and the 9/9 parity-fixture compile/parity run.
  "Green pytest" alone is explicitly **not** the gate.
- All 9 `snapshot_registry.py` stems have a parity fixture under `tests/parity/fixtures/`.
- `from vibecomfy.testing import *` exposes working fixtures (no `NotImplementedError`).
- `git ls-files` confirms `template_index.json` is **still tracked**; no `__pycache__`/
  `.DS_Store` remain tracked.
- `vibecomfy/source_map.py` and `_regen_templates.py` are gone; `grep` confirms no
  references remain.
- The duplication-inventory artifact exists and is accurate to the current tree.

## Touchpoints
`tests/test_agentic_affordances.py`, `vibecomfy/testing/__init__.py`,
`vibecomfy/testing/_pytest_plugin.py`, `tests/test_sisypy_integration.py`,
`vibecomfy/source_map.py`, `_regen_templates.py`, `vibecomfy/runtime/eval.py`,
`.gitignore`, repo root.

## Anti-scope
Do not touch `emitter.py`, `session.py`, `provider.py`, the validation modules, or
the eval-module trio beyond the single dead-branch deletion. Do not rename public
API. Do not edit docs (that's M6).
