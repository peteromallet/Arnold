# Resident managed-agent provider parity

This matrix is the acceptance contract for resident-managed Codex, Hermes,
and Claude runs. “Shared” means the resident owns identical durable semantics;
the upstream transport may still differ. Provider streams are deliberately not
described as byte-identical: `provider.raw` preserves the exact provider stdout,
while `events.jsonl` is the provider-neutral projection.

| Managed feature | Codex | Hermes (GLM 5.2 and other Hermes routes) | Claude | Contract / evidence |
|---|---|---|---|---|
| Model/provider routing | Native | Native | Native | Resolver rejects explicit mismatches before a run directory is created. |
| Detached managed supervisor | Shared | Shared | Shared | One manifest-bound worker process and PID custody. |
| `prompt.md`, `result.md`, `run.log`, `manifest.json` | Shared | Shared | Shared | Files are committed before provider start; result is separate from diagnostics. |
| Provider raw stdout | Codex CLI JSONL | Hermes launcher final-response stream | Claude CLI stream-JSON | Byte-exact `provider.raw`; the raw-stream kind is recorded in the manifest. |
| Normalized telemetry | Shared | Shared | Shared | `events.jsonl`, schema `arnold-managed-provider-event-v1`, preserves session/tool/turn/process evidence without claiming identical upstream events. |
| Durable session identity | CLI-emitted UUID | Resident-reserved Hermes ID, confirmed by launcher metadata | Resident-reserved UUID, confirmed by Claude stream | `model_session` is committed and provider-validated. |
| Session persistence | Codex session store | Hermes SQLite `SessionDB` | Claude CLI persistence | No provider is launched ephemerally or with Claude’s `--no-session-persistence`. |
| Terminal follow-up | `codex exec resume` | Same `SessionDB` ID plus hydrated conversation history | `claude --resume <uuid>` | A child continuation manifest retains parent and lineage custody. |
| Active follow-up | Exact supervisor interrupt, then resume | Same | Same | Interrupt occurs only after unique session and supervisor identity checks. |
| Missing/ambiguous session | Fail closed | Fail closed | Fail closed | No “continue latest” guessing. Cross-provider lineages are rejected. |
| Generic tool policy | Full `file,web,terminal` only | Native toolset filter | Exact built-in tool map (`Read/Edit/Write/Glob/Grep`, `WebFetch/WebSearch`, `Bash`) | Unknown toolsets fail. A narrowed Codex policy fails truthfully because the installed CLI has no equivalent allow-list. |
| Output-token control | Upstream model-managed; recorded as such | Native `max_tokens` request cap | `CLAUDE_CODE_MAX_OUTPUT_TOKENS` | Requested value and enforcement mode are recorded; no unsupported Codex flag is fabricated. |
| Provider timeout | Supervisor-enforced | Supervisor-enforced | Launcher and supervisor-enforced | Timeout is passed/used consistently and terminal return code 124 is captured. |
| Reasoning/effort | Codex config | Provider/model behavior (recorded; no invented flag) | Claude `--effort` | Capability differences are explicit in argv and manifest evidence. |
| Working directory | Shared | Shared | Shared | Exact resolved project directory. |
| Tool execution authority | `danger-full-access` | Inherited machine access | Claude permission policy (`auto` as root, bypass mode otherwise) | Effective policy is recorded; no silent widening beyond the provider adapter. |
| Launch idempotency | Shared | Shared | Shared | Provider, model, effort, tools, token cap, and timeout are part of the key. |
| Immutable request provenance and custody | Shared | Shared | Shared | Discord source envelope, correlation/custody IDs, and query relationship are provider-neutral. |
| Queue/dependency and synthesis ownership | Shared | Shared | Shared | Existing managed queue and aggregation machinery is unchanged. |
| Lifecycle/status/history | Shared | Shared | Shared | Launching/running/completed/failed/interrupted and delivery/request projections. |
| Completion delivery | Shared | Shared | Shared | One synthesis owner and existing resident completion-delivery contract. |
| Empty-success handling | Fail | Fail | Fail | A zero exit without a final provider result cannot become completed. |
| Provider/auth/process failure capture | Shared | Shared | Shared | Category, message, return code, raw/log paths, timestamps, and terminal lifecycle are durable. |
| Usage evidence | Codex turn usage when emitted | Hermes launcher metadata | Claude result usage | Stored in normalized events and manifest telemetry; missing upstream fields are not fabricated. |
| Backward managed-v2 reads | Shared | Shared | Shared | Legacy manifests receive additive default evidence paths/session reservation at worker time. |

The executable characterization is in
`tests/resident/test_provider_runtime.py`,
`tests/resident/test_provider_aware_launch.py`, and
`tests/resident/test_subagent_followup.py`. Live smoke success is required only
when credentials exist. An installed but unauthenticated Claude CLI must produce
an `authentication_failed` terminal receipt and must not be reported as a
successful Claude end-to-end run.
