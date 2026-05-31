# Session-cache fix — kill cross-iteration cache-replay in non-execute phases

## Goal

Implement the architectural fix proposed in ticket `01KRXNZZGRV17PHZRJ2Q56SPS3`: **persistence is within-call, never across-call; only `execute` keeps cross-call session persistence.** Every other phase (plan, prep, critique, gate, revise, finalize, review) starts a truly fresh session each invocation.

This kills the silent cache-replay failure mode that just burned ~$600 on Sprint B's stuck rework loop. The bug class is cross-vendor (shannon, codex, hermes). The fix needs to break the cache at multiple levels because we have proof that flipping a single flag is insufficient.

## Authoritative spec

**Ticket `01KRXNZZGRV17PHZRJ2Q56SPS3` at `.megaplan/tickets/01KRXNZZGRV17PHZRJ2Q56SPS3-cross-iteration-session-persistence-causes-silent-cache-hit-no-ops-in-revise-and.md` is the spec. Read it first.** It has:

- Original symptom + receipt evidence
- Root cause (`session_key_for` shares `{agent}_planner` across plan + revise)
- Cross-vendor scope analysis (shannon, codex, hermes all affected via `session_key_for`)
- Settled architectural conclusion (within-call only; execute is the exception)
- Proposed fix with two equivalent implementations
- Trade-offs (token / latency / debugging)
- Sprint B re-repro evidence with critical addendum: **`fresh=True` at the worker function level is NOT enough under `megaplan auto`.** Shannon's tmux pane survives flag flips. The CLI `--fresh` workaround likely tears down the pane via side effects that the worker-function flag doesn't replicate.

This brief does not re-derive the ticket; it locks the implementation scope.

## Locked decisions (do not re-debate)

### Scope

1. **Within-call-only persistence for: plan, prep, critique, gate, revise, finalize, review.** Each invocation starts a brand-new session/tmux-pane/process. Execute keeps its current behavior.
2. **Cross-vendor implementation.** All three worker backends — `workers/shannon.py`, `workers/_impl.py` (codex), `workers/hermes.py` — need to honor this rule. Don't fix just one.
3. **Three layers of defense are required** (Sprint B repro proved that one flag flip is insufficient):
   - **(a) Architectural flag:** dispatch layer in `workers/_impl.py:run_step_with_worker` passes `fresh=True` unconditionally for non-execute phases, OR `session_key_for` returns a fresh UUID-keyed entry per call for non-execute phases. Pick one and document why.
   - **(b) Backend-level enforcement:** the actual mechanism must break the cache.
     - Shannon: tear down the bun shannon process / tmux pane before non-execute invocations, OR route through Shannon's ephemeral mode if available, OR use `claude -p` print mode directly (no tmux). Renaming the prompt file per iteration (`revise_v{N}_shannon_prompt.txt`) is necessary as a belt-and-suspenders measure.
     - Codex: ensure `codex exec resume <session>` is not invoked for non-execute phases — spawn a new codex session each call.
     - Hermes: ensure the in-process conversation history is reset between non-execute phase calls.
   - **(c) No-op detector** at `_write_plan_version` in `megaplan/handlers/shared.py`: if `sha256(new_plan_text)` equals the prior version's hash, raise `cache_hit_suspected` with diagnostic fields (session_id reuse, identical token counts, prompt_hash_canonical comparison). Auto-driver surfaces the error rather than silently spinning.
4. **`feedback` phase exemption.** The `feedback` phase scaffolds a per-stage ratings template; it doesn't model-call. Whether it gets fresh-each-call treatment is irrelevant — leave its behavior unchanged.

### Out of scope

1. **Do NOT fix the dotenv re-injection bug** (`ANTHROPIC_API_KEY` empty-string trick) mentioned at the end of the ticket. Separate ticket, separate PR. Adjacent code, independent bug.
2. **Do NOT touch execute's session handling.** Execute is the documented exception. Within-call persistence is correct there (the worker's own multi-turn tool-calling loop needs it).
3. **Do NOT redesign `session_key_for`** beyond what the architectural rule requires. If implementation path (1) (dispatch flag flip) is chosen, leave `session_key_for` as is. If path (2) is chosen (UUID-keyed entries for non-execute), minimal change only.
4. **Do NOT add a per-run cost cap (`--max-cost-usd`)** as part of this fix. That's a different conversation and a default-on cap would be hedging. The no-op detector is the right safety net for THIS bug.

## Done criteria

1. **Regression test passes** (load-bearing acceptance criterion):
   - A standard-robustness mock-mode plan that triggers ≥3 revise iterations.
   - Assert consecutive `plan_v{N}.md` files have **different** sha256 hashes.
   - Assert `step_receipt_revise_v*.json` files do NOT share identical `(prompt_tokens, completion_tokens, session_id)` triples.
   - Assert `session_id` differs between iterations for plan, revise, critique, gate, review.
   - Test runs in CI on every PR touching `workers/` or `handlers/shared.py`.
