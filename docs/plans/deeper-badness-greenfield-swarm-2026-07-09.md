# Deeper Badness and Greenfield Swarm - 2026-07-09

DeepSeek swarm run:

- Model: `deepseek:deepseek-v4-pro`
- Lanes: 50
- Result: 50 succeeded, 0 failed
- Raw output: `/tmp/vibecomfy-deeper-badness-swarm-results`
- Report index: `/tmp/vibecomfy-deeper-badness-swarm-results/_report.json`

No Desloppify output was used for this synthesis.

## Executive Read

The second swarm changes the priority ordering. The first swarm was right that the core smell is dual authority and canonical/legacy drift. The deeper pass says the highest leverage next step is not a broad refactor. It is rebuilding trust: users and developers need to know that the running code is current, the preview is truthful, the submit loop cannot wedge, and the test gates actually cover the behaviors that keep breaking.

The greenfield work is also clearer: do not jump straight to big visual editors or cloud product until the verification layer exists. The best greenfield bet is a unified evidence/verification layer: visual regression, agentic scenarios, version/info endpoints, and canonical gates. That makes every later feature safer.

## Follow Now

### 1. Make preview correctness observable

Evidence:

- `vibecomfy/comfy_nodes/web/panel_overlay.js`
- `vibecomfy/comfy_nodes/web/comfy_adapter.js`
- `tests/e2e/helpers/canvas-debug-probes.mjs`
- `tests/browser/preview_overlay_ownership_static.test.mjs`
- `tests/e2e/specs/agent_panel_overlay.spec.mjs` was referenced by docs but not present in this checkout.

Findings:

- Preview/overlay rendering remains canvas-only.
- There is no screenshot or draw-call regression test for the overlay.
- Accessibility output was removed with the DOM chip path and not replaced.
- Badge contrast and label readability are still not verified.
- Prior probe drift means tests can claim overlay safety without proving the real canvas path.

Follow:

1. Add a small Canvas2D draw-call recorder test for `drawPreviewOverlay`.
2. Add one Playwright screenshot/pixel test for the real panel preview.
3. Add a minimal ARIA/live text summary of proposed changes that does not revive floating DOM labels.
4. Keep DOM labels out of the visual path, but do not let ownership tests forbid accessibility metadata.

Why now:

This directly targets the visible bug class: floating/clipped preview text and stale preview confidence.

### 2. Add submit watchdog and retry behavior

Evidence:

- `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`
- `vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js`
- `vibecomfy/comfy_nodes/agent/contracts.py`
- `vibecomfy/comfy_nodes/agent/session.py`

Findings:

- `SUBMITTING` can hang if `fetch()` never settles.
- Backend has `retryable` classification, but frontend treats retryable failures like terminal failures.
- Stale-state recovery has rich evidence but is manual-only.

Follow:

1. Add a submit deadline that aborts and transitions out of `SUBMITTING`.
2. Use `retryable` for a bounded retry loop that respects Stop/epoch guards.
3. Auto-rebaseline only after deterministic stale-state evidence; do not auto-resubmit until the UX is proven.

Why now:

Stuck submitting is the most damaging user-trust failure. This is small compared with most structural refactors.

### 3. Expose running-code identity

Evidence:

- `scripts/run_local_agent_comfy.sh`
- `scripts/build_web_cache_bust.sh`
- `vibecomfy/comfy_nodes/__init__.py`
- `vibecomfy/comfy_nodes/agent/routes.py`

Findings:

- Local launch has no PID/status/restart lifecycle.
- Browser cannot see VibeComfy version, git SHA, web bundle hash, uptime, or source directory.
- Cache-bust fallback to `./web` is convenient but silent.

Follow:

1. Add `/vibecomfy/info` with version, git SHA, web source hash/dist hash, Python version, process uptime, and web directory.
2. Surface the info route in the panel developer/status area.
3. Add `make dev-status` or `vibecomfy dev status`.
4. Warn visibly when serving raw `./web` because matching `web_dist` is missing.

Why now:

This would have shortened the stale-preview debugging loop immediately.

### 4. Fix agent-edit settings contract gaps

Evidence:

