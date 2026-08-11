> **Authority status (T44):** Zero-authority historical planning artifact — for reference only; not live operational authority. Canonical delegation is via the megaplan CLI and the migrated wrappers.

# SOL verdict

The plan is directionally right, but its central claim—“Hermes is only a backend behind one thin interface”—is false in the current checkout. Production phase dispatch bypasses `ArnoldDispatcher` when `MEGAPLAN_USE_AGENT_DISPATCHER` is off (`workers/_impl.py:7519`), and several direct Hermes paths remain.

## 1. Sense-check verdicts

| Area | Verdict | Main conditions / flaws |
|---|---|---|
| Phase-worker swap | **Sound-with-conditions** | Phase 0 is under-scoped: `_is_agent_available()` only special-cases Hermes and the direct dispatch branch handles Hermes/Claude/Codex, while flag-on dispatcher registration hard-codes `DeepSeekAdapter` (`workers/_impl.py:6599`, `7519–7663`). More importantly, `--yolo` does not reproduce Hermes’s tool-layer write/exec boundary; real schema, timeout, process-kill, and malformed-output tests are mandatory. |
| Resident swap | **Sound-with-conditions** | The provider abstraction is reusable, but omp is currently rejected by `MANAGED_AGENT_BACKENDS`, has no capability record, no session-ID policy, no evidence parser, and no `_command` branch (`routing.py`, `provider_runtime.py`, `agent_loop.py:601–640`). Persistent omp sessions must not be assumed equivalent to Arnold’s conversation/hot-context contract. |
| Subagent swap | **Not-sound as written** | `fan.py` and `launch_hermes_agent.py` are not the whole surface: legacy `_run_check()` in `orchestration/parallel_critique.py:305–365` still constructs `AIAgent`. Replacing same-process/shared-cwd fanout with omp `task` changes isolation, worktree, tool, timeout, and output semantics; use RPC fanout first unless those differences are explicitly accepted. |
| Cloud-wrapper swap | **Not-sound as written** | The inventory misses direct consumers in `arnold-repair-loop` and `arnold-watchdog`, not just `arnold-kimi-goal-operator`. The watchdog classifies and reaps literal `arnold.agent.run_agent` processes, so changing the launch command without changing custody/liveness logic creates an operational blind spot. Bun/omp installation also needs proof in cloud images and Hetzner deployment paths. |
| Delete-Hermes cleanup | **Not-sound** | The plan says to keep `runtime/sandbox.py` and `runtime/key_pool.py` while deleting the internals they re-export from (`arnold.agent.tools.*`, `arnold.agent.providers.pool`): that is an unresolved import contradiction, not a cleanup detail. Direct imports remain in legacy critique, tests, cloud wrappers, docs, and launch scripts; deletion requires a complete import/process/config graph, not a grep heuristic. |

The plan is overconfident in saying every LLM call already routes through `contracts.py`/`routing.py`/`ArnoldDispatcher`, and in treating the cloud surface as essentially one wrapper. It is also under-evidenced on sandbox equivalence, structured output over RPC, persistent-session identity, and actual cost events.

## 2. Section 9 answers

1. **No irreplaceable Hermes capability is proven, but deletion is not justified until real omp runs cover tool-loop behavior, malformed/streamed JSON, session continuation, and sandbox-boundary failures.**

2. **The direct branch is lower-risk first because it is the production path today; migrate the dispatcher flag path only after the omp adapter contract is proven.**

3. **`omp:deepseek:...` should classify as `deepseek` for fallback independence, while unqualified omp models classify as `omp`; transport and upstream provider must be recorded separately.**

4. **Yes: at minimum `orchestration/parallel_critique.py`, `cloud/wrappers/arnold-repair-loop`, `cloud/wrappers/arnold-watchdog`, Hermes launcher tests, and Hermes-specific worker tests are outside the summarized inventory.**

5. **Wrap omp in an enforceable OS/tool boundary and reject unsandboxed `--yolo` for execute; approval bypass is not filesystem isolation.**

6. **Keep Python-side hot-context composition and treat omp as stateless per turn initially; promote persistent omp sessions only after replay tests prove no duplication, stale context, or resume drift.**

7. **The OmpAdapter should own one centralized RPC-event-to-neutral-`TokenUsage`/`CostUsage` mapper, with costing remaining the consumer-facing SSoT.**

8. **Port every test asserting Arnold contracts through a fake RPC server plus one live smoke corpus, and delete only tests asserting Hermes implementation internals.**

## 3. Highest-value exploration

