# m4 — Real-browser test tier (Playwright against a live ComfyUI)

## Outcome
A Playwright (Chromium) test tier boots the real ComfyUI server with a mock agent provider and
runs the agent-edit panel's critical scenarios against a real DOM — covering the entire bug
class (layout, scroll, geometry, real-DOM API semantics, rAF behavior) that the jsdom-style
harness cannot see by construction.

## Why (evidence from live testing, 2026-06)
The following shipped bugs ALL had a fully green jsdom suite before and after discovery, and
were only found by hand-driving a real browser:
- `querySelectorAll(function)` TypeError swallowed in the rAF stack (panel froze; round 11)
- thread region flex-shrink clipping ~2,800px of conversation (commit dcb82be)
- sidebar mount growing unbounded so the outer sidebar scrolled the whole panel (d88a7c4)
- requestAnimationFrame frozen in occluded windows (round 8)
- auto-scroll landing on the turn-log instead of the newest message (1ed7163)
Layout/scroll/geometry assertions are only meaningful in a real browser engine.

## Scope (IN)
1. **Mock provider:** a test-only agent route in the server (behind an env flag, e.g.
   VIBECOMFY_AGENT_PROVIDER=fixture) that replays canned responses keyed by prompt — fixtures
   derived from real recorded turn artifacts (the response.json shapes under
   out/editor_sessions, copied into tests/fixtures/, NOT referenced in place). No external LLM
   calls, no API keys, deterministic.
2. **Server lifecycle for tests:** a launcher that boots ComfyUI on an ephemeral port with the
   fixture provider (reuse scripts/run_local_agent_comfy.sh semantics), waits for HTTP 200,
   tears down reliably.
3. **Playwright specs — the scenarios that have actually burned us:**
   - open panel via launcher AND via sidebar tab; panel height == viewport-bounded; thread
     scrolls internally (wheel + programmatic), composer visible without outer scroll;
   - rehydrate a multi-message session → all bubbles render, newest visible, no duplicates
     after close/reopen;
   - submit (fixture turn) → live progress rows appear in-thread then clear; candidate bubble
     + expandable details with Audit affordances;
   - apply (fixture accept) → canvas widget values actually change (read via page JS);
   - scroll contract: scrolled-up position preserved on incoming content; submit jumps to
     newest;
   - overlay geometry probe: edited node has full-box marker and per-row value panels at the
     correct widget rows (assert via the existing debug/canvas instrumentation, NOT pixel
     diffing);
   - console error sweep: zero uncaught errors/page errors across all specs.
4. **Runner integration:** `npm`-free if possible (repo has no package.json today — decide:
   a minimal devDependency-managed package.json under tests/e2e/ is acceptable, locked below);
   a single command documented in the repo (e.g. `node tests/e2e/run.mjs` or
   `npx playwright test`), plus a pytest marker or make-style entry so it slots next to the
   existing suites. Document cadence: pre-merge for panel-touching changes, not every commit.
5. **Docs:** a short section in docs/agent-edit-client-lifecycle.md (or a new
   docs/agent-edit-e2e.md) covering how to run, how fixtures are recorded/refreshed, and what
   belongs in this tier vs the jsdom harness.

## Locked decisions
- Playwright + Chromium only (no cross-browser matrix).
- Fixture provider lives server-side behind an env flag; production code paths must not change
  behavior when the flag is absent.
- Fixtures are committed copies; out/editor_sessions stays untouched and is never read by tests.
- No pixel-diff/screenshot assertions in this milestone (flaky); geometry asserted via DOM/JS
  probes and the existing debug hook.
- e2e dependencies isolated under tests/e2e/ (own package.json there is allowed; root stays
  clean).

## Open questions for the planner
- Whether the vendored/HiddenSwitch ComfyUI used by scripts/run_local_agent_comfy.sh can boot
  headless in CI-like environments without models present (the panel works with the missing-
  models toast up — specs must tolerate it); prep should verify the boot path and the minimal
  env it needs.
- Port allocation/parallelism strategy (single worker is fine; lock it).

## Constraints
- The tier must run on this repo's dev machine (macOS, pyenv 3.11.11) with one documented
  command and no manual steps beyond `playwright install chromium` (documented).
- Total runtime under ~5 minutes.
- Existing suites untouched and green; the e2e tier is additive.
- Never modify out/editor_sessions; never require RUNPOD/DeepSeek/Anthropic keys.

## Done criteria
- One command boots server + runs all specs green on a clean checkout.
- Deliberately re-introducing the flex-shrink clipping bug (locally, as a sanity check in
  review — not committed) fails the scroll spec; this proves the tier catches the class.
- Docs written; fixture-refresh path documented.

## Touchpoints
tests/e2e/* (new), vibecomfy/comfy_nodes/ (fixture provider flag + route),
scripts/ (test server launcher if needed), docs/.

## Anti-scope
- No CI-service configuration (GitHub Actions etc.) — local-runnable tier only; CI wiring is a
  later decision.
- No changes to panel behavior; if a spec exposes a real bug, file it in the review notes
  rather than scope-creeping the fix into this milestone (unless trivially small).
- No cross-browser support, no pixel diffing, no performance benchmarking.
- Do NOT touch ready_templates/, workflow_corpus/, vibecomfy IR/CLI/router.
