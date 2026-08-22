Reading additional input from stdin...
2026-08-21T23:54:17.520994Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-21T23:54:17.521027Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-21T23:54:17.521032Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.148.0
--------
workdir: /Users/peteromalley/Documents/arnold-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: high
reasoning summaries: none
session id: 01a026bf-291a-7243-ad85-d06c4a99c86f
--------
user
# Batch 5 oracle check-in — GPT-5.6 Sol (oracle)

> DELEGATION MANDATE — Direct, then validate.

Worktree: `/Users/peteromalley/Documents/arnold-oracle`. Read `.oracle/checkins/batch-5-rereview5.txt` (fresh review: PASS, no findings), `.oracle/rework/batch-5-attempt-1..5.md`, `.oracle/tasklist.md` (Batch 5), full delta `git diff 210bb6e078..HEAD`.

Batch 5: T8a gate froze the standalone/cloud discriminator (PASS); T8b implemented `resident attest` + authority domain-separation; five rework rounds hardened custody (worker-refresh gate, state-dir perms, typed guards, non-mutating loads, preflight-then-create, validated idempotent reuse). Fresh review PASS with zero findings; host verified 42 standalone tests green; live tampered-seed probe exit-2 with pointer unchanged.

Judge: is Batch 5 PASS? Single line `PASS` or `ISSUES` + one-line rationale. Under 80 words.
codex
I’m applying the requested oracle check directly: I’ll inspect every named artifact and the complete base-to-HEAD delta, then validate the security-sensitive paths with focused checks.
2026-08-21T23:54:27.989438Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-21T23:54:27.989546Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-21T23:54:27.989551Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc 'git status --short && rg -n "Batch 5|T8a|T8b" .oracle/tasklist.md && wc -l .oracle/checkins/batch-5-rereview5.txt .oracle/rework/batch-5-attempt-{1,2,3,4,5}.md && git diff --stat 210bb6e078..HEAD' in /Users/peteromalley/Documents/arnold-oracle
 succeeded in 0ms:
?? .oracle/briefs/
?? .oracle/checkins/batch-1-review.txt
?? .oracle/checkins/batch-1.md
?? .oracle/checkins/batch-2-rereview.txt
?? .oracle/checkins/batch-2-review.txt
?? .oracle/checkins/batch-2.md
?? .oracle/checkins/batch-3-rereview.txt
?? .oracle/checkins/batch-3-review.txt
?? .oracle/checkins/batch-3.md
?? .oracle/checkins/batch-4-rereview.txt
?? .oracle/checkins/batch-4-review.txt
?? .oracle/checkins/batch-4.md
?? .oracle/checkins/batch-5-rereview.txt
?? .oracle/checkins/batch-5-rereview2.txt
?? .oracle/checkins/batch-5-rereview3.txt
?? .oracle/checkins/batch-5-rereview4.txt
?? .oracle/checkins/batch-5-rereview5.txt
?? .oracle/checkins/batch-5-review.txt
?? .oracle/checkins/batch-5.md
?? .oracle/checkins/pre-execution-review.txt
?? .oracle/findings/
?? .oracle/rework/
2:   - Batches 1–7 with: T1–T11 from the plan (unchanged acceptances), T12 `[XHARD]` "final oracle review gates commit/push", T13 `normal` "sync: push HEAD:oracle-run, open worktree" — plus Batch 3 split into checkpoints (T4 checkpoint, then T5), and Batch 5's discriminator gate as its first task (T8a "freeze standalone/cloud authority discriminator + state-dir convention; escalate if primitives can't express fail-closed" before T8b).
20:4. **Blocking — custody discriminator remains unresolved before implementation.** `.oracle/plan.md §Residual open questions`; `.oracle/tasklist.md Batch 5`. The exact standalone/cloud authority discriminator is explicitly still open, yet T8 proceeds directly to implementation. **Suggested fix:** insert a Sol/oracle gate to freeze the discriminator and state-directory convention; halt and escalate if existing primitives cannot support it fail-closed.
53:## Batch 5 — Establish standalone custody honestly
      15 .oracle/checkins/batch-5-rereview5.txt
      41 .oracle/rework/batch-5-attempt-1.md
      25 .oracle/rework/batch-5-attempt-2.md
      25 .oracle/rework/batch-5-attempt-3.md
      25 .oracle/rework/batch-5-attempt-4.md
      27 .oracle/rework/batch-5-attempt-5.md
     158 total
 .oracle/status.md                                  |  14 +-
 .../megaplan/cloud/runtime_attestation.py          | 574 ++++++++++++++++-
 arnold_pipelines/megaplan/resident/cli.py          | 131 +++-
 docs/custom-resident-agents.md                     |  76 +++
 tests/cloud/test_runtime_attestation.py            |  41 +-
 tests/cloud/test_standalone_runtime_attestation.py | 706 +++++++++++++++++++++
 6 files changed, 1522 insertions(+), 20 deletions(-)

exec
/bin/zsh -lc "sed -n '1,220p' .oracle/checkins/batch-5-rereview5.txt; for f in .oracle/rework/batch-5-attempt-{1,2,3,4,5}.md; do sed -n '1,220p' \""'$f"; done; sed -n '"'45,90p' .oracle/tasklist.md" in /Users/peteromalley/Documents/arnold-oracle
 succeeded in 0ms:
PASS

No findings.

- Authority is digest-covered, type-checked, and domain-separated across cloud worker refresh, validator selection, and process receipts.
- Standalone evidence is fail-closed on strict repository root, full expected HEAD, live HEAD, provenance, module/PTH/wrapper/interpreter vectors, and exact standalone authority.
- Publication/load/process paths enforce `0700` directories and `0600` objects without repairing rejected state; load paths use non-mutating resolution.
- Publication preflights all operational directories before creating any.
- Existing seed/receipt reuse requires regular non-symlink files, exact `0600`, matching canonical digest/content, and completes before pointer publication.
- Pointer bytes remain unchanged on the tampered-mode and unsafe-directory rejection paths.
- Chain/cloud provisioning changes are limited to the intended authority field and compatibility checks; no provisioning path was reworked.
- Typed non-string authority mismatches raise `CliError`, not `TypeError`.

The reported 42 standalone tests passing is consistent with the inspected implementation and regression coverage.
0
# Batch 5 rework — attempt 1

All three findings are accepted.

## 1. Worker-refresh authority bypass

**Finding + evidence:** Accepted, blocking. `refresh_runtime_launch_seed_for_worker_dispatch()` (`runtime_attestation.py:1824–1830`) returns the configured seed when `ARNOLD_RUNTIME_MANIFEST` is absent before loading it or requiring cloud-chain authority. This lets a standalone seed cross the worker-dispatch custody boundary, contrary to frozen gate §1.

**Criterion + North Star:** Batch 5/T8 requires cloud/standalone mismatches to fail closed while chain behavior remains unchanged. **Compatibility is a contract**—existing cloud runs must keep working.

**Required outcome + scope:** When a seed is configured, load it and require cloud-chain authority before the no-manifest return. Preserve `None` for no configured seed and all existing cloud refresh behavior. Focused code and tests only.

**Classification/model:** **[XHARD]**—custody-boundary correction with cloud-regression risk. `openrouter:stealth/ox-alpha`.

**Acceptance + exact validation:** Standalone seed plus absent/blank manifest raises typed `runtime_launch_attestation_mismatch`; cloud seed retains existing behavior; no seed returns `None`; manifest-present refresh remains unchanged. Run:
`python -m pytest tests/cloud/test_standalone_runtime_attestation.py::test_worker_refresh_rejects_standalone_seed_without_manifest -q`
`python -m pytest tests/cloud/test_runtime_attestation.py tests/cloud/test_standalone_runtime_attestation.py -q`

## 2. Unsafe reused state-directory permissions

**Finding + evidence:** Accepted, blocking. `standalone_runtime_launch_dir()` secures only the root; `standalone_dispatch_paths()` silently chmods reused `seeds/`, `receipts/`, and `status/`; pointer loading validates files, not parent modes; process creation can write through reused unsafe `status/`.

**Criterion + North Star:** T8 requires root-custodied state and fail-closed custody. **Compatibility is a contract**—cloud paths remain unchanged.

**Required outcome + scope:** Centrally require real, contained `0700` operational directories on every standalone publication, load, and process create/read path; reject unsafe reuse before mutation. Preserve `0600` object checks.

**Classification/model:** **[XHARD]**—multi-path custody enforcement. `openrouter:stealth/ox-alpha`.

**Acceptance + exact validation:** Parameterize each directory at `0755`; relevant operations reject it, never repair it, and leave pointer/status bytes unchanged. Fresh modes remain `0700/0600`. Run the two-file suite above.

## 3. Non-string authority crash

**Finding + evidence:** Accepted, advisory. Membership checks at `runtime_attestation.py:1867` and `:2383` allow list/dict authorities to raise raw `TypeError`.

**Criterion + North Star:** T8 fail-closed mismatch behavior; **Compatibility is a contract** through typed errors.

**Required outcome + scope:** Guard with `isinstance(authority, str)` before membership; preserve valid strings.

**Classification/model:** **normal**—mechanical validation fix. `codex:gpt-5.6-luna`.

**Acceptance + exact validation:** List/dict values raise typed mismatch, never `TypeError`; valid authorities remain unchanged. Add the focused parameterized test, then run the two-file suite.
+# Batch 5 rework — attempt 2
+
+## Direct standalone pointer load omits `status/` custody
+
+**Disposition:** Accept, blocking. `load_standalone_runtime_dispatch_pointer()` requires `seeds/` and reaches `receipts/` only through the referenced receipt, but never requires `status/`; direct loads can therefore succeed with missing or unsafe `status/`.
+
+**Required outcome:** Before reading the pointer, call `_require_standalone_operational_dir(state, name, create=False)` for `seeds`, `receipts`, and `status`. Reject missing, symlinked, non-directory, or non-`0700` operational directories without repair or mutation. Keep fresh publication/process paths and cloud behavior unchanged.
+
+**Classification/model:** **[XHARD]** — this closes a fail-closed custody bypass on a direct load boundary while preserving compatibility across fresh paths. Select `openrouter:stealth/ox-alpha`; I agree with the user-declared rationale.
+
+**Acceptance:** Extend `test_standalone_load_rejects_unsafe_reused_directory_at_0755` to cover `status`; add `test_standalone_load_rejects_missing_status_directory`. Direct pointer loads reject unsafe or missing `status/`; valid direct loads remain successful; fresh directories remain `0700`, objects remain `0600`; the focused and two-file suites are green.
+
+**Exact validation:**
+
+`python -m pytest tests/cloud/test_standalone_runtime_attestation.py::test_standalone_load_rejects_unsafe_reused_directory_at_0755 -q`
+
+`python -m pytest tests/cloud/test_standalone_runtime_attestation.py::test_standalone_load_rejects_missing_status_directory -q`
+
+`python -m pytest tests/cloud/test_runtime_attestation.py tests/cloud/test_standalone_runtime_attestation.py -q`

tokens used
60,464
Created [batch-5-attempt-2.md](/Users/peteromalley/Documents/arnold-oracle/.oracle/rework/batch-5-attempt-2.md). It is 159 words and independently validated against the finding, diff, and existing tests.

No tests were run; the document specifies the required future validation commands. The repository-mandated Megaplan launcher was unavailable because all prescribed launchers lacked the `config` subcommand.
+# Batch 5 rework — attempt 3
+
+## Rejected standalone loads mutate custody state
+
+**Disposition:** Accept, blocking. `standalone_runtime_launch_dir()` creates missing parents and chmods the state directory before load/read callers invoke `_require_standalone_operational_dir(..., create=False)`, so rejection can repair or mutate reused state.
+
+**Required outcome:** Add a non-mutating standalone state resolver/validator for every load/read path. It must validate the existing root, state, and operational directories without `mkdir`, `chmod`, or writes. Preserve creation/normalization only for true publication and process-create paths; cloud behavior remains unchanged.
+
+**Classification/model:** **[XHARD]** — this is a fail-closed custody-boundary split spanning direct loads and configured process reads. Select `openrouter:stealth/ox-alpha`; I agree with the user declaration.
+
+**Acceptance:** `test_standalone_load_rejection_does_not_mutate_filesystem` proves rejected loads create no directories and change no modes, including missing parents/state/children and unsafe existing state. Valid loads are unchanged. Publication/process-create still create directories at `0700` and objects at `0600`. Focused and two-file suites are green.
+
+**Exact validation:**
+
+`python -m pytest tests/cloud/test_standalone_runtime_attestation.py::test_standalone_load_rejection_does_not_mutate_filesystem -q`
+
+`python -m pytest tests/cloud/test_standalone_runtime_attestation.py::test_publication_pointer_is_content_addressed_and_rejects_tampering -q`
+
+`python -m pytest tests/cloud/test_runtime_attestation.py tests/cloud/test_standalone_runtime_attestation.py -q`

tokens used
42,667
Created [batch-5-attempt-3.md](/Users/peteromalley/Documents/arnold-oracle/.oracle/rework/batch-5-attempt-3.md).

It is 161 words, includes all requested criteria and exact validation commands, and was independently validated after delegated inspection. No test suites were run; this task only emits the rework triage.
+# Batch 5 rework — attempt 4
+
+## Publication rejection partially mutates custody state
+
+**Disposition:** Accept, blocking. Independently reproduced: with missing `seeds`/`receipts` and an existing unsafe-`0755` `status`, `standalone_dispatch_paths()` creates both missing siblings before rejecting `status`.
+
+**Required outcome:** Use preflight-then-create ordering. First preflight all three operational directories non-mutating (`create=False`); absence must be recorded as eligible for later creation, while every existing symlink, non-directory, unreadable, or non-`0700` entry rejects. Preserve strict missing-directory rejection for load/read callers. Only after all three preflights pass may a second pass create missing entries (`create=True`). Fresh publication behavior remains unchanged.
+
+**Classification/model:** **[XHARD]** — fail-closed custody requires transaction-like validation across multiple paths without weakening strict read semantics. Select `openrouter:stealth/ox-alpha`; I agree with the declared routing.
+
+**Acceptance:** With unsafe-`0755` `status` and missing `seeds`/`receipts`, publication rejects and creates nothing; both siblings remain absent and existing modes remain unchanged. A fresh path still creates all three at `0700`; published objects remain `0600`. Add a regression test asserting zero directories created on rejection. Focused and two-file suites are green.
+
+**Exact validation:**
+
+`python -m pytest tests/cloud/test_standalone_runtime_attestation.py::test_standalone_publication_rejection_does_not_create_missing_siblings -q`
+
+`python -m pytest tests/cloud/test_standalone_runtime_attestation.py::test_publication_pointer_is_content_addressed_and_rejects_tampering -q`
+
+`python -m pytest tests/cloud/test_runtime_attestation.py tests/cloud/test_standalone_runtime_attestation.py -q`

tokens used
39,707
Created [batch-5-attempt-4.md](/Users/peteromalley/Documents/arnold-oracle/.oracle/rework/batch-5-attempt-4.md).

Validated against the source and delegated independent review. The artifact is 185 words and includes the exact acceptance criteria and validation commands. No tests were run; this task only emits the rework triage.
+# Batch 5 rework — attempt 5
+
+## Unsafe idempotent object reuse can advance the pointer
+
+**Disposition:** Accept, blocking. `FileExistsError` reuse currently compares parsed JSON only; a matching seed or receipt with tampered mode can pass reuse, after which `_atomic_write()` advances the pointer before the post-publication loader rejects it.
+
+**Required outcome:** Accept an existing seed or receipt only when it is a regular, non-symlink file with mode exactly `0600` and its digest matches the expected immutable object. Validate both reused objects before any pointer update. Otherwise reject without repair, `chmod`, or mutation.
+
+**Classification/model:** **[XHARD]** — this is transaction-ordering across two immutable custody objects and one atomic mutable pointer, with fail-closed filesystem semantics. Select `openrouter:stealth/ox-alpha`; I agree with the declared routing.
+
+**Acceptance:** For either an existing seed or receipt whose content matches but mode is tampered (for example `0644`), publication rejects; pointer bytes are unchanged and no file or mode is mutated. Valid `0600` idempotent reuse remains unchanged. The named regression `test_standalone_publication_rejects_unsafe_mode_reuse_without_advancing_pointer` and focused/two-file suites are green.
+
+**Exact validation:**
+
+`python -m pytest tests/cloud/test_standalone_runtime_attestation.py::test_standalone_publication_rejects_unsafe_mode_reuse_without_advancing_pointer -q`
+
+`python -m pytest tests/cloud/test_standalone_runtime_attestation.py -q`
+
+`python -m pytest tests/cloud/test_runtime_attestation.py tests/cloud/test_standalone_runtime_attestation.py -q`

tokens used
51,563
Created [batch-5-attempt-5.md](/Users/peteromalley/Documents/arnold-oracle/.oracle/rework/batch-5-attempt-5.md).

Validated against the source and delegated review: 184 words, all requested criteria and exact commands included. Tests were not run; this task only emits triage.

Megaplan fallback was necessary because all supported launchers reject the mandated `config show` command.

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
codex
The prior findings form a coherent hardening sequence. I’m now checking that each fix is actually present in the final implementation—not merely documented—and that no later change reopened an earlier boundary.
exec
/bin/zsh -lc 'git diff --find-renames --find-copies 210bb6e078..HEAD -- arnold_pipelines/megaplan/cloud/runtime_attestation.py arnold_pipelines/megaplan/resident/cli.py' in /Users/peteromalley/Documents/arnold-oracle
 succeeded in 0ms:
diff --git a/arnold_pipelines/megaplan/cloud/runtime_attestation.py b/arnold_pipelines/megaplan/cloud/runtime_attestation.py
index 9fba0f1524..8b4cd90acc 100644
--- a/arnold_pipelines/megaplan/cloud/runtime_attestation.py
+++ b/arnold_pipelines/megaplan/cloud/runtime_attestation.py
@@ -3,6 +3,7 @@
 from __future__ import annotations
 
 import argparse
+from datetime import datetime
 import fcntl
 import hashlib
 import importlib
@@ -25,6 +26,15 @@ from arnold_pipelines.megaplan.types import CliError
 
 
 RUNTIME_LAUNCH_SEED_SCHEMA = "arnold.megaplan.runtime_launch_seed.v1"
+RUNTIME_LAUNCH_CLOUD_AUTHORITY = "arnold.megaplan.runtime-launch/cloud-chain/v1"
+RUNTIME_LAUNCH_STANDALONE_AUTHORITY = "arnold.megaplan.runtime-launch/standalone-resident/v1"
+RUNTIME_LAUNCH_AUTHORITIES = frozenset(
+    {RUNTIME_LAUNCH_CLOUD_AUTHORITY, RUNTIME_LAUNCH_STANDALONE_AUTHORITY}
+)
+# Short aliases used by adapters and tests; the serialized values above are
+# the compatibility contract.
+CLOUD_CHAIN_AUTHORITY = RUNTIME_LAUNCH_CLOUD_AUTHORITY
+STANDALONE_RESIDENT_AUTHORITY = RUNTIME_LAUNCH_STANDALONE_AUTHORITY
 RUNTIME_PROCESS_ATTESTATION_SCHEMA = "arnold.megaplan.runtime_process_attestation.v1"
 # Codex fix 2026-08-17: the mutable per-runtime seed slot is retired. Seeds
 # are content-addressed per accepted generation and a separate atomic pointer
@@ -32,6 +42,13 @@ RUNTIME_PROCESS_ATTESTATION_SCHEMA = "arnold.megaplan.runtime_process_attestatio
 # retain the absolute immutable seed path they were dispatched with.
 DISPATCH_POINTER_SCHEMA = "arnold.megaplan.runtime_dispatch_pointer.v1"
 DISPATCH_CURRENT_FILENAME = "dispatch-current.json"
+STANDALONE_DISPATCH_POINTER_SCHEMA = (
+    "arnold.megaplan.standalone_runtime_dispatch_pointer.v1"
+)
+STANDALONE_ATTESTATION_RECEIPT_SCHEMA = (
+    "arnold.megaplan.standalone_runtime_attestation_receipt.v1"
+)
+STANDALONE_RUNTIME_LAUNCH_RELATIVE = Path(".megaplan/resident/runtime-launch")
 RUNTIME_ATTESTATION_ERROR = "runtime_launch_attestation_mismatch"
 # Canonical box-side paths for the per-epic launch-seed build (G14): the
 # supervisor prepare receipt, the box hot-env file, and the launch-seed store