1. **Exhaustive consumer census** — *Question:* what still imports or launches Hermes? *Confidence-up:* zero executable references after classifying intentional historical docs; *down:* any production launcher, CI, systemd, deploy, or sibling-repo hit. *Look:* `rg` across Arnold, `.github`, `agentbox`, cloud wrappers, sibling repos, systemd templates, tests. *Cheapest:* static scan plus process-string scan of deployment scripts.

2. **Complete phase dispatch matrix** — *Question:* does every phase route `omp` through availability, model resolution, direct dispatch, dispatcher mode, worker fanout, and loop phases? *Up:* tests exercising each branch; *down:* any agent-name allowlist or fallback path omitting omp. *Look:* `_impl.py`, `_core/io.py`, `worker_fanout.py`, `parallel_critique.py`, profiles/policy, CLI compatibility. *Cheapest:* static matrix followed by unit tests.

3. **Security delta experiment** — *Question:* can omp execute/write outside the intended plan worktree? *Up:* adversarial prompt tests show hard rejection under the chosen sandbox; *down:* `cd`, symlink, absolute-path, `/tmp`, `.git`, or child-process escapes. *Look:* `runtime/sandbox.py`, omp approval/security code, wrapper argv. *Cheapest:* fake RPC plus a tiny real canary; no full plan required.

4. **Real structured-output corpus** — *Question:* does omp RPC reliably produce payloads accepted by `capture_step_output` for plan, critique, gate, execute, review, and repair? *Up:* repeated valid outputs and correct rejection/repair of malformed outputs; *down:* prose contamination, truncation, schema dialect failures, or tool traces leaking into final text. *Look:* `model_seam.py`, `schemas.py`, omp `outputSchema` implementation. *Cheapest:* one live small-model run per phase with recorded prompts.

5. **Timeout/recovery/fallback test** — *Question:* do RPC abort, process-group kill, retry classification, and session cleanup behave like current workers? *Up:* injected hangs/503/partial output produce one bounded retry and correct evidence; *down:* orphaned omp children, duplicate execute, or fallback on schema/auth errors. *Look:* `_impl.py`, `fallback_chains.py`, resident timeout code, omp RPC client. *Cheapest:* fake server that hangs, emits malformed JSON, then succeeds.

6. **Fallback-family proof** — *Question:* do `omp:` chains preserve cross-provider rules and telemetry? *Up:* table-driven tests for `omp:deepseek`, `omp:claude`, direct Hermes equivalents, and unknown registry models; *down:* same upstream provider is incorrectly retried or independent providers are blocked. *Look:* `fallback_chains.py:308`, routing/parser tests, omp model registry. *Cheapest:* static implementation plus unit tests.

7. **Resident hot-context equivalence** — *Question:* does a resumed omp session preserve exactly the intended conversation, ancestry, tool policy, and context tree? *Up:* N-turn replay matches current runner artifacts; *down:* duplicate hot context, wrong session identity, or stale conversation state. *Look:* resident runtime/store, `agent_loop.py`, `provider_runtime.py`, omp session docs/events. *Cheapest:* deterministic fake provider, then one staging Discord turn.

8. **Cost telemetry mapping** — *Question:* which omp events contain prompt/completion/cache/tool usage and costs? *Up:* totals reconcile with provider billing/test fixtures; *down:* missing usage, double counting, or zero-cost successful runs. *Look:* omp RPC event schemas, `arnold/agent/costing`, execution hooks, manifests. *Cheapest:* capture one RPC transcript and write a reconciliation script.

9. **Cloud/deployment closure** — *Question:* can every phase/resident/repair host invoke the pinned editable omp build? *Up:* reproducible image/bootstrap check on agentbox and Hetzner; *down:* missing Bun, natives mismatch, PATH/session-dir permissions, or watchdog blindness. *Look:* cloud Dockerfiles/templates, `entrypoint.sh.tmpl`, systemd, runtime manifests, wrapper tests. *Cheapest:* static dependency census, then one remote smoke launch.

10. **Deletion graph and test classification** — *Question:* what can actually be removed without breaking neutral surfaces? *Up:* import graph clean after relocating sandbox/key-pool and migrating legacy critique; *down:* runtime imports or contract tests still depend on Hermes modules. *Look:* `arnold/agent`, `pytest` collection, packaging metadata, docs/configuration. *Cheapest:* import graph plus `pytest --collect-only`.

## 4. Single highest-risk unknown

**Can omp provide a bounded, sandbox-equivalent, schema-valid, timeout-recoverable phase execution contract without unsafe side effects?**

Highly confident means adversarial sandbox tests, representative live phase prompts, injected RPC failures, and repeated bakeoff runs all pass with no orphan processes, wrong-tree writes, schema regressions, or telemetry gaps.
