# Megaplan Complete-Cleanup Single-Root — Sense-Check vs Current Code
- Date: 2026-08-09
- Epic under review: .megaplan/initiatives/arnold-complete-cleanup-single-root (chain.yaml, NORTHSTAR.md, briefs/m0..m3, notes/PREP.md)
- Method: 14 read-only dimension agents + adversarial verification of high/critical actionable findings.

## Bottom Line
- The epic could NOT run as written today, on two launch prerequisites (both confirmed): (1) chain.yaml's `base_branch: native-python-working-tree` is a swept ref — it was re-created 2026-06-25 (9e6ea5d25c), was the actual chain base, and its content is fully resolvable by `main` — so it must be re-anchored to `main`/`main-unification` before any `chain start` (corrected from blocking → drift by reflog/lineage verification); (2) PREP.md's `--spec` path points at a nonexistent `briefs/chain.yaml` (chain.yaml lives at the initiative root) — the trailing `briefs/` must be dropped.
- The M2 "canonical CLI smoke for init/status/run/config" claim is overstated: `init`/`status` are real, but `run` and `config` are NOT registered subparsers on the canonical path — `parse_args(['run'])` and `parse_args(['config'])` exit SystemExit 2, and the handlers are unreachable orphan code. `execute` is the real run-phase verb. Docs still advertise the broken verbs (docs/pipelines.md:120, docs/configuration.md:9). Blocking for the M2 done criteria (critical).
- The single-root migration is already largely DONE and merged onto `main` (commit 1052ef091a deletes the legacy root). The legacy tree, `_pipeline` namespace, and legacy imports are all absent. Many briefs still describe the deletion as forward M1/M2 work, and the current live trajectory is the unification program (`main-unification` @ f6d62850), not this cleanup epic.
- Big drifts: 8 bundled skill symlinks under `arnold_pipelines/megaplan/skills/{babysit,megaplan,..tickets}/SKILL.md` were rewritten from committed relative targets to absolute `/Users/...` targets (symlink churn — violates M2 "no symlink/type churn"); `subagent-launcher/SKILL.md:73` still points agents at the deleted `arnold.pipelines.megaplan.agent` path; NEXT_STEPS.md / M3 "clean git status" gates describe a mid-June state that no longer matches the working tree.
- The TypeScript-era snapshot `/Users/peteromalley/Documents/Arnold.pre-megaplan-rename-20260624-142318` was removed locally WITHOUT ever being archived to `archive/typescript-bot-era` (no such ref), and no follow-up ticket/blocker records the deletion — the M0/M3 "archive-then-delete" requirement and its fallback both went unmet (high drift).
- Still valid in force: legacy root deletion, no `_pipeline` recreation, no cross-root implementation imports, the 134-entry legacy_reference_allowlist is fully live and shrink-consistent (stale=[]), and the 5 canonical pipeline rows' builders resolve. One "blocking" chain finding was refuted to drift by reflog/lineage verification.

## Verified Findings

### legacy-tree
- **still_valid / low — Legacy tree `arnold/pipelines/megaplan/` contains no business logic; prefer deleting entirely** (NORTHSTAR.md:9-15)
  - Current state: tree is not merely empty — it is entirely absent. Deleted wholesale by commit 1052ef091a. Zero tracked files.
  - Evidence: `arnold/pipelines/megaplan` (absent); `arnold/pipelines/` (only `_authoring.py` + `evidence_pack/`); NORTHSTAR.md:9-15
  - Recommended change: none. Optionally note deletion already completed (1052ef091a).
- **still_valid / low — M2 done: `arnold/pipelines/megaplan` absent or reduced to accepted migration-error stub** (m2-parity-and-delete.md:30)
  - Current state: satisfies the STRONGER branch — fully absent. Only archived-tests and scanner-target allowlist traces remain, both intentionally tolerated.
  - Evidence: `arnold/pipelines/__init__.py` (absent, correctly PEP420); `_authoring.py:5-7`; m2-parity-and-delete.md:30; legacy_reference_allowlist.json
  - Recommended change: none.
- **still_valid / low — M2 done: Legacy registry is empty or deleted** (m2-parity-and-delete.md:31)
  - Current state: legacy `_pipeline.registry` namespace is gone under both roots; rehomed to `arnold_pipelines/megaplan/registry.py` + `runtime/discovery.py`. Canonical `pipeline_ids.json` is non-empty (5 keep entries) — distinct from deleted legacy registry. Working-tree diff there is trailing-newline only.
  - Evidence: `arnold_pipelines/megaplan/registry.py:1-18`; `pipeline_ids.json`; m2-parity-and-delete.md:31
  - Recommended change: clarify "legacy registry" = the deleted `_pipeline.registry` namespace, not the canonical 5-entry file.
- **still_valid / low — NORTHSTAR clean: no `_pipeline` recreation; no cross-root import of implementation behavior** (NORTHSTAR.md:20,22)
  - Current state: no `_pipeline` namespace anywhere; `arnold/__init__.py` tracks `__version__='0.23.0'` locally to avoid the legacy circular import.
  - Evidence: `arnold/__init__.py`; `arnold_pipelines/megaplan/registry.py:12`
  - Recommended change: none. Invariant confirmed satisfied.

### canonical-root
- **still_valid / low — One Megaplan implementation root: `arnold_pipelines/megaplan/`; legacy tree contains no business logic** (NORTHSTAR.md:3-15)
  - Current state: canonical root is live and authoritative (118 entries); legacy root absent on disk. On `main`.
  - Evidence: `arnold_pipelines/megaplan/__init__.py`, `registry.py`, `cli/run.py`
  - Recommended change: none; note legacy root already physically deleted.
