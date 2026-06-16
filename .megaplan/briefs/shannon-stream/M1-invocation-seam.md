# M1: The invocation seam — `run_step -> WorkerResult` hosts all three engines

**Milestone id:** `M1-invocation-seam` · **Profile:** `partnered` · **Robustness:** `full` · **Depth:** `high` · **Vendor:** `codex` · **Repo:** megaplan (this repo)

Read `00-OVERVIEW.md` for the epic context + the five epic-wide invariants. This milestone is
**behavior-preserving**; the green suite is the backstop.

## Outcome
A single uniform interface — `run_step(step, state, dir) -> WorkerResult` — through which Hermes, Codex,
and Shannon are dispatched, with **zero behavior change** and the full suite green. The `WorkerResult`
contract is the artifact M2–M4 build on, extended with a typed optional **`rate_limit`** field so the
later cap/visibility reads the rate signal through the interface, never a Shannon backchannel.

## Scope
**IN:** formalize/clean the existing dispatch (`run_step_with_worker`) as the adapter seam; add
`rate_limit: dict | None` to `WorkerResult` (Shannon will populate it in M2; Hermes/Codex leave it
`None`); audit every caller (gate, critique, review, chain, receipts, observability) to confirm they
consume only neutral fields; add a one-shot regression characterizing today's dispatch outputs.
**OUT:** the new stream-json worker (M2); any concurrency/governor work (M3); any behavior change.

## Locked decisions
- The contract is an **interface, not a transport** — engines keep their native paths; nothing is forced
  through a file handshake. (Hermes = HTTP, Codex = `codex exec`, Shannon = tmux today / stream-json in M2.)
- `rate_limit` is a **typed optional field on `WorkerResult`**, not a side-channel.
- The **retry path is the ONLY place allowed to branch on worker kind** (Shannon self-cleans its
  session; Codex records the stale session explicitly). A future engine must self-clean like Shannon, not
  grow a third retry arm. Add a comment marking this as a deliberate, contained concession.
- `session_id` stays an **opaque string**; no cross-engine session-migration logic.
- Behavior-preserving: identical outputs on all three engines pre/post.

## Open questions (planner resolves)
- Is `shannon_plan` (the one engine-branded `WorkerResult` field) ever branched-on by a caller to infer
  worker kind? If so, neutralize the inference; the field name may stay if treated as opaque.
- Does the **observability vendor-classifier** (re-derives `claude`/`codex`/`deepseek` from model-name
  substrings) sit outside the execution seam? Confirm it is reporting-only and that nothing in the
  execution/admission path infers vendor from a model name.

## Constraints
- **Zero behavior change** — this is a refactor. If any phase's output shifts, it's a bug.
- Topological care: this reshapes a **shared contract** many callers depend on (the premium-planner
  rationale). No circular imports; the suite must still *collect*.
- Epic invariants apply (additive, vendor codex, keep tmux, OS-user boundary).

## Done criteria
- Full test suite green, byte-identical dispatch behavior for Hermes + Codex (characterization test).
- `WorkerResult.rate_limit` exists, typed, defaulting `None`, populated by no engine yet.
- A documented map of every `WorkerResult` consumer showing it reads only neutral fields.
- The retry-path engine-branch is the single audited exception, commented as such.

## Touchpoints
`megaplan/workers/_impl.py` (`run_step_with_worker` ~3157, `WorkerResult` ~412, `_extract_claude_usage`),
`megaplan/workers/shannon.py`, `megaplan/workers/hermes.py`, `megaplan/handlers/*` (gate/critique/review/
shared/execute/override), `megaplan/receipts/__init__.py`, `megaplan/observability/cost.py`.

## Rubric
Must: zero behavior change (suite green + characterization), `rate_limit` field added, consumer audit
done, retry-branch is the sole engine-aware spot. Should: the deliberate-concession comment; vendor-
classifier confirmed reporting-only.
