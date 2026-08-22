Reading additional input from stdin...
2026-08-21T20:39:45.825634Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-21T20:39:45.825685Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-21T20:39:45.825692Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.148.0
--------
workdir: /Users/peteromalley/Documents/arnold-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: high
reasoning summaries: none
session id: 01a0260d-1008-7591-8a76-c0f9158955ce
--------
user
# Batch 1 oracle check-in — GPT-5.6 Sol (oracle)

> DELEGATION MANDATE — You are a manager and validator of the normal execution pool, NOT a worker. Delegate as much as possible to the task's selected normal model: GPT-5.6 Luna. Your job is to direct, then validate: read delegated output against the acceptance criteria; do work yourself only when delegation is impossible.

Worktree: `/Users/peteromalley/Documents/arnold-oracle`. Read `.oracle/northstar.md`, `.oracle/agent_goal.md`, `.oracle/tasklist.md`, `.oracle/checkins/batch-1-review.txt` (Luna review: PASS, no findings), and the delta `git diff 796961cd9c..9224f52ce2`.

Batch 1 = T1 (preserve/prove arnold agent, Luna) + T3 ([XHARD] raw prompt parity, Sol-executed). Independent review passed with zero findings; host verified CMP byte-identity, agent list/run probes, 29-pass/6-pre-existing-env-fail tests.

Judge: is Batch 1 PASS? Consider the frozen acceptance, the review, the known 6-failure attestation env gap (pre-existing, T8-scoped), and North Star anti-patterns (raw parity respected; no normalization, no renames, no omp changes, no alternate runtime). Verdict: single line `PASS` or `ISSUES` + one-line rationale. Under 120 words.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m delegating the evidence check to GPT-5.6 Luna as required, then I’ll independently validate its conclusion against the frozen acceptance and requested diff.
2026-08-21T20:39:55.161532Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-21T20:39:55.161555Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-21T20:39:55.161560Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc "sed -n '1,240p' .oracle/northstar.md && sed -n '1,240p' .oracle/agent_goal.md && sed -n '1,280p' .oracle/tasklist.md && sed -n '1,240p' .oracle/checkins/batch-1-review.txt && git diff --stat 796961cd9c..9224f52ce2 && git diff --find-renames --find-copies 796961cd9c..9224f52ce2" in /Users/peteromalley/Documents/arnold-oracle
 succeeded in 0ms:
# North Star — Arnold custom-agent platform