- **drift / medium — No final `_pipeline` compat namespace recreated** (m1-authority-and-extraction.md:13-15)
  - Current state: claim's core holds (no `_pipeline` dir), but M1's preferred names never existed: `runtime/preflight.py` MISSING, `runtime/dispatch.py` MISSING, `runtime/patterns.py` MISSING. Real homes differ.
  - Evidence: `runtime/__init__.py:1-10`; `execute/preflight.py`; `cloud/preflight.py`; `_core/dispatch.py`
  - Recommended change: update brief to ACTUAL canonical homes (preflight at root+execute/, dispatch at `_core/`, patterns at `pattern_dynamic.py` + `runtime/pattern_topology.py`), or schedule extraction to match.
- **drift / medium — Extract executor into `runtime/executor.py`** (m1-authority-and-extraction.md:14-15)
  - Current state: NO `executor.py` anywhere; `executor` only appears as identifiers. Step execution realized as `execute/batch.py` (6879 lines) + `execute/core.py` + `drivers/in_process.py`.
  - Evidence: `execute/batch.py:1`, `execute/core.py:1`, `runtime/__init__.py`
  - Recommended change: name the real executor home (`execute/batch.py` + `execute/core.py`); if literal `runtime/executor.py` still desired, the M1 task is open, not complete.

### legacy-dotted-imports
- **drift / medium — No public docs/skills/assets instruct `python -m arnold.pipelines.megaplan`** (NORTHSTAR.md:21)
  - Current state: literal dotted invocation only in scanner-targets + historical archival docs. Live docs use canonical. BUT `subagent-launcher/SKILL.md:73` asserts "the real Hermes runtime lives under arnold.pipelines.megaplan.agent" — a deleted namespace, allowlisted as `historical-non-shipped` though it is live packaged instruction text.
  - Evidence: `checks.py:73`, `checks.py:76`; `skills/subagent-launcher/SKILL.md:73`; `docs/cloud.md:3`
  - Recommended change: fix SKILL.md:73 to `arnold_pipelines.megaplan.agent` or past-tense; revisit its allowlist category.
- **still_valid / low — M2 done: source/test/doc/skill scans show no unapproved legacy path usage** (m2-parity-and-delete.md:32)
  - Current state: no live non-archive import of the legacy path; only negative/ModuleNotFoundError tests remain. 63 hit files all allowlisted except 4 review docs under `docs/arnold/workflow-manifest-runtime-review/` deliberately excluded by scanner.
  - Evidence: `checks.py:73,1167`; `deleted_surfaces.py:98`; legacy_reference_allowlist.json
  - Recommended change: none; gate holds. Optionally document/a..lowlist the 4 excluded review docs.
- **drift / medium — NORTHSTAR deletion gate: no `__pycache__` survivors** (NORTHSTAR.md:26)
  - Current state: legacy subdir absent, but parent `arnold/pipelines/` holds gitignored `__pycache__/` (`_authoring.cpython-311.pyc` + 8 evidence_pack survivors) plus TRACKED product `evidence_pack/*` (build_pipeline, native, steps, verifier, resume imported by live tests, packaged pyproject.toml:93-94).
  - Evidence: `arnold/pipelines/__pycache__/_authoring.cpython-311.pyc`; `evidence_pack/__pycache__/pipeline.cpython-312.pyc`
  - Recommended change: scope "no stale `__pycache__` survivors" clause to the megaplan root (or the whole `arnold/pipelines/` dir) so evidence_pack survivors don't read as unmet; optionally schedule a bytecode-cleanup run.
- **still_valid / low — canonical package does not import from `arnold.pipelines.megaplan`** (NORTHSTAR.md:20)
  - Current state: legacy path absent; `cloud/cli.py:2266` references it only as a `find_spec()` presence REPORT (enforcement, not dependency).
  - Evidence: `cloud/cli.py:2266`, checks.py:73
  - Recommended change: none.
- **drift / medium — M2 sweep so humans/agents use canonical invocation** (m2-parity-and-delete.md:16)
  - Current state: most skills + cloud.md canonical, but `subagent-launcher/SKILL.md:73` still tells agents to use deleted `arnold.pipelines.megaplan.agent`, contradicting `megaplan-cloud/SKILL.md:163`.
  - Evidence: `skills/subagent-launcher/SKILL.md:73`; `skills/megaplan-cloud/SKILL.md:163`
  - Recommended change: fix to canonical or past-tense; update allowlist reason.
- **still_valid / low — M2 done: `git status --porcelain` shows no symlink/type churn** (m2-parity-and-delete.md:33)
  - Current state: no symlink/type churn under legacy root; stale bytecode gitignored so invisible to porcelain.
  - Evidence: `arnold/pipelines/__pycache__/_authoring.cpython-311.pyc`
  - Recommended change: none for epic; optionally delete gitignored bytecode. (Note: contradicts skills-docs-assets finding of actual symlink churn on skills — see blocking row.)
- **still_valid / low — M2 done: `arnold/pipelines/megaplan` absent or migration-error stub** (m2-parity-and-delete.md:30)
  - Current state: megaplan subdir gone; parent retains evidence_pack + _authoring.py only.
  - Evidence: `arnold/pipelines/` (no megaplan subdir)
  - Recommended change: none.

### legacy-fs-refs
- **still_valid / low — No docs/skills/assets instruct `python -m arnold.pipelines.megaplan`** (NORTHSTAR "What Clean Means")
  - Current state: dotted invocation only in negative scanner-targets + allowlisted historical artifacts. Every live surface canonical (README, AGENTS.md, skills, docs/cloud.md, discovery rows).
  - Evidence: checks.py:73-78; legacy_reference_allowlist.json; README.md:63,88; AGENTS.md:10-12; `skills/megaplan/SKILL.md:17`
  - Recommended change: none; claim true.