- `vibecomfy/comfy_nodes/agent/edit_chat.py`
- `vibecomfy/comfy_nodes/agent/provider.py`
- `vibecomfy/porting/edit/ops.py`
- `vibecomfy/porting/widgets/compact_resolver.py`
- `vibecomfy/comfy_nodes/agent/edit_response_contract.py`

Findings:

- Widget name resolution is asymmetric across prompt/object-info paths.
- The agent can be asked for settings edits in terms the engine cannot land.
- Batch REPL prompt/contracts are over-specified but still not a single executable contract.

Follow:

1. Make the prompt show exactly the widget names/slots accepted by the engine.
2. Add an executable “randomize sampler settings” scenario using actual rejection diagnostics.
3. Make the random/settings edit path fail with valid choices, not a generic pending/submit failure.

Why now:

This targets the user’s reported failure mode directly.

### 5. Gate browser and visual tests for real

Evidence:

- `tests/test_comfy_nodes_browser.py`
- `tests/browser/*.test.mjs`
- `tests/e2e/*`
- `Makefile`

Findings:

- Many Node browser tests are not wired through the Python/Make gate.
- Static ownership tests are useful as lint, but they cannot prove runtime behavior.
- The overlay and panel need at least one real browser verification path.

Follow:

1. Add a `make browser-contracts` target for critical Node tests.
2. Add a `make e2e-preview` or equivalent minimal Playwright target.
3. Keep static ownership tests, but stop treating them as behavioral proof.

Why now:

Without this, every frontend “fix” can be another stale-path fix.

### 6. Fix immediate safety issues around executable templates and env/secrets

Evidence:

- `vibecomfy/registry/ready.py`
- `vibecomfy/security/gate.py`
- `vibecomfy/comfy_nodes/agent/runtime_code.py`
- `vibecomfy/comfy_nodes/agent/audit.py`
- local env/script files

Findings:

- Dynamic ready templates can be auto-promoted and executed based on path provenance without the same AST policy used for agent-generated code.
- Unrestricted runtime code inherits the parent environment.
- Redaction is closed-set and misses common secret names.
- Some local scripts/files contain or reference hardcoded secrets/keys. Do not preserve those patterns.

Follow:

1. Apply content scanning or explicit confirmation to dynamic ready templates.
2. Sanitize environment inherited by unrestricted subprocesses.
3. Expand redaction with secret-pattern detection.
4. Audit local secret-bearing files before any publish/release work.

Why now:

These are small relative to their blast radius.

### 7. Fix the highest-yield executor regressions before large architecture work

Evidence:

- `vibecomfy/executor/research.py`
- `vibecomfy/porting/emit/ui.py`
- `vibecomfy/comfy_nodes/agent/edit_orchestration.py`
- `vibecomfy/comfy_nodes/agent/gates.py`

Findings from the adversarial priority lane:

- Source-level media-domain gating over-rejects valid cross-domain adapter precedents.
- Widget-shape fence can reject an entire emit because an unedited collateral node is schema-less or overflowing.
- Batch-REPL queue validation state can be computed but not reflected in the gate snapshot that assessors read.

Follow:

1. Mirror the slice-level cross-media adapter exception at the source-level precedent gate.
2. Scope widget-shape refusal to edited/touched nodes; pin opaque collateral where safe.
3. Ensure batch-REPL queue validation writes to the canonical serialized gate snapshot.

Why now:

These look like high-impact, low-to-medium-risk fixes. They are more user-visible than many generic architecture smells.

## Follow Soon

### 8. Diff-over-original fidelity architecture

Evidence:

- `docs/local_agent_text_to_graph_blockers.md`
- `vibecomfy/porting/emitter.py`
- `vibecomfy/porting/convert.py`
- `vibecomfy/comfy_nodes/agent/session.py`

The strongest medium-term architecture bet is preserving the original UI JSON and applying minimal structured diffs, rather than regenerating the whole graph from canonicalized IR. This directly attacks unknown custom-node loss, widget truncation, subgraph definition loss, and passthrough drift.

Follow after the above gates exist.

### 9. Enforcement/CI gate layer

Evidence:

- `Makefile`
- `.github/workflows/*`
- `template_index.json`
- `node_index.json`
- generated JS contract files

Build one “truthfulness” gate layer: manifest-to-disk, generated-contract freshness, template-to-model-assets, router-to-template coverage, browser contracts, and visual preview smoke.

Follow soon because it makes every later refactor cheaper.

