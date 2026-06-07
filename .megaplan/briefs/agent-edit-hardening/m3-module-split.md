# m3 — Split the panel god-file; consolidate module-global state into the singleton

## Outcome
`vibecomfy_roundtrip.js` (~9,500 lines, 288 functions) is decomposed along its existing seams
into focused modules, and all module-level mutable state (14 globals: scheduler bookkeeping,
flush counters, render instrumentation, commit timestamps) moves into the page-level panel
singleton so a second module evaluation can never split runtime state again. Behavior-preserving,
backstopped by the full characterization suites.

## Why (evidence from live testing, 2026-06)
- Module re-evaluation created duplicate panel objects in production (fix round 9, c142c8e);
  the PANEL is now a page-level singleton but scheduler/instrumentation state is still
  per-module-copy — the same failure mode is one loader quirk away.
- The file mixes five independent concerns (render scheduling, thread/bubble rendering, canvas
  overlay drawing, composer/settings, network handling); 23 live fix rounds repeatedly found
  cross-concern coupling (e.g. renderHistory scrolling before renderActivityRows appended).

## Scope (IN)
1. **Module map (locked seams, adjust names to repo conventions):**
   - `panel_runtime.js` — the page-level singleton accessor + ALL runtime state (current panel,
     scheduler queue/flags, flush counters, render instrumentation, commit timestamps) under a
     single `runtime` namespace keyed on the existing window singleton; idempotent under
     re-evaluation.
   - `panel_scheduler.js` — markDirty / raced rAF-vs-timeout flush / per-section exception
     isolation + re-queue.
   - `panel_thread.js` — bubbles, reconcile (DOM-as-truth), details, scroll follow logic,
     activity rows.
   - `panel_overlay.js` — all canvas overlay drawing (full-box markers, row value panels,
     ghost nodes, link previews).
   - `panel_composer.js` — composer, buttons, settings popover, notices.
   - The boundary module from m1 (network normalization) stays its own file.
   - `vibecomfy_roundtrip.js` remains the entry point: extension registration, panel shell
     construction, wiring the modules together.
2. **State consolidation:** every `let _x` module global moves into the runtime namespace;
   `window.__vibecomfyPanelDebug()` reads from it (hook output shape unchanged — tests and the
   debugging playbook in docs depend on it).
3. **Generalize DOM-as-truth self-heal:** the thread reconcile self-heals; audit the remaining
   signature caches (batch rows, bubble detail signatures, developer/settings sections) and give
   each the same validate-against-DOM-at-render-start treatment or document why it cannot diverge.
4. **Loading:** follow the existing multi-file pattern already used by vibecomfy_roundtrip.js +
   agent_edit_lifecycle.js + comfy_adapter.js (these already coexist — reuse exactly that
   mechanism). NO bundler, NO build step.

## Locked decisions
- Behavior-preserving: zero intentional behavior change. The suites are the gate.
- The debug hook's output shape is frozen (downstream debugging docs depend on it).
- File seams as listed; the planner may merge scheduler into runtime if circularity forces it,
  but thread/overlay/composer must be separate files.
- No bundler; no TypeScript; plain JS matching current style.

## Open questions for the planner
- Import/symbol-sharing mechanics between the new files given ComfyUI's web-extension loader —
  inspect how agent_edit_lifecycle.js is consumed today and replicate.
- Order-of-load constraints (runtime/singleton must initialize first) — make each module
  tolerant of any load order or document the required order in the entry file.

## Constraints
- Characterization gate: node --test tests/browser/roundtrip_smoke.test.mjs AND
  tests/browser/agent_edit_lifecycle.test.mjs AND pytest tests/test_comfy_nodes_agent_*.py all
  green with NO test logic changes beyond import/path mechanics (test edits that alter assertions
  are a red flag for behavior drift — justify each one explicitly in the task notes).
- Region-id parity between mounts must keep passing (existing test).
- A new test: evaluate the module entry twice in the harness → scheduler/instrumentation state
  does not split (extends the existing panelsCreated===1 test to runtime state).
- Keep the file count modest (≤7 new files); don't shatter into micro-modules.

## Done criteria
- vibecomfy_roundtrip.js under ~2,500 lines; no module-level mutable state anywhere
  (grep-verifiable: `^let _|^var _` in the web/ panel files returns nothing outside the runtime
  namespace definition).
- Double-evaluation test green; full suites green; live smoke (panel open, submit, apply on
  :8199 per docs/agent-edit-client-lifecycle.md debugging section) behaves identically.

## Touchpoints
vibecomfy/comfy_nodes/web/* (new files + slimmed vibecomfy_roundtrip.js), tests/browser/*
(import mechanics only), docs/agent-edit-client-lifecycle.md (module map section).

## Anti-scope
- NO behavior changes, message changes, or styling changes.
- Do NOT refactor agent_edit.py (server) — frontend decomposition only.
- Do NOT touch ready_templates/, workflow_corpus/, vibecomfy IR/CLI/router.
- Do NOT introduce a build system, package.json changes, or new dependencies.
- Do NOT modify out/editor_sessions evidence directories.