## Desirable end state
Anyone can run a **named, branded agent** ("arnold", then "astrid", then any repo's bot) that carries the current Discord resident prompt as its system prompt, tweak it with basic customisations (name, description, prompt, model, tools), and create a **new custom bot in another repo** from the same approach — without touching omp internals, without renaming compatibility surfaces, and without re-architecting the resident runtime.

Concretely: `agent run arnold` speaks the agentbox-operator-v1 persona; `agentbox install-omp-agent <name> --name/--description` ships a customised agent; `agentbox new-resident <name> --repo <path>` scaffolds a working Discord bot in a fresh repo (agent file + resident profile + env + launcher + systemd unit), backed by the existing resident platform.

## Enduring qualities / invariants
- **One runtime, one seam.** omp is the only model runtime; named agents are markdown files; the agent file is the entire identity surface. No second dispatch path.
- **Elegance over machinery.** The smallest surface that covers the need: markdown is the declarative config; CLI flags only for the two things users actually change (name, description). No flag duplication of file-editable fields.
- **Compatibility is a contract.** Never rename `arnold.megaplan.*`, `arnold-resident-*`, `ARNOLD_RESIDENT_DELEGATION_CONTEXT`, `arnold:resident-delivery:`; never rename omp's `@oh-my-pi/*`, binary, `APP_NAME`, `.omp`. Existing stores and cloud runs keep working.
- **Fork-clean omp.** Zero changes to omp source; everything ships via `.omp/` config, agent files, and the Arnold repo.
- **User-owned.** The human can run, customise, and extend without reading harness internals; every generated bot is understandable from its five scaffold files.

## Anti-patterns / hollow success
- Re-architecting the resident runtime to "make it general" — the platform exists; add seams, not engines.
- A generator that generates more than it documents — the scaffold must be readable and hand-editable, not a magic tree.
- Flag soup on the installer (--model/--tools/--prompt-file) duplicating markdown — precedence and quoting hell.
- Renaming compatibility surfaces for cosmetics (schema ids, env names, package names).
- Any mutation of `main` from this run; any silent scope widening (purge, unrelated refactors).
- Touching the Discord tool catalog semantics via agent-file `tools` — Discord actions come from the resident profile's tool registry; the agent file governs omp named-agent runs only.
- Working on a different prompt than the one the Discord resident actually runs — byte-parity with `AgentBoxOperatorProfile.system_prompt()` is the invariant.

## What aligned progress feels like
Each batch leaves the worktree green and the run closer to a working second-repo bot: installer customisation proven, external profile loading proven, one generated repo passing named-agent execution and a Discord dry-run, then one live round trip. Small commits, oracle-gated checkpoints, no dead ends.
# Agent goal — megado run: custom-agent implementation (R1–R3)

Frozen operational contract for this run. Links [North Star](./northstar.md).
This run advances the North Star by turning the branded `arnold` agent into a
**runnable, customisable, cross-repo-reproducible** platform deliverable.

## Objective
Implement and prove, end to end, the custom-agent capability on the Arnold repo
(in a worktree, never on `main`):

- **R1 — runnable**: `arnold` runs as an omp named agent whose system prompt is
  the current Discord resident prompt (`agentbox-operator-v1`, byte-identical
  to `AgentBoxOperatorProfile.system_prompt()`). Foundation committed
  (`agentbox/agents/arnold.md` + `agentbox install-omp-agent arnold` + tests).
  Deliverable: verified invocation (`agent run arnold`), docs.
- **R2 — basic customisations**: `agentbox install-omp-agent` gains
  `--name` / `--description` (output name + frontmatter); users customise
  prompt/model/thinking/tools by editing the markdown file; canonical persona
  changes follow the 3-step discipline (agent file + `resident_profile.py` +
  version bump) with a byte-parity test.
- **R3 — generalisable**: `agentbox new-resident <name> --repo <path>` scaffolds
  a custom Discord bot in another repo: project `.omp/agents/<name>.md`,
  `.agentbox/resident_profile.py` (subclass of `AgentBoxOperatorProfile`),
  `.agentbox/resident.env.example`, `.agentbox/run-resident` launcher,
  `.agentbox/<name>-resident.service`. Resident profile loading becomes
  extensible (`resident/config.py` profile string; `resident/cli.py` loads
  repo-relative `path.py:Class`). Zero omp fork changes.

## Authoritative inputs
- Source ref: `744a417198` (see `.oracle/custody.md`); foundation commit `b7c682798e`.
- Prior planning artifacts (facts + Codex R1–R3 plan): `/tmp/arnold-custom-agent/plan2-out.txt`,
  `/tmp/arnold-custom-agent/results/*.txt` (research reports), `.oracle/custody.md` facts.

## In-scope
- `agentbox/cli.py` (installer flags, `new-resident`), `agentbox/agents/`,
  `agentbox/templates/resident/*`, `pyproject.toml` artifacts,
  `arnold_pipelines/megaplan/resident/config.py` + `cli.py` (extensible profile
  loading), docs (`docs/custom-resident-agents.md`), tests for all of the above.

## Non-goals / out of scope (do NOT do)
- The hermes→omp label purge — it is in flight in the main tree (separate job);
  this worktree predates it. Do not re-implement or conflict with it; treat the
  resident as omp-based and build on the current tree's reality.
- Renaming compat surfaces: `arnold.megaplan.*`, `arnold-resident-*`,
  `ARNOLD_RESIDENT_DELEGATION_CONTEXT`, `arnold:resident-delivery:` UUID ns.
- Renaming omp identities (`@oh-my-pi/*`, `omp` binary, `APP_NAME`, `.omp`).
- Any mutation of `main` or other worktrees; no pushes except the oracle-run branch at the end.
- Discord developer-portal setup (external, manual, documented only).
- Megaplan phase machinery, the Discord transport internals (`discord.py`), or
  the tool catalog — unless a generated profile demonstrably requires a seam.

## Authorization boundaries
- Mutate: this worktree (`/Users/peteromalley/Documents/arnold-oracle`) only.
- Commit: per-batch commits on `oracle-run`; `.oracle/` artifacts may be committed.
- Sync: at completion, push `oracle-run` to `origin` (`HEAD:oracle-run`). NEVER main.
- Open: `open` the worktree at completion.
- Escalate to user: any change to the frozen goal, North Star, model policy,
  or any discovered need to touch `main` or rename compat surfaces.

## Model policy (user-declared; no automatic routing)
- **Normal tasks (explore, execute, review passes): GPT-5.6 Luna** (`codex:gpt-5.6-luna`).
- **[XHARD] tasks: GPT-5.6 Sol** (`codex:gpt-5.6-sol`, high reasoning).
- **Planner / Oracle / sense checker: GPT-5.6 Sol** (`gpt-5.6-sol`, high reasoning).
- Switching any class requires user approval; record every receipt with model + rationale.

## Done criteria (all must pass)
1. `agent run arnold` (via `~/.bun/bin/agent`) returns behavior governed by the
   agentbox-operator-v1 prompt; body byte-parity test green.
2. `agentbox install-omp-agent <template> --name <n> --description "<d>" --target <dir>`
   produces a renamed, re-described agent file; tests green.
3. `agentbox new-resident <name> --repo <path>` scaffolds the five files; the
   generated profile imports and passes a dry-run (`run-resident --dry-run`
   or equivalent no-network validation); external profile loading works with
   validation + clear rejection of bad profiles.
4. Tests: `pytest tests/agentbox/test_cli.py tests/agentbox/test_resident_profile.py`
   green; full targeted suite (affected areas) green.
5. Evidence matrix maps every criterion above to a receipt/evidence path.
6. Final oracle review (Sol) passes; North Star alignment confirmed; anti-patterns avoided.

## Validation commands
- `python -m pytest tests/agentbox/test_cli.py tests/agentbox/test_resident_profile.py -q`
- `python -c "import agentbox.cli"`
- `~/.bun/bin/agent list` (shows arnold) and one `~/.bun/bin/agent run arnold "…"` probe
- `agentbox new-resident demo --repo /tmp/demo-resident` + `python -c "import …"` on the generated profile
- No live Discord call required for this run; dry-run/structural validation only.

## Sync/promotion policy
- End of run: final verification → final oracle review → commit → push `oracle-run`
  to `origin` → `open` worktree → report phase-by-phase evidence.
- Merging `oracle-run` into `main` is a separate, user-authorized action; not performed here.
# Tasklist — megado run (FROZEN 2026-08-21)` + model-policy line (normal = `codex:gpt-5.6-luna`, [XHARD] = `codex:gpt-5.6-sol`, oracle = Sol; user-declared, no auto-routing) + a "Run-wide operational contract" block (per-batch commit on `oracle-run`; allowed `.oracle` commits; never `main`; final push `HEAD:oracle-run` + `open` gated on the final oracle review).
   - Batches 1–7 with: T1–T11 from the plan (unchanged acceptances), T12 `[XHARD]` "final oracle review gates commit/push", T13 `normal` "sync: push HEAD:oracle-run, open worktree" — plus Batch 3 split into checkpoints (T4 checkpoint, then T5), and Batch 5's discriminator gate as its first task (T8a "freeze standalone/cloud authority discriminator + state-dir convention; escalate if primitives can't express fail-closed" before T8b).
   - Each checkpoint line MUST end with exact commands (e.g. `python -m pytest tests/agentbox/test_cli.py tests/agentbox/test_resident_profile.py -q`, `~/.bun/bin/agent list`, `~/.bun/bin/agent run arnold "State your name and rules."`, `python -c "import agentbox.cli"`, `agentbox new-resident demo --repo /tmp/demo-r && python -c "import importlib; importlib.import_module('resident_profile')"`-style generation/import probes, evidence-matrix receipt check).
   - Model line per task: `[normal → codex:gpt-5.6-luna]` or `[XHARD → codex:gpt-5.6-sol]` with a short rationale.

Under 1300 words. Your output is saved verbatim as the frozen tasklist — it must be complete and self-contained.
codex
I’m reading the five Oracle artifacts now, then I’ll reconcile every review finding into a self-contained frozen tasklist.
exec
/bin/zsh -lc "sed -n '1,240p' .oracle/checkins/pre-execution-review.txt && sed -n '1,320p' .oracle/tasklist.md && sed -n '1,240p' .oracle/agent_goal.md && sed -n '1,240p' .oracle/northstar.md && sed -n '1,360p' .oracle/plan.md" in /Users/peteromalley/Documents/arnold-oracle
 succeeded in 0ms:
CONTRACT ISSUES

1. **Blocking — final oracle review is not operationally covered.** `.oracle/agent_goal.md §Done criteria 6`; `.oracle/tasklist.md Batch 7`. The tasklist mentions a generic North Star/anti-pattern review, but no explicit final Sol oracle review or model receipt. **Suggested fix:** add a post-verification `[XHARD]` Sol oracle task that gates commit and push.

2. **Blocking — authorization and sync steps are absent.** `.oracle/agent_goal.md §§Authorization boundaries, Sync/promotion policy`; `.oracle/tasklist.md`. No task/checkpoint requires per-batch commits, committing allowed `.oracle/` artifacts, final `HEAD:oracle-run` push, opening the worktree, or explicitly never mutating `main`. **Suggested fix:** add an operational final batch plus per-batch commit checkpoints encoding these exact constraints.

3. **Blocking — seam dependency is not guaranteed.** `.oracle/tasklist.md Batch 3`. T4 (configuration seam) and T5 (external loader) share a batch; batching does not establish that T4 completes before T5. **Suggested fix:** split T4 into a completed checkpoint before T5, or declare and enforce an intra-batch dependency.

4. **Blocking — custody discriminator remains unresolved before implementation.** `.oracle/plan.md §Residual open questions`; `.oracle/tasklist.md Batch 5`. The exact standalone/cloud authority discriminator is explicitly still open, yet T8 proceeds directly to implementation. **Suggested fix:** insert a Sol/oracle gate to freeze the discriminator and state-directory convention; halt and escalate if existing primitives cannot support it fail-closed.

5. **Advisory — checkpoints are assertions, not verifiable one-liners.** `.oracle/tasklist.md Batches 1–7`; `.oracle/agent_goal.md §Validation commands`. Several checkpoints omit exact commands, notably `python -c "import agentbox.cli"`, clean `new-resident` generation/import, and evidence-matrix receipt validation. **Suggested fix:** attach concrete one-line commands or named scripts to every checkpoint.

The remaining classifications are sensible. Non-goals and North Star direction are otherwise respected: one omp runtime, markdown identity, contained profile seam, readable five-file scaffold, no omp edits, compatibility renames, tool-catalog changes, purge work, or attestation bypass.
0
## Batch 1 — Preserve R1 and repair exact prompt parity
- Checkpoint: Raw and omp-parsed prompt parity tests pass; installed `arnold` appears in `agent list` and `agent run arnold` succeeds through the existing dispatcher. This must pass before scaffold generation.
- Advances: R1, R2; preserves one runtime/one identity seam and byte-parity with the live Discord prompt; avoids alternate dispatch, prompt normalization, and compatibility renames.
- Tasks:
  - normal T1: Preserve and prove the packaged `arnold` named agent and existing omp dispatch path — installed package exposes `arnold`; list/run probes succeed from repo root; no alternate runtime is added. Classification: bounded preservation and verification.
  - [XHARD] T3: Repair and enforce exact prompt parity using omp’s CRLF, delimiter, and trim semantics — raw body is exactly `system_prompt().encode() + b"\n"`, parsed body matches byte-for-byte, and semantic changes require both surfaces plus a version bump. Classification: parser-edge and identity-integrity sensitivity.

## Batch 2 — Constrain installer customization
- Checkpoint: Installer tests prove safe rename/re-description, unchanged prompt bytes, atomic non-overwriting writes, and clean rejection of unsafe names and unknown templates.
- Advances: R2; preserves markdown as the identity surface and elegance over machinery; avoids flag soup and hidden prompt mutation.
- Tasks:
  - normal T2: Add only `--name` and `--description` overrides to packaged-template installation — validate the restricted name grammar excluding `.`/`..`; update filename/frontmatter only; fail atomically on collisions or invalid input. Classification: bounded CLI/resource work with explicit rules.

## Batch 3 — Open one contained profile seam
- Checkpoint: Built-in and external profile-loading tests pass, including identical CLI/environment behavior, resolved-root containment, precise failures, deterministic reloads, and concurrent cross-repo isolation. This must pass before dry-run or generator integration.
- Advances: R3; preserves one minimal seam and fork-clean omp; avoids runtime re-architecture and treating trusted imports as sandboxed.
- Tasks:
  - normal T4: Make `ResidentConfig.profile` a validated non-empty string, remove argparse choices, preserve built-ins/defaults, pass the resolved root, and reject unknown simple names with concise `CliError` output. Classification: localized configuration seam.
  - [XHARD] T5: Load trusted repo-relative `path.py:Class` profiles with strict containment, hashed module identity, locked module mutation, and failure eviction — generated profiles construct; escapes, malformed targets, bad classes/constructors, stale modules, and concurrency hazards fail specifically. Classification: security-sensitive path resolution and global import-state concurrency.

## Batch 4 — Validate profiles and inherited runtime behavior
- Checkpoint: Network-free dry-run instantiates the selected profile and exposes import/constructor defects; fake-backend tests prove inherited `cloud_resume`; tool registries remain per-instance and unchanged. This must pass before generated launchers are wired.
- Advances: R3; preserves the existing resident runtime and Discord tool catalog; avoids hollow dry-run success and agent-file tool leakage.
- Tasks:
  - normal T6: Make dry-run construct dependencies and instantiate the selected profile while skipping tokens, attestation, runner/service construction, and network activity — profile defects surface without side effects. Classification: bounded lifecycle adjustment.
  - [XHARD] T7: Inject/default a compatible `CloudCliBackend` for inherited `cloud_resume` while retaining store/config/authorization injection and isolated tool registries — fake-backend and subclass tests pass without catalog changes. Classification: cross-cutting inherited-contract risk.

## Batch 5 — Establish standalone custody honestly
- Checkpoint: Standalone attestation passes only for the exact resolved root and live expected HEAD, produces validated seed/process receipts, and fails closed for tampering, staleness, or custody mismatch; chain provisioning remains behaviorally unchanged. This must pass before launcher wiring.
- Advances: R3; preserves compatibility as a contract and fail-closed custody; avoids counterfeit cloud evidence, downgrade paths, waivers, and parallel attestation machinery.
- Tasks:
  - [XHARD] T8: Add one domain-separated `resident attest` adapter using canonical vectors, validation, atomic content-addressed storage, and root-custodied state — valid standalone evidence satisfies runtime launch validation; wrong root/HEAD, altered evidence, stale seeds, and cloud/standalone mismatches fail closed. Classification: authority-boundary and custody-critical work.

## Batch 6 — Generate and wire the five-file resident
- Checkpoint: Generation transaction tests create exactly five readable artifacts with executable launcher and clean rollback; mocked startup attests exact HEAD, constructs the external profile, creates process attestation, and reaches service startup without network.
- Advances: R3; preserves user ownership, readable scaffolds, exact-root operation, and uncompromised custody; avoids magic trees, extra templates, waivers, and counterfeit JSON.
- Tasks:
  - normal T9: Generate exactly the five specified scaffold files after full pre-render/preflight — collisions mutate nothing; publication failure removes only invocation-created files; profile reads the project agent body and inherits Discord tools. Classification: mechanical templating with bounded transactional behavior.
  - [XHARD] T10: Wire the launcher to exact repo root, real env, external profile, repo-local state, exact-HEAD attestation, exported validated seed, and resident exec — valid mocked startup reaches service construction; missing or forged evidence fails clearly. Classification: custody-sensitive startup integration.

## Batch 7 — Package, document, and prove the deliverable
- Checkpoint: Clean-install wheel/sdist generation, targeted and affected suites, operational documentation, and the R1–R3 evidence matrix all pass with North Star and anti-pattern review.
- Advances: R1, R2, R3; proves the platform is runnable, customizable, and reproducible while preserving fork-clean omp, compatibility surfaces, and a readable five-file scaffold.
- Tasks:
  - normal T11: Package templates and complete tests, docs, and evidence — cover shadowing, exact roots, parity, containment, import isolation/concurrency, backend, dry-run, attestation, downgrade rejection, and chain regression; document install-through-operation and map every criterion to receipts. Classification: broad but primarily mechanical verification and release integration.PASS

Findings: none.

Evidence:
- `arnold.md` reflow preserves prompt words and semantics while removing soft line breaks, matching `AgentBoxOperatorProfile.system_prompt()`.
- Parity test mirrors omp’s relevant behavior: CRLF/CR normalization, first `\n---` after offset 3, body slicing, and trimming. It enforces exact raw body plus one terminal LF.
- Focused parity test passed: `1 passed, 28 deselected`.
- `~/.bun/bin/agent list` exposes `arnold`; `agent run arnold ...` succeeded through the existing omp path.
- Installed `~/.omp/agent/agents/arnold.md` is byte-identical to `agentbox/agents/arnold.md`.
- Delta contains no omp source changes, alternate runtime, compatibility renames, or resident semantic edits.
- The six attestation failures remain the documented pre-existing environment gap, not a Batch 1 defect.
0
 .oracle/status.md                       |  6 +++
 .oracle/tasklist.md                     | 70 +++++++++++++++++++++++++++++++++
 agentbox/agents/arnold.md               | 11 +-----
 tests/agentbox/test_resident_profile.py | 19 +++++++++
 4 files changed, 96 insertions(+), 10 deletions(-)
diff --git a/.oracle/status.md b/.oracle/status.md
new file mode 100644
index 0000000000..84a2cbabf7
--- /dev/null
+++ b/.oracle/status.md
@@ -0,0 +1,6 @@
+# Status — megado run on Arnold
+- Phase: 4 complete → 5 (execute) — FROZEN tasklist accepted 2026-08-21
+- Base: 744a417198; foundation b7c682798e; contract eac81e57d2; plan 796961cd9c
+- Model policy: normal=codex:gpt-5.6-luna, [XHARD]=codex:gpt-5.6-sol, oracle=Sol
+- Next: Batch 1 (T3 Sol then T1 Luna), then oracle checkpoint
+- Blocker/escalation: none in-run; main-tree purge (bg_7) timed out — post-run resolution
diff --git a/.oracle/tasklist.md b/.oracle/tasklist.md
new file mode 100644
index 0000000000..a9fbdf47c3
--- /dev/null
+++ b/.oracle/tasklist.md
@@ -0,0 +1,70 @@
+# Tasklist — megado run (FROZEN 2026-08-21)` + model-policy line (normal = `codex:gpt-5.6-luna`, [XHARD] = `codex:gpt-5.6-sol`, oracle = Sol; user-declared, no auto-routing) + a "Run-wide operational contract" block (per-batch commit on `oracle-run`; allowed `.oracle` commits; never `main`; final push `HEAD:oracle-run` + `open` gated on the final oracle review).
+   - Batches 1–7 with: T1–T11 from the plan (unchanged acceptances), T12 `[XHARD]` "final oracle review gates commit/push", T13 `normal` "sync: push HEAD:oracle-run, open worktree" — plus Batch 3 split into checkpoints (T4 checkpoint, then T5), and Batch 5's discriminator gate as its first task (T8a "freeze standalone/cloud authority discriminator + state-dir convention; escalate if primitives can't express fail-closed" before T8b).
+   - Each checkpoint line MUST end with exact commands (e.g. `python -m pytest tests/agentbox/test_cli.py tests/agentbox/test_resident_profile.py -q`, `~/.bun/bin/agent list`, `~/.bun/bin/agent run arnold "State your name and rules."`, `python -c "import agentbox.cli"`, `agentbox new-resident demo --repo /tmp/demo-r && python -c "import importlib; importlib.import_module('resident_profile')"`-style generation/import probes, evidence-matrix receipt check).
+   - Model line per task: `[normal → codex:gpt-5.6-luna]` or `[XHARD → codex:gpt-5.6-sol]` with a short rationale.
+
+Under 1300 words. Your output is saved verbatim as the frozen tasklist — it must be complete and self-contained.
+codex
+I’m reading the five Oracle artifacts now, then I’ll reconcile every review finding into a self-contained frozen tasklist.
+exec
+/bin/zsh -lc "sed -n '1,240p' .oracle/checkins/pre-execution-review.txt && sed -n '1,320p' .oracle/tasklist.md && sed -n '1,240p' .oracle/agent_goal.md && sed -n '1,240p' .oracle/northstar.md && sed -n '1,360p' .oracle/plan.md" in /Users/peteromalley/Documents/arnold-oracle
+ succeeded in 0ms:
+CONTRACT ISSUES
+
+1. **Blocking — final oracle review is not operationally covered.** `.oracle/agent_goal.md §Done criteria 6`; `.oracle/tasklist.md Batch 7`. The tasklist mentions a generic North Star/anti-pattern review, but no explicit final Sol oracle review or model receipt. **Suggested fix:** add a post-verification `[XHARD]` Sol oracle task that gates commit and push.
+
+2. **Blocking — authorization and sync steps are absent.** `.oracle/agent_goal.md §§Authorization boundaries, Sync/promotion policy`; `.oracle/tasklist.md`. No task/checkpoint requires per-batch commits, committing allowed `.oracle/` artifacts, final `HEAD:oracle-run` push, opening the worktree, or explicitly never mutating `main`. **Suggested fix:** add an operational final batch plus per-batch commit checkpoints encoding these exact constraints.
+
+3. **Blocking — seam dependency is not guaranteed.** `.oracle/tasklist.md Batch 3`. T4 (configuration seam) and T5 (external loader) share a batch; batching does not establish that T4 completes before T5. **Suggested fix:** split T4 into a completed checkpoint before T5, or declare and enforce an intra-batch dependency.
+
+4. **Blocking — custody discriminator remains unresolved before implementation.** `.oracle/plan.md §Residual open questions`; `.oracle/tasklist.md Batch 5`. The exact standalone/cloud authority discriminator is explicitly still open, yet T8 proceeds directly to implementation. **Suggested fix:** insert a Sol/oracle gate to freeze the discriminator and state-directory convention; halt and escalate if existing primitives cannot support it fail-closed.
+
+5. **Advisory — checkpoints are assertions, not verifiable one-liners.** `.oracle/tasklist.md Batches 1–7`; `.oracle/agent_goal.md §Validation commands`. Several checkpoints omit exact commands, notably `python -c "import agentbox.cli"`, clean `new-resident` generation/import, and evidence-matrix receipt validation. **Suggested fix:** attach concrete one-line commands or named scripts to every checkpoint.
+
+The remaining classifications are sensible. Non-goals and North Star direction are otherwise respected: one omp runtime, markdown identity, contained profile seam, readable five-file scaffold, no omp edits, compatibility renames, tool-catalog changes, purge work, or attestation bypass.
+0
+## Batch 1 — Preserve R1 and repair exact prompt parity
+- Checkpoint: Raw and omp-parsed prompt parity tests pass; installed `arnold` appears in `agent list` and `agent run arnold` succeeds through the existing dispatcher. This must pass before scaffold generation.
+- Advances: R1, R2; preserves one runtime/one identity seam and byte-parity with the live Discord prompt; avoids alternate dispatch, prompt normalization, and compatibility renames.
+- Tasks:
+  - normal T1: Preserve and prove the packaged `arnold` named agent and existing omp dispatch path — installed package exposes `arnold`; list/run probes succeed from repo root; no alternate runtime is added. Classification: bounded preservation and verification.
+  - [XHARD] T3: Repair and enforce exact prompt parity using omp’s CRLF, delimiter, and trim semantics — raw body is exactly `system_prompt().encode() + b"\n"`, parsed body matches byte-for-byte, and semantic changes require both surfaces plus a version bump. Classification: parser-edge and identity-integrity sensitivity.
+
+## Batch 2 — Constrain installer customization
+- Checkpoint: Installer tests prove safe rename/re-description, unchanged prompt bytes, atomic non-overwriting writes, and clean rejection of unsafe names and unknown templates.
+- Advances: R2; preserves markdown as the identity surface and elegance over machinery; avoids flag soup and hidden prompt mutation.
+- Tasks:
+  - normal T2: Add only `--name` and `--description` overrides to packaged-template installation — validate the restricted name grammar excluding `.`/`..`; update filename/frontmatter only; fail atomically on collisions or invalid input. Classification: bounded CLI/resource work with explicit rules.
+
+## Batch 3 — Open one contained profile seam
+- Checkpoint: Built-in and external profile-loading tests pass, including identical CLI/environment behavior, resolved-root containment, precise failures, deterministic reloads, and concurrent cross-repo isolation. This must pass before dry-run or generator integration.
+- Advances: R3; preserves one minimal seam and fork-clean omp; avoids runtime re-architecture and treating trusted imports as sandboxed.
+- Tasks:
+  - normal T4: Make `ResidentConfig.profile` a validated non-empty string, remove argparse choices, preserve built-ins/defaults, pass the resolved root, and reject unknown simple names with concise `CliError` output. Classification: localized configuration seam.
+  - [XHARD] T5: Load trusted repo-relative `path.py:Class` profiles with strict containment, hashed module identity, locked module mutation, and failure eviction — generated profiles construct; escapes, malformed targets, bad classes/constructors, stale modules, and concurrency hazards fail specifically. Classification: security-sensitive path resolution and global import-state concurrency.
+
+## Batch 4 — Validate profiles and inherited runtime behavior
+- Checkpoint: Network-free dry-run instantiates the selected profile and exposes import/constructor defects; fake-backend tests prove inherited `cloud_resume`; tool registries remain per-instance and unchanged. This must pass before generated launchers are wired.
+- Advances: R3; preserves the existing resident runtime and Discord tool catalog; avoids hollow dry-run success and agent-file tool leakage.
+- Tasks:
+  - normal T6: Make dry-run construct dependencies and instantiate the selected profile while skipping tokens, attestation, runner/service construction, and network activity — profile defects surface without side effects. Classification: bounded lifecycle adjustment.
+  - [XHARD] T7: Inject/default a compatible `CloudCliBackend` for inherited `cloud_resume` while retaining store/config/authorization injection and isolated tool registries — fake-backend and subclass tests pass without catalog changes. Classification: cross-cutting inherited-contract risk.
+
+## Batch 5 — Establish standalone custody honestly
+- Checkpoint: Standalone attestation passes only for the exact resolved root and live expected HEAD, produces validated seed/process receipts, and fails closed for tampering, staleness, or custody mismatch; chain provisioning remains behaviorally unchanged. This must pass before launcher wiring.
+- Advances: R3; preserves compatibility as a contract and fail-closed custody; avoids counterfeit cloud evidence, downgrade paths, waivers, and parallel attestation machinery.
+- Tasks:
+  - [XHARD] T8: Add one domain-separated `resident attest` adapter using canonical vectors, validation, atomic content-addressed storage, and root-custodied state — valid standalone evidence satisfies runtime launch validation; wrong root/HEAD, altered evidence, stale seeds, and cloud/standalone mismatches fail closed. Classification: authority-boundary and custody-critical work.
+
+## Batch 6 — Generate and wire the five-file resident
+- Checkpoint: Generation transaction tests create exactly five readable artifacts with executable launcher and clean rollback; mocked startup attests exact HEAD, constructs the external profile, creates process attestation, and reaches service startup without network.
+- Advances: R3; preserves user ownership, readable scaffolds, exact-root operation, and uncompromised custody; avoids magic trees, extra templates, waivers, and counterfeit JSON.
+- Tasks:
+  - normal T9: Generate exactly the five specified scaffold files after full pre-render/preflight — collisions mutate nothing; publication failure removes only invocation-created files; profile reads the project agent body and inherits Discord tools. Classification: mechanical templating with bounded transactional behavior.
+  - [XHARD] T10: Wire the launcher to exact repo root, real env, external profile, repo-local state, exact-HEAD attestation, exported validated seed, and resident exec — valid mocked startup reaches service construction; missing or forged evidence fails clearly. Classification: custody-sensitive startup integration.
+
+## Batch 7 — Package, document, and prove the deliverable
+- Checkpoint: Clean-install wheel/sdist generation, targeted and affected suites, operational documentation, and the R1–R3 evidence matrix all pass with North Star and anti-pattern review.
+- Advances: R1, R2, R3; proves the platform is runnable, customizable, and reproducible while preserving fork-clean omp, compatibility surfaces, and a readable five-file scaffold.
+- Tasks:
+  - normal T11: Package templates and complete tests, docs, and evidence — cover shadowing, exact roots, parity, containment, import isolation/concurrency, backend, dry-run, attestation, downgrade rejection, and chain regression; document install-through-operation and map every criterion to receipts. Classification: broad but primarily mechanical verification and release integration.
\ No newline at end of file
diff --git a/agentbox/agents/arnold.md b/agentbox/agents/arnold.md
index 5863225935..082ba5d608 100644
--- a/agentbox/agents/arnold.md
+++ b/agentbox/agents/arnold.md
@@ -2,13 +2,4 @@
 name: arnold
 description: "Arnold resident operator (agentbox-operator-v1): concise, state-first, one clarifying question."
 ---
-
-You are the AgentBox Operator for Discord. Keep responses concise,
-include operation ids whenever an operation is involved, inspect
-ambiguous machine state before asking, and ask exactly one concrete
-clarifying question when intent or target state is ambiguous. Up to three
-exact Discord reply ancestors are preloaded nearest-first. Never infer reply
-ancestry from recent messages; use `read_reply_chain` with the supplied cursor
-when older ancestors remain. Hot context's `user_timezone` is the presentation
-authority: render absolute user-visible times from deterministic `*_local` fields,
-keep stored/control-plane timestamps in UTC, and preserve relative durations.
+You are the AgentBox Operator for Discord. Keep responses concise, include operation ids whenever an operation is involved, inspect ambiguous machine state before asking, and ask exactly one concrete clarifying question when intent or target state is ambiguous. Up to three exact Discord reply ancestors are preloaded nearest-first. Never infer reply ancestry from recent messages; use `read_reply_chain` with the supplied cursor when older ancestors remain. Hot context's `user_timezone` is the presentation authority: render absolute user-visible times from deterministic `*_local` fields, keep stored/control-plane timestamps in UTC, and preserve relative durations.
diff --git a/tests/agentbox/test_resident_profile.py b/tests/agentbox/test_resident_profile.py
index bed8631606..1f53c75d3e 100644
--- a/tests/agentbox/test_resident_profile.py
+++ b/tests/agentbox/test_resident_profile.py
@@ -58,6 +58,25 @@ def _set_runtime_subject(subject: object) -> contextvars.Token:
     )
 
 
