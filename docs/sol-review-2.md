## 1. Correction audit

- **Phase-worker — addressed at plan level, not closed.** §1 correctly captures the bypasses and §4 Phase 0 adds availability detection, routing, dispatcher registration, fallback-family handling, sandbox gating, and failure tests. The original conditions landed. Two defects remain: the default `omp:deepseek/deepseek-v4-flash` conflicts with the later `omp:deepseek:…` grammar; and “map failures → retryable classes” is not an executable contract. Direct-path and dispatcher-path parity still needs a table-driven test.

- **Resident — addressed for provider replacement; not yet for the platform claim.** §1 and §4 Phase 1 correctly add backend capabilities, command construction, evidence normalization, session handshake, and Python-side stateless hot-context composition. The round-1 correction landed. However, the plan still says in §3 that a domain resident “needs only the agent file,” while the same section requires tools, persistence, and optional hooks. That contradiction matters.

- **Subagent — correction adequately refined.** §1 correctly downgrades `_run_check` to deprecated/test-only and §4 Phase 1 explicitly preserves shared-cwd/no-worktree fanout through RPC rather than `omp task`. This is the right position. It still needs an explicit output, timeout, cancellation, and manifest-parity test for RPC fanout.

- **Cloud — only partially addressed.** The six-wrapper/watchdog census and Bun finding in §1 are useful, and §4 Phase 1 names classifier/heartbeat work. But “all Hermes usage” is broader than those wrappers. A live default remains in [`agentbox-discord-resident.service`](../Arnold/agentbox/systemd/agentbox-discord-resident.service:12), and cloud bootstrap still creates/seeds Hermes state in [`entrypoint.sh.tmpl`](../Arnold/arnold_pipelines/megaplan/cloud/templates/entrypoint.sh.tmpl:9) and lines 68–70. These are absent from the migration list.

- **Delete Hermes — not adequately addressed.** §4 Phase 2 recognizes relocation, but the proposed relocation is not real yet: `runtime/sandbox.py` still imports `arnold.agent.tools.*`, and `runtime/key_pool.py` still imports `arnold.agent.providers.pool`. Current live consumers include resident runtime, preflight, profiles, and tests. “Delete `providers/`” plus “keep relocated key_pool” is unresolved. The §4 acceptance claim that `rg "arnold.agent"` leaves only neutral surfaces is impossible without a full import/conformance migration.

## 2. New-goal audit

The fork-cleanliness strategy is directionally right but not yet clean by proof. Reverting `src/task/agents.ts` and the bundled prompt is necessary, not sufficient:

- Generated Bun/TypeScript bundles, build output, package exports, lockfiles, or cached compiled agent definitions may still embed `agents.ts` behavior. A clean checkout must be built from scratch and inspected, not merely diffed at source level.
- An already-installed `~/.omp/agent/agents/resident.md` can make local tests pass while a fresh machine fails. The launcher needs deterministic install/discovery semantics, precedence rules for user versus project agents, version/hash validation, and a cold-start test with empty caches.
- The plan does not specify cache invalidation for the `agents.ts`/agent registry path, nor a package-level assertion that the fork contains only the stated docs/script changes.
- Existing Arnold deployment/config references to Hermes remain, as above.

The Astrid story is incomplete. A second resident needs, beyond an agent file:

1. Tool registration and permission boundaries for the Astrid CLI gateway.
2. Credential/environment provisioning and working-directory policy.
3. Session identity, persistence, resume, crash recovery, and concurrency rules.
4. Domain-specific evidence/output normalization into the resident store, manifest, ledger, and notifications.
5. Supervision, heartbeat, watchdog classification, and delivery hooks.
6. A CLI/bootstrap contract and a live end-to-end Astrid test.

## 3. Remaining gaps

- **OmpAdapter:** §4 Phase 0 needs an explicit mapping matrix: RPC launch failure, EOF, malformed JSONL, timeout, SIGTERM/SIGKILL, provider 429/5xx, auth, quota, unsupported model, context overflow, tool failure, missing final text, malformed payload, and schema failure. Generic adapter errors must not become availability failures. Retries must be bounded, attempt-idempotent, and forbidden after execute-side effects unless the existing `ExecuteFallbackUnsafe` policy applies.

- **Watchdog:** adding `"omp"` to `_CATEGORIES` is insufficient. The actual process may appear as generic `bun` with `src/cli.ts --mode rpc`; correlation must use process group, session directory, plan/attempt token, cwd, birth time, and heartbeat. Killing the parent must reliably kill the RPC child tree. Test orphan, PID reuse, stale heartbeat, and wrapper restart cases.

- **Sandbox:** bwrap is the correct Linux target; seatbelt is Mac-specific. The current cloud image already installs bubblewrap, but that does not prove unprivileged user namespaces or the required mount/network behavior. Define the exact mount map, writable roots, credential exposure, `/tmp`, `.git`, symlink, child-process, and network policy, then test it on the actual agentbox. “Containerized” is not evidence of per-run isolation.

- **Cost:** assistant-message usage may contain multiple tool-loop messages and cache buckets. The adapter must aggregate exactly once per RPC attempt, preserve input/output/cache-read/cache-write fields, attach model/provider identity, and reconcile receipt totals, ledger totals, and provider billing. Zero-cost or double-counted successful runs must fail validation.

- **Session equivalence:** the plan says Python composes full hot context while also reusing omp session directories. That can duplicate context on resume. Choose explicitly between stateless fresh sessions and omp-native continuation. Replay tests need restart, retry, process kill, concurrent-session, and duplicate-prompt assertions—not merely store/manifest shape parity.

- **Additional omission:** replace Hermes defaults and credential paths in systemd, cloud templates, docs/config examples, generated deployment artifacts, and test fixtures. “All Hermes usage” needs a categorized executable-reference acceptance test.

## 4. Final confidence call

**72/100.** The architecture is substantially improved and the round-1 corrections mostly landed, but the plan is not sound enough to execute unchanged.

To reach 90+:

1. **Hermes closure + fork-clean release gate** — exhaustive executable census, fresh-build/cache test, deployment/config cleanup, and clean-diff assertion. **1–2 days.**
2. **OmpAdapter contract suite** — fake-RPC failure matrix, usage/cost reconciliation, direct/dispatcher parity, and representative live phase corpus. **2–4 days.**
3. **Agentbox operational proof** — bwrap capability test, adversarial filesystem/process tests, watchdog/heartbeat end-to-end recovery, and resident session replay. **2–3 days.**

**Showstopper:** as written, the plan does not prove that a fresh deployment can run with zero Hermes references; the live resident service default and Hermes bootstrap paths must be closed first.
