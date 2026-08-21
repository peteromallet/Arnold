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
  - normal T11: Package templates and complete tests, docs, and evidence — cover shadowing, exact roots, parity, containment, import isolation/concurrency, backend, dry-run, attestation, downgrade rejection, and chain regression; document install-through-operation and map every criterion to receipts. Classification: broad but primarily mechanical verification and release integration.