+def test_arnold_agent_prompt_has_raw_byte_parity_with_resident_profile() -> None:
+    agent_file = Path(__file__).parents[2] / "agentbox" / "agents" / "arnold.md"
+    raw = agent_file.read_bytes()
+    assert raw.startswith(b"---")
+
+    closing_index = raw.index(b"\n---", 3)
+    assert raw[closing_index : closing_index + 5] == b"\n---\n"
+    raw_body = raw[closing_index + 5 :]
+
+    normalized = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
+    normalized_closing_index = normalized.index("\n---", 3)
+    parsed_body = normalized[normalized_closing_index + 4 :].strip().encode()
+    expected_prompt = AgentBoxOperatorProfile().system_prompt().encode()
+
+    # Semantic prompt edits MUST change both the agent file and resident_profile.py
+    # and bump AGENTBOX_OPERATOR_PROMPT_VERSION; raw-bytes is the authority
+    # (no whitespace normalization).
+    assert parsed_body == expected_prompt
+    assert raw_body == expected_prompt + b"\n"
 
 
 def test_agentbox_operator_profile_registers_exact_v0_tool_catalog(

codex
The implementation delta is narrowly scoped to the agent prompt and parity test; I’m checking commit boundaries and the authoritative Batch 1 acceptance now, including whether any artifact-only oddities affect the batch verdict.
exec
/bin/zsh -lc "git log --oneline --decorate --no-merges 796961cd9c..9224f52ce2 && git show --stat --oneline 9224f52ce2 && rg -n \"Batch 1|T1|T3|raw byte|parity|29 passed|6 failed|attestation\" .oracle agentbox tests -g '"'!*.pyc'"' | head -240 && git status --short --branch" in /Users/peteromalley/Documents/arnold-oracle
 succeeded in 5ms:
## oracle-run
?? .oracle/briefs/
?? .oracle/checkins/
?? .oracle/findings/

collab: Wait
codex
PASS
T1/T3 meet frozen acceptance; the six failures are pre-existing and T8-scoped, with no North Star anti-patterns introduced.
tokens used
39,786
PASS
T1/T3 meet frozen acceptance; the six failures are pre-existing and T8-scoped, with no North Star anti-patterns introduced.