- **still_valid / low — M2 sweep complete for shipped surfaces** (m2-parity-and-delete.md In-scope)
  - Current state: README/AGENTS/skills/docs all canonical; zero live legacy references outside scanner/allowlist. Ratchet asserts unallowlisted==[] and stale_allowlist==[].
  - Evidence: `skills/megaplan/SKILL.md:18`; docs/cloud.md; discovery.py:66-132
  - Recommended change: name `checks.py` + `legacy_reference_allowlist.json` explicitly as the M2 gate in the epic.
- **still_valid / low — Deletion gate: no legacy business logic; no permanent shims** (NORTHSTAR "Why This Matters" + m2-parity-and-delete.md)
  - Current state: legacy tree absolutely absent; pyproject.toml:83,110 retain deletion sentinels excluding `arnold/pipelines/**`; NEXT_STEPS.md:158 confirms path gone.
  - Evidence: pyproject.toml:83,110,94; NEXT_STEPS.md:158
  - Recommended change: none; gate satisfied at HEAD.
- **drift / medium — Epic doesn't name the enforcement mechanism** (NORTHSTAR; observed worktree)
  - Current state: enforcement IS present (checks.py:73-78, allowlist categorized, test asserts) but the epic never cites it — a spec-under-specifies-its-own-guard gap. Allowlist currently git-M (phantom stat cache — see conformance-allowlist).
  - Evidence: checks.py:73-78; legacy_reference_allowlist.json; test_legacy_reference_allowlist.py:38-119
  - Recommended change: add explicit line naming the conformance gate as the guarantee's mechanism.

### entrypoint-reality
- **blocking / critical — M2 canonical CLI smoke for init/status/run/config** (m2-parity-and-delete.md:11)
  - Current state: `init` (line 191) and `status` (line 244) registered; `run`/`config` NOT registered. `parse_args(['run'])`/`(['config'])` exit SystemExit 2. Dead handlers survive at `_main` 3573/3626; `cli/run.py:103 build_run_parser` has no callers. `execute` is the real run verb.
  - Evidence: `cli/__init__.py:191,244,3573,3626`; `cli/run.py:103`; `arnold/cli/__init__.py:8`; docs/pipelines.md:120; docs/configuration.md:9
  - Recommended change: (a) wire run/config into build_parser, or (b) correct the epic + docs (run verb is `execute`; no `config`) .
  - Verification: confirmed (high)
- **still_valid / low — init and status CLI smoke on canonical path** (m2-parity-and-delete.md:11 subset)
  - Current state: both registered + wired; package imports clean; `__file__` resolves.
  - Evidence: `cli/__init__.py:191,244`; `cli/status_view.py:1`
  - Recommended change: none for init/status.
- **still_valid / low — Legacy root deleted or intentionally non-functional** (m2-parity-and-delete.md:5)
  - Current state: legacy root fully deleted — ModuleNotFoundError on import, absent on disk, no `__init__.py` under `arnold/pipelines/`, version tracked locally. Stale command refs remain in docs.
  - Evidence: legacy_reference_allowlist.json:3; test_megaplan_coupling_gate.py:50; test_deleted_surfaces.py:101
  - Recommended change: update docs/pipelines.md and docs/configuration.md stale `arnold run`/`megaplan config` refs.
- **drift / low — leftover legacy-path residue (__pycache__/empty dirs) vs deletion sweep** (m2-parity-and-delete.md:18,33)
  - Current state: untracked residue at `tests/arnold/pipelines/megaplan/__pycache__/` + empty `execute/` + `.mypy_cache/3.11/arnold/pipelines/megaplan`. All gitignored; also mid-cherry-pick merge state on main.
  - Evidence: `tests/arnold/pipelines/megaplan/__pycache__`; `.mypy_cache/3.11/arnold/pipelines/megaplan`
  - Recommended change: clean residue; resolve/abort in-progress cherry-pick before closeout.

### cross-root-imports
- **still_valid / low — canonical pkg does not import from legacy root** (NORTHSTAR.md:20)
  - Current state: zero imports from `arnold.pipelines.megaplan` in canonical tree; __init__.py imports only neutral substrate + own submodules; legacy deleted by 1052ef091a.
  - Evidence: `arnold_pipelines/megaplan/__init__.py:56,74,41`
  - Recommended change: none.
- **still_valid / low — M1: no canonical module imports `_pipeline`** (m1-authority-and-extraction.md:29)
  - Current state: legacy pkg absent; `_pipeline` only in archive + conformance enforcement strings.
  - Evidence: deleted_surfaces.py:82,121,92; tests/archive/m6_deleted_legacy_runtime/; test_deleted_surfaces.py:101
  - Recommended change: none; mark gate satisfied (1052ef091a).
- **still_valid / low — Import order cannot change content-type/model-adapter/normalizer/registry behavior** (NORTHSTAR.md:24)
  - Current state: all four side-effect categories are canonical-local (`_register_megaplan_content_types` on neutral CONTENT_TYPES, `_install_model_adapter_once` with package flag); no legacy delegation.
  - Evidence: `__init__.py:55,71,89`; model_seam.py; deleted_surfaces.py:99
  - Recommended change: none.
- **drift / medium — M1 brief frames extraction/side-effect-migration/deletion as open work** (m1-authority-and-extraction.md:11)
  - Current state: that work already landed on main (1052ef091a ancestor of HEAD); runtime/ owns responsibilities.
  - Evidence: `arnold/pipelines/_authoring.py`; `runtime/resume.py`; `runtime/process.py`
  - Recommended change: reframe briefs as post-hoc verification/closeout, or mark epic completed.