### 10. Workflow version graph and semantic diff model

Evidence:

- `vibecomfy/comfy_nodes/agent/session.py`
- `vibecomfy/porting/edit/_diff.py`
- `vibecomfy/porting/layout/delta.py`
- `vibecomfy/comfy_nodes/agent/edit_humanize.py`

The current system has session baselines and turn artifacts, but not a general workflow history/version primitive. A content-addressed workflow version graph would support rollback, review, diff visualization, and collaboration.

Follow after diff-over-original work begins. Do not build this as a standalone product first.

## Defer Or Ignore

### Defer broad module splitting

The `SOURCE` module assembly, large `routes.py`, `session.py`, and reorganise modules are real debts. But splitting them before trust gates exist risks churn without improving the user-visible failures. Start with tests/gates and the smallest boundary fixes.

### Defer visual layout editor

The reorganise feature wants undo, previewability, and user agency. A full visual layout editor is attractive, but it should wait behind workflow versioning and visual regression.

### Defer cloud product

`vibecomfy cloud` / managed GPU execution has product potential, but local reliability, version identity, test truthfulness, and security posture are prerequisites. Fix those first.

### Ignore pure “file is huge” arguments

Several huge files are coherent enough to leave alone until a concrete bug or boundary extraction demands action. Size is not the decision criterion; authority and testability are.

### Treat research/Hivemind concerns as policy work, not emergency refactor

There are privacy/control questions around retrieval and hardcoded external-service configuration. Add opt-out and policy clarity, but do not rewrite retrieval before the agent-edit trust loop is stable.

## Greenfield Bets Worth Considering

### Bet A: VibeComfy Evidence Layer

Unify visual regression, browser contracts, agentic scenarios, and version/info endpoints into one concept: every user-visible claim should have evidence. This is the highest leverage greenfield bet because it supports every other feature.

Cost: 1-2 weeks for a useful first version.

### Bet B: Diff-Over-Original Editing Core

Preserve original ComfyUI JSON and apply minimal patches. This is the best architectural bet once the evidence layer exists.

Cost: 2-3 weeks.

### Bet C: Agentic Scenario Activation

Activate the staged multi-modal/live-agentic scenarios in waves and use them as regression gates for real tasks: preview edits, random settings, accept/reject, custom nodes, requires-custom-nodes, stale-state recovery.

Cost: 2-4 weeks, depending on GPU/API spend and triage load.

### Bet D: Headless Executor Service

Expose the executor as CLI/HTTP independent of the ComfyUI panel. This opens CI/batch/API use cases, but it should come after the response contracts and security policy are tighter.

Cost: 2-3 weeks.

### Bet E: Workflow Version Graph

Build content-addressed workflow revisions with semantic diffs, rollback, and lineage. This should grow naturally out of diff-over-original rather than as a separate greenfield island.

Cost: 2-4 weeks.

## Suggested Next Sprint

1. Add `/vibecomfy/info` and panel-visible version/hash/status.
2. Add submit timeout/abort recovery.
3. Add overlay draw-call or screenshot regression for current preview bug.
4. Fix settings/widget prompt-contract path for “random sampler settings.”
5. Wire critical browser tests into `make`.
6. Patch executable-template and unrestricted-env security issues.
7. Patch the three adversarial executor regressions if the current eval still reproduces them.

This ordering is intentionally pragmatic: it improves current debugging, current user trust, and future refactor safety before taking on the larger architecture bets.

## Raw Lane Index

Raw outputs are in `/tmp/vibecomfy-deeper-badness-swarm-results`.

Key lanes:

- `01_product_agent_edit_ux.txt`
- `02_preview_text_visual_quality.txt`
- `03_agent_prompt_contract_quality.txt`
- `08_agent_error_recovery.txt`
- `11_security_generated_code.txt`
- `12_operability_comfy_launch.txt`
- `14_ci_makefile_truthfulness.txt`
- `15_test_pyramid_strategy.txt`
- `17_playwright_visual_regression.txt`
- `40_agentic_testing_scenarios.txt`
- `41_multimodal_visual_agent.txt`
- `42_workflow_diff_visualization.txt`
- `43_workflow_version_control.txt`
- `49_priority_adversary.txt`
- `50_greenfield_strategy_synthesis.txt`