@@ -746,6 +763,7 @@ def build_runtime_launch_seed(
             errors.append(f"mixed_revision_module:{mod.get('module')}")
     core = {
         "schema": RUNTIME_LAUNCH_SEED_SCHEMA,
+        "authority": RUNTIME_LAUNCH_CLOUD_AUTHORITY,
         "expected_root": str(root),
         "expected_revision": expected_revision,
         # Codex fix 2026-08-17: the seed is bound to ONE accepted manifest
@@ -962,6 +980,8 @@ def _launch_seed_current(
         _verify_seed_digest(seed)
     except CliError:
         return False
+    if seed.get("authority") != RUNTIME_LAUNCH_CLOUD_AUTHORITY:
+        return False
     # Codex fix 2026-08-17: a seed built for an EARLIER accepted generation
     # is never reused to dispatch after a promotion. When *generation* is
     # provided it must equal the seed's bound manifest_generation.
@@ -1014,7 +1034,9 @@ def _launch_seed_current(
     )
 
 
-def _exclusive_write_json(path: Path, payload: Mapping[str, Any]) -> None:
+def _exclusive_write_json(
+    path: Path, payload: Mapping[str, Any], *, mode: int = 0o644
+) -> None:
     """Write *payload* to *path* with exclusive-create (``O_EXCL``) semantics.
 
     Codex fix 2026-08-17: an issued generation seed is IMMUTABLE. The file is
@@ -1028,7 +1050,7 @@ def _exclusive_write_json(path: Path, payload: Mapping[str, Any]) -> None:
     fd = os.open(
         str(path),
         os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
-        0o644,
+        mode,
     )
     try:
         with os.fdopen(fd, "w", encoding="utf-8") as handle:
@@ -1044,6 +1066,470 @@ def _exclusive_write_json(path: Path, payload: Mapping[str, Any]) -> None:
         raise
 
 
+def standalone_runtime_launch_dir(expected_root: Path, *, create: bool = True) -> Path:
+    """Return the root-custodied resident launch state directory.
+
+    The root is intentionally resolved strictly: a resident attestation is
+    never issued for a missing checkout or through a symlinked repository.
+
+    ``create=False`` is the read-only contract for every load/read path: the
+    existing root, state, and parent custody chain are validated without any
+    ``mkdir``, ``chmod``, or write, so a rejected load can never repair or
+    normalize reused state.  Creation and ``0700`` normalization remain
+    exclusive to true publication and process-create callers (the default).
+    """
+    try:
+        root = expected_root.expanduser().resolve(strict=True)
+    except OSError as exc:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "resident repository root is unavailable") from exc
+    state = root / STANDALONE_RUNTIME_LAUNCH_RELATIVE
+    try:
+        state.relative_to(root)
+    except ValueError as exc:  # defensive; the relative constant is fixed
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch state escaped repository root") from exc
+    chain = (root / ".megaplan", root / ".megaplan" / "resident", state)
+    if not create:
+        # Validate-only: fail closed on missing, symlinked, non-directory, or
+        # permissive custody state; never touch the filesystem.
+        for directory in chain:
+            if directory.is_symlink():
+                raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch state contains a symlink")
+            try:
+                info = directory.stat()
+            except FileNotFoundError as exc:
+                raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch state is unavailable") from None
+            except OSError as exc:
+                raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch state is unreadable") from exc
+            if not stat.S_ISDIR(info.st_mode):
+                raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch state is not a real directory")
+        if stat.S_IMODE(state.stat().st_mode) != 0o700:
+            raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch state permissions are unsafe")
+        return state
+    for directory in chain:
+        if directory.exists() and directory.is_symlink():
+            raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch state contains a symlink")
+        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
+        if directory == state:
+            try:
+                directory.chmod(0o700)
+            except OSError as exc:
+                raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch state permissions are unsafe") from exc
+    return state
+
+
+def _standalone_path(root: Path, relative: str) -> Path:
+    """Resolve a path below the resident state, rejecting symlink escapes."""
+    state = standalone_runtime_launch_dir(root)
+    path = Path(relative)
+    candidate = path if path.is_absolute() else state / path
+    try:
+        candidate.relative_to(state)
+    except ValueError as exc:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch path escaped state directory") from exc
+    # Inspect the lexical candidate before resolving it: resolving first would
+    # silently turn a final symlink into its target and erase the custody fact.
+    current = state
+    for part in candidate.relative_to(state).parts:
+        current = current / part
+        if current.is_symlink():
+            raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch path contains a symlink")
+    resolved = candidate.resolve(strict=False)
+    try:
+        resolved.relative_to(state.resolve(strict=True))
+    except ValueError as exc:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch path escaped state directory") from exc
+    return resolved
+
+
+def _git_toplevel(root: Path) -> str:
+    result = subprocess.run(
+        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
+        check=False,
+        capture_output=True,
+        text=True,
+    )
+    return result.stdout.strip() if result.returncode == 0 else ""
+
+
+def _validate_full_revision(value: str, *, label: str = "revision") -> str:
+    revision = str(value or "")
+    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", revision):
+        raise CliError(RUNTIME_ATTESTATION_ERROR, f"{label} must be a full hexadecimal Git OID")
+    return revision
+
+
+def _standalone_admission(root_value: Path, expected_revision: str) -> tuple[Path, str, str]:
+    try:
+        root = root_value.expanduser().resolve(strict=True)
+    except OSError as exc:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "resident repository root is unavailable") from exc
+    top = _git_toplevel(root)
+    try:
+        top_path = Path(top).resolve(strict=True)
+    except OSError as exc:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "resident repository is not a Git checkout") from exc
+    if top_path != root:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "Git top-level does not equal resident repository root")
+    expected = _validate_full_revision(expected_revision, label="expected HEAD")
+    live = _git_revision(root)
+    if live != expected:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "resident repository HEAD does not match expected HEAD")
+    return root, expected, live
+
+
+def build_standalone_runtime_launch_seed(
+    *,
+    expected_root: Path,
+    expected_revision: str,
+    generated_at: str | None = None,
+) -> dict[str, Any]:
+    """Build a domain-separated resident seed from local runtime evidence."""
+    root, expected, live = _standalone_admission(expected_root, expected_revision)
+    provenance = runtime_provenance(expected_root=root, expected_revision=expected)
+    modules, module_errors = _module_vector(root)
+    pth, pth_errors = _pth_vector(root)
+    wrappers, wrapper_errors = _wrapper_vector(root)
+    errors = [*(provenance.get("errors") or []), *module_errors, *pth_errors, *wrapper_errors]
+    if not provenance.get("ok"):
+        errors.append("runtime_provenance_not_ready")
+    core = {
+        "schema": RUNTIME_LAUNCH_SEED_SCHEMA,
+        "authority": RUNTIME_LAUNCH_STANDALONE_AUTHORITY,
+        "expected_root": str(root),
+        "expected_revision": expected,
+        "live_revision": live,
+        "generated_at": generated_at or now_utc(),
+        "runtime_provenance": provenance,
+        "loaded_modules": modules,
+        "interpreter": _interpreter_vector(
+            direct_url=(provenance.get("direct_url") if isinstance(provenance.get("direct_url"), Mapping) else {})
+        ),
+        "site_pth": pth,
+        "wrappers": wrappers,
+        "errors": sorted(set(errors)),
+        "ready": not errors,
+    }
+    return {**core, "content_sha256": _canonical_sha256(core)}
+
+
+def validate_standalone_runtime_launch_seed(
+    seed: Mapping[str, Any], *, component: str = "resident"
+) -> dict[str, Any]:
+    """Validate only resident evidence; this path never reads cloud artifacts."""
+    _verify_seed_digest(seed)
+    if seed.get("authority") != RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "runtime launch seed authority is not standalone-resident")
+    if component != "resident":
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone runtime launch seed is resident-only")
+    for field in ("manifest_sha256", "marker", "supervisor_receipt", "supervisor_runtime", "hot_env", "chain_runtime_binding"):
+        if seed.get(field):
+            raise CliError(RUNTIME_ATTESTATION_ERROR, f"standalone seed contains cloud field: {field}")
+    required_types = {
+        "expected_root": str,
+        "expected_revision": str,
+        "live_revision": str,
+        "generated_at": str,
+        "runtime_provenance": Mapping,
+        "loaded_modules": list,
+        "interpreter": Mapping,
+        "site_pth": list,
+        "wrappers": list,
+        "errors": list,
+    }
+    for field, expected_type in required_types.items():
+        if not isinstance(seed.get(field), expected_type):
+            raise CliError(
+                RUNTIME_ATTESTATION_ERROR,
+                f"standalone runtime launch seed has invalid {field}",
+            )
+    if type(seed.get("ready")) is not bool:
+        raise CliError(
+            RUNTIME_ATTESTATION_ERROR,
+            "standalone runtime launch seed has invalid ready state",
+        )
+    try:
+        root, expected, live = _standalone_admission(Path(str(seed.get("expected_root") or "")), str(seed.get("expected_revision") or ""))
+    except CliError:
+        raise
+    if str(seed.get("expected_root") or "") != str(root) or str(seed.get("expected_revision") or "") != expected:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone runtime attestation root or revision changed")
+    if str(seed.get("live_revision") or "") != live:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone runtime live revision changed")
+    generated_at = str(seed.get("generated_at") or "")
+    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", generated_at):
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone runtime attestation timestamp is invalid")
+    try:
+        parsed_generated_at = datetime.fromisoformat(
+            generated_at.removesuffix("Z") + "+00:00"
+        )
+    except ValueError as exc:
+        raise CliError(
+            RUNTIME_ATTESTATION_ERROR,
+            "standalone runtime attestation timestamp is invalid",
+        ) from exc
+    if parsed_generated_at.utcoffset() is None or parsed_generated_at.utcoffset().total_seconds() != 0:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone runtime attestation timestamp is invalid")
+    provenance = runtime_provenance(expected_root=root, expected_revision=expected)
+    if not provenance.get("ok") or provenance != seed.get("runtime_provenance"):
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone runtime provenance changed")
+    modules, module_errors = _module_vector(root)
+    pth, pth_errors = _pth_vector(root)
+    wrappers, wrapper_errors = _wrapper_vector(root)
+    interpreter = _interpreter_vector(
+        direct_url=(provenance.get("direct_url") if isinstance(provenance.get("direct_url"), Mapping) else {})
+    )
+    if module_errors or modules != seed.get("loaded_modules"):
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone loaded module vector changed")
+    if pth_errors or pth != seed.get("site_pth"):
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone site .pth vector changed")
+    if wrapper_errors or wrappers != seed.get("wrappers"):
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone wrapper vector changed")
+    if interpreter != seed.get("interpreter"):
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone interpreter identity changed")
+    if not bool(seed.get("ready")) or seed.get("errors"):
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone runtime launch seed was not release-ready")
+    return {
+        "status": "ready",
+        "seed_sha256": seed["content_sha256"],
+        "authority": RUNTIME_LAUNCH_STANDALONE_AUTHORITY,
+        "expected_root": str(root),
+        "expected_revision": expected,
+        "runtime_vector_sha256": runtime_vector_sha256(seed),
+    }
+
+
+def _inspect_standalone_operational_dir(state: Path, name: str) -> bool:
+    """Non-mutating check: True when present and safe, False when absent.
+
+    Any existing symlink, non-directory, unreadable entry, or mode other
+    than ``0700`` rejects; absence alone is not an error so callers can
+    record the entry as eligible for later creation.
+    """
+    directory = state / name
+    try:
+        directory.relative_to(state)
+    except ValueError as exc:  # defensive; *name* is a fixed component
+        raise CliError(
+            RUNTIME_ATTESTATION_ERROR,
+            f"resident {name} directory escaped state directory",
+        ) from exc
+    if directory.is_symlink():
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch state contains a symlink")
+    if directory.exists() and not directory.is_dir():
+        raise CliError(RUNTIME_ATTESTATION_ERROR, f"resident {name} directory is not a real directory")
+    try:
+        info = directory.stat()
+    except FileNotFoundError:
+        return False
+    except OSError as exc:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, f"resident {name} directory is unreadable") from exc
+    if stat.S_IMODE(info.st_mode) != 0o700:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, f"resident {name} directory permissions are unsafe")
+    return True
+
+
+def _require_standalone_operational_dir(state: Path, name: str, *, create: bool) -> None:
+    """Require a real, state-contained ``0700`` operational directory.
+
+    Reused directories are validated, never repaired: an existing symlink,
+    non-directory, or permissive mode fails closed before any seed, receipt,
+    pointer, or attestation bytes change.  Only freshly created directories
+    are normalized to ``0700``.
+    """
+    if _inspect_standalone_operational_dir(state, name):
+        return
+    if not create:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, f"resident {name} directory is unavailable")
+    (state / name).mkdir(mode=0o700)
+    (state / name).chmod(0o700)
+
+
+def standalone_dispatch_paths(root: Path, *, head: str, seed_sha256: str) -> dict[str, Path]:
+    state = standalone_runtime_launch_dir(root)
+    expected = _validate_full_revision(head, label="expected HEAD")
+    # Preflight every operational directory non-mutating before creating any:
+    # an unsafe reused entry rejects while custody state still lacks siblings.
+    missing = [
+        name
+        for name in ("seeds", "receipts", "status")
+        if not _inspect_standalone_operational_dir(state, name)
+    ]
+    for name in missing:
+        _require_standalone_operational_dir(state, name, create=True)
+    return {
+        "seed": _standalone_path(root, f"seeds/standalone-{expected}-{seed_sha256}.json"),
+        "pointer": _standalone_path(root, "seeds/dispatch-current.json"),
+        "receipts": _standalone_path(root, "receipts"),
+        "status": _standalone_path(root, "status/resident.runtime-process-attestation.json"),
+    }
+
+
+def build_standalone_runtime_attestation_receipt(
+    *, seed: Mapping[str, Any], seed_path: Path, pointer_path: Path, generated_at: str | None = None
+) -> dict[str, Any]:
+    _verify_seed_digest(seed)
+    if seed.get("authority") != RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "receipt requires standalone-resident seed")
+    core = {
+        "schema": STANDALONE_ATTESTATION_RECEIPT_SCHEMA,
+        "authority": RUNTIME_LAUNCH_STANDALONE_AUTHORITY,
+        "root": str(Path(str(seed["expected_root"])).resolve(strict=True)),
+        "expected_head": str(seed["expected_revision"]),
+        "live_head": str(seed.get("live_revision") or ""),
+        "generated_at": generated_at or str(seed.get("generated_at") or now_utc()),
+        "seed_path": str(seed_path.resolve(strict=False)),
+        "seed_sha256": str(seed["content_sha256"]),
+        "pointer_path": str(pointer_path.resolve(strict=False)),
+    }
+    return {**core, "content_sha256": _canonical_sha256(core)}
+
+
+def load_standalone_runtime_dispatch_pointer(root: Path) -> dict[str, Any]:
+    state = standalone_runtime_launch_dir(root, create=False)
+    for name in ("seeds", "receipts", "status"):
+        _require_standalone_operational_dir(state, name, create=False)
+    pointer_path = state / "seeds" / "dispatch-current.json"
+    if pointer_path.is_symlink() or pointer_path.parent.is_symlink():
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer is a symlink")
+    try:
+        if stat.S_IMODE(pointer_path.stat().st_mode) != 0o600:
+            raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer permissions are unsafe")
+    except OSError:
+        pass
+    pointer = _json_file(pointer_path, label="standalone runtime dispatch pointer")
+    if pointer.get("schema") != STANDALONE_DISPATCH_POINTER_SCHEMA or pointer.get("authority") != RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer authority is invalid")
+    resolved_root = Path(str(root)).expanduser().resolve(strict=True)
+    if str(pointer.get("root") or "") != str(resolved_root):
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer root mismatch")
+    seed_path = Path(str(pointer.get("seed_path") or ""))
+    receipt_path = Path(str(pointer.get("receipt_path") or ""))
+    for path in (seed_path, receipt_path):
+        if not path.is_absolute() or not path.exists() or path.is_symlink():
+            raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer path is unsafe")
+        try:
+            if stat.S_IMODE(path.stat().st_mode) != 0o600:
+                raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch object permissions are unsafe")
+        except OSError as exc:
+            raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch object is unreadable") from exc
+        state = standalone_runtime_launch_dir(resolved_root, create=False)
+        try:
+            lexical = path.relative_to(state)
+        except ValueError as exc:
+            raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer escaped state directory") from exc
+        _require_standalone_operational_dir(state, lexical.parts[0], create=False)
+        current = state
+        for part in lexical.parts:
+            current = current / part
+            if current.is_symlink():
+                raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch path contains a symlink")
+        try:
+            path.resolve(strict=True).relative_to(state.resolve(strict=True))
+        except ValueError as exc:
+            raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer escaped state directory") from exc
+    seed = _json_file(seed_path, label="standalone runtime launch seed")
+    receipt = _json_file(receipt_path, label="standalone runtime attestation receipt")
+    _verify_seed_digest(seed)
+    if seed.get("content_sha256") != pointer.get("seed_sha256"):
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch seed digest mismatch")
+    if seed.get("expected_revision") != pointer.get("expected_revision"):
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch seed revision mismatch")
+    if receipt.get("content_sha256") != pointer.get("receipt_sha256"):
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch receipt digest mismatch")
+    receipt_core = {key: value for key, value in receipt.items() if key != "content_sha256"}
+    if receipt.get("schema") != STANDALONE_ATTESTATION_RECEIPT_SCHEMA or receipt.get("authority") != RUNTIME_LAUNCH_STANDALONE_AUTHORITY or receipt.get("content_sha256") != _canonical_sha256(receipt_core):
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone attestation receipt is invalid")
+    if receipt.get("seed_path") != str(seed_path.resolve(strict=False)) or receipt.get("seed_sha256") != seed.get("content_sha256"):
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone attestation receipt seed binding is invalid")
+    if receipt.get("pointer_path") != str(pointer_path.resolve(strict=False)):
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone attestation receipt pointer binding is invalid")
+    if (
+        receipt.get("root") != pointer.get("root")
+        or receipt.get("expected_head") != pointer.get("expected_revision")
+        or receipt.get("live_head") != seed.get("live_revision")
+        or receipt.get("generated_at") != seed.get("generated_at")
+        or pointer.get("generated_at") != seed.get("generated_at")
+    ):
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone attestation receipt root/revision binding is invalid")
+    validate_standalone_runtime_launch_seed(seed)
+    return pointer
+
+
+def _verify_reused_immutable_object(
+    path: Path, payload: Mapping[str, Any], *, label: str
+) -> None:
+    """Accept a ``FileExistsError`` reuse only when custody is intact.
+
+    The existing object must be a regular non-symlink file with mode exactly
+    ``0600`` whose canonical digest matches the expected immutable object.
+    Anything else rejects without repair, chmod, or mutation so the dispatch
+    pointer can never advance onto a tampered custody object.
+    """
+    try:
+        st = path.lstat()
+    except OSError as exc:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, f"standalone {label} is unreadable") from exc
+    if path.is_symlink() or not stat.S_ISREG(st.st_mode):
+        raise CliError(RUNTIME_ATTESTATION_ERROR, f"standalone {label} is not a regular file")
+    if stat.S_IMODE(st.st_mode) != 0o600:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, f"standalone {label} permissions are unsafe")
+    existing = _json_file(path, label=f"standalone runtime {label}")
+    expected_digest = str(payload.get("content_sha256") or "")
+    existing_core = {key: value for key, value in existing.items() if key != "content_sha256"}
+    if (
+        existing.get("content_sha256") != expected_digest
+        or _canonical_sha256(existing_core) != expected_digest
+        or existing != dict(payload)
+    ):
+        raise CliError(RUNTIME_ATTESTATION_ERROR, f"immutable standalone {label} collision")
+
+
+def write_standalone_runtime_publication(
+    *, seed: Mapping[str, Any], seed_path: Path, root: Path, generated_at: str | None = None
+) -> dict[str, Any]:
+    """Publish a resident seed, issuance receipt, and dispatch pointer."""
+    validate_standalone_runtime_launch_seed(seed)
+    root, expected, live = _standalone_admission(root, str(seed.get("expected_revision") or ""))
+    if str(seed.get("expected_root") or "") != str(root) or live != str(seed.get("live_revision") or ""):
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone seed changed during publication")
+    paths = standalone_dispatch_paths(root, head=expected, seed_sha256=str(seed["content_sha256"]))
+    if paths["seed"].resolve(strict=False) != seed_path.resolve(strict=False):
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone seed path is not root-custodied")
+    try:
+        _exclusive_write_json(paths["seed"], seed, mode=0o600)
+    except FileExistsError:
+        _verify_reused_immutable_object(paths["seed"], seed, label="launch seed")
+    receipt = build_standalone_runtime_attestation_receipt(
+        seed=seed, seed_path=paths["seed"], pointer_path=paths["pointer"], generated_at=generated_at
+    )
+    receipt_path = _standalone_path(
+        root, f"receipts/{receipt['content_sha256']}.json"
+    )
+    try:
+        _exclusive_write_json(receipt_path, receipt, mode=0o600)
+    except FileExistsError:
+        _verify_reused_immutable_object(receipt_path, receipt, label="attestation receipt")
+    pointer = {
+        "schema": STANDALONE_DISPATCH_POINTER_SCHEMA,
+        "authority": RUNTIME_LAUNCH_STANDALONE_AUTHORITY,
+        "seed_path": str(paths["seed"].resolve(strict=False)),
+        "receipt_path": str(receipt_path.resolve(strict=False)),
+        "root": str(root),
+        "expected_revision": expected,
+        "generated_at": str(seed.get("generated_at") or generated_at or now_utc()),
+        "seed_sha256": str(seed["content_sha256"]),
+        "receipt_sha256": str(receipt["content_sha256"]),
+    }
+    if paths["pointer"].is_symlink():
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer is a symlink")
+    _atomic_write(paths["pointer"], pointer)
+    # Re-read and validate every published object before handing it to a caller.
+    published = load_standalone_runtime_dispatch_pointer(root)
+    if published != pointer:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "published standalone dispatch pointer changed")
+    return {"seed_path": paths["seed"], "receipt_path": receipt_path, "pointer_path": paths["pointer"], "receipt": receipt, "pointer": pointer}
+
+
 def _write_dispatch_pointer(
     store_dir: Path,
     seed_path: Path,
@@ -1437,9 +1923,16 @@ def refresh_runtime_launch_seed_for_worker_dispatch() -> Path | None:
     """
     manifest_value = str(os.environ.get("ARNOLD_RUNTIME_MANIFEST") or "").strip()
     current_path = configured_seed_path()
-    if not manifest_value or current_path is None:
-        return current_path
+    if current_path is None:
+        return None
+    # Custody boundary: a configured seed must prove cloud-chain authority
+    # BEFORE any early return, including the no-manifest one, so a
+    # standalone-resident seed cannot cross into worker dispatch unchallenged.
     current = _json_file(current_path, label="runtime launch seed")
+    if current.get("authority") != RUNTIME_LAUNCH_CLOUD_AUTHORITY:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "worker dispatch requires a cloud-chain runtime seed")
+    if not manifest_value:
+        return current_path
     input_paths = current.get("input_paths")
     input_paths = input_paths if isinstance(input_paths, Mapping) else {}
     chain_spec_value = str(input_paths.get("chain_spec") or "").strip()
@@ -1474,9 +1967,14 @@ def refresh_runtime_launch_seed_for_worker_dispatch() -> Path | None:
 
 def _verify_seed_digest(seed: Mapping[str, Any]) -> None:
     core = {key: value for key, value in seed.items() if key != "content_sha256"}
-    if seed.get("schema") != RUNTIME_LAUNCH_SEED_SCHEMA or seed.get(
-        "content_sha256"
-    ) != _canonical_sha256(core):
+    authority = seed.get("authority")
+    if (
+        seed.get("schema") != RUNTIME_LAUNCH_SEED_SCHEMA
+        or not isinstance(authority, str)
+        or authority not in RUNTIME_LAUNCH_AUTHORITIES
+        or not isinstance(seed.get("content_sha256"), str)
+        or seed.get("content_sha256") != _canonical_sha256(core)
+    ):
         raise CliError(
             RUNTIME_ATTESTATION_ERROR, "runtime launch seed digest is invalid"
         )
@@ -1523,6 +2021,11 @@ def validate_runtime_launch_seed(
     """
 
     _verify_seed_digest(seed)
+    authority = seed.get("authority")
+    if authority == RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
+        return validate_standalone_runtime_launch_seed(seed, component=component)
+    if authority != RUNTIME_LAUNCH_CLOUD_AUTHORITY:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "runtime launch seed authority is invalid")
     if not bool(seed.get("ready")) or seed.get("errors"):
         raise CliError(
             RUNTIME_ATTESTATION_ERROR,
@@ -1825,6 +2328,7 @@ def create_runtime_process_attestation(
         )
     core = {
         "schema": RUNTIME_PROCESS_ATTESTATION_SCHEMA,
+        "authority": seed.get("authority"),
         "component": component,
         "seed_sha256": validation["seed_sha256"],
         "runtime_vector_sha256": validation["runtime_vector_sha256"],
@@ -1851,10 +2355,19 @@ def validate_runtime_process_attestation(
     manifest, the current remote head, or a newly published generation.
     """
     _verify_seed_digest(seed)
+    if (
+        seed.get("authority") == RUNTIME_LAUNCH_STANDALONE_AUTHORITY
+        and component != "resident"
+    ):
+        raise CliError(
+            RUNTIME_ATTESTATION_ERROR,
+            "standalone runtime process attestation is resident-only",
+        )
     core = {
         key: attestation.get(key)
         for key in (
             "schema",
+            "authority",
             "component",
             "seed_sha256",
             "runtime_vector_sha256",
@@ -1863,6 +2376,7 @@ def validate_runtime_process_attestation(
     }
     if (
         attestation.get("schema") != RUNTIME_PROCESS_ATTESTATION_SCHEMA
+        or attestation.get("authority") != seed.get("authority")
         or attestation.get("content_sha256") != _canonical_sha256(core)
         or attestation.get("component") != component
         or attestation.get("seed_sha256") != seed.get("content_sha256")
@@ -1941,8 +2455,14 @@ def configured_seed_path() -> Path | None:
     return Path(value).expanduser().resolve(strict=False) if value else None
 
 
-def configured_process_attestation_path(component: str) -> Path:
+def configured_process_attestation_path(
+    component: str, *, seed: Mapping[str, Any] | None = None
+) -> Path:
     value = str(os.environ.get("MEGAPLAN_RUNTIME_PROCESS_ATTESTATION") or "").strip()
+    if seed is not None and seed.get("authority") == RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
+        return standalone_runtime_launch_dir(Path(str(seed.get("expected_root") or "")), create=False) / "status" / (
+            f"{component}.runtime-process-attestation.json"
+        )
     if value:
         return Path(value).expanduser().resolve(strict=False)
     return (
@@ -1957,6 +2477,8 @@ def require_configured_runtime_launch(
     target_pid: int | None = None,
     create: bool = False,
 ) -> dict[str, Any]:
+    raw_seed_value = str(os.environ.get("MEGAPLAN_RUNTIME_LAUNCH_SEED") or "").strip()
+    raw_seed_path = Path(raw_seed_value).expanduser() if raw_seed_value else None
     seed_path = configured_seed_path()
     if seed_path is None:
         raise CliError(
@@ -1964,8 +2486,28 @@ def require_configured_runtime_launch(
             "canonical runtime launch seed is required but missing",
         )
     seed = _json_file(seed_path, label="runtime launch seed")
+    authority = seed.get("authority")
+    if not isinstance(authority, str) or authority not in RUNTIME_LAUNCH_AUTHORITIES:
+        raise CliError(RUNTIME_ATTESTATION_ERROR, "runtime launch seed authority is invalid")
+    if authority == RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
+        if raw_seed_path is None or not raw_seed_path.is_absolute() or raw_seed_path.is_symlink():
+            raise CliError(RUNTIME_ATTESTATION_ERROR, "configured resident seed path is a symlink or missing")
+        pointer = load_standalone_runtime_dispatch_pointer(Path(str(seed.get("expected_root") or "")))
+        if Path(str(pointer.get("seed_path") or "")) != raw_seed_path:
+            raise CliError(RUNTIME_ATTESTATION_ERROR, "configured resident seed is not the published dispatch seed")
+        if pointer.get("seed_sha256") != seed.get("content_sha256"):
+            raise CliError(RUNTIME_ATTESTATION_ERROR, "configured resident seed digest does not match dispatch pointer")
     pid = target_pid or os.getpid()
-    attestation_path = configured_process_attestation_path(component)
+    attestation_path = configured_process_attestation_path(component, seed=seed)
+    if authority == RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
+        state = standalone_runtime_launch_dir(Path(str(seed.get("expected_root") or "")), create=create)
+        _require_standalone_operational_dir(state, "status", create=create)
+        if attestation_path.is_symlink():
+            raise CliError(RUNTIME_ATTESTATION_ERROR, "resident process attestation path is a symlink")
+        try:
+            attestation_path.resolve(strict=False).relative_to(state.resolve(strict=True))
+        except ValueError as exc:
+            raise CliError(RUNTIME_ATTESTATION_ERROR, "resident process attestation path escaped state directory") from exc
     if create:
         attestation = create_runtime_process_attestation(
             seed,
@@ -1974,6 +2516,18 @@ def require_configured_runtime_launch(
         )
         _atomic_write(attestation_path, attestation)
     else:
+        if authority == RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
+            try:
+                if stat.S_IMODE(attestation_path.stat().st_mode) != 0o600:
+                    raise CliError(
+                        RUNTIME_ATTESTATION_ERROR,
+                        "resident process attestation permissions are unsafe",
+                    )
+            except OSError as exc:
+                raise CliError(
+                    RUNTIME_ATTESTATION_ERROR,
+                    "runtime process attestation is unreadable",
+                ) from exc
         attestation = _json_file(
             attestation_path,
             label="runtime process attestation",
@@ -2045,4 +2599,4 @@ def main(argv: list[str] | None = None) -> int:
 
 
 if __name__ == "__main__":
-    raise SystemExit(main())
\ No newline at end of file
+    raise SystemExit(main())
diff --git a/arnold_pipelines/megaplan/resident/cli.py b/arnold_pipelines/megaplan/resident/cli.py
index 396bb0b4e7..3ab4fcbc1d 100644
--- a/arnold_pipelines/megaplan/resident/cli.py
+++ b/arnold_pipelines/megaplan/resident/cli.py
@@ -68,6 +68,27 @@ def _register_resident_subcommands(parser: argparse.ArgumentParser) -> None:
         ),
     )
 
+    attest_parser = sub.add_parser(
+        "attest",
+        help="Issue a root-custodied standalone resident runtime attestation",
+    )
+    attest_parser.add_argument(
+        "--repo-root",
+        required=True,
+        type=Path,
+        help="Repository root to admit as the standalone resident runtime",
+    )
+    attest_parser.add_argument(
+        "--expected-head",
+        required=True,
+        help="Full Git commit OID expected at admission",
+    )
+    attest_parser.add_argument(
+        "--json",
+        action="store_true",
+        help="Print the complete attestation result as JSON",
+    )
+
     scheduler_parser = sub.add_parser("scheduler-once", parents=[shared], help="Claim and process due resident jobs once")
     scheduler_parser.add_argument("--worker-id", default="resident-cli-scheduler")
 
@@ -244,7 +265,13 @@ def _register_resident_subcommands(parser: argparse.ArgumentParser) -> None:
     run_once.add_argument("--worker-id", default="resident-schedule-cli")
 
 
-def run_resident_cli(root: Path, args: argparse.Namespace) -> dict[str, Any]:
+def run_resident_cli(root: Path, args: argparse.Namespace) -> dict[str, Any] | str:
+    # ``resident attest`` is the standalone custody adapter.  It must not
+    # initialize a resident config/store (which may select a different root or
+    # create unrelated operational state) before the attestation admission.
+    if args.resident_action == "attest":
+        return _resident_attest(args)
+
     config = _resident_config(args)
     store = _resident_store(root, args)
     try:
@@ -303,6 +330,108 @@ def run_resident_cli(root: Path, args: argparse.Namespace) -> dict[str, Any]:
     raise CliError("invalid_args", f"Unknown resident action: {getattr(args, 'resident_action', None)!r}")
 
 
+_STANDALONE_ATTEST_JSON_FIELDS = (
+    "success",
+    "authority",
+    "root",
+    "expected_head",
+    "live_head",
+    "seed_path",
+    "seed_sha256",
+    "receipt_path",
+    "receipt_sha256",
+    "pointer_path",
+    "generated_at",
+)
+
+
+def _resident_attest(args: argparse.Namespace) -> dict[str, Any] | str:
+    """Issue and publish one standalone resident runtime attestation.
+
+    All custody, vector collection, publication ordering, and post-publication
+    validation live in :mod:`cloud.runtime_attestation`.  The resident CLI is
+    intentionally only the argument/output adapter: no cloud evidence is
+    synthesized here, and no pointer is touched if the canonical issuer fails.
+    """
+    from arnold_pipelines.megaplan.cloud import runtime_attestation
+
+    try:
+        seed = runtime_attestation.build_standalone_runtime_launch_seed(
+            expected_root=args.repo_root,
+            expected_revision=args.expected_head,
+        )
+        runtime_attestation.validate_standalone_runtime_launch_seed(seed)
+        root = Path(str(seed["expected_root"])).resolve(strict=True)
+        paths = runtime_attestation.standalone_dispatch_paths(
+            root,
+            head=str(seed["expected_revision"]),
+            seed_sha256=str(seed["content_sha256"]),
+        )
+        published = runtime_attestation.write_standalone_runtime_publication(
+            seed=seed,
+            seed_path=paths["seed"],
+            root=root,
+        )
+        receipt = published["receipt"]
+        pointer = published["pointer"]
+        result = {
+            "success": True,
+            "authority": receipt["authority"],
+            "root": receipt["root"],
+            "expected_head": receipt["expected_head"],
+            "live_head": receipt["live_head"],
+            "seed_path": str(paths["seed"]),
+            "seed_sha256": str(seed["content_sha256"]),
+            "receipt_path": str(published["receipt_path"]),
+            "receipt_sha256": str(receipt["content_sha256"]),
+            "pointer_path": str(published["pointer_path"]),
+            "generated_at": pointer["generated_at"],
+        }
+    except CliError as exc:
+        # Admission/custody failures are a caller/input failure for this
+        # command, even when the lower-level helper used its generic default
+        # exit code.  Publication/I/O failures are represented by ordinary
+        # exceptions and remain exit 1 below.
+        raise CliError(
+            exc.code,
+            exc.message,
+            valid_next=exc.valid_next,
+            extra=exc.extra,
+            exit_code=2,
+        ) from exc
+    except Exception as exc:
+        raise CliError(
+            "runtime_launch_attestation_error",
+            f"standalone runtime attestation failed: {exc}",
+            exit_code=1,
+        ) from exc
+
+    if not isinstance(result, Mapping):
+        raise CliError(
+            "runtime_launch_attestation_error",
+            "standalone runtime attestation issuer returned an invalid result",
+            exit_code=1,
+        )
+    # The canonical issuer returns these exact public fields.  Projecting the
+    # response here prevents internal receipt/seed details from leaking into
+    # the stable ``--json`` contract.
+    payload = {
+        field: result[field]
+        for field in _STANDALONE_ATTEST_JSON_FIELDS
+        if field in result
+    }
+    missing = [field for field in _STANDALONE_ATTEST_JSON_FIELDS if field not in payload]
+    if missing:
+        raise CliError(
+            "runtime_launch_attestation_error",
+            "standalone runtime attestation result is missing: " + ", ".join(missing),
+            exit_code=1,
+        )
+    if not args.json:
+        return str(payload["seed_path"]) + "\n"
+    return payload
+
+
 def _resident_supersede_todo(
     config: ResidentConfig, args: argparse.Namespace
 ) -> dict[str, Any]:

exec
/bin/zsh -lc 'rg -n "''^def (standalone_runtime_launch_dir|_standalone_path|build_standalone_runtime_launch_seed|validate_standalone_runtime_launch_seed|_inspect_standalone_operational_dir|_require_standalone_operational_dir|standalone_dispatch_paths|build_standalone_runtime_attestation_receipt|load_standalone_runtime_dispatch_pointer|_verify_reused_immutable_object|write_standalone_runtime_publication|refresh_runtime_launch_seed_for_worker_dispatch|_verify_seed_digest|validate_runtime_launch_seed|create_runtime_process_attestation|validate_runtime_process_attestation|configured_process_attestation_path|require_configured_runtime_launch)" arnold_pipelines/megaplan/cloud/runtime_attestation.py; sed -n '"'1060,1580p' arnold_pipelines/megaplan/cloud/runtime_attestation.py; sed -n '1910,2050p' arnold_pipelines/megaplan/cloud/runtime_attestation.py; sed -n '2310,2555p' arnold_pipelines/megaplan/cloud/runtime_attestation.py" in /Users/peteromalley/Documents/arnold-oracle
 succeeded in 0ms:
1069:def standalone_runtime_launch_dir(expected_root: Path, *, create: bool = True) -> Path:
1120:def _standalone_path(root: Path, relative: str) -> Path:
1180:def build_standalone_runtime_launch_seed(
1215:def validate_standalone_runtime_launch_seed(
1301:def _inspect_standalone_operational_dir(state: Path, name: str) -> bool:
1331:def _require_standalone_operational_dir(state: Path, name: str, *, create: bool) -> None:
1347:def standalone_dispatch_paths(root: Path, *, head: str, seed_sha256: str) -> dict[str, Path]:
1367:def build_standalone_runtime_attestation_receipt(
1387:def load_standalone_runtime_dispatch_pointer(root: Path) -> dict[str, Any]:
1458:def _verify_reused_immutable_object(
1487:def write_standalone_runtime_publication(
1916:def refresh_runtime_launch_seed_for_worker_dispatch() -> Path | None:
1968:def _verify_seed_digest(seed: Mapping[str, Any]) -> None:
2011:def validate_runtime_launch_seed(
2310:def create_runtime_process_attestation(
2340:def validate_runtime_process_attestation(
2458:def configured_process_attestation_path(
2474:def require_configured_runtime_launch(
            os.fsync(handle.fileno())
    except BaseException:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


def standalone_runtime_launch_dir(expected_root: Path, *, create: bool = True) -> Path:
    """Return the root-custodied resident launch state directory.

    The root is intentionally resolved strictly: a resident attestation is
    never issued for a missing checkout or through a symlinked repository.

    ``create=False`` is the read-only contract for every load/read path: the
    existing root, state, and parent custody chain are validated without any
    ``mkdir``, ``chmod``, or write, so a rejected load can never repair or
    normalize reused state.  Creation and ``0700`` normalization remain
    exclusive to true publication and process-create callers (the default).
    """
    try:
        root = expected_root.expanduser().resolve(strict=True)
    except OSError as exc:
        raise CliError(RUNTIME_ATTESTATION_ERROR, "resident repository root is unavailable") from exc
    state = root / STANDALONE_RUNTIME_LAUNCH_RELATIVE
    try:
        state.relative_to(root)
    except ValueError as exc:  # defensive; the relative constant is fixed
        raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch state escaped repository root") from exc
    chain = (root / ".megaplan", root / ".megaplan" / "resident", state)
    if not create:
        # Validate-only: fail closed on missing, symlinked, non-directory, or
        # permissive custody state; never touch the filesystem.
        for directory in chain:
            if directory.is_symlink():
                raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch state contains a symlink")
            try:
                info = directory.stat()
            except FileNotFoundError as exc:
                raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch state is unavailable") from None
            except OSError as exc:
                raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch state is unreadable") from exc
            if not stat.S_ISDIR(info.st_mode):
                raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch state is not a real directory")
        if stat.S_IMODE(state.stat().st_mode) != 0o700:
            raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch state permissions are unsafe")
        return state
    for directory in chain:
        if directory.exists() and directory.is_symlink():
            raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch state contains a symlink")
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if directory == state:
            try:
                directory.chmod(0o700)
            except OSError as exc:
                raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch state permissions are unsafe") from exc
    return state


def _standalone_path(root: Path, relative: str) -> Path:
    """Resolve a path below the resident state, rejecting symlink escapes."""
    state = standalone_runtime_launch_dir(root)
    path = Path(relative)
    candidate = path if path.is_absolute() else state / path
    try:
        candidate.relative_to(state)
    except ValueError as exc:
        raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch path escaped state directory") from exc
    # Inspect the lexical candidate before resolving it: resolving first would
    # silently turn a final symlink into its target and erase the custody fact.
    current = state
    for part in candidate.relative_to(state).parts:
        current = current / part
        if current.is_symlink():
            raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch path contains a symlink")
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(state.resolve(strict=True))
    except ValueError as exc:
        raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch path escaped state directory") from exc
    return resolved


def _git_toplevel(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _validate_full_revision(value: str, *, label: str = "revision") -> str:
    revision = str(value or "")
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", revision):
        raise CliError(RUNTIME_ATTESTATION_ERROR, f"{label} must be a full hexadecimal Git OID")
    return revision


def _standalone_admission(root_value: Path, expected_revision: str) -> tuple[Path, str, str]:
    try:
        root = root_value.expanduser().resolve(strict=True)
    except OSError as exc:
        raise CliError(RUNTIME_ATTESTATION_ERROR, "resident repository root is unavailable") from exc
    top = _git_toplevel(root)
    try:
        top_path = Path(top).resolve(strict=True)
    except OSError as exc:
        raise CliError(RUNTIME_ATTESTATION_ERROR, "resident repository is not a Git checkout") from exc
    if top_path != root:
        raise CliError(RUNTIME_ATTESTATION_ERROR, "Git top-level does not equal resident repository root")
    expected = _validate_full_revision(expected_revision, label="expected HEAD")
    live = _git_revision(root)
    if live != expected:
        raise CliError(RUNTIME_ATTESTATION_ERROR, "resident repository HEAD does not match expected HEAD")
    return root, expected, live


def build_standalone_runtime_launch_seed(
    *,
    expected_root: Path,
    expected_revision: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a domain-separated resident seed from local runtime evidence."""
    root, expected, live = _standalone_admission(expected_root, expected_revision)
    provenance = runtime_provenance(expected_root=root, expected_revision=expected)
    modules, module_errors = _module_vector(root)
    pth, pth_errors = _pth_vector(root)
    wrappers, wrapper_errors = _wrapper_vector(root)
    errors = [*(provenance.get("errors") or []), *module_errors, *pth_errors, *wrapper_errors]
    if not provenance.get("ok"):
        errors.append("runtime_provenance_not_ready")
    core = {
        "schema": RUNTIME_LAUNCH_SEED_SCHEMA,
        "authority": RUNTIME_LAUNCH_STANDALONE_AUTHORITY,
        "expected_root": str(root),
        "expected_revision": expected,
        "live_revision": live,
        "generated_at": generated_at or now_utc(),
        "runtime_provenance": provenance,
        "loaded_modules": modules,
        "interpreter": _interpreter_vector(
            direct_url=(provenance.get("direct_url") if isinstance(provenance.get("direct_url"), Mapping) else {})
        ),
        "site_pth": pth,
        "wrappers": wrappers,
        "errors": sorted(set(errors)),
        "ready": not errors,
    }
    return {**core, "content_sha256": _canonical_sha256(core)}


def validate_standalone_runtime_launch_seed(
    seed: Mapping[str, Any], *, component: str = "resident"
) -> dict[str, Any]:
    """Validate only resident evidence; this path never reads cloud artifacts."""
    _verify_seed_digest(seed)
    if seed.get("authority") != RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
        raise CliError(RUNTIME_ATTESTATION_ERROR, "runtime launch seed authority is not standalone-resident")
    if component != "resident":
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone runtime launch seed is resident-only")
    for field in ("manifest_sha256", "marker", "supervisor_receipt", "supervisor_runtime", "hot_env", "chain_runtime_binding"):
        if seed.get(field):
            raise CliError(RUNTIME_ATTESTATION_ERROR, f"standalone seed contains cloud field: {field}")
    required_types = {
        "expected_root": str,
        "expected_revision": str,
        "live_revision": str,
        "generated_at": str,
        "runtime_provenance": Mapping,
        "loaded_modules": list,
        "interpreter": Mapping,
        "site_pth": list,
        "wrappers": list,
        "errors": list,
    }
    for field, expected_type in required_types.items():
        if not isinstance(seed.get(field), expected_type):
            raise CliError(
                RUNTIME_ATTESTATION_ERROR,
                f"standalone runtime launch seed has invalid {field}",
            )
    if type(seed.get("ready")) is not bool:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "standalone runtime launch seed has invalid ready state",
        )
    try:
        root, expected, live = _standalone_admission(Path(str(seed.get("expected_root") or "")), str(seed.get("expected_revision") or ""))
    except CliError:
        raise
    if str(seed.get("expected_root") or "") != str(root) or str(seed.get("expected_revision") or "") != expected:
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone runtime attestation root or revision changed")
    if str(seed.get("live_revision") or "") != live:
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone runtime live revision changed")
    generated_at = str(seed.get("generated_at") or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", generated_at):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone runtime attestation timestamp is invalid")
    try:
        parsed_generated_at = datetime.fromisoformat(
            generated_at.removesuffix("Z") + "+00:00"
        )
    except ValueError as exc:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "standalone runtime attestation timestamp is invalid",
        ) from exc
    if parsed_generated_at.utcoffset() is None or parsed_generated_at.utcoffset().total_seconds() != 0:
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone runtime attestation timestamp is invalid")
    provenance = runtime_provenance(expected_root=root, expected_revision=expected)
    if not provenance.get("ok") or provenance != seed.get("runtime_provenance"):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone runtime provenance changed")
    modules, module_errors = _module_vector(root)
    pth, pth_errors = _pth_vector(root)
    wrappers, wrapper_errors = _wrapper_vector(root)
    interpreter = _interpreter_vector(
        direct_url=(provenance.get("direct_url") if isinstance(provenance.get("direct_url"), Mapping) else {})
    )
    if module_errors or modules != seed.get("loaded_modules"):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone loaded module vector changed")
    if pth_errors or pth != seed.get("site_pth"):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone site .pth vector changed")
    if wrapper_errors or wrappers != seed.get("wrappers"):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone wrapper vector changed")
    if interpreter != seed.get("interpreter"):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone interpreter identity changed")
    if not bool(seed.get("ready")) or seed.get("errors"):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone runtime launch seed was not release-ready")
    return {
        "status": "ready",
        "seed_sha256": seed["content_sha256"],
        "authority": RUNTIME_LAUNCH_STANDALONE_AUTHORITY,
        "expected_root": str(root),
        "expected_revision": expected,
        "runtime_vector_sha256": runtime_vector_sha256(seed),
    }


def _inspect_standalone_operational_dir(state: Path, name: str) -> bool:
    """Non-mutating check: True when present and safe, False when absent.

    Any existing symlink, non-directory, unreadable entry, or mode other
    than ``0700`` rejects; absence alone is not an error so callers can
    record the entry as eligible for later creation.
    """
    directory = state / name
    try:
        directory.relative_to(state)
    except ValueError as exc:  # defensive; *name* is a fixed component
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            f"resident {name} directory escaped state directory",
        ) from exc
    if directory.is_symlink():
        raise CliError(RUNTIME_ATTESTATION_ERROR, "resident launch state contains a symlink")
    if directory.exists() and not directory.is_dir():
        raise CliError(RUNTIME_ATTESTATION_ERROR, f"resident {name} directory is not a real directory")
    try:
        info = directory.stat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise CliError(RUNTIME_ATTESTATION_ERROR, f"resident {name} directory is unreadable") from exc
    if stat.S_IMODE(info.st_mode) != 0o700:
        raise CliError(RUNTIME_ATTESTATION_ERROR, f"resident {name} directory permissions are unsafe")
    return True


def _require_standalone_operational_dir(state: Path, name: str, *, create: bool) -> None:
    """Require a real, state-contained ``0700`` operational directory.

    Reused directories are validated, never repaired: an existing symlink,
    non-directory, or permissive mode fails closed before any seed, receipt,
    pointer, or attestation bytes change.  Only freshly created directories
    are normalized to ``0700``.
    """
    if _inspect_standalone_operational_dir(state, name):
        return
    if not create:
        raise CliError(RUNTIME_ATTESTATION_ERROR, f"resident {name} directory is unavailable")
    (state / name).mkdir(mode=0o700)
    (state / name).chmod(0o700)


def standalone_dispatch_paths(root: Path, *, head: str, seed_sha256: str) -> dict[str, Path]:
    state = standalone_runtime_launch_dir(root)
    expected = _validate_full_revision(head, label="expected HEAD")
    # Preflight every operational directory non-mutating before creating any:
    # an unsafe reused entry rejects while custody state still lacks siblings.
    missing = [
        name
        for name in ("seeds", "receipts", "status")
        if not _inspect_standalone_operational_dir(state, name)
    ]
    for name in missing:
        _require_standalone_operational_dir(state, name, create=True)
    return {
        "seed": _standalone_path(root, f"seeds/standalone-{expected}-{seed_sha256}.json"),
        "pointer": _standalone_path(root, "seeds/dispatch-current.json"),
        "receipts": _standalone_path(root, "receipts"),
        "status": _standalone_path(root, "status/resident.runtime-process-attestation.json"),
    }


def build_standalone_runtime_attestation_receipt(
    *, seed: Mapping[str, Any], seed_path: Path, pointer_path: Path, generated_at: str | None = None
) -> dict[str, Any]:
    _verify_seed_digest(seed)
    if seed.get("authority") != RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
        raise CliError(RUNTIME_ATTESTATION_ERROR, "receipt requires standalone-resident seed")
    core = {
        "schema": STANDALONE_ATTESTATION_RECEIPT_SCHEMA,
        "authority": RUNTIME_LAUNCH_STANDALONE_AUTHORITY,
        "root": str(Path(str(seed["expected_root"])).resolve(strict=True)),
        "expected_head": str(seed["expected_revision"]),
        "live_head": str(seed.get("live_revision") or ""),
        "generated_at": generated_at or str(seed.get("generated_at") or now_utc()),
        "seed_path": str(seed_path.resolve(strict=False)),
        "seed_sha256": str(seed["content_sha256"]),
        "pointer_path": str(pointer_path.resolve(strict=False)),
    }
    return {**core, "content_sha256": _canonical_sha256(core)}


def load_standalone_runtime_dispatch_pointer(root: Path) -> dict[str, Any]:
    state = standalone_runtime_launch_dir(root, create=False)
    for name in ("seeds", "receipts", "status"):
        _require_standalone_operational_dir(state, name, create=False)
    pointer_path = state / "seeds" / "dispatch-current.json"
    if pointer_path.is_symlink() or pointer_path.parent.is_symlink():
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer is a symlink")
    try:
        if stat.S_IMODE(pointer_path.stat().st_mode) != 0o600:
            raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer permissions are unsafe")
    except OSError:
        pass
    pointer = _json_file(pointer_path, label="standalone runtime dispatch pointer")
    if pointer.get("schema") != STANDALONE_DISPATCH_POINTER_SCHEMA or pointer.get("authority") != RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer authority is invalid")
    resolved_root = Path(str(root)).expanduser().resolve(strict=True)
    if str(pointer.get("root") or "") != str(resolved_root):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer root mismatch")
    seed_path = Path(str(pointer.get("seed_path") or ""))
    receipt_path = Path(str(pointer.get("receipt_path") or ""))
    for path in (seed_path, receipt_path):
        if not path.is_absolute() or not path.exists() or path.is_symlink():
            raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer path is unsafe")
        try:
            if stat.S_IMODE(path.stat().st_mode) != 0o600:
                raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch object permissions are unsafe")
        except OSError as exc:
            raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch object is unreadable") from exc
        state = standalone_runtime_launch_dir(resolved_root, create=False)
        try:
            lexical = path.relative_to(state)
        except ValueError as exc:
            raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer escaped state directory") from exc
        _require_standalone_operational_dir(state, lexical.parts[0], create=False)
        current = state
        for part in lexical.parts:
            current = current / part
            if current.is_symlink():
                raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch path contains a symlink")
        try:
            path.resolve(strict=True).relative_to(state.resolve(strict=True))
        except ValueError as exc:
            raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer escaped state directory") from exc
    seed = _json_file(seed_path, label="standalone runtime launch seed")
    receipt = _json_file(receipt_path, label="standalone runtime attestation receipt")
    _verify_seed_digest(seed)
    if seed.get("content_sha256") != pointer.get("seed_sha256"):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch seed digest mismatch")
    if seed.get("expected_revision") != pointer.get("expected_revision"):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch seed revision mismatch")
    if receipt.get("content_sha256") != pointer.get("receipt_sha256"):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch receipt digest mismatch")
    receipt_core = {key: value for key, value in receipt.items() if key != "content_sha256"}
    if receipt.get("schema") != STANDALONE_ATTESTATION_RECEIPT_SCHEMA or receipt.get("authority") != RUNTIME_LAUNCH_STANDALONE_AUTHORITY or receipt.get("content_sha256") != _canonical_sha256(receipt_core):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone attestation receipt is invalid")
    if receipt.get("seed_path") != str(seed_path.resolve(strict=False)) or receipt.get("seed_sha256") != seed.get("content_sha256"):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone attestation receipt seed binding is invalid")
    if receipt.get("pointer_path") != str(pointer_path.resolve(strict=False)):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone attestation receipt pointer binding is invalid")
    if (
        receipt.get("root") != pointer.get("root")
        or receipt.get("expected_head") != pointer.get("expected_revision")
        or receipt.get("live_head") != seed.get("live_revision")
        or receipt.get("generated_at") != seed.get("generated_at")
        or pointer.get("generated_at") != seed.get("generated_at")
    ):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone attestation receipt root/revision binding is invalid")
    validate_standalone_runtime_launch_seed(seed)
    return pointer


def _verify_reused_immutable_object(
    path: Path, payload: Mapping[str, Any], *, label: str
) -> None:
    """Accept a ``FileExistsError`` reuse only when custody is intact.

    The existing object must be a regular non-symlink file with mode exactly
    ``0600`` whose canonical digest matches the expected immutable object.
    Anything else rejects without repair, chmod, or mutation so the dispatch
    pointer can never advance onto a tampered custody object.
    """
    try:
        st = path.lstat()
    except OSError as exc:
        raise CliError(RUNTIME_ATTESTATION_ERROR, f"standalone {label} is unreadable") from exc
    if path.is_symlink() or not stat.S_ISREG(st.st_mode):
        raise CliError(RUNTIME_ATTESTATION_ERROR, f"standalone {label} is not a regular file")
    if stat.S_IMODE(st.st_mode) != 0o600:
        raise CliError(RUNTIME_ATTESTATION_ERROR, f"standalone {label} permissions are unsafe")
    existing = _json_file(path, label=f"standalone runtime {label}")
    expected_digest = str(payload.get("content_sha256") or "")
    existing_core = {key: value for key, value in existing.items() if key != "content_sha256"}
    if (
        existing.get("content_sha256") != expected_digest
        or _canonical_sha256(existing_core) != expected_digest
        or existing != dict(payload)
    ):
        raise CliError(RUNTIME_ATTESTATION_ERROR, f"immutable standalone {label} collision")


def write_standalone_runtime_publication(
    *, seed: Mapping[str, Any], seed_path: Path, root: Path, generated_at: str | None = None
) -> dict[str, Any]:
    """Publish a resident seed, issuance receipt, and dispatch pointer."""
    validate_standalone_runtime_launch_seed(seed)
    root, expected, live = _standalone_admission(root, str(seed.get("expected_revision") or ""))
    if str(seed.get("expected_root") or "") != str(root) or live != str(seed.get("live_revision") or ""):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone seed changed during publication")
    paths = standalone_dispatch_paths(root, head=expected, seed_sha256=str(seed["content_sha256"]))
    if paths["seed"].resolve(strict=False) != seed_path.resolve(strict=False):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone seed path is not root-custodied")
    try:
        _exclusive_write_json(paths["seed"], seed, mode=0o600)
    except FileExistsError:
        _verify_reused_immutable_object(paths["seed"], seed, label="launch seed")
    receipt = build_standalone_runtime_attestation_receipt(
        seed=seed, seed_path=paths["seed"], pointer_path=paths["pointer"], generated_at=generated_at
    )
    receipt_path = _standalone_path(
        root, f"receipts/{receipt['content_sha256']}.json"
    )
    try:
        _exclusive_write_json(receipt_path, receipt, mode=0o600)
    except FileExistsError:
        _verify_reused_immutable_object(receipt_path, receipt, label="attestation receipt")
    pointer = {
        "schema": STANDALONE_DISPATCH_POINTER_SCHEMA,
        "authority": RUNTIME_LAUNCH_STANDALONE_AUTHORITY,
        "seed_path": str(paths["seed"].resolve(strict=False)),
        "receipt_path": str(receipt_path.resolve(strict=False)),
        "root": str(root),
        "expected_revision": expected,
        "generated_at": str(seed.get("generated_at") or generated_at or now_utc()),
        "seed_sha256": str(seed["content_sha256"]),
        "receipt_sha256": str(receipt["content_sha256"]),
    }
    if paths["pointer"].is_symlink():
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer is a symlink")
    _atomic_write(paths["pointer"], pointer)
    # Re-read and validate every published object before handing it to a caller.
    published = load_standalone_runtime_dispatch_pointer(root)
    if published != pointer:
        raise CliError(RUNTIME_ATTESTATION_ERROR, "published standalone dispatch pointer changed")
    return {"seed_path": paths["seed"], "receipt_path": receipt_path, "pointer_path": paths["pointer"], "receipt": receipt, "pointer": pointer}


def _write_dispatch_pointer(
    store_dir: Path,
    seed_path: Path,
    *,
    generation: int,
    expected_revision: str,
    seed_sha256: str,
) -> Path:
    """Atomically point ``dispatch-current.json`` at the newest ready seed."""
    pointer = store_dir / DISPATCH_CURRENT_FILENAME
    _atomic_write(
        pointer,
        {
            "schema": DISPATCH_POINTER_SCHEMA,
            "seed_path": str(seed_path),
            "manifest_generation": generation,
            "expected_revision": expected_revision,
            "seed_sha256": seed_sha256,
        },
    )
    return pointer


def _find_current_seed(
    store_dir: Path,
    *,
    root: Path,
    expected_revision: str,
    marker_path: Path,
    manifest_path: Path,
    generation: int,
) -> Path | None:
    """Return an existing, still-valid immutable seed for this generation."""
    if not store_dir.is_dir():
        return None
    for candidate in sorted(store_dir.glob("*.json")):
        if candidate.name == DISPATCH_CURRENT_FILENAME:
            continue
        if _launch_seed_current(
            candidate,
            root=root,
            expected_revision=expected_revision,
            marker_path=marker_path,
            manifest_path=manifest_path,
            generation=generation,
        ):
            return candidate
    return None
        manifest = load_manifest(Path(manifest_value).expanduser().resolve(strict=False))
        return int(manifest.generation)
    except (ManifestError, TypeError, ValueError):
        return None


def refresh_runtime_launch_seed_for_worker_dispatch() -> Path | None:
    """Select the accepted generation immediately before a worker dispatch.

    The chain's configured seed remains its orchestration seed.  Each worker
    dispatch re-reads the accepted manifest under the promotion lock, resolves
    or creates that generation's immutable seed, and updates the exact seed
    path inherited by the child worker process.
    """
    manifest_value = str(os.environ.get("ARNOLD_RUNTIME_MANIFEST") or "").strip()
    current_path = configured_seed_path()
    if current_path is None:
        return None
    # Custody boundary: a configured seed must prove cloud-chain authority
    # BEFORE any early return, including the no-manifest one, so a
    # standalone-resident seed cannot cross into worker dispatch unchallenged.
    current = _json_file(current_path, label="runtime launch seed")
    if current.get("authority") != RUNTIME_LAUNCH_CLOUD_AUTHORITY:
        raise CliError(RUNTIME_ATTESTATION_ERROR, "worker dispatch requires a cloud-chain runtime seed")
    if not manifest_value:
        return current_path
    input_paths = current.get("input_paths")
    input_paths = input_paths if isinstance(input_paths, Mapping) else {}
    chain_spec_value = str(input_paths.get("chain_spec") or "").strip()
    marker_value = str(input_paths.get("marker") or "").strip()
    if not chain_spec_value or not marker_value:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "orchestration seed lacks chain_spec or marker dispatch inputs",
        )
    manifest_path = Path(manifest_value).expanduser().resolve(strict=False)
    lock_path = Path(f"{manifest_path}.promotion.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_SH)
        selected = ensure_runtime_launch_seed(
            manifest_path=manifest_path,
            chain_spec_path=Path(chain_spec_value),
            marker_path=Path(marker_value),
            chain_runtime_identity=(
                current.get("chain_runtime_binding", {}).get("runtime_identity")
                if isinstance(current.get("chain_runtime_binding"), Mapping)
                else None
            ),
        )
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
    os.environ["MEGAPLAN_RUNTIME_LAUNCH_SEED"] = str(selected)
    return selected


def _verify_seed_digest(seed: Mapping[str, Any]) -> None:
    core = {key: value for key, value in seed.items() if key != "content_sha256"}
    authority = seed.get("authority")
    if (
        seed.get("schema") != RUNTIME_LAUNCH_SEED_SCHEMA
        or not isinstance(authority, str)
        or authority not in RUNTIME_LAUNCH_AUTHORITIES
        or not isinstance(seed.get("content_sha256"), str)
        or seed.get("content_sha256") != _canonical_sha256(core)
    ):
        raise CliError(
            RUNTIME_ATTESTATION_ERROR, "runtime launch seed digest is invalid"
        )


def runtime_vector_sha256(seed: Mapping[str, Any]) -> str:
    """Hash the complete loaded-code vector carried by a verified launch seed."""

    return _canonical_sha256(
        {
            "modules": seed.get("loaded_modules"),
            "interpreter": seed.get("interpreter"),
            "pth": seed.get("site_pth"),
            "wrappers": seed.get("wrappers"),
        }
    )


def _component_runtime_vector_sha256(
    seed: Mapping[str, Any],
    *,
    component: str,
) -> str:
    if component in _SUPERVISOR_COMPONENTS:
        return _canonical_sha256(
            {
                "runtime": seed.get("supervisor_runtime"),
                "wrappers": seed.get("wrappers"),
            }
        )
    return runtime_vector_sha256(seed)


def validate_runtime_launch_seed(
    seed: Mapping[str, Any],
    *,
    component: str,
) -> dict[str, Any]:
    """Revalidate a launch seed against files, imports, and current interpreter.

    Only modules the validating worker actually imported are compared; seed
    entries absent from the worker (e.g. chain-CLI-only builder imports) are
    allowed.  Modules present in both sides must match identically.
    """

    _verify_seed_digest(seed)
    authority = seed.get("authority")
    if authority == RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
        return validate_standalone_runtime_launch_seed(seed, component=component)
    if authority != RUNTIME_LAUNCH_CLOUD_AUTHORITY:
        raise CliError(RUNTIME_ATTESTATION_ERROR, "runtime launch seed authority is invalid")
    if not bool(seed.get("ready")) or seed.get("errors"):
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "runtime launch seed was not release-ready",
        )
    root = Path(str(seed.get("expected_root") or "")).resolve(strict=False)
    revision = str(seed.get("expected_revision") or "")
    is_supervisor = component in _SUPERVISOR_COMPONENTS
    supervisor = seed.get("supervisor_receipt")
    supervisor = supervisor if isinstance(supervisor, Mapping) else {}
    if is_supervisor:
        current_runtime = supervisor_runtime_vector(
            expected_source=root,
            expected_revision=revision,
            expected_runtime=Path(str(supervisor.get("runtime") or "")),
            expected_fingerprint=str(supervisor.get("fingerprint") or ""),
        )
        if current_runtime != seed.get("supervisor_runtime"):
            raise CliError(
                RUNTIME_ATTESTATION_ERROR,
                "dedicated supervisor runtime vector drifted",
            )
def create_runtime_process_attestation(
    seed: Mapping[str, Any],
    *,
    component: str,
    target_pid: int,
) -> dict[str, Any]:
    validation = validate_runtime_launch_seed(seed, component=component)
    process = _proc_identity(target_pid)
    expected_selectors = (seed.get("hot_env") or {}).get("selectors") or {}
    mismatches = {
        name: {"expected": expected, "actual": process["selectors"].get(name, "")}
        for name, expected in expected_selectors.items()
        if process["selectors"].get(name) != expected
    }
    if mismatches:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            f"process inherited stale runtime selectors: {sorted(mismatches)}",
        )
    core = {
        "schema": RUNTIME_PROCESS_ATTESTATION_SCHEMA,
        "authority": seed.get("authority"),
        "component": component,
        "seed_sha256": validation["seed_sha256"],
        "runtime_vector_sha256": validation["runtime_vector_sha256"],
        "process": process,
    }
    return {**core, "content_sha256": _canonical_sha256(core)}


def validate_runtime_process_attestation(
    seed: Mapping[str, Any],
    attestation: Mapping[str, Any],
    *,
    component: str,
    target_pid: int,
) -> dict[str, Any]:
    """Re-confirm a process attestation WITHOUT re-reading a mutable manifest.

    Codex fix 2026-08-17: the full seed validation runs EXACTLY ONCE per
    process, at :func:`create_runtime_process_attestation` (the admission
    point). Subsequent checks in the same process validate only that (a) the
    immutable seed digest still matches, (b) the attestation belongs to the
    same PID/process-start identity, and (c) no Arnold module from a foreign
    root has since been imported. They must NEVER compare against the current
    manifest, the current remote head, or a newly published generation.
    """
    _verify_seed_digest(seed)
    if (
        seed.get("authority") == RUNTIME_LAUNCH_STANDALONE_AUTHORITY
        and component != "resident"
    ):
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "standalone runtime process attestation is resident-only",
        )
    core = {
        key: attestation.get(key)
        for key in (
            "schema",
            "authority",
            "component",
            "seed_sha256",
            "runtime_vector_sha256",
            "process",
        )
    }
    if (
        attestation.get("schema") != RUNTIME_PROCESS_ATTESTATION_SCHEMA
        or attestation.get("authority") != seed.get("authority")
        or attestation.get("content_sha256") != _canonical_sha256(core)
        or attestation.get("component") != component
        or attestation.get("seed_sha256") != seed.get("content_sha256")
        or attestation.get("runtime_vector_sha256")
        != _component_runtime_vector_sha256(seed, component=component)
        or attestation.get("process") != _proc_identity(target_pid)
    ):
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "runtime process attestation is stale or belongs to another process",
        )
    # No mixed-root Arnold modules may have been imported since admission.
    root = Path(str(seed.get("expected_root") or "")).resolve(strict=False)
    is_supervisor = component in _SUPERVISOR_COMPONENTS
    if is_supervisor:
        supervisor = seed.get("supervisor_receipt")
        supervisor = supervisor if isinstance(supervisor, Mapping) else {}
        module_root = Path(str(supervisor.get("runtime") or "")).resolve(strict=False)
        _modules, module_errors = _supervisor_module_vector(module_root)
    else:
        _modules, module_errors = _module_vector(root)
    if module_errors:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "loaded Arnold modules escaped the expected root: "
            + ", ".join(module_errors),
        )
    return {
        "status": "ready",
        "seed_sha256": seed["content_sha256"],
        "expected_root": str(root),
        "expected_revision": str(seed.get("expected_revision") or ""),
        "runtime_vector_sha256": _component_runtime_vector_sha256(
            seed,
            component=component,
        ),
    }


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path = path.resolve(strict=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def configured_runtime_attestation_required() -> bool:
    """Return ``True`` unless runtime attestation is explicitly disabled.

    Deny-by-default: runtime attestation is REQUIRED when
    ``MEGAPLAN_RUNTIME_ATTESTATION_REQUIRED`` is absent or any value other
    than ``"0"``.  Only an explicit ``"0"`` opts out.

    Note: the flag cannot waive the launch-seed requirement — a production
    launch always needs ``MEGAPLAN_RUNTIME_LAUNCH_SEED`` (see
    :func:`require_configured_runtime_launch`, which fails closed on a
    missing seed regardless of this flag).
    """
    return os.environ.get("MEGAPLAN_RUNTIME_ATTESTATION_REQUIRED") != "0"


def configured_seed_path() -> Path | None:
    value = str(os.environ.get("MEGAPLAN_RUNTIME_LAUNCH_SEED") or "").strip()
    return Path(value).expanduser().resolve(strict=False) if value else None


def configured_process_attestation_path(
    component: str, *, seed: Mapping[str, Any] | None = None
) -> Path:
    value = str(os.environ.get("MEGAPLAN_RUNTIME_PROCESS_ATTESTATION") or "").strip()
    if seed is not None and seed.get("authority") == RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
        return standalone_runtime_launch_dir(Path(str(seed.get("expected_root") or "")), create=False) / "status" / (
            f"{component}.runtime-process-attestation.json"
        )
    if value:
        return Path(value).expanduser().resolve(strict=False)
    return (
        Path("/workspace/.megaplan/status")
        / f"{component}.runtime-process-attestation.json"
    )


def require_configured_runtime_launch(
    component: str,
    *,
    target_pid: int | None = None,
    create: bool = False,
) -> dict[str, Any]:
    raw_seed_value = str(os.environ.get("MEGAPLAN_RUNTIME_LAUNCH_SEED") or "").strip()
    raw_seed_path = Path(raw_seed_value).expanduser() if raw_seed_value else None
    seed_path = configured_seed_path()
    if seed_path is None:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "canonical runtime launch seed is required but missing",
        )
    seed = _json_file(seed_path, label="runtime launch seed")
    authority = seed.get("authority")
    if not isinstance(authority, str) or authority not in RUNTIME_LAUNCH_AUTHORITIES:
        raise CliError(RUNTIME_ATTESTATION_ERROR, "runtime launch seed authority is invalid")
    if authority == RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
        if raw_seed_path is None or not raw_seed_path.is_absolute() or raw_seed_path.is_symlink():
            raise CliError(RUNTIME_ATTESTATION_ERROR, "configured resident seed path is a symlink or missing")
        pointer = load_standalone_runtime_dispatch_pointer(Path(str(seed.get("expected_root") or "")))
        if Path(str(pointer.get("seed_path") or "")) != raw_seed_path:
            raise CliError(RUNTIME_ATTESTATION_ERROR, "configured resident seed is not the published dispatch seed")
        if pointer.get("seed_sha256") != seed.get("content_sha256"):
            raise CliError(RUNTIME_ATTESTATION_ERROR, "configured resident seed digest does not match dispatch pointer")
    pid = target_pid or os.getpid()
    attestation_path = configured_process_attestation_path(component, seed=seed)
    if authority == RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
        state = standalone_runtime_launch_dir(Path(str(seed.get("expected_root") or "")), create=create)
        _require_standalone_operational_dir(state, "status", create=create)
        if attestation_path.is_symlink():
            raise CliError(RUNTIME_ATTESTATION_ERROR, "resident process attestation path is a symlink")
        try:
            attestation_path.resolve(strict=False).relative_to(state.resolve(strict=True))
        except ValueError as exc:
            raise CliError(RUNTIME_ATTESTATION_ERROR, "resident process attestation path escaped state directory") from exc
    if create:
        attestation = create_runtime_process_attestation(
            seed,
            component=component,
            target_pid=pid,
        )
        _atomic_write(attestation_path, attestation)
    else:
        if authority == RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
            try:
                if stat.S_IMODE(attestation_path.stat().st_mode) != 0o600:
                    raise CliError(
                        RUNTIME_ATTESTATION_ERROR,
                        "resident process attestation permissions are unsafe",
                    )
            except OSError as exc:
                raise CliError(
                    RUNTIME_ATTESTATION_ERROR,
                    "runtime process attestation is unreadable",
                ) from exc
        attestation = _json_file(
            attestation_path,
            label="runtime process attestation",
        )
        validate_runtime_process_attestation(
            seed,
            attestation,
            component=component,
            target_pid=pid,
        )
    return seed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    build = sub.add_parser("build")
    build.add_argument("--expected-root", type=Path, required=True)
    build.add_argument("--expected-revision", required=True)
    build.add_argument("--supervisor-receipt", type=Path, required=True)
    build.add_argument("--hot-env", type=Path, required=True)
    build.add_argument("--marker", type=Path, required=True)
    build.add_argument("--chain-spec", type=Path, required=True)
    build.add_argument("--seed-doc", type=Path, action="append", default=[])
    build.add_argument("--manifest", type=Path, default=None)

exec
/bin/zsh -lc 'python -m pytest tests/cloud/test_runtime_attestation.py tests/cloud/test_standalone_runtime_attestation.py -q' in /Users/peteromalley/Documents/arnold-oracle
exec
/bin/zsh -lc "git diff --unified=40 210bb6e078..HEAD -- tests/cloud/test_runtime_attestation.py | sed -n '1,1000p'; rg -n '"'^def test_'"' tests/cloud/test_standalone_runtime_attestation.py; git diff --check 210bb6e078..HEAD" in /Users/peteromalley/Documents/arnold-oracle
 succeeded in 0ms:
diff --git a/tests/cloud/test_runtime_attestation.py b/tests/cloud/test_runtime_attestation.py
index c314b2f034..8908beef73 100644
--- a/tests/cloud/test_runtime_attestation.py
+++ b/tests/cloud/test_runtime_attestation.py
@@ -164,80 +164,81 @@ def _release_seed(
         {
             "fingerprint": "supervisor-fingerprint",
             "runtime": sys.prefix,
             "source": str(root),
             "source_revision": revision,
             "imports": {
                 "arnold": supervisor_modules[0]["path"],
                 "arnold_pipelines": supervisor_modules[1]["path"],
                 "megaplan": supervisor_modules[2]["path"],
             },
         },
     )
     seed = attestation.build_runtime_launch_seed(
         expected_root=root,
         expected_revision=revision,
         supervisor_receipt_path=receipt,
         hot_env_path=hot_env,
         marker_path=marker,
         chain_spec_path=chain_spec,
         seed_doc_paths=[seed_doc],
     )
     return seed, {
         "root": root,
         "receipt": receipt,
         "hot_env": hot_env,
         "marker": marker,
         "chain_spec": chain_spec,
         "seed_doc": seed_doc,
         "wrapper": wrapper_dir / "arnold-watchdog",
     }
 
 
 def test_release_seed_binds_full_runtime_and_seed_document_manifest(
     tmp_path: Path,
     monkeypatch: pytest.MonkeyPatch,
 ) -> None:
     seed, paths = _release_seed(tmp_path, monkeypatch)
 
     assert seed["ready"] is True
     assert seed["errors"] == []
+    assert seed["authority"] == attestation.RUNTIME_LAUNCH_CLOUD_AUTHORITY
     assert seed["expected_root"] == str(paths["root"])
     assert seed["loaded_modules"]
     assert seed["interpreter"]["executable"] == str(Path(sys.executable).resolve())
     assert seed["interpreter"]["direct_url"] == {}
     assert seed["supervisor_receipt"]["fingerprint"] == "supervisor-fingerprint"
     assert seed["hot_env"]["selectors"]["MEGAPLAN_RUNTIME_SRC"] == str(paths["root"])
     assert seed["wrappers"][0]["sha256"]
     assert seed["chain_runtime_binding"]["runtime_identity"]["import_root"] == str(
         paths["root"]
     )
     manifest_paths = {
         item["path"] for item in seed["seed_document_manifest"]["entries"]
     }
     assert str(paths["seed_doc"]) in manifest_paths
     assert str(paths["marker"]) not in manifest_paths
     assert (
         attestation.validate_runtime_launch_seed(seed, component="worker")["status"]
         == "ready"
     )
 
 
 def test_complete_loaded_module_vector_rejects_mixed_and_late_modules(
     tmp_path: Path,
     monkeypatch: pytest.MonkeyPatch,
 ) -> None:
     seed, _paths = _release_seed(tmp_path, monkeypatch)
     original = list(seed["loaded_modules"])
     monkeypatch.setattr(
         attestation,
         "_module_vector",
         lambda _root: (
             [
                 *original,
                 {
                     "module": "arnold_pipelines.late_import",
                     "path": "/other/arnold_pipelines/late_import.py",
                     "root": "",
                 },
             ],
             ["mixed_module_root:arnold_pipelines.late_import"],
@@ -1268,96 +1269,130 @@ def test_regenerate_relaunch_command_noop_cases() -> None:
         )
         == command
     )
     assert (
         attestation._regenerate_relaunch_command(
             f"RUNTIME_REVISION={old}",
             old_revision=old,
             new_revision=old,
         )
         == f"RUNTIME_REVISION={old}"
     )
 
 
 def test_regenerate_relaunch_command_does_not_touch_hex_neighbors() -> None:
     """Word-boundary guard: a revision that is a prefix of another hex token
     (e.g. inside a longer digest or a path) is not swapped."""
     old = "a" * 40
     new = "b" * 40
     command = f"python -m chain {old} extra-{old}deadbeef"
     regenerated = attestation._regenerate_relaunch_command(
         command, old_revision=old, new_revision=new
     )
     assert regenerated == f"python -m chain {new} extra-{old}deadbeef"
 
 
 def test_worker_preflight_reads_configured_launch_seed_env(
     tmp_path: Path,
     monkeypatch: pytest.MonkeyPatch,
 ) -> None:
     """G14: the worker launch preflight sees the env export — with
     MEGAPLAN_RUNTIME_LAUNCH_SEED set, require_configured_runtime_launch reads
     that exact seed path instead of failing with 'required but missing'."""
     seed_path = tmp_path / "seed.json"
     seed_path.write_text(json.dumps({"schema": "x", "ready": True}), encoding="utf-8")
     monkeypatch.setenv("MEGAPLAN_RUNTIME_LAUNCH_SEED", str(seed_path))
     monkeypatch.delenv("MEGAPLAN_RUNTIME_PROCESS_ATTESTATION", raising=False)
     observed: dict[str, str] = {}
     monkeypatch.setattr(
         attestation,
         "_json_file",
-        lambda path, label: (observed.update(path=str(path)) or {"schema": "x", "ready": True}),
+        lambda path, label: (
+            observed.update(path=str(path))
+            or {
+                "schema": attestation.RUNTIME_LAUNCH_SEED_SCHEMA,
+                "authority": attestation.RUNTIME_LAUNCH_CLOUD_AUTHORITY,
+                "ready": True,
+            }
+        ),
     )
     monkeypatch.setattr(
         attestation,
         "create_runtime_process_attestation",
         lambda *args, **kwargs: {"pid": 123},
     )
     monkeypatch.setattr(attestation, "_atomic_write", lambda *args, **kwargs: None)
 
     seed = attestation.require_configured_runtime_launch(
         "worker", target_pid=123, create=True
     )
-    assert seed == {"schema": "x", "ready": True}
+    assert seed == {
+        "schema": attestation.RUNTIME_LAUNCH_SEED_SCHEMA,
+        "authority": attestation.RUNTIME_LAUNCH_CLOUD_AUTHORITY,
+        "ready": True,
+    }
     assert observed["path"] == str(seed_path)
 
 
+@pytest.mark.parametrize("authority", [[], {}], ids=["list", "dict"])
+def test_non_string_authority_fails_with_typed_mismatch(
+    tmp_path: Path,
+    monkeypatch: pytest.MonkeyPatch,
+    authority: object,
+) -> None:
+    seed = {
+        "schema": attestation.RUNTIME_LAUNCH_SEED_SCHEMA,
+        "authority": authority,
+        "content_sha256": "unused",
+    }
+    with pytest.raises(CliError) as excinfo:
+        attestation._verify_seed_digest(seed)
+    assert excinfo.value.code == attestation.RUNTIME_ATTESTATION_ERROR
+
+    seed_path = tmp_path / "seed.json"
+    _write_json(seed_path, seed)
+    monkeypatch.setenv("MEGAPLAN_RUNTIME_LAUNCH_SEED", str(seed_path))
+    with pytest.raises(CliError) as excinfo:
+        attestation.require_configured_runtime_launch("worker")
+    assert excinfo.value.code == attestation.RUNTIME_ATTESTATION_ERROR
+
+
 def test_attestation_disable_without_seed_does_not_authorize_production_launch(
     monkeypatch: pytest.MonkeyPatch,
 ) -> None:
     """P3 follow-up: explicit attestation-disable (MEGAPLAN_RUNTIME_ATTESTATION_REQUIRED=0)
     without a launch seed must NOT authorize a production launch — the gate
     still fails closed because the launch seed is mandatory.
     """
     monkeypatch.delenv("MEGAPLAN_RUNTIME_LAUNCH_SEED", raising=False)
     monkeypatch.delenv("MEGAPLAN_RUNTIME_PROCESS_ATTESTATION", raising=False)
     monkeypatch.setenv("MEGAPLAN_RUNTIME_ATTESTATION_REQUIRED", "0")
 
     with pytest.raises(CliError, match="required but missing"):
         attestation.require_configured_runtime_launch("resident")
 
 
 def test_build_cli_records_explicit_manifest_pointer(
     tmp_path: Path,
     monkeypatch: pytest.MonkeyPatch,
     capsys: pytest.CaptureFixture[str],
 ) -> None:
     """Codex consult 0ae19cc17afd (b.1): the `runtime_attestation build` CLI
     accepts --manifest and records the resolved path in input_paths.manifest
     (fixer/rebind parity with the production ensure_runtime_launch_seed path —
     the structural gap that produced the pointerless seed)."""
     _seed, paths = _release_seed(tmp_path, monkeypatch)
     manifest = tmp_path / "runtime-manifest.json"
     _write_json(manifest, {"epic": {"expected_head": "a" * 40}})
     output = tmp_path / "cli-seed.json"
     rc = attestation.main(
         [
             "build",
             "--expected-root",
             str(paths["root"]),
             "--expected-revision",
             "a" * 40,
             "--supervisor-receipt",
             str(paths["receipt"]),
             "--hot-env",
             str(paths["hot_env"]),
             "--marker",
@@ -1665,41 +1700,41 @@ def test_adopt_or_refuse_launch_identity_generation_advance() -> None:
 
     # Unknown recorded generation + same root -> adopt.
     adopted = _adopt_or_refuse_launch_identity(
         recorded, live, recorded_generation=None, live_generation=115
     )
     assert adopted["source_revision"] == live["source_revision"]
 
     # Different import_root -> fail closed.
     other_root = dict(live)
     other_root["import_root"] = "/workspace/runtime-candidates/other"
     try:
         _adopt_or_refuse_launch_identity(
             recorded, other_root, recorded_generation=114, live_generation=115
         )
     except Exception as exc:
         assert getattr(exc, "code", None) == RUNTIME_ATTESTATION_ERROR
     else:
         raise AssertionError("different import_root must fail closed")
 
     # Generation downgrade gen 115 -> 114 on same root -> adopt (engine
     # change of ANY direction on the same root is a non-event).
     adopted = _adopt_or_refuse_launch_identity(
         live, recorded, recorded_generation=115, live_generation=114
     )
     assert adopted["source_revision"] == recorded["source_revision"]
 
     # Same generation but different revision -> adopt (head moved at the
     # same gen is still an engine change; only a root swap fails closed).
     same_gen_other_rev = dict(live)
     same_gen_other_rev["source_revision"] = "c" * 40
     adopted = _adopt_or_refuse_launch_identity(
         recorded, same_gen_other_rev, recorded_generation=114, live_generation=114
     )
     assert adopted["source_revision"] == "c" * 40
 
     # normalized_runtime_identity round-trips through the helper.
     normalized_recorded = normalize_runtime_identity(recorded)
     adopted = _adopt_or_refuse_launch_identity(
         normalized_recorded, live, recorded_generation=114, live_generation=115
     )
-    assert adopted["source_revision"] == live["source_revision"]
\ No newline at end of file
+    assert adopted["source_revision"] == live["source_revision"]
58:def test_standalone_seed_validates_and_process_attestation_binds_authority(
121:def test_standalone_seed_wrong_authority_root_or_head_fails_closed(
133:def test_standalone_seed_digest_requires_recognized_authority(
143:def test_cloud_worker_validation_rejects_standalone_seed(
152:def test_standalone_seed_requires_canonical_errors_vector(
171:def test_standalone_seed_rejects_nonempty_cloud_evidence(
183:def test_standalone_seed_vector_drift_fails_closed(
202:def test_edited_seed_and_cloud_dispatch_path_fail_closed(
222:def test_standalone_process_attestation_cannot_cross_into_cloud_worker(
249:def test_standalone_admission_rejects_expected_head_whitespace(
260:def test_publication_pointer_is_content_addressed_and_rejects_tampering(
325:def test_resident_attest_json_and_plain_contract_via_adapter(
374:def test_resident_attest_wrong_head_returns_admission_exit_code_2(
402:def test_resident_attest_publication_failure_does_not_advance_pointer(
498:def test_worker_refresh_rejects_standalone_seed_without_manifest(
517:def test_standalone_publication_rejects_unsafe_reused_directory_at_0755(
535:def test_standalone_publication_rejects_unsafe_mode_reuse_without_advancing_pointer(
572:def test_standalone_publication_rejection_does_not_create_missing_siblings(
598:def test_standalone_load_rejects_unsafe_reused_directory_at_0755(
614:def test_standalone_load_rejects_missing_status_directory(
630:def test_resident_process_create_rejects_unsafe_status_directory_at_0755(
646:def test_resident_process_read_rejects_unsafe_status_directory_at_0755(
664:def test_standalone_load_rejection_does_not_mutate_filesystem(tmp_path: Path) -> None:

codex
A broader two-file run has exposed one failure despite the reported standalone-only green run. I’m isolating whether it is a real cloud-compatibility regression, an environmental artifact, or an expected test assumption that was not updated.
 exited 1 in 18137ms:
................F....................................................... [ 88%]
.........                                                                [100%]
=================================== FAILURES ===================================
_________ test_real_editable_launch_and_noneditable_supervisor_vectors _________

tmp_path = PosixPath('/private/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/pytest-of-peteromalley/pytest-249/test_real_editable_launch_and_0')

    def test_real_editable_launch_and_noneditable_supervisor_vectors(
        tmp_path: Path,
    ) -> None:
        source = Path(__file__).resolve().parents[2]
        revision = subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        launch_python = _install_test_runtime(
            tmp_path / "launch-venv",
            source,
            editable=True,
        )
        supervisor_runtime = tmp_path / "supervisor-venv"
>       supervisor_python = _install_test_runtime(
            supervisor_runtime,
            source,
            editable=False,
        )

tests/cloud/test_runtime_attestation.py:513: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
tests/cloud/test_runtime_attestation.py:494: in _install_test_runtime
    shutil.copytree(source / package, site_dir / package)
../../.pyenv/versions/3.11.11/lib/python3.11/shutil.py:573: in copytree
    return _copytree(entries=entries, src=src, dst=dst, symlinks=symlinks,
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

entries = [<DirEntry 'megaplan'>, <DirEntry 'run_authority'>, <DirEntry '.DS_Store'>, <DirEntry '_template'>, <DirEntry 'discovery.py'>, <DirEntry '__init__.py'>, ...]
src = PosixPath('/Users/peteromalley/Documents/arnold-oracle/arnold_pipelines')
dst = PosixPath('/private/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/pytest-of-peteromalley/pytest-249/test_real_editable_launch_and_0/supervisor-venv/lib/python3.11/site-packages/arnold_pipelines')
symlinks = False, ignore = None, copy_function = <function copy2 at 0x1051d0ae0>
ignore_dangling_symlinks = False, dirs_exist_ok = False

    def _copytree(entries, src, dst, symlinks, ignore, copy_function,
                  ignore_dangling_symlinks, dirs_exist_ok=False):
        if ignore is not None:
            ignored_names = ignore(os.fspath(src), [x.name for x in entries])
        else:
            ignored_names = ()
    
        os.makedirs(dst, exist_ok=dirs_exist_ok)
        errors = []
        use_srcentry = copy_function is copy2 or copy_function is copy
    
        for srcentry in entries:
            if srcentry.name in ignored_names:
                continue
            srcname = os.path.join(src, srcentry.name)
            dstname = os.path.join(dst, srcentry.name)
            srcobj = srcentry if use_srcentry else srcname
            try:
                is_symlink = srcentry.is_symlink()
                if is_symlink and os.name == 'nt':
                    # Special check for directory junctions, which appear as
                    # symlinks but we want to recurse.
                    lstat = srcentry.stat(follow_symlinks=False)
                    if lstat.st_reparse_tag == stat.IO_REPARSE_TAG_MOUNT_POINT:
                        is_symlink = False
                if is_symlink:
                    linkto = os.readlink(srcname)
                    if symlinks:
                        # We can't just leave it to `copy_function` because legacy
                        # code with a custom `copy_function` may rely on copytree
                        # doing the right thing.
                        os.symlink(linkto, dstname)
                        copystat(srcobj, dstname, follow_symlinks=not symlinks)
                    else:
                        # ignore dangling symlink if the flag is on
                        if not os.path.exists(linkto) and ignore_dangling_symlinks:
                            continue
                        # otherwise let the copy occur. copy2 will raise an error
                        if srcentry.is_dir():
                            copytree(srcobj, dstname, symlinks, ignore,
                                     copy_function, ignore_dangling_symlinks,
                                     dirs_exist_ok)
                        else:
                            copy_function(srcobj, dstname)
                elif srcentry.is_dir():
                    copytree(srcobj, dstname, symlinks, ignore, copy_function,
                             ignore_dangling_symlinks, dirs_exist_ok)
                else:
                    # Will raise a SpecialFileError for unsupported file types
                    copy_function(srcobj, dstname)
            # catch the Error from the recursive copytree so that we can
            # continue with other files
            except Error as err:
                errors.extend(err.args[0])
            except OSError as why:
                errors.append((srcname, dstname, str(why)))
        try:
            copystat(src, dst)
        except OSError as why:
            # Copying file access times may fail on Windows
            if getattr(why, 'winerror', None) is None:
                errors.append((src, dst, str(why)))
        if errors:
>           raise Error(errors)
E           shutil.Error: [('/Users/peteromalley/Documents/arnold-oracle/arnold_pipelines/megaplan/skills/babysit/SKILL.md', '/private/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/pytest-of-peteromalley/pytest-249/test_real_editable_launch_and_0/supervisor-venv/lib/python3.11/site-packages/arnold_pipelines/megaplan/skills/babysit/SKILL.md', "[Errno 2] No such file or directory: '/Users/peteromalley/Documents/arnold-oracle/arnold_pipelines/megaplan/skills/babysit/SKILL.md'")]

../../.pyenv/versions/3.11.11/lib/python3.11/shutil.py:527: Error
=========================== short test summary info ============================
FAILED tests/cloud/test_runtime_attestation.py::test_real_editable_launch_and_noneditable_supervisor_vectors - shutil.Error: [('/Users/peteromalley/Documents/arnold-oracle/arnold_pipelines/megaplan/skills/babysit/SKILL.md', '/private/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/pytest-of-peteromalley/pytest-249/test_real_editable_launch_and_0/supervisor-venv/lib/python3.11/site-packages/arnold_pipelines/megaplan/skills/babysit/SKILL.md', "[Errno 2] No such file or directory: '/Users/peteromalley/Documents/arnold-oracle/arnold_pipelines/megaplan/skills/babysit/SKILL.md'")]
1 failed, 80 passed in 14.78s

exec
/bin/zsh -lc 'ls -l arnold_pipelines/megaplan/skills/babysit/SKILL.md; git ls-files -s arnold_pipelines/megaplan/skills/babysit/SKILL.md; git diff 210bb6e078..HEAD -- arnold_pipelines/megaplan/skills/babysit/SKILL.md; python -m pytest tests/cloud/test_standalone_runtime_attestation.py -q' in /Users/peteromalley/Documents/arnold-oracle
 succeeded in 8249ms:
..........................................                               [100%]
42 passed in 4.87s

exec
/bin/zsh -lc "git diff --unified=20 210bb6e078..HEAD -- .oracle/status.md docs/custom-resident-agents.md; sed -n '1,760p' tests/cloud/test_standalone_runtime_attestation.py" in /Users/peteromalley/Documents/arnold-oracle
 succeeded in 0ms:
diff --git a/.oracle/status.md b/.oracle/status.md
index e3bddc0b27..01050da0a9 100644
--- a/.oracle/status.md
+++ b/.oracle/status.md
@@ -1,7 +1,9 @@
 # Status — megado run on Arnold
-- Phase: 4 complete → 5 (execute) — FROZEN tasklist accepted 2026-08-21
-- Base: 744a417198; foundation b7c682798e; contract eac81e57d2; plan 796961cd9c
-- Model policy: normal=codex:gpt-5.6-luna, [XHARD]=codex:gpt-5.6-sol, oracle=Sol
-- Next: Batch 1 (T3 Sol then T1 Luna), then oracle checkpoint
-- Blocker/escalation: none in-run; main-tree purge (bg_7) timed out — post-run resolution
-- 2026-08-21: user switched [XHARD] class to openrouter:stealth/ox-alpha (probe OK); oracle stays Sol. In-flight Sol T8b completes; applies from next [XHARD] dispatch.
+- Phase: 5 executing. B1-B4 PASS (+reworks closed). B5: T8a gate PASS, T8b implemented, rework attempts 1-5 (custody hardening loop), attempt-5 in flight.
+- USER-AUTHORIZED DEVIATIONS (2026-08-21):
+  - [XHARD] class switched to openrouter:stealth/ox-alpha (probe verified); oracle stays Sol.
+  - Batch gate relaxed: B6+B7 share one combined oracle gate (was per-batch).
+  - B6 parallelism authorized: T9 (Luna) and T10 (stealth) run concurrently; T10 codes against the frozen five-file contract, integrated at the B6 checkpoint.
+- Base: 744a417198 · foundation b7c682798e · contract eac81e57d2 · plan 796961cd9c · tasklist fde620d21d
+- Commits: B1 9224f52ce2 · B2 fd4f58b77a+1d9dc17f60 · B3 97bf1264c5+028cf9db97+f3bdcb9635 · B4 f4122bbebe+42f86de734+c522810273 · B5 c0c3af88a0(T8a)+902a2a46dd(T8b)+rework commits
+- Blockers: none in-run. Main-tree purge (bg_7) timed out mid-edit — post-run resolution owed to user.
diff --git a/docs/custom-resident-agents.md b/docs/custom-resident-agents.md
new file mode 100644
index 0000000000..e1b64d10ad
--- /dev/null
+++ b/docs/custom-resident-agents.md
@@ -0,0 +1,76 @@
+# Custom resident agents — install, customize, deploy
+
+This document covers the full custom-agent workflow: running `arnold` locally,
+customizing agents, and scaffolding a Discord resident bot into any repository
+with `agentbox new-resident`.
+
+> STATUS: skeleton drafted by the megado orchestrator (host). Executor T11
+> completes sections marked `[T11]` against the implemented behavior.
+
+## Run arnold (R1)
+
+```bash
+agentbox install-omp-agent arnold        # packaged source -> ~/.omp/agent/agents/
+~/.bun/bin/agent list                    # arnold appears
+~/.bun/bin/agent run arnold "State your name and rules."
+```
+
+**PATH caveat:** bare `agent` resolves to grok's binary (`~/.grok/bin/agent`) on
+this machine. Use `~/.bun/bin/agent` or set `OMP_BIN`.
+
+In-session dispatch: `{"agent": "arnold", "task": "…"}`.
+
+The prompt body of `agentbox/agents/arnold.md` is byte-identical to the live
+Discord resident prompt (`AgentBoxOperatorProfile.system_prompt()`,
+`agentbox-operator-v1`). A parity test enforces this.
+
+## Customize (R2)
+
+Two CLI flags only — everything else is edited in markdown:
+
+```bash
+agentbox install-omp-agent arnold --name my-op --description "Op for X" --target <dir>
+```
+
+- positional = source template; `--name` renames output + frontmatter;
+  `--description` replaces description; body bytes untouched.
+- names must match `^[A-Za-z0-9._-]+$` (not `.` / `..`); writes are atomic and
+  non-overwriting.
+- model / thinking-level / tools: edit the agent file frontmatter directly
+  (`model:`, `thinking-level:`, `tools:`), or use omp-native
+  `task.agentModelOverrides.<name>` / `modelRoles`.
+- **Agent-file `tools` never change Discord actions** — Discord tools come from
+  the resident profile's tool registry + authorizer.
+
+Canonical persona changes require all three: edit `agentbox/agents/arnold.md`,
+apply the identical change to `AgentBoxOperatorProfile.system_prompt()`, bump
+`AGENTBOX_OPERATOR_PROMPT_VERSION`. The parity test enforces byte equality.
+
+## Scaffold a bot in another repo (R3)
+
+```bash
+agentbox new-resident astrid --repo /path/to/astrid --description "…"
+```
+
+Generates exactly five files `[T11: confirm final set]`:
+
+| File | Purpose |
+|---|---|
+| `.omp/agents/<name>.md` | project-scoped named agent (shadows user-level inside this repo) |
+| `.agentbox/resident_profile.py` | profile subclass; system prompt from the project agent file |
+| `.agentbox/resident.env.example` | token var, model, allowlists, mode, store root |
+| `.agentbox/run-resident` | fixed-cwd launcher (executable) |
+| `.agentbox/<name>-resident.service` | systemd unit |
+
+External profiles are loaded repo-relative via `.agentbox/resident_profile.py:<Class>`
+— trusted project code, imported unsandboxed, contained under the repo root.
+
+## Deploy `[T11]`
+
+- one Discord application per repo (developer portal: name/avatar/message-content intent/permissions)
+- env file (uncommitted): `DISCORD_BOT_TOKEN`, allowlists, mode, store root
+- store: `<repo>/.megaplan/resident/` (FileStore; created on demand)
+- attestation: `<repo>` must be a clean git checkout at the expected HEAD;
+  provision the launch seed with `resident attest` `[T11: exact command per implementation]`
+- dry-run first: `--dry-run` constructs the profile without network
+- then systemd: `systemctl enable --now <name>-resident.service`
from __future__ import annotations

import hashlib
import json
import shutil
import stat
import sys
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.cloud import runtime_attestation as attestation
from arnold_pipelines.megaplan.cli import _main
from arnold_pipelines.megaplan.types import CliError


def _healthy_runtime_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, Any], Path, str]:
    """Issue a standalone seed with vectors isolated from host .pth state."""
    root = Path(__file__).resolve().parents[2]
    revision = attestation._git_revision(root)
    provenance = {
        "ok": True,
        "errors": [],
        "expected_root": str(root),
        "expected_revision": revision,
        "import_root": str(root),
        "editable_root": "",
        "direct_url": {},
        "pth": [],
        "source_revision": revision,
        "runtime_revision": revision,
        "imports": {},
    }
    modules = attestation._module_vector(root)[0]
    wrappers = attestation._wrapper_vector(root)[0]
    monkeypatch.setattr(attestation, "runtime_provenance", lambda **_: provenance)
    monkeypatch.setattr(attestation, "_pth_vector", lambda _root: ([], []))
    monkeypatch.setattr(attestation, "_module_vector", lambda _root: (modules, []))
    monkeypatch.setattr(attestation, "_wrapper_vector", lambda _root: (wrappers, []))
    seed = attestation.build_standalone_runtime_launch_seed(
        expected_root=root,
        expected_revision=revision,
        generated_at="2026-08-22T00:00:00Z",
    )
    assert seed["ready"] is True
    return seed, root, revision


def _recache(seed: dict[str, Any]) -> dict[str, Any]:
    core = {key: value for key, value in seed.items() if key != "content_sha256"}
    seed["content_sha256"] = attestation._canonical_sha256(core)
    return seed


def test_standalone_seed_validates_and_process_attestation_binds_authority(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    seed, _root, _revision = _healthy_runtime_fixture(monkeypatch)

    result = attestation.validate_runtime_launch_seed(seed, component="resident")
    assert result["status"] == "ready"
    assert result["authority"] == attestation.RUNTIME_LAUNCH_STANDALONE_AUTHORITY

    process = {
        "pid": 123,
        "start_ticks": "456",
        "executable": str(Path(sys.executable).resolve()),
        "executable_sha256": hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
        "selectors": {},
    }
    monkeypatch.setattr(attestation, "_proc_identity", lambda _pid: process)
    receipt = attestation.create_runtime_process_attestation(
        seed, component="resident", target_pid=123
    )
    assert receipt["authority"] == attestation.RUNTIME_LAUNCH_STANDALONE_AUTHORITY
    assert attestation.validate_runtime_process_attestation(
        seed, receipt, component="resident", target_pid=123
    )["status"] == "ready"

    state = tmp_path / "runtime-launch"
    state.mkdir(mode=0o700)
    state.chmod(0o700)
    monkeypatch.setattr(attestation, "standalone_runtime_launch_dir", lambda _root, create=True: state)
    paths = attestation.standalone_dispatch_paths(
        Path(str(seed["expected_root"])),
        head=str(seed["expected_revision"]),
        seed_sha256=str(seed["content_sha256"]),
    )
    published = attestation.write_standalone_runtime_publication(
        seed=seed,
        seed_path=paths["seed"],
        root=Path(str(seed["expected_root"])),
        generated_at=seed["generated_at"],
    )
    seed_path = paths["seed"]
    process_path = paths["status"]
    monkeypatch.setenv("MEGAPLAN_RUNTIME_LAUNCH_SEED", str(seed_path))
    monkeypatch.setenv("MEGAPLAN_RUNTIME_PROCESS_ATTESTATION", str(process_path))
    assert attestation.require_configured_runtime_launch(
        "resident", target_pid=123, create=True
    )["authority"] == attestation.RUNTIME_LAUNCH_STANDALONE_AUTHORITY
    assert json.loads(process_path.read_text(encoding="utf-8"))["authority"] == (
        attestation.RUNTIME_LAUNCH_STANDALONE_AUTHORITY
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("authority", attestation.RUNTIME_LAUNCH_CLOUD_AUTHORITY),
        ("authority", "arnold.megaplan.runtime-launch/unknown/v1"),
        ("expected_root", "/tmp/foreign-repository"),
        ("expected_revision", "a" * 40),
        ("live_revision", "b" * 40),
    ],
)
def test_standalone_seed_wrong_authority_root_or_head_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
) -> None:
    seed, _root, _revision = _healthy_runtime_fixture(monkeypatch)
    altered = {**seed, field: value}
    _recache(altered)
    with pytest.raises(CliError):
        attestation.validate_standalone_runtime_launch_seed(altered)


def test_standalone_seed_digest_requires_recognized_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, _root, _revision = _healthy_runtime_fixture(monkeypatch)
    missing = {key: value for key, value in seed.items() if key != "authority"}
    _recache(missing)
    with pytest.raises(CliError, match="digest"):
        attestation.validate_standalone_runtime_launch_seed(missing)


def test_cloud_worker_validation_rejects_standalone_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, _root, _revision = _healthy_runtime_fixture(monkeypatch)
    with pytest.raises(CliError):
        attestation.validate_runtime_launch_seed(seed, component="worker")


@pytest.mark.parametrize("errors", [None, {}, "not-a-list"])
def test_standalone_seed_requires_canonical_errors_vector(
    monkeypatch: pytest.MonkeyPatch,
    errors: Any,
) -> None:
    seed, _root, _revision = _healthy_runtime_fixture(monkeypatch)
    altered = dict(seed)
    if errors is None:
        altered.pop("errors")
    else:
        altered["errors"] = errors
    _recache(altered)
    with pytest.raises(CliError):
        attestation.validate_standalone_runtime_launch_seed(altered)


@pytest.mark.parametrize(
    "field",
    ["manifest_sha256", "marker", "supervisor_receipt", "supervisor_runtime", "hot_env", "chain_runtime_binding"],
)
def test_standalone_seed_rejects_nonempty_cloud_evidence(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    seed, _root, _revision = _healthy_runtime_fixture(monkeypatch)
    altered = {**seed, field: "cloud-evidence"}
    _recache(altered)
    with pytest.raises(CliError, match="cloud field"):
        attestation.validate_standalone_runtime_launch_seed(altered)


@pytest.mark.parametrize("vector", ["runtime_provenance", "loaded_modules", "site_pth", "wrappers", "interpreter"])
def test_standalone_seed_vector_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    vector: str,
) -> None:
    seed, _root, _revision = _healthy_runtime_fixture(monkeypatch)
    if vector == "runtime_provenance":
        monkeypatch.setattr(attestation, "runtime_provenance", lambda **_: {**seed[vector], "source_revision": "c" * 40})
    elif vector == "loaded_modules":
        monkeypatch.setattr(attestation, "_module_vector", lambda _root: ([{"module": "foreign", "path": "/tmp/foreign.py", "root": ""}], []))
    elif vector == "site_pth":
        monkeypatch.setattr(attestation, "_pth_vector", lambda _root: ([{"path": "/tmp/foreign.pth"}], []))
    elif vector == "wrappers":
        monkeypatch.setattr(attestation, "_wrapper_vector", lambda _root: ([{"path": "/tmp/changed", "sha256": "0" * 64}], []))
    else:
        monkeypatch.setattr(attestation, "_interpreter_vector", lambda **_: {"executable": "/tmp/foreign-python"})
    with pytest.raises(CliError):
        attestation.validate_standalone_runtime_launch_seed(seed)


def test_edited_seed_and_cloud_dispatch_path_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    edited = {**seed, "generated_at": "2026-08-23T00:00:00Z"}
    with pytest.raises(CliError, match="digest"):
        attestation.validate_standalone_runtime_launch_seed(edited)

    seed_path = tmp_path / "standalone.json"
    seed_path.write_text(json.dumps(seed), encoding="utf-8")
    assert attestation._launch_seed_current(
        seed_path,
        root=root,
        expected_revision=revision,
        marker_path=tmp_path / "marker.json",
        manifest_path=tmp_path / "manifest.json",
    ) is False


def test_standalone_process_attestation_cannot_cross_into_cloud_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, _root, _revision = _healthy_runtime_fixture(monkeypatch)
    process = {
        "pid": 123,
        "start_ticks": "456",
        "executable": str(Path(sys.executable).resolve()),
        "executable_sha256": hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
        "selectors": {},
    }
    monkeypatch.setattr(attestation, "_proc_identity", lambda _pid: process)
    resident_receipt = attestation.create_runtime_process_attestation(
        seed, component="resident", target_pid=123
    )
    forged = dict(resident_receipt)
    forged["component"] = "worker"
    forged_core = {key: forged.get(key) for key in (
        "schema", "authority", "component", "seed_sha256", "runtime_vector_sha256", "process"
    )}
    forged["content_sha256"] = attestation._canonical_sha256(forged_core)
    with pytest.raises(CliError):
        attestation.validate_runtime_process_attestation(
            seed, forged, component="worker", target_pid=123
        )


def test_standalone_admission_rejects_expected_head_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    with pytest.raises(CliError):
        attestation.build_standalone_runtime_launch_seed(
            expected_root=root,
            expected_revision=f" {revision} ",
        )


def test_publication_pointer_is_content_addressed_and_rejects_tampering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    state = tmp_path / "runtime-launch"
    state.mkdir(mode=0o700)
    state.chmod(0o700)
    monkeypatch.setattr(attestation, "standalone_runtime_launch_dir", lambda _root, create=True: state)
    paths = attestation.standalone_dispatch_paths(root, head=revision, seed_sha256=seed["content_sha256"])
    published = attestation.write_standalone_runtime_publication(
        seed=seed, seed_path=paths["seed"], root=root, generated_at=seed["generated_at"]
    )
    assert published["seed_path"] == paths["seed"]
    assert state.stat().st_mode & 0o777 == 0o700
    assert paths["seed"].parent.stat().st_mode & 0o777 == 0o700
    assert paths["receipts"].stat().st_mode & 0o777 == 0o700
    assert paths["status"].parent.stat().st_mode & 0o777 == 0o700
    assert paths["seed"].stat().st_mode & 0o777 == 0o600
    assert published["receipt_path"].stat().st_mode & 0o777 == 0o600
    assert attestation.load_standalone_runtime_dispatch_pointer(root)["authority"] == attestation.RUNTIME_LAUNCH_STANDALONE_AUTHORITY
    seed_path = paths["seed"]
    process = {
        "pid": 123,
        "start_ticks": "456",
        "executable": str(Path(sys.executable).resolve()),
        "executable_sha256": hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
        "selectors": {},
    }
    monkeypatch.setattr(attestation, "_proc_identity", lambda _pid: process)
    monkeypatch.setenv("MEGAPLAN_RUNTIME_LAUNCH_SEED", str(seed_path))
    monkeypatch.setenv("MEGAPLAN_RUNTIME_PROCESS_ATTESTATION", str(paths["status"]))
    attestation.require_configured_runtime_launch("resident", target_pid=123, create=True)
    assert paths["status"].stat().st_mode & 0o777 == 0o600

    pointer_path = paths["pointer"]
    valid_pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer_before_failed_issue = pointer_path.read_bytes()
    monkeypatch.setattr(
        attestation,
        "_wrapper_vector",
        lambda _root: ([{"path": "/tmp/foreign-wrapper", "sha256": "0" * 64}], []),
    )
    with pytest.raises(CliError):
        attestation.write_standalone_runtime_publication(
            seed=seed,
            seed_path=paths["seed"],
            root=root,
        )
    assert pointer_path.read_bytes() == pointer_before_failed_issue
    monkeypatch.setattr(attestation, "_wrapper_vector", lambda _root: (seed["wrappers"], []))
    pointer = dict(valid_pointer)
    pointer["seed_sha256"] = "0" * 64
    pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
    with pytest.raises(CliError, match="digest"):
        attestation.load_standalone_runtime_dispatch_pointer(root)

    pointer_path.unlink()
    outside = tmp_path / "outside-pointer.json"
    outside.write_text(json.dumps(valid_pointer), encoding="utf-8")
    pointer_path.symlink_to(outside)
    with pytest.raises(CliError):
        attestation.load_standalone_runtime_dispatch_pointer(root)


def test_resident_attest_json_and_plain_contract_via_adapter(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    expected = {
        "success": True,
        "authority": attestation.RUNTIME_LAUNCH_STANDALONE_AUTHORITY,
        "root": str(Path.cwd()),
        "expected_head": "a" * 40,
        "live_head": "a" * 40,
        "seed_path": "/repo/.megaplan/resident/runtime-launch/seeds/seed.json",
        "seed_sha256": "b" * 64,
        "receipt_path": "/repo/.megaplan/resident/runtime-launch/receipts/r.json",
        "receipt_sha256": "c" * 64,
        "pointer_path": "/repo/.megaplan/resident/runtime-launch/seeds/dispatch-current.json",
        "generated_at": "2026-08-22T00:00:00Z",
    }
    seed = {"expected_root": str(Path.cwd()), "expected_revision": "a" * 40, "content_sha256": "b" * 64}
    paths = {
        "seed": Path(expected["seed_path"]),
        "pointer": Path(expected["pointer_path"]),
    }
    receipt = {"authority": expected["authority"], "root": expected["root"],
               "expected_head": expected["expected_head"], "live_head": expected["live_head"],
               "content_sha256": expected["receipt_sha256"]}
    published = {"receipt": receipt, "pointer": {"generated_at": expected["generated_at"]},
                 "receipt_path": Path(expected["receipt_path"]), "pointer_path": paths["pointer"]}
    monkeypatch.setattr(attestation, "build_standalone_runtime_launch_seed", lambda **_: seed)
    monkeypatch.setattr(attestation, "validate_standalone_runtime_launch_seed", lambda *_args, **_kwargs: {"status": "ready"})
    monkeypatch.setattr(attestation, "standalone_dispatch_paths", lambda *_args, **_kwargs: paths)
    monkeypatch.setattr(attestation, "write_standalone_runtime_publication", lambda **_: published)
    assert _main(
        ["resident", "attest", "--repo-root", "/repo", "--expected-head", "a" * 40]
    ) == 0
    assert capsys.readouterr().out == expected["seed_path"] + "\n"
    assert _main(
        [
            "resident",
            "attest",
            "--repo-root",
            "/repo",
            "--expected-head",
            "a" * 40,
            "--json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out) == expected


def test_resident_attest_wrong_head_returns_admission_exit_code_2(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def reject_admission(**_kwargs: Any) -> dict[str, Any]:
        raise CliError(attestation.RUNTIME_ATTESTATION_ERROR, "HEAD mismatch")

    monkeypatch.setattr(
        attestation,
        "build_standalone_runtime_launch_seed",
        reject_admission,
    )
    rc = _main(
        [
            "resident",
            "attest",
            "--repo-root",
            str(Path.cwd()),
            "--expected-head",
            "0" * 40,
        ]
    )
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is False
    assert payload["error"] == attestation.RUNTIME_ATTESTATION_ERROR


def test_resident_attest_publication_failure_does_not_advance_pointer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = Path.cwd()
    head = attestation._git_revision(root)
    state = tmp_path / "runtime-launch"
    paths = {
        "seed": state / "seeds" / f"standalone-{head}-{'a' * 64}.json",
        "pointer": state / "seeds" / "dispatch-current.json",
    }
    paths["pointer"].parent.mkdir(parents=True)
    paths["pointer"].write_text('{"sentinel":true}\n', encoding="utf-8")
    before = paths["pointer"].read_bytes()
    seed = {
        "expected_root": str(root),
        "expected_revision": head,
        "content_sha256": "a" * 64,
    }

    monkeypatch.setattr(
        attestation,
        "build_standalone_runtime_launch_seed",
        lambda **_kwargs: seed,
    )
    monkeypatch.setattr(
        attestation,
        "validate_standalone_runtime_launch_seed",
        lambda *_args, **_kwargs: {"status": "ready"},
    )
    monkeypatch.setattr(
        attestation,
        "standalone_dispatch_paths",
        lambda *_args, **_kwargs: paths,
    )

    def reject_publication(**_kwargs: Any) -> dict[str, Any]:
        raise CliError(attestation.RUNTIME_ATTESTATION_ERROR, "publication refused")

    monkeypatch.setattr(
        attestation,
        "write_standalone_runtime_publication",
        reject_publication,
    )
    rc = _main(
        [
            "resident",
            "attest",
            "--repo-root",
            str(root),
            "--expected-head",
            head,
        ]
    )
    assert rc == 2
    assert paths["pointer"].read_bytes() == before
    assert json.loads(capsys.readouterr().out)["success"] is False


def _publish_healthy_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    seed: dict[str, Any],
    root: Path,
    revision: str,
) -> tuple[Path, dict[str, Path]]:
    """Publish a healthy standalone state into an isolated state directory."""
    state = tmp_path / "runtime-launch"
    state.mkdir(mode=0o700)
    monkeypatch.setattr(attestation, "standalone_runtime_launch_dir", lambda _root, create=True: state)
    paths = attestation.standalone_dispatch_paths(
        root, head=revision, seed_sha256=str(seed["content_sha256"])
    )
    attestation.write_standalone_runtime_publication(
        seed=seed, seed_path=paths["seed"], root=root, generated_at=seed["generated_at"]
    )
    return state, paths


def _patch_resident_process_identity(
    monkeypatch: pytest.MonkeyPatch,
    paths: dict[str, Path],
) -> None:
    process = {
        "pid": 123,
        "start_ticks": "456",
        "executable": str(Path(sys.executable).resolve()),
        "executable_sha256": hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
        "selectors": {},
    }
    monkeypatch.setattr(attestation, "_proc_identity", lambda _pid: process)
    monkeypatch.setenv("MEGAPLAN_RUNTIME_LAUNCH_SEED", str(paths["seed"]))
    monkeypatch.setenv("MEGAPLAN_RUNTIME_PROCESS_ATTESTATION", str(paths["status"]))


def test_worker_refresh_rejects_standalone_seed_without_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    _state, paths = _publish_healthy_state(tmp_path, monkeypatch, seed, root, revision)
    monkeypatch.setenv("MEGAPLAN_RUNTIME_LAUNCH_SEED", str(paths["seed"]))
    for absent_manifest in (True, False):
        if absent_manifest:
            monkeypatch.delenv("ARNOLD_RUNTIME_MANIFEST", raising=False)
        else:
            monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", "   ")
        with pytest.raises(CliError) as excinfo:
            attestation.refresh_runtime_launch_seed_for_worker_dispatch()
        assert excinfo.value.code == attestation.RUNTIME_ATTESTATION_ERROR
        assert "cloud-chain" in excinfo.value.message


@pytest.mark.parametrize("directory_name", ["seeds", "receipts", "status"])
def test_standalone_publication_rejects_unsafe_reused_directory_at_0755(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    directory_name: str,
) -> None:
    seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    state, paths = _publish_healthy_state(tmp_path, monkeypatch, seed, root, revision)
    pointer_before = paths["pointer"].read_bytes()
    unsafe = state / directory_name
    unsafe.chmod(0o755)
    with pytest.raises(CliError) as excinfo:
        attestation.write_standalone_runtime_publication(
            seed=seed, seed_path=paths["seed"], root=root, generated_at=seed["generated_at"]
        )
    assert excinfo.value.code == attestation.RUNTIME_ATTESTATION_ERROR
    assert stat.S_IMODE(unsafe.stat().st_mode) == 0o755  # never repaired
    assert paths["pointer"].read_bytes() == pointer_before

def test_standalone_publication_rejects_unsafe_mode_reuse_without_advancing_pointer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reused seed/receipt must be regular 0600 files matching their digests."""
    seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    state, paths = _publish_healthy_state(tmp_path, monkeypatch, seed, root, revision)
    pointer_before = paths["pointer"].read_bytes()
    # Valid 0600 idempotent reuse of BOTH immutable objects stays unchanged.
    attestation.write_standalone_runtime_publication(
        seed=seed, seed_path=paths["seed"], root=root, generated_at=seed["generated_at"]
    )
    assert paths["pointer"].read_bytes() == pointer_before
    # Tampered seed mode (content identical): reject, never advance or repair.
    paths["seed"].chmod(0o644)
    with pytest.raises(CliError) as excinfo:
        attestation.write_standalone_runtime_publication(
            seed=seed, seed_path=paths["seed"], root=root, generated_at=seed["generated_at"]
        )
    assert excinfo.value.code == attestation.RUNTIME_ATTESTATION_ERROR
    assert stat.S_IMODE(paths["seed"].stat().st_mode) == 0o644  # never repaired
    assert paths["pointer"].read_bytes() == pointer_before
    # Tampered receipt mode (content identical): same fail-closed behavior.
    paths["seed"].chmod(0o600)
    receipt_path = next((state / "receipts").glob("*.json"))
    receipt_path.chmod(0o664)
    with pytest.raises(CliError) as excinfo:
        attestation.write_standalone_runtime_publication(
            seed=seed, seed_path=paths["seed"], root=root, generated_at=seed["generated_at"]
        )
    assert excinfo.value.code == attestation.RUNTIME_ATTESTATION_ERROR
    assert stat.S_IMODE(receipt_path.stat().st_mode) == 0o664  # never repaired
    assert stat.S_IMODE(paths["seed"].stat().st_mode) == 0o600
    assert paths["pointer"].read_bytes() == pointer_before



def test_standalone_publication_rejection_does_not_create_missing_siblings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rejected publication with an unsafe ``status`` creates no missing siblings."""
    seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    state = tmp_path / "runtime-launch"
    state.mkdir(mode=0o700)
    state.chmod(0o700)
    monkeypatch.setattr(attestation, "standalone_runtime_launch_dir", lambda _root, create=True: state)
    unsafe_status = state / "status"
    unsafe_status.mkdir()
    unsafe_status.chmod(0o755)
    seed_path = state / "seeds" / f"standalone-{revision}-{seed['content_sha256']}.json"
    with pytest.raises(CliError) as excinfo:
        attestation.write_standalone_runtime_publication(
            seed=seed, seed_path=seed_path, root=root, generated_at=seed["generated_at"]
        )
    assert excinfo.value.code == attestation.RUNTIME_ATTESTATION_ERROR
    assert stat.S_IMODE(unsafe_status.stat().st_mode) == 0o755  # never repaired
    assert not (state / "seeds").exists()  # missing sibling never created by rejection
    assert not (state / "receipts").exists()  # missing sibling never created by rejection
    assert sorted(entry.name for entry in state.iterdir()) == ["status"]


@pytest.mark.parametrize("directory_name", ["seeds", "receipts", "status"])
def test_standalone_load_rejects_unsafe_reused_directory_at_0755(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    directory_name: str,
) -> None:
    seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    state, paths = _publish_healthy_state(tmp_path, monkeypatch, seed, root, revision)
    pointer_before = paths["pointer"].read_bytes()
    unsafe = state / directory_name
    unsafe.chmod(0o755)
    with pytest.raises(CliError):
        attestation.load_standalone_runtime_dispatch_pointer(root)
    assert stat.S_IMODE(unsafe.stat().st_mode) == 0o755  # never repaired
    assert paths["pointer"].read_bytes() == pointer_before


def test_standalone_load_rejects_missing_status_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    state, paths = _publish_healthy_state(tmp_path, monkeypatch, seed, root, revision)
    pointer_before = paths["pointer"].read_bytes()
    shutil.rmtree(state / "status")
    with pytest.raises(CliError):
        attestation.load_standalone_runtime_dispatch_pointer(root)
    assert not (state / "status").exists()  # never repaired
    assert paths["pointer"].read_bytes() == pointer_before
    assert stat.S_IMODE((state / "seeds").stat().st_mode) == 0o700
    assert stat.S_IMODE((state / "receipts").stat().st_mode) == 0o700


def test_resident_process_create_rejects_unsafe_status_directory_at_0755(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    state, paths = _publish_healthy_state(tmp_path, monkeypatch, seed, root, revision)
    _patch_resident_process_identity(monkeypatch, paths)
    unsafe = state / "status"
    unsafe.chmod(0o755)
    with pytest.raises(CliError) as excinfo:
        attestation.require_configured_runtime_launch("resident", target_pid=123, create=True)
    assert excinfo.value.code == attestation.RUNTIME_ATTESTATION_ERROR
    assert stat.S_IMODE(unsafe.stat().st_mode) == 0o755  # never repaired
    assert not paths["status"].exists()


def test_resident_process_read_rejects_unsafe_status_directory_at_0755(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    state, paths = _publish_healthy_state(tmp_path, monkeypatch, seed, root, revision)
    _patch_resident_process_identity(monkeypatch, paths)
    attestation.require_configured_runtime_launch("resident", target_pid=123, create=True)
    status_before = paths["status"].read_bytes()
    unsafe = state / "status"
    unsafe.chmod(0o755)
    with pytest.raises(CliError) as excinfo:
        attestation.require_configured_runtime_launch("resident", target_pid=123, create=False)
    assert excinfo.value.code == attestation.RUNTIME_ATTESTATION_ERROR
    assert stat.S_IMODE(unsafe.stat().st_mode) == 0o755  # never repaired
    assert paths["status"].read_bytes() == status_before


def test_standalone_load_rejection_does_not_mutate_filesystem(tmp_path: Path) -> None:
    """Rejected standalone loads create no directories and change no modes."""
    root = tmp_path / "repo"
    root.mkdir()

    def filesystem_snapshot() -> dict[str, tuple[str, int]]:
        return {
            str(path.relative_to(root)): (
                "dir" if path.is_dir() else "file",
                stat.S_IMODE(path.lstat().st_mode),
            )
            for path in sorted(root.rglob("*"))
        }

    def expect_rejection(context: str) -> None:
        before = filesystem_snapshot()
        with pytest.raises(CliError):
            attestation.load_standalone_runtime_dispatch_pointer(root)
        assert filesystem_snapshot() == before, f"load mutated filesystem: {context}"

    expect_rejection("missing .megaplan parent")
    (root / ".megaplan").mkdir(mode=0o700)
    expect_rejection("missing .megaplan/resident parent")
    (root / ".megaplan" / "resident").mkdir(mode=0o700)
    expect_rejection("missing runtime-launch state directory")
    state = root / ".megaplan" / "resident" / "runtime-launch"
    state.mkdir(mode=0o700)
    expect_rejection("missing operational directories")
    (state / "seeds").mkdir(mode=0o700)
    expect_rejection("missing receipts and status directories")
    assert not (state / "receipts").exists()  # never created by rejection
    assert not (state / "status").exists()  # never created by rejection
    (state / "receipts").mkdir(mode=0o700)
    (state / "status").mkdir(mode=0o700)
    expect_rejection("missing dispatch pointer")
    assert not (state / "seeds" / "dispatch-current.json").exists()
    state.chmod(0o755)
    expect_rejection("unsafe state directory mode")
    assert stat.S_IMODE(state.stat().st_mode) == 0o755  # never repaired
    state.chmod(0o700)
    (state / "receipts").chmod(0o755)
    expect_rejection("unsafe receipts directory mode")
    assert stat.S_IMODE((state / "receipts").stat().st_mode) == 0o755  # never repaired

exec
/bin/zsh -lc 'git log --oneline --decorate 210bb6e078..HEAD; git diff --name-status 210bb6e078..HEAD; git diff --check 210bb6e078..HEAD; git status --short -- arnold_pipelines/megaplan/cloud/runtime_attestation.py arnold_pipelines/megaplan/resident/cli.py tests/cloud/test_runtime_attestation.py tests/cloud/test_standalone_runtime_attestation.py docs/custom-resident-agents.md .oracle/status.md' in /Users/peteromalley/Documents/arnold-oracle
 succeeded in 0ms:
eb79d9ab7e (HEAD -> oracle-run) oracle batch 5: rework attempt 5 — custody-validated idempotent reuse before pointer advance
7422ff8cfc megado: record user-authorized deviations; draft R1-R3 docs skeleton
11109bfbd4 oracle batch 5: rework attempt 4 — preflight-then-create publication ordering
8f8e0c418f oracle batch 5: rework attempt 3 — non-mutating load-path custody validation
d6999063bf oracle batch 5: rework attempt 2 — status/ custody on direct pointer load
53f1a36d1c oracle batch 5: rework — worker-refresh authority gate, state-dir perm enforcement, typed authority guard
902a2a46dd oracle batch 5: standalone resident attest adapter (T8b)
M	.oracle/status.md
M	arnold_pipelines/megaplan/cloud/runtime_attestation.py
M	arnold_pipelines/megaplan/resident/cli.py
A	docs/custom-resident-agents.md
M	tests/cloud/test_runtime_attestation.py
A	tests/cloud/test_standalone_runtime_attestation.py

exec
/bin/zsh -lc 'rg -l "resident attest|run_resident_cli|resident_action" tests | sort; rg -n "def _json_file|def _git_revision|def _module_vector|def _pth_vector|def _wrapper_vector|def runtime_provenance" arnold_pipelines/megaplan/cloud/runtime_attestation.py; git show 210bb6e078:arnold_pipelines/megaplan/cloud/runtime_attestation.py >/dev/null && git merge-base --is-ancestor 210bb6e078 HEAD && echo base-is-ancestor' in /Users/peteromalley/Documents/arnold-oracle
 succeeded in 0ms:
tests/resident/test_resident_schedules.py
tests/resident/test_vp_todo_tools.py
124:def _json_file(path: Path, *, label: str) -> dict[str, Any]:
137:def _git_revision(root: Path) -> str:
194:def _module_vector(expected_root: Path) -> tuple[list[dict[str, str]], list[str]]:
297:def _pth_vector(expected_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
476:def _wrapper_vector(expected_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
base-is-ancestor

exec
/bin/zsh -lc "git log --all --oneline --decorate --grep='discriminator\\|T8a\\|gate' -30; git show --stat --oneline c0c3af88a0 2>/dev/null || true; git branch --contains c0c3af88a0 2>/dev/null || true; git merge-base c0c3af88a0 HEAD 2>/dev/null || true" in /Users/peteromalley/Documents/arnold-oracle
 succeeded in 66ms:
* oracle-run
c0c3af88a02dca3739bdc4441abf7565f39794ad

exec
/bin/zsh -lc "sed -n '1,220p' .oracle/checkins/standalone-authority-gate.txt; git log --oneline --ancestry-path c0c3af88a0..210bb6e078 | head -20; git show -s --format='%H %P %s' 210bb6e078 c0c3af88a0 902a2a46dd" in /Users/peteromalley/Documents/arnold-oracle
 succeeded in 0ms:
# T8a standalone authority gate

**Verdict: PASS.** Existing provenance/vector collectors, canonical digest validation, O_EXCL immutable publication, atomic pointer publication, and process-attestation primitives can express this fail-closed. T8b must extend the canonical module; it must not weaken or bypass the cloud/chain path.

## 1. Authority discriminator

Keep seed `schema = "arnold.megaplan.runtime_launch_seed.v1"`. Add the mandatory, digest-covered field:

- `authority = "arnold.megaplan.runtime-launch/cloud-chain/v1"` for seeds from `build_runtime_launch_seed` / `ensure_runtime_launch_seed`.
- `authority = "arnold.megaplan.runtime-launch/standalone-resident/v1"` for seeds from the new standalone builder used only by `resident attest`.

Missing, unknown, or mismatched authority fails; there is no legacy/missing-field fallback. `_verify_seed_digest` must require the schema, canonical `content_sha256`, and one recognized authority. `validate_runtime_launch_seed` must select exactly one validator and never retry the other: cloud requires all existing manifest-generation, marker launch-binding, supervisor receipt/runtime, hot-env, and chain-runtime-binding checks; standalone requires the standalone evidence below and rejects nonempty `manifest_sha256`, `marker`, `supervisor_receipt`, `supervisor_runtime`, `hot_env`, or `chain_runtime_binding`.

`_launch_seed_current`, `_find_current_seed`, `ensure_runtime_launch_seed`, and `refresh_runtime_launch_seed_for_worker_dispatch` require cloud-chain. The standalone builder/pointer loader require standalone-resident. `require_configured_runtime_launch`, `create_runtime_process_attestation`, and `validate_runtime_process_attestation` must preserve and check the selected authority; the process receipt includes `authority`. A dual-authority resident may dispatch once on the exact field, but validation may not fall back across domains.

## 2. Standalone evidence

The digest-covered standalone seed contains: resolved `expected_root`; explicit full `expected_revision`; separately collected `live_revision`; existing `schema`; exact `authority`; RFC3339 UTC `generated_at`; `runtime_provenance`; `loaded_modules`; `interpreter`; `site_pth`; `wrappers`; `errors`; `ready`; and canonical `content_sha256`.

`--repo-root` is resolved with `strict=True`; `git rev-parse --show-toplevel` must equal it. `--expected-head` must be a full hex commit OID and equal `git rev-parse HEAD` byte-for-byte. Collect with the existing `runtime_provenance`, `_module_vector`, `_pth_vector`, `_wrapper_vector`, `_interpreter_vector`, and revision helpers. Re-run the same vectors at startup. Foreign module/PTH roots, changed wrapper/interpreter/provenance, edited seed/digest, wrong root, or HEAD drift fails with `runtime_launch_attestation_mismatch`. Timestamp is audit evidence, not an expiry or waiver. No cloud marker, manifest, chain spec/binding, hot-env, or supervisor evidence is synthesized.

## 3. State directory

Use `<resolved-repo-root>/.megaplan/resident/runtime-launch/`; `.agentbox/` remains readable scaffold/config, not operational state.

- `seeds/standalone-<head>-<content_sha256>.json`
- `seeds/dispatch-current.json`
- `receipts/<receipt-content_sha256>.json`
- `status/resident.runtime-process-attestation.json`

Create directories `0700`; seeds, receipts, pointer, and status files are `0600`. Reject symlink/containment escape at every resolved path. Publish immutable seed and issuance receipt with `_exclusive_write_json` (extend its mode parameter, retaining `O_EXCL|O_NOFOLLOW`); publish pointer and per-process status with `_atomic_write` (`fsync` then `os.replace`). The standalone pointer has `schema = "arnold.megaplan.standalone_runtime_dispatch_pointer.v1"`, authority, absolute seed/receipt paths, root, expected revision, generation time, seed digest, and receipt digest. Validate containment and both referenced digests before reuse.

## 4. `resident attest`

`megaplan resident attest --repo-root ROOT --expected-head OID [--json]`

It performs the admission checks above, builds then validates the standalone seed, writes the immutable seed and issuance receipt, atomically advances the pointer, and validates the published objects again. Receipt schema is `arnold.megaplan.standalone_runtime_attestation_receipt.v1`; it records authority, root, expected/live HEAD, generated time, seed path/digest, pointer path, and its own canonical digest.

Without `--json`, stdout is only the absolute seed path for launcher export. With it, stdout is one object containing `success`, authority, root, expected/live HEAD, `seed_path`, `seed_sha256`, `receipt_path`, `receipt_sha256`, `pointer_path`, and `generated_at`. Exit `0` on success; `2` for argument/admission/custody mismatch; `1` for unexpected publication/I/O failure. Failure never advances the pointer.

Research receipt: GPT-5.6 Luna/high audited the machinery; GPT-5.6 Sol/high independently validated and froze this decision.
210bb6e078 megado: user model switch — [XHARD] = openrouter:stealth/ox-alpha
210bb6e078600ac706efc7afdb454c0241ca2e91 c0c3af88a02dca3739bdc4441abf7565f39794ad megado: user model switch — [XHARD] = openrouter:stealth/ox-alpha
c0c3af88a02dca3739bdc4441abf7565f39794ad c522810273576071b50b19d59b4670a5e2eee5d5 oracle batch 5: T8a authority gate — standalone discriminator frozen (PASS)
902a2a46ddb2b65bcf8dac35e3b5eecfc3ff879a 210bb6e078600ac706efc7afdb454c0241ca2e91 oracle batch 5: standalone resident attest adapter (T8b)

exec
/bin/zsh -lc "sed -n '105,160p' arnold_pipelines/megaplan/cloud/runtime_attestation.py; sed -n '1380,1528p' arnold_pipelines/megaplan/cloud/runtime_attestation.py; rg -n \"_verify_seed_digest\\(|authority.*RUNTIME_LAUNCH|RUNTIME_LAUNCH_CLOUD_AUTHORITY\" arnold_pipelines/megaplan/cloud/runtime_attestation.py" in /Users/peteromalley/Documents/arnold-oracle
 succeeded in 0ms:
        info = resolved.stat()
        data = resolved.read_bytes()
    except OSError:
        return {
            "path": str(resolved),
            "exists": False,
            "sha256": "",
            "size": 0,
            "mode": "",
        }
    return {
        "path": str(resolved),
        "exists": True,
        "sha256": _sha256_bytes(data),
        "size": len(data),
        "mode": stat.filemode(info.st_mode),
    }


def _json_file(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            f"{label} is unreadable or invalid JSON: {path}",
        ) from exc
    if not isinstance(value, dict):
        raise CliError(RUNTIME_ATTESTATION_ERROR, f"{label} must be a JSON object")
    return value


def _git_revision(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_branch(root: Path) -> str:
    """Return the current branch name, or empty string on failure."""
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_ancestry(root: Path, ancestor: str, descendant: str) -> bool:
    """Return True if *ancestor* is reachable from *descendant* (i.e., descendant contains ancestor)."""
    if not ancestor or not descendant:
        "seed_path": str(seed_path.resolve(strict=False)),
        "seed_sha256": str(seed["content_sha256"]),
        "pointer_path": str(pointer_path.resolve(strict=False)),
    }
    return {**core, "content_sha256": _canonical_sha256(core)}


def load_standalone_runtime_dispatch_pointer(root: Path) -> dict[str, Any]:
    state = standalone_runtime_launch_dir(root, create=False)
    for name in ("seeds", "receipts", "status"):
        _require_standalone_operational_dir(state, name, create=False)
    pointer_path = state / "seeds" / "dispatch-current.json"
    if pointer_path.is_symlink() or pointer_path.parent.is_symlink():
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer is a symlink")
    try:
        if stat.S_IMODE(pointer_path.stat().st_mode) != 0o600:
            raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer permissions are unsafe")
    except OSError:
        pass
    pointer = _json_file(pointer_path, label="standalone runtime dispatch pointer")
    if pointer.get("schema") != STANDALONE_DISPATCH_POINTER_SCHEMA or pointer.get("authority") != RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer authority is invalid")
    resolved_root = Path(str(root)).expanduser().resolve(strict=True)
    if str(pointer.get("root") or "") != str(resolved_root):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer root mismatch")
    seed_path = Path(str(pointer.get("seed_path") or ""))
    receipt_path = Path(str(pointer.get("receipt_path") or ""))
    for path in (seed_path, receipt_path):
        if not path.is_absolute() or not path.exists() or path.is_symlink():
            raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer path is unsafe")
        try:
            if stat.S_IMODE(path.stat().st_mode) != 0o600:
                raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch object permissions are unsafe")
        except OSError as exc:
            raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch object is unreadable") from exc
        state = standalone_runtime_launch_dir(resolved_root, create=False)
        try:
            lexical = path.relative_to(state)
        except ValueError as exc:
            raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer escaped state directory") from exc
        _require_standalone_operational_dir(state, lexical.parts[0], create=False)
        current = state
        for part in lexical.parts:
            current = current / part
            if current.is_symlink():
                raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch path contains a symlink")
        try:
            path.resolve(strict=True).relative_to(state.resolve(strict=True))
        except ValueError as exc:
            raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer escaped state directory") from exc
    seed = _json_file(seed_path, label="standalone runtime launch seed")
    receipt = _json_file(receipt_path, label="standalone runtime attestation receipt")
    _verify_seed_digest(seed)
    if seed.get("content_sha256") != pointer.get("seed_sha256"):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch seed digest mismatch")
    if seed.get("expected_revision") != pointer.get("expected_revision"):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch seed revision mismatch")
    if receipt.get("content_sha256") != pointer.get("receipt_sha256"):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch receipt digest mismatch")
    receipt_core = {key: value for key, value in receipt.items() if key != "content_sha256"}
    if receipt.get("schema") != STANDALONE_ATTESTATION_RECEIPT_SCHEMA or receipt.get("authority") != RUNTIME_LAUNCH_STANDALONE_AUTHORITY or receipt.get("content_sha256") != _canonical_sha256(receipt_core):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone attestation receipt is invalid")
    if receipt.get("seed_path") != str(seed_path.resolve(strict=False)) or receipt.get("seed_sha256") != seed.get("content_sha256"):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone attestation receipt seed binding is invalid")
    if receipt.get("pointer_path") != str(pointer_path.resolve(strict=False)):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone attestation receipt pointer binding is invalid")
    if (
        receipt.get("root") != pointer.get("root")
        or receipt.get("expected_head") != pointer.get("expected_revision")
        or receipt.get("live_head") != seed.get("live_revision")
        or receipt.get("generated_at") != seed.get("generated_at")
        or pointer.get("generated_at") != seed.get("generated_at")
    ):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone attestation receipt root/revision binding is invalid")
    validate_standalone_runtime_launch_seed(seed)
    return pointer


def _verify_reused_immutable_object(
    path: Path, payload: Mapping[str, Any], *, label: str
) -> None:
    """Accept a ``FileExistsError`` reuse only when custody is intact.

    The existing object must be a regular non-symlink file with mode exactly
    ``0600`` whose canonical digest matches the expected immutable object.
    Anything else rejects without repair, chmod, or mutation so the dispatch
    pointer can never advance onto a tampered custody object.
    """
    try:
        st = path.lstat()
    except OSError as exc:
        raise CliError(RUNTIME_ATTESTATION_ERROR, f"standalone {label} is unreadable") from exc
    if path.is_symlink() or not stat.S_ISREG(st.st_mode):
        raise CliError(RUNTIME_ATTESTATION_ERROR, f"standalone {label} is not a regular file")
    if stat.S_IMODE(st.st_mode) != 0o600:
        raise CliError(RUNTIME_ATTESTATION_ERROR, f"standalone {label} permissions are unsafe")
    existing = _json_file(path, label=f"standalone runtime {label}")
    expected_digest = str(payload.get("content_sha256") or "")
    existing_core = {key: value for key, value in existing.items() if key != "content_sha256"}
    if (
        existing.get("content_sha256") != expected_digest
        or _canonical_sha256(existing_core) != expected_digest
        or existing != dict(payload)
    ):
        raise CliError(RUNTIME_ATTESTATION_ERROR, f"immutable standalone {label} collision")


def write_standalone_runtime_publication(
    *, seed: Mapping[str, Any], seed_path: Path, root: Path, generated_at: str | None = None
) -> dict[str, Any]:
    """Publish a resident seed, issuance receipt, and dispatch pointer."""
    validate_standalone_runtime_launch_seed(seed)
    root, expected, live = _standalone_admission(root, str(seed.get("expected_revision") or ""))
    if str(seed.get("expected_root") or "") != str(root) or live != str(seed.get("live_revision") or ""):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone seed changed during publication")
    paths = standalone_dispatch_paths(root, head=expected, seed_sha256=str(seed["content_sha256"]))
    if paths["seed"].resolve(strict=False) != seed_path.resolve(strict=False):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone seed path is not root-custodied")
    try:
        _exclusive_write_json(paths["seed"], seed, mode=0o600)
    except FileExistsError:
        _verify_reused_immutable_object(paths["seed"], seed, label="launch seed")
    receipt = build_standalone_runtime_attestation_receipt(
        seed=seed, seed_path=paths["seed"], pointer_path=paths["pointer"], generated_at=generated_at
    )
    receipt_path = _standalone_path(
        root, f"receipts/{receipt['content_sha256']}.json"
    )
    try:
        _exclusive_write_json(receipt_path, receipt, mode=0o600)
    except FileExistsError:
        _verify_reused_immutable_object(receipt_path, receipt, label="attestation receipt")
    pointer = {
        "schema": STANDALONE_DISPATCH_POINTER_SCHEMA,
        "authority": RUNTIME_LAUNCH_STANDALONE_AUTHORITY,
        "seed_path": str(paths["seed"].resolve(strict=False)),
        "receipt_path": str(receipt_path.resolve(strict=False)),
        "root": str(root),
        "expected_revision": expected,
        "generated_at": str(seed.get("generated_at") or generated_at or now_utc()),
        "seed_sha256": str(seed["content_sha256"]),
        "receipt_sha256": str(receipt["content_sha256"]),
    }
    if paths["pointer"].is_symlink():
        raise CliError(RUNTIME_ATTESTATION_ERROR, "standalone dispatch pointer is a symlink")
    _atomic_write(paths["pointer"], pointer)
    # Re-read and validate every published object before handing it to a caller.
    published = load_standalone_runtime_dispatch_pointer(root)
    if published != pointer:
29:RUNTIME_LAUNCH_CLOUD_AUTHORITY = "arnold.megaplan.runtime-launch/cloud-chain/v1"
32:    {RUNTIME_LAUNCH_CLOUD_AUTHORITY, RUNTIME_LAUNCH_STANDALONE_AUTHORITY}
36:CLOUD_CHAIN_AUTHORITY = RUNTIME_LAUNCH_CLOUD_AUTHORITY
766:        "authority": RUNTIME_LAUNCH_CLOUD_AUTHORITY,
980:        _verify_seed_digest(seed)
983:    if seed.get("authority") != RUNTIME_LAUNCH_CLOUD_AUTHORITY:
1197:        "authority": RUNTIME_LAUNCH_STANDALONE_AUTHORITY,
1219:    _verify_seed_digest(seed)
1220:    if seed.get("authority") != RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
1294:        "authority": RUNTIME_LAUNCH_STANDALONE_AUTHORITY,
1370:    _verify_seed_digest(seed)
1371:    if seed.get("authority") != RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
1375:        "authority": RUNTIME_LAUNCH_STANDALONE_AUTHORITY,
1400:    if pointer.get("schema") != STANDALONE_DISPATCH_POINTER_SCHEMA or pointer.get("authority") != RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
1432:    _verify_seed_digest(seed)
1440:    if receipt.get("schema") != STANDALONE_ATTESTATION_RECEIPT_SCHEMA or receipt.get("authority") != RUNTIME_LAUNCH_STANDALONE_AUTHORITY or receipt.get("content_sha256") != _canonical_sha256(receipt_core):
1514:        "authority": RUNTIME_LAUNCH_STANDALONE_AUTHORITY,
1932:    if current.get("authority") != RUNTIME_LAUNCH_CLOUD_AUTHORITY:
1968:def _verify_seed_digest(seed: Mapping[str, Any]) -> None:
1974:        or authority not in RUNTIME_LAUNCH_AUTHORITIES
2023:    _verify_seed_digest(seed)
2025:    if authority == RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
2027:    if authority != RUNTIME_LAUNCH_CLOUD_AUTHORITY:
2357:    _verify_seed_digest(seed)
2359:        seed.get("authority") == RUNTIME_LAUNCH_STANDALONE_AUTHORITY
2462:    if seed is not None and seed.get("authority") == RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
2490:    if not isinstance(authority, str) or authority not in RUNTIME_LAUNCH_AUTHORITIES:
2492:    if authority == RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
2502:    if authority == RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
2519:        if authority == RUNTIME_LAUNCH_STANDALONE_AUTHORITY:

exec
/bin/zsh -lc "rg -n \"write_standalone_runtime_publication\\(\" -g'*.py' .; rg -n \"generated_at=\" tests/cloud/test_standalone_runtime_attestation.py arnold_pipelines/megaplan | head -100; git show 902a2a46dd:arnold_pipelines/megaplan/cloud/runtime_attestation.py | sed -n '1300,1500p' 2>/dev/null | head" in /Users/peteromalley/Documents/arnold-oracle
 succeeded in 2ms:
    if seed.get("authority") != RUNTIME_LAUNCH_STANDALONE_AUTHORITY:
        raise CliError(RUNTIME_ATTESTATION_ERROR, "receipt requires standalone-resident seed")
    core = {
        "schema": STANDALONE_ATTESTATION_RECEIPT_SCHEMA,
        "authority": RUNTIME_LAUNCH_STANDALONE_AUTHORITY,
        "root": str(Path(str(seed["expected_root"])).resolve(strict=True)),
        "expected_head": str(seed["expected_revision"]),
        "live_head": str(seed.get("live_revision") or ""),
        "generated_at": generated_at or str(seed.get("generated_at") or now_utc()),
        "seed_path": str(seed_path.resolve(strict=False)),

collab: Wait
exec
/bin/zsh -lc 'python -m pytest tests/resident/test_resident_schedules.py tests/resident/test_vp_todo_tools.py -q' in /Users/peteromalley/Documents/arnold-oracle
 succeeded in 7453ms:
.................................................                        [100%]
49 passed in 5.84s

codex
PASS — Authority domain separation and fail-closed custody invariants hold; 42 standalone tests pass, with no Batch 5 blocker found.
tokens used
108,438
PASS — Authority domain separation and fail-closed custody invariants hold; 42 standalone tests pass, with no Batch 5 blocker found.