### conformance-allowlist
- **still_valid / low — Allowlist entries are all live (shrink-only list)** (allowlist contract; checks.py:842-935)
  - Current state: all 134 entries live and matching; check reports allowlisted=134, observed=134, stale=[], unallowlisted=[], invalid=[], duplicates=[]; passes.
  - Evidence: legacy_reference_allowlist.json:1-808; checks.py:842-935,1145-1165
  - Recommended change: none.
- **still_valid / low — Any entry not matching code is stale → removed** (checks.py:896-921,924-928 invariant)
  - Current state: stale set machine-enforced fail; currently stale=[] . Recent history pure shrink (7acae08376 -30; 69e697dad2 -12).
  - Evidence: checks.py:896-921,930-935; checks.py:621-676
  - Recommended change: none.
- **drift / low — allowlist appears MODIFIED in git status** (epic premise)
  - Current state: M is a PHANTOM stat-cache artifact. Working/index/HEAD blobs all hash 03a78d9d…; `git update-index --refresh` clears it. Byte-identical to 7250ec5f23.
  - Evidence: legacy_reference_allowlist.json; .git/index
  - Recommended change: correct the brief premise — file is pristine at HEAD; verify via `git diff HEAD`.

### conformance-name-allowlist
- **still_valid / low — NEXT_STEPS lists the two `package-name-staleness` allowlist adds** (NEXT_STEPS.md:54-56)
  - Current state: both entries verbatim in NEXT_STEPS and present in `_allowlist.txt` (terminal_tool:130, registry:136).
  - Evidence: NEXT_STEPS.md:54; `_allowlist.txt:130,136`
  - Recommended change: mark done.
- **still_valid / low — The two legacy arnold.* modules still exist** (NEXT_STEPS.md:54-56 context)
  - Current state: `arnold/agent/tools/terminal_tool.py` (compat loader) and `arnold/pipeline/registry.py` (M1 compat shim slated for M7 removal) both real; legitimately allowlisted.
  - Evidence: `arnold/agent/tools/terminal_tool.py:1,18`; `arnold/pipeline/registry.py:1,16`
  - Recommended change: none; correct until each retired.
- **still_valid / low — staleness check flags modules; allowlist makes gate pass** (checks.py:547; suite.py:185,217-228)
  - Current state: check PASSED=True with current allowlist; both entries present.
  - Evidence: checks.py:557,561,31; suite.py:185,217,187
  - Recommended change: none; drop line 136 when `arnold/pipeline/registry.py` removed at M7.

### discovery-behavior
- **drift / medium — NEXT_STEPS raise-vs-warn mismatch resolved to warn-and-skip** (NEXT_STEPS.md:57)
  - Current state: `discover_python_pipelines()` has NO raise; warns+skips (619-632); `scan_python_pipelines()` never raises (460). Integrity tests assert warn-and-skip. Only raises (316/321) are builder-invocation-time (trust-tier gated), not discovery-time. Doc stale.
  - Evidence: `runtime/discovery.py:600,611,619,630,460,316,321`; tests/test_pipeline_discovery_integrity.py:194,209,225,241
  - Recommended change: update NEXT_STEPS.md:57 to record the resolution.
- **still_valid / medium — M2: every migrated pipeline row points at shipped canonical modules** (m2-parity-and-delete.md:15)
  - Current state: all 5 rows keep w/ manifest_hash; builders resolve (planning, creative, doc, jokes, core) and are in `_SCAN_ROOTS`. Wheel/editable residence unverified statically.
  - Evidence: pipeline_ids.json; pipelines/planning/__init__.py:24; creative/pipeline.py:301; doc/pipeline.py:234; jokes/pipeline.py:175; `__init__.py:38`; discovery.py:438
  - Recommended change: run the M2 installed-wheel smoke (brief line 17); confirm on the actual cleanup worktree.
- **drift / medium — NEXT_STEPS active M2 worktree/branch premise** (NEXT_STEPS.md:1)
  - Current state: checkout is `main` + dirty (modified skills, pipeline_ids, test_m5), NOT on `cleanup-single-root-m2-parity-delete` nor in the cleanup worktree.
  - Evidence: NEXT_STEPS.md:10,11; pipeline_ids.json
  - Recommended change: state authoritative branch/worktree; note M2 landed on main.

### chain-spec-validity
- **blocking / critical — chain.yaml `base_branch: native-python-working-tree` must exist to start** (chain.yaml:1)
  - Current state: ref absent everywhere. Disposition (loose-work-cleanup-disposition-20260625.md:73) records post-merge deletion.
  - Evidence: chain.yaml:1; disposition doc:73
  - Recommended change: point at an existing base (main).
  - Verification: REFUTED (high) — reflog shows the branch was RE-CREATED 2026-06-25 21:21 (9e6ea5d25c) and was the actual base of THIS chain; all chain-authoring commits + tip b7bfd8fbf2 are ancestors of HEAD main. Content fully resolvable by main; ref merely swept post-merge. Corrected verdict: **drift** (row in Stale/Drift, not Blocking, but keep chain-startability concern).
- **still_valid / low — Milestone idea paths resolve to existing briefs** (chain.yaml:8,19,32,45)
  - Current state: m0..m3 briefs all present; no path mismatch.
  - Evidence: briefs/m0..m3-*.md
  - Recommended change: none.