2. **Real-model repro** on Sprint B's brief: run `megaplan init .megaplan/briefs/yaml-pipelines-sprint-b.md` to at least one revise iteration. Inspect: consecutive plan hashes differ AND no `(prompt_tokens, completion_tokens, session_id)` triples are identical across iterations. (Cost ceiling for this verification: ≤$15. If revise's first call costs more than that, abort — something else is wrong.)
3. **No-op detector verified** by an integration test that monkeypatches the worker to return the SAME payload on consecutive calls. Assert `_write_plan_version` raises `cache_hit_suspected` with the expected diagnostic structure.
4. **Per-phase cost sanity guard**: revise on any tier never exceeds $5 per call. If a real run breaches it, abort the phase with a structured error referencing this ticket. Validated by an integration test that forces a high-cost worker response.
5. **Both flag-and-implementation layers committed.** A test that mocks the underlying backend cache (e.g. patches Shannon to ignore `--session-id`) and verifies the no-op detector catches the failure. Defense in depth.
6. **Ticket `01KRXNZZGRV17PHZRJ2Q56SPS3` closed** with a closing note linking to the merged PR(s).

## Touchpoints

- `megaplan/workers/_impl.py` — `session_key_for` (line ~1766), `resolve_agent_mode` (line ~2301), `run_step_with_worker` (line ~2409). Cross-vendor dispatch.
- `megaplan/workers/shannon.py` — `run_shannon_step` (line ~818). Tmux-pane teardown OR ephemeral-mode plumbing OR claude-print-mode route.
- `megaplan/workers/hermes.py` — hermes session resume logic.
- `megaplan/handlers/shared.py` — `_write_plan_version` (line ~396) for the no-op detector.
- `megaplan/handlers/critique.py` — `handle_revise` (line ~205) for the per-phase cost guard or surfacing the no-op error cleanly.
- Tests under `tests/workers/`, `tests/handlers/`, `tests/integration/`.
- Documentation: `docs/megaplan-decision.md` or `docs/observability-and-introspection-design.md` should mention the new safety nets.

## Anti-scope

- Don't redesign the `auto` driver. The fix is at the worker layer.
- Don't touch `parallel_critique.py` or any pipeline code.
- Don't migrate any prompts.
- Don't change profile TOMLs.
- Don't fix the dotenv re-injection issue (separate ticket).
- Don't add new flags to `megaplan` CLI unless absolutely required to wire the no-op detector's diagnostic output.

## Constraints

- Implementation under ~400 LOC of net new + changed code (excluding tests). If it grows past that, you're probably over-engineering.
- All three worker backends MUST be in scope. Don't ship a shannon-only fix and call it done.
- The CLI surface (`megaplan plan/prep/critique/gate/revise/finalize/review/execute`) stays unchanged. Behavior under the hood changes; user-visible behavior changes only insofar as the cache bug stops happening.
- No changes to existing test inputs or fixtures except where the fix changes recorded behavior.

## Profile recommendation for this sprint

`all-codex` profile + `--depth high` + `--robustness thorough`. Rationale:

- The bug primarily expresses in Shannon (`workers/shannon.py`). Routing every phase through Codex avoids the broken backend while we fix it. Sprint B evidence: `codex_critic` ran real generations every iteration (prompt tokens grew monotonically, varied artifact hashes). The Shannon-path was the failure surface.
- `--robustness thorough` because this is load-bearing infrastructure (session machinery every phase relies on). 8 critique checks + parallel critique. Regression here corrupts every future megaplan run.
- `--depth high` because the implementation path is non-obvious — author phases need real deliberation on the tmux-teardown vs ephemeral-mode vs print-mode trade-off and on the no-op-detector shape.
- `--with-feedback` to get a per-phase ratings template — we want a record of how each phase performed for this run so we can route future bug-fix work intelligently.
- `--in-worktree session-cache-fix --worktree-from sprint-a-base` — own worktree, doesn't disturb Sprint B (parked) or main.

CLI:

```bash
megaplan init .megaplan/briefs/session-cache-fix.md \
  --profile all-codex \
  --depth high \
  --robustness thorough \
  --with-feedback \
  --auto-start --auto-approve \
  --in-worktree session-cache-fix \
  --worktree-from sprint-a-base \
  --name session-cache-fix
```

**Meta-note about dogfooding**: this megaplan is fixing the bug it might itself encounter. Run it through codex (where the bug is mild or non-triggering) to dodge the recursion. If revise on codex DOES hit a cache-replay anyway, the no-op detector we're shipping will catch it — and that's actually a clean smoke test for the detector.