- **still_valid / medium — M3: Ticket 01KVZZ45DAZW9P5H4JA66JWNY3 linked to this epic** (m3-merge-result-closeout.md:28)
  - Current state: ticket already linked (`epics: [arnold-complete-cleanup-single-root]`), status still open. "Linked" already trivially satisfied; "closed by it" not.
  - Evidence: `.megaplan/tickets/01KVZZ45DAZW9P5H4JA66JWNY3-*.md:4,16`; tickets/core.py:3
  - Recommended change: act on stronger "closed by it" branch + fix stale ticket-body chain.yaml path (real: `.megaplan/initiatives/.../chain.yaml`).
- **still_valid / low — M0: local main contains native completion merge + cleanup commits** (m0-baseline-inventory-ratchets.md:11)
  - Current state: disposition doc present + matches; HEAD past those commits.
  - Evidence: disposition doc:11,19,68
  - Recommended change: none.
- **blocking / critical — PREP.md `--spec` path is wrong** (PREP.md:56)
  - Current state: chain.yaml at initiative ROOT; NO chain.yaml under `briefs/`. Invocation would file-not-found.
  - Evidence: PREP.md:56; chain.yaml:1; `briefs/`
  - Recommended change: drop trailing `briefs/` → `chain start --spec .megaplan/initiatives/arnold-complete-cleanup-single-root/chain.yaml`.
  - Verification: confirmed (high)
- **drift / high — Chain config internally inconsistent with repo reality** (synthesis)
  - Current state: base_branch deleted; PREP spec path wrong; ticket body chain.yaml path wrong. Repo healthy (migration mostly achieved) but launch config points at deleted/incorrect paths.
  - Evidence: disposition doc:73; PREP.md:56; ticket body:31
  - Recommended change: reconcile all three config surfaces before start.
  - Verification: confirmed (high)

### snapshot-archive
- **drift / high — M0: push external snapshot to archive/typescript-bot-era, verify, then delete** (m0-baseline-inventory-ratchets.md)
  - Current state: local snapshot `/Users/peteromalley/Documents/Arnold.pre-megaplan-rename-20260624-142318` is GONE; NO `archive/typescript-bot-era` ref/branch/tag ever created. M3 closeout (m3-merge-result-closeout-20260626.md) recorded it "remains". Net: removed without archival.
  - Evidence: m0-baseline-inventory-ratchets.md:1; loose-work-cleanup-disposition-20260625.md:76
  - Recommended change: record archive-ability + push if any surviving copy; else document abandonment.
  - Verification: confirmed (high)
- **drift / high — M3: verify snapshot archived + removed, or record push/blocker failure** (m3-merge-result-closeout.md)
  - Current state: no follow-up ticket/blocker artifact exists (grep 'typescript-bot-era' matches only briefs + closeout doc). Cleanup-single-root-m3-closeout branch absent. Fallback never fulfilled.
  - Evidence: m3-merge-result-closeout-20260626.md:1; m3-brief:1; chain.yaml:1
  - Recommended change: create the missing follow-up ticket/blocker documenting the unarchived deletion.
  - Verification: confirmed (high), corrected verdict drift + stale
- **stale / low — Old TypeScript snapshot still present** (m3-merge-result-closeout.md baseline)
  - Current state: now ABSENT (2026-08-09); removed without the required archive push.
  - Evidence: m3-merge-result-closeout-20260626.md:1
  - Recommended change: none for survival fact; actionable fix captured above.

### worktree-reality
- **stale / low — M3: delete `native-python-pipelines-completion-thread2` worktree** (m3-merge-result-closeout.md:14)
  - Current state: worktree absent everywhere; only 3 unrelated worktrees exist. Delete moot.
  - Evidence: brief :14; archived closeout doc
  - Recommended change: convert to verify-check ("confirm gone from all hosts incl. cloud box").
- **drift / high — NEXT_STEPS: use cleanup worktree `/Users/.../.megaplan-worktrees/arnold-cleanup-single-root`** (NEXT_STEPS.md:12,63,70,112,143,159)
  - Current state: dir does not exist; no such branch; resume narrative stale vs Aug-9. Live trajectory is unification (`main-unification` f6d62850, merge/unification-20260809). Following today → cd into nonexistent dir.
  - Evidence: NEXT_STEPS.md:12,63,159,152
  - Recommended change: re-point to unification worktrees or archive NEXT_STEPS.
  - Verification: confirmed (high)
- **drift / high — chain.yaml base_branch `native-python-working-tree` + prep_direction** (chain.yaml:1,12; NEXT_STEPS.md:130)
  - Current state: no such branch/ref. Modern base is unification frontier.
  - Evidence: chain.yaml:1,12; NEXT_STEPS.md:130
  - Recommended change: re-anchor base_branch to `main-unification`/`main`.
  - Verification: confirmed (high)
- **still_valid / low — `editible-install`/`base/editable-install` relate to cloud deploy** (MEMORY notes)
  - Current state: live deploy artifacts; editible-install #dda97cc315 checked out in `Arnold-resident-restart-fix`; origin + remotes/box-wa carry it.
  - Evidence: worktree list; git rev-parse editible-install/origin/base/box-wa
  - Recommended change: add one-line note in epic that this is the cloud deploy lane (don't prune).
- **stale / medium — M3 done: "git status is clean" + "no undecided work"** (m3-merge-result-closeout.md:24,27)
  - Current state: working tree NOT clean (8 modified tracked + ~25 untracked, normal in-flight work). Written for mid-June state.
  - Evidence: brief :24,27; NEXT_STEPS.md:168
  - Recommended change: scope M3 clean-status to the epic's own artifact set only, or treat as obsolete.
- **drift / medium — M3 implies a single "integrated checkout"** (m3-merge-result-closeout.md:5,11,18,23)
  - Current state: integration surface split across 9 worktrees; `main-unification` = current HEAD.
  - Evidence: `git worktree list` (9 entries); rev-parse main vs main-unification
  - Recommended change: name the concrete integration branch/worktree.

### test-survivors
- **still_valid / low — M3: no milestone merge resurrected deleted files** (m3-merge-result-closeout.md:12)
  - Current state: `test_pipeline_runtime_e2e.py` only under `tests/archive/m6_deleted_legacy_runtime/`; three `legacy_*`-named live tests are intentional cross-ref tests.
  - Evidence: `tests/archive/m6_deleted_legacy_runtime/test_pipeline_runtime_e2e.py:1`; test_legacy_reference_allowlist.py; test_legacy_baseline_inventory.py; test_legacy_import.py
  - Recommended change: record archive-integrity check + document the three surviving tests as intentional.
- **drift / medium — M2 plan selectors reference archived `tests/test_pipeline_runtime_e2e.py`** (NEXT_STEPS.md:169)
  - Current state: file gone top-level (only archive + stale .pyc); but plan metadata selectors not reconciled (NEXT_STEPS:169 still live caveat). Active selectors (lines 75-83) all exist.
  - Evidence: NEXT_STEPS.md:169,75; test_pipeline_composability.py; test_pipeline_compose.py
  - Recommended change: purge archived path from m2 plan selectors; update NEXT_STEPS:169 as resolved.
- **still_valid / low — conformance/native test layout** (NEXT_STEPS.md:77-79)
  - Current state: tests/arnold/conformance, tests/arnold_pipelines/megaplan, tests/arnold/pipeline/native all populated.
  - Evidence: NEXT_STEPS.md:77,78,79; test_conformance.py; native/test_runtime.py
  - Recommended change: none; lock the three-dir layout as canonical clean-break selection.
- **drift / low — `tests/cli/test_m5_workflow_cli.py` exists as m5 module-invocation test** (repo layout)
  - Current state: modified + uncommitted; `test_workflow_module_invocation` now injects PYTHONPATH (temp artifact dir). Working-tree change not landed.
  - Evidence: test_m5_workflow_cli.py:1,78
  - Recommended change: land/reconcile the PYTHONPATH fix.
- **drift / low — M3 done: "git status is clean" + "no undecided work"** (m3-merge-result-closeout.md:25-26)
  - Current state: NOT clean (10 modified SKILL.md, pipeline_ids.json, test_m5, allowlist + untracked .megaplan/runs/.tmp_remote_r5/AGENTS.md).
  - Evidence: brief :25,26
  - Recommended change: clarify "clean status" is forward-looking end-of-M3; inventory untracked items with disposition bucket.

### skills-docs-assets
- **drift / medium — M2: "remove ALL legacy implementation files… stale docs… __pycache__… deleted path references"** (m2-parity-and-delete.md:18)
  - Current state: no root SKILL.md; __pycache__ present but gitignored; _codex_skills dir untracked (gitignored:52). 8 TRACKED files under `arnold/pipelines/` (_authoring.py + evidence_pack/*) remain — megaplan root gone but broad "remove ALL legacy" unmet. 3 stale docs reference legacy paths (docs/m8-outbound-coverage.md:23, docs/elegant-arnold-megaplan-split-plan.md:197-236, docs/native-python-epic-readiness.md:20).
  - Evidence: `_authoring.py:9`; `evidence_pack/__init__.py:8`; docs/m8-outbound-coverage.md:23; .gitignore:1,52
  - Recommended change: scope "legacy implementation files" = megaplan root + the 8 `arnold/pipelines/` tracked files; add stale-doc sweep item.
- **still_valid / low — M0: `_codex_skills` contamination not present in committed changes** (m0-baseline-inventory-ratchets.md:29)
  - Current state: `git ls-files | grep _codex_skills` empty; `_codex_skills/` dir on disk is plain skill files (not symlinks), untracked via .gitignore:52. Criterion holds.
  - Evidence: .gitignore:52; `data/_codex_skills/`
  - Recommended change: none.
- **blocking / critical — M2 done: `git status --porcelain` shows no symlink/type churn** (m2-parity-and-delete.md:33)
  - Current state: 8 skill symlinks rewritten from committed RELATIVE (`../../data/x.md`) to ABSOLUTE (`/Users/peteromalley/.../data/x.md`) targets → git sees symlink churn on those paths. Hex resolve fine on this machine, but gate unmet.
  - Evidence: `skills/babysit/SKILL.md`, `skills/megaplan-tickets/SKILL.md`, `skills/superfixer-debug/SKILL.md` (unchanged)
  - Recommended change: restore the 8 symlinks to relative targets (git checkout) so porcelain clean.
  - Verification: confirmed (high)
- **drift / medium — M2 outcome: legacy root deleted + no permanent shims** (m2-parity-and-delete.md:5,22)
  - Current state: megaplan/ absent (good) but `arnold/pipelines/_authoring.py` remains self-importing + 8 tracked files; legacy refs in tools/ + tests/ (tools/generate_m6_controlled_registries.py, tools/generate_wbc_boundary_inventory.py, tests/test_validate_package_disposition.py).
  - Evidence: `_authoring.py:9`; tools/generate_m6_controlled_registries.py; tests/test_validate_package_disposition.py
  - Recommended change: list the 8 files in delete scope (or carve to M3); track tools/tests legacy refs.

## Blocking Items (must-fix before run)

| # | Dimension | Claim | Why it blocks | Evidence | Fix |
|---|---|---|---|---|---|
| 1 | entrypoint-reality | M2 canonical CLI smoke for `run`/`config` (m2-parity-and-delete.md:11) | `parse_args(['run'])`/`(['config'])` exit SystemExit 2 — not registered; handlers orphaned; docs advertise broken verbs. M2 done-criteria cannot pass. | cli/__init__.py:191,244,3573,3626; cli/run.py:103; docs/pipelines.md:120; docs/configuration.md:9 | (a) register run/config subparsers, or (b) correct epic + docs (run verb = `execute`; no `config`). Verification confirmed (high) |
| 2 | chain-spec-validity | PREP.md `--spec` path → `briefs/chain.yaml` (PREP.md:56) | chain.yaml lives at initiative ROOT; no chain.yaml under briefs/ → `chain start` file-not-found. | PREP.md:56; chain.yaml:1; briefs/ | Drop trailing `briefs/` from the spec path. Verification confirmed (high) |
| 3 | skills-docs-assets | M2 "no symlink/type churn" (m2-parity-and-delete.md:33) | 8 skill symlinks rewritten relative→absolute → git status --porcelain dirty with symlink diffs; M2 gate unmet. | skills/{babysit,..,megaplan-tickets}/SKILL.md (HEAD relative, FS absolute) | Restore 8 relative symlink targets (git checkout). Verification confirmed (high) |

Note: the chain.yaml `base_branch: native-python-working-tree` blocked/failed finding was REFUTED to drift — the branch was re-created and is the actual chain base, and its content is fully resolved by HEAD main. It is not listed as blocking, but the ephemeral ref is absent (see Stale/Drift row 3).

## Stale / Drift Items (should-fix)

| # | Dimension | Claim | Drift | Evidence | Fix |
|---|---|---|---|---|---|
| 1 | snapshot-archive | M0/M3: snapshot archived to archive/typescript-bot-era then deleted | Snapshot gone locally but never archived (no ref); no follow-up ticket records deletion. Both branch and fallback unmet. | m0-baseline-inventory-ratchets.md:1; m3-merge-result-closeout-20260626.md:1; disposal:76 | Create follow-up ticket/blocker; push if any surviving copy. Verified confirmed (high) |
| 2 | snapshot-archive | M3: "verified archived + removed" claim | M3 closeout false today; blocker artifact absent. | m3-brief:1; closeout doc:1 | Document unarchived deletion + removal path. Verified confirmed (high) |
| 3 | worktree-reality | chain.yaml `base_branch: native-python-working-tree` | Ref swept (re-created post-disposition, was chain base, merged into main). Base content resolvable via main; ref name stale. | chain.yaml:1,12; NEXT_STEPS.md:130; reflog 9e6ea5d25c | Re-anchor base_branch to main/main-unification. Verified confirmed (high) |
| 4 | worktree-reality | NEXT_STEPS "use arnold-cleanup-single-root worktree" | Worktree + branch nonexistent; resume narrative stale vs Aug-9 unification program. | NEXT_STEPS.md:12,63,159,152 | Re-point to unification tree or archive NEXT_STEPS. Verified confirmed (high) |
| 5 | chain-spec-validity | Chain config internally inconsistent (base + spec + ticket path) | Three persisted config surfaces point at deleted/incorrect paths. | disposal:73; PREP.md:56; ticket body:31 | Reconcile all three. Verified confirmed (high) |
| 6 | discovery-behavior | NEXT_STEPS raise-vs-warn open decision (line 57) | Resolved to warn-and-skip; discovery.py no longer raises; doc not updated. | discovery.py:600,619,630; NEXT_STEPS.md:57 | Check off line 57, record resolution. |
| 7 | discovery-behavior | NEXT_STEPS active M2 worktree/branch premise | Checkout is main+dirty, not the cleanup branch/worktree. | NEXT_STEPS.md:10,11 | Restate authoritative branch; note M2 landed on main. |
| 8 | worktree-reality | M3 "integrated checkout" is single | Integration split across 9 worktrees; main-unification=HEAD. Persisted config implies a single checkout. | worktree list; rev-parse main vs main-unification | Name concrete integration branch/worktree. |
| 9 | worktree-reality / test-survivors | M3 done "git status is clean" / "no undecided work" | Working tree dirty (modified skills, pipeline_ids, test_m5, allowlist + many untracked). Not a current acceptance gate. | m3-brief:24,25,26,27; NEXT_STEPS:168 | Scope to epic artifact set only or treat obsolete. |
| 10 | legacy-dotted-imports | "No surface instructs `arnold.pipelines.megaplan`" | subagent-launcher/SKILL.md:73 points agents at deleted `arnold.pipelines.megaplan.agent`, allowlisted as historical though actionable. | skills/subagent-launcher/SKILL.md:73; megaplan-cloud/SKILL.md:163 | Fix to `arnold_pipelines.megaplan.agent` / past-tense; recategorize allowlist. |
| 11 | legacy-dotted-imports | M2 sweep so humans/agents use canonical invocation | Same subagent-launcher stale actionable line. | skills/subagent-launcher/SKILL.md:73 | Fix + update allowlist reason. |
| 12 | legacy-dotted-imports | NORTHSTAR no __pycache__ survivors | Parent `arnold/pipelines/` holds gitignored __pycache__ + tracked evidence_pack product. | `arnold/pipelines/__pycache__/*.pyc`; pyproject.toml:93 | Scope clause; optional bytecode cleanup. |
| 13 | skills-docs-assets | M2 "remove ALL legacy implementation files/deleted path refs" | 8 tracked `arnold/pipelines/*` files remain; 3 docs still reference legacy paths; _authoring.py self-imports. | `_authoring.py:9`; docs/m8-outbound-coverage.md:23; docs/elegant-arnold-megaplan-split-plan.md:197-236 | List 8 files in delete scope or carve to M3; stale-doc sweep. |
| 14 | skills-docs-assets | M2 "legacy root deleted + no permanent shims" | `arnold/pipelines/_authoring.py` + evidence_pack remain; legacy refs in tools/ + tests/. | `_authoring.py:9`; tools/generate_m6_controlled_registries.py; tests/test_validate_package_disposition.py | Scope delete list; replace self-import; track tools/tests legacy refs. |
| 15 | entrypoint-reality | leftover legacy-path __pycache__/empty dirs vs deletion sweep | Residue at tests/arnold/pipelines/megaplan + .mypy_cache; mid-cherry-pick state. | `tests/arnold/pipelines/megaplan/__pycache__`; `.mypy_cache/3.11/arnold/pipelines/megaplan` | Clean residue; resolve cherry-pick. |
| 16 | canonical-root | M1 preferred canonical names never created (runtime/preflight, dispatch, patterns) | Brief names differ from actual homes. | `runtime/__init__.py:1-10`; execute/preflight.py; _core/dispatch.py | Update brief to real homes or extract. |
| 17 | canonical-root | Executor never extracted to runtime/executor.py | Actual executor is execute/batch.py + core.py. | execute/batch.py:1; execute/core.py:1 | Name real home or complete extraction. |
| 18 | cross-root-imports | M1 brief frames side-effect-migration/deletion as open | Already landed on main (1052ef091a). | `runtime/resume.py`; `runtime/process.py` | Reframe as post-hoc verification / closeout epic. |
| 19 | chain-spec-validity | M3 "linked/closed by" ticket criterion | "Linked" already true; "closed by it" not; body chain.yaml path stale. | ticket .md:4,16,31 | Act on stronger branch; fix ticket path. |
| 20 | discovery-behavior | M2 package-compat wheel/editable half | Static inspection can't confirm install residence; scans verify on main, brief's worktree differs. | pipeline_ids.json; discovery.py:438 | Run installed-wheel smoke (brief line 17). |
| 21 | conformance-allowlist | allowlist "appears MODIFIED" | M is phantom stat-cache; file pristine at HEAD. | legacy_reference_allowlist.json; git diff HEAD | Correct brief premise; verify via git diff HEAD. |
| 22 | legacy-fs-refs | Epic doesn't name enforcement mechanism | Guarantee enforced but never cited → reintroduction not caught by readers. | checks.py:73-78; legacy_reference_allowlist.json | Add explicit gate line to epic. |
| 23 | test-survivors | M2 selectors reference archived tests/test_pipeline_runtime_e2e.py | Gone top-level but plan metadata not reconciled; NEXT_STEPS:169 live caveat. | NEXT_STEPS.md:169,75 | Purge from selectors; mark resolved. |
| 24 | test-survivors | tests/cli/test_m5_workflow_cli.py m5 module-invocation | Modified/uncommitted PYTHONPATH fix. | test_m5_workflow_cli.py:1,78 | Land/reconcile the fix. |
| 25 | worktree-reality | M3 delete `native-python-pipelines-completion-thread2` | Worktree already absent → delete moot. | m3-brief:14 | Convert to verify-check. |
| 26 | snapshot-archive | M3 "old TypeScript snapshot still present" | Now absent; removed without archive. | m3-closeout doc:1 | Record final disposition. |

## Still Valid

### legacy-tree
- still_valid: legacy tree contains no business logic and is actually deleted wholesale (1052ef091a); M2 absent/stub gate met (stronger branch); legacy registry (_pipeline.registry) deleted, canonical 5-entry file distinct; NORTHSTAR no-`_pipeline`-recreation + no cross-root implementation import invariants hold.

### canonical-root
- still_valid: single authoritative root `arnold_pipelines/megaplan/`; legacy root absent.

### legacy-dotted-imports
- still_valid: no unapproved legacy path usage (M2 gate holds); canonical package imports nothing from legacy path; M2 porcelain no-symlink-churn under legacy root.

### legacy-fs-refs
- still_valid: no doc/skill/asset instructs the dotted invocation; shipped-surface sweep complete; deletion gate satisfied at HEAD.

### entrypoint-reality
- still_valid: init/status CLI smoke on canonical path; legacy root deleted (ModuleNotFoundError).

### cross-root-imports
- still_valid: zero cross-root imports; no canonical module imports `_pipeline`; import-order invariance holds (side effects canonical-local).

### conformance-allowlist
- still_valid: all 134 allowlist entries live and matching (stale=[]); shrink-only invariant machine-enforced.

### conformance-name-allowlist
- still_valid: both `package-name-staleness` entries documented + present; both legacy arnold.* modules exist and legitimately allowlisted; staleness gate passes.

### discovery-behavior
- still_valid: all 5 migrated pipeline rows' builders resolve to shipped canonical modules (static scan on main).

### chain-spec-validity
- still_valid: milestone idea paths resolve to existing briefs m0..m3; M0 local-main-contains-merge claim holds; ticket 01KVZZ45 already linked to epic.

### snapshot-archive
- (none still_valid — all drift/stale)

### worktree-reality
- still_valid: `editible-install`/`base/editable-install` are the live cloud-deploy lane (don't prune).

### test-survivors
- still_valid: no milestone merge resurrected deleted legacy files; three surviving `legacy_*` tests are intentional cross-ref tests; the three-dir conformance/native test layout exists as described.

### skills-docs-assets
- still_valid: `_codex_skills` contamination not present in committed changes (no symlinks, untracked).